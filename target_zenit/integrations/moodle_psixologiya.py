# Copyright (c) 2026, Target Zenit
# Frappe -> Moodle: markaziy «Psixologiya xizmati» kursi sinxroni.
# Moodle tomoni: local_targetzenit/PSIXOLOG_ARXITEKTURA.md (2-3 bo'limlar).
#
# NIMA QILADI (har kuni 07:15, foydalanuvchi 07:00 va kurs 07:10 dan KEYIN):
#   1. `PSIXOLOGIYA::<yil>` kursini ta'minlaydi (<yil> kategoriyasida, ko'rinadigan).
#   2. Sinf guruhlarini ta'minlaydi: «1 A(full)» ... «11 B(hybrid)» + «Xodimlar».
#      SINF QOIDASI: Student Group `group_based_on='Activity'` VA nomi raqam
#      bilan boshlanadi — CHOICE/daraja (ENGLISH High ...) guruhlari chetda.
#   3. Barcha faol o'quvchini student rolida yozadi + o'z sinf guruhiga,
#      faol xodimlarni student rolida + «Xodimlar» guruhiga qo'shadi.
#   4. Psixologni (Moodle Settings -> psixolog) editingteacher qilib yozadi —
#      u shu kursda quiz/feedback yaratadi va natijalarni ko'radi.
#   5. Chiqib ketganlarni suspend qiladi (kurs sinxoni qoidasi: HECH QACHON
#      o'chirilmaydi, javob va baholar qoladi).
#
# GURUH A'ZOLIGI JONLI DIFF bilan: Moodle'dagi haqiqiy a'zolar o'qiladi va
# faqat farq yoziladi (har yurishda delete+insert YO'Q — tezlik qoidasi).
# Bu kurs TO'LIQ sinxron mulki: guruhlarga qo'lda qo'shilgan odam keyingi
# yurishda olib tashlanadi.
#
# YOZILISH HOLATI `Moodle Course Link` qatorida saqlanadi (idnumber =
# PSIXOLOGIYA::<yil>, guruh/fan BO'SH — shuning uchun kurs sinxoni
# (`jadvalsiz` bloki `not d.guruh` bilan) bu qatorga tegmaydi).

from __future__ import annotations

import json

import frappe
from frappe.utils import now_datetime

from target_zenit.integrations.moodle import (
	MOODLE_BOSHQARUV,
	MoodleError,
	_call,
	_settings,
)
from target_zenit.integrations.moodle_kurs import (
	ENROL_BATCH,
	_kategoriyalar,
	_oquv_yili,
	_user_map,
	_yozilishlar,
)

# local_targetzenit\psixolog::KURS_PREFIX / XODIM_GURUH bilan BIR XIL.
KURS_PREFIX = "PSIXOLOGIYA::"
XODIM_GURUH = "Xodimlar"

# Guruh a'zoligi bitta so'rovda nechtadan yoziladi (2 maydon x 150 = 300 << 5000)
GURUH_BATCH = 150


# ---------------------------------------------------------------- Frappe tomoni

def _sinflar(yil):
	"""{sinf guruhi nomi: [Student docname, ...]} — faqat 1-11 sinflar.

	Sinf = `group_based_on='Activity'` VA nomi raqam bilan boshlanadi
	(«7 A(full)»). CHOICE ham Activity, lekin harf bilan boshlanadi;
	ENGLISH/MATH daraja guruhlari esa Course asosida — ikkisi ham chetda.
	"""
	rows = frappe.db.sql(
		"""
		SELECT sg.name AS guruh, sgs.student
		FROM `tabStudent Group` sg
		INNER JOIN `tabStudent Group Student` sgs ON sgs.parent = sg.name
		INNER JOIN `tabStudent` s ON s.name = sgs.student
		WHERE sg.group_based_on = 'Activity'
		  AND sg.academic_year = %s
		  AND sg.disabled = 0
		  AND sg.name REGEXP '^[0-9]'
		  AND sgs.active = 1
		  AND s.enabled = 1
		  AND IFNULL(s.date_of_leaving, '0001-01-01') <= '0001-01-01'
		""",
		(yil,),
		as_dict=True,
	)
	sinf = {}
	for r in rows:
		sinf.setdefault(r.guruh, []).append(r.student)
	return sinf


def _xodimlar():
	"""Faol xodimlar (Employee ID ro'yxati) — «Xodimlar» guruhiga."""
	return [
		r.name
		for r in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name"])
	]


# ---------------------------------------------------------------- Moodle tomoni

def _kurs_taminla(yil, lines, dry):
	"""Markaziy kursni topadi yoki yaratadi. Moodle kurs id (yoki dry'da -1)."""
	key = f"{KURS_PREFIX}{yil}"

	res = _call("core_course_get_courses_by_field", {"field": "idnumber", "value": key})
	kurslar = (res or {}).get("courses") or []
	if kurslar:
		return int(kurslar[0]["id"]), key

	# Kategoriya: <yil> ildizi (kurs sinxoni yaratadi; yo'q bo'lsa o'zimiz).
	kategoriyalar = _kategoriyalar()
	yil_id = kategoriyalar.get(f"TZ-AY-{yil}")
	if not yil_id:
		if dry:
			lines.append(f"  [test] kategoriya yaratiladi: {yil}")
			yil_id = -1
		else:
			res = _call("core_course_create_categories", {
				"categories": [{"name": yil, "idnumber": f"TZ-AY-{yil}", "parent": 0}],
			})
			yil_id = res[0]["id"]
			lines.append(f"Kategoriya yaratildi: {yil} (id {yil_id})")

	if dry:
		lines.append(f"  [test] kurs yaratiladi: Psixologiya xizmati ({key})")
		return -1, key

	res = _call("core_course_create_courses", {
		"courses": [{
			"fullname": "Psixologiya xizmati",
			"shortname": f"PSIXOLOGIYA {yil}",
			"categoryid": yil_id,
			"idnumber": key,
			# KO'RINADIGAN kurs: o'quvchi testni shu kurs orqali yechadi
			# (markaziy baholash kursidan farqi shu).
			"visible": 1,
			"summary": "Maktab psixologi test va so'rovnomalari. "
			"Guruhlar = sinflar, Frappe'dan avtomatik yuritiladi.",
			"summaryformat": 1,
		}],
	})
	cid = int(res[0]["id"])
	lines.append(f"Kurs yaratildi: Psixologiya xizmati (id {cid}, {key})")
	return cid, key


def _guruhlar_taminla(cid, kerakli_nomlar, yil, lines, dry):
	"""Kursdagi guruhlarni ta'minlaydi. {guruh nomi: moodle group id}."""
	mavjud = {}
	for g in _call("core_group_get_course_groups", {"courseid": cid}) or []:
		mavjud[g["name"]] = int(g["id"])

	yoq = [n for n in kerakli_nomlar if n not in mavjud]
	if yoq:
		if dry:
			lines.append(f"  [test] {len(yoq)} ta guruh yaratiladi: {', '.join(yoq[:5])} ...")
			for n in yoq:
				mavjud[n] = -1
		else:
			res = _call("core_group_create_groups", {
				"groups": [
					{
						"courseid": cid,
						"name": n,
						"idnumber": f"PSIX::{yil}::{n}",
						"description": "",
						"descriptionformat": 1,
					}
					for n in yoq
				],
			})
			for g in res or []:
				mavjud[g["name"]] = int(g["id"])
			lines.append(f"Guruhlar yaratildi: {len(yoq)} ta")
	return mavjud


def _azolik_diff(guruh_ids, kerak_azolik, users_teskari, lines, dry):
	"""Guruh a'zoligini JONLI holat bilan solishtirib, faqat farqni yozadi.

	kerak_azolik: {groupid: set(moodle userid)}.
	users_teskari: {moodle userid: link kaliti} — faqat BIZ boshqaradigan
	odamlar olib tashlanadi; qo'lda yaratilgan boshqa akkauntga tegilmaydi.
	"""
	ids = [g for g in guruh_ids.values() if g > 0]
	hozirgi = {g: set() for g in ids}
	if ids:
		for r in _call("core_group_get_group_members", {"groupids": ids}) or []:
			hozirgi[int(r["groupid"])] = {int(u) for u in r.get("userids") or []}

	qoshish, ochirish = [], []
	for gid in ids:
		kerak = kerak_azolik.get(gid, set())
		bor = hozirgi.get(gid, set())
		for uid in kerak - bor:
			qoshish.append({"groupid": gid, "userid": uid})
		for uid in bor - kerak:
			if uid in users_teskari:
				ochirish.append({"groupid": gid, "userid": uid})

	lines.append(f"Guruh a'zoligi: +{len(qoshish)} / -{len(ochirish)}")
	if dry:
		return

	for nom, royxat in (("core_group_add_group_members", qoshish),
						 ("core_group_delete_group_members", ochirish)):
		for i in range(0, len(royxat), GURUH_BATCH):
			chunk = royxat[i : i + GURUH_BATCH]
			try:
				_call(nom, {"members": chunk})
			except MoodleError as e:
				# Partiya atomar — aybdorni ajratamiz (yozilish naqshi).
				if len(chunk) == 1:
					lines.append(f"XATO guruh a'zoligida {chunk[0]}: {e}")
					continue
				for bitta in chunk:
					try:
						_call(nom, {"members": [bitta]})
					except MoodleError as e2:
						lines.append(f"XATO guruh a'zoligida {bitta}: {e2}")


def _holat_saqla(key, cid, kerak, student_role, dry):
	"""Yozilish holatini Moodle Course Link qatorida saqlaydi.

	`guruh`/`fan` ATAYLAB BO'SH — kurs sinxonining `jadvalsiz` bloki
	`not d.guruh` sharti bilan bu qatorni chetlab o'tadi, ya'ni u bizning
	kursni yashirishga urinmaydi.
	"""
	if dry:
		return
	values = {
		"idnumber": key,
		"fullname": "Psixologiya xizmati",
		"shortname": key.replace("::", " "),
		"moodle_course_id": cid,
		"student_count": sum(1 for _u, r, _g in kerak.values() if r == student_role),
		"last_synced": now_datetime(),
		"enrolled_json": json.dumps(
			{k: r for k, (_u, r, _g) in kerak.items()}, ensure_ascii=False
		),
	}
	if frappe.db.exists("Moodle Course Link", key):
		frappe.db.set_value("Moodle Course Link", key, values, update_modified=False)
	else:
		frappe.get_doc({
			"doctype": "Moodle Course Link", "status": "Faol", **values,
		}).insert(ignore_permissions=True)


# ---------------------------------------------------------------- Sinxron yadrosi

def sync_psixologiya(trigger="Qo'lda"):
	"""Markaziy psixologiya kursi: kurs + guruhlar + yozilishlar. Log nomini qaytaradi."""
	s = _settings()
	if not s.enabled:
		frappe.throw("Moodle Settings: integratsiya yoqilmagan.")
	if not s.get("sync_psixologiya"):
		frappe.throw("Moodle Settings: «Psixologiya kursini yuritish» yoqilmagan.")

	dry = bool(s.dry_run)
	student_role = int(s.student_role or 5)
	teacher_role = int(s.teacher_role or 3)

	log = frappe.get_doc({
		"doctype": "Moodle Sync Log",
		"sync_type": "Psixologiya",
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
		users = _user_map()
		sinflar = _sinflar(yil)
		xodimlar = _xodimlar()
		psixolog = (s.get("psixolog") or "").strip()

		lines.append(
			f"O'quv yili: {yil} | sinf guruhlari: {len(sinflar)} | "
			f"faol xodim: {len(xodimlar)} | Moodle'da {len(users)} foydalanuvchi | "
			f"psixolog: {psixolog or 'TANLANMAGAN'}"
		)
		if not sinflar:
			frappe.throw("Birorta sinf guruhi topilmadi (Activity + raqam bilan boshlanadigan).")

		# --- 1. Kurs
		cid, key = _kurs_taminla(yil, lines, dry)

		# --- 2. Kimlar kerak: {link kaliti: (moodle uid, roleid, guruh nomi)}
		kerak = {}
		linksiz = 0
		for sinf, studlar in sinflar.items():
			for st in studlar:
				uid = users.get(st)
				if not uid:
					linksiz += 1
					continue
				kerak[st] = (uid, student_role, sinf)
		for emp in xodimlar:
			uid = users.get(emp)
			if uid and emp not in kerak:
				kerak[emp] = (uid, student_role, XODIM_GURUH)
		# Psixolog — O'QITUVCHI (xodim yozuvining ustiga yoziladi); guruhsiz.
		if psixolog:
			uid = users.get(psixolog)
			if uid:
				kerak[psixolog] = (uid, teacher_role, None)
			else:
				lines.append(f"DIQQAT: psixolog {psixolog} Moodle'da topilmadi — "
					"foydalanuvchi sinxoni (07:00) o'tganmi?")
		if linksiz:
			lines.append(f"Moodle akkaunti yo'q o'quvchi: {linksiz} ta — chetda qoldi.")

		# --- 3. Yozilishlar: hammasi idempotent (suspend=0), ketganlar suspend=1.
		enrolments = [
			{"roleid": rid, "userid": uid, "courseid": cid, "suspend": 0}
			for _k, (uid, rid, _g) in kerak.items()
		]
		stat["created"] = len(enrolments)

		eski = {}
		if frappe.db.exists("Moodle Course Link", key):
			try:
				eski = json.loads(
					frappe.db.get_value("Moodle Course Link", key, "enrolled_json") or "{}"
				)
			except ValueError:
				eski = {}
		if s.suspend_on_leave:
			for k, rid in eski.items():
				if k in kerak:
					continue
				uid = users.get(k)
				if uid:
					enrolments.append({
						"roleid": int(rid) or student_role, "userid": uid,
						"courseid": cid, "suspend": 1,
					})
					stat["hidden"] += 1

		if dry:
			lines.append(f"  [test] yozilish: {stat['created']} faol, {stat['hidden']} suspend")
		else:
			xato_kurslar = _yozilishlar(enrolments, lines)
			if xato_kurslar:
				stat["errors"] += 1

		# --- 4. Guruhlar va a'zolik (jonli diff)
		guruh_nomlar = [*sorted(sinflar), XODIM_GURUH]
		guruh_ids = {}
		if cid != -1:
			guruh_ids = _guruhlar_taminla(cid, guruh_nomlar, yil, lines, dry)
		else:
			lines.append(f"  [test] guruhlar yaratiladi: {len(guruh_nomlar)} ta")

		if cid != -1 and guruh_ids:
			kerak_azolik = {}
			for _k, (uid, _rid, guruh) in kerak.items():
				gid = guruh_ids.get(guruh) if guruh else None
				if gid and gid > 0:
					kerak_azolik.setdefault(gid, set()).add(uid)
			users_teskari = {uid: k for k, uid in users.items()}
			_azolik_diff(guruh_ids, kerak_azolik, users_teskari, lines, dry)

		# --- 5. Holat
		_holat_saqla(key, cid, kerak, student_role, dry)

		log.db_set({
			"status": "Tugadi",
			"finished": now_datetime(),
			"created_count": stat["created"],
			"suspended_count": stat["hidden"],
			"skipped_count": linksiz,
			"error_count": stat["errors"],
			"details": "\n".join(lines)[:140000],
		})
		frappe.db.set_single_value(
			"Moodle Settings", "last_status",
			f"{'TEST — ' if dry else ''}Psixologiya: yozildi {stat['created']}, "
			f"suspend {stat['hidden']}, xato {stat['errors']}",
		)
		frappe.db.commit()
		return log.name

	except Exception:
		frappe.db.rollback()
		log.db_set({
			"status": "Xato",
			"finished": now_datetime(),
			"error_count": stat["errors"] + 1,
			"details": ("\n".join(lines) + "\n\n" + frappe.get_traceback())[:140000],
		})
		frappe.db.commit()
		frappe.log_error(title="Moodle psixologiya sync", message=frappe.get_traceback())
		raise


# ---------------------------------------------------------------- Kirish nuqtalari

@frappe.whitelist()
def preview(limit=10):
	"""Moodle'ga MUROJAAT QILMASDAN nima yuborilishini ko'rsatadi."""
	frappe.only_for(MOODLE_BOSHQARUV)
	yil = _oquv_yili()
	users = _user_map()
	sinflar = _sinflar(yil)
	xodimlar = _xodimlar()
	s = _settings()

	lines = [
		f"Kurs: {KURS_PREFIX}{yil} (Psixologiya xizmati)",
		f"Psixolog: {s.get('psixolog') or 'TANLANMAGAN — Moodle Settings da tanlang'}",
		f"Sinf guruhlari ({len(sinflar)}):",
	]
	for nom in sorted(sinflar)[: int(limit)]:
		azolar = sinflar[nom]
		bor = sum(1 for st in azolar if st in users)
		lines.append(f"  {nom}: {len(azolar)} o'quvchi ({bor} tasida Moodle akkaunt)")
	if len(sinflar) > int(limit):
		lines.append(f"  ... va yana {len(sinflar) - int(limit)} ta sinf")
	bor = sum(1 for e in xodimlar if e in users)
	lines.append(f"{XODIM_GURUH}: {len(xodimlar)} xodim ({bor} tasida Moodle akkaunt)")
	return "\n".join(lines)


@frappe.whitelist()
def sync_now():
	"""Qo'lda ishga tushirish (Moodle Settings sahifasidan yoki bench execute)."""
	frappe.only_for(MOODLE_BOSHQARUV)
	return sync_psixologiya(trigger="Qo'lda")


def daily_sync():
	"""Cron 07:15 — yoqilgan bo'lsagina, jim."""
	s = _settings()
	if not (s.enabled and s.get("sync_psixologiya")):
		return
	try:
		sync_psixologiya(trigger="Avto")
	except Exception:
		# Xato log'da (Moodle Sync Log + Error Log) — cron zanjirini buzmaymiz.
		pass
