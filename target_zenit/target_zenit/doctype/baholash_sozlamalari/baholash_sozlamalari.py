# Copyright (c) 2026, Target Zenit
from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

# Shkala -> (max_baho, otish, past, rag_qizil_ortacha, rag_sariq_ortacha)
SHKALA = {
	"5 ballik": (5, 3, 3, 3.0, 4.0),
	"10 ballik": (10, 5, 4, 5.0, 7.0),
	"100 ballik": (100, 60, 55, 60.0, 75.0),
}


class BaholashSozlamalari(Document):
	def validate(self):
		if self.max_baho and self.otish_bahosi and self.otish_bahosi > self.max_baho:
			frappe.throw(_("O'tish bahosi eng yuqori bahodan katta bo'lishi mumkin emas."))
		if self.rag_sariq_ortacha and self.rag_qizil_ortacha \
				and self.rag_qizil_ortacha > self.rag_sariq_ortacha:
			frappe.throw(_("Qizil chegara sariq chegaradan katta bo'lmasligi kerak."))
		if self.chorak_usuli == "Vaznli" and not frappe.db.exists("Baho Turi", {"faol": 1}):
			frappe.msgprint(_("«Vaznli» usul tanlandi, lekin faol «Baho Turi» yo'q. "
			                  "Baho Turi ro'yxatini to'ldiring."), indicator="orange", alert=True)

	def on_update(self):
		frappe.cache().delete_value("tz_baholash_sozlamalari")

	@frappe.whitelist()
	def shkala_boyicha_tiklash(self):
		"""Shkala tanlanganda chegaralarni standart qiymatlarga keltiradi."""
		v = SHKALA.get(self.shkala or "5 ballik")
		if not v:
			return
		self.max_baho, self.otish_bahosi, self.past_baho, \
			self.rag_qizil_ortacha, self.rag_sariq_ortacha = v
		return {"max_baho": self.max_baho, "otish_bahosi": self.otish_bahosi,
		        "past_baho": self.past_baho,
		        "rag_qizil_ortacha": self.rag_qizil_ortacha,
		        "rag_sariq_ortacha": self.rag_sariq_ortacha}
