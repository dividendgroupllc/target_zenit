# Copyright (c) 2026, Target Zenit
"""Qo'ng'iroq yozuvini MATNGA aylantirish (1-bosqich — xulosa/tahlil YO'Q).

Oqim:
    yozuv kelib tushadi (api._yozuvni_biriktir)
        → navbatga(qongiroq)        [frappe.enqueue, queue="long"]
        → transkripsiya_qil(...)    [provayder: gemini / faster_whisper / mohir]
        → Telefon Qongirogi.transkript + holat="Transkripsiya"

Nega fon vazifasi: transkripsiya 5–60 sekund oladi. Uni ingest so'rovi ichida
bajarish Android ilovasini kutib qoldiradi va yuklash timeout bo'ladi.

Nega holat bilan boshqaramiz: `holat` maydoni allaqachon
Yangi → Yozuv bor → Transkripsiya → Tahlil qilindi zanjirini nazarda tutgan.
Shuning uchun yangi "qilindi/qilinmadi" flagi qo'shilmaydi.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from target_zenit.telefoniya import storage

# Gemini bitta so'rovga 20 MB (prompt + fayl). Base64 ~1.37x kattalashtiradi,
# shuning uchun xom fayl uchun xavfsiz chegara ~13 MB.
MAKS_INLINE_BAYT = 13 * 1024 * 1024

# Qayta urinish: 429 (limit) va 5xx (503 "high demand") — vaqtinchalik xatolar.
URINISH = 4
KUTISH = (2, 8, 25)          # sekund: urinishlar orasidagi pauza
VAQTINCHALIK_KODLAR = {408, 429, 500, 502, 503, 504, 529}


PAUZA_KALIT = "tz_stt_kvota_pauza"   # cache: kvota tugaganda shu vaqtgacha tegmaymiz
KVOTA_CHEGARA = 600                  # sek: bundan uzoq kutish talab qilinsa — kunlik kvota


class VaqtinchalikXato(Exception):
	"""Provayder tomonidagi o'tkinchi muammo (band, limit, tarmoq).

	Doimiy xatodan (noto'g'ri kalit, buzuq fayl) ataylab ajratilgan: doimiy xatoda
	hujjat `holat="Xato"` bo'lib navbatdan chiqadi, vaqtinchalik xatoda esa
	`holat="Yozuv bor"` qolib, soatlik vazifa uni qayta oladi.
	"""


class KvotaXato(VaqtinchalikXato):
	"""Kunlik/daqiqalik kvota tugagan (429).

	Oddiy vaqtinchalik xatodan farqi: qayta urinishning MA'NOSI YO'Q — kvota soatlar
	o'tib tiklanadi. Shuning uchun darhol to'xtaymiz va butun quvurni `kutish_sek`
	muddatiga pauzaga qo'yamiz. Aks holda `*/15` cron kun bo'yi har 15 daqiqada
	tugagan kvotaga so'rov yog'dirardi.
	"""

	def __init__(self, matn: str, kutish_sek: int = 0):
		super().__init__(matn)
		self.kutish_sek = kutish_sek


def _kutishni_oqi(matn: str) -> int:
	"""Gemini xabaridan kutish vaqtini sekundda ajratadi.

	Namuna: "Please retry in 17h26m2s" / "retryDelay": "34s"
	"""
	import re

	m = re.search(r"retry\s+in\s+(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", matn, re.I)
	if not m or not any(m.groups()):
		m = re.search(r"retryDelay\"?:?\s*\"?(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", matn, re.I)
	if not m or not any(m.groups()):
		return 0
	soat, daq, sek = (float(x or 0) for x in m.groups())
	return int(soat * 3600 + daq * 60 + sek)


def _pauza_qoy(sekund: int, sabab: str) -> None:
	"""Butun STT/tahlil quvurini `sekund` muddatiga pauzaga qo'yadi."""
	from frappe.utils import add_to_date, now_datetime

	sekund = max(60, min(int(sekund or 0) or 3600, 24 * 3600))
	qiymat = {"gacha": str(add_to_date(now_datetime(), seconds=sekund)), "sabab": sabab[:300]}
	frappe.cache().set_value(PAUZA_KALIT, qiymat, expires_in_sec=sekund)
	frappe.logger("telefoniya").warning(f"STT pauza {sekund}s: {sabab}")


def pauza_holati() -> dict:
	"""Pauza bormi: {"bor": bool, "gacha": str|None, "qolgan_sek": int, "sabab": str|None}"""
	from frappe.utils import now_datetime, time_diff_in_seconds

	q = frappe.cache().get_value(PAUZA_KALIT)
	if not isinstance(q, dict) or not q.get("gacha"):
		return {"bor": False, "gacha": None, "qolgan_sek": 0, "sabab": None}
	qolgan = int(time_diff_in_seconds(q["gacha"], now_datetime()))
	if qolgan <= 0:
		frappe.cache().delete_value(PAUZA_KALIT)
		return {"bor": False, "gacha": None, "qolgan_sek": 0, "sabab": None}
	return {"bor": True, "gacha": q["gacha"], "qolgan_sek": qolgan, "sabab": q.get("sabab")}


@frappe.whitelist()
def pauza_holati_api() -> dict:
	"""Formadagi JS uchun — `pauza_holati()`ning whitelist qobig'i."""
	return pauza_holati()


@frappe.whitelist()
def pauzani_bekor() -> dict:
	"""Pauzani qo'lda olib tashlash (tarif ko'tarilgandan keyin kutib o'tirmaslik uchun)."""
	frappe.only_for(("System Manager", "Sales Manager"))
	frappe.cache().delete_value(PAUZA_KALIT)
	return {"ok": 1}

MIME = {
	"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "opus": "audio/ogg",
	"m4a": "audio/mp4", "aac": "audio/aac", "amr": "audio/amr", "3gp": "audio/3gpp",
	"webm": "audio/webm", "flac": "audio/flac",
}

# Sotuv qo'ng'irog'i: o'zbekcha, ichida rus/ingliz so'zlari aralash.
# Prompt ataylab "faqat matn" deb qattiq aytadi — xulosa 2-bosqichda.
PROMPT = (
	"Bu o'zbek maktabining sotuv menejeri bilan mijoz (ota-ona) o'rtasidagi "
	"telefon qo'ng'irog'i yozuvi. Nutq asosan o'zbek tilida, ichida rus va "
	"ingliz tilidagi so'zlar aralash kelishi mumkin.\n\n"
	"VAZIFA: suhbatni so'zma-so'z matnga aylantir.\n\n"
	"QOIDALAR:\n"
	"- So'zlovchilarni ajrat: har qatorni 'MENEJER:' yoki 'MIJOZ:' bilan boshla.\n"
	"- Ruscha/inglizcha so'zlar AYTILGANIDEK qoldirilsin — tarjima qilinmasin.\n"
	"- Hech narsa qo'shma, qisqartirma, tuzatma, xulosa yozma.\n"
	"- Eshitilmagan joyni [eshitilmadi] deb belgila.\n"
	"- Agar audioda nutq bo'lmasa (jimlik, signal, avtojavob), faqat "
	"[nutq yo'q] deb yoz.\n"
	"- Javobda FAQAT transkript bo'lsin, boshqa izoh bo'lmasin."
)


# ---------------------------------------------------------------- sozlamalar
def _sozlamalar() -> dict:
	s = frappe.get_cached_doc("Telefoniya Sozlamalari")
	return {
		"yoqilgan": bool(cint(s.ai_yoqilgan)),
		"provayder": (s.stt_provayder or "yoq").strip(),
		"model": (getattr(s, "gemini_model", None) or "gemini-3.8-flash").strip(),
		"til": (getattr(s, "stt_til", None) or "uz").strip(),
		"min_sek": cint(getattr(s, "stt_min_sekund", None)) or 5,
		"maks_daq": cint(getattr(s, "stt_maks_daqiqa", None)) or 30,
		"zaxira": (getattr(s, "stt_zaxira_model", None) or "").strip(),
		"kalit": _kalit(s),
	}


def _kalit(s) -> str:
	"""API kalit: avval Sozlamalardan (shifrlangan), bo'lmasa site_config.json'dan."""
	try:
		if getattr(s, "gemini_api_kalit", None):
			return (s.get_password("gemini_api_kalit") or "").strip()
	except Exception:
		pass
	return (frappe.conf.get("gemini_api_key") or "").strip()


# ---------------------------------------------------------------- navbat
def navbatga(qongiroq: str, majburiy: bool = False) -> bool:
	"""Yozuv kelganda chaqiriladi. Fon vazifasiga qo'yadi (yoki jimgina o'tkazadi)."""
	s = _sozlamalar()
	if not majburiy and (not s["yoqilgan"] or s["provayder"] == "yoq"):
		return False
	# Kvota tugagan bo'lsa navbatga ham qo'ymaymiz — vazifa darhol yiqilib,
	# faqat log'ni to'ldirardi. Pauza tugashi bilan cron o'zi yig'ib oladi.
	if pauza_holati()["bor"]:
		return False
	frappe.enqueue(
		"target_zenit.telefoniya.stt.transkripsiya_qil",
		queue="long", timeout=1800, job_name=f"stt:{qongiroq}",
		enqueue_after_commit=True,
		qongiroq=qongiroq, majburiy=majburiy,
	)
	return True


@frappe.whitelist()
def qolda(qongiroq: str) -> dict:
	"""Formadagi «Transkripsiya qilish» tugmasi — sozlama o'chiq bo'lsa ham ishlaydi.

	Kvota pauzasi bor bo'lsa so'rov YUBORILMAYDI: foydalanuvchiga xom 429 matnini
	ko'rsatish o'rniga qancha kutish kerakligini aytamiz. Pauzani Sozlamalardagi
	tugma bilan olib tashlash mumkin (tarif ko'tarilgan bo'lsa).
	"""
	frappe.has_permission("Telefon Qongirogi", "write", doc=qongiroq, throw=True)
	p = pauza_holati()
	if p["bor"]:
		return {"holat": "kvota", "sabab": _kvota_xabari(p), "kutish_sek": p["qolgan_sek"]}
	return transkripsiya_qil(qongiroq, majburiy=True, qayta=True)


def _kvota_xabari(p: dict) -> str:
	soat, daq = p["qolgan_sek"] // 3600, p["qolgan_sek"] % 3600 // 60
	vaqt = f"{soat} soat {daq} daqiqa" if soat else f"{daq} daqiqa"
	return (f"Kunlik AI kvotasi tugagan — {vaqt}dan keyin tiklanadi. "
	        f"Tarifni ko'tarsangiz, Telefoniya Sozlamalaridan «Kvota pauzasini olib tashlash»ni bosing.")


# ---------------------------------------------------------------- asosiy ish
def transkripsiya_qil(qongiroq: str, majburiy: bool = False, qayta: bool = False) -> dict:
	"""Bitta qo'ng'iroq yozuvini matnga aylantiradi. Idempotent."""
	doc = frappe.get_doc("Telefon Qongirogi", qongiroq)
	s = _sozlamalar()

	if not majburiy and (not s["yoqilgan"] or s["provayder"] == "yoq"):
		return {"holat": "o'tkazildi", "sabab": "AI o'chirilgan"}
	if doc.transkript and not qayta:
		return {"holat": "o'tkazildi", "sabab": "transkript allaqachon bor"}
	if not doc.yozuv_bor or not doc.fayl_yoli or doc.yozuv_ochirildi:
		return {"holat": "o'tkazildi", "sabab": "yozuv yo'q"}
	if not storage.bormi(doc.fayl_yoli):
		_xato(doc, "Yozuv fayli diskda topilmadi")
		return {"holat": "xato", "sabab": "fayl yo'q"}

	toliq = os.path.join(storage.baza_papka(), doc.fayl_yoli)
	davomiylik = _davomiylik(toliq)
	if davomiylik and davomiylik != doc.yozuv_davomiyligi:
		doc.db_set("yozuv_davomiyligi", int(davomiylik), update_modified=False)

	# Pul tejash: juda qisqa (javob berilmagan / signal) va juda uzun yozuvlar
	if davomiylik and davomiylik < s["min_sek"]:
		return {"holat": "o'tkazildi", "sabab": f"qisqa yozuv ({davomiylik:.0f}s)"}
	if davomiylik and davomiylik > s["maks_daq"] * 60:
		_xato(doc, f"Yozuv juda uzun: {davomiylik/60:.0f} daq (chegara {s['maks_daq']} daq)")
		return {"holat": "xato", "sabab": "uzun"}

	hajm = os.path.getsize(toliq)
	if hajm > MAKS_INLINE_BAYT:
		_xato(doc, f"Fayl juda katta: {hajm/1048576:.1f} MB (chegara {MAKS_INLINE_BAYT/1048576:.0f} MB)")
		return {"holat": "xato", "sabab": "katta fayl"}

	try:
		if s["provayder"] == "gemini":
			matn, model = _gemini(toliq, s)
		elif s["provayder"] == "faster_whisper":
			matn, model = _faster_whisper(toliq, s)
		elif s["provayder"] == "mohir":
			matn, model = _mohir(toliq, s)
		else:
			frappe.throw(_("Noma'lum STT provayder: {0}").format(s["provayder"]))
	except KvotaXato as e:
		# Kunlik kvota tugagan — hujjat navbatda qoladi, quvur pauzaga tushadi
		# (pauza `_gemini` ichida qo'yiladi). Pul va log bekorga sarflanmaydi.
		doc.db_set("xato_matni", f"Kvota tugagan: {e}"[:500], notify=True)
		frappe.db.commit()
		return {"holat": "kvota", "sabab": str(e)[:300],
		        "kutish_sek": e.kutish_sek, "qayta": "kvota tiklanganda cron uradi"}
	except VaqtinchalikXato as e:
		# Provayder band/limit — hujjat navbatda QOLADI (holat "Yozuv bor"), faqat
		# sabab yoziladi. Soatlik `qolganlarni_qil` keyinroq qayta uradi.
		doc.db_set("xato_matni", f"Vaqtinchalik: {e}"[:500], notify=True)
		frappe.db.commit()
		return {"holat": "vaqtinchalik", "sabab": str(e)[:300], "qayta": "soatlik vazifa uradi"}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"STT xato: {qongiroq}")
		_xato(doc, f"{type(e).__name__}: {e}"[:500])
		return {"holat": "xato", "sabab": str(e)[:200]}

	matn = (matn or "").strip()
	if not matn:
		_xato(doc, "Provayder bo'sh matn qaytardi")
		return {"holat": "xato", "sabab": "bo'sh matn"}

	doc.db_set({
		"transkript": matn,
		"stt_model": model[:140],
		"transkript_tili": s["til"][:16],
		"transkripsiya_vaqti": now_datetime(),
		"transkript_sozlar": len(matn.split()),
		"holat": "Transkripsiya",
		"xato_matni": None,
	}, notify=True)
	frappe.db.commit()

	# Transkript tayyor — endi qisqa tahlilni navbatga qo'yamiz (2-bosqich).
	# Alohida vazifa: tahlil yiqilsa transkript saqlanib qolishi kerak.
	try:
		from target_zenit.telefoniya import analiz
		analiz.navbatga(qongiroq, majburiy=majburiy)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Tahlil navbatga qo'yilmadi: {qongiroq}")

	return {
		"holat": "tayyor", "sozlar": len(matn.split()),
		"model": model, "davomiylik": davomiylik,
	}


def _xato(doc, matn: str) -> None:
	doc.db_set({"holat": "Xato", "xato_matni": matn}, notify=True)
	frappe.db.commit()


def _davomiylik(yol: str) -> float | None:
	"""Audio davomiyligi (sekund) — faylning o'zidan, ffprobe bilan.

	Metadatadagi `suhbat_vaqti`ga ishonmaymiz: u Asterisk/Android yuborgan
	qiymat va fayldagi haqiqiy davomiylikdan farq qilishi mumkin (yozuv
	keyinroq boshlangan yoki uzilib qolgan bo'lsa).
	"""
	try:
		chiqdi = subprocess.run(
			["ffprobe", "-v", "error", "-show_entries", "format=duration",
			 "-of", "default=nw=1:nk=1", yol],
			capture_output=True, text=True, timeout=30,
		)
		return float(chiqdi.stdout.strip()) if chiqdi.returncode == 0 else None
	except Exception:
		return None


# ---------------------------------------------------------------- provayderlar
def _gemini(yol: str, s: dict) -> tuple[str, str]:
	"""Google Gemini — audioni to'g'ridan-to'g'ri oladi (STT+diarizatsiya bir so'rovda).

	Modellar ro'yxati bo'yicha ketadi: asosiy model, keyin (sozlangan bo'lsa) zaxira.
	Har biri bir necha marta qayta uriniladi — 503 "high demand" o'tkinchi holat.
	"""
	if not s["kalit"]:
		frappe.throw(_("Gemini API kalit kiritilmagan (Telefoniya Sozlamalari)."))

	kengaytma = yol.rsplit(".", 1)[-1].lower()
	with open(yol, "rb") as f:
		b64 = base64.standard_b64encode(f.read()).decode()

	modellar = [s["model"]] + ([s["zaxira"]] if s.get("zaxira") and s["zaxira"] != s["model"] else [])
	oxirgi: Exception | None = None

	kvota_hammasida = True
	for model in modellar:
		try:
			return _gemini_soro(model, b64, kengaytma, s["kalit"]), model
		except KvotaXato as e:
			# Bu modelning kvotasi tugagan — zaxira modelning kvotasi ALOHIDA,
			# shuning uchun unga o'tishning ma'nosi bor.
			oxirgi = e
			if model != modellar[-1]:
				frappe.logger("telefoniya").warning(f"STT: {model} kvotasi tugagan, zaxiraga o'tildi")
			continue
		except VaqtinchalikXato as e:
			# Band (503) — kvota emas, demak keyinroq qayta urinish mantiqiy
			oxirgi = e
			kvota_hammasida = False
			if model != modellar[-1]:
				frappe.logger("telefoniya").warning(f"STT: {model} band, zaxiraga o'tildi: {e}")
			continue

	# Hamma model kvotaga urildi — butun quvurni pauzaga qo'yamiz
	if kvota_hammasida and isinstance(oxirgi, KvotaXato):
		_pauza_qoy(oxirgi.kutish_sek, str(oxirgi))
	raise oxirgi or VaqtinchalikXato("Gemini javob bermadi")


def _gemini_soro(model: str, b64: str, kengaytma: str, kalit: str) -> str:
	"""Bitta modelga so'rov — vaqtinchalik xatolarda qayta urinadi."""
	import random
	import time

	import requests

	body = {
		"model": model,
		"input": [
			{"type": "text", "text": PROMPT},
			{"type": "audio", "data": b64, "mime_type": MIME.get(kengaytma, "audio/mpeg")},
		],
	}

	for urinish in range(URINISH):
		try:
			r = requests.post(
				"https://generativelanguage.googleapis.com/v1beta/interactions",
				headers={"x-goog-api-key": kalit, "Content-Type": "application/json"},
				json=body, timeout=900,
			)
		except requests.RequestException as e:
			sabab = VaqtinchalikXato(f"tarmoq: {type(e).__name__}")
		else:
			if r.status_code == 200:
				return _gemini_matn(r.json())
			if r.status_code == 429:
				# Kvota: qayta urinish befoyda. Boshqa modelning kvotasi alohida,
				# shuning uchun bu yerda to'xtaymiz — `_gemini` zaxira modelni sinaydi.
				kut = _kutishni_oqi(r.text)
				xabar = f"Gemini 429 ({model}): {r.text[:220]}"
				if kut >= KVOTA_CHEGARA or "per day" in r.text.lower():
					raise KvotaXato(xabar, kutish_sek=kut or 3600)
				sabab = VaqtinchalikXato(xabar)
			elif r.status_code in VAQTINCHALIK_KODLAR:
				sabab = VaqtinchalikXato(f"Gemini {r.status_code} ({model}): {r.text[:200]}")
			else:
				# 400/401/403 — kalit, model nomi yoki fayl muammosi. Qayta urinish
				# foyda bermaydi, shuning uchun darhol doimiy xato beramiz.
				frappe.throw(_("Gemini {0} ({1}): {2}").format(r.status_code, model, r.text[:400]))

		if urinish < URINISH - 1:
			kut = KUTISH[min(urinish, len(KUTISH) - 1)] + random.uniform(0, 2)
			frappe.logger("telefoniya").warning(
				f"STT qayta urinish {urinish + 1}/{URINISH} ({kut:.0f}s kutib): {sabab}")
			time.sleep(kut)

	raise sabab


def _gemini_matn(javob: dict) -> str:
	"""Javobdan matnni ajratadi — API shakli o'zgarishiga chidamli."""
	if isinstance(javob.get("output_text"), str):
		return javob["output_text"]

	bolaklar: list[str] = []

	def yur(x):
		if isinstance(x, dict):
			if isinstance(x.get("text"), str) and x.get("type") in (None, "text", "output_text"):
				bolaklar.append(x["text"])
			for v in x.values():
				yur(v)
		elif isinstance(x, list):
			for v in x:
				yur(v)

	for kalit in ("output", "candidates", "response"):
		if kalit in javob:
			yur(javob[kalit])
			if bolaklar:
				break
	if not bolaklar:
		yur(javob)
	if not bolaklar:
		frappe.throw(_("Gemini javobidan matn ajratilmadi: {0}").format(
			json.dumps(javob, ensure_ascii=False)[:400]))
	return "\n".join(bolaklar).strip()


def _faster_whisper(yol: str, s: dict) -> tuple[str, str]:
	"""Self-hosted, bepul. O'zbekchada aniqligi past (WER ~30%) — ingliz uchun yaxshi.
	Serverda: ./env/bin/pip install faster-whisper"""
	try:
		from faster_whisper import WhisperModel
	except ImportError:
		frappe.throw(_("faster-whisper o'rnatilmagan: ./env/bin/pip install faster-whisper"))

	model = WhisperModel("large-v3", compute_type="int8")
	segmentlar, _info = model.transcribe(yol, language=s["til"] or None, vad_filter=True)
	return " ".join(x.text.strip() for x in segmentlar).strip(), "faster-whisper:large-v3"


def _mohir(yol: str, s: dict) -> tuple[str, str]:
	"""Mahalliy o'zbek provayderi (mohir.ai / muxlisa.uz) — ma'lumot mamlakatda qoladi.
	Kalit va endpoint har provayderga xos; ulanganda shu yerga yoziladi."""
	frappe.throw(_("Mohir/Muxlisa provayderi hali ulanmagan — 'gemini' tanlang."))


# ---------------------------------------------------------------- avto ulanish
def qongiroq_on_update(doc, method=None) -> None:
	"""`Telefon Qongirogi` saqlanganda — yozuv bor-u transkript yo'q bo'lsa navbatga.

	Asosiy avto yo'l `api._yozuvni_biriktir` ichida (yozuv kelgan zahoti). Bu esa
	zaxira: hujjat qo'lda tahrirlansa, boshqa koddan saqlansa yoki kelgusida
	yangi yuklash yo'li paydo bo'lsa ham transkripsiya o'tkazib yuborilmaydi.
	`db_set` doc event'larni chaqirmaydi, shuning uchun ikkisi takrorlanmaydi.
	"""
	if not doc.get("yozuv_bor") or doc.get("yozuv_ochirildi"):
		return
	if doc.get("transkript") or not doc.get("fayl_yoli"):
		return
	if doc.get("holat") == "Xato":
		# Doimiy xato — qayta urinish foyda bermaydi (kalit/fayl muammosi).
		# Vaqtinchalik xatoda holat "Yozuv bor"da qoladi, demak bu yerga tushadi.
		return
	try:
		navbatga(doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"STT navbatga qo'yilmadi: {doc.name}")


@frappe.whitelist()
def avto_holat() -> dict:
	"""Avto transkripsiya ishlayaptimi — va ishlamasa NEGA.

	Sozlamada ikkita o'chirgich bor (`ai_yoqilgan` va `stt_provayder`), shuning
	uchun "yoqdim, lekin ishlamaydi" holati juda oson yuzaga keladi. Bu funksiya
	aniq sababni aytadi.
	"""
	s = _sozlamalar()
	sabablar = []
	if not s["yoqilgan"]:
		sabablar.append("«AI yoqilgan» belgilanmagan")
	if s["provayder"] == "yoq":
		sabablar.append("«Nutq→matn provayderi» = yoq")
	if s["provayder"] == "gemini" and not s["kalit"]:
		sabablar.append("Gemini API kalit kiritilmagan")

	bor = {"yozuv_bor": 1, "yozuv_ochirildi": 0}
	jami = frappe.db.count("Telefon Qongirogi", bor)
	tayyor = frappe.db.count("Telefon Qongirogi", {**bor, "transkript": ["is", "set"]})
	xato = frappe.db.count("Telefon Qongirogi", {**bor, "holat": "Xato"})
	p = pauza_holati()
	if p["bor"]:
		sabablar.append(
			f"Kvota tugagan — {p['qolgan_sek'] // 3600} soat {p['qolgan_sek'] % 3600 // 60} daqiqadan keyin tiklanadi"
		)

	tahlil = frappe.db.count("Telefon Qongirogi", {"ai_xulosa": ["is", "set"]})
	return {
		"ishlayapti": not sabablar,
		"pauza": p,
		"sabablar": sabablar,
		"tahlil_bor": tahlil,
		"provayder": s["provayder"],
		"model": s["model"],
		"zaxira": s["zaxira"] or None,
		"jami_yozuv": jami,
		"transkript_bor": tayyor,
		"navbatda": max(0, jami - tayyor - xato),
		"xato": xato,
	}


@frappe.whitelist()
def hammasini_qil(limit: int = 500) -> dict:
	"""Mavjud (eski) yozuvlarni bir martalik navbatga qo'yish — backfill.

	`qolganlarni_qil` har 15 daqiqada kichik partiya oladi (kutilmagan xarajatni
	cheklash uchun). Eski arxivni bir yo'la o'tkazish esa ataylab qo'lda qaror.
	"""
	frappe.only_for(("System Manager", "Sales Manager"))
	return qolganlarni_qil(limit=cint(limit), majburiy=True)


# ---------------------------------------------------------------- qolganlar
def qolganlarni_qil(limit: int = 20, majburiy: bool = False) -> dict:
	"""Soatlik vazifa: yozuvi bor, lekin transkript qilinmagan qo'ng'iroqlar.

	Nega kerak: `navbatga()` ingest paytida chaqiriladi, lekin worker o'chgan,
	kalit noto'g'ri yoki sozlama keyinroq yoqilgan bo'lishi mumkin. Bu vazifa
	o'tkazib yuborilganlarni yig'ib oladi.
	"""
	s = _sozlamalar()
	if not majburiy and (not s["yoqilgan"] or s["provayder"] == "yoq"):
		return {"o'tkazildi": "AI o'chirilgan"}
	if s["provayder"] == "yoq":
		return {"o'tkazildi": "provayder tanlanmagan"}
	p = pauza_holati()
	if p["bor"]:
		return {"o'tkazildi": f"kvota pauzasi: {p['qolgan_sek'] // 60} daqiqa qoldi"}

	nomlar = frappe.get_all(
		"Telefon Qongirogi",
		filters={"yozuv_bor": 1, "yozuv_ochirildi": 0, "transkript": ["in", ("", None)],
		         "holat": ["!=", "Xato"]},
		pluck="name", order_by="boshlandi desc", limit_page_length=cint(limit),
	)
	for nom in nomlar:
		navbatga(nom, majburiy=majburiy)
	return {"navbatga_qoyildi": len(nomlar)}
