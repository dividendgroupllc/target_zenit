# Copyright (c) 2026, Target Zenit
# Sotuv menejerining o'z workspace'iga ("Sotuv Menejr") qarzdorlik yorliqlarini
# qo'shadi. Bu workspace DB'da (UI orqali) yaratilgan — faylda yo'q, shuning uchun
# after_migrate'da idempotent qo'shiladi: serverda ham o'zi paydo bo'ladi.
from __future__ import annotations

import json

import frappe

TARGET_WORKSPACE = "Sotuv Menejr"

SHORTCUTS = [
	{
		"label": "Qarzdorlik paneli",
		"type": "Page",
		"link_to": "qarzdorlik",
		"color": "Red",
	},
	{
		"label": "Qarz ishlarim",
		"type": "DocType",
		"link_to": "Qarz Ishi",
		"doc_view": "List",
		"color": "Orange",
	},
]


def add_qarzdorlik_shortcuts():
	"""Yorliqlarni qo'shadi (bor bo'lsa tegmaydi) va content bloklariga kiritadi."""
	if not frappe.db.exists("Workspace", TARGET_WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", TARGET_WORKSPACE)
	mavjud = {s.label for s in ws.shortcuts}
	qoshildi = []

	for sc in SHORTCUTS:
		if sc["label"] in mavjud:
			continue
		ws.append("shortcuts", sc)
		qoshildi.append(sc["label"])

	if not qoshildi:
		return

	try:
		blocks = json.loads(ws.content or "[]")
	except Exception:
		blocks = []
	mavjud_bloklar = {
		b.get("data", {}).get("shortcut_name") for b in blocks if b.get("type") == "shortcut"
	}
	for label in qoshildi:
		if label not in mavjud_bloklar:
			blocks.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "shortcut",
					"data": {"shortcut_name": label, "col": 3},
				}
			)
	ws.content = json.dumps(blocks)
	ws.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"{TARGET_WORKSPACE}: qo'shildi -> {qoshildi}")


def after_migrate():
	try:
		add_qarzdorlik_shortcuts()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik setup_workspace")
