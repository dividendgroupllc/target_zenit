# Oylik tabel uchun HRMS tayyorgarligi:
# - Attendance.custom_koef maydoni (kunlik stavka koeffitsienti)
# - Employee.custom_ish_kuni maydoni (oyiga norma ish kuni; bo'sh = default)
# - Employee.custom_oylik maydoni (shartnoma oyligi, Overview tabida; saqlansa SSA avto)
# - "Bonus" Salary Component
# - "Target Oylik" Salary Structure
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Attendance": [
                {
                    "fieldname": "custom_koef",
                    "label": "Stavka koeffitsienti (tabel)",
                    "fieldtype": "Float",
                    "precision": "9",
                    "insert_after": "status",
                    "in_list_view": 1,
                },
            ],
            "Employee": [
                {
                    "fieldname": "custom_ish_kuni",
                    "label": "Ish kuni (tabel, oyiga)",
                    "fieldtype": "Int",
                    "insert_after": "designation",
                    "description": "Oylik tabelda kunlik narx = oylik / shu son. Bo'sh qolsa: o'qituvchi 21, boshqalar 26.",
                },
                # Shartnoma oyligi — Overview tabida (designation/ish kuni yonida).
                # Saqlanganda hook SSA avto-yaratadi; oylik tabel bilan ikki tomonlama sinxron.
                {
                    "fieldname": "custom_oylik",
                    "label": "Oylik ish haqi (shartnoma)",
                    "fieldtype": "Currency",
                    "options": "salary_currency",
                    "insert_after": "custom_ish_kuni",
                    "description": "Saqlanganda Salary Structure Assignment avtomatik yaratiladi (bugundan amal qiladi). Oylik tabel bilan sinxron.",
                },
            ],
        },
        ignore_validate=True,
        update=True,
    )

    from target_zenit.target_zenit.api.oylik_tabel import (
        STRUKTURA,
        _bonus_komponent_ta_minla,
        _struktura_ta_minla,
    )

    _bonus_komponent_ta_minla()
    _struktura_ta_minla()

    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    # Kiritish nuqtasi ctc emas, Overview'dagi custom_oylik — eski ctc relabel'lar olib tashlanadi
    frappe.db.delete("Property Setter", {"name": ["in", ["Employee-ctc-label", "Employee-ctc-description"]]})
    frappe.db.sql(
        "update `tabEmployee` set custom_oylik = ctc "
        "where ifnull(ctc, 0) > 0 and ifnull(custom_oylik, 0) = 0"
    )

    # Maoshlar doim UZS — kompaniya valyutasi USD bo'lsa ham
    make_property_setter("Employee", "salary_currency", "default", "UZS", "Text")
    frappe.db.sql("update `tabEmployee` set salary_currency = 'UZS'")

    # Struktura oldin kompaniya valyutasi (USD) bilan yaratilgan bo'lsa — UZS'ga tuzatish
    # (submitted hujjat, salary slip'lar hali yo'q — xavfsiz)
    if frappe.db.get_value("Salary Structure", STRUKTURA, "currency") != "UZS":
        frappe.db.set_value("Salary Structure", STRUKTURA, "currency", "UZS")

    frappe.db.commit()
