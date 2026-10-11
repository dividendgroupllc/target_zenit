# Copyright (c) 2026, Target Zenit
# O'rinbosarlik (substitution / cover — Untis Vertretungsplanung).
# Asl jadval (Jadval Yozuvi) O'ZGARMAYDI — ustiga Jadval Ozgarishi qatlami yoziladi.
# Oqim: sana + yo'q o'qituvchi -> ta'sirlangan darslar -> ranjlangan cover kandidat
# (bo'sh + malakali + kam cover, fairness) -> belgilash/bekor.
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from target_zenit.dars_jadvali.oqituvchi_jadval import (
	KUNLAR,
	_faol_versiya,
	_guard,
	_mavjudlik_map,
	_mavjudlikmi,
)


def _kun_nomi(sana) -> str:
	wd = getdate(sana).weekday()  # Dushanba=0
	return KUNLAR[wd] if wd < len(KUNLAR) else ""


def _ozgarishlar(sana, versiya):
	"""Shu sanadagi barcha Jadval Ozgarishi -> {jadval_yozuvi: doc}."""
	rows = frappe.get_all(
		"Jadval Ozgarishi", filters={"sana": getdate(sana)},
		fields=["name", "jadval_yozuvi", "tur", "asl_oqituvchi", "yangi_oqituvchi",
		        "yangi_xona", "sabab"], limit_page_length=0)
	return {r.jadval_yozuvi: r for r in rows}


@frappe.whitelist()
def kun_darslari(sana: str, oqituvchi: str | None = None, versiya: str | None = None) -> dict:
	"""Shu sana (hafta kuni) uchun darslar + mavjud o'zgarishlar. oqituvchi berilsa — faqat uniki."""
	_guard()
	versiya = _faol_versiya(versiya)
	kun = _kun_nomi(sana)
	if not kun:
		return {"sana": str(sana), "kun": "", "darslar": [], "xabar": "Dam olish kuni (jadval yo'q)"}

	filtr = {"versiya": versiya, "kun": kun}
	if oqituvchi:
		filtr["oqituvchi"] = oqituvchi
	yozuvlar = frappe.get_all(
		"Jadval Yozuvi", filters=filtr,
		fields=["name", "dars_raqami", "fan", "guruh_nomi", "oqituvchi", "oqituvchi_nomi", "xona", "boshlanish"],
		order_by="dars_raqami asc", limit_page_length=0)

	ozg = _ozgarishlar(sana, versiya)
	darslar = []
	for y in yozuvlar:
		o = ozg.get(y.name)
		darslar.append({
			"jadval_yozuvi": y.name, "dars_raqami": y.dars_raqami, "fan": y.fan,
			"guruh_nomi": y.guruh_nomi, "asl_oqituvchi": y.oqituvchi,
			"asl_oqituvchi_nomi": y.oqituvchi_nomi, "xona": y.xona,
			"ozgarish": ({
				"name": o.name, "tur": o.tur,
				"yangi_oqituvchi": o.yangi_oqituvchi,
				"yangi_oqituvchi_nomi": frappe.db.get_value("Instructor", o.yangi_oqituvchi, "instructor_name") if o.yangi_oqituvchi else None,
				"sabab": o.sabab,
			} if o else None),
		})
	return {"sana": str(sana), "kun": kun, "versiya": versiya, "darslar": darslar}


def _band_oqituvchilar_slotda(versiya, kun, dars, sana):
	"""Shu sana + slotda band o'qituvchilar: asl jadval (Bekor bo'lmaganlar) + cover beruvchilar."""
	band = set()
	# Asl jadval
	for r in frappe.db.sql(
		"""SELECT name, oqituvchi FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND kun=%s AND dars_raqami=%s AND oqituvchi IS NOT NULL""",
		(versiya, kun, dars), as_dict=True):
		band.add(r.oqituvchi)
	# Shu sanadagi o'zgarishlar: Bekor bo'lsa asl o'qituvchi bo'shaydi; cover beruvchi band bo'ladi
	ozg = _ozgarishlar(sana, versiya)
	for jy, o in ozg.items():
		meta = frappe.db.get_value("Jadval Yozuvi", jy, ["kun", "dars_raqami"], as_dict=True)
		if not meta or meta.kun != kun or int(meta.dars_raqami or 0) != int(dars):
			continue
		if o.tur == "Bekor" and o.asl_oqituvchi in band:
			band.discard(o.asl_oqituvchi)
		if o.tur == "O'rinbosar" and o.yangi_oqituvchi:
			band.add(o.yangi_oqituvchi)
	return band


@frappe.whitelist()
def guruh_kun(sana: str, guruh: str, versiya: str | None = None) -> dict:
	"""Bitta sinf/guruhning shu sanadagi darslari + o'zgarish overlay (o'quvchi/ota-ona ko'rinishi)."""
	_guard()
	versiya = _faol_versiya(versiya)
	kun = _kun_nomi(sana)
	nomi = frappe.db.get_value("Student Group", guruh, "student_group_name") or guruh
	if not kun:
		return {"sana": str(sana), "kun": "", "guruh_nomi": nomi, "darslar": [], "xabar": "Dam olish kuni"}

	# Shu sinfga tegishli darslar: sinflar ro'yxatida bu guruh/sinf nomi bor
	yozuvlar = frappe.db.sql(
		"""SELECT name, dars_raqami, fan, guruh_nomi, oqituvchi, oqituvchi_nomi, xona, boshlanish
		   FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND kun=%s AND (guruh=%s OR sinflar LIKE %s)
		   ORDER BY dars_raqami ASC""",
		(versiya, kun, guruh, f"%{nomi}%"), as_dict=True)

	ozg = _ozgarishlar(sana, versiya)
	darslar = []
	for y in yozuvlar:
		o = ozg.get(y.name)
		darslar.append({
			"jadval_yozuvi": y.name, "dars_raqami": y.dars_raqami, "fan": y.fan,
			"guruh_nomi": y.guruh_nomi, "oqituvchi_nomi": y.oqituvchi_nomi,
			"xona": y.xona, "boshlanish": str(y.boshlanish or "")[:5],
			"ozgarish": ({
				"tur": o.tur,
				"yangi_oqituvchi_nomi": frappe.db.get_value("Instructor", o.yangi_oqituvchi, "instructor_name") if o.yangi_oqituvchi else None,
				"sabab": o.sabab,
			} if o else None),
		})
	return {"sana": str(sana), "kun": kun, "guruh": guruh, "guruh_nomi": nomi, "versiya": versiya, "darslar": darslar}


@frappe.whitelist()
def cover_kandidatlar(jadval_yozuvi: str, sana: str, versiya: str | None = None) -> list[dict]:
	"""Shu dars (sana) uchun o'rinbosar kandidatlar — ranjlangan:
	fanni o'qitadi -> kam cover (fairness) -> kam yuklama. Band/blok chiqariladi."""
	_guard()
	versiya = _faol_versiya(versiya)
	jy = frappe.db.get_value(
		"Jadval Yozuvi", jadval_yozuvi,
		["kun", "dars_raqami", "fan", "oqituvchi"], as_dict=True)
	if not jy:
		frappe.throw(_("Dars topilmadi."))
	kun, dars, fan, asl = jy.kun, int(jy.dars_raqami or 0), jy.fan, jy.oqituvchi

	# Fanni o'tadigan o'qituvchilar (malaka proksi)
	fan_oqit = set(r.oqituvchi for r in frappe.db.sql(
		"""SELECT DISTINCT oqituvchi FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND fan=%s AND oqituvchi IS NOT NULL""", (versiya, fan), as_dict=True))

	band_now = _band_oqituvchilar_slotda(versiya, kun, dars, sana)
	# Umumiy yuklama
	soat = {r.oqituvchi: r.n for r in frappe.db.sql(
		"""SELECT oqituvchi, COUNT(*) n FROM `tabJadval Yozuvi`
		   WHERE versiya=%s GROUP BY oqituvchi""", (versiya,), as_dict=True)}
	# Cover statistikasi (fairness) — necha marta o'rinbosar bo'lgan
	cover_soni = {r.yangi_oqituvchi: r.n for r in frappe.db.sql(
		"""SELECT yangi_oqituvchi, COUNT(*) n FROM `tabJadval Ozgarishi`
		   WHERE tur='O''rinbosar' AND yangi_oqituvchi IS NOT NULL GROUP BY yangi_oqituvchi""",
		as_dict=True)}

	ins_list = frappe.get_all("Instructor", filters={"custom_vakant": 0},
		fields=["name", "instructor_name", "custom_haftalik_norma"], limit_page_length=0)
	natija = []
	for i in ins_list:
		name = i["name"]
		if name == asl or name in band_now:
			continue
		mav = _mavjudlik_map(name)
		if _mavjudlikmi(mav, kun, dars) == "band":
			continue
		norma = i.get("custom_haftalik_norma") or 0
		yuk = soat.get(name, 0)
		sabab = []
		if norma and yuk >= norma:
			sabab.append(f"norma to'lgan ({yuk}/{norma})")
		natija.append({
			"oqituvchi": name, "nomi": i["instructor_name"],
			"fanni_oqitadi": name in fan_oqit,
			"afzal": _mavjudlikmi(mav, kun, dars) == "afzal",
			"soat": yuk, "norma": norma, "cover_soni": cover_soni.get(name, 0),
			"ogoh": "; ".join(sabab),
		})
	natija.sort(key=lambda x: (not x["fanni_oqitadi"], x["cover_soni"], not x["afzal"], x["soat"]))
	return natija


def _upsert(jadval_yozuvi, sana, tur, yangi_oqituvchi=None, yangi_xona=None, sabab=None):
	mavjud = frappe.db.get_value(
		"Jadval Ozgarishi", {"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana)}, "name")
	doc = frappe.get_doc("Jadval Ozgarishi", mavjud) if mavjud else frappe.new_doc("Jadval Ozgarishi")
	doc.update({
		"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana), "tur": tur,
		"yangi_oqituvchi": yangi_oqituvchi, "yangi_xona": yangi_xona,
		"sabab": sabab, "kim_kiritdi": frappe.session.user,
	})
	doc.save(ignore_permissions=True) if mavjud else doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc


@frappe.whitelist()
def cover_belgila(jadval_yozuvi: str, sana: str, yangi_oqituvchi: str, sabab: str | None = None) -> dict:
	"""O'rinbosar tayinlash."""
	_guard()
	doc = _upsert(jadval_yozuvi, sana, "O'rinbosar", yangi_oqituvchi=yangi_oqituvchi, sabab=sabab)
	return {"name": doc.name, "yangi_oqituvchi_nomi": frappe.db.get_value("Instructor", yangi_oqituvchi, "instructor_name")}


@frappe.whitelist()
def bekor_qil(jadval_yozuvi: str, sana: str, sabab: str | None = None) -> dict:
	"""Darsni bekor qilish (o'rinbosarsiz)."""
	_guard()
	doc = _upsert(jadval_yozuvi, sana, "Bekor", sabab=sabab)
	return {"name": doc.name}


@frappe.whitelist()
def ozgarish_ochir(name: str) -> dict:
	"""O'zgarishni olib tashlash (asl jadvalga qaytadi)."""
	_guard()
	frappe.delete_doc("Jadval Ozgarishi", name, ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1}


@frappe.whitelist()
def cover_statistika(dan: str | None = None, gacha: str | None = None) -> list[dict]:
	"""Fairness: har o'qituvchi necha marta o'rinbosar bo'lgan (sana oralig'ida)."""
	_guard()
	cond, args = ["tur='O''rinbosar'", "yangi_oqituvchi IS NOT NULL"], []
	if dan:
		cond.append("sana >= %s")
		args.append(getdate(dan))
	if gacha:
		cond.append("sana <= %s")
		args.append(getdate(gacha))
	rows = frappe.db.sql(
		f"""SELECT yangi_oqituvchi, COUNT(*) n FROM `tabJadval Ozgarishi`
		    WHERE {' AND '.join(cond)} GROUP BY yangi_oqituvchi ORDER BY n DESC""",
		tuple(args), as_dict=True)
	for r in rows:
		r["nomi"] = frappe.db.get_value("Instructor", r.yangi_oqituvchi, "instructor_name")
	return rows
