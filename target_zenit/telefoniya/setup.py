# Copyright (c) 2026, Target Zenit
"""Telefoniya moduli uchun bir martalik sozlash — har migrate'da tekshiriladi."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROL = "Telefoniya Agent"

# Qo'ng'iroq yuboruvchi MASHINA akkauntlari (Android ilova, Asterisk yuklovchisi).
#
# Nega ro'yxat kodda turadi: 2026-11-11 da ingest butunlay to'xtab qolgan edi, chunki
# `Telefon Qongirogi` doctype'i Custom DocPerm orqali `Telefoniya Agent` ruxsatini
# yo'qotgan (sabab: murojaat/setup.py, u yerda tuzatildi). Rol foydalanuvchida
# TURGAN edi — ya'ni "rol berilgan" degani ingest ishlayotganini BILDIRMAYDI.
#
# Shu sababli ingest ruxsati endi rol/DocPerm zanjiriga YAGONA tayanch sifatida
# bog'lanmaydi: bu ro'yxatdagi mashina akkauntlari `api._ruxsatni_tekshir()` dan
# har doim o'tadi. Rol ham har migrate'da biriktirilib turiladi (ikkinchi himoya).
# Qo'shimcha akkaunt site_config'dagi `telefoniya_ingest_users` orqali beriladi.
INGEST_FOYDALANUVCHILAR = ("telefoniya@targetschool.uz",)

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
	_rolni_biriktir()
	_docpermni_tekshir()
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


def ingest_foydalanuvchilar() -> list[str]:
	"""Kodda qayd etilgan + site_config'da qo'shilgan mashina akkauntlari."""
	qoshimcha = frappe.get_conf().get("telefoniya_ingest_users") or []
	if isinstance(qoshimcha, str):
		qoshimcha = [qoshimcha]
	return list(dict.fromkeys([*INGEST_FOYDALANUVCHILAR, *qoshimcha]))


def _rolni_biriktir():
	"""Mashina akkauntlarida `ROL` borligini ta'minlaydi (idempotent).

	Rolsiz qolgan akkaunt = jimgina ma'lumot yo'qotish, shuning uchun bu
	tekshiruv har migrate'da takrorlanadi.
	"""
	for email in ingest_foydalanuvchilar():
		if not frappe.db.exists("User", email):
			continue
		if frappe.db.exists("Has Role", {"parent": email, "parenttype": "User", "role": ROL}):
			continue
		try:
			user = frappe.get_doc("User", email)
			user.append("roles", {"role": ROL})
			user.save(ignore_permissions=True)
			frappe.logger("telefoniya").warning(
				f"'{ROL}' roli {email} ga qayta biriktirildi (yo'qolgan edi)"
			)
		except Exception as e:
			frappe.logger("telefoniya").error(f"{email} ga rol biriktirilmadi: {e}")


def _docpermni_tekshir():
	"""`ROL` ning "Telefon Qongirogi" ga ruxsati DOCPERM darajasida borligini ta'minlaydi.

	Nega bu alohida kerak: kimdir «Role Permissions Manager» da shu doctype'ni
	bir marta saqlasa, Frappe **Custom DocPerm** jadvalini yaratadi va shundan
	keyin app'ning `telefon_qongirogi.json` dagi ruxsatlari BUTUNLAY e'tiborsiz
	qoladi (`meta.py`: "Reset permissions with Custom DocPerm if exists").
	`bench migrate` ularni tiklamaydi. Natijada foydalanuvchida rol TURGANI
	HOLDA ruxsat ishlamay qoladi — tashqaridan rol "berilgan va o'chirilmagan"
	ko'rinadi, lekin har yuklash HTTP 403 oladi.

	`add_permission` avval standart ruxsatlarni Custom DocPerm'ga nusxalaydi,
	shuning uchun boshqa rollarning ruxsati buzilmaydi.
	"""
	from frappe.permissions import add_permission, update_permission_property

	dt = "Telefon Qongirogi"
	if not frappe.db.exists("DocType", dt):
		return

	custom_bor = frappe.db.exists("Custom DocPerm", {"parent": dt})
	jadval = "Custom DocPerm" if custom_bor else "DocPerm"
	if frappe.db.exists(jadval, {"parent": dt, "role": ROL, "permlevel": 0}):
		return

	try:
		add_permission(dt, ROL, 0)
		for ptype in ("read", "write", "create"):
			update_permission_property(dt, ROL, 0, ptype, 1)
		frappe.logger("telefoniya").warning(
			f"'{ROL}' uchun {dt} ruxsati tiklandi (DocPerm'da yo'q edi)"
		)
	except Exception as e:
		frappe.logger("telefoniya").error(f"{dt} ruxsatini tiklab bo'lmadi: {e}")


def _papka_yarat():
	"""Yozuvlar papkasini oldindan yaratib qo'yamiz — birinchi qo'ng'iroqda
	ruxsat muammosi chiqib qolmasin."""
	import os

	from target_zenit.telefoniya import storage

	try:
		os.makedirs(storage.baza_papka(), mode=0o750, exist_ok=True)
	except Exception as e:
		frappe.logger("telefoniya").warning(f"Yozuvlar papkasini yaratib bo'lmadi: {e}")
