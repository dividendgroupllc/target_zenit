# Copyright (c) 2026, Target Zenit
# To'lov rejalarini ommaviy yaratish: 1-sentabrdan 10 oy (sentabr..iyun),
# oylik summa = Student.custom_monthly_payment.
#
# Ishga tushirish:
#   bench --site target.local execute target_zenit.qarzdorlik.setup.generate_plans
# Natijani ko'rish uchun avval dry run:
#   bench --site target.local execute target_zenit.qarzdorlik.setup.generate_plans --kwargs "{'dry_run': 1}"
from __future__ import annotations

import json

import frappe
from frappe.utils import flt, getdate

OYLAR = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # sentabr..iyun
OY_NOMI = {
	1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May", 6: "Iyun",
	9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}


def _months(academic_year: str):
	start_year = int(academic_year.split("-")[0])
	out = []
	for m in OYLAR:
		y = start_year if m >= 9 else start_year + 1
		out.append((f"{OY_NOMI[m]} {y}", getdate(f"{y}-{m:02d}-01")))
	return out


def backfill_payer():
	"""Mavjud ochiq Qarz Ishi'larda bo'sh to'lovchi ism/telefonni to'ldiradi
	(zanjir: Student.payer -> ota-ona Guardian -> o'quvchining o'zi)."""
	from target_zenit.qarzdorlik.engine import YOPIQ_STATUSLAR, _payer_info

	cases = frappe.get_all(
		"Qarz Ishi",
		filters={"ishlov_status": ["not in", list(YOPIQ_STATUSLAR)]},
		fields=["name", "student", "payer_name", "payer_phone"],
	)
	updated = telsiz = 0
	for c in cases:
		if c.payer_phone:
			continue
		nm, tel = _payer_info(c.student)
		if not tel:
			telsiz += 1
			continue
		vals = {"payer_phone": tel}
		if not c.payer_name and nm:
			vals["payer_name"] = nm
		frappe.db.set_value("Qarz Ishi", c.name, vals, update_modified=False)
		updated += 1
	frappe.db.commit()
	print(json.dumps({"jami_ochiq": len(cases), "toldirildi": updated, "tel_topilmadi": telsiz}, ensure_ascii=False))



def joriy_oquv_yili() -> str:
	"""Sentabr-iyun: 1-iyuldan keyin yangi o'quv yili boshlanadi."""
	t = getdate(frappe.utils.nowdate())
	return f"{t.year}-{t.year + 1}" if t.month >= 7 else f"{t.year - 1}-{t.year}"


def plan_yarat(student: str, academic_year: str | None = None, dry_run: int = 0):
	"""Bitta o'quvchiga Tolov Rejasi (idempotent).

	Qaytaradi: reja nomi | None (reja kerak emas yoki allaqachon bor).
	Sabablari: grant/investor (summa yo'q), shartnomasiz, nofaol, reja bor."""
	academic_year = academic_year or joriy_oquv_yili()
	s = frappe.db.get_value(
		"Student", student,
		["name", "student_name", "enabled", "joining_date", "custom_shartnoma_qilindi",
		 "custom_monthly_payment", "custom_final_amount"],
		as_dict=True,
	)
	if not s or not s.enabled or not s.custom_shartnoma_qilindi:
		return None

	months = _months(academic_year)
	monthly = flt(s.custom_monthly_payment)
	final = flt(s.custom_final_amount)
	if monthly <= 0 and final <= 0:
		return None                      # grant/investor — qarz nazoratiga kirmaydi
	if monthly <= 0:
		monthly = final / len(months)

	if frappe.db.exists("Tolov Rejasi", {
		"student": s.name, "academic_year": academic_year, "holat": ["!=", "Bekor"]}):
		return None

	joined = getdate(s.joining_date) if s.joining_date else None
	rows = [
		{"oy_label": label, "due_date": due, "amount": monthly}
		for label, due in months
		if not (joined and joined > due and (joined.year, joined.month) != (due.year, due.month))
	]
	if not rows or dry_run:
		return None

	doc = frappe.get_doc({
		"doctype": "Tolov Rejasi", "student": s.name, "academic_year": academic_year,
		"holat": "Faol", "oylik_tolov": monthly, "yakuniy_summa": final, "oylar": rows,
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def generate_plans(academic_year: str = "2026-2027", dry_run: int = 0):
	"""Shartnomali faol o'quvchilarga Tolov Rejasi yaratadi (bor bo'lsa o'tkazib yuboradi).

	Chetda qoladiganlar (hisobotda ko'rinadi, jim o'tmaydi):
	  - grant/investor: summa ham, oylik ham 0 — bu norma;
	  - nomuvofiq: yakuniy != oylik x oylar soni."""
	students = frappe.get_all(
		"Student",
		filters={"enabled": 1, "custom_shartnoma_qilindi": 1},
		fields=[
			"name", "student_name", "joining_date", "customer",
			"custom_monthly_payment", "custom_final_amount", "custom_tariff",
		],
	)
	months = _months(academic_year)
	res = {"yaratildi": 0, "bor_edi": 0, "grant_investor": [], "nomuvofiq": [], "xato": []}

	for s in students:
		monthly = flt(s.custom_monthly_payment)
		final = flt(s.custom_final_amount)

		if monthly <= 0 and final <= 0:
			res["grant_investor"].append(f"{s.student_name} ({s.name}, tarif={s.custom_tariff})")
			continue
		if monthly <= 0 and final > 0:
			monthly = final / len(months)

		if frappe.db.exists(
			"Tolov Rejasi",
			{"student": s.name, "academic_year": academic_year, "holat": ["!=", "Bekor"]},
		):
			res["bor_edi"] += 1
			continue

		# O'quv yili o'rtasida kelgan: kelgan oyidan boshlab to'liq oylar
		joined = getdate(s.joining_date) if s.joining_date else None
		rows = []
		for label, due in months:
			if joined and joined > due and (joined.year, joined.month) != (due.year, due.month):
				continue
			rows.append({"oy_label": label, "due_date": due, "amount": monthly})

		if not rows:
			res["xato"].append(f"{s.student_name} ({s.name}): reja oylari chiqmadi")
			continue

		total = monthly * len(rows)
		if final and len(rows) == len(months) and abs(total - final) > 1:
			res["nomuvofiq"].append(
				f"{s.student_name} ({s.name}): oylik {monthly:,.0f} x {len(rows)} = "
				f"{total:,.0f} != yakuniy {final:,.0f}"
			)

		if dry_run:
			res["yaratildi"] += 1
			continue

		try:
			frappe.get_doc(
				{
					"doctype": "Tolov Rejasi",
					"student": s.name,
					"academic_year": academic_year,
					"holat": "Faol",
					"oylik_tolov": monthly,
					"yakuniy_summa": final,
					"oylar": rows,
				}
			).insert(ignore_permissions=True)
			res["yaratildi"] += 1
		except Exception as e:
			res["xato"].append(f"{s.student_name} ({s.name}): {e}")

	if not dry_run:
		frappe.db.commit()

	summary = {
		"yaratildi": res["yaratildi"],
		"bor_edi": res["bor_edi"],
		"grant_investor_soni": len(res["grant_investor"]),
		"nomuvofiq": res["nomuvofiq"][:30],
		"xato": res["xato"][:30],
	}
	print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
	return summary
