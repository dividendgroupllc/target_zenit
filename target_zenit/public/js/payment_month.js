// "За какой месяц" — Journal Entry / Payment Entry / Sales Invoice uchun.
// Ro'yxat ochilganda faqat UCHTA variant ko'rinadi (o'tgan / shu / kelasi oy),
// lekin yozib qidirsa 24 oy orqaga va 12 oy oldinga bo'lgan oylar ham topiladi.
// Format: yil oldin — "2026 Avgust". Bazada "2026-08" saqlanadi.
(function () {
	const MONTHS_UZ = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
		"Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];

	function entry(offset, tag) {
		const now = new Date();
		const dt = new Date(now.getFullYear(), now.getMonth() + offset, 1);
		const m = dt.getMonth();
		const y = dt.getFullYear();
		return {
			value: `${y}-${String(m + 1).padStart(2, "0")}`,
			label: `${y} ${MONTHS_UZ[m]}${tag ? " — " + tag : ""}`,
		};
	}

	function options() {
		const head = [entry(-1, "o'tgan oy"), entry(0, "shu oy"), entry(1, "kelasi oy")];
		const seen = new Set(head.map((o) => o.value));
		const rest = [];
		for (let d = -24; d <= 12; d++) {
			const e = entry(d, "");
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

	["Journal Entry", "Payment Entry", "Sales Invoice"].forEach((dt) => {
		frappe.ui.form.on(dt, {
			refresh: apply,
			posting_date(frm) {
				apply(frm);
				// bo'sh bo'lsa — hujjat sanasining oyi (keyin qo'lda o'zgartirsa bo'ladi)
				if (!frm.doc.custom_payment_month && frm.doc.posting_date) {
					frm.set_value("custom_payment_month", String(frm.doc.posting_date).slice(0, 7));
				}
			},
		});
	});
})();
