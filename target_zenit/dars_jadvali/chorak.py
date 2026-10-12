# Copyright (c) 2026, Target Zenit
# Chorak bahosi: sozlamalardagi usul (O'rtacha / Vaznli / Qo'lda) bo'yicha hisoblash,
# o'qituvchi tasdiqlashi va `Chorak Bahosi` yozuvlariga saqlash.
from __future__ import annotations

import json

import frappe
from frappe import _

from target_zenit.dars_jadvali import baholash as bah
from target_zenit.dars_jadvali import sozlamalar as soz


@frappe.whitelist()
def chorak_jadval(guruh: str, fan: str, chorak: str) -> dict:
	"""Guruh+fan+chorak uchun har o'quvchining ballari, tizim hisobi va mavjud chorak bahosi."""
	if not bah._menejermi() and not bah._mening_instructorim():
		frappe.throw(_("Ruxsat yo'q."), frappe.PermissionError)
	s = soz.olish()

	oquvchilar = frappe.get_all(
		"Student Group Student",
		filters={"parent": guruh, "parenttype": "Student Group", "active": 1},
		fields=["student", "student_name", "group_roll_number"],
		order_by="group_roll_number, student_name", limit_page_length=0)

	# Chorakdagi barcha natijalar (ball + davomat)
	natijalar = frappe.get_all(
		"Dars Natijasi",
		filters={"guruh": guruh, "fan": fan, "chorak": chorak},
		fields=["student", "baho", "baho_turi", "davomat", "sana"],
		order_by="sana", limit_page_length=0)
	# Chorakda o'tilgan darslar soni (davomat foizi uchun):
	# belgilangan bajarilishlar yoki jurnalda yozuv bor sanalar — qaysi ko'p bo'lsa
	darslar = max(
		len({str(r.sana) for r in natijalar}),
		frappe.db.count("Dars Bajarilishi", {"guruh": guruh, "fan": fan, "holat": "O'tildi"}) or 0)

	per = {}
	for r in natijalar:
		p = per.setdefault(r.student, {"ballar": [], "yoqlik": 0, "kechikish": 0})
		if r.baho:
			p["ballar"].append({"baho": r.baho, "baho_turi": r.baho_turi, "sana": str(r.sana)})
		if r.davomat in soz.YOQLIK:
			p["yoqlik"] += 1
		elif r.davomat == "Kechikdi":
			p["kechikish"] += 1

	# Uy vazifa bajarmagani
	uv_bajarmagan = {}
	for r in frappe.get_all(
		"Uy Vazifa Natijasi",
		filters={"guruh": guruh, "fan": fan, "chorak": chorak, "holat": "Bajarmadi"},
		fields=["student"], limit_page_length=0):
		uv_bajarmagan[r.student] = uv_bajarmagan.get(r.student, 0) + 1

	# Mavjud chorak bahosi
	mavjud = {r.student: r for r in frappe.get_all(
		"Chorak Bahosi", filters={"guruh": guruh, "fan": fan, "chorak": chorak},
		fields=["name", "student", "baho", "hisoblangan", "qolda", "izoh"], limit_page_length=0)}

	qatorlar = []
	for o in oquvchilar:
		p = per.get(o.student, {"ballar": [], "yoqlik": 0, "kechikish": 0})
		hisob = soz.chorak_hisobla(p["ballar"], s)
		k = soz.korsatkich(
			[b["baho"] for b in p["ballar"]], darslar=darslar, yoqlik=p["yoqlik"],
			kechikish=p["kechikish"], uv_bajarmagan=uv_bajarmagan.get(o.student, 0), s=s)
		m = mavjud.get(o.student)
		qatorlar.append({
			"student": o.student, "student_name": o.student_name,
			"roll": o.group_roll_number,
			"ballar": [b["baho"] for b in p["ballar"]],
			"baho_turlari": [b["baho_turi"] for b in p["ballar"]],
			"baho_soni": hisob["baho_soni"], "ortacha": hisob["ortacha"],
			"hisoblangan": hisob["hisoblangan"], "taklif": hisob["baho"],
			"yetarli": hisob["yetarli"],
			"yoqlik": p["yoqlik"], "kechikish": p["kechikish"],
			"davomat_foiz": k["davomat_foiz"], "rang": k["rang"], "trend": k["trend"],
			"bayroqlar": k["bayroqlar"],
			"chorak_bahosi": m.baho if m else None,
			"qolda": m.qolda if m else 0,
			"yozuv": m.name if m else None,
			"izoh": m.izoh if m else None,
		})
	return {
		"guruh": guruh, "fan": fan, "chorak": chorak, "darslar": darslar,
		"usul": s.get("chorak_usuli"), "min_baho_soni": s.get("min_baho_soni"),
		"max_baho": s.get("max_baho"), "sozlamalar": s,
		"qatorlar": qatorlar,
	}


@frappe.whitelist()
def chorak_saqla(guruh: str, fan: str, chorak: str, qatorlar) -> dict:
	"""Chorak bahosini saqlash (upsert). qatorlar: [{student, baho, izoh}]"""
	if isinstance(qatorlar, str):
		qatorlar = json.loads(qatorlar)
	oqituvchi = frappe.db.get_value("Jadval Yozuvi", {"guruh": guruh, "fan": fan}, "oqituvchi")
	bah._ruxsat(oqituvchi)
	s = soz.olish()
	n = 0
	for q in qatorlar:
		student = q.get("student")
		if not student:
			continue
		baho = q.get("baho")
		baho = int(baho) if baho not in (None, "", 0) else None
		if baho and s.get("max_baho") and baho > s["max_baho"]:
			frappe.throw(_("Chorak bahosi {0} dan katta bo'lishi mumkin emas.").format(s["max_baho"]))
		nom = frappe.db.get_value(
			"Chorak Bahosi", {"student": student, "fan": fan, "chorak": chorak}, "name")
		if baho is None:
			if nom:
				frappe.delete_doc("Chorak Bahosi", nom, ignore_permissions=True)
			continue
		qiymat = {
			"student": student, "fan": fan, "guruh": guruh, "chorak": chorak,
			"oqituvchi": oqituvchi, "baho": baho, "usul": s.get("chorak_usuli"),
			"hisoblangan": q.get("hisoblangan"), "ortacha": q.get("ortacha"),
			"baho_soni": q.get("baho_soni"),
			"qolda": 1 if q.get("qolda") else 0, "izoh": q.get("izoh"),
		}
		if nom:
			doc = frappe.get_doc("Chorak Bahosi", nom)
			doc.update(qiymat)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(dict(doctype="Chorak Bahosi", **qiymat)).insert(ignore_permissions=True)
		n += 1
	frappe.db.commit()
	return {"saqlandi": n}


@frappe.whitelist()
def chorak_avto(guruh: str, fan: str, chorak: str) -> dict:
	"""Tizim hisobini hammaga qo'yish («O'rtacha»/«Vaznli» usul uchun tez tugma).
	Qo'lda o'zgartirilgan baholar tegilmaydi."""
	d = chorak_jadval(guruh, fan, chorak)
	qatorlar = []
	otkazildi = 0
	for q in d["qatorlar"]:
		if q["qolda"]:
			otkazildi += 1
			continue
		if q["taklif"] is None:
			continue
		qatorlar.append({
			"student": q["student"], "baho": q["taklif"],
			"hisoblangan": q["hisoblangan"], "ortacha": q["ortacha"],
			"baho_soni": q["baho_soni"], "qolda": 0,
		})
	r = chorak_saqla(guruh, fan, chorak, qatorlar)
	r["otkazildi"] = otkazildi
	return r
