# Copyright (c) 2026, Target Zenit
"""Murojaat — ota-onaning shikoyati / taklifi / muammosi va uning yechimi.

NEGA ALOHIDA DOCTYPE (Qarz Ishi'ga maydon qo'shish emas):
  - Shikoyat qarzdan mustaqil: qarzi yo'q ota-ona ham o'qituvchidan shikoyat
    qiladi. Qarz Ishi to'lov tushganda yopiladi — shikoyat esa hal qilinmagan
    holda u bilan birga ko'rinmay ketardi.
  - Bitta qarz ishida bir vaqtda ikki xil murojaat bo'ladi (biri CEO'ga,
    biri direktorga) — bitta hujjatda ikki javobgar va ikki muddat sig'maydi.

ZANJIR (yopiq halqa):
  1) Sotuvchi gaplashadi. O'zi hal qila olmasa «Rahbarga yo'naltirish»
     (yoki AI qo'ng'iroq tahlilidan avtomatik) -> Murojaat «Yangi»
  2) Kategoriya marshrutni beradi: CEO yoki Direktor paneliga tushadi
  3) Rahbar ko'radi (korildi_*), komment yozadi, `yechim_turi` + `yechim`
  4) Yechim yozilsa holat -> «Ota-onaga xabar berish» (rahbar hal qildi,
     ota-ona hali bilmaydi — halqa yopilmagan)
  5) Menejer ota-onaga qo'ng'iroq qilib `xabar_berildi` -> «Yopildi»
  Istisno: `yechim_turi` = «Ahamiyatsiz» (AI xato topgan) -> darhol «Yopildi»,
  ota-onaga qo'ng'iroq qilishning hojati yo'q.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime, nowdate

# Rahbar rollari: murojaat shu rollardagi odamlarning paneliga tushadi
ROL_CEO = "CEO"
ROL_DIREKTOR = "Direktor"
YONALISH_ROL = {"CEO": ROL_CEO, "Direktor": ROL_DIREKTOR}

# Ota-onaga qaytib qo'ng'iroq qilish SHART bo'lmagan qarorlar
XABARSIZ_YOPILADI = ("Ahamiyatsiz",)


class Murojaat(Document):
	def before_insert(self):
		self.ochilgan = self.ochilgan or now_datetime()
		self.menejer = self.menejer or frappe.session.user
		if not self.suhbat_vaqti:
			self.suhbat_vaqti = self.ochilgan

	def validate(self):
		self._marshrut()
		self._masul_biriktir()
		self._oquvchi_malumoti()
		self._muddat()
		self._yechim_nazorati()

	def on_update(self):
		self._biriktir()

	# ------------------------------------------------------------ marshrut
	def _marshrut(self):
		"""Yo'nalish kategoriyadan keladi. Kategoriya bo'lmasa — qo'lda
		tanlangan yo'nalish qoladi, u ham bo'lmasa CEO (javobsiz qolmasin)."""
		if self.kategoriya:
			kat = frappe.db.get_value(
				"Murojaat Kategoriyasi", self.kategoriya,
				["yonaltirish", "sla_kun"], as_dict=True
			)
			# Kategoriya o'zgargan bo'lsa yo'nalish ham ergashadi; rahbar
			# «Direktorga uzatish» qilganda esa kategoriya bilan birga uzatiladi
			if kat and kat.yonaltirish:
				self.yonaltirildi = kat.yonaltirish
		if not self.yonaltirildi:
			self.yonaltirildi = "CEO"
		if self.masul and not self._rahbarmi(self.masul):
			frappe.throw(
				_("«{0}» — {1} roli biriktirilmagan foydalanuvchi, mas'ul bo'la olmaydi.")
				.format(self.masul, YONALISH_ROL[self.yonaltirildi])
			)

	def _masul_biriktir(self):
		"""Mas'ul bo'sh bo'lsa — yo'nalishdagi rahbarga avtomatik biriktiradi.

		AI ochgan murojaat ham, menejer yo'naltirgani ham EGASIZ qolmaydi:
		yo'nalish aniq bo'lgach (CEO yoki Direktor) aniq odam ham qo'yiladi,
		unga ToDo ochiladi. Rahbarlar hali tayinlanmagan bo'lsa (rol hech kimga
		biriktirilmagan) — bo'sh qoladi, panel «Biriktirilmagan» deb ko'rsatadi."""
		if self.masul or self.holat == "Yopildi":
			return
		self.masul = avto_masul(self.yonaltirildi)

	def _rahbarmi(self, user: str) -> bool:
		rol = YONALISH_ROL.get(self.yonaltirildi)
		roles = {r.lower() for r in frappe.get_roles(user)}
		return bool(rol and ({rol.lower(), "system manager"} & roles))

	def _oquvchi_malumoti(self):
		"""Ism/sinf JONLI o'qiladi — nusxa eskirib ro'yxat bilan karta har xil
		ism ko'rsatmasligi uchun (ism_sync.py dagi qoida bilan bir xil)."""
		if self.student:
			st = frappe.db.get_value(
				"Student", self.student,
				["student_name", "custom_sinf_guruh", "custom_payer_name", "custom_payer_phone"],
				as_dict=True,
			)
			if st:
				self.student_name = st.student_name
				self.sinf = st.custom_sinf_guruh
				self.payer_name = self.payer_name or st.custom_payer_name
				self.payer_phone = self.payer_phone or st.custom_payer_phone
		if self.menejer:
			self.menejer_nomi = frappe.db.get_value("User", self.menejer, "full_name") or self.menejer

	def _muddat(self):
		if self.sla_sana:
			return
		kun = 3
		if self.kategoriya:
			kun = frappe.db.get_value("Murojaat Kategoriyasi", self.kategoriya, "sla_kun")
		# Yuqori muhimlik muddatni qisqartiradi (lekin 1 kundan kam emas)
		kun = int(kun or 0)
		if self.muhimlik == "Yuqori" and kun > 1:
			kun = max(1, kun // 2)
		if kun > 0:
			self.sla_sana = add_days(str(self.ochilgan or nowdate())[:10], kun)

	# -------------------------------------------------------------- yechim
	def _yechim_nazorati(self):
		"""Qaror yozilsa holat avtomatik keyingi qadamga o'tadi.

		Yechim matnisiz yopib bo'lmaydi: «qanday hal qildingiz» savoliga javob
		qolmasa butun modulning ma'nosi yo'qoladi."""
		eski = self.get_doc_before_save()

		if self.yechim_turi and not (self.yechim or "").strip():
			frappe.throw(_("Qaror qabul qilindi — «Qanday hal qilindi» maydoni majburiy."))

		# Qaror yangi yozildi
		if self.yechim_turi and not (eski and eski.yechim_turi):
			self.yechim_kim = self.yechim_kim or frappe.session.user
			self.yechim_vaqti = self.yechim_vaqti or now_datetime()
			if self.holat in ("Yangi", "Ko'rib chiqilmoqda"):
				self.holat = (
					"Yopildi" if self.yechim_turi in XABARSIZ_YOPILADI
					else "Ota-onaga xabar berish"
				)

		if self.holat == "Yopildi":
			if not self.yechim_turi:
				frappe.throw(_("Yopish uchun «Qaror» va «Qanday hal qilindi» to'ldirilishi shart."))
			if self.yechim_turi not in XABARSIZ_YOPILADI and not self.xabar_berildi:
				frappe.throw(
					_("Ota-onaga xabar berilmagan. Avval ota-onaga javob bering "
					  "(«Ota-onaga xabar berildi» tugmasi), keyin yopiladi.")
				)
			self.yopilgan_sana = self.yopilgan_sana or nowdate()
		else:
			self.yopilgan_sana = None

	def _biriktir(self):
		"""Mas'ul tayinlansa ToDo ochiladi — rahbarga qo'ng'iroqcha ko'rinadi."""
		if not self.masul or self.holat == "Yopildi":
			return
		bor = frappe.db.exists(
			"ToDo",
			{"reference_type": "Murojaat", "reference_name": self.name,
			 "allocated_to": self.masul, "status": "Open"},
		)
		if bor:
			return
		frappe.get_doc({
			"doctype": "ToDo",
			"allocated_to": self.masul,
			"reference_type": "Murojaat",
			"reference_name": self.name,
			"date": self.sla_sana,
			"priority": {"Yuqori": "High", "O'rta": "Medium", "Past": "Low"}.get(self.muhimlik, "Medium"),
			"description": f"{self.turi}: {self.student_name or '—'} ({self.sinf or '—'}) — {(self.matn or '')[:180]}",
		}).insert(ignore_permissions=True)


# =========================================================== yordamchilar
def izoh_qosh(doc, matn: str, turi: str = "Komment", kim: str | None = None) -> None:
	"""Timeline'ga qator qo'shadi (hujjat saqlanishini chaqiruvchi hal qiladi)."""
	kim = kim or frappe.session.user
	doc.append("izohlar", {
		"vaqt": now_datetime(),
		"kim": kim,
		"kim_nomi": frappe.db.get_value("User", kim, "full_name") or kim,
		"turi": turi,
		"matn": matn,
	})


def avto_masul(yonalish: str) -> str | None:
	"""Shu yo'nalish uchun MAS'UL rahbar. Tartib:
	  1) «Murojaat Sozlamalari» dagi standart rahbar (aniq ko'rsatilgan);
	  2) o'sha rolli YAGONA faol foydalanuvchi (sozlama shart emas);
	  3) bir nechta bo'lsa — eng kam ochiq murojaati bori (yuk muvozanati).

	Nega 3-qadam bor: "egasiz murojaat" — modulning eng xavfli holati.
	Hamma ko'radigan, lekin hech kim javob bermaydigan navbat paydo bo'lmasligi
	uchun tizim aniq odamni tanlaydi; rahbar keyin o'zi boshqasiga uzatadi.
	"""
	s = sozlamalar()
	if not s.get("avto_biriktir"):
		return None
	standart = s.get("standart_ceo" if yonalish == "CEO" else "standart_direktor")
	if standart and frappe.db.get_value("User", standart, "enabled"):
		return standart

	nomzodlar = rahbarlar(yonalish)
	if not nomzodlar:
		return None
	if len(nomzodlar) == 1:
		return nomzodlar[0]

	yuk = {u: 0 for u in nomzodlar}
	for r in frappe.get_all(
		"Murojaat",
		filters={"masul": ["in", nomzodlar], "holat": ["!=", "Yopildi"]},
		fields=["masul", "count(name) as soni"],
		group_by="masul",
	):
		yuk[r.masul] = r.soni
	# Teng bo'lsa — alifbo tartibi: natija takrorlanadigan bo'lsin
	return min(sorted(nomzodlar), key=lambda u: yuk.get(u, 0))


def sozlamalar() -> dict:
	"""Single hujjat, keshlanadi (har murojaatda o'qib o'tirmaslik uchun)."""
	kesh = frappe.cache().get_value("murojaat_sozlamalari")
	if kesh is None:
		if frappe.db.exists("DocType", "Murojaat Sozlamalari"):
			d = frappe.get_cached_doc("Murojaat Sozlamalari")
			kesh = {
				"avto_biriktir": int(d.avto_biriktir or 0),
				"standart_ceo": d.standart_ceo,
				"standart_direktor": d.standart_direktor,
			}
		else:
			kesh = {"avto_biriktir": 1, "standart_ceo": None, "standart_direktor": None}
		frappe.cache().set_value("murojaat_sozlamalari", kesh)
	return kesh


def rahbarlar(yonalish: str) -> list[str]:
	"""Shu yo'nalishdagi faol rahbar userlari."""
	rol = YONALISH_ROL.get(yonalish)
	if not rol:
		return []
	nomlar = frappe.get_all(
		"Has Role", filters={"role": rol, "parenttype": "User"}, pluck="parent"
	)
	if not nomlar:
		return []
	return frappe.get_all(
		"User", filters={"name": ["in", nomlar], "enabled": 1}, pluck="name"
	)
