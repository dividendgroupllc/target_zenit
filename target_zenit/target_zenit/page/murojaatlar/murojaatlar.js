// Copyright (c) 2026, Target Zenit — Murojaatlar (rahbar paneli)
// Ota-onalarning shikoyat / taklif / muammolari: ko'rish, komment yozish,
// qaror qabul qilish va ota-onaga javob berilganini qayd etish.
// BITTA sahifa, rolga qarab o'zini sozlaydi: CEO o'ziga tegishlini, Direktor
// o'zinikini, sotuvchi esa o'zi yo'naltirganini ko'radi.
frappe.pages["murojaatlar"].on_page_load = function (wrapper) {
	new TZMurojaatPanel(wrapper);
};

const MUR_M = "target_zenit.target_zenit.page.murojaatlar.murojaatlar";
const MUR_API = "target_zenit.murojaat.api";

const HOLAT_RANG = {
	"Yangi": "red", "Ko'rib chiqilmoqda": "blue",
	"Ota-onaga xabar berish": "orange", "Yopildi": "green",
};
const QAROR_RANG = {
	"Hal qilindi": "green", "Inobatga olindi": "green",
	"Keyinroq ko'riladi": "orange", "Rad etildi": "mut", "Ahamiyatsiz": "mut",
};
const TUR_BELGI = { "Shikoyat": "⚠", "Taklif": "💡", "Muammo": "❗", "So'rov": "❓" };

class TZMurojaatPanel {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper, title: __("Murojaatlar"), single_column: true,
		});
		this.data = null;
		this.detail = null;
		this.selected = null;
		this.fHolat = "ochiq";     // ochiq | muddati | menda | Yangi | ... | hammasi
		this.fYonalish = "";
		this.fKategoriya = "";
		this.fTuri = "";
		this.fMasul = "";
		this.q = "";
		this.havola = this.havola_oqi();
		this.skeleton();
		this.load(true);
	}

	havola_oqi() {
		const ro = frappe.route_options || {};
		let name = ro.murojaat || null;
		try {
			const u = new URLSearchParams(window.location.search || "");
			name = name || u.get("murojaat");
		} catch (e) { /* URL o'qilmasa muammo emas */ }
		if (name) frappe.route_options = {};
		return name;
	}

	// ================= helpers =================
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	fmt(n) {
		n = Math.round(Number(n) || 0);
		const s = Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
		return (n < 0 ? "−" : "") + s;
	}
	dmy(s) {
		const p = String(s || "").slice(0, 10).split("-");
		return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : "—";
	}
	dt(s) {
		if (!s) return "—";
		return `${this.dmy(s)} ${String(s).slice(11, 16)}`;
	}
	tel(p) {
		p = String(p || "").trim();
		if (!p) return "";
		return `<a class="m-tel" href="tel:${this.esc(p.replace(/[^+\d]/g, ""))}">${this.esc(p)}</a>`;
	}
	kun_farq(sana) {
		if (!sana) return null;
		const a = new Date(String(sana).slice(0, 10)), b = new Date(frappe.datetime.get_today());
		return Math.round((a - b) / 86400000);
	}
	rol() { return (this.data && this.data.rol) || {}; }
	rahbarmi() { const r = this.rol(); return !!(r.ceo || r.direktor); }
	// Faqat kuzatuvchi (investor, operator, moliya): ko'radi, yozmaydi.
	// Server ham to'xtatadi — bu shunchaki tugmalarni yashirish uchun.
	yozamanmi() { return !!this.rol().yozish; }
	// User ismi: ro'yxat/karta hech qachon email ko'rsatmasligi kerak
	masul_nomi(user) {
		if (!user) return "";
		const royxat = (this.data && this.data.masullar) || [];
		const rahbar = (this.data && this.data.rahbarlar) || [];
		const topildi = royxat.find((m) => m.user === user) || rahbar.find((m) => m.user === user);
		return (topildi && topildi.nomi) || user;
	}

	// ================= skeleton =================
	skeleton() {
		this.page.main.html(`
			<div class="mur-wrap">
				<div class="mur-kpi" id="mur-kpi"></div>
				<div class="mur-bar" id="mur-bar"></div>
				<div class="mur-body">
					<div class="mur-list" id="mur-list"></div>
					<div class="mur-detail" id="mur-detail"></div>
				</div>
			</div>`);
		this.page.set_primary_action(__("Yangilash"), () => this.load());
	}

	load(birinchi) {
		frappe.call({
			method: `${MUR_M}.get_data`,
			args: {
				holat: this.fHolat === "hammasi" ? null : this.fHolat,
				yonalish: this.fYonalish || null,
				kategoriya: this.fKategoriya || null,
				turi: this.fTuri || null,
				masul: this.fMasul || null,
				qidiruv: this.q || null,
			},
			freeze: !!birinchi,
			callback: (r) => {
				this.data = r.message || {};
				this.render();
				if (this.havola) {
					const n = this.havola; this.havola = null;
					this.ochish(n);
				} else if (this.selected) {
					this.load_detail(this.selected);
				}
			},
		});
	}

	render() {
		this.render_kpi();
		this.render_bar();
		this.render_list();
		if (!this.selected) this.render_bosh();
	}

	// ================= KPI =================
	render_kpi() {
		const s = (this.data.stats) || {};
		const r = this.rol();
		let kim = r.hammasi ? __("CEO + Direktor")
			: (r.yonalishlar || []).join(" / ") || __("Yuborganlarim");
		if (r.kuzatuv) kim = __("hammasi — faqat ko'rish");
		const k = (lab, val, sub, cls) => `
			<div class="card kpi ${cls || ""}">
				<div class="lab">${lab}</div>
				<div class="val">${val}</div>
				<div class="sub">${sub || ""}</div>
			</div>`;
		$("#mur-kpi").html(`
			<div class="mur-kpi-row">
				${k(__("Ochiq murojaat"), this.fmt(s.ochiq), kim)}
				${k(__("Ko'rilmagan"), this.fmt(s.korilmagan), __("hali ochilmagan"), s.korilmagan ? "warn" : "")}
				${k(__("Muddati o'tdi"), this.fmt(s.muddati), __("javob kechikdi"), s.muddati ? "bad" : "")}
				${k(__("Biriktirilmagan"), this.fmt(s.biriktirilmagan), __("mas'ul rahbar tayinlanmagan"), s.biriktirilmagan ? "warn" : "")}
				${k(__("Ota-onaga javob"), this.fmt(s.xabar_kutilmoqda), __("menejer qo'ng'iroq qilishi kerak"), s.xabar_kutilmoqda ? "warn" : "")}
				${k(__("Bu oy yopildi"), this.fmt(s.oy_yopildi), __("{0} taklif inobatga olindi", [this.fmt(s.oy_inobat)]), "ok")}
				${k(__("O'rtacha hal qilish"), `${s.ort_kun || 0} ${__("kun")}`, __("ochilgandan yopilgangacha"))}
			</div>
			${this.render_kesim(s.kategoriya_kesim)}`);
	}

	// Takrorlanayotgan masala — bitta murojaatni yopish emas, SABABNI yo'q qilish
	render_kesim(kesim) {
		if (!kesim || !kesim.length) return "";
		const max = Math.max(...kesim.map((x) => Number(x.soni) || 0)) || 1;
		const qatorlar = kesim.map((x) => `
			<div class="mur-kes-row" data-kat="${this.esc(x.kategoriya)}">
				<div class="mur-kes-nom">${this.esc(x.kategoriya)}</div>
				<div class="mur-kes-bar"><i style="width:${Math.round((x.soni / max) * 100)}%"></i></div>
				<div class="mur-kes-son">${this.fmt(x.soni)}${
					Number(x.ochiq) ? ` <span class="mut">(${this.fmt(x.ochiq)} ${__("ochiq")})</span>` : ""}</div>
			</div>`).join("");
		return `
			<div class="card mur-kesim">
				<div class="hd"><h3>${__("Qaysi masala ko'p takrorlanyapti")}</h3>
					<span class="mut">${__("kategoriyani bosing — filtrlanadi")}</span></div>
				<div class="mur-kes-list">${qatorlar}</div>
			</div>`;
	}

	// ================= filtr paneli =================
	render_bar() {
		const r = this.rol();
		const chip = (kod, lab, son) => `
			<button class="mur-chip ${this.fHolat === kod ? "on" : ""}" data-holat="${kod}">
				${lab}${son != null ? ` <b>${this.fmt(son)}</b>` : ""}</button>`;
		const s = this.data.stats || {};
		const kats = (this.data.kategoriyalar || []).map(
			(k) => `<option value="${this.esc(k.name)}" ${this.fKategoriya === k.name ? "selected" : ""}>${
				this.esc(k.nomi)} → ${this.esc(k.yonaltirish)}</option>`).join("");
		const yonalish = r.hammasi ? `
			<select class="mur-sel" id="mur-f-yonalish">
				<option value="">${__("Kimga: hammasi")}</option>
				<option value="CEO" ${this.fYonalish === "CEO" ? "selected" : ""}>CEO</option>
				<option value="Direktor" ${this.fYonalish === "Direktor" ? "selected" : ""}>${__("Direktor")}</option>
			</select>` : "";

		$("#mur-bar").html(`
			<div class="mur-chips">
				${chip("ochiq", __("Ochiq"), s.ochiq)}
				${chip("Yangi", __("Yangi"), s.yangi)}
				${chip("muddati", __("Muddati o'tdi"), s.muddati)}
				${chip("menda", __("Menda"))}
				${chip("Ota-onaga xabar berish", __("Ota-onaga javob"), s.xabar_kutilmoqda)}
				${chip("Yopildi", __("Yopilgan"))}
				${chip("hammasi", __("Hammasi"))}
			</div>
			<div class="mur-filters">
				${yonalish}
				<select class="mur-sel" id="mur-f-turi">
					<option value="">${__("Turi: hammasi")}</option>
					${["Shikoyat", "Taklif", "Muammo", "So'rov"].map(
						(t) => `<option value="${t}" ${this.fTuri === t ? "selected" : ""}>${__(t)}</option>`).join("")}
				</select>
				<select class="mur-sel" id="mur-f-kat">
					<option value="">${__("Kategoriya: hammasi")}</option>${kats}
				</select>
				<select class="mur-sel" id="mur-f-masul">
					<option value="">${__("Kim biriktirilgan: hammasi")}</option>
					${(this.data.masullar || []).map((m) => `
						<option value="${this.esc(m.user)}" ${this.fMasul === m.user ? "selected" : ""}>${
							this.esc(m.nomi)} (${this.fmt(m.soni)})</option>`).join("")}
				</select>
				<input class="mur-search" id="mur-q" type="search"
					placeholder="${__("O'quvchi, ota-ona, matn, MR-…")}" value="${this.esc(this.q)}">
			</div>`);

		$("#mur-bar").off("click", "[data-holat]").on("click", "[data-holat]", (e) => {
			this.fHolat = $(e.currentTarget).data("holat"); this.load();
		});
		$("#mur-f-yonalish").off().on("change", (e) => { this.fYonalish = e.target.value; this.load(); });
		$("#mur-f-turi").off().on("change", (e) => { this.fTuri = e.target.value; this.load(); });
		$("#mur-f-kat").off().on("change", (e) => { this.fKategoriya = e.target.value; this.load(); });
		$("#mur-f-masul").off().on("change", (e) => { this.fMasul = e.target.value; this.load(); });
		let t = null;
		$("#mur-q").off().on("input", (e) => {
			clearTimeout(t); const v = e.target.value;
			t = setTimeout(() => { this.q = v; this.load(); }, 350);
		});
		$("#mur-kpi").off("click", ".mur-kes-row").on("click", ".mur-kes-row", (e) => {
			this.fKategoriya = $(e.currentTarget).data("kat"); this.fHolat = "hammasi"; this.load();
		});
	}

	// ================= ro'yxat =================
	render_list() {
		const rows = this.data.rows || [];
		if (!rows.length) {
			$("#mur-list").html(`<div class="mur-empty">${__("Bu filtrda murojaat yo'q")}</div>`);
			return;
		}
		$("#mur-list").html(`
			<div class="mur-list-hd">${__("{0} murojaat", [this.fmt(rows.length)])}</div>
			${rows.map((x) => this.list_item(x)).join("")}`);
		$("#mur-list").off("click", ".mur-item").on("click", ".mur-item", (e) => {
			this.ochish($(e.currentTarget).data("name"));
		});
	}

	list_item(x) {
		const kun = this.kun_farq(x.sla_sana);
		const muddat = x.holat === "Yopildi"
			? `<span class="mur-pill green">${__("yopildi")} ${this.dmy(x.yopilgan_sana)}</span>`
			: (kun == null ? ""
				: `<span class="mur-pill ${kun < 0 ? "red" : (kun <= 1 ? "orange" : "mut")}">${
					kun < 0 ? __("{0} kun kechikdi", [Math.abs(kun)])
						: (kun === 0 ? __("bugun") : __("{0} kun qoldi", [kun]))}</span>`);
		return `
			<div class="mur-item ${this.selected === x.name ? "on" : ""} ${x.kechikdi ? "late" : ""}"
			     data-name="${this.esc(x.name)}">
				<div class="mur-item-top">
					<span class="mur-tur">${TUR_BELGI[x.turi] || "•"} ${this.esc(x.turi)}</span>
					${x.yangimi ? `<span class="mur-pill red">${__("ko'rilmagan")}</span>` : ""}
					<span class="mur-pill ${HOLAT_RANG[x.holat] || "mut"}">${this.esc(x.holat)}</span>
					<span class="mur-pill ${x.yonaltirildi === "CEO" ? "violet" : "teal"}">${this.esc(x.yonaltirildi)}</span>
					${x.muhimlik === "Yuqori" ? `<span class="mur-pill red">${__("yuqori")}</span>` : ""}
				</div>
				<div class="mur-item-nom">${this.esc(x.student_name || x.payer_name || "—")}
					<span class="mut">${x.sinf ? ` · ${this.esc(x.sinf)}` : ""}</span></div>
				<div class="mur-item-matn">${this.esc(x.matn || "")}</div>
				<div class="mur-item-pod">
					<span class="mut">${this.esc(x.kategoriya || __("kategoriya yo'q"))}</span>
					<span class="mut">· ${__("yubordi")}: ${this.esc(x.menejer_nomi || x.menejer || "—")}</span>
					<span class="mut">· ${this.dt(x.suhbat_vaqti || x.ochilgan)}</span>
					${muddat}
					${x.yechim_turi ? `<span class="mur-pill ${QAROR_RANG[x.yechim_turi] || "mut"}">${this.esc(x.yechim_turi)}</span>` : ""}
				</div>
				<div class="mur-item-masul">
					${x.masul
						? `<span class="mur-pill ${x.holat === "Yopildi" ? "mut" : "blue"}">${
							__("mas'ul")}: ${this.esc(x.masul_nomi || x.masul)}</span>`
						: `<span class="mur-pill orange">${__("biriktirilmagan")} — ${
							this.esc(x.yonaltirildi)} ${__("ko'radi")}</span>`}
					${x.yechim_kim_nomi
						? `<span class="mut">${__("qaror")}: ${this.esc(x.yechim_kim_nomi)}</span>` : ""}
				</div>
			</div>`;
	}

	render_bosh() {
		$("#mur-detail").html(`
			<div class="mur-bosh">
				<div class="mur-bosh-ico">📋</div>
				<h3>${__("Murojaatni tanlang")}</h3>
				<p>${__("Chapdagi ro'yxatdan murojaatni bosing — ota-onaning gapi, ovoz yozuvi, oldingi suhbatlar tarixi va qaror oynasi shu yerda ochiladi.")}</p>
				${this.rol().kuzatuv ? `<p class="mut small">${
					__("Sizda faqat ko'rish ruxsati: barcha murojaatlarni va yechimlarni ko'rasiz, lekin yozmaysiz.")}</p>` : ""}
			</div>`);
	}

	ochish(name) {
		this.selected = name;
		this.render_list();
		this.load_detail(name);
	}

	load_detail(name) {
		$("#mur-detail").html(`<div class="mur-bosh">${__("Yuklanmoqda…")}</div>`);
		frappe.call({
			method: `${MUR_M}.get_case`, args: { name },
			callback: (r) => {
				this.detail = r.message || null;
				this.render_detail();
			},
			error: () => { $("#mur-detail").html(`<div class="mur-bosh">${__("Ochilmadi")}</div>`); },
		});
	}

	// ================= karta (to'liq tasnif) =================
	render_detail() {
		const d = this.detail;
		if (!d) return this.render_bosh();
		const m = d.murojaat;
		$("#mur-detail").html(`
			${this.d_bosh(m)}
			${this.d_matn(m)}
			${this.d_qaror(m)}
			${this.d_izohlar(d.izohlar)}
			${this.d_kim(m, d.qarz)}
			${this.d_suhbatlar(d.qongiroqlar, m)}
			${this.d_tarix(d.ays)}
			${this.d_boshqa(d.qarz)}`);
		this.bind_detail();
	}

	d_bosh(m) {
		const kun = this.kun_farq(m.sla_sana);
		return `
			<div class="card mur-hd">
				<div class="mur-hd-top">
					<div>
						<div class="mur-hd-tur">${TUR_BELGI[m.turi] || "•"} ${this.esc(m.turi)}
							<span class="mur-pill ${m.yonaltirildi === "CEO" ? "violet" : "teal"}">${this.esc(m.yonaltirildi)}</span>
							<span class="mur-pill ${HOLAT_RANG[m.holat] || "mut"}">${this.esc(m.holat)}</span>
							${m.muhimlik === "Yuqori" ? `<span class="mur-pill red">${__("yuqori muhimlik")}</span>` : ""}
						</div>
						<h2>${this.esc(m.student_name || m.payer_name || m.name)}
							<span class="mut">${m.sinf ? ` · ${this.esc(m.sinf)}` : ""}</span></h2>
						<div class="mut">${this.esc(m.name)} · ${this.esc(m.kategoriya || __("kategoriya yo'q"))}
							· ${__("ochilgan")} ${this.dt(m.ochilgan)}</div>
					</div>
					<div class="mur-hd-muddat">
						${m.holat === "Yopildi"
							? `<div class="mur-pill green big">${__("Yopildi")} ${this.dmy(m.yopilgan_sana)}</div>`
							: (kun == null ? ""
								: `<div class="mur-pill ${kun < 0 ? "red" : (kun <= 1 ? "orange" : "mut")} big">${
									kun < 0 ? __("{0} kun kechikdi", [Math.abs(kun)])
										: (kun === 0 ? __("javob bugun") : __("{0} kun qoldi", [kun]))}</div>`)}
						<div class="mut small">${m.korildi_vaqti
							? __("ko'rildi: {0} · {1}", [this.esc(m.korildi_kim || "—"), this.dt(m.korildi_vaqti)])
							: __("hali ko'rilmagan")}</div>
					</div>
				</div>
				<div class="mur-hd-meta">
					<span>${__("Gaplashgan menejer")}: <b>${this.esc(m.menejer_nomi || m.menejer || "—")}</b></span>
					<span>${__("Suhbat")}: <b>${this.dt(m.suhbat_vaqti)}</b></span>
					<span>${__("Manba")}: <b>${this.esc(m.manba)}</b></span>
					<span>${__("Mas'ul rahbar")}: <b>${m.masul
						? this.esc(this.masul_nomi(m.masul))
						: __("biriktirilmagan")}</b></span>
					${m.yechim_kim ? `<span>${__("Qaror")}: <b>${
						this.esc(this.masul_nomi(m.yechim_kim))}</b></span>` : ""}
				</div>
			</div>`;
	}

	d_matn(m) {
		return `
			<div class="card mur-matn">
				<div class="hd"><h3>${__("Ota-ona nima dedi")}</h3></div>
				<div class="mur-quote">${this.esc(m.matn || "—")}</div>
				${m.manba === "AI qo'ng'iroq tahlili"
					? `<div class="mut small">${__("Bu matn qo'ng'iroq transkriptining AI tahlilidan olingan. Ovoz yozuvini pastda eshitib tekshirish mumkin.")}</div>`
					: ""}
			</div>`;
	}

	// Rahbar qarori — modulning yuragi: "muammo qanday hal qilindi"
	d_qaror(m) {
		const rahbar = this.rahbarmi();
		const yopiq = m.holat === "Yopildi";
		const qaror_bor = !!m.yechim_turi;

		let amal = "";
		if (rahbar && !qaror_bor && this.yozamanmi()) {
			amal = `
				<div class="mur-qaror-form">
					<div class="mur-qaror-tugmalar">
						${["Hal qilindi", "Inobatga olindi", "Keyinroq ko'riladi", "Rad etildi", "Ahamiyatsiz"]
							.map((q) => `<button class="mur-qbtn" data-qaror="${this.esc(q)}">${__(q)}</button>`).join("")}
					</div>
					<div class="mut small">${__("«Inobatga olindi» — taklif o'rinli, amalga oshiriladi. «Ahamiyatsiz» — AI xato topgan, ota-onaga qo'ng'iroq qilish shart emas.")}</div>
				</div>`;
		} else if (!qaror_bor) {
			amal = `<div class="mut">${__("Rahbar qarori kutilmoqda.")}</div>`;
		}

		const xabar_tugma = (m.holat === "Ota-onaga xabar berish" && this.yozamanmi())
			? `<button class="mur-btn primary" id="mur-xabar">${__("Ota-onaga javob berdim → yopish")}</button>`
			: "";

		return `
			<div class="card mur-qaror">
				<div class="hd"><h3>${__("Rahbar qarori")}</h3>
					${qaror_bor ? `<span class="mur-pill ${QAROR_RANG[m.yechim_turi] || "mut"}">${this.esc(m.yechim_turi)}</span>` : ""}</div>
				${qaror_bor ? `
					<div class="mur-yechim">${this.esc(m.yechim || "")}</div>
					<div class="mut small">${__("Qaror: {0} · {1}", [this.esc(m.yechim_kim || "—"), this.dt(m.yechim_vaqti)])}</div>
					${m.xabar_berildi ? `
						<div class="mur-xabar ok">${__("Ota-onaga xabar berildi")}:
							${this.esc(m.xabar_kim || "—")} · ${this.dt(m.xabar_vaqti)}
							${m.xabar_matni ? `<div class="mur-quote small">${this.esc(m.xabar_matni)}</div>` : ""}</div>`
						: (yopiq ? "" : `<div class="mur-xabar warn">${__("Ota-onaga hali xabar berilmagan — halqa yopilmagan")}</div>`)}
				` : amal}
				<div class="mur-amallar">
					${xabar_tugma}
					${rahbar && this.yozamanmi() && !yopiq ? `
						<button class="mur-btn" id="mur-uzat">${__("Boshqa rahbarga uzatish")}</button>
						<button class="mur-btn" id="mur-masul">${__("O'zimga biriktirish")}</button>` : ""}
					${qaror_bor && rahbar && this.yozamanmi() && !yopiq
						? `<button class="mur-btn" id="mur-qaror-tahrir">${__("Qarorni tahrirlash")}</button>` : ""}
					<button class="mur-btn ghost" id="mur-och-doc">${__("Hujjatni ochish")}</button>
				</div>
			</div>`;
	}

	d_izohlar(izohlar) {
		const qatorlar = (izohlar || []).map((i) => `
			<div class="mur-izoh ${this.esc((i.turi || "").toLowerCase().replace(/[^a-z]/g, ""))}">
				<div class="mur-izoh-hd">
					<b>${this.esc(i.kim_nomi || i.kim || "—")}</b>
					<span class="mur-pill mut small">${this.esc(i.turi)}</span>
					<span class="mut small">${this.dt(i.vaqt)}</span>
				</div>
				<div class="mur-izoh-matn">${this.esc(i.matn || "")}</div>
			</div>`).join("");
		return `
			<div class="card mur-izohlar">
				<div class="hd"><h3>${__("Izohlar — kim nima qildi")}</h3></div>
				<div class="mur-izoh-list">${qatorlar
					|| `<div class="mut">${__("Hali izoh yo'q")}</div>`}</div>
				${this.yozamanmi() ? `
					<div class="mur-izoh-yoz">
						<textarea id="mur-izoh-matn" rows="2"
							placeholder="${__("Izoh yozing: nima aniqlandi, kim bilan gaplashildi, nima qilinadi…")}"></textarea>
						<button class="mur-btn primary" id="mur-izoh-btn">${__("Izoh qo'shish")}</button>
					</div>`
					: `<div class="mut small">${__("Sizda faqat ko'rish ruxsati bor — izoh yozish uchun rahbar yoki sotuv roli kerak.")}</div>`}
			</div>`;
	}

	d_kim(m, qarz) {
		const ish = qarz && qarz.ish;
		const st = (qarz && qarz.student) || {};
		return `
			<div class="card mur-kim">
				<div class="hd"><h3>${__("Kim murojaat qildi")}</h3></div>
				<div class="mur-grid">
					<div><span class="mut">${__("O'quvchi")}</span>
						<b>${this.esc(m.student_name || "—")}</b>
						${st.enabled === 0 ? `<span class="mur-pill mut">${__("ketgan")}</span>` : ""}</div>
					<div><span class="mut">${__("Sinf")}</span><b>${this.esc(m.sinf || "—")}</b></div>
					<div><span class="mut">${__("Ota-ona / to'lovchi")}</span><b>${this.esc(m.payer_name || "—")}</b></div>
					<div><span class="mut">${__("Telefon")}</span>${this.tel(m.payer_phone) || "—"}</div>
					${ish ? `
						<div><span class="mut">${__("Qarz")}</span>
							<b class="${Number(ish.qarz_summa) > 0 ? "bad" : ""}">${this.fmt(ish.qarz_summa)}</b>
							<span class="mut">${this.esc(ish.aging_bucket || "")}</span></div>
						<div><span class="mut">${__("Qarz holati")}</span><b>${this.esc(ish.ishlov_status || "")}</b></div>`
						: `<div><span class="mut">${__("Qarz")}</span><b class="ok">${__("ochiq qarz ishi yo'q")}</b></div>`}
				</div>
				${m.student ? `
					<div class="mur-amallar">
						<button class="mur-btn ghost" id="mur-qarz-panel">${__("Qarzdorlik panelida ochish")}</button>
					</div>` : ""}
			</div>`;
	}

	// Ovoz yozuvi + transkript + AI tahlil: rahbar matnga ishonmay, ota-onaning
	// o'z ovozini eshitib tekshirishi mumkin
	d_suhbatlar(qlar, m) {
		qlar = (qlar || []).filter((q) => q.audio || q.transkript || q.ai_xulosa);
		if (!qlar.length) return "";
		const kartalar = qlar.slice(0, 8).map((q, i) => {
			const url = `/api/method/target_zenit.telefoniya.api.stream_recording?qongiroq=${encodeURIComponent(q.name)}`;
			const manbami = q.name === m.telefon_qongirogi;
			return `
				<div class="mur-qong ${manbami ? "manba" : ""}">
					<div class="mur-qong-hd">
						${manbami ? `<span class="mur-pill violet">${__("shu murojaat manbasi")}</span>` : ""}
						<b>${this.dt(q.boshlandi)}</b>
						<span class="mut">${this.esc(q.menejer || "—")}</span>
						<span class="mut">${this.esc(q.kim || "")}</span>
						<span class="mut">${this.esc(q.tugash_sababi || "")}</span>
					</div>
					${q.audio ? `<audio class="mur-audio" controls preload="none" src="${url}"></audio>`
						: `<div class="mut small">${__("ovoz yozuvi yo'q")}</div>`}
					${q.ai_xulosa ? `<div class="mur-ai">${this.ai_html(q.ai_xulosa)}</div>` : ""}
					${q.transkript ? `
						<details class="mur-trans"><summary>${__("Transkript")} (${this.fmt(q.transkript_sozlar)} ${__("so'z")})</summary>
							<div class="mur-trans-matn">${this.esc(q.transkript)}</div></details>` : ""}
				</div>`;
		}).join("");
		return `
			<div class="card mur-suhbat">
				<div class="hd"><h3>${__("Telefon suhbatlari")}</h3>
					<span class="mut">${__("ovoz, AI tahlil va matn")}</span></div>
				${kartalar}
			</div>`;
	}

	ai_html(xulosa) {
		return String(xulosa || "").split("\n").filter((x) => x.trim()).map((qator) => {
			const i = qator.indexOf(":");
			if (i < 0) return `<div>${this.esc(qator)}</div>`;
			const bosh = qator.slice(0, i).trim(), qiymat = qator.slice(i + 1).trim();
			const muhim = ["TAKLIF VA SHIKOYAT", "DIQQAT", "MUROJAAT TURI", "MUROJAAT YO'NALISHI"]
				.includes(bosh.toUpperCase());
			return `<div class="mur-ai-row ${muhim ? "muhim" : ""}">
				<span class="mur-ai-k">${this.esc(bosh)}</span>
				<span class="mur-ai-v">${this.esc(qiymat)}</span></div>`;
		}).join("");
	}

	d_tarix(ays) {
		if (!ays || !ays.length) return "";
		const qatorlar = ays.slice(0, 15).map((a) => `
			<tr>
				<td>${this.dt(a.vaqt)}</td>
				<td>${this.esc(a.menejer_nomi || a.masul || "—")}</td>
				<td>${this.esc(a.aloqa_natijasi || "")}${
					a.hisob_natijasi ? ` · <b>${this.esc(a.hisob_natijasi)}</b>` : ""}</td>
				<td>${this.esc(a.komment || "")}</td>
			</tr>`).join("");
		return `
			<div class="card mur-tarix">
				<div class="hd"><h3>${__("Sotuvchilar bilan aloqa tarixi")}</h3>
					<span class="mut">${__("ota-onaga ikkinchi marta bir xil javob bermaslik uchun")}</span></div>
				<div class="mur-table-wrap">
					<table class="mur-table">
						<thead><tr><th>${__("Vaqt")}</th><th>${__("Menejer")}</th>
							<th>${__("Natija")}</th><th>${__("Izoh")}</th></tr></thead>
						<tbody>${qatorlar}</tbody>
					</table>
				</div>
			</div>`;
	}

	d_boshqa(qarz) {
		const b = (qarz && qarz.boshqa) || [];
		if (!b.length) return "";
		return `
			<div class="card mur-boshqa">
				<div class="hd"><h3>${__("Shu o'quvchi bo'yicha boshqa murojaatlar")}</h3>
					<span class="mut">${__("takrorlanayotgan masalami?")}</span></div>
				${b.map((x) => `
					<div class="mur-boshqa-row" data-name="${this.esc(x.name)}">
						<span class="mut">${this.dmy(x.ochilgan)}</span>
						<span class="mur-pill ${HOLAT_RANG[x.holat] || "mut"}">${this.esc(x.holat)}</span>
						<span>${TUR_BELGI[x.turi] || "•"} ${this.esc(x.kategoriya || x.turi)}</span>
						<span class="mur-boshqa-matn">${this.esc(x.matn || "")}</span>
						${x.yechim_turi ? `<span class="mur-pill ${QAROR_RANG[x.yechim_turi] || "mut"}">${this.esc(x.yechim_turi)}</span>` : ""}
					</div>`).join("")}
			</div>`;
	}

	// ================= amallar =================
	bind_detail() {
		const m = this.detail.murojaat;
		const el = $("#mur-detail");

		el.off("click", "[data-qaror]").on("click", "[data-qaror]", (e) => {
			this.qaror_modal($(e.currentTarget).data("qaror"));
		});
		el.off("click", "#mur-qaror-tahrir").on("click", "#mur-qaror-tahrir",
			() => this.qaror_modal(m.yechim_turi, m.yechim));
		el.off("click", "#mur-izoh-btn").on("click", "#mur-izoh-btn", () => this.izoh_yoz());
		el.off("click", "#mur-xabar").on("click", "#mur-xabar", () => this.xabar_modal());
		el.off("click", "#mur-uzat").on("click", "#mur-uzat", () => this.uzat_modal());
		el.off("click", "#mur-masul").on("click", "#mur-masul", () => this.masul_biriktir());
		el.off("click", "#mur-och-doc").on("click", "#mur-och-doc",
			() => frappe.set_route("Form", "Murojaat", m.name));
		el.off("click", "#mur-qarz-panel").on("click", "#mur-qarz-panel", () => {
			frappe.route_options = { student: m.student };
			frappe.set_route("qarzdorlik");
		});
		el.off("click", ".mur-boshqa-row").on("click", ".mur-boshqa-row", (e) => {
			this.ochish($(e.currentTarget).data("name"));
		});
	}

	qaror_modal(qaror, mavjud) {
		const m = this.detail.murojaat;
		const taklif = m.turi === "Taklif";
		const d = new frappe.ui.Dialog({
			title: __("Qaror: {0}", [__(qaror)]),
			fields: [
				{
					fieldtype: "HTML", fieldname: "info",
					options: `<div class="mur-modal-info">${frappe.utils.escape_html(m.matn || "")}</div>`,
				},
				{
					fieldtype: "Select", fieldname: "yechim_turi", label: __("Qaror"), reqd: 1,
					options: ["Hal qilindi", "Inobatga olindi", "Keyinroq ko'riladi",
					          "Rad etildi", "Ahamiyatsiz"].join("\n"),
					default: qaror,
				},
				{
					fieldtype: "Small Text", fieldname: "yechim", reqd: 1,
					label: taklif ? __("Taklif bo'yicha qaror — nima qilinadi")
						: __("Qanday hal qilindi"),
					default: mavjud || "",
					description: __("Aniq yozilsin: nima qilindi, kim bajaradi, qachon. Ota-onaga aytiladigan javob ham shu yerda."),
				},
				{
					fieldtype: "Select", fieldname: "muhimlik", label: __("Muhimlik"),
					options: "Past\nO'rta\nYuqori", default: m.muhimlik,
				},
			],
			primary_action_label: __("Saqlash"),
			primary_action: (v) => {
				frappe.call({
					method: `${MUR_API}.qaror_ber`,
					args: { name: m.name, yechim_turi: v.yechim_turi, yechim: v.yechim,
					        muhimlik: v.muhimlik },
					freeze: true,
					callback: () => {
						d.hide();
						frappe.show_alert({ message: __("Qaror saqlandi"), indicator: "green" }, 5);
						this.load();
						this.load_detail(m.name);
					},
				});
			},
		});
		d.show();
	}

	izoh_yoz() {
		const m = this.detail.murojaat;
		const matn = ($("#mur-izoh-matn").val() || "").trim();
		if (!matn) {
			frappe.show_alert({ message: __("Izoh bo'sh"), indicator: "orange" }, 4);
			return;
		}
		frappe.call({
			method: `${MUR_API}.izoh_yoz`, args: { name: m.name, matn }, freeze: true,
			callback: () => { this.load(); this.load_detail(m.name); },
		});
	}

	xabar_modal() {
		const m = this.detail.murojaat;
		const d = new frappe.ui.Dialog({
			title: __("Ota-onaga javob berildi"),
			fields: [
				{
					fieldtype: "HTML", fieldname: "info",
					options: `<div class="mur-modal-info"><b>${__("Rahbar qarori")}:</b><br>${
						frappe.utils.escape_html(m.yechim || "")}</div>`,
				},
				{
					fieldtype: "Small Text", fieldname: "matn", label: __("Ota-ona reaksiyasi"),
					description: __("Javobni qanday qabul qildi, qo'shimcha gapi bo'ldimi"),
				},
			],
			primary_action_label: __("Yopish"),
			primary_action: (v) => {
				frappe.call({
					method: `${MUR_API}.xabar_berdim`,
					args: { name: m.name, matn: v.matn || null }, freeze: true,
					callback: () => {
						d.hide();
						frappe.show_alert({ message: __("Murojaat yopildi"), indicator: "green" }, 5);
						this.load(); this.load_detail(m.name);
					},
				});
			},
		});
		d.show();
	}

	uzat_modal() {
		const m = this.detail.murojaat;
		const boshqa = m.yonaltirildi === "CEO" ? "Direktor" : "CEO";
		const kats = (this.detail.kategoriyalar || []).filter((k) => k.yonaltirish === boshqa);
		const d = new frappe.ui.Dialog({
			title: __("{0} ga uzatish", [__(boshqa)]),
			fields: [
				{
					fieldtype: "Select", fieldname: "kategoriya", label: __("Kategoriya"),
					options: [""].concat(kats.map((k) => k.name)).join("\n"),
					description: __("Kategoriya yo'nalishni belgilaydi — shu ro'yxatda faqat {0} kategoriyalari", [__(boshqa)]),
				},
				{ fieldtype: "Small Text", fieldname: "izoh", label: __("Nima uchun uzatilyapti") },
			],
			primary_action_label: __("Uzatish"),
			primary_action: (v) => {
				frappe.call({
					method: `${MUR_API}.uzat`,
					args: { name: m.name, yonaltirildi: boshqa,
					        kategoriya: v.kategoriya || null, izoh: v.izoh || null },
					freeze: true,
					callback: () => {
						d.hide();
						frappe.show_alert({ message: __("{0} ga uzatildi", [__(boshqa)]), indicator: "blue" }, 5);
						this.load(); this.load_detail(m.name);
					},
				});
			},
		});
		d.show();
	}

	masul_biriktir() {
		const m = this.detail.murojaat;
		frappe.call({
			method: `${MUR_API}.masul_biriktir`,
			args: { name: m.name, masul: frappe.session.user }, freeze: true,
			callback: () => {
				frappe.show_alert({ message: __("O'zingizga biriktirildi"), indicator: "green" }, 4);
				this.load(); this.load_detail(m.name);
			},
		});
	}
}
