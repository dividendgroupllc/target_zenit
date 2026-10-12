# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe.model.document import Document


class UyVazifa(Document):
	def before_save(self):
		if self.jadval_yozuvi and not self.guruh:
			jy = frappe.db.get_value(
				"Jadval Yozuvi", self.jadval_yozuvi,
				["guruh", "fan", "oqituvchi"], as_dict=True)
			if jy:
				self.guruh, self.fan, self.oqituvchi = jy.guruh, jy.fan, jy.oqituvchi
