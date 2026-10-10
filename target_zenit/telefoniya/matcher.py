# Copyright (c) 2026, Target Zenit
"""Raqamni CRM yozuvlariga bog'lash.

Zanjir: normal raqam -> Family (phone/phone2) -> Admission Lead
        normal raqam -> Admission Lead.phone (to'g'ridan-to'g'ri)
        normal raqam -> Student (o'quvchi/ota-ona mobil raqami)

Family Child jadvalida Student'ga link yo'q, shuning uchun oila orqali o'quvchiga
avtomatik chiqib bo'lmaydi — uchta bog'lanish mustaqil izlanadi.
"""

import frappe

from target_zenit.telefoniya.utils import normalize_phone


def _ustun_bormi(doctype: str, fieldname: str) -> bool:
	"""Maydon hali qo'shilmagan bo'lsa (migrate'dan oldin) qidirmaymiz."""
	try:
		return fieldname in frappe.db.get_table_columns(doctype)
	except Exception:
		return False


def topish(normal: str | None) -> dict:
	"""Normal raqam bo'yicha bog'lanishlarni izlaydi."""
	natija = {
		"family": None,
		"admission_lead": None,
		"student": None,
		"aloqador_ism": None,
	}
	if not normal:
		return natija

	# 1) Oila — ikkita raqam maydoni ham tekshiriladi.
	oila = None
	if _ustun_bormi("Family", "normal_telefon"):
		oila = frappe.db.get_value(
			"Family", {"normal_telefon": normal}, ["name", "family_name"], as_dict=True
		) or frappe.db.get_value(
			"Family", {"normal_telefon2": normal}, ["name", "family_name"], as_dict=True
		)
	if oila:
		natija["family"] = oila.name

	# 2) Murojaat — avval raqam bo'yicha, topilmasa oila bo'yicha. Eng yangisi olinadi.
	lead = None
	if _ustun_bormi("Admission Lead", "normal_telefon"):
		lead = _bitta(
			"Admission Lead", {"normal_telefon": normal}, ["name", "child_name", "family"]
		)
	if not lead and oila:
		lead = _bitta("Admission Lead", {"family": oila.name}, ["name", "child_name", "family"])
	if lead:
		natija["admission_lead"] = lead.name
		if not natija["family"] and lead.get("family"):
			natija["family"] = lead.family

	# 3) O'quvchi — Student'dagi normal_telefon (Custom Field).
	oquvchi = None
	if _ustun_bormi("Student", "normal_telefon"):
		oquvchi = _bitta("Student", {"normal_telefon": normal}, ["name", "student_name"])
	if oquvchi:
		natija["student"] = oquvchi.name

	# Ko'rsatish uchun ism — eng aniqrog'idan boshlab.
	natija["aloqador_ism"] = (
		(oquvchi and oquvchi.get("student_name"))
		or (lead and lead.get("child_name"))
		or (oila and oila.get("family_name"))
		or None
	)
	return natija


def topish_xom(xom_raqam: str | None) -> dict:
	"""Xom raqamni normallashtirib qidiradi."""
	return topish(normalize_phone(xom_raqam))


def xodim_topish(ichki_raqam: str | None) -> dict:
	"""Ichki raqam (SIP extension) -> Employee + User."""
	natija = {"xodim": None, "foydalanuvchi": None}
	if not ichki_raqam or not _ustun_bormi("Employee", "telefon_ichki_raqam"):
		return natija
	xodim = _bitta(
		"Employee",
		{"telefon_ichki_raqam": str(ichki_raqam).strip()},
		["name", "user_id"],
	)
	if xodim:
		natija["xodim"] = xodim.name
		natija["foydalanuvchi"] = xodim.get("user_id")
	return natija


def _bitta(doctype: str, filters: dict, fields: list) -> frappe._dict | None:
	qatorlar = frappe.get_all(
		doctype, filters=filters, fields=fields, order_by="modified desc", limit=1
	)
	return qatorlar[0] if qatorlar else None
