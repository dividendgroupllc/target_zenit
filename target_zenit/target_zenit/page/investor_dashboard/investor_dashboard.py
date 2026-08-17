# Copyright (c) 2026, Target Zenit
# Investor moliyaviy dashboard — manba: ERPNext GL Entry / Account / Education Fees / Employee Advance.
# Har bir hisob-kitob himoyalangan (try/except) + edge-case'lar (0'ga bo'lish, valyuta, bo'sh davr,
# kelajak oy, doctype yo'qligi) hisobga olingan. Sof accrual P&L + kassa pul oqimi alohida.

from __future__ import annotations

import calendar
from collections import defaultdict

import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, today

MONTHS_UZ = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
             "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]
MONTHS_SHORT_UZ = ["Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]
DIVIDEND_NUMBERS = ("3200", "3201", "3202")

# Kassa pul oqimi kategoriyalari (kirim/chiqim manbasi bo'yicha)
CAT_LABELS = {
    "customer": "O'quvchilar / mijozlar",
    "shareholder": "Ta'sischilar",
    "supplier": "Ta'minotchilar",
    "employee": "Xodimlar",
    "dividend": "Dividend",
    "expense": "Xarajatlar",
    "transfer": "Ko'chirmalar",
    "other": "Boshqa",
}


# ===========================================================================
# Umumiy yordamchilar
# ===========================================================================
def _has(doctype: str) -> bool:
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


def _default_company():
    c = frappe.defaults.get_user_default("Company")
    if not c:
        c = frappe.db.get_single_value("Global Defaults", "default_company")
    if not c:
        names = frappe.get_all("Company", pluck="name", limit=1)
        c = names[0] if names else None
    return c


def _company_currency(company):
    if company:
        cur = frappe.db.get_value("Company", company, "default_currency")
        if cur:
            return cur
    return "UZS"


def _co(company, alias=""):
    if not company:
        return ""
    col = f"{alias}." if alias else ""
    return f" AND {col}company = %(company)s"


def _cmp(cur, prev):
    """Taqqoslash: joriy vs oldingi → {value, prev, delta_abs, delta_pct}. 0'ga bo'lish himoyalangan."""
    cur = flt(cur)
    prev = flt(prev)
    if not prev:
        pct = None  # oldingi 0 bo'lsa foiz hisoblab bo'lmaydi ("yangi")
    else:
        pct = round((cur - prev) / abs(prev) * 100, 1)
    return {"value": cur, "prev": prev, "delta_abs": round(cur - prev, 2), "delta_pct": pct}


def _month_bounds(ref_date, i=0):
    d = getdate(add_months(ref_date, -i))
    return get_first_day(d), get_last_day(d), MONTHS_SHORT_UZ[d.month - 1], d


# ===========================================================================
# Kassa hisoblari
# ===========================================================================
def _cash_accounts(company):
    accs = {}
    try:
        filters = {"company": company} if company else {}
        for r in frappe.get_all("Mode of Payment Account", filters=filters,
                                fields=["default_account", "parent"]):
            if r.default_account:
                accs.setdefault(r.default_account, r.parent)
    except Exception:
        pass
    if not accs:
        try:
            f = {"account_type": ["in", ["Cash", "Bank"]], "is_group": 0}
            if company:
                f["company"] = company
            for a in frappe.get_all("Account", filters=f, fields=["name"]):
                accs[a.name] = a.name
        except Exception:
            pass
    return accs


def _acc_currency(account):
    return frappe.db.get_value("Account", account, "account_currency") or "UZS"


def _balance_before(accounts, date, company):
    """Berilgan sanadan OLDINGI qoldiq (opening uchun)."""
    if not accounts:
        return {}
    rows = frappe.db.sql(
        f"""SELECT account, IFNULL(SUM(debit_in_account_currency - credit_in_account_currency),0) bal
            FROM `tabGL Entry`
            WHERE account IN %(a)s AND posting_date < %(d)s AND is_cancelled=0 {_co(company)}
            GROUP BY account""",
        {"a": tuple(accounts), "d": date, "company": company}, as_dict=True)
    return {r.account: flt(r.bal) for r in rows}


def _balance_upto(accounts, date, company):
    if not accounts:
        return {}
    rows = frappe.db.sql(
        f"""SELECT account, IFNULL(SUM(debit_in_account_currency - credit_in_account_currency),0) bal
            FROM `tabGL Entry`
            WHERE account IN %(a)s AND posting_date <= %(d)s AND is_cancelled=0 {_co(company)}
            GROUP BY account""",
        {"a": tuple(accounts), "d": date, "company": company}, as_dict=True)
    return {r.account: flt(r.bal) for r in rows}


def _cash_section(company, from_date, to_date, company_currency):
    """Har hisob: opening → kirim → chiqim → closing (DDS uslubi)."""
    accs = _cash_accounts(company)
    account_list = list(accs.keys())
    opening = _balance_before(account_list, from_date, company)
    period = {}
    if account_list:
        rows = frappe.db.sql(
            f"""SELECT account,
                       IFNULL(SUM(debit_in_account_currency),0) kirim,
                       IFNULL(SUM(credit_in_account_currency),0) chiqim
                FROM `tabGL Entry`
                WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
                  AND is_cancelled=0 {_co(company)}
                GROUP BY account""",
            {"a": tuple(account_list), "f": from_date, "t": to_date, "company": company}, as_dict=True)
        period = {r.account: (flt(r.kirim), flt(r.chiqim)) for r in rows}

    rows_out = []
    tot = {"opening": 0.0, "kirim": 0.0, "chiqim": 0.0, "closing": 0.0}
    other = defaultdict(lambda: {"opening": 0.0, "closing": 0.0})
    main_accounts = []
    for account, mode in accs.items():
        cur = _acc_currency(account)
        op = flt(opening.get(account, 0.0))
        kirim, chiqim = period.get(account, (0.0, 0.0))
        cl = op + kirim - chiqim
        row = {"account": account, "mode": mode, "currency": cur,
               "opening": op, "kirim": kirim, "chiqim": chiqim, "closing": cl}
        rows_out.append(row)
        if cur == company_currency:
            main_accounts.append(account)
            tot["opening"] += op
            tot["kirim"] += kirim
            tot["chiqim"] += chiqim
            tot["closing"] += cl
        else:
            other[cur]["opening"] += op
            other[cur]["closing"] += cl
    rows_out.sort(key=lambda r: -r["closing"])
    return {
        "accounts": rows_out,
        "total": tot,
        "other": [{"currency": c, "opening": v["opening"], "closing": v["closing"]} for c, v in other.items()],
        "main_accounts": main_accounts,
    }


def _cashflow_by_category(main_accounts, company, from_date, to_date):
    """Kassa kirim/chiqimini kontragent kategoriyasi bo'yicha ajratish."""
    inflow = defaultdict(float)
    outflow = defaultdict(float)
    if not main_accounts:
        return {"in": [], "out": []}
    rows = frappe.db.sql(
        f"""SELECT voucher_type, voucher_no, party_type, `against`,
                   debit_in_account_currency AS d, credit_in_account_currency AS c
            FROM `tabGL Entry`
            WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
              AND is_cancelled=0 {_co(company)}""",
        {"a": tuple(main_accounts), "f": from_date, "t": to_date, "company": company}, as_dict=True)
    if not rows:
        return {"in": [], "out": []}

    pe_names = list({r.voucher_no for r in rows if r.voucher_type == "Payment Entry"})
    je_names = list({r.voucher_no for r in rows if r.voucher_type == "Journal Entry"})
    pe_info = {}
    if pe_names:
        for pe in frappe.get_all("Payment Entry", filters={"name": ["in", pe_names]},
                                 fields=["name", "party_type", "payment_type"]):
            pe_info[pe.name] = (pe.party_type, pe.payment_type)
    je_info = defaultdict(list)
    if je_names:
        jrows = frappe.db.sql(
            """SELECT jea.parent, jea.party_type, a.root_type, a.account_number
               FROM `tabJournal Entry Account` jea
               JOIN `tabAccount` a ON a.name = jea.account
               WHERE jea.parent IN %(n)s""",
            {"n": tuple(je_names)}, as_dict=True)
        for j in jrows:
            je_info[j.parent].append((j.party_type, j.root_type, j.account_number))

    ptmap = {"Customer": "customer", "Supplier": "supplier",
             "Employee": "employee", "Shareholder": "shareholder", "Student": "customer"}

    def resolve(r):
        if r.voucher_type == "Payment Entry":
            pt, ptype = pe_info.get(r.voucher_no, (None, None))
            if ptype == "Internal Transfer":
                return "transfer"
            if pt in ptmap:
                return ptmap[pt]
        if r.voucher_type == "Journal Entry":
            lines = je_info.get(r.voucher_no, [])
            for party_type, _root_type, _num in lines:
                if party_type in ptmap:
                    return ptmap[party_type]
            for _party_type, root_type, num in lines:
                if root_type == "Equity" and (num or "") in DIVIDEND_NUMBERS:
                    return "dividend"
                if root_type == "Expense":
                    return "expense"
        if r.party_type in ptmap:
            return ptmap[r.party_type]
        return "other"

    for r in rows:
        cat = resolve(r)
        if flt(r.d) > 0:
            inflow[cat] += flt(r.d)
        if flt(r.c) > 0:
            outflow[cat] += flt(r.c)

    def pack(dd):
        items = [{"key": k, "label": CAT_LABELS.get(k, k), "amount": v} for k, v in dd.items() if v > 0.5]
        items.sort(key=lambda x: -x["amount"])
        return items
    return {"in": pack(inflow), "out": pack(outflow)}


def _monthly_flow(main_accounts, company, ref_date, months_back=12):
    labels, income, expense, net = [], [], [], []
    if not main_accounts:
        return {"months": labels, "income": income, "expense": expense, "net": net}
    for i in range(months_back - 1, -1, -1):
        f, t, short, _ = _month_bounds(ref_date, i)
        row = frappe.db.sql(
            f"""SELECT IFNULL(SUM(debit_in_account_currency),0) kirim,
                       IFNULL(SUM(credit_in_account_currency),0) chiqim
                FROM `tabGL Entry`
                WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
                  AND is_cancelled=0 {_co(company)}""",
            {"a": tuple(main_accounts), "f": f, "t": t, "company": company}, as_dict=True)
        labels.append(short)
        income.append(flt(row[0].kirim))
        expense.append(flt(row[0].chiqim))
        net.append(flt(row[0].kirim) - flt(row[0].chiqim))
    return {"months": labels, "income": income, "expense": expense, "net": net}


def _daily_collection(main_accounts, company, ref_date):
    d = getdate(ref_date)
    first, last = get_first_day(d), get_last_day(d)
    days = {}
    if main_accounts:
        try:
            rows = frappe.db.sql(
                f"""SELECT DAY(posting_date) day, IFNULL(SUM(debit_in_account_currency),0) amt
                    FROM `tabGL Entry`
                    WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
                      AND is_cancelled=0 {_co(company)}
                    GROUP BY DAY(posting_date)""",
                {"a": tuple(main_accounts), "f": first, "t": last, "company": company}, as_dict=True)
            for r in rows:
                if flt(r.amt) > 0:
                    days[int(r.day)] = flt(r.amt)
        except Exception:
            pass
    return {"year": d.year, "month": d.month, "month_label": MONTHS_UZ[d.month - 1],
            "first_weekday": getdate(first).weekday(), "days_in_month": calendar.monthrange(d.year, d.month)[1],
            "days": days}


def _balance_trend(main_accounts, company, ref_date, months_back=12):
    out = []
    if not main_accounts:
        return out
    for i in range(months_back - 1, -1, -1):
        _, last, short, _ = _month_bounds(ref_date, i)
        bal = sum(_balance_upto(main_accounts, last, company).values())
        out.append({"label": short, "value": flt(bal)})
    return out


# ===========================================================================
# P&L (accrual) — daromad / xarajat / sof foyda
# ===========================================================================
def _root_total(root_type, company, from_date, to_date, currency, positive_is_credit):
    sign = "credit_in_account_currency - debit_in_account_currency" if positive_is_credit \
        else "debit_in_account_currency - credit_in_account_currency"
    try:
        row = frappe.db.sql(
            f"""SELECT IFNULL(SUM({sign}),0) v
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.root_type=%(rt)s AND ge.posting_date BETWEEN %(f)s AND %(t)s
                  AND ge.is_cancelled=0 AND ge.account_currency=%(cur)s {_co(company,'ge')}""",
            {"rt": root_type, "f": from_date, "t": to_date, "cur": currency, "company": company}, as_dict=True)
        return flt(row[0].v)
    except Exception:
        return 0.0


def _pnl_period(company, from_date, to_date, currency):
    income = _root_total("Income", company, from_date, to_date, currency, positive_is_credit=True)
    expense = _root_total("Expense", company, from_date, to_date, currency, positive_is_credit=False)
    net = income - expense
    margin = round(net / income * 100, 1) if income else None
    return {"income": income, "expense": expense, "net": net, "margin": margin}


def _expense_breakdown(company, from_date, to_date, currency, prev_from, prev_to):
    out = []
    try:
        rows = frappe.db.sql(
            f"""SELECT a.account_name name,
                       IFNULL(SUM(ge.debit_in_account_currency - ge.credit_in_account_currency),0) amt
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.root_type='Expense' AND ge.posting_date BETWEEN %(f)s AND %(t)s
                  AND ge.is_cancelled=0 AND ge.account_currency=%(cur)s {_co(company,'ge')}
                GROUP BY a.name HAVING amt>0 ORDER BY amt DESC""",
            {"f": from_date, "t": to_date, "cur": currency, "company": company}, as_dict=True)
        for r in rows:
            out.append({"label": r.name, "amount": flt(r.amt)})
    except Exception:
        pass
    # Dividend
    try:
        div = frappe.db.sql(
            f"""SELECT IFNULL(SUM(ge.debit_in_account_currency),0) amt
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.root_type='Equity' AND a.account_number IN %(n)s
                  AND ge.posting_date BETWEEN %(f)s AND %(t)s AND ge.is_cancelled=0
                  AND ge.account_currency=%(cur)s {_co(company,'ge')}""",
            {"n": DIVIDEND_NUMBERS, "f": from_date, "t": to_date, "cur": currency, "company": company}, as_dict=True)
        if div and flt(div[0].amt) > 0:
            out.append({"label": "Dividend", "amount": flt(div[0].amt)})
    except Exception:
        pass
    out.sort(key=lambda x: -x["amount"])
    if len(out) > 7:
        head, tail = out[:7], out[7:]
        head.append({"label": "Boshqa", "amount": sum(x["amount"] for x in tail)})
        out = head
    total = sum(x["amount"] for x in out) or 1
    for x in out:
        x["pct"] = round(x["amount"] / total * 100, 1)
    return out


def _monthly_pnl(company, ref_date, currency, months_back=12):
    labels, income, expense, net, margin = [], [], [], [], []
    for i in range(months_back - 1, -1, -1):
        f, t, short, _ = _month_bounds(ref_date, i)
        p = _pnl_period(company, f, t, currency)
        labels.append(short)
        income.append(p["income"])
        expense.append(p["expense"])
        net.append(p["net"])
        margin.append(p["margin"] if p["margin"] is not None else 0)
    return {"months": labels, "income": income, "expense": expense, "net": net, "margin": margin}


# ===========================================================================
# Qarzdorlik (debitorka / kreditorka / xodim)
# ===========================================================================
def _party_total(company, date, account_type, positive_is_debit, currency):
    sign = "debit_in_account_currency - credit_in_account_currency" if positive_is_debit \
        else "credit_in_account_currency - debit_in_account_currency"
    try:
        row = frappe.db.sql(
            f"""SELECT IFNULL(SUM({sign}),0) v
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.account_type=%(at)s AND ge.posting_date<=%(d)s AND ge.is_cancelled=0
                  AND ge.account_currency=%(cur)s {_co(company,'ge')}""",
            {"at": account_type, "d": date, "cur": currency, "company": company}, as_dict=True)
        return flt(row[0].v)
    except Exception:
        return 0.0


def _party_top(company, date, account_type, positive_is_debit, currency, limit=6):
    sign = "ge.debit_in_account_currency - ge.credit_in_account_currency" if positive_is_debit \
        else "ge.credit_in_account_currency - ge.debit_in_account_currency"
    out = []
    try:
        rows = frappe.db.sql(
            f"""SELECT ge.party_type, ge.party, IFNULL(SUM({sign}),0) bal
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.account_type=%(at)s AND ge.posting_date<=%(d)s AND ge.is_cancelled=0
                  AND ge.account_currency=%(cur)s AND ge.party IS NOT NULL AND ge.party!=''
                  {_co(company,'ge')}
                GROUP BY ge.party_type, ge.party HAVING bal>0 ORDER BY bal DESC LIMIT %(l)s""",
            {"at": account_type, "d": date, "cur": currency, "company": company, "l": limit}, as_dict=True)
        for r in rows:
            out.append({"name": _party_name(r.party_type, r.party), "amount": flt(r.bal)})
    except Exception:
        pass
    return out


def _party_name(party_type, party):
    field = {"Customer": "customer_name", "Supplier": "supplier_name", "Employee": "employee_name",
             "Shareholder": "title", "Student": "student_name"}.get(party_type)
    if field:
        try:
            n = frappe.db.get_value(party_type, party, field)
            if n:
                return n
        except Exception:
            pass
    return party


def _receivable_aging(company, date, currency):
    buckets = [("0–30 kun", 0, 30), ("30–60 kun", 30, 60), ("60–90 kun", 60, 90), ("90+ kun", 90, 10 ** 6)]
    out = [{"label": b[0], "amount": 0.0} for b in buckets]
    try:
        rows = frappe.db.sql(
            f"""SELECT DATEDIFF(%(d)s, ge.posting_date) age,
                       IFNULL(SUM(ge.debit_in_account_currency - ge.credit_in_account_currency),0) bal
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.account_type='Receivable' AND ge.posting_date<=%(d)s AND ge.is_cancelled=0
                  AND ge.account_currency=%(cur)s {_co(company,'ge')}
                GROUP BY ge.posting_date""",
            {"d": date, "cur": currency, "company": company}, as_dict=True)
        for r in rows:
            age = int(r.age or 0)
            for i, (_, lo, hi) in enumerate(buckets):
                if lo <= age < hi:
                    out[i]["amount"] += flt(r.bal)
                    break
    except Exception:
        pass
    return out


def _employee_advances():
    if not _has("Employee Advance"):
        return {"total": 0.0, "top": [], "available": False}
    total = 0.0
    agg = defaultdict(float)
    try:
        for r in frappe.get_all("Employee Advance", filters={"docstatus": 1},
                                fields=["employee_name", "paid_amount", "claimed_amount", "return_amount"]):
            outstanding = flt(r.paid_amount) - flt(r.claimed_amount) - flt(r.return_amount)
            if outstanding > 0:
                total += outstanding
                agg[r.employee_name or "—"] += outstanding
    except Exception:
        pass
    top = [{"name": n, "amount": a} for n, a in sorted(agg.items(), key=lambda x: -x[1])[:5]]
    return {"total": total, "top": top, "available": True}


# ===========================================================================
# O'quvchilar to'lovi (Education Fees)
# ===========================================================================
def _tuition_section(company):
    res = {"available": False, "active": 0, "with_fees": 0,
           "billed": 0.0, "collected": 0.0, "outstanding": 0.0, "rate": None,
           "status": {"paid": 0, "partial": 0, "debtor": 0},
           "by_class": [], "top_debtors": []}
    if _has("Student"):
        try:
            res["active"] = frappe.db.count("Student", {"enabled": 1})
        except Exception:
            try:
                res["active"] = frappe.db.count("Student")
            except Exception:
                pass
    if not _has("Fees"):
        return res
    res["available"] = True
    try:
        rows = frappe.db.sql(
            """SELECT student, student_name,
                      IFNULL(SUM(grand_total),0) billed,
                      IFNULL(SUM(outstanding_amount),0) outstanding
               FROM `tabFees` WHERE docstatus=1 GROUP BY student, student_name""", as_dict=True)
        for r in rows:
            billed = flt(r.billed)
            outstanding = flt(r.outstanding)
            collected = billed - outstanding
            res["with_fees"] += 1
            res["billed"] += billed
            res["collected"] += collected
            res["outstanding"] += outstanding
            if outstanding <= 0.5:
                res["status"]["paid"] += 1
            elif outstanding >= billed - 0.5:
                res["status"]["debtor"] += 1
            else:
                res["status"]["partial"] += 1
            if outstanding > 0.5:
                res["top_debtors"].append({"name": r.student_name or r.student, "amount": outstanding})
        res["rate"] = round(res["collected"] / res["billed"] * 100, 1) if res["billed"] else None
        res["top_debtors"].sort(key=lambda x: -x["amount"])
        res["top_debtors"] = res["top_debtors"][:6]
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: fees")
    # Sinf (program) kesimi
    try:
        cls = frappe.db.sql(
            """SELECT COALESCE(NULLIF(program,''),'Belgilanmagan') label,
                      COUNT(DISTINCT student) students,
                      IFNULL(SUM(grand_total),0) billed,
                      IFNULL(SUM(grand_total - outstanding_amount),0) collected
               FROM `tabFees` WHERE docstatus=1 GROUP BY label
               HAVING billed>0 ORDER BY billed DESC LIMIT 10""", as_dict=True)
        for c in cls:
            billed = flt(c.billed)
            res["by_class"].append({
                "label": c.label, "students": int(c.students or 0),
                "billed": billed, "collected": flt(c.collected),
                "rate": round(flt(c.collected) / billed * 100, 1) if billed else 0,
            })
    except Exception:
        pass
    return res


# ===========================================================================
# Asosiy API
# ===========================================================================
ALLOWED_ROLES = ["System Manager", "Accounts Manager", "Accounts User", "investor"]


def _guard():
    """Rolni harf ko'rinishiga befarq (case-insensitive) tekshirish."""
    allowed = {r.lower() for r in ALLOWED_ROLES}
    user_roles = {r.lower() for r in frappe.get_roles()}
    if not (allowed & user_roles):
        frappe.throw(
            "Ruxsat yo'q. Investor paneli uchun 'investor' roli kerak.",
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_dashboard_data(year=None, month=None):
    _guard()

    tdy = getdate(today())
    year = int(year) if year else tdy.year
    month = int(month) if month else tdy.month
    ref = getdate(f"{year}-{month:02d}-01")
    f0, t0 = get_first_day(ref), get_last_day(ref)
    pf, pt, _, _ = _month_bounds(ref, 1)          # oldingi oy
    yf, yt, _, ydate = _month_bounds(ref, 12)     # o'tgan yil shu oy
    is_future = ref > getdate(f"{tdy.year}-{tdy.month:02d}-01")

    company = _default_company()
    ccy = _company_currency(company)

    warnings = []
    flags = {"has_fees": _has("Fees"), "has_employee_advance": _has("Employee Advance"),
             "has_students": _has("Student")}

    # ---- Kassa ----
    try:
        cash = _cash_section(company, f0, t0, ccy)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: cash")
        cash = {"accounts": [], "total": {"opening": 0, "kirim": 0, "chiqim": 0, "closing": 0}, "other": [], "main_accounts": []}
    main_accounts = cash["main_accounts"]
    cash_now = cash["total"]["closing"]
    cash_prev = sum(_balance_upto(main_accounts, pt, company).values())
    cash_yoy = sum(_balance_upto(main_accounts, yt, company).values())

    flow = _monthly_flow(main_accounts, company, ref, 12)
    cat = _cashflow_by_category(main_accounts, company, f0, t0)

    # ---- P&L ----
    pnl_cur = _pnl_period(company, f0, t0, ccy)
    pnl_prev = _pnl_period(company, pf, pt, ccy)
    pnl_yoy = _pnl_period(company, yf, yt, ccy)

    # ---- Qarzdorlik ----
    rec_now = _party_total(company, t0, "Receivable", True, ccy)
    rec_prev = _party_total(company, pt, "Receivable", True, ccy)
    pay_now = _party_total(company, t0, "Payable", False, ccy)
    pay_prev = _party_total(company, pt, "Payable", False, ccy)
    emp = _employee_advances()

    # ---- O'quvchilar ----
    tuition = _tuition_section(company)

    net_balance = cash_now + rec_now - pay_now - emp["total"]
    net_prev = cash_prev + rec_prev - pay_prev - emp["total"]

    if not main_accounts:
        warnings.append("Kassa hisoblari topilmadi (Mode of Payment Account sozlanmagan).")
    if not flags["has_fees"]:
        warnings.append("Education Fees ma'lumoti yo'q — o'quvchi to'lov bo'limi cheklangan.")
    if is_future:
        warnings.append("Tanlangan oy kelajakda — ba'zi ko'rsatkichlar hali to'lmagan.")

    return {
        "meta": {
            "company": company, "currency": ccy,
            "period": {"year": year, "month": month, "label": f"{MONTHS_UZ[month - 1]} {year}",
                       "from": str(f0), "to": str(t0)},
            "prev_label": f"{MONTHS_SHORT_UZ[getdate(pf).month - 1]} {getdate(pf).year}",
            "yoy_label": f"{ydate.year}",
            "is_future": is_future, "flags": flags, "warnings": warnings,
        },
        "overview": {
            "cash": _cmp(cash_now, cash_prev), "cash_yoy": _cmp(cash_now, cash_yoy),
            "cash_other": cash["other"],
            "income": _cmp(pnl_cur["income"], pnl_prev["income"]), "income_yoy": _cmp(pnl_cur["income"], pnl_yoy["income"]),
            "expense": _cmp(pnl_cur["expense"], pnl_prev["expense"]), "expense_yoy": _cmp(pnl_cur["expense"], pnl_yoy["expense"]),
            "net_profit": _cmp(pnl_cur["net"], pnl_prev["net"]), "net_profit_yoy": _cmp(pnl_cur["net"], pnl_yoy["net"]),
            "margin": pnl_cur["margin"],
            "receivable": _cmp(rec_now, rec_prev), "payable": _cmp(pay_now, pay_prev),
            "net_balance": _cmp(net_balance, net_prev),
            "components": {"cash": cash_now, "receivable": rec_now, "payable": pay_now, "employee": emp["total"]},
            "active_students": tuition["active"],
            "collection_rate": tuition["rate"],
            "balance_trend": _balance_trend(main_accounts, company, ref, 12),
        },
        "cashflow": {
            "accounts": cash["accounts"], "total": cash["total"], "other": cash["other"],
            "categories": cat, "monthly": flow,
            "daily": _daily_collection(main_accounts, company, ref),
        },
        "pnl": {
            "current": pnl_cur, "prev": pnl_prev, "yoy": pnl_yoy,
            "expense_breakdown": _expense_breakdown(company, f0, t0, ccy, pf, pt),
            "monthly": _monthly_pnl(company, ref, ccy, 12),
        },
        "debts": {
            "receivable": {"total": rec_now, "cmp": _cmp(rec_now, rec_prev),
                           "aging": _receivable_aging(company, t0, ccy),
                           "top": _party_top(company, t0, "Receivable", True, ccy)},
            "payable": {"total": pay_now, "cmp": _cmp(pay_now, pay_prev),
                        "top": _party_top(company, t0, "Payable", False, ccy)},
            "employee": emp,
            "net_working": rec_now - pay_now,
        },
        "tuition": tuition,
    }


@frappe.whitelist()
def get_years():
    try:
        rows = frappe.db.sql("SELECT DISTINCT YEAR(posting_date) y FROM `tabGL Entry` "
                             "WHERE is_cancelled=0 ORDER BY y DESC")
        years = [int(r[0]) for r in rows if r[0]]
    except Exception:
        years = []
    ty = getdate(today()).year
    if ty not in years:
        years.insert(0, ty)
    return years
