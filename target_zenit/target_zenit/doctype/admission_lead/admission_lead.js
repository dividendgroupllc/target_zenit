// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Admission Lead", {
	setup(frm) {
		frm.set_query("status", () => ({
			filters: { stage: frm.doc.stage || "" },
		}));
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.instagram_user_id) {
			frm.add_custom_button(__("Instagram javob"), () => {
				target_zenit.instagram_reply_dialog({
					ig_user_id: frm.doc.instagram_user_id,
					lead: frm.doc.name,
				});
			});
			frm.add_custom_button(__("Yozishmalar"), () => {
				frappe.set_route("List", "Instagram Message", {
					ig_user_id: frm.doc.instagram_user_id,
				});
			});
		}
	},

	stage(frm) {
		// Bosqich o'zgarsa, eski bosqich statusi mos kelmay qoladi
		if (frm.doc.status) {
			frappe.db.get_value("Admission Status", frm.doc.status, "stage").then((r) => {
				if (r.message && r.message.stage !== frm.doc.stage) {
					frm.set_value("status", "");
				}
			});
		}
	},
});
