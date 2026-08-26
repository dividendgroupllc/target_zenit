import frappe

DEFAULT_CURRENCY = "UZS"


def set_default_currency(doc, method=None):
	"""Yangi Customer'ga (jumladan Student'dan avto-yaratilganiga) UZS qo'yish.

	Kompaniya valyutasi USD bo'lgani uchun bo'sh qolgan default_currency
	tranzaksiyalarda USD deb olinadi — shuning oldini oladi.
	Qo'lda boshqa valyuta tanlangan bo'lsa, tegilmaydi.
	"""
	if not doc.default_currency:
		doc.default_currency = DEFAULT_CURRENCY
