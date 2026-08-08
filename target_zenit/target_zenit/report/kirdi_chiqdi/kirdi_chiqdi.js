// Copyright (c) 2026, Target Zenit

frappe.query_reports["Kirdi Chiqdi"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("Boshlanish sanasi"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Tugash sanasi"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "person_type",
			label: __("Kim"),
			fieldtype: "Select",
			options: "\nNoma'lum\nO'quvchi\nO'qituvchi\nXodim",
		},
	],
};
