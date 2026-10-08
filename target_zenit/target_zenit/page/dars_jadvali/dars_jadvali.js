// Copyright (c) 2026, Target Zenit — Dars jadvali (zavuch paneli)
// Sinflar x darslar to'ri, kun bo'yicha. Manba: Jadval Yozuvi (haftalik shablon).
frappe.pages["dars-jadvali"].on_page_load = function (wrapper) {
	new TZDarsJadvali(wrapper);
};

const DJ_M = "target_zenit.target_zenit.page.dars_jadvali.dars_jadvali";

class TZDarsJadvali {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dars jadvali"), single_column: true });
		this.data = null;
		this.kun = "Dushanba";
		this.versiya = null;
		this.fSinf = "";
		this.fOqituvchi = "";
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	// Fan nomidan barqaror rang (har fan doim bir xil rangda)
	rang(fan) {
		let h = 0;
		for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360;
		return h;
	}

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${DJ_M}.get_data`,
			args: { versiya: this.versiya },
			freeze: true,
			callback: (r) => {
				this.data = r.message || {};
				if (this.data.xatolik) {
					this.body.html(`<div class="loading">${this.esc(this.data.xatolik)}</div>`);
					return;
				}
				this.versiya = this.data.versiya;
				this.render();
			},
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	// Sinfga mos qo'ng'iroq jadvali (pattern bo'yicha, tartib bilan)
	vaqt(sinf, no) {
		const qs = Object.values(this.data.qongiroqlar || {}).sort((a, b) => a.tartib - b.tartib);
		for (const q of qs) {
			for (let p of String(q.sinf_pattern || "").split(",")) {
				p = p.trim();
				if (!p) continue;
				const rx = new RegExp("^" + p.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
				if (rx.test(sinf)) {
					const row = (q.qatorlar || []).find((x) => x.turi === "Dars" && x.no === no);
					return row ? `${row.b}–${row.t}` : "";
				}
			}
		}
		return "";
	}

	sinflar() {
		const all = this.data.sinflar || [];
		return this.fSinf ? all.filter((s) => s === this.fSinf) : all;
	}

	render() {
		const d = this.data;
		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Dars jadvali</h1>
					<div class="sub">${this.esc(d.versiya)} · ${d.jami_yozuv} ta dars · ${(d.sinflar || []).length} sinf</div>
				</div>
				<div class="spacer"></div>
				<select class="fversiya">
					${(d.versiyalar || []).map((v) =>
						`<option value="${this.esc(v.name)}" ${v.name === d.versiya ? "selected" : ""}>${this.esc(v.nomi)} — ${this.esc(v.holat)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="controls mb">
				<div class="chips kunlar">
					${(d.kunlar || []).map((k) => `<button class="chip ${this.kun === k ? "on" : ""}" data-kun="${k}">${k}</button>`).join("")}
				</div>
				<div class="spacer"></div>
				<select class="fsinf">
					<option value="">Barcha sinflar</option>
					${(d.sinflar || []).map((s) => `<option value="${this.esc(s)}" ${this.fSinf === s ? "selected" : ""}>${this.esc(s)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="yuklama">O'qituvchi yuklamasi</button>
			</div>

			<div class="jadval-wrap card"></div>
		`);
		this.render_grid();
		this.bind();
	}

	render_grid() {
		const d = this.data;
		const sinflar = this.sinflar();
		const rows = (d.darslar || []).map((no) => {
			const kataklar = sinflar.map((s) => {
				const list = (d.katak || {})[`${s}|${this.kun}|${no}`] || [];
				if (!list.length) return `<td class="bosh"></td>`;
				const inner = list.map((x) => {
					const h = this.rang(x.fan);
					const blok = x.blok ? ` <span class="bk">${this.esc(x.guruh_nomi || "").split(" ")[1] || ""}</span>` : "";
					return `<div class="lesson" style="--h:${h}" data-name="${this.esc(x.name)}" title="${this.esc(x.guruh_nomi || "")}">
						<div class="fan">${this.esc(x.fan)}${blok}</div>
						<div class="oqit">${this.esc(x.oqituvchi || "—")}</div>
					</div>`;
				}).join("");
				return `<td class="${list.length > 1 ? "multi" : ""}">${inner}</td>`;
			}).join("");
			const v = sinflar.length ? this.vaqt(sinflar[0], no) : "";
			return `<tr><th class="dars-no"><b>${no}</b><span>${this.esc(v)}</span></th>${kataklar}</tr>`;
		}).join("");

		this.body.find(".jadval-wrap").html(`
			<div class="scroll-x">
			<table class="grid">
				<thead><tr><th class="dars-no">№</th>${sinflar.map((s) => `<th>${this.esc(s.replace(/\s*\((full|hybrid)\)/, ""))}<span>${this.esc(/hybrid/.test(s) ? "hybrid" : "full")}</span></th>`).join("")}</tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
		`);
		this.body.find(".lesson").on("click", (e) => {
			const n = $(e.currentTarget).data("name");
			frappe.set_route("Form", "Jadval Yozuvi", n);
		});
	}

	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".chip[data-kun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("kun");
			this.render();
		});
		this.body.find(".fsinf").on("change", (e) => { this.fSinf = e.target.value; this.render_grid(); });
		this.body.find(".fversiya").on("change", (e) => { this.versiya = e.target.value; this.load(); });
		this.body.find(`[data-act="yuklama"]`).on("click", () => this.yuklama_dialog());
	}

	yuklama_dialog() {
		const rows = (this.data.yuklama || []).map((y) =>
			`<tr><td>${this.esc(y.oqituvchi)}</td><td class="r ${y.soat >= 35 ? "ogoh" : ""}">${y.soat}</td></tr>`).join("");
		new frappe.ui.Dialog({
			title: "O'qituvchilar haftalik yuklamasi",
			size: "small",
			fields: [{
				fieldtype: "HTML",
				options: `<div class="tz-jadval"><table class="tbl mini-tbl"><thead><tr><th>O'qituvchi</th><th class="r">Soat</th></tr></thead><tbody>${rows}</tbody></table></div>`,
			}],
		}).show();
	}
}
