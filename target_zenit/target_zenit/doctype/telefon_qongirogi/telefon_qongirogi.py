# Copyright (c) 2026, Target Zenit
# Telefon Qongirogi — bitta qo'ng'iroqning metadatasi va ovoz yozuvi yo'li.
# Yozuv fayli Frappe `files` papkasidan tashqarida turadi (telefoniya/storage.py).
import frappe
from frappe.model.document import Document

from target_zenit.telefoniya import matcher, storage
from target_zenit.telefoniya.utils import normalize_phone


class TelefonQongirogi(Document):
	def validate(self):
		self._raqamni_normalla()
		self._boglanishni_toldir()
		self._vaqtni_hisobla()

	def on_trash(self):
		# Hujjat o'chirilsa yozuv fayli ham ketadi — yetim fayl qolmasin.
		if self.fayl_yoli:
			storage.ochir(self.fayl_yoli)

	def _raqamni_normalla(self):
		self.normal_telefon = normalize_phone(self.tashqi_raqam)

	def _boglanishni_toldir(self):
		"""Bog'lanishlar bo'sh bo'lsa raqam bo'yicha izlaydi.

		Qo'lda to'ldirilgan bog'lanish ustidan yozilmaydi — menejer "bu qo'ng'iroq
		aslida boshqa bola haqida" deb tuzatgan bo'lishi mumkin.
		"""
		if self.family and self.admission_lead and self.student:
			return
		topilgan = matcher.topish(self.normal_telefon)
		for maydon in ("family", "admission_lead", "student"):
			if not self.get(maydon):
				self.set(maydon, topilgan.get(maydon))
		if not self.aloqador_ism:
			self.aloqador_ism = topilgan.get("aloqador_ism")

		if not self.xodim or not self.foydalanuvchi:
			xodim = matcher.xodim_topish(self.ichki_raqam)
			self.xodim = self.xodim or xodim.get("xodim")
			self.foydalanuvchi = self.foydalanuvchi or xodim.get("foydalanuvchi")

	def _vaqtni_hisobla(self):
		"""Kutish va jami vaqtni vaqt belgilaridan chiqaradi.

		Asterisk suhbat_vaqtini o'zi yuboradi; kutish va jami esa shu uch
		vaqt belgisidan kelib chiqadi. Jiringlash vaqtini suhbat vaqtiga
		qo'shib yubormaslik muhim — menejer samaradorligi buzilib ketadi.
		"""
		from frappe.utils import get_datetime, time_diff_in_seconds

		if self.boshlandi and self.javob_berildi:
			self.kutish_vaqti = max(
				0, int(time_diff_in_seconds(get_datetime(self.javob_berildi), get_datetime(self.boshlandi)))
			)
		if self.boshlandi and self.tugadi:
			self.jami_vaqti = max(
				0, int(time_diff_in_seconds(get_datetime(self.tugadi), get_datetime(self.boshlandi)))
			)
		elif self.suhbat_vaqti or self.kutish_vaqti:
			self.jami_vaqti = (self.suhbat_vaqti or 0) + (self.kutish_vaqti or 0)


def permission_query_conditions(user: str | None = None) -> str:
	"""Menejer faqat o'z qo'ng'iroqlarini ko'radi, rahbar hammasini.

	Hujjat darajasidagi `has_permission` bilan birga ishlaydi — ro'yxat va
	hisobotlar shu shart bo'yicha filtrlanadi.
	"""
	user = user or frappe.session.user
	if _hammasini_korishi_mumkin(user):
		return ""
	return f"(`tabTelefon Qongirogi`.`foydalanuvchi` = {frappe.db.escape(user)})"


def has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if _hammasini_korishi_mumkin(user):
		return True
	return (doc.foydalanuvchi or "") == user


def _hammasini_korishi_mumkin(user: str) -> bool:
	if user == "Administrator":
		return True
	rollar = set(frappe.get_roles(user))
	return bool(rollar & {"System Manager", "Sales Manager", "Telefoniya Agent"})
