# Copyright (c) 2026, Target Zenit
"""AI qo'ng'iroq tahlilidan avtomatik murojaat ochish.

Manba — `telefoniya/analiz.py` promptidagi majburiy qatorlar:
    TAKLIF VA SHIKOYAT: <ota-onaning MAKTAB haqidagi gapi>
    MUROJAAT TURI:      <Shikoyat / Taklif / Muammo / So'rov / yo'q>
    DIQQAT:             <rahbar bilishi shart bo'lgan narsa>

Qaror (2026-11-04): AI topgan murojaat TO'G'RIDAN-TO'G'RI rahbar paneliga
tushadi — oraliq tasdiq yo'q. Shuning uchun ikki himoya qo'yilgan:
  1) yo'nalish AI'ning MUROJAAT YO'NALISHI qatoridan keladi (o'quv -> Direktor,
     tashkiliy -> CEO), aniq kategoriya esa kalit so'z bo'yicha topiladi.
     Ikkisi zid kelsa AI yo'nalishi ustun: aniq kategoriya emas, «Aniqlanmagan
     - o'quv/tashkiliy» qo'yiladi — murojaat noto'g'ri rahbarga ketmaydi, lekin
     egasiz ham qolmaydi;
  2) rahbarda «Ahamiyatsiz» qarori bor — AI xato o'qigan bo'lsa bir bosishda
     yopiladi, ota-onaga qo'ng'iroq qilish talab qilinmaydi.

Idempotent: bitta qo'ng'iroqdan bitta murojaat (`telefon_qongirogi` bo'yicha
tekshiradi) — qayta tahlil qilinsa dublikat ochilmaydi.
"""

from __future__ import annotations

import frappe

from target_zenit.murojaat import api

TAKLIF_KALITLAR = ("TAKLIF VA SHIKOYAT", "MIJOZ TAKLIFI")
BOSH_QIYMATLAR = ("taklif yo'q", "taklif yoq", "shikoyat yo'q", "yo'q", "yoq",
                  "-", "—", "", "aniqlanmadi", "none")
TURLAR = ("Shikoyat", "Taklif", "Muammo", "So'rov")

# AI aytgan yo'nalish -> murojaat yo'nalishi (rol)
YONALISH_MAP = {"o'quv": "Direktor", "oquv": "Direktor", "tashkiliy": "CEO"}
ZAXIRA_KAT = {"Direktor": "Aniqlanmagan - o'quv", "CEO": "Aniqlanmagan - tashkiliy"}
MIN_UZUNLIK = 12      # "yo'q" ga yaqin qisqa javoblarni tashlaymiz


def _qator(xulosa: str | None, kalit: str) -> str:
	for q in str(xulosa or "").splitlines():
		q = q.strip()
		if q.upper().startswith(kalit.upper() + ":"):
			return q[len(kalit) + 1:].strip()
	return ""


def _bosh(matn: str) -> bool:
	return (matn or "").strip().lower() in BOSH_QIYMATLAR


def taklif_matni(xulosa: str | None) -> str:
	"""AI xulosasidan ota-onaning maktab bo'yicha gapi. Bo'lmasa bo'sh satr."""
	for kalit in TAKLIF_KALITLAR:
		matn = _qator(xulosa, kalit)
		if matn and not _bosh(matn):
			return matn
	return ""


def _turi(xulosa: str | None, kategoriya: str | None) -> str:
	"""AI aytgan tur ustun; aytmasa kategoriyaning odatdagi turi; u ham
	bo'lmasa «Shikoyat» (rahbar e'tiborini talab qiladigan xavfsiz taxmin)."""
	aytgan = _qator(xulosa, "MUROJAAT TURI")
	for t in TURLAR:
		if aytgan and t.lower() in aytgan.lower():
			return t
	if kategoriya:
		tavsiya = frappe.db.get_value("Murojaat Kategoriyasi", kategoriya, "turi_tavsiya")
		if tavsiya in TURLAR:
			return tavsiya
	return "Shikoyat"


def _yonalish(xulosa: str | None) -> str | None:
	"""AI'ning MUROJAAT YO'NALISHI qatori -> CEO / Direktor. Aytmasa None."""
	aytgan = _qator(xulosa, "MUROJAAT YO'NALISHI").lower()
	if not aytgan or _bosh(aytgan):
		return None
	for kalit, rol in YONALISH_MAP.items():
		if kalit in aytgan:
			return rol
	return None


def _marshrut(matn: str, xulosa: str | None) -> tuple[str | None, str | None]:
	"""(kategoriya, yonaltirildi) — AI yo'nalishi bilan kalit so'z kelishuvi.

	Kalit so'z aniq kategoriya beradi (masalan "O'qituvchi ustidan shikoyat"),
	AI esa umumiy yo'nalishni. Mos kelsa — aniq kategoriya ishlatiladi. Zid
	kelsa AI yo'nalishi ustun: AI butun suhbatni o'qigan, kalit so'z esa bitta
	satrdagi tasodifiy so'zga ilashgan bo'lishi mumkin."""
	kat = api.kategoriya_top(matn)
	ai_yonalish = _yonalish(xulosa)
	kat_yonalish = (
		frappe.db.get_value("Murojaat Kategoriyasi", kat, "yonaltirish") if kat else None
	)

	if kat and (not ai_yonalish or ai_yonalish == kat_yonalish):
		return kat, kat_yonalish or ai_yonalish
	yonalish = ai_yonalish or kat_yonalish or "CEO"
	zaxira = ZAXIRA_KAT.get(yonalish)
	if zaxira and frappe.db.exists("Murojaat Kategoriyasi", zaxira):
		return zaxira, yonalish
	return None, yonalish


def _student_top(tq) -> str | None:
	"""Qo'ng'iroqdagi raqamdan o'quvchini topish.

	Avval qo'ng'iroqning o'zidagi bog'lanish, keyin to'lovchi/o'quvchi raqami,
	oxirida ota-ona (Guardian) raqami. Bir raqamga bir nechta farzand to'g'ri
	kelsa — ochiq qarz ishi borini olamiz (sotuv qo'ng'irog'i shu bola bo'yicha)."""
	if tq.student:
		return tq.student
	tel = tq.normal_telefon
	if not tel:
		return None

	nomzodlar = frappe.get_all(
		"Student",
		or_filters=[["custom_payer_phone", "like", f"%{tel[-9:]}"],
		            ["student_mobile_number", "like", f"%{tel[-9:]}"]],
		filters={"enabled": 1},
		pluck="name",
		limit_page_length=10,
	)
	if not nomzodlar:
		nomzodlar = frappe.db.sql_list(
			"""SELECT DISTINCT sg.parent
			   FROM `tabStudent Guardian` sg
			   JOIN `tabGuardian` g ON g.name = sg.guardian
			   JOIN `tabStudent` s ON s.name = sg.parent
			   WHERE sg.parenttype = 'Student' AND s.enabled = 1
			     AND REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(g.mobile_number,''),
			         ' ',''),'-',''),'(',''),')','') LIKE %s
			   LIMIT 10""",
			(f"%{tel[-9:]}",),
		)
	if not nomzodlar:
		return None
	if len(nomzodlar) == 1:
		return nomzodlar[0]
	qarzli = frappe.get_all(
		"Qarz Ishi",
		filters={"student": ["in", nomzodlar],
		         "ishlov_status": ["not in", ("Yopildi - To'landi", "Yopildi - Boshqa")]},
		fields=["student"], order_by="qarz_summa desc", limit_page_length=1,
	)
	return qarzli[0].student if qarzli else nomzodlar[0]


def qongiroqdan(qongiroq: str) -> dict:
	"""AI tahlili tayyor bo'lgan qo'ng'iroqdan murojaat ochadi (yoki o'tkazadi)."""
	tq = frappe.db.get_value(
		"Telefon Qongirogi", qongiroq,
		["name", "ai_xulosa", "student", "normal_telefon", "foydalanuvchi",
		 "xodim", "boshlandi", "aloqador_ism", "kontakt_ism"],
		as_dict=True,
	)
	if not tq:
		return {"holat": "yo'q"}
	if frappe.db.exists("Murojaat", {"telefon_qongirogi": qongiroq}):
		return {"holat": "o'tkazildi", "sabab": "murojaat allaqachon bor"}

	matn = taklif_matni(tq.ai_xulosa)
	if not matn or len(matn) < MIN_UZUNLIK:
		return {"holat": "o'tkazildi", "sabab": "taklif/shikoyat yo'q"}

	kategoriya, yonaltirildi = _marshrut(matn, tq.ai_xulosa)
	student = _student_top(tq)
	qarz_ishi = None
	if student:
		ochiq = frappe.get_all(
			"Qarz Ishi",
			filters={"student": student,
			         "ishlov_status": ["not in", ("Yopildi - To'landi", "Yopildi - Boshqa")]},
			pluck="name", order_by="qarz_summa desc", limit_page_length=1,
		)
		qarz_ishi = ochiq[0] if ochiq else None

	diqqat = _qator(tq.ai_xulosa, "DIQQAT")
	menejer = tq.foydalanuvchi
	if not menejer and tq.xodim:
		menejer = frappe.db.get_value("Employee", tq.xodim, "user_id")

	name = api.murojaat_yarat(
		matn=matn,
		turi=_turi(tq.ai_xulosa, kategoriya),
		kategoriya=kategoriya,
		yonaltirildi=yonaltirildi,
		student=student,
		qarz_ishi=qarz_ishi,
		telefon_qongirogi=qongiroq,
		muhimlik="Yuqori" if (diqqat and not _bosh(diqqat)) else "O'rta",
		manba="AI qo'ng'iroq tahlili",
		menejer=menejer or "Administrator",
		suhbat_vaqti=tq.boshlandi,
		payer_name=tq.aloqador_ism or tq.kontakt_ism,
		payer_phone=tq.normal_telefon,
		izoh=("AI qo'ng'iroq tahlilidan avtomatik ochildi"
		      + (f". DIQQAT: {diqqat}" if diqqat and not _bosh(diqqat) else "")),
		ignore_permissions=True,
	)
	frappe.db.commit()
	return {"holat": "ochildi", "murojaat": name, "kategoriya": kategoriya,
	        "yonaltirildi": yonaltirildi}


def qongiroqdan_xavfsiz(qongiroq: str) -> None:
	"""Tahlil oqimidan chaqiriladi: murojaat ochilmasa ham tahlil buzilmasin."""
	try:
		qongiroqdan(qongiroq)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Murojaat avto-ochish xato: {qongiroq}")


@frappe.whitelist()
def qolganlarni_qil(limit: int = 300) -> dict:
	"""Tahlili bor-u murojaati ochilmagan qo'ng'iroqlar (backfill + cron zaxirasi).

	Modul yoqilgandan OLDIN tahlil qilingan qo'ng'iroqlardagi shikoyatlar ham
	rahbarga ko'rinishi kerak — aks holda modul faqat bugundan ishlagan bo'ladi."""
	frappe.only_for(("System Manager", "Sales Manager", "CEO", "Direktor"))
	bor = set(frappe.get_all(
		"Murojaat", filters={"telefon_qongirogi": ["is", "set"]},
		pluck="telefon_qongirogi", limit_page_length=0,
	))
	nomlar = frappe.get_all(
		"Telefon Qongirogi",
		filters={"ai_xulosa": ["is", "set"]},
		pluck="name", order_by="boshlandi desc", limit_page_length=int(limit),
	)
	ochildi = 0
	for nom in nomlar:
		if nom in bor:
			continue
		if qongiroqdan(nom).get("holat") == "ochildi":
			ochildi += 1
	return {"korildi": len(nomlar), "ochildi": ochildi}
