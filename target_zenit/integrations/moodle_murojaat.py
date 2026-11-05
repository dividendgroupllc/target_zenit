# Copyright (c) 2026, Target Zenit
# Frappe <-> Moodle: ota-ona murojaatlari (shikoyat / taklif / muammo).
#
# EGALIK TAQSIMOTI (2026-11-04 qarori, MUROJAAT_ARXITEKTURA.md):
#   * murojaatning TUG'ILISHI — Frappe: kim qachon gaplashdi, kim shikoyat
#     qildi, nima dedi (qo'ng'iroq yozuvi va AI tahlili shu yerda);
#   * murojaatning YURITILISHI — Moodle: CEO, direktor va zavuch ko'radi,
#     komment yozadi, QAROR qabul qiladi (ilovada ham ishlaydi);
#   * ota-onaga yetkazish — Moodle: javob bolasining akkauntiga bildirishnoma
#     bo'lib boradi (Moodle'da ota-ona akkaunti yo'q, u bolasining logini
#     bilan kiradi);
#   * Frappe panellarida KO'RSATISH — bu modul javoblarni qaytarib oladi
#     (investor paneli, sotuv nazorati va qarzdorlik paneli uchun).
#
# Shuning uchun IKKI TOMONLAMA YOZISH YO'Q: har maydonning bitta egasi bor.
# `push` faqat manba maydonlarini yuboradi, `pull` faqat yuritish maydonlarini
# qaytarib oladi. Moodle hech qachon Frappeni chaqirmaydi — token faqat Frappe
# tomonda saqlanadi.
#
# BOG'LANISH (unikal ID qoidasi): Student.name -> user.idnumber,
# Employee.name -> user.idnumber, Murojaat.name -> _murojaat.frappename.
# Ism yoki email bo'yicha hech qachon qidirilmaydi.

from __future__ import annotations

import frappe
from frappe.utils import cint, get_datetime, getdate, now_datetime

from target_zenit.integrations.moodle import MoodleError, _call, _settings

# Bitta so'rovda nechta murojaat. Moodle REST so'rovni forma maydonlari
# ko'rinishida oladi: har murojaat ~17 maydonga yoyiladi, PHP
# `max_input_vars` = 5000. 120 x 17 = 2040 — zaxirasi bilan xavfsiz.
BATCH = 120

# Yopilgan murojaat ham bir marta yuboriladi (Moodle'da yo'q bo'lsa), lekin
# keyin tegilmaydi: Moodle yopilganning manbasini qayta yozmaydi.
YUBORILADI_HOLAT = ("Yangi", "Ko'rib chiqilmoqda", "Ota-onaga xabar berish", "Yopildi")

KURSOR = "moodle_murojaat_kursor"      # Moodle'dan oxirgi olingan timemodified


def _ts(qiymat) -> int:
	"""Frappe datetime -> unix. Bo'sh bo'lsa 0."""
	if not qiymat:
		return 0
	try:
		return int(get_datetime(qiymat).timestamp())
	except Exception:
		return 0


def _idnumber(user: str | None) -> str:
	"""Frappe User -> Employee.name (Moodle `user.idnumber` shu qiymat).

	Murojaat maydonlari User'ga ishora qiladi, Moodle akkaunti esa Employee
	orqali yaratiladi. Employee yozuvi bo'lmagan xodim (masalan hali kadrlarga
	kirmagan) uchun bo'sh qaytadi — Moodle qatorni saqlaydi, lekin
	`manageruserid = 0` bo'lib qoladi va panel buni ko'rsatadi."""
	if not user:
		return ""
	return frappe.db.get_value("Employee", {"user_id": user}, "name") or ""


# =============================================================== YUBORISH
def _qatorlar(nomlar=None, limit: int = 0) -> list[dict]:
	"""Moodle'ga yuboriladigan murojaatlar (manba maydonlari)."""
	filtr = {"holat": ["in", list(YUBORILADI_HOLAT)]}
	if nomlar:
		filtr = {"name": ["in", list(nomlar)]}

	rows = frappe.get_all(
		"Murojaat",
		filters=filtr,
		fields=[
			"name", "turi", "kategoriya", "yonaltirildi", "muhimlik", "matn",
			"student", "student_name", "sinf", "payer_name", "payer_phone",
			"menejer", "menejer_nomi", "manba", "suhbat_vaqti", "ochilgan",
			"sla_sana",
		],
		order_by="ochilgan desc",
		limit_page_length=cint(limit) or 0,
	)
	out = []
	for r in rows:
		out.append({
			"frappename": r.name,
			"turi": r.turi or "Shikoyat",
			"kategoriya": r.kategoriya or "",
			# Yo'nalish Moodle'da RUXSATNI belgilaydi: CEO yoki Direktor
			# capability'si shu qiymat bo'yicha tekshiriladi.
			"yonalish": r.yonaltirildi or "CEO",
			"muhimlik": r.muhimlik or "O'rta",
			"matn": r.matn or "",
			"studentidnumber": r.student or "",
			"studentname": r.student_name or "",
			"sinf": r.sinf or "",
			"payername": r.payer_name or "",
			"payerphone": r.payer_phone or "",
			"manageridnumber": _idnumber(r.menejer),
			"managername": r.menejer_nomi or "",
			"manba": r.manba or "",
			"suhbatvaqti": _ts(r.suhbat_vaqti),
			"ochilgan": _ts(r.ochilgan),
			"slasana": _ts(r.sla_sana),
		})
	return out


def push(nomlar=None, limit: int = 0, trigger: str = "Qo'lda") -> dict:
	"""Murojaatlarni Moodle'ga yuboradi (bo'laklab)."""
	s = _settings()
	if not cint(s.enabled):
		return {"holat": "o'chirilgan"}

	qatorlar = _qatorlar(nomlar, limit)
	if not qatorlar:
		return {"holat": "yuborilmadi", "sabab": "murojaat yo'q"}

	jami = {"yangi": 0, "yangilandi": 0, "otkazildi": 0}
	akkauntsiz: set[str] = set()
	xato = None

	for i in range(0, len(qatorlar), BATCH):
		bolak = qatorlar[i:i + BATCH]
		try:
			res = _call("local_targetzenit_push_murojaat", {"rows": bolak})
		except MoodleError as e:
			xato = str(e)
			frappe.log_error(xato, "Moodle murojaat push")
			break
		if isinstance(res, dict):
			for k in jami:
				jami[k] += cint(res.get(k))
			akkauntsiz.update(res.get("akkauntsiz") or [])

	natija = {
		"holat": "xato" if xato else "tayyor",
		"yuborildi": len(qatorlar),
		**jami,
		"akkauntsiz": sorted(akkauntsiz),
		"trigger": trigger,
	}
	if xato:
		natija["xato"] = xato[:500]
	return natija


# ============================================================== OLIB KELISH
def pull(limit: int = 200, qayta: int = 0) -> dict:
	"""Moodle'dagi rahbar qarorlarini Frappe nusxasiga ko'chiradi.

	FAQAT KO'RSATISH uchun: `/app/murojaatlar`, sotuv nazorati va qarzdorlik
	panellarida "kimga biriktirilgan, qanday hal qilindi, ko'rib chiqildimi"
	ustunlari shundan to'ladi. Frappe bu maydonlarni o'zi o'zgartirmaydi —
	egasi Moodle.

	`qayta=1` kursorni nolga tushiradi (hammasini qaytadan oladi).
	"""
	s = _settings()
	if not cint(s.enabled):
		return {"holat": "o'chirilgan"}

	since = 0 if cint(qayta) else cint(frappe.db.get_default(KURSOR) or 0)
	olindi = yangilandi = 0
	topilmadi = []
	yana = 1
	aylanish = 0

	while yana and aylanish < 20:      # 20 x 200 = 4000 qator — yetarli chegara
		aylanish += 1
		try:
			res = _call("local_targetzenit_get_murojaat",
			            {"since": since, "limit": cint(limit)})
		except MoodleError as e:
			frappe.log_error(str(e), "Moodle murojaat pull")
			return {"holat": "xato", "xato": str(e)[:500], "olindi": olindi}

		rows = (res or {}).get("rows") or []
		yana = cint((res or {}).get("yana"))
		yangi_kursor = cint((res or {}).get("since")) or since

		for r in rows:
			olindi += 1
			if _nusxaga_yoz(r):
				yangilandi += 1
			else:
				topilmadi.append(r.get("frappename"))

		# Kursor FAQAT muvaffaqiyatli bo'lakdan keyin saqlanadi: xato bo'lsa
		# keyingi yurishda o'sha joydan davom etadi, qator yo'qolmaydi.
		if yangi_kursor > since:
			since = yangi_kursor
			frappe.db.set_default(KURSOR, since)
		if not rows:
			break

	frappe.db.commit()
	return {
		"holat": "tayyor", "olindi": olindi, "yangilandi": yangilandi,
		"kursor": since, "topilmadi": topilmadi[:20],
	}


# Moodle holati -> Frappe holati. Frappe'dagi «Ota-onaga xabar berish» qadami
# Moodle'da YO'Q: ota-ona javobni ilovada o'zi ko'radi, shuning uchun Moodle
# qaror bilan darhol yopadi.
HOLAT_MAP = {
	"Yangi": "Yangi",
	"Ko'rib chiqilmoqda": "Ko'rib chiqilmoqda",
	"Yopildi": "Yopildi",
}


def _nusxaga_yoz(r: dict) -> bool:
	"""Bitta qatorni Frappe'dagi Murojaat hujjatiga yozadi. False = topilmadi."""
	nom = r.get("frappename")
	if not nom or not frappe.db.exists("Murojaat", nom):
		return False

	masul = None
	idn = (r.get("masul") or "").strip()
	if idn:
		masul = frappe.db.get_value("Employee", idn, "user_id")

	qiymat = {
		"holat": HOLAT_MAP.get(r.get("holat") or "", "Ko'rib chiqilmoqda"),
		"yonaltirildi": r.get("yonalish") or "CEO",
		"korildi_vaqti": _dt(r.get("korildivaqti")),
		"yechim_turi": r.get("qarorturi") or None,
		"yechim": r.get("qaror") or None,
		"yechim_vaqti": _dt(r.get("qarorvaqti")),
		"moodle_izoh_soni": cint(r.get("izohsoni")),
		"moodle_qaror_kim": r.get("qarorism") or None,
		"moodle_otaona_kordi": _dt(r.get("otaonakordi")),
	}
	if masul:
		qiymat["masul"] = masul
	if qiymat["holat"] == "Yopildi":
		yop = _dt(r.get("yopilganvaqti"))
		qiymat["yopilgan_sana"] = getdate(yop) if yop else None
		# Ota-ona javobni ILOVADA ko'radi — menejerning qo'ng'irog'i shart
		# emas, shuning uchun "xabar berildi" belgisi Moodle ko'rganidan
		# yoki qarorning o'zidan kelib chiqadi (aks holda Frappe validate
		# yopishga ruxsat bermaydi).
		qiymat["xabar_berildi"] = 1
		if qiymat["moodle_otaona_kordi"]:
			qiymat["xabar_vaqti"] = qiymat["moodle_otaona_kordi"]

	# `db_set` emas, to'g'ridan-to'g'ri UPDATE: Murojaat.validate ichida
	# yopish uchun shartlar bor (yechim matni, ota-onaga xabar) va ular
	# Moodle'da allaqachon bajarilgan. Hujjat orqali saqlash bu shartlarni
	# qaytadan tekshirib, Moodle'dan kelgan haqiqatni rad etardi.
	frappe.db.set_value("Murojaat", nom, qiymat, update_modified=False)
	return True


def _dt(ts) -> str | None:
	from datetime import datetime

	ts = cint(ts)
	if not ts:
		return None
	return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ================================================================ jadval
def on_murojaat_insert(doc, method=None):
	"""Yangi murojaat darhol Moodle'ga. Navbatda bajariladi: Moodle javob
	bermasa yoki sekin bo'lsa, murojaat yaratish (sotuvchining ishi) shu
	sababli to'xtab qolmasligi kerak."""
	s = _settings()
	if not cint(s.enabled):
		return
	frappe.enqueue(
		"target_zenit.integrations.moodle_murojaat.push",
		queue="short", timeout=300, enqueue_after_commit=True,
		job_name=f"moodle_murojaat:{doc.name}",
		nomlar=[doc.name], trigger="Yangi murojaat",
	)


def pull_cron():
	"""Cron uchun o'ram: sozlama o'chirilgan bo'lsa jim qaytadi."""
	if not cint(_settings().enabled):
		return
	pull()


def daily_sync():
	"""Kunlik: yangi murojaatlarni yuborish + javoblarni olib kelish."""
	sync(trigger="Jadval")


def sync(trigger: str = "Jadval") -> dict:
	"""Ikki yo'nalish birga: avval yuborish, keyin olib kelish.

	Tartib muhim: yangi murojaat Moodle'ga tushmasdan uning javobi ham
	bo'lmaydi, shuning uchun push birinchi."""
	natija = {"push": push(trigger=trigger), "pull": pull()}
	return natija


@frappe.whitelist()
def sync_now(limit: int = 0) -> dict:
	frappe.only_for(("System Manager", "Sales Manager", "CEO", "Direktor"))
	return {"push": push(limit=cint(limit), trigger="Qo'lda"), "pull": pull()}


@frappe.whitelist()
def preview(limit: int = 5) -> dict:
	"""Nima yuboriladi — so'rov qilmasdan ko'rish (nosozlik izlash uchun)."""
	frappe.only_for(("System Manager", "Sales Manager"))
	qatorlar = _qatorlar(limit=cint(limit))
	return {
		"soni": frappe.db.count("Murojaat", {"holat": ["in", list(YUBORILADI_HOLAT)]}),
		"kursor": cint(frappe.db.get_default(KURSOR) or 0),
		"namuna": qatorlar,
		# Employee yozuvi yo'q menejerlar — Moodle'da bog'lanmaydi
		"employeesiz": sorted({
			q["managername"] or "—" for q in qatorlar if not q["manageridnumber"]
		}),
	}
