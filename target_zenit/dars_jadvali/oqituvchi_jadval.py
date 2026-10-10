# Copyright (c) 2026, Target Zenit
# O'qituvchi band/bo'sh to'ri + yuklama + "kim o'qita oladi" kandidatlari.
# Dunyo standartlari: teacher availability grid (Untis Zeitwunsche) + cover-candidate
# ranking (Untis/Arbor) + feasibility pre-check. FAQAT O'QISH — jadvalni o'zgartirmaydi.
from __future__ import annotations

import frappe
from frappe import _

KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"]
MENEJER = {"system manager", "zavuch", "academics user", "education manager"}


def _guard():
	if not (MENEJER & {r.lower() for r in frappe.get_roles()}):
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)


def _faol_versiya(versiya=None):
	return versiya or frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")


def _max_darslar(versiya):
	"""Qo'ng'iroq jadvalidagi eng ko'p dars raqami (grid balandligi)."""
	m = frappe.db.sql(
		"""SELECT MAX(q.dars_raqami) FROM `tabQongiroq Qatori` q
		   WHERE q.dars_raqami > 0""")
	return int(m[0][0]) if m and m[0][0] else 10


def _mavjudlik_map(oqituvchi):
	"""Instructor.custom_mavjudlik -> {(kun, dars): holat}. dars=0 => butun kun."""
	rows = frappe.get_all(
		"Oqituvchi Mavjudlik",
		filters={"parent": oqituvchi, "parenttype": "Instructor"},
		fields=["kun", "dars_raqami", "holat"], limit_page_length=0,
	)
	out = {}
	for r in rows:
		holat = "band" if (r.holat or "").startswith("Band") else "afzal"
		out[(r.kun, int(r.dars_raqami or 0))] = holat
	return out


def _mavjudlikmi(mav, kun, dars):
	"""(kun,dars) uchun: 'band' / 'afzal' / None."""
	if (kun, 0) in mav:
		return mav[(kun, 0)]
	return mav.get((kun, dars))


@frappe.whitelist()
def oqituvchi_tori(oqituvchi: str, versiya: str | None = None) -> dict:
	"""Bitta o'qituvchining haftalik band/bo'sh to'ri + yuklama tahlili."""
	_guard()
	versiya = _faol_versiya(versiya)
	ndars = _max_darslar(versiya)
	mav = _mavjudlik_map(oqituvchi)

	# Band yacheykalar — jadval yozuvidan
	yozuvlar = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "oqituvchi": oqituvchi},
		fields=["name", "kun", "dars_raqami", "fan", "guruh_nomi", "xona"],
		limit_page_length=0,
	)
	band = {}
	for y in yozuvlar:
		band.setdefault((y.kun, int(y.dars_raqami or 0)), []).append(
			{"name": y.name, "fan": y.fan, "guruh": y.guruh_nomi, "xona": y.xona})

	# To'r: har kun x dars
	tor = []
	kunlik_son = {k: 0 for k in KUNLAR}
	for d in range(1, ndars + 1):
		qator = {"dars": d, "kataklar": []}
		for k in KUNLAR:
			cell = {"holat": "bosh"}
			if (k, d) in band:
				cell = {"holat": "band", "darslar": band[(k, d)]}
				kunlik_son[k] += 1
			else:
				mh = _mavjudlikmi(mav, k, d)
				if mh == "band":
					cell = {"holat": "blok"}
				elif mh == "afzal":
					cell = {"holat": "afzal"}
			qator["kataklar"].append(cell)
		tor.append(qator)

	# Yuklama tahlili
	ins = frappe.db.get_value(
		"Instructor", oqituvchi,
		["instructor_name", "custom_haftalik_norma", "custom_max_kun",
		 "custom_max_kunlik_dars", "custom_max_ketma_ket", "custom_vakant"],
		as_dict=True) or {}
	jami = len(yozuvlar)
	ish_kunlari = sum(1 for k in KUNLAR if kunlik_son[k] > 0)

	# Max ketma-ket (har kun bo'yicha eng uzun uzluksiz dars zanjiri)
	max_ketma = 0
	for k in KUNLAR:
		seq = best = 0
		for d in range(1, ndars + 1):
			if (k, d) in band:
				seq += 1; best = max(best, seq)
			else:
				seq = 0
		max_ketma = max(max_ketma, best)

	norma = ins.get("custom_haftalik_norma") or 0
	ogohlar = []
	if norma and jami > norma:
		ogohlar.append(f"Yuklama normadan oshgan: {jami} > {norma}")
	if ins.get("custom_max_kun") and ish_kunlari > ins["custom_max_kun"]:
		ogohlar.append(f"Ish kunlari ko'p: {ish_kunlari} > {ins['custom_max_kun']}")
	if ins.get("custom_max_kunlik_dars"):
		for k in KUNLAR:
			if kunlik_son[k] > ins["custom_max_kunlik_dars"]:
				ogohlar.append(f"{k}: {kunlik_son[k]} dars (max {ins['custom_max_kunlik_dars']})")
	if ins.get("custom_max_ketma_ket") and max_ketma > ins["custom_max_ketma_ket"]:
		ogohlar.append(f"Ketma-ket {max_ketma} dars (max {ins['custom_max_ketma_ket']})")
	# Band slot afzal/blokga tushganmi
	for (k, d) in band:
		if _mavjudlikmi(mav, k, d) == "band":
			ogohlar.append(f"{k} {d}-dars: band slotda dars qo'yilgan")

	return {
		"oqituvchi": oqituvchi,
		"nomi": ins.get("instructor_name"),
		"vakant": ins.get("custom_vakant"),
		"versiya": versiya,
		"kunlar": KUNLAR,
		"tor": tor,
		"yuklama": {
			"jami": jami, "norma": norma, "ish_kunlari": ish_kunlari,
			"max_kun": ins.get("custom_max_kun") or 0,
			"kunlik": kunlik_son, "max_ketma": max_ketma,
			"max_ketma_limit": ins.get("custom_max_ketma_ket") or 0,
		},
		"ogohlar": ogohlar,
	}


@frappe.whitelist()
def oqituvchilar(versiya: str | None = None, fan: str | None = None,
                 guruh: str | None = None) -> list[dict]:
	"""Barcha o'qituvchilar + haftalik soat. fan/guruh berilsa — faqat shu fan/guruhда
	dars o'tadigan o'qituvchilar."""
	_guard()
	versiya = _faol_versiya(versiya)
	ins = frappe.get_all(
		"Instructor",
		fields=["name", "instructor_name", "custom_vakant", "custom_haftalik_norma"],
		order_by="instructor_name", limit_page_length=0)
	soat = {}
	for r in frappe.db.sql(
		"""SELECT oqituvchi, COUNT(*) n FROM `tabJadval Yozuvi`
		   WHERE versiya=%s GROUP BY oqituvchi""", (versiya,), as_dict=True):
		soat[r.oqituvchi] = r.n
	# Fan/guruh filtri: shu fan/guruhда darsi bor o'qituvchilar
	ruxsat = None
	if fan or guruh:
		f = {"versiya": versiya}
		if fan:
			f["fan"] = fan
		if guruh:
			f["guruh"] = guruh
		ruxsat = set(r.oqituvchi for r in frappe.get_all(
			"Jadval Yozuvi", filters=f, fields=["oqituvchi"], limit_page_length=0) if r.oqituvchi)
	out = []
	for i in ins:
		if ruxsat is not None and i["name"] not in ruxsat:
			continue
		i["soat"] = soat.get(i["name"], 0)
		out.append(i)
	return out


@frappe.whitelist()
def filtr_variantlari(versiya: str | None = None) -> dict:
	"""Filtr dropdownlari uchun: fanlar (jadvaldagilar) + guruhlar (turi bo'yicha)."""
	_guard()
	versiya = _faol_versiya(versiya)
	fanlar = sorted(set(
		r.fan for r in frappe.get_all("Jadval Yozuvi", filters={"versiya": versiya},
		fields=["fan"], distinct=True, limit_page_length=0) if r.fan))
	guruhlar = frappe.get_all(
		"Student Group",
		fields=["name", "student_group_name", "custom_guruh_turi"],
		order_by="custom_guruh_turi, student_group_name", limit_page_length=0)
	return {"fanlar": fanlar, "guruhlar": guruhlar}


@frappe.whitelist()
def dars_qosh(oqituvchi: str, kun: str, dars_raqami, fan: str, guruh: str,
              versiya: str | None = None) -> dict:
	"""Shu (o'qituvchi, kun, dars) slotiga yangi dars qo'shadi. Jadval Yozuvi'ning o'zi
	vaqt/sinf/konfliktni tekshiradi — konflikt bo'lsa xato beradi."""
	_guard()
	versiya = _faol_versiya(versiya)
	doc = frappe.get_doc({
		"doctype": "Jadval Yozuvi",
		"versiya": versiya,
		"kun": kun,
		"dars_raqami": int(dars_raqami),
		"oqituvchi": oqituvchi,
		"fan": fan,
		"guruh": guruh,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "fan": doc.fan, "guruh": doc.guruh_nomi or doc.guruh}


@frappe.whitelist()
def dars_ochir(name: str) -> dict:
	"""Jadval yozuvini (darsni) o'chiradi."""
	_guard()
	frappe.delete_doc("Jadval Yozuvi", name, ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1}


def _fan_oqituvchilari(versiya):
	"""Qaysi o'qituvchi qaysi fanni o'qitadi (jadvaldagi mavjud darslardan — malaka proksi)."""
	m = {}
	for r in frappe.db.sql(
		"""SELECT DISTINCT fan, oqituvchi FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND oqituvchi IS NOT NULL""", (versiya,), as_dict=True):
		m.setdefault(r.fan, set()).add(r.oqituvchi)
	return m


@frappe.whitelist()
def kim_ola_oladi(kun: str, dars_raqami, fan: str | None = None,
                  guruh: str | None = None, versiya: str | None = None) -> list[dict]:
	"""Shu (kun, dars) uchun darsni o'tishi mumkin bo'lgan o'qituvchilar — ranjlangan.
	Tartib: fanni o'qitadi -> kam yuklama. Band/blok/limit sabablari bilan chiqariladi."""
	_guard()
	versiya = _faol_versiya(versiya)
	dars_raqami = int(dars_raqami)
	fan_map = _fan_oqituvchilari(versiya)
	fan_oqit = fan_map.get(fan, set()) if fan else set()

	# Shu slotda band o'qituvchilar
	band_now = set(r.oqituvchi for r in frappe.db.sql(
		"""SELECT DISTINCT oqituvchi FROM `tabJadval Yozuvi`
		   WHERE versiya=%s AND kun=%s AND dars_raqami=%s""",
		(versiya, kun, dars_raqami), as_dict=True))

	# Umumiy yuklama va kunlik
	soat = {}
	for r in frappe.db.sql(
		"""SELECT oqituvchi, COUNT(*) n FROM `tabJadval Yozuvi`
		   WHERE versiya=%s GROUP BY oqituvchi""", (versiya,), as_dict=True):
		soat[r.oqituvchi] = r.n

	ins_list = frappe.get_all(
		"Instructor", filters={"custom_vakant": 0},
		fields=["name", "instructor_name", "custom_haftalik_norma"],
		limit_page_length=0)

	natija = []
	for i in ins_list:
		nm, name = i["instructor_name"], i["name"]
		sabab = []
		if name in band_now:
			continue  # band — kandidat emas
		mav = _mavjudlik_map(name)
		if _mavjudlikmi(mav, kun, dars_raqami) == "band":
			continue  # bu vaqtda ishlamaydi
		norma = i.get("custom_haftalik_norma") or 0
		yuk = soat.get(name, 0)
		if norma and yuk >= norma:
			sabab.append(f"norma to'lgan ({yuk}/{norma})")
		fanchi = name in fan_oqit
		afzal = _mavjudlikmi(mav, kun, dars_raqami) == "afzal"
		natija.append({
			"oqituvchi": name, "nomi": nm, "soat": yuk, "norma": norma,
			"fanni_oqitadi": fanchi, "afzal": afzal,
			"ogoh": "; ".join(sabab),
		})
	# Rank: fanni o'qitadi -> afzal -> kam yuklama
	natija.sort(key=lambda x: (not x["fanni_oqitadi"], not x["afzal"], x["soat"]))
	return natija
