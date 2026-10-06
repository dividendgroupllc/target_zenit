// Copyright (c) 2026, Target Zenit
// Biriktirish jadvalidagi "Sinf / shablon" maydoniga faol Student Group'lar
// avto-taklif bo'lib keladi (qo'lda shablon yozish ham mumkin: 7*, G1* ...).
frappe.ui.form.on("Qarzdorlik Sozlamalari", {
	setup(frm) {
		frappe.db
			.get_list("Student Group", {
				filters: { disabled: 0 },
				fields: ["name"],
				order_by: "name asc",
				limit: 500,
			})
			.then((rows) => {
				const opts = (rows || []).map((d) => d.name);
				frm.fields_dict.biriktirish.grid.update_docfield_property(
					"sinf_pattern",
					"options",
					opts
				);
			});
	},
});
