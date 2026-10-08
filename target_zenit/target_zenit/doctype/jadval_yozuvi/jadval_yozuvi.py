# Copyright (c) 2026, Target Zenit
# Jadval Yozuvi — haftalik shablonning bitta katagi (kun x dars x guruh).
# Hard cheklovlar shu yerda tekshiriladi: guruh/o'qituvchi/sinf/xona bandligi.
import frappe
from frappe import _
from frappe.model.document import Document

KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]


class JadvalYozuvi(Document):
	def validate(self):
		self.kun_raqami = KUNLAR.index(self.kun) + 1 if self.kun in KUNLAR else 0
		self._sinflarni_toldir()
		self._vaqtni_toldir()
		self._konflikt_tekshir()

	def _sinflarni_toldir(self):
		self.sinflar = ", ".join(guruh_sinflari(self.guruh, self.blok))

	def _vaqtni_toldir(self):
		from target_zenit.target_zenit.doctype.qongiroq_jadvali.qongiroq_jadvali import vaqt

		sinflar = (self.sinflar or "").split(", ")
		b, t = vaqt(sinflar[0] if sinflar and sinflar[0] else self.guruh, self.dars_raqami)
		self.boshlanish, self.tugash = b, t

	def _konflikt_tekshir(self):
		"""Shu versiya + kun + dars bo'yicha bandlikni tekshiradi."""
		boshqalar = frappe.get_all(
			"Jadval Yozuvi",
			filters={
				"versiya": self.versiya,
				"kun": self.kun,
				"dars_raqami": self.dars_raqami,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "guruh", "guruh_nomi", "oqituvchi", "oqituvchi_nomi", "xona", "sinflar", "fan"],
		)
		men_sinflar = set((self.sinflar or "").split(", ")) - {""}

		for b in boshqalar:
			# 1) Bitta guruh ikki darsda
			if b.guruh == self.guruh:
				frappe.throw(
					_("Konflikt: «{0}» guruhida {1} {2}-darsda allaqachon dars bor ({3}).").format(
						b.guruh_nomi or b.guruh, self.kun, self.dars_raqami, b.fan
					)
				)
			# 2) O'qituvchi bir vaqtda ikki joyda
			if self.oqituvchi and b.oqituvchi == self.oqituvchi:
				frappe.throw(
					_("Konflikt: {0} {1} {2}-darsda «{3}» guruhida band.").format(
						self.oqituvchi_nomi or self.oqituvchi, self.kun, self.dars_raqami,
						b.guruh_nomi or b.guruh,
					)
				)
			# 3) Sinf bir vaqtda ikki guruhda (blok ichidagi guruhlar — istisno)
			b_sinflar = set((b.sinflar or "").split(", ")) - {""}
			kesishma = men_sinflar & b_sinflar
			if kesishma and not (self.blok and b.get("blok") == self.blok):
				bir_blokda = (
					self.blok
					and frappe.db.get_value("Jadval Yozuvi", b.name, "blok") == self.blok
				)
				if not bir_blokda:
					frappe.throw(
						_("Konflikt: {0} sinf(lar)i {1} {2}-darsda «{3}» guruhida ham bor.").format(
							", ".join(sorted(kesishma)), self.kun, self.dars_raqami,
							b.guruh_nomi or b.guruh,
						)
					)
			# 4) Xona bandligi
			if self.xona and b.xona == self.xona:
				frappe.throw(
					_("Konflikt: «{0}» xonasi {1} {2}-darsda band.").format(
						self.xona, self.kun, self.dars_raqami
					)
				)


def guruh_sinflari(guruh: str, blok: str | None = None) -> list[str]:
	"""Guruhga tegishli sinflar ro'yxati.
	- Sinf guruhi bo'lsa: o'zi
	- Daraja/tanlov guruhi bo'lsa: blokdagi sinflar (yoki custom_azo_sinflar)"""
	if not guruh:
		return []
	tur = frappe.db.get_value("Student Group", guruh, "custom_guruh_turi")
	if tur in (None, "", "Sinf"):
		return [guruh]
	if blok:
		return frappe.get_all(
			"Dars Bloki Sinfi", filters={"parent": blok}, pluck="sinf", order_by="idx"
		)
	azo = frappe.db.get_value("Student Group", guruh, "custom_azo_sinflar")
	return [s.strip() for s in (azo or "").split(",") if s.strip()]
