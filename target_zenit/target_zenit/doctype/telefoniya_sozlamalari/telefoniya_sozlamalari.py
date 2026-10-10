# Copyright (c) 2026, Target Zenit
import os

import frappe
from frappe.model.document import Document


class TelefoniyaSozlamalari(Document):
	def validate(self):
		papka = (self.yozuvlar_papkasi or "").strip()
		if papka and not os.path.isabs(papka):
			frappe.throw("Yozuvlar papkasi to'liq yo'l bo'lishi kerak (/ dan boshlanadi)")
		self.yozuvlar_papkasi = papka

		if self.saqlash_kuni is not None and self.saqlash_kuni < 0:
			frappe.throw("Saqlash muddati manfiy bo'lishi mumkin emas")
		if (self.sim_pauza_maks or 0) < (self.sim_pauza_min or 0):
			frappe.throw("Maksimal pauza minimaldan kichik bo'lishi mumkin emas")

	def before_save(self):
		# Haqiqatda qaysi papka ishlatilayotganini ko'rsatib turamiz.
		# storage.baza_papka() bazadan o'qiydi — saqlash paytida u hali eski
		# qiymatni ko'radi, shuning uchun yo'lni shu yerda o'zimiz hisoblaymiz.
		from target_zenit.telefoniya.storage import SUKUTDAGI_PAPKA_NOMI

		papka = self.yozuvlar_papkasi or frappe.get_site_path("private", SUKUTDAGI_PAPKA_NOMI)
		self.joriy_papka = os.path.realpath(papka)
