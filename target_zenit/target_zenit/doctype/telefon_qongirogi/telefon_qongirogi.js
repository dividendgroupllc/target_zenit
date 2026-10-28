// Copyright (c) 2026, Target Zenit
frappe.ui.form.on("Telefon Qongirogi", {
	refresh(frm) {
		pleer_chiz(frm);
		transkript_tugma(frm);

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

// Nutq -> matn: yozuv bor bo'lsa qo'lda ham ishga tushirish mumkin.
// Avtomatik oqim: yozuv kelganda telefoniya/api.py o'zi navbatga qo'yadi.
function transkript_tugma(frm) {
	if (frm.is_new() || !frm.doc.yozuv_bor || frm.doc.yozuv_ochirildi) return;

	const bor = !!frm.doc.transkript;
	// Mavjud transkriptni QAYTA yurgizish — faqat administrator (token isrofi);
	// matni yo'q yozuvni hamma yurgiza oladi.
	const admin = frappe.session.user === "Administrator"
		|| (frappe.user_roles || []).includes("System Manager");
	if (bor && !admin) return;
	frm.add_custom_button(bor ? __("Transkriptni yangilash") : __("Transkripsiya qilish"), () => {
		if (bor && !confirm(__("Mavjud transkript ustiga yoziladi. Davom etamizmi?"))) return;
		frappe.call({
			method: "target_zenit.telefoniya.stt.qolda",
			args: { qongiroq: frm.doc.name },
			freeze: true,
			freeze_message: __("Nutq matnga aylantirilmoqda… (bir necha sekund)"),
			callback: (r) => {
				const m = r.message || {};
				if (m.holat === "tayyor") {
					frappe.show_alert({
						message: __("Transkript tayyor: {0} so'z ({1})", [m.sozlar, m.model]),
						indicator: "green",
					}, 7);
				} else {
					frappe.show_alert({
						message: __("Transkripsiya bo'lmadi: {0}", [m.sabab || m.holat || "?"]),
						indicator: "orange",
					}, 10);
				}
				frm.reload_doc();
			},
		});
	}, __("AI"));
}
