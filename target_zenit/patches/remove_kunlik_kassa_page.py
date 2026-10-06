# Kunlik kassa alohida sahifa sifatida bekor qilindi — endi u investor
# dashboardning "Kunlik kassa" bo'limi. Eski Page hujjatini o'chirish
# (fayllari olib tashlangan, lekin DB'dagi yozuv migrate'da o'zi ketmaydi).
import frappe


def execute():
    if frappe.db.exists("Page", "kunlik-kassa"):
        frappe.delete_doc("Page", "kunlik-kassa", ignore_permissions=True, force=True)
