# Copyright (c) 2026, Target Zenit
# DB'da (UI orqali) yaratilgan workspace'larga yorliq qo'shish. Bunday
# workspace'lar app fayllarida yo'q, shuning uchun after_migrate'da idempotent
# qo'shiladi — serverda ham o'zi paydo bo'ladi.
#   * "Sotuv Menejr"  — qarzdorlik paneli va qarz ishlari;
#   * "Investor"      — sotuv nazorati sahifasi (2026-10-27).
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


# Investor workspace'ida sotuv nazorati ALOHIDA sahifa bo'lib tursin
# (dashboard ichida emas — foydalanuvchi qarori, 2026-10-27).
INVESTOR_WORKSPACE = "Investor"
INVESTOR_SHORTCUTS = [
	{
		"label": "Sotuv nazorati",
		"type": "Page",
		"link_to": "sotuv-nazorati",
		"color": "Blue",
	},
]


def add_qarzdorlik_shortcuts(workspace: str = TARGET_WORKSPACE, shortcuts=None):
	"""Yorliqlarni qo'shadi (bor bo'lsa tegmaydi) va content bloklariga kiritadi."""
	shortcuts = SHORTCUTS if shortcuts is None else shortcuts
	if not frappe.db.exists("Workspace", workspace):
		return

	ws = frappe.get_doc("Workspace", workspace)
	mavjud = {s.label for s in ws.shortcuts}
	qoshildi = []

	for sc in shortcuts:
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
	print(f"{workspace}: qo'shildi -> {qoshildi}")


def after_migrate():
	for ws, shortcuts in (
		(TARGET_WORKSPACE, SHORTCUTS),
		(INVESTOR_WORKSPACE, INVESTOR_SHORTCUTS),
	):
		try:
			add_qarzdorlik_shortcuts(ws, shortcuts)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"setup_workspace: {ws}")
