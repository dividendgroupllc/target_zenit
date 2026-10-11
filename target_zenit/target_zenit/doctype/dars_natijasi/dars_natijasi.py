# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe.model.document import Document


class DarsNatijasi(Document):
	def before_save(self):
		# Baho faqat kelgan o'quvchiga
		if self.davomat and self.davomat != "Keldi":
			self.baho = None
