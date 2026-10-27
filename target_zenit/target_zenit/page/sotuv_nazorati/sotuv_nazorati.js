// Copyright (c) 2026, Target Zenit — Sotuv nazorati sahifasi.
// Butun ko'rinish `public/js/sotuv_nazorati_view.js` da (investor dashboard ham
// shuni ishlatadi); bu yerda faqat sahifa qobig'i.
frappe.pages["sotuv-nazorati"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper, title: __("Sotuv nazorati"), single_column: true,
	});
	const bugun = frappe.datetime.get_today();
	const body = $(`<div></div>`).appendTo(page.main);
	new window.TZSotuvNazoratiView({
		wrapper: body,
		from_date: frappe.datetime.add_days(bugun, -30),
		to_date: bugun,
		toolbar: true,
	});
};
