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


def _sinf_nomimi(nom: str | None) -> bool:
	"""«5 A(full)» kabi RAQAM BILAN BOSHLANADIGAN sinf nomimi?

	Oqim guruhlarida ham raqam bor («ENGLISH Low 6-7»), shuning uchun
	«raqam bormi» tekshiruvi yetarli emas."""
	return bool(re.match(r"\s*\d+\s*[A-Za-z(]", str(nom or "")))


class OquvReja(Document):
	def validate(self):
		self.jami_soat = sum((q.soat or 0) for q in (self.qatorlar or []))
		# sinf_daraja ni tanlangan sinflardan avto to'ldiramiz (bo'sh bo'lsa).
		# FAQAT raqamli sinf guruhlaridan: «ENGLISH Low 6-7» dan «6» ajratib
		# olish Low va High rejalarini bir-biridan ajratib bo'lmaydigan
		# qilib qo'yardi (2026-11-09).
		if not self.sinf_daraja and self.sinflar:
			darajalar = sorted({
				_daraja_raqam(s.guruh_nomi or s.guruh) for s in self.sinflar
				if _sinf_nomimi(s.guruh_nomi or s.guruh)
			} - {""})
			self.sinf_daraja = ", ".join(darajalar) if darajalar else None
		self.nomi = self._nom_yasa()
		# Qatorlar tartibini idx bo'yicha avto-raqamlash (bo'sh bo'lsa)
		for i, q in enumerate(self.qatorlar or [], start=1):
			if not q.tartib:
				q.tartib = i
		self._faol_yagona()

	def _nom_yasa(self) -> str:
		"""Reja nomi. Oqim guruhlarida GURUH NOMI ishlatiladi, chunki yorliq
		(«ENGLISH 6-7») Low va High uchun bir xil bo'lib, ro'yxatda ikki
		bir xil qator turardi."""
		fan = self.fan or "?"
		yil = f" ({self.academic_year})" if self.academic_year else ""

		guruhlar = [(s.guruh_nomi or s.guruh) for s in (self.sinflar or []) if (s.guruh_nomi or s.guruh)]
		oqimlar = [g for g in guruhlar if not _sinf_nomimi(g)]
		if oqimlar:
			# Oqim/tanlov/qo'shma guruh — o'z nomi bilan ko'rsatamiz
			kesim = ", ".join(oqimlar[:3]) + ("…" if len(oqimlar) > 3 else "")
			return f"{fan} — {kesim}{yil}"

		sinf = self.sinf_daraja or (guruhlar[0] if guruhlar else "?")
		if str(sinf).replace("-", "").replace(",", "").replace(" ", "").isdigit():
			sinf = f"{sinf}-sinf"
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
