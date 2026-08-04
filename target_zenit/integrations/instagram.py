# Copyright (c) 2026, Target Zenit
# Instagram DM webhook + javob yuborish.
# Webhook URL: /api/method/target_zenit.integrations.instagram.webhook

import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime
from werkzeug.wrappers import Response

GRAPH_URL = "https://graph.facebook.com"

# +998 90 123-45-67, 998901234567, 901234567 kabi ko'rinishlarni topadi
PHONE_PATTERN = re.compile(r"(?:\+?998[\s\-.()]*)?(?:\d[\s\-.()]*){9}")


def extract_phone(text: str) -> str | None:
	"""Xabar matnidan O'zbekiston telefon raqamini topib +998XXXXXXXXX ko'rinishga keltiradi."""
	for match in PHONE_PATTERN.finditer(text or ""):
		digits = re.sub(r"\D", "", match.group())
		if len(digits) == 9:
			return "+998" + digits
		if len(digits) == 12 and digits.startswith("998"):
			return "+" + digits
	return None


@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
	if frappe.request.method == "GET":
		return verify_webhook()
	return handle_incoming()


def verify_webhook():
	"""Meta webhook'ni birinchi ulashda GET so'rov bilan tekshiradi."""
	args = frappe.request.args
	settings = frappe.get_cached_doc("Instagram Settings")
	if (
		args.get("hub.mode") == "subscribe"
		and settings.verify_token
		and args.get("hub.verify_token") == settings.verify_token
	):
		return Response(args.get("hub.challenge"), status=200)
	return Response("Verification failed", status=403)


def handle_incoming():
	settings = frappe.get_cached_doc("Instagram Settings")
	if not settings.enabled:
		return Response("disabled", status=200)

	try:
		payload = json.loads(frappe.request.data or "{}")
	except json.JSONDecodeError:
		return Response("bad payload", status=400)

	if payload.get("object") != "instagram":
		return Response("ignored", status=200)

	for entry in payload.get("entry", []):
		for event in entry.get("messaging", []):
			try:
				process_message_event(event, settings)
			except Exception:
				frappe.log_error(
					title="Instagram webhook error", message=frappe.get_traceback()
				)

	frappe.db.commit()
	# Meta 20 soniyada javob kutadi; xato bo'lsa ham 200 qaytaramiz (retry bo'roni bo'lmasin)
	return Response("ok", status=200)


def process_message_event(event, settings):
	message = event.get("message") or {}
	text = message.get("text")
	mid = message.get("mid")
	sender_id = (event.get("sender") or {}).get("id")

	if not sender_id or not text:
		return  # attachment/reaction/echo — hozircha faqat matn

	if message.get("is_echo"):
		return  # o'zimiz yuborgan xabarning aks-sadosi

	if mid and frappe.db.exists("Instagram Message", {"message_id": mid}):
		return  # Meta ba'zan takror yuboradi

	lead = frappe.db.get_value("Admission Lead", {"instagram_user_id": sender_id}, "name")
	inquiry = None
	is_new_inquiry = False
	if not lead:
		inquiry = frappe.db.get_value(
			"Admission Inquiry",
			{"instagram_user_id": sender_id, "inquiry_status": ("in", ["Yangi", "Bog'lanildi"])},
			"name",
		)
		if not inquiry:
			inquiry = create_inquiry_from_ig(sender_id, text, settings)
			is_new_inquiry = True

	frappe.get_doc(
		{
			"doctype": "Instagram Message",
			"direction": "Kirish",
			"ig_user_id": sender_id,
			"message_id": mid,
			"sent_at": now_datetime(),
			"text": text,
			"lead": lead,
			"inquiry": inquiry,
		}
	).insert(ignore_permissions=True)

	if inquiry:
		handle_phone_automation(inquiry, sender_id, text, is_new_inquiry, settings)


def handle_phone_automation(inquiry, sender_id, text, is_new_inquiry, settings):
	"""Telefon avtomatikasi: xabardan raqamni topib saqlaydi, bo'lmasa so'raydi."""
	if frappe.db.get_value("Admission Inquiry", inquiry, "phone"):
		return

	phone = extract_phone(text)
	if phone:
		frappe.db.set_value("Admission Inquiry", inquiry, "phone", phone, update_modified=False)
		auto_reply(settings, sender_id, settings.phone_thanks_text, inquiry)
	elif is_new_inquiry:
		auto_reply(settings, sender_id, settings.auto_reply_text, inquiry)


def auto_reply(settings, ig_user_id, text, inquiry=None):
	"""Avtomatik javob — xato bo'lsa jarayonni to'xtatmaydi, faqat log yozadi."""
	if not settings.auto_reply_enabled or not text:
		return
	token = settings.get_password("access_token", raise_exception=False)
	if not token:
		return
	try:
		mid = post_message(settings, token, ig_user_id, text)
		save_outgoing(ig_user_id, mid, text, inquiry=inquiry)
	except Exception:
		frappe.log_error(title="Instagram auto-reply error", message=frappe.get_traceback())


def create_inquiry_from_ig(sender_id, text, settings):
	"""Notanish IG foydalanuvchidan birinchi xabar → yangi ariza."""
	profile_name = fetch_ig_profile_name(sender_id, settings)
	inquiry = frappe.get_doc(
		{
			"doctype": "Admission Inquiry",
			"parent_name": profile_name or f"Instagram: {sender_id}",
			"source": "Instagram DM",
			"message": text,
			"instagram_user_id": sender_id,
		}
	)
	inquiry.insert(ignore_permissions=True)
	return inquiry.name


def fetch_ig_profile_name(sender_id, settings):
	token = settings.get_password("access_token", raise_exception=False)
	if not token:
		return None
	try:
		resp = requests.get(
			f"{GRAPH_URL}/{settings.api_version or 'v23.0'}/{sender_id}",
			params={"fields": "name,username", "access_token": token},
			timeout=10,
		)
		if resp.ok:
			data = resp.json()
			name = data.get("name") or data.get("username")
			username = data.get("username")
			if name and username and name != username:
				return f"{name} (@{username})"
			return name or (f"@{username}" if username else None)
	except requests.RequestException:
		pass
	return None


@frappe.whitelist()
def send_message(ig_user_id: str, text: str, lead: str | None = None, inquiry: str | None = None):
	"""CRM'dan Instagram DM javob yuborish (24 soat oynasi ichida)."""
	settings = frappe.get_cached_doc("Instagram Settings")
	if not settings.enabled:
		frappe.throw(_("Instagram integratsiyasi yoqilmagan (Instagram Settings)"))

	token = settings.get_password("access_token", raise_exception=False)
	if not token:
		frappe.throw(_("Access token kiritilmagan (Instagram Settings)"))

	try:
		mid = post_message(settings, token, ig_user_id, text)
	except requests.RequestException as e:
		frappe.log_error(title="Instagram send error", message=str(e))
		frappe.throw(_("Xabar yuborilmadi: {0}").format(str(e)[:200]))

	save_outgoing(ig_user_id, mid, text, lead=lead, inquiry=inquiry)
	return {"ok": True}


def post_message(settings, token, ig_user_id, text):
	resp = requests.post(
		f"{GRAPH_URL}/{settings.api_version or 'v23.0'}/me/messages",
		params={"access_token": token},
		json={"recipient": {"id": ig_user_id}, "message": {"text": text}},
		timeout=15,
	)
	if not resp.ok:
		raise requests.RequestException(resp.text)
	return (resp.json() or {}).get("message_id")


def save_outgoing(ig_user_id, mid, text, lead=None, inquiry=None):
	frappe.get_doc(
		{
			"doctype": "Instagram Message",
			"direction": "Chiqish",
			"ig_user_id": ig_user_id,
			"message_id": mid,
			"sent_at": now_datetime(),
			"text": text,
			"lead": lead,
			"inquiry": inquiry,
		}
	).insert(ignore_permissions=True)
