# Copyright (c) 2026, Target Zenit
# Frappe <-> Moodle: ota-ona murojaatlari (shikoyat / taklif / muammo).
#
# EGALIK TAQSIMOTI (2026-11-26 da QAYTA KO'RILDI, MUROJAAT_ARXITEKTURA.md):
#   * murojaatning TUG'ILISHI — Frappe: kim qachon gaplashdi, kim shikoyat
#     qildi, nima dedi (qo'ng'iroq yozuvi va AI tahlili shu yerda);
#   * YURITILISHI — IKKI TOMONDA HAM: CEO/Direktor qaror va izohni Frappe
#     panelida ham, Moodle'da ham yoza oladi (2026-11-26 qarori: rahbarlar
#     amalda Frappe'da ishlayapti, 2026-11-04 dagi "faqat Moodle" taqsimoti
#     prodda ishlamadi — qarorlar pull tomonidan o'chirilib ketayotgan edi);
#   * ota-onaga yetkazish — Moodle: javob bolasining akkauntiga bildirishnoma
#     bo'lib boradi (Frappe'da yozilgan qaror ham push orqali Moodle'ga
#     yetib borib, bildirishnoma o'sha yerdan ketadi);
#   * Frappe panellarida KO'RSATISH — pull javoblarni qaytarib oladi
#     (investor paneli, sotuv nazorati va qarzdorlik paneli uchun).
#
# ZIDDIYAT QOIDASI (ikki tomonlama yozishda): BIRINCHI yozilgan qaror g'olib.
#   * push qarorni Moodle'ga faqat Moodle'da hali qaror YO'Q bo'lsa yozadi;
#   * pull qarorni Frappe'ga faqat Frappe'da hali qaror YO'Q bo'lsa yozadi;
#   * holat hech qachon ORQAGA qaytmaydi (Yopildi -> Yangi bo'lmaydi) —
#     `_nusxaga_yoz` dagi HOLAT_DARAJA shuni kafolatlaydi.
# Izohlar esa qo'shilib boradi (append-only): dublikat `frappeid` /
# `moodle_id` belgilari bilan to'siladi, hech qaysi tomon o'chirmaydi.
#
# BOG'LANISH (unikal ID qoidasi): Student.name -> user.idnumber,
# Employee.name -> user.idnumber, Murojaat.name -> _murojaat.frappename.
# Ism yoki email bo'yicha hech qachon qidirilmaydi.

from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, nowdate

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
def _qarz_holati(studentlar) -> dict:
	"""student -> {summa, holat, kechikish}. Ochiq qarz ishidan.

	Rahbar qaror qabul qilishdan oldin oilaning qarzini ko'rishi kerak:
	chegirma yoki bo'lib to'lash haqidagi qaror shunga bog'liq."""
	studentlar = [s for s in studentlar if s]
	if not studentlar:
		return {}
	out = {}
	for r in frappe.get_all(
		"Qarz Ishi",
		filters={"student": ["in", studentlar],
		         "ishlov_status": ["not in", ("Yopildi - To'landi", "Yopildi - Boshqa")]},
		fields=["student", "qarz_summa", "ishlov_status", "aging_bucket"],
		order_by="qarz_summa desc",
	):
		# Bir o'quvchida bir nechta ochiq ish bo'lsa — kattasi (birinchi keladi)
		out.setdefault(r.student, {
			"summa": flt(r.qarz_summa),
			"holat": r.ishlov_status or "",
			"kechikish": r.aging_bucket or "",
		})
	return out


def _suhbatlar(studentlar, limit_har: int = 15) -> dict:
	"""student -> aloqa tarixi (Aloqa Yozuvi), yangisi tepada.

	«Kim qachon gaplashdi» — foydalanuvchi aynan shuni Moodle'ga ko'chirishni
	so'ragan. Rahbar buni ko'rmasa ota-onaga ikkinchi marta bir xil javob
	beriladi."""
	studentlar = [s for s in studentlar if s]
	if not studentlar:
		return {}
	rows = frappe.db.sql(
		"""SELECT COALESCE(NULLIF(ay.student, ''), qi.student) student,
		          ay.vaqt, ay.kanal, ay.aloqa_natijasi, ay.hisob_natijasi,
		          ay.komment, u.full_name menejer
		     FROM `tabAloqa Yozuvi` ay
		     LEFT JOIN `tabQarz Ishi` qi ON qi.name = ay.qarz_ishi
		     LEFT JOIN `tabUser` u ON u.name = ay.masul
		    WHERE COALESCE(NULLIF(ay.student, ''), qi.student) IN %(st)s
		 ORDER BY ay.vaqt DESC""",
		{"st": tuple(studentlar)},
		as_dict=True,
	)
	out: dict[str, list] = {}
	for r in rows:
		qator = out.setdefault(r.student, [])
		if len(qator) >= limit_har:
			continue
		qator.append({
			"vaqt": _ts(r.vaqt),
			"menejer": r.menejer or "",
			"kanal": r.kanal or "",
			"natija": r.aloqa_natijasi or "",
			"suhbatnatija": r.hisob_natijasi or "",
			"izoh": (r.komment or "")[:500],
		})
	return out


def _frappe_izohlar(nomlar) -> dict:
	"""murojaat -> Frappe'da TUG'ILGAN kommentlar (Moodle'ga yuboriladi).

	Faqat `moodle_id` BO'SH qatorlar: Moodle'dan kelganini qaytarib yuborsak
	aylanish (loop) va dublikat paydo bo'ladi. Faqat «Komment» turi: «Yechim»
	qaror maydonlari bilan alohida ketadi, «Yo'naltirish»/«Holat» esa tizim
	yozuvlari — Moodle o'zinikini o'zi yozadi."""
	if not nomlar:
		return {}
	rows = frappe.get_all(
		"Murojaat Izohi",
		filters={"parenttype": "Murojaat", "parent": ["in", list(nomlar)],
		         "turi": "Komment", "moodle_id": ["in", ("", None)]},
		fields=["name", "parent", "vaqt", "kim", "kim_nomi", "matn"],
		order_by="vaqt asc",
		limit_page_length=0,
	)
	out: dict[str, list] = {}
	for r in rows:
		out.setdefault(r.parent, []).append({
			"frappeid": r.name,
			"vaqt": _ts(r.vaqt),
			"kimidnumber": _idnumber(r.kim),
			"kimname": r.kim_nomi or r.kim or "",
			"matn": (r.matn or "")[:4000],
		})
	return out


def _qatorlar(nomlar=None, limit: int = 0, faqat_ochiq: bool = False) -> list[dict]:
	"""Moodle'ga yuboriladigan murojaatlar (manba + Frappe'da yozilgan qaror/izoh).

	`faqat_ochiq` — davriy sinxron uchun: ochiqlar + QARORI HALI MOODLE'GA
	YETIB BORMAGANLAR (Frappe'da yopilgan, lekin `moodle_qaror_kim` hali bo'sh —
	darhol push o'tmay qolgan bo'lsa cron o'zini-o'zi tuzatadi)."""
	if nomlar:
		filtr = {"name": ["in", list(nomlar)]}
	elif faqat_ochiq:
		ochiq = frappe.get_all(
			"Murojaat", filters={"holat": ["in", [h for h in YUBORILADI_HOLAT if h != "Yopildi"]]},
			pluck="name", limit_page_length=0,
		)
		# Frappe qarori Moodle'da hali aks etmaganlar (oxirgi 30 kun — eski
		# arxivni har 15 daqiqada titkilamaslik uchun)
		qarorli = frappe.get_all(
			"Murojaat",
			filters={"yechim_turi": ["is", "set"], "moodle_qaror_kim": ["is", "not set"],
			         "yechim_vaqti": [">", add_days(nowdate(), -30)]},
			pluck="name", limit_page_length=0,
		)
		nomlar = list(dict.fromkeys(ochiq + qarorli))
		if not nomlar:
			return []
		filtr = {"name": ["in", nomlar]}
	else:
		filtr = {"holat": ["in", list(YUBORILADI_HOLAT)]}

	rows = frappe.get_all(
		"Murojaat",
		filters=filtr,
		fields=[
			"name", "turi", "kategoriya", "yonaltirildi", "muhimlik", "matn",
			"student", "student_name", "sinf", "payer_name", "payer_phone",
			"menejer", "menejer_nomi", "manba", "suhbat_vaqti", "ochilgan",
			"sla_sana", "yechim_turi", "yechim", "yechim_kim", "yechim_vaqti",
		],
		order_by="ochilgan desc",
		limit_page_length=cint(limit) or 0,
	)
	studentlar = {r.student for r in rows if r.student}
	qarzlar = _qarz_holati(studentlar)
	suhbatlar = _suhbatlar(studentlar)
	izohlar = _frappe_izohlar([r.name for r in rows])

	# Qaror beruvchilarning ismlari (Moodle'da "kim hal qildi" ko'rinadi)
	qaror_userlar = {r.yechim_kim for r in rows if r.yechim_kim}
	ismlar = {
		u.name: u.full_name or u.name
		for u in (frappe.get_all("User", filters={"name": ["in", list(qaror_userlar)]},
		                         fields=["name", "full_name"]) if qaror_userlar else [])
	}

	out = []
	for r in rows:
		qarz = qarzlar.get(r.student) or {}
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
			"qarzsumma": qarz.get("summa", 0.0),
			"qarzholat": qarz.get("holat", ""),
			"qarzkechikish": qarz.get("kechikish", ""),
			# JSON satr: Moodle REST so'rovni forma maydonlari ko'rinishida
			# oladi, ichma-ich ro'yxat bilan `max_input_vars` (5000) oshib
			# ketardi — JSON bilan har murojaatga bitta maydon
			"suhbatlar": json.dumps(suhbatlar.get(r.student) or [], ensure_ascii=False),
			# Frappe'da yozilgan qaror (2026-11-26: rahbar ikki joyda ishlaydi).
			# Moodle buni faqat O'ZIDA QAROR YO'Q bo'lsa qabul qiladi va
			# ota-onaga bildirishnomani o'zi yuboradi.
			"qarorturi": r.yechim_turi or "",
			"qaror": r.yechim or "",
			"qarorkimidnumber": _idnumber(r.yechim_kim),
			"qarorkimname": ismlar.get(r.yechim_kim) or "",
			"qarorvaqti": _ts(r.yechim_vaqti),
			# Frappe'da tug'ilgan kommentlar — Moodle timeline'ida ham chiqadi
			"izohlar": json.dumps(izohlar.get(r.name) or [], ensure_ascii=False),
		})
	return out


def push(nomlar=None, limit: int = 0, trigger: str = "Qo'lda",
         faqat_ochiq: int = 0) -> dict:
	"""Murojaatlarni Moodle'ga yuboradi (bo'laklab)."""
	s = _settings()
	if not cint(s.enabled):
		return {"holat": "o'chirilgan"}

	qatorlar = _qatorlar(nomlar, limit, faqat_ochiq=bool(cint(faqat_ochiq)))
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


# Holat DARAJASI: pull holatni hech qachon ORQAGA qaytarmaydi. Aynan shu
# qoida yo'qligi 2026-11-26 gacha Frappe'da berilgan qarorlarni o'chirib
# yuborayotgan edi (Moodle'da hamma qator «Yangi» turgani uchun har 15
# daqiqada holat «Yangi»ga, qaror NULL'ga qaytarilardi).
HOLAT_DARAJA = {
	"Yangi": 0,
	"Ko'rib chiqilmoqda": 1,
	"Ota-onaga xabar berish": 2,      # eski oqimdan qolgan hujjatlar uchun
	"Yopildi": 3,
}


def _nusxaga_yoz(r: dict) -> bool:
	"""Bitta Moodle qatorini Frappe'dagi Murojaat bilan BIRLASHTIRADI.

	QOIDALAR (2026-11-26, rahbar ikki joyda ishlaydi):
	  * holat faqat OLDINGA siljiydi (HOLAT_DARAJA);
	  * qaror faqat Frappe'da YO'Q bo'lsa yoziladi (birinchi yozilgan g'olib);
	  * korildi_vaqti faqat bo'sh bo'lsa to'ldiriladi;
	  * masul Frappe'da bo'sh bo'lsagina Moodle'dan olinadi;
	  * Moodle'da tug'ilgan izohlar child jadvalga QO'SHILADI (moodle_id
	    bo'yicha dublikat to'siladi), hech narsa o'chirilmaydi.
	False = murojaat Frappe'da topilmadi."""
	nom = r.get("frappename")
	if not nom or not frappe.db.exists("Murojaat", nom):
		return False

	joriy = frappe.db.get_value(
		"Murojaat", nom,
		["holat", "yechim_turi", "yechim_kim", "korildi_vaqti", "masul",
		 "yopilgan_sana"],
		as_dict=True,
	)

	qiymat = {
		"yonaltirildi": r.get("yonalish") or "CEO",
		"moodle_izoh_soni": cint(r.get("izohsoni")),
		"moodle_otaona_kordi": _dt(r.get("otaonakordi")),
	}

	# Holat: faqat oldinga
	moodle_holat = r.get("holat") or ""
	if HOLAT_DARAJA.get(moodle_holat, 1) > HOLAT_DARAJA.get(joriy.holat, 0):
		qiymat["holat"] = moodle_holat

	# Ko'rildi: bo'sh bo'lsa to'ldiriladi (Frappe'da ochilgan vaqt o'chmaydi)
	if not joriy.korildi_vaqti and cint(r.get("korildivaqti")):
		qiymat["korildi_vaqti"] = _dt(r.get("korildivaqti"))

	# Qaror: birinchi yozilgan g'olib — Frappe'da bor bo'lsa TEGILMAYDI
	if (r.get("qarorturi") or "").strip():
		if not joriy.yechim_turi:
			qiymat["yechim_turi"] = r.get("qarorturi")
			qiymat["yechim"] = r.get("qaror") or None
			qiymat["yechim_vaqti"] = _dt(r.get("qarorvaqti"))
		# Moodle'da qaror BOR — belgi sifatida ham ishlaydi: cron shu maydon
		# bo'sh turgan (qarori hali yetib bormagan) hujjatlarni qayta yuboradi
		qiymat["moodle_qaror_kim"] = r.get("qarorism") or "—"

	masul = None
	idn = (r.get("masul") or "").strip()
	if idn and not joriy.masul:
		masul = frappe.db.get_value("Employee", idn, "user_id")
	if masul:
		qiymat["masul"] = masul

	if qiymat.get("holat") == "Yopildi":
		yop = _dt(r.get("yopilganvaqti"))
		qiymat["yopilgan_sana"] = joriy.yopilgan_sana or (getdate(yop) if yop else nowdate())
		# Ota-ona javobni ILOVADA ko'radi — menejer qo'ng'irog'i shart emas
		qiymat["xabar_berildi"] = 1
		if qiymat["moodle_otaona_kordi"]:
			qiymat["xabar_vaqti"] = qiymat["moodle_otaona_kordi"]

	# `db_set` emas, to'g'ridan-to'g'ri UPDATE: Murojaat.validate ichida
	# yopish shartlari bor va ular Moodle'da allaqachon bajarilgan. Hujjat
	# orqali saqlash Moodle'dan kelgan haqiqatni rad etishi mumkin edi.
	frappe.db.set_value("Murojaat", nom, qiymat, update_modified=False)

	_moodle_izohlarni_qoshish(nom, r.get("izohlar"))
	return True


def _moodle_izohlarni_qoshish(nom: str, izohlar_json) -> None:
	"""Moodle'da tug'ilgan kommentlarni child jadvalga qo'shadi (append-only).

	Dublikat `moodle_id` bilan to'siladi. `kim` (User havolasi) yo'q — Moodle
	foydalanuvchisining Frappe akkauntini izlash shart emas, ism yetarli
	(panel `kim_nomi`ni ko'rsatadi)."""
	if not izohlar_json:
		return
	try:
		rows = json.loads(izohlar_json) if isinstance(izohlar_json, str) else izohlar_json
	except Exception:
		return
	if not isinstance(rows, list) or not rows:
		return

	bor = set(frappe.get_all(
		"Murojaat Izohi",
		filters={"parenttype": "Murojaat", "parent": nom, "moodle_id": ["is", "set"]},
		pluck="moodle_id",
	))
	max_idx = cint(frappe.db.sql(
		"""SELECT MAX(idx) FROM `tabMurojaat Izohi`
		    WHERE parenttype = 'Murojaat' AND parent = %s""",
		(nom,),
	)[0][0])
	for q in rows:
		if not isinstance(q, dict):
			continue
		mid = str(q.get("moodleid") or "").strip()
		matn = (q.get("matn") or "").strip()
		if not mid or mid in bor or not matn:
			continue
		max_idx += 1
		child = frappe.get_doc({
			"doctype": "Murojaat Izohi",
			"parenttype": "Murojaat",
			"parent": nom,
			"parentfield": "izohlar",
			"idx": max_idx,
			"vaqt": _dt(q.get("vaqt")),
			"kim_nomi": (q.get("kim") or "Moodle")[:140],
			"turi": "Komment",
			"matn": matn[:4000],
			"moodle_id": mid,
		})
		child.name = frappe.generate_hash(length=10)
		child.db_insert()


def _dt(ts) -> str | None:
	from datetime import datetime

	ts = cint(ts)
	if not ts:
		return None
	return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ================================================================ jadval
def darhol_push(doc, trigger: str = "Darhol"):
	"""Bitta murojaatni DARHOL Moodle'ga yuboradi (navbatda).

	Yangi murojaat, rahbar qarori va izoh uchun bitta yo'l: 15 daqiqalik
	cron'ni kutmaslik kerak — qaror bilan birga ota-onaga bildirishnoma
	ketadi. Navbatda bajariladi: Moodle javob bermasa yoki sekin bo'lsa,
	foydalanuvchining tugmasi shu sababli qotib qolmasligi kerak."""
	s = _settings()
	if not cint(s.enabled):
		return
	frappe.enqueue(
		"target_zenit.integrations.moodle_murojaat.push",
		queue="short", timeout=300, enqueue_after_commit=True,
		job_name=f"moodle_murojaat:{doc.name}",
		nomlar=[doc.name], trigger=trigger,
	)


def on_murojaat_insert(doc, method=None):
	"""Yangi murojaat darhol Moodle'ga."""
	darhol_push(doc, trigger="Yangi murojaat")


def on_aloqa_insert(doc, method=None):
	"""Sotuvchi yangi suhbat yozdi -> o'sha o'quvchining ochiq murojaatlari
	Moodle'da yangilanadi.

	NEGA KERAK: rahbar kartada «kim qachon gaplashdi» ni ko'radi. Suhbat
	faqat kunlik sinxronda ketsa, rahbar eski tarixga qarab qaror qabul
	qilardi — ota-onaga ikkinchi marta bir xil javob berilardi."""
	if not cint(_settings().enabled):
		return
	student = doc.get("student") or frappe.db.get_value(
		"Qarz Ishi", doc.get("qarz_ishi"), "student")
	if not student:
		return
	nomlar = frappe.get_all(
		"Murojaat",
		filters={"student": student, "holat": ["!=", "Yopildi"]},
		pluck="name", limit_page_length=20,
	)
	if not nomlar:
		return
	frappe.enqueue(
		"target_zenit.integrations.moodle_murojaat.push",
		queue="short", timeout=300, enqueue_after_commit=True,
		job_name=f"moodle_murojaat_suhbat:{student}",
		nomlar=nomlar, trigger="Yangi suhbat",
	)


def sync_cron():
	"""Har 15 daqiqada: ochiq murojaatlarni yangilab yuborish + javoblarni
	olib kelish.

	Yaratilish `after_insert` bilan darhol ketadi, bu esa KEYINGI
	o'zgarishlar uchun: qarz summasi to'lov bilan o'zgaradi, kategoriya
	to'g'rilanadi, muddat suriladi. Ochiq murojaatlar soni o'nlab bo'lgani
	uchun bu arzon."""
	if not cint(_settings().enabled):
		return
	push(trigger="Jadval", faqat_ochiq=1)
	pull()


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
