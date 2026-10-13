import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	"""Instructor link maydonlarida docname o'rniga instructor_name ko'rsatish.

	Education Settings'da `instructor_created_by = Full Name` bo'lgani uchun
	Instructor hujjatining docname'i — o'qituvchining ismi satri. Xodim ismi
	pasport bo'yicha o'zgartirilganda docname eskicha qolib ketadi (autoname
	faqat yaratilganda ishlaydi), shuning uchun Jadval Yozuvi va boshqa link
	maydonlarda eski ism ko'rinardi. show_title_field_in_link yoqilsa, link
	maydon title_field'ni (instructor_name) ko'rsatadi — u esa ism_sync orqali
	Employee.employee_name bilan sinxron yuritiladi.
	"""
	make_property_setter(
		"Instructor",
		None,
		"show_title_field_in_link",
		1,
		"Check",
		for_doctype=True,
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Instructor")
