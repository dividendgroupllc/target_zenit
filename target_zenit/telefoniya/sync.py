# Copyright (c) 2026, Target Zenit
"""Telefon raqamlarini kanonik ko'rinishda ushlab turish.

Odamlar raqamni xohlagan ko'rinishda kiritadi. Agar normallashtirish faqat
qidiruv paytida qilinsa, indeks ishlamaydi va har qidiruvda butun jadval
ko'rib chiqiladi. Shuning uchun saqlash paytida bir marta hisoblab,
indekslangan maydonda saqlaymiz.
"""

import frappe

from target_zenit.telefoniya.utils import normalize_phone


def family_validate(doc, method=None):
	doc.normal_telefon = normalize_phone(doc.get("phone"))
	doc.normal_telefon2 = normalize_phone(doc.get("phone2"))


def admission_lead_validate(doc, method=None):
	doc.normal_telefon = normalize_phone(doc.get("phone"))


def student_validate(doc, method=None):
	# Custom Field — after_migrate'dan oldin hali mavjud bo'lmasligi mumkin.
	if doc.meta.has_field("normal_telefon"):
		doc.normal_telefon = normalize_phone(doc.get("student_mobile_number"))


# Backfill uchun: doctype -> (manba maydon, maqsad maydon) juftliklari
BACKFILL = {
	"Family": [("phone", "normal_telefon"), ("phone2", "normal_telefon2")],
	"Admission Lead": [("phone", "normal_telefon")],
	"Student": [("student_mobile_number", "normal_telefon")],
}


def backfill(doctype: str) -> int:
	"""Mavjud yozuvlardagi raqamlarni bir martalik normallashtiradi."""
	juftlar = BACKFILL.get(doctype) or []
	ustunlar = frappe.db.get_table_columns(doctype)
	juftlar = [(m, n) for m, n in juftlar if m in ustunlar and n in ustunlar]
	if not juftlar:
		return 0

	maydonlar = ["name"] + [m for m, _ in juftlar] + [n for _, n in juftlar]
	ozgargan = 0
	for qator in frappe.get_all(doctype, fields=maydonlar, limit_page_length=0):
		yangilash = {}
		for manba, maqsad in juftlar:
			kutilgan = normalize_phone(qator.get(manba))
			if (qator.get(maqsad) or None) != kutilgan:
				yangilash[maqsad] = kutilgan
		if yangilash:
			# update_modified=False — bu texnik maydon, hujjat "o'zgardi" deb
			# hisoblanmasligi kerak (modified bo'yicha saralashlar buzilmasin).
			frappe.db.set_value(doctype, qator.name, yangilash, update_modified=False)
			ozgargan += 1
	return ozgargan
