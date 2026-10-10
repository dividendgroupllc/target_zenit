# Copyright (c) 2026, Target Zenit
# O'quv reja (KTP) ishchi mantiqi: faol rejani topish, keyingi o'tilmagan mavzu,
# "dars o'tdim" tasdig'i (Dars Bajarilishi yaratadi), qamrov hisoboti.
# Standart ERPNext/jadval yadrosini buzmaydi — ustiga ulanadi.
from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

MENEJER_ROLLARI = {"system manager", "zavuch", "academics user", "education manager"}
KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _vaqt_str(v) -> str:
	if not v:
		return ""
	if hasattr(v, "total_seconds"):
		j = int(v.total_seconds())
		return f"{j // 3600:02d}:{(j % 3600) // 60:02d}"
	s = str(v)
	return s[:5] if len(s) >= 5 else s


def _daraja_raqam(s: str | None) -> str:
	"""Guruh/daraja nomidan sinf raqamini ajratadi: '5 A(full)' -> '5'."""
	m = re.search(r"\d+", str(s or ""))
	return m.group(0) if m else ""


def _menejermi() -> bool:
	return bool(MENEJER_ROLLARI & {r.lower() for r in frappe.get_roles()})


def _mening_instructorim() -> str | None:
	user = frappe.session.user
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		ins = frappe.db.get_value("Instructor", {"employee": emp}, "name")
		if ins:
			return ins
	full_name = frappe.db.get_value("User", user, "full_name")
	return frappe.db.get_value("Instructor", {"instructor_name": full_name}, "name")


def aktiv_reja(fan: str, guruh: str | None = None, guruh_nomi: str | None = None) -> str | None:
	"""Shu (fan, guruh) uchun Faol O'quv Reja. Avval guruh to'g'ridan-to'g'ri
	rejaning `sinflar` ro'yxatida bormi (ishonchli); keyin sinf-daraja bo'yicha
	taxmin; oxirida fanга bitta Faol reja bo'lsa — o'sha."""
	if not fan:
		return None
	# 1) To'g'ridan-to'g'ri a'zolik (eng ishonchli — sinflar ro'yxatida bormi)
	if guruh:
		band = frappe.db.sql(
			"""SELECT r.name FROM `tabOquv Reja Guruhi` g
			   JOIN `tabOquv Reja` r ON r.name = g.parent
			   WHERE r.fan = %s AND r.holat = 'Faol' AND g.guruh = %s LIMIT 1""",
			(fan, guruh),
		)
		if band:
			return band[0][0]
	# 2) Zaxira — FAQAT sinflari ko'rsatilmagan (bo'sh) rejalar uchun; aks holda
	#    aniq sinflar ro'yxati bor reja boshqa sinfga noto'g'ri tushmasligi uchun
	#    a'zolik topilmasa — mos reja yo'q.
	bosh = frappe.get_all(
		"Oquv Reja", filters={"fan": fan, "holat": "Faol"},
		fields=["name", "sinf_daraja"], limit_page_length=0,
	)
	bosh = [p for p in bosh if not frappe.db.exists("Oquv Reja Guruhi", {"parent": p.name})]
	if not bosh:
		return None
	if len(bosh) == 1:
		return bosh[0].name
	nomi = guruh_nomi or (frappe.db.get_value("Student Group", guruh, "student_group_name") if guruh else "")
	daraja = _daraja_raqam(nomi) or _daraja_raqam(guruh)
	for p in bosh:
		if daraja and daraja in {d.strip() for d in str(p.sinf_daraja or "").split(",")}:
			return p.name
	return None


def _otilgan_qatorlar(oquv_reja: str, guruh: str) -> set[str]:
	"""Shu guruh uchun o'tilgan (yoki qisman) reja qatorlari (ID) to'plami."""
	rows = frappe.get_all(
		"Dars Bajarilishi",
		filters={"oquv_reja": oquv_reja, "guruh": guruh, "holat": ["in", ["O'tildi", "Qisman"]]},
		fields=["reja_qatori"], limit_page_length=0,
	)
	return {r.reja_qatori for r in rows if r.reja_qatori}


def keyingi_mavzu(oquv_reja: str, guruh: str) -> dict | None:
	"""Shu guruh uchun keyingi o'tilmagan mavzu + progress."""
	if not oquv_reja:
		return None
	qatorlar = frappe.get_all(
		"Oquv Reja Qatori", filters={"parent": oquv_reja, "parenttype": "Oquv Reja"},
		fields=["name", "tartib", "bolim", "mavzu", "soat"], order_by="idx asc",
		limit_page_length=0,
	)
	otilgan = _otilgan_qatorlar(oquv_reja, guruh)
	keyingi = None
	for q in qatorlar:
		if q.name not in otilgan:
			keyingi = q
			break
	return {
		"keyingi": keyingi,
		"otildi": len(otilgan),
		"jami": len(qatorlar),
	}


@frappe.whitelist()
def dars_holati(fan: str, guruh: str, sana: str | None = None,
                jadval_yozuvi: str | None = None, guruh_nomi: str | None = None) -> dict:
	"""Bitta dars uchun: faol reja + keyingi mavzu + bugun o'tilganmi."""
	sana = sana or nowdate()
	reja = aktiv_reja(fan, guruh, guruh_nomi)
	natija = {"oquv_reja": reja, "keyingi": None, "otildi": 0, "jami": 0, "bugun": None}
	if reja:
		km = keyingi_mavzu(reja, guruh) or {}
		natija.update({"keyingi": km.get("keyingi"), "otildi": km.get("otildi", 0),
		               "jami": km.get("jami", 0)})
	# Shu slot bugun allaqachon tasdiqlanganmi?
	filtr = {"guruh": guruh, "sana": sana}
	if jadval_yozuvi:
		filtr["jadval_yozuvi"] = jadval_yozuvi
	natija["bugun"] = frappe.db.get_value(
		"Dars Bajarilishi", filtr, ["name", "mavzu", "holat", "reja_qatori"], as_dict=True
	)
	return natija


@frappe.whitelist()
def dars_detali(jadval_yozuvi: str, sana: str | None = None) -> dict:
	"""Dars ustiga bosilganda — TO'LIQ ma'lumot: dars + o'quv reja + mavzular
	ro'yxati (shu sinf uchun o'tildi belgisi bilan) + bugungi yozuv."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi)
	dars = {
		"jadval_yozuvi": jy.name,
		"fan": jy.fan,
		"guruh": jy.guruh,
		"guruh_nomi": jy.guruh_nomi or jy.guruh,
		"sinflar": jy.sinflar,
		"kun": jy.kun,
		"dars_raqami": jy.dars_raqami,
		"boshlanish": _vaqt_str(jy.boshlanish),
		"tugash": _vaqt_str(jy.tugash),
		"xona": jy.xona,
		"oqituvchi": jy.oqituvchi,
		"oqituvchi_nomi": jy.oqituvchi_nomi,
		"sana": str(sana),
	}
	reja = aktiv_reja(jy.fan, jy.guruh, jy.guruh_nomi)
	mavzular, keyingi, otildi = [], None, 0
	if reja:
		otilgan = _otilgan_qatorlar(reja, jy.guruh)
		rows = frappe.get_all(
			"Oquv Reja Qatori", filters={"parent": reja, "parenttype": "Oquv Reja"},
			fields=["name", "tartib", "bolim", "mavzu", "soat", "dars_turi"],
			order_by="idx asc", limit_page_length=0,
		)
		for q in rows:
			done = q.name in otilgan
			if done:
				otildi += 1
			elif keyingi is None:
				keyingi = q.name
			q["otildi"] = done
			mavzular.append(q)
	bugun = frappe.db.get_value(
		"Dars Bajarilishi", {"guruh": jy.guruh, "sana": sana, "jadval_yozuvi": jy.name},
		["name", "reja_qatori", "mavzu", "holat", "izoh"], as_dict=True,
	)
	return {
		"dars": dars,
		"oquv_reja": reja,
		"oquv_reja_nomi": frappe.db.get_value("Oquv Reja", reja, "nomi") if reja else None,
		"mavzular": mavzular,
		"keyingi": keyingi,
		"otildi": otildi,
		"jami": len(mavzular),
		"bugun": bugun,
	}


@frappe.whitelist()
def dars_otdim(jadval_yozuvi: str | None = None, oquv_reja: str | None = None,
               reja_qatori: str | None = None, guruh: str | None = None,
               fan: str | None = None, sana: str | None = None,
               holat: str = "O'tildi", izoh: str | None = None) -> dict:
	"""O'qituvchi «shu darsni o'tdim» tasdig'i — Dars Bajarilishi yaratadi/yangilaydi.
	Ruxsat: menejer YOKI darsning o'z o'qituvchisi."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi) if jadval_yozuvi else None

	# Ruxsat: menejer yoki shu darsning o'qituvchisi
	oqituvchi = jy.oqituvchi if jy else None
	if not _menejermi():
		meniki = _mening_instructorim()
		if not meniki or (jy and jy.oqituvchi != meniki):
			frappe.throw(_("Faqat shu darsning o'qituvchisi tasdiqlashi mumkin."), frappe.PermissionError)
		oqituvchi = oqituvchi or meniki

	guruh = guruh or (jy.guruh if jy else None)
	fan = fan or (jy.fan if jy else None)
	if not guruh:
		frappe.throw(_("Guruh aniqlanmadi."))

	oquv_reja = oquv_reja or aktiv_reja(fan, guruh, jy.guruh_nomi if jy else None)

	# Mavzu snapshot (reja_qatori berilmagan bo'lsa — keyingi o'tilmagan)
	tartib = mavzu = None
	if not reja_qatori and oquv_reja:
		km = keyingi_mavzu(oquv_reja, guruh) or {}
		k = km.get("keyingi")
		if k:
			reja_qatori, tartib, mavzu = k["name"], k.get("tartib"), k.get("mavzu")
	elif reja_qatori:
		q = frappe.db.get_value("Oquv Reja Qatori", reja_qatori, ["tartib", "mavzu"], as_dict=True)
		if q:
			tartib, mavzu = q.tartib, q.mavzu

	# Dublikat tekshiruvi (guruh + sana + slot) — bo'lsa yangilanadi
	filtr = {"guruh": guruh, "sana": sana}
	if jadval_yozuvi:
		filtr["jadval_yozuvi"] = jadval_yozuvi
	mavjud = frappe.db.get_value("Dars Bajarilishi", filtr, "name")

	qiymat = {
		"oquv_reja": oquv_reja, "reja_qatori": reja_qatori, "tartib": tartib, "mavzu": mavzu,
		"guruh": guruh, "fan": fan, "oqituvchi": oqituvchi, "sana": sana,
		"jadval_yozuvi": jadval_yozuvi, "holat": holat, "izoh": izoh,
		"boshlanish": jy.boshlanish if jy else None,
	}
	if jy and jy.boshlanish and jy.tugash:
		try:
			b = jy.boshlanish.total_seconds() if hasattr(jy.boshlanish, "total_seconds") else 0
			t = jy.tugash.total_seconds() if hasattr(jy.tugash, "total_seconds") else 0
			if t > b:
				qiymat["davomiylik_min"] = int((t - b) // 60)
		except Exception:
			pass

	if mavjud:
		doc = frappe.get_doc("Dars Bajarilishi", mavjud)
		doc.update(qiymat)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(dict(doctype="Dars Bajarilishi", **qiymat))
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "mavzu": mavzu, "holat": holat}


@frappe.whitelist()
def qamrov(academic_year: str | None = None, fan: str | None = None) -> list[dict]:
	"""Qamrov matritsasi: har Faol reja x unга tegishli guruhlar bo'yicha o'tildi/jami."""
	if not _menejermi():
		frappe.throw(_("Qamrov hisoboti uchun ruxsat yo'q."), frappe.PermissionError)
	filtr = {"holat": "Faol"}
	if academic_year:
		filtr["academic_year"] = academic_year
	if fan:
		filtr["fan"] = fan
	rejalar = frappe.get_all("Oquv Reja", filters=filtr,
	                         fields=["name", "fan", "sinf_daraja", "jami_soat"], limit_page_length=0)
	natija = []
	for r in rejalar:
		jami = frappe.db.count("Oquv Reja Qatori", {"parent": r.name, "parenttype": "Oquv Reja"})
		# Shu reja bo'yicha dars o'tilgan guruhlar
		guruhlar = frappe.db.sql(
			"""SELECT guruh, guruh_nomi,
			          COUNT(DISTINCT CASE WHEN holat IN ('O''tildi','Qisman') THEN reja_qatori END) otildi,
			          MAX(sana) oxirgi
			   FROM `tabDars Bajarilishi` WHERE oquv_reja=%s GROUP BY guruh, guruh_nomi""",
			(r.name,), as_dict=True,
		)
		natija.append({
			"oquv_reja": r.name, "fan": r.fan, "sinf_daraja": r.sinf_daraja,
			"jami_mavzu": jami, "guruhlar": guruhlar,
		})
	return natija
