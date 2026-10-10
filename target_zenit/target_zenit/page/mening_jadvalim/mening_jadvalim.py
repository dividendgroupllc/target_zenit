# Copyright (c) 2026, Target Zenit
# "Mening jadvalim" — o'qituvchi uchun: bugungi darslar + haftalik jadval.
# Har darsdan davomat olishga o'tish mumkin (Course Schedule orqali).
from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, nowdate

from target_zenit import oquv_reja as oreja

KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _vaqt_str(v) -> str:
	"""Time/timedelta/str -> 'HH:MM'."""
	if not v:
		return ""
	if hasattr(v, "total_seconds"):  # timedelta
		jami = int(v.total_seconds())
		return f"{jami // 3600:02d}:{(jami % 3600) // 60:02d}"
	s = str(v)
	return s[:5] if len(s) >= 5 else s


def _mening_instructorim():
	"""Joriy foydalanuvchining Instructor yozuvi (Employee orqali yoki to'g'ridan)."""
	user = frappe.session.user
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		ins = frappe.db.get_value("Instructor", {"employee": emp}, "name")
		if ins:
			return ins
	full_name = frappe.db.get_value("User", user, "full_name")
	return frappe.db.get_value("Instructor", {"instructor_name": full_name}, "name")


@frappe.whitelist()
def get_data(oqituvchi: str | None = None, versiya: str | None = None):
	"""Tanlangan (yoki o'zining) o'qituvchi jadvali."""
	menejer = bool(
		{"system manager", "zavuch", "academics user", "education manager"}
		& {r.lower() for r in frappe.get_roles()}
	)
	if oqituvchi and not menejer:
		frappe.throw("Boshqa o'qituvchi jadvalini ko'rish uchun ruxsat yo'q.", frappe.PermissionError)

	oqituvchi = oqituvchi or _mening_instructorim()
	versiya = versiya or frappe.db.get_value(
		"Jadval Versiyasi", {"holat": "Faol"}, "name"
	) or frappe.db.get_value("Jadval Versiyasi", {}, "name")

	natija = {
		"oqituvchi": oqituvchi,
		"oqituvchi_nomi": frappe.db.get_value("Instructor", oqituvchi, "instructor_name") if oqituvchi else None,
		"versiya": versiya,
		"menejer": menejer,
		"bugun_kuni": KUNLAR[getdate(nowdate()).weekday()],
		"darslar": [],
		"qongiroq": {},
	}
	if menejer:
		natija["oqituvchilar"] = frappe.get_all(
			"Instructor", fields=["name", "instructor_name"], order_by="instructor_name", limit_page_length=0
		)
	if not oqituvchi or not versiya:
		return natija

	natija["darslar"] = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "oqituvchi": oqituvchi},
		fields=[
			"name", "kun", "kun_raqami", "dars_raqami", "fan", "guruh", "guruh_nomi",
			"sinflar", "xona", "boshlanish", "tugash",
		],
		order_by="kun_raqami asc, dars_raqami asc",
		limit_page_length=0,
	)
	# Joriy haftaning dushanbasi (sanalarni darsга biriktirish uchun)
	bugun = getdate(nowdate())
	hafta_boshi = add_days(bugun, -bugun.weekday())
	for d in natija["darslar"]:
		d["boshlanish"] = _vaqt_str(d["boshlanish"])
		d["tugash"] = _vaqt_str(d["tugash"])
		# Shu dars sanasi (joriy haftada) — kun_raqami 1=Dushanba
		kr = (d.get("kun_raqami") or 1) - 1
		d["sana"] = str(add_days(hafta_boshi, kr))
		# O'quv reja holati (faol reja + keyingi mavzu + o'tilganmi)
		try:
			h = oreja.dars_holati(d["fan"], d["guruh"], sana=d["sana"],
			                      jadval_yozuvi=d["name"], guruh_nomi=d.get("guruh_nomi"))
			d["oquv_reja"] = h.get("oquv_reja")
			d["keyingi"] = h.get("keyingi")
			d["otildi"] = h.get("otildi")
			d["jami"] = h.get("jami")
			d["bugun"] = h.get("bugun")
		except Exception:
			d["oquv_reja"] = None
	natija["haftalik_soat"] = len(natija["darslar"])
	natija["bugun_sana"] = str(bugun)
	return natija


@frappe.whitelist()
def dars_detali(jadval_yozuvi: str, sana: str | None = None):
	"""Dars ustiga bosilganda to'liq ma'lumot (oquv_reja modulida)."""
	return oreja.dars_detali(jadval_yozuvi=jadval_yozuvi, sana=sana)


@frappe.whitelist()
def dars_otdim(jadval_yozuvi: str, sana: str | None = None, reja_qatori: str | None = None,
               holat: str = "O'tildi", izoh: str | None = None):
	"""«Shu darsni o'tdim» — o'quv reja bajarilishini belgilaydi (oquv_reja modulida)."""
	return oreja.dars_otdim(jadval_yozuvi=jadval_yozuvi, sana=sana,
	                        reja_qatori=reja_qatori, holat=holat, izoh=izoh)


@frappe.whitelist()
def davomat_ochish(jadval_yozuvi: str, sana: str | None = None):
	"""Shu dars uchun bugungi Course Schedule'ni topadi yoki yaratadi — davomat uchun."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi)

	mavjud = frappe.db.get_value(
		"Course Schedule",
		{"student_group": jy.guruh, "schedule_date": sana, "from_time": jy.boshlanish},
		"name",
	)
	if mavjud:
		return {"course_schedule": mavjud, "yangi": 0}

	cs = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"student_group": jy.guruh,
			"course": jy.fan,
			"instructor": jy.oqituvchi,
			"room": jy.xona,
			"schedule_date": sana,
			"from_time": jy.boshlanish,
			"to_time": jy.tugash,
			"title": f"{jy.fan} — {jy.guruh_nomi or jy.guruh}",
		}
	)
	cs.flags.ignore_validate = True
	cs.insert(ignore_permissions=True)
	return {"course_schedule": cs.name, "yangi": 1}
