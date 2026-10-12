# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe.model.document import Document


class UyVazifaNatijasi(Document):
	def before_save(self):
		if self.uy_vazifa and not (self.guruh and self.fan and self.sana):
			uv = frappe.db.get_value(
				"Uy Vazifa", self.uy_vazifa,
				["guruh", "fan", "sana", "chorak", "oqituvchi", "max_ball"], as_dict=True)
			if uv:
				self.guruh = self.guruh or uv.guruh
				self.fan = self.fan or uv.fan
				self.sana = self.sana or uv.sana
				self.chorak = self.chorak or uv.chorak
				self.oqituvchi = self.oqituvchi or uv.oqituvchi
				self.max_ball = self.max_ball or uv.max_ball
		if self.holat == "Bajarmadi":
			self.ball = 0
