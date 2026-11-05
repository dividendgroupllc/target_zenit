# Copyright (c) 2026, Target Zenit
"""Rahbar paneli — ota-onalarning shikoyat/taklif/muammolari.

BITTA sahifa, rolga qarab o'zini sozlaydi (2026-11-04 qarori):
  CEO     -> faqat CEO'ga yo'naltirilganlar
  Direktor-> faqat Direktorga yo'naltirilganlar
  Admin / Sales Manager -> hammasi (nazorat)
  Sotuvchi-> o'zi yo'naltirganlari ("yuborganim nima bo'ldi")

Ikki xil kod yozib ikki joyda tuzatib yurmaslik uchun ko'rinish server
tomonda `api._yonalish_filtri()` bilan kesiladi, UI esa `rol` javobiga qarab
tugmalarni ko'rsatadi.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, getdate, nowdate

from target_zenit.murojaat import api

YOPIQ = ("Yopildi",)
QARZ_YOPIQ = ("Yopildi - To'landi", "Yopildi - Boshqa")


@frappe.whitelist()
def get_data(holat=None, yonalish=None, kategoriya=None, turi=None, masul=None,
             from_date=None, to_date=None, qidiruv=None, limit=400):
	"""Navbat + KPI + filtr ro'yxatlari."""
	r = api._guard()

	filters = api._yonalish_filtri(r)
	if yonalish and r["hammasi"]:
		filters["yonaltirildi"] = yonalish
	if kategoriya:
		filters["kategoriya"] = kategoriya
	if turi:
		filters["turi"] = turi
	if masul:
		# "biriktirilmagan" — mas'ul tayinlanmagan, ya'ni yo'nalishdagi hamma
		# rahbar ko'radi, lekin hech kim o'ziga olmagan
		filters["masul"] = ["is", "not set"] if masul == "__yoq__" else masul
	if from_date and to_date:
		filters["ochilgan"] = ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]

	# Holat chiplari: "ochiq" — hali yopilmagan hammasi (rahbarning asosiy navbati)
	if holat in ("hammasi", "all", ""):
		holat = None      # chip nomi — holat qiymati emas
	if holat == "ochiq":
		filters["holat"] = ["not in", list(YOPIQ)]
	elif holat == "muddati":
		filters["holat"] = ["not in", list(YOPIQ)]
		filters["sla_sana"] = ["<", nowdate()]
	elif holat == "menda":
		filters["holat"] = ["not in", list(YOPIQ)]
		filters["masul"] = frappe.session.user
	elif holat:
		filters["holat"] = holat

	or_filters = None
	if qidiruv:
		q = f"%{qidiruv}%"
		or_filters = [["student_name", "like", q], ["matn", "like", q],
		              ["payer_name", "like", q], ["payer_phone", "like", q],
		              ["name", "like", q]]

	rows = frappe.get_all(
		"Murojaat",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "turi", "kategoriya", "muhimlik", "yonaltirildi", "masul",
			"holat", "matn", "student", "student_name", "sinf", "payer_name",
			"payer_phone", "manba", "menejer", "menejer_nomi", "suhbat_vaqti",
			"ochilgan", "sla_sana", "korildi_vaqti", "yechim_turi", "yechim",
			"yechim_vaqti", "yechim_kim", "xabar_berildi", "yopilgan_sana",
			"telefon_qongirogi", "qarz_ishi",
			# Moodle'dan olib kelingan yuritish ma'lumoti (egasi — Moodle)
			"moodle_qaror_kim", "moodle_izoh_soni", "moodle_otaona_kordi",
			"xabar_kim", "xabar_vaqti", "xabar_matni",
		],
		order_by="ochilgan desc",
		limit_page_length=cint(limit),
	)
	# Mas'ul / qaror beruvchi ISMLARI: ro'yxatda "kim biriktirilgan" ko'rinib
	# turishi kerak (admin, investor va operator uchun asosiy ustun)
	userlar = {u for x in rows for u in (x.masul, x.get("yechim_kim")) if u}
	ismlar = {
		u.name: u.full_name or u.name
		for u in (frappe.get_all("User", filters={"name": ["in", list(userlar)]},
		                         fields=["name", "full_name"]) if userlar else [])
	}

	bugun = getdate(nowdate())
	for x in rows:
		x["masul_nomi"] = ismlar.get(x.masul) or ""
		x["yechim_kim_nomi"] = ismlar.get(x.get("yechim_kim")) or ""
		x["kechikdi"] = (
			1 if (x.sla_sana and x.holat not in YOPIQ and getdate(x.sla_sana) < bugun) else 0
		)
		x["yangimi"] = 1 if not x.korildi_vaqti else 0

	# Tartib: muddati o'tganlar tepada, keyin muhimlik, keyin yangisi.
	# SQL'da emas Python'da — `FIELD(...)` ichidagi "O'rta" apostrofi order_by
	# satrini buzadi, bu esa ro'yxat tartibi uchun arzimas narsa.
	MUHIM = {"Yuqori": 0, "O'rta": 1, "Past": 2}
	# `ochilgan desc` SQL'dan kelgan — stabil sort uni guruh ichida saqlaydi
	rows.sort(key=lambda x: (-x["kechikdi"], MUHIM.get(x.muhimlik, 1)))

	return {
		"rows": rows,
		"stats": _stats(r),
		"rol": r,
		"kategoriyalar": api.kategoriyalar(),
		"rahbarlar": _rahbarlar(r),
		"masullar": _masullar(r),
	}


def _masullar(r: dict) -> list[dict]:
	"""Filtr uchun: murojaatlarda ALLAQACHON uchraydigan mas'ullar + soni.

	Rahbarlar ro'yxatidan farqi — bu yerda "kim real ishlayapti" ko'rinadi,
	nazorat uchun aynan shu kerak."""
	asos = api._yonalish_filtri(r)
	rows = frappe.get_all(
		"Murojaat",
		filters={**asos, "masul": ["is", "set"]},
		fields=["masul", "count(name) as soni"],
		group_by="masul",
		limit_page_length=0,
	)
	ismlar = {
		u.name: u.full_name or u.name
		for u in frappe.get_all(
			"User", filters={"name": ["in", [x.masul for x in rows]]},
			fields=["name", "full_name"],
		)
	} if rows else {}
	out = [
		{"user": x.masul, "nomi": ismlar.get(x.masul) or x.masul, "soni": cint(x.soni)}
		for x in sorted(rows, key=lambda x: -cint(x.soni))
	]
	yoq = frappe.db.count("Murojaat", {**asos, "masul": ["is", "not set"],
	                                  "holat": ["not in", list(YOPIQ)]})
	if yoq:
		out.append({"user": "__yoq__", "nomi": "Biriktirilmagan", "soni": yoq})
	return out


def _stats(r: dict) -> dict:
	"""KPI: ochiq, ko'rilmagan, muddati o'tgan, bu oy yopilgan, o'rtacha kun."""
	asos = api._yonalish_filtri(r)

	def soni(extra):
		f = dict(asos)
		f.update(extra)
		return frappe.db.count("Murojaat", f)

	ochiq = {"holat": ["not in", list(YOPIQ)]}
	oy_boshi = nowdate()[:7] + "-01"
	yopilgan = frappe.get_all(
		"Murojaat",
		filters={**asos, "holat": "Yopildi", "yopilgan_sana": [">=", oy_boshi]},
		fields=["ochilgan", "yopilgan_sana", "yechim_turi"],
		limit_page_length=0,
	)
	kunlar = [
		(getdate(y.yopilgan_sana) - getdate(str(y.ochilgan)[:10])).days
		for y in yopilgan if y.ochilgan and y.yopilgan_sana
	]
	return {
		"ochiq": soni(ochiq),
		"yangi": soni({"holat": "Yangi"}),
		"korilmagan": soni({**ochiq, "korildi_vaqti": ["is", "not set"]}),
		"muddati": soni({**ochiq, "sla_sana": ["<", nowdate()]}),
		"xabar_kutilmoqda": soni({"holat": "Ota-onaga xabar berish"}),
		"biriktirilmagan": soni({**ochiq, "masul": ["is", "not set"]}),
		"oy_yopildi": len(yopilgan),
		"oy_inobat": sum(1 for y in yopilgan if y.yechim_turi == "Inobatga olindi"),
		"ort_kun": round(sum(kunlar) / len(kunlar), 1) if kunlar else 0,
		"kategoriya_kesim": _kategoriya_kesim(asos),
	}


def _kategoriya_kesim(asos: dict) -> list[dict]:
	"""Qaysi masala ko'p takrorlanyapti — rahbar uchun eng qimmatli ko'rsatkich:
	bitta murojaatni hal qilish emas, SABABNI yo'q qilish kerak."""
	# Ikki alohida so'rov: `sum(case when …)` ni Frappe'ning get_all'i
	# "sub-query or function is restricted" deb qaytaradi, xom SQL yozishdan
	# ko'ra ikki marta sanash xavfsizroq va o'qishga oson
	def kesim(extra):
		return {
			r.kategoriya: cint(r.soni)
			for r in frappe.get_all(
				"Murojaat",
				filters={**asos, "kategoriya": ["is", "set"], **extra},
				fields=["kategoriya", "count(name) as soni"],
				group_by="kategoriya",
				limit_page_length=0,
			)
		}

	jami = kesim({})
	ochiq = kesim({"holat": ["not in", list(YOPIQ)]})
	rows = [
		{"kategoriya": k, "soni": v, "ochiq": ochiq.get(k, 0)}
		for k, v in sorted(jami.items(), key=lambda x: -x[1])[:12]
	]
	return rows


def _rahbarlar(r: dict) -> list[dict]:
	from target_zenit.target_zenit.doctype.murojaat.murojaat import rahbarlar

	out = []
	for y in (("CEO", "Direktor") if r["hammasi"] else r["yonalishlar"]):
		for u in rahbarlar(y):
			out.append({
				"user": u, "yonalish": y,
				"nomi": frappe.db.get_value("User", u, "full_name") or u,
			})
	return out


@frappe.whitelist()
def get_case(name: str):
	"""Murojaatning TO'LIQ tasnifi: kim, qachon, nima dedi, ovozi, oldingi
	suhbatlari, qarz holati, izohlar timeline'i."""
	doc, r = api._ol(name)

	# Rahbar kartani ochdi — "ko'rib chiqildimi" shu bilan belgilanadi
	if r["ceo"] or r["direktor"]:
		api.korildi(name)
		doc.reload()

	student = doc.student
	qongiroqlar, ays, qarz = [], [], None

	if student:
		from target_zenit.target_zenit.page.qarzdorlik import qarzdorlik as qp

		# Shu o'quvchi bo'yicha barcha suhbatlar (ovoz + transkript + AI)
		qongiroqlar = qp._qongiroqlar(student, doc.payer_phone, doc.payer_name, limit=30)

		# Sotuvchilar bilan bo'lgan butun aloqa tarixi — rahbar "avval nima
		# gaplashilgan" ni ko'rmasa, ota-onaga ikkinchi marta bir xil javob beriladi
		ays = frappe.db.sql(
			"""SELECT ay.name, ay.vaqt, ay.masul, ay.kanal, ay.aloqa_natijasi,
			          ay.hisob_natijasi, ay.komment, ay.keyingi_harakat,
			          ay.keyingi_sana, ay.vada_summa, ay.vada_sana,
			          u.full_name menejer_nomi
			   FROM `tabAloqa Yozuvi` ay
			   LEFT JOIN `tabQarz Ishi` qi ON qi.name = ay.qarz_ishi
			   LEFT JOIN `tabUser` u ON u.name = ay.masul
			   WHERE COALESCE(NULLIF(ay.student, ''), qi.student) = %s
			   ORDER BY ay.vaqt DESC LIMIT 30""",
			(student,), as_dict=True,
		)

		st = frappe.db.get_value(
			"Student", student,
			["student_name", "custom_sinf_guruh", "student_mobile_number", "enabled"],
			as_dict=True,
		)
		ochiq = frappe.get_all(
			"Qarz Ishi",
			filters={"student": student, "ishlov_status": ["not in", list(QARZ_YOPIQ)]},
			fields=["name", "qarz_summa", "ishlov_status", "aging_bucket",
			        "eng_eski_muddat", "masul", "keyingi_aloqa"],
			order_by="qarz_summa desc", limit_page_length=1,
		)
		qarz = {
			"student": st,
			"ish": ochiq[0] if ochiq else None,
			# Shu o'quvchi bo'yicha boshqa murojaatlar — takrorlanayotgan
			# masalani ko'rish uchun
			"boshqa": frappe.get_all(
				"Murojaat",
				filters={"student": student, "name": ["!=", name]},
				fields=["name", "turi", "kategoriya", "holat", "yechim_turi",
				        "ochilgan", "matn"],
				order_by="ochilgan desc", limit_page_length=10,
			),
		}

	# Shu murojaatning o'z qo'ng'irog'i ro'yxat boshida turishi kerak
	if doc.telefon_qongirogi:
		for q in qongiroqlar:
			q["manba_qongiroq"] = 1 if q["name"] == doc.telefon_qongirogi else 0
		qongiroqlar.sort(key=lambda q: (-q.get("manba_qongiroq", 0),))

	return {
		"murojaat": doc.as_dict(no_nulls=False),
		"izohlar": api._izohlar(doc),
		"qongiroqlar": qongiroqlar,
		"ays": ays,
		"qarz": qarz,
		"rol": r,
		"kategoriyalar": api.kategoriyalar(),
		"rahbarlar": _rahbarlar(r),
	}
