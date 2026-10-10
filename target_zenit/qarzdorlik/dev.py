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


def test_sotuv_nazorati():
	"""Sotuv nazorati paneli: rollar bo'yicha ko'rinish tekshiruvi."""
	from target_zenit.target_zenit.page.investor_dashboard import investor_dashboard as inv

	for user in ("Administrator", "xojakbar@gmail.com", "sotuv_menejer@gmail.com"):
		frappe.set_user(user)
		try:
			d = inv.get_sotuv_nazorati()
			print(
				f"{user:28} faqat_ozi={d['faqat_ozi']!s:5} "
				f"menejerlar={len(d['menejerlar'])} aloqalar={len(d['aloqalar'])} "
				f"qongiroq={d['jami']['qongiroq']}"
			)
		except Exception as e:
			print(f"{user:28} XATO: {type(e).__name__}: {str(e)[:80]}")
	frappe.set_user("Administrator")


def test_tarif_hisob():
	"""Tarif avtomatikasi: foiz -> chegirma -> yakuniy -> oylik."""
	nom = frappe.db.get_value("Student", {"enabled": 1}, "name")
	doc = frappe.get_doc("Student", nom)
	asl = {f: doc.get(f) for f in (
		"custom_tariff_amount", "custom_discount_foiz", "custom_discount_amount",
		"custom_final_amount", "custom_monthly_payment")}

	print("1) FOIZ BILAN: tarif 60 000 000, chegirma 20%")
	doc.custom_tariff_amount = 60_000_000
	doc.custom_discount_foiz = 20
	doc.save(ignore_permissions=True)
	doc.reload()
	print(f"   chegirma = {doc.custom_discount_amount:,.0f} | yakuniy = {doc.custom_final_amount:,.0f} "
	      f"| oylik = {doc.custom_monthly_payment:,.0f}")
	ok1 = (doc.custom_discount_amount == 12_000_000 and doc.custom_final_amount == 48_000_000
	       and doc.custom_monthly_payment == 4_800_000)
	print("   KUTILGAN: 12 000 000 | 48 000 000 | 4 800 000 ->", "✓ TO'G'RI" if ok1 else "✗ XATO")

	print("2) SUMMA BILAN: chegirma 19 000 000 qo'lda (79 mln tarifda)")
	doc.custom_tariff_amount = 79_000_000
	doc.custom_discount_foiz = 0
	doc.custom_discount_amount = 19_000_000
	doc.save(ignore_permissions=True)
	doc.reload()
	print(f"   foiz = {doc.custom_discount_foiz} | yakuniy = {doc.custom_final_amount:,.0f} "
	      f"| oylik = {doc.custom_monthly_payment:,.0f}")
	ok2 = doc.custom_final_amount == 60_000_000 and doc.custom_monthly_payment == 6_000_000
	print("   KUTILGAN: ~24.05% | 60 000 000 | 6 000 000 ->", "✓ TO'G'RI" if ok2 else "✗ XATO")

	# asl holatga qaytarish
	for f, v in asl.items():
		doc.set(f, v)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"3) {nom} asl holatiga qaytarildi: yakuniy={doc.custom_final_amount:,.0f}")


def test_tarif_drift():
	"""Yumaloq bo'lmagan foizli shartnoma tegilmasdan saqlanganda siljimasligi."""
	nom = frappe.db.sql("""SELECT name FROM tabStudent WHERE enabled=1
		AND custom_tariff_amount>0 AND custom_discount_foiz>0
		AND ABS(custom_tariff_amount*custom_discount_foiz/100 - custom_discount_amount)>1
		LIMIT 1""")
	if not nom:
		print("Bunday yozuv yo'q")
		return
	nom = nom[0][0]
	oldin = frappe.db.get_value("Student", nom, ["custom_discount_amount", "custom_final_amount",
		"custom_monthly_payment"], as_dict=True)
	doc = frappe.get_doc("Student", nom)
	doc.save(ignore_permissions=True)  # hech narsa o'zgartirmasdan saqlash
	frappe.db.commit()
	keyin = frappe.db.get_value("Student", nom, ["custom_discount_amount", "custom_final_amount",
		"custom_monthly_payment"], as_dict=True)
	print(f"{nom}\n  oldin: {oldin}\n  keyin: {keyin}")
	print("  ->", "✓ O'ZGARMADI" if oldin == keyin else "✗ SILJIDI")


def test_zavuch_yoqlama(user="zavuch_test@target.local"):
	"""Zavuch: yo'qlama ishlaydimi va PUL ma'lumoti yopiqmi?"""
	from frappe.desk.desk_page import getpage

	from target_zenit import yoqlama

	frappe.set_user(user)
	print("roles:", sorted(frappe.get_roles()))
	for pg in ("yoqlama", "dars-jadvali"):
		try:
			getpage(pg)
			print(f"  sahifa {pg}: OCHILADI")
		except Exception as e:
			print(f"  sahifa {pg}: XATO {type(e).__name__}")
	try:
		d = yoqlama.get_data()
		pul_maydonlari = {k for r in d["qatorlar"] for k in r
						  if k in ("oylik", "summa", "custom_oylik", "bonus", "jami")}
		print(f"  yo'qlama: OK — {len(d['qatorlar'])} xodim, {len(d['kunlar'])} kun")
		print(f"  qaytgan pul maydonlari: {pul_maydonlari or 'YO`Q ✓'}")
	except Exception as e:
		print("  yo'qlama XATO:", type(e).__name__, e)

	print("  --- pul ma'lumotiga kirish urinishlari ---")
	for dt in ("Employee", "Salary Slip", "Salary Structure", "Tabel Oylik", "Payment Entry", "GL Entry"):
		print(f"  {dt:18} o'qish: {frappe.has_permission(dt, 'read')}")
	try:
		from target_zenit.target_zenit.api import oylik_tabel

		oylik_tabel.get_tabel()
		print("  oylik tabel (pul): OCHILDI — MUAMMO!")
	except Exception as e:
		print(f"  oylik tabel (pul): YOPIQ ✓ ({type(e).__name__})")
	frappe.set_user("Administrator")


def test_yoqlama_yozish(user="zavuch_test@target.local"):
	"""Zavuch yo'qlama belgilay oladimi va u oylik tabelga tushadimi?"""
	from frappe.utils import nowdate

	from target_zenit import yoqlama

	emp = frappe.db.get_value("Instructor", {"employee": ["is", "set"]}, "employee")
	sana = nowdate()
	frappe.set_user(user)
	try:
		r1 = yoqlama.belgila(emp, sana, "Keldi")
		print("  Keldi deb belgilandi:", r1)
		r2 = yoqlama.belgila(emp, sana, "Kelmadi")
		print("  Kelmadi deb o'zgartirildi:", r2)
		r3 = yoqlama.belgila(emp, sana, "tozalash")
		print("  Tozalandi:", r3)
	except Exception as e:
		print("  XATO:", type(e).__name__, e)
	frappe.set_user("Administrator")
	qolgan = frappe.db.get_value("Attendance", {"employee": emp, "attendance_date": sana,
											   "docstatus": ["<", 2]}, "name")
	print("  Bazada qolgan yozuv:", qolgan or "yo'q (tozalandi) ✓")
	frappe.db.commit()


def test_zavuch_sidebar(user="zavuch_test@target.local"):
	"""Zavuch yon panelida qaysi workspace'lar ko'rinadi?"""
	from frappe.desk.desktop import get_workspace_sidebar_items

	frappe.set_user(user)
	try:
		items = get_workspace_sidebar_items().get("pages", [])
		print("ko'rinadigan workspace'lar:", [p.get("name") for p in items])
	except Exception as e:
		print("XATO:", type(e).__name__, e)
	ws = frappe.get_doc("Workspace", "Zavuch")
	print("Zavuch ruxsati (has_permission):", frappe.has_permission("Workspace", doc=ws))
	frappe.set_user("Administrator")


def test_operator_yoqlama(user="xojakbar@gmail.com"):
	"""Operator: yo'qlama to'liq huquq bilan ishlaydimi?"""
	from frappe.desk.desk_page import getpage
	from frappe.utils import nowdate

	from target_zenit import yoqlama

	frappe.set_user(user)
	try:
		getpage("yoqlama")
		print("  sahifa: OCHILADI")
	except Exception as e:
		print("  sahifa XATO:", type(e).__name__)
	try:
		d = yoqlama.get_data()
		print(f"  get_data: OK — {len(d['qatorlar'])} xodim")
	except Exception as e:
		print("  get_data XATO:", type(e).__name__, e)
	emp = frappe.db.get_value("Instructor", {"employee": ["is", "set"]}, "employee")
	try:
		print("  belgila(Keldi):", yoqlama.belgila(emp, nowdate(), "Keldi"))
		print("  belgila(tozalash):", yoqlama.belgila(emp, nowdate(), "tozalash"))
	except Exception as e:
		print("  belgila XATO:", type(e).__name__, e)
	for dt in ("Attendance", "Jadval Yozuvi", "Course Schedule"):
		print(f"  {dt:16} o'qish={frappe.has_permission(dt,'read')} yozish={frappe.has_permission(dt,'write')} "
			  f"yaratish={frappe.has_permission(dt,'create')} o'chirish={frappe.has_permission(dt,'delete')}")
	frappe.set_user("Administrator")
	frappe.db.commit()


def test_kim_yoqlamaga_kiradi():
	"""Yo'qlamaga kim kira oladi — xojakbar@gmail.com (Xojakbar_Operator) vs
	operator@gmail.com (Operator). Faqat birinchisiga ruxsat berilgan."""
	from frappe.desk.desk_page import getpage

	from target_zenit import yoqlama

	for user in ("xojakbar@gmail.com", "operator@gmail.com"):
		frappe.set_user(user)
		rollar = [r for r in frappe.get_roles() if "perator" in r or "avuch" in r]
		try:
			getpage("yoqlama")
			sahifa = "OCHILADI"
		except Exception:
			sahifa = "yopiq"
		try:
			d = yoqlama.get_data()
			api = f"OK ({len(d['qatorlar'])} xodim)"
		except Exception as e:
			api = f"yopiq ({type(e).__name__})"
		print(f"{user:24} rollari={rollar} | sahifa: {sahifa} | API: {api}")
	frappe.set_user("Administrator")


def test_yoqlama_bugun_qoidasi():
	"""Zavuch faqat bugunni belgilay oladimi; operator esa istalgan kunni?"""
	from frappe.utils import add_days, nowdate

	from target_zenit import yoqlama

	emp = frappe.db.get_value("Instructor", {"employee": ["is", "set"]}, "employee")
	bugun, kecha = nowdate(), add_days(nowdate(), -1)

	for user in ("zavuch_test@target.local", "xojakbar@gmail.com"):
		frappe.set_user(user)
		d = yoqlama.get_data()
		print(f"\n{user}  (faqat_bugun={d['faqat_bugun']})")
		for sana, nom in ((bugun, "BUGUN"), (kecha, "kecha")):
			try:
				yoqlama.belgila(emp, sana, "Keldi")
				yoqlama.belgila(emp, sana, "tozalash")
				print(f"   {nom:6} ({sana}): ✓ belgilay oldi")
			except Exception as e:
				print(f"   {nom:6} ({sana}): ✗ {type(e).__name__} — {str(e)[:70]}")
	frappe.set_user("Administrator")
	frappe.db.commit()


def test_avto_yangilanish():
	"""Qarzdorlik paneli avtomatik yangilanadimi:
	1) yangi shartnomali o'quvchi -> reja + qarz ishi ochiladimi?
	2) yangi Sales Invoice (nachisleniya) -> rejaga tushadimi?"""
	from frappe.utils import nowdate

	from target_zenit.qarzdorlik import engine

	# --- 1) Yangi o'quvchi (shartnomali) ---
	s = frappe.get_doc({
		"doctype": "Student", "first_name": "ZZTest Avto", "custom_shartnoma_qilindi": 1,
		"custom_tariff": "Kontrak", "custom_tariff_amount": 60_000_000,
		"custom_discount_foiz": 20, "joining_date": nowdate(),
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"1) Yangi o'quvchi: {s.name} | yakuniy={s.custom_final_amount:,.0f} oylik={s.custom_monthly_payment:,.0f}")
	print("   reja (darhol):", frappe.db.exists("Tolov Rejasi", {"student": s.name}) or "YO'Q")

	engine.nightly()
	frappe.db.commit()
	tr = frappe.db.exists("Tolov Rejasi", {"student": s.name})
	qi = frappe.db.exists("Qarz Ishi", {"student": s.name})
	print("   nightly'dan keyin -> reja:", tr or "YO'Q", "| qarz ishi:", qi or "YO'Q")

	# --- 2) Yangi Sales Invoice (kitob/forma) ---
	mavjud = frappe.db.get_value("Tolov Rejasi", {"holat": "Faol"}, ["name", "student", "customer"], as_dict=True)
	oldin = frappe.db.count("Tolov Rejasi Oyi", {"parent": mavjud.name})
	# eng oddiy SI: mavjud itemdan
	item = frappe.db.get_value("Sales Invoice Item", {"item_code": ["like", "Kitob%"]}, "item_code") or "Kitob"
	try:
		si = frappe.get_doc({
			"doctype": "Sales Invoice", "customer": mavjud.customer, "currency": "UZS",
			"conversion_rate": 1, "posting_date": nowdate(), "due_date": nowdate(),
			"items": [{"item_code": item, "qty": 1, "rate": 1_500_000}],
		})
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()
		frappe.db.commit()
		keyin = frappe.db.count("Tolov Rejasi Oyi", {"parent": mavjud.name})
		print(f"\n2) Yangi SI {si.name} ({mavjud.student}): reja qatorlari {oldin} -> {keyin}",
			  "✓ avto qo'shildi" if keyin > oldin else "✗ qo'shilmadi")
		si.cancel()
		frappe.db.commit()
	except Exception as e:
		print("\n2) SI XATO:", type(e).__name__, str(e)[:120])

	# tozalash
	for dt, nm in (("Qarz Ishi", qi), ("Tolov Rejasi", tr)):
		if nm:
			frappe.delete_doc(dt, nm, force=1, ignore_permissions=True)
	frappe.delete_doc("Student", s.name, force=1, ignore_permissions=True)
	frappe.db.commit()
	print("\n(test ma'lumotlari tozalandi)")


def test_si_avto(student="EDU-STU-2026-00591"):
	"""Yangi Sales Invoice (nachisleniya) rejaga avtomatik tushadimi?"""
	from frappe.utils import nowdate

	tr = frappe.db.get_value("Tolov Rejasi", {"student": student, "holat": "Faol"},
							 ["name", "customer", "qarz_bugun"], as_dict=True)
	if not tr:
		print("Reja topilmadi:", student)
		return
	oldin_q = frappe.db.count("Tolov Rejasi Oyi", {"parent": tr.name})
	si = frappe.get_doc({
		"doctype": "Sales Invoice", "customer": tr.customer, "currency": "UZS",
		"conversion_rate": 1, "posting_date": nowdate(), "due_date": nowdate(),
		"items": [{"item_code": "Kitob", "qty": 1, "rate": 1_500_000}],
	})
	si.flags.ignore_permissions = True
	si.insert()
	si.submit()
	frappe.db.commit()
	keyin_q = frappe.db.count("Tolov Rejasi Oyi", {"parent": tr.name})
	keyin_qarz = frappe.db.get_value("Tolov Rejasi", tr.name, "qarz_bugun")
	print(f"SI {si.name} submit -> qatorlar {oldin_q} -> {keyin_q} | "
		  f"qarz {tr.qarz_bugun:,.0f} -> {keyin_qarz:,.0f}",
		  "✓ AVTO" if keyin_q > oldin_q else "✗")
	si.cancel()
	frappe.db.commit()
	oxiri = frappe.db.count("Tolov Rejasi Oyi", {"parent": tr.name, "holat": ["!=", "Bekor"]})
	print(f"SI bekor qilindi -> faol qatorlar: {oxiri}",
		  "✓ qator Bekor bo'ldi" if oxiri == oldin_q else "✗")
