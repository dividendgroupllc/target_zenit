# Copyright (c) 2026, Target Zenit
# Jadval Versiyasi — jadval chorakka bog'lanmaydi, sanadan amal qiladi.
# Bir vaqtda faqat bitta Faol versiya (sana oraliqlari kesishmaydi).
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class JadvalVersiyasi(Document):
	def validate(self):
		if self.amal_tugashi and getdate(self.amal_tugashi) < getdate(self.amal_boshlanishi):
			frappe.throw(_("Amal tugashi boshlanishidan oldin bo'lishi mumkin emas."))
		if self.holat == "Faol":
			self._kesishuv_tekshir()
		self.yozuvlar_soni = frappe.db.count("Jadval Yozuvi", {"versiya": self.name})

	def _kesishuv_tekshir(self):
		"""Shu o'quv yilida boshqa Faol versiya bilan sana oralig'i kesishmasin."""
		for v in frappe.get_all(
			"Jadval Versiyasi",
			filters={
				"holat": "Faol",
				"academic_year": self.academic_year,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "amal_boshlanishi", "amal_tugashi"],
		):
			bosh = getdate(self.amal_boshlanishi)
			tug = getdate(self.amal_tugashi) if self.amal_tugashi else None
			v_bosh = getdate(v.amal_boshlanishi)
			v_tug = getdate(v.amal_tugashi) if v.amal_tugashi else None
			if (tug is None or v_bosh <= tug) and (v_tug is None or bosh <= v_tug):
				frappe.throw(
					_("«{0}» versiyasi bilan sana oralig'i kesishadi ({1} — {2}). "
					  "Avval uni Arxivga o'tkazing yoki tugash sanasini qo'ying.").format(
						v.name, v.amal_boshlanishi, v.amal_tugashi or "muddatsiz"
					)
				)

	@frappe.whitelist()
	def nusxa_ol(self, yangi_nomi: str, amal_boshlanishi: str):
		"""Shu versiyadan nusxa (Qoralama) — barcha jadval yozuvlari bilan."""
		yangi = frappe.copy_doc(self)
		yangi.nomi = yangi_nomi
		yangi.holat = "Qoralama"
		yangi.amal_boshlanishi = amal_boshlanishi
		yangi.amal_tugashi = None
		yangi.insert()
		for y in frappe.get_all("Jadval Yozuvi", filters={"versiya": self.name}, pluck="name"):
			d = frappe.copy_doc(frappe.get_doc("Jadval Yozuvi", y))
			d.versiya = yangi.name
			d.insert(ignore_permissions=True)
		frappe.msgprint(_("Nusxa yaratildi: {0}").format(yangi.name))
		return yangi.name
