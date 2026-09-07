# Copyright (c) 2026, Target Zenit
# eduvisit (yunusobod.eduvisit.uz) API v7 -> Frappe: FAQAT TURNIKET (kirdi/chiqdi).
#
# MUHIM (2026-09-07, foydalanuvchi qarori): API orqali O'QUVCHI MA'LUMOTLARI
# SINXRONLANMAYDI — yaratilmaydi, yangilanmaydi, o'chirilmaydi. Sabab: operatorlar
# o'quvchi ismlarini to'liq yozib chiqishgan va guruhlarni qo'lda yuritishadi;
# eski sync ularni eduvisit'dagi holatiga qaytarib yuborar edi.
# Ota-ona (Guardian) sync ham o'chirilgan. Student Group sync ham YO'Q.
#
# API'dan keladigan YAGONA ma'lumot — turniket hodisalari:
#   GET /attendance/?date=...&page=N -> Terminal Checkin (dedup: external_event_id)
#   -> target_zenit.attendance.sync_student_attendance -> Student Attendance (Present)
# Bular Student hujjatining O'ZIGA tegmaydi (faqat mavjud o'quvchiga bog'lanadi,
# bog'lash uchun kalit: Student.custom_eduvisit_id — qo'lda saqlanadi).
#
# Ishga tushirish:
#   - Qo'lda: Eduvisit Settings -> "Turniketni tortish (bugun)" -> sync_attendance_now()
#   - Avtomatik: scheduler hourly_attendance() / daily_sync() (faqat 'Yoqilgan' bo'lsa)

import json

import frappe
import requests
from frappe.utils import add_days, get_datetime, now_datetime, today

SETTINGS = "Eduvisit Settings"
STUDENT_ID_FIELD = "custom_eduvisit_id"
TIMEOUT = 60
PAGE_SIZE = 200  # v7 maksimum

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


# ---------------------------------------------------- Turniket (kirdi/chiqdi)

def _student_name_by_ext(ext):
	"""eduvisit student external_id -> Frappe Student.name (yoki None). Faqat O'QISH."""
	if not ext:
		return None
	return frappe.db.get_value("Student", {STUDENT_ID_FIELD: ext})


def _upsert_checkin(ev):
	"""eduvisit xom turniket hodisasini Terminal Checkin'ga yozadi. event id bo'yicha dedup.
	Student hujjatiga TEGMAYDI — faqat checkin'ni mavjud o'quvchiga bog'laydi."""
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

	# Settings'da oxirgi sync holatini ko'rsatib turamiz (faqat turniket)
	try:
		s = _settings()
		summary = (
			f"{now_datetime():%Y-%m-%d %H:%M} — turniket: yangi {created} ta o'tish, "
			f"davomat (Present) {att['created']} ta. O'quvchi sync O'CHIRILGAN."
		)
		s.db_set("last_sync", now_datetime(), update_modified=False)
		s.db_set("last_result", summary, update_modified=False)
		frappe.db.commit()
	except Exception:
		pass

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
	"""ESKI 'Sync Now' tugmasi. O'quvchi sync BUTUNLAY O'CHIRILGAN — ataylab xato beradi,
	toki eski keshdagi tugma bosilsa ham hech narsa o'zgarmasin."""
	frappe.only_for("System Manager")
	frappe.throw(
		"O'quvchi ma'lumotlari endi eduvisit API'dan SINXRONLANMAYDI "
		"(ism/guruh/holat operatorlar tomonidan qo'lda yuritiladi). "
		"API'dan faqat turniket kirdi/chiqdi ma'lumotlari tortiladi — "
		"buning uchun \"Turniketni tortish\" tugmasidan foydalaning."
	)


@frappe.whitelist()
def test_connection():
	"""Ulanishni tekshiradi: API'dan bugungi turniket hodisalari sonini qaytaradi."""
	frappe.only_for("System Manager")
	data = _get("/attendance/", {"page": 1, "page_size": 1, "date": today()})
	return {"ok": True, "count": data.get("count")}


def daily_sync():
	"""Har kuni ertalab scheduler chaqiradi (faqat 'Yoqilgan' bo'lsa).
	FAQAT turniket: kecha/bugungi hodisalar (kech kelganlarini ham to'ldiradi).
	O'quvchi ma'lumotlari ataylab sinxronlanmaydi."""
	s = _settings()
	if not s.enabled:
		return
	sync_attendance(date_from=add_days(today(), -1), date_to=today())
