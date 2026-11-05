# Copyright (c) 2026, Target Zenit
"""MIJOZ UCHUN HISOB-KITOB HISOBOTI (PDF).

Maqsad: sotuv menejeri ota-onaga yuboradigan bitta hujjat — "qancha
hisoblandi, qancha to'ladingiz, qaysi oy uchun, qancha qoldi". Telefonda
og'zaki tushuntirish o'rniga havola yoki fayl tashlanadi.

NEGA HTML -> PDF (reportlab emas): bu hujjat MIJOZ uchun, ya'ni ko'rinishi
muhim. `pdf_engine/` dagi reportlab chizuvchisi buxgalteriya hisobotlari
uchun (P&L, balans) — koordinata bilan chiziladi va dizaynni o'zgartirish
qimmat. Jinja + CSS esa shablonni tahrirlashni oson qiladi.

QOIDA: bu modul HECH NARSA HISOBLAMAYDI. Hamma son `engine.plan_xulosa` va
`engine.get_payments` dan keladi — ya'ni panelda ko'rinadigan sonlar bilan
AYNAN bir xil. Aks holda mijozga yuborilgan hujjat panel bilan farq qilib,
ishonchni yo'qotardi.
"""

from __future__ import annotations

from functools import lru_cache

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate, now_datetime, nowdate

from target_zenit.qarzdorlik import engine

SHABLON = "target_zenit/templates/includes/qarzdorlik_hisobot.html"

# Maktab logotipi. PDF'ga data-URI bo'lib SINGDIRILADI, havola sifatida emas:
# wkhtmltopdf sahifani alohida jarayonda chizadi va `/assets/...` havolasini
# olish uchun saytga qaytib so'rov yuborishi kerak bo'lardi (login talab
# qilinadigan sahifada u bo'sh kvadrat bo'lib chiqadi). Singdirilgan rasm
# har doim ko'rinadi va PDF o'zi bilan ketadi.
LOGO = "target_zenit/public/images/target_logo.png"

OYLAR_UZ = {
	1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May", 6: "Iyun",
	7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}


@lru_cache(maxsize=1)
def logo_uri() -> str:
	"""Logotipning data-URI ko'rinishi (bir marta o'qiladi, keshlanadi).

	Fayl topilmasa bo'sh satr — shablon unda matnli sarlavhaga qaytadi,
	hisobot chiqmay qolmaydi."""
	import base64
	import os

	yol = os.path.join(frappe.get_app_path("target_zenit"), "public", "images",
	                   "target_logo.png")
	if not os.path.exists(yol):
		return ""
	with open(yol, "rb") as f:
		return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def son(qiymat) -> str:
	"""1234567.0 -> "1 234 567". Mijoz o'qiydigan hujjatda tiyin keraksiz."""
	# `round()` butun son qaytaradi — qo'shimcha `int()` ortiqcha (ruff RUF046)
	n = round(flt(qiymat))
	belgi = "−" if n < 0 else ""
	return belgi + f"{abs(n):,}".replace(",", " ")


def sana(qiymat) -> str:
	if not qiymat:
		return "—"
	d = getdate(qiymat)
	return f"{d.day:02d}.{d.month:02d}.{d.year}"


def oy_nomi(label) -> str:
	"""«2026-09» -> «Sentabr 2026». Reja qatorlari shu formatda keladi."""
	s = str(label or "").strip()
	if len(s) >= 7 and s[4] == "-" and s[:4].isdigit() and s[5:7].isdigit():
		oy = int(s[5:7])
		return f"{OYLAR_UZ.get(oy, s[5:7])} {s[:4]}"
	return s or "—"


# ============================================================== ma'lumot
def malumot(case: str) -> dict:
	"""Hisobot uchun hamma ma'lumot. Panel bilan bir manbadan."""
	qi = frappe.get_doc("Qarz Ishi", case)

	from target_zenit.target_zenit.page.qarzdorlik.qarzdorlik import _student_live

	jonli = _student_live([qi.student]).get(qi.student) or frappe._dict()
	oquvchi = {
		"ism": jonli.get("student_name") or qi.student_name,
		"sinf": jonli.get("sinf") or qi.sinf or "",
		"tolovchi": jonli.get("payer_name") or qi.payer_name or "",
		"telefon": jonli.get("payer_phone") or qi.payer_phone or "",
		"id": qi.student,
	}

	xulosa, oylar, tolovlar, davr = None, [], [], None
	if qi.tolov_rejasi:
		tr = frappe.get_doc("Tolov Rejasi", qi.tolov_rejasi)
		xulosa = engine.plan_xulosa(tr)
		oylar = xulosa["oylar"]
		davr = engine._plan_payment_window(tr)
		tolovlar = engine.get_payments(tr.customer, davr)
		oquvchi["oquv_yili"] = tr.academic_year or ""

	# "Qaysi oy uchun to'ladi" — to'lovning nachisleniyalarga taqsimoti
	_taqsimot_biriktir(tolovlar)

	# To'lovlar: yangisi tepada — mijoz oxirgi to'lovini birinchi ko'radi
	tolovlar = sorted(tolovlar, key=lambda p: str(p["posting_date"]), reverse=True)

	kompaniya = frappe.defaults.get_user_default("Company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	return {
		"case": qi.name,
		"oquvchi": oquvchi,
		"xulosa": xulosa,
		"oylar": oylar,
		"tolovlar": tolovlar,
		"davr": davr,
		"kompaniya": kompaniya,
		"sana": nowdate(),
		"tayyorlagan": frappe.db.get_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
	}


def _usul(p: dict) -> str:
	"""Mijoz tushunadigan to'lov usuli.

	`Journal Entry` — buxgalteriya atamasi, ota-onaga hech narsa demaydi.
	Bunday yozuv odatda bank o'tkazmasi yoki o'zaro hisob-kitob bo'ladi,
	shuning uchun neytral «O'tkazma» deyiladi — ikkalasi uchun ham to'g'ri."""
	usul = (p.get("mode_of_payment") or "").strip()
	if not usul or usul.lower() in ("journal entry", "journal voucher"):
		return "O'tkazma" if p["doctype"] == "Journal Entry" else "—"
	return usul


def _taqsimot_biriktir(tolovlar) -> None:
	"""Har to'lovga «qaysi oy uchun» taqsimotini qo'shadi.

	MANBA TANLOVI: `Payment Entry Reference` -> `Sales Invoice.custom_payment_month`.
	Bu — buxgalteriyaning HAQIQATI: to'lov aynan qaysi nachisleniyaga
	yozilgani. `Kassa.payment_month` ("За какой месяц") ham bor, lekin u
	3323 kassadan faqat 567 tasida to'ldirilgan (2026-11-05 tekshiruvi),
	ya'ni yagona manba qilib bo'lmaydi — u ZAXIRA sifatida ishlatiladi.

	Bitta to'lov bir nechta oyga bo'linishi mumkin (ota-ona ikki oyni birga
	to'laydi) — shuning uchun qator ro'yxat bo'lib keladi. Taqsimlanmagan
	qoldiq AVANS: u kelgusi nachisleniyaga o'tadi va shunday ko'rsatiladi."""
	pe_nomlar = [p["name"] for p in tolovlar if p["doctype"] == "Payment Entry"]
	taqsim: dict[str, list] = {}
	if pe_nomlar:
		for r in frappe.db.sql(
			"""SELECT per.parent pe, per.allocated_amount summa,
			          si.custom_payment_month oy, si.posting_date
			   FROM `tabPayment Entry Reference` per
			   JOIN `tabSales Invoice` si ON si.name = per.reference_name
			   WHERE per.docstatus = 1 AND per.reference_doctype = 'Sales Invoice'
			     AND per.parent IN %(nomlar)s
			   ORDER BY si.posting_date""",
			{"nomlar": tuple(pe_nomlar)},
			as_dict=True,
		):
			# Oy ko'rsatilmagan hisob-faktura uchun hujjat sanasidan olamiz —
			# nachisleniya o'sha oyga tegishli
			oy = r.oy or (str(r.posting_date)[:7] if r.posting_date else None)
			taqsim.setdefault(r.pe, []).append({"oy": oy, "summa": flt(r.summa)})

	for p in tolovlar:
		qatorlar = taqsim.get(p["name"]) or []
		# Bir xil oyga bir nechta hisob-faktura bo'lsa qo'shib ko'rsatamiz:
		# mijozga "Sentabr: 1 800 000" yetarli, hujjat nomlari keraksiz
		yigma: dict = {}
		for q in qatorlar:
			yigma[q["oy"]] = yigma.get(q["oy"], 0.0) + q["summa"]
		p["taqsimot"] = [
			{"oy": oy, "summa": summa}
			for oy, summa in sorted(yigma.items(), key=lambda x: str(x[0] or ""))
		]
		# Zaxira: taqsimot bo'lmasa kassadagi oy
		if not p["taqsimot"] and p.get("kassa_oy"):
			p["taqsimot"] = [{"oy": p["kassa_oy"], "summa": abs(flt(p["amount_uzs"]))}]
		p["taqsimlangan"] = sum(x["summa"] for x in p["taqsimot"])

		# DIQQAT: taqsimot yo'qligi "avans" degani EMAS. Journal Entry bilan
		# yozilgan to'lovda `Payment Entry Reference` umuman bo'lmaydi, lekin
		# qarz mexanizmi uni oylarga baribir yozadi — oylar jadvali "To'landi"
		# deb turganda to'lovlar ro'yxatida "avans" yozish mijozga ochiq
		# ziddiyat ko'rsatardi (2026-11-05 da shu nuqson topildi). Shuning
		# uchun bu yerda HECH QANDAY taxmin qilinmaydi: ma'lum bo'lsa oy
		# yoziladi, bo'lmasa chiziqcha. Avansning haqiqiy summasi esa
		# rejaning o'zidan (`xulosa.jami.avans`) olinadi va yakunda alohida
		# qator bo'lib ko'rsatiladi.
		p["usul"] = _usul(p)


# ================================================================== PDF
def html(case: str) -> str:
	"""Shablonni to'ldiradi (PDF ham, brauzerda ko'rish ham shundan)."""
	d = malumot(case)
	return frappe.render_template(SHABLON, {
		**d,
		"son": son,
		"sana_f": sana,
		"oy_nomi": oy_nomi,
		"logo": logo_uri(),
	})


@frappe.whitelist()
def korish(case: str):
	"""Brauzerda ko'rish — PDF yasashdan oldin tekshirish uchun."""
	from target_zenit.target_zenit.page.qarzdorlik.qarzdorlik import _guard

	_guard()
	frappe.response["type"] = "page"
	frappe.response["page_name"] = "qarzdorlik_hisobot"
	frappe.response["data"] = html(case)
	return html(case)


@frappe.whitelist()
def pdf(case: str) -> dict:
	"""PDF yasab private File sifatida saqlaydi va havolasini qaytaradi.

	Fayl nomi o'quvchi ismi bilan: menejer telefonida bir nechta hisobot
	yotganda qaysi biri kimga tegishli ekani ko'rinib turishi kerak."""
	from target_zenit.target_zenit.page.qarzdorlik.qarzdorlik import _guard

	_guard()
	d = malumot(case)
	kontent = frappe.render_template(SHABLON, {
		**d, "son": son, "sana_f": sana, "oy_nomi": oy_nomi, "logo": logo_uri(),
	})

	from frappe.utils.pdf import get_pdf

	baytlar = get_pdf(kontent, options={
		"page-size": "A4",
		"margin-top": "12mm",
		"margin-bottom": "14mm",
		"margin-left": "10mm",
		"margin-right": "10mm",
		"encoding": "UTF-8",
		# Mijozga ketadigan hujjatda brauzer sarlavhasi/URL'i turmasligi kerak
		"no-outline": None,
		"disable-smart-shrinking": None,
	})

	nom = _fayl_nomi(d)
	return {"file_url": _saqla(baytlar, nom, case), "file_name": nom}


def _fayl_nomi(d: dict) -> str:
	"""«Hisob-kitob_Baxtiyorov-Muxammadjon_05-11-2026.pdf»"""
	import re

	ism = re.sub(r"[^\w\s-]", "", str(d["oquvchi"]["ism"] or d["case"]), flags=re.U)
	ism = re.sub(r"\s+", "-", ism.strip())[:60] or d["case"]
	kun = sana(d["sana"]).replace(".", "-")
	return f"Hisob-kitob_{ism}_{kun}.pdf"


def _saqla(baytlar: bytes, nom: str, case: str | None = None) -> str:
	"""Private File sifatida saqlaydi.

	Eski nusxa avval o'chiriladi — aks holda Frappe nomga tasodifiy suffiks
	qo'shadi va menejer har bosishda yangi fayl to'plab qolardi
	(`api/report_common.save_private_file` dagi bilan bir xil tuzoq)."""
	import os

	stem = nom.rsplit(".", 1)[0]
	for name in frappe.get_all(
		"File", filters={"file_name": ["like", f"{stem}%"]}, pluck="name"
	):
		frappe.delete_doc("File", name, ignore_permissions=True, delete_permanently=True)
	yol = frappe.get_site_path("private", "files", nom)
	if os.path.exists(yol):
		os.remove(yol)

	doc = frappe.get_doc({
		"doctype": "File",
		"file_name": nom,
		"is_private": 1,
		"folder": "Home/Attachments",
		"content": baytlar,
		# Ishga biriktiramiz: hisobot kimga yuborilgani hujjat tarixida qoladi
		"attached_to_doctype": "Qarz Ishi" if case else None,
		"attached_to_name": case or None,
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.file_url
