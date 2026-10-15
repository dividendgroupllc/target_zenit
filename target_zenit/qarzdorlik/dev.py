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


def test_si_kassa_pe(student="EDU-STU-2026-00247"):
	"""To'liq zanjir: Sales Invoice -> Kassa -> Payment Entry (bog'langan holda)."""
	from frappe.utils import nowdate

	from target_zenit.target_zenit.doctype.kassa.kassa import get_customer_invoices

	cust = frappe.db.get_value("Student", student, "customer")
	invs = get_customer_invoices(cust)
	if not invs:
		print("Ochiq nachisleniya yo'q:", cust)
		return
	inv = invs[0]
	print(f"Mijoz: {cust}")
	print(f"Nachisleniya: {inv['name']} | {inv['itemlar']} | qoldiq {inv['outstanding']:,.0f}")

	k = frappe.get_doc({
		"doctype": "Kassa", "date": nowdate(), "transaction_type": "Приход",
		"company": frappe.db.get_value("Sales Invoice", inv["name"], "company"),
		"mode_of_payment": "Наличый UZS", "cash_account": "Наличый UZS - TZ",
		"party_type": "Customer", "party": cust,
		"sales_invoice": inv["name"], "amount": inv["outstanding"],
		"remarks": "TEST: SI -> Kassa -> PE zanjiri",
	})
	k.flags.ignore_permissions = True
	k.insert()
	k.submit()
	frappe.db.commit()
	print(f"\nKassa: {k.name} -> yaratilgan hujjat: {k.linked_doctype} {k.linked_entry}")

	pe = frappe.get_doc("Payment Entry", k.linked_entry)
	print(f"PE: {pe.name} | {pe.paid_amount:,.0f} {pe.paid_from_account_currency}")
	print("PE references (nachisleniyaga bog'lanish):")
	for r in pe.references:
		print(f"   {r.reference_doctype} {r.reference_name} -> taqsimlandi {r.allocated_amount:,.0f}")
	qoldiq = frappe.db.get_value("Sales Invoice", inv["name"], "outstanding_amount")
	print(f"\nNachisleniya qoldig'i: {inv['outstanding']:,.0f} -> {qoldiq:,.0f}",
		  "✓ YOPILDI" if qoldiq <= 0.005 else "(qisman)")

	# tozalash
	k.cancel()
	frappe.db.commit()
	oxirgi = frappe.db.get_value("Sales Invoice", inv["name"], "outstanding_amount")
	print(f"Kassa bekor qilindi -> nachisleniya qoldig'i qaytdi: {oxirgi:,.0f}",
		  "✓" if abs(oxirgi - inv["outstanding"]) < 1 else "✗")


def test_kassa_fifo(student="EDU-STU-2026-00247", summa=8_000_000):
	"""Faktura TANLANMAGAN holat: to'lov eng eskisidan boshlab taqsimlanadimi?"""
	from frappe.utils import nowdate

	from target_zenit.target_zenit.doctype.kassa.kassa import get_customer_invoices

	cust = frappe.db.get_value("Student", student, "customer")
	oldin = get_customer_invoices(cust)
	print(f"Ochiq nachisleniyalar ({cust}):")
	for i in oldin[:4]:
		print(f"   {i['sana']}  {i['name']:24} {i['itemlar'][:20]:22} qoldiq {i['outstanding']:>12,.0f}")

	k = frappe.get_doc({
		"doctype": "Kassa", "date": nowdate(), "transaction_type": "Приход",
		"company": frappe.db.get_value("Sales Invoice", oldin[0]["name"], "company"),
		"mode_of_payment": "Наличый UZS", "cash_account": "Наличый UZS - TZ",
		"party_type": "Customer", "party": cust, "amount": summa,
		"remarks": "TEST: faktura tanlanmagan — FIFO",
	})
	k.flags.ignore_permissions = True
	k.insert()
	k.submit()
	frappe.db.commit()

	pe = frappe.get_doc("Payment Entry", k.linked_entry)
	print(f"\nKassa {k.name} -> PE {pe.name} ({summa:,.0f} so'm) taqsimoti:")
	for r in pe.references:
		print(f"   {r.reference_name:24} -> {r.allocated_amount:>12,.0f}")
	print(f"   Taqsimlanmagan (avans): {summa - sum(r.allocated_amount for r in pe.references):,.0f}")

	k.cancel()
	frappe.db.commit()
	print("\n(bekor qilindi — qoldiqlar qaytdi)")


def test_adriel_stsenariy(student_like="Adriel"):
	"""Foydalanuvchi skrinshotidagi holat: 2 800 000 kerak, 2 714 000 to'landi,
	14 000 qaytim -> qoldiq 100 000 bo'lishi kerak."""
	from frappe.utils import nowdate

	from target_zenit.qarzdorlik import engine

	tr = frappe.db.sql("""SELECT tr.name, tr.customer FROM `tabTolov Rejasi` tr
		JOIN tabStudent s ON s.name=tr.student
		WHERE s.student_name LIKE %s AND tr.holat='Faol' LIMIT 1""",
		(student_like + "%",), as_dict=True)
	if not tr:
		print("Reja topilmadi")
		return
	tr = tr[0]
	kassalar = []

	def kassa(tur, summa):
		k = frappe.get_doc({
			"doctype": "Kassa", "date": nowdate(), "transaction_type": tur,
			"company": "Target Zenit", "mode_of_payment": "Наличый UZS",
			"cash_account": "Наличый UZS - TZ", "party_type": "Customer",
			"party": tr.customer, "amount": summa, "remarks": "TEST stsenariy",
		})
		k.flags.ignore_permissions = True
		k.insert()
		k.submit()
		kassalar.append(k)
		return k

	kassa("Приход", 2_714_000)
	kassa("Расход", 14_000)
	frappe.db.commit()
	engine.recompute_plan(tr.name, sync_case=True)
	frappe.db.commit()

	rows = frappe.db.sql("""SELECT oy_label, amount, paid_amount, qaytim, outstanding, holat
		FROM `tabTolov Rejasi Oyi` WHERE parent=%s AND holat!='Bekor'
		ORDER BY due_date LIMIT 2""", (tr.name,), as_dict=True)
	print("TO'LOV JADVALI:")
	for r in rows:
		print(f"  {r.oy_label[:28]:30} summa={r.amount:>11,.0f} to'langan={r.paid_amount:>11,.0f} "
			  f"qaytim={r.qaytim:>9,.0f} qoldiq={r.outstanding:>11,.0f}  {r.holat}")
	kerak = rows[0].amount - 2_714_000 + 14_000
	print(f"\nKutilgan qoldiq: {kerak:,.0f} | chiqdi: {rows[0].outstanding:,.0f}",
		  "✓ TO'G'RI" if abs(rows[0].outstanding - kerak) < 1 else "✗ XATO")

	for k in reversed(kassalar):
		k.cancel()
	frappe.db.commit()
	engine.recompute_plan(tr.name, sync_case=True)
	frappe.db.commit()
	print("(test kassalari bekor qilindi)")


def test_faqat_tanlangan(student="EDU-STU-2026-00247"):
	"""Yangi qoida: faqat kassir tanlagan nachisleniya bog'lanadi.
	1) nachisleniya TANLANMAGAN -> hech narsa bog'lanmaydi (avans)
	2) nachisleniya TANLANGAN   -> faqat o'shanga bog'lanadi"""
	from frappe.utils import nowdate

	from target_zenit.target_zenit.doctype.kassa.kassa import get_customer_invoices

	cust = frappe.db.get_value("Student", student, "customer")
	invs = get_customer_invoices(cust)
	print(f"Mijoz: {cust} | ochiq nachisleniyalar: {len(invs)} ta")
	for i in invs[:3]:
		print(f"   {i['sana']}  {i['itemlar'][:22]:24} qoldiq {i['outstanding']:>12,.0f}")

	def kassa(summa, inv=None):
		k = frappe.get_doc({
			"doctype": "Kassa", "date": nowdate(), "transaction_type": "Приход",
			"company": "Target Zenit", "mode_of_payment": "Наличый UZS",
			"cash_account": "Наличый UZS - TZ", "party_type": "Customer",
			"party": cust, "amount": summa, "sales_invoice": inv,
			"remarks": "TEST: faqat tanlangan qoida",
		})
		k.flags.ignore_permissions = True
		k.insert()
		k.submit()
		frappe.db.commit()
		pe = frappe.get_doc("Payment Entry", k.linked_entry)
		return k, pe

	print("\n1) Nachisleniya TANLANMAGAN (8 000 000):")
	k1, pe1 = kassa(8_000_000)
	print(f"   PE {pe1.name} -> bog'langan nachisleniyalar: {len(pe1.references)}",
		  "✓ bog'lanmadi (avans)" if not pe1.references else "✗ BOG'LANDI")

	print("\n2) Nachisleniya TANLANGAN (kitob/forma):")
	kf = next((i for i in invs if "Kitob" in (i["itemlar"] or "")), invs[0])
	k2, pe2 = kassa(kf["outstanding"], kf["name"])
	print(f"   PE {pe2.name} -> ", end="")
	for r in pe2.references:
		print(f"{r.reference_name} = {r.allocated_amount:,.0f}", end=" ")
	print("✓ faqat tanlangani" if len(pe2.references) == 1 else "✗")
	qoldiq = frappe.db.get_value("Sales Invoice", kf["name"], "outstanding_amount")
	print(f"   {kf['name']} qoldig'i: {kf['outstanding']:,.0f} -> {qoldiq:,.0f}")

	for k in (k2, k1):
		k.cancel()
	frappe.db.commit()
	print("\n(test kassalari bekor qilindi)")


def test_je_tolov(student="EDU-STU-2026-00247"):
	"""Journal Entry orqali to'lov qarzdorlikda hisobga olinishini sinash:
	1) JE kredit (debitorka) -> to'lov sifatida qo'shiladi;
	2) JE debet -> qaytim sifatida ayiriladi;
	3) JE nachisleniyaga bog'langan (reference) -> ikki marta hisoblanmaydi."""
	from frappe.utils import flt, nowdate

	from target_zenit.qarzdorlik import engine

	tr_name = frappe.db.get_value("Tolov Rejasi", {"student": student, "holat": "Faol"}, "name")
	tr = frappe.get_doc("Tolov Rejasi", tr_name)
	cust, window = tr.customer, engine._plan_payment_window(tr)
	debit_to = frappe.db.get_value(
		"Sales Invoice", {"customer": cust, "docstatus": 1}, "debit_to") or "Debitors - TZ"
	kassa_hisob = "Наличый UZS - TZ"

	def hol(sarlavha):
		t, q = engine._payments_split(cust, window)
		engine.recompute_plan(tr_name, sync_case=True)
		frappe.db.commit()
		d = frappe.db.get_value(
			"Tolov Rejasi", tr_name, ["jami_tolangan", "jami_qaytim", "qarz_bugun"], as_dict=True)
		print(f"  {sarlavha:34} to'lov={t:>13,.0f} qaytim={q:>11,.0f} "
			  f"| rejada to'langan={flt(d.jami_tolangan):>13,.0f} qarz={flt(d.qarz_bugun):>13,.0f}")
		return t, q

	print(f"O'quvchi: {tr.student_name} | mijoz: {cust} | hisob: {debit_to}")
	t0, _q0 = hol("0) boshlang'ich")

	def je(summa, yonalish, ref=None):
		"""yonalish='kredit' -> to'lov; 'debet' -> qaytim."""
		mijoz_qator = {
			"account": debit_to, "party_type": "Customer", "party": cust,
			"reference_type": "Sales Invoice" if ref else None, "reference_name": ref,
		}
		kassa_qator = {"account": kassa_hisob}
		if yonalish == "kredit":
			mijoz_qator["credit_in_account_currency"] = summa
			kassa_qator["debit_in_account_currency"] = summa
		else:
			mijoz_qator["debit_in_account_currency"] = summa
			kassa_qator["credit_in_account_currency"] = summa
		d = frappe.get_doc({
			"doctype": "Journal Entry", "voucher_type": "Journal Entry", "multi_currency": 1,
			"company": "Target Zenit", "posting_date": nowdate(),
			"user_remark": f"TEST JE {yonalish}", "accounts": [mijoz_qator, kassa_qator],
		})
		d.flags.ignore_permissions = True
		d.insert()
		# Nachisleniyaga bog'langan qatorda ERPNext hisob-faktura kursini
		# qo'llaydi -> bazaviy (USD) tomonda tiyinlik farq chiqadi. Haqiqiy
		# buxgalteriyada bu kurs farqi qatori bilan yopiladi — testda ham shunday.
		farq = flt(d.total_debit) - flt(d.total_credit)
		if abs(farq) > 0.005:
			gl_hisob = frappe.db.get_value(
				"Company", "Target Zenit", "exchange_gain_loss_account")
			qator = {"account": gl_hisob}
			qator["credit_in_account_currency" if farq > 0 else "debit_in_account_currency"] = abs(farq)
			d.append("accounts", qator)
			d.save()
		d.submit()
		frappe.db.commit()
		return d

	yaratilgan = []
	j1 = je(5_000_000, "kredit")
	yaratilgan.append(j1)
	t1, q1 = hol("1) JE kredit +5 000 000")
	print("     to'lov 5 000 000 ga oshdi" if abs(t1 - t0 - 5_000_000) < 1 else "     ✗ XATO")

	j2 = je(1_500_000, "debet")
	yaratilgan.append(j2)
	_t2, q2 = hol("2) JE debet 1 500 000 (qaytim)")
	print("     qaytim 1 500 000 ga oshdi" if abs(q2 - q1 - 1_500_000) < 1 else "     ✗ XATO")

	si = frappe.db.get_value(
		"Sales Invoice", {"customer": cust, "docstatus": 1, "outstanding_amount": [">", 0]},
		["name", "outstanding_amount"], as_dict=True)
	if si:
		qator = next((r for r in tr.oylar if r.manba_hujjat == si.name), None)
		j3 = je(flt(si.outstanding_amount), "kredit", ref=si.name)
		yaratilgan.append(j3)
		hol(f"3) JE {si.name} ga bog'langan")
		tr2 = frappe.get_doc("Tolov Rejasi", tr_name)
		q2_ = next((r for r in tr2.oylar if r.manba_hujjat == si.name), None)
		if qator and q2_:
			print(f"     SI qatori: to'langan {flt(qator.paid_amount):,.0f} -> "
				  f"{flt(q2_.paid_amount):,.0f} | qoldiq {flt(q2_.outstanding):,.0f}")
		jami = sum(flt(r.paid_amount) for r in tr2.oylar)
		print(f"     jadval jami to'langan={jami:,.0f} vs sof to'lov="
			  f"{engine._payments_since(cust, window):,.0f}")

	print("\n  Panel ro'yxati (ilk 6):")
	for r in engine.get_payments(cust, window)[:6]:
		print(f"    {r['posting_date']}  {r['doctype']:<14} {r['amount_uzs']:>13,.0f}  {r['mode_of_payment']}")

	for d in reversed(yaratilgan):
		d.reload()
		d.cancel()
	frappe.db.commit()
	engine.recompute_plan(tr_name, sync_case=True)
	frappe.db.commit()
	hol("4) hammasi bekor qilingandan keyin")


def test_nachisleniya_jadval(student=None):
	"""Jadval haqiqiy nachisleniya bilan ishlayaptimi — bitta o'quvchida tekshirish.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_nachisleniya_jadval
	"""
	import json

	from target_zenit.qarzdorlik import engine

	if not student:
		student = frappe.db.sql(
			"""SELECT tr.student FROM `tabTolov Rejasi` tr
			   WHERE tr.holat='Faol' AND EXISTS (
			     SELECT 1 FROM `tabPayment Entry` pe WHERE pe.docstatus=1
			       AND pe.party=tr.customer AND pe.payment_type='Receive')
			   LIMIT 1"""
		)[0][0]
	tr_name = frappe.db.get_value("Tolov Rejasi", {"student": student, "holat": "Faol"})
	engine.recompute_plan(tr_name, sync_case=True)
	frappe.db.commit()
	tr = frappe.get_doc("Tolov Rejasi", tr_name)
	x = engine.plan_xulosa(tr)
	print(f"\n=== {tr.student_name} ({student}) — {tr_name} ===")
	print(f"shartnoma {tr.yakuniy_summa:,.0f} | nachislangan {x['oquv']['nachislangan']:,.0f} "
	      f"| to'langan {x['oquv']['tolangan']:,.0f} | qarz {x['jami']['qarz']:,.0f} "
	      f"| avans {x['jami']['avans']:,.0f}")
	for m in x["oylar"]:
		print(f"  {m['oy_label']:<16} {m['due_date']!s} nachis={m['nachislangan']:>12,.0f} "
		      f"reja={m['reja']:>12,.0f} tol={m['tolangan']:>12,.0f} qold={m['qoldiq']:>12,.0f} {m['holat']}")
	for q in x["qoshimcha"]:
		print(f"  [{q['nom']}] nachis={q['nachislangan']:,.0f} tol={q['tolangan']:,.0f} qold={q['qoldiq']:,.0f}")
	print(json.dumps(x["jami"], indent=1, default=str))


def nachisleniya_tasir():
	"""Butun bazada o'lchash: nachisleniyaga o'tish qarzga qanday ta'sir qildi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.nachisleniya_tasir
	"""
	from target_zenit.qarzdorlik import engine

	oldin = frappe.db.sql(
		"""SELECT COALESCE(SUM(qarz_bugun),0), COALESCE(SUM(jami_hisoblangan),0),
		          COALESCE(SUM(jami_tolangan),0), COALESCE(SUM(avans_summa),0)
		   FROM `tabTolov Rejasi` WHERE holat='Faol'"""
	)[0]
	rejalar = frappe.get_all("Tolov Rejasi", filters={"holat": "Faol"}, pluck="name")
	xato = 0
	for n in rejalar:
		try:
			engine.recompute_plan(n, sync_case=False)
		except Exception:
			xato += 1
			frappe.log_error(frappe.get_traceback(), f"nachisleniya_tasir: {n}")
	frappe.db.commit()
	keyin = frappe.db.sql(
		"""SELECT COALESCE(SUM(qarz_bugun),0), COALESCE(SUM(jami_hisoblangan),0),
		          COALESCE(SUM(jami_tolangan),0), COALESCE(SUM(avans_summa),0)
		   FROM `tabTolov Rejasi` WHERE holat='Faol'"""
	)[0]
	nomlar = ("qarz_bugun", "nachislangan", "tolangan", "avans")
	print(f"\nrejalar: {len(rejalar)}, xato: {xato}")
	for i, nom in enumerate(nomlar):
		print(f"  {nom:<14} {oldin[i]:>18,.0f} -> {keyin[i]:>18,.0f}  ({keyin[i]-oldin[i]:+,.0f})")
	for h, n, sm in frappe.db.sql(
		"""SELECT o.holat, COUNT(*), COALESCE(SUM(o.amount),0) FROM `tabTolov Rejasi Oyi` o
		   JOIN `tabTolov Rejasi` tr ON tr.name=o.parent WHERE tr.holat='Faol'
		   GROUP BY o.holat ORDER BY 2 DESC"""
	):
		print(f"  qator {h:<18} {n:>5} ta  {sm:>18,.0f}")


def test_panel_api(user="Administrator"):
	"""Panel endpointlari: get_data (faol/ketgan) + get_case (xulosa bilan).
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_panel_api
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user(user)
	faol = panel.get_data()
	ketgan = panel.get_data(ketganlar=1)
	print(f"faol ishlar: {len(faol['cases'])}, ketganlar: {len(ketgan['cases'])}, "
	      f"stats.ketgan_soni={faol['stats']['ketgan_soni']}, "
	      f"ketgan_huquqi={faol['ketgan_huquqi']}")
	assert all(not c["ketgan"] for c in faol["cases"]), "faol ro'yxatda ketgan bor!"
	assert all(c["ketgan"] for c in ketgan["cases"]), "ketganlar ro'yxatida faol bor!"

	c = max(faol["cases"], key=lambda x: x["qarz_summa"])
	d = panel.get_case(c["name"])
	x = d["xulosa"]
	print(f"\nkarta: {c['student_name']} — qarz {c['qarz_summa']:,.0f}")
	print(f"  oylar: {len(x['oylar'])}, qoshimcha: {[q['nom'] for q in x['qoshimcha']]}")
	print(f"  oquv: {x['oquv']}")
	print(f"  jami: {x['jami']}")
	# Jami tekshiruvi: o'quv + qo'shimcha = jami
	assert abs(x["jami"]["nachislangan"] - x["oquv"]["nachislangan"]
	           - x["qoshimcha_jami"]["nachislangan"]) < 1, "jami nachisleniya mos kelmadi"
	assert abs(x["jami"]["qarz"] - c["qarz_summa"]) < 1, (
		f"xulosa qarzi ({x['jami']['qarz']:,.0f}) Qarz Ishi summasiga "
		f"({c['qarz_summa']:,.0f}) teng emas")
	print("\nOK — xulosa va qarz summasi mos")


def test_ketgan_oqim():
	"""«O'quvchi ketdi» oqimi: belgilash -> ro'yxatdan chiqishi -> qaytarish.
	Oxirida hamma o'zgarish qaytariladi (test ma'lumot qoldirmaydi).
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_ketgan_oqim
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	case = panel.get_data()["cases"][0]
	print(f"sinov: {case['student_name']} ({case['student']}) — ish {case['name']}")

	panel.ketgan_belgilash(case["name"], sabab="Sinov (avtomatik qaytariladi)")
	st = frappe.db.get_value("Student", case["student"], ["enabled", "date_of_leaving"], as_dict=True)
	faol = {c["name"] for c in panel.get_data()["cases"]}
	ketgan = {c["name"] for c in panel.get_data(ketganlar=1)["cases"]}
	print(f"  belgilangandan keyin: enabled={st.enabled}, ketish={st.date_of_leaving}, "
	      f"faol ro'yxatda={case['name'] in faol}, ketganlar ro'yxatida={case['name'] in ketgan}")
	assert st.enabled == 0 and st.date_of_leaving, "Student hujjatiga yozilmadi"
	assert case["name"] not in faol, "ketgan o'quvchi faol ro'yxatda qoldi"
	assert case["name"] in ketgan, "ketganlar ro'yxatida ko'rinmadi"

	reja = frappe.db.get_value("Qarz Ishi", case["name"], "tolov_rejasi")
	bekor = frappe.db.count("Tolov Rejasi Oyi", {"parent": reja, "holat": "Bekor"})
	panel.qaytardi(case["name"])
	st = frappe.db.get_value("Student", case["student"], ["enabled", "date_of_leaving"], as_dict=True)
	faol = {c["name"] for c in panel.get_data()["cases"]}
	print(f"  qaytarilgandan keyin: enabled={st.enabled}, ketish={st.date_of_leaving}, "
	      f"faol ro'yxatda={case['name'] in faol}")
	assert st.enabled == 1 and not st.date_of_leaving, "qaytarish ishlamadi"
	assert case["name"] in faol, "qaytarilgandan keyin ro'yxatga qaytmadi"
	tr = frappe.db.get_value("Qarz Ishi", case["name"], "tolov_rejasi")
	qoldi = frappe.db.count("Tolov Rejasi Oyi", {"parent": tr, "holat": "Bekor"})
	print(f"  bekor qilingan oylar: qaytarishdan oldin {bekor} -> hozir {qoldi}")
	assert qoldi == 0, f"ketish paytida bekor bo'lgan {qoldi} oy tiklanmadi"
	print("OK — ketgan/qaytarish oqimi ishlaydi, ma'lumot tiklandi")


def test_qongiroq_boglanish(case="QI-2026-145130"):
	"""Qo'ng'iroq -> qarzdorlik kartasi bog'lanishi (raqam bo'yicha).

	Serverdagi haqiqiy ma'lumot namunasi bo'yicha sinov qo'ng'iroqlari yaratiladi
	(Android manbasi, turli raqam formatlari), panel kartasida ko'rinishi
	tekshiriladi va oxirida HAMMASI o'chiriladi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_qongiroq_boglanish
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	qi = frappe.db.get_value(
		"Qarz Ishi", case, ["student", "student_name", "payer_phone"], as_dict=True
	)
	print(f"ish: {case} — {qi.student_name}, to'lovchi {qi.payer_phone}")
	raqamlar = panel._case_raqamlar(qi.student, qi.payer_phone)
	print(f"kartaning raqamlari: {raqamlar}")
	assert raqamlar, "o'quvchida raqam topilmadi"

	# Serverda uchragan formatlar: "+998...", "998...", "9 xonali", bo'sh raqam
	xom = qi.payer_phone.replace("+998", "")          # 999386709 (9 xonali)
	namunalar = [
		(qi.payer_phone, 95, 1, "Ota-ona to'lashga va'da berdi"),
		(xom, 32, 1, None),
		("+998" + xom, 0, 0, None),
		(None, 52, 1, None),                          # raqamsiz — bog'lanmasligi kerak
	]
	yaratilgan = []
	try:
		for i, (raqam, suhbat, yozuv, izoh) in enumerate(namunalar):
			d = frappe.get_doc(
				{
					"doctype": "Telefon Qongirogi",
					"asterisk_uniqueid": f"dev-sinov-{i}-{frappe.generate_hash(length=6)}",
					"yonalish": "Chiquvchi" if i % 2 == 0 else "Kiruvchi",
					"holat": "Yozuv bor" if yozuv else "Yangi",
					"manba": "Android",
					"boshlandi": add_to_date(now_datetime(), hours=-i - 1),
					"tugash_sababi": "Javob berildi" if suhbat else "Javob yo'q",
					"tashqi_raqam": raqam,
					"suhbat_vaqti": suhbat,
					"yozuv_bor": yozuv,
					"izoh": izoh,
				}
			).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
			print(f"  {d.name}: tashqi={raqam} -> normal={d.normal_telefon}")
		frappe.db.commit()

		d = panel.get_case(case)
		qlar = d["qongiroqlar"]
		print(f"\nkartada {len(qlar)} qo'ng'iroq (jami {len(yaratilgan)} yaratildi, 1 tasi raqamsiz):")
		for q in qlar:
			print(f"  {q['boshlandi']} {q['yonalish']:<9} {q['menejer']:<14} "
			      f"suhbat={q['suhbat_vaqti']}s audio={q['audio']} kim={q['kim']} izoh={q['izoh']}")
		assert len(qlar) == 3, f"3 ta bog'langan qo'ng'iroq kutilgan edi, {len(qlar)} chiqdi"
		assert all(q["kim"] for q in qlar), "raqam egasi aniqlanmadi"
		assert sum(q["audio"] for q in qlar) == 2, "audio belgisi noto'g'ri"

		data = panel.get_data()
		ro = [c for c in data["cases"] if c["name"] == case]
		if ro:
			print(f"navbatda: qongiroq_soni={ro[0]['qongiroq_soni']} "
			      f"yozuv_soni={ro[0]['yozuv_soni']} oxirgi={ro[0]['oxirgi_qongiroq']}")
			assert ro[0]["qongiroq_soni"] == 3, "ro'yxatdagi hisob mos kelmadi"
		# «Qo'ng'iroq yozib olindi» KPI va filtri
		st = data["stats"]
		yozuvlilar = [c["student_name"] for c in data["cases"] if c["yozuv_soni"]]
		print(f"KPI: yozuvli odam={st['yozuvli']}, jami yozuv={st['yozuv_jami']}, "
		      f"ro'yxat={yozuvlilar}")
		assert st["yozuvli"] == len(yozuvlilar) >= 1, "KPI hisobi mos kelmadi"
		assert st["yozuv_jami"] >= 2, "yozuvlar soni kam chiqdi"
		print("\nOK — qo'ng'iroqlar raqam bo'yicha kartaga bog'landi")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		print(f"({len(yaratilgan)} sinov qo'ng'irog'i o'chirildi)")


def test_ism_jonli(case="QI-2026-142230"):
	"""Panel ismni Student'dan JONLI o'qiyaptimi (nusxadan emas).

	O'quvchining ismi vaqtincha o'zgartiriladi (faqat Student jadvalida, nusxalar
	ataylab eskicha qoldiriladi), panel ro'yxati va kartasi yangi ismni
	ko'rsatishi tekshiriladi, keyin hammasi tiklanadi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_ism_jonli
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	student = frappe.db.get_value("Qarz Ishi", case, "student")
	eski = frappe.db.get_value("Student", student, "student_name")
	eski_nusxa = frappe.db.get_value("Qarz Ishi", case, "student_name")
	eski_sinf = frappe.db.get_value("Student", student, "custom_sinf_guruh")
	yangi = eski.strip() + " (TUZATILDI)"
	print(f"{student}: '{eski}' -> '{yangi}' (Qarz Ishi nusxasi: '{eski_nusxa}')")
	try:
		# Faqat Student o'zgaradi — nusxalar (Qarz Ishi) ataylab tegilmaydi
		frappe.db.set_value("Student", student, "student_name", yangi, update_modified=False)
		frappe.db.set_value("Student", student, "custom_sinf_guruh", "99 Z(sinov)", update_modified=False)
		frappe.db.commit()
		nusxa = frappe.db.get_value("Qarz Ishi", case, "student_name")
		assert nusxa == eski_nusxa, "nusxa o'zgarib ketdi — sinov sharti buzildi"

		ro = [c for c in panel.get_data()["cases"] if c["name"] == case]
		assert ro, "ish ro'yxatda topilmadi"
		d = panel.get_case(case)
		print(f"  ro'yxat: '{ro[0]['student_name']}' / sinf '{ro[0]['sinf']}'")
		print(f"  karta:   '{d['case']['student_name']}' / sinf '{d['case']['sinf']}'")
		assert ro[0]["student_name"] == yangi, "ro'yxat eski ismni ko'rsatdi"
		assert d["case"]["student_name"] == yangi, "karta eski ismni ko'rsatdi"
		assert ro[0]["sinf"] == "99 Z(sinov)" == d["case"]["sinf"], "sinf jonli olinmadi"
		assert ro[0]["student_name"] == d["case"]["student_name"], "ro'yxat va karta har xil!"

		# To'lovchi bo'limi ham jonli bo'lishi kerak
		eski_tolovchi = frappe.db.get_value("Student", student, "custom_payer_name")
		frappe.db.set_value(
			"Student", student, "custom_payer_name", "Sinov To'lovchi", update_modified=False
		)
		frappe.db.commit()
		try:
			ro2 = next(c for c in panel.get_data()["cases"] if c["name"] == case)
			d2 = panel.get_case(case)
			print(f"  to'lovchi: ro'yxat '{ro2['payer_name']}' / karta '{d2['case']['payer_name']}'")
			assert ro2["payer_name"] == d2["case"]["payer_name"] == "Sinov To'lovchi", (
				"to'lovchi ismi jonli olinmadi"
			)
		finally:
			frappe.db.set_value(
				"Student", student, "custom_payer_name", eski_tolovchi, update_modified=False
			)
			frappe.db.commit()
		print("OK — ism, sinf va to'lovchi Student'dan jonli olinyapti; ro'yxat = karta")
	finally:
		frappe.db.set_value("Student", student, "student_name", eski, update_modified=False)
		frappe.db.set_value("Student", student, "custom_sinf_guruh", eski_sinf, update_modified=False)
		frappe.db.commit()
		print("(ism va sinf tiklandi)")
