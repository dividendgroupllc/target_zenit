// Copyright (c) 2026, Target Zenit — O'rinbosarlik (Vertretung)
// Sana + yo'q o'qituvchi -> ta'sirlangan darslar -> ranjlangan cover kandidat (fairness) -> belgilash/bekor.
// Asl jadval o'zgarmaydi — ustiga Jadval Ozgarishi qatlami.
frappe.pages["orinbosarlik"].on_page_load = function (wrapper) {
	new TZOrinbosarlik(wrapper);
};

const OB_M = "target_zenit.dars_jadvali.orinbosarlik";
const OJ_M = "target_zenit.dars_jadvali.oqituvchi_jadval";

class TZOrinbosarlik {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("O'rinbosarlik"), single_column: true });
		this.sana = frappe.datetime.get_today();
		this.oqituvchi = "";
		this.instructors = [];
		this.make_skeleton();
		this.boot();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-ob"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	boot() {
		frappe.call({ method: `${OJ_M}.oqituvchilar`, callback: (r) => { this.instructors = r.message || []; this.load(); }, error: () => this.load() });
	}
	load() {
		frappe.call({
			method: `${OB_M}.kun_darslari`,
			args: { sana: this.sana, oqituvchi: this.oqituvchi || undefined },
			callback: (r) => { this.d = r.message; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`),
		});
	}
	render() {
		const d = this.d || {};
		const opts = `<option value="">Barcha o'qituvchilar</option>` + (this.instructors || []).map((t) =>
			`<option value="${this.esc(t.name)}" ${this.oqituvchi === t.name ? "selected" : ""}>${this.esc(t.instructor_name)} (${t.soat}s)</option>`).join("");
		this.body.html(`
			<div class="topbar"><div><h1>O'rinbosarlik</h1>
				<div class="sub">Yo'q o'qituvchi darslariga o'rinbosar tayinlang — asl jadval o'zgarmaydi</div></div>
				<button class="stat-btn" data-act="stat">📊 Cover statistikasi</button></div>
			<div class="filters">
				<label>Sana: <input type="date" class="fsana" value="${this.esc(this.sana)}"></label>
				<select class="foqit">${opts}</select>
				<span class="kun">${d.kun ? this.esc(d.kun) : ""}</span>
			</div>
			<div class="card tbl-wrap"></div>
		`);
		this.render_table();
		this.body.find(".fsana").on("change", (e) => { this.sana = e.target.value; this.load(); });
		this.body.find(".foqit").on("change", (e) => { this.oqituvchi = e.target.value; this.load(); });
		this.body.find(`[data-act="stat"]`).on("click", () => this.statistika());
	}
	statusCell(x) {
		const o = x.ozgarish;
		if (!o) return `<span class="st normal">—</span>`;
		if (o.tur === "Bekor") return `<span class="st bekor">Bekor</span>`;
		if (o.tur === "O'rinbosar") return `<span class="st cover">→ ${this.esc(o.yangi_oqituvchi_nomi || o.yangi_oqituvchi)}</span>`;
		return `<span class="st">${this.esc(o.tur)}</span>`;
	}
	render_table() {
		const d = this.d || {};
		if (!d.kun) { this.body.find(".tbl-wrap").html(`<div class="empty">${this.esc(d.xabar || "Dam olish kuni")}</div>`); return; }
		if (!(d.darslar || []).length) { this.body.find(".tbl-wrap").html(`<div class="empty">Bu kun uchun dars topilmadi${this.oqituvchi ? " (tanlangan o'qituvchida)" : ""}</div>`); return; }
		const html = `<table class="tbl"><thead><tr><th>#</th><th>Vaqt</th><th>Fan</th><th>Guruh</th><th>Asl o'qituvchi</th><th>Holat</th><th>Amal</th></tr></thead><tbody>
			${d.darslar.map((x) => `<tr data-jy="${this.esc(x.jadval_yozuvi)}" class="${x.ozgarish ? "chg" : ""}">
				<td class="n">${x.dars_raqami}</td><td class="vq">${this.esc(x.boshlanish || "")}${x.tugash ? "–" + this.esc(x.tugash) : ""}</td><td>${this.esc(x.fan)}</td><td>${this.esc(x.guruh_nomi)}</td>
				<td>${this.esc(x.asl_oqituvchi_nomi || x.asl_oqituvchi || "—")}</td>
				<td>${this.statusCell(x)}</td>
				<td class="act">
					${x.ozgarish
						? `<button class="b-rm" data-name="${this.esc(x.ozgarish.name)}">↩ Olib tashlash</button>`
						: `<button class="b-cover">O'rinbosar</button><button class="b-bekor">Bekor</button>`}
				</td></tr>`).join("")}
			</tbody></table>`;
		this.body.find(".tbl-wrap").html(html);
		this.body.find(".b-cover").on("click", (e) => this.coverDialog($(e.currentTarget).closest("tr").data("jy")));
		this.body.find(".b-bekor").on("click", (e) => this.bekor($(e.currentTarget).closest("tr").data("jy")));
		this.body.find(".b-rm").on("click", (e) => this.ochir($(e.currentTarget).data("name")));
	}
	coverDialog(jy) {
		const self = this; const dars = (this.d.darslar || []).find((x) => x.jadval_yozuvi === jy) || {};
		const dlg = new frappe.ui.Dialog({
			title: __(`O'rinbosar — ${dars.fan || ""} · ${dars.guruh_nomi || ""}`),
			fields: [
				{ fieldtype: "HTML", fieldname: "info", options: `<div class="ob-info">Asl: <b>${self.esc(dars.asl_oqituvchi_nomi || "")}</b> · ${self.esc(this.d.kun)}, ${dars.dars_raqami}-dars${dars.boshlanish ? ` (${self.esc(dars.boshlanish)}–${self.esc(dars.tugash)})` : ""} · ${self.esc(this.sana)}</div><div class="ob-cands">Yuklanmoqda…</div>` },
				{ fieldtype: "Small Text", fieldname: "sabab", label: __("Sabab (ixtiyoriy)") },
			],
		});
		dlg.show();
		frappe.call({
			method: `${OB_M}.cover_kandidatlar`, args: { jadval_yozuvi: jy, sana: this.sana },
			callback: (r) => {
				const list = r.message || [];
				const html = list.slice(0, 40).map((c) => `
					<div class="ob-cand ${c.fanni_oqitadi ? "fanchi" : ""}" data-n="${self.esc(c.oqituvchi)}">
						<b>${self.esc(c.nomi)}</b>
						${c.fanni_oqitadi ? '<span class="t ok">fan</span>' : ""}${c.afzal ? '<span class="t af">afzal</span>' : ""}
						<span class="cov">cover: ${c.cover_soni}</span><span class="h">${c.soat}${c.norma ? "/" + c.norma : ""}s</span>
						${c.ogoh ? `<i>${self.esc(c.ogoh)}</i>` : ""}
					</div>`).join("") || "<div class='mini'>Bo'sh o'qituvchi yo'q</div>";
				dlg.fields_dict.info.$wrapper.find(".ob-cands").html(html);
				dlg.fields_dict.info.$wrapper.find(".ob-cand").on("click", (e) => {
					const oq = $(e.currentTarget).data("n");
					frappe.call({
						method: `${OB_M}.cover_belgila`,
						args: { jadval_yozuvi: jy, sana: self.sana, yangi_oqituvchi: oq, sabab: dlg.get_value("sabab") },
						freeze: true, callback: (res) => {
							if (res.message) { frappe.show_alert({ message: __("O'rinbosar: ") + self.esc(res.message.yangi_oqituvchi_nomi), indicator: "green" }); dlg.hide(); self.load(); }
						},
					});
				});
			},
		});
	}
	bekor(jy) {
		const self = this;
		frappe.prompt([{ fieldtype: "Small Text", fieldname: "sabab", label: __("Bekor sababi") }], (v) => {
			frappe.call({ method: `${OB_M}.bekor_qil`, args: { jadval_yozuvi: jy, sana: self.sana, sabab: v.sabab }, freeze: true,
				callback: () => { frappe.show_alert({ message: __("Bekor qilindi"), indicator: "orange" }); self.load(); } });
		}, __("Darsni bekor qilish"), __("Bekor qilish"));
	}
	ochir(name) {
		const self = this;
		frappe.call({ method: `${OB_M}.ozgarish_ochir`, args: { name: name }, freeze: true,
			callback: () => { frappe.show_alert({ message: __("Olib tashlandi"), indicator: "blue" }); self.load(); } });
	}
	statistika() {
		const self = this;
		frappe.call({ method: `${OB_M}.cover_statistika`, callback: (r) => {
			const list = r.message || [];
			const html = list.length
				? `<table class="tbl"><thead><tr><th>O'qituvchi</th><th class="r">O'rinbosar (marta)</th></tr></thead><tbody>
					${list.map((c) => `<tr><td>${self.esc(c.nomi)}</td><td class="r">${c.n}</td></tr>`).join("")}</tbody></table>`
				: "<div class='mini'>Hali o'rinbosarlik yo'q</div>";
			const dlg = new frappe.ui.Dialog({ title: __("Cover statistikasi (fairness)"), fields: [{ fieldtype: "HTML", fieldname: "h", options: html }] });
			dlg.show();
		}});
	}
}
