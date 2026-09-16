// Copyright (c) 2026, abdulloh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Oylik Vedomost", {
	refresh(frm) {
		if (frm.doc.fayl && !frm.is_new()) {
			frm.add_custom_button(__("Fayldan to'ldirish"), () => fill(frm)).addClass("btn-primary");
		}
		if (frm.doc.qatorlar && frm.doc.qatorlar.length) {
			const bogsiz = frm.doc.qatorlar.filter((r) => !r.employee).length;
			if (bogsiz) {
				frm.dashboard.set_headline(
					__("{0} ta qator bazadagi xodimga bog'lanmagan — ular vedomostdagi F.I.Sh bilan ko'rinadi.", [bogsiz]));
			}
		}
	},
});

function fill(frm) {
	frappe.confirm(
		__("Qatorlar fayldan qayta o'qiladi va almashtiriladi. Davom etamizmi?"),
		() => {
			frappe.call({
				method: "target_zenit.target_zenit.doctype.oylik_vedomost.oylik_vedomost.fill_from_file",
				args: { docname: frm.doc.name },
				freeze: true,
				freeze_message: __("Excel o'qilyapti…"),
			}).then((r) => {
				const m = r.message || {};
				frm.reload_doc();
				frappe.msgprint({
					title: __("Yuklandi"),
					indicator: "green",
					message: __("Varaq: <b>{0}</b><br>Qatorlar: <b>{1}</b> (bog'langan {2}, bog'lanmagan {3})<br>Jami oklad: <b>{4}</b><br>Jami nachisleniya: <b>{5}</b>",
						[m.varaq, m.count, m.linked, m.unlinked,
						 format_currency(m.jami_oklad), format_currency(m.jami_nachisleniya)]),
				});
			});
		}
	);
}
