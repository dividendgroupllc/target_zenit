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


@frappe.whitelist()
def get_data():
	"""Ochiq ishlar ro'yxati + statistikalar + menejerlar (filtr uchun)."""
	_guard()
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
	}


@frappe.whitelist()
def get_case(name: str):
	"""Bitta ish kartasi: reja oylari, to'lovlar, timeline, ota-ona telefonlari."""
	_guard()
	qi = frappe.get_doc("Qarz Ishi", name)

	months, payments = [], []
	if qi.tolov_rejasi:
		tr = frappe.get_doc("Tolov Rejasi", qi.tolov_rejasi)
		months = [
			{
				"oy_label": r.oy_label, "due_date": r.due_date, "amount": r.amount,
				"paid_amount": r.paid_amount, "outstanding": r.outstanding, "holat": r.holat,
			}
			for r in tr.oylar
		]
		from target_zenit.qarzdorlik import engine

		payments = engine.get_payments(tr.customer, engine._plan_payment_window(tr))

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
