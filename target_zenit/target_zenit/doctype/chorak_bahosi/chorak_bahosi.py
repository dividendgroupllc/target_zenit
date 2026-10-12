# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ChorakBahosi(Document):
	def validate(self):
		# Bir o'quvchi + fan + chorak uchun bitta yozuv
		dup = frappe.db.get_value("Chorak Bahosi", {
			"student": self.student, "fan": self.fan, "chorak": self.chorak,
			"name": ["!=", self.name or ""],
		}, "name")
		if dup:
			frappe.throw(_("Bu o'quvchi uchun shu fan va chorakda baho allaqachon bor: {0}").format(dup))
