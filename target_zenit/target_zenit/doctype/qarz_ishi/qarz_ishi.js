// Qarz Ishi formasi — "Aloqa tarixi (izohlar)" bo'limi.
// Izohlar `Aloqa Yozuvi`da saqlanadi (qarzdorlik paneli ham shu manbadan
// o'qiydi). Yozuvlar O'QUVCHI bo'yicha ko'rsatiladi: qarz to'langanda ish
// yopilib yangi ish ochiladi, suhbatlar esa eski ishda qolib ketadi.

frappe.ui.form.on("Qarz Ishi", {
	refresh(frm) {
		aloqa_tarixini_chiz(frm);
	},
});

function aloqa_tarixini_chiz(frm) {
	const $joy = frm.get_field("aloqa_tarixi").$wrapper;
	if (frm.is_new()) {
		$joy.html("");
		return;
	}
	$joy.html(`<div class="text-muted">Yuklanmoqda…</div>`);
	frappe.call({
		method: "target_zenit.target_zenit.doctype.qarz_ishi.qarz_ishi.aloqa_tarixi",
		args: { qarz_ishi: frm.doc.name },
		callback: (r) => {
			const rows = r.message || [];
			if (!rows.length) {
				$joy.html(`<div class="text-muted">Hali aloqa yozuvi yo'q.
					Izohlar «Qarzdorlik paneli»dagi «Qo'ng'iroq natijasi» oynasidan yoziladi.</div>`);
				return;
			}
			const esc = frappe.utils.escape_html;
			const fmt = (n) => format_currency(n, "UZS");
			const satr = (a) => `
				<div style="border-left:2px solid var(--border-color); padding:4px 0 8px 10px; margin-bottom:6px">
					<div style="font-size:12px">
						<b>${esc(a.kanal || "")}</b> · ${esc(a.aloqa_natijasi || "")}${a.hisob_natijasi ? " → " + esc(a.hisob_natijasi) : ""}
						<span class="text-muted">· ${frappe.datetime.str_to_user(a.vaqt)} · ${esc(a.masul || "")}</span>
						${a.boshqa_ish ? `<span class="indicator-pill gray" title="O'quvchining oldingi ishida yozilgan: ${esc(a.qarz_ishi)}">oldingi ish</span>` : ""}
					</div>
					${a.komment ? `<div style="margin:3px 0; white-space:pre-wrap">${esc(a.komment)}</div>`
						: `<div class="text-muted" style="margin:3px 0">(izoh yozilmagan)</div>`}
					${a.vada_summa ? `<div style="font-size:12px">Va'da: <b>${fmt(a.vada_summa)}</b> — ${frappe.datetime.str_to_user(a.vada_sana)}</div>` : ""}
					<div class="text-muted" style="font-size:11px">Keyingi: ${esc(a.keyingi_harakat || "—")}
						${a.keyingi_sana ? "· " + frappe.datetime.str_to_user(a.keyingi_sana) : ""}</div>
				</div>`;
			const boshqa = rows.filter((a) => a.boshqa_ish).length;
			$joy.html(`
				<div style="font-size:12px; margin-bottom:6px" class="text-muted">
					${rows.length} ta aloqa yozuvi (o'quvchi bo'yicha${boshqa ? `, shundan ${boshqa} tasi oldingi ishlarda` : ""})
				</div>
				${rows.map(satr).join("")}`);
		},
	});
}
