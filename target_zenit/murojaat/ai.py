# Copyright (c) 2026, Target Zenit
"""AI qo'ng'iroq tahlilidan avtomatik murojaat ochish.

Manba — `telefoniya/analiz.py` promptidagi majburiy qatorlar:
    TAKLIF VA SHIKOYAT: <ota-onaning MAKTAB haqidagi gapi>
    MUROJAAT TURI:      <Shikoyat / Taklif / Muammo / So'rov / yo'q>
    DIQQAT:             <rahbar bilishi shart bo'lgan narsa>

Qaror (2026-11-04): AI topgan murojaat TO'G'RIDAN-TO'G'RI rahbar paneliga
tushadi — oraliq tasdiq yo'q. Shuning uchun ikki himoya qo'yilgan:
  1) yo'nalish AI'ning MUROJAAT YO'NALISHI qatoridan keladi (o'quv -> Direktor,
     tashkiliy -> CEO), aniq kategoriya esa kalit so'z bo'yicha topiladi.
     Ikkisi zid kelsa AI yo'nalishi ustun: aniq kategoriya emas, «Aniqlanmagan
     - o'quv/tashkiliy» qo'yiladi — murojaat noto'g'ri rahbarga ketmaydi, lekin
     egasiz ham qolmaydi;
  2) rahbarda «Ahamiyatsiz» qarori bor — AI xato o'qigan bo'lsa bir bosishda
     yopiladi, ota-onaga qo'ng'iroq qilish talab qilinmaydi.

Idempotent: bitta qo'ng'iroqdan bitta murojaat (`telefon_qongirogi` bo'yicha
tekshiradi) — qayta tahlil qilinsa dublikat ochilmaydi.
"""

from __future__ import annotations

import re

import frappe
from frappe.utils import cint

from target_zenit.murojaat import api

TAKLIF_KALITLAR = ("TAKLIF VA SHIKOYAT", "MIJOZ TAKLIFI")
BOSH_QIYMATLAR = ("taklif yo'q", "taklif yoq", "shikoyat yo'q", "yo'q", "yoq",
                  "-", "—", "", "aniqlanmadi", "none")
TURLAR = ("Shikoyat", "Taklif", "Muammo", "So'rov")

# AI aytgan yo'nalish -> murojaat yo'nalishi (rol)
YONALISH_MAP = {"o'quv": "Direktor", "oquv": "Direktor", "tashkiliy": "CEO"}
ZAXIRA_KAT = {"Direktor": "Aniqlanmagan - o'quv", "CEO": "Aniqlanmagan - tashkiliy"}
MIN_UZUNLIK = 12      # "yo'q" ga yaqin qisqa javoblarni tashlaymiz


def _qator(xulosa: str | None, kalit: str) -> str:
	for q in str(xulosa or "").splitlines():
		q = q.strip()
		if q.upper().startswith(kalit.upper() + ":"):
			return q[len(kalit) + 1:].strip()
	return ""


def _bosh(matn: str) -> bool:
	return (matn or "").strip().lower() in BOSH_QIYMATLAR


def taklif_matni(xulosa: str | None) -> str:
	"""AI xulosasidan ota-onaning maktab bo'yicha gapi. Bo'lmasa bo'sh satr."""
	for kalit in TAKLIF_KALITLAR:
		matn = _qator(xulosa, kalit)
		if matn and not _bosh(matn):
			return matn
	return ""


def _turi(xulosa: str | None, kategoriya: str | None) -> str:
	"""AI aytgan tur ustun; aytmasa kategoriyaning odatdagi turi; u ham
	bo'lmasa «Shikoyat» (rahbar e'tiborini talab qiladigan xavfsiz taxmin)."""
	aytgan = _qator(xulosa, "MUROJAAT TURI")
	for t in TURLAR:
		if aytgan and t.lower() in aytgan.lower():
			return t
	if kategoriya:
		tavsiya = frappe.db.get_value("Murojaat Kategoriyasi", kategoriya, "turi_tavsiya")
		if tavsiya in TURLAR:
			return tavsiya
	return "Shikoyat"


def _yonalish(xulosa: str | None) -> str | None:
	"""AI'ning MUROJAAT YO'NALISHI qatori -> CEO / Direktor. Aytmasa None."""
	aytgan = _qator(xulosa, "MUROJAAT YO'NALISHI").lower()
	if not aytgan or _bosh(aytgan):
		return None
	for kalit, rol in YONALISH_MAP.items():
		if kalit in aytgan:
			return rol
	return None


def _marshrut(matn: str, xulosa: str | None) -> tuple[str | None, str | None]:
	"""(kategoriya, yonaltirildi) — AI yo'nalishi bilan kalit so'z kelishuvi.

	Kalit so'z aniq kategoriya beradi (masalan "O'qituvchi ustidan shikoyat"),
	AI esa umumiy yo'nalishni. Mos kelsa — aniq kategoriya ishlatiladi. Zid
	kelsa AI yo'nalishi ustun: AI butun suhbatni o'qigan, kalit so'z esa bitta
	satrdagi tasodifiy so'zga ilashgan bo'lishi mumkin."""
	kat = api.kategoriya_top(matn)
	ai_yonalish = _yonalish(xulosa)
	kat_yonalish = (
		frappe.db.get_value("Murojaat Kategoriyasi", kat, "yonaltirish") if kat else None
	)

	if kat and (not ai_yonalish or ai_yonalish == kat_yonalish):
		return kat, kat_yonalish or ai_yonalish
	yonalish = ai_yonalish or kat_yonalish or "CEO"
	zaxira = ZAXIRA_KAT.get(yonalish)
	if zaxira and frappe.db.exists("Murojaat Kategoriyasi", zaxira):
		return zaxira, yonalish
	return None, yonalish


def _student_top(tq) -> str | None:
	"""Qo'ng'iroqdagi raqamdan o'quvchini topish.

	BOG'LANISH NORMALLASHTIRILGAN RAQAM BO'YICHA (2026-11-07 tuzatishi).
	Avval `LIKE '%<oxirgi 9 xona>'` ishlatilardi va u ishlamasdi: bazada
	274 o'quvchidan HECH BIRIDA raqam toza "998XXXXXXXXX" ko'rinishida
	emas — "77 377 38 58", "50 007 1618" kabi bo'sh joyli matnlar. Natijada
	AI topgan shikoyatlar o'quvchisiz qolardi: rahbar kim shikoyat qilganini
	bilmasdi va ota-ona javobni ilovada hech qachon ko'rmasdi.

	Shuning uchun sotuv nazoratidagi bilan BIR XIL xarita ishlatiladi —
	hamma o'quvchi/ota-ona raqami Python tomonda normallashtiriladi."""
	if tq.student:
		return tq.student

	from target_zenit.telefoniya.utils import normalize_phone

	xarita = _raqam_xarita()
	for xom in (tq.normal_telefon, tq.tashqi_raqam):
		tel = normalize_phone(xom)
		if tel and tel in xarita:
			return xarita[tel]["student"]

	# ZAXIRA: raqamga ortiqcha xona yopishgan holat. Telefoniya ma'lumotida
	# 13 xonali qiymatlar uchraydi va naqsh aniq (2026-11-07, prod):
	#
	#   7718905507718 = 771890550 + 7718   (birinchi 4 xona oxiriga takroran)
	#   9967388589967 = 996738858 + 9967
	#
	# Ya'ni HAQIQIY raqam — BIRINCHI 9 xona. Shunga qaramay ikkala uch ham
	# sinaladi: manba ilovaning xatosi va u kelajakda boshqacha buzishi
	# mumkin, 9 xonali moslik esa 394 raqamli xaritada tasodifan to'g'ri
	# kelmaydi.
	#
	# Faqat 12 XONADAN UZUN qiymatlarda qo'llanadi: qisqa qiymatlarda
	# (masalan 11 xonali "99877767228" — bitta xonasi YETISHMAYDI) 9 xona
	# ajratib olish raqamni SURIB YUBORADI va boshqa odamga tushib qolardi.
	for xom in (tq.normal_telefon, tq.tashqi_raqam):
		raqamlar = re.sub(r"\D", "", str(xom or ""))
		if len(raqamlar) <= 12:
			continue
		for bolak in (raqamlar[:9], raqamlar[-9:]):
			tel = normalize_phone(bolak)
			if tel and tel in xarita:
				return xarita[tel]["student"]

	return None


def _raqam_xarita() -> dict:
	"""normal raqam -> {student, ...}. So'rov davomida bir marta quriladi.

	Xarita og'ir (hamma o'quvchi + Guardian), lekin murojaat kamdan-kam
	ochiladi — tahlil qilingan har qo'ng'iroqda bir marta."""
	kesh = getattr(frappe.local, "_murojaat_raqam_xarita", None)
	if kesh is None:
		from target_zenit.target_zenit.page.sotuv_nazorati.sotuv_nazorati import (
			_raqam_xarita as xarita,
		)

		kesh = xarita()
		frappe.local._murojaat_raqam_xarita = kesh
	return kesh


def qongiroqdan(qongiroq: str) -> dict:
	"""AI tahlili tayyor bo'lgan qo'ng'iroqdan murojaat ochadi (yoki o'tkazadi)."""
	tq = frappe.db.get_value(
		"Telefon Qongirogi", qongiroq,
		["name", "ai_xulosa", "student", "normal_telefon", "tashqi_raqam", "foydalanuvchi",
		 "xodim", "boshlandi", "aloqador_ism", "kontakt_ism"],
		as_dict=True,
	)
	if not tq:
		return {"holat": "yo'q"}
	if frappe.db.exists("Murojaat", {"telefon_qongirogi": qongiroq}):
		return {"holat": "o'tkazildi", "sabab": "murojaat allaqachon bor"}

	matn = taklif_matni(tq.ai_xulosa)
	if not matn or len(matn) < MIN_UZUNLIK:
		return {"holat": "o'tkazildi", "sabab": "taklif/shikoyat yo'q"}

	kategoriya, yonaltirildi = _marshrut(matn, tq.ai_xulosa)
	student = _student_top(tq)
	qarz_ishi = None
	if student:
		ochiq = frappe.get_all(
			"Qarz Ishi",
			filters={"student": student,
			         "ishlov_status": ["not in", ("Yopildi - To'landi", "Yopildi - Boshqa")]},
			pluck="name", order_by="qarz_summa desc", limit_page_length=1,
		)
		qarz_ishi = ochiq[0] if ochiq else None

	diqqat = _qator(tq.ai_xulosa, "DIQQAT")
	menejer = tq.foydalanuvchi
	if not menejer and tq.xodim:
		menejer = frappe.db.get_value("Employee", tq.xodim, "user_id")

	name = api.murojaat_yarat(
		matn=matn,
		turi=_turi(tq.ai_xulosa, kategoriya),
		kategoriya=kategoriya,
		yonaltirildi=yonaltirildi,
		student=student,
		qarz_ishi=qarz_ishi,
		telefon_qongirogi=qongiroq,
		muhimlik="Yuqori" if (diqqat and not _bosh(diqqat)) else "O'rta",
		manba="AI qo'ng'iroq tahlili",
		menejer=menejer or "Administrator",
		suhbat_vaqti=tq.boshlandi,
		payer_name=tq.aloqador_ism or tq.kontakt_ism,
		payer_phone=tq.normal_telefon,
		izoh=("AI qo'ng'iroq tahlilidan avtomatik ochildi"
		      + (f". DIQQAT: {diqqat}" if diqqat and not _bosh(diqqat) else "")),
		ignore_permissions=True,
	)
	frappe.db.commit()
	return {"holat": "ochildi", "murojaat": name, "kategoriya": kategoriya,
	        "yonaltirildi": yonaltirildi}


def qongiroqdan_xavfsiz(qongiroq: str) -> None:
	"""Tahlil oqimidan chaqiriladi: murojaat ochilmasa ham tahlil buzilmasin."""
	try:
		qongiroqdan(qongiroq)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Murojaat avto-ochish xato: {qongiroq}")


@frappe.whitelist()
def qolganlarni_qil(limit: int = 300) -> dict:
	"""Tahlili bor-u murojaati ochilmagan qo'ng'iroqlar (backfill + cron zaxirasi).

	Modul yoqilgandan OLDIN tahlil qilingan qo'ng'iroqlardagi shikoyatlar ham
	rahbarga ko'rinishi kerak — aks holda modul faqat bugundan ishlagan bo'ladi."""
	frappe.only_for(("System Manager", "Sales Manager", "CEO", "Direktor"))
	bor = set(frappe.get_all(
		"Murojaat", filters={"telefon_qongirogi": ["is", "set"]},
		pluck="telefon_qongirogi", limit_page_length=0,
	))
	nomlar = frappe.get_all(
		"Telefon Qongirogi",
		filters={"ai_xulosa": ["is", "set"]},
		pluck="name", order_by="boshlandi desc", limit_page_length=int(limit),
	)
	ochildi = 0
	for nom in nomlar:
		if nom in bor:
			continue
		if qongiroqdan(nom).get("holat") == "ochildi":
			ochildi += 1
	return {"korildi": len(nomlar), "ochildi": ochildi}


@frappe.whitelist()
def oquvchini_bogla(dry_run: int = 1, limit: int = 500) -> dict:
	"""O'quvchisi bog'lanmagan murojaatlarni qayta bog'laydi.

	NEGA KERAK: 2026-11-07 gacha raqam `LIKE` bilan qidirilardi va bazadagi
	raqamlar bo'sh joyli matn bo'lgani uchun hech qachon topilmasdi. Natijada
	AI topgan shikoyatlar o'quvchisiz qoldi — rahbar kim shikoyat qilganini
	bilmaydi, ota-ona esa javobni ilovada ko'rmaydi (bog'lanish bo'lmasa
	Moodle akkaunti ham topilmaydi).

	`dry_run=1` — faqat ko'rsatadi, yozmaydi."""
	frappe.only_for(("System Manager", "Sales Manager"))

	nomlar = frappe.get_all(
		"Murojaat",
		filters={"student": ["in", ("", None)], "telefon_qongirogi": ["is", "set"]},
		fields=["name", "telefon_qongirogi", "payer_phone"],
		limit_page_length=cint(limit),
	)
	topildi, qoldi = [], []
	for m in nomlar:
		tq = frappe.db.get_value(
			"Telefon Qongirogi", m.telefon_qongirogi,
			["name", "student", "normal_telefon", "tashqi_raqam"], as_dict=True,
		)
		student = _student_top(tq) if tq else None
		if not student:
			# Xom raqam ham ko'rsatiladi: nuqson manbai telefoniyada bo'lsa
			# (ilova buzuq raqam yuborsa) shu yerdan ko'rinadi
			qoldi.append({
				"murojaat": m.name,
				"normal": tq.normal_telefon if tq else None,
				"xom": tq.tashqi_raqam if tq else None,
			})
			continue
		topildi.append({"murojaat": m.name, "student": student,
		                "ism": frappe.db.get_value("Student", student, "student_name")})
		if not cint(dry_run):
			doc = frappe.get_doc("Murojaat", m.name)
			doc.student = student
			# Qarz ishi ham bog'lanadi — rahbar qarz holatini ko'rsin
			ochiq = frappe.get_all(
				"Qarz Ishi",
				filters={"student": student,
				         "ishlov_status": ["not in", ("Yopildi - To'landi", "Yopildi - Boshqa")]},
				pluck="name", order_by="qarz_summa desc", limit_page_length=1,
			)
			if ochiq and not doc.qarz_ishi:
				doc.qarz_ishi = ochiq[0]
			doc.save(ignore_permissions=True)
	if not cint(dry_run) and topildi:
		frappe.db.commit()
	return {
		"korildi": len(nomlar), "boglandi": len(topildi), "qoldi": len(qoldi),
		"dry_run": cint(dry_run), "namuna": topildi[:10], "bogllanmadi": qoldi[:10],
	}
