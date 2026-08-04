// Copyright (c) 2026, Target Zenit

frappe.query_reports["Qabul Voronkasi"] = {
	filters: [
		{
			fieldname: "academic_year",
			label: __("O'quv yili"),
			fieldtype: "Data",
		},
		{
			fieldname: "source",
			label: __("Manba"),
			fieldtype: "Link",
			options: "Lead Source",
		},
		{
			fieldname: "from_date",
			label: __("Boshlanish sanasi"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Tugash sanasi"),
			fieldtype: "Date",
		},
	],
};
