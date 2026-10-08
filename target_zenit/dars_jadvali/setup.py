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
	operator_ruxsatlari()
	custom_fieldlar()
	qongiroqlar()
	sinf_guruhlarini_belgila()
	frappe.db.commit()
	print("Dars jadvali setup tugadi.")


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
