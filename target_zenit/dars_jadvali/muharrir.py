# Copyright (c) 2026, Target Zenit
# Jadval muharriri — zavuch uchun interaktiv ko'chirish qatlami.
# Dunyo standartlari (aSc/Untis/Prime): karta ko'tarilganda slotlarni jonli
# bo'yash (yashil=mumkin / qizil=band + NEGA sababi), lock/pin, "bu katakka
# nima sig'adi" teskari qidiruv. Konfliktning yakuniy himoyasi — Jadval
# Yozuvi.validate (bu yerdagi xarita faqat UI uchun oldindan hisob).
from __future__ import annotations

import frappe
from frappe import _

from target_zenit.dars_jadvali.oqituvchi_jadval import (
	KUNLAR,
	_faol_versiya,
	_mavjudlik_map,
	_mavjudlikmi,
	_max_darslar,
)
from target_zenit.nomlar import oqituvchi_nomlari

MUHARRIR = {"system manager", "zavuch", "academics user", "education manager", "xojakbar_operator"}


def _guard():
	if not (MUHARRIR & {r.lower() for r in frappe.get_roles()}):
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)


def _versiya_yozuvlari(versiya):
	return frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya},
		fields=["name", "kun", "dars_raqami", "guruh", "guruh_nomi", "fan",
		        "oqituvchi", "oqituvchi_nomi", "blok", "xona", "sinflar", "qulf"],
		limit_page_length=0,
	)


def _kochma_toplam(doc, yozuvlar):
	"""Ko'chiriladigan yozuvlar to'plami: oddiy dars = o'zi; blok darsi = shu
	blokning AYNI SLOTdagi barcha parallel yozuvlari (blok birga ko'chadi)."""
	if not doc.blok:
		return [y for y in yozuvlar if y.name == doc.name]
	return [
		y for y in yozuvlar
		if y.blok == doc.blok and y.kun == doc.kun
		and int(y.dars_raqami or 0) == int(doc.dars_raqami or 0)
	]


def _slot_xarita(yozuvlar, kochma):
	"""(kun, dars) -> shu slotdagi boshqa yozuvlar (ko'chma to'plamdan tashqari)."""
	kochma_nomlar = {y.name for y in kochma}
	m = {}
	for y in yozuvlar:
		if y.name in kochma_nomlar:
			continue
		m.setdefault((y.kun, int(y.dars_raqami or 0)), []).append(y)
	return m


def _slot_sabablari(slot_rows, oqituvchilar, sinflar, xonalar, blok):
	"""Bitta slot uchun konflikt sabablari ro'yxati (bo'sh = mumkin)."""
	sabab = []
	for r in slot_rows:
		if r.oqituvchi and r.oqituvchi in oqituvchilar:
			sabab.append(f"O'qituvchi band: {r.oqituvchi_nomi or r.oqituvchi} — {r.fan}")
			continue
		r_sinflar = {s.strip() for s in (r.sinflar or "").split(",") if s.strip()}
		kesishma = sinflar & r_sinflar
		if kesishma and not (blok and r.blok == blok):
			sabab.append(f"Sinf band: {', '.join(sorted(kesishma))} — {r.fan}")
			continue
		if r.xona and r.xona in xonalar:
			sabab.append(f"Xona band: {r.xona}")
	# dublikatlarni tartibni saqlab olib tashlash (blokda bir xil sabab ko'p chiqadi)
	return list(dict.fromkeys(sabab))


def _sinflar_toplam(rows) -> set:
	out = set()
	for r in rows:
		out |= {s.strip() for s in (r.sinflar or "").split(",") if s.strip()}
	return out


def _siqiladiganlar(slot_rows, sinflar, blok):
	"""Maqsad slotda bizning sinflarimizni band qilgan (siqib chiqariladigan) yozuvlar."""
	out = []
	for r in slot_rows:
		r_sinflar = {s.strip() for s in (r.sinflar or "").split(",") if s.strip()}
		if (sinflar & r_sinflar) and not (blok and r.blok == blok):
			out.append(r)
	return out


def _swap_baho(siqiladigan, slot_rows, kochma, oqituvchilar, sinflar, xonalar, blok,
               eski_rows, mavlar, eski_kun, eski_dars, kun, d):
	"""Maqsad slotdagi qarshi dars(lar) bilan 2 tomonlama almashuvni baholaydi.
	Qaytaradi: (holat, tavsif, sabab) — holat = 'swap_ok' (toza) / 'swap_warn'
	(muammo bor, lekin baribir bosib ko'rsa bo'ladi). Istalgan darsni almashtirish
	mumkin — professional muharrir uslubi (aSc/Untis)."""
	kochma_nomlar = {y.name for y in kochma}
	tavsif = list(dict.fromkeys(
		f"{r.fan} — {r.guruh_nomi or r.guruh}" for r in siqiladigan))[:3]
	sabab = []

	# (A) Bizning dars maqsad slotga tushadi: o'sha slotdagi QARSHI bo'lmagan
	# (siqilmaydigan) yozuvlar bilan to'qnashmasinmi
	siq_nomlar = {r.name for r in siqiladigan}
	qolgan = [r for r in slot_rows if r.name not in siq_nomlar]
	sabab += _slot_sabablari(qolgan, oqituvchilar, sinflar, xonalar, blok)
	for o, mav in mavlar.items():
		if _mavjudlikmi(mav, kun, d) == "band":
			sabab.append(f"{oqituvchi_nomlari([o]).get(o) or o} bu vaqtda ishlamaydi")

	# (B) Qarshi dars bizning eski slotga tushadi
	s_oqit = {r.oqituvchi for r in siqiladigan if r.oqituvchi}
	s_sinf = _sinflar_toplam(siqiladigan)
	s_xona = {r.xona for r in siqiladigan if r.xona}
	eski_qolgan = [r for r in eski_rows if r.name not in kochma_nomlar]
	sabab += _slot_sabablari(eski_qolgan, s_oqit, s_sinf, s_xona, None)
	for o in s_oqit:
		if _mavjudlikmi(_mavjudlik_map(o), eski_kun, eski_dars) == "band":
			sabab.append(f"{oqituvchi_nomlari([o]).get(o) or o} eski vaqtda ishlamaydi")

	if any(r.qulf for r in siqiladigan):
		sabab.append("qarshi dars qulflangan")

	sabab = list(dict.fromkeys(sabab))
	holat = "swap_warn" if sabab else "swap_ok"
	return holat, tavsif, sabab[:4]


@frappe.whitelist()
def kochirish_xarita(yozuv: str) -> dict:
	"""Karta «ko'tarilganda» butun hafta slotlari holati: ok / afzal / band (+NEGA).
	Blok darsi uchun butun parallel to'plam birga baholanadi."""
	_guard()
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	slotlar = _slot_xarita(yozuvlar, kochma)
	ndars = _max_darslar(doc.versiya)

	oqituvchilar = {y.oqituvchi for y in kochma if y.oqituvchi}
	sinflar = set()
	for y in kochma:
		sinflar |= {s.strip() for s in (y.sinflar or "").split(",") if s.strip()}
	xonalar = {y.xona for y in kochma if y.xona}
	mavlar = {o: _mavjudlik_map(o) for o in oqituvchilar}

	eski_kun, eski_dars = doc.kun, int(doc.dars_raqami or 0)
	eski_rows = slotlar.get((eski_kun, eski_dars), [])
	xarita = {}
	for kun in KUNLAR:
		for d in range(1, ndars + 1):
			key = f"{kun}|{d}"
			if kun == eski_kun and d == eski_dars:
				xarita[key] = {"holat": "oz"}
				continue
			slot_rows = slotlar.get((kun, d), [])
			# Maqsad slotda bizning sinf(lar)imizni band qilgan dars(lar) bormi?
			siqiladigan = _siqiladiganlar(slot_rows, sinflar, doc.blok)
			if siqiladigan:
				# Band katak — ISTALGANINI almashtirsa bo'ladi (toza yoki ogohli)
				holat, tavsif, sabab = _swap_baho(
					siqiladigan, slot_rows, kochma, oqituvchilar, sinflar, xonalar,
					doc.blok, eski_rows, mavlar, eski_kun, eski_dars, kun, d)
				xarita[key] = {"holat": holat, "bilan": tavsif, "sabab": sabab}
				continue
			# Bo'sh katak — bizning darsimiz to'g'ridan-to'g'ri tushadimi?
			sabab = _slot_sabablari(slot_rows, oqituvchilar, sinflar, xonalar, doc.blok)
			afzal = False
			for o, mav in mavlar.items():
				mh = _mavjudlikmi(mav, kun, d)
				if mh == "band":
					sabab.append(f"{oqituvchi_nomlari([o]).get(o) or o} bu vaqtda ishlamaydi")
				elif mh == "afzal":
					afzal = True
			if sabab:
				xarita[key] = {"holat": "band", "sabab": sabab[:4]}
			else:
				xarita[key] = {"holat": "afzal" if afzal else "ok"}

	return {
		"yozuv": doc.name,
		"fan": doc.fan,
		"guruh_nomi": doc.guruh_nomi or doc.guruh,
		"sinflar": sorted(sinflar),
		"blok": doc.blok,
		"blok_hajmi": len(kochma),
		"qulf": any(y.qulf for y in kochma),
		"kun": doc.kun,
		"dars_raqami": int(doc.dars_raqami or 0),
		"xarita": xarita,
	}


@frappe.whitelist()
def dars_kochir(yozuv: str, kun: str, dars_raqami) -> dict:
	"""Darsni (blok bo'lsa — butun parallel to'plamni) yangi slotga ko'chiradi.
	Validate konfliktni qayta tekshiradi — xato bo'lsa hech narsa o'zgarmaydi."""
	_guard()
	dars_raqami = int(dars_raqami)
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	eski = {"kun": doc.kun, "dars_raqami": int(doc.dars_raqami or 0)}
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	if any(y.qulf for y in kochma):
		frappe.throw(_("Dars qulflangan — avval qulfni oching."))
	kochirildi = []
	for y in kochma:
		d = frappe.get_doc("Jadval Yozuvi", y.name)
		d.kun = kun
		d.dars_raqami = dars_raqami
		d.save(ignore_permissions=True)
		kochirildi.append(d.name)
	frappe.db.commit()
	return {"ok": 1, "eski": eski, "kochirildi": kochirildi}


@frappe.whitelist()
def dars_almashtir(yozuv: str, kun: str, dars_raqami) -> dict:
	"""2 tomonlama almashuv: bizning dars maqsad slotga, u yerdagi qarshi dars(lar)
	bizning eski slotga. Avval xom (raw) ko'chiriladi, so'ng har hujjat to'liq
	validate bilan saqlanadi — konflikt chiqsa hammasi orqaga qaytadi."""
	_guard()
	dars_raqami = int(dars_raqami)
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	eski_kun, eski_dars = doc.kun, int(doc.dars_raqami or 0)
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	if any(y.qulf for y in kochma):
		frappe.throw(_("Dars qulflangan — avval qulfni oching."))
	sinflar = _sinflar_toplam(kochma)
	kochma_nomlar = {y.name for y in kochma}
	siqiladigan = [
		y for y in yozuvlar
		if y.kun == kun and int(y.dars_raqami or 0) == dars_raqami
		and y.name not in kochma_nomlar
		and (sinflar & {s.strip() for s in (y.sinflar or "").split(",")})
		and not (doc.blok and y.blok == doc.blok)
	]
	if not siqiladigan:
		frappe.throw(_("Bu slotda almashadigan dars yo'q — oddiy ko'chirishni ishlating."))
	if any(y.qulf for y in siqiladigan):
		frappe.throw(_("Qarshi dars qulflangan — almashtirib bo'lmaydi."))
	try:
		# 1) xom ko'chirish (oraliq holatda validate chaqirilmaydi)
		for y in siqiladigan:
			frappe.db.set_value("Jadval Yozuvi", y.name,
				{"kun": eski_kun, "dars_raqami": eski_dars}, update_modified=False)
		for y in kochma:
			frappe.db.set_value("Jadval Yozuvi", y.name,
				{"kun": kun, "dars_raqami": dars_raqami}, update_modified=False)
		# 2) yakuniy holatda to'liq validate (vaqt/kun_raqami qayta hisoblanadi)
		for nm in [y.name for y in siqiladigan] + sorted(kochma_nomlar):
			d2 = frappe.get_doc("Jadval Yozuvi", nm)
			d2.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		raise
	frappe.db.commit()
	return {
		"ok": 1,
		"eski": {"kun": eski_kun, "dars_raqami": eski_dars},
		"kochirildi": sorted(kochma_nomlar),
		"almashdi": [y.name for y in siqiladigan],
	}


@frappe.whitelist()
def qulf_toggle(yozuv: str) -> dict:
	"""Qulf yoqish/ochish. Blok darsi uchun butun parallel to'plamga qo'llanadi."""
	_guard()
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	yangi = 0 if doc.qulf else 1
	for y in kochma:
		frappe.db.set_value("Jadval Yozuvi", y.name, "qulf", yangi, update_modified=False)
	frappe.db.commit()
	return {"qulf": yangi, "soni": len(kochma)}


@frappe.whitelist()
def katak_kandidatlar(sinf: str, kun: str, dars_raqami, versiya: str | None = None) -> dict:
	"""Bo'sh katak uchun «bu yerga nima sig'adi?» (aSc teskari qidiruv):
	(a) shu sinfning boshqa slotlardagi ko'chirsa bo'ladigan darslari,
	(b) shu slotda bo'sh o'qituvchilar (fanlari va yuklamasi bilan)."""
	_guard()
	versiya = _faol_versiya(versiya)
	dars_raqami = int(dars_raqami)
	yozuvlar = _versiya_yozuvlari(versiya)

	slot_rows = [y for y in yozuvlar if y.kun == kun and int(y.dars_raqami or 0) == dars_raqami]
	band_oqit = {y.oqituvchi for y in slot_rows if y.oqituvchi}
	band_xona = {y.xona for y in slot_rows if y.xona}

	# (a) shu sinfning boshqa darslari — shu katakka ko'chirish mumkinmi
	sinf_darslari = [
		y for y in yozuvlar
		if sinf in {s.strip() for s in (y.sinflar or "").split(",")}
		and not (y.kun == kun and int(y.dars_raqami or 0) == dars_raqami)
	]
	# Blok guruhlash: blok darsi butun to'plam bilan baholanadi
	korilgan_blok = set()
	kochirish = []
	for y in sinf_darslari:
		if y.blok:
			bk = (y.blok, y.kun, int(y.dars_raqami or 0))
			if bk in korilgan_blok:
				continue
			korilgan_blok.add(bk)
			toplam = [
				z for z in yozuvlar
				if z.blok == y.blok and z.kun == y.kun
				and int(z.dars_raqami or 0) == int(y.dars_raqami or 0)
			]
		else:
			toplam = [y]
		oqitlar = {z.oqituvchi for z in toplam if z.oqituvchi}
		sinflar = set()
		for z in toplam:
			sinflar |= {s.strip() for s in (z.sinflar or "").split(",") if s.strip()}
		xonalar = {z.xona for z in toplam if z.xona}
		sabab = _slot_sabablari(
			[r for r in slot_rows if r.name not in {z.name for z in toplam}],
			oqitlar, sinflar, xonalar, y.blok,
		)
		for o in oqitlar:
			if _mavjudlikmi(_mavjudlik_map(o), kun, dars_raqami) == "band":
				sabab.append(f"{y.oqituvchi_nomi or o} bu vaqtda ishlamaydi")
		if any(z.qulf for z in toplam):
			sabab.append("qulflangan")
		kochirish.append({
			"yozuv": y.name, "fan": y.fan, "guruh_nomi": y.guruh_nomi or y.guruh,
			"kun": y.kun, "dars_raqami": int(y.dars_raqami or 0),
			"blok": y.blok, "blok_hajmi": len(toplam),
			"mumkin": not sabab, "sabab": sabab[:3],
		})
	kochirish.sort(key=lambda x: (not x["mumkin"], x["kun"], x["dars_raqami"]))

	# (b) shu slotda bo'sh o'qituvchilar
	soat = {}
	fanlari = {}
	for y in yozuvlar:
		if y.oqituvchi:
			soat[y.oqituvchi] = soat.get(y.oqituvchi, 0) + 1
			fanlari.setdefault(y.oqituvchi, set()).add(y.fan)
	ins_list = frappe.get_all(
		"Instructor", filters={"custom_vakant": 0},
		fields=["name", "instructor_name", "custom_haftalik_norma"], limit_page_length=0)
	nomlar = oqituvchi_nomlari([i["name"] for i in ins_list])
	bosh = []
	for i in ins_list:
		nm = i["name"]
		if nm in band_oqit:
			continue
		if _mavjudlikmi(_mavjudlik_map(nm), kun, dars_raqami) == "band":
			continue
		bosh.append({
			"oqituvchi": nm,
			"nomi": nomlar.get(nm) or i["instructor_name"],
			"soat": soat.get(nm, 0),
			"norma": i.get("custom_haftalik_norma") or 0,
			"fanlar": sorted(fanlari.get(nm, set()))[:6],
		})
	bosh.sort(key=lambda x: x["soat"])

	return {"kochirish": kochirish, "bosh_oqituvchilar": bosh, "band_xonalar": sorted(band_xona)}
