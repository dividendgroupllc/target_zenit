# Copyright (c) 2026, Target Zenit
# Baholash sozlamalari (zavuch belgilaydi) + ulardan kelib chiqadigan hisob-kitoblar:
#   - baho shkalasi (5/10/100 ballik), o'tish va «past baho» chegarasi
#   - chorak bahosi usuli (O'rtacha / Vaznli / Qo'lda) + yaxlitlash
#   - kechikish qoidalari
#   - uy vazifa tekshirilishi
#   - o'zlashtirish ko'rsatkichi: trend o'qi + RAG rang + xavf bayrog'lari
#
# Hamma joy (dars kokpiti, jurnal, hisobotlar) faqat shu moduldan o'qiydi —
# qoidani bir joyda o'zgartirsa, hammasi moslashadi.
from __future__ import annotations

import frappe
from frappe.utils import flt

CACHE_KEY = "tz_baholash_sozlamalari"

# Sozlamalar hali kiritilmagan bo'lsa ishlatiladigan standart (5 ballik tizim)
DEFAULT = {
	"shkala": "5 ballik",
	"max_baho": 5,
	"otish_bahosi": 3,
	"past_baho": 3,
	"chorak_usuli": "O'rtacha",
	"yaxlitlash": "Matematik",
	"min_baho_soni": 3,
	"tuzatish_muddati_kun": 7,
	"kechikish_yoqilgan": 1,
	"kechikish_daqiqa": 10,
	"kechikish_yoqlik": 3,
	"kechikish_davomatga": 0,
	"uv_tekshirish": 1,
	"uv_default_max_ball": 5,
	"uv_bajarmaslik_limit": 2,
	"rag_qizil_ortacha": 3.0,
	"rag_sariq_ortacha": 4.0,
	"rag_qizil_davomat": 80.0,
	"rag_sariq_davomat": 90.0,
	"ketma_ket_past": 3,
	"trend_sezgirlik": 0.3,
}

# Davomat holatlari (kechikish o'chirilgan bo'lsa «Kechikdi» ko'rsatilmaydi)
DAVOMAT_HAMMASI = ("Keldi", "Kechikdi", "Kelmadi", "Kasal", "Qatnashmadi")
# Darsда bo'lgan hisoblanadigan holatlar (baho qo'yish mumkin)
BORLIK = ("Keldi", "Kechikdi")
# Yo'qlik hisoblanadigan holatlar
YOQLIK = ("Kelmadi", "Kasal", "Qatnashmadi")

# Davomat foizi bo'yicha xavf bayrog'i qo'yish uchun minimal dars soni.
# Bundan kam dars o'tilgan bo'lsa foiz ko'rsatiladi, lekin «qizil» qilinmaydi.
MIN_DARSLAR = 4


@frappe.whitelist()
def olish() -> dict:
	"""Baholash sozlamalari (keshlangan). Yozuv bo'lmasa — DEFAULT."""
	s = frappe.cache().get_value(CACHE_KEY)
	if s:
		return s
	s = dict(DEFAULT)
	try:
		doc = frappe.get_cached_doc("Baholash Sozlamalari")
		for k in DEFAULT:
			v = doc.get(k)
			if v not in (None, ""):
				s[k] = v
	except Exception:
		pass
	# raqamli maydonlarni normallashtirish
	for k in ("max_baho", "otish_bahosi", "past_baho", "min_baho_soni", "tuzatish_muddati_kun",
	          "kechikish_daqiqa", "kechikish_yoqlik", "uv_default_max_ball",
	          "uv_bajarmaslik_limit", "ketma_ket_past"):
		s[k] = int(flt(s.get(k)))
	for k in ("rag_qizil_ortacha", "rag_sariq_ortacha", "rag_qizil_davomat",
	          "rag_sariq_davomat", "trend_sezgirlik"):
		s[k] = flt(s.get(k))
	for k in ("kechikish_yoqilgan", "kechikish_davomatga", "uv_tekshirish"):
		s[k] = 1 if s.get(k) else 0
	s["davomat_holatlari"] = list(davomat_holatlari(s))
	frappe.cache().set_value(CACHE_KEY, s, expires_in_sec=600)
	return s


def kesh_tozalash():
	frappe.cache().delete_value(CACHE_KEY)


def davomat_holatlari(s: dict | None = None) -> tuple:
	s = s or olish()
	if s.get("kechikish_yoqilgan"):
		return DAVOMAT_HAMMASI
	return tuple(x for x in DAVOMAT_HAMMASI if x != "Kechikdi")


# ------------------------------------------------------------------ baho vaznlari
def vaznlar() -> dict:
	"""{baho_turi: vazn} — faol Baho Turi yozuvlaridan."""
	try:
		return {r.name: flt(r.vazn) or 1.0 for r in frappe.get_all(
			"Baho Turi", filters={"faol": 1}, fields=["name", "vazn"], limit_page_length=0)}
	except Exception:
		return {}


def yaxlit(x: float, usul: str | None = None) -> int | None:
	"""Chorak bahosini butun songa keltirish."""
	if x is None:
		return None
	usul = usul or olish().get("yaxlitlash") or "Matematik"
	import math
	if usul == "Yuqoriga":
		return math.ceil(x - 1e-9)
	if usul == "Pastga":
		return math.floor(x + 1e-9)
	return math.floor(x + 0.5)  # Matematik: 3.5 -> 4


def chorak_hisobla(ballar: list[dict], s: dict | None = None) -> dict:
	"""Bitta o'quvchining bitta fan+chorak ballaridan chorak bahosini hisoblaydi.

	ballar: [{"baho": 5, "baho_turi": "Nazorat ishi"}, ...]
	Qaytaradi: {ortacha, hisoblangan, baho, baho_soni, usul, yetarli}
	"""
	s = s or olish()
	usul = s.get("chorak_usuli") or "O'rtacha"
	bh = [flt(b.get("baho")) for b in ballar if b.get("baho")]
	natija = {"usul": usul, "baho_soni": len(bh), "ortacha": None,
	          "hisoblangan": None, "baho": None,
	          "yetarli": len(bh) >= max(1, s.get("min_baho_soni") or 1)}
	if not bh:
		return natija
	natija["ortacha"] = round(sum(bh) / len(bh), 2)

	if usul == "Vaznli":
		vz = vaznlar()
		jami_v = 0.0
		jami = 0.0
		for b in ballar:
			if not b.get("baho"):
				continue
			v = vz.get(b.get("baho_turi")) or 1.0
			jami += flt(b["baho"]) * v
			jami_v += v
		hisob = (jami / jami_v) if jami_v else natija["ortacha"]
	else:
		# «Qo'lda» bo'lsa ham tizim taklifini o'rtacha sifatida beradi
		hisob = natija["ortacha"]

	natija["hisoblangan"] = round(hisob, 2)
	natija["baho"] = yaxlit(hisob, s.get("yaxlitlash")) if natija["yetarli"] else None
	return natija


# ------------------------------------------------------------- o'zlashtirish (RAG)
def trend(ballar: list, s: dict | None = None) -> int:
	"""So'nggi ballar bo'yicha trend: 1 = o'sish, -1 = pasayish, 0 = barqaror.
	`ballar` — sana bo'yicha O'SISH tartibida (eng oxirgisi oxirida)."""
	s = s or olish()
	bh = [flt(b) for b in ballar if b]
	if len(bh) < 4:
		return 0
	n = min(3, len(bh) // 2)
	oxirgi = sum(bh[-n:]) / n
	oldingi = sum(bh[-2 * n:-n]) / n
	farq = oxirgi - oldingi
	sez = s.get("trend_sezgirlik") or 0.3
	# 100 ballik shkalada sezgirlik proporsional kattalashadi
	if (s.get("max_baho") or 5) > 10:
		sez = sez * (s["max_baho"] / 5.0)
	if farq > sez:
		return 1
	if farq < -sez:
		return -1
	return 0


def ketma_ket_past_soni(ballar: list, s: dict | None = None) -> int:
	"""Oxiridan boshlab ketma-ket qancha «past» baho borligi."""
	s = s or olish()
	chegara = s.get("past_baho") or 3
	n = 0
	for b in reversed([flt(x) for x in ballar if x]):
		if b <= chegara:
			n += 1
		else:
			break
	return n


def korsatkich(ballar: list, darslar: int = 0, yoqlik: int = 0,
               kechikish: int = 0, uv_bajarmagan: int = 0,
               s: dict | None = None) -> dict:
	"""O'quvchining qisqa o'zlashtirish ko'rsatkichi — dars kokpiti kartasi uchun.

	`ballar` sana bo'yicha o'sish tartibida bo'lishi kerak.
	Qaytaradi: {ortacha, trend, rang, davomat_foiz, ketma_ket_past, bayroqlar[]}
	"""
	s = s or olish()
	bh = [flt(b) for b in ballar if b]
	ortacha = round(sum(bh) / len(bh), 1) if bh else None

	hisoblangan_yoqlik = yoqlik
	if s.get("kechikish_davomatga") and s.get("kechikish_yoqlik"):
		hisoblangan_yoqlik += kechikish // max(1, s["kechikish_yoqlik"])
	davomat_foiz = round(100.0 * (darslar - hisoblangan_yoqlik) / darslar, 1) if darslar else None

	kkp = ketma_ket_past_soni(bh, s)
	bayroqlar = []
	rang = "yashil"

	def pastroq(yangi):
		nonlocal rang
		tartib = {"yashil": 0, "sariq": 1, "qizil": 2}
		if tartib[yangi] > tartib[rang]:
			rang = yangi

	if ortacha is not None:
		if ortacha < (s.get("rag_qizil_ortacha") or 3):
			pastroq("qizil")
			bayroqlar.append(f"o'rtacha past ({ortacha})")
		elif ortacha < (s.get("rag_sariq_ortacha") or 4):
			pastroq("sariq")
	# Davomat bo'yicha xavf faqat yetarli dars o'tilganda (1-2 darsdan «0%» chiqmasligi uchun)
	if davomat_foiz is not None and darslar >= MIN_DARSLAR:
		if davomat_foiz < (s.get("rag_qizil_davomat") or 80):
			pastroq("qizil")
			bayroqlar.append(f"davomat {davomat_foiz}%")
		elif davomat_foiz < (s.get("rag_sariq_davomat") or 90):
			pastroq("sariq")
	if s.get("ketma_ket_past") and kkp >= s["ketma_ket_past"]:
		pastroq("qizil")
		bayroqlar.append(f"{kkp} ta ketma-ket past baho")
	if s.get("uv_tekshirish") and s.get("uv_bajarmaslik_limit") \
			and uv_bajarmagan >= s["uv_bajarmaslik_limit"]:
		pastroq("sariq")
		bayroqlar.append(f"uy vazifa {uv_bajarmagan} marta bajarilmagan")
	if kechikish and kechikish >= max(2, s.get("kechikish_yoqlik") or 3):
		bayroqlar.append(f"{kechikish} marta kechikkan")

	return {
		"ortacha": ortacha,
		"trend": trend(bh, s),
		"rang": rang,
		"davomat_foiz": davomat_foiz,
		"ketma_ket_past": kkp,
		"kechikish": kechikish,
		"uv_bajarmagan": uv_bajarmagan,
		"bayroqlar": bayroqlar,
	}


# ------------------------------------------------------------------ baho tuzatish
def tuzatish_mumkinmi(sana, menejer: bool = False, s: dict | None = None) -> bool:
	"""Berilgan sanadagi bahoni hozir o'zgartirish mumkinmi (muddat sozlamasi)."""
	s = s or olish()
	if menejer:
		return True
	kun = s.get("tuzatish_muddati_kun") or 0
	if kun <= 0:
		return True
	from frappe.utils import date_diff, getdate, nowdate
	return date_diff(getdate(nowdate()), getdate(sana)) <= kun
