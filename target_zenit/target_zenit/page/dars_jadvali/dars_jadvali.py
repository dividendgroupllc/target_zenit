# Copyright (c) 2026, Target Zenit
# Dars jadvali paneli (zavuch): sinflar x darslar to'ri, kun bo'yicha.
# Ma'lumot manbai — Jadval Yozuvi (haftalik shablon).
from __future__ import annotations

from collections import defaultdict

import frappe

ALLOWED_ROLES = [
	"System Manager", "Zavuch", "Academics User", "Education Manager",
	"Sales Manager", "investor", "Xojakbar_Operator",
]
KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]


def _vaqt_str(v) -> str:
	"""Time/timedelta/str -> 'HH:MM'."""
	if not v:
		return ""
	if hasattr(v, "total_seconds"):  # timedelta
		jami = int(v.total_seconds())
		return f"{jami // 3600:02d}:{(jami % 3600) // 60:02d}"
	s = str(v)
	return s[:5] if len(s) >= 5 else s


def _guard():
	allowed = {r.lower() for r in ALLOWED_ROLES}
	if not (allowed & {r.lower() for r in frappe.get_roles()}):
		frappe.throw("Ruxsat yo'q.", frappe.PermissionError)


@frappe.whitelist()
def get_data(versiya: str | None = None):
	_guard()
	versiyalar = frappe.get_all(
		"Jadval Versiyasi",
		fields=["name", "nomi", "holat", "amal_boshlanishi", "academic_year"],
		order_by="holat asc, amal_boshlanishi desc",
	)
	if not versiyalar:
		return {"versiyalar": [], "xatolik": "Jadval versiyasi yo'q"}
	versiya = versiya or next(
		(v.name for v in versiyalar if v.holat == "Faol"), versiyalar[0].name
	)

	sinflar = frappe.get_all(
		"Student Group",
		filters={"custom_guruh_turi": "Sinf", "disabled": 0},
		pluck="name",
	)
	sinflar.sort(key=_sinf_tartib)

	yozuvlar = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya},
		fields=[
			"name", "kun", "dars_raqami", "guruh", "guruh_nomi", "fan",
			"oqituvchi", "oqituvchi_nomi", "blok", "sinflar", "xona",
			"boshlanish", "tugash",
		],
		limit_page_length=0,
	)

	# sinf x kun x dars -> darslar ro'yxati (blokda bir nechta guruh bo'lishi mumkin)
	katak = defaultdict(list)
	yuklama = defaultdict(set)
	for y in yozuvlar:
		y_sinflar = [s.strip() for s in (y.sinflar or "").split(",") if s.strip()] or [y.guruh]
		for s in y_sinflar:
			katak[f"{s}|{y.kun}|{y.dars_raqami}"].append(
				{
					"name": y.name,
					"fan": y.fan,
					"guruh": y.guruh,
					"guruh_nomi": y.guruh_nomi,
					"oqituvchi": y.oqituvchi_nomi or y.oqituvchi,
					"blok": y.blok,
					"xona": y.xona,
				}
			)
		if y.oqituvchi:
			yuklama[y.oqituvchi].add((y.kun, y.dars_raqami))

	qongiroqlar = {}
	for q in frappe.get_all("Qongiroq Jadvali", filters={"faol": 1}, pluck="name"):
		doc = frappe.get_cached_doc("Qongiroq Jadvali", q)
		qongiroqlar[q] = {
			"sinf_pattern": doc.sinf_pattern,
			"tartib": doc.tartib,
			"qatorlar": [
				{"no": r.dars_raqami, "b": _vaqt_str(r.boshlanish), "t": _vaqt_str(r.tugash), "turi": r.turi}
				for r in doc.qatorlar
			],
		}

	o_nomlari = {
		i.name: i.instructor_name
		for i in frappe.get_all("Instructor", fields=["name", "instructor_name"])
	}
	return {
		"versiyalar": versiyalar,
		"versiya": versiya,
		"sinflar": sinflar,
		"kunlar": KUNLAR[:5],
		"darslar": list(range(1, 11)),
		"katak": katak,
		"qongiroqlar": qongiroqlar,
		"yuklama": sorted(
			({"oqituvchi": o_nomlari.get(k, k), "soat": len(v)} for k, v in yuklama.items()),
			key=lambda x: -x["soat"],
		),
		"jami_yozuv": len(yozuvlar),
	}


def _sinf_tartib(nom: str):
	"""'10 A(full)' -> (10, 'A') — tabiiy tartib."""
	import re

	m = re.match(r"\s*(\d+)\s*([AB])", nom)
	return (int(m.group(1)), m.group(2)) if m else (999, nom)


@frappe.whitelist()
def get_oqituvchi_jadvali(oqituvchi: str, versiya: str | None = None):
	"""Bitta o'qituvchining haftalik jadvali (panelda ko'rish uchun)."""
	_guard()
	versiya = versiya or frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name")
	return frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "oqituvchi": oqituvchi},
		fields=["kun", "dars_raqami", "fan", "guruh_nomi", "sinflar", "boshlanish", "tugash"],
		order_by="kun_raqami asc, dars_raqami asc",
		limit_page_length=0,
	)
