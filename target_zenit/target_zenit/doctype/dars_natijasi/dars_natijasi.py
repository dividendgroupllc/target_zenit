# Copyright (c) 2026, Target Zenit
from __future__ import annotations

from frappe.model.document import Document

from target_zenit.dars_jadvali import sozlamalar as soz


class DarsNatijasi(Document):
	def before_save(self):
		# Baho faqat darsда bo'lgan o'quvchiga (Keldi / Kechikdi)
		if self.davomat and self.davomat not in soz.BORLIK:
			self.baho = None
			self.baho_turi = None
		# Kechikish daqiqasi faqat «Kechikdi» holatida saqlanadi
		if self.davomat != "Kechikdi":
			self.kechikish_min = None
