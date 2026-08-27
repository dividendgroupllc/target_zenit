# Student.custom_sinf_guruh'ni mavjud Student Group a'zoliklaridan to'ldirish.
# Field fixtures orqali yaratiladi (post_model_sync'da fixtures allaqachon yuklangan).

import frappe


def execute():
	# 2026-2027 guruhlar allaqachon joriy — yillik avto-ko'chirish (yearly_promotion)
	# birinchi marta 2027-yil 1-sentabrda ishlashi kerak.
	if not frappe.db.get_default("sinf_promotion_year"):
		frappe.db.set_default("sinf_promotion_year", "2026")

	if not frappe.db.has_column("Student", "custom_sinf_guruh"):
		return
	rows = frappe.get_all("Student Group Student", fields=["parent", "student"])
	for r in rows:
		if not frappe.db.get_value("Student", r.student, "custom_sinf_guruh"):
			frappe.db.set_value(
				"Student", r.student, "custom_sinf_guruh", r.parent, update_modified=False
			)
