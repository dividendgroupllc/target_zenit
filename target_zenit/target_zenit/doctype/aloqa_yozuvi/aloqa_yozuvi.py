# Copyright (c) 2026, Target Zenit
# Aloqa Yozuvi — har bir qo'ng'iroq/xabar. Saqlanganda kaskad:
# Va'da bo'lsa PTP ochadi, Qarz Ishi'ning statusi/sanalari/schyotchiklarini yangilaydi.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, nowdate

# Suhbat natijasi -> Qarz Ishi ishlov statusi
STATUS_MAP = {
	"Va'da berdi": "Gaplashildi - Va'da",
	"Bo'lib to'lashga kelishildi": "Bo'lib to'lash",
	"E'tiroz-nizo": "Gaplashildi - Nizo",
	"To'laganman deydi": "To'lov tekshirilmoqda",
	"Rad etdi": "Eskalatsiya",
	"Ma'lumot oldi": "Urinilmoqda",
}


class AloqaYozuvi(Document):
	def before_insert(self):
		self.masul = self.masul or frappe.session.user
		self.vaqt = self.vaqt or now_datetime()

	def validate(self):
		if self.aloqa_natijasi == "Gaplashildi" and not self.hisob_natijasi:
			frappe.throw(_("Gaplashilgan bo'lsa «Suhbat natijasi» majburiy."))
		if self.aloqa_natijasi != "Gaplashildi":
			self.hisob_natijasi = None
		if self.hisob_natijasi == "Va'da berdi":
			if not self.vada_summa or not self.vada_sana:
				frappe.throw(_("Va'da uchun summa va sana majburiy."))
			if getdate(self.vada_sana) < getdate(nowdate()):
				frappe.throw(_("Va'da sanasi o'tmishda bo'lishi mumkin emas."))
		if getdate(self.keyingi_sana) < getdate(nowdate()):
			frappe.throw(_("«Keyingi sana» o'tmishda bo'lishi mumkin emas."))

	def after_insert(self):
		self._ptp_och()
		self._ishni_yangila()

	def _ptp_och(self):
		if self.hisob_natijasi != "Va'da berdi":
			return
		# Shu ish bo'yicha eski ochiq va'dalar bekor qilinadi — bitta amal qiluvchi va'da
		for name in frappe.get_all(
			"Tolov Vadasi",
			filters={"qarz_ishi": self.qarz_ishi, "holat": "Ochiq"},
			pluck="name",
		):
			frappe.db.set_value("Tolov Vadasi", name, "holat", "Bekor")
		frappe.get_doc(
			{
				"doctype": "Tolov Vadasi",
				"qarz_ishi": self.qarz_ishi,
				"aloqa_yozuvi": self.name,
				"masul": self.masul,
				"vada_sana": self.vada_sana,
				"vada_summa": self.vada_summa,
				"holat": "Ochiq",
			}
		).insert(ignore_permissions=True)

	def _ishni_yangila(self):
		qi = frappe.get_doc("Qarz Ishi", self.qarz_ishi)
		qi.urinishlar_soni = (qi.urinishlar_soni or 0) + 1
		qi.oxirgi_aloqa = self.vaqt
		qi.keyingi_aloqa = self.keyingi_sana

		yangi_status = None
		if self.keyingi_harakat == "Eskalatsiya":
			yangi_status = "Eskalatsiya"
		elif self.hisob_natijasi:
			yangi_status = STATUS_MAP.get(self.hisob_natijasi)
		elif qi.ishlov_status == "Yangi":
			yangi_status = "Urinilmoqda"

		if yangi_status:
			qi.ishlov_status = yangi_status
			if yangi_status == "Gaplashildi - Nizo" and not qi.nizo_sababi:
				qi.nizo_sababi = self.komment or self.hisob_natijasi

		qi.save(ignore_permissions=True)
