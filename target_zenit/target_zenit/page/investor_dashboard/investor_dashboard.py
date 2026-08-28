# Copyright (c) 2026, Target Zenit
# Investor moliyaviy dashboard — manba: ERPNext GL Entry / Account / Education Fees / Employee Advance.
# Har bir hisob-kitob himoyalangan (try/except) + edge-case'lar (0'ga bo'lish, valyuta, bo'sh davr,
# kelajak oy, doctype yo'qligi) hisobga olingan. Sof accrual P&L + kassa pul oqimi alohida.

from __future__ import annotations

import calendar
import re
from collections import defaultdict

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate, today

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


def _cash_bank_universe(tracked, company):
    """Ichki o'tkazmani aniqlash uchun KENG kassa/bank to'plami: account_type Cash/Bank bo'lgan
    barcha hisoblar + kuzatilayotgan (Mode of Payment) hisoblar. Bu ba'zi bank hisobi to'lov usuli
    sifatida sozlanmagan bo'lsa ham ko'chirmani to'g'ri tutadi."""
    uni = set(tracked or [])
    try:
        f = {"account_type": ["in", ["Cash", "Bank"]], "is_group": 0}
        if company:
            f["company"] = company
        for a in frappe.get_all("Account", filters=f, fields=["name"]):
            uni.add(a.name)
    except Exception:
        pass
    return uni


def _internal_transfer_flows(cash_accounts, company, from_date, to_date):
    """'Ichki o'tkazma' (konvertatsiya / kassa-bank ko'chirma) — pul o'z kassa/bank hisoblari orasida
    yuradi. Voucher ≥2 ta har xil kassa/bank hisobiga tegsa → ichki o'tkazma (DDS 'Перемещения' bilan
    bir xil g'oya). Haqiqiy tashqi harakat (mijoz to'lovi, xarajat, maosh) faqat BITTA kassa hisobiga
    tegadi → noto'g'ri chiqarib yuborilmaydi. Valyuta ayirmasi (Income/Expense) oyog'i bo'lsa ham tutadi.

    Qaytaradi: ({account: {kirim, chiqim}}, {ichki o'tkazma voucher_no lar to'plami})."""
    flows = defaultdict(lambda: {"kirim": 0.0, "chiqim": 0.0})
    internal = set()
    if not cash_accounts:
        return flows, internal
    rows = frappe.db.sql(
        f"""SELECT voucher_no, account,
                   debit_in_account_currency d, credit_in_account_currency c
            FROM `tabGL Entry`
            WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
              AND is_cancelled=0 {_co(company)}""",
        {"a": tuple(cash_accounts), "f": from_date, "t": to_date, "company": company}, as_dict=True)
    if not rows:
        return flows, internal
    vnos = list({r.voucher_no for r in rows if r.voucher_no})
    if not vnos:
        return flows, internal
    universe = _cash_bank_universe(cash_accounts, company)
    # Har voucher nechta HAR XIL kassa/bank hisobiga tegadi? ≥2 → ichki o'tkazma
    ncash = {}
    chunk = 800
    for i in range(0, len(vnos), chunk):
        part = vnos[i:i + chunk]
        res = frappe.db.sql(
            f"""SELECT voucher_no, COUNT(DISTINCT account) n
                FROM `tabGL Entry`
                WHERE voucher_no IN %(v)s AND account IN %(u)s AND is_cancelled=0 {_co(company)}
                GROUP BY voucher_no""",
            {"v": tuple(part), "u": tuple(universe), "company": company}, as_dict=True)
        for r in res:
            ncash[r.voucher_no] = int(r.n or 0)
    internal = {vn for vn, n in ncash.items() if n >= 2}
    for r in rows:
        if r.voucher_no in internal:
            flows[r.account]["kirim"] += flt(r.d)
            flows[r.account]["chiqim"] += flt(r.c)
    return flows, internal


def _cash_section(company, from_date, to_date, company_currency):
    """Har hisob: opening → kirim → chiqim → closing (DDS uslubi).
    Kirim/chiqim HAMMA joyda (KPI, valyuta kesimi va hisoblar jadvali) ichki o'tkazmasiz —
    konvertatsiya va ko'chirma (peremeshenie) chiqarib tashlanadi, chunki bular kompaniya ichidagi
    harakat, real savdo oqimi emas. Yakuniy qoldiq esa haqiqiy kassa balansi bo'lib qoladi."""
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

    # Ichki o'tkazma (konvertatsiya/ko'chirma) oqimlari — jami kirim/chiqimdan chiqariladi
    tflows, pure_vouchers = _internal_transfer_flows(account_list, company, from_date, to_date)

    rows_out = []
    tot = {"opening": 0.0, "kirim": 0.0, "chiqim": 0.0, "closing": 0.0}
    other = defaultdict(lambda: {"opening": 0.0, "closing": 0.0})
    # Har valyuta kesimida jami (kirim/chiqim ichki o'tkazmasiz, closing haqiqiy) — "Jami USD / Jami UZS"
    by_ccy = defaultdict(lambda: {"opening": 0.0, "kirim": 0.0, "chiqim": 0.0, "closing": 0.0, "accounts": 0})
    main_accounts = []
    for account, mode in accs.items():
        cur = _acc_currency(account)
        op = flt(opening.get(account, 0.0))
        kirim, chiqim = period.get(account, (0.0, 0.0))
        cl = op + kirim - chiqim                       # HAQIQIY yakuniy qoldiq (to'liq harakat)
        tf = tflows.get(account, {"kirim": 0.0, "chiqim": 0.0})
        k_ext = kirim - flt(tf["kirim"])               # ichki o'tkazmasiz kirim
        c_ext = chiqim - flt(tf["chiqim"])             # ichki o'tkazmasiz chiqim
        # hisoblar kesimi jadvali: kirim/chiqim ICHKI O'TKAZMASIZ (konvertatsiya/ko'chirma chiqarilgan);
        # yakuniy qoldiq esa haqiqiy kassa balansi (op + to'liq kirim − to'liq chiqim).
        row = {"account": account, "mode": mode, "currency": cur,
               "opening": op, "kirim": k_ext, "chiqim": c_ext, "closing": cl}
        rows_out.append(row)
        b = by_ccy[cur]
        b["opening"] += op
        b["kirim"] += k_ext
        b["chiqim"] += c_ext
        b["closing"] += cl
        b["accounts"] += 1
        if cur == company_currency:
            main_accounts.append(account)
            tot["opening"] += op
            tot["kirim"] += k_ext
            tot["chiqim"] += c_ext
            tot["closing"] += cl
        else:
            other[cur]["opening"] += op
            other[cur]["closing"] += cl
    rows_out.sort(key=lambda r: -r["closing"])
    # company valyutasi birinchi, keyin closing bo'yicha
    by_currency = [dict(currency=c, **v) for c, v in by_ccy.items()]
    by_currency.sort(key=lambda x: (x["currency"] != company_currency, -x["closing"]))
    return {
        "accounts": rows_out,
        "total": tot,
        "other": [{"currency": c, "opening": v["opening"], "closing": v["closing"]} for c, v in other.items()],
        "by_currency": by_currency,
        "main_accounts": main_accounts,
        "pure_transfer_vouchers": pure_vouchers,
    }


def _cashflow_by_category(all_accounts, main_set, acc_ccy, company_currency, company, from_date, to_date,
                          pure_vouchers=None):
    """Kassa kirim/chiqimini kontragent kategoriyasi + aniq kontragent (batafsil) + valyuta bo'yicha ajratish.
    Kategoriya/party jamlanmasi faqat asosiy (company) valyuta hisoblari (main_set) bo'yicha;
    tranzaksiyalar (in_tx/out_tx) esa barcha valyutalar bo'yicha (har biri o'z valyuta belgisi bilan).
    Ichki o'tkazma (pure_vouchers — konvertatsiya/ko'chirma) kirim/chiqimga KIRMAYDI (chiqarib tashlanadi)."""
    pure_set = pure_vouchers or set()
    empty = {"in": [], "out": [], "in_detail": [], "out_detail": [], "in_tx": [], "out_tx": []}
    inflow = defaultdict(float)
    outflow = defaultdict(float)
    inflow_p = defaultdict(float)   # (cat, party_type, party) -> summa
    outflow_p = defaultdict(float)
    if not all_accounts:
        return empty
    rows = frappe.db.sql(
        f"""SELECT voucher_type, voucher_no, party_type, party, `against`, account, posting_date,
                   debit_in_account_currency AS d, credit_in_account_currency AS c
            FROM `tabGL Entry`
            WHERE account IN %(a)s AND posting_date BETWEEN %(f)s AND %(t)s
              AND is_cancelled=0 {_co(company)}""",
        {"a": tuple(all_accounts), "f": from_date, "t": to_date, "company": company}, as_dict=True)
    if not rows:
        return empty

    pe_names = list({r.voucher_no for r in rows if r.voucher_type == "Payment Entry"})
    je_names = list({r.voucher_no for r in rows if r.voucher_type == "Journal Entry"})
    pe_info = {}
    if pe_names:
        for pe in frappe.get_all("Payment Entry", filters={"name": ["in", pe_names]},
                                 fields=["name", "party_type", "party", "payment_type"]):
            pe_info[pe.name] = (pe.party_type, pe.party, pe.payment_type)
    je_info = defaultdict(list)
    if je_names:
        jrows = frappe.db.sql(
            """SELECT jea.parent, jea.party_type, jea.party, a.root_type, a.account_number
               FROM `tabJournal Entry Account` jea
               JOIN `tabAccount` a ON a.name = jea.account
               WHERE jea.parent IN %(n)s""",
            {"n": tuple(je_names)}, as_dict=True)
        for j in jrows:
            je_info[j.parent].append((j.party_type, j.party, j.root_type, j.account_number))

    ptmap = {"Customer": "customer", "Supplier": "supplier",
             "Employee": "employee", "Shareholder": "shareholder", "Student": "customer"}

    def resolve(r):
        """(kategoriya, party_type, party) qaytaradi."""
        if r.voucher_type == "Payment Entry":
            pt, party, ptype = pe_info.get(r.voucher_no, (None, None, None))
            if ptype == "Internal Transfer":
                return "transfer", None, None
            if pt in ptmap:
                return ptmap[pt], pt, party
            if pt:
                return "other", pt, party
        if r.voucher_type == "Journal Entry":
            lines = je_info.get(r.voucher_no, [])
            for party_type, party, _root_type, _num in lines:
                if party_type in ptmap:
                    return ptmap[party_type], party_type, party
            for _party_type, _party, root_type, num in lines:
                if root_type == "Equity" and (num or "") in DIVIDEND_NUMBERS:
                    return "dividend", None, None
                if root_type == "Expense":
                    return "expense", None, None
        if r.party_type in ptmap:
            return ptmap[r.party_type], r.party_type, r.party
        return "other", None, None

    in_tx, out_tx = [], []      # har bir to'lov: sana + kontragent + kategoriya + summa (kimdan/kimga · qancha · qachon)
    name_cache = {}

    def pname(pt, party, cat):
        if not party:
            return CAT_LABELS.get(cat, cat)   # kontragentsiz (ko'chirma/dividend/xarajat) — kategoriya nomi
        key = (pt, party)
        if key not in name_cache:
            name_cache[key] = _party_name(pt, party)
        return name_cache[key]

    for r in rows:
        if r.voucher_no in pure_set:
            continue  # ichki o'tkazma (konvertatsiya/ko'chirma) — kassa kirim/chiqimiga kirmaydi
        cat, pt, party = resolve(r)
        if cat == "transfer":
            continue  # zaxira: resolve() ichki o'tkazma deb topgan bo'lsa ham chiqarib tashlaymiz
        d, c = flt(r.d), flt(r.c)
        is_main = r.account in main_set               # asosiy valyuta hisobi (jamlanma faqat shu)
        cur = acc_ccy.get(r.account) or company_currency
        if d > 0:
            if is_main:
                inflow[cat] += d
                if party:
                    inflow_p[(cat, pt, party)] += d
            in_tx.append({"date": str(r.posting_date), "category": cat,
                          "category_label": CAT_LABELS.get(cat, cat), "party_type": pt,
                          "party": party, "name": pname(pt, party, cat),
                          "amount": d, "currency": cur, "voucher": r.voucher_no})
        if c > 0:
            if is_main:
                outflow[cat] += c
                if party:
                    outflow_p[(cat, pt, party)] += c
            out_tx.append({"date": str(r.posting_date), "category": cat,
                           "category_label": CAT_LABELS.get(cat, cat), "party_type": pt,
                           "party": party, "name": pname(pt, party, cat),
                           "amount": c, "currency": cur, "voucher": r.voucher_no})

    def pack(dd):
        items = [{"key": k, "label": CAT_LABELS.get(k, k), "amount": v} for k, v in dd.items() if v > 0.5]
        items.sort(key=lambda x: -x["amount"])
        return items

    def pack_detail(dd):
        items = []
        for (cat, pt, party), amt in dd.items():
            if amt <= 0.5:
                continue
            items.append({"category": cat, "category_label": CAT_LABELS.get(cat, cat),
                          "party_type": pt, "party": party, "name": _party_name(pt, party),
                          "amount": amt})
        items.sort(key=lambda x: -x["amount"])
        return items[:200]

    # tranzaksiyalar: eng yangi sana birinchi, keyin summa bo'yicha (barcha valyuta; frontend filtrlaydi)
    in_tx.sort(key=lambda x: (x["date"], x["amount"]), reverse=True)
    out_tx.sort(key=lambda x: (x["date"], x["amount"]), reverse=True)
    return {"in": pack(inflow), "out": pack(outflow),
            "in_detail": pack_detail(inflow_p), "out_detail": pack_detail(outflow_p),
            "in_tx": in_tx[:600], "out_tx": out_tx[:600]}


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
# Xarajat guruhlari — Budjet vs oddiy (Chart of Accounts guruhi bo'yicha)
# ===========================================================================
def _is_budget_group(name):
    n = (name or "").lower()
    return "budget" in n or "budjet" in n or "бюджет" in n or "byudjet" in n


def _budget_split(company, from_date, to_date, currency):
    """Xarajatni ikki guruhga ajratish: budjetga kirgan / kirmagan. Guruh nomidan avtomatik aniqlanadi."""
    out = {"available": False, "budget": 0.0, "normal": 0.0,
           "budget_label": "Budjet xarajati", "normal_label": "Budjetdan tashqari xarajat",
           "budget_accounts": [], "normal_accounts": []}
    try:
        gfilt = {"root_type": "Expense", "is_group": 1}
        if company:
            gfilt["company"] = company
        groups = frappe.get_all("Account", filters=gfilt, fields=["account_name", "lft", "rgt"])
        branges = [(g.lft, g.rgt) for g in groups if _is_budget_group(g.account_name)]
        if not branges:
            return out  # budjet guruhi topilmadi → mavjud emas
        rows = frappe.db.sql(
            f"""SELECT a.account_name name, a.lft lft,
                       IFNULL(SUM(ge.debit_in_account_currency - ge.credit_in_account_currency),0) amt
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name=ge.account
                WHERE a.root_type='Expense' AND a.is_group=0
                  AND ge.posting_date BETWEEN %(f)s AND %(t)s AND ge.is_cancelled=0
                  AND ge.account_currency=%(cur)s {_co(company,'ge')}
                GROUP BY a.name, a.account_name, a.lft""",
            {"f": from_date, "t": to_date, "cur": currency, "company": company}, as_dict=True)
        bud_list, nor_list = [], []
        for r in rows:
            amt = flt(r.amt)
            if abs(amt) < 0.5:
                continue
            item = {"label": r.name, "amount": amt}
            if any(lo <= (r.lft or 0) <= hi for lo, hi in branges):
                out["budget"] += amt
                bud_list.append(item)
            else:
                out["normal"] += amt
                nor_list.append(item)
        bud_list.sort(key=lambda x: -x["amount"])
        nor_list.sort(key=lambda x: -x["amount"])
        out["budget_accounts"] = bud_list
        out["normal_accounts"] = nor_list
        out["available"] = True
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: budget_split")
    return out


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


def _party_groups_map(rows):
    """Kontragent qatorlari uchun guruhni to'plamli aniqlaydi (Customer->customer_group,
    Supplier->supplier_group). Kam so'rov: har tur uchun bitta IN-so'rov."""
    cust, supp = set(), set()
    for r in rows:
        if r["party_type"] == "Customer":
            cust.add(r["party"])
        elif r["party_type"] == "Supplier":
            supp.add(r["party"])
    m = {}
    try:
        if cust:
            for d in frappe.get_all("Customer", filters={"name": ["in", list(cust)]},
                                    fields=["name", "customer_group"]):
                m[("Customer", d.name)] = d.customer_group or ""
        if supp:
            for d in frappe.get_all("Supplier", filters={"name": ["in", list(supp)]},
                                    fields=["name", "supplier_group"]):
                m[("Supplier", d.name)] = d.supplier_group or ""
    except Exception:
        pass
    return m


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
def _student_payments(company, from_date, to_date):
    """O'quvchi to'lovlari — bevosita Payment Entry (Receive) asosida.
    Maktabda Fees (schyot) ishlatilmaydi, faqat to'lovlar yoziladi → to'lovlarni
    o'quvchi kesimida, izohlari (remarks) bilan ko'rsatamiz. Faqat customer_group='Student'
    bo'lgan mijozlar; payment_type='Receive' (chiquvchi/xato 'Pay' yozuvlar chiqarib tashlanadi).
    Summa = KASSAGA TUSHGAN REAL PUL (received_amount), valyutasi = tushgan hisob valyutasi.
    Kassalar asosan so'm bo'lgani uchun ko'pchiligi so'm da chiqadi (USD $166.66 → 2 000 000 so'm).
    Yon ma'lumot sifatida o'quvchi to'lagan asl summa (paid_amount + paid_from valyutasi) ham beriladi."""
    res = {"by_currency": [], "students": [], "recent": [],
           "total_count": 0, "total_students": 0, "period_total_base": 0.0}
    if not from_date or not to_date:
        return res
    try:
        rows = frappe.db.sql(
            f"""SELECT pe.name, pe.posting_date, pe.party, pe.party_name,
                       pe.paid_amount, pe.paid_from_account_currency ccy,
                       pe.received_amount, pe.paid_to_account_currency deposit_ccy,
                       pe.base_paid_amount, pe.mode_of_payment, pe.paid_to,
                       pe.reference_no, k.remarks kassa_remarks, pe.remarks pe_remarks
                FROM `tabPayment Entry` pe
                JOIN `tabCustomer` c ON c.name = pe.party AND c.customer_group = 'Student'
                LEFT JOIN `tabKassa` k ON k.name = pe.reference_no
                WHERE pe.docstatus = 1 AND pe.party_type = 'Customer'
                  AND pe.payment_type = 'Receive'
                  AND pe.posting_date BETWEEN %(f)s AND %(t)s {_co(company, 'pe')}
                ORDER BY pe.posting_date DESC, pe.name DESC""",
            {"f": from_date, "t": to_date, "company": company}, as_dict=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: student payments")
        return res
    if not rows:
        return res

    byc = defaultdict(lambda: {"total": 0.0, "count": 0, "students": set()})
    stud = defaultdict(lambda: {"total": 0.0, "count": 0, "last_date": None,
                                "currency": None, "name": None})
    all_students = set()
    base_total = 0.0
    for r in rows:
        amt = flt(r.received_amount)          # KASSAGA TUSHGAN REAL PUL
        cur = r.deposit_ccy or ""             # tushgan hisob valyutasi (asosan so'm)
        base_total += flt(r.base_paid_amount)
        b = byc[cur]
        b["total"] += amt
        b["count"] += 1
        b["students"].add(r.party)
        all_students.add(r.party)
        key = (r.party, cur)
        s = stud[key]
        s["total"] += amt
        s["count"] += 1
        s["name"] = r.party_name or r.party
        s["currency"] = cur
        if s["last_date"] is None or str(r.posting_date) > str(s["last_date"]):
            s["last_date"] = str(r.posting_date)

    res["by_currency"] = sorted(
        [{"currency": c, "total": v["total"], "count": v["count"],
          "students": len(v["students"])} for c, v in byc.items()],
        key=lambda x: -x["total"])
    res["students"] = sorted(
        [{"name": v["name"], "party": k[0], "currency": v["currency"],
          "total": v["total"], "count": v["count"], "last_date": v["last_date"]}
         for k, v in stud.items()], key=lambda x: -x["total"])
    def _clean(s):
        # Kassa izohi: tab bilan ajratilgan (ism<TAB>izoh) + oxiridagi qator — tozalaymiz
        return " ".join((s or "").replace("\t", " ").replace("\r", " ").split()).strip()
    res["recent"] = [{"name": r.name, "date": str(r.posting_date),
                      "student": r.party_name or r.party,
                      "amount": flt(r.received_amount), "currency": r.deposit_ccy or "",
                      "orig_amount": flt(r.paid_amount), "orig_currency": r.ccy or "",
                      "mode": r.mode_of_payment or "", "ref": r.reference_no or "",
                      "remarks": _clean(r.kassa_remarks) or _clean(r.pe_remarks)} for r in rows[:400]]
    res["total_count"] = len(rows)
    res["total_students"] = len(all_students)
    res["period_total_base"] = base_total
    return res


def _tuition_section(company, from_date=None, to_date=None):
    res = {"available": False, "active": 0, "contracted": 0, "with_fees": 0,
           "billed": 0.0, "collected": 0.0, "outstanding": 0.0, "rate": None,
           "status": {"paid": 0, "partial": 0, "debtor": 0},
           "by_class": [], "top_debtors": [],
           "payments": _student_payments(company, from_date, to_date)}
    if _has("Student"):
        try:
            res["active"] = frappe.db.count("Student", {"enabled": 1})
        except Exception:
            try:
                res["active"] = frappe.db.count("Student")
            except Exception:
                pass
        # Shartnoma qilingan faol o'quvchilar (custom_shartnoma_qilindi — Student custom field);
        # maydon bo'lmagan saytda xato bermasligi uchun himoyalangan
        try:
            res["contracted"] = frappe.db.count(
                "Student", {"enabled": 1, "custom_shartnoma_qilindi": 1})
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
# Umumiy tab kartalari — debitorka/kreditorka toifa kesimi, o'quvchilar sinf
# kesimi (Student Group), pul qoldiqlari va balans (mockup dizayni uchun)
# ===========================================================================
PARTY_CAT_LABELS = {
    "customer": "O'quvchilar",
    "employee": "Xodimlar (o'qituvchilar)",
    "supplier": "Ta'minotchilar",
    "shareholder": "Investorlar",
    "kredit": "Kredit",
    "other": "Boshqa",
}


def _party_balance_cards(company, date):
    """Debitorka/kreditorka — sana holatiga, valyuta + kontragent toifasi kesimida.
    Har kontragentning sof qoldig'i: musbat (Дт) → debitorka, manfiy (Кт) → kreditorka.
    'Kredit qarzdorlik' hisobidagi harakat alohida 'Kredit' toifasiga chiqariladi.
    Kontragentli hisoblar hozircha barchasi qisqa muddatli (Current) guruhlarda."""
    res = {"debitorka": [], "kreditorka": []}
    try:
        rows = frappe.db.sql(
            f"""SELECT ge.party_type, ge.party, ge.account_currency cur,
                       CASE WHEN a.account_name LIKE 'Kredit qarzdorlik%%' THEN 1 ELSE 0 END is_kredit,
                       IFNULL(SUM(ge.debit_in_account_currency - ge.credit_in_account_currency),0) bal
                FROM `tabGL Entry` ge JOIN `tabAccount` a ON a.name = ge.account
                WHERE ge.is_cancelled=0 AND ge.posting_date<=%(d)s
                  AND ge.party IS NOT NULL AND ge.party!='' {_co(company,'ge')}
                GROUP BY ge.party_type, ge.party, ge.account_currency, is_kredit""",
            {"d": date, "company": company}, as_dict=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: party_balance_cards")
        return res
    ptmap = {"Customer": "customer", "Student": "customer", "Employee": "employee",
             "Supplier": "supplier", "Shareholder": "shareholder"}
    deb = defaultdict(lambda: defaultdict(float))    # valyuta -> toifa -> summa
    cred = defaultdict(lambda: defaultdict(float))
    for r in rows:
        bal = flt(r.bal)
        if abs(bal) < 0.5:
            continue
        cat = "kredit" if r.is_kredit else ptmap.get(r.party_type, "other")
        cur = r.cur or "UZS"
        if bal > 0:
            deb[cur][cat] += bal
        else:
            cred[cur][cat] += -bal

    def pack(dd):
        out = []
        for cur, cats in dd.items():
            items = [{"key": k, "label": PARTY_CAT_LABELS.get(k, k), "amount": v}
                     for k, v in cats.items() if v > 0.5]
            items.sort(key=lambda x: -x["amount"])
            if items:
                out.append({"currency": cur, "total": sum(x["amount"] for x in items), "items": items})
        out.sort(key=lambda x: (x["currency"] != "UZS", x["currency"]))
        return out

    res["debitorka"] = pack(deb)
    res["kreditorka"] = pack(cred)
    return res


def _nat_key(s):
    """Tabiiy tartib: G1A, G2A, ..., G10B (alifboda G10 G1'dan oldin kelib qolmasligi uchun)."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


def _students_by_group():
    """Sinflar kesimida faol o'quvchilar soni — Student Group (active=1) asosida."""
    out = []
    if not _has("Student Group"):
        return out
    try:
        rows = frappe.db.sql(
            """SELECT sg.student_group_name label, COUNT(sgs.name) students
               FROM `tabStudent Group` sg
               JOIN `tabStudent Group Student` sgs ON sgs.parent = sg.name AND sgs.active = 1
               WHERE IFNULL(sg.disabled, 0) = 0
               GROUP BY sg.name, sg.student_group_name
               HAVING students > 0""", as_dict=True)
        out = [{"label": r.label, "students": int(r.students or 0)} for r in rows]
        out.sort(key=lambda x: _nat_key(x["label"]))
    except Exception:
        pass
    return out


def _cash_balance_card(company, date):
    """Xisobdagi pullar — sana holatiga, valyuta jami + har hisob kesimida."""
    accs = _cash_accounts(company)
    bals = _balance_upto(list(accs.keys()), date, company)
    by = defaultdict(lambda: {"total": 0.0, "items": []})
    for account in accs:
        bal = flt(bals.get(account, 0.0))
        cur = _acc_currency(account)
        b = by[cur]
        b["total"] += bal
        if abs(bal) > 0.5:
            b["items"].append({"label": account, "amount": bal})
    out = []
    for cur, v in by.items():
        v["items"].sort(key=lambda x: -x["amount"])
        out.append({"currency": cur, "total": v["total"], "items": v["items"]})
    out.sort(key=lambda x: (x["currency"] != "UZS", x["currency"]))
    return out


def _balance_card(company, date, ccy):
    """Balans — sana holatiga, kompaniya valyutasida. Aktiv/majburiyat/kapital jami,
    Working Capital (aylanma kapital), Debt-to-Equity va guruh kesimida taqsimot.
    Kapitalga to'plangan foyda (Income − Expense, boshidan) ham qo'shiladi —
    shunda Aktiv = Majburiyat + Kapital tengligi saqlanadi. Majburiyatga uzoq
    muddatlilar ham kiradi (hozircha hammasi Current guruhida)."""
    res = {"currency": ccy, "assets": 0.0, "liabilities": 0.0, "equity": 0.0,
           "current_assets": 0.0, "current_liabilities": 0.0, "long_term_liabilities": 0.0,
           "working_capital": None, "debt_to_equity": None,
           "asset_items": [], "liability_items": [], "equity_items": []}
    try:
        afilt = {"company": company} if company else {}
        accs = frappe.get_all("Account", filters=afilt,
                              fields=["name", "account_name", "root_type", "parent_account",
                                      "is_group", "lft", "rgt"])
        rows = frappe.db.sql(
            f"""SELECT account, IFNULL(SUM(debit - credit),0) bal
                FROM `tabGL Entry`
                WHERE is_cancelled=0 AND posting_date<=%(d)s {_co(company)}
                GROUP BY account""",
            {"d": date, "company": company}, as_dict=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: balance_card")
        return res

    amap = {a.name: a for a in accs}
    cur_asset_rng = [(g.lft, g.rgt) for g in accs
                     if g.is_group and "current assets" in (g.account_name or "").lower()]
    cur_liab_rng = [(g.lft, g.rgt) for g in accs
                    if g.is_group and "current liabilities" in (g.account_name or "").lower()]

    def in_rng(a, rng):
        return any(lo <= (a.lft or 0) <= hi for lo, hi in rng)

    profit = 0.0
    agg = {"Asset": defaultdict(float), "Liability": defaultdict(float), "Equity": defaultdict(float)}
    for r in rows:
        a = amap.get(r.account)
        if not a:
            continue
        bal = flt(r.bal)          # debet − kredit (kompaniya valyutasida)
        if a.root_type == "Asset":
            res["assets"] += bal
            if in_rng(a, cur_asset_rng):
                res["current_assets"] += bal
            parent = amap.get(a.parent_account)
            label = (parent.account_name if parent else "") or a.account_name or r.account
            agg["Asset"][label] += bal
        elif a.root_type == "Liability":
            res["liabilities"] += -bal
            if in_rng(a, cur_liab_rng):
                res["current_liabilities"] += -bal
            parent = amap.get(a.parent_account)
            label = (parent.account_name if parent else "") or a.account_name or r.account
            agg["Liability"][label] += -bal
        elif a.root_type == "Equity":
            res["equity"] += -bal
            agg["Equity"][a.account_name or r.account] += -bal
        else:  # Income/Expense — to'plangan foyda: Income kredit (+), Expense debet (−)
            profit -= bal

    res["equity"] += profit
    if abs(profit) > 0.5:
        agg["Equity"]["To'plangan foyda (P&L)"] = profit
    if cur_asset_rng and cur_liab_rng:
        res["working_capital"] = res["current_assets"] - res["current_liabilities"]
    res["long_term_liabilities"] = res["liabilities"] - res["current_liabilities"] if cur_liab_rng else 0.0
    if abs(res["equity"]) > 0.5:
        res["debt_to_equity"] = round(res["liabilities"] / res["equity"], 2)

    def pack(dd):
        items = [{"label": k, "amount": v} for k, v in dd.items() if abs(v) > 0.5]
        items.sort(key=lambda x: -abs(x["amount"]))
        return items

    res["asset_items"] = pack(agg["Asset"])
    res["liability_items"] = pack(agg["Liability"])
    res["equity_items"] = pack(agg["Equity"])
    return res


def _overview_cards(company, to_date, ccy):
    pb = _party_balance_cards(company, to_date)
    return {
        "as_of": str(to_date),
        "debitorka": pb["debitorka"],
        "kreditorka": pb["kreditorka"],
        "students_by_group": _students_by_group(),
        "cash": _cash_balance_card(company, to_date),
        "balance": _balance_card(company, to_date, ccy),
    }


# ===========================================================================
# Asosiy API
# ===========================================================================
ALLOWED_ROLES = ["System Manager", "Accounts Manager", "Accounts User", "investor", "Xojakbar_Operator"]


def _guard():
    """Rolni harf ko'rinishiga befarq (case-insensitive) tekshirish."""
    allowed = {r.lower() for r in ALLOWED_ROLES}
    user_roles = {r.lower() for r in frappe.get_roles()}
    if not (allowed & user_roles):
        frappe.throw(
            "Ruxsat yo'q. Investor paneli uchun 'investor' roli kerak.",
            frappe.PermissionError,
        )


def _fmt_date(d):
    return getdate(d).strftime("%d.%m.%Y")


def _resolve_range(from_date, to_date):
    tdy = getdate(today())
    t0 = getdate(to_date) if to_date else tdy
    f0 = getdate(from_date) if from_date else get_first_day(t0)
    if f0 > t0:
        f0, t0 = t0, f0
    return f0, t0, tdy


@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None):
    _guard()

    f0, t0, tdy = _resolve_range(from_date, to_date)
    length = (t0 - f0).days
    pt = add_days(f0, -1)                 # oldingi teng oraliq
    pf = add_days(pt, -length)
    yf = getdate(add_months(f0, -12))     # o'tgan yil shu oraliq
    yt = getdate(add_months(t0, -12))
    is_future = f0 > tdy

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
        cash = {"accounts": [], "total": {"opening": 0, "kirim": 0, "chiqim": 0, "closing": 0}, "other": [], "by_currency": [], "main_accounts": []}
    main_accounts = cash["main_accounts"]
    cash_now = cash["total"]["closing"]
    cash_prev = sum(_balance_upto(main_accounts, pt, company).values())
    cash_yoy = sum(_balance_upto(main_accounts, yt, company).values())

    flow = _monthly_flow(main_accounts, company, t0, 12)
    all_cash = [a["account"] for a in cash["accounts"]]
    acc_ccy = {a["account"]: a["currency"] for a in cash["accounts"]}
    cat = _cashflow_by_category(all_cash, set(main_accounts), acc_ccy, ccy, company, f0, t0,
                                pure_vouchers=cash.get("pure_transfer_vouchers"))
    budget = _budget_split(company, f0, t0, ccy)

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
    tuition = _tuition_section(company, f0, t0)

    # ---- Umumiy tab kartalari (mockup: taqsimotli 5 karta + balans) ----
    try:
        cards = _overview_cards(company, t0, ccy)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: overview_cards")
        cards = {}

    if not main_accounts:
        warnings.append("Kassa hisoblari topilmadi (Mode of Payment Account sozlanmagan).")
    if not flags["has_fees"]:
        warnings.append("Education Fees ma'lumoti yo'q — o'quvchi to'lov bo'limi cheklangan.")
    if is_future:
        warnings.append("Tanlangan oraliq kelajakda — ba'zi ko'rsatkichlar hali to'lmagan.")

    return {
        "meta": {
            "company": company, "currency": ccy,
            "period": {"label": f"{_fmt_date(f0)} — {_fmt_date(t0)}",
                       "from": str(f0), "to": str(t0), "days": length + 1},
            "prev_label": f"{_fmt_date(pf)} — {_fmt_date(pt)}",
            "yoy_label": "o'tgan yil",
            "is_future": is_future, "flags": flags, "warnings": warnings,
        },
        "overview": {
            "cash_accounts": [{"account": a["account"], "mode": a["mode"],
                               "currency": a["currency"], "closing": a["closing"]}
                              for a in cash["accounts"]],
            "cash_total": _cmp(cash_now, cash_prev), "cash_yoy": _cmp(cash_now, cash_yoy),
            "expense": _cmp(pnl_cur["expense"], pnl_prev["expense"]),
            "receivable": _cmp(rec_now, rec_prev), "payable": _cmp(pay_now, pay_prev),
            "active_students": tuition["active"],
            "contracted_students": tuition["contracted"],
            "collection_rate": tuition["rate"],
            "cards": cards,
        },
        "cashflow": {
            "accounts": cash["accounts"], "total": cash["total"], "other": cash["other"],
            "by_currency": cash.get("by_currency", []),
            "categories": cat, "monthly": flow, "budget": budget,
            "daily": _daily_collection(main_accounts, company, t0),
        },
        "pnl": {
            "current": pnl_cur, "prev": pnl_prev, "yoy": pnl_yoy,
            "income_cmp": _cmp(pnl_cur["income"], pnl_prev["income"]), "income_yoy": _cmp(pnl_cur["income"], pnl_yoy["income"]),
            "expense_cmp": _cmp(pnl_cur["expense"], pnl_prev["expense"]), "expense_yoy": _cmp(pnl_cur["expense"], pnl_yoy["expense"]),
            "net_cmp": _cmp(pnl_cur["net"], pnl_prev["net"]), "net_yoy": _cmp(pnl_cur["net"], pnl_yoy["net"]),
            "expense_breakdown": _expense_breakdown(company, f0, t0, ccy, pf, pt),
            "monthly": _monthly_pnl(company, t0, ccy, 12),
        },
        "debts": {
            "receivable_total": rec_now, "receivable_cmp": _cmp(rec_now, rec_prev),
            "payable_total": pay_now, "payable_cmp": _cmp(pay_now, pay_prev),
            "employee": emp,
        },
        "tuition": tuition,
    }


# ===========================================================================
# Kontragent otchot (debts bo'limi jadvali) — GL Entry asosida, davr kesimida
# ===========================================================================
KONTRAGENT_TYPES = ["Customer", "Supplier", "Employee", "Shareholder", "Student"]


@frappe.whitelist()
def get_kontragent(from_date=None, to_date=None, party_type=None, party=None, currency=None, party_group=None):
    """Kontragent bo'yicha: boshlang'ich qoldiq → davr harakati (kredit/debet) → yakuniy qoldiq."""
    _guard()
    f0, t0, _ = _resolve_range(from_date, to_date)
    company = _default_company()

    conds = ["ge.is_cancelled=0", "ge.party IS NOT NULL", "ge.party!=''",
             "ge.party_type IS NOT NULL", "ge.party_type!=''", "ge.posting_date<=%(t)s"]
    vals = {"f": str(f0), "t": str(t0)}
    if party_type:
        conds.append("ge.party_type=%(pt)s")
        vals["pt"] = party_type
    if party:
        conds.append("ge.party=%(p)s")
        vals["p"] = party
    if currency:
        conds.append("ge.account_currency=%(cur)s")
        vals["cur"] = currency
    if company:
        conds.append("ge.company=%(company)s")
        vals["company"] = company
    where = " AND ".join(conds)

    try:
        rows = frappe.db.sql(
            f"""SELECT ge.party_type, ge.party, ge.account_currency cur,
                   IFNULL(SUM(CASE WHEN ge.posting_date < %(f)s
                        THEN ge.credit_in_account_currency - ge.debit_in_account_currency ELSE 0 END),0) opening_net,
                   IFNULL(SUM(CASE WHEN ge.posting_date >= %(f)s
                        THEN ge.credit_in_account_currency ELSE 0 END),0) p_credit,
                   IFNULL(SUM(CASE WHEN ge.posting_date >= %(f)s
                        THEN ge.debit_in_account_currency ELSE 0 END),0) p_debit
                FROM `tabGL Entry` ge
                WHERE {where}
                GROUP BY ge.party_type, ge.party, ge.account_currency""",
            vals, as_dict=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: kontragent")
        rows = []

    keys = ("opening_credit", "opening_debit", "period_credit", "period_debit", "final_credit", "final_debit")
    tmp = []
    for r in rows:
        op = flt(r.opening_net)
        pc, pd = flt(r.p_credit), flt(r.p_debit)
        if abs(op) < 0.5 and pc < 0.5 and pd < 0.5:
            continue  # harakatsiz kontragentni ko'rsatmaymiz
        fin = op + pc - pd
        cur = r.cur or "UZS"
        row = {
            "party_type": r.party_type, "party": r.party,
            "name": _party_name(r.party_type, r.party), "currency": cur,
            "opening_credit": op if op > 0 else 0.0, "opening_debit": -op if op < 0 else 0.0,
            "period_credit": flt(r.p_credit), "period_debit": flt(r.p_debit),
            "final_credit": fin if fin > 0 else 0.0, "final_debit": -fin if fin < 0 else 0.0,
        }
        row["_move"] = pc + pd
        tmp.append(row)

    # kontragent guruhini to'plamli aniqlab, guruh filtri bo'lsa qo'llaymiz
    gmap = _party_groups_map(tmp)
    data = []
    tbc = defaultdict(lambda: defaultdict(float))
    for row in tmp:
        grp = gmap.get((row["party_type"], row["party"]), "")
        if party_group and grp != party_group:
            continue
        row["party_group"] = grp
        data.append(row)
        cur = row["currency"]
        for k in keys:
            tbc[cur][k] += row[k]

    data.sort(key=lambda x: -x["_move"])
    data = data[:500]
    for row in data:
        row.pop("_move", None)

    totals = [dict(currency=c, **{k: v[k] for k in keys}) for c, v in tbc.items()]
    totals.sort(key=lambda x: x["currency"])
    return {"rows": data, "totals": totals,
            "period": {"from": str(f0), "to": str(t0),
                       "label": f"{_fmt_date(f0)} — {_fmt_date(t0)}"},
            "party_types": KONTRAGENT_TYPES}


@frappe.whitelist()
def get_kontragent_parties(party_type=None):
    """Tanlangan tur bo'yicha kontragentlar ro'yxati (filter select uchun)."""
    _guard()
    if not party_type:
        return []
    company = _default_company()
    conds = ["party_type=%(pt)s", "party IS NOT NULL", "party!=''", "is_cancelled=0"]
    vals = {"pt": party_type}
    if company:
        conds.append("company=%(company)s")
        vals["company"] = company
    try:
        rows = frappe.db.sql(
            f"SELECT DISTINCT party FROM `tabGL Entry` WHERE {' AND '.join(conds)} ORDER BY party LIMIT 1000",
            vals, as_dict=True)
    except Exception:
        rows = []
    return [{"value": r.party, "label": _party_name(party_type, r.party)} for r in rows]


DDS_CATEGORY_ORDER = [
    ("customer", "Покупатели"),
    ("supplier", "Поставщики"),
    ("shareholder", "Учредители"),
    ("dividend", "Дивиденды"),
    ("employee", "Сотрудники"),
    ("transfer", "Перемещения"),
    ("other", "Прочие"),
    ("expense", "Расходы"),
]


@frappe.whitelist()
def get_dds(from_date=None, to_date=None, mode_of_payment=None, party_type=None, party=None, category=None):
    """DDS (pul oqimi) hisoboti — kassa hisoblari bo'yicha boshlang'ich qoldiq →
    kategoriyalar kesimida kirim/chiqim → yakuniy qoldiq + harakatlar ro'yxati.
    DDS reportining o'z get_data() mantig'i qayta ishlatiladi (raqamlar aynan mos)."""
    _guard()
    f0, t0, _ = _resolve_range(from_date, to_date)
    from target_zenit.target_zenit.report.dds import dds as _dds

    filters = {"from_date": str(f0), "to_date": str(t0)}
    if mode_of_payment:
        filters["mode_of_payment"] = mode_of_payment
    if party_type:
        filters["party_type"] = party_type
    if party:
        filters["party"] = party
    if category:
        filters["category"] = category

    try:
        data, expense_summaries, dividend_summaries = _dds.get_data(filters)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "investor_dashboard: dds")
        data, expense_summaries, dividend_summaries = [], {}, {}

    opening = 0.0
    closing = 0.0
    cat_tot = {k: {"kirim": 0.0, "chiqim": 0.0} for k, _ in DDS_CATEGORY_ORDER}
    tx = []
    for row in data:
        if "_opening_balance" in row:
            opening = flt(row["_opening_balance"])
        if "_closing_balance" in row:
            closing = flt(row["_closing_balance"])
        cat = row.get("category") or "other"
        if cat not in cat_tot:
            cat = "other"
        k = flt(row.get("kirim"))
        c = flt(row.get("chiqim"))
        cat_tot[cat]["kirim"] += k
        cat_tot[cat]["chiqim"] += c
        tx.append({
            "date": str(row.get("posting_date") or ""),
            "account": row.get("account") or "",
            "category": row.get("category") or "other",
            "category_label": _dds.CATEGORY_LABELS.get(row.get("category") or "other", "Прочие"),
            "description": row.get("description") or "",
            "kirim": k, "chiqim": c,
            "remarks": row.get("remarks") or "",
            "voucher_type": row.get("voucher_type") or "",
            "voucher_no": row.get("voucher_no") or "",
        })

    if not data:
        closing = opening

    # eng oxirgi (yangi) submit qilingan transaksiyalar tepada bo'lsin:
    # get_data() posting_date, creation bo'yicha o'sish tartibida beradi → teskari qilamiz.
    tx.reverse()

    categories = []
    for k, label in DDS_CATEGORY_ORDER:
        t = cat_tot[k]
        if abs(t["kirim"]) > 0.005 or abs(t["chiqim"]) > 0.005:
            categories.append({"key": k, "label": label,
                               "kirim": t["kirim"], "chiqim": t["chiqim"]})

    total_kirim = sum(t["kirim"] for t in cat_tot.values())
    total_chiqim = sum(t["chiqim"] for t in cat_tot.values())

    expense_bd = [{
        "label": (kk[len("Расходы: "):] if kk.startswith("Расходы: ") else kk),
        "kirim": flt(v["kirim"]), "chiqim": flt(v["chiqim"]),
    } for kk, v in expense_summaries.items()]
    expense_bd.sort(key=lambda x: -(x["kirim"] + x["chiqim"]))

    dividend_bd = [{
        "label": kk, "kirim": flt(v["kirim"]), "chiqim": flt(v["chiqim"]),
    } for kk, v in dividend_summaries.items()]
    dividend_bd.sort(key=lambda x: -(x["kirim"] + x["chiqim"]))

    try:
        modes = [m.name for m in frappe.get_all("Mode of Payment", fields=["name"], order_by="name")]
    except Exception:
        modes = []

    return {
        "opening": opening, "closing": closing,
        "total_kirim": total_kirim, "total_chiqim": total_chiqim,
        "categories": categories,
        "expense_breakdown": expense_bd,
        "dividend_breakdown": dividend_bd,
        "transactions": tx[:800],
        "tx_count": len(tx),
        "modes": modes,
        "period": {"from": str(f0), "to": str(t0),
                   "label": f"{_fmt_date(f0)} — {_fmt_date(t0)}"},
    }


@frappe.whitelist()
def get_kontragent_groups(party_type=None):
    """Kontragent guruhlari ro'yxati (filter select uchun). Customer->Customer Group,
    Supplier->Supplier Group. Boshqa turlar uchun guruh tushunchasi yo'q."""
    _guard()
    groups = set()
    try:
        if not party_type or party_type == "Customer":
            for r in frappe.get_all("Customer", fields=["distinct customer_group as g"]):
                if r.g:
                    groups.add(r.g)
        if not party_type or party_type == "Supplier":
            for r in frappe.get_all("Supplier", fields=["distinct supplier_group as g"]):
                if r.g:
                    groups.add(r.g)
    except Exception:
        pass
    return sorted(groups)
