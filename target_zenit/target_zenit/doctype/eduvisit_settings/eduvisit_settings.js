// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Eduvisit Settings", {
	refresh(frm) {
		// Qo'lda sinxronizatsiya tugmasi
		frm.add_custom_button(__("Sync Now"), () => {
			frappe.confirm(
				__("eduvisit'dan o'quvchilarni hozir tortib olamizmi?"),
				() => {
					frappe.dom.freeze(__("Sinxronizatsiya... (bir necha daqiqa)"));
					frappe.call({
						method: "target_zenit.integrations.eduvisit.sync_now",
						callback: (r) => {
							frappe.dom.unfreeze();
							const m = r.message || {};
							frappe.msgprint({
								title: __("Sinxronizatsiya tugadi"),
								indicator: m.errors && m.errors.length ? "orange" : "green",
								message: __(
									"Yangi: {0}, yangilangan: {1}, xatolar: {2}",
									[m.created || 0, m.updated || 0, (m.errors || []).length]
								),
							});
							frm.reload_doc();
						},
						error: () => frappe.dom.unfreeze(),
					});
				}
			);
		}).addClass("btn-primary");

		// Turniket (kirdi/chiqdi) — bugungi hodisalarni tortish
		frm.add_custom_button(__("Turniketni tortish (bugun)"), () => {
			frappe.dom.freeze(__("Turniket hodisalari tortilyapti..."));
			frappe.call({
				method: "target_zenit.integrations.eduvisit.sync_attendance_now",
				callback: (r) => {
					frappe.dom.unfreeze();
					const m = r.message || {};
					frappe.msgprint({
						title: __("Turniket tortildi"),
						indicator: "green",
						message: __(
							"Yangi o'tishlar: {0}, davomat (Present) yozildi: {1}",
							[m.checkins_new || 0, m.attendance_created || 0]
						),
					});
				},
				error: () => frappe.dom.unfreeze(),
			});
		});

		// Ulanishni tekshirish tugmasi
		frm.add_custom_button(__("Test ulanish"), () => {
			frappe.call({
				method: "target_zenit.integrations.eduvisit.test_connection",
				callback: (r) => {
					const m = r.message || {};
					frappe.msgprint({
						title: __("Ulanish OK"),
						indicator: "green",
						message: __("API ishlayapti. O'quvchilar soni: {0}", [m.count || 0]),
					});
				},
			});
		});
	},
});
