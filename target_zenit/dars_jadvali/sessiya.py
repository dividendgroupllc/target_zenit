# Copyright (c) 2026, Target Zenit
# Birlashgan dars sessiyasi — eduvisit "session" uslubi: bitta darsда davomat + baho +
# mavzu (o'tilgan) + uy vazifa BIR joyda. Faqat ma'lumot yig'adi va uy vazifani saqlaydi;
# davomat/baho = baholash.natija_saqla, mavzu = oquv_reja.dars_otdim orqali.
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from target_zenit import oquv_reja as oreja
from target_zenit.dars_jadvali import baholash as bah
from target_zenit.dars_jadvali import sozlamalar as soz
from target_zenit.dars_jadvali.oqituvchi_jadval import _vaqt_str

# Hafta kunlari (0 = Dushanba) — jadvaldagi `kun` maydoni bilan mos
KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


@frappe.whitelist()
def sessiya_malumot(jadval_yozuvi: str, sana: str | None = None) -> dict:
	"""Bitta dars sessiyasi uchun hamma narsa: dars + o'quvchilar (davomat/baho) +
	o'quv reja (keyingi mavzu / bugungi bajarilish) + uy vazifa."""
	sana = sana or nowdate()
	jy = frappe.db.get_value(
		"Jadval Yozuvi", jadval_yozuvi,
		["fan", "guruh", "guruh_nomi", "oqituvchi", "oqituvchi_nomi", "kun", "versiya",
		 "dars_raqami", "boshlanish", "tugash", "xona"], as_dict=True)
	if not jy:
		frappe.throw(_("Dars topilmadi."))
	s = soz.olish()

	# Davomat + baho (o'quvchilar) + chorak o'rtachasi (chap taraf uchun)
	jurnal = bah.dars_oquvchilari(jadval_yozuvi, sana)
	chorak = jurnal.get("chorak")
	oquvchilar = jurnal.get("oquvchilar") or []
	sids = [o["student"] for o in oquvchilar]

	# O'quvchi rasmlari (kartada yuz ko'rinadi — o'rinbosar/yangi o'qituvchi uchun muhim)
	if sids:
		rasm_map = {r.name: r.image for r in frappe.get_all(
			"Student", filters={"name": ["in", sids]},
			fields=["name", "image"], limit_page_length=0)}
		for o in oquvchilar:
			o["rasm"] = rasm_map.get(o["student"])

	ustunlar, katak_map = [], {}
	if oquvchilar and chorak:
		# Har o'quvchining shu fan+chorak bo'yicha ballari (sana bo'yicha o'sish tartibida)
		# va jurnal matritsasi (o'quvchi × dars sanasi — katak-katak ko'rinish uchun)
		ball_map, absent_map, kech_map = {}, {}, {}
		sanalar = set()
		for r in frappe.get_all(
			"Dars Natijasi",
			filters={"guruh": jy.guruh, "fan": jy.fan, "chorak": chorak,
			         "student": ["in", sids]},
			fields=["student", "baho", "baho_turi", "davomat", "sana",
			        "kechikish_min", "jadval_yozuvi", "izoh"],
			order_by="sana", limit_page_length=0):
			if r.baho:
				ball_map.setdefault(r.student, []).append(r.baho)
			if r.davomat in soz.YOQLIK:
				absent_map[r.student] = absent_map.get(r.student, 0) + 1
			elif r.davomat == "Kechikdi":
				kech_map[r.student] = kech_map.get(r.student, 0) + 1
			d = str(r.sana)
			sanalar.add(d)
			katak_map[(r.student, d)] = {
				"baho": r.baho, "davomat": r.davomat, "baho_turi": r.baho_turi,
				"kechikish_min": r.kechikish_min, "jadval_yozuvi": r.jadval_yozuvi,
				"izoh": r.izoh,
			}
		# Tanlangan kun ustuni har doim bo'lsin (hali hech narsa yozilmagan bo'lsa ham)
		sanalar.add(str(getdate(sana)))
		# Chorakdagi BARCHA dars kunlari — jurnali bo'sh o'tgan kunlar ham ustun bo'lib chiqadi,
		# shunda o'qituvchi oldingi sanaga ham baho/davomat qo'yishi mumkin.
		kun_jy = _chorak_dars_kunlari(jy, chorak, sana)
		sanalar.update(kun_jy.keys())
		# O'tilgan mavzular (ustun ustiga olib boriladi — qaysi darsда ekani ko'rinsin)
		mavzu_map = {}
		for r in frappe.get_all(
			"Dars Bajarilishi",
			filters={"guruh": jy.guruh, "fan": jy.fan, "sana": ["in", list(sanalar)]},
			fields=["sana", "mavzu", "holat"], limit_page_length=0):
			mavzu_map[str(r.sana)] = {"mavzu": r.mavzu, "holat": r.holat}
		# Xronologik tartib: o'tgan kunlar chapda, bugun (tanlangan kun) eng o'ngda —
		# qog'oz jurnal kabi. Frontend ochilganda o'ng chetga surib qo'yadi.
		bugun_s = str(getdate(nowdate()))
		joriy_s = str(getdate(sana))
		for d in sorted(sanalar):
			p = d.split("-")
			ustunlar.append({
				"sana": d,
				"label": f"{p[2]}.{p[1]}" if len(p) == 3 else d,
				"bugun": d == joriy_s,          # tanlangan (joriy ko'rilayotgan) kun
				"haqiqiy_bugun": d == bugun_s,
				"kelajak": d > bugun_s,
				"jadval_yozuvi": kun_jy.get(d) or jadval_yozuvi,
				"mavzu": (mavzu_map.get(d) or {}).get("mavzu"),
				"tahrir": 1 if soz.tuzatish_mumkinmi(d, menejer=bah._menejermi(), s=s) else 0,
			})

		# Chorakda o'tilgan darslar soni (davomat foizi uchun).
		# «Dars Bajarilishi» hali to'ldirilmagan bo'lsa — jurnalda yozuv bor sanalar soni.
		otilgan_darslar = frappe.db.count(
			"Dars Bajarilishi", {"guruh": jy.guruh, "fan": jy.fan, "holat": "O'tildi"}) or 0
		jurnal_kunlari = len({str(r.sana) for r in frappe.get_all(
			"Dars Natijasi", filters={"guruh": jy.guruh, "fan": jy.fan, "chorak": chorak},
			fields=["sana"], limit_page_length=0)})
		otilgan_darslar = max(otilgan_darslar, jurnal_kunlari)

		# Uy vazifa bajarmagani (chorak bo'yicha)
		uv_yoq = {}
		for r in frappe.get_all(
			"Uy Vazifa Natijasi",
			filters={"guruh": jy.guruh, "fan": jy.fan, "chorak": chorak,
			         "student": ["in", sids], "holat": "Bajarmadi"},
			fields=["student"], limit_page_length=0):
			uv_yoq[r.student] = uv_yoq.get(r.student, 0) + 1

		for o in oquvchilar:
			bh = ball_map.get(o["student"], [])
			k = soz.korsatkich(
				bh, darslar=otilgan_darslar, yoqlik=absent_map.get(o["student"], 0),
				kechikish=kech_map.get(o["student"], 0),
				uv_bajarmagan=uv_yoq.get(o["student"], 0), s=s)
			o["chorak_ortacha"] = k["ortacha"]
			o["chorak_ballar"] = bh[-8:]
			o["chorak_yoqlik"] = absent_map.get(o["student"], 0)
			o["chorak_kechikish"] = kech_map.get(o["student"], 0)
			o["trend"] = k["trend"]
			o["rang"] = k["rang"]
			o["davomat_foiz"] = k["davomat_foiz"]
			o["bayroqlar"] = k["bayroqlar"]
			o["uv_bajarmagan"] = uv_yoq.get(o["student"], 0)
			o["kataklar"] = [katak_map.get((o["student"], u["sana"])) for u in ustunlar]

	# O'quv reja (keyingi mavzu + bugungi bajarilish)
	reja = {}
	try:
		h = oreja.dars_detali(jadval_yozuvi, sana)
		reja = {
			"oquv_reja": h.get("oquv_reja"), "oquv_reja_nomi": h.get("oquv_reja_nomi"),
			"mavzular": h.get("mavzular"), "keyingi": h.get("keyingi"),
			"otildi": h.get("otildi"), "jami": h.get("jami"), "bugun": h.get("bugun"),
		}
	except Exception:
		reja = {"oquv_reja": None}

	# Har reja qatori shu guruhда QAYSI KUN(lar)da o'tilgani — ro'yxatda belgilash uchun
	mavzu_sanalar = {}
	if reja.get("oquv_reja"):
		for r in frappe.get_all(
			"Dars Bajarilishi",
			filters={"oquv_reja": reja["oquv_reja"], "guruh": jy.guruh},
			fields=["reja_qatori", "sana", "holat"], order_by="sana", limit_page_length=0):
			if r.reja_qatori:
				mavzu_sanalar.setdefault(r.reja_qatori, []).append(
					{"sana": str(r.sana), "holat": r.holat})
	reja["mavzu_sanalar"] = mavzu_sanalar

	# Uy vazifa (mavjud bo'lsa)
	uv_name = frappe.db.get_value("Uy Vazifa", {"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana)}, "name")
	uy_vazifa = None
	if uv_name:
		uv = frappe.db.get_value(
			"Uy Vazifa", uv_name,
			["name", "vazifa", "izoh", "muddat", "max_ball", "fayl"], as_dict=True)
		uy_vazifa = {
			"name": uv.name, "vazifa": uv.vazifa, "izoh": uv.izoh,
			"muddat": str(uv.muddat) if uv.muddat else None,
			"max_ball": uv.max_ball, "fayl": uv.fayl,
		}

	# Chorakdagi barcha uy vazifalari (o'ng taraf ro'yxati)
	uv_filtr = {"guruh": jy.guruh, "fan": jy.fan}
	if chorak:
		uv_filtr["chorak"] = chorak
	uy_vazifalar = []
	for r in frappe.get_all(
		"Uy Vazifa", filters=uv_filtr,
		fields=["name", "sana", "muddat", "vazifa", "max_ball", "fayl"],
		order_by="sana desc", limit_page_length=0):
		uy_vazifalar.append({
			"name": r.name, "sana": str(r.sana), "muddat": str(r.muddat) if r.muddat else None,
			"vazifa": r.vazifa, "max_ball": r.max_ball, "fayl": r.fayl,
			"bugungi": str(r.sana) == str(getdate(sana)),
		})

	# Bugungi darslar (kokpit ichidagi ‹ oldingi / keyingi › navigatsiya uchun)
	navigatsiya = _bugungi_darslar(jy, sana, jadval_yozuvi)

	# Oldingi dars: nima o'tilgan, kim yo'q edi, qanday uy vazifa berilgan
	oldingi = _oldingi_dars(jy, sana)

	return {
		"dars": {
			"jadval_yozuvi": jadval_yozuvi, "fan": jy.fan, "guruh": jy.guruh,
			"guruh_nomi": jy.guruh_nomi, "oqituvchi_nomi": jy.oqituvchi_nomi,
			"kun": jy.kun, "dars_raqami": jy.dars_raqami,
			"boshlanish": _vaqt_str(jy.boshlanish), "tugash": _vaqt_str(jy.tugash),
			"xona": jy.xona, "sana": str(sana),
		},
		"oquvchilar": oquvchilar,
		"chorak": chorak,
		"reja": reja,
		"uy_vazifa": uy_vazifa,
		"uy_vazifalar": uy_vazifalar,
		"ustunlar": ustunlar,
		"navigatsiya": navigatsiya,
		"oldingi": oldingi,
		"sozlamalar": s,
		"baho_turlari": frappe.get_all(
			"Baho Turi", filters={"faol": 1}, fields=["name", "qisqa", "vazn"],
			order_by="vazn desc", limit_page_length=0),
		"tuzatish_mumkin": soz.tuzatish_mumkinmi(sana, menejer=bah._menejermi(), s=s),
	}


def _chorak_dars_kunlari(jy, chorak: str | None, sana) -> dict:
	"""Shu guruh+fan bo'yicha chorakdagi dars kunlari -> o'sha kundagi `Jadval Yozuvi`.
	Haftalik jadvaldan hisoblanadi (kun -> hafta kuni), chorak boshidan bugungacha."""
	from datetime import timedelta

	if not chorak:
		return {}
	t = frappe.db.get_value("Academic Term", chorak,
	                        ["term_start_date", "term_end_date"], as_dict=True)
	if not t:
		return {}
	boshi, oxiri = getdate(t.term_start_date), getdate(t.term_end_date)
	# Kelajakka chiqmaymiz (lekin tanlangan kun har holda qo'shiladi)
	chek = min(oxiri, max(getdate(nowdate()), getdate(sana)))
	slots = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": jy.versiya, "guruh": jy.guruh, "fan": jy.fan},
		fields=["name", "kun", "dars_raqami"], order_by="dars_raqami", limit_page_length=0)
	wd = {}
	for r in slots:
		try:
			i = KUNLAR.index(r.kun)
		except (ValueError, AttributeError):
			continue
		wd.setdefault(i, r.name)
	if not wd:
		return {}
	natija = {}
	d = boshi
	while d <= chek:
		nom = wd.get(d.weekday())
		if nom:
			natija[str(d)] = nom
		d = d + timedelta(days=1)
	return natija


# ----------------------------------------------------------- navigatsiya / oldingi dars
def _bugungi_darslar(jy, sana, joriy: str) -> dict:
	"""Shu o'qituvchining shu kundagi darslari + joriy darsning oldingi/keyingisi."""
	if not (jy.oqituvchi and jy.kun):
		return {"darslar": [], "oldingi": None, "keyingi": None}
	darslar = []
	for r in frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": jy.versiya, "oqituvchi": jy.oqituvchi, "kun": jy.kun},
		fields=["name", "dars_raqami", "fan", "guruh", "guruh_nomi", "boshlanish", "tugash"],
		order_by="dars_raqami", limit_page_length=0):
		darslar.append({
			"jadval_yozuvi": r.name, "dars_raqami": r.dars_raqami, "fan": r.fan,
			"guruh": r.guruh, "guruh_nomi": r.guruh_nomi,
			"boshlanish": _vaqt_str(r.boshlanish), "tugash": _vaqt_str(r.tugash),
			"joriy": r.name == joriy,
		})
	idx = next((i for i, d in enumerate(darslar) if d["joriy"]), None)
	return {
		"darslar": darslar, "sana": str(sana),
		"oldingi": darslar[idx - 1] if (idx not in (None, 0)) else None,
		"keyingi": darslar[idx + 1] if (idx is not None and idx + 1 < len(darslar)) else None,
	}


def _oldingi_dars(jy, sana) -> dict | None:
	"""Shu guruh+fan bo'yicha oxirgi o'tilgan dars: mavzu, yo'q bo'lganlar, uy vazifa."""
	oldin = frappe.get_all(
		"Dars Bajarilishi",
		filters={"guruh": jy.guruh, "fan": jy.fan, "sana": ["<", getdate(sana)]},
		fields=["name", "sana", "mavzu", "holat", "izoh"],
		order_by="sana desc", limit_page_length=1)
	if not oldin:
		return None
	o = oldin[0]
	yoq = frappe.get_all(
		"Dars Natijasi",
		filters={"guruh": jy.guruh, "fan": jy.fan, "sana": o.sana,
		         "davomat": ["in", list(soz.YOQLIK)]},
		fields=["student_name", "davomat"], limit_page_length=0)
	uv = frappe.db.get_value(
		"Uy Vazifa", {"guruh": jy.guruh, "fan": jy.fan, "sana": o.sana},
		["name", "vazifa", "muddat", "max_ball", "tekshiriladi"], as_dict=True)
	return {
		"sana": str(o.sana), "mavzu": o.mavzu, "holat": o.holat, "izoh": o.izoh,
		"yoq": [{"ism": y.student_name, "holat": y.davomat} for y in yoq],
		"uy_vazifa": ({
			"name": uv.name, "vazifa": uv.vazifa, "max_ball": uv.max_ball,
			"muddat": str(uv.muddat) if uv.muddat else None,
			"tekshiriladi": uv.tekshiriladi,
		} if uv else None),
	}


@frappe.whitelist()
def uy_vazifa_saqla(jadval_yozuvi: str, sana: str, vazifa: str,
                    muddat: str | None = None, max_ball=None,
                    izoh: str | None = None, fayl: str | None = None,
                    tekshiriladi=None) -> dict:
	"""Dars uchun uy vazifasini saqlaydi (upsert). Ruxsat: menejer yoki dars o'qituvchisi."""
	jy = frappe.db.get_value("Jadval Yozuvi", jadval_yozuvi, "oqituvchi")
	bah._ruxsat(jy)  # menejer yoki shu darsning o'qituvchisi
	if not (vazifa or "").strip():
		# Bo'sh vazifa — mavjud bo'lsa o'chiriladi
		mavjud = frappe.db.get_value("Uy Vazifa", {"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana)}, "name")
		if mavjud:
			frappe.delete_doc("Uy Vazifa", mavjud, ignore_permissions=True)
			frappe.db.commit()
		return {"ochirildi": 1}
	chorak = bah._chorak(sana)
	st = soz.olish()
	mavjud = frappe.db.get_value("Uy Vazifa", {"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana)}, "name")
	if tekshiriladi is None:
		tekshiriladi = st.get("uv_tekshirish")
	mb = int(max_ball) if max_ball not in (None, "", 0) else (st.get("uv_default_max_ball") or None)
	qiymat = {
		"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana), "vazifa": vazifa,
		"muddat": getdate(muddat) if muddat else None,
		"max_ball": mb,
		"tekshiriladi": 1 if int(tekshiriladi or 0) else 0,
		"izoh": izoh, "fayl": fayl, "chorak": chorak,
	}
	if mavjud:
		doc = frappe.get_doc("Uy Vazifa", mavjud)
		doc.update(qiymat)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(dict(doctype="Uy Vazifa", **qiymat))
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist()
def guruh_uy_vazifalari(guruh: str, chorak: str | None = None, limit: int = 60) -> list[dict]:
	"""Guruhning uy vazifalari ro'yxati (eng yangisi birinchi)."""
	if not bah._menejermi() and not bah._mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	filtr = {"guruh": guruh}
	if chorak:
		filtr["chorak"] = chorak
	return frappe.get_all(
		"Uy Vazifa", filters=filtr,
		fields=["name", "sana", "muddat", "fan", "vazifa", "max_ball", "fayl"],
		order_by="sana desc", limit_page_length=int(limit))


# --------------------------------------------------------------- uy vazifani tekshirish
@frappe.whitelist()
def uy_vazifa_natijalari(uy_vazifa: str) -> dict:
	"""Bitta uy vazifa bo'yicha o'quvchilar ro'yxati + kim bajardi / ball.
	Sozlamalarda «uy vazifa tekshiriladi» yoqilgan bo'lsa dars kokpitida ishlatiladi."""
	uv = frappe.db.get_value(
		"Uy Vazifa", uy_vazifa,
		["name", "guruh", "fan", "sana", "muddat", "vazifa", "max_ball",
		 "tekshiriladi", "oqituvchi", "chorak"], as_dict=True)
	if not uv:
		frappe.throw(_("Uy vazifa topilmadi."))
	if not bah._menejermi() and not bah._mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)

	oquvchilar = frappe.get_all(
		"Student Group Student",
		filters={"parent": uv.guruh, "parenttype": "Student Group", "active": 1},
		fields=["student", "student_name", "group_roll_number"],
		order_by="group_roll_number, student_name", limit_page_length=0)
	mavjud = {r.student: r for r in frappe.get_all(
		"Uy Vazifa Natijasi", filters={"uy_vazifa": uy_vazifa},
		fields=["name", "student", "holat", "ball", "izoh"], limit_page_length=0)}

	qatorlar = []
	for o in oquvchilar:
		m = mavjud.get(o.student)
		qatorlar.append({
			"student": o.student, "student_name": o.student_name, "roll": o.group_roll_number,
			"holat": m.holat if m else None,
			"ball": m.ball if m else None,
			"izoh": m.izoh if m else None,
			"saqlangan": bool(m),
		})
	return {
		"uy_vazifa": uv.name, "vazifa": uv.vazifa, "sana": str(uv.sana),
		"muddat": str(uv.muddat) if uv.muddat else None,
		"max_ball": uv.max_ball, "tekshiriladi": uv.tekshiriladi,
		"tekshirilgan": sum(1 for q in qatorlar if q["saqlangan"]),
		"jami": len(qatorlar),
		"qatorlar": qatorlar,
	}


@frappe.whitelist()
def uy_vazifa_natija_saqla(uy_vazifa: str, qatorlar) -> dict:
	"""Uy vazifa tekshiruvini saqlash. qatorlar: [{student, holat, ball, izoh}].
	holat bo'sh bo'lsa — yozuv o'chiriladi (tekshirilmagan holatga qaytadi)."""
	if isinstance(qatorlar, str):
		qatorlar = json.loads(qatorlar)
	uv = frappe.db.get_value(
		"Uy Vazifa", uy_vazifa,
		["guruh", "fan", "sana", "chorak", "oqituvchi", "max_ball"], as_dict=True)
	if not uv:
		frappe.throw(_("Uy vazifa topilmadi."))
	bah._ruxsat(uv.oqituvchi)
	n = 0
	for q in qatorlar:
		student = q.get("student")
		if not student:
			continue
		holat = q.get("holat")
		nom = frappe.db.get_value(
			"Uy Vazifa Natijasi", {"uy_vazifa": uy_vazifa, "student": student}, "name")
		if not holat:
			if nom:
				frappe.delete_doc("Uy Vazifa Natijasi", nom, ignore_permissions=True)
			continue
		ball = q.get("ball")
		ball = int(ball) if ball not in (None, "") else None
		if ball is not None and uv.max_ball and ball > uv.max_ball:
			frappe.throw(_("Ball {0} dan katta bo'lishi mumkin emas.").format(uv.max_ball))
		qiymat = {
			"uy_vazifa": uy_vazifa, "student": student, "holat": holat,
			"ball": 0 if holat == "Bajarmadi" else ball,
			"izoh": q.get("izoh"), "guruh": uv.guruh, "fan": uv.fan,
			"sana": uv.sana, "chorak": uv.chorak, "oqituvchi": uv.oqituvchi,
			"max_ball": uv.max_ball,
		}
		if nom:
			doc = frappe.get_doc("Uy Vazifa Natijasi", nom)
			doc.update(qiymat)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(dict(doctype="Uy Vazifa Natijasi", **qiymat)).insert(ignore_permissions=True)
		n += 1
	frappe.db.commit()
	return {"saqlandi": n}
