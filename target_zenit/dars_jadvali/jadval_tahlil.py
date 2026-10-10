# Copyright (c) 2026, Target Zenit
# Jadval yetarlilik (feasibility) tahlili — "Хватит ли учителей?" (Untis) / capacity pre-check.
# O'qituvchi sig'imi (mavjudlik+limitdan) vs talab (soat); sinf sig'imi (grid) vs band slot;
# vakant darslar; fan bo'yicha malaka sig'imi. FAQAT O'QISH.
from __future__ import annotations

import frappe
from frappe import _

from target_zenit.dars_jadvali.oqituvchi_jadval import (
	KUNLAR, _faol_versiya, _guard, _mavjudlik_map, _mavjudlikmi, _max_darslar,
)


def _oqituvchi_sigimi(ins: dict, ndars: int) -> dict:
	"""Bitta o'qituvchining haftalik dars sig'imi (mavjudlik + limitlardan)."""
	mav = _mavjudlik_map(ins["name"])
	per_day_cap = ins.get("custom_max_kunlik_dars") or ndars
	kunlar_bor = 0
	sigim = 0
	for kun in KUNLAR:
		if _mavjudlikmi(mav, kun, 0) == "band":  # butun kun yopiq
			continue
		bosh = sum(1 for d in range(1, ndars + 1) if _mavjudlikmi(mav, kun, d) != "band")
		bosh = min(bosh, per_day_cap)
		if bosh > 0:
			kunlar_bor += 1
			sigim += bosh
	# max_kun — faqat eng yaxshi kunlar hisobga olinadi
	if ins.get("custom_max_kun") and kunlar_bor > ins["custom_max_kun"]:
		sigim = min(sigim, ins["custom_max_kun"] * per_day_cap)
		kunlar_bor = ins["custom_max_kun"]
	if ins.get("custom_haftalik_norma"):
		sigim = min(sigim, ins["custom_haftalik_norma"])
	return {"sigim": sigim, "kunlar_bor": kunlar_bor}


@frappe.whitelist()
def tahlil(versiya: str | None = None) -> dict:
	"""To'liq yetarlilik tahlili: o'qituvchilar, sinflar, vakant, fanlar."""
	_guard()
	versiya = _faol_versiya(versiya)
	ndars = _max_darslar(versiya)
	grid_sigim = ndars * len(KUNLAR)  # bitta sinf uchun maksimum slot (masalan 50)

	yozuvlar = frappe.get_all(
		"Jadval Yozuvi", filters={"versiya": versiya},
		fields=["kun", "dars_raqami", "sinflar", "oqituvchi", "oqituvchi_nomi", "fan", "guruh"],
		limit_page_length=0,
	)

	# --- O'qituvchi talabi (soat) ---
	oq_soat, oq_vakant = {}, 0
	sinf_slot = {}   # sinf -> set((kun,dars))
	fan_soat = {}
	for y in yozuvlar:
		if y.oqituvchi:
			oq_soat[y.oqituvchi] = oq_soat.get(y.oqituvchi, 0) + 1
		else:
			oq_vakant += 1
		fan_soat[y.fan] = fan_soat.get(y.fan, 0) + 1
		for s in (y.sinflar or "").split(","):
			s = s.strip()
			if s:
				sinf_slot.setdefault(s, set()).add((y.kun, int(y.dars_raqami or 0)))

	# --- O'qituvchilar ---
	ins_list = frappe.get_all(
		"Instructor",
		fields=["name", "instructor_name", "custom_vakant", "custom_haftalik_norma",
		        "custom_max_kun", "custom_max_kunlik_dars"],
		order_by="instructor_name", limit_page_length=0)
	oqituvchilar = []
	oq_muammo = 0
	for i in ins_list:
		talab = oq_soat.get(i["name"], 0)
		if i.get("custom_vakant") and talab == 0:
			continue
		cap = _oqituvchi_sigimi(i, ndars)
		holat = "ok"
		if talab > cap["sigim"]:
			holat = "sigim_oshgan"      # sig'imdan ko'p — jadval yig'ilmaydi
		elif i.get("custom_haftalik_norma") and talab > i["custom_haftalik_norma"]:
			holat = "norma_oshgan"
		if holat != "ok":
			oq_muammo += 1
		oqituvchilar.append({
			"nomi": i["instructor_name"], "talab": talab, "sigim": cap["sigim"],
			"norma": i.get("custom_haftalik_norma") or 0, "kunlar_bor": cap["kunlar_bor"],
			"bosh": cap["sigim"] - talab, "holat": holat,
		})
	oqituvchilar.sort(key=lambda x: (x["holat"] == "ok", -(x["talab"] - x["sigim"])))

	# --- Sinflar (faqat asosiy "Sinf" turidagilar) ---
	sinf_turlari = {g.name: g for g in frappe.get_all(
		"Student Group", filters={"custom_guruh_turi": "Sinf"},
		fields=["name", "student_group_name"], limit_page_length=0)}
	sinflar = []
	sinf_muammo = 0
	for nm, g in sinf_turlari.items():
		band = len(sinf_slot.get(nm, set()))
		holat = "ok"
		if band > grid_sigim:
			holat = "sigim_oshgan"; sinf_muammo += 1
		elif band == grid_sigim:
			holat = "toliq"
		sinflar.append({
			"sinf": g.student_group_name or nm, "band": band, "sigim": grid_sigim,
			"bosh": grid_sigim - band, "holat": holat,
		})
	sinflar.sort(key=lambda x: -x["band"])

	# --- Fan bo'yicha malaka sig'imi (fanni o'tadigan o'qituvchilar sig'imi vs talab) ---
	fan_oqit = {}
	for r in frappe.db.sql(
		"""SELECT DISTINCT fan, oqituvchi FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND oqituvchi IS NOT NULL""", (versiya,), as_dict=True):
		fan_oqit.setdefault(r.fan, set()).add(r.oqituvchi)
	ins_map = {i["name"]: i for i in ins_list}
	sig_cache = {}
	fanlar = []
	for fan, talab in sorted(fan_soat.items(), key=lambda x: -x[1]):
		oqitlar = fan_oqit.get(fan, set())
		cap = 0
		for o in oqitlar:
			if o not in sig_cache:
				sig_cache[o] = _oqituvchi_sigimi(ins_map[o], ndars)["sigim"] if o in ins_map else 0
			cap += sig_cache[o]
		fanlar.append({"fan": fan, "talab": talab, "oqituvchilar_soni": len(oqitlar),
		               "umumiy_sigim": cap, "kam": talab > cap})

	return {
		"versiya": versiya, "ndars": ndars, "grid_sigim": grid_sigim,
		"stats": {
			"jami_dars": len(yozuvlar), "vakant": oq_vakant,
			"oq_muammo": oq_muammo, "sinf_muammo": sinf_muammo,
			"oqituvchi_soni": len(oqituvchilar), "sinf_soni": len(sinflar),
		},
		"oqituvchilar": oqituvchilar,
		"sinflar": sinflar,
		"fanlar": fanlar,
	}
