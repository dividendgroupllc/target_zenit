# Copyright (c) 2026, Target Zenit
# "Mening jadvalim" — o'qituvchi uchun: bugungi darslar + haftalik jadval.
# Har darsdan davomat olishga o'tish mumkin (Course Schedule orqali).
from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, getdate, nowdate

from target_zenit import oquv_reja as oreja
from target_zenit.dars_jadvali import baholash as bah
from target_zenit.dars_jadvali import sozlamalar as soz

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
		"oqituvchi_nomi": frappe.db.get_value("Instructor", oqituvchi, "instructor_name") if oqituvchi else None,
		"versiya": versiya,
		"menejer": menejer,
		"bugun_kuni": KUNLAR[getdate(nowdate()).weekday()],
		"darslar": [],
		"qongiroq": {},
	}
	if menejer:
		natija["oqituvchilar"] = frappe.get_all(
			"Instructor", fields=["name", "instructor_name"], order_by="instructor_name", limit_page_length=0
		)
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
				"asl_oqituvchi_nomi": frappe.db.get_value("Instructor", o.asl_oqituvchi, "instructor_name"),
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
			"yangi_oqituvchi_nomi": frappe.db.get_value("Instructor", o.yangi_oqituvchi, "instructor_name") if o.yangi_oqituvchi else None,
			"sabab": o.sabab,
		} if o else None)
		# O'quv reja holati (faol reja + keyingi mavzu + o'tilganmi)
		try:
			h = oreja.dars_holati(d["fan"], d["guruh"], sana=d["sana"],
			                      jadval_yozuvi=d["name"], guruh_nomi=d.get("guruh_nomi"))
			d["oquv_reja"] = h.get("oquv_reja")
			d["keyingi"] = h.get("keyingi")
			d["otildi"] = h.get("otildi")
			d["jami"] = h.get("jami")
			d["bugun"] = h.get("bugun")
		except Exception:
			d["oquv_reja"] = None
	natija["haftalik_soat"] = len(natija["darslar"])
	natija["bugun_sana"] = str(bugun)
	natija["hafta"] = siljish
	natija["hafta_boshi"] = str(hafta_boshi)
	natija["hafta_oxiri"] = str(hafta_oxiri)
	natija["shu_hafta"] = siljish == 0
	return natija


@frappe.whitelist()
def jurnal_oquvchilari(jadval_yozuvi: str, sana: str | None = None):
	"""Baho/davomat jurnali uchun dars o'quvchilari (baholash modulida)."""
	return bah.dars_oquvchilari(jadval_yozuvi, sana)


@frappe.whitelist()
def jurnal_saqla(jadval_yozuvi: str, sana: str, qatorlar):
	"""Baho/davomat saqlash (baholash modulida)."""
	return bah.natija_saqla(jadval_yozuvi, sana, qatorlar)


@frappe.whitelist()
def dars_detali(jadval_yozuvi: str, sana: str | None = None):
	"""Dars ustiga bosilganda to'liq ma'lumot (oquv_reja modulida)."""
	return oreja.dars_detali(jadval_yozuvi=jadval_yozuvi, sana=sana)


@frappe.whitelist()
def dars_otdim(jadval_yozuvi: str, sana: str | None = None, reja_qatori: str | None = None,
               holat: str = "O'tildi", izoh: str | None = None):
	"""«Shu darsni o'tdim» — o'quv reja bajarilishini belgilaydi (oquv_reja modulida)."""
	return oreja.dars_otdim(jadval_yozuvi=jadval_yozuvi, sana=sana,
	                        reja_qatori=reja_qatori, holat=holat, izoh=izoh)


@frappe.whitelist()
def davomat_ochish(jadval_yozuvi: str, sana: str | None = None):
	"""Shu dars uchun bugungi Course Schedule'ni topadi yoki yaratadi — davomat uchun."""
	sana = sana or nowdate()
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi)

	mavjud = frappe.db.get_value(
		"Course Schedule",
		{"student_group": jy.guruh, "schedule_date": sana, "from_time": jy.boshlanish},
		"name",
	)
	if mavjud:
		return {"course_schedule": mavjud, "yangi": 0}

	cs = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"student_group": jy.guruh,
			"course": jy.fan,
			"instructor": jy.oqituvchi,
			"room": jy.xona,
			"schedule_date": sana,
			"from_time": jy.boshlanish,
			"to_time": jy.tugash,
			"title": f"{jy.fan} — {jy.guruh_nomi or jy.guruh}",
		}
	)
	cs.flags.ignore_validate = True
	cs.insert(ignore_permissions=True)
	return {"course_schedule": cs.name, "yangi": 1}


# ======================================================================== KUN PANELI
# «Qoldirilgan ishlarim» (Kundalik/eMaktab uslubi) + «Diqqat talab qiladi» (xavf ro'yxati).
# O'qituvchi ekranga kirishi bilan: qaysi darsга mavzu/baho/uy vazifa qo'yilmagani,
# qaysi uy vazifa tekshirilmagani va qaysi o'quvchi orqada qolgani ko'rinadi.

TUR_OGIRLIK = {"jurnal": 0, "uv_tekshirish": 1, "mavzu": 2, "uy_vazifa": 3}


@frappe.whitelist()
def kun_paneli(oqituvchi: str | None = None, kun_soni: int = 14) -> dict:
	"""O'qituvchining qoldirilgan ishlari + diqqat talab qiladigan o'quvchilari."""
	from collections import defaultdict

	menejer = bool(
		{"system manager", "zavuch", "academics user", "education manager"}
		& {r.lower() for r in frappe.get_roles()})
	if oqituvchi and not menejer:
		frappe.throw("Ruxsat yo'q.", frappe.PermissionError)
	oqituvchi = oqituvchi or _mening_instructorim()
	kun_soni = int(kun_soni or 14)
	natija = {"oqituvchi": oqituvchi, "qoldirilgan": [], "diqqat": [], "kun_soni": kun_soni}
	if not oqituvchi:
		return natija

	st = soz.olish()
	versiya = frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")
	if not versiya:
		return natija

	bugun = getdate(nowdate())
	boshi = add_days(bugun, -kun_soni)
	hozir = frappe.utils.now_datetime().time()

	darslar = frappe.get_all(
		"Jadval Yozuvi", filters={"versiya": versiya, "oqituvchi": oqituvchi},
		fields=["name", "kun", "kun_raqami", "dars_raqami", "fan", "guruh",
		        "guruh_nomi", "boshlanish", "tugash"], limit_page_length=0)
	if not darslar:
		return natija

	# Nomzod (dars, sana) juftliklari — o'tgan kunlar + bugun (darsi tugaganlari)
	nomzod = []
	for d in darslar:
		kr = (d.get("kun_raqami") or 0) - 1  # 0 = Dushanba
		if kr < 0:
			continue
		sana = boshi
		while sana <= bugun:
			if sana.weekday() == kr:
				if sana < bugun or (d.get("tugash") and _vaqt_str(d["tugash"]) <= hozir.strftime("%H:%M")):
					nomzod.append((d, sana))
			sana = add_days(sana, 1)
	if not nomzod:
		return natija

	jy_nomlar = list({d["name"] for d, _ in nomzod})

	# Bekor qilingan / boshqaga berilgan darslarni chiqarib tashlash
	ozg = {}
	for o in frappe.get_all(
		"Jadval Ozgarishi",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": ["between", [boshi, bugun]]},
		fields=["jadval_yozuvi", "sana", "tur", "yangi_oqituvchi"], limit_page_length=0):
		ozg[(o.jadval_yozuvi, str(o.sana))] = o

	# Bajarilgan ishlar — bir martalik so'rovlar
	bajarilgan = {(r.jadval_yozuvi, str(r.sana)) for r in frappe.get_all(
		"Dars Bajarilishi",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": ["between", [boshi, bugun]]},
		fields=["jadval_yozuvi", "sana"], limit_page_length=0)}

	jurnal = defaultdict(int)
	for r in frappe.get_all(
		"Dars Natijasi",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": ["between", [boshi, bugun]]},
		fields=["jadval_yozuvi", "sana"], limit_page_length=0):
		jurnal[(r.jadval_yozuvi, str(r.sana))] += 1

	uv_map = {}
	for r in frappe.get_all(
		"Uy Vazifa",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": ["between", [boshi, bugun]]},
		fields=["name", "jadval_yozuvi", "sana", "muddat", "tekshiriladi", "vazifa"],
		limit_page_length=0):
		uv_map[(r.jadval_yozuvi, str(r.sana))] = r

	uv_tekshirilgan = defaultdict(int)
	if uv_map:
		for r in frappe.get_all(
			"Uy Vazifa Natijasi",
			filters={"uy_vazifa": ["in", [u.name for u in uv_map.values()]]},
			fields=["uy_vazifa"], limit_page_length=0):
			uv_tekshirilgan[r.uy_vazifa] += 1

	qoldirilgan = []
	for d, sana in nomzod:
		kalit = (d["name"], str(sana))
		o = ozg.get(kalit)
		if o and (o.tur == "Bekor" or (o.yangi_oqituvchi and o.yangi_oqituvchi != oqituvchi)):
			continue
		asos = {
			"jadval_yozuvi": d["name"], "sana": str(sana), "kun": d["kun"],
			"dars_raqami": d["dars_raqami"], "fan": d["fan"],
			"guruh": d["guruh"], "guruh_nomi": d["guruh_nomi"],
		}
		uv = uv_map.get(kalit)
		# Dars umuman yuritilmagan bo'lsa — uchta qator o'rniga bitta (shovqin kamayadi)
		if kalit not in jurnal and kalit not in bajarilgan and not uv:
			qoldirilgan.append(dict(asos, tur="jurnal",
			                        matn="dars yuritilmagan: jurnal, mavzu va uy vazifa yo'q"))
			continue
		if kalit not in jurnal:
			qoldirilgan.append(dict(asos, tur="jurnal", matn="jurnal to'ldirilmagan (baho/davomat yo'q)"))
		if kalit not in bajarilgan:
			qoldirilgan.append(dict(asos, tur="mavzu", matn="o'tilgan mavzu belgilanmagan"))
		if not uv:
			qoldirilgan.append(dict(asos, tur="uy_vazifa", matn="uy vazifa berilmagan"))
		elif st.get("uv_tekshirish") and uv.tekshiriladi and not uv_tekshirilgan.get(uv.name):
			muddat = getdate(uv.muddat) if uv.muddat else getdate(sana)
			if muddat <= bugun:
				qoldirilgan.append(dict(
					asos, tur="uv_tekshirish", uy_vazifa=uv.name,
					matn=f"uy vazifa tekshirilmagan: {(uv.vazifa or '')[:60]}"))

	qoldirilgan.sort(key=lambda x: (TUR_OGIRLIK.get(x["tur"], 9), x["sana"]))
	natija["qoldirilgan"] = qoldirilgan[:40]
	natija["qoldirilgan_jami"] = len(qoldirilgan)

	# ---------------------------------------------------------------- diqqat ro'yxati
	chorak = bah._chorak(bugun)
	if chorak:
		guruh_fan = {(d["guruh"], d["fan"]) for d in darslar}
		ball_map, yoq_map, kech_map, ism_map, gf_map = {}, {}, {}, {}, {}
		for r in frappe.get_all(
			"Dars Natijasi",
			filters={"oqituvchi": oqituvchi, "chorak": chorak},
			fields=["student", "student_name", "guruh", "fan", "baho", "davomat", "sana"],
			order_by="sana", limit_page_length=0):
			if (r.guruh, r.fan) not in guruh_fan:
				continue
			k = (r.student, r.guruh, r.fan)
			ism_map[k] = r.student_name
			gf_map[k] = (r.guruh, r.fan)
			if r.baho:
				ball_map.setdefault(k, []).append(r.baho)
			if r.davomat in soz.YOQLIK:
				yoq_map[k] = yoq_map.get(k, 0) + 1
			elif r.davomat == "Kechikdi":
				kech_map[k] = kech_map.get(k, 0) + 1

		uv_yoq = {}
		for r in frappe.get_all(
			"Uy Vazifa Natijasi",
			filters={"oqituvchi": oqituvchi, "chorak": chorak, "holat": "Bajarmadi"},
			fields=["student", "guruh", "fan"], limit_page_length=0):
			uv_yoq[(r.student, r.guruh, r.fan)] = uv_yoq.get((r.student, r.guruh, r.fan), 0) + 1

		# Dars soni: belgilangan bajarilishlar yoki jurnalda yozuv bor sanalar (qaysi ko'p bo'lsa)
		jurnal_kun = {}
		for r in frappe.get_all(
			"Dars Natijasi", filters={"oqituvchi": oqituvchi, "chorak": chorak},
			fields=["guruh", "fan", "sana"], limit_page_length=0):
			jurnal_kun.setdefault((r.guruh, r.fan), set()).add(str(r.sana))
		darslar_soni = {}
		for (g, f) in guruh_fan:
			darslar_soni[(g, f)] = max(
				frappe.db.count("Dars Bajarilishi", {"guruh": g, "fan": f, "holat": "O'tildi"}) or 0,
				len(jurnal_kun.get((g, f), ())))

		diqqat = []
		for k in set(list(ball_map) + list(yoq_map) + list(kech_map) + list(uv_yoq)):
			student, guruh, fan = k
			g_f = (guruh, fan)
			kk = soz.korsatkich(
				ball_map.get(k, []), darslar=darslar_soni.get(g_f, 0),
				yoqlik=yoq_map.get(k, 0), kechikish=kech_map.get(k, 0),
				uv_bajarmagan=uv_yoq.get(k, 0), s=st)
			if kk["rang"] == "yashil" and not kk["bayroqlar"]:
				continue
			diqqat.append({
				"student": student,
				"student_name": ism_map.get(k) or frappe.db.get_value("Student", student, "student_name"),
				"guruh": guruh, "fan": fan,
				"guruh_nomi": next((d["guruh_nomi"] for d in darslar if d["guruh"] == guruh), guruh),
				"ortacha": kk["ortacha"], "trend": kk["trend"], "rang": kk["rang"],
				"davomat_foiz": kk["davomat_foiz"], "yoqlik": yoq_map.get(k, 0),
				"kechikish": kech_map.get(k, 0), "uv_bajarmagan": uv_yoq.get(k, 0),
				"bayroqlar": kk["bayroqlar"],
			})
		diqqat.sort(key=lambda x: (0 if x["rang"] == "qizil" else 1, -(len(x["bayroqlar"]))))
		natija["diqqat"] = diqqat[:12]
		natija["diqqat_jami"] = len(diqqat)
		natija["chorak"] = chorak
	return natija


# ==================================================================== BUGUN BATAFSIL
# «Bugun nima qildim / nima qilishim kerak» — bir kunlik to'liq qaydnoma.
# Har dars uchun: guruh, mavzu (reja bo'yicha va amalda o'tilgani), yo'qlama, nechta baho
# qo'yilgani, o'rtacha baho, uy vazifa va tekshiruvi, zavuch yuklagan qo'shimcha darslar.

def _dars_checklist(d: dict) -> dict:
	"""Darsning bajarilish darajasi: nima qilingan, nima qolgan."""
	qadamlar = [
		("yoqlama", "Yo'qlama", bool(d["jurnal"]["belgilangan"]) or bool(d["jurnal"]["baholangan"])),
		("baho", "Baho", bool(d["jurnal"]["baholangan"])),
		("mavzu", "Mavzu", bool(d["bajarilish"])),
		("uy_vazifa", "Uy vazifa", bool(d["uy_vazifa"])),
	]
	if d["uy_vazifa"] and d["uy_vazifa"].get("tekshiriladi"):
		qadamlar.append(("uv_tekshirish", "Tekshiruv",
		                 bool(d["uy_vazifa"].get("tekshirilgan"))))
	bajarilgan = [q for q in qadamlar if q[2]]
	return {
		"qadamlar": [{"kod": k, "nom": n, "ok": bool(ok)} for k, n, ok in qadamlar],
		"bajarilgan": len(bajarilgan), "jami": len(qadamlar),
		"qolgan": [n for k, n, ok in qadamlar if not ok],
	}


@frappe.whitelist()
def bugun_batafsil(oqituvchi: str | None = None, sana: str | None = None) -> dict:
	"""Bitta kun uchun o'qituvchining to'liq kun qaydnomasi."""
	menejer = bool(
		{"system manager", "zavuch", "academics user", "education manager"}
		& {r.lower() for r in frappe.get_roles()})
	if oqituvchi and not menejer:
		frappe.throw("Ruxsat yo'q.", frappe.PermissionError)
	oqituvchi = oqituvchi or _mening_instructorim()
	sana = getdate(sana or nowdate())
	kun = KUNLAR[sana.weekday()]
	st = soz.olish()

	natija = {
		"oqituvchi": oqituvchi, "sana": str(sana), "kun": kun,
		"darslar": [], "qoshimcha": [], "yakun": {}, "sozlamalar": st,
	}
	if not oqituvchi:
		return natija
	versiya = frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")
	if not versiya:
		return natija

	# 1) O'zining shu kundagi darslari
	oz_darslar = frappe.get_all(
		"Jadval Yozuvi",
		filters={"versiya": versiya, "oqituvchi": oqituvchi, "kun": kun},
		fields=["name", "dars_raqami", "fan", "guruh", "guruh_nomi", "sinflar",
		        "xona", "boshlanish", "tugash", "oqituvchi"],
		order_by="dars_raqami", limit_page_length=0)

	# 2) Shu sanadagi jadval o'zgarishlari (bekor / o'rinbosarlik)
	ozg_oz, qoshimcha_jy = {}, []
	for o in frappe.get_all(
		"Jadval Ozgarishi", filters={"sana": sana},
		fields=["name", "jadval_yozuvi", "tur", "asl_oqituvchi", "yangi_oqituvchi",
		        "sabab", "kun", "dars_raqami", "guruh_nomi", "fan"],
		limit_page_length=0):
		if o.jadval_yozuvi and frappe.db.get_value("Jadval Yozuvi", o.jadval_yozuvi, "oqituvchi") == oqituvchi:
			ozg_oz[o.jadval_yozuvi] = o
		# Zavuch yuklagan qo'shimcha yuklama — men o'rinbosar bo'lgan darslar
		if o.yangi_oqituvchi == oqituvchi:
			qoshimcha_jy.append(o)

	# Qo'shimcha darslarni ham ro'yxatga qo'shamiz (belgisi bilan)
	hammasi = [dict(d, qoshimcha=0, ozgarish=None) for d in oz_darslar]
	for o in qoshimcha_jy:
		jy = frappe.db.get_value(
			"Jadval Yozuvi", o.jadval_yozuvi,
			["name", "dars_raqami", "fan", "guruh", "guruh_nomi", "sinflar", "xona",
			 "boshlanish", "tugash", "oqituvchi"], as_dict=True)
		if not jy:
			continue
		hammasi.append(dict(jy, qoshimcha=1, ozgarish={
			"tur": o.tur, "sabab": o.sabab,
			"asl_oqituvchi_nomi": frappe.db.get_value("Instructor", o.asl_oqituvchi, "instructor_name"),
		}))
	for d in hammasi:
		if not d.get("qoshimcha"):
			o = ozg_oz.get(d["name"])
			d["ozgarish"] = ({
				"tur": o.tur, "sabab": o.sabab,
				"yangi_oqituvchi_nomi": frappe.db.get_value("Instructor", o.yangi_oqituvchi, "instructor_name") if o.yangi_oqituvchi else None,
			} if o else None)
	hammasi.sort(key=lambda d: (d.get("dars_raqami") or 0))
	if not hammasi:
		natija["yakun"] = {"jami": 0}
		return natija

	jy_nomlar = [d["name"] for d in hammasi]

	# 3) Bir martalik so'rovlar: bajarilish, jurnal, uy vazifa, a'zolar
	bajar = {}
	for r in frappe.get_all(
		"Dars Bajarilishi",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": sana},
		fields=["name", "jadval_yozuvi", "mavzu", "holat", "izoh", "tartib", "modified"],
		limit_page_length=0):
		bajar[r.jadval_yozuvi] = r

	jurnal = {}
	for r in frappe.get_all(
		"Dars Natijasi",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": sana},
		fields=["jadval_yozuvi", "student", "baho", "davomat", "modified"],
		limit_page_length=0):
		j = jurnal.setdefault(r.jadval_yozuvi, {
			"baholar": [], "yoq": 0, "kechikdi": 0, "belgilangan": 0, "oxirgi": None})
		j["belgilangan"] += 1
		if r.baho:
			j["baholar"].append(r.baho)
		if r.davomat in soz.YOQLIK:
			j["yoq"] += 1
		elif r.davomat == "Kechikdi":
			j["kechikdi"] += 1
		if not j["oxirgi"] or str(r.modified) > str(j["oxirgi"]):
			j["oxirgi"] = str(r.modified)

	uvlar = {}
	for r in frappe.get_all(
		"Uy Vazifa",
		filters={"jadval_yozuvi": ["in", jy_nomlar], "sana": sana},
		fields=["name", "jadval_yozuvi", "vazifa", "muddat", "max_ball", "tekshiriladi", "fayl"],
		limit_page_length=0):
		uvlar[r.jadval_yozuvi] = r
	uv_tek = {}
	if uvlar:
		for r in frappe.get_all(
			"Uy Vazifa Natijasi",
			filters={"uy_vazifa": ["in", [u.name for u in uvlar.values()]]},
			fields=["uy_vazifa", "holat"], limit_page_length=0):
			t = uv_tek.setdefault(r.uy_vazifa, {"jami": 0, "bajardi": 0, "bajarmadi": 0})
			t["jami"] += 1
			if r.holat == "Bajardi":
				t["bajardi"] += 1
			elif r.holat == "Bajarmadi":
				t["bajarmadi"] += 1

	azolar = {}
	for g in {d["guruh"] for d in hammasi if d.get("guruh")}:
		azolar[g] = frappe.db.count(
			"Student Group Student", {"parent": g, "parenttype": "Student Group", "active": 1})

	# 4) Har dars uchun to'liq karta
	hozir = frappe.utils.now_datetime()
	bugunmi = sana == getdate(nowdate())
	for d in hammasi:
		bosh, tug = _vaqt_str(d.get("boshlanish")), _vaqt_str(d.get("tugash"))
		holat_vaqt = "kelajak"
		if not bugunmi:
			holat_vaqt = "o'tgan" if sana < getdate(nowdate()) else "kelajak"
		else:
			hhmm = hozir.strftime("%H:%M")
			if tug and hhmm > tug:
				holat_vaqt = "o'tgan"
			elif bosh and hhmm >= bosh:
				holat_vaqt = "hozir"

		j = jurnal.get(d["name"]) or {"baholar": [], "yoq": 0, "kechikdi": 0,
		                              "belgilangan": 0, "oxirgi": None}
		bh = j["baholar"]
		b = bajar.get(d["name"])
		uv = uvlar.get(d["name"])
		t = uv_tek.get(uv.name) if uv else None

		# O'quv reja holati (reja bo'yicha nima o'tilishi kerak)
		reja = {}
		try:
			h = oreja.dars_holati(d["fan"], d["guruh"], sana=str(sana),
			                      jadval_yozuvi=d["name"], guruh_nomi=d.get("guruh_nomi"))
			reja = {
				"oquv_reja": h.get("oquv_reja"), "oquv_reja_nomi": h.get("oquv_reja_nomi"),
				"keyingi": h.get("keyingi"), "otildi": h.get("otildi"), "jami": h.get("jami"),
			}
		except Exception:
			reja = {"oquv_reja": None}

		karta = {
			"jadval_yozuvi": d["name"], "dars_raqami": d.get("dars_raqami"),
			"fan": d["fan"], "guruh": d.get("guruh"),
			"guruh_nomi": d.get("guruh_nomi") or d.get("sinflar") or d.get("guruh"),
			"xona": d.get("xona"), "boshlanish": bosh, "tugash": tug,
			"holat_vaqt": holat_vaqt,
			"qoshimcha": d.get("qoshimcha") or 0,
			"ozgarish": d.get("ozgarish"),
			"oquvchi_soni": azolar.get(d.get("guruh"), 0),
			"reja": reja,
			"bajarilish": ({
				"mavzu": b.mavzu, "holat": b.holat, "izoh": b.izoh, "tartib": b.tartib,
				"vaqt": str(b.modified)[11:16] if b.modified else None,
			} if b else None),
			"jurnal": {
				"belgilangan": j["belgilangan"], "baholangan": len(bh),
				"ortacha": round(sum(bh) / len(bh), 1) if bh else None,
				"eng_past": min(bh) if bh else None, "eng_yuqori": max(bh) if bh else None,
				"yoq": j["yoq"], "kechikdi": j["kechikdi"],
				"keldi": max(0, azolar.get(d.get("guruh"), 0) - j["yoq"]),
				"oxirgi_vaqt": (j["oxirgi"] or "")[11:16] or None,
			},
			"uy_vazifa": ({
				"name": uv.name, "vazifa": uv.vazifa, "max_ball": uv.max_ball,
				"muddat": str(uv.muddat) if uv.muddat else None,
				"tekshiriladi": uv.tekshiriladi, "fayl": uv.fayl,
				"tekshirilgan": (t or {}).get("jami", 0),
				"bajardi": (t or {}).get("bajardi", 0),
				"bajarmadi": (t or {}).get("bajarmadi", 0),
			} if uv else None),
		}
		karta["checklist"] = _dars_checklist(karta)
		if karta["ozgarish"] and karta["ozgarish"].get("tur") == "Bekor":
			karta["checklist"] = {"qadamlar": [], "bajarilgan": 0, "jami": 0, "qolgan": []}
		if karta["qoshimcha"]:
			natija["qoshimcha"].append(karta)
		natija["darslar"].append(karta)

	# 5) Kun yakuni
	ishlagan = [d for d in natija["darslar"]
	            if not (d["ozgarish"] and d["ozgarish"].get("tur") == "Bekor")]
	hamma_baho = sum(d["jurnal"]["baholangan"] for d in ishlagan)
	ballar = [d["jurnal"]["ortacha"] for d in ishlagan if d["jurnal"]["ortacha"] is not None]
	natija["yakun"] = {
		"jami": len(natija["darslar"]),
		"bekor": len(natija["darslar"]) - len(ishlagan),
		"qoshimcha": len(natija["qoshimcha"]),
		"otilgan": sum(1 for d in ishlagan if d["bajarilish"]),
		"otilmagan": sum(1 for d in ishlagan if not d["bajarilish"] and d["holat_vaqt"] == "o'tgan"),
		"baho_soni": hamma_baho,
		"ortacha": round(sum(ballar) / len(ballar), 1) if ballar else None,
		"yoq": sum(d["jurnal"]["yoq"] for d in ishlagan),
		"kechikdi": sum(d["jurnal"]["kechikdi"] for d in ishlagan),
		"uy_vazifa": sum(1 for d in ishlagan if d["uy_vazifa"]),
		"uv_tekshirilmagan": sum(1 for d in ishlagan if d["uy_vazifa"]
		                         and d["uy_vazifa"]["tekshiriladi"]
		                         and not d["uy_vazifa"]["tekshirilgan"]),
		"tugallangan": sum(1 for d in ishlagan
		                   if d["checklist"]["jami"] and d["checklist"]["bajarilgan"] == d["checklist"]["jami"]),
		"oquvchi_soni": sum(d["oquvchi_soni"] for d in ishlagan),
	}
	return natija
