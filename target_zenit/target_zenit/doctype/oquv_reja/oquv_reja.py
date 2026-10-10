# Copyright (c) 2026, Target Zenit
# O'quv Reja (standart KTP): fan x sinf-daraja uchun bitta Faol reja.
from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document


def _daraja_raqam(s: str | None) -> str:
	m = re.search(r"\d+", str(s or ""))
	return m.group(0) if m else ""


class OquvReja(Document):
	def validate(self):
		self.jami_soat = sum((q.soat or 0) for q in (self.qatorlar or []))
		# sinf_daraja ni tanlangan sinflardan avto to'ldiramiz (bo'sh bo'lsa)
		if not self.sinf_daraja and self.sinflar:
			darajalar = sorted({_daraja_raqam(s.guruh_nomi or s.guruh) for s in self.sinflar} - {""})
			self.sinf_daraja = ", ".join(darajalar) if darajalar else None
		self.nomi = self._nom_yasa()
		# Qatorlar tartibini idx bo'yicha avto-raqamlash (bo'sh bo'lsa)
		for i, q in enumerate(self.qatorlar or [], start=1):
			if not q.tartib:
				q.tartib = i
		self._faol_yagona()

	def _nom_yasa(self) -> str:
		fan = self.fan or "?"
		sinf = self.sinf_daraja or (self.sinflar[0].guruh_nomi if self.sinflar else "?")
		yil = f" ({self.academic_year})" if self.academic_year else ""
		return f"{fan} — {sinf}{yil}"

	def _faol_yagona(self):
		"""Bir fan uchun bitta sinf (Student Group) ikki Faol rejada bo'lmasin —
		aks holda qaysi reja amal qilishi noaniq bo'ladi."""
		if self.holat != "Faol":
			return
		guruhlar = [s.guruh for s in (self.sinflar or []) if s.guruh]
		if not guruhlar:
			return
		band = frappe.db.sql(
			"""SELECT DISTINCT g.guruh
			   FROM `tabOquv Reja Guruhi` g JOIN `tabOquv Reja` r ON r.name = g.parent
			   WHERE r.fan = %s AND r.holat = 'Faol' AND r.name != %s
			     AND g.guruh IN ({})""".format(", ".join(["%s"] * len(guruhlar))),
			[self.fan, self.name or "", *guruhlar],
		)
		if band:
			frappe.throw(
				_("Bu fan uchun quyidagi sinf(lar) allaqachon boshqa Faol rejada: {0}").format(
					", ".join(b[0] for b in band)
				)
			)
