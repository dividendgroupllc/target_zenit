# Copyright (c) 2026, abdulloh and contributors
# For license information, please see license.txt

"""Nachisleniya Journal Entry submit bo'lganda — o'sha xodim va OY bo'yicha
bog'lanmagan avans to'lovlarini avtomatik ulash.

Oqim: ba'zan oylik avval to'lanadi, nachisleniya keyin yoziladi. Bunda to'lov
avans bo'lib qoladi (Payment Entry.references bo'sh). Nachisleniya yozilgach,
ERPNext'ning o'z vositasi — Payment Reconciliation — orqali ulanadi, chunki
submit bo'lgan Payment Entry'ga bog'lanishni to'g'ridan-to'g'ri qo'shib bo'lmaydi
(references maydonida allow_on_submit = 0).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def _month_of(doc):
    return (doc.get("custom_payment_month") or "").strip() or str(doc.posting_date)[:7]


def link_employee_advances(doc, method=None):
    """JE submit bo'lgach — shu xodim/oy bo'yicha bog'lanmagan to'lovlarni ulash."""
    if doc.doctype != "Journal Entry" or doc.docstatus != 1:
        return
    oy = _month_of(doc)
    if not oy:
        return

    # JE ichidagi xodim qatorlari (kredit tomoni = nachisleniya)
    targets = {}
    for row in doc.get("accounts") or []:
        if row.party_type == "Employee" and row.party and flt(row.credit_in_account_currency) > 0:
            targets.setdefault((row.party, row.account), 0.0)
            targets[(row.party, row.account)] += flt(row.credit_in_account_currency)
    if not targets:
        return

    for (employee, account), _amt in targets.items():
        try:
            _reconcile_one(doc.company, employee, account, oy)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "target_zenit: avans bog'lash")
        try:
            _warn_other_account_advances(doc.company, employee, account, oy)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "target_zenit: avans ogohlantirish")


def _reconcile_one(company, employee, account, oy):
    """Bitta xodim uchun: shu oydagi bog'lanmagan avanslarni nachisleniyaga ulash."""
    pr = frappe.new_doc("Payment Reconciliation")
    pr.company = company
    pr.party_type = "Employee"
    pr.party = employee
    pr.receivable_payable_account = account
    pr.get_unreconciled_entries()

    if not pr.get("payments") or not pr.get("invoices"):
        return

    # To'lov tomonida: oyi ATAYLAB belgilangan bo'lishi shart. Eski (belgilanmagan)
    # to'lovlar sanasiga qarab tasodifan ilinib ketmasligi uchun — ular faqat qo'lda
    # (Payment Reconciliation orqali) bog'lanadi.
    pr.set("payments", [p for p in pr.payments
                        if _explicit_month(p.reference_type, p.reference_name) == oy])
    # Nachisleniya tomonida oy posting date'dan olinadi (maydon avtomatik to'ladi)
    pr.set("invoices", [i for i in pr.invoices
                        if _voucher_month(i.invoice_type, i.invoice_number) == oy])
    if not pr.payments or not pr.invoices:
        return

    pr.allocate_entries({
        "payments": [p.as_dict() for p in pr.payments],
        "invoices": [i.as_dict() for i in pr.invoices],
    })
    if pr.get("allocation"):
        pr.reconcile()


def _voucher_month(doctype, name):
    """Hujjatning "qaysi oy uchun" qiymati (bo'sh bo'lsa — sanasining oyi)."""
    if not doctype or not name:
        return None
    row = frappe.db.get_value(doctype, name, ["custom_payment_month", "posting_date"], as_dict=True)
    if not row:
        return None
    return (row.custom_payment_month or "").strip() or str(row.posting_date)[:7]


def sync_month_from_posting_date(doc, method=None):
    """Nachisleniya hujjatlarida oy — HAR DOIM posting date oyidan.

    Buxgalter qaysi oy uchun nachisleniya yozsa, posting date'ni o'sha oyga suradi
    (25-avgustda yozilgan iyul nachisleniyasi posting date = 14.07). Shuning uchun
    bu hujjatlarda alohida oy tanlash kerak emas — aks holda sana o'zgarganda
    maydon eski oyda qotib qoladi.
    """
    if doc.get("posting_date"):
        doc.custom_payment_month = str(doc.posting_date)[:7]


def _explicit_month(doctype, name):
    """Hujjatda oy ATAYLAB belgilanganmi — bo'lsa o'sha, bo'lmasa None.

    Sanaga qaytish (fallback) yo'q: avtomatik bog'lash faqat operator aniq
    "qaysi oy uchun" deb ko'rsatgan to'lovlarga qo'llanadi.
    """
    if not doctype or not name:
        return None
    return (frappe.db.get_value(doctype, name, "custom_payment_month") or "").strip() or None


def _warn_other_account_advances(company, employee, account, oy):
    """Shu oy uchun BOSHQA qarz hisobida bog'lanmagan avans bo'lsa — ogohlantirish.

    Bunday avans nachisleniyaga ulanmaydi (ERPNext to'lov va nachisleniya bir xil
    hisobda bo'lishini talab qiladi), shuning uchun operator buni bilishi kerak.
    """
    rows = frappe.db.sql("""
        SELECT pe.name, pe.reference_no kassa, ge.account,
               ABS(ge.debit_in_account_currency) amt, ge.account_currency cur
        FROM `tabGL Entry` ge
        JOIN `tabPayment Entry` pe ON pe.name = ge.voucher_no AND pe.docstatus = 1
        JOIN `tabAccount` a ON a.name = ge.account AND a.account_type = 'Payable'
        WHERE ge.is_cancelled = 0 AND ge.voucher_type = 'Payment Entry'
          AND ge.party_type = 'Employee' AND ge.party = %(emp)s
          AND ge.company = %(company)s AND ge.account != %(account)s
          AND ge.debit_in_account_currency > 0
          AND IFNULL(pe.custom_payment_month, '') = %(oy)s
          AND NOT EXISTS (
              SELECT 1 FROM `tabPayment Ledger Entry` ple
              WHERE ple.voucher_no = pe.name AND ple.delinked = 0
                AND ple.against_voucher_no != ple.voucher_no
          )
    """, {"emp": employee, "company": company, "account": account, "oy": oy}, as_dict=True)
    if not rows:
        return

    emp_name = frappe.db.get_value("Employee", employee, "employee_name") or employee

    def _label(r):
        """Operator Kassa bilan ishlaydi — Payment Entry emas, Kassa raqami ko'rsatiladi."""
        if r.kassa and frappe.db.exists("Kassa", r.kassa):
            return (f'<a href="/app/kassa/{frappe.utils.quoted(r.kassa)}" target="_blank">'
                    f'{frappe.utils.escape_html(r.kassa)}</a>')
        return frappe.utils.escape_html(r.name)

    items = "".join(
        f"<li>{_label(r)} — <b>{frappe.utils.escape_html(r.account)}</b>"
        f" · {frappe.utils.fmt_money(r.amt, currency=r.cur)}</li>" for r in rows)
    frappe.msgprint(
        _("<b>{0}</b> uchun bu oyda ({1}) to'lov bor, lekin <b>boshqa qarz hisobida</b> — "
          "shuning uchun bu nachisleniyaga bog'lanmadi:<ul>{2}</ul>"
          "Bog'lanishi uchun nachisleniyani <b>{3}</b> hisobida yozing yoki "
          "o'sha Kassa hujjatini bekor qilib, amend qilib qayta submit qiling.")
        .format(emp_name, oy, items, rows[0].account),
        title=_("Bog'lanmagan to'lov"), indicator="orange")


@frappe.whitelist()
def get_advance_account(employee, posting_date=None, company=None, month=None):
    """Xodimga shu OY uchun Kassadan berilgan bog'lanmagan avans qaysi hisobda.

    Nachisleniya yozilayotganda hisob shu avansnikiga moslanadi — aks holda
    to'lov va nachisleniya har xil hisobda bo'lib, bog'lanmay qoladi.
    Bir nechta hisobda avans bo'lsa — summasi eng kattasi olinadi.
    """
    if not employee:
        return None
    oy = (month or "").strip() or (str(posting_date)[:7] if posting_date else None)
    if not oy:
        return None
    company = company or frappe.db.get_single_value("Global Defaults", "default_company")

    rows = frappe.db.sql("""
        SELECT ge.account, SUM(ge.debit_in_account_currency) amt,
               ge.account_currency cur, COUNT(DISTINCT pe.name) n
        FROM `tabGL Entry` ge
        JOIN `tabPayment Entry` pe ON pe.name = ge.voucher_no AND pe.docstatus = 1
        JOIN `tabAccount` a ON a.name = ge.account AND a.account_type = 'Payable'
        WHERE ge.is_cancelled = 0 AND ge.voucher_type = 'Payment Entry'
          AND ge.party_type = 'Employee' AND ge.party = %(emp)s
          AND ge.company = %(company)s AND ge.debit_in_account_currency > 0
          AND IFNULL(pe.custom_payment_month, '') = %(oy)s
          AND NOT EXISTS (
              SELECT 1 FROM `tabPayment Ledger Entry` ple
              WHERE ple.voucher_no = pe.name AND ple.delinked = 0
                AND ple.against_voucher_no != ple.voucher_no
          )
        GROUP BY ge.account, ge.account_currency
        ORDER BY amt DESC
    """, {"emp": employee, "company": company, "oy": oy}, as_dict=True)
    if not rows:
        return None

    top = rows[0]
    return {"account": top.account, "amount": flt(top.amt), "currency": top.cur,
            "count": cint(top.n), "month": oy}
