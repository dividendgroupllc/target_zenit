# Copyright (c) 2026, Target Zenit
# Xodimlar qarzdorligi paneli — o'qituvchi va xodimlar bitta jadvalda:
# hisoblangan (kredit) / to'langan (debet) / saldo.
#   saldo > 0  -> xodim kompaniyaga qarzdor (avans/qarz/ortiqcha to'lov)
#   saldo < 0  -> kompaniya xodimga qarzdor (to'lanmagan oylik)
#
# Manba: FAQAT party_type='Employee' GL qatorlari (UZS schyotlar) —
# investor dashboardi bilan bir xil mantiq. "Jalilov B / <FIO>" Customer qatorlari
# ATAYLAB qo'shilmaydi: ular o'sha xodim yozuvining ikkinchi tomoni (ikki marta sanash).
from __future__ import annotations

import frappe
from frappe.utils import flt

ALLOWED_ROLES = [
	"System Manager", "Sales Manager", "HR Manager", "HR User",
	"Accounts Manager", "Accounts User", "investor", "Xojakbar_Operator",
]

def _guard():
	allowed = {r.lower() for r in ALLOWED_ROLES}
	if not (allowed & {r.lower() for r in frappe.get_roles()}):
		frappe.throw("Ruxsat yo'q.", frappe.PermissionError)


@frappe.whitelist()
def get_data():
	"""Xodimlar saldosi — FAQAT party_type='Employee' GL qatorlaridan (UZS schyotlar).

	MUHIM (2026-10-08 tuzatildi): avval "Jalilov B / <FIO>" Customer qatorlari ham
	qo'shilardi — bu IKKI MARTA sanash edi. Chunki "ortiqcha to'lov investorga
	o'tkazildi" Journal Entry'sining ikkala tomoni ham bitta hujjatda:
	    Dt  Jalilov B - TZ        (Customer: Jalilov B / <FIO>)
	    Kt  Creditors Xodimlar    (Employee: HR-EMP-xxxxx)
	Xodim tomoni allaqachon saldoni to'g'rilaydi, ustiga Jalilov tomonini qo'shsak —
	summa ikkilanadi (misol: Abraham Ilao haqiqatda 0, panel -15 123 182 ko'rsatgan).
	34 ta Jalilov qatoridan 32 tasi aynan shunday juftlikda edi."""
	_guard()

	emp_gl = frappe.db.sql(
		"""SELECT ge.party,
		          SUM(ge.debit_in_account_currency) debit,
		          SUM(ge.credit_in_account_currency) credit,
		          MAX(ge.posting_date) oxirgi
		   FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name = ge.account
		   WHERE ge.party_type='Employee' AND ge.is_cancelled=0
		     AND a.account_currency='UZS'
		   GROUP BY ge.party""",
		as_dict=True,
	)

	employees = frappe.get_all(
		"Employee",
		fields=["name", "employee_name", "designation", "status", "cell_number"],
		limit_page_length=0,
	)
	emp_by_id = {e.name: e for e in employees}

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
				"oxirgi": None,
			}
		return rows[key]

	for v in emp_gl:
		emp = emp_by_id.get(v.party)
		row = ensure_row(emp, party_label=v.party)
		row["hisoblangan"] += flt(v.credit)
		row["tolangan"] += flt(v.debit)
		if v.oxirgi and (not row["oxirgi"] or v.oxirgi > row["oxirgi"]):
			row["oxirgi"] = v.oxirgi

	# Faol, lekin GL harakati yo'q xodimlar ham jadvalda ko'rinsin
	for e in employees:
		if e.status == "Active" and e.name not in rows:
			ensure_row(e)

	out = []
	for row in rows.values():
		# saldo > 0: xodim qarzdor; < 0: kompaniya qarzdor
		row["saldo"] = row["tolangan"] - row["hisoblangan"]
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
	"""Bitta xodim: oylar kesimi (nachisleniya vs to'lov) + harakatlar.

	- Faqat party_type='Employee' qatorlari (Jalilov tomoni qo'shilmaydi — §get_data).
	- Harakatlar HUJJAT bo'yicha guruhlanadi: bitta Payment Entry GL'da bir necha
	  qatorga bo'linishi mumkin (bir qismi avans, bir qismi JE'ga taqsimlangan) —
	  foydalanuvchiga u "bitta kassa ikki marta" bo'lib ko'rinadi. Endi bitta qator."""
	_guard()
	if not employee:
		return {"months": [], "gl": []}

	gl = frappe.db.sql(
		"""SELECT ge.posting_date, ge.voucher_type, ge.voucher_no,
		          SUM(ge.debit_in_account_currency) debit,
		          SUM(ge.credit_in_account_currency) credit,
		          LEFT(COALESCE(MAX(je.user_remark), MAX(ge.remarks), ''), 200) izoh,
		          COALESCE(NULLIF(TRIM(MAX(je.custom_payment_month)), ''),
		                   NULLIF(TRIM(MAX(pe.custom_payment_month)), ''),
		                   DATE_FORMAT(ge.posting_date, '%%Y-%%m')) oy,
		          COUNT(*) qatorlar
		   FROM `tabGL Entry` ge
		   JOIN `tabAccount` a ON a.name = ge.account
		   LEFT JOIN `tabJournal Entry` je ON je.name = ge.voucher_no AND ge.voucher_type='Journal Entry'
		   LEFT JOIN `tabPayment Entry` pe ON pe.name = ge.voucher_no AND ge.voucher_type='Payment Entry'
		   WHERE ge.party_type='Employee' AND ge.party=%s AND ge.is_cancelled=0
		     AND a.account_currency='UZS'
		   GROUP BY ge.voucher_no, ge.posting_date, ge.voucher_type
		   ORDER BY ge.posting_date DESC, ge.voucher_no DESC""",
		(employee,),
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
