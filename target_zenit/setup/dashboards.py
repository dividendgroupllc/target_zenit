# Copyright (c) 2026, Target Zenit
# Qabul dashboard: raqamli kartochkalar + grafiklar.
# Ishga tushirish: bench --site target.local execute target_zenit.setup.dashboards.setup_dashboards

import json

import frappe

NUMBER_CARDS = [
	{
		"label": "Yangi arizalar",
		"document_type": "Admission Inquiry",
		"filters_json": json.dumps([["Admission Inquiry", "inquiry_status", "=", "Yangi", False]]),
	},
	{
		"label": "Jami murojaatlar",
		"document_type": "Admission Lead",
		"filters_json": "[]",
	},
	{
		"label": "Qabul qilinganlar",
		"document_type": "Admission Lead",
		"filters_json": json.dumps([["Admission Lead", "stage", "=", "Qabul qilindi", False]]),
	},
	{
		"label": "Oilalar",
		"document_type": "Family",
		"filters_json": "[]",
	},
]

CHARTS = [
	{
		"chart_name": "Qabul voronkasi",
		"chart_type": "Report",
		"report_name": "Qabul Voronkasi",
		"use_report_chart": 1,
		"type": "Bar",
		"filters_json": "{}",
	},
	{
		"chart_name": "Murojaatlar manba bo'yicha",
		"chart_type": "Group By",
		"document_type": "Admission Lead",
		"group_by_type": "Count",
		"group_by_based_on": "source",
		"type": "Donut",
		"filters_json": "[]",
	},
]


def setup_dashboards():
	for card in NUMBER_CARDS:
		if not frappe.db.exists("Number Card", card["label"]):
			frappe.get_doc(
				{
					"doctype": "Number Card",
					"name": card["label"],
					"function": "Count",
					"is_public": 1,
					"show_percentage_stats": 0,
					**card,
				}
			).insert(ignore_permissions=True)

	for chart in CHARTS:
		if not frappe.db.exists("Dashboard Chart", chart["chart_name"]):
			frappe.get_doc(
				{
					"doctype": "Dashboard Chart",
					"is_public": 1,
					"timeseries": 0,
					**chart,
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("Dashboard", "Qabul"):
		frappe.get_doc(
			{
				"doctype": "Dashboard",
				"dashboard_name": "Qabul",
				"charts": [{"chart": c["chart_name"], "width": "Full"} for c in CHARTS],
				"cards": [{"card": c["label"]} for c in NUMBER_CARDS],
			}
		).insert(ignore_permissions=True)

	frappe.db.commit()
	print(f"OK: {len(NUMBER_CARDS)} kartochka, {len(CHARTS)} grafik, 'Qabul' dashboard tayyor")
