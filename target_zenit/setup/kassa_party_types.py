# Copyright (c) 2026, Target Zenit
# Kassa'dagi "Тип контрагента" ro'yxatini Chart of Accounts bilan sinxronlaydi.
#
# Ro'yxat = Customer/Supplier/Shareholder/Employee + "Indirect Expenses" ichidagi
# xarajat papkalari (masalan "Budget xarajati - TZ", "Xarajatlar - TZ").
#
# Nega Property Setter: Select maydonining qiymatlari server tomonda doctype meta'siga
# qarab tekshiriladi. Papkalar CoA'dan kelgani uchun ular meta'ga shu yo'l bilan yoziladi —
# aks holda papka tanlangan hujjat saqlanmaydi.
#
# Qachon ishlaydi: har `bench migrate` da va CoA'dagi xarajat account'i o'zgarganda.
# Qo'lda: bench --site <site> execute target_zenit.setup.kassa_party_types.sync_party_type_options

import frappe

from target_zenit.target_zenit.doctype.kassa.kassa import (
	BASE_PARTY_TYPES,
	LEGACY_PARTY_TYPES,
	get_expense_groups,
)

DOCTYPE = "Kassa"
FIELDNAME = "party_type"


def build_options() -> str:
	"""Barcha kompaniyalar bo'yicha to'liq ro'yxat (meta uchun superset).

	Formada foydalanuvchi faqat o'z kompaniyasining papkalarini ko'radi — buni
	kassa.js `get_party_type_options(company)` orqali qiladi.
	"""
	options = ["", *BASE_PARTY_TYPES]

	for company in frappe.get_all("Company", pluck="name"):
		for group in get_expense_groups(company):
			if group.name not in options:
				options.append(group.name)

	# Eski hujjatlardagi qiymatlar: formada ko'rinmaydi, faqat validatsiya uchun
	options += [value for value in LEGACY_PARTY_TYPES if value not in options]

	return "\n".join(options)


def sync_party_type_options() -> str:
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	options = build_options()
	current = frappe.db.get_value(
		"Property Setter",
		{"doc_type": DOCTYPE, "field_name": FIELDNAME, "property": "options"},
		"value",
	)
	if current == options:
		return options

	make_property_setter(
		DOCTYPE, FIELDNAME, "options", options, "Text", validate_fields_for_doctype=False
	)
	frappe.clear_cache(doctype=DOCTYPE)
	return options


def on_account_change(doc, method=None):
	"""Chart of Accounts'dagi xarajat account'i o'zgarsa ro'yxatni yangilaydi."""
	if doc.root_type != "Expense":
		return
	# Ommaviy yozuv paytida (o'rnatish, migratsiya, import) har account uchun
	# qayta hisoblash shart emas — oxirida after_migrate baribir sinxronlaydi.
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_import:
		return
	sync_party_type_options()


def after_migrate():
	sync_party_type_options()
