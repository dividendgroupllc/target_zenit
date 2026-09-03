import frappe

from target_zenit.target_zenit.doctype.kassa.kassa import PARTY_NAME_FIELDS


def execute():
	"""Kassa.party_name'ni kontragentning joriy nom maydonidan qayta yozish.

	Ilgari party_name faqat client'da bir marta to'ldirilgan — Customer nomi
	keyin tahrirlansa, Kassa'da eski nom (docname) qolib ketardi. Bu patch
	barcha mavjud hujjatlarni (submit qilinganlarni ham) joriy nomga tenglaydi.
	"""
	for party_type, name_field in PARTY_NAME_FIELDS.items():
		frappe.db.sql(
			"""
			UPDATE `tabKassa` k
			INNER JOIN `tab{party_type}` p ON p.name = k.party
			SET k.party_name = p.`{name_field}`
			WHERE k.party_type = %s
				AND IFNULL(p.`{name_field}`, '') != ''
				AND IFNULL(k.party_name, '') != p.`{name_field}`
			""".format(party_type=party_type, name_field=name_field),
			party_type,
		)
