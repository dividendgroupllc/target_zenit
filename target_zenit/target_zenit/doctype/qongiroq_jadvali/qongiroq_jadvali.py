# Copyright (c) 2026, Target Zenit
# Qo'ng'iroq jadvali — dars raqami -> vaqt. Maktabda ikki variant:
# 1A-5A va 5B-11B (faqat 5-dars va tushlik farq qiladi).
from fnmatch import fnmatch

import frappe
from frappe import _
from frappe.model.document import Document


class QongiroqJadvali(Document):
	def validate(self):
		raqamlar = [r.dars_raqami for r in self.qatorlar if r.turi == "Dars"]
		if len(raqamlar) != len(set(raqamlar)):
			frappe.throw(_("Dars raqamlari takrorlanmasligi kerak."))
		for r in self.qatorlar:
			if r.boshlanish and r.tugash and str(r.tugash) <= str(r.boshlanish):
				frappe.throw(
					_("{0}-qator: tugash vaqti boshlanishdan keyin bo'lishi kerak.").format(r.idx)
				)


def for_sinf(sinf: str):
	"""Sinf nomiga mos qo'ng'iroq jadvalini qaytaradi (tartib bo'yicha birinchi mos kelgani)."""
	for js in frappe.get_all(
		"Qongiroq Jadvali",
		filters={"faol": 1},
		fields=["name", "sinf_pattern"],
		order_by="tartib asc",
	):
		for p in (js.sinf_pattern or "").split(","):
			p = p.strip()
			if p and fnmatch(sinf or "", p):
				return frappe.get_cached_doc("Qongiroq Jadvali", js.name)
	return None


def vaqt(sinf: str, dars_raqami: int):
	"""(boshlanish, tugash) — sinf va dars raqami bo'yicha."""
	js = for_sinf(sinf)
	if not js:
		return None, None
	for r in js.qatorlar:
		if r.turi == "Dars" and r.dars_raqami == dars_raqami:
			return r.boshlanish, r.tugash
	return None, None
