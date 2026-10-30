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
	"""Sotuv nazorati sahifasi: rollar bo'yicha ko'rinish tekshiruvi."""
	from target_zenit.target_zenit.page.sotuv_nazorati import sotuv_nazorati as sn

	for user in ("Administrator", "xojakbar@gmail.com", "sotuv_menejer@gmail.com"):
		frappe.set_user(user)
		try:
			d = sn.get_data()
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


def test_bekor_korinmaydi(student="EDU-STU-2026-00591"):
	"""Bekor qilingan nachisleniya panelda ko'rinmasligi kerak.

	Shu o'quvchida bekor qilingan Sales Invoice (docstatus=2) qatorlari bor —
	panel javobida ular bo'lmasligi va summalarga kirmasligi tekshiriladi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_bekor_korinmaydi
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	case = frappe.db.get_value("Qarz Ishi", {"student": student}, "name")
	assert case, f"{student} uchun qarz ishi yo'q"

	tr = frappe.db.get_value("Tolov Rejasi", {"student": student, "holat": "Faol"})
	bekor = frappe.get_all(
		"Tolov Rejasi Oyi",
		filters={"parent": tr, "parenttype": "Tolov Rejasi", "holat": "Bekor"},
		fields=["name", "oy_label", "amount", "manba_hujjat"],
	)
	print(f"{student}: bekor qilingan {len(bekor)} qator")
	for b in bekor:
		si_holat = frappe.db.get_value("Sales Invoice", b.manba_hujjat, "docstatus") if b.manba_hujjat else None
		print(f"  {b.oy_label} — {b.amount:,.0f} (SI {b.manba_hujjat}, docstatus={si_holat})")
	assert bekor, "sinov uchun bekor qilingan qator topilmadi"

	d = panel.get_case(case)
	nomlar = {b.oy_label for b in bekor}
	yomon = [m for m in d["months"] if m["holat"] == "Bekor"]
	assert not yomon, f"panelda bekor qator chiqdi: {yomon}"
	x = d["xulosa"]
	assert not [m for m in x["oylar"] if m["oy_label"] in nomlar and m["nachislangan"]], (
		"xulosada bekor qator summasi bor")
	bekor_summa = sum(b.amount for b in bekor)
	jami_si = sum(q["nachislangan"] for q in x["qoshimcha"])
	print(f"  panel qatorlari: {len(d['months'])} ta (bekorlar yo'q)")
	print(f"  qo'shimcha nachisleniya jami: {jami_si:,.0f} "
	      f"(bekor qilinganlari {bekor_summa:,.0f} kirmagan)")
	print("OK — bekor qilingan nachisleniyalar panelda ko'rinmaydi")


def sinov_izini_tozala(student="EDU-STU-2026-00498"):
	"""Sinov paytida «ketgan» deb belgilanib qolgan o'quvchini tiklash
	(lokal bazadagi iz). Panelning o'z `qaytardi` oqimidan foydalanadi."""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	st = frappe.db.get_value(
		"Student", student, ["student_name", "enabled", "date_of_leaving"], as_dict=True)
	print(f"{student} ({st.student_name}): enabled={st.enabled}, ketish={st.date_of_leaving}")
	case = frappe.db.get_value("Qarz Ishi", {"student": student}, "name")
	if case:
		print("  natija:", panel.qaytardi(case))
	else:
		frappe.db.set_value("Student", student, {"enabled": 1, "date_of_leaving": None})
		frappe.db.commit()
	st = frappe.db.get_value(
		"Student", student, ["enabled", "date_of_leaving"], as_dict=True)
	bekor = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabTolov Rejasi Oyi` o
		   JOIN `tabTolov Rejasi` tr ON tr.name = o.parent
		   WHERE tr.student = %s AND o.holat = 'Bekor'""", (student,))[0][0]
	print(f"  hozir: enabled={st.enabled}, ketish={st.date_of_leaving}, bekor qatorlar={bekor}")


def qaytimli_royxat():
	"""Qaytimi bor hamma o'quvchi: qaytim jadvalga qarz bo'lib yozilganmi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.qaytimli_royxat
	"""
	rows = frappe.db.sql(
		"""SELECT tr.name reja, tr.student, tr.student_name, tr.jami_qaytim,
		          tr.qarz_bugun, tr.avans_summa,
		          (SELECT COALESCE(SUM(o.qaytim), 0) FROM `tabTolov Rejasi Oyi` o
		           WHERE o.parent = tr.name AND o.holat <> 'Bekor') jadvalda
		   FROM `tabTolov Rejasi` tr
		   WHERE tr.holat = 'Faol' AND tr.jami_qaytim > 0
		   ORDER BY tr.jami_qaytim DESC""",
		as_dict=True,
	)
	print(f"qaytimi bor o'quvchilar: {len(rows)} ta\n")
	print(f"{'Oquvchi':<42}{'qaytim':>12}{'jadvalda':>12}{'qarz':>14}{'avans':>14}")
	muammo = 0
	for r in rows:
		belgi = ""
		if r.jadvalda > 0.5:
			belgi = "  <-- oydan yechilgan" if r.avans_summa > 0.5 else "  (avans yo'q)"
			muammo += 1 if r.avans_summa > 0.5 else 0
		print(f"{(r.student_name or '')[:40]:<42}{r.jami_qaytim:>12,.0f}"
		      f"{r.jadvalda:>12,.0f}{r.qarz_bugun:>14,.0f}{r.avans_summa:>14,.0f}{belgi}")
	print(f"\njami qaytim: {sum(r.jami_qaytim for r in rows):,.0f} | "
	      f"jadvalga yozilgan: {sum(r.jadvalda for r in rows):,.0f} | "
	      f"avans borida oydan yechilgani: {muammo} ta")


def test_masul_avto(case="QI-2026-145130", user=None):
	"""Mas'ul oxirgi gaplashgan xodimga avtomatik o'tyaptimi.

	1) telefon qo'ng'irog'i (gaplashilgan bo'lsa ham) -> mas'ul O'ZGARMAYDI;
	2) panelda yozilgan natija (Aloqa Yozuvi, «Javob yo'q» ham) -> o'sha xodimga;
	3) Qarz Ishi'ga qo'lda komment -> o'sha xodimga.
	Oxirida hamma o'zgarish qaytariladi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_masul_avto
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.qarzdorlik import engine

	frappe.set_user("Administrator")
	qi = frappe.db.get_value(
		"Qarz Ishi", case, ["student", "student_name", "payer_phone", "masul"], as_dict=True)
	eski_masul = qi.masul
	# Hozirgi mas'uldan BOSHQA, mas'ul bo'la oladigan foydalanuvchi
	user = user or next(
		u for u in frappe.get_all("Qarz Ishi", pluck="masul", limit_page_length=0)
		if u and u != eski_masul and engine._masul_bola_oladi(u))
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	raqamlar = list(panel._case_raqamlar(qi.student, qi.payer_phone))
	print(f"{case} ({qi.student_name}): mas'ul '{eski_masul}', raqamlar {raqamlar}")
	assert raqamlar, "o'quvchida raqam yo'q"

	yaratilgan, ay = [], None
	try:
		# 1) Javobsiz qo'ng'iroq — mas'ul o'zgarmasligi kerak
		d = frappe.get_doc({
			"doctype": "Telefon Qongirogi", "manba": "Android",
			"asterisk_uniqueid": f"dev-masul-0-{frappe.generate_hash(length=6)}",
			"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), hours=-2),
			"tashqi_raqam": raqamlar[0], "tugash_sababi": "Javob yo'q",
			"suhbat_vaqti": 0, "foydalanuvchi": user,
		}).insert(ignore_permissions=True)
		yaratilgan.append(d.name)
		frappe.db.commit()
		keyin = frappe.db.get_value("Qarz Ishi", case, "masul")
		print(f"  javobsiz qo'ng'iroqdan keyin: '{keyin}'")
		assert keyin == eski_masul, "javobsiz qo'ng'iroq mas'ulni o'zgartirdi"

		# 2) Gaplashilgan qo'ng'iroq ham mas'ulni o'zgartirmaydi: biriktirish
		#    faqat panelda yozilgan ish bo'yicha ketadi
		d = frappe.get_doc({
			"doctype": "Telefon Qongirogi", "manba": "Android",
			"asterisk_uniqueid": f"dev-masul-1-{frappe.generate_hash(length=6)}",
			"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), minutes=-30),
			"tashqi_raqam": raqamlar[0], "tugash_sababi": "Javob berildi",
			"suhbat_vaqti": 95, "foydalanuvchi": user,
		}).insert(ignore_permissions=True)
		yaratilgan.append(d.name)
		frappe.db.commit()
		keyin = frappe.db.get_value("Qarz Ishi", case, "masul")
		print(f"  gaplashilgan qo'ng'iroqdan keyin: '{keyin}' (o'zgarmasligi kerak)")
		assert keyin == eski_masul, "telefon qo'ng'irog'i mas'ulni o'zgartirdi"

		# 3) Panelda BOSHQA menejer «Javob yo'q» deb yozdi — bu ham qilingan ish
		boshqa = user
		frappe.set_user(boshqa)
		ay = frappe.get_doc({
			"doctype": "Aloqa Yozuvi", "qarz_ishi": case, "kanal": "Qo'ng'iroq",
			"aloqa_natijasi": "Javob yo'q",
			"komment": "Sinov: javob bermadi", "keyingi_harakat": "Qayta qo'ng'iroq",
			"keyingi_sana": frappe.utils.nowdate(),
		}).insert(ignore_permissions=True)
		frappe.db.commit()
		frappe.set_user("Administrator")
		keyin = frappe.db.get_value("Qarz Ishi", case, "masul")
		print(f"  «Javob yo'q» yozuvidan keyin: '{keyin}' (kutilgan '{boshqa}')")
		assert keyin == boshqa, "panel yozuvidan keyin mas'ul o'zgarmadi"

		# 4) Qarz Ishi'ga qo'lda komment (yana birinchi menejer) — u ham ish
		frappe.set_user(eski_masul)
		frappe.get_doc("Qarz Ishi", case).add_comment("Comment", "Sinov komment")
		frappe.db.commit()
		frappe.set_user("Administrator")
		engine.masul_yangila(case)
		frappe.db.commit()
		keyin = frappe.db.get_value("Qarz Ishi", case, "masul")
		print(f"  kommentdan keyin: '{keyin}' (kutilgan '{eski_masul}')")
		assert keyin == eski_masul, "komment mas'ulni o'zgartirmadi"
		print("OK — mas'ul oxirgi ishlagan xodimga avtomatik biriktirilyapti")
	finally:
		frappe.set_user("Administrator")
		for c in frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Qarz Ishi", "reference_name": case,
			         "content": ["like", "%Sinov%"]},
			pluck="name",
		):
			frappe.delete_doc("Comment", c, force=True, ignore_permissions=True)
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		if ay:
			for v in frappe.get_all("Tolov Vadasi", filters={"aloqa_yozuvi": ay.name}, pluck="name"):
				frappe.delete_doc("Tolov Vadasi", v, force=True, ignore_permissions=True)
			frappe.delete_doc("Aloqa Yozuvi", ay.name, force=True, ignore_permissions=True)
		frappe.db.set_value("Qarz Ishi", case, "masul", eski_masul, update_modified=False)
		frappe.db.commit()
		print(f"(tozalandi, mas'ul tiklandi: {eski_masul})")


def test_qarz_turi_filtri():
	"""Qarz turi bo'yicha bo'linish va jadval tepasidagi yakun to'g'rimi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_qarz_turi_filtri
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	d = panel.get_data()
	turlar = d["stats"]["turlar"]
	print("Qarz turlari (filtr ro'yxati):")
	for tur, v in turlar.items():
		print(f"  {tur:<22} {v['soni']:>4} ta  {v['summa']:>16,.0f}")

	# Har ishning turlar yig'indisi umumiy qarzga teng bo'lishi kerak
	farqli = []
	for c in d["cases"]:
		s = sum((c.get("qarz_turlari") or {}).values())
		if abs(s - (c["qarz_summa"] or 0)) > 1500:
			farqli.append((c["student_name"], c["qarz_summa"], s))
	print(f"\nturlar yig'indisi qarzga teng emas: {len(farqli)} ta")
	for f in farqli[:5]:
		print(f"   {f[0]}: qarz {f[1]:,.0f} vs turlar {f[2]:,.0f}")

	# Filtr namunasi: faqat Kitob/Forma/Yotoqxonadan qarzi borlar
	for tanlov in (["Kitob"], ["Forma", "Yotoqxona to'lovi"], ["O'quv to'lovi"]):
		mos = [c for c in d["cases"]
		       if set(c.get("qarz_turlari") or {}) & set(tanlov)]
		summa = sum(
			sum((c["qarz_turlari"].get(t) or 0) for t in tanlov) for c in mos)
		print(f"  filtr {tanlov}: {len(mos)} ta o'quvchi, shu tur bo'yicha {summa:,.0f}")
	assert not farqli, "turlar yig'indisi qarz summasiga mos kelmadi"
	print("\nOK — qarz turlari va yakunlar mos")


def test_tel_ruxsat(userlar=None):
	"""Qarzdorlik panelidagi ovoz yozuvi + transkript + AI tahlil qaysi
	rollarga ko'rinadi. Har bir foydalanuvchi uchun: panel ochiladimi,
	qo'ng'iroqlar ro'yxati to'ladimi, yozuvni eshita oladimi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_tel_ruxsat
	"""
	from target_zenit.target_zenit.doctype.telefon_qongirogi.telefon_qongirogi import (
		_hammasini_korishi_mumkin,
	)

	userlar = userlar or [
		"investor@gmail.com", "targetceo@gmail.com", "xojakbar@gmail.com",
		"sotuv_menejer@gmail.com",
	]
	jami = frappe.db.count("Telefon Qongirogi")
	print(f"bazada {jami} ta qo'ng'iroq yozuvi\n")
	for u in userlar:
		if not frappe.db.exists("User", u):
			print(f"{u:<28} — yo'q")
			continue
		frappe.set_user(u)
		rollar = sorted(set(frappe.get_roles(u)) & {
			"investor", "Xojakbar_Operator", "Sotuv meneger", "Sales Manager",
			"System Manager", "Telefoniya Agent"})
		koradi = _hammasini_korishi_mumkin(u)
		oqiy = frappe.has_permission("Telefon Qongirogi", "read")
		nechta = len(frappe.get_list(
			"Telefon Qongirogi", fields=["name"], limit_page_length=0, ignore_permissions=False))
		print(f"{u:<28} rollar={rollar} | doctype o'qish={oqiy} | "
		      f"hammasini ko'radi={koradi} | ro'yxatda {nechta}/{jami}")
	frappe.set_user("Administrator")


def test_investor_suhbatlari(user="investor@gmail.com", case=None):
	"""Investor qarzdorlik kartasida suhbat (ovoz+matn+tahlil) ko'ra oladimi."""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user(user)
	d = panel.get_data()
	case = case or (d["cases"][0]["name"] if d["cases"] else None)
	assert case, "ochiq ish yo'q"
	k = panel.get_case(case)
	q = k["qongiroqlar"]
	print(f"{user}: panel {len(d['cases'])} ta ish; karta {case}")
	print(f"  tel_hammasi={k['tel_hammasi']}, qo'ng'iroqlar={len(q)}")
	for x in q[:5]:
		print(f"   {x['boshlandi']} audio={x['audio']} "
		      f"transkript={'bor' if x.get('transkript') else 'yo‘q'} "
		      f"tahlil={'bor' if x.get('ai_xulosa') else 'yo‘q'} menejer={x['menejer']}")
	frappe.set_user("Administrator")
	return {"ishlar": len(d["cases"]), "qongiroqlar": len(q)}


def test_investor_tahlil_korinishi(case="QI-2026-145130", user="investor@gmail.com"):
	"""To'liq oqim: ovoz yozuvi + transkript + AI tahlili bor qo'ng'iroq
	yaratiladi va INVESTOR uni qarzdorlik kartasida ko'ra olishi tekshiriladi
	(matn to'liq keladimi, pleer manzili ochiladimi). Oxirida o'chiriladi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_investor_tahlil_korinishi
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	qi = frappe.db.get_value("Qarz Ishi", case, ["student", "payer_phone"], as_dict=True)
	raqam = next(iter(panel._case_raqamlar(qi.student, qi.payer_phone)))
	matn = "Menejer: Assalomu alaykum. Ota-ona: Shu oy 15-sanada to'laymiz." * 3
	xulosa = ("MAVZU: Qarz bo'yicha kelishuv\nMIJOZ HOLATI: Ijobiy\n"
	          "VA'DA: 15-sanada to'lash\nDIQQAT: Yo'q")
	d = frappe.get_doc({
		"doctype": "Telefon Qongirogi", "manba": "Android",
		"asterisk_uniqueid": f"dev-investor-{frappe.generate_hash(length=6)}",
		"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), minutes=-20),
		"tashqi_raqam": raqam, "tugash_sababi": "Javob berildi", "suhbat_vaqti": 95,
		"yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3", "holat": "Tahlil qilindi",
		"transkript": matn, "transkript_sozlar": len(matn.split()),
		"ai_xulosa": xulosa, "ai_model": "gemini-sinov",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	try:
		frappe.set_user(user)
		k = panel.get_case(case)
		q = [x for x in k["qongiroqlar"] if x["name"] == d.name]
		print(f"{user}: kartada {len(k['qongiroqlar'])} qo'ng'iroq, tel_hammasi={k['tel_hammasi']}")
		assert q, "investor qo'ng'iroqni ko'rmadi"
		q = q[0]
		print(f"  audio={q['audio']} | transkript {len(q.get('transkript') or '')} belgi "
		      f"({q.get('transkript_sozlar')} so'z) | tahlil {len(q.get('ai_xulosa') or '')} belgi")
		assert q.get("transkript") == matn, "transkript to'liq kelmadi"
		assert q.get("ai_xulosa") == xulosa, "AI tahlil kelmadi"
		# Pleer endpointi: ruxsat tekshiruvi o'tadimi (fayl yo'qligi boshqa xato)
		doc = frappe.get_doc("Telefon Qongirogi", d.name)
		doc.check_permission("read")
		print("  stream_recording ruxsati: OK")
		print("OK — investor ovoz yozuvi, to'liq matn va AI tahlilni ko'ra oladi")
	finally:
		frappe.set_user("Administrator")
		frappe.delete_doc("Telefon Qongirogi", d.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		print("(sinov qo'ng'irog'i o'chirildi)")


def test_sotuv_sahifasi():
	"""Yangi «Sotuv nazorati» sahifasi: Page yozuvi, fayllar, endpoint va
	rollar bo'yicha ko'rinish.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_sotuv_sahifasi
	"""
	import os

	from target_zenit.target_zenit.page.sotuv_nazorati import sotuv_nazorati as sn

	frappe.set_user("Administrator")
	page = frappe.db.get_value("Page", "sotuv-nazorati", ["title", "module"], as_dict=True)
	rollar = frappe.get_all("Has Role", filters={"parent": "sotuv-nazorati",
	                                             "parenttype": "Page"}, pluck="role")
	papka = os.path.dirname(sn.__file__)
	fayllar = sorted(f for f in os.listdir(papka) if not f.startswith("__"))
	print(f"Page: {page} \n  rollar: {sorted(rollar)}\n  fayllar: {fayllar}")
	assert page, "Page yozuvi yaratilmadi (migrate kerak)"
	for kerak in ("sotuv_nazorati.js", "sotuv_nazorati.py", "sotuv_nazorati.json"):
		assert kerak in fayllar, f"{kerak} yo'q"

	# Ko'rinish umumiy bundle'da (sahifa ham, boshqa joy ham shuni ishlatadi)
	import target_zenit

	ildiz = os.path.dirname(target_zenit.__file__)
	for yol in ("public/js/sotuv_nazorati_view.js", "public/css/sotuv_nazorati_view.css"):
		assert os.path.exists(os.path.join(ildiz, yol)), f"{yol} yo'q"
	hooks = frappe.get_hooks("app_include_js") + frappe.get_hooks("app_include_css")
	assert any("sotuv_nazorati_view" in h for h in hooks), "hooks'ga ulanmagan"
	print("  umumiy ko'rinish: public/js + public/css, hooks'da bor")

	# Workspace yorliqlari — investor va qarzdorlik CRM
	for ws in ("Investor", "Qarzdorlik CRM"):
		yorliq = frappe.db.exists("Workspace Shortcut",
		                          {"parent": ws, "link_to": "sotuv-nazorati"})
		print(f"  {ws} workspace yorlig'i: {'bor' if yorliq else 'YO‘Q'}")
		assert yorliq, f"{ws} workspace'ida yorliq yo'q"

	# Endpoint — davr bo'yicha
	d = sn.get_data(from_date=frappe.utils.add_days(frappe.utils.today(), -60))
	print(f"  get_data: menejerlar={len(d['menejerlar'])} aloqalar={len(d['aloqalar'])} "
	      f"jami={ {k: round(v) if isinstance(v, float) else v for k, v in d['jami'].items()} }")

	t = sn.get_telefon(from_date=frappe.utils.add_days(frappe.utils.today(), -60))
	print(f"  get_telefon: qo'ng'iroq={t['jami']['qongiroq']} menejer={len(t['menejerlar'])} "
	      f"o'quvchi={len(t['oquvchilar'])} taklif={t['jami']['taklif']}")

	# Investor dashboardda eski endpoint qolmaganini tekshirish
	from target_zenit.target_zenit.page.investor_dashboard import investor_dashboard as inv

	assert not hasattr(inv, "get_sotuv_nazorati"), "eski endpoint dashboardda qolib ketdi"
	print("  investor dashboardda eski endpoint yo'q — ko'chirish to'liq")

	# Rollar: sotuv menejeri faqat o'zini, nazorat — hammani
	for user in ("xojakbar@gmail.com", "investor@gmail.com", "sotuv_menejer@gmail.com"):
		if not frappe.db.exists("User", user):
			continue
		frappe.set_user(user)
		try:
			r = sn.get_data()
			print(f"  {user:<26} faqat_ozi={r['faqat_ozi']!s:5} menejerlar={len(r['menejerlar'])}")
		except Exception as e:
			print(f"  {user:<26} XATO: {type(e).__name__}: {str(e)[:60]}")
	frappe.set_user("Administrator")
	print("OK — sahifa tayyor")


def test_sotuv_telefon_kesimi(case="QI-2026-145130"):
	"""Investor uchun telefon kesimi: menejer/kun/o'quvchi bo'yicha fakt,
	AI tahlil va ota-ona takliflari ajratilyaptimi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_sotuv_telefon_kesimi
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel
	from target_zenit.target_zenit.page.sotuv_nazorati import sotuv_nazorati as sn

	frappe.set_user("Administrator")
	qi = frappe.db.get_value("Qarz Ishi", case, ["student", "student_name", "payer_phone"], as_dict=True)
	raqam = next(iter(panel._case_raqamlar(qi.student, qi.payer_phone)))
	user = frappe.db.get_value("User", {"enabled": 1, "name": ["like", "%menejer%"]}, "name") or "Administrator"

	namunalar = [
		("Suhbat 1", 95, "MAVZU: Qarz bo'yicha\nNATIJA: Kelishildi\n"
		 "TAKLIF VA SHIKOYAT: Matematika o'qituvchisi yaxshi edi, qaytarsangiz\n"
		 "MIJOZ HOLATI: Ijobiy\nDIQQAT: yo'q"),
		("Suhbat 2", 120, "MAVZU: Eslatma\nNATIJA: Gaplashildi\n"
		 "TAKLIF VA SHIKOYAT: Taklif yo'q\nMIJOZ HOLATI: Neytral\nDIQQAT: yo'q"),
		("Suhbat 3", 60, "MAVZU: Qarz\nNATIJA: Va'da berdi\n"
		 "TAKLIF VA SHIKOYAT: Bolalar nazoratini kuchaytirish kerak, tadbirlar kam\n"
		 "MIJOZ HOLATI: Qarshi\nDIQQAT: yo'q"),
	]
	yaratilgan = []
	try:
		for i, (nom, vaqt, xulosa) in enumerate(namunalar):
			d = frappe.get_doc({
				"doctype": "Telefon Qongirogi", "manba": "Android",
				"asterisk_uniqueid": f"dev-kesim-{i}-{frappe.generate_hash(length=6)}",
				"yonalish": "Chiquvchi" if i % 2 == 0 else "Kiruvchi",
				"boshlandi": add_to_date(now_datetime(), days=-i, hours=-1),
				"tashqi_raqam": raqam, "tugash_sababi": "Javob berildi",
				"suhbat_vaqti": vaqt, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
				"holat": "Tahlil qilindi", "foydalanuvchi": user,
				"transkript": f"{nom}: menejer va ota-ona suhbati matni. " * 10,
				"transkript_sozlar": 90, "ai_xulosa": xulosa, "ai_model": "gemini-sinov",
			}).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
		frappe.db.commit()

		d = sn.get_telefon(from_date=frappe.utils.add_days(frappe.utils.today(), -7))
		j = d["jami"]
		print(f"JAMI: qo'ng'iroq={j['qongiroq']} gaplashildi={j['gaplashildi']} "
		      f"daqiqa={j['daqiqa']} mijoz={j['mijozlar']} o'quvchi={j['oquvchilar']} "
		      f"yozuv={j['yozuv']} tahlil={j['tahlil']} taklif={j['taklif']}")
		m = next((x for x in d["menejerlar"] if x["masul"] == user), None)
		print(f"MENEJER {user}: qo'ng'iroq={m['qongiroq']} kun={m['kunlar_soni']} "
		      f"kunlik_o'rtacha={m['kunlik_ortacha']} daqiqa={m['daqiqa']} "
		      f"noyob_mijoz={m['mijozlar_soni']} o'quvchi={m['oquvchilar_soni']} taklif={m['taklif']}")
		o = next((x for x in d["oquvchilar"] if x["student"] == qi.student), None)
		print(f"O'QUVCHI {qi.student_name.strip()}: qo'ng'iroq={o['qongiroq']} "
		      f"daqiqa={o['daqiqa']} menejer={o['menejerlar']} nima_haqida='{o['oxirgi_mavzu']}'")
		print(f"KUNLIK: {d['kunlik']}")
		print("TAKLIFLAR:")
		for t in d["takliflar"]:
			print(f"   {str(t['sana'])[:16]} · {t['student_name'].strip()} · {t['menejer']}: {t['matn']}")

		assert m and m["qongiroq"] == 3, "menejer kesimi noto'g'ri"
		assert o and o["qongiroq"] == 3, "o'quvchi kesimi noto'g'ri"
		assert len(d["takliflar"]) == 2, f"2 ta taklif kutilgan, {len(d['takliflar'])} chiqdi"
		assert all(t["student"] == qi.student for t in d["takliflar"]), "taklif o'quvchiga bog'lanmadi"
		assert j["tahlil"] == 3 and j["yozuv"] == 3, "yozuv/tahlil hisobi noto'g'ri"
		assert m["kunlik_ortacha"] > 0 and m["daqiqa"] > 4, "kunlik/daqiqa hisobi noto'g'ri"
		print("\nOK — menejer, kun, o'quvchi kesimi va takliflar to'g'ri ajratilyapti")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		print(f"({len(yaratilgan)} sinov qo'ng'irog'i o'chirildi)")


def test_sotuv_sana_filtri(case="QI-2026-145130"):
	"""«Gaplashilgan sana» filtri: bitta kun, bir nechta kun va tartib.

	Tekshiradi: tanlangan kun(lar)dan boshqa suhbat tushmasligi, davr
	avtomatik shu kunlarga sozlanishi, `mavjud_kunlar` filtrdan qat'iy nazar
	to'liq qolishi (tanlagich yo'qolib qolmasin) va o'quvchilar oxirgi
	gaplashilgan sana bo'yicha (yangi tepada) tartiblanishi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_sotuv_sana_filtri
	"""
	from frappe.utils import add_days, add_to_date, now_datetime, today

	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel
	from target_zenit.target_zenit.page.sotuv_nazorati import sotuv_nazorati as sn

	frappe.set_user("Administrator")
	qi = frappe.db.get_value("Qarz Ishi", case, ["student", "payer_phone"], as_dict=True)
	if not qi:      # sinov bazasida aniq ish bo'lmasa — telefoni bor birinchisi
		qi = frappe.db.get_value(
			"Qarz Ishi", {"payer_phone": ["is", "set"]},
			["name", "student", "payer_phone"], as_dict=True)
		assert qi, "telefoni bor Qarz Ishi topilmadi"
		case = qi.name
	raqam = next(iter(panel._case_raqamlar(qi.student, qi.payer_phone)))
	print(f"sinov ishi: {case}")
	user = frappe.db.get_value("User", {"enabled": 1, "name": ["like", "%menejer%"]}, "name") or "Administrator"

	# Uch xil kunga bittadan suhbat: kecha, 3 kun oldin, 5 kun oldin
	kunlar = [add_days(today(), -1), add_days(today(), -3), add_days(today(), -5)]
	yaratilgan = []
	try:
		for i, kun in enumerate(kunlar):
			d = frappe.get_doc({
				"doctype": "Telefon Qongirogi", "manba": "Android",
				"asterisk_uniqueid": f"dev-sana-{i}-{frappe.generate_hash(length=6)}",
				"yonalish": "Chiquvchi",
				"boshlandi": add_to_date(now_datetime(), days=-(2 * i + 1), hours=-1),
				"tashqi_raqam": raqam, "tugash_sababi": "Javob berildi",
				"suhbat_vaqti": 60 + i, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
				"holat": "Tahlil qilindi", "foydalanuvchi": user,
				"ai_xulosa": f"MAVZU: Sinov {i}\nNATIJA: Gaplashildi\n"
				             "TAKLIF VA SHIKOYAT: Taklif yo'q\nMIJOZ HOLATI: Neytral",
			}).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
		frappe.db.commit()

		xom = {"from_date": add_days(today(), -30), "to_date": today()}

		# 1) Bitta kun
		bir = sn.get_telefon(**xom, sanalar=[kunlar[1]])
		olingan = {str(q["boshlandi"])[:10] for q in bir["qongiroqlar"]}
		print(f"1 KUN {kunlar[1]}: qo'ng'iroq={bir['jami']['qongiroq']} "
		      f"kunlar={sorted(olingan)} davr={bir['from_date']}..{bir['to_date']}")
		assert olingan == {kunlar[1]}, f"boshqa kun tushdi: {olingan}"
		assert bir["from_date"] == bir["to_date"] == kunlar[1], "davr kunga sozlanmadi"
		assert bir["sanalar"] == [kunlar[1]], "sanalar qaytmadi"
		assert len(bir["mavjud_kunlar"]) >= 3, "tanlagich kunlari filtrda qisqarib qoldi"

		# 2) Ikki kun (teskari tartibda berilsa ham)
		ikki = sn.get_telefon(**xom, sanalar=f'["{kunlar[0]}", "{kunlar[2]}"]')
		olingan = {str(q["boshlandi"])[:10] for q in ikki["qongiroqlar"]}
		print(f"2 KUN: kunlar={sorted(olingan)} davr={ikki['from_date']}..{ikki['to_date']}")
		assert olingan == {kunlar[0], kunlar[2]}, f"kunlar noto'g'ri: {olingan}"
		assert kunlar[1] not in olingan, "tanlanmagan kun ham tushdi"

		# 3) Tartib: oxirgi gaplashilgan tepada
		hammasi = sn.get_telefon(**xom)
		tartib = [str(o["oxirgi"]) for o in hammasi["oquvchilar"]]
		assert tartib == sorted(tartib, reverse=True), "o'quvchilar sana bo'yicha tartiblanmadi"
		print(f"TARTIB: {len(tartib)} o'quvchi, eng tepada {tartib[0][:16]}")

		# 4) Panel yozuvlari (get_data) ham shu filtrni tushunadi
		a = sn.get_data(**xom, sanalar=[kunlar[1]])
		a_kunlar = {str(x["creation"])[:10] for x in a["aloqalar"]}
		assert not a_kunlar or a_kunlar == {kunlar[1]}, f"get_data filtri ishlamadi: {a_kunlar}"
		print(f"GET_DATA 1 kun: yozuv={a['jami']['qongiroq']} kunlar={sorted(a_kunlar)}")

		# 5) Axlat kiritish sahifani buzmasin
		assert sn._sanalar('["salom", "", "2026-10-06", "2026-10-06"]') == ["2026-10-06"]
		assert sn._sanalar(None) == [] and sn._sanalar("[]") == []
		print("\nOK — sana filtri bitta/bir nechta kunda ham to'g'ri ishlayapti")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		print(f"({len(yaratilgan)} sinov qo'ng'irog'i o'chirildi)")


def test_suhbat_matni(user="investor@gmail.com"):
	"""Suhbat matni talab bo'yicha ochiladimi (ro'yxatda yuborilmaydi)."""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.target_zenit.page.sotuv_nazorati import sotuv_nazorati as sn

	frappe.set_user("Administrator")
	matn = "Menejer: Assalomu alaykum. Ota-ona: Shu hafta to'laymiz. " * 20
	d = frappe.get_doc({
		"doctype": "Telefon Qongirogi", "manba": "Android",
		"asterisk_uniqueid": f"dev-matn-{frappe.generate_hash(length=6)}",
		"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), minutes=-10),
		"tashqi_raqam": "+998901112233", "tugash_sababi": "Javob berildi",
		"suhbat_vaqti": 140, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
		"holat": "Tahlil qilindi", "transkript": matn, "transkript_sozlar": len(matn.split()),
		"ai_xulosa": "MAVZU: Qarz\nTAKLIF VA SHIKOYAT: Taklif yo'q\nMIJOZ HOLATI: Ijobiy",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	try:
		ro = sn.get_telefon(from_date=frappe.utils.today())
		q = next(x for x in ro["qongiroqlar"] if x["name"] == d.name)
		print(f"ro'yxatda: transkript_bor={q['transkript_bor']} sozlar={q['transkript_sozlar']} "
		      f"matn maydoni={'bor' if 'transkript' in q else 'YO‘Q (to‘g‘ri)'}")
		assert "transkript" not in q, "ro'yxat og'ir: matn yuborilyapti"
		assert q["transkript_bor"] == 1

		frappe.set_user(user)
		s = sn.get_suhbat(d.name)
		print(f"{user}: get_suhbat -> {len(s['transkript'])} belgi, "
		      f"tahlil {len(s['ai_xulosa'])} belgi, taklif='{s['taklif']}'")
		assert s["transkript"] == matn, "to'liq matn kelmadi"
		print("OK — matn faqat talab bo'yicha ochilyapti")
	finally:
		frappe.set_user("Administrator")
		frappe.delete_doc("Telefon Qongirogi", d.name, force=True, ignore_permissions=True)
		frappe.db.commit()
		print("(sinov qo'ng'irog'i o'chirildi)")


def test_panel_havolasi(case="QI-2026-145130"):
	"""Sotuv nazoratidagi havola qarzdorlik panelini shu o'quvchida ochadimi.

	`ish_topish` uchta holatni qoplashi kerak: ish nomi bo'yicha, o'quvchi
	bo'yicha, va ketgan o'quvchi (panel "Ketganlar" ro'yxatiga o'tadi).
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_panel_havolasi
	"""
	from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as panel

	frappe.set_user("Administrator")
	student = frappe.db.get_value("Qarz Ishi", case, "student")

	r1 = panel.ish_topish(case=case)
	r2 = panel.ish_topish(student=student)
	r3 = panel.ish_topish(student="EDU-STU-YOQ-0000")
	print(f"ish bo'yicha : {r1}")
	print(f"o'quvchi b-cha: {r2}")
	print(f"topilmagan   : {r3}")
	assert r1["case"] == case and r2["case"] == case, "ish topilmadi"
	assert r1["ketgan"] == 0, "faol o'quvchi 'ketgan' deb belgilandi"
	assert r3["case"] is None, "yo'q o'quvchiga ish qaytdi"

	# Ketgan o'quvchi: panel "Ketganlar" ro'yxatiga o'tishi uchun bayroq kerak
	eski = frappe.db.get_value("Student", student, ["enabled", "date_of_leaving"], as_dict=True)
	try:
		frappe.db.set_value("Student", student, {"enabled": 0,
		                                         "date_of_leaving": frappe.utils.today()})
		frappe.db.commit()
		r4 = panel.ish_topish(case=case)
		print(f"ketgan holat : {r4}")
		assert r4["ketgan"] == 1, "ketgan o'quvchi aniqlanmadi"
	finally:
		frappe.db.set_value("Student", student, {"enabled": eski.enabled,
		                                         "date_of_leaving": eski.date_of_leaving})
		frappe.db.commit()
	print("OK — havola panelni to'g'ri o'quvchida ochadi")


def masul_diagnostika(limit=25):
	"""Nega qarz ishlari bitta menejerda qolib ketgan — sababini ko'rsatadi.

	Serverda ishga tushirish:
	  bench --site targetschool.erpcontrol.uz execute \
	      target_zenit.qarzdorlik.dev.masul_diagnostika
	"""
	from target_zenit.qarzdorlik.engine import (
		YOPIQ_STATUSLAR,
		masul_bola_oladimi,
		oxirgi_ishlagan,
	)

	cfg = frappe.get_cached_doc("Qarzdorlik Sozlamalari")
	print("=== 0) Yangi ish OCHILGANDA kimga biriktiriladi (sinf qoidalari) ===")
	qoidalar = [(r.sinf_pattern, r.masul) for r in (cfg.biriktirish or [])]
	for p_, m_ in qoidalar:
		print(f"   {p_!s:<24} -> {m_}")
	print(f"   DEFAULT (qoida mos kelmasa): {cfg.default_masul or 'Administrator'}")
	kimlar = {m for _, m in qoidalar} | ({cfg.default_masul} if cfg.default_masul else set())
	if len(kimlar) <= 1:
		print("   ⚠ Hamma yangi ish BITTA odamga tushadi — qoidalarni bo'lib bering "
		      "(Qarzdorlik Sozlamalari -> Sinf bo'yicha avto-biriktirish).")

	print("\n=== 1) Qarz ishlari kimda (ochiq ishlar) ===")
	for r in frappe.db.sql(
		"""SELECT masul, COUNT(*) n FROM `tabQarz Ishi`
		   WHERE ishlov_status NOT IN %(y)s GROUP BY masul ORDER BY n DESC""",
		{"y": tuple(YOPIQ_STATUSLAR)}, as_dict=True):
		mumkin, sabab = masul_bola_oladimi(r.masul)
		print(f"   {r.masul!s:<34} {r.n:>5} ta   (mas'ul bo'la oladi: {mumkin} — {sabab})")

	print("\n=== 2) Kim panelga yozyapti (Aloqa Yozuvi) ===")
	for r in frappe.db.sql(
		"""SELECT masul, COUNT(*) n, MAX(creation) oxirgi FROM `tabAloqa Yozuvi`
		   GROUP BY masul ORDER BY n DESC""", as_dict=True):
		mumkin, sabab = masul_bola_oladimi(r.masul)
		print(f"   {r.masul!s:<34} {r.n:>5} ta   oxirgi {str(r.oxirgi)[:16]}   "
		      f"({'biriktiriladi' if mumkin else 'BIRIKTIRILMAYDI: ' + sabab})")

	print("\n=== 3) Kim komment yozyapti (Qarz Ishi kommentlari) ===")
	for r in frappe.db.sql(
		"""SELECT owner, COUNT(*) n, MAX(creation) oxirgi FROM `tabComment`
		   WHERE reference_doctype='Qarz Ishi' AND comment_type='Comment'
		   GROUP BY owner ORDER BY n DESC""", as_dict=True):
		mumkin, sabab = masul_bola_oladimi(r.owner)
		print(f"   {r.owner!s:<34} {r.n:>5} ta   oxirgi {str(r.oxirgi)[:16]}   "
		      f"({'biriktiriladi' if mumkin else 'BIRIKTIRILMAYDI: ' + sabab})")

	print("\n=== 4) Faollik bor, lekin mas'ul mos emas (eng muhimi) ===")
	nomuvofiq = 0
	for name, masul in frappe.db.sql(
		"""SELECT name, masul FROM `tabQarz Ishi`
		   WHERE ishlov_status NOT IN %(y)s ORDER BY modified DESC""",
		{"y": tuple(YOPIQ_STATUSLAR)}):
		user, vaqt, manba = oxirgi_ishlagan(name)
		if not user or user == masul:
			continue
		mumkin, sabab = masul_bola_oladimi(user)
		nomuvofiq += 1
		if nomuvofiq <= limit:
			print(f"   {name}: hozir '{masul}' · oxirgi ishlagan '{user}' "
			      f"({manba}, {str(vaqt)[:16]}) -> {'o‘tadi' if mumkin else 'TO‘SIQ: ' + sabab}")
	print(f"   jami nomuvofiq: {nomuvofiq} ta")

	print("\n=== 5) Avtomatik biriktirish tarixi (tizim izohlari) ===")
	n = frappe.db.count("Comment", {"reference_doctype": "Qarz Ishi",
	                                "comment_type": "Info",
	                                "content": ["like", "%Mas'ul avtomatik%"]})
	print(f"   {n} ta ish avtomatik qayta biriktirilgan")
	print("\nXULOSA: 2/3-bo'limda 'BIRIKTIRILMAYDI' bo'lsa — rol muammosi; "
	      "hammasi bitta foydalanuvchida bo'lsa — jamoa bitta login bilan ishlayapti; "
	      "4-bo'limda nomuvofiq ko'p bo'lsa — `engine.masullarni_yangila()` ni "
	      "ishga tushiring (kechasi o'zi ham ishlaydi).")


def test_komment_biriktirish(case="QI-2026-145130"):
	"""Qarz Ishi'ga komment yozilganda mas'ul darhol o'sha xodimga o'tadimi.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_komment_biriktirish
	"""
	from target_zenit.qarzdorlik import engine

	frappe.set_user("Administrator")
	eski = frappe.db.get_value("Qarz Ishi", case, "masul")
	yangi_user = next(
		u for u in frappe.get_all("Qarz Ishi", pluck="masul", limit_page_length=0)
		if u and u != eski and engine._masul_bola_oladi(u))
	print(f"{case}: mas'ul '{eski}' · komment yozadi '{yangi_user}'")
	try:
		frappe.set_user(yangi_user)
		frappe.get_doc("Qarz Ishi", case).add_comment("Comment", "Sinov: ota-ona bilan gaplashdim")
		frappe.db.commit()
		frappe.set_user("Administrator")
		keyin = frappe.db.get_value("Qarz Ishi", case, "masul")
		print(f"  kommentdan keyin: '{keyin}' (kutilgan '{yangi_user}')")
		assert keyin == yangi_user, "komment hook ishlamadi"
		izoh = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Qarz Ishi", "reference_name": case,
			         "comment_type": "Info", "content": ["like", "%Mas'ul avtomatik%"]},
			fields=["content"], order_by="creation desc", limit=1)
		print(f"  iz: {izoh[0].content if izoh else '—'}")
		assert izoh, "o'zgarish izohi yozilmadi"
		print("OK — komment yozilishi bilan ish o'sha xodimga o'tdi")
	finally:
		frappe.set_user("Administrator")
		for c in frappe.get_all("Comment", filters={
			"reference_doctype": "Qarz Ishi", "reference_name": case,
			"content": ["like", "%Sinov:%"]}, pluck="name"):
			frappe.delete_doc("Comment", c, force=True, ignore_permissions=True)
		frappe.db.set_value("Qarz Ishi", case, "masul", eski, update_modified=False)
		frappe.db.commit()
		print(f"(tiklandi: {eski})")


def test_qayta_tahlil_ruxsati(user="sotuv_menejer@gmail.com"):
	"""Qayta tahlil/transkripsiya faqat adminda, birinchi marta — hammada.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_qayta_tahlil_ruxsati
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.telefoniya import analiz

	frappe.set_user("Administrator")
	d = frappe.get_doc({
		"doctype": "Telefon Qongirogi", "manba": "Android",
		"asterisk_uniqueid": f"dev-ruxsat-{frappe.generate_hash(length=6)}",
		"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), minutes=-5),
		"tashqi_raqam": "+998901112233", "tugash_sababi": "Javob berildi",
		"suhbat_vaqti": 60, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
		"transkript": "sinov matni", "transkript_sozlar": 2,
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	natija = {}
	try:
		for u in ("Administrator", user):
			frappe.set_user(u)
			natija[u] = {"ruxsatmi": analiz.qayta_ruxsatmi()}
			# tahlili YO'Q — hamma yurgiza olishi kerak (to'siq faqat qaytada)
			try:
				analiz.qayta_ruxsat(False, "tahlil")
				natija[u]["birinchi"] = "mumkin"
			except Exception as e:
				natija[u]["birinchi"] = f"TO'SIQ: {type(e).__name__}"
			# tahlili BOR — faqat admin
			try:
				analiz.qayta_ruxsat(True, "tahlil")
				natija[u]["qayta"] = "mumkin"
			except Exception as e:
				natija[u]["qayta"] = f"to'siq ({type(e).__name__})"
		for u, r in natija.items():
			print(f"  {u:<28} ruxsatmi={r['ruxsatmi']!s:5} birinchi={r['birinchi']:<10} qayta={r['qayta']}")

		assert natija["Administrator"]["qayta"] == "mumkin", "admin qayta yurgiza olmadi"
		assert natija[user]["qayta"].startswith("to'siq"), "oddiy foydalanuvchi qayta yurgiza oldi!"
		assert natija[user]["birinchi"] == "mumkin", "birinchi tahlil ham yopilib qolgan"
		print("OK — qayta tahlil faqat adminda, avtomatik/birinchi tahlil hammada")
	finally:
		frappe.set_user("Administrator")
		frappe.delete_doc("Telefon Qongirogi", d.name, force=True, ignore_permissions=True)
		frappe.db.commit()


def test_qongiroq_biriktirish():
	"""Eski qo'ng'iroqlarni to'g'ri xodimga biriktirish (ikki telefon bitta
	akkauntda bo'lgan holat): ko'rish -> dry run -> yozish -> tekshirish.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_qongiroq_biriktirish
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.telefoniya import backfill

	frappe.set_user("Administrator")
	emp = frappe.db.get_value("Employee", {"status": "Active"}, ["name", "user_id"], as_dict=True)
	# "Ikkala telefonda bitta akkaunt" holatini taqlid qilamiz — mavjud
	# foydalanuvchi olinadi (yangi User yaratish bu lokal nusxada ishlamaydi)
	umumiy = frappe.db.get_value("User", {"enabled": 1, "name": ["like", "%menejer%"]}, "name")
	assert umumiy, "sinov uchun foydalanuvchi topilmadi"
	yaratilgan = []
	try:
		for i, sim in enumerate(["+998901111111", "+998902222222"] * 2):
			d = frappe.get_doc({
				"doctype": "Telefon Qongirogi", "manba": "Android",
				"asterisk_uniqueid": f"dev-bf-{i}-{frappe.generate_hash(length=6)}",
				"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), days=-i),
				"tashqi_raqam": f"+99893000000{i}", "tugash_sababi": "Javob berildi",
				"suhbat_vaqti": 60, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
				"foydalanuvchi": umumiy, "qurilma": "Redmi 13", "sim_raqam": sim,
			}).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
		frappe.db.commit()
		print("--- koring() ---")
		backfill.koring(foydalanuvchi=umumiy)

		print("\n--- dry run (faqat 1-SIM) ---")
		r1 = backfill.biriktir(xodim=emp.name, foydalanuvchi=umumiy,
		                       sim="+998901111111", dry_run=1)
		assert r1["jami"] == 2 and r1["ozgardi"] == 0, "dry run yozib yubordi!"

		print("\n--- yozish ---")
		r2 = backfill.biriktir(xodim=emp.name, foydalanuvchi=umumiy,
		                       sim="+998901111111", dry_run=0)
		assert r2["ozgardi"] == 2

		biriktirilgan = frappe.get_all(
			"Telefon Qongirogi", filters={"name": ["in", yaratilgan]},
			fields=["name", "sim_raqam", "xodim", "foydalanuvchi"])
		for b in biriktirilgan:
			print(f"   {b.sim_raqam}  xodim={b.xodim or '—'}  user={b.foydalanuvchi}")
		bir = [b for b in biriktirilgan if b.sim_raqam == "+998901111111"]
		ikki = [b for b in biriktirilgan if b.sim_raqam == "+998902222222"]
		assert all(b.xodim == emp.name for b in bir), "1-SIM biriktirilmadi"
		assert all(not b.xodim for b in ikki), "2-SIM ham o'zgarib ketdi!"
		if emp.user_id:
			assert all(b.foydalanuvchi == emp.user_id for b in bir), "foydalanuvchi yangilanmadi"
		print("\nOK — faqat tanlangan telefon yozuvlari biriktirildi")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		print(f"({len(yaratilgan)} sinov yozuvi o'chirildi)")


def test_akkaunt_kochirish():
	"""Umumiy akkauntdagi yozuvlarni xodimga ko'chirish va eski userni
	o'chirishga tayyorlash oqimi (sinov ma'lumotida).
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_akkaunt_kochirish
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.telefoniya import backfill

	frappe.set_user("Administrator")
	eski = "sotuvmanager@gmail.com"
	assert frappe.db.exists("User", eski), f"{eski} topilmadi"
	emp = frappe.db.get_value(
		"Employee", "HR-EMP-00068", ["name", "employee_name", "user_id"], as_dict=True)
	print(f"eski akkaunt: {eski} | maqsad: {emp.name} ({emp.user_id})")

	yaratilgan = []
	try:
		for i in range(3):
			d = frappe.get_doc({
				"doctype": "Telefon Qongirogi", "manba": "Android",
				"asterisk_uniqueid": f"dev-kochir-{i}-{frappe.generate_hash(length=6)}",
				"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), days=-i),
				"tashqi_raqam": f"+99893111000{i}", "tugash_sababi": "Javob berildi",
				"suhbat_vaqti": 60, "yozuv_bor": 1, "fayl_yoli": "dev/sinov.mp3",
				"foydalanuvchi": eski, "qurilma": "Redmi 13",
			}).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
		frappe.db.commit()

		print("\n--- izlar (ko'chirishdan oldin) ---")
		izlar = backfill.akkaunt_izlari(eski)
		assert izlar.get("Telefon Qongirogi.foydalanuvchi", 0) >= 3

		print("\n--- dry run ---")
		r1 = backfill.akkauntni_kochir(xodim=emp.name, eski=eski, dry_run=1)
		assert r1["ozgardi"] == 0, "dry run yozib yubordi!"

		print("\n--- ko'chirish ---")
		r2 = backfill.akkauntni_kochir(xodim=emp.name, eski=eski, dry_run=0)
		print(f"   natija: {r2['ozgardi']} ta ko'chdi, qoldi: {r2['qoldi']}")
		qolgan = frappe.db.count("Telefon Qongirogi", {"foydalanuvchi": eski})
		yangi = frappe.get_all(
			"Telefon Qongirogi", filters={"name": ["in", yaratilgan]},
			fields=["name", "foydalanuvchi", "xodim"])
		for y in yangi:
			print(f"   {y.name}: user={y.foydalanuvchi} xodim={y.xodim}")
		assert qolgan == 0, "eski akkauntda yozuv qoldi"
		assert all(y.xodim == emp.name and y.foydalanuvchi == emp.user_id for y in yangi)

		print("\n--- o'chirishga tayyorligi (dry run) ---")
		r3 = backfill.akkauntni_ochir(user=eski, dry_run=1)
		print(f"   holat: {r3['holat']}")
		print("\nOK — ko'chirish ishladi, akkaunt o'chirishga tayyorlanadi")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		print(f"({len(yaratilgan)} sinov yozuvi o'chirildi)")


def test_biriktir_hammasi():
	"""Serverda ALLAQACHON turgan `biriktir()` bilan umumiy akkauntning
	hamma yozuvini bitta xodimga ko'chirish (xodimsiz=0) — deploy kutmasdan.
	bench --site target.local execute target_zenit.qarzdorlik.dev.test_biriktir_hammasi
	"""
	from frappe.utils import add_to_date, now_datetime

	from target_zenit.telefoniya import backfill

	frappe.set_user("Administrator")
	eski = "sotuvmanager@gmail.com"
	emp = frappe.db.get_value("Employee", "HR-EMP-00068",
	                          ["name", "user_id"], as_dict=True)
	boshqa = frappe.db.get_value("Employee", {"name": ["!=", emp.name], "status": "Active"}, "name")
	yaratilgan = []
	try:
		# Biri xodimsiz, biri BOSHQA xodimga biriktirilgan — ikkalasi ham ko'chishi kerak
		for i, xod in enumerate([None, boshqa]):
			d = frappe.get_doc({
				"doctype": "Telefon Qongirogi", "manba": "Android",
				"asterisk_uniqueid": f"dev-hammasi-{i}-{frappe.generate_hash(length=6)}",
				"yonalish": "Chiquvchi", "boshlandi": add_to_date(now_datetime(), days=-i),
				"tashqi_raqam": f"+99893222000{i}", "tugash_sababi": "Javob berildi",
				"suhbat_vaqti": 60, "foydalanuvchi": eski, "xodim": xod,
			}).insert(ignore_permissions=True)
			yaratilgan.append(d.name)
		frappe.db.commit()

		r = backfill.biriktir(xodim=emp.name, foydalanuvchi=eski, xodimsiz=0, dry_run=0)
		print(f"   ko'chirildi: {r['ozgardi']} ta")
		natija = frappe.get_all("Telefon Qongirogi", filters={"name": ["in", yaratilgan]},
		                        fields=["name", "xodim", "foydalanuvchi"])
		for n in natija:
			print(f"   {n.name}: xodim={n.xodim} user={n.foydalanuvchi}")
		assert all(n.xodim == emp.name and n.foydalanuvchi == emp.user_id for n in natija), \
			"xodimsiz=0 bilan hammasi ko'chmadi"
		print("OK — `biriktir(xodimsiz=0)` umumiy akkauntning hammasini ko'chiradi")
	finally:
		for n in yaratilgan:
			frappe.delete_doc("Telefon Qongirogi", n, force=True, ignore_permissions=True)
		frappe.db.commit()
