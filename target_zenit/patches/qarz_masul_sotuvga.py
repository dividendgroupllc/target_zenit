# Qarzdorlik: mas'ul faqat "Sotuv meneger" rolli foydalanuvchi bo'la oladi.
# Shu roli yo'q mas'ulga biriktirilgan mavjud Qarz Ishlarini qayta
# taqsimlash: sozlamalardagi sinf-pattern -> default_masul -> sinf bo'yicha
# barqaror taqsimot (engine._pick_masul bilan bir xil qoida).
import frappe


def execute():
    from target_zenit.qarzdorlik.engine import _pick_masul, _settings, sotuv_menejermi

    if not frappe.db.exists("DocType", "Qarz Ishi"):
        return
    cfg = _settings()
    ozgardi = 0
    for r in frappe.get_all("Qarz Ishi", fields=["name", "masul", "sinf"],
                            limit_page_length=0):
        if sotuv_menejermi(r.masul):
            continue
        yangi = _pick_masul(r.sinf, cfg)
        if yangi and yangi != r.masul:
            frappe.db.set_value("Qarz Ishi", r.name, "masul", yangi,
                                update_modified=False)
            ozgardi += 1
    if ozgardi:
        frappe.db.commit()
