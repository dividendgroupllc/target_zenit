# Copyright (c) 2026, Target Zenit
# Qarz Ishi — qarzdor o'quvchi bo'yicha markaziy workflow hujjati.
# Ochish/yopishni faqat engine qiladi (frappe.flags.qarz_engine), menejer esa
# ishlov holatini yuritadi. O'quvchiga bir vaqtda bitta ochiq ish.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

YOPIQ_STATUSLAR = ("Yopildi - To'landi", "Yopildi - Boshqa")


class QarzIshi(Document):
	def before_insert(self):
		self.ochilgan_sana = self.ochilgan_sana or nowdate()
		if not self.keyingi_aloqa:
			self.keyingi_aloqa = nowdate()

	def validate(self):
		self._bitta_ochiq_ish()
		self._status_qoidalari()

	def _bitta_ochiq_ish(self):
		if self.ishlov_status in YOPIQ_STATUSLAR:
			return
		dup = frappe.db.exists(
			"Qarz Ishi",
			{
				"student": self.student,
				"ishlov_status": ["not in", list(YOPIQ_STATUSLAR)],
				"name": ["!=", self.name or ""],
			},
		)
		if dup:
			frappe.throw(
				_("{0} bo'yicha ochiq ish allaqachon bor: {1}").format(
					self.student_name or self.student, dup
				)
			)

	def _status_qoidalari(self):
		if self.ishlov_status not in YOPIQ_STATUSLAR and not self.keyingi_aloqa:
			frappe.throw(_("Ochiq ishda «Keyingi aloqa» sanasi majburiy."))

		if self.ishlov_status == "Gaplashildi - Nizo" and not (self.nizo_sababi or "").strip():
			frappe.throw(_("Nizo statusida «Nizo sababi» majburiy."))

		# "Yopildi - To'landi"ni faqat tizim qo'yadi (qarz haqiqatan nolga tushganda).
		# Menejer "To'lov tekshirilmoqda"gacha olib keladi — PE tushishi bilan engine yopadi.
		old = self.get_doc_before_save()
		status_changed = not old or old.ishlov_status != self.ishlov_status
		if (
			self.ishlov_status == "Yopildi - To'landi"
			and status_changed
			and not frappe.flags.qarz_engine
		):
			frappe.throw(
				_("«Yopildi - To'landi»ni tizim o'zi qo'yadi (to'lov tushgach). "
				  "Agar ota-ona to'laganini aytsa — «To'lov tekshirilmoqda» statusini tanlang.")
			)

		if self.ishlov_status in YOPIQ_STATUSLAR:
			self.yopilgan_sana = self.yopilgan_sana or nowdate()
			if not self.yopilish_sababi:
				self.yopilish_sababi = (
					"To'landi" if self.ishlov_status == "Yopildi - To'landi" else "Boshqa"
				)
		else:
			self.yopilgan_sana = None
