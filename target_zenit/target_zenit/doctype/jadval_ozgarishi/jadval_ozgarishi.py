# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe.model.document import Document


class JadvalOzgarishi(Document):
	def validate(self):
		if self.jadval_yozuvi and not self.asl_oqituvchi:
			jy = frappe.db.get_value(
				"Jadval Yozuvi", self.jadval_yozuvi,
				["oqituvchi", "kun", "dars_raqami", "guruh_nomi", "fan"], as_dict=True)
			if jy:
				self.asl_oqituvchi = jy.oqituvchi
				self.kun = jy.kun
				self.dars_raqami = jy.dars_raqami
				self.guruh_nomi = jy.guruh_nomi
				self.fan = jy.fan
