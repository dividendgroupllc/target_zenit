# Copyright (c) 2026, Target Zenit
# Kunlik kirdi-chiqdi tahlili: har bir odam har bir kun uchun bitta qator —
# birinchi kirish, oxirgi o'tish, ichkarida bo'lgan taxminiy vaqt, o'tishlar soni.

import frappe
from frappe import _
from frappe.utils import add_days, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.from_date:
		filters.from_date = add_days(nowdate(), -7)
	if not filters.to_date:
		filters.to_date = nowdate()

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "date", "label": _("Sana"), "fieldtype": "Date", "width": 100},
		{
			"fieldname": "person_type",
			"label": _("Kim"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "person_name",
			"label": _("Ism"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "person_id",
			"label": _("Terminal ID"),
			"fieldtype": "Data",
			"width": 90,
		},
		{
			"fieldname": "first_in",
			"label": _("Birinchi kirish"),
			"fieldtype": "Time",
			"width": 110,
		},
		{
			"fieldname": "last_out",
			"label": _("Oxirgi o'tish"),
			"fieldtype": "Time",
			"width": 110,
		},
		{
			"fieldname": "duration",
			"label": _("Oraliq (soat)"),
			"fieldtype": "Float",
			"precision": 1,
			"width": 100,
		},
		{
			"fieldname": "passes",
			"label": _("O'tishlar soni"),
			"fieldtype": "Int",
			"width": 100,
		},
	]


def get_data(filters):
	conditions = ""
	values = {"from_date": filters.from_date, "to_date": filters.to_date}
	if filters.get("person_type"):
		conditions += " and person_type = %(person_type)s"
		values["person_type"] = filters.person_type

	return frappe.db.sql(
		f"""
		select
			date(event_time) as date,
			person_type,
			person_name,
			person_id,
			time(min(event_time)) as first_in,
			time(max(event_time)) as last_out,
			round(timestampdiff(minute, min(event_time), max(event_time)) / 60.0, 1) as duration,
			count(*) as passes
		from `tabTerminal Checkin`
		where date(event_time) between %(from_date)s and %(to_date)s
			{conditions}
		group by date(event_time), person_id, person_type, person_name
		order by date desc, person_type, person_name
		""",
		values,
		as_dict=True,
	)
