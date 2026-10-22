// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Moodle Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Ulanishni tekshirish"), () => {
			frappe.call({
				method: "target_zenit.integrations.moodle.test_connection",
				freeze: true,
				freeze_message: __("Moodle bilan bog'lanilmoqda..."),
				callback: (r) => {
					if (!r.message) return;
					const m = r.message;
					const missing = m.yetishmayotgan_funksiyalar || [];
					let html = `<b>${frappe.utils.escape_html(m.sitename || "")}</b><br>
						Moodle: ${frappe.utils.escape_html(m.release || "")}<br>
						Token egasi: ${frappe.utils.escape_html(m.username || "")} (id ${m.userid})`;
					if (missing.length) {
						html += `<hr><div class="text-danger"><b>Web service'ga qo'shilmagan funksiyalar:</b><br>
							${missing.join("<br>")}</div>
							<small>Moodle: Server → Web services → External services → Frappe Sync → Functions</small>`;
					} else {
						html += `<hr><span class="text-success">Kerakli funksiyalar bor — sinxronga tayyor.</span>`;
					}
					frappe.msgprint({ title: __("Moodle ulanishi"), message: html, indicator: missing.length ? "orange" : "green" });
				},
			});
		});

		frm.add_custom_button(__("Hozir sinxronlash"), () => {
			frappe.confirm(
				frm.doc.dry_run
					? __("Test rejimi yoqilgan — Moodle'ga hech narsa yozilmaydi. Davom etamizmi?")
					: __("Frappe'dagi o'quvchi va o'qituvchilar Moodle'ga yuboriladi. Davom etamizmi?"),
				() => {
					frappe.call({
						method: "target_zenit.integrations.moodle.sync_now",
						freeze: true,
						freeze_message: __("Fon vazifasi qo'yilmoqda..."),
						callback: (r) => {
							frm.reload_doc();
							frappe.msgprint({
								title: __("To'liq sinxron boshlandi"),
								message: __(
									"Sinxron FONDA ketmoqda — bu bir necha daqiqa oladi. " +
									"Jarayonni 'Moodle Sync Log' dagi eng yangi yozuvdan kuzatasan: " +
									"holati 'Ishlayapti' dan 'Tugadi' ga o'tadi, raqamlar esa " +
									"har partiyadan keyin yangilanib boradi (sahifani yangilab tur)."
								),
								indicator: "blue",
							});
							frappe.set_route("List", "Moodle Sync Log");
						},
					});
				}
			);
		}).addClass("btn-primary");

		frm.add_custom_button(__("Sinov sinxroni (bir nechta kishi)"), () => {
			frappe.prompt(
				{
					fieldname: "limit",
					label: __("Nechta faol odam bilan sinaymiz?"),
					fieldtype: "Int",
					default: 3,
					reqd: 1,
					description: __("Faqat shu sondagi faol odam Moodle'ga yuboriladi. 07:00 dagi avto sinxron bundan ta'sirlanmaydi."),
				},
				(v) => {
					frappe.call({
						method: "target_zenit.integrations.moodle.sync_now",
						args: { limit: v.limit },
						freeze: true,
						freeze_message: __("Sinov sinxroni ketmoqda..."),
						callback: (r) => {
							frm.reload_doc();
							if (r.message && r.message.log) {
								frappe.set_route("Form", "Moodle Sync Log", r.message.log);
							}
						},
					});
				},
				__("Sinov sinxroni"),
				__("Boshlash")
			);
		});

		// --- Kurs va yozilish (2-bosqich) ---
		frm.add_custom_button(__("Kurslarni sinxronlash"), () => {
			frappe.confirm(
				frm.doc.dry_run
					? __("Test rejimi yoqilgan — Moodle'ga hech narsa yozilmaydi. Davom etamizmi?")
					: __("Dars jadvalidagi har (guruh x fan) uchun Moodle'da kurs yaratiladi va o'quvchi/o'qituvchi unga yoziladi. Davom etamizmi?"),
				() => {
					frappe.call({
						method: "target_zenit.integrations.moodle_kurs.kurs_sync_now",
						freeze: true,
						freeze_message: __("Fon vazifasi qo'yilmoqda..."),
						callback: (r) => {
							frm.reload_doc();
							frappe.msgprint({
								title: __("Kurs sinxroni boshlandi"),
								message: __("Sinxron FONDA ketmoqda. Jarayonni 'Moodle Sync Log' dagi eng yangi 'Kurs' yozuvidan kuzatasan."),
								indicator: "blue",
							});
							frappe.set_route("List", "Moodle Sync Log");
						},
					});
				}
			);
		}, __("Kurslar"));

		frm.add_custom_button(__("Sinov: bir nechta kurs"), () => {
			frappe.prompt(
				{
					fieldname: "limit",
					label: __("Nechta kurs bilan sinaymiz?"),
					fieldtype: "Int",
					default: 3,
					reqd: 1,
					description: __("Faqat shu sondagi kurs yaratiladi va unga yozilish qilinadi."),
				},
				(v) => {
					frappe.call({
						method: "target_zenit.integrations.moodle_kurs.kurs_sync_now",
						args: { limit: v.limit },
						freeze: true,
						freeze_message: __("Sinov kurs sinxroni ketmoqda..."),
						callback: (r) => {
							frm.reload_doc();
							if (r.message && r.message.log) {
								frappe.set_route("Form", "Moodle Sync Log", r.message.log);
							}
						},
					});
				},
				__("Sinov kurs sinxroni"),
				__("Boshlash")
			);
		}, __("Kurslar"));

		frm.add_custom_button(__("Kurs ro'yxati"), () => {
			frappe.set_route("List", "Moodle Course Link");
		}, __("Ko'rish"));

		frm.add_custom_button(__("Foydalanuvchi ro'yxati"), () => {
			frappe.set_route("List", "Moodle User Link");
		}, __("Ko'rish"));

		frm.add_custom_button(__("Sinxron tarixi"), () => {
			frappe.set_route("List", "Moodle Sync Log");
		}, __("Ko'rish"));

		if (!frm.doc.enabled) {
			frm.dashboard.add_comment(
				__("Integratsiya o'chirilgan — na avto (07:00), na qo'lda sinxron ishlamaydi."),
				"orange",
				true
			);
		}
	},
});
