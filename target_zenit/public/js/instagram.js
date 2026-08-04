// Copyright (c) 2026, Target Zenit
// Instagram DM javob yozish dialogi (Admission Lead / Admission Inquiry formalarida)

frappe.provide("target_zenit");

target_zenit.instagram_reply_dialog = function ({ ig_user_id, lead, inquiry }) {
	const d = new frappe.ui.Dialog({
		title: __("Instagram javob yozish"),
		fields: [
			{
				fieldname: "text",
				fieldtype: "Small Text",
				label: __("Xabar matni"),
				reqd: 1,
			},
		],
		primary_action_label: __("Yuborish"),
		primary_action(values) {
			frappe.call({
				method: "target_zenit.integrations.instagram.send_message",
				args: { ig_user_id, text: values.text, lead, inquiry },
				freeze: true,
				callback() {
					frappe.show_alert({ message: __("Yuborildi"), indicator: "green" });
					d.hide();
				},
			});
		},
	});
	d.show();
};
