# Copyright (c) 2026, Target Zenit
# Dars jurnali: har darsда o'quvchiga baho + davomat (Keldi/Kelmadi/Kasal/Qatnashmadi).
# Choraklik (4 chorak = Academic Term) + o'tgan baholar ko'rinishi.
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

DAVOMAT = ("Keldi", "Kelmadi", "Kasal", "Qatnashmadi")
MENEJER = {"system manager", "zavuch", "academics user", "education manager"}


def _menejermi() -> bool:
	return bool(MENEJER & {r.lower() for r in frappe.get_roles()})


def _mening_instructorim() -> str | None:
	user = frappe.session.user
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		ins = frappe.db.get_value("Instructor", {"employee": emp}, "name")
		if ins:
			return ins
	full_name = frappe.db.get_value("User", user, "full_name")
	return frappe.db.get_value("Instructor", {"instructor_name": full_name}, "name")


def _ruxsat(jy_oqituvchi):
	if _menejermi():
		return
	meniki = _mening_instructorim()
	if not meniki or (jy_oqituvchi and jy_oqituvchi != meniki):
		frappe.throw(_("Faqat shu darsning o'qituvchisi baholay oladi."), frappe.PermissionError)


def _chorak(sana) -> str | None:
	"""Shu sana tushadigan Academic Term (chorak)."""
	sana = getdate(sana)
	return frappe.db.get_value(
		"Academic Term",
		{"term_start_date": ["<=", sana], "term_end_date": [">=", sana]}, "name")


@frappe.whitelist()
def dars_oquvchilari(jadval_yozuvi: str, sana: str | None = None) -> dict:
	"""Dars guruhidagi o'quvchilar + har biriga mavjud natija (baho/davomat)."""
	sana = sana or nowdate()
	jy = frappe.db.get_value(
		"Jadval Yozuvi", jadval_yozuvi,
		["guruh", "guruh_nomi", "fan", "oqituvchi", "oqituvchi_nomi", "dars_raqami", "kun"], as_dict=True)
	if not jy:
		frappe.throw(_("Dars topilmadi."))

	oquvchilar = frappe.get_all(
		"Student Group Student",
		filters={"parent": jy.guruh, "parenttype": "Student Group", "active": 1},
		fields=["student", "student_name", "group_roll_number"],
		order_by="group_roll_number, student_name", limit_page_length=0)

	# Mavjud natijalar (shu dars + sana)
	mavjud = {r.student: r for r in frappe.get_all(
		"Dars Natijasi",
		filters={"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana)},
		fields=["name", "student", "davomat", "baho", "izoh"], limit_page_length=0)}

	qatorlar = []
	for o in oquvchilar:
		m = mavjud.get(o.student)
		qatorlar.append({
			"student": o.student, "student_name": o.student_name,
			"roll": o.group_roll_number,
			"davomat": m.davomat if m else "Keldi",
			"baho": m.baho if m else None,
			"izoh": m.izoh if m else None,
			"saqlangan": bool(m),
		})
	return {
		"jadval_yozuvi": jadval_yozuvi, "guruh": jy.guruh, "guruh_nomi": jy.guruh_nomi,
		"fan": jy.fan, "oqituvchi": jy.oqituvchi, "oqituvchi_nomi": jy.oqituvchi_nomi,
		"kun": jy.kun, "dars_raqami": jy.dars_raqami, "sana": str(sana),
		"chorak": _chorak(sana),
		"oquvchilar": qatorlar,
	}


@frappe.whitelist()
def natija_saqla(jadval_yozuvi: str, sana: str, qatorlar) -> dict:
	"""Bir dars uchun barcha o'quvchilar baho/davomatini saqlaydi (upsert)."""
	if isinstance(qatorlar, str):
		qatorlar = json.loads(qatorlar)
	jy = frappe.db.get_value(
		"Jadval Yozuvi", jadval_yozuvi,
		["guruh", "fan", "oqituvchi"], as_dict=True)
	if not jy:
		frappe.throw(_("Dars topilmadi."))
	_ruxsat(jy.oqituvchi)
	chorak = _chorak(sana)
	n = 0
	for q in qatorlar:
		student = q.get("student")
		if not student:
			continue
		davomat = q.get("davomat") or "Keldi"
		baho = q.get("baho")
		baho = int(baho) if (baho not in (None, "", 0) and davomat == "Keldi") else None
		mavjud = frappe.db.get_value(
			"Dars Natijasi", {"jadval_yozuvi": jadval_yozuvi, "sana": getdate(sana), "student": student}, "name")
		# "Belgilanmagan = Keldi": Keldi + baho yo'q => yozuv saqlanmaydi
		# (faqat kelmaganlar va baholar yoziladi). Eski bo'sh yozuv bo'lsa — o'chiriladi.
		if davomat == "Keldi" and not baho:
			if mavjud:
				frappe.delete_doc("Dars Natijasi", mavjud, ignore_permissions=True)
			continue
		qiymat = {
			"student": student, "jadval_yozuvi": jadval_yozuvi, "guruh": jy.guruh,
			"fan": jy.fan, "oqituvchi": jy.oqituvchi, "sana": getdate(sana),
			"chorak": chorak, "davomat": davomat, "baho": baho, "izoh": q.get("izoh"),
		}
		if mavjud:
			d = frappe.get_doc("Dars Natijasi", mavjud)
			d.update(qiymat)
			d.save(ignore_permissions=True)
		else:
			frappe.get_doc(dict(doctype="Dars Natijasi", **qiymat)).insert(ignore_permissions=True)
		n += 1
	frappe.db.commit()
	return {"saqlandi": n}


@frappe.whitelist()
def oquvchi_tarix(student: str, fan: str | None = None, chorak: str | None = None,
                  limit: int = 100) -> list[dict]:
	"""O'quvchining o'tgan baholari/davomatlari (eng yangisi birinchi)."""
	filtr = {"student": student}
	if fan:
		filtr["fan"] = fan
	if chorak:
		filtr["chorak"] = chorak
	return frappe.get_all(
		"Dars Natijasi", filters=filtr,
		fields=["sana", "fan", "davomat", "baho", "izoh", "chorak"],
		order_by="sana desc", limit_page_length=int(limit))


@frappe.whitelist()
def guruh_hisobot(guruh: str, chorak: str | None = None, fan: str | None = None) -> dict:
	"""Choraklik hisobot: guruhdagi har o'quvchining o'rtacha bahosi + davomat yig'indisi."""
	if not _menejermi() and not _mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	filtr = {"guruh": guruh}
	if chorak:
		filtr["chorak"] = chorak
	if fan:
		filtr["fan"] = fan
	rows = frappe.get_all(
		"Dars Natijasi", filters=filtr,
		fields=["student", "student_name", "davomat", "baho"], limit_page_length=0)
	agg = {}
	for r in rows:
		a = agg.setdefault(r.student, {
			"student": r.student, "student_name": r.student_name,
			"baholar": [], "keldi": 0, "kelmadi": 0, "kasal": 0, "qatnashmadi": 0})
		if r.baho:
			a["baholar"].append(r.baho)
		key = {"Keldi": "keldi", "Kelmadi": "kelmadi", "Kasal": "kasal", "Qatnashmadi": "qatnashmadi"}.get(r.davomat)
		if key:
			a[key] += 1
	natija = []
	for a in agg.values():
		bh = a.pop("baholar")
		a["ortacha"] = round(sum(bh) / len(bh), 1) if bh else None
		a["baho_soni"] = len(bh)
		natija.append(a)
	natija.sort(key=lambda x: x["student_name"] or "")
	return {"guruh": guruh, "chorak": chorak, "oquvchilar": natija}


KUNLAR = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]


@frappe.whitelist()
def jurnal_jadval(guruh: str, fan: str, chorak: str | None = None,
                  versiya: str | None = None) -> dict:
	"""eMaktab-uslub jurnal: o'quvchilar × dars sanalari matritsasi (baho/davomat).
	Ustunlar — shu guruh+fan darslarining chorakdagi sanalari (bugungacha)."""
	if not _menejermi() and not _mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	from datetime import timedelta
	versiya = versiya or frappe.db.get_value("Jadval Versiyasi", {"holat": "Faol"}, "name") \
		or frappe.db.get_value("Jadval Versiyasi", {}, "name")

	# Chorak sana oralig'i
	if chorak:
		t = frappe.db.get_value("Academic Term", chorak, ["term_start_date", "term_end_date"], as_dict=True)
		start, end = getdate(t.term_start_date), getdate(t.term_end_date)
	else:
		start, end = getdate("2000-01-01"), getdate(nowdate())
	bugun = getdate(nowdate())
	oxiri = min(end, bugun)

	oquvchilar = frappe.get_all(
		"Student Group Student",
		filters={"parent": guruh, "parenttype": "Student Group", "active": 1},
		fields=["student", "student_name", "group_roll_number"],
		order_by="group_roll_number, student_name", limit_page_length=0)

	# Darslar (jadval yozuvi) — shu guruh+fan
	jys = frappe.get_all(
		"Jadval Yozuvi", filters={"versiya": versiya, "guruh": guruh, "fan": fan},
		fields=["name", "kun", "dars_raqami"], limit_page_length=0)

	# Ustunlar: har jadval yozuvi uchun chorakdagi mos hafta kunlari sanalari
	ustunlar = []
	for jy in jys:
		try:
			wd = KUNLAR.index(jy.kun)
		except ValueError:
			continue
		d = start
		while d <= oxiri:
			if d.weekday() == wd:
				ustunlar.append({
					"jadval_yozuvi": jy.name, "sana": str(d),
					"kun": jy.kun, "dars_raqami": jy.dars_raqami,
					"label": f"{d.day:02d}.{d.month:02d}",
				})
			d = d + timedelta(days=1)
	ustunlar.sort(key=lambda x: (x["sana"], x["dars_raqami"] or 0))

	# Mavjud natijalar
	cells = {}
	for r in frappe.get_all(
		"Dars Natijasi",
		filters={"guruh": guruh, "fan": fan, "sana": ["between", [start, end]]},
		fields=["student", "jadval_yozuvi", "sana", "davomat", "baho"], limit_page_length=0):
		cells[(r.student, r.jadval_yozuvi, str(r.sana))] = {"davomat": r.davomat, "baho": r.baho}

	qatorlar = []
	for o in oquvchilar:
		kat = []
		for u in ustunlar:
			kat.append(cells.get((o.student, u["jadval_yozuvi"], u["sana"])))
		qatorlar.append({
			"student": o.student, "student_name": o.student_name,
			"roll": o.group_roll_number, "kataklar": kat,
		})
	return {
		"guruh": guruh, "fan": fan, "chorak": chorak,
		"ustunlar": ustunlar, "qatorlar": qatorlar,
	}


@frappe.whitelist()
def oquvchi_karta(student: str) -> dict:
	"""Bitta o'quvchi hisobot kartasi: fan × chorak bo'yicha o'rtacha baho +
	davomat (kelmadi/kasal/qatnashmadi) yig'indisi. Ota-ona/sinf rahbari uchun."""
	if not _menejermi() and not _mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	ism = frappe.db.get_value("Student", student, "student_name")
	rows = frappe.get_all(
		"Dars Natijasi", filters={"student": student},
		fields=["fan", "chorak", "davomat", "baho"], limit_page_length=0)
	# choraklar tartibi
	ch_order = [c.name for c in frappe.get_all(
		"Academic Term", fields=["name"], order_by="term_start_date", limit_page_length=0)]
	ch_label = {c.name: (c.term_name or c.name) for c in frappe.get_all(
		"Academic Term", fields=["name", "term_name"], limit_page_length=0)}

	cells = {}      # (fan, chorak) -> {baholar:[], kelmadi, kasal, qatnashmadi}
	fanlar, choraklar_used = set(), set()
	for r in rows:
		fanlar.add(r.fan)
		ch = r.chorak or "—"
		choraklar_used.add(ch)
		c = cells.setdefault((r.fan, ch), {"baholar": [], "kelmadi": 0, "kasal": 0, "qatnashmadi": 0})
		if r.baho:
			c["baholar"].append(r.baho)
		k = {"Kelmadi": "kelmadi", "Kasal": "kasal", "Qatnashmadi": "qatnashmadi"}.get(r.davomat)
		if k:
			c[k] += 1

	choraklar = [c for c in ch_order if c in choraklar_used] + \
		[c for c in sorted(choraklar_used) if c not in ch_order]
	jadval = []
	for fan in sorted(fanlar):
		qator = {"fan": fan, "choraklar": []}
		hamma_baho = []
		for ch in choraklar:
			c = cells.get((fan, ch))
			if c:
				bh = c["baholar"]
				hamma_baho += bh
				qator["choraklar"].append({
					"ortacha": round(sum(bh) / len(bh), 1) if bh else None,
					"baho_soni": len(bh), "kelmadi": c["kelmadi"],
					"kasal": c["kasal"], "qatnashmadi": c["qatnashmadi"],
				})
			else:
				qator["choraklar"].append(None)
		qator["yillik"] = round(sum(hamma_baho) / len(hamma_baho), 1) if hamma_baho else None
		jadval.append(qator)

	return {
		"student": student, "ism": ism,
		"choraklar": [{"name": c, "label": ch_label.get(c, c)} for c in choraklar],
		"jadval": jadval,
	}


@frappe.whitelist()
def choraklar() -> list[dict]:
	"""Academic Term (choraklar) ro'yxati."""
	return frappe.get_all(
		"Academic Term", fields=["name", "term_name", "academic_year", "term_start_date", "term_end_date"],
		order_by="term_start_date", limit_page_length=0)


def choraklar_ornat():
	"""4 chorak (Academic Term) — yo'q bo'lsa yaratadi. Sanalar AY nomidan (YYYY-YYYY)
	olingan standart; user tahrirlashi mumkin. after_migrate'да idempotent chaqiriladi."""
	ay = frappe.db.get_value("Academic Year", {}, "name")
	if not ay:
		return
	import re as _re
	m = _re.findall(r"\d{4}", ay)
	if len(m) >= 2:
		sy, ey = int(m[0]), int(m[1])
	elif m:
		sy = int(m[0])
		ey = sy + 1
	else:
		return
	terms = [
		("1-chorak", f"{sy}-09-01", f"{sy}-11-02"),
		("2-chorak", f"{sy}-11-10", f"{sy}-12-28"),
		("3-chorak", f"{ey}-01-12", f"{ey}-03-22"),
		("4-chorak", f"{ey}-03-30", f"{ey}-05-25"),
	]
	# AY sana oralig'i choraklarni qamrashi uchun (validatsiyani chetlab)
	frappe.db.set_value("Academic Year", ay, "year_start_date",
	                    min(frappe.db.get_value("Academic Year", ay, "year_start_date") or getdate(f"{sy}-09-01"),
	                        getdate(f"{sy}-09-01")), update_modified=False)
	frappe.db.set_value("Academic Year", ay, "year_end_date",
	                    max(frappe.db.get_value("Academic Year", ay, "year_end_date") or getdate(f"{ey}-05-25"),
	                        getdate(f"{ey}-05-25")), update_modified=False)
	for nm, b, e in terms:
		if not frappe.db.exists("Academic Term", {"academic_year": ay, "term_name": nm}):
			frappe.get_doc({
				"doctype": "Academic Term", "academic_year": ay, "term_name": nm,
				"term_start_date": b, "term_end_date": e,
			}).insert(ignore_permissions=True)
	frappe.db.commit()
