# Copyright (c) 2026, Target Zenit
# Frappe -> Moodle: kurs, kategoriya va kursga yozish (enrolment) sinxroni.
#
# NIMA UCHUN KERAK: Moodle'da "o'quvchi" yoki "o'qituvchi" foydalanuvchining
# xossasi emas — bu KURS ichida beriladigan rol. Shuning uchun odamlar kirsin-u
# o'z fanini ko'rsin desak, kurs yaratib, odamni unga rol bilan yozish kerak.
#
# MANBA (hammasi Frappe'da yuritiladi):
#   Jadval Yozuvi (faol versiya) -> qaysi guruhda qaysi fanni kim o'qitadi
#   Student Group Student        -> guruhda kim o'qiydi
#   Moodle User Link             -> o'sha odamning Moodle user id'si
#
# TUZILMA (foydalanuvchi qarori, 2026-10-22):
#   Kategoriya: <o'quv yili>  ->  <guruh>
#   Kurs      : har (guruh x fan) juftligi uchun bittadan  (~307 ta)
#   Rollar    : o'qituvchi = editingteacher (3), o'quvchi = student (5)
#
# SINXRON KALITI: <o'quv yili>::<guruh>::<fan> -> Moodle kursining `idnumber`i.
# O'quv yili kalitda bo'lgani uchun har sentabrda yangi kurslar tug'iladi,
# o'tgan yilgilari baholari bilan arxivda qoladi.
#
# HECH QACHON O'CHIRILMAYDI:
#   fan jadvaldan chiqsa  -> kurs yashiriladi (visible=0)
#   o'quvchi guruhdan chiqsa -> yozilishi suspend qilinadi (baholari qoladi)

from __future__ import annotations

import hashlib
import json

import frappe
from frappe.utils import now_datetime

from target_zenit.integrations.moodle import (
	MoodleError,
	_call,
	_settings,
)

# Bitta so'rovda nechta yozilish yuboriladi
ENROL_BATCH = 150
# Bitta so'rovda nechta kurs yaratiladi
COURSE_BATCH = 20


# ---------------------------------------------------------------- Frappe tomoni

def _oquv_yili():
	"""Faol jadval versiyasidan o'quv yilini oladi."""
	yil = frappe.db.get_value(
		"Jadval Versiyasi", {"holat": "Faol"}, "academic_year", order_by="creation desc"
	)
	if not yil:
		frappe.throw(
			"Faol jadval versiyasi topilmadi (Jadval Versiyasi -> holat 'Faol'). "
			"Kurs sinxroni qaysi o'quv yili uchun ishlashini bilmaydi."
		)
	return yil


def _juftliklar(yil):
	"""Faol jadvaldan (guruh, fan) juftliklari va ularning o'qituvchisi.

	Bitta juftlikda bir nechta o'qituvchi uchrasa, eng ko'p dars soati borini
	olamiz (amalda bunday holat yo'q — tekshirilgan).
	"""
	rows = frappe.db.sql(
		"""
		SELECT jy.guruh, jy.guruh_nomi, jy.fan, jy.oqituvchi, jy.oqituvchi_nomi,
		       COUNT(*) AS soat
		FROM `tabJadval Yozuvi` jy
		INNER JOIN `tabJadval Versiyasi` jv ON jv.name = jy.versiya
		WHERE jv.holat = 'Faol'
		  AND IFNULL(jy.guruh, '') != ''
		  AND IFNULL(jy.fan, '') != ''
		GROUP BY jy.guruh, jy.guruh_nomi, jy.fan, jy.oqituvchi, jy.oqituvchi_nomi
		ORDER BY soat DESC
		""",
		as_dict=True,
	)
	juft = {}
	for r in rows:
		kalit = (r.guruh, r.fan)
		if kalit in juft:
			continue  # soat bo'yicha tartiblangan — birinchisi asosiy o'qituvchi
		juft[kalit] = {
			"idnumber": f"{yil}::{r.guruh}::{r.fan}",
			"guruh": r.guruh,
			"guruh_nomi": r.guruh_nomi or r.guruh,
			"fan": r.fan,
			"oqituvchi": r.oqituvchi,
			"oqituvchi_nomi": r.oqituvchi_nomi,
			"soat": r.soat,
		}
	return juft


def _guruh_azolari():
	"""{guruh: [Student docname, ...]} — faqat faol a'zolar va faol o'quvchilar."""
	rows = frappe.db.sql(
		"""
		SELECT sgs.parent AS guruh, sgs.student
		FROM `tabStudent Group Student` sgs
		INNER JOIN `tabStudent` s ON s.name = sgs.student
		WHERE sgs.active = 1
		  AND s.enabled = 1
		  AND IFNULL(s.date_of_leaving, '0001-01-01') <= '0001-01-01'
		""",
		as_dict=True,
	)
	azo = {}
	for r in rows:
		azo.setdefault(r.guruh, []).append(r.student)
	return azo


def _oqituvchi_kaliti(instructor):
	"""Instructor -> Moodle User Link kaliti (Employee ID yoki INSTR-<docname>)."""
	if not instructor:
		return None
	emp = frappe.db.get_value("Instructor", instructor, "employee")
	return emp or f"INSTR-{instructor}"


def _user_map():
	"""{sinxron kaliti: moodle_user_id} — faqat Moodle'da haqiqatan bor bo'lganlar."""
	rows = frappe.get_all(
		"Moodle User Link",
		filters={"moodle_user_id": [">", 0]},
		fields=["name", "moodle_user_id", "status"],
		limit_page_length=0,
	)
	return {r.name: r.moodle_user_id for r in rows}


def _hash(payload):
	return hashlib.md5(
		json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
	).hexdigest()


# ---------------------------------------------------------------- Moodle tomoni

def _kategoriyalar():
	"""Moodle'dagi hamma kategoriya: {idnumber: id}."""
	res = _call("core_course_get_categories", {"addsubcategories": 1})
	return {c["idnumber"]: c["id"] for c in (res or []) if c.get("idnumber")}


def _kategoriya_taminla(yil, guruhlar, lines, dry):
	"""Kerakli kategoriyalarni yaratadi: <yil> -> <guruh>. {guruh: category_id}."""
	mavjud = _kategoriyalar()

	yil_key = f"TZ-AY-{yil}"
	yil_id = mavjud.get(yil_key)
	if not yil_id:
		if dry:
			lines.append(f"  [test] kategoriya yaratiladi: {yil}")
			yil_id = -1
		else:
			res = _call("core_course_create_categories", {
				"categories": [{"name": yil, "idnumber": yil_key, "parent": 0}],
			})
			yil_id = res[0]["id"]
			lines.append(f"Kategoriya yaratildi: {yil} (id {yil_id})")

	natija, yaratiladi = {}, []
	for guruh in sorted(guruhlar):
		key = f"TZ-SG-{yil}::{guruh}"
		if key in mavjud:
			natija[guruh] = mavjud[key]
		else:
			yaratiladi.append({"name": guruh, "idnumber": key, "parent": yil_id})

	if yaratiladi:
		if dry:
			lines.append(f"  [test] {len(yaratiladi)} ta sinf kategoriyasi yaratiladi")
			for y in yaratiladi:
				natija[y["name"]] = -1
		else:
			for i in range(0, len(yaratiladi), COURSE_BATCH):
				chunk = yaratiladi[i : i + COURSE_BATCH]
				res = _call("core_course_create_categories", {"categories": chunk})
				for c in res or []:
					natija[c["name"]] = c["id"]
			lines.append(f"Sinf kategoriyalari yaratildi: {len(yaratiladi)} ta")

	return natija


def _moodle_kurslar():
	"""Moodle'dagi hamma kurs: {idnumber: kurs dict}."""
	res = _call("core_course_get_courses")
	return {c["idnumber"]: c for c in (res or []) if c.get("idnumber")}


def _kurs_yarat(kurslar):
	"""Partiya bo'lib yaratadi; partiya yiqilsa bittalab ajratadi."""
	yaratildi, xatolar = {}, {}
	try:
		res = _call("core_course_create_courses", {"courses": kurslar})
		for c in res or []:
			yaratildi[c["shortname"]] = c["id"]
		return yaratildi, xatolar
	except MoodleError as e:
		if len(kurslar) == 1:
			xatolar[kurslar[0]["shortname"]] = str(e)
			return yaratildi, xatolar
	for k in kurslar:
		y, x = _kurs_yarat([k])
		yaratildi.update(y)
		xatolar.update(x)
	return yaratildi, xatolar


def _kurs_yangila(kurslar):
	xatolar = {}
	if not kurslar:
		return xatolar
	try:
		_call("core_course_update_courses", {"courses": kurslar})
		return xatolar
	except MoodleError as e:
		if len(kurslar) == 1:
			xatolar[str(kurslar[0].get("id"))] = str(e)
			return xatolar
	for k in kurslar:
		xatolar.update(_kurs_yangila([k]))
	return xatolar


def _yozilishlar(enrolments, lines):
	"""enrol_manual_enrol_users — yozish ham, suspend qilish ham shu orqali."""
	xato = 0
	for i in range(0, len(enrolments), ENROL_BATCH):
		chunk = enrolments[i : i + ENROL_BATCH]
		try:
			_call("enrol_manual_enrol_users", {"enrolments": chunk})
		except MoodleError as e:
			xato += len(chunk)
			lines.append(f"XATO yozilishda ({len(chunk)} ta): {e}")
	return xato


# ---------------------------------------------------------------- Sinxron yadrosi

def sync_kurslar(trigger="Qo'lda", limit=0):
	"""Kurs + kategoriya + yozilish sinxroni. Moodle Sync Log nomini qaytaradi."""
	s = _settings()
	if not s.enabled:
		frappe.throw("Moodle Settings: integratsiya yoqilmagan.")

	dry = bool(s.dry_run)
	limit = int(limit or 0)
	student_role = int(s.student_role or 5)
	teacher_role = int(s.teacher_role or 3)

	log = frappe.get_doc({
		"doctype": "Moodle Sync Log",
		"sync_type": "Kurs",
		"trigger_type": trigger,
		"status": "Ishlayapti",
		"started": now_datetime(),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

	lines = []
	stat = {"created": 0, "updated": 0, "hidden": 0, "skipped": 0, "errors": 0}
	if dry:
		lines.append("TEST REJIMI: Moodle'ga hech narsa yozilmaydi.")

	try:
		yil = _oquv_yili()
		juft = _juftliklar(yil)
		azolar = _guruh_azolari()
		users = _user_map()
		lines.append(
			f"O'quv yili: {yil} | jadvaldan {len(juft)} ta (guruh x fan) juftligi | "
			f"{len(azolar)} guruhda a'zolik | Moodle'da {len(users)} foydalanuvchi"
		)

		if limit > 0:
			kalitlar = sorted(juft)[:limit]
			juft = {k: juft[k] for k in kalitlar}
			lines.append(f"SINOV REJIMI: faqat {len(juft)} ta kurs bilan ishlanadi (limit={limit}).")

		# --- Kategoriyalar
		guruhlar = {v["guruh"] for v in juft.values()}
		kat = _kategoriya_taminla(yil, guruhlar, lines, dry)

		# --- Moodle'dagi mavjud kurslar va mahalliy bog'lanishlar
		mavjud = {} if dry else _moodle_kurslar()
		links = {
			d.name: d
			for d in frappe.get_all(
				"Moodle Course Link",
				fields=["name", "moodle_course_id", "shortname", "sync_hash",
						"enrolled_json", "guruh", "fan", "status"],
				limit_page_length=0,
			)
		}
		# Kalit o'zgarishi himoyasi (guruh nomi o'zgarsa dublikat kurs ochilmasin)
		by_ref = {(d.guruh, d.fan): d for d in links.values() if d.guruh and d.fan}
		lines.append(f"Moodle'da idnumber bo'yicha topilgan kurs: {len(mavjud)} | mahalliy bog'lanish: {len(links)}")

		yaratiladi, yangilanadi, yangi_links = [], [], {}

		for (guruh, fan), v in juft.items():
			key = v["idnumber"]
			cat_id = kat.get(guruh, 0)
			fullname = f"{v['guruh_nomi']} — {fan}"
			shortname = f"{yil} {guruh} {fan}"
			mdl = mavjud.get(key)
			link = links.get(key)
			shape = _hash({"f": fullname, "c": cat_id, "v": 1})

			if mdl:
				if link and link.sync_hash == shape and link.moodle_course_id == mdl.get("id"):
					stat["skipped"] += 1
				else:
					yangilanadi.append({
						"id": mdl["id"], "fullname": fullname,
						"categoryid": cat_id, "visible": 1,
					})
					stat["updated"] += 1
				kurs_id = mdl["id"]
			else:
				eski = by_ref.get((guruh, fan))
				if eski and eski.name != key and eski.moodle_course_id:
					# Kalit o'zgargan (masalan guruh nomi) — yangi kurs ochmaymiz
					lines.append(f"KALIT O'ZGARDI: {eski.name} -> {key} — mavjud kurs yangilanadi.")
					yangilanadi.append({
						"id": eski.moodle_course_id, "idnumber": key,
						"fullname": fullname, "categoryid": cat_id, "visible": 1,
					})
					kurs_id = eski.moodle_course_id
					stat["updated"] += 1
					if not dry:
						frappe.rename_doc("Moodle Course Link", eski.name, key,
										  force=True, ignore_permissions=True)
				else:
					yaratiladi.append({
						"fullname": fullname,
						"shortname": shortname,
						"categoryid": cat_id,
						"idnumber": key,
						"visible": 1,
					})
					kurs_id = 0
					stat["created"] += 1

			yangi_links[key] = {**v, "fullname": fullname, "shortname": shortname,
								"category_id": cat_id, "moodle_course_id": kurs_id,
								"sync_hash": shape}

		lines.append(f"Kurs rejasi: yaratish {stat['created']}, yangilash {stat['updated']}, o'zgarmagan {stat['skipped']}")

		if dry:
			for k in list(yangi_links)[:15]:
				v = yangi_links[k]
				lines.append(f"  [test] {v['fullname']} | o'qituvchi: {v.get('oqituvchi_nomi') or '—'} | {k}")
			if len(yangi_links) > 15:
				lines.append(f"  ... va yana {len(yangi_links) - 15} ta")
		else:
			for i in range(0, len(yaratiladi), COURSE_BATCH):
				chunk = yaratiladi[i : i + COURSE_BATCH]
				ok, xato = _kurs_yarat(chunk)
				for sn, cid in ok.items():
					key = next(k for k, v in yangi_links.items() if v["shortname"] == sn)
					yangi_links[key]["moodle_course_id"] = cid
				for sn, err in xato.items():
					stat["errors"] += 1
					stat["created"] -= 1
					lines.append(f"XATO kurs yaratishda {sn}: {err}")

			for i in range(0, len(yangilanadi), COURSE_BATCH):
				xato = _kurs_yangila(yangilanadi[i : i + COURSE_BATCH])
				for cid, err in xato.items():
					stat["errors"] += 1
					lines.append(f"XATO kurs yangilashda (id {cid}): {err}")

		# --- Yozilishlar (enrolment)
		enrolments, enrol_holat = [], {}
		for key, v in yangi_links.items():
			cid = v.get("moodle_course_id") or 0
			if not cid:
				continue

			kerak = {}
			for st in azolar.get(v["guruh"], []):
				uid = users.get(st)
				if uid:
					kerak[st] = (uid, student_role)
			o_kalit = _oqituvchi_kaliti(v.get("oqituvchi"))
			if o_kalit and users.get(o_kalit):
				kerak[o_kalit] = (users[o_kalit], teacher_role)

			eski = {}
			link = links.get(key)
			if link and link.enrolled_json:
				try:
					eski = json.loads(link.enrolled_json)
				except ValueError:
					eski = {}

			for kalit, (uid, rid) in kerak.items():
				if eski.get(kalit) != rid:
					enrolments.append({"roleid": rid, "userid": uid, "courseid": cid, "suspend": 0})

			# Chiqib ketganlar: o'chirmaymiz — yozilishini suspend qilamiz
			for kalit, rid in (eski or {}).items():
				if kalit not in kerak:
					uid = users.get(kalit)
					if uid:
						enrolments.append({"roleid": rid, "userid": uid, "courseid": cid, "suspend": 1})

			enrol_holat[key] = {k: r for k, (_u, r) in kerak.items()}
			v["student_count"] = sum(1 for _k, (_u, r) in kerak.items() if r == student_role)

		lines.append(f"Yozilish o'zgarishi: {len(enrolments)} ta")
		if dry:
			lines.append("  [test] yozilishlar yuborilmadi.")
		elif enrolments:
			stat["errors"] += _yozilishlar(enrolments, lines)

		# --- Jadvaldan chiqib ketgan kurslarni yashirish
		yoq_boldi = [
			d for k, d in links.items()
			if k not in yangi_links and d.moodle_course_id and d.status != "Yashirilgan"
		]
		if yoq_boldi and limit == 0:
			lines.append(f"Jadvalda qolmagan kurs: {len(yoq_boldi)} ta — yashiriladi (o'chirilmaydi).")
			if not dry:
				_kurs_yangila([{"id": d.moodle_course_id, "visible": 0} for d in yoq_boldi])
				for d in yoq_boldi:
					frappe.db.set_value("Moodle Course Link", d.name, "status", "Yashirilgan")
			stat["hidden"] = len(yoq_boldi)

		_saqla(yangi_links, enrol_holat, dry)

		log.db_set({
			"status": "Xato" if stat["errors"] and not (stat["created"] or stat["updated"]) else "Tugadi",
			"finished": now_datetime(),
			"created_count": stat["created"],
			"updated_count": stat["updated"],
			"suspended_count": stat["hidden"],
			"skipped_count": stat["skipped"],
			"error_count": stat["errors"],
			"details": "\n".join(lines)[:140000],
		})
		frappe.db.set_single_value(
			"Moodle Settings", "last_status",
			f"{'TEST — ' if dry else ''}Kurs: yaratildi {stat['created']}, yangilandi {stat['updated']}, "
			f"yashirildi {stat['hidden']}, xato {stat['errors']}",
		)
		frappe.db.commit()
		return log.name

	except Exception as e:
		frappe.db.rollback()
		lines.append(f"TO'XTADI: {e}")
		log.db_set({
			"status": "Xato",
			"finished": now_datetime(),
			"error_count": stat["errors"] + 1,
			"details": ("\n".join(lines) + "\n\n" + frappe.get_traceback())[:140000],
		})
		frappe.db.commit()
		frappe.log_error(title="Moodle kurs sync", message=frappe.get_traceback())
		raise


def _saqla(yangi_links, enrol_holat, dry):
	if dry:
		return
	for key, v in yangi_links.items():
		values = {
			"idnumber": key,
			"guruh": v["guruh"],
			"fan": v["fan"],
			"oqituvchi": v.get("oqituvchi"),
			"fullname": v["fullname"],
			"shortname": v["shortname"],
			"category_id": v.get("category_id") or 0,
			"moodle_course_id": v.get("moodle_course_id") or 0,
			"student_count": v.get("student_count") or 0,
			"sync_hash": v.get("sync_hash"),
			"status": "Faol",
			"last_synced": now_datetime(),
			"enrolled_json": json.dumps(enrol_holat.get(key, {}), ensure_ascii=False),
		}
		if frappe.db.exists("Moodle Course Link", key):
			doc = frappe.get_doc("Moodle Course Link", key)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "Moodle Course Link", **values}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- Kirish nuqtalari

@frappe.whitelist()
def preview_kurslar(limit=10):
	"""Moodle'ga murojaat qilmasdan nima yaratilishini ko'rsatadi."""
	frappe.only_for("System Manager")
	yil = _oquv_yili()
	juft = _juftliklar(yil)
	azolar = _guruh_azolari()
	users = _user_map()

	namuna = []
	for (guruh, fan), v in list(juft.items())[: int(limit)]:
		o_kalit = _oqituvchi_kaliti(v.get("oqituvchi"))
		namuna.append({
			"kurs": f"{v['guruh_nomi']} — {fan}",
			"kalit": v["idnumber"],
			"o_qituvchi": v.get("oqituvchi_nomi") or "—",
			"o_qituvchi_moodle'da": bool(o_kalit and users.get(o_kalit)),
			"o_quvchi": len(azolar.get(guruh, [])),
			"moodle'da_bor_o_quvchi": sum(1 for st in azolar.get(guruh, []) if users.get(st)),
		})

	oqituvchisiz = [
		f"{v['guruh_nomi']} — {f}" for (_g, f), v in juft.items()
		if (_oqituvchi_kaliti(v.get("oqituvchi")) or "") not in users
	]
	return {
		"o_quv_yili": yil,
		"kurs_soni": len(juft),
		"guruh_soni": len({v["guruh"] for v in juft.values()}),
		"moodle_foydalanuvchi": len(users),
		"o_qituvchisi_topilmagan_kurs": len(oqituvchisiz),
		"namuna": namuna,
	}


@frappe.whitelist()
def kurs_sync_now(limit=0):
	"""Moodle Settings tugmasi. Sinov darhol, to'liq sinxron fonda."""
	frappe.only_for("System Manager")
	limit = int(limit or 0)
	if limit > 0:
		return {"rejim": "darhol", "log": sync_kurslar(trigger="Qo'lda", limit=limit)}
	frappe.enqueue(
		"target_zenit.integrations.moodle_kurs.sync_kurslar",
		queue="long", timeout=3600, job_name="moodle_kurs_sync",
		trigger="Qo'lda", limit=0,
	)
	return {"rejim": "fonda"}


def daily_sync():
	"""Scheduler: foydalanuvchi sinxronidan keyin kurslar (hooks.py, 07:10)."""
	s = _settings()
	if not s.enabled:
		return
	sync_kurslar(trigger="Avto (07:00)")
