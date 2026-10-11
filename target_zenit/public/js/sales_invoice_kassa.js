// Copyright (c) 2026, Target Zenit
// Sales Invoice -> "Kassa" tugmasi: nachisleniyadan to'g'ridan-to'g'ri kassaga
// o'tish. Kassa submit bo'lganda Payment Entry yaratiladi va u SHU hisob-fakturaga
// bog'lanadi (kassa.py -> allocate_customer_invoices).
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (flt(frm.doc.outstanding_amount) <= 0.005) return;
		if (frm.doc.party_type && frm.doc.party_type !== "Customer") return;

		frm.add_custom_button(__("Kassa (to'lov)"), () => tz_kassa_yarat(frm), __("Create"));
		// "Create" guruhini birinchi bo'lib ochib qo'yamiz — eng ko'p ishlatiladigani
		frm.page.set_inner_btn_group_as_primary(__("Create"));
	},
});

function tz_kassa_yarat(frm) {
	frappe.new_doc("Kassa", {
		transaction_type: "Приход",
		date: frappe.datetime.get_today(),
		company: frm.doc.company,
		party_type: "Customer",
		party: frm.doc.customer,
		party_name: frm.doc.customer_name,
		sales_invoice: frm.doc.name,
		amount: flt(frm.doc.outstanding_amount),
		payment_month: frm.doc.custom_payment_month || "",
		remarks: `${frm.doc.name} bo'yicha to'lov`,
	});
}
