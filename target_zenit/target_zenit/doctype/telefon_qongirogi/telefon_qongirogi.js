// Copyright (c) 2026, Target Zenit
frappe.ui.form.on("Telefon Qongirogi", {
	refresh(frm) {
		pleer_chiz(frm);

		if (frm.doc.admission_lead) {
			frm.add_custom_button(__("Murojaatni ochish"), () =>
				frappe.set_route("Form", "Admission Lead", frm.doc.admission_lead)
			);
		}
		if (frm.doc.family) {
			frm.add_custom_button(__("Oilani ochish"), () =>
				frappe.set_route("Form", "Family", frm.doc.family)
			);
		}
	},
});

function pleer_chiz(frm) {
	const maydon = frm.get_field("yozuv_html");
	if (!maydon) return;

	if (frm.is_new() || !frm.doc.yozuv_bor) {
		const sabab = frm.doc.yozuv_ochirildi
			? __("Yozuv saqlash muddati tugab o'chirilgan.")
			: __("Bu qo'ng'iroqda ovoz yozuvi yo'q.");
		maydon.$wrapper.html(`<div class="text-muted">${sabab}</div>`);
		return;
	}

	// Yozuv Frappe `files` papkasidan tashqarida — faqat shu endpoint beradi,
	// u ruxsatni tekshiradi (menejer o'zinikini, rahbar hammasini).
	const url =
		"/api/method/target_zenit.telefoniya.api.stream_recording?qongiroq=" +
		encodeURIComponent(frm.doc.name);

	const hajm = frm.doc.fayl_hajmi
		? (frm.doc.fayl_hajmi / 1024 / 1024).toFixed(2) + " MB"
		: "";

	maydon.$wrapper.html(`
		<audio controls preload="metadata" style="width:100%;max-width:520px">
			<source src="${url}" type="audio/mpeg">
			${__("Brauzeringiz audio ijrosini qo'llab-quvvatlamaydi.")}
		</audio>
		<div class="text-muted small" style="margin-top:4px">
			${__("Chap kanal — menejer, o'ng kanal — mijoz.")} ${hajm}
		</div>
	`);
}
