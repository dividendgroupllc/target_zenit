# Copyright (c) 2026, Target Zenit
# Qarzdorlik paneli — savdo menejerlari ish stoli:
# qarzdorlar navbati, o'quvchi kartasi (oylar/to'lovlar/timeline),
# "Qo'ng'iroq natijasi" modali (AY + PTP + QI bitta amalda).
from __future__ import annotations

import json

import frappe
from frappe.utils import flt, getdate, nowdate

ALLOWED_ROLES = [
	"System Manager", "Sales Manager", "Sales User", "Sotuv meneger",
	"investor", "Xojakbar_Operator",
]
YOPIQ = ("Yopildi - To'landi", "Yopildi - Boshqa")


def _guard():
	allowed = {r.lower() for r in ALLOWED_ROLES}
	if not (allowed & {r.lower() for r in frappe.get_roles()}):
		frappe.throw("Ruxsat yo'q. Qarzdorlik paneli uchun sotuv roli kerak.", frappe.PermissionError)


def _is_rahbar() -> bool:
	roles = {r.lower() for r in frappe.get_roles()}
	return bool({"system manager", "sales manager"} & roles)


# «Ketgan» belgisini qo'yish huquqi — sotuv rahbari va sotuv menejeri
# (o'quvchining maktabni tashlaganini birinchi bo'lib ular biladi).
KETGAN_ROLLAR = {"system manager", "sales manager", "sotuv meneger"}


def _ketgan_huquqi() -> bool:
	return bool(KETGAN_ROLLAR & {r.lower() for r in frappe.get_roles()})


@frappe.whitelist()
def get_data(ketganlar: int = 0):
	"""Ochiq ishlar ro'yxati + statistikalar + menejerlar (filtr uchun).

	Default'da FAQAT faol (enabled, ketmagan) o'quvchilar ko'rsatiladi — menejer
	navbatida maktabda o'qiyotganlar turishi kerak. Ketganlarning qarzi yo'qolmaydi:
	`ketganlar=1` bilan alohida ro'yxat sifatida ochiladi (panelda chip bor)."""
	_guard()
	ketganlar = int(ketganlar or 0)
	cases = frappe.get_all(
		"Qarz Ishi",
		filters={"ishlov_status": ["not in", list(YOPIQ)]},
		fields=[
			"name", "student", "student_name", "sinf", "payer_name", "payer_phone",
			"qarz_summa", "eng_eski_muddat", "aging_bucket", "ishlov_status",
			"keyingi_aloqa", "masul", "urinishlar_soni", "buzilgan_vadalar",
			"oxirgi_aloqa", "aloqa_cheklovi", "ochilgan_sana",
		],
		order_by="keyingi_aloqa asc, qarz_summa desc",
		limit_page_length=0,
	)

	# O'quvchining faolligi: nofaol (enabled=0) yoki ketgan (date_of_leaving)
	# bo'lsa — u "ketgan" hisoblanadi.
	holat_map = {}
	if cases:
		for st in frappe.get_all(
			"Student",
			filters={"name": ["in", list({c.student for c in cases})]},
			fields=["name", "enabled", "date_of_leaving"],
		):
			holat_map[st.name] = st
	ketgan_soni = 0
	tanlangan = []
	for c in cases:
		st = holat_map.get(c.student)
		c["ketgan"] = 1 if (st and (not st.enabled or st.date_of_leaving)) else 0
		c["ketgan_sana"] = (st or {}).get("date_of_leaving")
		ketgan_soni += c["ketgan"]
		if bool(c["ketgan"]) == bool(ketganlar):
			tanlangan.append(c)
	cases = tanlangan

	# Har ish bo'yicha aloqa yozuvlari soni — "gaplashilgan" (kamida bir marta
	# aloqaga chiqilgan) ishlarni ajratish uchun.
	case_names = [c.name for c in cases]
	aloqa_map = {}
	if case_names:
		for r in frappe.db.sql(
			"""SELECT qarz_ishi, COUNT(*) soni,
			          SUM(CASE WHEN aloqa_natijasi='Gaplashildi' THEN 1 ELSE 0 END) gaplashildi
			   FROM `tabAloqa Yozuvi`
			   WHERE qarz_ishi IN ({}) GROUP BY qarz_ishi""".format(
				", ".join(["%s"] * len(case_names))
			),
			tuple(case_names),
			as_dict=True,
		):
			aloqa_map[r.qarz_ishi] = r
	for c in cases:
		m = aloqa_map.get(c.name)
		c["aloqa_soni"] = int(m.soni) if m else 0
		c["gaplashildi_soni"] = int(m.gaplashildi or 0) if m else 0

	today = getdate(nowdate())
	stats = {
		"ochiq": len(cases),
		"jami_qarz": sum(flt(c.qarz_summa) for c in cases),
		"bugun": 0,
		"otgan": 0,
		"gaplashilgan": sum(1 for c in cases if c["aloqa_soni"] > 0),
		"vada_buzilgan": sum(1 for c in cases if c.ishlov_status == "Va'da buzildi"),
		"eskalatsiya": sum(1 for c in cases if c.ishlov_status == "Eskalatsiya"),
		"ketgan_soni": ketgan_soni,
		"ketganlar_rejimi": 1 if ketganlar else 0,
		"buckets": {},
	}
	for c in cases:
		if c.keyingi_aloqa:
			if getdate(c.keyingi_aloqa) < today:
				stats["otgan"] += 1
			elif getdate(c.keyingi_aloqa) == today:
				stats["bugun"] += 1
		b = c.aging_bucket or "—"
		stats["buckets"].setdefault(b, {"soni": 0, "summa": 0})
		stats["buckets"][b]["soni"] += 1
		stats["buckets"][b]["summa"] += flt(c.qarz_summa)

	managers = sorted({c.masul for c in cases if c.masul})
	user_map = {}
	if managers:
		for u in frappe.get_all(
			"User", filters={"name": ["in", managers]}, fields=["name", "full_name"]
		):
			user_map[u.name] = u.full_name or u.name

	return {
		"cases": cases,
		"stats": stats,
		"managers": [{"name": m, "full_name": user_map.get(m, m)} for m in managers],
		"me": frappe.session.user,
		"rahbar": _is_rahbar(),
		"ketgan_huquqi": _ketgan_huquqi(),
	}


@frappe.whitelist()
def get_case(name: str):
	"""Bitta ish kartasi: reja oylari, to'lovlar, timeline, ota-ona telefonlari."""
	_guard()
	qi = frappe.get_doc("Qarz Ishi", name)

	months, payments, hisob, xulosa = [], [], None, None
	if qi.tolov_rejasi:
		tr = frappe.get_doc("Tolov Rejasi", qi.tolov_rejasi)
		months = [
			{
				"oy_label": r.oy_label, "due_date": r.due_date, "amount": r.amount,
				"paid_amount": r.paid_amount, "qaytim": r.qaytim,
				"outstanding": r.outstanding, "holat": r.holat,
				"reja_amount": r.reja_amount, "nachisleniya": r.nachisleniya,
				"manba_hujjat": r.manba_hujjat, "izoh": r.izoh,
			}
			for r in tr.oylar
		]
		from target_zenit.qarzdorlik import engine

		payments = engine.get_payments(tr.customer, engine._plan_payment_window(tr))

		# Hisob tafsiloti — "nega bunday chiqdi" savoliga javob (UI'da ko'rinadi)
		tolov, qaytim = engine._payments_split(tr.customer, engine._plan_payment_window(tr))
		hisob = {
			"reja": tr.name,
			"customer": tr.customer,
			"davr_boshi": engine._plan_payment_window(tr),
			"jami_tolov": tolov,
			"jami_qaytim": qaytim,
			"sof": tolov - qaytim,
			# Yangi qoidadan keyin jami to'lov bilan jadval farq qilishi MUMKIN:
			# kitob/forma/yotoqxona nachisleniyasiga bog'lanmagan pul o'sha qatorga
			# tushmaydi. Farq ko'rinib turishi uchun ikkisi ham ko'rsatiladi.
			"jadvalga_tushgan": sum(flt(r.paid_amount) for r in tr.oylar),
			"taqsimlanmagan": flt(tr.avans_summa),
			"jadvalda_qaytim": sum(flt(r.qaytim) for r in tr.oylar),
			"hisoblangan": str(tr.modified)[:16],
		}
		# Batafsil xulosa: o'quv to'lovi / kitob-forma / oyma-oy nachisleniya
		xulosa = engine.plan_xulosa(tr)

	# Timeline: aloqa yozuvlari + va'dalar, xronologik (yangi tepada)
	ays = frappe.get_all(
		"Aloqa Yozuvi",
		filters={"qarz_ishi": name},
		fields=[
			"name", "vaqt", "masul", "kanal", "aloqa_natijasi", "hisob_natijasi",
			"komment", "keyingi_harakat", "keyingi_sana", "vada_summa", "vada_sana",
		],
		order_by="vaqt desc",
		limit_page_length=50,
	)
	ptps = frappe.get_all(
		"Tolov Vadasi",
		filters={"qarz_ishi": name},
		fields=["name", "vada_sana", "vada_summa", "holat", "amal_summa", "creation"],
		order_by="creation desc",
		limit_page_length=20,
	)

	guardians = frappe.db.sql(
		"""SELECT COALESCE(g.guardian_name, sg.guardian_name) guardian_name,
		          sg.relation, g.mobile_number
		   FROM `tabStudent Guardian` sg
		   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parent = %s AND sg.parenttype = 'Student'
		   ORDER BY sg.idx""",
		(qi.student,),
		as_dict=True,
	)

	# Shu to'lovchining boshqa farzandlari (aka-uka — bitta qo'ng'iroqda)
	siblings = []
	if qi.payer_phone:
		siblings = frappe.get_all(
			"Qarz Ishi",
			filters={
				"payer_phone": qi.payer_phone,
				"name": ["!=", name],
				"ishlov_status": ["not in", list(YOPIQ)],
			},
			fields=["name", "student_name", "qarz_summa", "masul", "ishlov_status"],
			limit_page_length=10,
		)

	student_phone = frappe.db.get_value("Student", qi.student, "student_mobile_number")

	return {
		"case": qi.as_dict(no_nulls=False),
		"months": months,
		"payments": payments,
		"hisob": hisob,
		"xulosa": xulosa,
		"ays": ays,
		"ptps": ptps,
		"guardians": guardians,
		"siblings": siblings,
		"student_phone": student_phone,
	}


@frappe.whitelist()
def save_call(payload):
	"""«Qo'ng'iroq natijasi» modali: Aloqa Yozuvi yaratadi — qolganini
	(PTP, Qarz Ishi statusi/sanalari) AY'ning o'zi kaskadda qiladi."""
	_guard()
	if isinstance(payload, str):
		payload = json.loads(payload)

	fields = {
		"qarz_ishi", "kanal", "aloqa_natijasi", "hisob_natijasi", "komment",
		"keyingi_harakat", "keyingi_sana", "vada_summa", "vada_sana",
	}
	doc = {"doctype": "Aloqa Yozuvi"}
	doc.update({k: v for k, v in payload.items() if k in fields and v not in (None, "")})
	ay = frappe.get_doc(doc).insert()  # permission tekshiruvi bilan

	qi = frappe.db.get_value(
		"Qarz Ishi",
		ay.qarz_ishi,
		["name", "ishlov_status", "keyingi_aloqa", "urinishlar_soni", "qarz_summa"],
		as_dict=True,
	)
	return {"ay": ay.name, "case": qi}


@frappe.whitelist()
def reassign(case: str, masul: str):
	"""Mas'ulni almashtirish — faqat rahbar."""
	_guard()
	if not _is_rahbar():
		frappe.throw("Mas'ulni faqat rahbar (Sales Manager) almashtira oladi.")
	frappe.db.set_value("Qarz Ishi", case, "masul", masul)
	return {"ok": 1}


@frappe.whitelist()
def qayta_hisobla(case: str):
	"""«Qayta hisoblash» tugmasi — shu o'quvchining rejasini qaytadan hisoblaydi.
	Kod yangilangandan keyin eski qiymatlar qolib ketsa shu yerdan tuzatiladi
	(kechasi nightly baribir hammasini qayta hisoblaydi)."""
	_guard()
	tr = frappe.db.get_value("Qarz Ishi", case, "tolov_rejasi")
	if not tr:
		frappe.throw("Bu ishga to'lov rejasi bog'lanmagan.")
	from target_zenit.qarzdorlik import engine

	engine.recompute_plan(tr, sync_case=True)
	frappe.db.commit()
	return get_case(case)


@frappe.whitelist()
def ketgan_belgilash(case: str, sana: str | None = None, sabab: str | None = None):
	"""«O'quvchi ketdi» — sotuv menejeri panelda belgilaydi, yozuv STUDENT
	hujjatiga tushadi (date_of_leaving + enabled=0) va izoh komment sifatida
	saqlanadi (kim, qachon, nega belgiladi).

	Keyin Student hook'i (`on_student_change`) ketish sanasidan keyingi oylarni
	Bekor qiladi va qolgan qarzni "Ketgan-qarzli" guruhiga o'tkazadi — ya'ni
	qarz yo'qolmaydi, faqat navbatdan chiqadi."""
	_guard()
	if not _ketgan_huquqi():
		frappe.throw("O'quvchini «ketgan» deb belgilashni faqat sotuv menejeri/rahbari qila oladi.")

	student = frappe.db.get_value("Qarz Ishi", case, "student")
	if not student:
		frappe.throw("Ish topilmadi.")
	sana = sana or nowdate()
	if getdate(sana) > getdate(nowdate()):
		frappe.throw("Ketish sanasi kelajakda bo'lishi mumkin emas.")

	doc = frappe.get_doc("Student", student)
	doc.date_of_leaving = sana
	doc.enabled = 0
	doc.save(ignore_permissions=True)
	doc.add_comment(
		"Comment",
		f"Qarzdorlik panelida «ketgan» deb belgilandi: {getdate(sana).strftime('%d.%m.%Y')}"
		+ (f" — {sabab}" if sabab else ""),
	)
	frappe.db.commit()
	return {"ok": 1, "student": student, "sana": sana}


@frappe.whitelist()
def qaytardi(case: str):
	"""Xato belgilangan bo'lsa — o'quvchini qaytarish (ketish sanasi olinadi).

	Ketish belgilanganda Student hook'i ketish sanasidan KEYINGI oylarni Bekor
	qilgan edi — ular ham tiklanadi, aks holda o'quvchi qaytsa ham rejasi
	yarim qolib, nachisleniya tushadigan oylar ko'rinmas edi."""
	_guard()
	if not _ketgan_huquqi():
		frappe.throw("Faqat sotuv menejeri/rahbari qaytara oladi.")
	student = frappe.db.get_value("Qarz Ishi", case, "student")
	ketish = frappe.db.get_value("Student", student, "date_of_leaving")

	doc = frappe.get_doc("Student", student)
	doc.date_of_leaving = None
	doc.enabled = 1
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", "Qarzdorlik panelida «ketgan» belgisi olib tashlandi")

	tiklandi = 0
	if ketish:
		for tr in frappe.get_all(
			"Tolov Rejasi", filters={"student": student, "holat": ["!=", "Bekor"]}, pluck="name"
		):
			for r in frappe.get_all(
				"Tolov Rejasi Oyi",
				filters={"parent": tr, "parenttype": "Tolov Rejasi",
				         "holat": "Bekor", "due_date": [">", ketish]},
				pluck="name",
			):
				frappe.db.set_value(
					"Tolov Rejasi Oyi", r, "holat", "Kutilmoqda", update_modified=False
				)
				tiklandi += 1
			if tiklandi:
				from target_zenit.qarzdorlik import engine

				engine.recompute_plan(tr, sync_case=True)
	frappe.db.commit()
	return {"ok": 1, "student": student, "tiklandi": tiklandi}
