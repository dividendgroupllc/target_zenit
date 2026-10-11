// Copyright (c) 2026, Target Zenit — Baho jurnali (eMaktab/kundalik uslubi)
// Guruh + fan + chorak -> o'quvchilar × dars sanalari jadvali. Katak bosilsa tez baho/davomat.
// O'rtacha ustun + davomat yig'indisi (hisobot ham shu yerda vizual).
frappe.pages["baho-jurnali"].on_page_load = function (wrapper) {
	new TZBahoJurnali(wrapper);
};

const BJ_M = "target_zenit.dars_jadvali.baholash";
const BJ_OJ = "target_zenit.dars_jadvali.oqituvchi_jadval";

class TZBahoJurnali {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Baho jurnali"), single_column: true });
		this.guruh = ""; this.fan = ""; this.chorak = "";
		this.guruhlar = []; this.fanlar = []; this.choraklar = [];
		this.make_skeleton();
		this.boot();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-bj"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	boot() {
		frappe.call({
			method: `${BJ_OJ}.filtr_variantlari`,
			callback: (r) => {
				const m = r.message || {};
				this.guruhlar = (m.guruhlar || []).filter((g) => g.custom_guruh_turi === "Sinf");
				this.fanlar = m.fanlar || [];
				if (this.guruhlar[0]) this.guruh = this.guruhlar[0].name;
				frappe.call({ method: `${BJ_M}.choraklar`, callback: (r2) => { this.choraklar = r2.message || []; if (this.choraklar[0]) this.chorak = this.choraklar[0].name; this.render(); }, error: () => this.render() });
			},
			error: () => this.render(),
		});
	}
	render() {
		this.body.html(`
			<div class="topbar"><h1>Baho jurnali</h1>
				<div class="sub">eMaktab uslubida — guruhdagi hamma o'quvchini bitta jadvalda baholang</div></div>
			<div class="filters">
				<select class="fg"><option value="">Sinf</option>${this.guruhlar.map((g) => `<option value="${this.esc(g.name)}" ${this.guruh === g.name ? "selected" : ""}>${this.esc(g.student_group_name || g.name)}</option>`).join("")}</select>
				<select class="ff"><option value="">Fan tanlang</option>${this.fanlar.map((f) => `<option value="${this.esc(f)}" ${this.fan === f ? "selected" : ""}>${this.esc(f)}</option>`).join("")}</select>
				<select class="fc">${this.choraklar.map((c) => `<option value="${this.esc(c.name)}" ${this.chorak === c.name ? "selected" : ""}>${this.esc(c.term_name || c.name)}</option>`).join("")}</select>
			</div>
			<div class="jwrap"><div class="empty">Fan tanlang</div></div>
		`);
		this.body.find(".fg").on("change", (e) => { this.guruh = e.target.value; this.load(); });
		this.body.find(".ff").on("change", (e) => { this.fan = e.target.value; this.load(); });
		this.body.find(".fc").on("change", (e) => { this.chorak = e.target.value; this.load(); });
		if (this.guruh && this.fan) this.load();
	}
	load() {
		if (!this.guruh || !this.fan) { this.body.find(".jwrap").html(`<div class="empty">Fan tanlang</div>`); return; }
		this.body.find(".jwrap").html(`<div class="loading">Yuklanmoqda…</div>`);
		frappe.call({
			method: `${BJ_M}.jurnal_jadval`,
			args: { guruh: this.guruh, fan: this.fan, chorak: this.chorak || undefined },
			callback: (r) => { this.data = r.message; this.renderGrid(); },
			error: () => this.body.find(".jwrap").html(`<div class="empty">Xatolik</div>`),
		});
	}
	cellTxt(c) {
		if (!c) return "";
		if (c.davomat === "Kelmadi") return `<span class="m kem">H</span>`;
		if (c.davomat === "Kasal") return `<span class="m kas">K</span>`;
		if (c.davomat === "Qatnashmadi") return `<span class="m qat">Q</span>`;
		if (c.baho != null) return `<span class="b ${c.baho >= 4 ? "g" : c.baho < 3 ? "r" : "y"}">${c.baho}</span>`;
		return `<span class="dot">•</span>`;
	}
	renderGrid() {
		const d = this.data; if (!d) return;
		if (!(d.qatorlar || []).length) { this.body.find(".jwrap").html(`<div class="empty">Bu sinfda o'quvchi yo'q</div>`); return; }
		if (!(d.ustunlar || []).length) { this.body.find(".jwrap").html(`<div class="empty">Bu chorakда dars sanasi yo'q</div>`); return; }
		const U = d.ustunlar;
		const head = `<tr><th class="nmc">O'quvchi</th>${U.map((u, i) => `<th class="dc" data-c="${i}" title="${this.esc(u.kun)} ${u.dars_raqami}-dars — bosib shu kun jurnalini oching">${this.esc(u.label)}</th>`).join("")}<th class="avc">O'rt.</th></tr>`;
		const rows = d.qatorlar.map((o, ri) => {
			const bahos = o.kataklar.filter((c) => c && c.baho != null).map((c) => c.baho);
			const avg = bahos.length ? (bahos.reduce((a, b) => a + b, 0) / bahos.length).toFixed(1) : "";
			return `<tr>
				<td class="nmc" title="${this.esc(o.student_name)}">${this.esc(o.roll || ri + 1)}. ${this.esc(o.student_name)}</td>
				${o.kataklar.map((c, ci) => `<td class="jc" data-r="${ri}" data-c="${ci}">${this.cellTxt(c)}</td>`).join("")}
				<td class="avc">${avg ? `<b class="${avg >= 4 ? "g" : avg < 3 ? "r" : ""}">${avg}</b>` : "—"}</td>
			</tr>`;
		}).join("");
		this.body.find(".jwrap").html(`<div class="jscroll"><table class="jtbl">${head}${rows}</table></div>
			<div class="note">Katakka bosib baho/davomat qo'ying. H=kelmadi · K=kasal · Q=qatnashmadi · belgilanmagan = keldi.</div>`);
		this.body.find(".jc").on("click", (e) => { const t = $(e.currentTarget); this.editCell(Number(t.data("r")), Number(t.data("c"))); });
		this.body.find(".dc").on("click", (e) => this.editColumn(Number($(e.currentTarget).data("c"))));
	}
	editCell(ri, ci) {
		const self = this; const o = this.data.qatorlar[ri]; const u = this.data.ustunlar[ci]; const c = o.kataklar[ci] || {};
		const dlg = new frappe.ui.Dialog({
			title: __("Baho / Davomat"),
			fields: [
				{ fieldtype: "HTML", options: `<div class="ec-h"><b>${self.esc(o.student_name)}</b> · ${self.esc(u.kun)} ${self.esc(u.label)} · ${self.esc(this.data.fan)}</div>` },
				{ fieldtype: "Select", fieldname: "davomat", label: __("Davomat"), options: "Keldi\nKelmadi\nKasal\nQatnashmadi", default: c.davomat || "Keldi" },
				{ fieldtype: "Int", fieldname: "baho", label: __("Baho (faqat Keldi)"), default: c.baho != null ? c.baho : "" },
			],
			primary_action_label: __("Saqlash"),
			primary_action: (v) => {
				frappe.call({
					method: `${BJ_M}.natija_saqla`,
					args: { jadval_yozuvi: u.jadval_yozuvi, sana: u.sana, qatorlar: JSON.stringify([{ student: o.student, davomat: v.davomat, baho: v.baho || null }]) },
					freeze: true,
					callback: () => {
						o.kataklar[ci] = (v.davomat === "Keldi" && !v.baho) ? null : { davomat: v.davomat, baho: v.davomat === "Keldi" ? (v.baho || null) : null };
						dlg.hide(); self.renderGrid();
					},
				});
			},
		});
		dlg.show();
	}
	editColumn(ci) {
		// Butun kun (ustun) jurnali — o'sha sanadagi barcha o'quvchilar
		const self = this; const u = this.data.ustunlar[ci];
		frappe.call({
			method: `${BJ_M}.dars_oquvchilari`, args: { jadval_yozuvi: u.jadval_yozuvi, sana: u.sana },
			freeze: true, callback: (r) => { if (r.message) self.ochKun(r.message, u); },
		});
	}
	ochKun(d, u) {
		const self = this; const DAV = ["Keldi", "Kelmadi", "Kasal", "Qatnashmadi"];
		const rows = (d.oquvchilar || []).map((o, i) => `
			<tr data-student="${self.esc(o.student)}"><td class="r">${o.roll || i + 1}</td><td>${self.esc(o.student_name)}</td>
			<td><select class="k-dav">${DAV.map((x) => `<option value="${x}" ${o.davomat === x ? "selected" : ""}>${x}</option>`).join("")}</select></td>
			<td><input type="number" class="k-b" value="${o.baho != null ? o.baho : ""}" ${o.davomat !== "Keldi" ? "disabled" : ""}></td></tr>`).join("");
		const dlg = new frappe.ui.Dialog({
			title: `${self.esc(this.data.fan)} · ${self.esc(u.kun)} ${self.esc(u.label)}`, size: "large",
			fields: [{ fieldtype: "HTML", options: `<div class="jur-wrap2"><table class="jur-tbl2"><thead><tr><th>№</th><th>O'quvchi</th><th>Davomat</th><th>Baho</th></tr></thead><tbody>${rows}</tbody></table></div>` }],
			primary_action_label: __("Saqlash"),
			primary_action: () => {
				const qs = [];
				dlg.$wrapper.find("tbody tr").each(function () { const $t = $(this); const bv = $t.find(".k-b").val(); qs.push({ student: $t.data("student"), davomat: $t.find(".k-dav").val(), baho: bv ? Number(bv) : null }); });
				frappe.call({ method: `${BJ_M}.natija_saqla`, args: { jadval_yozuvi: u.jadval_yozuvi, sana: u.sana, qatorlar: JSON.stringify(qs) }, freeze: true,
					callback: (r) => { if (r.message) { frappe.show_alert({ message: __("Saqlandi: ") + r.message.saqlandi, indicator: "green" }); dlg.hide(); self.load(); } } });
			},
		});
		dlg.$wrapper.on("change", ".k-dav", function () { const $b = $(this).closest("tr").find(".k-b"); if ($(this).val() === "Keldi") $b.prop("disabled", false); else $b.prop("disabled", true).val(""); });
		dlg.show();
	}
}
