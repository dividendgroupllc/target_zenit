# Copyright (c) 2026, Target Zenit
# Zavuch uchun KUNLIK YO'QLAMA — pul ma'lumotisiz.
#
# Ma'lumot ERPNext `Attendance` ga yoziladi — oylik tabel (api/oylik_tabel.py)
# aynan shu yozuvlarni o'qiydi, ya'ni zavuch belgilagan yo'qlama buxgalteriya
# tabeliga avtomatik tushadi. Bu sahifada OYLIK/BONUS/SUMMA umuman yo'q.
from __future__ import annotations

import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

ROLLAR = ["System Manager", "Zavuch", "Xojakbar_Operator", "HR Manager", "HR User"]
HAFTA = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


# Bu rollar istalgan (o'tgan) kunni ham tahrirlay oladi
TOLIQ_ROLLAR = {"system manager", "xojakbar_operator", "hr manager", "hr user"}


def _guard(tahrir=False):
	rollar = {r.lower() for r in frappe.get_roles()}
	if not ({r.lower() for r in ROLLAR} & rollar):
		frappe.throw(_("Yo'qlamaga ruxsatingiz yo'q"), frappe.PermissionError)


def _faqat_bugun() -> bool:
	"""Zavuch kunlik yo'qlamani FAQAT bugungi kunga qiladi.
	O'tgan kunlarni tuzatish — HR/operator/administrator vakolatida."""
	rollar = {r.lower() for r in frappe.get_roles()}
	return not (TOLIQ_ROLLAR & rollar)


def _oy_ochiqmi(yil, oy) -> bool:
	holat = frappe.db.get_value("Tabel Oyi", {"yil": yil, "oy": oy}, "holat")
	return holat != "Yopiq"


@frappe.whitelist()
def get_data(yil=None, oy=None, kategoriya=None):
	"""Oylik yo'qlama to'ri: xodimlar x kunlar. Pul maydonlari qaytarilmaydi."""
	_guard()
	bugun = getdate(nowdate())
	yil, oy = cint(yil) or bugun.year, cint(oy) or bugun.month
	kunlar_soni = calendar.monthrange(yil, oy)[1]
	oy_boshi, oy_oxiri = f"{yil}-{oy:02d}-01", f"{yil}-{oy:02d}-{kunlar_soni}"

	# O'qituvchilar (Instructor orqali) — zavuchning asosiy ro'yxati
	instr_emp = {
		i.employee: i.instructor_name
		for i in frappe.get_all("Instructor", fields=["employee", "instructor_name"],
								limit_page_length=0) if i.employee
	}

	# Oylik tabel bilan BIR XIL tanlov: faqat "Oylik tabelda" belgisi qo'yilgan
	# xodimlar (Active'lar ko'p, tabelga esa hozir real ishlayotganlar kiradi).
	# Ishdan ketganlar — ketgan oyigacha ko'rinadi, keyin chiqib ketadi.
	xodimlar = frappe.get_all(
		"Employee",
		filters={"custom_tabelda": 1, "date_of_joining": ["<=", oy_oxiri]},
		# DIQQAT: oylik/summa maydonlari ATAYLAB olinmaydi
		fields=["name", "employee_name", "designation", "custom_tolov_turi",
				"custom_ish_haqi_kategoriya", "date_of_joining", "relieving_date", "status"],
		order_by="employee_name",
		limit_page_length=0,
		ignore_permissions=True,
	)
	oy_boshi_d = getdate(oy_boshi)
	saralangan = []
	for x in xodimlar:
		ketgan = getdate(x.relieving_date) if x.relieving_date else None
		if x.status != "Active" and (not ketgan or ketgan < oy_boshi_d):
			continue
		if ketgan and ketgan < oy_boshi_d:
			continue
		saralangan.append(x)
	xodimlar = saralangan
	# Filtr ro'yxati uchun — kategoriyalar filtrdan OLDIN yig'iladi,
	# aks holda bittasini tanlagach qolganlari ro'yxatdan yo'qolardi
	kanon = ["Admin oylik", "O'qituvchi", "Xodimlar", "Oshxona"]
	bor_kat = {(x.custom_ish_haqi_kategoriya or "").strip() for x in xodimlar}
	kategoriyalar = [k for k in kanon if k in bor_kat] or kanon

	# Ish haqi kategoriyasi (tabel) bo'yicha filtr
	if kategoriya == "__none":
		xodimlar = [x for x in xodimlar if not (x.custom_ish_haqi_kategoriya or "").strip()]
	elif kategoriya:
		xodimlar = [x for x in xodimlar if (x.custom_ish_haqi_kategoriya or "") == kategoriya]

	nomlar = [x.name for x in xodimlar]
	belgilar = {}
	if nomlar:
		for a in frappe.get_all(
			"Attendance",
			filters={"employee": ["in", nomlar], "attendance_date": ["between", [oy_boshi, oy_oxiri]],
					 "docstatus": ["<", 2]},
			fields=["employee", "attendance_date", "status", "custom_koef"],
			limit_page_length=0,
			ignore_permissions=True,
		):
			belgilar[f"{a.employee}|{a.attendance_date}"] = {
				"status": a.status, "koef": flt(a.custom_koef),
			}

	# Dars jadvalidan: kim qaysi hafta kunlari dars qiladi (yo'qlama uchun yo'riqnoma)
	darsli = {}
	versiya = frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")
	if versiya:
		KUN_RAQAM = {"Dushanba": 0, "Seshanba": 1, "Chorshanba": 2, "Payshanba": 3, "Juma": 4}
		for j in frappe.get_all(
			"Jadval Yozuvi", filters={"versiya": versiya},
			fields=["oqituvchi", "kun"], limit_page_length=0,
		):
			emp = frappe.db.get_value("Instructor", j.oqituvchi, "employee") if j.oqituvchi else None
			if emp and j.kun in KUN_RAQAM:
				darsli.setdefault(emp, set()).add(KUN_RAQAM[j.kun])

	kunlar = []
	for k in range(1, kunlar_soni + 1):
		d = getdate(f"{yil}-{oy:02d}-{k:02d}")
		kunlar.append({"kun": k, "sana": str(d), "hafta": HAFTA[d.weekday()],
					   "dam": d.weekday() >= 5, "kelajak": d > bugun})

	qatorlar = []
	for x in xodimlar:
		kunlik = []
		keldi = 0
		for kd in kunlar:
			b = belgilar.get(f"{x.name}|{kd['sana']}")
			holat = b["status"] if b else None
			if holat == "Present":
				keldi += 1
			kunlik.append({"sana": kd["sana"], "holat": holat,
						   "koef": b["koef"] if b else None})
		qatorlar.append({
			"xodim": x.name,
			"ism": instr_emp.get(x.name) or x.employee_name,
			"lavozim": x.designation or "",
			"kategoriya": x.custom_ish_haqi_kategoriya or "",
			"soatbay": (x.custom_tolov_turi or "").strip() == "Soatbay",
			"dars_kunlari": sorted(darsli.get(x.name, [])),
			"kunlik": kunlik,
			"keldi": keldi,
		})

	return {
		"yil": yil, "oy": oy, "kunlar": kunlar, "qatorlar": qatorlar,
		"kategoriyalar": kategoriyalar,
		"faqat_bugun": _faqat_bugun(),
		"kategoriya": kategoriya or "",
		"oy_ochiq": _oy_ochiqmi(yil, oy),
		"bugun": str(bugun),
		"oqituvchilar_soni": len(instr_emp),
	}


@frappe.whitelist()
def belgila(xodim, sana, holat, koef=None):
	"""Bitta kunni belgilash: Keldi / Kelmadi / tozalash.
	Attendance'ga yoziladi — oylik tabel shu yozuvlarni o'qiydi."""
	_guard(tahrir=True)
	sana = getdate(sana)
	bugun = getdate(nowdate())
	if sana > bugun:
		frappe.throw(_("Kelajak kunga yo'qlama qilib bo'lmaydi"))
	if _faqat_bugun() and sana != bugun:
		frappe.throw(
			_("Siz faqat BUGUNGI kun ({0}) uchun yo'qlama qila olasiz. "
			  "O'tgan kunni tuzatish kerak bo'lsa — HR yoki administratorga murojaat qiling.")
			.format(bugun.strftime("%d.%m.%Y")),
			frappe.PermissionError,
		)
	if not _oy_ochiqmi(sana.year, sana.month):
		frappe.throw(_("Bu oy yopilgan — o'zgartirib bo'lmaydi"))

	emp = frappe.db.get_value(
		"Employee", xodim, ["name", "company", "custom_tolov_turi"], as_dict=True)
	if not emp:
		frappe.throw(_("Xodim topilmadi"))
	soatbay = (emp.custom_tolov_turi or "").strip() == "Soatbay"

	if holat == "tozalash":
		for a in frappe.get_all("Attendance", filters={
				"employee": xodim, "attendance_date": sana, "docstatus": ["<", 2]}, pluck="name"):
			doc = frappe.get_doc("Attendance", a)
			doc.flags.ignore_permissions = True
			doc.cancel() if doc.docstatus == 1 else doc.delete(ignore_permissions=True)
		return {"ok": 1, "holat": None}

	status = "Present" if holat == "Keldi" else "Absent"
	if soatbay and status == "Present":
		koef = flt(koef) if koef is not None else 8
		if koef < 0 or koef > 24:
			frappe.throw(_("Soat 0 dan 24 gacha bo'lishi kerak"))
	else:
		koef = 1.0 if status == "Present" else 0.0

	mavjud = frappe.db.get_value("Attendance", {
		"employee": xodim, "attendance_date": sana, "docstatus": ["<", 2]}, "name")
	if mavjud:
		doc = frappe.get_doc("Attendance", mavjud)
		doc.flags.ignore_permissions = True
		if doc.docstatus == 1:
			doc.cancel()
			mavjud = None
		else:
			doc.status = status
			doc.custom_koef = koef
			doc.save(ignore_permissions=True)
	if not mavjud:
		doc = frappe.get_doc({
			"doctype": "Attendance", "naming_series": "HR-ATT-.YYYY.-",
			"employee": xodim, "attendance_date": sana, "status": status,
			"custom_koef": koef, "company": emp.company,
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

	return {"ok": 1, "holat": status, "koef": koef}
