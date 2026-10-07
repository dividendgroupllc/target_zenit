# Copyright (c) 2026, Target Zenit
# FAQAT LOKAL DEV: qarzdorlik modulini sinash uchun test ma'lumotlari.
# Prod'da ishlatilmaydi — prod'da tariflar allaqachon kiritilgan.
import frappe

TEST_STUDENTS = [
	"EDU-STU-2026-00490",  # ~66M to'lagan -> avans stsenariysi
	"EDU-STU-2026-00493",  # 1M to'lagan -> qisman
	"EDU-STU-2026-00151",  # 0 to'lagan -> to'liq qarzdor
	"EDU-STU-2026-00265",  # 400k to'lagan -> qisman
]


def check_page():
	"""Diagnostika: qarzdorlik Page hujjati va unga js/css biriktirilishini tekshirish."""
	doc = frappe.get_doc("Page", "qarzdorlik")
	print("standard:", doc.standard, "| module:", doc.module, "| roles:", [r.role for r in doc.roles])
	try:
		doc.load_assets()
		print("script len:", len(doc.script or ""), "| style len:", len(doc.style or ""))
	except Exception as e:
		print("load_assets XATO:", e)


def make_test_plan(student="EDU-STU-2026-00151", monthly=5_000_000):
	"""To'lovsiz o'quvchiga test Tolov Rejasi — qarzdor stsenariyni sinash uchun.
	Keyin: engine.nightly() -> Qarz Ishi ochilishi kerak."""
	from target_zenit.qarzdorlik import engine

	doc = frappe.get_doc(
		{
			"doctype": "Tolov Rejasi",
			"student": student,
			"academic_year": "2026-2027",
			"holat": "Faol",
			"oylik_tolov": monthly,
			"yakuniy_summa": monthly * 10,
			"oylar": [
				{
					"oy_label": lbl,
					"due_date": due,
					"amount": monthly,
				}
				for lbl, due in [
					("Sentabr 2026", "2026-09-01"), ("Oktabr 2026", "2026-10-01"),
					("Noyabr 2026", "2026-11-01"), ("Dekabr 2026", "2026-12-01"),
					("Yanvar 2027", "2027-01-01"), ("Fevral 2027", "2027-02-01"),
					("Mart 2027", "2027-03-01"), ("Aprel 2027", "2027-04-01"),
					("May 2027", "2027-05-01"), ("Iyun 2027", "2027-06-01"),
				]
			],
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	qarz = engine.recompute_plan(doc.name, sync_case=True)
	frappe.db.commit()
	print("TR:", doc.name, "qarz:", qarz)
	case = frappe.db.get_value(
		"Qarz Ishi", {"student": student}, ["name", "qarz_summa", "aging_bucket", "ishlov_status", "masul"], as_dict=True
	)
	print("Qarz Ishi:", case)


def test_call_flow(case=None):
	"""Qo'ng'iroq kaskadi testi: AY (va'da) -> PTP ochilishi + QI status o'tishi."""
	from frappe.utils import add_days, nowdate

	case = case or frappe.db.get_value(
		"Qarz Ishi", {"ishlov_status": ["not in", ["Yopildi - To'landi", "Yopildi - Boshqa"]]}
	)
	ay = frappe.get_doc(
		{
			"doctype": "Aloqa Yozuvi",
			"qarz_ishi": case,
			"kanal": "Qo'ng'iroq",
			"aloqa_natijasi": "Gaplashildi",
			"hisob_natijasi": "Va'da berdi",
			"komment": "Test: ota-ona 3 kundan keyin to'lashga va'da berdi",
			"keyingi_harakat": "Va'dani kutish",
			"keyingi_sana": add_days(nowdate(), 4),
			"vada_summa": 10_000_000,
			"vada_sana": add_days(nowdate(), 3),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	print("AY:", ay.name)
	print("QI:", frappe.db.get_value(
		"Qarz Ishi", case,
		["ishlov_status", "keyingi_aloqa", "urinishlar_soni", "oxirgi_aloqa"], as_dict=True))
	print("PTP:", frappe.db.get_value(
		"Tolov Vadasi", {"qarz_ishi": case, "holat": "Ochiq"},
		["name", "vada_sana", "vada_summa", "student_name"], as_dict=True))


def test_ptp_breach():
	"""Va'da buzilishi testi: ochiq PTP sanasini o'tmishga surib, check_ptps ni sinash."""
	from frappe.utils import add_days, nowdate

	from target_zenit.qarzdorlik import engine

	ptp = frappe.db.get_value("Tolov Vadasi", {"holat": "Ochiq"}, ["name", "qarz_ishi"], as_dict=True)
	if not ptp:
		print("Ochiq PTP yo'q")
		return
	frappe.db.set_value("Tolov Vadasi", ptp.name, "vada_sana", add_days(nowdate(), -3))
	frappe.db.commit()
	engine.check_ptps()
	frappe.db.commit()
	print("PTP:", frappe.db.get_value(
		"Tolov Vadasi", ptp.name, ["holat", "amal_summa", "tekshirilgan_sana"], as_dict=True))
	print("QI:", frappe.db.get_value(
		"Qarz Ishi", ptp.qarz_ishi,
		["ishlov_status", "buzilgan_vadalar", "keyingi_aloqa"], as_dict=True))
	print("ToDo:", frappe.db.get_value(
		"ToDo", {"reference_type": "Qarz Ishi", "reference_name": ptp.qarz_ishi, "status": "Open"},
		["name", "allocated_to"], as_dict=True))


def set_test_tariffs():
	"""4 ta test o'quvchiga oylik 5M / yakuniy 50M tarif qo'yadi (ORM orqali)."""
	for name in TEST_STUDENTS:
		frappe.db.set_value(
			"Student",
			name,
			{
				"custom_monthly_payment": 5_000_000,
				"custom_final_amount": 50_000_000,
				"custom_tariff": "Kontrak",
			},
		)
	frappe.db.commit()
	print("OK:", TEST_STUDENTS)


def check_user_access(user="xojakbar@gmail.com", page="xodim-qarzdorlik"):
	"""Diagnostika: foydalanuvchi sahifani ocha oladimi va endpoint ishlaydimi."""
	frappe.set_user(user)
	print("roles:", sorted(frappe.get_roles()))
	try:
		from frappe.desk.desk_page import getpage

		getpage(page)
		print("getpage: OK")
	except Exception as e:
		print("getpage XATO:", type(e).__name__, e)
	try:
		from target_zenit.target_zenit.page.xodim_qarzdorlik import xodim_qarzdorlik as xq

		d = xq.get_data()
		print("get_data: OK, qatorlar:", len(d["rows"]), "| stats:", d["stats"])
	except Exception as e:
		print("get_data XATO:", type(e).__name__, e)
	frappe.set_user("Administrator")


def check_sotuv_access(user="sotuv_menejer@gmail.com"):
	"""Sotuv menejer: qarzdorlik sahifasi, endpointlar va workspace ko'rinishi."""
	from frappe.desk.desk_page import getpage

	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as qp

	frappe.set_user(user)
	print("roles:", sorted(frappe.get_roles()))
	for nom, fn in [
		("getpage(qarzdorlik)", lambda: getpage("qarzdorlik")),
		("get_data", qp.get_data),
	]:
		try:
			res = fn()
			qo = len(res["cases"]) if isinstance(res, dict) and "cases" in res else "OK"
			print(f"{nom}: OK ({qo})")
		except Exception as e:
			print(f"{nom} XATO:", type(e).__name__, e)
	try:
		case = frappe.db.get_value("Qarz Ishi", {}, "name")
		d = qp.get_case(case)
		print("get_case: OK, oylar:", len(d["months"]), "| to'lovlar:", len(d["payments"]))
	except Exception as e:
		print("get_case XATO:", type(e).__name__, e)
	ws = [
		w.name
		for w in frappe.get_all("Workspace", fields=["name"])
		if frappe.has_permission("Workspace", doc=w.name)
	]
	print("ko'rinadigan workspace'lar:", [w for w in ws if "arz" in w or "otuv" in w])
	frappe.set_user("Administrator")


def check_sotuv_perms(user="sotuv_menejer@gmail.com"):
	"""Sotuv menejer qo'ng'iroq yozuvi qila oladimi (yaratish/yozish huquqlari)."""
	frappe.set_user(user)
	for dt, ptype in [
		("Aloqa Yozuvi", "create"), ("Aloqa Yozuvi", "write"),
		("Qarz Ishi", "write"), ("Qarz Ishi", "read"),
		("Tolov Rejasi", "read"), ("Tolov Vadasi", "read"),
	]:
		print(f"{dt} / {ptype}:", frappe.has_permission(dt, ptype))
	frappe.set_user("Administrator")
