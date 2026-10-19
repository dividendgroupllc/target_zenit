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
from frappe.utils import cint

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
	# Kassa'da "To'lov usuli" MAJBURIY maydon — o'qish ruxsati bo'lmasa
	# yozuvni saqlab ham bo'lmaydi
	"Mode of Payment": (1, 0, 0, 0),
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
	"""Doctype ruxsatlarini o'rnatish (idempotent).

	Ruxsat faqat OSHIRILADI — UI'dan qo'lda berilgan qo'shimcha huquq
	(masalan Employee write) deploy'da o'chib ketmaydi.

	MUHIM TUZOQ: `frappe.permissions.update_permission_property()` qatorni
	`if_owner=0` bo'yicha qidiradi. Agar UI'da "faqat o'zi yaratgan hujjatlar"
	belgisi yoqilgan bo'lsa (if_owner=1), u qator TOPILMAYDI va funksiya
	JIMGINA hech narsa qilmaydi — ruxsat berilgandek ko'rinadi, lekin
	ro'yxatlar bo'sh chiqadi (xodim o'zi yaratmagan yozuvlarni ko'rmaydi).
	Shuning uchun qatorlar bu yerda to'g'ridan-to'g'ri yangilanadi.
	"""
	from frappe.permissions import add_permission

	if not frappe.db.exists("Role", ROL):
		return
	n, tuzatilgan = 0, []
	for dt, (r, w, c, d) in PERMS.items():
		if not frappe.db.exists("DocType", dt):
			continue
		qatorlar = frappe.get_all(
			"Custom DocPerm", filters={"parent": dt, "role": ROL, "permlevel": 0},
			fields=["name", "read", "write", "create", "delete", "submit", "if_owner"],
			order_by="if_owner asc")
		if not qatorlar:
			add_permission(dt, ROL, 0)
			qatorlar = frappe.get_all(
				"Custom DocPerm", filters={"parent": dt, "role": ROL, "permlevel": 0},
				fields=["name", "read", "write", "create", "delete", "submit", "if_owner"],
				order_by="if_owner asc")
		if not qatorlar:
			continue

		asosiy = qatorlar[0]
		if cint(asosiy.if_owner):
			# "faqat o'zi yaratgani" cheklovini olib tashlaymiz — aks holda
			# ro'yxatlar bo'sh ko'rinadi
			frappe.db.set_value("Custom DocPerm", asosiy.name, "if_owner", 0)
			tuzatilgan.append(dt)
		# ortib qolgan if_owner qatorlari (faqat SHU rol uchun) keraksiz
		for q in qatorlar[1:]:
			if cint(q.if_owner):
				frappe.db.delete("Custom DocPerm", {"name": q.name})

		yangi = {}
		for prop, val in (("read", r), ("write", w), ("create", c), ("delete", d),
						  ("submit", 1 if dt in SUBMIT_HUQUQI else 0),
						  ("report", 1), ("export", 1), ("print", 1), ("share", 1)):
			# faqat oshirish: qo'lda berilgan huquqni pasaytirmaymiz
			if cint(asosiy.get(prop)) and not val:
				continue
			yangi[prop] = val
		if yangi:
			frappe.db.set_value("Custom DocPerm", asosiy.name, yangi)
		n += 1

	frappe.clear_cache()
	print(f"{ROL} ruxsatlari: {n} doctype"
		  + (f" | 'faqat o'zi yaratgani' cheklovi olindi: {', '.join(tuzatilgan)}" if tuzatilgan else ""))


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


# ---------------------------------------------------------------- diagnostika

# Kassa'dan xodimga to'lov qilish uchun minimal kerakli ruxsatlar
TEKSHIRILADIGAN = ("Employee", "Kassa", "Mode of Payment", "Account", "Company",
				   "Journal Entry", "Payment Entry", "Currency Exchange")


def tekshir(email=None):
	"""PROD'da muammoni aniqlash uchun: rol, ruxsatlar va to'lov yo'li tekshiruvi.

	Ishlatish:
	  bench --site <sayt> execute target_zenit.moliya_rol.tekshir \\
	        --kwargs "{'email': 'nigora@...'}"

	Nimalarni ko'rsatadi:
	  1) foydalanuvchi rollari va ROL bor-yo'qligi
	  2) UNING ZIMMASIDAGI "User Permission" cheklovlari — Employee bo'yicha
	     cheklov bo'lsa u FAQAT O'Z yozuvini ko'radi (ro'yxat "bo'sh" bo'lib
	     ko'rinadi va Kassa'da boshqa xodimni party sifatida tanlay olmaydi)
	  3) har doctype uchun read/write/create + "faqat o'zi yaratgani" (if_owner)
	  4) o'sha foydalanuvchi nomidan Employee ro'yxati necha yozuv qaytaradi
	"""
	if not email:
		print("email kerak: --kwargs \"{'email': 'nigora@...'}\"")
		return
	if not frappe.db.exists("User", email):
		print(f"TOPILMADI: {email} degan foydalanuvchi yo'q")
		return

	rollar = frappe.get_all("Has Role", filters={"parent": email, "parenttype": "User"}, pluck="role")
	print(f"Foydalanuvchi: {email} | enabled: {frappe.db.get_value('User', email, 'enabled')}")
	print(f"  rollari: {rollar}")
	print(f"  '{ROL}' roli: {'BOR' if ROL in rollar else 'YO`Q  <-- rolni tayinlash kerak'}")

	up = frappe.get_all("User Permission", filters={"user": email},
						fields=["allow", "for_value", "applicable_for"])
	if up:
		print("  User Permission cheklovlari:")
		for r in up:
			belgi = "  <-- SHU SABABLI XODIMLAR KO'RINMAYDI" if r.allow == "Employee" else ""
			print(f"    {r.allow} = {r.for_value} (applicable_for: {r.applicable_for or '-'}){belgi}")
	else:
		print("  User Permission cheklovi yo'q (yaxshi)")

	print("  Ruxsatlar (rol bo'yicha yozuv):")
	for dt in TEKSHIRILADIGAN:
		if not frappe.db.exists("DocType", dt):
			continue
		p = None
		for jadval in ("Custom DocPerm", "DocPerm"):
			qatorlar = frappe.get_all(
				jadval, filters={"parent": dt, "role": ROL, "permlevel": 0},
				fields=["read", "write", "create", "submit", "if_owner"],
				order_by="if_owner asc")
			if qatorlar:
				p = qatorlar[0]
				break
		if not p:
			print(f"    {dt:18} — rol uchun ruxsat yozuvi YO'Q")
			continue
		ogoh = "  <-- 'faqat o'zi yaratgani' yoqilgan, ro'yxat bo'sh ko'rinadi" if cint(p.if_owner) else ""
		print(f"    {dt:18} read={cint(p.read)} write={cint(p.write)} create={cint(p.create)} "
			  f"submit={cint(p.submit)}{ogoh}")

	# Foydalanuvchi nomidan haqiqiy ro'yxat
	avvalgi = frappe.session.user
	try:
		frappe.set_user(email)
		for dt in ("Employee", "Kassa"):
			try:
				n = len(frappe.get_list(dt, limit=20))
				print(f"  {email} ko'radigan {dt}: {n} yozuv (20 tagacha tekshirildi)")
			except Exception as e:
				print(f"  {dt} ro'yxati XATO: {type(e).__name__} {str(e)[:120]}")
	finally:
		frappe.set_user(avvalgi)
