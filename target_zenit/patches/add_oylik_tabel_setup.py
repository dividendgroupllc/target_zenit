# Oylik tabel uchun HRMS tayyorgarligi:
# - Attendance.custom_koef maydoni (kunlik stavka koeffitsienti)
# - Employee.custom_ish_kuni maydoni (oyiga norma ish kuni; bo'sh = default)
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
            ],
        },
        ignore_validate=True,
        update=True,
    )

    from target_zenit.target_zenit.api.oylik_tabel import (
        _bonus_komponent_ta_minla,
        _struktura_ta_minla,
    )

    _bonus_komponent_ta_minla()
    _struktura_ta_minla()
    frappe.db.commit()
