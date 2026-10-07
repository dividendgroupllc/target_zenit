# Copyright (c) 2026, Target Zenit
# Xodimlar qarzdorligi paneli — o'qituvchi va xodimlar bitta jadvalda:
# hisoblangan (kredit) / to'langan (debet) / saldo.
#   saldo > 0  -> xodim kompaniyaga qarzdor (avans/qarz/ortiqcha to'lov)
#   saldo < 0  -> kompaniya xodimga qarzdor (to'lanmagan oylik)
#
# Manbalar (hammasi GL, UZS schyotlar):
#   1) party_type='Employee' yozuvlari (oylik nachisleniya JE + to'lov PE/JE)
#   2) "Jalilov B / <F.I.Sh.>" Customer'lari — eski ortiqcha to'lovlar (opening);
#      xodimga employee_name bo'yicha bog'lanadi, topilmasa alohida qator.
from __future__ import annotations

import frappe
from frappe.utils import flt

ALLOWED_ROLES = [
	"System Manager", "Sales Manager", "HR Manager", "HR User",
	"Accounts Manager", "Accounts User", "investor", "Xojakbar_Operator",
]

JALILOV_PREFIX = "Jalilov B /"


def _guard():
	allowed = {r.lower() for r in ALLOWED_ROLES}
	if not (allowed & {r.lower() for r in frappe.get_roles()}):
		frappe.throw("Ruxsat yo'q.", frappe.PermissionError)


def _uzs(ge_row):
	"""GL qatori UZS qiymati (schyot UZS bo'lsa account currency, aks holda base USD->UZS)."""
	if ge_row.account_currency == "UZS":
		return flt(ge_row.debit_acc), flt(ge_row.credit_acc)
	# USD schyot (kam uchraydi) — taxminiy kurs bilan
	rate = 12000.0
	return flt(ge_row.debit) * rate, flt(ge_row.credit) * rate


@frappe.whitelist()
def get_data():
	_guard()

	# 1) Employee-party GL agregati
	emp_gl = frappe.db.sql(
		"""SELECT ge.party, a.account_currency,
		          SUM(ge.debit_in_account_currency) debit_acc,
		          SUM(ge.credit_in_account_currency) credit_acc,
		          SUM(ge.debit) debit, SUM(ge.credit) credit,
		          MAX(ge.posting_date) oxirgi
		   FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name = ge.account
		   WHERE ge.party_type='Employee' AND ge.is_cancelled=0
		   GROUP BY ge.party, a.account_currency""",
		as_dict=True,
	)
	by_emp = {}
	for r in emp_gl:
		d, c = _uzs(r)
		row = by_emp.setdefault(r.party, {"debit": 0, "credit": 0, "oxirgi": None})
		row["debit"] += d
		row["credit"] += c
		if not row["oxirgi"] or (r.oxirgi and r.oxirgi > row["oxirgi"]):
			row["oxirgi"] = r.oxirgi

	# 2) "Jalilov B /" customer'lari (eski ortiqcha to'lovlar)
	jal = frappe.db.sql(
		"""SELECT ge.party, a.account_currency,
		          SUM(ge.debit_in_account_currency) debit_acc,
		          SUM(ge.credit_in_account_currency) credit_acc,
		          SUM(ge.debit) debit, SUM(ge.credit) credit,
		          MAX(ge.posting_date) oxirgi
		   FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name = ge.account
		   WHERE ge.party_type='Customer' AND ge.party LIKE %s AND ge.is_cancelled=0
		   GROUP BY ge.party, a.account_currency""",
		(JALILOV_PREFIX + "%",),
		as_dict=True,
	)

	employees = frappe.get_all(
		"Employee",
		fields=["name", "employee_name", "designation", "status", "cell_number"],
		limit_page_length=0,
	)
	emp_by_id = {e.name: e for e in employees}
	emp_by_name = {}
	for e in employees:
		emp_by_name.setdefault((e.employee_name or "").strip().lower(), e)

	rows = {}

	def ensure_row(emp=None, party_label=None):
		key = emp.name if emp else f"~{party_label}"
		if key not in rows:
			rows[key] = {
				"employee": emp.name if emp else None,
				"ism": emp.employee_name if emp else party_label,
				"lavozim": (emp.designation if emp else "") or "",
				"faol": (emp.status == "Active") if emp else False,
				"telefon": (emp.cell_number if emp else "") or "",
				"hisoblangan": 0.0,   # kredit (oylik yozilgani)
				"tolangan": 0.0,      # debet (to'lab berilgani)
				"eski_qarz": 0.0,     # Jalilov B qoldig'i
				"oxirgi": None,
				"jalilov_party": None,
			}
		return rows[key]

	for party, v in by_emp.items():
		emp = emp_by_id.get(party)
		row = ensure_row(emp, party_label=party)
		row["hisoblangan"] += v["credit"]
		row["tolangan"] += v["debit"]
		if v["oxirgi"] and (not row["oxirgi"] or v["oxirgi"] > row["oxirgi"]):
			row["oxirgi"] = v["oxirgi"]

	for r in jal:
		d, c = _uzs(r)
		saldo = d - c
		if abs(saldo) < 1:
			continue
		fio = r.party[len(JALILOV_PREFIX):].strip()
		emp = emp_by_name.get(fio.lower())
		if not emp:
			# Xodimga mos kelmaganlari (masalan "Svet jarimasi", "o'quvchilar to'lovi")
			# xodim paneliga kirmaydi — ular moliya/investor hisobotiga tegishli
			continue
		row = ensure_row(emp, party_label=fio + " (eski)")
		row["eski_qarz"] += saldo
		row["jalilov_party"] = r.party
		if r.oxirgi and (not row["oxirgi"] or r.oxirgi > row["oxirgi"]):
			row["oxirgi"] = r.oxirgi

	# Faol, lekin GL harakati yo'q xodimlar ham jadvalda ko'rinsin
	for e in employees:
		if e.status == "Active" and e.name not in rows:
			ensure_row(e)

	out = []
	for row in rows.values():
		# saldo > 0: xodim qarzdor; < 0: kompaniya qarzdor
		row["saldo"] = (row["tolangan"] - row["hisoblangan"]) + row["eski_qarz"]
		out.append(row)
	out.sort(key=lambda x: -x["saldo"])

	stats = {
		"xodim_qarzi": sum(r["saldo"] for r in out if r["saldo"] > 0),
		"xodim_qarzi_soni": sum(1 for r in out if r["saldo"] > 1000),
		"kompaniya_qarzi": -sum(r["saldo"] for r in out if r["saldo"] < 0),
		"kompaniya_qarzi_soni": sum(1 for r in out if r["saldo"] < -1000),
		"jami": len(out),
	}
	return {"rows": out, "stats": stats}


@frappe.whitelist()
def get_detail(employee=None, jalilov_party=None):
	"""Bitta xodim: oylar kesimi (nachisleniya vs to'lov, custom_payment_month
	bo'yicha — bo'sh bo'lsa posting oyi) + GL harakatlari (oxirgi 60 ta)."""
	_guard()
	conds, params = [], []
	if employee:
		conds.append("(ge.party_type='Employee' AND ge.party=%s)")
		params.append(employee)
	if jalilov_party:
		conds.append("(ge.party_type='Customer' AND ge.party=%s)")
		params.append(jalilov_party)
	if not conds:
		return {"months": [], "gl": []}

	gl = frappe.db.sql(
		f"""SELECT ge.posting_date, ge.voucher_type, ge.voucher_no, ge.account,
		           ge.debit_in_account_currency debit, ge.credit_in_account_currency credit,
		           LEFT(COALESCE(je.user_remark, ge.remarks, ''), 160) izoh,
		           COALESCE(NULLIF(TRIM(je.custom_payment_month), ''),
		                    NULLIF(TRIM(pe.custom_payment_month), ''),
		                    DATE_FORMAT(ge.posting_date, '%%Y-%%m')) oy
		    FROM `tabGL Entry` ge
		    LEFT JOIN `tabJournal Entry` je ON je.name = ge.voucher_no AND ge.voucher_type='Journal Entry'
		    LEFT JOIN `tabPayment Entry` pe ON pe.name = ge.voucher_no AND ge.voucher_type='Payment Entry'
		    WHERE ({' OR '.join(conds)}) AND ge.is_cancelled=0
		    ORDER BY ge.posting_date DESC, ge.creation DESC""",
		tuple(params),
		as_dict=True,
	)

	months = {}
	for r in gl:
		m = months.setdefault(r.oy, {"oy": r.oy, "hisoblangan": 0.0, "tolangan": 0.0})
		m["hisoblangan"] += flt(r.credit)
		m["tolangan"] += flt(r.debit)
	month_rows = sorted(months.values(), key=lambda x: x["oy"], reverse=True)
	for m in month_rows:
		m["farq"] = m["hisoblangan"] - m["tolangan"]  # >0: shu oy uchun to'lanmagan

	return {"months": month_rows, "gl": gl[:60]}
