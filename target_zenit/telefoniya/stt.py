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
	frappe.enqueue(
		"target_zenit.telefoniya.stt.transkripsiya_qil",
		queue="long", timeout=1800, job_name=f"stt:{qongiroq}",
		enqueue_after_commit=True,
		qongiroq=qongiroq, majburiy=majburiy,
	)
	return True


@frappe.whitelist()
def qolda(qongiroq: str) -> dict:
	"""Formadagi «Transkripsiya qilish» tugmasi — sozlama o'chiq bo'lsa ham ishlaydi."""
	frappe.has_permission("Telefon Qongirogi", "write", doc=qongiroq, throw=True)
	return transkripsiya_qil(qongiroq, majburiy=True, qayta=True)


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
	"""Google Gemini — audioni to'g'ridan-to'g'ri oladi (STT+diarizatsiya bir so'rovda)."""
	import requests

	if not s["kalit"]:
		frappe.throw(_("Gemini API kalit kiritilmagan (Telefoniya Sozlamalari)."))

	kengaytma = yol.rsplit(".", 1)[-1].lower()
	with open(yol, "rb") as f:
		b64 = base64.standard_b64encode(f.read()).decode()

	r = requests.post(
		"https://generativelanguage.googleapis.com/v1beta/interactions",
		headers={"x-goog-api-key": s["kalit"], "Content-Type": "application/json"},
		json={
			"model": s["model"],
			"input": [
				{"type": "text", "text": PROMPT},
				{"type": "audio", "data": b64,
				 "mime_type": MIME.get(kengaytma, "audio/mpeg")},
			],
		},
		timeout=900,
	)
	if r.status_code != 200:
		frappe.throw(_("Gemini {0}: {1}").format(r.status_code, r.text[:400]))
	return _gemini_matn(r.json()), s["model"]


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


# ---------------------------------------------------------------- qolganlar
def qolganlarni_qil(limit: int = 20) -> dict:
	"""Soatlik vazifa: yozuvi bor, lekin transkript qilinmagan qo'ng'iroqlar.

	Nega kerak: `navbatga()` ingest paytida chaqiriladi, lekin worker o'chgan,
	kalit noto'g'ri yoki sozlama keyinroq yoqilgan bo'lishi mumkin. Bu vazifa
	o'tkazib yuborilganlarni yig'ib oladi.
	"""
	s = _sozlamalar()
	if not s["yoqilgan"] or s["provayder"] == "yoq":
		return {"o'tkazildi": "AI o'chirilgan"}

	nomlar = frappe.get_all(
		"Telefon Qongirogi",
		filters={"yozuv_bor": 1, "yozuv_ochirildi": 0, "transkript": ["in", ("", None)],
		         "holat": ["!=", "Xato"]},
		pluck="name", order_by="boshlandi desc", limit_page_length=cint(limit),
	)
	for nom in nomlar:
		navbatga(nom)
	return {"navbatga_qoyildi": len(nomlar)}
