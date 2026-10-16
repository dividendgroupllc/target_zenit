# Copyright (c) 2026, Target Zenit
# Qarzdorlik paneli — savdo menejerlari ish stoli:
# qarzdorlar navbati, o'quvchi kartasi (oylar/to'lovlar/timeline),
# "Qo'ng'iroq natijasi" modali (AY + PTP + QI bitta amalda).
from __future__ import annotations

import json

import frappe
from frappe.utils import cint, flt, getdate, nowdate

ALLOWED_ROLES = [
	"System Manager", "Sales Manager", "Sales User", "Sotuv meneger",
	"investor", "Xojakbar_Operator",
	"Nigora_Moliya",
]
YOPIQ = ("Yopildi - To'landi", "Yopildi - Boshqa")


def _guard():
	allowed = {r.lower() for r in ALLOWED_ROLES}
	if not (allowed & {r.lower() for r in frappe.get_roles()}):
		frappe.throw("Ruxsat yo'q. Qarzdorlik paneli uchun sotuv roli kerak.", frappe.PermissionError)


# Mas'ul bo'la oladigan YAGONA rol — sotuv menejeri. Qarz ishi faqat shu
# roldagi foydalanuvchilarga biriktiriladi.
SOTUV_ROL = "Sotuv meneger"


def sotuv_menejerlar() -> list[dict]:
	"""Faol (enabled) "Sotuv meneger" rolli foydalanuvchilar."""
	nomlar = frappe.get_all(
		"Has Role", filters={"role": SOTUV_ROL, "parenttype": "User"}, pluck="parent"
	)
	if not nomlar:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", nomlar], "enabled": 1},
		fields=["name", "full_name"],
		order_by="full_name",
	)


def _sotuv_menejermi(user: str) -> bool:
	return bool(user) and frappe.db.exists(
		"Has Role", {"role": SOTUV_ROL, "parenttype": "User", "parent": user}
	) and cint(frappe.db.get_value("User", user, "enabled"))


# ------------------------------------------------------------ telefoniya
# Qo'ng'iroqlar qarzdorlik kartasiga RAQAM bo'yicha bog'lanadi: `Telefon
# Qongirogi.normal_telefon` ("998XXXXXXXXX") bilan o'quvchining to'lovchi /
# ota-ona / o'quvchi raqamlari solishtiriladi. Student'dagi `normal_telefon`
# maydoni bazada to'ldirilmagan, shuning uchun matcher'ning avtomatik
# bog'lanishiga tayanib bo'lmaydi.
TEL_DT = "Telefon Qongirogi"


def _normal(raw):
	from target_zenit.telefoniya.utils import normalize_phone

	return normalize_phone(raw)


def _tel_hammasini_koradi() -> bool:
	"""Rahbar (va Telefoniya Agent) hamma qo'ng'iroqni eshitadi, menejer —
	faqat o'zinikini. Doctype'ning o'z qoidasi bilan bir xil bo'lishi uchun
	shu yerda ham o'sha funksiya ishlatiladi."""
	from target_zenit.target_zenit.doctype.telefon_qongirogi.telefon_qongirogi import (
		_hammasini_korishi_mumkin,
	)

	return _hammasini_korishi_mumkin(frappe.session.user)


def _case_raqamlar(student: str, payer_phone=None, payer_name=None) -> dict:
	"""Shu o'quvchiga tegishli normal raqamlar: {raqam: kimning raqami}.

	To'lovchi, ota-onalar (Guardian) va o'quvchining o'z raqami. Bitta raqam
	aka-ukalarda umumiy bo'lishi mumkin — qo'ng'iroq ikkisining kartasida ham
	ko'rinadi, bu to'g'ri: qo'ng'iroq to'lovchi bilan bo'lgan."""
	out = {}

	def qosh(raw, kim):
		n = _normal(raw)
		if n and n not in out:
			out[n] = kim

	qosh(payer_phone, payer_name or "To'lovchi")
	st = frappe.db.get_value(
		"Student",
		student,
		["student_name", "student_mobile_number", "custom_payer_phone", "custom_payer_name"],
		as_dict=True,
	) or frappe._dict()
	qosh(st.custom_payer_phone, st.custom_payer_name or "To'lovchi")
	for g in frappe.db.sql(
		"""SELECT COALESCE(g.guardian_name, sg.guardian_name) nm, sg.relation, g.mobile_number tel
		   FROM `tabStudent Guardian` sg
		   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parent = %s AND sg.parenttype = 'Student'
		   ORDER BY sg.idx""",
		(student,),
		as_dict=True,
	):
		qosh(g.tel, f"{g.nm or 'Ota-ona'}{f' ({g.relation})' if g.relation else ''}")
	qosh(st.student_mobile_number, (st.student_name or "O'quvchi") + " (o'quvchi)")
	return out


def _qongiroqlar(student: str, payer_phone=None, payer_name=None, limit: int = 60) -> list[dict]:
	"""O'quvchi/to'lovchi bilan bo'lgan qo'ng'iroqlar — yangisi tepada.

	Ruxsat: rahbar hammasini, menejer faqat o'zi qilgan qo'ng'iroqlarni ko'radi
	(`Telefon Qongirogi` doctype qoidasi bilan bir xil)."""
	raqamlar = _case_raqamlar(student, payer_phone, payer_name)
	if not raqamlar and not student:
		return []

	filters = {} if _tel_hammasini_koradi() else {"foydalanuvchi": frappe.session.user}
	or_filters = [["normal_telefon", "in", list(raqamlar)]] if raqamlar else []
	or_filters.append(["student", "=", student])
	rows = frappe.get_all(
		TEL_DT,
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "boshlandi", "yonalish", "tugash_sababi", "kim_tugatdi",
			"suhbat_vaqti", "kutish_vaqti", "yozuv_bor", "yozuv_ochirildi",
			"izoh", "kontakt_ism", "aloqador_ism", "maqsad", "manba",
			"xodim", "foydalanuvchi", "normal_telefon", "tashqi_raqam",
		],
		order_by="boshlandi desc",
		limit_page_length=limit,
	)

	# Menejer ismi: User.full_name, bo'lmasa Employee nomi
	userlar = {u for r in rows if (u := r.foydalanuvchi)}
	xodimlar = {x for r in rows if (x := r.xodim)}
	u_map = {
		u.name: u.full_name or u.name
		for u in (
			frappe.get_all("User", filters={"name": ["in", list(userlar)]},
			               fields=["name", "full_name"]) if userlar else []
		)
	}
	x_map = {
		e.name: e.employee_name
		for e in (
			frappe.get_all("Employee", filters={"name": ["in", list(xodimlar)]},
			               fields=["name", "employee_name"]) if xodimlar else []
		)
	}
	for r in rows:
		r["menejer"] = u_map.get(r.foydalanuvchi) or x_map.get(r.xodim) or "—"
		r["kim"] = raqamlar.get(r.normal_telefon) or r.kontakt_ism or r.aloqador_ism or ""
		r["audio"] = 1 if (r.yozuv_bor and not r.yozuv_ochirildi) else 0
	return rows


def _student_live(studentlar) -> dict:
	"""student_id -> jonli ma'lumot: ism, sinf, to'lovchi, faollik.

	Panel ismni HECH QACHON nusxadan o'qimaydi. `Qarz Ishi.student_name` va
	`sinf` — fetch_from suratlari: o'quvchining ismi tuzatilsa (masalan
	"Rustamov" -> "Rustamjonov") nusxa eskicha qolib ketadi va ro'yxat bilan
	karta har xil ism ko'rsatardi. Shuning uchun har safar Student hujjatidan
	student_id bo'yicha o'qiymiz — ism o'zgargan zahoti panelda ham o'zgaradi.

	To'lovchi ham shu yerda: Student.payer -> ota-ona (Guardian) -> o'quvchining
	o'zi zanjiri (`engine._payer_info` bilan bir xil mantiq, lekin hamma
	o'quvchi uchun ikkita so'rovda)."""
	studentlar = [x for x in {s for s in studentlar if s}]
	if not studentlar:
		return {}

	out = {}
	for st in frappe.get_all(
		"Student",
		filters={"name": ["in", studentlar]},
		fields=[
			"name", "student_name", "custom_sinf_guruh", "enabled", "date_of_leaving",
			"custom_payer_name", "custom_payer_phone", "student_mobile_number",
		],
	):
		out[st.name] = frappe._dict(
			student_name=st.student_name,
			sinf=st.custom_sinf_guruh,
			enabled=st.enabled,
			date_of_leaving=st.date_of_leaving,
			payer_name=st.custom_payer_name,
			payer_phone=st.custom_payer_phone,
			_mobil=st.student_mobile_number,
		)

	# Ota-ona raqami — faqat to'lovchi telefoni bo'sh o'quvchilarga kerak
	kerak = [s for s, v in out.items() if not v.payer_phone]
	if kerak:
		for g in frappe.db.sql(
			"""SELECT sg.parent student, COALESCE(g.guardian_name, sg.guardian_name) nm,
			          g.mobile_number tel
			   FROM `tabStudent Guardian` sg
			   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
			   WHERE sg.parenttype = 'Student' AND sg.parent IN %s
			     AND g.mobile_number IS NOT NULL AND g.mobile_number != ''
			   ORDER BY sg.parent, sg.idx""",
			(tuple(kerak),),
			as_dict=True,
		):
			v = out.get(g.student)
			if v and not v.payer_phone:
				v.payer_phone = g.tel
				v.payer_name = v.payer_name or g.nm

	for v in out.values():
		if not v.payer_phone:
			v.payer_phone = v._mobil
		v.pop("_mobil", None)
	return out


def _qongiroq_statistikasi(cases) -> None:
	"""Navbat ro'yxatiga qo'ng'iroq soni va oxirgi suhbat vaqtini qo'shadi.

	Hamma ish uchun bitta so'rovda: avval barcha tegishli raqamlar yig'iladi
	(to'lovchi + ota-onalar + o'quvchi), keyin qo'ng'iroqlar raqam bo'yicha
	guruhlanadi. Har ish uchun alohida so'rov yuborilsa panel 276 marta
	bazaga borardi."""
	for c in cases:
		c["qongiroq_soni"] = 0
		c["oxirgi_qongiroq"] = None
		c["yozuv_soni"] = 0
	if not cases:
		return

	studentlar = [c.student for c in cases if c.student]
	# O'quvchi -> uning raqamlari (normal ko'rinishda)
	st_raqam = {}

	def qosh(student, raw):
		n = _normal(raw)
		if n:
			st_raqam.setdefault(student, set()).add(n)

	for c in cases:
		qosh(c.student, c.payer_phone)
	for st in frappe.get_all(
		"Student",
		filters={"name": ["in", studentlar]},
		fields=["name", "student_mobile_number", "custom_payer_phone"],
	):
		qosh(st.name, st.custom_payer_phone)
		qosh(st.name, st.student_mobile_number)
	if studentlar:
		for g in frappe.db.sql(
			"""SELECT sg.parent student, g.mobile_number tel
			   FROM `tabStudent Guardian` sg
			   JOIN `tabGuardian` g ON g.name = sg.guardian
			   WHERE sg.parenttype = 'Student' AND sg.parent IN %s
			     AND g.mobile_number IS NOT NULL AND g.mobile_number != ''""",
			(tuple(studentlar),),
			as_dict=True,
		):
			qosh(g.student, g.tel)

	hamma_raqam = {n for s in st_raqam.values() for n in s}
	if not hamma_raqam:
		return

	shart = "" if _tel_hammasini_koradi() else " AND foydalanuvchi = %(user)s"
	stat = {
		r.normal_telefon: r
		for r in frappe.db.sql(
			f"""SELECT normal_telefon, COUNT(*) soni, MAX(boshlandi) oxirgi,
			           SUM(CASE WHEN yozuv_bor=1 AND IFNULL(yozuv_ochirildi,0)=0
			                    THEN 1 ELSE 0 END) yozuvli
			    FROM `tabTelefon Qongirogi`
			    WHERE normal_telefon IN %(raqamlar)s{shart}
			    GROUP BY normal_telefon""",
			{"raqamlar": tuple(hamma_raqam), "user": frappe.session.user},
			as_dict=True,
		)
	}
	if not stat:
		return
	for c in cases:
		for n in st_raqam.get(c.student, ()):  # aka-ukada raqam umumiy bo'lishi mumkin
			r = stat.get(n)
			if not r:
				continue
			c["qongiroq_soni"] += int(r.soni or 0)
			c["yozuv_soni"] += int(r.yozuvli or 0)
			if not c["oxirgi_qongiroq"] or str(r.oxirgi) > str(c["oxirgi_qongiroq"]):
				c["oxirgi_qongiroq"] = r.oxirgi


def _komment_biriktir(qongiroqlar, ays, soat: int = 4) -> None:
	"""Qo'ng'iroqqa menejerning qisqa tafsilotini biriktiradi.

	Menejer suhbat natijasini `Telefon Qongirogi.izoh` ga emas, panelning
	«Qo'ng'iroq natijasi» modaliga yozadi (Aloqa Yozuvi). Shuning uchun
	qo'ng'iroqdan keyin `soat` ichida yozilgan eng YAQIN aloqa yozuvi shu
	suhbatning tafsiloti deb olinadi — panelda audio yonida ko'rinadi."""
	if not qongiroqlar or not ays:
		return
	from frappe.utils import get_datetime, time_diff_in_seconds

	oyna = soat * 3600
	for q in qongiroqlar:
		if q.get("izoh") or not q.get("boshlandi"):
			continue
		eng_yaqin, eng_farq = None, None
		for a in ays:
			if not a.get("vaqt") or not (a.get("komment") or a.get("hisob_natijasi")):
				continue
			farq = time_diff_in_seconds(get_datetime(a.vaqt), get_datetime(q["boshlandi"]))
			if 0 <= farq <= oyna and (eng_farq is None or farq < eng_farq):
				eng_yaqin, eng_farq = a, farq
		if eng_yaqin:
			q["ay_komment"] = eng_yaqin.get("komment")
			q["ay_natija"] = eng_yaqin.get("hisob_natijasi")
			q["ay_name"] = eng_yaqin.get("name")


def _is_rahbar() -> bool:
	roles = {r.lower() for r in frappe.get_roles()}
	return bool({"system manager", "sales manager"} & roles)


# «Ketgan» belgisini qo'yish huquqi — sotuv rahbari va sotuv menejeri
# (o'quvchining maktabni tashlaganini birinchi bo'lib ular biladi).
KETGAN_ROLLAR = {"system manager", "sales manager", "sotuv meneger"}


def _ketgan_huquqi() -> bool:
	return bool(KETGAN_ROLLAR & {r.lower() for r in frappe.get_roles()})


@frappe.whitelist()
def get_data(ketganlar: int = 0):
	"""Ochiq ishlar ro'yxati + statistikalar + menejerlar (filtr uchun).

	Default'da FAQAT faol (enabled, ketmagan) o'quvchilar ko'rsatiladi — menejer
	navbatida maktabda o'qiyotganlar turishi kerak. Ketganlarning qarzi yo'qolmaydi:
	`ketganlar=1` bilan alohida ro'yxat sifatida ochiladi (panelda chip bor)."""
	_guard()
	ketganlar = int(ketganlar or 0)
	cases = frappe.get_all(
		"Qarz Ishi",
		filters={"ishlov_status": ["not in", list(YOPIQ)]},
		fields=[
			"name", "student", "student_name", "sinf", "payer_name", "payer_phone",
			"qarz_summa", "eng_eski_muddat", "aging_bucket", "ishlov_status",
			"keyingi_aloqa", "masul", "urinishlar_soni", "buzilgan_vadalar",
			"oxirgi_aloqa", "aloqa_cheklovi", "ochilgan_sana",
		],
		order_by="keyingi_aloqa asc, qarz_summa desc",
		limit_page_length=0,
	)

	# Ism, sinf, to'lovchi — Student hujjatidan JONLI (nusxadan emas), shu bilan
	# birga faollik: nofaol (enabled=0) yoki ketgan (date_of_leaving) bo'lsa
	# o'quvchi "ketgan" hisoblanadi.
	live = _student_live([c.student for c in cases])
	ketgan_soni = 0
	tanlangan = []
	for c in cases:
		st = live.get(c.student)
		if st:
			c["student_name"] = st.student_name or c.student_name
			c["sinf"] = st.sinf
			c["payer_name"] = st.payer_name or c.payer_name
			c["payer_phone"] = st.payer_phone or c.payer_phone
		c["ketgan"] = 1 if (st and (not st.enabled or st.date_of_leaving)) else 0
		c["ketgan_sana"] = st.date_of_leaving if st else None
		ketgan_soni += c["ketgan"]
		if bool(c["ketgan"]) == bool(ketganlar):
			tanlangan.append(c)
	cases = tanlangan

	# Har ish bo'yicha aloqa yozuvlari soni — "gaplashilgan" (kamida bir marta
	# aloqaga chiqilgan) ishlarni ajratish uchun.
	case_names = [c.name for c in cases]
	aloqa_map = {}
	if case_names:
		for r in frappe.db.sql(
			"""SELECT qarz_ishi, COUNT(*) soni,
			          SUM(CASE WHEN aloqa_natijasi='Gaplashildi' THEN 1 ELSE 0 END) gaplashildi
			   FROM `tabAloqa Yozuvi`
			   WHERE qarz_ishi IN ({}) GROUP BY qarz_ishi""".format(
				", ".join(["%s"] * len(case_names))
			),
			tuple(case_names),
			as_dict=True,
		):
			aloqa_map[r.qarz_ishi] = r
	for c in cases:
		m = aloqa_map.get(c.name)
		c["aloqa_soni"] = int(m.soni) if m else 0
		c["gaplashildi_soni"] = int(m.gaplashildi or 0) if m else 0

	_qongiroq_statistikasi(cases)

	today = getdate(nowdate())
	stats = {
		"ochiq": len(cases),
		"jami_qarz": sum(flt(c.qarz_summa) for c in cases),
		"bugun": 0,
		"otgan": 0,
		"gaplashilgan": sum(1 for c in cases if c["aloqa_soni"] > 0),
		# Ovoz yozuvi bor suhbat o'tkazilgan o'quvchilar (KPI + filtr uchun)
		"yozuvli": sum(1 for c in cases if c.get("yozuv_soni")),
		"yozuv_jami": sum(int(c.get("yozuv_soni") or 0) for c in cases),
		"vada_buzilgan": sum(1 for c in cases if c.ishlov_status == "Va'da buzildi"),
		"eskalatsiya": sum(1 for c in cases if c.ishlov_status == "Eskalatsiya"),
		"ketgan_soni": ketgan_soni,
		"ketganlar_rejimi": 1 if ketganlar else 0,
		"buckets": {},
	}
	for c in cases:
		if c.keyingi_aloqa:
			if getdate(c.keyingi_aloqa) < today:
				stats["otgan"] += 1
			elif getdate(c.keyingi_aloqa) == today:
				stats["bugun"] += 1
		b = c.aging_bucket or "—"
		stats["buckets"].setdefault(b, {"soni": 0, "summa": 0})
		stats["buckets"][b]["soni"] += 1
		stats["buckets"][b]["summa"] += flt(c.qarz_summa)

	# Mas'ul bo'la oladiganlar — FAQAT sotuv menejerlari; filtr menyusiga
	# ishlardagi eski (legacy) mas'ullar ham qo'shiladi, toki ular bo'yicha
	# ham filtrlash mumkin bo'lsin
	sotuvchilar = sotuv_menejerlar()
	bor = {m["name"] for m in sotuvchilar}
	legacy = sorted({c.masul for c in cases if c.masul and c.masul not in bor})
	user_map = {}
	if legacy:
		for u in frappe.get_all(
			"User", filters={"name": ["in", legacy]}, fields=["name", "full_name"]
		):
			user_map[u.name] = u.full_name or u.name
	managers = ([{"name": m["name"], "full_name": m["full_name"] or m["name"]} for m in sotuvchilar]
				+ [{"name": m, "full_name": (user_map.get(m, m) or m) + " (sotuv emas)"} for m in legacy])

	return {
		"cases": cases,
		"stats": stats,
		"managers": managers,
		"sotuv_menejerlar": [{"name": m["name"], "full_name": m["full_name"] or m["name"]}
							 for m in sotuvchilar],
		"me": frappe.session.user,
		"rahbar": _is_rahbar(),
		"ketgan_huquqi": _ketgan_huquqi(),
	}


@frappe.whitelist()
def get_case(name: str):
	"""Bitta ish kartasi: reja oylari, to'lovlar, timeline, ota-ona telefonlari."""
	_guard()
	qi = frappe.get_doc("Qarz Ishi", name)

	# Ism/sinf/to'lovchi — Student hujjatidan jonli. Qarz Ishi'dagi nusxa
	# (fetch_from surati) eskirgan bo'lishi mumkin; ro'yxat bilan karta
	# har xil ism ko'rsatmasligi uchun ikkalasi ham shu manbadan oladi.
	jonli = _student_live([qi.student]).get(qi.student)
	if jonli:
		qi.student_name = jonli.student_name or qi.student_name
		qi.sinf = jonli.sinf
		qi.payer_name = jonli.payer_name or qi.payer_name
		qi.payer_phone = jonli.payer_phone or qi.payer_phone

	months, payments, hisob, xulosa = [], [], None, None
	if qi.tolov_rejasi:
		tr = frappe.get_doc("Tolov Rejasi", qi.tolov_rejasi)
		# Bekor qilingan qatorlar KO'RSATILMAYDI: nachisleniyasi (Sales Invoice)
		# bekor qilinganda yoki o'quvchi ketganda qator "Bekor" bo'ladi — u na
		# qarzga kiradi, na to'lov kutiladi. Hisob-kitob ham shunday
		# (engine va plan_xulosa Bekor qatorlarni tashlab ketadi).
		months = [
			{
				"oy_label": r.oy_label, "due_date": r.due_date, "amount": r.amount,
				"paid_amount": r.paid_amount, "qaytim": r.qaytim,
				"outstanding": r.outstanding, "holat": r.holat,
				"reja_amount": r.reja_amount, "nachisleniya": r.nachisleniya,
				"manba_hujjat": r.manba_hujjat, "izoh": r.izoh,
			}
			for r in tr.oylar
			if r.holat != "Bekor"
		]
		from target_zenit.qarzdorlik import engine

		payments = engine.get_payments(tr.customer, engine._plan_payment_window(tr))

		# Hisob tafsiloti — "nega bunday chiqdi" savoliga javob (UI'da ko'rinadi)
		tolov, qaytim = engine._payments_split(tr.customer, engine._plan_payment_window(tr))
		hisob = {
			"reja": tr.name,
			"customer": tr.customer,
			"davr_boshi": engine._plan_payment_window(tr),
			"jami_tolov": tolov,
			"jami_qaytim": qaytim,
			"sof": tolov - qaytim,
			# Yangi qoidadan keyin jami to'lov bilan jadval farq qilishi MUMKIN:
			# kitob/forma/yotoqxona nachisleniyasiga bog'lanmagan pul o'sha qatorga
			# tushmaydi. Farq ko'rinib turishi uchun ikkisi ham ko'rsatiladi.
			"jadvalga_tushgan": sum(flt(r.paid_amount) for r in tr.oylar),
			"taqsimlanmagan": flt(tr.avans_summa),
			"jadvalda_qaytim": sum(flt(r.qaytim) for r in tr.oylar),
			"hisoblangan": str(tr.modified)[:16],
		}
		# Batafsil xulosa: o'quv to'lovi / kitob-forma / oyma-oy nachisleniya
		xulosa = engine.plan_xulosa(tr)

	# Timeline: aloqa yozuvlari + va'dalar, xronologik (yangi tepada)
	ays = frappe.get_all(
		"Aloqa Yozuvi",
		filters={"qarz_ishi": name},
		fields=[
			"name", "vaqt", "masul", "kanal", "aloqa_natijasi", "hisob_natijasi",
			"komment", "keyingi_harakat", "keyingi_sana", "vada_summa", "vada_sana",
		],
		order_by="vaqt desc",
		limit_page_length=50,
	)
	ptps = frappe.get_all(
		"Tolov Vadasi",
		filters={"qarz_ishi": name},
		fields=["name", "vada_sana", "vada_summa", "holat", "amal_summa", "creation"],
		order_by="creation desc",
		limit_page_length=20,
	)

	guardians = frappe.db.sql(
		"""SELECT COALESCE(g.guardian_name, sg.guardian_name) guardian_name,
		          sg.relation, g.mobile_number
		   FROM `tabStudent Guardian` sg
		   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parent = %s AND sg.parenttype = 'Student'
		   ORDER BY sg.idx""",
		(qi.student,),
		as_dict=True,
	)

	# Shu to'lovchining boshqa farzandlari (aka-uka — bitta qo'ng'iroqda)
	siblings = []
	if qi.payer_phone:
		siblings = frappe.get_all(
			"Qarz Ishi",
			filters={
				"payer_phone": qi.payer_phone,
				"name": ["!=", name],
				"ishlov_status": ["not in", list(YOPIQ)],
			},
			fields=["name", "student", "student_name", "qarz_summa", "masul", "ishlov_status"],
			limit_page_length=10,
		)
		sib_live = _student_live([s.student for s in siblings])
		for sb in siblings:
			sb["student_name"] = (sib_live.get(sb.student) or {}).get(
				"student_name"
			) or sb.student_name

	student_phone = frappe.db.get_value("Student", qi.student, "student_mobile_number")

	# Telefon suhbatlari (ovoz yozuvi bilan) — raqam bo'yicha bog'lanadi
	qongiroqlar = _qongiroqlar(qi.student, qi.payer_phone, qi.payer_name)
	_komment_biriktir(qongiroqlar, ays)

	return {
		"case": qi.as_dict(no_nulls=False),
		"months": months,
		"payments": payments,
		"hisob": hisob,
		"xulosa": xulosa,
		"ays": ays,
		"ptps": ptps,
		"guardians": guardians,
		"siblings": siblings,
		"student_phone": student_phone,
		"qongiroqlar": qongiroqlar,
		"tel_hammasi": 1 if _tel_hammasini_koradi() else 0,
	}


@frappe.whitelist()
def save_call(payload):
	"""«Qo'ng'iroq natijasi» modali: Aloqa Yozuvi yaratadi — qolganini
	(PTP, Qarz Ishi statusi/sanalari) AY'ning o'zi kaskadda qiladi."""
	_guard()
	if isinstance(payload, str):
		payload = json.loads(payload)

	fields = {
		"qarz_ishi", "kanal", "aloqa_natijasi", "hisob_natijasi", "komment",
		"keyingi_harakat", "keyingi_sana", "vada_summa", "vada_sana",
	}
	doc = {"doctype": "Aloqa Yozuvi"}
	doc.update({k: v for k, v in payload.items() if k in fields and v not in (None, "")})
	ay = frappe.get_doc(doc).insert()  # permission tekshiruvi bilan

	qi = frappe.db.get_value(
		"Qarz Ishi",
		ay.qarz_ishi,
		["name", "ishlov_status", "keyingi_aloqa", "urinishlar_soni", "qarz_summa"],
		as_dict=True,
	)
	return {"ay": ay.name, "case": qi}


@frappe.whitelist()
def reassign(case: str, masul: str):
	"""Mas'ulni almashtirish — faqat rahbar, faqat SOTUV MENEJERIGA."""
	_guard()
	if not _is_rahbar():
		frappe.throw("Mas'ulni faqat rahbar (Sales Manager) almashtira oladi.")
	if not _sotuv_menejermi(masul):
		frappe.throw(
			f"Mas'ul faqat «{SOTUV_ROL}» roli biriktirilgan faol foydalanuvchi bo'la oladi. "
			f"«{masul}» bu rolga ega emas."
		)
	frappe.db.set_value("Qarz Ishi", case, "masul", masul)
	return {"ok": 1}


@frappe.whitelist()
def qayta_hisobla(case: str):
	"""«Qayta hisoblash» tugmasi — shu o'quvchining rejasini qaytadan hisoblaydi.
	Kod yangilangandan keyin eski qiymatlar qolib ketsa shu yerdan tuzatiladi
	(kechasi nightly baribir hammasini qayta hisoblaydi)."""
	_guard()
	tr = frappe.db.get_value("Qarz Ishi", case, "tolov_rejasi")
	if not tr:
		frappe.throw("Bu ishga to'lov rejasi bog'lanmagan.")
	from target_zenit.qarzdorlik import engine

	engine.recompute_plan(tr, sync_case=True)
	frappe.db.commit()
	return get_case(case)


@frappe.whitelist()
def ketgan_belgilash(case: str, sana: str | None = None, sabab: str | None = None):
	"""«O'quvchi ketdi» — sotuv menejeri panelda belgilaydi, yozuv STUDENT
	hujjatiga tushadi (date_of_leaving + enabled=0) va izoh komment sifatida
	saqlanadi (kim, qachon, nega belgiladi).

	Keyin Student hook'i (`on_student_change`) ketish sanasidan keyingi oylarni
	Bekor qiladi va qolgan qarzni "Ketgan-qarzli" guruhiga o'tkazadi — ya'ni
	qarz yo'qolmaydi, faqat navbatdan chiqadi."""
	_guard()
	if not _ketgan_huquqi():
		frappe.throw("O'quvchini «ketgan» deb belgilashni faqat sotuv menejeri/rahbari qila oladi.")

	student = frappe.db.get_value("Qarz Ishi", case, "student")
	if not student:
		frappe.throw("Ish topilmadi.")
	sana = sana or nowdate()
	if getdate(sana) > getdate(nowdate()):
		frappe.throw("Ketish sanasi kelajakda bo'lishi mumkin emas.")

	doc = frappe.get_doc("Student", student)
	doc.date_of_leaving = sana
	doc.enabled = 0
	doc.save(ignore_permissions=True)
	doc.add_comment(
		"Comment",
		f"Qarzdorlik panelida «ketgan» deb belgilandi: {getdate(sana).strftime('%d.%m.%Y')}"
		+ (f" — {sabab}" if sabab else ""),
	)
	frappe.db.commit()
	return {"ok": 1, "student": student, "sana": sana}


@frappe.whitelist()
def qaytardi(case: str):
	"""Xato belgilangan bo'lsa — o'quvchini qaytarish (ketish sanasi olinadi).

	Ketish belgilanganda Student hook'i ketish sanasidan KEYINGI oylarni Bekor
	qilgan edi — ular ham tiklanadi, aks holda o'quvchi qaytsa ham rejasi
	yarim qolib, nachisleniya tushadigan oylar ko'rinmas edi."""
	_guard()
	if not _ketgan_huquqi():
		frappe.throw("Faqat sotuv menejeri/rahbari qaytara oladi.")
	student = frappe.db.get_value("Qarz Ishi", case, "student")
	ketish = frappe.db.get_value("Student", student, "date_of_leaving")

	doc = frappe.get_doc("Student", student)
	doc.date_of_leaving = None
	doc.enabled = 1
	doc.save(ignore_permissions=True)
	doc.add_comment("Comment", "Qarzdorlik panelida «ketgan» belgisi olib tashlandi")

	tiklandi = 0
	if ketish:
		for tr in frappe.get_all(
			"Tolov Rejasi", filters={"student": student, "holat": ["!=", "Bekor"]}, pluck="name"
		):
			for r in frappe.get_all(
				"Tolov Rejasi Oyi",
				filters={"parent": tr, "parenttype": "Tolov Rejasi",
				         "holat": "Bekor", "due_date": [">", ketish]},
				pluck="name",
			):
				frappe.db.set_value(
					"Tolov Rejasi Oyi", r, "holat", "Kutilmoqda", update_modified=False
				)
				tiklandi += 1
			if tiklandi:
				from target_zenit.qarzdorlik import engine

				engine.recompute_plan(tr, sync_case=True)
	frappe.db.commit()
	return {"ok": 1, "student": student, "tiklandi": tiklandi}
