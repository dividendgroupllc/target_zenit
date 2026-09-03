import frappe

DEFAULT_CURRENCY = "UZS"


def set_customer_defaults(doc, method=None):
	"""Yangi Customer'ga (jumladan Student'dan avto-yaratilganiga) UZS defaultlari.

	1. default_currency: kompaniya valyutasi USD bo'lgani uchun bo'sh qolgan
	   default_currency tranzaksiyalarda USD deb olinadi — shuning oldini oladi.
	   Qo'lda boshqa valyuta tanlangan bo'lsa, tegilmaydi.

	2. Debitor schyoti: Kassa/Payment Entry valyutani customer'ning receivable
	   account'idan oladi. Kompaniya standarti "1310 - Debtors" USD'da, shuning
	   uchun UZS receivable account'ni (Debtors uzs) aniq biriktirib qo'yamiz —
	   aks holda Kassa'da USD tanlanib qoladi.
	"""
	if not doc.default_currency:
		doc.default_currency = DEFAULT_CURRENCY

	if doc.default_currency == DEFAULT_CURRENCY:
		set_uzs_receivable_account(doc)


def update_kassa_party_name(doc, method=None):
	"""customer_name tahrirlanganda — shu mijozga bog'langan barcha Kassa
	hujjatlaridagi party_name'ni yangi nomga moslash.

	Customer'ning docname'i nom tahrirlanganda o'zgarmaydi, shuning uchun Kassa
	party_name'ni docname'dan emas, customer_name'dan yuritamiz. Submit qilingan
	hujjatlarni qayta saqlab bo'lmaydi, shu sabab to'g'ridan-to'g'ri db orqali.
	"""
	old = doc.get_doc_before_save()
	if old and old.customer_name == doc.customer_name:
		return

	frappe.db.set_value(
		"Kassa",
		{"party_type": "Customer", "party": doc.name},
		"party_name",
		doc.customer_name,
		update_modified=False,
	)


def set_uzs_receivable_account(doc):
	company = frappe.defaults.get_global_default("company")
	if not company:
		return

	# Shu kompaniya uchun schyot allaqachon tanlangan bo'lsa — tegmaymiz
	for row in doc.get("accounts") or []:
		if row.company == company and row.account:
			return

	account = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"account_type": "Receivable",
			"is_group": 0,
			"account_currency": DEFAULT_CURRENCY,
		},
		"name",
	)
	if account:
		doc.append("accounts", {"company": company, "account": account})
