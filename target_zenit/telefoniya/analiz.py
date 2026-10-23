# Copyright (c) 2026, Target Zenit
"""Qo'ng'iroq transkriptining QISQA tahlili (2-bosqich).

Oqim:  transkript tayyor (stt.transkripsiya_qil)
           → navbatga(qongiroq)
           → tahlil_qil(...)  — Gemini matnni o'qiydi
           → Telefon Qongirogi.ai_xulosa + holat="Tahlil qilindi"

Nega audio emas, MATN tahlil qilinadi: matn tokeni audio tokenidan ~10 barobar
arzon (45 daqiqalik suhbat audiosi ~67k token, matni ~3k token), natija esa
pedagogik/sotuv xulosasi uchun bir xil. Audio faqat 1-bosqichda kerak.

Nega alohida modul: transkripsiya (stt.py) aniqlik masalasi — o'lchab bo'ladi;
tahlil esa talqin masalasi — prompt tez-tez o'zgaradi. Ikkisini aralashtirsak
promptni tuzatish uchun ishlab turgan transkripsiyaga tegishga majbur bo'lardik.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from target_zenit.telefoniya import stt

# Qarzdorlik/sotuv konteksti: menejer ota-onaga qo'ng'iroq qiladi.
# Format ataylab QAT'IY — panelda yonma-yon solishtirish uchun bir xil ko'rinish kerak.
PROMPT = """Quyida xususiy maktab menejeri va ota-ona o'rtasidagi telefon suhbati matni.

Vazifa: suhbatning ENG MUHIM joylarini qisqa tahlil qil. Uzun yozma — menejer
rahbari bir qarashda tushunadigan darajada qisqa bo'lsin.

Javobni ANIQ shu formatda ber (har qator bitta satr, qo'shimcha izoh yozma):

MAVZU: <suhbat nima haqida — 1 qisqa gap>
NATIJA: <nima bilan tugadi — 1 qisqa gap>
KELISHUV: <aniq kelishuv bo'lsa yoz: summa va sana. Bo'lmasa: yo'q>
E'TIROZ: <mijozning asosiy e'tirozi yoki sababi. Bo'lmasa: yo'q>
MIJOZ HOLATI: <biridan birini tanla: Ijobiy / Neytral / Qarshi / Bog'lanmadi>
KEYINGI QADAM: <menejer nima qilishi kerak — 1 qisqa gap>
DIQQAT: <rahbar bilishi shart bo'lgan muhim narsa bo'lsa yoz, bo'lmasa: yo'q>

Qoidalar:
- Faqat matnda BOR narsani yoz, taxmin qilma, o'zingdan qo'shma.
- Summalar va sanalarni matndagidek aniq ko'rsat.
- Matn juda qisqa yoki tushunarsiz bo'lsa: MAVZU: aniqlanmadi — qolganlarga: yo'q
- O'zbek tilida yoz.

SUHBAT MATNI:
---
{matn}
---"""

MAKS_BELGI = 60_000       # juda uzun transkriptni kesamiz (token xarajati nazorati)


def navbatga(qongiroq: str, majburiy: bool = False) -> bool:
	"""Transkript tayyor bo'lgandan keyin chaqiriladi."""
	s = stt._sozlamalar()
	if not majburiy and (not s["yoqilgan"] or s["provayder"] != "gemini"):
		return False
	if stt.pauza_holati()["bor"]:
		return False
	frappe.enqueue(
		"target_zenit.telefoniya.analiz.tahlil_qil",
		queue="long", timeout=900, job_name=f"analiz:{qongiroq}",
		enqueue_after_commit=True,
		qongiroq=qongiroq, majburiy=majburiy,
	)
	return True


@frappe.whitelist()
def qolda(qongiroq: str) -> dict:
	"""Formadagi/paneldagi «Tahlil qilish» tugmasi (kvota pauzasini hurmat qiladi)."""
	frappe.has_permission("Telefon Qongirogi", "write", doc=qongiroq, throw=True)
	p = stt.pauza_holati()
	if p["bor"]:
		return {"holat": "kvota", "sabab": stt._kvota_xabari(p), "kutish_sek": p["qolgan_sek"]}
	return tahlil_qil(qongiroq, majburiy=True, qayta=True)


def tahlil_qil(qongiroq: str, majburiy: bool = False, qayta: bool = False) -> dict:
	"""Bitta qo'ng'iroq transkriptini tahlil qiladi. Idempotent."""
	doc = frappe.get_doc("Telefon Qongirogi", qongiroq)
	s = stt._sozlamalar()

	if not majburiy and (not s["yoqilgan"] or s["provayder"] != "gemini"):
		return {"holat": "o'tkazildi", "sabab": "AI o'chirilgan"}
	if not doc.transkript:
		return {"holat": "o'tkazildi", "sabab": "transkript yo'q"}
	if doc.ai_xulosa and not qayta:
		return {"holat": "o'tkazildi", "sabab": "tahlil allaqachon bor"}

	matn = (doc.transkript or "").strip()
	# Nutq yo'q bo'lsa tahlil qilib pul sarflashning ma'nosi yo'q
	if "[nutq yo'q]" in matn.lower() or len(matn.split()) < 5:
		doc.db_set({
			"ai_xulosa": "MAVZU: aniqlanmadi (nutq yo'q yoki juda qisqa)",
			"ai_model": "—", "ai_tahlil_vaqti": now_datetime(),
			"holat": "Tahlil qilindi",
		}, notify=True)
		frappe.db.commit()
		return {"holat": "tayyor", "sabab": "nutq yo'q"}

	try:
		xulosa, model = _gemini_matn_tahlil(matn[:MAKS_BELGI], s)
	except stt.KvotaXato as e:
		doc.db_set("xato_matni", f"Kvota tugagan: {e}"[:500], notify=True)
		frappe.db.commit()
		return {"holat": "kvota", "sabab": str(e)[:300], "kutish_sek": e.kutish_sek}
	except stt.VaqtinchalikXato as e:
		doc.db_set("xato_matni", f"Tahlil vaqtinchalik: {e}"[:500], notify=True)
		frappe.db.commit()
		return {"holat": "vaqtinchalik", "sabab": str(e)[:300]}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), f"AI tahlil xato: {qongiroq}")
		doc.db_set("xato_matni", f"Tahlil xato: {type(e).__name__}: {e}"[:500], notify=True)
		frappe.db.commit()
		return {"holat": "xato", "sabab": str(e)[:200]}

	doc.db_set({
		"ai_xulosa": (xulosa or "").strip(),
		"ai_model": model[:140],
		"ai_tahlil_vaqti": now_datetime(),
		"holat": "Tahlil qilindi",
		"xato_matni": None,
	}, notify=True)
	frappe.db.commit()
	return {"holat": "tayyor", "model": model, "xulosa": xulosa}


def _gemini_matn_tahlil(matn: str, s: dict) -> tuple[str, str]:
	"""Faqat matn yuboriladi (audio emas) — shuning uchun arzon va tez."""
	import random
	import time

	import requests

	if not s["kalit"]:
		frappe.throw(_("Gemini API kalit kiritilmagan (Telefoniya Sozlamalari)."))

	modellar = [s["model"]] + ([s["zaxira"]] if s.get("zaxira") and s["zaxira"] != s["model"] else [])
	oxirgi: Exception | None = None
	kvota_hammasida = True

	for model in modellar:
		body = {"model": model, "input": [{"type": "text", "text": PROMPT.format(matn=matn)}]}
		for urinish in range(stt.URINISH):
			try:
				r = requests.post(
					"https://generativelanguage.googleapis.com/v1beta/interactions",
					headers={"x-goog-api-key": s["kalit"], "Content-Type": "application/json"},
					json=body, timeout=300,
				)
			except requests.RequestException as e:
				oxirgi = stt.VaqtinchalikXato(f"tarmoq: {type(e).__name__}")
			else:
				if r.status_code == 200:
					return stt._gemini_matn(r.json()), model
				if r.status_code == 429:
					# Kvota tugagan — qayta urinish befoyda, keyingi modelga o'tamiz
					kut = stt._kutishni_oqi(r.text)
					xabar = f"Gemini 429 ({model}): {r.text[:220]}"
					if kut >= stt.KVOTA_CHEGARA or "per day" in r.text.lower():
						oxirgi = stt.KvotaXato(xabar, kutish_sek=kut or 3600)
						break
					oxirgi = stt.VaqtinchalikXato(xabar)
				elif r.status_code in stt.VAQTINCHALIK_KODLAR:
					oxirgi = stt.VaqtinchalikXato(f"Gemini {r.status_code} ({model}): {r.text[:200]}")
					kvota_hammasida = False
				else:
					frappe.throw(_("Gemini {0} ({1}): {2}").format(r.status_code, model, r.text[:400]))
			if urinish < stt.URINISH - 1:
				time.sleep(stt.KUTISH[min(urinish, len(stt.KUTISH) - 1)] + random.uniform(0, 2))

	# Hamma model kvotaga urildi — butun quvurni pauzaga qo'yamiz
	if kvota_hammasida and isinstance(oxirgi, stt.KvotaXato):
		stt._pauza_qoy(oxirgi.kutish_sek, str(oxirgi))
	raise oxirgi or stt.VaqtinchalikXato("Gemini javob bermadi")


# ---------------------------------------------------------------- qolganlar
def qolganlarni_qil(limit: int = 60, majburiy: bool = False) -> dict:
	"""Transkripti bor, lekin tahlili yo'q qo'ng'iroqlar (cron zaxirasi)."""
	s = stt._sozlamalar()
	if not majburiy and (not s["yoqilgan"] or s["provayder"] != "gemini"):
		return {"o'tkazildi": "AI o'chirilgan"}
	p = stt.pauza_holati()
	if p["bor"]:
		return {"o'tkazildi": f"kvota pauzasi: {p['qolgan_sek'] // 60} daqiqa qoldi"}

	nomlar = frappe.get_all(
		"Telefon Qongirogi",
		filters={"transkript": ["is", "set"], "ai_xulosa": ["in", ("", None)]},
		pluck="name", order_by="boshlandi desc", limit_page_length=cint(limit),
	)
	for nom in nomlar:
		navbatga(nom, majburiy=majburiy)
	return {"navbatga_qoyildi": len(nomlar)}


@frappe.whitelist()
def hammasini_qil(limit: int = 500) -> dict:
	frappe.only_for(("System Manager", "Sales Manager"))
	return qolganlarni_qil(limit=cint(limit), majburiy=True)
