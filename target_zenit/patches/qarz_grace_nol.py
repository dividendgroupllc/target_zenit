# Qarzdorlik: "5-kungacha kutish" bekor — nachisleniya qilingan kundan
# boshlab qarzdorlik panelida ko'rinadi. Buning uchun:
#   1) sozlamadagi grace_days -> 0 (imtiyoz kunlari yo'q)
#   2) barcha faol rejalarni qayta hisoblash — oylik qatorlarning muddati
#      nachisleniya sanasiga o'tadi va yangi Qarz Ishlari darhol ochiladi
import frappe


def execute():
    if not frappe.db.exists("DocType", "Qarzdorlik Sozlamalari"):
        return
    frappe.db.set_value("Qarzdorlik Sozlamalari", "Qarzdorlik Sozlamalari",
                        "grace_days", 0)
    frappe.clear_cache(doctype="Qarzdorlik Sozlamalari")

    from target_zenit.qarzdorlik import engine

    for tr in frappe.get_all("Tolov Rejasi", filters={"holat": "Faol"},
                             pluck="name", limit_page_length=0):
        try:
            engine.recompute_plan(tr, sync_case=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"qarz_grace_nol: {tr}")
    frappe.db.commit()
