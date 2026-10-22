# Copyright (c) 2026, Target Zenit
# Frappe -> Moodle: dars jadvali va o'quv kalendarini uzatish.
#
# Moodle'da jadvalni ko'rsatishning standart vositasi yo'q, shuning uchun
# `local_targetzenit` plaginiga o'z jadvali va sahifasi qo'yilgan. Bu modul
# plaginning `local_targetzenit_push_timetable` funksiyasiga ma'lumot yuboradi.
#
# NIMA YUBORILADI:
#   - faol `Jadval Versiyasi` dagi hamma dars (guruh, fan, o'qituvchi, kun,
#     dars raqami, vaqt, xona + kursning idnumber'i)
#   - o'quv kalendari: `Academic Term` (chorak oraliqlari) va `Holiday List`
#     dagi bayramlar — sahifada sanalarni hisoblash uchun
#
# Har yuborishda Moodle o'sha o'quv yilini BUTUNLAY almashtiradi: Frappe
# yagona manba, qisman yangilash chalkashlik keltiradi.

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from target_zenit.integrations.moodle import _call, _settings
from target_zenit.integrations.moodle_kurs import _oquv_yili


def _vaqt(qiymat):
	"""MariaDB `time` qiymati "9:00:00" ko'rinishida keladi -> "09:00"."""
	if not qiymat:
		return ""
	qism = str(qiymat).split(":")
	if len(qism) >= 2:
		try:
			return f"{int(qism[0]):02d}:{int(qism[1]):02d}"
		except ValueError:
			pass
	return str(qiymat)[:5]


def _darslar(yil):
	"""Faol jadvaldagi hamma dars — plagin kutgan ko'rinishda."""
	rows = frappe.db.sql(
		"""
		SELECT jy.guruh, jy.guruh_nomi, jy.fan, jy.oqituvchi, jy.oqituvchi_nomi,
		       jy.kun, jy.kun_raqami, jy.dars_raqami, jy.boshlanish, jy.tugash, jy.xona
		FROM `tabJadval Yozuvi` jy
		INNER JOIN `tabJadval Versiyasi` jv ON jv.name = jy.versiya
		WHERE jv.holat = 'Faol'
		  AND IFNULL(jy.guruh, '') != ''
		  AND IFNULL(jy.fan, '') != ''
		ORDER BY jy.kun_raqami, jy.dars_raqami, jy.guruh
		""",
		as_dict=True,
	)

	# O'qituvchi kaliti — foydalanuvchi sinxronidagi bilan BIR XIL bo'lishi shart,
	# aks holda sahifada "mening jadvalim" ishlamaydi.
	emp_map = {
		i.name: i.employee
		for i in frappe.get_all("Instructor", fields=["name", "employee"], limit_page_length=0)
	}

	darslar = []
	for r in rows:
		oqituvchi_kaliti = ""
		if r.oqituvchi:
			oqituvchi_kaliti = emp_map.get(r.oqituvchi) or f"INSTR-{r.oqituvchi}"
		darslar.append({
			"groupkey": r.guruh,
			"groupname": r.guruh_nomi or r.guruh,
			"subjectkey": r.fan,
			"subjectname": r.fan,
			"teacherkey": oqituvchi_kaliti,
			"teachername": r.oqituvchi_nomi or "",
			"dayno": int(r.kun_raqami or 0),
			"dayname": r.kun or "",
			"lessonno": int(r.dars_raqami or 0),
			"starttime": _vaqt(r.boshlanish),
			"endtime": _vaqt(r.tugash),
			"room": r.xona or "",
			"courseidnumber": f"{yil}::{r.guruh}::{r.fan}",
		})
	return darslar


def _kalendar(yil, holiday_list=None):
	"""Chorak oraliqlari + bayramlar. Sahifa sanalarni shular asosida hisoblaydi."""
	kalendar = []

	for t in frappe.get_all(
		"Academic Term",
		filters={"academic_year": yil},
		fields=["name", "term_start_date", "term_end_date"],
		order_by="term_start_date",
		limit_page_length=0,
	):
		if t.term_start_date and t.term_end_date:
			kalendar.append({
				"entrytype": "term",
				"name": t.name,
				"startdate": str(t.term_start_date),
				"enddate": str(t.term_end_date),
			})

	if holiday_list:
		for h in frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list},
			fields=["holiday_date", "description"],
			order_by="holiday_date",
			limit_page_length=0,
		):
			if h.holiday_date:
				kalendar.append({
					"entrytype": "holiday",
					"name": (h.description or "Bayram")[:255],
					"startdate": str(h.holiday_date),
					"enddate": str(h.holiday_date),
				})

	return kalendar


def push(trigger="Qo'lda"):
	"""Jadval va kalendarni Moodle'ga yuboradi. Moodle Sync Log qaytaradi."""
	s = _settings()
	if not s.enabled:
		frappe.throw("Moodle Settings: integratsiya yoqilmagan.")

	log = frappe.get_doc({
		"doctype": "Moodle Sync Log",
		"sync_type": "Kurs",
		"trigger_type": trigger,
		"status": "Ishlayapti",
		"started": now_datetime(),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

	lines = []
	try:
		yil = _oquv_yili()
		darslar = _darslar(yil)
		kalendar = _kalendar(yil, s.holiday_list)

		choraklar = sum(1 for k in kalendar if k["entrytype"] == "term")
		bayramlar = sum(1 for k in kalendar if k["entrytype"] == "holiday")
		lines.append(
			f"O'quv yili: {yil} | dars qatori: {len(darslar)} | "
			f"chorak: {choraklar} | bayram: {bayramlar}"
		)
		if not s.holiday_list:
			lines.append(
				"OGOHLANTIRISH: Bayram kunlari ro'yxati tanlanmagan — jadvalda "
				"bayram kunlari ham dars kuni bo'lib ko'rinadi."
			)
		if not choraklar:
			lines.append(
				f"OGOHLANTIRISH: {yil} uchun Academic Term topilmadi — sahifa "
				"sanalarni hisoblay olmaydi."
			)

		if s.dry_run:
			lines.append("TEST REJIMI: Moodle'ga yuborilmadi.")
			natija = {"lessons": 0, "calendar": 0}
		else:
			natija = _call("local_targetzenit_push_timetable", {
				"academicyear": yil,
				"lessons": darslar,
				"calendar": kalendar,
			})
			lines.append(
				f"Moodle qabul qildi: {natija.get('lessons')} dars, "
				f"{natija.get('calendar')} kalendar yozuvi"
			)

		log.db_set({
			"status": "Tugadi",
			"finished": now_datetime(),
			"updated_count": natija.get("lessons") or 0,
			"skipped_count": natija.get("calendar") or 0,
			"details": "\n".join(lines)[:140000],
		})
		frappe.db.set_single_value(
			"Moodle Settings", "last_status",
			f"Jadval: {natija.get('lessons')} dars yuborildi",
		)
		frappe.db.commit()
		return log.name

	except Exception as e:
		frappe.db.rollback()
		lines.append(f"TO'XTADI: {e}")
		log.db_set({
			"status": "Xato",
			"finished": now_datetime(),
			"error_count": 1,
			"details": ("\n".join(lines) + "\n\n" + frappe.get_traceback())[:140000],
		})
		frappe.db.commit()
		frappe.log_error(title="Moodle jadval push", message=frappe.get_traceback())
		raise


@frappe.whitelist()
def preview_jadval(limit=5):
	"""Moodle'ga tegmasdan nima yuborilishini ko'rsatadi."""
	frappe.only_for("System Manager")
	s = _settings()
	yil = _oquv_yili()
	darslar = _darslar(yil)
	kalendar = _kalendar(yil, s.holiday_list)
	return {
		"o_quv_yili": yil,
		"dars_qatori": len(darslar),
		"guruh": len({d["groupkey"] for d in darslar}),
		"o_qituvchi": len({d["teacherkey"] for d in darslar if d["teacherkey"]}),
		"chorak": sum(1 for k in kalendar if k["entrytype"] == "term"),
		"bayram": sum(1 for k in kalendar if k["entrytype"] == "holiday"),
		"bayram_royxati": s.holiday_list or "(tanlanmagan)",
		"namuna": darslar[: int(limit)],
	}


@frappe.whitelist()
def push_now():
	"""Moodle Settings tugmasi."""
	frappe.only_for("System Manager")
	return push(trigger="Qo'lda")


def daily_sync():
	"""Scheduler: kurs sinxronidan keyin (hooks.py, 07:20)."""
	s = _settings()
	if not s.enabled:
		return
	push(trigger="Avto (07:00)")
