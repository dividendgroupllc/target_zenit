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


def _laganda_bormi() -> bool:
	"""`joylanmagan` ustuni bazada bormi (migrate yurgazilgandan keyin). Prod'da
	migrate kech qolsa sahifa yiqilmasligi uchun — mavjud has_column naqshi."""
	return frappe.db.has_column("Jadval Yozuvi", "joylanmagan")


def _versiya_yozuvlari(versiya):
	fields = ["name", "kun", "dars_raqami", "guruh", "guruh_nomi", "fan",
	          "oqituvchi", "oqituvchi_nomi", "blok", "xona", "sinflar", "qulf"]
	if _laganda_bormi():
		fields.append("joylanmagan")
	rows = frappe.get_all(
		"Jadval Yozuvi", filters={"versiya": versiya}, fields=fields,
		limit_page_length=0,
	)
	for r in rows:
		r.setdefault("joylanmagan", 0)
	return rows


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

	lagandadan = bool(doc.get("joylanmagan"))
	eski_kun, eski_dars = doc.kun, int(doc.dars_raqami or 0)
	eski_rows = [] if lagandadan else slotlar.get((eski_kun, eski_dars), [])
	xarita = {}
	for kun in KUNLAR:
		for d in range(1, ndars + 1):
			key = f"{kun}|{d}"
			if not lagandadan and kun == eski_kun and d == eski_dars:
				xarita[key] = {"holat": "oz"}
				continue
			slot_rows = slotlar.get((kun, d), [])
			# Maqsad slotda bizning sinf(lar)imizni band qilgan dars(lar) bormi?
			siqiladigan = _siqiladiganlar(slot_rows, sinflar, doc.blok)
			if siqiladigan:
				if lagandadan:
					# Lagandadan kelgan karta: almashuv emas, SIQIB CHIQARISH —
					# qarshi dars lagandaga tushadi (aSc bounce uslubi)
					tavsif = list(dict.fromkeys(
						f"{r.fan} — {r.guruh_nomi or r.guruh}" for r in siqiladigan))[:3]
					if any(r.qulf for r in siqiladigan):
						xarita[key] = {"holat": "band", "sabab": ["qarshi dars qulflangan"]}
						continue
					siq_nomlar = {r.name for r in siqiladigan}
					qolgan = [r for r in slot_rows if r.name not in siq_nomlar]
					sabab = _slot_sabablari(qolgan, oqituvchilar, sinflar, xonalar, doc.blok)
					for o, mav in mavlar.items():
						if _mavjudlikmi(mav, kun, d) == "band":
							sabab.append(f"{oqituvchi_nomlari([o]).get(o) or o} bu vaqtda ishlamaydi")
					if sabab:
						xarita[key] = {"holat": "band", "sabab": sabab[:4]}
					else:
						xarita[key] = {"holat": "siqish", "bilan": tavsif}
					continue
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
		"lagandadan": lagandadan,
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
	eski = {
		"kun": doc.kun,
		"dars_raqami": int(doc.dars_raqami or 0),
		"joylanmagan": int(doc.joylanmagan or 0),
	}
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	if any(y.qulf for y in kochma):
		frappe.throw(_("Dars qulflangan — avval qulfni oching."))
	kochirildi = []
	for y in kochma:
		d = frappe.get_doc("Jadval Yozuvi", y.name)
		d.kun = kun
		d.dars_raqami = dars_raqami
		d.joylanmagan = 0
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
def laganda_dedup(versiya: str | None = None) -> dict:
	"""Lagandadagi (joylanmagan) DUBLIKAT darslarni tozalaydi — har bir noyob
	dars (guruh+fan+blok+o'qituvchi) dan bitta nusxa qoldirib, qolganini o'chiradi.
	FAQAT joylanmagan kartalar — real (joylangan) jadvalga tegmaydi."""
	_guard()
	from collections import defaultdict
	versiya = _faol_versiya(versiya)
	lag = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "joylanmagan": 1},
		fields=["name", "guruh", "fan", "blok", "oqituvchi"], order_by="name")
	key = defaultdict(list)
	for r in lag:
		key[(r.guruh, r.fan, r.blok, r.oqituvchi)].append(r.name)
	ochir = []
	for names in key.values():
		if len(names) > 1:
			ochir += sorted(names)[1:]  # eng kichik JY qoladi
	ochirildi = 0
	for nm in ochir:
		# Xavfsizlik: faqat hali ham joylanmagan bo'lsa o'chiramiz
		if frappe.db.get_value("Jadval Yozuvi", nm, "joylanmagan") == 1:
			frappe.delete_doc("Jadval Yozuvi", nm, ignore_permissions=True, force=True)
			ochirildi += 1
	frappe.db.commit()
	return {
		"ochirildi": ochirildi,
		"qolgan": frappe.db.count("Jadval Yozuvi", {"versiya": versiya, "joylanmagan": 1}),
	}


@frappe.whitelist()
def lagandaga(yozuv: str) -> dict:
	"""Kartani jadvaldan lagandaga oladi (o'chirmaydi — joylanmagan bo'ladi).
	Blok darsi butun parallel to'plami bilan olinadi. Undo = eski slotga kochir."""
	_guard()
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	if doc.joylanmagan:
		frappe.throw(_("Karta allaqachon lagandada."))
	eski = {"kun": doc.kun, "dars_raqami": int(doc.dars_raqami or 0)}
	yozuvlar = _versiya_yozuvlari(doc.versiya)
	kochma = _kochma_toplam(doc, yozuvlar)
	if any(y.qulf for y in kochma):
		frappe.throw(_("Dars qulflangan — avval qulfni oching."))
	olingan = []
	for y in kochma:
		d = frappe.get_doc("Jadval Yozuvi", y.name)
		d.joylanmagan = 1
		d.save(ignore_permissions=True)
		olingan.append(d.name)
	frappe.db.commit()
	return {"ok": 1, "eski": eski, "olingan": olingan}


@frappe.whitelist()
def dars_siqib_joyla(yozuv: str, kun: str, dars_raqami) -> dict:
	"""Bizning dars maqsad slotga tushadi, u yerdagi qarshi dars(lar) LAGANDAGA
	siqib chiqariladi (aSc bounce). Konflikt chiqsa hammasi orqaga qaytadi."""
	_guard()
	dars_raqami = int(dars_raqami)
	doc = frappe.get_doc("Jadval Yozuvi", yozuv)
	eski = {
		"kun": doc.kun,
		"dars_raqami": int(doc.dars_raqami or 0),
		"joylanmagan": int(doc.joylanmagan or 0),
	}
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
		frappe.throw(_("Bu slotda siqib chiqariladigan dars yo'q — oddiy ko'chirishni ishlating."))
	if any(y.qulf for y in siqiladigan):
		frappe.throw(_("Qarshi dars qulflangan — siqib chiqarib bo'lmaydi."))
	try:
		for y in siqiladigan:
			frappe.db.set_value("Jadval Yozuvi", y.name,
				{"joylanmagan": 1, "kun": "", "dars_raqami": 0}, update_modified=False)
		for y in kochma:
			frappe.db.set_value("Jadval Yozuvi", y.name,
				{"kun": kun, "dars_raqami": dars_raqami, "joylanmagan": 0},
				update_modified=False)
		for nm in [y.name for y in siqiladigan] + sorted(kochma_nomlar):
			d2 = frappe.get_doc("Jadval Yozuvi", nm)
			d2.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		raise
	frappe.db.commit()
	return {
		"ok": 1,
		"eski": eski,
		"kochirildi": sorted(kochma_nomlar),
		"siqildi": [
			{"yozuv": y.name, "fan": y.fan, "guruh_nomi": y.guruh_nomi or y.guruh}
			for y in siqiladigan
		],
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


# ===================== Versiya / e'lon qilish (publish gate) =====================
# Model: zavuch QORALAMA versiyada tahrir qiladi (o'qituvchi/Moodle ko'rmaydi,
# chunki ular faqat Faol versiyani/Moodle slotlarini o'qiydi). "Saqlash va e'lon
# qilish" bosilganda: eski Faol -> Arxiv, qoralama -> Faol, so'ng Moodle'ga push.


@frappe.whitelist()
def versiya_holati(versiya: str) -> dict:
	"""Joriy versiya haqida: holat, dars soni, boshqa Faol versiya bormi."""
	_guard()
	d = frappe.db.get_value(
		"Jadval Versiyasi", versiya,
		["name", "nomi", "holat", "academic_year", "amal_boshlanishi"],
		as_dict=True) or {}
	d["dars_soni"] = frappe.db.count("Jadval Yozuvi", {"versiya": versiya, "joylanmagan": 0}) \
		if _laganda_bormi() else frappe.db.count("Jadval Yozuvi", {"versiya": versiya})
	d["lagandada"] = frappe.db.count("Jadval Yozuvi", {"versiya": versiya, "joylanmagan": 1}) \
		if _laganda_bormi() else 0
	faol = frappe.get_all(
		"Jadval Versiyasi",
		filters={"holat": "Faol", "name": ["!=", versiya]},
		fields=["name", "nomi"], limit_page_length=0)
	d["boshqa_faol"] = faol
	# Moodle integratsiyasi yoqilganmi
	try:
		from target_zenit.integrations.moodle import _settings
		d["moodle_yoqilgan"] = bool(_settings().enabled)
	except Exception:
		d["moodle_yoqilgan"] = False
	return d


@frappe.whitelist()
def qoralama_yarat(versiya: str, yangi_nomi: str | None = None) -> dict:
	"""Istalgan versiyadan tahrir uchun QORALAMA nusxa (barcha darslari bilan).
	Faol versiyaga tegmay, xavfsiz tahrir qilish uchun."""
	_guard()
	from frappe.utils import today
	doc = frappe.get_doc("Jadval Versiyasi", versiya)
	asos = (yangi_nomi or f"{doc.nomi} — qoralama {today()}").strip()
	nomi = asos
	i = 2
	while frappe.db.exists("Jadval Versiyasi", nomi):
		nomi = f"{asos} ({i})"
		i += 1
	yangi = doc.nusxa_ol(nomi, today())
	return {"versiya": yangi, "nomi": nomi}


@frappe.whitelist()
def eln_qil(versiya: str, amal_sanasi: str | None = None, moodle=1) -> dict:
	"""Qoralamani E'LON qiladi: eski Faol -> Arxiv, bu versiya -> Faol,
	so'ng (ixtiyoriy) Moodle'ga jadval push qiladi. Atomik (xatoda rollback)."""
	_guard()
	from frappe.utils import cint, today
	doc = frappe.get_doc("Jadval Versiyasi", versiya)
	if doc.holat == "Faol":
		frappe.throw(_("Bu versiya allaqachon Faol."))
	sana = amal_sanasi or str(doc.amal_boshlanishi or today())[:10]
	try:
		# 1) Shu o'quv yilidagi eski Faol(lar) -> Arxiv (kesishuv bo'lmasin)
		eskilar = frappe.get_all(
			"Jadval Versiyasi",
			filters={"holat": "Faol", "academic_year": doc.academic_year,
			         "name": ["!=", doc.name]},
			pluck="name")
		for e in eskilar:
			ev = frappe.get_doc("Jadval Versiyasi", e)
			ev.holat = "Arxiv"
			ev.save(ignore_permissions=True)
		# 2) Qoralama -> Faol (amal sanasi bilan; validate kesishuvni tekshiradi)
		doc.holat = "Faol"
		doc.amal_boshlanishi = sana
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		raise
	frappe.db.commit()

	# 3) Moodle'ga push (fon vazifasi — tarmoq so'rovi sekin bo'lishi mumkin)
	moodle_holat = "o'tkazildi"
	if cint(moodle):
		try:
			from target_zenit.integrations.moodle import _settings
			if _settings().enabled:
				frappe.enqueue(
					"target_zenit.integrations.moodle_jadval.push",
					queue="long", timeout=1800, enqueue_after_commit=True,
					job_name=f"moodle_jadval_eln:{doc.name}",
					trigger="Jadvaldan e'lon")
				moodle_holat = "navbatga qo'yildi (fonda ~1 daqiqa)"
			else:
				moodle_holat = "Moodle integratsiyasi o'chirilgan — yuborilmadi"
		except Exception as e:
			moodle_holat = f"Moodle xatosi: {str(e)[:120]}"
	else:
		moodle_holat = "o'tkazildi (so'rovingizga ko'ra)"

	return {
		"ok": 1,
		"versiya": doc.name,
		"amal_sanasi": sana,
		"arxivlandi": eskilar,
		"moodle": moodle_holat,
	}


# ===================== Guruh nomini o'zgartirish =====================
# Faqat KO'RINADIGAN nom (student_group_name) o'zgaradi; ichki ID (docname) va
# shu bilan Moodle groupkey, havolalar, bloklar BARQAROR qoladi ([[unic-id-qoidasi]]).
# Darslar va o'quvchilar tegilmaydi.


@frappe.whitelist()
def guruh_nomini_ozgartir(guruh: str, yangi_nomi: str) -> dict:
	"""Guruhning ko'rinadigan nomini o'zgartiradi. Ichki ID, darslar, o'quvchilar,
	Moodle bog'lanishi saqlanadi — faqat nom yangilanadi (barcha versiyalarda)."""
	_guard()
	yangi_nomi = (yangi_nomi or "").strip()
	if not yangi_nomi:
		frappe.throw(_("Yangi nom bo'sh bo'lmasin."))
	if not frappe.db.exists("Student Group", guruh):
		frappe.throw(_("Guruh topilmadi."))
	eski = frappe.db.get_value("Student Group", guruh, "student_group_name")
	if yangi_nomi == eski:
		return {"ok": 1, "ozgarmadi": 1, "yangi": yangi_nomi}
	band = frappe.db.exists(
		"Student Group", {"student_group_name": yangi_nomi, "name": ["!=", guruh]})
	if band:
		frappe.throw(_("«{0}» nomi boshqa guruhda band.").format(yangi_nomi))

	# 1) Ko'rinadigan nom (ichki ID = docname tegilmaydi)
	frappe.db.set_value("Student Group", guruh, "student_group_name", yangi_nomi)
	# 2) Jadval Yozuvi.guruh_nomi — fetch_from "snapshot" eski qiymatni saqlaydi,
	#    shuning uchun shu guruhning darslarida qo'lda yangilaymiz.
	darslar = frappe.db.count("Jadval Yozuvi", {"guruh": guruh})
	frappe.db.sql(
		"UPDATE `tabJadval Yozuvi` SET guruh_nomi=%s WHERE guruh=%s", (yangi_nomi, guruh))
	frappe.db.commit()

	# 3) Moodle (ixtiyoriy) — ko'rinadigan guruh nomi (groupname) yangilansin.
	#    groupkey = docname o'zgarmagani uchun bog'lanish buzilmaydi.
	moodle = "o'chirilgan"
	try:
		from target_zenit.integrations.moodle import _settings
		if _settings().enabled:
			frappe.enqueue(
				"target_zenit.integrations.moodle_jadval.push",
				queue="long", timeout=1800, enqueue_after_commit=True,
				job_name=f"moodle_guruh_nom:{guruh}", trigger="Guruh nomi o'zgardi")
			moodle = "navbatga qo'yildi"
	except Exception:
		moodle = "yuborilmadi"

	return {"ok": 1, "guruh": guruh, "eski": eski, "yangi": yangi_nomi,
	        "darslar": darslar, "moodle": moodle}


# ===================== Kechki (qo'shimcha) darslar =====================
# Oddiy darslardan keyin (dars_raqami > qo'ng'iroq jadvali maksimumi) qo'shiladigan
# darslar. Faqat ba'zi guruhlar uchun. Mavjud guruh modeli bilan: bitta sinf,
# kross-sinf (qo'shma: 6+7+8 birga), yoki darajaga bo'lingan (High/Middle, har
# darajaga alohida ustoz — ENGLISH kabi) qo'llab-quvvatlanadi.
import re as _re


def _oraliq(sinflar) -> str:
	raqamlar = sorted(
		{_re.match(r"\d+", s).group(0) for s in sinflar if _re.match(r"\d+", s)}, key=int)
	if not raqamlar:
		return "kechki"
	return raqamlar[0] if len(raqamlar) == 1 else f"{raqamlar[0]}-{raqamlar[-1]}"


def _unik_nom(doctype, asos) -> str:
	nomi = asos
	i = 2
	while frappe.db.exists(doctype, nomi):
		nomi = f"{asos} ({i})"
		i += 1
	return nomi


def _kechki_slot(versiya, kun, sinflar, regular_max) -> int:
	"""Berilgan sinflar shu kunda band bo'lmagan eng kichik kechki slot."""
	sinflar_set = set(sinflar)
	band = {}  # dars_raqami -> band sinflar
	for y in frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "kun": kun, "dars_raqami": [">", regular_max]},
		fields=["dars_raqami", "sinflar"], limit_page_length=0):
		s = {x.strip() for x in (y.sinflar or "").split(",") if x.strip()}
		band.setdefault(int(y.dars_raqami), set()).update(s)
	d = regular_max + 1
	while band.get(d) and (band[d] & sinflar_set):
		d += 1
	return d


@frappe.whitelist()
def kechki_dars_qosh(versiya, kun, fan, sinflar, darajalar=None, dars_raqami=None,
                     boshlanish=None, tugash=None) -> dict:
	"""Kechki dars(lar) qo'shadi.
	sinflar: JSON ro'yxat (1+ sinf docname). darajalar: JSON ro'yxat
	[{nom, oqituvchi}] — bo'sh/bitta+nomsiz = oddiy; bir nechta = darajaga bo'lingan.
	boshlanish/tugash: zam direktor kiritgan vaqt (HH:MM), qo'ng'iroq jadvalisiz."""
	_guard()
	import json
	sinflar = json.loads(sinflar) if isinstance(sinflar, str) else (sinflar or [])
	darajalar = json.loads(darajalar) if isinstance(darajalar, str) else (darajalar or [])
	sinflar = [s for s in sinflar if s]
	if not sinflar:
		frappe.throw(_("Kamida bitta sinf tanlang."))
	if not fan:
		frappe.throw(_("Fan tanlang."))
	versiya = _faol_versiya(versiya)
	if not darajalar:
		darajalar = [{"nom": "", "oqituvchi": None}]
	regular_max = _max_darslar(versiya)
	dr = int(dars_raqami) if dars_raqami else _kechki_slot(versiya, kun, sinflar, regular_max)
	ay = frappe.db.get_value("Jadval Versiyasi", versiya, "academic_year")
	vaqt = {"boshlanish": boshlanish or None, "tugash": tugash or None}

	oddiy = len(sinflar) == 1 and len(darajalar) == 1 and not (darajalar[0].get("nom") or "").strip()
	yaratilgan = []
	if oddiy:
		d = frappe.get_doc({
			"doctype": "Jadval Yozuvi", "versiya": versiya, "kun": kun, "dars_raqami": dr,
			"fan": fan, "guruh": sinflar[0], "oqituvchi": darajalar[0].get("oqituvchi") or None,
			**vaqt})
		d.insert(ignore_permissions=True)
		yaratilgan.append(d.name)
	else:
		oraliq = _oraliq(sinflar)
		blok_nomi = _unik_nom("Dars Bloki", f"{fan} {oraliq} kechki")
		guruh_qatorlari = []
		for dj in darajalar:
			nom = (dj.get("nom") or "").strip()
			tur = "Daraja" if nom else "Qo'shma"
			daraja_lbl = nom or "Qo'shma"
			gnomi = _unik_nom("Student Group", f"{fan} {daraja_lbl} {oraliq} kechki")
			sg = frappe.get_doc({
				"doctype": "Student Group", "student_group_name": gnomi,
				"group_based_on": "Course", "course": fan if frappe.db.exists("Course", fan) else None,
				"academic_year": ay, "custom_guruh_turi": tur, "custom_daraja": daraja_lbl,
				"custom_azo_sinflar": ", ".join(sinflar)})
			sg.flags.ignore_mandatory = True
			sg.insert(ignore_permissions=True)
			guruh_qatorlari.append(
				{"daraja": daraja_lbl, "guruh": gnomi, "oqituvchi": dj.get("oqituvchi") or None})
		frappe.get_doc({
			"doctype": "Dars Bloki", "nomi": blok_nomi,
			"fan": fan if frappe.db.exists("Course", fan) else None, "academic_year": ay,
			"sinflar": [{"sinf": s} for s in sinflar],
			"guruhlar": [
				{"daraja": g["daraja"], "guruh": g["guruh"], "oqituvchi": g["oqituvchi"]}
				for g in guruh_qatorlari],
		}).insert(ignore_permissions=True)
		for g in guruh_qatorlari:
			frappe.db.set_value("Student Group", g["guruh"], "custom_blok", blok_nomi, update_modified=False)
			d = frappe.get_doc({
				"doctype": "Jadval Yozuvi", "versiya": versiya, "kun": kun, "dars_raqami": dr,
				"fan": fan, "guruh": g["guruh"], "blok": blok_nomi, "oqituvchi": g["oqituvchi"],
				**vaqt})
			d.insert(ignore_permissions=True)
			yaratilgan.append(d.name)
	frappe.db.commit()
	return {"ok": 1, "dars_raqami": dr, "kechki": 1, "yaratilgan": yaratilgan}


# ===================== Kechki guruhga o'quvchi biriktirish =====================


@frappe.whitelist()
def guruh_oquvchilari(guruh: str) -> dict:
	"""Guruh a'zolari + a'zo sinflaridan nomzod o'quvchilar (biriktirish uchun)."""
	_guard()
	azolar = frappe.get_all(
		"Student Group Student", filters={"parent": guruh},
		fields=["student", "student_name"], limit_page_length=0)
	azo_ids = {a.student for a in azolar}

	azo_sinflar = frappe.db.get_value("Student Group", guruh, "custom_azo_sinflar") or ""
	sinflar = [s.strip() for s in azo_sinflar.split(",") if s.strip()]
	# Blok orqali ham (daraja guruhida azo_sinflar bo'lmasa)
	if not sinflar:
		blok = frappe.db.get_value("Student Group", guruh, "custom_blok")
		if blok:
			sinflar = frappe.get_all("Dars Bloki Sinfi", filters={"parent": blok}, pluck="sinf")
	if not sinflar:
		sinflar = [guruh]

	nomzodlar = []
	korilgan = set()
	for sinf in sinflar:
		for r in frappe.get_all(
			"Student Group Student", filters={"parent": sinf},
			fields=["student", "student_name"], order_by="group_roll_number, idx",
			limit_page_length=0):
			if r.student in korilgan:
				continue
			korilgan.add(r.student)
			nomzodlar.append({
				"student": r.student, "nomi": r.student_name, "sinf": sinf,
				"azo": r.student in azo_ids})
	return {
		"guruh": guruh,
		"nomi": frappe.db.get_value("Student Group", guruh, "student_group_name"),
		"azolar_soni": len(azo_ids), "sinflar": sinflar, "nomzodlar": nomzodlar,
	}


@frappe.whitelist()
def guruh_oquvchilari_saqla(guruh: str, studentlar) -> dict:
	"""Guruh a'zoligini berilgan o'quvchilar ro'yxatiga moslaydi (qo'shadi/olib tashlaydi).
	Mavjud qatorlar (roll raqami) saqlanadi — faqat farq qo'llanadi."""
	_guard()
	import json
	studentlar = json.loads(studentlar) if isinstance(studentlar, str) else (studentlar or [])
	studentlar = [s for s in studentlar if s]
	doc = frappe.get_doc("Student Group", guruh)
	eski = {r.student: r for r in doc.students}
	doc.set("students", [])
	roll = 1
	for sid in studentlar:
		r = eski.get(sid)
		doc.append("students", {
			"student": sid,
			"student_name": (r.student_name if r else None)
			or frappe.db.get_value("Student", sid, "student_name"),
			"group_roll_number": (r.group_roll_number if r and r.group_roll_number else roll),
			"active": 1,
		})
		roll += 1
	doc.flags.ignore_mandatory = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": 1, "soni": len(studentlar)}
