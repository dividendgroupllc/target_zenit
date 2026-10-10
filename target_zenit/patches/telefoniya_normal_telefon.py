# Copyright (c) 2026, Target Zenit
"""Mavjud Family / Admission Lead / Student raqamlarini bir martalik normallashtirish.

Bu maydonlar yangi qo'shilgani uchun eski yozuvlarda bo'sh turadi — backfill
qilinmasa, qo'ng'iroq eski oilalarga va o'quvchilarga bog'lanmaydi.

⚠️ Patch'lar `after_migrate` hooklaridan OLDIN ishlaydi. Student'dagi
`normal_telefon` esa Custom Field — ya'ni patch paytida u hali mavjud
bo'lmaydi va backfill jimgina 0 ta yozuv bilan tugaydi. Shuning uchun
maydonlarni shu yerda o'zimiz yaratib olamiz (idempotent).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from target_zenit.telefoniya.setup import CUSTOM_FIELDS
from target_zenit.telefoniya.sync import backfill


def execute():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	frappe.db.commit()

	for doctype in ("Family", "Admission Lead", "Student"):
		if not frappe.db.table_exists(doctype):
			continue
		soni = backfill(doctype)
		print(f"  {doctype}: {soni} ta yozuv normallashtirildi")
	frappe.db.commit()
