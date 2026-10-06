"""
target_zenit/api/pl_pdf_api.py
==============================
Profit & Loss PDF — armada'dagi bilan bir xil logika:
  1. ERPNext profit_and_loss_statement.execute() → oylik qiymatlar
  2. Hisoblar daraxtidan bo'limlar DINAMIK yig'iladi (yangi hisob
     qo'shilsa kod o'zgartirish shart emas):
       - Выручка          → Income leaflari (4110 Sales, 4120 Service, ...)
       - Себестоимость    → Direct Expenses (5100) leaflari
       - Опер. расходы    → Indirect Expenses (5200) leaflari
  3. pdf_engine/pl_pdf.generate() → PDF → private File → { file_url }

Debug (hisoblar ro'yxati):
  bench --site target.local execute \
      target_zenit.target_zenit.api.pl_pdf_api.debug_accounts
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
)

DEFAULT_COMPANY = "Target Zenit"
MAX_COLS = 12

# Standart (inglizcha) hisob nomlari uchun ruscha ko'rinish — armada
# formati; maxsus (o'zbekcha) hisoblar o'z nomi bilan chiqadi
LABEL_RU = {
    "Sales":                      "Выручка от реализации",
    "Service":                    "Выручка от услуг",
    "Cost of Goods Sold":         "Сырьевая себестоимость",
    "Stock Adjustment":           "Корректировка склада",
    "Expenses Included In Asset Valuation": "Расходы в оценке активов",
    "Expenses Included In Valuation":       "Расходы в оценке",
    "Travel Expenses":            "Командировочные",
    "Utility Expenses":           "Коммунальные услуги",
    "Write Off":                  "Списание",
    "Exchange Gain/Loss":         "Курсовая разница",
    "Gain/Loss on Asset Disposal": "Выбытие активов",
    "Miscellaneous Expenses":     "Прочие",
}


def _section_rows(leaves, vals, abbr, n_cols, skip_zero=True):
    """Leaf hisoblar → [(label, values)]; hammasi nol bo'lgan qatorlar
    tashlab yuboriladi (ishlatilmagan standart hisoblar chiqmasin)."""
    out = []
    for acc in leaves:
        values = account_values(vals, acc, abbr, n_cols)
        if skip_zero and not any(values):
            continue
        label = LABEL_RU.get(acc.account_name, acc.account_name)
        out.append((label, values))
    return out


# PDF'da BITTA qator ostida JAMLANADIGAN hisob guruhlari (buxgalteriya
# talabi). Nomlar qisman, kichik harfda solishtiriladi — hisob nomi sal
# o'zgarsa ham ("Bank foiz"/"Bank foize") ushlab qolsin. Guruh qatorlari
# opex ro'yxatining ENG OXIRIDA, shu tartibda chiqadi.
JAMLAMA_GURUHLAR = [
    (("exchange gain/loss", "bank foiz", "bank komissiya", "valyuta farqi"),
     "Курсовая разница и банковские расходы"),
    # Kommunal xarajatlar: "Kommunal (elektr, gaz, suv, chiqindi)" +
    # "Kamunalka musir" + "Kamunalka kanalizatsiya" — ikki xil imlo
    # ("kamunal"/"kommunal") ikkalasi ham ushlanadi.
    (("kamunal", "kommunal"),
     "Kommunal xarajatlar"),
    # Soliqlar: Boshqa soliqlar + Ijtimoiy soliq + Pensiya jamg'arma +
    # Soliqlar (band qilish) + Daromad soliq. "pensiya jamg" — apostrof
    # variantlaridan ta'sirlanmasin. Guruh ro'yxatning ENG OXIRIDA turadi.
    (("boshqa soliq", "ijtimoiy soliq", "pensiya jamg", "band qilish",
      "daromad soliq"),
     "Soliqlar"),
]


def _jamlama_idx(account_name):
    """Hisob qaysi jamlama guruhga tegishli (hech biriga bo'lmasa None)."""
    n = (account_name or "").strip().lower()
    for i, (kalitlar, _lbl) in enumerate(JAMLAMA_GURUHLAR):
        if any(k in n for k in kalitlar):
            return i
    return None


def _merge_jamlama(leaves, vals, abbr, n_cols):
    """Opex leaflarini ikkiga ajratadi: (oddiy_qatorlar, guruhlar).

    Guruh PDF'da KATEGORIYA bo'lib chiqadi: bold sarlavha (guruh jami
    bilan) + ichida har bir hisob ALOHIDA qator — nimadan tashkil
    topgani ko'rinib turadi."""
    qolgan = []
    azolar = [[] for _ in JAMLAMA_GURUHLAR]
    for acc in leaves:
        gi = _jamlama_idx(acc.account_name)
        if gi is None:
            qolgan.append(acc)
        else:
            azolar[gi].append(acc)
    rows = _section_rows(qolgan, vals, abbr, n_cols)
    groups = []
    for gi, (_kalitlar, label) in enumerate(JAMLAMA_GURUHLAR):
        g_rows = _section_rows(azolar[gi], vals, abbr, n_cols)  # nol a'zolar tushib qoladi
        if not g_rows:
            continue
        jami = [sum(r[1][i] for r in g_rows) for i in range(n_cols)]
        groups.append({"label": label, "jami": jami, "rows": g_rows})
    return rows, groups


@frappe.whitelist()
def generate_pl_pdf(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    normalized = normalize_filters(filters, accumulated_default=0)
    company = normalized.get("company") or DEFAULT_COMPANY
    abbr = get_company_abbr(company)

    execute = frappe.get_attr(
        "erpnext.accounts.report.profit_and_loss_statement"
        ".profit_and_loss_statement.execute"
    )
    columns, rows, *_ = execute(frappe._dict(normalized))

    skip = {"account", "currency", "total", "account_name",
            "indent", "parent_account", "is_group", "has_value",
            "account_type", "opening_balance", "include_in_gross",
            "year_start_date", "year_end_date"}
    col_keys = [
        c["fieldname"] for c in columns
        if c["fieldname"] not in skip
        and c.get("fieldtype") == "Currency"
        and c["fieldname"] != "total"
    ][:MAX_COLS]
    n_cols = len(col_keys)

    vals = extract_values(rows, col_keys, abbr)
    accounts = get_accounts(company)

    income_root = find_group(accounts, root_type="Income")
    direct_grp = find_group(accounts, account_number="5100")
    indirect_grp = find_group(accounts, account_number="5200")

    revenue_rows = _section_rows(
        leaves_under(accounts, income_root), vals, abbr, n_cols)
    cogs_rows = _section_rows(
        leaves_under(accounts, direct_grp), vals, abbr, n_cols)

    if indirect_grp:
        opex_leaves = leaves_under(accounts, indirect_grp)
    else:
        # Fallback: Direct'ga kirmagan barcha Expense leaflari
        direct_names = {a.name for a in leaves_under(accounts, direct_grp)}
        opex_leaves = [a for a in accounts
                       if not a.is_group and a.root_type == "Expense"
                       and a.name not in direct_names]
    # Jamlama guruhlar (kurs farqi+bank; soliqlar) — ro'yxat oxirida
    # kategoriya bo'lib chiqadi: sarlavha (jami) + a'zo hisoblar alohida
    opex_rows, opex_groups = _merge_jamlama(opex_leaves, vals, abbr, n_cols)

    payload = {
        "revenue_rows": revenue_rows,
        "cogs_rows":    cogs_rows,
        "opex_rows":    opex_rows,
        "opex_groups":  opex_groups,
    }

    from target_zenit.target_zenit.pdf_engine.pl_pdf import generate

    start = (normalized.get("period_start_date") or "")[:7]
    end = (normalized.get("period_end_date") or "")[:7]
    safe_co = company.replace(" ", "_")
    filename = f"PL_{safe_co}_{start}_to_{end}.pdf"

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
    income_root = find_group(accounts, root_type="Income")
    direct_grp = find_group(accounts, account_number="5100")
    indirect_grp = find_group(accounts, account_number="5200")

    for title, grp in [("REVENUE", income_root),
                       ("COGS (Direct)", direct_grp),
                       ("OPEX (Indirect)", indirect_grp)]:
        print(f"\n=== {title} ===")
        for a in leaves_under(accounts, grp):
            print(f"  {a.account_number or '----'}  {a.account_name}")
