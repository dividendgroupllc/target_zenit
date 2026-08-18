"""
target_zenit/api/balance_pdf_api.py
===================================
Balance Sheet PDF — armada'dagi bilan bir xil logika:
  1. ERPNext balance_sheet.execute() → kumulyativ qoldiqlar (oyma-oy)
  2. Hisob-based bo'limlar hisoblar daraxtidan DINAMIK yig'iladi:
       Активы  : Основные средства (1700), Запасы (1400),
                 Денежные средства (1100+1200), Прочие активы (qolganlari)
       Пассивы : Капитал (3000), Обязательства (2000, AP'dan tashqari)
  3. Kontragent qatorlari (Дебиторская/Кредиторская) hisob qoldig'idan EMAS,
     har kontragent bo'yicha NETTO hisoblanadi (armada usuli):
       netto debet → aktiv qator, netto kredit → passiv qator.
     Shu sabab AR (1300), Employee Advances (1610) va AP (2100) subtree'lari
     hisob-based bo'limlarga KIRITILMAYDI (ikki marta sanalmasin).
  4. Прибыль текущего периода va Дивиденды — oylik OQIM sifatida, Прибыль
     прошлых периодов esa balansga bog'lab tuzatiladi, shunda har ustunda
     Капитал = Активы − Обязательства (Разница = 0).

Debug:
  bench --site target.local execute \
      target_zenit.target_zenit.api.balance_pdf_api.debug_accounts
"""

import json

import frappe

from target_zenit.target_zenit.api.report_common import (
    account_values,
    extract_values,
    find_group,
    get_accounts,
    get_company_abbr,
    leaves_under,
    normalize_filters,
    save_private_file,
    strip_abbr,
)

DEFAULT_COMPANY = "Target Zenit"
MAX_COLS = 12

PROVISIONAL_KEY = "'Provisional Profit / Loss (Credit)'"

# Kontragent qatorlari (armada shablonidagi AYNAN shu labellar)
PARTY_DEBIT_LABEL = {
    "Customer": "Задолженность клиентов",
    "Supplier": "Выданные авансы поставщикам",
    "Employee": "Задолженность сотр-в",
}
PARTY_CREDIT_LABEL = {
    "Customer": "Полученные авансы от клиентов",
    "Supplier": "Задолженность перед поставщиками",
    "Employee": "Задолженность перед сотрудниками",
}

# Standart hisob nomlari uchun ruscha ko'rinish (armada formati);
# maxsus (o'zbekcha) hisoblar o'z nomi bilan chiqadi
LABEL_RU = {
    "Capital Stock":                "Уставный капитал",
    "Opening Balance Equity":       "Входящий баланс (Opening)",
    "Temporary Opening":            "Временный (Opening)",
    "Office Equipments":            "Офисное оборудование",
    "Electronic Equipments":        "Электроника",
    "Furnitures and Fixtures":      "Мебель",
    "Capital Equipments":           "Капитальное оборудование",
    "Plants and Machineries":       "Оборудование",
    "Buildings":                    "Здания",
    "Softwares":                    "Программы",
    "Accumulated Depreciation":     "Накопленная амортизация",
    "CWIP Account":                 "Незавершённое строительство",
    "Earnest Money":                "Задаток",
    "Secured Loans":                "Кредиты банков",
    "Unsecured Loans":              "Займы",
    "Bank Overdraft Account":       "Овердрафт",
    "TDS Payable":                  "Задолженность по налогам и сборам",
    "VAT":                          "НДС (VAT)",
    "Stock Received But Not Billed": "Товары получены, не выставлен счёт",
    "Asset Received But Not Billed": "Активы получены, не выставлен счёт",
}

_MONTH_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _column_end_dates(col_keys, period_end_date):
    """col_key ('jul_2026') → shu ustunning oxirgi sanasi (oy oxiri,
    period_end bilan cheklangan)."""
    import calendar
    from datetime import date

    from frappe.utils import getdate

    period_end = getdate(period_end_date)
    ends = []
    for ck in col_keys:
        parts = str(ck).split("_")
        mon = _MONTH_NUM.get(parts[0].lower())
        if mon and len(parts) > 1 and parts[1].isdigit():
            year = int(parts[1])
            month_end = date(year, mon, calendar.monthrange(year, mon)[1])
            ends.append(min(month_end, period_end))
        else:
            ends.append(period_end)
    return ends


def _party_balances(company, col_keys, period_end_date):
    """Har (party_type, party) bo'yicha barcha hisoblardagi netto qoldiq
    (debet − kredit) har ustun oxiriga hisoblanadi; musbat → aktiv qator,
    manfiy → passiv qatorga yig'iladi."""
    from collections import defaultdict

    from frappe.utils import flt

    ends = _column_end_dates(col_keys, period_end_date)
    debit = {pt: [0.0] * len(ends) for pt in PARTY_DEBIT_LABEL}
    credit = {pt: [0.0] * len(ends) for pt in PARTY_CREDIT_LABEL}
    if not ends:
        return debit, credit

    rows = frappe.db.sql(
        """
        SELECT
            party_type,
            party,
            YEAR(posting_date)  AS yr,
            MONTH(posting_date) AS mo,
            SUM(debit - credit) AS net
        FROM `tabGL Entry`
        WHERE
            is_cancelled = 0
            AND company = %(company)s
            AND party_type IN ('Customer', 'Supplier', 'Employee')
            AND party IS NOT NULL AND party != ''
            AND posting_date <= %(last_date)s
        GROUP BY party_type, party, YEAR(posting_date), MONTH(posting_date)
        """,
        {"company": company, "last_date": ends[-1]},
        as_dict=True,
    )

    per_party = defaultdict(lambda: defaultdict(float))
    for r in rows:
        per_party[(r.party_type, r.party)][(int(r.yr), int(r.mo))] += flt(r.net)

    for (party_type, _party), months in per_party.items():
        for i, end in enumerate(ends):
            bal = sum(v for (y, m), v in months.items()
                      if (y, m) <= (end.year, end.month))
            if bal > 0:
                debit[party_type][i] += bal
            elif bal < 0:
                credit[party_type][i] += -bal

    return debit, credit


@frappe.whitelist()
def generate_balance_pdf(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    normalized = normalize_filters(filters, accumulated_default=1)
    # Balans doim kumulyativ qoldiq bilan ishlaydi
    normalized["accumulated_values"] = 1
    company = normalized.get("company") or DEFAULT_COMPANY
    abbr = get_company_abbr(company)

    bs_execute = frappe.get_attr(
        "erpnext.accounts.report.balance_sheet.balance_sheet.execute"
    )
    columns, rows, *_ = bs_execute(frappe._dict(normalized))

    skip_fields = {
        "account", "currency", "total", "account_name",
        "indent", "parent_account", "is_group", "has_value",
        "account_type", "opening_balance", "include_in_gross",
        "year_start_date", "year_end_date",
    }
    col_keys = [
        c["fieldname"] for c in columns
        if c["fieldname"] not in skip_fields
        and c.get("fieldtype") == "Currency"
        and c["fieldname"] != "total"
    ][:MAX_COLS]
    n_cols = len(col_keys)

    vals = extract_values(rows, col_keys, abbr)

    # Oylik oqim (kumulyativ emas) — Прибыль текущего / Дивиденды uchun
    monthly_filters = dict(normalized)
    monthly_filters["accumulated_values"] = 0
    _, monthly_rows, *_ = bs_execute(frappe._dict(monthly_filters))
    monthly_vals = extract_values(monthly_rows, col_keys, abbr)

    # ── Hisoblar daraxti ─────────────────────────────────────────────────
    accounts = get_accounts(company)

    fixed_grp = find_group(accounts, account_number="1700")
    stock_grp = find_group(accounts, account_number="1400")
    cash_grp = find_group(accounts, account_number="1100")
    bank_grp = find_group(accounts, account_number="1200")
    ar_grp = find_group(accounts, account_number="1300")
    ap_grp = find_group(accounts, account_number="2100")
    equity_grp = find_group(accounts, account_number="3000")

    def _leaves(grp):
        return leaves_under(accounts, grp)

    def _rows_of(leaves, skip_zero=True, source=None):
        src = source or vals
        out = []
        for acc in leaves:
            values = account_values(src, acc, abbr, n_cols)
            if skip_zero and not any(values):
                continue
            label = LABEL_RU.get(acc.account_name, acc.account_name)
            out.append((label, values))
        return out

    used = set()
    for grp in (fixed_grp, stock_grp, cash_grp, bank_grp, ar_grp):
        for a in _leaves(grp):
            used.add(a.name)

    # Employee Advances (1610) — kontragent netto qatori qoplaydi
    emp_adv = [a for a in accounts
               if not a.is_group and str(a.account_number or "") == "1610"]
    for a in emp_adv:
        used.add(a.name)

    other_asset_leaves = [
        a for a in accounts
        if not a.is_group and a.root_type == "Asset" and a.name not in used
    ]

    # ── Kontragent qatorlari ─────────────────────────────────────────────
    party_debit, party_credit = _party_balances(
        company, col_keys, normalized.get("period_end_date"))

    debit_rows = [(PARTY_DEBIT_LABEL[pt], party_debit[pt])
                  for pt in ("Customer", "Supplier", "Employee")]
    credit_rows = [(PARTY_CREDIT_LABEL[pt], party_credit[pt])
                   for pt in ("Customer", "Supplier", "Employee")]

    # ── Капитал: oylik oqim + tuzatilgan «прошлых периодов» ──────────────
    def _get(key, src):
        v = src.get(key)
        return (list(v) + [0.0] * n_cols)[:n_cols] if v else [0.0] * n_cols

    equity_leaves = _leaves(equity_grp)

    def _find_acc(number):
        for a in equity_leaves:
            if str(a.account_number or "") == number:
                return a
        return None

    re_acc_doc = _find_acc("3400")       # Retained Earnings
    div_doc = _find_acc("3200")          # Dividends Paid

    re_key = strip_abbr(re_acc_doc.name, abbr) if re_acc_doc else None
    div_key = strip_abbr(div_doc.name, abbr) if div_doc else None

    re_cum = _get(re_key, vals) if re_key else [0.0] * n_cols
    tek_cum = _get(PROVISIONAL_KEY, vals)
    div_cum = _get(div_key, vals) if div_key else [0.0] * n_cols

    tek_m = _get(PROVISIONAL_KEY, monthly_vals)
    div_m = _get(div_key, monthly_vals) if div_key else [0.0] * n_cols

    # Балансга bog'langan qoldiq: RE + kumulyativ foyda + kumulyativ
    # dividend − PDF'da alohida ko'rsatiladigan joriy oy oqimlari
    pribyl_proshlyh = [
        re_cum[i] + tek_cum[i] + div_cum[i] - tek_m[i] - div_m[i]
        for i in range(n_cols)
    ]

    # Kapital qatorlari — armada tuzilishida:
    #   Уставный капитал / ... / Накопленная прибыль/убыток: (label) /
    #   — прошлых периодов (kursiv) / — текущих периодов (kursiv) / Дивиденды
    kapital_rows = [
        (label, vals, "data")
        for label, vals in _rows_of(
            [a for a in equity_leaves if a not in (re_acc_doc, div_doc)])
    ]
    kapital_rows.append(("Накопленная прибыль/убыток:", None, "label_only"))
    kapital_rows.append(("— прошлых периодов", pribyl_proshlyh, "italic_data"))
    kapital_rows.append(("— текущих периодов", tek_m, "italic_data"))
    kapital_rows.append(("Дивиденды", div_m, "data"))

    # ── Обязательства (AP subtree'siz — kontragent qatorlari qoplaydi) ───
    ap_leaves = {a.name for a in _leaves(ap_grp)}
    liab_leaves = [
        a for a in accounts
        if not a.is_group and a.root_type == "Liability"
        and a.name not in ap_leaves
    ]
    kred_zadolzh_rows = credit_rows + _rows_of(liab_leaves)

    # ── Payload ──────────────────────────────────────────────────────────
    payload = {
        "asset_groups": [
            {"label": "Внеоборотные активы", "sections": [
                {"label": "Основные средства",
                 "rows": _rows_of(_leaves(fixed_grp))},
            ]},
            {"label": "Оборотные активы", "sections": [
                {"label": "Запасы", "rows": _rows_of(_leaves(stock_grp))},
                {"label": "Денежные средства",
                 "rows": _rows_of(_leaves(cash_grp) + _leaves(bank_grp))},
                {"label": "Дебиторская задолж-ть", "rows": debit_rows},
                {"label": "Прочие активы",
                 "rows": _rows_of(other_asset_leaves)},
            ]},
        ],
        "equity_rows": kapital_rows,
        "liab_sections": [
            {"label": "Кредиторская задолженность",
             "rows": kred_zadolzh_rows},
        ],
    }

    from target_zenit.target_zenit.pdf_engine.balance_pdf import generate

    start = (normalized.get("period_start_date") or "")[:7]
    end = (normalized.get("period_end_date") or "")[:7]
    safe_co = company.replace(" ", "_")
    filename = f"BS_{safe_co}_{start}_to_{end}.pdf"

    output_path = generate(
        payload, filename, col_keys=col_keys,
        company=company,
        period_label=f"{start} — {end}" if start else "",
    )

    file_url = save_private_file(output_path, filename)
    return {"file_url": file_url, "file_name": filename}


# ─── DEBUG ───────────────────────────────────────────────────────────────────

def debug_accounts(company=DEFAULT_COMPANY):
    accounts = get_accounts(company)
    for num, title in [("1700", "Основные средства"), ("1400", "Запасы"),
                       ("1100", "Наличные"), ("1200", "Банк"),
                       ("3000", "Капитал")]:
        grp = find_group(accounts, account_number=num)
        print(f"\n=== {title} ({num}) ===")
        for a in leaves_under(accounts, grp):
            print(f"  {a.account_number or '----'}  {a.account_name}")
