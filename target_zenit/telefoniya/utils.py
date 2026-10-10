# Copyright (c) 2026, Target Zenit
"""Telefon raqamini kanonik ko'rinishga keltirish.

Muammo: GSM shlyuz raqamni turli formatda beradi (998901234567, +998901234567,
901234567, 0901234567), Family/Admission Lead maydonlari esa odamlar qo'lda
to'ldirgan erkin matn ("90 123 45 67", "+998(90)123-45-67").

Yechim: ikki tomonni ham bitta formatga keltiramiz — faqat raqamlar, xalqaro
kod bilan: "998901234567". Qidiruv va solishtirish shu format bo'yicha ketadi.
"""

import re

# O'zbekiston xalqaro kodi va milliy raqam uzunligi (kod + abonent = 9 raqam).
MAMLAKAT_KODI = "998"
MILLIY_UZUNLIK = 9

# Shahar ichidagi 7 raqamli qisqa raqam uchun standart hudud kodi (Toshkent).
SUKUTDAGI_HUDUD_KODI = "71"


def normalize_phone(raw: str | None, hudud_kodi: str = SUKUTDAGI_HUDUD_KODI) -> str | None:
	"""Istalgan ko'rinishdagi raqamni "998XXXXXXXXX" ga keltiradi.

	Tanib bo'lmasa — None. Chet el raqami bo'lsa raqamlari o'zgarmasdan qaytadi
	(taxmin qilib O'zbekiston kodini qo'shib yubormaymiz).
	"""
	if not raw:
		return None

	# Faqat raqamlar. "+", qavs, tire, bo'shliq — hammasi tashlanadi.
	d = re.sub(r"\D", "", str(raw))
	if not d:
		return None

	# Xalqaro chiqish prefikslari: 00998... yoki 8998... (eski ruscha uslub).
	if d.startswith("00"):
		d = d[2:]
	elif len(d) == 13 and d.startswith("8" + MAMLAKAT_KODI):
		d = d[1:]

	# Allaqachon to'g'ri: 998 + 9 raqam.
	if len(d) == len(MAMLAKAT_KODI) + MILLIY_UZUNLIK and d.startswith(MAMLAKAT_KODI):
		return d

	# Milliy format: 901234567 (mobil) yoki 712001122 (Toshkent shahar).
	if len(d) == MILLIY_UZUNLIK:
		return MAMLAKAT_KODI + d

	# Shahar ichi trank prefiksi bilan: 0901234567.
	if len(d) == MILLIY_UZUNLIK + 1 and d.startswith("0"):
		return MAMLAKAT_KODI + d[1:]

	# Shahar ichidagi qisqa raqam: 2001122 -> hudud kodi qo'shiladi.
	if len(d) == 7:
		return MAMLAKAT_KODI + hudud_kodi + d

	# Qolgani — chet el yoki tanib bo'lmaydigan raqam. Buzmasdan qaytaramiz.
	return d


def format_phone(normal: str | None) -> str:
	"""Ko'rsatish uchun chiroyli ko'rinish: +998 90 123 45 67."""
	if not normal:
		return ""
	if len(normal) == 12 and normal.startswith(MAMLAKAT_KODI):
		k, o, a, b, c = normal[:3], normal[3:5], normal[5:8], normal[8:10], normal[10:]
		return f"+{k} {o} {a} {b} {c}"
	return f"+{normal}"
