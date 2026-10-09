# Mavjud barcha Employee uchun ish haqi kategoriyasini (bo'sh bo'lsa) lavozimdan
# to'ldiradi. Idempotent — faqat bo'sh va lavozimi bor xodimlarga tegadi.
# Qo'lda tanlangan qiymatlar o'zgartirilmaydi.
import frappe

from target_zenit.target_zenit.api.oylik_tabel import _ish_haqi_kategoriya


def execute():
    if not frappe.db.has_column("Employee", "custom_ish_haqi_kategoriya"):
        return
    emps = frappe.get_all(
        "Employee",
        filters={"custom_ish_haqi_kategoriya": ["in", [None, ""]]},
        fields=["name", "designation", "custom_tolov_turi"],
    )
    n = 0
    for e in emps:
        if not (e.designation or "").strip():
            continue
        cat = _ish_haqi_kategoriya(None, e.designation, e.custom_tolov_turi)
        frappe.db.set_value(
            "Employee", e.name, "custom_ish_haqi_kategoriya", cat,
            update_modified=False,
        )
        n += 1
    frappe.db.commit()
    print(f"ish_haqi_kategoriya backfill: {n} ta xodim to'ldirildi")
