# Copyright (c) 2026, Target Zenit
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime


class AdmissionLead(Document):
	def validate(self):
		self.validate_status_belongs_to_stage()

	def validate_status_belongs_to_stage(self):
		if self.status:
			status_stage = frappe.db.get_value("Admission Status", self.status, "stage")
			if status_stage == self.stage:
				return
			# Bosqich o'zgargan bo'lsa (masalan Kanban'da sudralganda) eski status
			# yangi bosqichga to'g'ri kelmaydi — jimgina almashtiramiz
			if not self.is_new() and frappe.db.get_value(self.doctype, self.name, "stage") != self.stage:
				self.status = self.get_default_status()
			else:
				frappe.throw(
					_("'{0}' statusi '{1}' bosqichiga tegishli emas. Avval bosqichga mos status tanlang.").format(
						self.status, self.stage
					)
				)
		elif self.stage:
			self.status = self.get_default_status()

	def get_default_status(self):
		# Yangi bosqichning birinchi Active statusi
		statuses = frappe.get_all(
			"Admission Status",
			filters={"stage": self.stage, "status_type": "Active"},
			order_by="sort_order asc",
			limit=1,
			pluck="name",
		)
		return statuses[0] if statuses else None

	def after_insert(self):
		self.create_first_contact_todo()

	def create_first_contact_todo(self):
		# 24 soat SLA: yangi murojaatga mas'ul xodimga topshiriq
		if not self.lead_owner:
			return
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": self.lead_owner,
				"reference_type": self.doctype,
				"reference_name": self.name,
				"date": add_to_date(now_datetime(), hours=24),
				"priority": "High",
				"description": _("Yangi murojaat: {0} — 24 soat ichida birinchi aloqa qiling").format(
					self.child_name
				),
			}
		).insert(ignore_permissions=True)
