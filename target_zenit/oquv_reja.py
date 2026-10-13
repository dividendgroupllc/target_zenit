# Copyright (c) 2026, Target Zenit
# O'quv reja (KTP) ishchi mantiqi: faol rejani topish, keyingi o'tilmagan mavzu,
# "dars o'tdim" tasdig'i (Dars Bajarilishi yaratadi), qamrov hisoboti.
# Standart ERPNext/jadval yadrosini buzmaydi — ustiga ulanadi.
from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

MENEJER_ROLLARI = {"system manager", "zavuch", "academics user", "education manager"}
KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _vaqt_str(v) -> str:
	if not v:
		return ""
	if hasattr(v, "total_seconds"):
		j = int(v.total_seconds())
		return f"{j // 3600:02d}:{(j % 3600) // 60:02d}"
	s = str(v)
	return s[:5] if len(s) >= 5 else s


def _daraja_raqam(s: str | None) -> str:
	"""Guruh/daraja nomidan sinf raqamini ajratadi: '5 A(full)' -> '5'."""
	m = re.search(r"\d+", str(s or ""))
	return m.group(0) if m else ""


def _menejermi() -> bool:
	return bool(MENEJER_ROLLARI & {r.lower() for r in frappe.get_roles()})


def _mening_instructorim() -> str | None:
	"""Instructor'ni ID bo'yicha aniqlaydi (ism o'zgarishiga chidamli) — ism_sync.py."""
	from target_zenit.ism_sync import joriy_instructor

	return joriy_instructor()


def aktiv_reja(fan: str, guruh: str | None = None, guruh_nomi: str | None = None) -> str | None:
	"""Shu (fan, guruh) uchun Faol O'quv Reja. Avval guruh to'g'ridan-to'g'ri
	rejaning `sinflar` ro'yxatida bormi (ishonchli); keyin sinf-daraja bo'yicha
	taxmin; oxirida fanга bitta Faol reja bo'lsa — o'sha."""
	if not fan:
		return None
	# 1) To'g'ridan-to'g'ri a'zolik (eng ishonchli — sinflar ro'yxatida bormi)
	if guruh:
		band = frappe.db.sql(
			"""SELECT r.name FROM `tabOquv Reja Guruhi` g
			   JOIN `tabOquv Reja` r ON r.name = g.parent
			   WHERE r.fan = %s AND r.holat = 'Faol' AND g.guruh = %s LIMIT 1""",
			(fan, guruh),
		)
		if band:
			return band[0][0]
	# 2) Zaxira — FAQAT sinflari ko'rsatilmagan (bo'sh) rejalar uchun; aks holda
	#    aniq sinflar ro'yxati bor reja boshqa sinfga noto'g'ri tushmasligi uchun
	#    a'zolik topilmasa — mos reja yo'q.
	bosh = frappe.get_all(
		"Oquv Reja", filters={"fan": fan, "holat": "Faol"},
		fields=["name", "sinf_daraja"], limit_page_length=0,
	)
	bosh = [p for p in bosh if not frappe.db.exists("Oquv Reja Guruhi", {"parent": p.name})]
	if not bosh:
		return None
	if len(bosh) == 1:
		return bosh[0].name
	nomi = guruh_nomi or (frappe.db.get_value("Student Group", guruh, "student_group_name") if guruh else "")
	daraja = _daraja_raqam(nomi) or _daraja_raqam(guruh)
	for p in bosh:
		if daraja and daraja in {d.strip() for d in str(p.sinf_daraja or "").split(",")}:
			return p.name
	return None


def _otilgan_qatorlar(oquv_reja: str, guruh: str) -> set[str]:
	"""Shu guruh uchun o'tilgan (yoki qisman) reja qatorlari (ID) to'plami."""
	rows = frappe.get_all(
		"Dars Bajarilishi",
		filters={"oquv_reja": oquv_reja, "guruh": guruh, "holat": ["in", ["O'tildi", "Qisman"]]},
		fields=["reja_qatori"], limit_page_length=0,
	)
	return {r.reja_qatori for r in rows if r.reja_qatori}


def keyingi_mavzu(oquv_reja: str, guruh: str) -> dict | None:
	"""Shu guruh uchun keyingi o'tilmagan mavzu + progress."""
	if not oquv_reja:
		return None
	qatorlar = frappe.get_all(
		"Oquv Reja Qatori", filters={"parent": oquv_reja, "parenttype": "Oquv Reja"},
		fields=["name", "tartib", "bolim", "mavzu", "soat"], order_by="idx asc",
		limit_page_length=0,
	)
	otilgan = _otilgan_qatorlar(oquv_reja, guruh)
	keyingi = None
	for q in qatorlar:
		if q.name not in otilgan:
			keyingi = q
			break
	return {
		"keyingi": keyingi,
		"otildi": len(otilgan),
		"jami": len(qatorlar),
	}


@frappe.whitelist()
def dars_holati(fan: str, guruh: str, sana: str | None = None,
                jadval_yozuvi: str | None = None, guruh_nomi: str | None = None) -> dict:
	"""Bitta dars uchun: faol reja + keyingi mavzu + bugun o'tilganmi."""
	sana = sana or nowdate()
	reja = aktiv_reja(fan, guruh, guruh_nomi)
	natija = {"oquv_reja": reja, "keyingi": None, "otildi": 0, "jami": 0, "bugun": None}
	if reja:
		km = keyingi_mavzu(reja, guruh) or {}
		natija.update({"keyingi": km.get("keyingi"), "otildi": km.get("otildi", 0),
		               "jami": km.get("jami", 0)})
	# Shu slot bugun allaqachon tasdiqlanganmi?
	filtr = {"guruh": guruh, "sana": sana}
	if jadval_yozuvi:
		filtr["jadval_yozuvi"] = jadval_yozuvi
	natija["bugun"] = frappe.db.get_value(
		"Dars Bajarilishi", filtr, ["name", "mavzu", "holat", "reja_qatori"], as_dict=True
	)
	return natija


@frappe.whitelist()
def dars_detali(jadval_yozuvi: str, sana: str | None = None) -> dict:
	"""Dars ustiga bosilganda — TO'LIQ ma'lumot: dars + o'quv reja + mavzular
	ro'yxati (shu sinf uchun o'tildi belgisi bilan) + bugungi yozuv."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi)
	dars = {
		"jadval_yozuvi": jy.name,
		"fan": jy.fan,
		"guruh": jy.guruh,
		"guruh_nomi": jy.guruh_nomi or jy.guruh,
		"sinflar": jy.sinflar,
		"kun": jy.kun,
		"dars_raqami": jy.dars_raqami,
		"boshlanish": _vaqt_str(jy.boshlanish),
		"tugash": _vaqt_str(jy.tugash),
		"xona": jy.xona,
		"oqituvchi": jy.oqituvchi,
		"oqituvchi_nomi": jy.oqituvchi_nomi,
		"sana": str(sana),
	}
	reja = aktiv_reja(jy.fan, jy.guruh, jy.guruh_nomi)
	mavzular, keyingi, otildi = [], None, 0
	if reja:
		otilgan = _otilgan_qatorlar(reja, jy.guruh)
		rows = frappe.get_all(
			"Oquv Reja Qatori", filters={"parent": reja, "parenttype": "Oquv Reja"},
			fields=["name", "tartib", "bolim", "mavzu", "soat", "dars_turi"],
			order_by="idx asc", limit_page_length=0,
		)
		for q in rows:
			done = q.name in otilgan
			if done:
				otildi += 1
			elif keyingi is None:
				keyingi = q.name
			q["otildi"] = done
			mavzular.append(q)
	bugun = frappe.db.get_value(
		"Dars Bajarilishi", {"guruh": jy.guruh, "sana": sana, "jadval_yozuvi": jy.name},
		["name", "reja_qatori", "mavzu", "holat", "izoh"], as_dict=True,
	)
	return {
		"dars": dars,
		"oquv_reja": reja,
		"oquv_reja_nomi": frappe.db.get_value("Oquv Reja", reja, "nomi") if reja else None,
		"mavzular": mavzular,
		"keyingi": keyingi,
		"otildi": otildi,
		"jami": len(mavzular),
		"bugun": bugun,
	}


@frappe.whitelist()
def dars_otdim(jadval_yozuvi: str | None = None, oquv_reja: str | None = None,
               reja_qatori: str | None = None, guruh: str | None = None,
               fan: str | None = None, sana: str | None = None,
               holat: str = "O'tildi", izoh: str | None = None) -> dict:
	"""O'qituvchi «shu darsni o'tdim» tasdig'i — Dars Bajarilishi yaratadi/yangilaydi.
	Ruxsat: menejer YOKI darsning o'z o'qituvchisi."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi) if jadval_yozuvi else None

	# Ruxsat: menejer yoki shu darsning o'qituvchisi
	oqituvchi = jy.oqituvchi if jy else None
	if not _menejermi():
		meniki = _mening_instructorim()
		if not meniki or (jy and jy.oqituvchi != meniki):
			frappe.throw(_("Faqat shu darsning o'qituvchisi tasdiqlashi mumkin."), frappe.PermissionError)
		oqituvchi = oqituvchi or meniki

	guruh = guruh or (jy.guruh if jy else None)
	fan = fan or (jy.fan if jy else None)
	if not guruh:
		frappe.throw(_("Guruh aniqlanmadi."))

	oquv_reja = oquv_reja or aktiv_reja(fan, guruh, jy.guruh_nomi if jy else None)

	# Mavzu snapshot (reja_qatori berilmagan bo'lsa — keyingi o'tilmagan)
	tartib = mavzu = None
	if not reja_qatori and oquv_reja:
		km = keyingi_mavzu(oquv_reja, guruh) or {}
		k = km.get("keyingi")
		if k:
			reja_qatori, tartib, mavzu = k["name"], k.get("tartib"), k.get("mavzu")
	elif reja_qatori:
		q = frappe.db.get_value("Oquv Reja Qatori", reja_qatori, ["tartib", "mavzu"], as_dict=True)
		if q:
			tartib, mavzu = q.tartib, q.mavzu

	# Dublikat tekshiruvi (guruh + sana + slot) — bo'lsa yangilanadi
	filtr = {"guruh": guruh, "sana": sana}
	if jadval_yozuvi:
		filtr["jadval_yozuvi"] = jadval_yozuvi
	mavjud = frappe.db.get_value("Dars Bajarilishi", filtr, "name")

	qiymat = {
		"oquv_reja": oquv_reja, "reja_qatori": reja_qatori, "tartib": tartib, "mavzu": mavzu,
		"guruh": guruh, "fan": fan, "oqituvchi": oqituvchi, "sana": sana,
		"jadval_yozuvi": jadval_yozuvi, "holat": holat, "izoh": izoh,
		"boshlanish": jy.boshlanish if jy else None,
	}
	if jy and jy.boshlanish and jy.tugash:
		try:
			b = jy.boshlanish.total_seconds() if hasattr(jy.boshlanish, "total_seconds") else 0
			t = jy.tugash.total_seconds() if hasattr(jy.tugash, "total_seconds") else 0
			if t > b:
				qiymat["davomiylik_min"] = int((t - b) // 60)
		except Exception:
			pass

	if mavjud:
		doc = frappe.get_doc("Dars Bajarilishi", mavjud)
		doc.update(qiymat)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(dict(doctype="Dars Bajarilishi", **qiymat))
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "mavzu": mavzu, "holat": holat}


@frappe.whitelist()
def qamrov(academic_year: str | None = None, fan: str | None = None) -> list[dict]:
	"""Qamrov matritsasi: har Faol reja x unга tegishli guruhlar bo'yicha o'tildi/jami."""
	if not _menejermi():
		frappe.throw(_("Qamrov hisoboti uchun ruxsat yo'q."), frappe.PermissionError)
	filtr = {"holat": "Faol"}
	if academic_year:
		filtr["academic_year"] = academic_year
	if fan:
		filtr["fan"] = fan
	rejalar = frappe.get_all("Oquv Reja", filters=filtr,
	                         fields=["name", "fan", "sinf_daraja", "jami_soat"], limit_page_length=0)
	natija = []
	for r in rejalar:
		jami = frappe.db.count("Oquv Reja Qatori", {"parent": r.name, "parenttype": "Oquv Reja"})
		# Shu reja bo'yicha dars o'tilgan guruhlar
		guruhlar = frappe.db.sql(
			"""SELECT guruh, guruh_nomi,
			          COUNT(DISTINCT CASE WHEN holat IN ('O''tildi','Qisman') THEN reja_qatori END) otildi,
			          MAX(sana) oxirgi
			   FROM `tabDars Bajarilishi` WHERE oquv_reja=%s GROUP BY guruh, guruh_nomi""",
			(r.name,), as_dict=True,
		)
		natija.append({
			"oquv_reja": r.name, "fan": r.fan, "sinf_daraja": r.sinf_daraja,
			"jami_mavzu": jami, "guruhlar": guruhlar,
		})
	return natija


# ============================================================ MAVZULARNI KO'PLAB KIRITISH
# O'qituvchi butun chorak mavzularini bir martada biriktiradi: ro'yxatni (Word/Excel/KTP'dan)
# ko'chirib joylaydi → tizim qatorlarga ajratadi → tasdiqlanadi.
# Qo'llanadigan joy: dars kokpiti («Mavzu biriktirish») va «Mening jadvalim» → 📘 Mavzular.

# Satr boshidagi raqamlash: "1.", "12)", "-", "•", "*"
_RAQAM = re.compile(r"^\s*(?:\d{1,3}\s*[.)\]]|[-–—•*])\s*")
# Oxiridagi soat: "(2 soat)", "— 2 soat", "- 2s", "2 soat"
_SOAT = re.compile(r"[\s(\[—–-]+(\d{1,2})\s*(?:soat|s|час|ч|h)?\s*[)\]]?\s*$", re.IGNORECASE)
# Bo'lim sarlavhasi: "# ...", "== ... ==", "1-bob ...", "I bob", oxiri ":" bo'lgan satr
_BOLIM = re.compile(r"^\s*(?:#+\s*|=+\s*)(.+?)\s*=*\s*$")
_BOLIM_SOZ = re.compile(r"^\s*(\d+\s*[-–]?\s*(?:bob|chorak|bo'?lim|modul|fasl)\b.*)$", re.IGNORECASE)

TUR_KALIT = [
	("Nazorat", ("nazorat", "kontrol", "bsb", "bsbb", "test", "imtihon", "yakuniy")),
	("Takrorlash", ("takror", "umumlash", "повтор")),
	("Amaliy", ("amaliy", "laborator", "mashq", "praktik")),
]


def _tur_aniqla(mavzu: str) -> str:
	m = (mavzu or "").lower()
	for tur, kalitlar in TUR_KALIT:
		if any(k in m for k in kalitlar):
			return tur
	return "Yangi mavzu"


@frappe.whitelist()
def matn_parse(matn: str, default_soat: int = 1) -> dict:
	"""Ko'chirib joylangan matnni KTP qatorlariga ajratadi (saqlashdan oldin ko'rsatish uchun).

	Har satr — bitta mavzu. Tushunarli ko'rinishlar:
	    Natural sonlar
	    1. Natural sonlar
	    2) Oddiy kasrlar — 2 soat
	    Kasrlarni qo'shish (3 soat)
	    Kasrlar | Oddiy kasrlar | 2        (bo'lim | mavzu | soat)
	    Oddiy kasrlar; 2
	    # 1-bob. Kasrlar                   (bo'lim sarlavhasi — keyingi mavzularga tegishli)
	    == 2-chorak ==
	    [nazorat] 1-chorak nazorat ishi    (dars turi qo'lda)
	"""
	default_soat = int(default_soat or 1)
	qatorlar, ogohlantirish = [], []
	bolim = None
	korilgan = {}
	for xom in str(matn or "").replace("\r", "").split("\n"):
		satr = xom.strip()
		if not satr:
			continue

		# 1) Bo'lim sarlavhasi
		mb = _BOLIM.match(satr)
		if mb and (satr.startswith("#") or satr.startswith("=")):
			bolim = mb.group(1).strip() or None
			continue
		if _BOLIM_SOZ.match(satr) and not _SOAT.search(satr):
			bolim = satr.strip(" :")
			continue
		if satr.endswith(":") and len(satr) <= 60:
			bolim = satr.rstrip(":").strip()
			continue

		satr = _RAQAM.sub("", satr)

		# 2) Dars turi qo'lda: [nazorat] ...
		tur = None
		if satr.startswith("["):
			yopish = satr.find("]")
			if yopish > 0:
				belgi = satr[1:yopish].strip().lower()
				xarita = {"nazorat": "Nazorat", "takror": "Takrorlash", "takrorlash": "Takrorlash",
				          "amaliy": "Amaliy", "yangi": "Yangi mavzu", "boshqa": "Boshqa"}
				tur = xarita.get(belgi)
				satr = satr[yopish + 1:].strip()

		# 3) Ustunlarga ajratish (| ; tab)
		qism = [p.strip() for p in re.split(r"\s*[|;]\s*|\t+", satr) if p.strip()]
		q_bolim, mavzu, soat = bolim, satr, None
		if len(qism) >= 3:
			q_bolim, mavzu = qism[0], qism[1]
			soat = int(qism[2]) if qism[2].isdigit() else None
		elif len(qism) == 2:
			if qism[1].isdigit():
				mavzu, soat = qism[0], int(qism[1])
			else:
				q_bolim, mavzu = qism[0], qism[1]
		else:
			mavzu = qism[0] if qism else satr

		# 4) Oxiridagi soat
		if soat is None:
			ms = _SOAT.search(mavzu)
			if ms:
				soat = int(ms.group(1))
				mavzu = mavzu[: ms.start()].strip(" .—–-()[]")
		mavzu = mavzu.strip(" .;|")
		if not mavzu:
			continue
		if len(mavzu) > 240:
			mavzu = mavzu[:240]
			ogohlantirish.append("Juda uzun mavzu qisqartirildi.")

		kalit = mavzu.lower()
		korilgan[kalit] = korilgan.get(kalit, 0) + 1
		qatorlar.append({
			"tartib": len(qatorlar) + 1,
			"bolim": q_bolim,
			"mavzu": mavzu,
			"soat": soat or default_soat,
			"dars_turi": tur or _tur_aniqla(mavzu),
		})

	takror = [m for m, n in korilgan.items() if n > 1]
	if takror:
		ogohlantirish.append(f"Takrorlangan mavzu: {len(takror)} ta (saqlanadi — kerak bo'lsa o'chiring).")
	if not qatorlar:
		ogohlantirish.append("Mavzu topilmadi. Har mavzuni alohida satrga yozing.")
	return {
		"qatorlar": qatorlar,
		"jami": len(qatorlar),
		"jami_soat": sum(q["soat"] for q in qatorlar),
		"ogohlantirish": list(dict.fromkeys(ogohlantirish)),
	}


def _joriy_yil() -> str | None:
	return frappe.db.get_value("Academic Year", {"name": ["like", "%"]}, "name", order_by="year_start_date desc")


@frappe.whitelist()
def mening_fanlarim(oqituvchi: str | None = None) -> dict:
	"""O'qituvchining jadvaldagi fan×guruh juftliklari + har biriga reja holati.
	Dialogda «qaysi fan, qaysi guruh» ro'yxatini to'ldirish uchun."""
	if oqituvchi and not _menejermi():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	# Menejer (zavuch) uchun — butun maktab bo'yicha; o'qituvchi uchun — faqat o'zi
	if not oqituvchi and not _menejermi():
		oqituvchi = _mening_instructorim()
	natija = {"oqituvchi": oqituvchi, "juftliklar": [], "choraklar": [],
	          "academic_year": _joriy_yil(), "hammasi": 0}
	natija["choraklar"] = frappe.get_all(
		"Academic Term", fields=["name", "term_name"], order_by="term_start_date",
		limit_page_length=0)
	versiya = frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")
	if not versiya:
		return natija

	# Zavuch/menejer o'zi o'qituvchi bo'lmasa — butun jadvaldan fan×guruh juftliklari
	filtr = {"versiya": versiya}
	if oqituvchi:
		filtr["oqituvchi"] = oqituvchi
	elif not _menejermi():
		return natija
	natija["hammasi"] = 0 if oqituvchi else 1

	korilgan = {}
	for r in frappe.get_all(
		"Jadval Yozuvi", filters=filtr,
		fields=["fan", "guruh", "guruh_nomi"], limit_page_length=0):
		if not (r.fan and r.guruh):
			continue
		korilgan.setdefault((r.fan, r.guruh), r.guruh_nomi)
	for (fan, guruh), nomi in sorted(korilgan.items(), key=lambda x: (x[0][0], str(x[1]))):
		reja = aktiv_reja(fan, guruh, nomi)
		jami = frappe.db.count("Oquv Reja Qatori", {"parent": reja, "parenttype": "Oquv Reja"}) if reja else 0
		otilgan = len(_otilgan_qatorlar(reja, guruh)) if reja else 0
		natija["juftliklar"].append({
			"fan": fan, "guruh": guruh, "guruh_nomi": nomi or guruh,
			"oquv_reja": reja,
			"reja_nomi": frappe.db.get_value("Oquv Reja", reja, "nomi") if reja else None,
			"mavzu_soni": jami, "otilgan": otilgan,
		})
	return natija


def _reja_top_yoki_yarat(fan: str, guruhlar: list[str], academic_year: str | None = None) -> tuple[str, bool]:
	"""Shu fan+guruh(lar) uchun Faol rejani topadi, bo'lmasa yaratadi. (name, yangi?)"""
	for g in guruhlar:
		r = aktiv_reja(fan, g)
		if r:
			# Qolgan guruhlarni ham shu rejaga biriktiramiz
			doc = frappe.get_doc("Oquv Reja", r)
			bor = {s.guruh for s in (doc.sinflar or [])}
			yangi = [x for x in guruhlar if x not in bor]
			if yangi and bor:  # sinflari ko'rsatilgan reja bo'lsa — qo'shamiz
				for x in yangi:
					doc.append("sinflar", {
						"guruh": x,
						"guruh_nomi": frappe.db.get_value("Student Group", x, "student_group_name"),
					})
				doc.save(ignore_permissions=True)
			return r, False
	doc = frappe.get_doc({
		"doctype": "Oquv Reja", "fan": fan, "holat": "Faol",
		"academic_year": academic_year or _joriy_yil(),
		"muallif": frappe.session.user,
		"sinflar": [{"guruh": g,
		             "guruh_nomi": frappe.db.get_value("Student Group", g, "student_group_name")}
		            for g in guruhlar],
	})
	doc.insert(ignore_permissions=True)
	return doc.name, True


def _ruxsat_fan(fan: str, guruhlar: list[str]):
	"""O'qituvchi faqat o'zi dars beradigan fan/guruhга reja tuzadi (menejerga cheklov yo'q)."""
	if _menejermi():
		return
	ins = _mening_instructorim()
	if not ins:
		frappe.throw(_("Hisobingizga o'qituvchi (Instructor) yozuvi bog'lanmagan."), frappe.PermissionError)
	for g in guruhlar:
		if not frappe.db.exists("Jadval Yozuvi", {"fan": fan, "guruh": g, "oqituvchi": ins}):
			frappe.throw(
				_("Siz «{0}» guruhiga «{1}» fanidan dars bermaysiz.").format(g, fan),
				frappe.PermissionError)


@frappe.whitelist()
def mavzular_saqla(fan: str, guruhlar, matn: str = "", bolim: str | None = None,
                   rejim: str = "qoshish", default_soat: int = 1,
                   academic_year: str | None = None, qatorlar=None) -> dict:
	"""Butun chorak mavzularini bir martada biriktiradi.

	fan      — Course
	guruhlar — Student Group ro'yxati (JSON yoki list)
	matn     — ko'chirib joylangan ro'yxat (yoki `qatorlar` to'g'ridan-to'g'ri berilsa — o'sha)
	bolim    — hamma qatorga qo'yiladigan bo'lim/chorak nomi (masalan "1-chorak")
	rejim    — "qoshish" (oxiriga qo'shadi) yoki "almashtirish" (o'tilmagan qatorlarni o'chiradi)
	"""
	if isinstance(guruhlar, str):
		guruhlar = json.loads(guruhlar) if guruhlar.strip().startswith("[") else [guruhlar]
	guruhlar = [g for g in (guruhlar or []) if g]
	if not (fan and guruhlar):
		frappe.throw(_("Fan va kamida bitta guruh tanlanishi kerak."))
	_ruxsat_fan(fan, guruhlar)

	if isinstance(qatorlar, str):
		qatorlar = json.loads(qatorlar)
	if not qatorlar:
		qatorlar = matn_parse(matn, default_soat)["qatorlar"]
	if not qatorlar:
		frappe.throw(_("Mavzu topilmadi. Har mavzuni alohida satrga yozing."))

	reja, yangi = _reja_top_yoki_yarat(fan, guruhlar, academic_year)
	doc = frappe.get_doc("Oquv Reja", reja)

	ochirildi = saqlangan = 0
	if rejim == "almashtirish":
		# O'tilgan (Dars Bajarilishi bor) qatorlarга tegmaymiz — tarix buzilmasin
		band = {r.reja_qatori for r in frappe.get_all(
			"Dars Bajarilishi", filters={"oquv_reja": reja},
			fields=["reja_qatori"], limit_page_length=0) if r.reja_qatori}
		qoldi = [q for q in doc.qatorlar if q.name in band]
		ochirildi = len(doc.qatorlar) - len(qoldi)
		doc.qatorlar = []
		for q in qoldi:
			doc.append("qatorlar", {
				"tartib": q.tartib, "bolim": q.bolim, "mavzu": q.mavzu, "soat": q.soat,
				"davomiylik_min": q.davomiylik_min, "dars_turi": q.dars_turi,
				"tavsif": q.tavsif, "resurs": q.resurs,
			})
		saqlangan = len(qoldi)

	oxirgi = max([(q.tartib or 0) for q in doc.qatorlar] or [0])
	for i, q in enumerate(qatorlar, start=1):
		doc.append("qatorlar", {
			"tartib": oxirgi + i,
			"bolim": (q.get("bolim") or bolim or None),
			"mavzu": q.get("mavzu"),
			"soat": int(q.get("soat") or default_soat or 1),
			"dars_turi": q.get("dars_turi") or _tur_aniqla(q.get("mavzu")),
			"tavsif": q.get("tavsif"),
			"resurs": q.get("resurs"),
		})
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"oquv_reja": doc.name, "reja_nomi": doc.nomi, "yangi_reja": 1 if yangi else 0,
		"qoshildi": len(qatorlar), "ochirildi": ochirildi, "saqlangan": saqlangan,
		"jami": len(doc.qatorlar), "jami_soat": doc.jami_soat,
		"guruhlar": [s.guruh_nomi or s.guruh for s in (doc.sinflar or [])],
	}


@frappe.whitelist()
def reja_royxati(fan: str | None = None, limit: int = 60) -> list[dict]:
	"""Nusxa olish uchun mavjud rejalar (mavzulari bor)."""
	filtr = {}
	if fan:
		filtr["fan"] = fan
	rows = frappe.get_all(
		"Oquv Reja", filters=filtr,
		fields=["name", "nomi", "fan", "sinf_daraja", "holat", "jami_soat", "academic_year"],
		order_by="modified desc", limit_page_length=int(limit))
	for r in rows:
		r["mavzu_soni"] = frappe.db.count("Oquv Reja Qatori", {"parent": r.name, "parenttype": "Oquv Reja"})
	return [r for r in rows if r["mavzu_soni"]]


@frappe.whitelist()
def rejadan_nusxa(manba: str, fan: str, guruhlar, bolim: str | None = None,
                  rejim: str = "qoshish", academic_year: str | None = None) -> dict:
	"""Boshqa rejadagi mavzularni shu fan+guruhga nusxalash (o'tgan yildan / parallel sinfdan)."""
	qatorlar = frappe.get_all(
		"Oquv Reja Qatori", filters={"parent": manba, "parenttype": "Oquv Reja"},
		fields=["tartib", "bolim", "mavzu", "soat", "davomiylik_min", "dars_turi", "tavsif", "resurs"],
		order_by="idx asc", limit_page_length=0)
	if not qatorlar:
		frappe.throw(_("Manba rejada mavzu yo'q."))
	return mavzular_saqla(fan=fan, guruhlar=guruhlar, bolim=bolim, rejim=rejim,
	                      academic_year=academic_year, qatorlar=json.dumps(qatorlar))


@frappe.whitelist()
def reja_qatorlari(reja: str) -> list[dict]:
	"""Rejadagi mavzular (nusxa olish uchun ko'rib chiqish)."""
	return frappe.get_all(
		"Oquv Reja Qatori", filters={"parent": reja, "parenttype": "Oquv Reja"},
		fields=["tartib", "bolim", "mavzu", "soat", "dars_turi", "tavsif", "resurs"],
		order_by="idx asc", limit_page_length=0)


@frappe.whitelist()
def mavzu_olib_tashla(jadval_yozuvi: str, sana: str) -> dict:
	"""Shu kun (sana) uchun belgilangan mavzuni olib tashlaydi — `Dars Bajarilishi` o'chiriladi.
	Faqat o'sha kun yozuviga ta'sir qiladi, boshqa kunlar tegilmaydi."""
	jy = frappe.db.get_value("Jadval Yozuvi", jadval_yozuvi, ["guruh", "oqituvchi"], as_dict=True)
	if not jy:
		frappe.throw(_("Dars topilmadi."))
	if not _menejermi():
		meniki = _mening_instructorim()
		if not meniki or jy.oqituvchi != meniki:
			frappe.throw(_("Faqat shu darsning o'qituvchisi o'zgartira oladi."), frappe.PermissionError)
	nom = frappe.db.get_value(
		"Dars Bajarilishi",
		{"guruh": jy.guruh, "sana": getdate(sana), "jadval_yozuvi": jadval_yozuvi}, "name")
	if not nom:
		return {"ochirildi": 0}
	frappe.delete_doc("Dars Bajarilishi", nom, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"ochirildi": 1, "name": nom}
