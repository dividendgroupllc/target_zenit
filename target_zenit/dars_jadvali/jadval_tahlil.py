# Copyright (c) 2026, Target Zenit
# Jadval yetarlilik (feasibility) tahlili — "Хватит ли учителей?" (Untis) / capacity pre-check.
# O'qituvchi sig'imi (mavjudlik+limitdan) vs talab (soat); sinf sig'imi (grid) vs band slot;
# vakant darslar; fan bo'yicha malaka sig'imi. FAQAT O'QISH.
from __future__ import annotations

from itertools import pairwise

import frappe
from frappe import _

from target_zenit.dars_jadvali.oqituvchi_jadval import (
	KUNLAR,
	_faol_versiya,
	_guard,
	_mavjudlik_map,
	_mavjudlikmi,
	_max_darslar,
)
from target_zenit.nomlar import oqituvchi_nomlari


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
	ins_nom = oqituvchi_nomlari([i["name"] for i in ins_list])
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
			"nomi": ins_nom.get(i["name"]) or i["instructor_name"],
			"talab": talab, "sigim": cap["sigim"],
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
			holat = "sigim_oshgan"
			sinf_muammo += 1
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
		"versiya": versiya, "ndars": ndars, "grid_sigim": grid_sigim, "sanpin": sanpin_tahlil(versiya),
		"stats": {
			"jami_dars": len(yozuvlar), "vakant": oq_vakant,
			"oq_muammo": oq_muammo, "sinf_muammo": sinf_muammo,
			"oqituvchi_soni": len(oqituvchilar), "sinf_soni": len(sinflar),
		},
		"oqituvchilar": oqituvchilar,
		"sinflar": sinflar,
		"fanlar": fanlar,
	}


# ------------------------------------------------- SanPiN / Sivkov qiyinchilik tahlili
OGIR_BALL = 9  # shu balldan boshlab fan "og'ir" hisoblanadi (ketma-ketlik tekshiruvi)


def _sinf_darajasi(nom: str) -> int:
	"""'10 A(full)' -> 10. Raqamsiz (Pre school) -> 0."""
	import re

	m = re.match(r"\s*(\d+)", nom or "")
	return int(m.group(1)) if m else 0


def sanpin_tahlil(versiya: str | None = None) -> dict:
	"""Har sinf uchun kunlik qiyinchilik balli (Sivkov/SanPiN shkalasi) +
	ogohlantirishlar: cho'qqi hafta boshida/oxirida, og'ir fanlar ketma-ket.
	Post-sovet tizimlarining (Ректор/НИКА) o'ziga xos qatlami — tekshiruv
	spravkasi uchun ham ishlatiladi."""
	versiya = _faol_versiya(versiya)
	if not frappe.db.exists("DocType", "Fan Qiyinchiligi"):
		return {"sinflar": [], "shkala_bor": False}
	shkala = {
		r.fan: (r.ball_boshlangich or 5, r.ball_yuqori or 5)
		for r in frappe.get_all(
			"Fan Qiyinchiligi", fields=["fan", "ball_boshlangich", "ball_yuqori"],
			limit_page_length=0)
	}
	yozuvlar = frappe.get_all(
		"Jadval Yozuvi", filters={"versiya": versiya},
		fields=["kun", "dars_raqami", "sinflar", "fan"], limit_page_length=0)

	sinf_nomlari = {g.name: g.student_group_name or g.name for g in frappe.get_all(
		"Student Group", filters={"custom_guruh_turi": "Sinf"},
		fields=["name", "student_group_name"], limit_page_length=0)}

	# (sinf, kun, dars) -> eng og'ir parallel dars (daraja guruhlari bitta slot)
	slot = {}
	for y in yozuvlar:
		for s in (y.sinflar or "").split(","):
			s = s.strip()
			if s not in sinf_nomlari:
				continue
			daraja = _sinf_darajasi(sinf_nomlari[s])
			b = shkala.get(y.fan, (5, 5))[0 if 1 <= daraja <= 4 else 1]
			key = (s, y.kun, int(y.dars_raqami or 0))
			if key not in slot or b > slot[key][0]:
				slot[key] = (b, y.fan)

	natija = []
	for s, nomi in sorted(sinf_nomlari.items(), key=lambda x: (_sinf_darajasi(x[1]), x[1])):
		kunlik = {}
		ogohlar = []
		for kun in KUNLAR:
			darslar = sorted(
				(d, v) for (ss, kk, d), v in slot.items() if ss == s and kk == kun)
			kunlik[kun] = sum(v[0] for _d, v in darslar)
			# og'ir fanlar ketma-ket
			for (d1, v1), (d2, v2) in pairwise(darslar):
				if d2 == d1 + 1 and v1[0] >= OGIR_BALL and v2[0] >= OGIR_BALL and v1[1] != v2[1]:
					ogohlar.append(f"{kun} {d1}–{d2}: {v1[1]} + {v2[1]} ketma-ket (ikkalasi og'ir)")
		if not any(kunlik.values()):
			continue
		eng_ogir = max(KUNLAR, key=lambda k: kunlik[k])
		if eng_ogir in ("Dushanba", "Juma"):
			ogohlar.insert(0,
				f"Eng og'ir kun — {eng_ogir} ({kunlik[eng_ogir]} ball). "
				"SanPiN: cho'qqi seshanba–chorshanbada bo'lishi kerak.")
		natija.append({
			"sinf": nomi, "daraja": _sinf_darajasi(nomi),
			"kunlik": kunlik, "jami": sum(kunlik.values()),
			"eng_ogir": eng_ogir, "ogohlar": ogohlar[:6],
		})

	return {
		"sinflar": natija,
		"shkala_bor": True,
		"kunlar": KUNLAR,
		"muammoli": sum(1 for r in natija if r["ogohlar"]),
	}
