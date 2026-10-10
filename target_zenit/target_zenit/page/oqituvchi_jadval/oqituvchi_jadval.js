// Copyright (c) 2026, Target Zenit — O'qituvchilar bandligi
// Zavuch: o'qituvchi tanlanadi -> haftalik band/bo'sh grid (qaysi sinfga dars) + yuklama;
// fan/sinf filtri bilan o'qituvchi ro'yxatini toraytirish; bo'sh katakka bosib dars qo'shish;
// band katakni o'chirish; "kim o'tishi mumkin" kandidatlar.
frappe.pages["oqituvchi-jadval"].on_page_load = function (wrapper) {
	new TZOqituvchiBandligi(wrapper);
};

const OJ_M = "target_zenit.dars_jadvali.oqituvchi_jadval";

class TZOqituvchiBandligi {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("O'qituvchilar bandligi"), single_column: true });
		this.q = "";
		this.fFan = "";
		this.fGuruh = "";
		this.selected = null;
		this.variants = { fanlar: [], guruhlar: [] };
		this.make_skeleton();
		this.boot();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-ojb"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	boot() {
		frappe.call({
			method: `${OJ_M}.filtr_variantlari`,
			callback: (r) => { this.variants = r.message || { fanlar: [], guruhlar: [] }; this.load_list(); },
			error: () => this.load_list(),
		});
	}

	load_list() {
		frappe.call({
			method: `${OJ_M}.oqituvchilar`,
			args: { fan: this.fFan || undefined, guruh: this.fGuruh || undefined },
			callback: (r) => { this.list = r.message || []; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	guruhOptions() {
		const byType = {};
		(this.variants.guruhlar || []).forEach((g) => {
			const t = g.custom_guruh_turi || "Boshqa";
			(byType[t] = byType[t] || []).push(g);
		});
		const order = ["Sinf", "Daraja", "Tanlov", "Qo'shma", "Qo'shimcha", "Boshqa"];
		const label = { Sinf: "Sinflar", Daraja: "Darajalar", Tanlov: "Tanlov", "Qo'shma": "Qo'shma", "Qo'shimcha": "Qo'shimcha", Boshqa: "Boshqa" };
		return order.filter((t) => byType[t]).map((t) =>
			`<optgroup label="${this.esc(label[t] || t)}">${byType[t].map((g) =>
				`<option value="${this.esc(g.name)}" ${this.fGuruh === g.name ? "selected" : ""}>${this.esc(g.student_group_name || g.name)}</option>`).join("")}</optgroup>`).join("");
	}

	render() {
		this.body.html(`
			<div class="topbar">
				<div><h1>O'qituvchilar bandligi</h1>
					<div class="sub">O'qituvchini tanlang — band/bo'sh darslari ko'rinadi · bo'sh katakka bosib dars qo'shing · band katakni bosib o'chiring</div></div>
			</div>
			<div class="filters">
				<select class="ffan"><option value="">Barcha fanlar</option>
					${(this.variants.fanlar || []).map((f) => `<option value="${this.esc(f)}" ${this.fFan === f ? "selected" : ""}>${this.esc(f)}</option>`).join("")}
				</select>
				<select class="fguruh"><option value="">Barcha sinflar/guruhlar</option>${this.guruhOptions()}</select>
				${(this.fFan || this.fGuruh) ? `<button class="clf">✕ filtrni tozalash</button>` : ""}
			</div>
			<div class="split">
				<div class="list card">
					<input type="text" class="q" placeholder="O'qituvchi qidirish…" value="${this.esc(this.q)}">
					<div class="tlist"></div>
				</div>
				<div class="main card"><div class="empty">O'qituvchini tanlang</div></div>
			</div>
		`);
		this.render_list();
		this.body.find(".q").on("input", frappe.utils.debounce((e) => { this.q = e.target.value; this.render_list(); }, 200));
		this.body.find(".ffan").on("change", (e) => { this.fFan = e.target.value; this.load_list(); });
		this.body.find(".fguruh").on("change", (e) => { this.fGuruh = e.target.value; this.load_list(); });
		this.body.find(".clf").on("click", () => { this.fFan = ""; this.fGuruh = ""; this.load_list(); });
		if (this.selected && (this.list || []).some((t) => t.name === this.selected)) this.load_grid(this.selected);
	}

	render_list() {
		const q = this.q.trim().toLowerCase();
		const rows = (this.list || []).filter((t) => !q || (t.instructor_name || "").toLowerCase().includes(q));
		const html = rows.map((t) => `
			<div class="trow ${this.selected === t.name ? "sel" : ""}" data-n="${this.esc(t.name)}">
				<span class="nm">${this.esc(t.instructor_name)}${t.custom_vakant ? ' <span class="vk">vakant</span>' : ""}</span>
				<span class="h">${t.soat} s${t.custom_haftalik_norma ? `/${t.custom_haftalik_norma}` : ""}</span>
			</div>`).join("") || `<div class="empty mini">Topilmadi</div>`;
		this.body.find(".tlist").html(html);
		this.body.find(".trow").on("click", (e) => { this.selected = $(e.currentTarget).data("n"); this.render_list(); this.load_grid(this.selected); });
	}

	load_grid(name) {
		this.body.find(".main").html(`<div class="loading">Yuklanmoqda…</div>`);
		frappe.call({
			method: `${OJ_M}.oqituvchi_tori`, args: { oqituvchi: name },
			callback: (r) => { this.grid = r.message; this.render_grid(); },
		});
	}

	render_grid() {
		const d = this.grid; if (!d) return;
		const y = d.yuklama, kun = d.kunlar;
		const ogoh = (d.ogohlar || []).length
			? `<div class="ogoh">${d.ogohlar.map((o) => `<span>⚠️ ${this.esc(o)}</span>`).join("")}</div>` : "";
		const head = `<tr><th class="c-d">#</th>${kun.map((k) => `<th>${this.esc(k)}<span class="kn">${y.kunlik[k] || 0}</span></th>`).join("")}</tr>`;
		const rows = d.tor.map((qt) => `
			<tr><td class="c-d">${qt.dars}</td>${qt.kataklar.map((c, ki) => this.cell(c, kun[ki], qt.dars)).join("")}</tr>`).join("");
		this.body.find(".main").html(`
			<div class="g-head">
				<div class="g-name">${this.esc(d.nomi)}${d.vakant ? ' <span class="vk">vakant</span>' : ""}</div>
				<div class="g-stat">
					<span class="chip">Jami: <b>${y.jami}</b>${y.norma ? ` / ${y.norma}` : ""} soat</span>
					<span class="chip">Ish kuni: <b>${y.ish_kunlari}</b>${y.max_kun ? ` / ${y.max_kun}` : ""}</span>
					<span class="chip">Max ketma-ket: <b>${y.max_ketma}</b>${y.max_ketma_limit ? ` / ${y.max_ketma_limit}` : ""}</span>
				</div>
			</div>
			${ogoh}
			<div class="legend"><span class="lg band">Band</span><span class="lg bosh">Bo'sh (bosib qo'shing)</span><span class="lg blok">Band emas</span><span class="lg afzal">Afzal</span></div>
			<div class="gtbl-wrap"><table class="gtbl">${head}${rows}</table></div>
		`);
		this.body.find(".cell.bosh").on("click", (e) => {
			const t = $(e.currentTarget); this.darsQoshDialog(t.data("kun"), t.data("dars"));
		});
		this.body.find(".cell.band").on("click", (e) => {
			const t = $(e.currentTarget); this.darsOchir(t.data("name"), t.data("info"));
		});
	}

	cell(c, kun, dars) {
		if (c.holat === "band") {
			const d0 = (c.darslar || [])[0] || {};
			const extra = (c.darslar || []).length > 1 ? ` +${c.darslar.length - 1}` : "";
			const info = `${d0.fan || ""} · ${d0.guruh || ""}`;
			return `<td class="cell band" style="--h:${this.rang(d0.fan)}" data-name="${this.esc(d0.name)}" data-info="${this.esc(info)}" title="${this.esc(info)}${d0.xona ? " · " + this.esc(d0.xona) : ""} — bosib o'chiring">
				<span class="f">${this.esc(d0.fan)}</span><span class="g">${this.esc(d0.guruh || "")}${extra}</span></td>`;
		}
		if (c.holat === "blok") return `<td class="cell blok" title="Band emas (ishlamaydi)"></td>`;
		const cls = c.holat === "afzal" ? "cell afzal bosh" : "cell bosh";
		return `<td class="${cls}" data-kun="${this.esc(kun)}" data-dars="${dars}" title="Bo'sh — bosib dars qo'shing">+</td>`;
	}

	darsQoshDialog(kun, dars) {
		const self = this;
		const dlg = new frappe.ui.Dialog({
			title: __(`${kun}, ${dars}-dars — dars qo'shish`),
			fields: [
				{ fieldtype: "Link", fieldname: "oqituvchi", label: __("O'qituvchi"), options: "Instructor", default: this.selected, reqd: 1 },
				{ fieldtype: "Link", fieldname: "fan", label: __("Fan"), options: "Course", default: this.fFan || undefined, reqd: 1 },
				{ fieldtype: "Link", fieldname: "guruh", label: __("Sinf / guruh"), options: "Student Group", default: this.fGuruh || undefined, reqd: 1 },
				{ fieldtype: "Button", fieldname: "kim", label: __("Kim o'tishi mumkin? (bo'sh o'qituvchilar)") },
				{ fieldtype: "HTML", fieldname: "cand" },
			],
			primary_action_label: __("Qo'shish"),
			primary_action: (v) => {
				frappe.call({
					method: `${OJ_M}.dars_qosh`,
					args: { oqituvchi: v.oqituvchi, kun: kun, dars_raqami: dars, fan: v.fan, guruh: v.guruh },
					freeze: true, freeze_message: __("Qo'shilmoqda…"),
					callback: (r) => {
						if (r.message) {
							frappe.show_alert({ message: __("Dars qo'shildi: ") + self.esc(r.message.fan + " · " + r.message.guruh), indicator: "green" });
							dlg.hide();
							if (v.oqituvchi === self.selected) self.load_grid(self.selected);
							self.load_list();
						}
					},
				});
			},
		});
		// "Kim o'tishi mumkin" — bo'sh+malakali kandidatlarni ko'rsatadi, bosilsa o'qituvchini tanlaydi
		dlg.fields_dict.kim.$input.on("click", () => {
			const fan = dlg.get_value("fan");
			frappe.call({
				method: `${OJ_M}.kim_ola_oladi`,
				args: { kun: kun, dars_raqami: dars, fan: fan || undefined },
				callback: (r) => {
					const list = r.message || [];
					const html = `<div class="oj-cands">${list.slice(0, 30).map((c) =>
						`<div class="oj-cand ${c.fanni_oqitadi ? "fanchi" : ""}" data-n="${self.esc(c.oqituvchi)}">
							<b>${self.esc(c.nomi)}</b> ${c.fanni_oqitadi ? '<span class="t ok">fan</span>' : ""}${c.afzal ? '<span class="t af">afzal</span>' : ""}
							<span class="h">${c.soat}${c.norma ? "/" + c.norma : ""}s</span>${c.ogoh ? ` <i>${self.esc(c.ogoh)}</i>` : ""}
						</div>`).join("") || "<div class='mini'>Bo'sh o'qituvchi yo'q</div>"}</div>`;
					dlg.fields_dict.cand.$wrapper.html(html);
					dlg.fields_dict.cand.$wrapper.find(".oj-cand").on("click", (e) => {
						dlg.set_value("oqituvchi", $(e.currentTarget).data("n"));
					});
				},
			});
		});
		dlg.show();
	}

	darsOchir(name, info) {
		if (!name) return;
		const self = this;
		frappe.confirm(__("O'chirilsinmi? ") + this.esc(info), () => {
			frappe.call({
				method: `${OJ_M}.dars_ochir`, args: { name: name }, freeze: true,
				callback: () => {
					frappe.show_alert({ message: __("O'chirildi"), indicator: "orange" });
					self.load_grid(self.selected); self.load_list();
				},
			});
		});
	}
}
