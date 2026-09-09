# Copyright (c) 2026, Target Zenit
# Sotuv paneli — sotuv menejerlari uchun o'quvchilar ma'lumotlari (moliyaviy
# tranzaksiyalarsiz): guruhlar, shartnoma holati/turi, ota-onalar, telefonlar.
# Manba: Student (custom fieldlar bilan), Student Guardian -> Guardian, Student Group.

from __future__ import annotations

import frappe

ALLOWED_ROLES = ["System Manager", "Sales Manager", "Sales User", "Sotuv meneger", "Xojakbar_Operator"]

STUDENT_FIELDS = [
    "name",
    "student_name",
    "first_name",
    "enabled",
    "joining_date",
    "date_of_birth",
    "gender",
    "student_email_id",
    "student_mobile_number",
    "city",
    "address_line_1",
    "custom_sinf_guruh",
    "custom_edu_language",
    "custom_student_holat",
    "custom_izoh",
    "custom_shartnoma_qilindi",
    "custom_shartnoma_turi",
    "custom_contract_no",
    "custom_contract_date",
    "custom_shartnoma_file",
    "custom_tariff",
    "custom_tariff_amount",
    "custom_discount_amount",
    "custom_final_amount",
    "custom_payer_name",
    "custom_payer_phone",
]


def _guard():
    """Rolni harf ko'rinishiga befarq (case-insensitive) tekshirish."""
    allowed = {r.lower() for r in ALLOWED_ROLES}
    user_roles = {r.lower() for r in frappe.get_roles()}
    if not (allowed & user_roles):
        frappe.throw(
            "Ruxsat yo'q. Sotuv paneli uchun 'Sales User' yoki 'Sales Manager' roli kerak.",
            frappe.PermissionError,
        )


def _guardians_map():
    """student -> [{guardian_name, relation, mobile_number, email_address}] (Guardian bilan join)."""
    rows = frappe.db.sql(
        """SELECT sg.parent AS student, sg.relation,
                  COALESCE(g.guardian_name, sg.guardian_name) AS guardian_name,
                  g.mobile_number, g.email_address
           FROM `tabStudent Guardian` sg
           LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
           WHERE sg.parenttype = 'Student'
           ORDER BY sg.idx""",
        as_dict=True,
    )
    out = {}
    for r in rows:
        out.setdefault(r.student, []).append(
            {
                "guardian_name": r.guardian_name or "",
                "relation": r.relation or "",
                "mobile_number": r.mobile_number or "",
                "email_address": r.email_address or "",
            }
        )
    return out


@frappe.whitelist()
def get_data():
    _guard()

    students = frappe.get_all(
        "Student",
        fields=STUDENT_FIELDS,
        order_by="student_name asc, first_name asc",
        limit_page_length=0,
    )

    gmap = _guardians_map()
    for s in students:
        s["guardians"] = gmap.get(s["name"], [])
        if not s.get("student_name"):
            s["student_name"] = s.get("first_name") or s["name"]

    # Faol guruhlar ro'yxati (o'quvchisi yo'q guruhlar ham ko'rinsin)
    groups = frappe.get_all(
        "Student Group",
        filters={"disabled": 0},
        fields=["name", "student_group_name"],
        order_by="student_group_name asc",
        limit_page_length=0,
    )

    return {"students": students, "groups": groups}
