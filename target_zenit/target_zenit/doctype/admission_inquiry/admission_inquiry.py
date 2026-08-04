# Copyright (c) 2026, Target Zenit
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AdmissionInquiry(Document):
	pass


@frappe.whitelist()
def convert_to_lead(inquiry_name: str):
	"""Arizadan Family (bor bo'lsa telefon bo'yicha topiladi) + Admission Lead yaratish."""
	inquiry = frappe.get_doc("Admission Inquiry", inquiry_name)

	if inquiry.converted_lead:
		frappe.throw(_("Bu arizadan allaqachon lead ochilgan: {0}").format(inquiry.converted_lead))

	if not inquiry.phone:
		frappe.throw(
			_("Telefon raqami kiritilmagan. Avval ota-onadan telefonini so'rab, arizaga kiriting.")
		)

	family_name = frappe.db.get_value(
		"Family", {"phone": inquiry.phone}, "name"
	) or frappe.db.get_value("Family", {"phone2": inquiry.phone}, "name")

	if not family_name:
		family = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": inquiry.parent_name,
				"father_name": inquiry.parent_name,
				"phone": inquiry.phone,
				"children": [
					{"full_name": inquiry.child_name or _("Noma'lum"), "birth_year": inquiry.birth_year}
				],
			}
		)
		family.insert(ignore_permissions=True)
		family_name = family.name

	lead = frappe.get_doc(
		{
			"doctype": "Admission Lead",
			"child_name": inquiry.child_name or inquiry.parent_name,
			"family": family_name,
			"birth_year": inquiry.birth_year,
			"target_grade": inquiry.target_grade,
			"stage": "Murojaat",
			"source": inquiry.source,
			"lead_owner": frappe.session.user,
			"notes": inquiry.message,
			"instagram_user_id": inquiry.instagram_user_id,
		}
	)
	lead.insert(ignore_permissions=True)

	# Arizaga bog'langan Instagram yozishmalarni lead'ga ko'chiramiz
	frappe.db.set_value(
		"Instagram Message", {"inquiry": inquiry.name}, "lead", lead.name, update_modified=False
	)

	inquiry.db_set("inquiry_status", "Lead ochildi")
	inquiry.db_set("converted_lead", lead.name)
	return lead.name
