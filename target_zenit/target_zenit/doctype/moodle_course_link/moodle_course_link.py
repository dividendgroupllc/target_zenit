# Copyright (c) 2026, Target Zenit
# Moodle kursining Frappe tomondagi yozuvi.
#
# BOSHQARUV FRAPPE'DA: kurs ochiq/yopiq bo'lishi `amal` maydoni va dars
# jadvali bilan hal qilinadi (moodle_kurs.sync_kurslar), Moodle esa
# unga bo'ysunadi. Shu yozuvni Frappe'da o'chirish = Moodle'dagi kursni
# ham o'chirish (on_trash).

import frappe
from frappe.model.document import Document


class MoodleCourseLink(Document):
	def on_trash(self):
		"""Yozuv o'chirilsa — Moodle'dagi kurs ham o'chadi.

		Sinxron o'zi o'chirgan holatda avval `moodle_course_id` ni 0 qilib
		qo'yadi (API allaqachon chaqirilgan), shuning uchun bu yerda
		ikkinchi marta chaqirilmaydi."""
		if not self.moodle_course_id:
			return
		from target_zenit.integrations.moodle_kurs import kursni_ochir

		try:
			kursni_ochir(int(self.moodle_course_id))
		except Exception as e:
			frappe.throw(
				f"Moodle'dagi kurs o'chirilmadi, shuning uchun bu yozuv ham "
				f"o'chirilmadi: {e}\n\nAgar Moodle'da qo'lda o'chirgan bo'lsangiz, "
				f"avval «Amal» maydonini «O'chirish» qilib sinxronni ishga tushiring."
			)
