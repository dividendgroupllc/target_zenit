# Copyright (c) 2026, Target Zenit
# "Mening jadvalim" — o'qituvchi uchun: bugungi darslar + haftalik jadval.
# Har darsdan davomat olishga o'tish mumkin (Course Schedule orqali).
from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, getdate, nowdate

from target_zenit.dars_jadvali import baholash as bah
from target_zenit.dars_jadvali import sozlamalar as soz
from target_zenit.nomlar import oqituvchi_nomi, oqituvchi_nomlari

KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _vaqt_str(v) -> str:
	"""Time/timedelta/str -> 'HH:MM'."""
	if not v:
		return ""
	if hasattr(v, "total_seconds"):  # timedelta
		jami = int(v.total_seconds())
		return f"{jami // 3600:02d}:{(jami % 3600) // 60:02d}"
	s = str(v)
	return s[:5] if len(s) >= 5 else s


def _mening_instructorim():
	"""Joriy foydalanuvchining Instructor yozuvi.

	Aniqlash ID bo'yicha boradi (Employee.user_id -> Instructor.employee); ism
	bo'yicha moslashtirish faqat oxirgi chora, chunki xodim ismi pasport bo'yicha
	o'zgartirilganda Instructor docname'i eskicha qolib ketadi — ism_sync.py.
	"""
	from target_zenit.ism_sync import joriy_instructor

	return joriy_instructor()


@frappe.whitelist()
def get_data(oqituvchi: str | None = None, versiya: str | None = None, hafta: int = 0):
	"""Tanlangan (yoki o'zining) o'qituvchi jadvali.

	`hafta` — joriy haftadan siljish (0 = shu hafta, -1 = o'tgan, +1 = keyingi).
	Haftalik jadval biz o'zgartirmagunimizcha amal qiladi, shuning uchun istalgan
	haftaga o'tish mumkin — sanalar shunchaki shu hafta dushanbasidan hisoblanadi."""
	menejer = bool(
		{"system manager", "zavuch", "academics user", "education manager"}
		& {r.lower() for r in frappe.get_roles()}
	)
	if oqituvchi and not menejer:
		frappe.throw("Boshqa o'qituvchi jadvalini ko'rish uchun ruxsat yo'q.", frappe.PermissionError)

	oqituvchi = oqituvchi or _mening_instructorim()
	versiya = versiya or frappe.db.get_value(
		"Jadval Versiyasi", {"holat": "Faol"}, "name"
	) or frappe.db.get_value("Jadval Versiyasi", {}, "name")

	natija = {
		"oqituvchi": oqituvchi,
		# Ism Employee'dan jonli (Instructor.instructor_name — nusxa)
		"oqituvchi_nomi": oqituvchi_nomi(oqituvchi),
		"versiya": versiya,
		"menejer": menejer,
		"bugun_kuni": KUNLAR[getdate(nowdate()).weekday()],
		"darslar": [],
		"qongiroq": {},
	}
	if menejer:
		oqituvchilar = frappe.get_all(
			"Instructor", fields=["name", "instructor_name"], limit_page_length=0
		)
		nomlar = oqituvchi_nomlari([o.name for o in oqituvchilar])
		for o in oqituvchilar:
			o["instructor_name"] = nomlar.get(o.name) or o.instructor_name
		oqituvchilar.sort(key=lambda o: (o["instructor_name"] or "").lower())
		natija["oqituvchilar"] = oqituvchilar
	if not oqituvchi or not versiya:
		return natija

	natija["darslar"] = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "oqituvchi": oqituvchi},
		fields=[
			"name", "kun", "kun_raqami", "dars_raqami", "fan", "guruh", "guruh_nomi",
			"sinflar", "xona", "boshlanish", "tugash",
		],
		order_by="kun_raqami asc, dars_raqami asc",
		limit_page_length=0,
	)
	# Ko'rilayotgan haftaning dushanbasi (sanalarni darsga biriktirish uchun).
	# `hafta` siljishi: 0 = shu hafta, -1 = o'tgan hafta, +1 = keyingi hafta…
	bugun = getdate(nowdate())
	siljish = cint(hafta)
	hafta_boshi = add_days(add_days(bugun, -bugun.weekday()), siljish * 7)
	hafta_oxiri = add_days(hafta_boshi, 4)

	# Shu haftadagi jadval o'zgarishlari (o'rinbosarlik/bekor) — bir marta
	ozg_map = {}
	cover_vazifalar = []
	for o in frappe.get_all(
		"Jadval Ozgarishi",
		filters={"sana": ["between", [hafta_boshi, hafta_oxiri]]},
		fields=["name", "sana", "jadval_yozuvi", "tur", "asl_oqituvchi",
		        "yangi_oqituvchi", "sabab", "kun", "dars_raqami", "guruh_nomi", "fan"],
		limit_page_length=0):
		ozg_map[(str(o.sana), o.jadval_yozuvi)] = o
		# Bu o'qituvchi o'rinbosar bo'ladigan darslar
		if o.yangi_oqituvchi == oqituvchi:
			jy = frappe.db.get_value("Jadval Yozuvi", o.jadval_yozuvi,
			                         ["boshlanish", "tugash"], as_dict=True) or {}
			cover_vazifalar.append({
				"sana": str(o.sana), "kun": o.kun, "dars_raqami": o.dars_raqami,
				"fan": o.fan, "guruh_nomi": o.guruh_nomi,
				"asl_oqituvchi_nomi": oqituvchi_nomi(o.asl_oqituvchi),
				"boshlanish": _vaqt_str(jy.get("boshlanish")), "tugash": _vaqt_str(jy.get("tugash")),
				"sabab": o.sabab,
			})
	cover_vazifalar.sort(key=lambda x: (x["sana"], x["dars_raqami"] or 0))
	natija["cover_vazifalar"] = cover_vazifalar

	for d in natija["darslar"]:
		d["boshlanish"] = _vaqt_str(d["boshlanish"])
		d["tugash"] = _vaqt_str(d["tugash"])
		# Shu dars sanasi (joriy haftada) — kun_raqami 1=Dushanba
		kr = (d.get("kun_raqami") or 1) - 1
		d["sana"] = str(add_days(hafta_boshi, kr))
		# O'zgarish overlay (shu sana + shu dars)
		o = ozg_map.get((d["sana"], d["name"]))
		d["ozgarish"] = ({
			"tur": o.tur,
			"yangi_oqituvchi_nomi": oqituvchi_nomi(o.yangi_oqituvchi),
			"sabab": o.sabab,
		} if o else None)
		# Mavzu/bajarilish overlay'i OLIB TASHLANDI (2026-11-08): dars
		# bajarilishi Moodle'da yuritiladi. Bu sahifa faqat JADVALni ko'rsatadi.
	natija["haftalik_soat"] = len(natija["darslar"])
	natija["bugun_sana"] = str(bugun)
	natija["hafta"] = siljish
	natija["hafta_boshi"] = str(hafta_boshi)
	natija["hafta_oxiri"] = str(hafta_oxiri)
	natija["shu_hafta"] = siljish == 0
	return natija


# DARS KOKPITI OLIB TASHLANDI (2026-11-08).
#
# `jurnal_oquvchilari`, `jurnal_saqla`, `dars_detali`, `dars_otdim`,
# `davomat_ochish`, `kun_paneli`, `bugun_batafsil` — davomat, baho, uy vazifa
# va «darsni o'tdim» belgisi. Bularning hammasi MOODLE'ga ko'chdi
# (o'qituvchi paneli, dars kokpiti va mobil ilova), Frappe'dagi nusxalari esa
# hech qachon ishlatilmagan: `Dars Natijasi`, `Uy Vazifa`, `Chorak Bahosi`
# doctype'larida bitta ham qator yo'q edi.
#
# Bu sahifada endi FAQAT o'qituvchining o'z jadvali ko'rinadi.
