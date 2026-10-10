// Copyright (c) 2026, Target Zenit — Jadval yetarlilik (feasibility) tahlili
// "Хватит ли учителей?" — jadval tuzishdan oldin sig'im yetadimi: o'qituvchi talab vs sig'im,
// sinf band vs grid, vakant darslar, fan malaka sig'imi.
frappe.pages["jadval-tahlil"].on_page_load = function (wrapper) {
	new TZJadvalTahlil(wrapper);
};

const JT_M = "target_zenit.dars_jadvali.jadval_tahlil";

class TZJadvalTahlil {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Jadval yetarlilik tahlili"), single_column: true });
		this.tab = "oqituvchilar";
		this.make_skeleton();
		this.load();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jt"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	load() {
		frappe.call({ method: `${JT_M}.tahlil`, callback: (r) => { this.d = r.message; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`) });
	}
	render() {
		const d = this.d; if (!d) return;
		const s = d.stats;
		this.body.html(`
			<div class="topbar"><div><h1>Jadval yetarlilik tahlili</h1>
				<div class="sub">Sig'im yetadimi — jadval tuzishdan oldin muammolarni ko'rsatadi · versiya: ${this.esc(d.versiya)}</div></div>
				<button class="refresh" data-act="reload">↻ Yangilash</button></div>
			<div class="cards">
				<div class="kpi"><div class="lab">Jami dars</div><div class="val">${s.jami_dars}</div></div>
				<div class="kpi ${s.vakant ? "bad" : "ok"}"><div class="lab">Vakant (o'qituvchisiz)</div><div class="val">${s.vakant}</div></div>
				<div class="kpi ${s.oq_muammo ? "bad" : "ok"}"><div class="lab">O'qituvchi sig'im muammosi</div><div class="val">${s.oq_muammo}</div></div>
				<div class="kpi ${s.sinf_muammo ? "bad" : "ok"}"><div class="lab">Sinf sig'im muammosi</div><div class="val">${s.sinf_muammo}</div></div>
			</div>
			<div class="tabs">
				<button data-t="oqituvchilar" class="${this.tab === "oqituvchilar" ? "on" : ""}">O'qituvchilar (${d.oqituvchilar.length})</button>
				<button data-t="sinflar" class="${this.tab === "sinflar" ? "on" : ""}">Sinflar (${d.sinflar.length})</button>
				<button data-t="fanlar" class="${this.tab === "fanlar" ? "on" : ""}">Fanlar (${d.fanlar.length})</button>
			</div>
			<div class="card tbl-wrap"></div>
		`);
		this.render_tab();
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".tabs button").on("click", (e) => { this.tab = $(e.currentTarget).data("t"); this.render(); });
	}
	badge(h) {
		if (h === "ok") return `<span class="pill ok">OK</span>`;
		if (h === "toliq") return `<span class="pill full">To'liq</span>`;
		if (h === "norma_oshgan") return `<span class="pill warn">Norma oshgan</span>`;
		if (h === "sigim_oshgan") return `<span class="pill bad">Sig'im oshgan</span>`;
		return `<span class="pill">${this.esc(h)}</span>`;
	}
	render_tab() {
		const d = this.d; let html = "";
		if (this.tab === "oqituvchilar") {
			html = `<table class="tbl"><thead><tr><th>O'qituvchi</th><th class="r">Talab (soat)</th><th class="r">Sig'im</th><th class="r">Norma</th><th class="r">Ish kuni</th><th class="r">Bo'sh</th><th>Holat</th></tr></thead><tbody>
				${d.oqituvchilar.map((o) => `<tr class="${o.holat !== "ok" ? "hl" : ""}">
					<td>${this.esc(o.nomi)}</td><td class="r">${o.talab}</td><td class="r">${o.sigim}</td>
					<td class="r">${o.norma || "—"}</td><td class="r">${o.kunlar_bor}</td>
					<td class="r ${o.bosh < 0 ? "red" : ""}">${o.bosh}</td><td>${this.badge(o.holat)}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Sig'im = mavjud kun/dars slotlari (mavjudlik + limitlardan), norma bo'lsa shu bilan cheklangan. «Sig'im oshgan» = talab > sig'im → jadval yig'ilmaydi (grafik kengaytirish yoki ikkinchi o'qituvchi kerak).</div>`;
		} else if (this.tab === "sinflar") {
			html = `<table class="tbl"><thead><tr><th>Sinf</th><th class="r">Band slot</th><th class="r">Sig'im (grid)</th><th class="r">Bo'sh</th><th>Holat</th></tr></thead><tbody>
				${d.sinflar.map((s) => `<tr class="${s.holat === "sigim_oshgan" ? "hl" : ""}">
					<td>${this.esc(s.sinf)}</td><td class="r">${s.band}</td><td class="r">${s.sigim}</td>
					<td class="r">${s.bosh}</td><td>${this.badge(s.holat)}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Sig'im = ${d.ndars} dars × 5 kun = ${d.grid_sigim}. «Sig'im oshgan» = darslar grid'ga sig'maydi (qo'ng'iroqqa dars qo'shish yoki soat kamaytirish kerak).</div>`;
		} else {
			html = `<table class="tbl"><thead><tr><th>Fan</th><th class="r">Talab (soat)</th><th class="r">O'qituvchilar</th><th class="r">Umumiy sig'im</th><th>Holat</th></tr></thead><tbody>
				${d.fanlar.map((f) => `<tr class="${f.kam ? "hl" : ""}">
					<td>${this.esc(f.fan)}</td><td class="r">${f.talab}</td><td class="r">${f.oqituvchilar_soni}</td>
					<td class="r">${f.umumiy_sigim}</td><td>${f.kam ? this.badge("sigim_oshgan") : this.badge("ok")}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Fanni o'tadigan o'qituvchilarning umumiy sig'imi talabдан kam bo'lsa — malakali o'qituvchi yetmaydi.</div>`;
		}
		this.body.find(".tbl-wrap").html(html);
	}
}
