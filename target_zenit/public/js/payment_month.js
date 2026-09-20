// "За какой месяц" — Journal Entry / Payment Entry / Sales Invoice uchun.
// Ro'yxat ochilganda UCHTA oy ko'rinadi (o'tgan, shu, kelasi),
// lekin yozib qidirsa 24 oy orqaga va 12 oy oldinga bo'lgan oylar ham topiladi.
// Format: yil oldin — "2026 Avgust". Bazada "2026-08" saqlanadi.
(function () {
	const MONTHS_UZ = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
		"Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];

	function entry(offset) {
		const now = new Date();
		const dt = new Date(now.getFullYear(), now.getMonth() + offset, 1);
		const m = dt.getMonth();
		const y = dt.getFullYear();
		return {
			value: `${y}-${String(m + 1).padStart(2, "0")}`,
			label: `${y} ${MONTHS_UZ[m]}`,
		};
	}

	function options() {
		const head = [entry(-1), entry(0), entry(1)];
		const seen = new Set(head.map((o) => o.value));
		const rest = [];
		for (let d = -24; d <= 12; d++) {
			const e = entry(d);
			if (!seen.has(e.value)) { seen.add(e.value); rest.push(e); }
		}
		return head.concat(rest);
	}

	function apply(frm) {
		const ctrl = frm.get_field("custom_payment_month");
		if (!ctrl) return;
		const opts = options();
		frm.set_df_property("custom_payment_month", "options", opts);
		frm.set_df_property("custom_payment_month", "max_items", 3);
		if (ctrl.set_data) ctrl.set_data(opts);
		if (ctrl.awesomplete) ctrl.awesomplete.maxItems = 3;
	}

	// Tanlov FAQAT Payment Entry'da: u yerda pul chiqqan sana bilan oylik oyi
	// har xil bo'lishi mumkin. Journal Entry va Sales Invoice'da esa oy posting
	// date'dan avtomatik olinadi (maydon read-only), shuning uchun picker kerak emas.
	frappe.ui.form.on("Payment Entry", {
		refresh: apply,
		posting_date(frm) {
			apply(frm);
			if (!frm.doc.custom_payment_month && frm.doc.posting_date) {
				frm.set_value("custom_payment_month", String(frm.doc.posting_date).slice(0, 7));
			}
		},
	});
})();
