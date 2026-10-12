// Copyright (c) 2026, Target Zenit
frappe.ui.form.on("Baholash Sozlamalari", {
	shkala(frm) {
		if (!frm.doc.shkala) return;
		frm.call("shkala_boyicha_tiklash").then((r) => {
			if (r && r.message) {
				Object.entries(r.message).forEach(([k, v]) => frm.set_value(k, v));
				frappe.show_alert({ message: __("Chegaralar shkalaga moslashtirildi"), indicator: "green" });
			}
		});
	},
});
