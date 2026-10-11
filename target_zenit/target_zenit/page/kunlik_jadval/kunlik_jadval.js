// Copyright (c) 2026, Target Zenit — Kunlik jadval (o'quvchi/ota-ona/o'qituvchi ko'rinishi)
// Sana + sinf (yoki o'qituvchi) -> shu kun darslari KUNLIK LENTA ko'rinishida, o'zgarish overlay bilan
// (bekor = chizilgan, o'rinbosar = yangi o'qituvchi yashil). Telefonga mos.
frappe.pages["kunlik-jadval"].on_page_load = function (wrapper) {
	new TZKunlikJadval(wrapper);
};

const KJ_OB = "target_zenit.dars_jadvali.orinbosarlik";
const KJ_OJ = "target_zenit.dars_jadvali.oqituvchi_jadval";

class TZKunlikJadval {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Kunlik jadval"), single_column: true });
		this.sana = frappe.datetime.get_today();
		this.rejim = "sinf"; // sinf | oqituvchi
		this.guruh = "";
		this.oqituvchi = "";
		this.guruhlar = [];
		this.instructors = [];
		this.make_skeleton();
		this.boot();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-kj"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	boot() {
		frappe.call({
			method: `${KJ_OJ}.filtr_variantlari`,
			callback: (r) => {
				this.guruhlar = ((r.message || {}).guruhlar || []);
				const sinf = this.guruhlar.find((g) => g.custom_guruh_turi === "Sinf");
				if (sinf) this.guruh = sinf.name;
				frappe.call({ method: `${KJ_OJ}.oqituvchilar`, callback: (r2) => { this.instructors = r2.message || []; this.load(); }, error: () => this.load() });
			},
			error: () => this.load(),
		});
	}
	load() {
		this.renderShell();
		if (this.rejim === "sinf") {
			if (!this.guruh) { this.renderBody({ darslar: [], xabar: "Sinf tanlang" }); return; }
			frappe.call({ method: `${KJ_OB}.guruh_kun`, args: { sana: this.sana, guruh: this.guruh }, callback: (r) => this.renderBody(r.message), error: () => this.renderBody(null) });
		} else {
			if (!this.oqituvchi) { this.renderBody({ darslar: [], xabar: "O'qituvchi tanlang" }); return; }
			frappe.call({ method: `${KJ_OB}.kun_darslari`, args: { sana: this.sana, oqituvchi: this.oqituvchi }, callback: (r) => this.renderBody(r.message), error: () => this.renderBody(null) });
		}
	}
	guruhOptions() {
		const byType = {};
		this.guruhlar.forEach((g) => { (byType[g.custom_guruh_turi || "Boshqa"] = byType[g.custom_guruh_turi || "Boshqa"] || []).push(g); });
		const order = ["Sinf", "Daraja", "Tanlov", "Qo'shma", "Qo'shimcha", "Boshqa"];
		const lab = { Sinf: "Sinflar", Daraja: "Darajalar", Tanlov: "Tanlov", "Qo'shma": "Qo'shma", "Qo'shimcha": "Qo'shimcha", Boshqa: "Boshqa" };
		return order.filter((t) => byType[t]).map((t) =>
			`<optgroup label="${this.esc(lab[t] || t)}">${byType[t].map((g) =>
				`<option value="${this.esc(g.name)}" ${this.guruh === g.name ? "selected" : ""}>${this.esc(g.student_group_name || g.name)}</option>`).join("")}</optgroup>`).join("");
	}
	renderShell() {
		const selector = this.rejim === "sinf"
			? `<select class="fsel">${this.guruhOptions()}</select>`
			: `<select class="fsel"><option value="">— o'qituvchi —</option>${this.instructors.map((t) => `<option value="${this.esc(t.name)}" ${this.oqituvchi === t.name ? "selected" : ""}>${this.esc(t.instructor_name)}</option>`).join("")}</select>`;
		this.body.html(`
			<div class="topbar"><h1>Kunlik jadval</h1></div>
			<div class="ctrl">
				<div class="seg">
					<button class="${this.rejim === "sinf" ? "on" : ""}" data-r="sinf">Sinf</button>
					<button class="${this.rejim === "oqituvchi" ? "on" : ""}" data-r="oqituvchi">O'qituvchi</button>
				</div>
				<div class="datebar">
					<button class="nav" data-d="-1">‹</button>
					<input type="date" class="fsana" value="${this.esc(this.sana)}">
					<button class="nav" data-d="1">›</button>
				</div>
				${selector}
			</div>
			<div class="feed"><div class="loading">Yuklanmoqda…</div></div>
		`);
		this.body.find(".seg button").on("click", (e) => { this.rejim = $(e.currentTarget).data("r"); this.load(); });
		this.body.find(".fsana").on("change", (e) => { this.sana = e.target.value; this.load(); });
		this.body.find(".fsel").on("change", (e) => { if (this.rejim === "sinf") this.guruh = e.target.value; else this.oqituvchi = e.target.value; this.load(); });
		this.body.find(".nav").on("click", (e) => { this.sana = frappe.datetime.add_days(this.sana, Number($(e.currentTarget).data("d"))); this.load(); });
	}
	renderBody(d) {
		const feed = this.body.find(".feed");
		if (!d) { feed.html(`<div class="empty">Xatolik</div>`); return; }
		const kunLabel = d.kun ? `${this.esc(d.kun)}, ${this.esc(d.sana)}` : this.esc(d.sana);
		const title = this.rejim === "sinf" ? this.esc(d.guruh_nomi || "") : this.esc((this.instructors.find((t) => t.name === this.oqituvchi) || {}).instructor_name || "");
		if (!d.kun || !(d.darslar || []).length) {
			feed.html(`<div class="day-h">${title} · ${kunLabel}</div><div class="empty">${this.esc(d.xabar || "Bu kun uchun dars yo'q")}</div>`);
			return;
		}
		// dars_raqami bo'yicha guruhlash (parallel darajalar bitta slotda)
		const bySlot = {};
		d.darslar.forEach((x) => { (bySlot[x.dars_raqami] = bySlot[x.dars_raqami] || []).push(x); });
		const slots = Object.keys(bySlot).map(Number).sort((a, b) => a - b);
		const chg = d.darslar.filter((x) => x.ozgarish).length;
		const html = `
			<div class="day-h">${title} · ${kunLabel}${chg ? ` <span class="chgcnt">${chg} o'zgarish</span>` : ""}</div>
			<div class="tl">${slots.map((s) => {
				const items = bySlot[s];
				const b = items[0].boshlanish || "", e = items[0].tugash || "";
				return `<div class="slot">
					<div class="slot-n"><b>${s}</b><span>${this.esc(b)}</span>${e ? `<span class="e">${this.esc(e)}</span>` : ""}</div>
					<div class="slot-items">${items.map((x) => this.lesson(x)).join("")}</div>
				</div>`;
			}).join("")}</div>`;
		feed.html(html);
	}
	lesson(x) {
		const o = x.ozgarish;
		const h = this.rang(x.fan);
		let who, flag = "";
		if (this.rejim === "sinf") {
			const base = x.oqituvchi_nomi || "—";
			if (o && o.tur === "Bekor") { who = `<s>${this.esc(base)}</s>`; flag = `<span class="fl bekor">Bekor qilindi</span>`; }
			else if (o && o.tur === "O'rinbosar") { who = `<s>${this.esc(base)}</s> → <b class="sub">${this.esc(o.yangi_oqituvchi_nomi || "")}</b>`; flag = `<span class="fl cover">O'rinbosar</span>`; }
			else who = this.esc(base);
		} else {
			who = this.esc(x.guruh_nomi || "");
			if (o && o.tur === "Bekor") flag = `<span class="fl bekor">Bekor</span>`;
			else if (o && o.tur === "O'rinbosar") flag = `<span class="fl cover">Siz o'rniga: ${this.esc(o.yangi_oqituvchi_nomi || "")}</span>`;
		}
		return `<div class="les ${o ? (o.tur === "Bekor" ? "is-bekor" : "is-cover") : ""}" style="--h:${h}">
			<div class="les-f">${this.esc(x.fan)}</div>
			<div class="les-w">${who}</div>
			${x.xona ? `<div class="les-x">🚪 ${this.esc(x.xona)}</div>` : ""}
			${flag}${o && o.sabab ? `<div class="les-s">${this.esc(o.sabab)}</div>` : ""}
		</div>`;
	}
}
