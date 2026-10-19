// Copyright (c) 2026, Target Zenit
// Avto transkripsiya holati: ishlayaptimi, ishlamasa NEGA + eski yozuvlarni o'tkazish.
// Sozlamada ikkita o'chirgich bor (AI yoqilgan + provayder), shuning uchun
// "yoqdim, lekin ishlamaydi" holatini panel aniq aytib beradi.
frappe.ui.form.on("Telefoniya Sozlamalari", {
	refresh(frm) {
		holat_chiz(frm);
		frm.add_custom_button(__("Eski yozuvlarni transkripsiya qilish"), () => {
			frappe.confirm(
				__("Transkripti yo'q barcha yozuvlar navbatga qo'yiladi. Har biri uchun API to'lovi ketadi. Davom etamizmi?"),
				() => frappe.call({
					method: "target_zenit.telefoniya.stt.hammasini_qil",
					freeze: true,
					callback: (r) => {
						const m = r.message || {};
						frappe.msgprint({
							title: __("Navbatga qo'yildi"), indicator: "green",
							message: m.navbatga_qoyildi != null
								? __("{0} ta yozuv navbatga qo'yildi. Fon vazifasi ishlaydi — bir necha daqiqadan keyin ro'yxatni yangilang.", [m.navbatga_qoyildi])
								: JSON.stringify(m),
						});
						setTimeout(() => holat_chiz(frm), 1500);
					},
				})
			);
		}, __("AI"));
	},
	ai_yoqilgan(frm) { frm.save().then(() => holat_chiz(frm)); },
	stt_provayder(frm) { holat_chiz(frm); },
});

function holat_chiz(frm) {
	const maydon = frm.get_field("stt_holat_html");
	if (!maydon) return;
	frappe.call({
		method: "target_zenit.telefoniya.stt.avto_holat",
		callback: (r) => {
			const d = r.message || {};
			const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
			const bosh = d.ishlayapti
				? `<div style="color:#1a7f37;font-weight:600">✅ Avto transkripsiya YOQILGAN</div>
				   <div class="text-muted" style="font-size:11px">Yangi yozuv kelishi bilan o'zi matnga aylanadi — tugma bosish kerak emas.</div>`
				: `<div style="color:#d8443c;font-weight:600">❌ Avto transkripsiya O'CHIQ</div>
				   <ul style="margin:4px 0 0 18px;font-size:12px">${(d.sabablar || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
			maydon.$wrapper.html(`
				<div style="border:1px solid var(--border-color);border-radius:8px;padding:10px 12px">
					${bosh}
					<div style="margin-top:8px;display:flex;gap:18px;flex-wrap:wrap;font-size:12px">
						<span>Yozuvli qo'ng'iroq: <b>${d.jami_yozuv || 0}</b></span>
						<span style="color:#1a7f37">Transkript bor: <b>${d.transkript_bor || 0}</b></span>
						<span style="color:#b45309">Navbatda: <b>${d.navbatda || 0}</b></span>
						<span style="color:#d8443c">Xato: <b>${d.xato || 0}</b></span>
					</div>
					<div class="text-muted" style="margin-top:6px;font-size:11px">
						Model: ${esc(d.model || "—")}${d.zaxira ? ` · zaxira: ${esc(d.zaxira)}` : ""}
						· o'tkazib yuborilganlar har 15 daqiqada qayta uriniladi
					</div>
				</div>`);
		},
	});
}
