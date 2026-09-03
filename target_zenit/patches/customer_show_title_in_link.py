import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	"""Customer link maydonlarida docname (ID) o'rniga customer_name ko'rsatish.

	Student qayta nomlanganda customer_name yangilanadi, lekin Customer docname'i
	eskicha qoladi — Kassa'dagi "Контрагент" link maydoni esa docname'ni ko'rsatadi.
	show_title_field_in_link yoqilsa, link maydonlar title_field'ni (customer_name)
	ko'rsatadi — Kassa'da ham, boshqa hujjatlarda ham joriy nom ko'rinadi.
	"""
	make_property_setter(
		"Customer",
		None,
		"show_title_field_in_link",
		1,
		"Check",
		for_doctype=True,
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Customer")
