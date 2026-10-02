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
                # Tabelga kirish belgisi: Active/Inactive yetarli emas (Active'lar
                # ko'p) — tabel FAQAT shu checkbox belgilanganlarni oladi
                {
                    "fieldname": "custom_tabelda",
                    "label": "Oylik tabelda (hozir ishlayapti)",
                    "fieldtype": "Check",
                    "insert_after": "status",
                    "default": "0",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "description": "Belgilangan xodimlargina oylik tabel jadvalida chiqadi.",
                },
                # Shartnoma oyligi — Overview tabida (designation/ish kuni yonida).
                # Saqlanganda hook SSA avto-yaratadi; oylik tabel bilan ikki tomonlama sinxron.
                {
                    "fieldname": "custom_oylik",
                    "label": "Oylik ish haqi (shartnoma)",
                    "fieldtype": "Currency",
                    "options": "salary_currency",
                    "insert_after": "custom_ish_kuni",
                    "description": "Kunbay xodimda — OYLIK summa, soatbay xodimda — SOAT NARXI. "
                    "Saqlanganda Salary Structure Assignment avtomatik yaratiladi. Oylik tabel bilan sinxron.",
                },
                # To'lov turi: kunbay (0/1 yo'qlama, oylik/norma kun) yoki soatbay
                # (tabelga soat yoziladi, jami = soat narxi x soatlar). O'qituvchilar
                # odatda soatbay.
                {
                    "fieldname": "custom_tolov_turi",
                    "label": "To'lov turi (tabel)",
                    "fieldtype": "Select",
                    "options": "Kunbay\nSoatbay",
                    "default": "Kunbay",
                    "insert_after": "custom_oylik",
                    "in_standard_filter": 1,
                },
                # Oy yopilgandagi avto-nachisleniya kategoriyasi (buxgalter
                # registri atamalari bilan). Hisob mapping'i:
                # "Admin oylik" -> "Ish haqi — admin xodimlar";
                # O'qituvchi / Xodimlar / Oshxona -> "Ish haqi — o'qituvchilar
                # va boshqa xodimlar, sebestoimost". Bo'sh bo'lsa lavozim va
                # to'lov turidan taxmin qilinadi (oshpaz -> Oshxona,
                # tutor/tozalik/komendant -> Xodimlar, soatbay/teacher ->
                # O'qituvchi, qolganlar -> Admin oylik).
                {
                    "fieldname": "custom_ish_haqi_kategoriya",
                    "label": "Ish haqi kategoriyasi (tabel)",
                    "fieldtype": "Select",
                    "options": "\nAdmin oylik\nO'qituvchi\nXodimlar\nOshxona",
                    "insert_after": "custom_tolov_turi",
                    "in_standard_filter": 1,
                    "description": "Oy yopilganda nachisleniya qaysi xarajat hisobiga tushishini belgilaydi: "
                    "Admin oylik — admin hisobi; O'qituvchi/Xodimlar/Oshxona — sebestoimost hisobi. "
                    "Bo'sh bo'lsa lavozim va to'lov turidan avtomatik aniqlanadi.",
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
