# Copyright (c) 2026, Target Zenit
# Dars Bajarilishi — bitta sinfда bitta dars o'tilgani (fakt).
from __future__ import annotations

import frappe
from frappe.model.document import Document


class DarsBajarilishi(Document):
	def before_save(self):
		if self.guruh and not self.guruh_nomi:
			self.guruh_nomi = frappe.db.get_value("Student Group", self.guruh, "student_group_name")
