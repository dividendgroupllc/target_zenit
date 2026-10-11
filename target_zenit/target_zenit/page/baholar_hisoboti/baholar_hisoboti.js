// Copyright (c) 2026, Target Zenit — Baholar hisoboti (choraklik/yillik)
// Guruh + chorak tanlanadi -> o'quvchilar o'rtacha baho + davomat yig'indisi.
frappe.pages["baholar-hisoboti"].on_page_load = function (wrapper) {
	new TZBaholarHisoboti(wrapper);
};

const BH_M = "target_zenit.dars_jadvali.baholash";
const BH_OJ = "target_zenit.dars_jadvali.oqituvchi_jadval";

class TZBaholarHisoboti {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Baholar hisoboti"), single_column: true });
		this.guruh = "";
		this.chorak = "";
		this.fan = "";
		this.guruhlar = [];
		this.choraklar = [];
		this.fanlar = [];
		this.make_skeleton();
		this.boot();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-bh"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	boot() {
		frappe.call({
			method: `${BH_OJ}.filtr_variantlari`,
			callback: (r) => {
				const m = r.message || {};
				this.guruhlar = (m.guruhlar || []).filter((g) => g.custom_guruh_turi === "Sinf");
				this.fanlar = m.fanlar || [];
				if (this.guruhlar[0]) this.guruh = this.guruhlar[0].name;
				frappe.call({ method: `${BH_M}.choraklar`, callback: (r2) => { this.choraklar = r2.message || []; this.render(); }, error: () => this.render() });
			},
			error: () => this.render(),
		});
	}
	load() {
		if (!this.guruh) { this.renderTable({ oquvchilar: [] }); return; }
		frappe.call({
			method: `${BH_M}.guruh_hisobot`,
			args: { guruh: this.guruh, chorak: this.chorak || undefined, fan: this.fan || undefined },
			callback: (r) => this.renderTable(r.message), error: () => this.renderTable(null),
		});
	}
	render() {
		this.body.html(`
			<div class="topbar"><h1>Baholar hisoboti</h1>
				<div class="sub">Choraklik / yillik — o'quvchilar o'rtacha bahosi va davomati</div></div>
			<div class="filters">
				<select class="fg"><option value="">Sinf tanlang</option>${this.guruhlar.map((g) => `<option value="${this.esc(g.name)}" ${this.guruh === g.name ? "selected" : ""}>${this.esc(g.student_group_name || g.name)}</option>`).join("")}</select>
				<select class="fc"><option value="">Yillik (barcha chorak)</option>${this.choraklar.map((c) => `<option value="${this.esc(c.name)}" ${this.chorak === c.name ? "selected" : ""}>${this.esc(c.term_name || c.name)}</option>`).join("")}</select>
				<select class="ff"><option value="">Barcha fanlar</option>${this.fanlar.map((f) => `<option value="${this.esc(f)}" ${this.fan === f ? "selected" : ""}>${this.esc(f)}</option>`).join("")}</select>
			</div>
			<div class="card tbl-wrap"><div class="loading">Tanlang…</div></div>
		`);
		this.body.find(".fg").on("change", (e) => { this.guruh = e.target.value; this.load(); });
		this.body.find(".fc").on("change", (e) => { this.chorak = e.target.value; this.load(); });
		this.body.find(".ff").on("change", (e) => { this.fan = e.target.value; this.load(); });
		if (this.guruh) this.load();
	}
	renderTable(d) {
		const w = this.body.find(".tbl-wrap");
		if (!d) { w.html(`<div class="empty">Xatolik</div>`); return; }
		if (!(d.oquvchilar || []).length) { w.html(`<div class="empty">Ma'lumot yo'q (bu sinf/chorakда baho qo'yilmagan)</div>`); return; }
		const html = `<table class="tbl"><thead><tr>
			<th>O'quvchi</th><th class="r">O'rtacha baho</th><th class="r">Baho soni</th>
			<th class="r kem">Kelmadi</th><th class="r kas">Kasal</th><th class="r qat">Qatnashmadi</th></tr></thead><tbody>
			${d.oquvchilar.map((o) => `<tr>
				<td>${this.esc(o.student_name)}</td>
				<td class="r"><b class="${o.ortacha >= 4 ? "g" : o.ortacha != null && o.ortacha < 3 ? "b" : ""}">${o.ortacha != null ? o.ortacha : "—"}</b></td>
				<td class="r">${o.baho_soni}</td>
				<td class="r kem">${o.kelmadi || ""}</td>
				<td class="r kas">${o.kasal || ""}</td><td class="r qat">${o.qatnashmadi || ""}</td>
			</tr>`).join("")}
			</tbody></table>
			<div class="note">«Keldi» belgilash shart emas — belgilanmagan o'quvchi kelgan hisoblanadi. Faqat kelmaganlar va baholar saqlanadi.</div>`;
		w.html(html);
	}
}
