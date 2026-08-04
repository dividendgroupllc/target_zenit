# Copyright (c) 2026, Target Zenit
# For license information, please see license.txt

import frappe
from frappe import _

# "Qayta ro'yxat" parallel jarayon — asosiy voronkaga kirmaydi
FUNNEL_MAX_SORT_ORDER = 90


def execute(filters=None):
	filters = frappe._dict(filters or {})

	stages = frappe.get_all(
		"Admission Stage",
		filters={"sort_order": ("<=", FUNNEL_MAX_SORT_ORDER)},
		fields=["name", "sort_order"],
		order_by="sort_order asc",
	)

	lead_filters = {}
	if filters.get("academic_year"):
		lead_filters["academic_year"] = filters.academic_year
	if filters.get("source"):
		lead_filters["source"] = filters.source
	if filters.get("from_date") and filters.get("to_date"):
		lead_filters["creation"] = ("between", [filters.from_date, filters.to_date])
	elif filters.get("from_date"):
		lead_filters["creation"] = (">=", filters.from_date)
	elif filters.get("to_date"):
		lead_filters["creation"] = ("<=", filters.to_date)

	counts = []
	for stage in stages:
		lead_filters["stage"] = stage.name
		counts.append(frappe.db.count("Admission Lead", lead_filters))

	data = []
	total_reached_first = None
	prev_reached = None
	for i, stage in enumerate(stages):
		# shu bosqichga yetib kelganlar = hozir shu yoki keyingi bosqichlarda turganlar
		reached = sum(counts[i:])
		if total_reached_first is None:
			total_reached_first = reached

		conv_prev = (reached / prev_reached * 100) if prev_reached else None
		conv_total = (reached / total_reached_first * 100) if total_reached_first else None

		data.append(
			{
				"stage": stage.name,
				"current_count": counts[i],
				"reached": reached,
				"conv_prev": round(conv_prev, 1) if conv_prev is not None else None,
				"conv_total": round(conv_total, 1) if conv_total is not None else None,
			}
		)
		prev_reached = reached

	columns = [
		{"fieldname": "stage", "label": _("Bosqich"), "fieldtype": "Data", "width": 180},
		{"fieldname": "current_count", "label": _("Hozir shu bosqichda"), "fieldtype": "Int", "width": 160},
		{"fieldname": "reached", "label": _("Yetib kelganlar"), "fieldtype": "Int", "width": 140},
		{"fieldname": "conv_prev", "label": _("Oldingi bosqichdan %"), "fieldtype": "Percent", "width": 160},
		{"fieldname": "conv_total", "label": _("Boshidan %"), "fieldtype": "Percent", "width": 130},
	]

	chart = {
		"data": {
			"labels": [d["stage"] for d in data],
			"datasets": [{"name": _("Yetib kelganlar"), "values": [d["reached"] for d in data]}],
		},
		"type": "bar",
		"colors": ["#2490ef"],
	}

	return columns, data, None, chart
