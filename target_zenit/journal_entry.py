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
from frappe.utils import flt


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
