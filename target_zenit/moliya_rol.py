# Copyright (c) 2026, Target Zenit
"""Moliya bo'limi boshlig'i (Nigora) uchun shaxsiy rol va ruxsatlar.

Xojakbar_Operator uslubida: bitta odamga atalgan rol — sahifalar ro'yxatiga
qo'shiladi (Page JSON'larida), doctype ruxsatlari esa shu yerda idempotent
o'rnatiladi.

Nima ochiladi:
  - /app/oylik-tabel        — Oylik tabel (TO'LIQ tahrir: yo'qlama, oylik,
                              nalog, pitaniya, jami)
  - /app/xodim-qarzdorlik   — Xodimlar qarzdorligi
  - /app/qarzdorlik         — O'quvchilar qarzdorligi paneli
  + "Qarzdorlik CRM" workspace yorliqlari

Rol PROD'da foydalanuvchiga QO'LDA tayinlanadi (User hujjatida) — bu yerda
faqat rolning o'zi va doctype ruxsatlari ta'minlanadi.
"""

import frappe

ROL = "Nigora_Moliya"

# doctype: (read, write, create, delete)
# Oylik tabel va qarzdorlik sahifalari ma'lumotni server tomonda oladi
# (ignore_permissions), shuning uchun bu ruxsatlar FAQAT sahifadan ochiladigan
# ro'yxat/hujjat ko'rinishlari va ruxsat tekshiradigan amallar uchun kerak.
PERMS = {
	# O'quvchilar qarzdorligi paneli — qo'ng'iroq natijasi yoziladi
	"Qarz Ishi": (1, 1, 0, 0),
	"Aloqa Yozuvi": (1, 1, 1, 0),
	"Tolov Rejasi": (1, 0, 0, 0),
	"Tolov Vadasi": (1, 0, 0, 0),
	# Oylik tabel — "O'zgarishlar jurnali" tugmasi va oy yozuvlari
	"Tabel Ozgarish Jurnali": (1, 0, 0, 0),
	"Tabel Oyi": (1, 0, 0, 0),
	"Tabel Oylik": (1, 0, 0, 0),
	"Tabel Ish Kuni": (1, 0, 0, 0),
	"Tabel Jami": (1, 0, 0, 0),
	"Tabel Nalog": (1, 0, 0, 0),
	"Tabel Pitaniya": (1, 0, 0, 0),
}


def rol_yarat():
	"""Rolning o'zi (desk'ga kiradigan custom rol). Idempotent."""
	if frappe.db.exists("Role", ROL):
		return False
	frappe.get_doc({
		"doctype": "Role",
		"role_name": ROL,
		"desk_access": 1,
		"is_custom": 1,
	}).insert(ignore_permissions=True)
	print(f"Rol yaratildi: {ROL}")
	return True


def ruxsatlar():
	"""Doctype ruxsatlarini o'rnatish (idempotent)."""
	from frappe.permissions import add_permission, update_permission_property

	if not frappe.db.exists("Role", ROL):
		return
	n = 0
	for dt, (r, w, c, d) in PERMS.items():
		if not frappe.db.exists("DocType", dt):
			continue
		bor = frappe.db.exists("Custom DocPerm", {"parent": dt, "role": ROL, "permlevel": 0}) \
			or frappe.db.exists("DocPerm", {"parent": dt, "role": ROL, "permlevel": 0})
		if not bor:
			add_permission(dt, ROL, 0)
		for prop, val in (("read", r), ("write", w), ("create", c), ("delete", d),
						  ("report", 1), ("export", 1), ("print", 1), ("share", 1)):
			update_permission_property(dt, ROL, 0, prop, val, validate=False)
		n += 1
	print(f"{ROL} ruxsatlari: {n} doctype")


def before_migrate():
	"""Rol Page/Workspace JSON'lari sinxronlanishidan OLDIN yaratilishi kerak —
	aks holda sahifadagi "Nigora_Moliya" roli link validatsiyasidan o'tmaydi."""
	try:
		rol_yarat()
		frappe.db.commit()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "moliya_rol before_migrate")


def after_migrate():
	try:
		rol_yarat()
		ruxsatlar()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "moliya_rol after_migrate")
