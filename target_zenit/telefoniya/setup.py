# Copyright (c) 2026, Target Zenit
"""Telefoniya moduli uchun bir martalik sozlash — har migrate'da tekshiriladi."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROL = "Telefoniya Agent"

CUSTOM_FIELDS = {
	"Employee": [
		{
			"fieldname": "telefon_ichki_raqam",
			"label": "Ichki telefon raqami",
			"fieldtype": "Data",
			"insert_after": "cell_number",
			"search_index": 1,
			"description": "Asterisk SIP extension (masalan 101). Qo'ng'iroqni menejerga bog'lash shu orqali.",
		}
	],
	"Student": [
		{
			"fieldname": "normal_telefon",
			"label": "Normal telefon",
			"fieldtype": "Data",
			"insert_after": "student_mobile_number",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
			"search_index": 1,
			"description": "Kanonik ko'rinish (998XXXXXXXXX) — avtomatik to'ldiriladi.",
		}
	],
}


def after_migrate():
	_rol_yarat()
	create_custom_fields(CUSTOM_FIELDS, update=True)
	_papka_yarat()


def _rol_yarat():
	if frappe.db.exists("Role", ROL):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": ROL,
			"desk_access": 1,
			"is_custom": 1,
		}
	).insert(ignore_permissions=True)
	frappe.logger("telefoniya").info(f"'{ROL}' roli yaratildi")


def _papka_yarat():
	"""Yozuvlar papkasini oldindan yaratib qo'yamiz — birinchi qo'ng'iroqda
	ruxsat muammosi chiqib qolmasin."""
	import os

	from target_zenit.telefoniya import storage

	try:
		os.makedirs(storage.baza_papka(), mode=0o750, exist_ok=True)
	except Exception as e:
		frappe.logger("telefoniya").warning(f"Yozuvlar papkasini yaratib bo'lmadi: {e}")
