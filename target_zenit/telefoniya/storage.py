# Copyright (c) 2026, Target Zenit
"""Ovoz yozuvlarini diskda saqlash qatlami.

Yozuvlar ataylab Frappe'ning `private/files` papkasidan TASHQARIDA saqlanadi:
`bench backup --with-files` faqat `public/files` va `private/files` ni tar qiladi,
shuning uchun bu papka zaxiraga kirmaydi. Aks holda bir necha oydan keyin har bir
backup o'n gigabaytlab o'sib ketardi.

Ruxsat nazorati yo'qolmaydi — fayl faqat `api.stream_recording` orqali beriladi,
u esa Telefon Qongirogi hujjatining o'qish huquqini tekshiradi.
"""

import os
import re

import frappe

SUKUTDAGI_PAPKA_NOMI = "call-recordings"


def baza_papka() -> str:
	"""Yozuvlar saqlanadigan ildiz papka (to'liq yo'l)."""
	sozlangan = (frappe.db.get_single_value("Telefoniya Sozlamalari", "yozuvlar_papkasi") or "").strip()
	papka = sozlangan or frappe.get_site_path("private", SUKUTDAGI_PAPKA_NOMI)
	return os.path.realpath(papka)


def nisbiy_yol(uniqueid: str, boshlandi, kengaytma: str = "mp3") -> str:
	"""Sana bo'yicha bo'lingan nisbiy yo'l: 2026/10/10/1760087423.481.mp3

	Sana bo'yicha bo'lish muhim: bitta papkada yuz minglab fayl bo'lsa
	fayl tizimi va `ls` sekinlashadi, saqlash muddati bo'yicha o'chirish esa
	butun papkani ko'rib chiqmasdan amalga oshadi.
	"""
	from frappe.utils import get_datetime

	dt = get_datetime(boshlandi)
	_idni_tekshir(uniqueid)
	return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/{uniqueid}.{kengaytma.lstrip('.')}"


# Asterisk UNIQUEID ko'rinishi: "1760087423.481", ba'zan tizim prefiksi bilan.
ID_SHABLON = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _idni_tekshir(uniqueid) -> None:
	"""Yaroqsiz ID'ni RAD ETADI — tuzatmaydi.

	Noto'g'ri belgilarni jimgina tashlab yuborish xavfli bo'lardi: ikki xil
	ID bitta fayl nomiga tushib, bir qo'ng'iroqning yozuvi ikkinchisini
	o'chirib yuborishi mumkin. Yozuv qaytarib bo'lmaydigan ma'lumot, shuning
	uchun shubhali ID'da to'xtaymiz.
	"""
	matn = str(uniqueid or "")
	if not ID_SHABLON.match(matn) or ".." in matn:
		frappe.throw(f"Yaroqsiz Asterisk ID: {matn!r}", frappe.ValidationError)


def _toliq_yol(nisbiy: str) -> str:
	"""Nisbiy yo'lni to'liq yo'lga aylantiradi va baza papkadan chiqmaganini tekshiradi.

	Bu tekshiruv majburiy: `fayl_yoli` bazadan keladi, va "../../../etc/passwd"
	ko'rinishidagi qiymat bilan papkadan tashqariga chiqib ketish mumkin bo'lardi.
	"""
	baza = baza_papka()
	toliq = os.path.realpath(os.path.join(baza, nisbiy))
	if not (toliq == baza or toliq.startswith(baza + os.sep)):
		frappe.throw("Fayl yo'li yozuvlar papkasidan tashqarida")
	return toliq


def saqla(nisbiy: str, content: bytes) -> str:
	"""Faylni diskka yozadi, kerakli papkalarni yaratadi. To'liq yo'lni qaytaradi."""
	toliq = _toliq_yol(nisbiy)
	os.makedirs(os.path.dirname(toliq), exist_ok=True)
	with open(toliq, "wb") as f:
		f.write(content)
	os.chmod(toliq, 0o640)
	return toliq


def oqi(nisbiy: str) -> bytes:
	toliq = _toliq_yol(nisbiy)
	if not os.path.isfile(toliq):
		frappe.throw("Yozuv fayli diskda topilmadi", frappe.DoesNotExistError)
	with open(toliq, "rb") as f:
		return f.read()


def bormi(nisbiy: str) -> bool:
	try:
		return os.path.isfile(_toliq_yol(nisbiy))
	except Exception:
		return False


def ochir(nisbiy: str) -> bool:
	"""Faylni o'chiradi. Yo'q bo'lsa ham xato bermaydi."""
	try:
		toliq = _toliq_yol(nisbiy)
	except Exception:
		return False
	if os.path.isfile(toliq):
		os.remove(toliq)
		return True
	return False
