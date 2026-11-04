# Copyright (c) 2026, Target Zenit
"""Murojaat amallari — qarzdorlik paneli, rahbar paneli va sotuv nazoratidan
chaqiriladigan yagona nuqta.

Nega bitta modul: "yo'naltirish" uch joyda bor (qo'ng'iroq natijasi modali,
karta tugmasi, AI avtomatikasi) — logika bitta joyda bo'lmasa uchta xil
xatti-harakat paydo bo'ladi.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate

from target_zenit.target_zenit.doctype.murojaat.murojaat import (
	ROL_CEO,
	ROL_DIREKTOR,
	izoh_qosh,
)

YOPIQ = ("Yopildi",)
SOTUV_ROLLAR = {"sales manager", "sales user", "sotuv meneger"}

# FAQAT KUZATUVCHI rollar: hamma murojaatni ko'radi (ikki yo'nalishni ham),
# lekin hech narsa yozmaydi — na izoh, na qaror, na yo'naltirish.
# Nazorat/hisobot uchun: investor va operator "nima bo'lyapti" ni ko'rishi
# kerak, lekin masalaning egasi emas (2026-11-04 qoidasi).
KUZATUV_ROLLAR = {"investor", "xojakbar_operator", "nigora_moliya"}


# ============================================================ rol / ko'rish
def rolim() -> dict:
	"""Joriy foydalanuvchi murojaat tizimida kim: rahbarmi, sotuvchimi, ikkalasi?"""
	roles = {r.lower() for r in frappe.get_roles()}
	admin = bool({"system manager"} & roles)
	ceo = admin or ROL_CEO.lower() in roles
	direktor = admin or ROL_DIREKTOR.lower() in roles
	sotuv = bool(roles & SOTUV_ROLLAR)
	kuzatuv = bool(roles & KUZATUV_ROLLAR)
	return {
		"admin": 1 if admin else 0,
		"ceo": 1 if ceo else 0,
		"direktor": 1 if direktor else 0,
		"sotuv": 1 if sotuv else 0,
		# Faqat kuzatuvchi (yozish huquqisiz) — UI tugmalarni yashiradi
		"kuzatuv": 1 if (kuzatuv and not (ceo or direktor or sotuv)) else 0,
		"yozish": 1 if (ceo or direktor or sotuv) else 0,
		# Ikki yo'nalishni ham ko'radigan odam: admin, ikki rol birga yoki
		# kuzatuvchi (nazorat butun manzarani ko'rishi kerak)
		"hammasi": 1 if (admin or (ceo and direktor) or (kuzatuv and not sotuv)) else 0,
		"yonalishlar": [y for y, bor in (("CEO", ceo), ("Direktor", direktor)) if bor],
		"user": frappe.session.user,
	}


def _guard():
	"""O'QISH ruxsati. Yozish uchun alohida `_yozish_guard()` bor."""
	r = rolim()
	if not (r["ceo"] or r["direktor"] or r["sotuv"] or r["kuzatuv"]):
		frappe.throw(
			_("Ruxsat yo'q. Murojaatlar paneli uchun CEO, Direktor yoki sotuv roli kerak."),
			frappe.PermissionError,
		)
	return r


def _yozish_guard(r: dict | None = None) -> dict:
	"""Faqat kuzatuvchi (investor, operator, moliya) hech narsa yozmaydi.
	Server tomonda to'siq: UI tugmasi yashirin bo'lsa ham API chaqirilsa
	o'tib ketmasligi kerak."""
	r = r or rolim()
	if not r["yozish"]:
		frappe.throw(
			_("Sizda faqat ko'rish ruxsati bor — murojaatga yozib bo'lmaydi."),
			frappe.PermissionError,
		)
	return r


def _yonalish_filtri(r: dict) -> dict:
	"""Rahbar FAQAT o'ziga tegishli yo'nalishni ko'radi. Sotuvchi esa o'zi
	yo'naltirganlarini — "yuborgan murojaatim nima bo'ldi" savoliga javob."""
	if r["hammasi"]:
		return {}
	if r["ceo"] or r["direktor"]:
		return {"yonaltirildi": ["in", r["yonalishlar"]]}
	return {"menejer": frappe.session.user}


def _koradi(doc, r: dict) -> bool:
	"""Shu hujjatni ko'rish huquqi bormi (filtr bilan bir xil mantiq)."""
	if r["hammasi"]:
		return True
	if (r["ceo"] or r["direktor"]) and doc.yonaltirildi in r["yonalishlar"]:
		return True
	# Sotuvchi o'zi yuborganini ko'radi
	return doc.menejer == frappe.session.user


# ================================================================ kategoriya
def kategoriyalar(faqat_faol: bool = True) -> list[dict]:
	kesh = frappe.cache().get_value("murojaat_kategoriyalar")
	if kesh is None:
		kesh = frappe.get_all(
			"Murojaat Kategoriyasi",
			fields=["name", "nomi", "yonaltirish", "turi_tavsiya", "sla_kun",
			        "kalit_sozlar", "faol"],
			order_by="yonaltirish, nomi",
			limit_page_length=0,
		)
		frappe.cache().set_value("murojaat_kategoriyalar", kesh)
	return [k for k in kesh if k.get("faol")] if faqat_faol else list(kesh)


def kategoriya_top(matn: str) -> str | None:
	"""Matndagi kalit so'z bo'yicha kategoriya. Topilmasa None — chaqiruvchi
	«Aniqlanmagan» ga tushiradi (javobsiz qolmasligi uchun)."""
	past = (matn or "").lower()
	if not past:
		return None
	eng_yaxshi, eng_uzun = None, 0
	for k in kategoriyalar():
		for soz in (k.get("kalit_sozlar") or "").split(","):
			soz = soz.strip().lower()
			# Uzunroq moslik ustun: "o'qituvchi ustidan shikoyat" > "dars"
			if soz and soz in past and len(soz) > eng_uzun:
				eng_yaxshi, eng_uzun = k["name"], len(soz)
	return eng_yaxshi


# Kalit so'z ham, kategoriya ham topilmaganda: murojaat EGASIZ qolmasin
ZAXIRA_KAT = {"Direktor": "Aniqlanmagan - o'quv", "CEO": "Aniqlanmagan - tashkiliy"}


def _zaxira_kategoriya(yonaltirildi: str | None) -> str | None:
	nomi = ZAXIRA_KAT.get(yonaltirildi or "CEO")
	return nomi if nomi and frappe.db.exists("Murojaat Kategoriyasi", nomi) else None


# ================================================================ yaratish
def murojaat_yarat(
	matn: str,
	turi: str = "Shikoyat",
	kategoriya: str | None = None,
	student: str | None = None,
	qarz_ishi: str | None = None,
	aloqa_yozuvi: str | None = None,
	telefon_qongirogi: str | None = None,
	yonaltirildi: str | None = None,
	muhimlik: str = "O'rta",
	manba: str = "Menejer",
	menejer: str | None = None,
	suhbat_vaqti=None,
	payer_name: str | None = None,
	payer_phone: str | None = None,
	izoh: str | None = None,
	ignore_permissions: bool = False,
) -> str:
	"""Bitta yo'naltirish nuqtasi — hamma joy shu funksiyadan o'tadi."""
	matn = (matn or "").strip()
	if not matn:
		frappe.throw(_("Murojaat matni bo'sh bo'lishi mumkin emas."))

	if not kategoriya:
		kategoriya = kategoriya_top(matn) or _zaxira_kategoriya(yonaltirildi)

	# Qarz ishidan o'quvchi/to'lovchi kontekstini olib qo'yamiz — rahbar
	# "kim murojaat qilyapti" ni qidirib yurmasligi kerak
	if qarz_ishi and not student:
		qi = frappe.db.get_value(
			"Qarz Ishi", qarz_ishi, ["student", "payer_name", "payer_phone"], as_dict=True
		)
		if qi:
			student = qi.student
			payer_name = payer_name or qi.payer_name
			payer_phone = payer_phone or qi.payer_phone

	doc = frappe.get_doc({
		"doctype": "Murojaat",
		"turi": turi or "Shikoyat",
		"kategoriya": kategoriya,
		"muhimlik": muhimlik or "O'rta",
		"yonaltirildi": yonaltirildi,
		"holat": "Yangi",
		"matn": matn,
		"student": student,
		"payer_name": payer_name,
		"payer_phone": payer_phone,
		"qarz_ishi": qarz_ishi,
		"manba": manba,
		"menejer": menejer or frappe.session.user,
		"suhbat_vaqti": suhbat_vaqti,
		"aloqa_yozuvi": aloqa_yozuvi,
		"telefon_qongirogi": telefon_qongirogi,
	})
	izoh_qosh(
		doc,
		izoh or f"Yo'naltirildi ({manba})",
		turi="Yo'naltirish",
		kim=menejer or frappe.session.user,
	)
	doc.insert(ignore_permissions=ignore_permissions)

	# Qarz ishida ham iz qolsin: menejer kartani ochganda ko'rinadi
	if qarz_ishi:
		frappe.get_doc("Qarz Ishi", qarz_ishi).add_comment(
			"Info",
			f"Rahbarga yo'naltirildi: {doc.name} ({doc.yonaltirildi}) — "
			f"{doc.kategoriya or 'kategoriya yo‘q'}: {matn[:160]}",
		)
	return doc.name


@frappe.whitelist()
def yonaltir(payload):
	"""Qarzdorlik panelidan «Rahbarga yo'naltirish»."""
	_guard()
	if isinstance(payload, str):
		payload = json.loads(payload)

	ruxsat = {
		"matn", "turi", "kategoriya", "student", "qarz_ishi", "aloqa_yozuvi",
		"telefon_qongirogi", "yonaltirildi", "muhimlik", "suhbat_vaqti",
	}
	kwargs = {k: v for k, v in payload.items() if k in ruxsat and v not in (None, "")}
	kwargs.setdefault("manba", payload.get("manba") or "Menejer")
	name = murojaat_yarat(**kwargs)
	doc = frappe.db.get_value(
		"Murojaat", name, ["name", "yonaltirildi", "kategoriya", "sla_sana", "turi"], as_dict=True
	)
	return doc


@frappe.whitelist()
def kategoriya_royxati():
	"""Modal uchun: kategoriya -> yo'nalish xaritasi (UI kimga ketishini
	darhol ko'rsatadi, menejer taxmin qilib o'tirmaydi)."""
	_guard()
	return kategoriyalar()


# ================================================================== amallar
def _ol(name: str, yozish: bool = False):
	r = _guard()
	doc = frappe.get_doc("Murojaat", name)
	if r["hammasi"]:
		return doc, r
	if (r["ceo"] or r["direktor"]) and doc.yonaltirildi in r["yonalishlar"]:
		return doc, r
	# Sotuvchi o'zi yuborganini ko'radi; yozish faqat "ota-onaga xabar" qadami
	if doc.menejer == frappe.session.user:
		return doc, r
	frappe.throw(_("Bu murojaat sizga yo'naltirilmagan."), frappe.PermissionError)


@frappe.whitelist()
def korildi(name: str):
	"""Rahbar kartani ochdi — "ko'rib chiqildimi" savoliga javob shu."""
	doc, r = _ol(name)
	if not (r["ceo"] or r["direktor"]):
		return {"ok": 0}
	ozgardi = False
	if not doc.korildi_vaqti:
		doc.db_set({"korildi_kim": frappe.session.user, "korildi_vaqti": now_datetime()},
		           update_modified=False)
		ozgardi = True
	if doc.holat == "Yangi":
		doc.db_set("holat", "Ko'rib chiqilmoqda", update_modified=False)
		ozgardi = True
	if ozgardi:
		frappe.db.commit()
	return {"ok": 1, "holat": doc.holat}


@frappe.whitelist()
def izoh_yoz(name: str, matn: str):
	"""Komment — rahbar ham, menejer ham yozadi (timeline bitta)."""
	doc, _r = _ol(name)
	matn = (matn or "").strip()
	if not matn:
		frappe.throw(_("Izoh bo'sh."))
	izoh_qosh(doc, matn, turi="Komment")
	if doc.holat == "Yangi":
		doc.holat = "Ko'rib chiqilmoqda"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1, "izohlar": _izohlar(doc), "holat": doc.holat}


@frappe.whitelist()
def qaror_ber(name: str, yechim_turi: str, yechim: str, muhimlik: str | None = None):
	"""Rahbar qarori. Bu qadamdan keyin ish MENEJERGA qaytadi (ota-onaga javob),
	«Ahamiyatsiz» bo'lsa darhol yopiladi."""
	doc, r = _ol(name)
	if not (r["ceo"] or r["direktor"]):
		frappe.throw(_("Qarorni faqat CEO yoki Direktor qabul qiladi."), frappe.PermissionError)
	yechim = (yechim or "").strip()
	if not yechim:
		frappe.throw(_("«Qanday hal qilindi» to'ldirilishi shart."))

	doc.yechim_turi = yechim_turi
	doc.yechim = yechim
	doc.yechim_kim = frappe.session.user
	doc.yechim_vaqti = now_datetime()
	if muhimlik:
		doc.muhimlik = muhimlik
	if not doc.masul:
		doc.masul = frappe.session.user
	izoh_qosh(doc, f"{yechim_turi}: {yechim}", turi="Yechim")
	doc.save(ignore_permissions=True)

	# Menejerga vazifa: ota-onaga javob bering
	if doc.holat == "Ota-onaga xabar berish" and doc.menejer:
		frappe.get_doc({
			"doctype": "ToDo",
			"allocated_to": doc.menejer,
			"reference_type": "Murojaat",
			"reference_name": doc.name,
			"date": nowdate(),
			"priority": "High",
			"description": f"Ota-onaga javob bering ({doc.student_name or '—'}): {yechim[:180]}",
		}).insert(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1, "holat": doc.holat, "izohlar": _izohlar(doc)}


@frappe.whitelist()
def uzat(name: str, yonaltirildi: str, kategoriya: str | None = None, izoh: str | None = None):
	"""«Direktorga uzatish» / «CEO'ga uzatish» — masala boshqa rahbarga tegishli."""
	doc, r = _ol(name)
	if not (r["ceo"] or r["direktor"]):
		frappe.throw(_("Uzatishni faqat rahbar qiladi."), frappe.PermissionError)
	if yonaltirildi not in ("CEO", "Direktor"):
		frappe.throw(_("Yo'nalish faqat CEO yoki Direktor bo'ladi."))

	eski = doc.yonaltirildi
	# Kategoriya yo'nalishni belgilaydi — uzatishda ikkisi mos kelishi kerak,
	# aks holda validate qaytarib yuboradi
	if kategoriya:
		doc.kategoriya = kategoriya
	elif frappe.db.get_value("Murojaat Kategoriyasi", doc.kategoriya, "yonaltirish") != yonaltirildi:
		doc.kategoriya = None
	doc.yonaltirildi = yonaltirildi
	doc.masul = None
	izoh_qosh(
		doc,
		f"{eski} -> {yonaltirildi}" + (f": {izoh}" if izoh else ""),
		turi="Yo'naltirish",
	)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1, "yonaltirildi": doc.yonaltirildi, "kategoriya": doc.kategoriya}


@frappe.whitelist()
def xabar_berdim(name: str, matn: str | None = None):
	"""Menejer ota-onaga javobni aytdi — halqa yopiladi."""
	doc, _r = _ol(name)
	if doc.holat != "Ota-onaga xabar berish":
		frappe.throw(_("Avval rahbar qarori kerak — hozir bu qadam emas."))
	doc.xabar_berildi = 1
	doc.xabar_kim = frappe.session.user
	doc.xabar_vaqti = now_datetime()
	doc.xabar_matni = (matn or "").strip() or None
	doc.holat = "Yopildi"
	izoh_qosh(doc, (matn or "Ota-onaga xabar berildi"), turi="Ota-onaga xabar")
	doc.save(ignore_permissions=True)
	for todo in frappe.get_all(
		"ToDo",
		filters={"reference_type": "Murojaat", "reference_name": doc.name, "status": "Open"},
		pluck="name",
	):
		frappe.db.set_value("ToDo", todo, "status", "Closed")
	frappe.db.commit()
	return {"ok": 1, "holat": doc.holat, "izohlar": _izohlar(doc)}


@frappe.whitelist()
def masul_biriktir(name: str, masul: str):
	"""Rahbar murojaatni o'ziga (yoki boshqa rahbarga) biriktiradi."""
	doc, r = _ol(name)
	if not (r["ceo"] or r["direktor"]):
		frappe.throw(_("Biriktirishni faqat rahbar qiladi."), frappe.PermissionError)
	doc.masul = masul
	izoh_qosh(doc, f"Mas'ul: {frappe.db.get_value('User', masul, 'full_name') or masul}",
	          turi="Yo'naltirish")
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1, "masul": doc.masul}


def _izohlar(doc) -> list[dict]:
	return [
		{"vaqt": str(i.vaqt), "kim": i.kim, "kim_nomi": i.kim_nomi,
		 "turi": i.turi, "matn": i.matn}
		for i in doc.izohlar
	]


# ====================================================== boshqa panellar uchun
def ochiq_murojaatlar(studentlar) -> dict:
	"""student -> ochiq murojaatlar ro'yxati (qarzdorlik kartasi uchun).

	Menejer kartani ochganda "bu masala allaqachon yo'naltirilgan" ko'rinsin —
	bitta shikoyat uchun uch marta murojaat ochilmasligi kerak."""
	if isinstance(studentlar, str):
		studentlar = [studentlar]
	studentlar = [s for s in studentlar if s]
	if not studentlar:
		return {}
	rows = frappe.get_all(
		"Murojaat",
		filters={"student": ["in", studentlar]},
		fields=["name", "student", "turi", "kategoriya", "yonaltirildi", "holat",
		        "muhimlik", "matn", "yechim_turi", "yechim", "sla_sana", "ochilgan",
		        "masul", "korildi_vaqti", "yopilgan_sana"],
		order_by="ochilgan desc",
		limit_page_length=0,
	)
	out: dict[str, list] = {}
	for r in rows:
		out.setdefault(r.student, []).append(r)
	return out


def qongiroq_murojaatlari(qongiroqlar) -> dict:
	"""Telefon Qongirogi -> murojaat holati (sotuv nazorati takliflar jadvali)."""
	nomlar = [q for q in (qongiroqlar or []) if q]
	if not nomlar:
		return {}
	rows = frappe.get_all(
		"Murojaat",
		filters={"telefon_qongirogi": ["in", nomlar]},
		fields=["name", "telefon_qongirogi", "turi", "kategoriya", "yonaltirildi",
		        "holat", "masul", "yechim_turi", "yechim", "korildi_vaqti",
		        "sla_sana", "yopilgan_sana"],
		limit_page_length=0,
	)
	out = {}
	for r in rows:
		# Bitta qo'ng'iroqdan bir nechta murojaat bo'lsa — oxirgisi ko'rsatiladi
		out.setdefault(r.telefon_qongirogi, r)
	return out
