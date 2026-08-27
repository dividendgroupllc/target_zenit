# Copyright (c) 2026, Target Zenit
# eduvisit (yunusobod.eduvisit.uz) API v7 -> Frappe Education sinxronizatsiyasi.
#
# Manba: EduVisit API v7 (read-only, GET, sahifalangan). Auth: X-API-Key.
#   GET /students/?page=N&page_size=200 -> o'quvchilar (ota-onasi ICHIDA: parents[])
#   GET /parents/                       -> ota-onalar (kerak bo'lsa)
#   GET /attendance/today/              -> bugungi turniket (keldi/ketdi)
# Nishon: standart Education doctype'lari (Student, Guardian, Student Group).
# Custom maydonlar (sync kaliti): Student.custom_eduvisit_id, Guardian.custom_eduvisit_id.
#
# Ishga tushirish:
#   - Qo'lda: Eduvisit Settings -> "Sync Now" tugmasi -> sync_now()
#   - Avtomatik: har kuni ertalab scheduler -> daily_sync()

import json
import re

import frappe
import requests
from frappe.utils import add_days, get_datetime, now_datetime, today

SETTINGS = "Eduvisit Settings"
STUDENT_ID_FIELD = "custom_eduvisit_id"
GUARDIAN_ID_FIELD = "custom_eduvisit_id"
TIMEOUT = 60
PAGE_SIZE = 200  # v7 maksimum

# eduvisit relation_code -> Frappe Student Guardian.relation (Select)
RELATION_MAP = {"father": "Father", "mother": "Mother"}
GENDER_MAP = {"male": "Male", "female": "Female"}
# eduvisit direction -> Terminal Checkin.direction
DIRECTION_MAP = {"in": "Kirdi", "out": "Chiqdi"}


# ---------------------------------------------------------------- HTTP qatlami

def _settings():
	return frappe.get_cached_doc(SETTINGS)


def _headers(s):
	token = s.get_password("api_token") if s.api_token else ""
	scheme = s.auth_scheme or "X-API-Key"
	if scheme == "X-API-Key":
		return {"X-API-Key": token}
	return {"Authorization": f"{scheme} {token}"}


def _get(path, params=None):
	s = _settings()
	if not (s.base_url and s.api_token):
		frappe.throw("Eduvisit Settings: API base URL yoki token kiritilmagan.")
	url = s.base_url.rstrip("/") + "/" + path.lstrip("/")
	resp = requests.get(url, headers=_headers(s), params=params, timeout=TIMEOUT)
	resp.raise_for_status()
	return resp.json()


def _paged(path, params=None):
	"""v7 sahifalangan ro'yxatini to'liq aylanib chiqadi. Har bir yozuvni yield qiladi."""
	page = 1
	while True:
		q = dict(params or {})
		q["page"] = page
		q["page_size"] = PAGE_SIZE
		data = _get(path, q)
		results = data.get("results") or []
		yield from results
		if not data.get("next") or not results:
			break
		page += 1


# ------------------------------------------------------------ Yordamchi funksiyalar

def _clean_phone(value):
	digits = re.sub(r"\D", "", value or "")
	return ("+" + digits) if digits else ""


def ensure_custom_fields():
	"""Student va Guardian'da eduvisit kalitini (bir martalik) yaratadi. Idempotent."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Student": [
				{
					"fieldname": STUDENT_ID_FIELD,
					"label": "Eduvisit ID",
					"fieldtype": "Data",
					"unique": 1,
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "naming_series",
					"description": "eduvisit external_id (sync kaliti). Qo'lda o'zgartirilmasin.",
				}
			],
			"Guardian": [
				{
					"fieldname": GUARDIAN_ID_FIELD,
					"label": "Eduvisit ID",
					"fieldtype": "Data",
					"unique": 1,
					"read_only": 1,
					"no_copy": 1,
					"insert_after": "guardian_name",
					"description": "eduvisit parent id (sync kaliti). Qo'lda o'zgartirilmasin.",
				}
			],
		},
		ignore_validate=True,
	)


def _get_or_create_group(group_name, academic_year):
	if not group_name:
		return None
	existing = frappe.db.get_value("Student Group", {"student_group_name": group_name})
	if existing:
		return existing
	grp = frappe.new_doc("Student Group")
	grp.student_group_name = group_name
	# "Activity" — Program/Course talab qilmaydi (sinf ro'yxati sifatida).
	grp.group_based_on = "Activity"
	if academic_year:
		grp.academic_year = academic_year
	grp.flags.ignore_mandatory = True
	grp.insert(ignore_permissions=True)
	return grp.name


def _ensure_group_membership(group, student_name, student_full, active):
	if not group:
		return
	if frappe.db.exists("Student Group Student", {"parent": group, "student": student_name}):
		return
	grp = frappe.get_doc("Student Group", group)
	grp.append(
		"students",
		{"student": student_name, "student_name": student_full, "active": 1 if active else 0},
	)
	grp.flags.ignore_mandatory = True
	grp.save(ignore_permissions=True)


# --------------------------------------------------------------- Guardian (ota-ona)

def _upsert_guardian(p):
	"""eduvisit parent (student ichidagi) -> Guardian. eduvisit id bo'yicha dedup."""
	if not p or not p.get("id"):
		return None, None
	ext = str(p["id"])
	full = p.get("full_name") or "Ota-ona"
	phone = _clean_phone(p.get("phone"))
	email = p.get("email") or ""

	name = frappe.db.get_value("Guardian", {GUARDIAN_ID_FIELD: ext})
	if not name and phone:
		name = frappe.db.get_value("Guardian", {"mobile_number": phone})

	guardian = frappe.get_doc("Guardian", name) if name else frappe.new_doc("Guardian")
	guardian.set(GUARDIAN_ID_FIELD, ext)
	guardian.guardian_name = full
	if phone:
		guardian.mobile_number = phone
	if email:
		guardian.email_address = email
	guardian.flags.ignore_mandatory = True
	if guardian.is_new():
		guardian.insert(ignore_permissions=True)
	else:
		guardian.save(ignore_permissions=True)
	return guardian.name, guardian.guardian_name


def _sync_student_guardians(student_doc, parents):
	"""Student.guardians jadvalini eduvisit parents[] bo'yicha to'ldiradi."""
	existing = {row.guardian for row in (student_doc.guardians or [])}
	changed = False
	for p in parents or []:
		gname, gtitle = _upsert_guardian(p)
		if not gname or gname in existing:
			continue
		relation = RELATION_MAP.get((p.get("relation_code") or "").lower(), "Others")
		student_doc.append(
			"guardians",
			{"guardian": gname, "guardian_name": gtitle, "relation": relation},
		)
		existing.add(gname)
		changed = True
	if changed:
		student_doc.flags.ignore_mandatory = True
		student_doc.save(ignore_permissions=True)


# ---------------------------------------------------------------- O'quvchi (Student)

def upsert_student(item, academic_year, create_guardians):
	"""eduvisit o'quvchi yozuvini Student'ga upsert qiladi. (name, is_new) qaytaradi."""
	ext = item.get("external_id")
	if not ext:
		return None, False

	name = frappe.db.get_value("Student", {STUDENT_ID_FIELD: ext})
	is_new = not name
	doc = frappe.new_doc("Student") if is_new else frappe.get_doc("Student", name)

	doc.set(STUDENT_ID_FIELD, ext)
	doc.first_name = item.get("first_name") or ""
	doc.middle_name = item.get("middle_name") or ""
	doc.last_name = item.get("last_name") or ""
	doc.student_name = item.get("full_name") or " ".join(
		x for x in [doc.first_name, doc.last_name] if x
	)

	if item.get("birth_date"):
		doc.date_of_birth = item.get("birth_date")

	gender = GENDER_MAP.get((item.get("gender") or "").lower())
	if gender:
		doc.gender = gender

	if _settings().sync_photos and item.get("photo_url"):
		doc.image = item.get("photo_url")

	# Faollik / maktabdan chiqish
	active = bool(item.get("is_active")) and not item.get("is_archived")
	doc.enabled = 1 if active else 0
	if active:
		doc.date_of_leaving = None
	elif not doc.date_of_leaving:
		doc.date_of_leaving = today()
		if not doc.reason_for_leaving:
			doc.reason_for_leaving = "eduvisit: nofaol"

	doc.flags.ignore_mandatory = True
	if is_new:
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	# Sinf -> Student Group
	# Qo'lda tayinlangan guruh (custom_sinf_guruh) ustuvor — sync unga tegmaydi,
	# faqat guruhi hali yo'q (yangi) o'quvchiga eduvisit'dagi guruhni qo'yadi.
	if not doc.get("custom_sinf_guruh"):
		group = _get_or_create_group(item.get("group_name"), academic_year)
		if group:
			_ensure_group_membership(group, doc.name, doc.student_name, active)
			doc.db_set("custom_sinf_guruh", group, update_modified=False)

	# Ota-onalar (v7'da o'quvchi ichida keladi — alohida so'rov shart emas)
	if create_guardians and item.get("parents"):
		doc = frappe.get_doc("Student", doc.name)
		_sync_student_guardians(doc, item.get("parents"))

	return doc.name, is_new


# ------------------------------------------------------------------- Asosiy oqim

def run_sync():
	"""To'liq sinxronizatsiya. Natija lug'atini qaytaradi."""
	ensure_custom_fields()
	s = _settings()
	academic_year = s.default_academic_year
	create_guardians = bool(s.create_guardians)

	created = updated = total = 0
	errors = []

	for item in _paged("/students/"):
		total += 1
		try:
			name, is_new = upsert_student(item, academic_year, create_guardians)
			if not name:
				continue
			created += 1 if is_new else 0
			updated += 0 if is_new else 1
			frappe.db.commit()
		except Exception as exc:
			frappe.db.rollback()
			errors.append(f"{item.get('external_id')}: {exc}")
			frappe.log_error(frappe.get_traceback(), "Eduvisit sync (o'quvchi)")

	result = {"created": created, "updated": updated, "errors": errors, "total": total}
	summary = f"{now_datetime():%Y-%m-%d %H:%M} — jami {total}, yangi {created}, yangilangan {updated}, xato {len(errors)}"
	s.db_set("last_sync", now_datetime(), update_modified=False)
	s.db_set("last_result", summary, update_modified=False)
	frappe.db.commit()
	return result


# ---------------------------------------------------- Turniket (kirdi/chiqdi)

def _student_name_by_ext(ext):
	"""eduvisit student external_id -> Frappe Student.name (yoki None)."""
	if not ext:
		return None
	return frappe.db.get_value("Student", {STUDENT_ID_FIELD: ext})


def _upsert_checkin(ev):
	"""eduvisit xom turniket hodisasini Terminal Checkin'ga yozadi. event id bo'yicha dedup."""
	eid = ev.get("id")
	if eid is None:
		return False
	ext_event = f"ev-{eid}"
	ext_student = ev.get("student_external_id")
	student = _student_name_by_ext(ext_student)

	existing = frappe.db.get_value(
		"Terminal Checkin", {"external_event_id": ext_event}, ["name", "student"], as_dict=True
	)
	if existing:
		# O'z-o'zini tuzatish: check-in o'quvchidan oldin kelgan bo'lsa, endi bog'laymiz.
		if student and not existing.student:
			frappe.db.set_value(
				"Terminal Checkin", existing.name,
				{"student": student, "person_type": "O'quvchi"}, update_modified=False,
			)
		return False

	device = ev.get("device") or {}
	event_time = f"{ev.get('date')} {ev.get('time')}".strip()

	doc = frappe.get_doc(
		{
			"doctype": "Terminal Checkin",
			"external_event_id": ext_event,
			"person_id": ext_student or str(ev.get("student_id") or ""),
			"person_name": ev.get("student_full_name"),
			"person_type": "O'quvchi" if student else "Noma'lum",
			"student": student,
			"event_time": get_datetime(event_time),
			"direction": DIRECTION_MAP.get((ev.get("direction") or "").lower(), ""),
			"terminal": device.get("name"),
			"event_code": "eduvisit",
			"raw_data": json.dumps(ev, ensure_ascii=False),
		}
	)
	doc.flags.ignore_mandatory = True
	doc.insert(ignore_permissions=True)
	return True


def sync_attendance(date=None, date_from=None, date_to=None):
	"""eduvisit turniket hodisalarini Terminal Checkin'ga tortadi, keyin
	har bir kun uchun Student Attendance'ni (Present) qayta hisoblaydi."""
	from target_zenit.attendance import sync_student_attendance

	params = {}
	if date_from and date_to:
		params["date_from"], params["date_to"] = date_from, date_to
	else:
		params["date"] = date or today()

	created = 0
	dates = set()
	for ev in _paged("/attendance/", params):
		try:
			if _upsert_checkin(ev):
				created += 1
			if ev.get("date"):
				dates.add(ev.get("date"))
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Eduvisit sync (turniket)")

	att = {"created": 0, "already": 0}
	for d in sorted(dates):
		r = sync_student_attendance(d)
		att["created"] += r.get("created", 0)
		att["already"] += r.get("already", 0)

	return {"checkins_new": created, "days": sorted(dates), "attendance_created": att["created"]}


# --------------------------------------------------------------- Kirish nuqtalari

@frappe.whitelist()
def sync_attendance_now(date=None):
	"""'Turniketni tortish' tugmasi — bugungi (yoki berilgan kun) kirdi/chiqdi."""
	frappe.only_for("System Manager")
	return sync_attendance(date=date)


def hourly_attendance():
	"""Scheduler (har soat): bugungi turniket hodisalarini tortadi (faqat 'Yoqilgan')."""
	s = _settings()
	if not s.enabled:
		return
	sync_attendance(date=today())


@frappe.whitelist()
def sync_now():
	"""Eduvisit Settings'dagi 'Sync Now' tugmasi shu funksiyani chaqiradi."""
	frappe.only_for("System Manager")
	return run_sync()


@frappe.whitelist()
def test_connection():
	"""Ulanishni tekshiradi: API'dan o'quvchilar sonini qaytaradi."""
	frappe.only_for("System Manager")
	data = _get("/students/", {"page": 1, "page_size": 1})
	return {"ok": True, "count": data.get("count")}


def daily_sync():
	"""Har kuni ertalab scheduler chaqiradi (faqat 'Yoqilgan' bo'lsa).
	O'quvchilar + kecha/bugungi turniket (kechagi kech kelgan hodisalarni ham to'ldiradi)."""
	s = _settings()
	if not s.enabled:
		return
	run_sync()
	sync_attendance(date_from=add_days(today(), -1), date_to=today())
