# Copyright (c) 2026, Target Zenit
# Dars jadvali moduli uchun boshlang'ich sozlash (idempotent):
#   - Student Group custom fieldlari (guruh turi, daraja, a'zo sinflar, blok)
#   - Instructor custom fieldlari (vakant belgisi)
#   - Ikki qo'ng'iroq jadvali (1A-5A va 5B-11B)
#
# Ishga tushirish: bench --site <sayt> execute target_zenit.dars_jadvali.setup.hammasi
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Student Group": [
		{
			"fieldname": "custom_guruh_turi",
			"label": "Guruh turi",
			"fieldtype": "Select",
			"options": "Sinf\nDaraja\nTanlov\nQo'shma\nQo'shimcha",
			"default": "Sinf",
			"insert_after": "group_based_on",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "custom_daraja",
			"label": "Daraja / tanlov",
			"fieldtype": "Data",
			"description": "High / Middle / Low yoki tanlov nomi",
			"insert_after": "custom_guruh_turi",
			"depends_on": "eval:doc.custom_guruh_turi && doc.custom_guruh_turi!='Sinf'",
		},
		{
			"fieldname": "custom_azo_sinflar",
			"label": "A'zo sinflar",
			"fieldtype": "Small Text",
			"description": "Qaysi sinflardan yig'ilgan (vergul bilan). Blok berilgan bo'lsa blokdan olinadi.",
			"insert_after": "custom_daraja",
			"depends_on": "eval:doc.custom_guruh_turi && doc.custom_guruh_turi!='Sinf'",
		},
		{
			"fieldname": "custom_blok",
			"label": "Dars bloki",
			"fieldtype": "Link",
			"options": "Dars Bloki",
			"insert_after": "custom_azo_sinflar",
			"depends_on": "eval:doc.custom_guruh_turi && doc.custom_guruh_turi!='Sinf'",
		},
	],
	"Instructor": [
		{
			"fieldname": "custom_vakant",
			"label": "Vakant (o'qituvchi tayinlanmagan)",
			"fieldtype": "Check",
			"insert_after": "instructor_name",
			"description": "Jadvalda dars bor, lekin o'qituvchi hali yo'q (AI VACANT, CHESS VAKANT...)",
		},
		{
			"fieldname": "custom_haftalik_norma",
			"label": "Haftalik norma (soat)",
			"fieldtype": "Int",
			"insert_after": "custom_vakant",
			"description": "0 = nazorat qilinmaydi",
		},
		{
			"fieldname": "custom_max_kun",
			"label": "Haftada max ish kuni",
			"fieldtype": "Int",
			"insert_after": "custom_haftalik_norma",
			"description": "0 = cheklanmagan",
		},
		{
			"fieldname": "custom_max_kunlik_dars",
			"label": "Kuniga max dars",
			"fieldtype": "Int",
			"insert_after": "custom_max_kun",
			"description": "0 = cheklanmagan",
		},
		{
			"fieldname": "custom_max_ketma_ket",
			"label": "Max ketma-ket dars",
			"fieldtype": "Int",
			"insert_after": "custom_max_kunlik_dars",
			"description": "0 = cheklanmagan",
		},
		{
			"fieldname": "custom_mavjudlik_section",
			"label": "Mavjudlik / cheklovlar",
			"fieldtype": "Section Break",
			"insert_after": "custom_max_ketma_ket",
		},
		{
			"fieldname": "custom_mavjudlik",
			"label": "Band/afzal kun va darslar",
			"fieldtype": "Table",
			"options": "Oqituvchi Mavjudlik",
			"insert_after": "custom_mavjudlik_section",
			"description": "Faqat istisnolar: band (ishlamaydi) yoki afzal ko'radigan kun/dars. Bo'sh = butun hafta mavjud.",
		},
	],
}

# Maktabning haqiqiy qo'ng'iroq jadvali (Excel sarlavhasidan)
QONGIROQLAR = [
	{
		"nomi": "Kichik sinflar (1A-5A)",
		"sinf_pattern": "1 *,2 *,3 *,4 *,5 A*",
		"tartib": 1,
		"qatorlar": [
			(1, "09:00:00", "09:40:00", "Dars"), (2, "09:45:00", "10:25:00", "Dars"),
			(3, "10:30:00", "11:10:00", "Dars"), (4, "11:15:00", "11:55:00", "Dars"),
			(0, "12:00:00", "12:40:00", "Tushlik"),
			(5, "12:45:00", "13:25:00", "Dars"), (6, "13:30:00", "14:10:00", "Dars"),
			(7, "14:15:00", "14:55:00", "Dars"), (8, "15:00:00", "15:40:00", "Dars"),
			(0, "15:45:00", "16:05:00", "Tanaffus"),
			(9, "16:10:00", "16:50:00", "Dars"), (10, "16:55:00", "17:35:00", "Dars"),
		],
	},
	{
		"nomi": "Katta sinflar (5B-11B)",
		"sinf_pattern": "*",
		"tartib": 9,
		"qatorlar": [
			(1, "09:00:00", "09:40:00", "Dars"), (2, "09:45:00", "10:25:00", "Dars"),
			(3, "10:30:00", "11:10:00", "Dars"), (4, "11:15:00", "11:55:00", "Dars"),
			(5, "12:00:00", "12:40:00", "Dars"),
			(0, "12:45:00", "13:25:00", "Tushlik"),
			(6, "13:30:00", "14:10:00", "Dars"), (7, "14:15:00", "14:55:00", "Dars"),
			(8, "15:00:00", "15:40:00", "Dars"),
			(0, "15:45:00", "16:05:00", "Tanaffus"),
			(9, "16:10:00", "16:50:00", "Dars"), (10, "16:55:00", "17:35:00", "Dars"),
		],
	},
]


def custom_fieldlar():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	print("Custom fieldlar: OK")


def qongiroqlar():
	for q in QONGIROQLAR:
		if frappe.db.exists("Qongiroq Jadvali", q["nomi"]):
			print(f"  bor edi: {q['nomi']}")
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Qongiroq Jadvali",
				"nomi": q["nomi"],
				"sinf_pattern": q["sinf_pattern"],
				"tartib": q["tartib"],
				"faol": 1,
				"qatorlar": [
					{"dars_raqami": n, "boshlanish": b, "tugash": t, "turi": tur}
					for n, b, t, tur in q["qatorlar"]
				],
			}
		)
		doc.insert(ignore_permissions=True)
		print(f"  yaratildi: {doc.name}")


def sinf_guruhlarini_belgila():
	"""Mavjud 21 Student Group — 'Sinf' turi bilan belgilanadi."""
	n = 0
	for sg in frappe.get_all("Student Group", pluck="name"):
		if not frappe.db.get_value("Student Group", sg, "custom_guruh_turi"):
			frappe.db.set_value("Student Group", sg, "custom_guruh_turi", "Sinf", update_modified=False)
			n += 1
	print(f"Sinf deb belgilandi: {n} ta guruh")


def hammasi():
	zavuch_roli()
	oqituvchi_roli()
	operator_ruxsatlari()
	custom_fieldlar()
	qongiroqlar()
	sinf_guruhlarini_belgila()
	try:
		from target_zenit.dars_jadvali.baholash import choraklar_ornat
		choraklar_ornat()
	except Exception:
		frappe.log_error("choraklar_ornat", frappe.get_traceback())
	baholash_sozlash()
	workspace_yorliqlari()
	frappe.db.commit()
	print("Dars jadvali setup tugadi.")


# ------------------------------------------------- Baholash sozlamalari (zavuch uchun)
# Standart baho turlari (vazn = chorak bahosi «Vaznli» hisoblanganda ishlatiladi)
BAHO_TURLARI = [
	("Og'zaki", "O", 1.0),
	("Uy vazifa", "UV", 1.0),
	("Mustaqil ish", "MI", 1.5),
	("Nazorat ishi", "NI", 3.0),
	("Chorak nazorati", "CHN", 3.0),
]


def baholash_sozlash():
	"""«Baholash Sozlamalari» (Single) va standart «Baho Turi» ro'yxati — idempotent.
	Zavuch bu yerda baho shkalasi, chorak bahosi usuli, kechikish va uy vazifa
	qoidalarini belgilaydi."""
	if not frappe.db.exists("DocType", "Baho Turi"):
		return
	for nom, qisqa, vazn in BAHO_TURLARI:
		if not frappe.db.exists("Baho Turi", nom):
			frappe.get_doc({
				"doctype": "Baho Turi", "turi": nom, "qisqa": qisqa,
				"vazn": vazn, "faol": 1,
			}).insert(ignore_permissions=True)
			print(f"Baho Turi yaratildi: {nom}")

	# Single yozuv — birinchi marta standart qiymatlar bilan yaratiladi
	if frappe.db.exists("DocType", "Baholash Sozlamalari") \
			and not frappe.db.get_singles_value("Baholash Sozlamalari", "shkala"):
		doc = frappe.get_single("Baholash Sozlamalari")
		doc.shkala = "5 ballik"
		doc.max_baho = 5
		doc.otish_bahosi = 3
		doc.past_baho = 3
		doc.chorak_usuli = "O'rtacha"
		doc.yaxlitlash = "Matematik"
		doc.min_baho_soni = 3
		doc.tuzatish_muddati_kun = 7
		doc.kechikish_yoqilgan = 1
		doc.kechikish_daqiqa = 10
		doc.kechikish_yoqlik = 3
		doc.uv_tekshirish = 1
		doc.uv_default_max_ball = 5
		doc.uv_bajarmaslik_limit = 2
		doc.rag_qizil_ortacha = 3
		doc.rag_sariq_ortacha = 4
		doc.rag_qizil_davomat = 80
		doc.rag_sariq_davomat = 90
		doc.ketma_ket_past = 3
		doc.trend_sezgirlik = 0.3
		doc.save(ignore_permissions=True)
		print("Baholash Sozlamalari yaratildi (5 ballik, o'rtacha)")
	try:
		from target_zenit.dars_jadvali import sozlamalar as _soz
		_soz.kesh_tozalash()
	except Exception:
		pass


# ----------------------------------------------------- Workspace yorliqlari
YORLIQLAR = [
	# (workspace, shortcut nomi, tur, link/doctype)
	("Zavuch", "Baholash sozlamalari", "DocType", "Baholash Sozlamalari"),
	("Zavuch", "Baho turlari", "DocType", "Baho Turi"),
	("Zavuch", "Chorak baholari", "DocType", "Chorak Bahosi"),
	("O'qituvchi", "Chorak baholari", "DocType", "Chorak Bahosi"),
	("O'qituvchi", "Uy vazifa natijalari", "DocType", "Uy Vazifa Natijasi"),
]


def workspace_yorliqlari():
	"""Zavuch va O'qituvchi panellariga baholash yorliqlari (idempotent)."""
	import json as _json

	for ws_name, nom, tur, link in YORLIQLAR:
		if not frappe.db.exists("Workspace", ws_name) or not frappe.db.exists("DocType", link):
			continue
		ws = frappe.get_doc("Workspace", ws_name)
		if any((sc.label or "") == nom for sc in ws.shortcuts):
			continue
		ws.append("shortcuts", {"label": nom, "type": tur, "link_to": link, "doc_view": ""})
		# content'ga ham qo'shamiz (panelda ko'rinishi uchun)
		try:
			content = _json.loads(ws.content or "[]")
		except Exception:
			content = []
		if not any(c.get("data", {}).get("shortcut_name") == nom for c in content):
			if not any(c.get("data", {}).get("text", "").find("Baholash") >= 0 for c in content):
				content.append({"type": "header",
				                "data": {"text": "<span class=\"h5\">Baholash</span>", "col": 12}})
			content.append({"type": "shortcut", "data": {"shortcut_name": nom, "col": 3}})
			ws.content = _json.dumps(content)
		ws.flags.ignore_permissions = True
		ws.save(ignore_permissions=True)
		print(f"Workspace «{ws_name}» -> yorliq «{nom}»")


# ---------------------------------------------------------------- Zavuch roli
ZAVUCH = "Zavuch"

# ERPNext/Education doctype'lari uchun Custom DocPerm (o'zimiznikilarga
# ruxsat doctype JSON'ida yozilgan)
ZAVUCH_PERMS = {
	# doctype: (read, write, create, delete)
	"Student Group": (1, 1, 1, 0),
	"Course": (1, 1, 1, 0),
	"Instructor": (1, 1, 1, 0),
	"Course Schedule": (1, 1, 1, 1),
	"Student Attendance": (1, 1, 1, 0),
	"Room": (1, 1, 1, 0),
	"Academic Year": (1, 0, 0, 0),
	"Academic Term": (1, 1, 1, 0),
	"Program": (1, 0, 0, 0),
	"Student": (1, 0, 0, 0),
	"Holiday List": (1, 0, 0, 0),
	# Kunlik yo'qlama (pul ma'lumoti yo'q). DIQQAT: Employee ATAYLAB berilmaydi —
	# unda oylik summa bor; yo'qlama sahifasi xodim ismlarini server tomonda oladi.
	"Attendance": (1, 1, 1, 0),
}


def zavuch_roli():
	"""Zavuch (o'quv ishlari bo'yicha direktor o'rinbosari) roli va ruxsatlari."""
	if not frappe.db.exists("Role", ZAVUCH):
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": ZAVUCH,
				"desk_access": 1,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)
		print(f"Rol yaratildi: {ZAVUCH}")

	from frappe.permissions import add_permission, update_permission_property

	for dt, (r, w, c, d) in ZAVUCH_PERMS.items():
		if not frappe.db.exists("DocType", dt):
			continue
		bor = frappe.db.exists(
			"Custom DocPerm", {"parent": dt, "role": ZAVUCH, "permlevel": 0}
		) or frappe.db.exists("DocPerm", {"parent": dt, "role": ZAVUCH, "permlevel": 0})
		if not bor:
			add_permission(dt, ZAVUCH, 0)
		for prop, val in (
			("read", r), ("write", w), ("create", c), ("delete", d),
			("report", 1), ("export", 1), ("print", 1), ("share", 1),
		):
			update_permission_property(dt, ZAVUCH, 0, prop, val, validate=False)
	print(f"{ZAVUCH} ruxsatlari: {len(ZAVUCH_PERMS)} doctype")


# ---------------------------------------------------------------- O'qituvchi roli
OQITUVCHI = "O'qituvchi"

# ERPNext/Education doctype'lari uchun Custom DocPerm (o'zimiznikilarga JSON'da).
# O'qituvchi asosan O'QIYDI; baho/dars bajarilishini maxsus sahifalar orqali yozadi.
# DIQQAT: Employee / Salary / Payment / GL — ATAYLAB BERILMAYDI (pul ma'lumoti).
OQITUVCHI_PERMS = {
	# doctype: (read, write, create, delete)
	"Student Group": (1, 0, 0, 0),
	"Student": (1, 0, 0, 0),
	"Course": (1, 0, 0, 0),
	"Instructor": (1, 0, 0, 0),
	"Course Schedule": (1, 0, 0, 0),
	"Student Attendance": (1, 0, 0, 0),
	"Room": (1, 0, 0, 0),
	"Academic Year": (1, 0, 0, 0),
	"Academic Term": (1, 0, 0, 0),
	"Program": (1, 0, 0, 0),
}


def oqituvchi_roli():
	"""O'qituvchi roli + ruxsatlari. User YARATILMAYDI (foydalanuvchi o'zi qiladi).
	O'z doctype'larimizga ruxsat JSON'da (Dars Natijasi/Oquv Reja/Dars Bajarilishi/
	Jadval Yozuvi/Jadval Ozgarishi/Qongiroq Jadvali)."""
	if not frappe.db.exists("Role", OQITUVCHI):
		frappe.get_doc({
			"doctype": "Role", "role_name": OQITUVCHI,
			"desk_access": 1, "is_custom": 1,
		}).insert(ignore_permissions=True)
		print(f"Rol yaratildi: {OQITUVCHI}")

	from frappe.permissions import add_permission, update_permission_property

	for dt, (r, w, c, d) in OQITUVCHI_PERMS.items():
		if not frappe.db.exists("DocType", dt):
			continue
		bor = frappe.db.exists(
			"Custom DocPerm", {"parent": dt, "role": OQITUVCHI, "permlevel": 0}
		) or frappe.db.exists("DocPerm", {"parent": dt, "role": OQITUVCHI, "permlevel": 0})
		if not bor:
			add_permission(dt, OQITUVCHI, 0)
		for prop, val in (
			("read", r), ("write", w), ("create", c), ("delete", d),
			("report", 1), ("export", r), ("print", 1), ("share", 0),
		):
			update_permission_property(dt, OQITUVCHI, 0, prop, val, validate=False)
	print(f"{OQITUVCHI} ruxsatlari: {len(OQITUVCHI_PERMS)} doctype")


def zavuch_test(user="zavuch_test@target.local"):
	"""Diagnostika: Zavuch roli bilan sahifa va endpointlar ishlaydimi."""
	if not frappe.db.exists("User", user):
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": user,
				"first_name": "Zavuch",
				"last_name": "Test",
				"send_welcome_email": 0,
				"user_type": "System User",
			}
		)
		u.append("roles", {"role": ZAVUCH})
		u.insert(ignore_permissions=True)
		frappe.db.commit()

	frappe.set_user(user)
	print("roles:", sorted(frappe.get_roles()))
	from frappe.desk.desk_page import getpage

	for pg in ("dars-jadvali", "mening-jadvalim"):
		try:
			getpage(pg)
			print(f"  getpage({pg}): OK")
		except Exception as e:
			print(f"  getpage({pg}) XATO:", type(e).__name__, e)
	try:
		from target_zenit.target_zenit.page.dars_jadvali import dars_jadvali as dj

		d = dj.get_data()
		print("  get_data: OK — yozuv:", d["jami_yozuv"], "| sinf:", len(d["sinflar"]))
	except Exception as e:
		print("  get_data XATO:", type(e).__name__, e)
	for dt in ("Jadval Yozuvi", "Student Group", "Course Schedule", "Instructor"):
		print(f"  {dt}: read={frappe.has_permission(dt, 'read')} write={frappe.has_permission(dt, 'write')}")
	frappe.set_user("Administrator")


def fayl_royxatdan_otkaz(nom="Umumiy_dars_jadvali.xlsx"):
	"""Test: sites/.../public/files ichidagi faylni File doctype'ga ro'yxatdan o'tkazish."""
	if frappe.db.exists("File", {"file_name": nom}):
		print("File yozuvi bor edi")
		return
	frappe.get_doc(
		{"doctype": "File", "file_name": nom, "file_url": f"/files/{nom}", "is_private": 0}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	print("File yozuvi yaratildi:", nom)


def after_migrate():
	"""Deploy (migrate) paytida avtomatik: rol, custom fieldlar, qo'ng'iroq jadvali.
	Idempotent — har migrate'da bemalol ishlayveradi."""
	try:
		hammasi()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "dars_jadvali setup after_migrate")


# Xojakbar_Operator — yo'qlama va dars jadvali bo'yicha TO'LIQ huquq
OPERATOR = "Xojakbar_Operator"
OPERATOR_PERMS = {
	"Attendance": (1, 1, 1, 1),
	"Jadval Versiyasi": (1, 1, 1, 1),
	"Jadval Yozuvi": (1, 1, 1, 1),
	"Dars Bloki": (1, 1, 1, 1),
	"Qongiroq Jadvali": (1, 1, 1, 1),
	"Student Group": (1, 1, 1, 0),
	"Course": (1, 1, 1, 0),
	"Instructor": (1, 1, 1, 0),
	"Course Schedule": (1, 1, 1, 1),
	"Room": (1, 1, 1, 0),
}


def operator_ruxsatlari():
	"""Operatorga yo'qlama/jadval bo'yicha to'liq huquq (o'qish-yozish-o'chirish)."""
	from frappe.permissions import add_permission, update_permission_property

	if not frappe.db.exists("Role", OPERATOR):
		print(f"{OPERATOR} roli yo'q — o'tkazib yuborildi")
		return
	for dt, (r, w, c, d) in OPERATOR_PERMS.items():
		if not frappe.db.exists("DocType", dt):
			continue
		bor = frappe.db.exists("Custom DocPerm", {"parent": dt, "role": OPERATOR, "permlevel": 0}) \
			or frappe.db.exists("DocPerm", {"parent": dt, "role": OPERATOR, "permlevel": 0})
		if not bor:
			add_permission(dt, OPERATOR, 0)
		for prop, val in (("read", r), ("write", w), ("create", c), ("delete", d),
						  ("report", 1), ("export", 1), ("print", 1), ("share", 1)):
			update_permission_property(dt, OPERATOR, 0, prop, val, validate=False)
	print(f"{OPERATOR} ruxsatlari: {len(OPERATOR_PERMS)} doctype")
