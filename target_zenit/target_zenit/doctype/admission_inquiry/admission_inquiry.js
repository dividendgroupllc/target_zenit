// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Admission Inquiry", {
	refresh(frm) {
		if (!frm.is_new() && !frm.doc.converted_lead) {
			frm.add_custom_button(__("Lead ochish"), () => {
				frappe.call({
					method:
						"target_zenit.target_zenit.doctype.admission_inquiry.admission_inquiry.convert_to_lead",
					args: { inquiry_name: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) {
							frappe.show_alert({ message: __("Lead ochildi"), indicator: "green" });
							frappe.set_route("Form", "Admission Lead", r.message);
						}
					},
				});
			}).addClass("btn-primary");
		}
		if (frm.doc.converted_lead) {
			frm.add_custom_button(__("Lead'ga o'tish"), () => {
				frappe.set_route("Form", "Admission Lead", frm.doc.converted_lead);
			});
		}
		if (frm.doc.instagram_user_id) {
			frm.add_custom_button(__("Instagram javob"), () => {
				target_zenit.instagram_reply_dialog({
					ig_user_id: frm.doc.instagram_user_id,
					inquiry: frm.doc.name,
				});
			});
			frm.add_custom_button(__("Yozishmalar"), () => {
				frappe.set_route("List", "Instagram Message", {
					ig_user_id: frm.doc.instagram_user_id,
				});
			});
		}
	},
});
