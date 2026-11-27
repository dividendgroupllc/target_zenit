# Copyright (c) 2026, Target Zenit
# Zavuch uchun KUNLIK YO'QLAMA — pul ma'lumotisiz.
#
# Ma'lumot ERPNext `Attendance` ga yoziladi — oylik tabel (api/oylik_tabel.py)
# aynan shu yozuvlarni o'qiydi, ya'ni zavuch belgilagan yo'qlama buxgalteriya
# tabeliga avtomatik tushadi. Bu sahifada OYLIK/BONUS/SUMMA umuman yo'q.
from __future__ import annotations

import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, nowdate

from target_zenit.kadrlar import ish_haqi_kategoriyalari

ROLLAR = ["System Manager", "Zavuch", "Xojakbar_Operator", "HR Manager", "HR User",
		  "Direktor"]
HAFTA = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]

# FAQAT KO'RISH rollari (2026-11-19, foydalanuvchi talabi): Direktor roli
# yo'qlamani ko'radi, lekin belgilay olmaydi.
# Bu ro'yxatdagi rol faqat qo'shimcha huquq BERMAYDI — foydalanuvchida
# tahrir roli (Zavuch, HR...) ham bo'lsa, tahrir ishlayveradi.
KORISH_ROLLAR = {"direktor"}

# FAQAT KO'RISH foydalanuvchilari: shu ro'yxatdagi user ROLIDAN QAT'I NAZAR
# yozolmaydi (roli boshqa joylar uchun qolaveradi). Hozir bo'sh —
# nurbekzamdirektor 2026-11-19 da qo'shilgan edi, 2026-11-23 da foydalanuvchi
# talabi bilan to'liq yo'qlama huquqi qaytarildi.
KORISH_FOYDALANUVCHILAR = set()


# Bu rollar istalgan (o'tgan) kunni ham tahrirlay oladi.
# Zavuch ham kiradi (2026-11-04, foydalanuvchi talabi): kunlik yo'qlamani
# o'tkazib yuborgan kunlarini keyin to'ldirishi kerak. Chegara baribir bor:
# kelajak kunga yozilmaydi va YOPILGAN oy tahrirlanmaydi (`belgila`).
TOLIQ_ROLLAR = {"system manager", "xojakbar_operator", "hr manager", "hr user", "zavuch"}

# Turniket ish vaqti chegaralari (2026-11-27 qaror): 09:00 dan keyingi birinchi
# o'tish = "kechikib keldi" (QAT'IY, grace yo'q); kun yakunida oxirgi o'tishi
# 18:00 dan oldingi CHIQISH bo'lsa = "erta chiqib ketdi". Soatbay xodimga smena
# hisobi YO'Q — turniket u uchun faqat dalil (keldimi), ogohlantirish berilmaydi.
ISH_BOSHI = "09:00:00"
ISH_TUGASHI = "18:00:00"


def _guard(tahrir=False):
	rollar = {r.lower() for r in frappe.get_roles()}
	if not ({r.lower() for r in ROLLAR} & rollar):
		frappe.throw(_("Yo'qlamaga ruxsatingiz yo'q"), frappe.PermissionError)
	if tahrir and _faqat_korish():
		frappe.throw(_("Sizga yo'qlama faqat KO'RISH uchun ochilgan — belgilash mumkin emas"),
					 frappe.PermissionError)


def _faqat_korish() -> bool:
	"""Foydalanuvchi yozolmaydi: yo ro'yxatda (user bo'yicha blok),
	yo unda tahrir beruvchi rol yo'q (faqat ko'rish roli bor)."""
	if frappe.session.user.lower() in KORISH_FOYDALANUVCHILAR:
		return True
	rollar = {r.lower() for r in frappe.get_roles()}
	tahrir_rollar = {r.lower() for r in ROLLAR} - KORISH_ROLLAR
	return not (tahrir_rollar & rollar)


def _faqat_bugun() -> bool:
	"""Faqat bugungi kunni belgilay oladimi.

	TOLIQ_ROLLAR (zavuch, HR, operator, administrator) o'tgan kunlarni ham
	tahrirlaydi; ro'yxatda bo'lmagan rol faqat bugungi kun bilan cheklanadi."""
	rollar = {r.lower() for r in frappe.get_roles()}
	return not (TOLIQ_ROLLAR & rollar)


def _kategoriya_tanlovi(kategoriya):
	"""Filtr qiymatini ro'yxatga keltiradi: bitta string YOKI JSON ro'yxat."""
	tanlov = kategoriya
	if isinstance(tanlov, str) and tanlov.strip().startswith("["):
		import json
		try:
			tanlov = json.loads(tanlov)
		except Exception:
			tanlov = [kategoriya]
	if isinstance(tanlov, str):
		tanlov = [tanlov] if tanlov else []
	return [str(t) for t in (tanlov or []) if t]


def _kategoriya_mos(x, tanlov):
	kat = (x.custom_ish_haqi_kategoriya or "").strip()
	return (kat in tanlov) or ("__none" in tanlov and not kat)


def _oy_ochiqmi(yil, oy) -> bool:
	holat = frappe.db.get_value("Tabel Oyi", {"yil": yil, "oy": oy}, "holat")
	return holat != "Yopiq"


def _norma_map(yil, oy, nomlar):
	"""Shu oy uchun qo'lda kiritilgan norma ish kunlari ("Tabel Ish Kuni")."""
	if not nomlar:
		return {}
	return {r.xodim: cint(r.kun) for r in frappe.get_all(
		"Tabel Ish Kuni", filters={"yil": yil, "oy": oy, "xodim": ["in", nomlar]},
		fields=["xodim", "kun"], limit_page_length=0, ignore_permissions=True)}


def _kerak_kun(x, kunlar, dars_kunlari, norma_map, kirgan, ketgan):
	"""Xodim shu oyda NECHA KUN kelishi kerak + bu son qayerdan olingani.

	USTUNLIK TARTIBI (2026-11-18): oylik tabelda shu oy uchun QO'LDA kiritilgan
	norma ("Tabel Ish Kuni") hamma narsadan ustun — jadvalli o'qituvchida ham.
	Aks holda tabelda "kelishi kerak kun"ni o'zgartirish yo'qlamadagi "Kerak"ka
	ta'sir qilmasdi (foydalanuvchi talabi). Qo'lda kiritilmagan bo'lsa:
	dars jadvalida kunlari bor xodim (o'qituvchi) — jadval bo'yicha: oyda
	uning dars kunlari necha marta keladi (ishga kirgan/ketgan sanasi
	hisobga olinadi); jadvali yo'q xodim — Employee.custom_ish_kuni ->
	default (o'qituvchi 21, boshqalar 26)."""
	if x.name in norma_map:
		return norma_map[x.name], "oy"
	if dars_kunlari:
		n = 0
		for kd in kunlar:
			d = getdate(kd["sana"])
			if d.weekday() not in dars_kunlari:
				continue
			if kirgan and d < kirgan:
				continue
			if ketgan and d > ketgan:
				continue
			n += 1
		return n, "jadval"
	if cint(x.get("custom_ish_kuni")):
		return cint(x.get("custom_ish_kuni")), "xodim"
	from target_zenit.target_zenit.api.oylik_tabel import _default_ish_kuni
	return _default_ish_kuni(x.designation), "default"


@frappe.whitelist()
def get_data(yil=None, oy=None, kategoriya=None):
	"""Oylik yo'qlama to'ri: xodimlar x kunlar. Pul maydonlari qaytarilmaydi.

	kategoriya — bitta qiymat YOKI JSON ro'yxat (ko'p tanlov): masalan
	'["O\\'qituvchi","Oshxona"]'. "__none" — kategoriyasi belgilanmaganlar."""
	_guard()
	bugun = getdate(nowdate())
	yil, oy = cint(yil) or bugun.year, cint(oy) or bugun.month
	kunlar_soni = calendar.monthrange(yil, oy)[1]
	oy_boshi, oy_oxiri = f"{yil}-{oy:02d}-01", f"{yil}-{oy:02d}-{kunlar_soni}"

	# Oylik tabel bilan BIR XIL tanlov: faqat "Oylik tabelda" belgisi qo'yilgan
	# xodimlar (Active'lar ko'p, tabelga esa hozir real ishlayotganlar kiradi).
	# Ishdan ketganlar — ketgan oyigacha ko'rinadi, keyin chiqib ketadi.
	xodimlar = frappe.get_all(
		"Employee",
		filters={"custom_tabelda": 1, "date_of_joining": ["<=", oy_oxiri]},
		# DIQQAT: oylik/summa maydonlari ATAYLAB olinmaydi
		fields=["name", "employee_name", "designation", "custom_tolov_turi",
				"custom_ish_haqi_kategoriya", "custom_ish_kuni",
				"date_of_joining", "relieving_date", "status"],
		order_by="employee_name",
		limit_page_length=0,
		ignore_permissions=True,
	)
	oy_boshi_d = getdate(oy_boshi)
	saralangan = []
	for x in xodimlar:
		ketgan = getdate(x.relieving_date) if x.relieving_date else None
		if x.status != "Active" and (not ketgan or ketgan < oy_boshi_d):
			continue
		if ketgan and ketgan < oy_boshi_d:
			continue
		saralangan.append(x)
	xodimlar = saralangan
	# Filtr ro'yxati uchun — kategoriyalar filtrdan OLDIN yig'iladi,
	# aks holda bittasini tanlagach qolganlari ro'yxatdan yo'qolardi
	# Ro'yxat Employee maydonidan olinadi (qotib yozilmaydi): kadrlar yangi
	# kategoriya qo'shsa yoki nomini o'zgartirsa filtr ham o'zi yangilanadi.
	kategoriyalar = ish_haqi_kategoriyalari(
		[x.custom_ish_haqi_kategoriya for x in xodimlar]
	)

	# Ish haqi kategoriyasi (tabel) bo'yicha filtr — KO'P TANLOV:
	# ro'yxatdagi istalgan kategoriyaga mos xodimlar ko'rsatiladi
	tanlov = _kategoriya_tanlovi(kategoriya)
	if tanlov:
		xodimlar = [x for x in xodimlar if _kategoriya_mos(x, tanlov)]

	nomlar = [x.name for x in xodimlar]
	belgilar = {}
	if nomlar:
		for a in frappe.get_all(
			"Attendance",
			filters={"employee": ["in", nomlar], "attendance_date": ["between", [oy_boshi, oy_oxiri]],
					 "docstatus": ["<", 2]},
			fields=["employee", "attendance_date", "status", "custom_koef"],
			limit_page_length=0,
			ignore_permissions=True,
		):
			belgilar[f"{a.employee}|{a.attendance_date}"] = {
				"status": a.status, "koef": flt(a.custom_koef),
			}

	# Dars jadvalidan: kim qaysi hafta kunlari dars qiladi (yo'qlama uchun
	# yo'riqnoma) va QAYSI FANlardan kiradi
	darsli = {}
	fanlar = {}
	versiya = frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")
	if versiya:
		KUN_RAQAM = {"Dushanba": 0, "Seshanba": 1, "Chorshanba": 2, "Payshanba": 3,
					 "Juma": 4, "Shanba": 5}
		# Instructor -> Employee bitta so'rovda (har yozuv uchun alohida emas)
		ins_emp = {i.name: i.employee for i in frappe.get_all(
			"Instructor", fields=["name", "employee"], limit_page_length=0) if i.employee}
		yozuvlar = frappe.get_all(
			"Jadval Yozuvi", filters={"versiya": versiya},
			fields=["oqituvchi", "kun", "fan"], limit_page_length=0,
		)
		# Fan nomlari (Course docname -> course_name)
		fan_kodlari = {j.fan for j in yozuvlar if j.fan}
		fan_nomi = {}
		if fan_kodlari:
			fan_nomi = {c.name: (c.course_name or c.name) for c in frappe.get_all(
				"Course", filters={"name": ["in", list(fan_kodlari)]},
				fields=["name", "course_name"], limit_page_length=0)}
		for j in yozuvlar:
			emp = ins_emp.get(j.oqituvchi)
			if not emp:
				continue
			if j.kun in KUN_RAQAM:
				darsli.setdefault(emp, set()).add(KUN_RAQAM[j.kun])
			if j.fan:
				fanlar.setdefault(emp, set()).add(fan_nomi.get(j.fan, j.fan))

	kunlar = []
	for k in range(1, kunlar_soni + 1):
		d = getdate(f"{yil}-{oy:02d}-{k:02d}")
		kunlar.append({"kun": k, "sana": str(d), "hafta": HAFTA[d.weekday()],
					   "dam": d.weekday() >= 5, "kelajak": d > bugun})

	# "Nechi kun kelishi kerak" uchun oylik tabeldagi norma ish kuni zanjiri
	norma_map = _norma_map(yil, oy, nomlar)

	qatorlar = []
	for x in xodimlar:
		kunlik = []
		keldi = 0
		# Ishga kirgan/ketgan sanalari — oylik tabeldagi kabi: xodim ishlamagan
		# kunlar "—" bo'lib ko'rinadi va belgilanmaydi (ketgani bir ko'rishda bilinadi)
		kirgan = getdate(x.date_of_joining) if x.date_of_joining else None
		ketgan = getdate(x.relieving_date) if x.relieving_date else None
		for kd in kunlar:
			sana_d = getdate(kd["sana"])
			if kirgan and sana_d < kirgan:
				kunlik.append({"sana": kd["sana"], "holat": None, "koef": None,
							   "tashqari": "kirmagan"})
				continue
			if ketgan and sana_d > ketgan:
				kunlik.append({"sana": kd["sana"], "holat": None, "koef": None,
							   "tashqari": "ketgan"})
				continue
			b = belgilar.get(f"{x.name}|{kd['sana']}")
			holat = b["status"] if b else None
			if holat == "Present":
				keldi += 1
			kunlik.append({"sana": kd["sana"], "holat": holat,
						   "koef": b["koef"] if b else None, "tashqari": None})
		kerak_kun, kerak_manba = _kerak_kun(x, kunlar, darsli.get(x.name), norma_map,
											kirgan, ketgan)
		qatorlar.append({
			"xodim": x.name,
			# Ism HAR DOIM Employee hujjatidan (xodim ID bo'yicha) — Instructor'dagi
			# `instructor_name` nusxa, ism tuzatilganda eskicha qolib ketadi.
			"ism": x.employee_name or x.name,
			"lavozim": x.designation or "",
			"kategoriya": x.custom_ish_haqi_kategoriya or "",
			"soatbay": (x.custom_tolov_turi or "").strip() == "Soatbay",
			"kirgan_sana": str(kirgan) if kirgan else None,
			"ketgan_sana": str(ketgan) if ketgan else None,
			"fanlar": sorted(fanlar.get(x.name, [])),
			"kerak_kun": kerak_kun,
			"kerak_manba": kerak_manba,
			"dars_kunlari": sorted(darsli.get(x.name, [])),
			"kunlik": kunlik,
			"keldi": keldi,
		})

	return {
		"yil": yil, "oy": oy, "kunlar": kunlar, "qatorlar": qatorlar,
		"kategoriyalar": kategoriyalar,
		"faqat_bugun": _faqat_bugun(),
		"faqat_korish": _faqat_korish(),
		"kategoriya": kategoriya or "",
		"oy_ochiq": _oy_ochiqmi(yil, oy),
		"bugun": str(bugun),
		# Instructor sifatida ro'yxatdan o'tgan xodimlar soni (ma'lumot uchun)
		"oqituvchilar_soni": frappe.db.count("Instructor", {"employee": ["!=", ""]}),
	}


@frappe.whitelist()
def kun_data(sana=None, kategoriya=None):
	"""Bitta kunning to'liq manzarasi: har xodimning turniket kirdi-chiqdilari
	(HRMS Employee Checkin — turniket webhook yozadi) + zavuch yo'qlama belgisi.

	Turniket = DALIL, zavuch belgisi = TASDIQ: oylik tabel faqat Attendance'ni
	o'qiydi, Attendance'ni esa faqat shu sahifadagi `belgila` yozadi — turniket
	o'z-o'zidan oylikka ta'sir qilmaydi."""
	_guard()
	bugun = getdate(nowdate())
	sana = getdate(sana) if sana else bugun

	xodimlar = frappe.get_all(
		"Employee",
		filters={"custom_tabelda": 1, "date_of_joining": ["<=", str(sana)]},
		fields=["name", "employee_name", "designation", "custom_tolov_turi",
				"custom_ish_haqi_kategoriya", "date_of_joining", "relieving_date",
				"status"],
		order_by="employee_name",
		limit_page_length=0,
		ignore_permissions=True,
	)
	# Shu kunda real ishlagan xodimlargina (oy ko'rinishidagi "—" kunlar bu
	# ro'yxatga umuman kirmaydi — kun tanlangach ortiqcha qator shart emas)
	saralangan = []
	for x in xodimlar:
		ketgan = getdate(x.relieving_date) if x.relieving_date else None
		if x.status != "Active" and (not ketgan or ketgan < sana):
			continue
		if ketgan and ketgan < sana:
			continue
		saralangan.append(x)
	xodimlar = saralangan

	kategoriyalar = ish_haqi_kategoriyalari(
		[x.custom_ish_haqi_kategoriya for x in xodimlar]
	)
	tanlov = _kategoriya_tanlovi(kategoriya)
	if tanlov:
		xodimlar = [x for x in xodimlar if _kategoriya_mos(x, tanlov)]
	nomlar = [x.name for x in xodimlar]

	belgilar = {}
	checkinlar = {}
	if nomlar:
		for a in frappe.get_all(
			"Attendance",
			filters={"employee": ["in", nomlar], "attendance_date": str(sana),
					 "docstatus": ["<", 2]},
			fields=["employee", "status", "custom_koef"],
			limit_page_length=0, ignore_permissions=True,
		):
			belgilar[a.employee] = {"status": a.status, "koef": flt(a.custom_koef)}
		for c in frappe.get_all(
			"Employee Checkin",
			filters={"employee": ["in", nomlar],
					 "time": ["between", [f"{sana} 00:00:00", f"{sana} 23:59:59"]]},
			fields=["employee", "time", "log_type", "device_id"],
			order_by="time asc", limit_page_length=0, ignore_permissions=True,
		):
			checkinlar.setdefault(c.employee, []).append(c)

	kech_chegara = get_datetime(f"{sana} {ISH_BOSHI}")
	erta_chegara = get_datetime(f"{sana} {ISH_TUGASHI}")
	# "Erta chiqib ketdi" faqat kun yakunlangach aytiladi — ish kuni o'rtasida
	# chiqib turgan odam hali qaytib kirishi mumkin (tushlik va h.k.)
	kun_yakun = sana < bugun or now_datetime() >= erta_chegara

	qatorlar = []
	for x in xodimlar:
		soatbay = (x.custom_tolov_turi or "").strip() == "Soatbay"
		evs = checkinlar.get(x.name, [])
		hodisalar = [{
			"vaqt": get_datetime(c.time).strftime("%H:%M"),
			"turi": c.log_type or "",
			"terminal": c.device_id or "",
		} for c in evs]
		kirdi_soni = sum(1 for c in evs if c.log_type == "IN")
		chiqdi_soni = sum(1 for c in evs if c.log_type == "OUT")
		birinchi = get_datetime(evs[0].time) if evs else None
		oxirgi = get_datetime(evs[-1].time) if evs else None

		# Ogohlantirishlar — faqat smenali (soatbay bo'lmagan) xodimga:
		# soatbay o'qituvchiga turniket faqat dalil, kech/erta hisobi yo'q
		ogohlar = []
		if evs and not soatbay:
			if birinchi > kech_chegara:
				ogohlar.append({"turi": "kech",
								"matn": f"Kechikib keldi ({birinchi.strftime('%H:%M')})"})
			if kun_yakun:
				if evs[-1].log_type == "OUT" and oxirgi < erta_chegara:
					ogohlar.append({"turi": "erta",
									"matn": f"Erta chiqib ketdi ({oxirgi.strftime('%H:%M')})"})
				elif chiqdi_soni == 0:
					ogohlar.append({"turi": "chiqishyoq",
									"matn": "Chiqishi qayd etilmagan"})

		b = belgilar.get(x.name)
		qatorlar.append({
			"xodim": x.name,
			"ism": x.employee_name or x.name,
			"lavozim": x.designation or "",
			"kategoriya": x.custom_ish_haqi_kategoriya or "",
			"soatbay": soatbay,
			"hodisalar": hodisalar,
			"kirdi_soni": kirdi_soni,
			"chiqdi_soni": chiqdi_soni,
			"birinchi": birinchi.strftime("%H:%M") if birinchi else None,
			"oxirgi": oxirgi.strftime("%H:%M") if oxirgi else None,
			"ogohlar": ogohlar,
			# tanlovPop/saqla oy ko'rinishidagi qator bilan BIR XIL ishlashi uchun
			"kunlik": [{"sana": str(sana), "holat": b["status"] if b else None,
						"koef": b["koef"] if b else None, "tashqari": None}],
			"keldi": 1 if b and b["status"] == "Present" else 0,
		})

	return {
		"sana": str(sana), "hafta": HAFTA[sana.weekday()],
		"dam": sana.weekday() >= 5, "kelajak": sana > bugun,
		"qatorlar": qatorlar,
		"kategoriyalar": kategoriyalar,
		"faqat_bugun": _faqat_bugun(),
		"faqat_korish": _faqat_korish(),
		"oy_ochiq": _oy_ochiqmi(sana.year, sana.month),
		"bugun": str(bugun),
		"kun_yakun": kun_yakun,
		"ish_boshi": ISH_BOSHI[:5], "ish_tugashi": ISH_TUGASHI[:5],
		"turniketda": sum(1 for q in qatorlar if q["hodisalar"]),
		"kechikkan": sum(1 for q in qatorlar
						 if any(o["turi"] == "kech" for o in q["ogohlar"])),
		"erta_ketgan": sum(1 for q in qatorlar
						   if any(o["turi"] == "erta" for o in q["ogohlar"])),
	}


@frappe.whitelist()
def belgila(xodim, sana, holat, koef=None):
	"""Bitta kunni belgilash: Keldi / Kelmadi / tozalash.
	Attendance'ga yoziladi — oylik tabel shu yozuvlarni o'qiydi."""
	_guard(tahrir=True)
	sana = getdate(sana)
	bugun = getdate(nowdate())
	if sana > bugun:
		frappe.throw(_("Kelajak kunga yo'qlama qilib bo'lmaydi"))
	if _faqat_bugun() and sana != bugun:
		frappe.throw(
			_("Siz faqat BUGUNGI kun ({0}) uchun yo'qlama qila olasiz. "
			  "O'tgan kunni tuzatish kerak bo'lsa — HR yoki administratorga murojaat qiling.")
			.format(bugun.strftime("%d.%m.%Y")),
			frappe.PermissionError,
		)
	if not _oy_ochiqmi(sana.year, sana.month):
		frappe.throw(_("Bu oy yopilgan — o'zgartirib bo'lmaydi"))

	emp = frappe.db.get_value(
		"Employee", xodim,
		["name", "company", "custom_tolov_turi", "date_of_joining", "relieving_date"],
		as_dict=True)
	if not emp:
		frappe.throw(_("Xodim topilmadi"))
	# Ishga kirishdan oldin / ishdan ketgandan keyin yo'qlama bo'lmaydi
	if emp.date_of_joining and sana < getdate(emp.date_of_joining):
		frappe.throw(_("Xodim {0} da ishga kirgan — undan oldingi kunga yozib bo'lmaydi")
					 .format(emp.date_of_joining))
	if emp.relieving_date and sana > getdate(emp.relieving_date):
		frappe.throw(_("Xodim {0} da ishdan ketgan — undan keyingi kunga yozib bo'lmaydi")
					 .format(emp.relieving_date))
	soatbay = (emp.custom_tolov_turi or "").strip() == "Soatbay"

	if holat == "tozalash":
		for a in frappe.get_all("Attendance", filters={
				"employee": xodim, "attendance_date": sana, "docstatus": ["<", 2]}, pluck="name"):
			doc = frappe.get_doc("Attendance", a)
			doc.flags.ignore_permissions = True
			doc.cancel() if doc.docstatus == 1 else doc.delete(ignore_permissions=True)
		return {"ok": 1, "holat": None}

	status = "Present" if holat == "Keldi" else "Absent"
	if soatbay and status == "Present":
		koef = flt(koef) if koef is not None else 8
		if koef < 0 or koef > 24:
			frappe.throw(_("Soat 0 dan 24 gacha bo'lishi kerak"))
	else:
		koef = 1.0 if status == "Present" else 0.0

	mavjud = frappe.db.get_value("Attendance", {
		"employee": xodim, "attendance_date": sana, "docstatus": ["<", 2]}, "name")
	if mavjud:
		doc = frappe.get_doc("Attendance", mavjud)
		doc.flags.ignore_permissions = True
		if doc.docstatus == 1:
			doc.cancel()
			mavjud = None
		else:
			doc.status = status
			doc.custom_koef = koef
			doc.save(ignore_permissions=True)
	if not mavjud:
		doc = frappe.get_doc({
			"doctype": "Attendance", "naming_series": "HR-ATT-.YYYY.-",
			"employee": xodim, "attendance_date": sana, "status": status,
			"custom_koef": koef, "company": emp.company,
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

	return {"ok": 1, "holat": status, "koef": koef}
