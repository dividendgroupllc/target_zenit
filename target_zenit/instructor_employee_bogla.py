# Copyright (c) 2026, Target Zenit
# `Instructor` -> `Employee` bog'lanishini ism bo'yicha tiklash.
#
# NEGA KERAK: Moodle'dagi o'qituvchi kaliti (`idnumber`) — bog'langan
# `Employee.name`. Bog'lanish bo'lmasa kalit `INSTR-<ism>` bo'lib qoladi va
# oylik tabelidan kelgan ma'lumot unga ULANMAYDI: o'qituvchi "Mening oyligim"
# sahifasini bo'sh ko'radi.
#
# NIMA UCHUN ISM BO'YICHA: Instructor docname qisqa yozilgan
# ("Muxtorov Husan"), Employee esa to'liq ("Muxtorov Husanbek"), ba'zan so'z
# tartibi teskari ("Glory Ilao" / "Ilao Glory Lusita") yoki imlo boshqacha
# ("Nigmatov Muhammadsodiq" / "Nigmatov Muhammasodiqjon"). Shuning uchun aniq
# tenglik ishlamaydi.
#
# QOIDA: ism bilan bog'lash — faqat BIR MARTALIK tuzatish. Bundan keyin
# bog'lanish `Instructor.employee` maydonida turadi va tizimlararo aloqa
# faqat unikal ID orqali ketadi.
#
# XAVFSIZLIK: `dry_run=1` (default) hech narsa yozmaydi. Shubhali mosliklar
# ALOHIDA ro'yxatda chiqadi va avtomatik bog'lanmaydi — ularni odam tasdiqlaydi.

from __future__ import annotations

import re
from difflib import SequenceMatcher

import frappe

# Shundan yuqori o'xshashlik — avtomatik bog'lanadi.
ANIQ = 0.86
# Shundan yuqori, lekin ANIQ dan past — odam tasdiqlashi uchun ko'rsatiladi.
SHUBHALI = 0.62


# Odam tomonidan TASDIQLANGAN mosliklar — faqat Employee ID bilan.
#
# NEGA ALOHIDA: bu uchtasi ismlar o'xshashligi bo'yicha ishonchsiz chiqdi
# (familiya Instructor'da yozilmagan, imlo xatosi va ism varianti), shuning
# uchun ularni algoritm emas, odam hal qildi. ID yozib qo'yilgani uchun
# keyinchalik ism o'zgarsa ham bu moslik buzilmaydi.
#
# Tasdiqlandi: 2026-10-29, lavozimlar bo'yicha tekshirilgan.
QOLDA = {
	# Instructor docname                 Employee ID      (lavozim)
	"Anvarovna Xosiyat":         "HR-EMP-00041",   # Primary Education
	"Werner Fourie":             "HR-EMP-00180",   # GLOBAL PERSPECTIVE
	"Dushayev Fayoz Anvarovich": "HR-EMP-00191",   # Business teacher
}


def _normal(ism: str) -> list[str]:
	"""Ismni solishtirishga tayyorlaydi: so'zlar ro'yxati, saralangan.

	O'zbek imlosidagi odatiy tafovutlar tenglashtiriladi:
	  - apostrof turlari (ʻ ʼ ' `) olib tashlanadi
	  - "o'g'li", "qizi", "o'g'li" kabi otasining ismi qo'shimchalari tashlanadi
	    (Instructor'da ular yo'q, Employee'da bor)
	  - x/h va ye/e almashinuvi (Yerdullayeva / Erdullaeva)
	"""
	s = (ism or "").lower()
	s = re.sub(r"[ʻʼ'`’‘]", "", s)
	s = s.replace("ye", "e").replace("x", "h")
	s = re.sub(r"[^a-zа-яё\s]", " ", s)
	tashla = {"ogli", "qizi", "oglu", "o", "ugli"}
	sozlar = [w for w in s.split() if w and w not in tashla]
	return sorted(sozlar)


def _oxshashlik(a: str, b: str) -> float:
	"""Ikki ismning o'xshashligi (so'z tartibiga bog'liq emas).

	So'zlar saralanib birlashtiriladi, shuning uchun "Glory Ilao" va
	"Ilao Glory Lusita" yuqori ball oladi.
	"""
	ta, tb = _normal(a), _normal(b)
	if not ta or not tb:
		return 0.0

	# Har bir Instructor so'ziga Employee tomonidan eng yaqin so'z topiladi:
	# "Husan" / "Husanbek" yoki "Muhammadsodiq" / "Muhammasodiqjon" kabi
	# qisqartmalar shunda ham yuqori ball oladi.
	ballar = []
	for w in ta:
		eng = max((SequenceMatcher(None, w, v).ratio() for v in tb), default=0.0)
		ballar.append(eng)
	return sum(ballar) / len(ballar)


def _nomzodlar():
	"""Bog'lanishi kerak bo'lgan Instructor'lar va tanlov uchun Employee'lar."""
	instructorlar = frappe.get_all(
		"Instructor",
		filters={"status": "Active", "employee": ["in", ["", None]]},
		fields=["name", "instructor_name", "custom_vakant"],
		limit_page_length=0,
	)
	instructorlar = [i for i in instructorlar if not i.custom_vakant]

	# Allaqachon boshqa Instructor'ga biriktirilgan Employee qayta olinmaydi.
	band = set(
		r.employee for r in frappe.get_all(
			"Instructor", filters={"employee": ["not in", ["", None]]},
			fields=["employee"], limit_page_length=0)
	)
	xodimlar = [
		e for e in frappe.get_all(
			"Employee",
			filters={"status": "Active"},
			fields=["name", "employee_name", "custom_tabelda", "designation"],
			limit_page_length=0,
		)
		if e.name not in band
	]
	return instructorlar, xodimlar


@frappe.whitelist()
def bogla(dry_run=1, faqat_tabel=1):
	"""Instructor'larni Employee bilan bog'laydi.

	dry_run=1      — hech narsa yozilmaydi, faqat hisobot (DEFAULT)
	faqat_tabel=1  — nomzod sifatida faqat `Oylik tabelda` xodimlar olinadi
	                 (maqsad aynan oylikni ulash)
	"""
	frappe.only_for(("System Manager", "Administrator"))
	dry_run = int(dry_run or 0)
	faqat_tabel = int(faqat_tabel or 0)

	instructorlar, xodimlar = _nomzodlar()
	if faqat_tabel:
		xodimlar = [e for e in xodimlar if e.custom_tabelda]

	bogllandi, shubhali, topilmadi = [], [], []
	ishlatilgan = set()
	hal_bolgan_qolda = set()

	# 1-qadam: odam tasdiqlagan mosliklar. Ular ism o'xshashligidan QAT'I NAZAR
	# bog'lanadi va algoritmning tanloviga aralashmaydi.
	nomlar = {i.name for i in instructorlar}
	for iname, eid in QOLDA.items():
		if iname not in nomlar:
			continue                     # allaqachon bog'langan yoki yo'q
		xodim = frappe.db.get_value("Employee", eid,
			["name", "employee_name", "designation"], as_dict=True)
		if not xodim:
			shubhali.append({
				"instructor": iname, "instructor_ismi": iname,
				"employee": eid, "employee_ismi": "(TOPILMADI)",
				"lavozim": "", "ball": 0.0,
			})
			continue
		hal_bolgan_qolda.add(iname)
		ishlatilgan.add(xodim.name)
		bogllandi.append({
			"instructor": iname,
			"instructor_ismi": iname,
			"employee": xodim.name,
			"employee_ismi": xodim.employee_name,
			"lavozim": xodim.designation or "",
			"ball": 1.0,
			"manba": "qolda tasdiqlangan",
		})

	# Avval ENG ishonchli mosliklarni bog'laymiz: barcha juftlik hisoblanib,
	# balldan kamayish tartibida olinadi. Shunda bir Employee ikki Instructor
	# orasida "talash" bo'lmaydi — u eng yaqin ismga ketadi.
	juftlar = []
	for i in instructorlar:
		for e in xodimlar:
			b = _oxshashlik(i.instructor_name or i.name, e.employee_name)
			if b >= SHUBHALI:
				juftlar.append((b, i.name, i.instructor_name or i.name,
				                e.name, e.employee_name, e.designation))
	juftlar.sort(key=lambda x: -x[0])

	hal_bolgan = set(hal_bolgan_qolda)
	for ball, iname, iism, ename, eism, lavozim in juftlar:
		if iname in hal_bolgan or ename in ishlatilgan:
			continue
		yozuv = {
			"instructor": iname,
			"instructor_ismi": iism,
			"employee": ename,
			"employee_ismi": eism,
			"lavozim": lavozim or "",
			"ball": round(ball, 3),
		}
		if ball >= ANIQ:
			hal_bolgan.add(iname)
			ishlatilgan.add(ename)
			bogllandi.append(yozuv)
		else:
			shubhali.append(yozuv)

	for i in instructorlar:
		if i.name not in hal_bolgan and not any(
			s["instructor"] == i.name for s in shubhali
		):
			topilmadi.append({
				"instructor": i.name,
				"instructor_ismi": i.instructor_name or i.name,
			})

	yozildi = 0
	if not dry_run:
		for b in bogllandi:
			frappe.db.set_value("Instructor", b["instructor"], "employee",
			                    b["employee"], update_modified=False)
			yozildi += 1
		frappe.db.commit()

	return {
		"dry_run": bool(dry_run),
		"instructor_bogllanmagan": len(instructorlar),
		"aniq_moslik": len(bogllandi),
		"yozildi": yozildi,
		"shubhali": len(shubhali),
		"topilmadi": len(topilmadi),
		"aniq": bogllandi,
		"shubhali_royxat": shubhali,
		"topilmadi_royxat": topilmadi,
	}
