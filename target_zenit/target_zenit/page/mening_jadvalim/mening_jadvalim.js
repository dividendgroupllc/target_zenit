// Copyright (c) 2026, Target Zenit — "Mening jadvalim" (o'qituvchi)
// Bugungi darslar (davomat olish tugmasi bilan) + haftalik jadval + hafta navigatsiyasi.
// Dars audiosi bu sahifada EMAS — «dars sessiyasi» kokpitidagi mavzu kartasida.
frappe.pages["mening-jadvalim"].on_page_load = function (wrapper) {
	new TZMeningJadvalim(wrapper);
};

const MJ_M = "target_zenit.target_zenit.page.mening_jadvalim.mening_jadvalim";

class TZMeningJadvalim {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Mening jadvalim"), single_column: true });
		this.oqituvchi = null;
		this.hafta = 0;          // 0 = shu hafta, -1 = o'tgan, +1 = keyingi
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }
	kunQisqa(k) { return ({ Dushanba: "Du", Seshanba: "Se", Chorshanba: "Ch", Payshanba: "Pa", Juma: "Ju", Shanba: "Sh" })[k] || k; }
	ozgInfo(x) {
		const o = x.ozgarish; if (!o) return "";
		if (o.tur === "Bekor") return `<div class="ozg bekor">⛔ Bu dars bugun bekor qilindi${o.sabab ? ` — ${this.esc(o.sabab)}` : ""}</div>`;
		if (o.tur === "O'rinbosar") return `<div class="ozg cover">🔄 O'rinbosar: <b>${this.esc(o.yangi_oqituvchi_nomi || "")}</b> (siz bu darsга kirmaysiz)</div>`;
		return "";
	}
	// Hafta yorlig'i: «12–16 okt» (shu hafta bo'lsa — «Shu hafta»)
	haftaLabel(d) {
		const oy = ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"];
		const b = String(d.hafta_boshi || "").split("-"), o = String(d.hafta_oxiri || "").split("-");
		if (b.length !== 3) return "Hafta";
		const diapazon = `${+b[2]}–${+o[2]} ${oy[+b[1] - 1] || ""}`;
		return d.shu_hafta ? `Shu hafta · ${diapazon}` : diapazon;
	}

	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval tz-mening"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${MJ_M}.get_data`,
			args: { oqituvchi: this.oqituvchi, hafta: this.hafta },
			callback: (r) => { this.data = r.message || {}; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`),
		});
	}

	render() {
		const d = this.data;
		if (!d.oqituvchi) {
			this.body.html(`<div class="loading">Sizning hisobingizga o'qituvchi (Instructor) yozuvi bog'lanmagan.<br>
				Iltimos, administratorga murojaat qiling.</div>`);
			return;
		}
		const bugungi = (d.darslar || []).filter((x) => x.kun === d.bugun_kuni);
		const kunlar = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"];

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>${this.esc(d.oqituvchi_nomi || "Mening jadvalim")}</h1>
					<div class="sub">${this.esc(d.versiya || "")} · haftalik ${d.haftalik_soat || 0} dars · bugun ${this.esc(d.bugun_kuni)}</div>
				</div>
				<div class="spacer"></div>
				${d.menejer ? `<select class="foqituvchi">
					<option value="">— o'qituvchini tanlang —</option>
					${(d.oqituvchilar || []).map((o) => `<option value="${this.esc(o.name)}" ${o.name === d.oqituvchi ? "selected" : ""}>${this.esc(o.instructor_name)}</option>`).join("")}
				</select>` : ""}
				<button class="refresh" data-act="mavzu" title="Butun chorak mavzularini bir martada biriktirish">📘 Mavzular</button>
				<span class="hafta-nav">
					<button class="refresh" data-act="h-prev" title="o'tgan hafta">‹</button>
					<button class="refresh h-lbl" data-act="h-bugun" title="shu haftaga qaytish">${this.haftaLabel(d)}</button>
					<button class="refresh" data-act="h-next" title="keyingi hafta">›</button>
				</span>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			${(d.cover_vazifalar || []).filter((c) => c.sana !== d.bugun_sana).length ? `
			<div class="card cover-card">
				<div class="box-t">🔄 Zavuch yuklagan qo'shimcha darslar (shu hafta, boshqa kunlar)</div>
				${d.cover_vazifalar.filter((c) => c.sana !== d.bugun_sana).map((c) => `
					<div class="cv-row">
						<div class="cv-when"><b>${this.esc(this.kunQisqa(c.kun))}</b> ${this.esc(this.dmy(c.sana))}<span>${this.esc(c.boshlanish)}–${this.esc(c.tugash)}</span></div>
						<div class="cv-info"><b>${this.esc(c.fan)}</b> · ${this.esc(c.guruh_nomi)}<div class="mini">asl o'qituvchi: ${this.esc(c.asl_oqituvchi_nomi || "—")}${c.sabab ? ` · ${this.esc(c.sabab)}` : ""}</div></div>
					</div>`).join("")}
			</div>` : ""}

			<div class="hafta">
				${kunlar.map((k) => {
					const list = (d.darslar || []).filter((x) => x.kun === k);
					return `<div class="card kun-card ${(k === d.bugun_kuni && d.shu_hafta) ? "bugun-card" : ""}">
						<div class="box-t">${k} <span class="mini">${list.length} dars</span></div>
						${list.map((x) => `<div class="w-row ${x.ozgarish ? (x.ozgarish.tur === "Bekor" ? "w-bekor" : "w-cover") : ""}" data-jy="${this.esc(x.name)}" data-sana="${this.esc(x.sana)}" style="--h:${this.rang(x.fan)}" ${x.ozgarish ? `title="${x.ozgarish.tur === "Bekor" ? "Bekor qilindi" : "O'rinbosar: " + this.esc(x.ozgarish.yangi_oqituvchi_nomi || "")}"` : ""}>
							<span class="no">${x.dars_raqami}</span>
							<span class="t">${this.esc(x.boshlanish)}${x.tugash ? "–" + this.esc(x.tugash) : ""}</span>
							<span class="f">${this.esc(x.fan)}</span>
							<span class="g">${this.esc(x.sinflar || x.guruh_nomi || "")}</span>
							${x.ozgarish ? `<span class="w-chg">${x.ozgarish.tur === "Bekor" ? "✕" : "↷"}</span>` : (x.bugun ? `<span class="w-ok" title="O'tildi: ${this.esc((x.bugun || {}).mavzu || "")}">✓</span>` : "")}
						</div>`).join("") || `<div class="empty mini">—</div>`}
					</div>`;
				}).join("")}
			</div>
		`);

		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(`[data-act="h-prev"]`).on("click", () => { this.hafta -= 1; this.load(); });
		this.body.find(`[data-act="h-next"]`).on("click", () => { this.hafta += 1; this.load(); });
		this.body.find(`[data-act="h-bugun"]`).on("click", () => { if (this.hafta) { this.hafta = 0; this.load(); } });
		this.body.find(`[data-act="mavzu"]`).on("click", () => {
			if (!window.tz_mavzu_dialog) { frappe.show_alert({ message: "Sahifani yangilang (Ctrl+Shift+R)", indicator: "orange" }); return; }
			window.tz_mavzu_dialog({ onsave: () => this.load() });
		});
		this.body.find(".foqituvchi").on("change", (e) => { this.oqituvchi = e.target.value; this.load(); });
	}
}

// DARS KOKPITI OLIB TASHLANDI (2026-11-08): davomat, baho, uy vazifa va
// «darsni o'tdim» belgisi MOODLE'ga ko'chdi (o'qituvchi paneli + mobil ilova).
// Bu sahifada endi faqat o'qituvchining haftalik JADVALI va zavuch yuklagan
// o'rinbosarlik vazifalari ko'rinadi; 📘 Mavzular tugmasi esa rejani kiritadi.
