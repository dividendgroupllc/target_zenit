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
			${d.oquvchilar.map((o) => `<tr class="st-row" data-student="${this.esc(o.student)}" title="Hisobot kartasi — bosing">
				<td><span class="st-link">${this.esc(o.student_name)}</span></td>
				<td class="r"><b class="${o.ortacha >= 4 ? "g" : o.ortacha != null && o.ortacha < 3 ? "b" : ""}">${o.ortacha != null ? o.ortacha : "—"}</b></td>
				<td class="r">${o.baho_soni}</td>
				<td class="r kem">${o.kelmadi || ""}</td>
				<td class="r kas">${o.kasal || ""}</td><td class="r qat">${o.qatnashmadi || ""}</td>
			</tr>`).join("")}
			</tbody></table>
			<div class="note">«Keldi» belgilash shart emas — belgilanmagan o'quvchi kelgan hisoblanadi. O'quvchi ustiga bosib to'liq kartasini ko'ring.</div>`;
		w.html(html);
		w.find(".st-row").on("click", (e) => this.showCard($(e.currentTarget).data("student")));
	}

	showCard(student) {
		const self = this;
		frappe.call({
			method: `${BH_M}.oquvchi_karta`, args: { student: student },
			freeze: true, freeze_message: "Yuklanmoqda…",
			callback: (r) => {
				const d = r.message; if (!d) return;
				const chs = d.choraklar || [];
				const head = `<tr><th>Fan</th>${chs.map((c) => `<th class="r">${self.esc(c.label)}</th>`).join("")}<th class="r">Yillik</th></tr>`;
				const cell = (c) => {
					if (!c) return `<td class="r">—</td>`;
					const abs = (c.kelmadi || c.kasal || c.qatnashmadi)
						? `<span class="ab" title="kelmadi/kasal/qatnashmadi">${c.kelmadi || 0}/${c.kasal || 0}/${c.qatnashmadi || 0}</span>` : "";
					return `<td class="r">${c.ortacha != null ? `<b>${c.ortacha}</b>` : "—"} ${abs}</td>`;
				};
				const rows = (d.jadval || []).map((f) => `<tr><td>${self.esc(f.fan)}</td>${f.choraklar.map(cell).join("")}<td class="r yil">${f.yillik != null ? `<b>${f.yillik}</b>` : "—"}</td></tr>`).join("")
					|| `<tr><td colspan="9" class="empty">Baho yo'q</td></tr>`;
				const html = `<div class="card-h">${self.esc(d.ism)}</div>
					<div class="card-wrap"><table class="card-tbl"><thead>${head}</thead><tbody>${rows}</tbody></table></div>
					<div class="note">Katakda: <b>o'rtacha baho</b> · kichik — kelmadi/kasal/qatnashmadi soni.</div>`;
				const dlg = new frappe.ui.Dialog({ title: __("Hisobot kartasi"), size: "large", fields: [{ fieldtype: "HTML", fieldname: "h", options: html }] });
				dlg.show();
			},
		});
	}
}
