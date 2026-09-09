# Copyright (c) 2026, abdulloh and contributors
# For license information, please see license.txt

"""Kurs yozuvlari faqat BITTA yo'nalishda kiritiladi: kompaniya valyutasidan
(USD) boshqa valyutaga, ya'ni "1 USD = 11 770 UZS" ko'rinishida.

Nega: ERPNext teskari yo'nalishni o'zi hisoblamaydi (erpnext.setup.utils.
get_exchange_rate faqat aynan from→to yozuvni qidiradi). Ikkala yo'nalish
qo'lda alohida kiritilsa, ular hech qachon bir-birining aniq teskarisi
bo'lmaydi (masalan 12 000 va 0.000083330) — natijada har bir aralash-valyutali
to'lovda sun'iy Exchange Gain/Loss va qoldiq farqlar paydo bo'ladi.

Shu modul USD→UZS yozuv saqlanganda teskari UZS→USD yozuvni avtomatik
yaratadi/yangilaydi (kurs = 1/R, 9 kasr xona — frappe Float ustunining
maksimal aniqligi), o'chirilganda esa teskarisini ham o'chiradi. Teskari
yo'nalishni qo'lda kiritish esa bloklanadi.
"""

import frappe
from frappe import _
from frappe.utils import flt

MIRROR_FLAG = "target_zenit_mirror_sync"


def get_company_currency():
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if company:
		return frappe.get_cached_value("Company", company, "default_currency")
	return None


def validate(doc, method=None):
	"""Teskari (X→USD) yo'nalishni qo'lda kiritishni bloklash."""
	if doc.flags.get(MIRROR_FLAG):
		return

	company_currency = get_company_currency()
	if not company_currency:
		return

	if doc.to_currency == company_currency and doc.from_currency != company_currency:
		frappe.throw(
			_(
				"Kursni faqat {0}→{1} yo'nalishida kiriting (masalan: 1 {0} = 11770 {1}). "
				"Teskari {1}→{0} yozuv avtomatik yaratiladi."
			).format(company_currency, doc.from_currency)
		)


def sync_mirror(doc, method=None):
	"""USD→X yozuv saqlanganda teskari X→USD yozuvni yaratish/yangilash."""
	if doc.flags.get(MIRROR_FLAG):
		return

	company_currency = get_company_currency()
	if not company_currency or doc.from_currency != company_currency:
		return

	if flt(doc.exchange_rate) <= 0:
		return

	reverse_rate = flt(1 / flt(doc.exchange_rate), 9)

	existing = frappe.db.get_value(
		"Currency Exchange",
		{
			"date": doc.date,
			"from_currency": doc.to_currency,
			"to_currency": doc.from_currency,
		},
		"name",
	)

	if existing:
		mirror = frappe.get_doc("Currency Exchange", existing)
		if (
			flt(mirror.exchange_rate, 9) == reverse_rate
			and mirror.for_buying == doc.for_buying
			and mirror.for_selling == doc.for_selling
		):
			return
	else:
		mirror = frappe.new_doc("Currency Exchange")
		mirror.date = doc.date
		mirror.from_currency = doc.to_currency
		mirror.to_currency = doc.from_currency

	mirror.exchange_rate = reverse_rate
	mirror.for_buying = doc.for_buying
	mirror.for_selling = doc.for_selling
	mirror.flags[MIRROR_FLAG] = True
	mirror.flags.ignore_permissions = True
	mirror.save()


def delete_mirror(doc, method=None):
	"""USD→X yozuv o'chirilganda teskari X→USD yozuvni ham o'chirish."""
	if doc.flags.get(MIRROR_FLAG):
		return

	company_currency = get_company_currency()
	if not company_currency or doc.from_currency != company_currency:
		return

	existing = frappe.db.get_value(
		"Currency Exchange",
		{
			"date": doc.date,
			"from_currency": doc.to_currency,
			"to_currency": doc.from_currency,
		},
		"name",
	)
	if existing:
		mirror = frappe.get_doc("Currency Exchange", existing)
		mirror.flags[MIRROR_FLAG] = True
		mirror.flags.ignore_permissions = True
		mirror.delete()
