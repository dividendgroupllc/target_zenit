import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

SERIYA = "EDU-INS-.YYYY.-"


def execute():
	"""Instructor'ni ism satri bilan nomlashdan naming series'ga o'tkazish.

	Education Settings'da `instructor_created_by = Full Name` bo'lsa, Instructor
	hujjatining docname'i — o'qituvchining ismi. `autoname` faqat hujjat
	yaratilganda ishlaydi, shuning uchun xodim ismi keyin (masalan pasport
	bo'yicha) o'zgartirilganda docname eskicha qolib ketadi: jadval yozuvlari,
	Course Schedule va hisobotlar eski ism satriga bog'langan holda qoladi.

	"Naming Series" da yangi Instructor'lar barqaror ID oladi (EDU-INS-2026-00001)
	va ism o'zgarishi hech narsaga ta'sir qilmaydi. Mavjud yozuvlar
	qayta nomlanmaydi — ularning docname'i eski ism satri bo'lib qoladi, lekin
	panellar va link maydonlar `instructor_name`ni ko'rsatadi
	(instructor_show_title_in_link patchi + ism_sync.py).
	"""
	frappe.db.set_single_value("Education Settings", "instructor_created_by", "Naming Series")

	# Yangi hujjatda naming_series bo'sh qolmasligi uchun default qo'yiladi —
	# aks holda `set_name_by_naming_series` "Naming Series mandatory" deb to'xtaydi.
	meta = frappe.get_meta("Instructor")
	df = meta.get_field("naming_series")
	if df and SERIYA in (df.options or ""):
		make_property_setter(
			"Instructor", "naming_series", "default", SERIYA, "Text",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Instructor")
