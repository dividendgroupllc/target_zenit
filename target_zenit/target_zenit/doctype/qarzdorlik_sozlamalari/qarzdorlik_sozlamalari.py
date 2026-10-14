# Copyright (c) 2026, Target Zenit
import frappe
from frappe import _
from frappe.model.document import Document


class QarzdorlikSozlamalari(Document):
	def validate(self):
		# Mas'ul faqat "Sotuv meneger" rolli faol foydalanuvchi bo'la oladi —
		# default ham, sinf biriktirishlari ham
		from target_zenit.qarzdorlik.engine import SOTUV_ROL, sotuv_menejermi

		if self.default_masul and not sotuv_menejermi(self.default_masul):
			frappe.throw(_("Default mas'ul «{0}» — «{1}» roliga ega emas. "
						   "Mas'ul faqat sotuv menejeri bo'la oladi.")
						 .format(self.default_masul, SOTUV_ROL))
		for r in (self.biriktirish or []):
			if r.masul and not sotuv_menejermi(r.masul):
				frappe.throw(_("Biriktirish ({0}): «{1}» — «{2}» roliga ega emas. "
							   "Mas'ul faqat sotuv menejeri bo'la oladi.")
							 .format(r.sinf_pattern, r.masul, SOTUV_ROL))
