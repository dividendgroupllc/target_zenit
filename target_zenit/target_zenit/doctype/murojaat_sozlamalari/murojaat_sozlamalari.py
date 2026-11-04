# Copyright (c) 2026, Target Zenit
"""Murojaat sozlamalari (Single): avtomatik biriktirish va standart rahbarlar.

Nega kerak: AI yo'nalishni (CEO / Direktor) o'zi aniqlaydi, lekin yo'nalishda
bir nechta foydalanuvchi bo'lishi mumkin — "kimning vazifasi" aniq bo'lmasa
murojaat egasiz qoladi. Shu yerda har yo'nalish uchun standart mas'ul
ko'rsatiladi; bitta rolli foydalanuvchi bo'lsa sozlama shart emas, tizim
o'zi topadi.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from target_zenit.target_zenit.doctype.murojaat.murojaat import YONALISH_ROL


class MurojaatSozlamalari(Document):
	def validate(self):
		for maydon, yonalish in (("standart_ceo", "CEO"), ("standart_direktor", "Direktor")):
			user = self.get(maydon)
			if not user:
				continue
			rol = YONALISH_ROL[yonalish]
			roles = {r.lower() for r in frappe.get_roles(user)}
			if not ({rol.lower(), "system manager"} & roles):
				frappe.throw(
					_("«{0}» foydalanuvchisida «{1}» roli yo'q — standart mas'ul bo'la olmaydi.")
					.format(user, rol)
				)
			if not frappe.db.get_value("User", user, "enabled"):
				frappe.throw(_("«{0}» foydalanuvchisi o'chirilgan.").format(user))

	def on_update(self):
		frappe.cache().delete_value("murojaat_sozlamalari")
