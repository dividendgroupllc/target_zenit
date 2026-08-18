"""
target_zenit/api/report_common.py
=================================
P&L va Balance PDF API'lari uchun umumiy yordamchilar:
  - filter normalizatsiya (ERPNext financial_statements execute() uchun)
  - hisoblar daraxti (tabAccount, lft/rgt bo'yicha leaflar)
  - report qatorlaridan qiymat ajratish
"""

import frappe


def normalize_filters(f, accumulated_default=0):
    """Frappe query-report filterlarini ERPNext report execute() ko'rinishiga
    keltiradi. Fiscal Year rejimida period sanalarini ham to'ldiradi."""
    result = {
        "company":            f.get("company"),
        "filter_based_on":    f.get("filter_based_on", "Date Range"),
        "period_start_date":  f.get("period_start_date"),
        "period_end_date":    f.get("period_end_date"),
        "from_fiscal_year":   f.get("from_fiscal_year"),
        "to_fiscal_year":     f.get("to_fiscal_year"),
        "periodicity":        f.get("periodicity", "Monthly"),
        "accumulated_values": int(f.get("accumulated_values",
                                        accumulated_default)),
        "include_default_book_entries": int(
            f.get("include_default_book_entries", 1)),
    }

    if result["filter_based_on"] != "Date Range" and not result["period_start_date"]:
        from_fy = result.get("from_fiscal_year")
        to_fy = result.get("to_fiscal_year")
        if from_fy and to_fy:
            fy_start = frappe.db.get_value("Fiscal Year", from_fy,
                                           "year_start_date")
            fy_end = frappe.db.get_value("Fiscal Year", to_fy,
                                         "year_end_date")
            if fy_start and fy_end:
                result["period_start_date"] = str(fy_start)
                result["period_end_date"] = str(fy_end)

    return result


def get_company_abbr(company):
    return frappe.db.get_value("Company", company, "abbr") or ""


def strip_abbr(name, abbr):
    """'1740 - Office Equipments - TZ' → '1740 - Office Equipments'"""
    suffix = f" - {abbr}"
    name = str(name or "")
    if abbr and name.endswith(suffix):
        return name[: -len(suffix)].strip()
    return name.strip()


def get_accounts(company):
    """Kompaniyaning barcha hisoblari, lft (daraxt) tartibida."""
    return frappe.db.sql(
        """
        SELECT name, account_name, account_number, parent_account,
               lft, rgt, is_group, root_type
        FROM tabAccount
        WHERE company = %s
        ORDER BY lft
        """,
        (company,),
        as_dict=True,
    )


def find_group(accounts, account_number=None, root_type=None):
    """account_number (masalan '5200') yoki root_type bo'yicha group hisobni
    topadi. Topilmasa None."""
    for a in accounts:
        if not a.is_group:
            continue
        if account_number and str(a.account_number or "") == str(account_number):
            return a
        if (root_type and not account_number
                and a.root_type == root_type and not a.parent_account):
            return a
    return None


def leaves_under(accounts, group):
    """Group subtree'sidagi leaf hisoblar (lft tartibida)."""
    if not group:
        return []
    return [a for a in accounts
            if not a.is_group and group.lft < a.lft < group.rgt]


def extract_values(rows, col_keys, abbr):
    """Report qatorlari → { hisob nomi (abbr'siz) : [v1..vn] }.
    Ham 'account' (docname), ham 'account_name' bo'yicha indekslaydi —
    'Provisional Profit / Loss (Credit)' kabi hisobsiz qatorlar
    account_name orqali topiladi."""
    vals = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [float(row.get(ck) or 0) for ck in col_keys]
        for field in ("account", "account_name"):
            key = strip_abbr(row.get(field), abbr)
            if key and key not in vals:
                vals[key] = values
    return vals


def account_values(vals, account, abbr, n_cols):
    """Bitta leaf hisobning qiymat ro'yxati (topilmasa nol)."""
    key = strip_abbr(account.name, abbr)
    v = vals.get(key)
    if v is None:
        # raqam bo'yicha fallback: '5201 - ...' prefiksi mos kelsa
        num = str(account.account_number or "").strip()
        if num:
            for k, kv in vals.items():
                if k.split(" - ")[0].strip() == num:
                    v = kv
                    break
    return (list(v) + [0.0] * n_cols)[:n_cols] if v else [0.0] * n_cols


def save_private_file(local_path, filename):
    """PDF'ni private File doc sifatida saqlaydi, file_url qaytaradi.

    Eski nusxalar (doc + disk fayl) avval o'chiriladi — shunda nom
    barqaror qoladi, Frappe unique-suffix qo'shmaydi."""
    import os

    with open(local_path, "rb") as f:
        content = f.read()
    os.remove(local_path)

    stem = filename.rsplit(".", 1)[0]
    for name in frappe.get_all(
            "File", filters={"file_name": ["like", f"{stem}%"]}, pluck="name"):
        frappe.delete_doc("File", name, ignore_permissions=True,
                          delete_permanently=True)
    site_path = frappe.get_site_path("private", "files", filename)
    if os.path.exists(site_path):
        os.remove(site_path)

    file_doc = frappe.get_doc({
        "doctype":    "File",
        "file_name":  filename,
        "is_private": 1,
        "folder":     "Home/Attachments",
        "content":    content,
    })
    file_doc.flags.ignore_permissions = True
    file_doc.insert()
    return file_doc.file_url
