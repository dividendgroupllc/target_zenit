// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Eduvisit Settings", {
	refresh(frm) {
		// O'quvchi sync O'CHIRILGAN (2026-09-07): API faqat turniket ma'lumotini beradi.
		// Ism/guruh/holat — operatorlar qo'lda yuritadi, API ularni QAYTA YOZMAYDI.
		frm.dashboard.set_headline(
			__("O'quvchi ma'lumotlari API'dan sinxronlanmaydi — faqat turniket (kirdi/chiqdi) tortiladi. Ism, sinf-guruh va holatlar qo'lda yuritiladi.")
		);

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
		}).addClass("btn-primary");

		// Ulanishni tekshirish tugmasi
		frm.add_custom_button(__("Test ulanish"), () => {
			frappe.call({
				method: "target_zenit.integrations.eduvisit.test_connection",
				callback: (r) => {
					const m = r.message || {};
					frappe.msgprint({
						title: __("Ulanish OK"),
						indicator: "green",
						message: __("API ishlayapti. Bugungi turniket hodisalari: {0}", [m.count || 0]),
					});
				},
			});
		});
	},
});
