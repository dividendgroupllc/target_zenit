# Copyright (c) 2026, Target Zenit
# Qarzdorlik engine — qarz hisoblash va ish (case) boshqaruvi.
#
# Qarz manbai — Tolov Rejasi (jadval), GL EMAS: bazada accrual hujjatlari yo'q,
# GL'dagi Receivable faqat avanslarni ko'rsatadi. To'lovlar (Payment Entry, Receive)
# rejaning oylariga FIFO taqsimlanadi; taqsimot alohida saqlanmaydi — har safar
# deterministik qayta hisoblanadi.
#
# Kirish nuqtalari:
#   nightly()      — scheduler (daily)
#   on_payment()   — Payment Entry on_submit/on_cancel hook
#   recompute_plan() — bitta rejani qayta hisoblash (TR on_update ham chaqiradi)
from __future__ import annotations

from fnmatch import fnmatch

import frappe
from frappe.utils import add_days, date_diff, flt, getdate, nowdate

YOPIQ_STATUSLAR = ("Yopildi - To'landi", "Yopildi - Boshqa")


def _settings():
	s = frappe.get_cached_doc("Qarzdorlik Sozlamalari")
	return frappe._dict(
		grace_days=s.grace_days if s.grace_days is not None else 3,
		tolerance=flt(s.tolerance) or 1000,
		min_threshold=flt(s.min_threshold) or 10000,
		buzilgan_vada_limit=s.buzilgan_vada_limit or 2,
		sla_soat=s.sla_soat or 48,
		default_masul=s.default_masul,
		biriktirish=[(r.sinf_pattern, r.masul) for r in (s.biriktirish or [])],
	)


def _payments_since(customer: str, from_date) -> float:
	"""Mijozning from_date'dan beri tushgan to'lovlari, UZS'da.

	DIQQAT: kompaniya bazaviy valyutasi USD, shartnomalar esa UZS — shuning uchun
	base_paid_amount (USD) ISHLATILMAYDI:
	  - UZS'dan to'lov: paid_amount (UZS);
	  - USD to'lov UZS kassaga: received_amount (UZS);
	  - USD -> USD: o'sha kungi USD->UZS kurs (Currency Exchange) bilan."""
	if not customer:
		return 0.0
	rows = frappe.db.sql(
		"""SELECT paid_from_account_currency f, paid_to_account_currency t,
		          paid_amount, received_amount, posting_date
		   FROM `tabPayment Entry`
		   WHERE docstatus=1 AND payment_type='Receive' AND party_type='Customer'
		     AND party=%s AND posting_date >= %s""",
		(customer, from_date),
		as_dict=True,
	)
	total = 0.0
	for r in rows:
		if r.f == "UZS":
			total += flt(r.paid_amount)
		elif r.t == "UZS":
			total += flt(r.received_amount)
		else:
			total += flt(r.paid_amount) * _usd_uzs_rate(r.posting_date)
	return total


def get_payments(customer: str, from_date) -> list[dict]:
	"""To'lovlar ro'yxati UZS ekvivalenti bilan (panel kartasi uchun)."""
	if not customer:
		return []
	rows = frappe.db.sql(
		"""SELECT name, posting_date, paid_from_account_currency f,
		          paid_to_account_currency t, paid_amount, received_amount,
		          remarks, mode_of_payment
		   FROM `tabPayment Entry`
		   WHERE docstatus=1 AND payment_type='Receive' AND party_type='Customer'
		     AND party=%s AND posting_date >= %s
		   ORDER BY posting_date DESC""",
		(customer, from_date),
		as_dict=True,
	)
	out = []
	for r in rows:
		if r.f == "UZS":
			uzs = flt(r.paid_amount)
		elif r.t == "UZS":
			uzs = flt(r.received_amount)
		else:
			uzs = flt(r.paid_amount) * _usd_uzs_rate(r.posting_date)
		out.append(
			{
				"name": r.name,
				"posting_date": r.posting_date,
				"amount_uzs": uzs,
				"currency": r.f,
				"mode_of_payment": r.mode_of_payment,
				"remarks": (r.remarks or "")[:140],
			}
		)
	return out


def _usd_uzs_rate(date) -> float:
	rate = frappe.db.get_value(
		"Currency Exchange",
		{"from_currency": "USD", "to_currency": "UZS", "date": ["<=", date]},
		"exchange_rate",
		order_by="date desc",
	)
	return flt(rate) or 12000.0


def _plan_payment_window(tr) -> str:
	"""Rejaga hisoblanadigan to'lovlar boshlanish sanasi: o'quv yili boshidan
	2 oy oldin (avgust/iyul avanslari shu yilga tegishli). Oldingi yil to'lovlari
	aralashmasligi uchun."""
	try:
		start_year = int(str(tr.academic_year).split("-")[0])
	except Exception:
		start_year = getdate(nowdate()).year
	return f"{start_year}-07-01"


# ---------------------------------------------------------------- recompute
def recompute_plan(tr_name: str, sync_case: bool = True):
	"""Bitta Tolov Rejasi: FIFO taqsimot -> oy qatorlari + jami maydonlar.
	Hamma yozuv db.set_value bilan (on_update rekursiyasi yo'q)."""
	tr = frappe.get_doc("Tolov Rejasi", tr_name)
	if tr.holat == "Bekor":
		return None

	frappe.flags.qarz_engine = True
	try:
		total_paid = _payments_since(tr.customer, _plan_payment_window(tr))
		today = getdate(nowdate())

		rows = sorted(
			[r for r in tr.oylar if r.holat != "Bekor"], key=lambda r: getdate(r.due_date)
		)
		pool = total_paid
		qarz = 0.0
		eng_eski = None
		for r in rows:
			amount = flt(r.amount)
			alloc = min(pool, amount)
			pool -= alloc
			outstanding = amount - alloc

			if outstanding <= 0.005:
				holat = "To'landi"
			elif alloc > 0:
				holat = "Qisman"
			elif getdate(r.due_date) <= today:
				holat = "Muddati keldi"
			else:
				holat = "Kutilmoqda"

			if getdate(r.due_date) <= today and outstanding > 0.005:
				qarz += outstanding
				if eng_eski is None:
					eng_eski = getdate(r.due_date)

			if (
				flt(r.paid_amount) != alloc
				or flt(r.outstanding) != outstanding
				or r.holat != holat
			):
				frappe.db.set_value(
					"Tolov Rejasi Oyi",
					r.name,
					{"paid_amount": alloc, "outstanding": outstanding, "holat": holat},
					update_modified=False,
				)

		jami = sum(flt(r.amount) for r in rows)
		frappe.db.set_value(
			"Tolov Rejasi",
			tr.name,
			{
				"jami_hisoblangan": jami,
				"jami_tolangan": min(total_paid, jami),
				"qarz_bugun": qarz,
				"eng_eski_muddat": eng_eski,
				"avans_summa": max(total_paid - jami, 0),
			},
			update_modified=False,
		)

		if sync_case:
			_sync_case(tr, qarz, eng_eski)
		return qarz
	finally:
		frappe.flags.qarz_engine = False


# ---------------------------------------------------------------- case sync
def _bucket(eng_eski, left_school: bool) -> str:
	if left_school:
		return "Ketgan-qarzli"
	if not eng_eski:
		return ""
	days = date_diff(nowdate(), eng_eski)
	if days <= 30:
		return "1-30"
	if days <= 60:
		return "31-60"
	if days <= 90:
		return "61-90"
	return "90+"


def _pick_masul(sinf: str, cfg) -> str:
	for pattern, user in cfg.biriktirish:
		for p in str(pattern).split(","):
			if p.strip() and fnmatch(sinf or "", p.strip()):
				if frappe.db.get_value("User", user, "enabled"):
					return user
	if cfg.default_masul and frappe.db.get_value("User", cfg.default_masul, "enabled"):
		return cfg.default_masul
	return "Administrator"


def _payer_info(student_id: str, student=None):
	"""To'lovchi ism/tel zanjiri: Student.payer -> ota-ona (Guardian) -> o'quvchining o'zi."""
	if student is None:
		student = frappe.db.get_value(
			"Student",
			student_id,
			["custom_payer_name", "custom_payer_phone", "student_mobile_number"],
			as_dict=True,
		) or frappe._dict()
	if student.custom_payer_phone:
		return student.custom_payer_name, student.custom_payer_phone

	g = frappe.db.sql(
		"""SELECT COALESCE(g.guardian_name, sg.guardian_name) nm, g.mobile_number tel
		   FROM `tabStudent Guardian` sg
		   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parent = %s AND sg.parenttype = 'Student'
		     AND g.mobile_number IS NOT NULL AND g.mobile_number != ''
		   ORDER BY sg.idx LIMIT 1""",
		(student_id,),
		as_dict=True,
	)
	if g:
		return (student.custom_payer_name or g[0].nm), g[0].tel
	return student.custom_payer_name, student.student_mobile_number


def _sync_case(tr, qarz: float, eng_eski):
	cfg = _settings()
	open_case = frappe.db.get_value(
		"Qarz Ishi",
		{"student": tr.student, "ishlov_status": ["not in", list(YOPIQ_STATUSLAR)]},
		["name", "ishlov_status", "buzilgan_vadalar"],
		as_dict=True,
	)
	frappe.flags.qarz_engine = True

	# 1) Qarz yopildi -> ishni yopish
	if qarz <= cfg.tolerance:
		if open_case:
			qi = frappe.get_doc("Qarz Ishi", open_case.name)
			qi.ishlov_status = "Yopildi - To'landi"
			qi.yopilish_sababi = "To'landi"
			qi.qarz_summa = qarz
			qi.save(ignore_permissions=True)
			# ochiq va'dalar bajarildi hisoblanadi
			for p in frappe.get_all(
				"Tolov Vadasi", filters={"qarz_ishi": qi.name, "holat": "Ochiq"}, pluck="name"
			):
				frappe.db.set_value(
					"Tolov Vadasi",
					p,
					{"holat": "Bajarildi", "tekshirilgan_sana": nowdate()},
				)
		return

	left_school = bool(frappe.db.get_value("Student", tr.student, "date_of_leaving"))
	bucket = _bucket(eng_eski, left_school)

	# 2) Ochiq ish bor -> qarz ma'lumotlarini yangilash
	if open_case:
		frappe.db.set_value(
			"Qarz Ishi",
			open_case.name,
			{"qarz_summa": qarz, "eng_eski_muddat": eng_eski, "aging_bucket": bucket},
			update_modified=False,
		)
		return

	# 3) Yangi ish ochish: threshold + grace
	if qarz < cfg.min_threshold:
		return
	if eng_eski and date_diff(nowdate(), eng_eski) <= cfg.grace_days:
		return

	student = frappe.db.get_value(
		"Student",
		tr.student,
		["custom_payer_name", "custom_payer_phone", "student_mobile_number", "custom_sinf_guruh"],
		as_dict=True,
	) or frappe._dict()
	payer_name, payer_phone = _payer_info(tr.student, student)

	qi = frappe.get_doc(
		{
			"doctype": "Qarz Ishi",
			"student": tr.student,
			"tolov_rejasi": tr.name,
			"payer_name": payer_name,
			"payer_phone": payer_phone,
			"qarz_summa": qarz,
			"eng_eski_muddat": eng_eski,
			"aging_bucket": bucket,
			"masul": _pick_masul(student.custom_sinf_guruh, cfg),
			"ishlov_status": "Yangi",
			"keyingi_aloqa": nowdate(),
		}
	)
	qi.insert(ignore_permissions=True)


# ---------------------------------------------------------------- PTP check
def check_ptps():
	"""Muddati (+1 kun bufer) o'tgan ochiq va'dalar: to'lov tushganmi?"""
	cfg = _settings()
	deadline = add_days(nowdate(), -1)
	ptps = frappe.get_all(
		"Tolov Vadasi",
		filters={"holat": "Ochiq", "vada_sana": ["<=", deadline]},
		fields=["name", "qarz_ishi", "vada_summa", "creation", "masul", "student_name"],
	)
	for p in ptps:
		customer = frappe.db.get_value("Qarz Ishi", p.qarz_ishi, "customer")
		paid = _payments_since(customer, getdate(p.creation))
		if paid >= flt(p.vada_summa) - cfg.tolerance:
			holat = "Bajarildi"
		elif paid > 0:
			holat = "Qisman"
		else:
			holat = "Buzildi"
		frappe.db.set_value(
			"Tolov Vadasi",
			p.name,
			{"holat": holat, "amal_summa": paid, "tekshirilgan_sana": nowdate()},
		)
		if holat == "Bajarildi":
			continue

		# Qisman/Buzildi -> ish bugunga qaytadi
		qi = frappe.get_doc("Qarz Ishi", p.qarz_ishi)
		if qi.ishlov_status in YOPIQ_STATUSLAR:
			continue
		frappe.flags.qarz_engine = True
		if holat == "Buzildi":
			qi.buzilgan_vadalar = (qi.buzilgan_vadalar or 0) + 1
		qi.ishlov_status = (
			"Eskalatsiya"
			if (qi.buzilgan_vadalar or 0) >= cfg.buzilgan_vada_limit
			else "Va'da buzildi"
		)
		qi.keyingi_aloqa = nowdate()
		qi.save(ignore_permissions=True)
		frappe.flags.qarz_engine = False
		_todo(
			qi.masul,
			"Qarz Ishi",
			qi.name,
			f"Va'da bajarilmadi: {p.student_name or qi.student_name} — "
			f"{frappe.format_value(p.vada_summa, {'fieldtype': 'Currency'})} va'da, "
			f"tushgani {frappe.format_value(paid, {'fieldtype': 'Currency'})}",
		)


# ---------------------------------------------------------------- SLA
def check_sla():
	"""Yangi ish sla_soat ichida birinchi aloqasiz qolsa — mas'ulga ToDo."""
	cfg = _settings()
	rows = frappe.db.sql(
		"""SELECT name, masul, student_name FROM `tabQarz Ishi`
		   WHERE ishlov_status='Yangi' AND urinishlar_soni=0
		     AND TIMESTAMPDIFF(HOUR, creation, NOW()) > %s""",
		(cfg.sla_soat,),
		as_dict=True,
	)
	for r in rows:
		_todo(
			r.masul,
			"Qarz Ishi",
			r.name,
			f"SLA: {r.student_name} bo'yicha {cfg.sla_soat} soatdan beri birinchi aloqa yo'q",
		)


def _todo(user, ref_dt, ref_dn, description):
	"""Takrorlanmaydigan ochiq ToDo."""
	if frappe.db.exists(
		"ToDo",
		{
			"reference_type": ref_dt,
			"reference_name": ref_dn,
			"status": "Open",
			"allocated_to": user,
		},
	):
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": user,
			"reference_type": ref_dt,
			"reference_name": ref_dn,
			"description": description,
			"priority": "High",
			"date": nowdate(),
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------- jobs/hooks
def nightly():
	"""Daily scheduler: hamma faol reja -> recompute + case sync; PTP; SLA.
	Har qadam alohida himoyalangan — bitta xato qolganini to'xtatmaydi."""
	for tr_name in frappe.get_all("Tolov Rejasi", filters={"holat": "Faol"}, pluck="name"):
		try:
			recompute_plan(tr_name, sync_case=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"qarzdorlik nightly: {tr_name}")
	try:
		check_ptps()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: check_ptps")
	try:
		check_sla()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: check_sla")
	frappe.db.commit()


def on_payment(doc, method=None):
	"""PE submit/cancel — shu mijoz rejasini darhol qayta hisoblash
	(ota-ona to'lagan zahoti menejer ro'yxatidan tushsin)."""
	try:
		if doc.party_type != "Customer" or doc.payment_type != "Receive":
			return
		for tr_name in frappe.get_all(
			"Tolov Rejasi",
			filters={"customer": doc.party, "holat": "Faol"},
			pluck="name",
		):
			recompute_plan(tr_name, sync_case=True)
	except Exception:
		# To'lov o'tkazishni hech qachon bloklamaymiz
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_payment: {doc.name}")


def on_student_change(doc, method=None):
	"""O'quvchi ketsa — kelgusi oylar Bekor, qolgan qarz 'Ketgan-qarzli' bucket."""
	try:
		if not doc.date_of_leaving:
			return
		for tr_name in frappe.get_all(
			"Tolov Rejasi", filters={"student": doc.name, "holat": "Faol"}, pluck="name"
		):
			leaving = getdate(doc.date_of_leaving)
			tr = frappe.get_doc("Tolov Rejasi", tr_name)
			for r in tr.oylar:
				if getdate(r.due_date) > leaving and r.holat != "Bekor":
					frappe.db.set_value(
						"Tolov Rejasi Oyi", r.name, "holat", "Bekor", update_modified=False
					)
			recompute_plan(tr_name, sync_case=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_student_change: {doc.name}")
