# Copyright (c) 2026, Target Zenit
import frappe
from frappe.model.document import Document


class TabelIshKuni(Document):
    def validate(self):
        if not (1 <= (self.oy or 0) <= 12):
            frappe.throw("Oy 1 dan 12 gacha bo'lishi kerak")
        if not (1 <= (self.kun or 0) <= 31):
            frappe.throw("Ish kuni 1 dan 31 gacha bo'lishi kerak")
