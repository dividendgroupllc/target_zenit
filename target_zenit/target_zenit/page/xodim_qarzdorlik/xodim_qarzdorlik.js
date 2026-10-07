// Copyright (c) 2026, Target Zenit — Xodimlar qarzdorligi
// O'qituvchi va xodimlar bitta jadvalda: hisoblangan / to'langan / saldo.
// Saldo > 0 — xodim kompaniyaga qarzdor; saldo < 0 — kompaniya xodimga qarzdor.
frappe.pages["xodim-qarzdorlik"].on_page_load = function (wrapper) {
	new TZXodimQarzPanel(wrapper);
};

const XQ_M = "target_zenit.target_zenit.page.xodim_qarzdorlik.xodim_qarzdorlik";

class TZXodimQarzPanel {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Xodimlar qarzdorligi"), single_column: true });
		this.data = null;
		this.selected = null;
		this.q = "";
		this.fTur = "qarzdor"; // qarzdor | kompaniya | hamma
		this.fLavozim = "";    // lavozim (guruh) filtri
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : "—"; }
	fmt(n) {
		n = Math.round(Number(n) || 0);
		const s = Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
		return (n < 0 ? "−" : "") + s;
	}
	saldoPill(v) {
		if (v > 1000) return `<span class="pill bk-b4">Xodim qarzdor</span>`;
		if (v < -1000) return `<span class="pill st-blue">Kompaniya qarzdor</span>`;
		return `<span class="pill st-mut">0</span>`;
	}

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-qarz tz-xodim"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${XQ_M}.get_data`,
			callback: (r) => { this.data = r.message || { rows: [], stats: {} }; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	// Ro'yxatdagi lavozimlar (guruh sifatida), alfavit tartibida
	lavozimlar() {
		const set = new Set((this.data.rows || []).map((r) => r.lavozim).filter(Boolean));
		return [...set].sort((a, b) => a.localeCompare(b));
	}

	filtered() {
		const q = this.q.trim().toLowerCase();
		return (this.data.rows || []).filter((r) => {
			if (this.fTur === "qarzdor" && !(r.saldo > 1000)) return false;
			if (this.fTur === "kompaniya" && !(r.saldo < -1000)) return false;
			if (this.fLavozim === "__none" && r.lavozim) return false;
			if (this.fLavozim && this.fLavozim !== "__none" && r.lavozim !== this.fLavozim) return false;
			if (q) {
				const hay = [r.ism, r.lavozim, r.telefon, r.employee].join(" ").toLowerCase();
				if (!hay.includes(q)) return false;
			}
			return true;
		});
	}

	render() {
		const st = this.data.stats || {};
		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Xodimlar qarzdorligi</h1>
					<div class="sub">O'qituvchi va xodimlar — bitta jadvalda · GL asosida jonli hisob</div>
				</div>
				<div class="spacer"></div>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="grid cols-3 mb kpis">
				<div class="card kpi click ${this.fTur === "qarzdor" ? "sel" : ""}" data-t="qarzdor">
					<div class="lab"><span class="pin r"></span>Xodimlar kompaniyaga qarzdor</div>
					<div class="val">${this.fmt(st.xodim_qarzi)} <span class="cur">so'm</span></div>
					<div class="sub">${this.fmt(st.xodim_qarzi_soni)} kishi (avans, qarz, ortiqcha to'lov)</div></div>
				<div class="card kpi click ${this.fTur === "kompaniya" ? "sel" : ""}" data-t="kompaniya">
					<div class="lab"><span class="pin b"></span>Kompaniya xodimlarga qarzdor</div>
					<div class="val">${this.fmt(st.kompaniya_qarzi)} <span class="cur">so'm</span></div>
					<div class="sub">${this.fmt(st.kompaniya_qarzi_soni)} kishi (to'lanmagan oylik)</div></div>
				<div class="card kpi click ${this.fTur === "hamma" ? "sel" : ""}" data-t="hamma">
					<div class="lab"><span class="pin g"></span>Jami ro'yxatda</div>
					<div class="val">${this.fmt(st.jami)}</div>
					<div class="sub">hamma xodim va o'qituvchilar</div></div>
			</div>

			<div class="controls mb">
				<input type="text" class="q" placeholder="Qidiruv: ism, lavozim, telefon…" value="${this.esc(this.q)}">
				<select class="flavozim">
					<option value="">Barcha lavozimlar</option>
					<option value="__none" ${this.fLavozim === "__none" ? "selected" : ""}>Lavozimsiz</option>
					${this.lavozimlar().map((l) =>
						`<option value="${this.esc(l)}" ${this.fLavozim === l ? "selected" : ""}>${this.esc(l)}</option>`).join("")}
				</select>
			</div>

			<div class="split">
				<div class="list card"></div>
				<div class="detail card"><div class="empty">Xodimni tanlang — harakatlar shu yerda ochiladi</div></div>
			</div>
		`);
		this.render_list();
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".q").on("input", frappe.utils.debounce((e) => { this.q = e.target.value; this.render_list(); }, 250));
		this.body.find(".flavozim").on("change", (e) => { this.fLavozim = e.target.value; this.render_list(); });
		this.body.find(".kpi.click").on("click", (e) => { this.fTur = $(e.currentTarget).data("t"); this.render(); });
	}

	render_list() {
		const rows = this.filtered();
		const html = rows.length
			? `<table class="tbl">
				<thead><tr><th>Xodim</th><th>Lavozim</th><th class="r">Hisoblangan</th><th class="r">To'langan</th><th class="r">Eski qarz</th><th class="r">Saldo (so'm)</th><th>Holat</th><th>Oxirgi harakat</th></tr></thead>
				<tbody>
				${rows.map((r, i) => `
					<tr data-i="${i}" class="${this.selected === i ? "sel" : ""}">
						<td><div class="nm">${r.employee ? `<a class="slink" href="/app/employee/${encodeURIComponent(r.employee)}" onclick="event.stopPropagation()">${this.esc(r.ism)}</a>` : this.esc(r.ism)}</div>
							<div class="mini">${this.esc(r.telefon || "")} ${r.faol ? "" : '<span class="pill st-mut">ishdan ketgan</span>'}</div></td>
						<td>${this.esc(r.lavozim || "—")}</td>
						<td class="r">${this.fmt(r.hisoblangan)}</td>
						<td class="r">${this.fmt(r.tolangan)}</td>
						<td class="r">${r.eski_qarz ? this.fmt(r.eski_qarz) : "—"}</td>
						<td class="r money ${r.saldo > 1000 ? "red2" : r.saldo < -1000 ? "blue2" : ""}">${this.fmt(r.saldo)}</td>
						<td>${this.saldoPill(r.saldo)}</td>
						<td>${this.dmy(r.oxirgi)}</td>
					</tr>`).join("")}
				</tbody></table>`
			: `<div class="empty">Mos xodim topilmadi</div>`;
		this.body.find(".list").html(html);
		this._rows = rows;
		this.body.find(".list tr[data-i]").on("click", (e) => this.show_detail(Number($(e.currentTarget).data("i"))));
	}

	show_detail(i) {
		this.selected = i;
		const r = this._rows[i];
		if (!r) return;
		this.body.find(".list tr[data-i]").removeClass("sel");
		this.body.find(`.list tr[data-i="${i}"]`).addClass("sel");
		this.body.find(".detail").html(`<div class="loading">Yuklanmoqda…</div>`);
		frappe.call({
			method: `${XQ_M}.get_detail`,
			args: { employee: r.employee, jalilov_party: r.jalilov_party },
			callback: (resp) => {
				const d = resp.message || { months: [], gl: [] };
				const months = d.months || [];
				const gl = d.gl || [];
				const oyNomi = (oy) => {
					const [y, m] = String(oy || "").split("-");
					const nomlar = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
						"Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"];
					return nomlar[Number(m)] ? `${nomlar[Number(m)]} ${y}` : oy;
				};
				this.body.find(".detail").html(`
					<div class="d-head">
						<div><div class="d-name">${this.esc(r.ism)} <span class="mini">${this.esc(r.lavozim || "")}</span></div></div>
						<div class="d-debt">
							<div class="d-sum ${r.saldo < 0 ? "blue2" : ""}">${this.fmt(r.saldo)} <span class="cur">so'm</span></div>
							<div>${this.saldoPill(r.saldo)}</div>
						</div>
					</div>
					<div class="box"><div class="box-t">Oylar kesimida (nachisleniya ↔ to'lov)</div>
						<table class="tbl mini-tbl"><thead><tr><th>Oy</th><th class="r">Nachisleniya</th><th class="r">To'langan</th><th class="r">Qoldiq</th></tr></thead>
						<tbody>${months.map((m) => `
							<tr><td>${this.esc(oyNomi(m.oy))}</td>
							<td class="r">${m.hisoblangan ? this.fmt(m.hisoblangan) : "—"}</td>
							<td class="r">${m.tolangan ? this.fmt(m.tolangan) : "—"}</td>
							<td class="r money ${m.farq > 1000 ? "blue2" : m.farq < -1000 ? "red2" : ""}">${this.fmt(m.farq)}</td></tr>`).join("")}
						</tbody></table>
						<div class="mini" style="margin-top:4px">Qoldiq &gt; 0 — shu oy oyligi to'liq to'lanmagan; &lt; 0 — oylikdan ortiq to'langan (avans/qarz)</div>
					</div>
					<div class="box"><div class="box-t">Harakatlar (oxirgi ${gl.length} ta)</div>
						<table class="tbl mini-tbl"><thead><tr><th>Sana</th><th>Oy</th><th>Hujjat</th><th class="r">Hisoblandi</th><th class="r">To'landi</th></tr></thead>
						<tbody>${gl.map((g) => `
							<tr><td>${this.dmy(g.posting_date)}</td>
							<td class="mini">${this.esc(g.oy || "")}</td>
							<td><a href="/app/${g.voucher_type.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(g.voucher_no)}">${this.esc(g.voucher_no)}</a>
								${g.izoh ? `<div class="mini">${this.esc(g.izoh)}</div>` : ""}</td>
							<td class="r">${g.credit ? this.fmt(g.credit) : ""}</td>
							<td class="r">${g.debit ? this.fmt(g.debit) : ""}</td></tr>`).join("")}
						</tbody></table>
					</div>
				`);
			},
		});
	}
}
