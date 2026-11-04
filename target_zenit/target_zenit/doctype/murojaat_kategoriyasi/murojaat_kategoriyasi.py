# Copyright (c) 2026, Target Zenit
"""Murojaat kategoriyasi — marshrut jadvali.

Kategoriya kimga tegishli ekanini (CEO yoki Direktor) va qancha kun ichida
javob berilishi kerakligini shu hujjat belgilaydi. Marshrut ATAYLAB kodda
emas: yangi kategoriya chiqsa rahbariyat o'zi hujjat yaratib yo'nalishini
tanlaydi, kod o'zgarmaydi.
"""

import frappe
from frappe.model.document import Document


class MurojaatKategoriyasi(Document):
	def validate(self):
		# Kalit so'zlar solishtirish uchun normallashtiriladi (kichik harf, toza)
		if self.kalit_sozlar:
			sozlar = [s.strip().lower() for s in self.kalit_sozlar.replace("\n", ",").split(",")]
			self.kalit_sozlar = ", ".join([s for s in sozlar if s])

	def on_update(self):
		frappe.cache().delete_value("murojaat_kategoriyalar")

	def on_trash(self):
		frappe.cache().delete_value("murojaat_kategoriyalar")
