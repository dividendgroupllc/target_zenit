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
  - /app/investor-dashboard — Investor paneli
  - /app/sotuv-dashboard    — Sotuv paneli
  + "Kassa" workspace (barcha yorliqlar bir joyda) va "Qarzdorlik CRM"

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
	# ---- "Kassa" workspace (moliya ishi) ----
	# Kassa yozuvlari va kunlik kurs — kiritadi/tahrirlaydi (o'chirish yo'q)
	"Kassa": (1, 1, 1, 0),
	"Currency Exchange": (1, 1, 1, 0),
	# Kontragentlar
	"Customer": (1, 1, 1, 0),
	"Supplier": (1, 1, 1, 0),
	# Ma'lumot uchun (faqat o'qish)
	"Student": (1, 0, 0, 0),
	"Guardian": (1, 0, 0, 0),
	"Employee": (1, 0, 0, 0),
	# Hisobotlar ishlashi uchun kerakli manba doctype'lar (faqat o'qish):
	# DDS / P&L -> GL Entry, Ombor qoldig'i -> Stock Ledger Entry
	"GL Entry": (1, 0, 0, 0),
	"Stock Ledger Entry": (1, 0, 0, 0),
	"Account": (1, 0, 0, 0),
	"Cost Center": (1, 0, 0, 0),
	"Fiscal Year": (1, 0, 0, 0),
	"Item": (1, 0, 0, 0),
	"Warehouse": (1, 0, 0, 0),
	# P&L valyuta ustunlari / Ombor qoldig'i o'lchov birligi uchun
	"Currency": (1, 0, 0, 0),
	"UOM": (1, 0, 0, 0),
	"Item Group": (1, 0, 0, 0),
	"Brand": (1, 0, 0, 0),
	"Company": (1, 0, 0, 0),
	"Journal Entry": (1, 0, 0, 0),
	"Payment Entry": (1, 0, 0, 0),
}

# Submit huquqi beriladigan doctype'lar (Kassa — submit bo'lmasa GL yozuvi
# shakllanmaydi). CANCEL ATAYLAB berilmaydi: bekor qilish GL'ga ta'sir qiladi,
# uni Accounts Manager qiladi.
SUBMIT_HUQUQI = {"Kassa"}

# Hisobotlar — Report hujjatining "roles" jadvaliga qo'shiladi.
# MUHIM: standart hisobotlar (P&L, Stock Balance) JSON'dan qayta
# sinxronlanadi, shuning uchun rol HAR MIGRATE'da shu yerda qayta
# qo'shiladi (after_migrate sync'dan keyin ishlaydi).
REPORTLAR = ("DDS", "Profit and Loss Statement", "Stock Balance", "Balance Sheet")


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
						  ("submit", 1 if dt in SUBMIT_HUQUQI else 0),
						  ("report", 1), ("export", 1), ("print", 1), ("share", 1)):
			update_permission_property(dt, ROL, 0, prop, val, validate=False)
		n += 1
	print(f"{ROL} ruxsatlari: {n} doctype")


def hisobot_rollari():
	"""Hisobot hujjatlariga rolni qo'shish (idempotent)."""
	if not frappe.db.exists("Role", ROL):
		return
	qoshildi = []
	for rp in REPORTLAR:
		if not frappe.db.exists("Report", rp):
			continue
		doc = frappe.get_doc("Report", rp)
		if ROL in [r.role for r in doc.roles]:
			continue
		doc.append("roles", {"role": ROL})
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		qoshildi.append(rp)
	if qoshildi:
		print(f"{ROL} hisobot ruxsati: {', '.join(qoshildi)}")


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
		hisobot_rollari()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "moliya_rol after_migrate")
