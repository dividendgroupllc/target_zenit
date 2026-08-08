# Copyright (c) 2026, Target Zenit
# Hikvision yuz-tanish terminallaridan o'tish xabarlarini qabul qilish.
# Terminal (ISAPI HTTP Host Notification) har bir o'tishni shu manzilga yuboradi:
#   /api/method/target_zenit.integrations.hikvision.listen?token=MAXFIY_KALIT
# Format: multipart/form-data (event_log JSON + rasm) yoki raw XML/JSON.

import json
import xml.etree.ElementTree as ET

import frappe
from frappe.utils import now_datetime
from werkzeug.wrappers import Response


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def listen(**kwargs):
	settings = frappe.get_cached_doc("Hikvision Settings")
	if not settings.enabled:
		return Response("disabled", status=200)

	token = frappe.request.args.get("token") or kwargs.get("token")
	if not settings.secret_token or token != settings.secret_token:
		return Response("forbidden", status=403)

	if frappe.request.method != "POST":
		return Response("ok", status=200)

	event, picture = extract_event()
	if event:
		try:
			save_checkin(event, picture)
			frappe.db.set_single_value("Hikvision Settings", "last_event", now_datetime())
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="Hikvision webhook error", message=frappe.get_traceback())

	# Terminal 200 kutadi; xato bo'lsa ham 200 qaytaramiz —
	# hodisa terminal xotirasida baribir saqlanadi, qayta yuborish bo'roni kerak emas.
	return Response("ok", status=200)


def extract_event():
	"""So'rovdan hodisa (dict) va rasmni (bytes) ajratib oladi.

	Hikvision uch xil ko'rinishda yuborishi mumkin:
	1. multipart/form-data: "event_log" qismi (JSON) + "Picture" qismi (JPEG)
	2. raw JSON body
	3. raw XML body (EventNotificationAlert)
	Heartbeat va shaxssiz hodisalar uchun None qaytadi.
	"""
	req = frappe.request
	candidates = []
	picture = None

	if req.files:
		for key in req.files:
			for f in req.files.getlist(key):
				data = f.read()
				if not data:
					continue
				mimetype = (f.mimetype or "").lower()
				if key.lower().startswith("picture") or mimetype.startswith("image/"):
					picture = data
				else:
					candidates.append(data)
	if req.form:
		for val in req.form.values():
			if val:
				candidates.append(val.encode() if isinstance(val, str) else val)
	if req.data:
		candidates.append(req.data)

	for raw in candidates:
		payload = parse_payload(raw)
		if payload:
			event = normalize_event(payload)
			if event:
				return event, picture
	return None, None


def parse_payload(raw: bytes):
	raw = (raw or b"").strip()
	if not raw:
		return None
	if raw.startswith(b"<"):
		return xml_to_dict(raw)
	try:
		return json.loads(raw)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None


def xml_to_dict(raw: bytes):
	"""ISAPI XML (namespace bilan) ni oddiy dict'ga aylantiradi."""
	try:
		root = ET.fromstring(raw)
	except ET.ParseError:
		return None

	def strip_ns(tag):
		return tag.split("}", 1)[-1]

	def to_dict(el):
		children = list(el)
		if not children:
			return (el.text or "").strip()
		result = {}
		for child in children:
			result[strip_ns(child.tag)] = to_dict(child)
		return result

	return {strip_ns(root.tag): to_dict(root)} if strip_ns(root.tag) != "EventNotificationAlert" else to_dict(root)


def normalize_event(payload: dict):
	"""Har xil formatdagi xabarni bitta ko'rinishga keltiradi.

	Faqat shaxs aniqlangan o'tish hodisalarini qaytaradi (heartbeat emas).
	"""
	if not isinstance(payload, dict):
		return None

	event_type = str(payload.get("eventType") or "").lower()
	if event_type in ("heartbeat", "videoloss"):
		return None

	acs = payload.get("AccessControllerEvent")
	if not isinstance(acs, dict):
		return None

	person_id = str(acs.get("employeeNoString") or acs.get("employeeNo") or "").strip()
	person_name = str(acs.get("name") or "").strip()
	if not person_id:
		# shaxssiz hodisa (eshik ochildi, notanish yuz va h.k.) — saqlamaymiz
		return None

	return {
		"person_id": person_id,
		"person_name": person_name,
		"event_time": parse_event_time(payload.get("dateTime")),
		"terminal": str(acs.get("deviceName") or "").strip(),
		"terminal_ip": str(payload.get("ipAddress") or "").strip(),
		"verify_mode": str(acs.get("currentVerifyMode") or "").strip(),
		"event_code": f"{acs.get('majorEventType', '')}/{acs.get('subEventType', '')}",
		"raw": payload,
	}


def parse_event_time(value):
	"""'2026-08-07T09:15:30+05:00' -> '2026-08-07 09:15:30' (mahalliy vaqt)."""
	value = str(value or "").strip()
	if len(value) >= 19:
		return value[:19].replace("T", " ")
	return now_datetime()


def save_checkin(event: dict, picture: bytes | None):
	# Terminal bir hodisani qayta yuborsa — dublikat yozmaymiz
	if frappe.db.exists(
		"Terminal Checkin",
		{
			"person_id": event["person_id"],
			"event_time": event["event_time"],
			"terminal_ip": event["terminal_ip"],
		},
	):
		return

	who = classify_person(event["person_id"])
	doc = frappe.get_doc(
		{
			"doctype": "Terminal Checkin",
			"person_id": event["person_id"],
			"person_name": event["person_name"],
			"person_type": who.get("person_type"),
			"student": who.get("student"),
			"employee": who.get("employee"),
			"event_time": event["event_time"],
			"terminal": event["terminal"],
			"terminal_ip": event["terminal_ip"],
			"verify_mode": event["verify_mode"],
			"event_code": event["event_code"],
			"raw_data": json.dumps(event["raw"], ensure_ascii=False, indent=1, default=str),
		}
	)
	doc.insert(ignore_permissions=True)

	if picture:
		# Rasm buzuq bo'lsa ham o'tish yozuvi saqlanib qolishi shart
		try:
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"checkin-{doc.name}.jpg",
					"attached_to_doctype": "Terminal Checkin",
					"attached_to_name": doc.name,
					"attached_to_field": "picture",
					"is_private": 1,
					"content": picture,
				}
			)
			file_doc.insert(ignore_permissions=True)
			doc.db_set("picture", file_doc.file_url)
		except Exception:
			frappe.log_error(title="Hikvision picture error", message=frappe.get_traceback())


def classify_person(person_id: str) -> dict:
	"""Terminal ID bo'yicha kimligini aniqlaydi va tegishli hujjatga bog'laydi.

	O'quvchi:  Student doctype'idagi 'custom_hikvision_id' maydoni orqali.
	Xodim:     Employee doctype'idagi 'attendance_device_id' (ERPNext standart maydoni) orqali.
	O'qituvchi: xodim bo'lib, unga Instructor biriktirilgan bo'lsa.
	Hech qayerda topilmasa — "Noma'lum" (keyin qo'lda yoki ro'yxatga olishda bog'lanadi).
	"""
	if frappe.db.exists("DocType", "Student") and frappe.get_meta("Student").has_field(
		"custom_hikvision_id"
	):
		student = frappe.db.get_value("Student", {"custom_hikvision_id": person_id})
		if student:
			return {"person_type": "O'quvchi", "student": student}

	if frappe.db.exists("DocType", "Employee"):
		employee = frappe.db.get_value("Employee", {"attendance_device_id": person_id})
		if employee:
			person_type = "Xodim"
			if frappe.db.exists("DocType", "Instructor") and frappe.db.exists(
				"Instructor", {"employee": employee}
			):
				person_type = "O'qituvchi"
			return {"person_type": person_type, "employee": employee}

	return {"person_type": "Noma'lum"}
