// Copyright (c) 2026, Target Zenit — Investor paneli (professional, bo'limli)
frappe.pages["investor-dashboard"].on_page_load = function (wrapper) {
	new TZInvestorDashboard(wrapper);
};

class TZInvestorDashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Investor paneli"), single_column: true });
		this.data = null;
		this.active = "overview";
		this.state = { from_date: frappe.datetime.month_start(), to_date: frappe.datetime.get_today() };
		// kassa/pul oqimi interaktiv holati
		this.cfMetric = "kirim";     // opening | kirim | chiqim | closing
		this.cfCcy = null;           // valyuta filtri (USD/UZS...)
		this.cfFlow = null;          // batafsil jadval: null | 'kirim' | 'chiqim'
		this.budgetView = null;      // budjet breakdown: null | 'budget' | 'normal'
		// kontragent jadvali holati
		this.ktFilter = { party_type: "Supplier", party: "", currency: "", party_group: "" };
		this.kontragent = null;
		// DDS (pul oqimi hisoboti) holati
		this.ddsFilter = { mode_of_payment: "", party_type: "", party: "", category: "" };
		this.dds = null;
		// Balans (balance sheet) holati
		this.bs = null;
		this.bsOpen = new Set();                 // ochilgan daraxt tugunlari
		this.bsOpt = { acc: 1, fb: 1, per: "" }; // yig'ilgan qiymat / default finance book / davr ustunlari
		// Umumiy tab — karta batafsili: null | 'students' | 'debitorka' | 'kreditorka' | 'cash'
		this.ovDetail = null;
		this.ovStudents = null;     // o'quvchilar to'liq ro'yxati (kesh)
		this.ovStudOpen = new Set(); // ochilgan sinflar (o'quvchilar paneli)
		this.ovStudQ = "";           // o'quvchi qidiruv matni
		// o'quvchilar paneli ko'rinish rejimi (tepadagi chiplar bilan almashadi):
		// 'all' — hammasi | 'contracted' — faqat shartnomalilar | 'classes' — faqat sinflar
		// ro'yxati (yig'ilgan) | 'nogroup' — faqat sinfga biriktirilmaganlar
		this.ovStudMode = "all";
		// O'quvchilar to'lovi tab — karta batafsili: null|'active'|'contracted'|'payments'|'payers'
		this.tuitionDetail = null;
		this.tuitionCcy = null;      // to'lovlar ro'yxatida valyuta filtri (UZS/USD chipi)
		this.ovCash = null;         // kassa batafsil (kesh)
		this.ovCashAccs = [];       // kassa batafsilda tanlangan hisoblar (bo'sh = hammasi)
		this.ovCashOps = [];        // Kassa operatsiya turi filtri (bo'sh = hammasi)
		this.mselOpen = null;       // ochiq turgan ko'p tanlovli menyu kaliti (sahifada bittasi)
		this.cfAcc = null;          // kassa/pul oqimida bosilgan hisob (harakatlari pastda ochiladi)
		this.personal = null;       // Personal bo'limi ma'lumoti (kesh)
		this.personalCats = [];     // kategoriya filtri (bo'sh = hammasi)
		this.personalQ = "";        // ism bo'yicha qidiruv
		this.cfAccTx = null;        // o'sha hisob harakatlari (kesh)
		this.months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
		this.tabs = [
			{ key: "overview", label: "Umumiy" },
			{ key: "cashflow", label: "Kassa va pul oqimi" },
			{ key: "debts", label: "Qarzdorlik" },
			{ key: "dds", label: "Pul oqimi (DDS)" },
			{ key: "tuition", label: "O'quvchilar to'lovi" },
			{ key: "personal", label: "Personal" },
			{ key: "balance", label: "Balans" },
			{ key: "nach", label: "Nachisleniya" },
		];
		this.nach = null;           // nachisleniya ma'lumoti (kesh)
		this.nachSide = "debit";    // "debit" (kirim) | "credit" (chiqim)
		this.nachGroups = [];       // tanlangan guruhlar (bo'sh = hammasi)
		this.nachCats = [];         // tanlangan toifalar (bo'sh = hammasi)
		this.nachAccts = [];        // qarz hisobi filtri
		this.nachSinfs = [];        // sinf (o'quvchi guruhi) filtri
		this.nachPoss = [];         // xodim lavozimi filtri
		this.nachDkinds = [];       // hujjat turi/holati filtri
		this.nachCcy = null;        // tanlangan valyuta filtri
		this.nachQ = "";            // kontragent qidiruvi
		// kassa hisob kartalari uchun rang palitrasi (har shot alohida rang)
		this.acctColors = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c6)", "var(--good)", "var(--warn)", "var(--c5)"];
		this.make_skeleton();
		this.load_data();
	}

	// ================= helpers =================
	ccyLabel(c) { return c === "UZS" ? "so'm" : (c || ""); }
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	acctName(a) { return String(a || "").replace(/\s*-\s*[A-Z]{1,4}\s*$/, ""); } // " - TZ" suffiksni olib tashlash
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : String(s || ""); }

	fmt(n) { // to'liq, bo'shliqli
		n = Math.round(Number(n) || 0);
		const s = Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
		return (n < 0 ? "−" : "") + s;
	}
	kc(n) { // kompakt (mlrd/mln/ming) — vergul kasr
		const v = Number(n) || 0, a = Math.abs(v), sg = v < 0 ? "−" : "";
		if (a >= 1e9) return sg + (a / 1e9).toFixed(2).replace(".", ",") + " mlrd";
		if (a >= 1e6) return sg + (a / 1e6).toFixed(1).replace(".", ",") + " mln";
		if (a >= 1e3) return sg + Math.round(a / 1e3) + " ming";
		return sg + Math.round(a);
	}
	m1(n) { return ((Number(n) || 0) / 1e6).toFixed(1).replace(".", ","); } // mln son (chartlar)
	kcT(n) { // juda ixcham (kalendar katagi uchun): 1,2M · 450k · 3B
		const v = Math.abs(Number(n) || 0);
		if (v >= 1e9) return (v / 1e9).toFixed(1).replace(".", ",") + "B";
		if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1).replace(".", ",") + "M";
		if (v >= 1e3) return Math.round(v / 1e3) + "k";
		return Math.round(v);
	}
	m2(n) { // 2 kasrli to'liq son (USD kabi valyutalar uchun): 1 733,33
		n = Number(n) || 0;
		const neg = n < 0 ? "−" : "";
		const a = Math.abs(n).toFixed(2).split(".");
		return neg + a[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ") + "," + a[1];
	}
	mAmt(n, c) { return c === "UZS" ? this.fmt(n) : this.m2(n); } // so'm butun, boshqa valyuta 2 kasr

	badge(cmp, opt) {
		opt = opt || {};
		if (!cmp) return "";
		const invert = !!opt.invert, label = opt.label || "oldingi davr", p = cmp.delta_pct;
		if (p === null || p === undefined) {
			if (Math.abs(cmp.value) < 0.5 && Math.abs(cmp.prev) < 0.5) return "";
			return `<span class="delta up">yangi <span class="dl">${label}</span></span>`;
		}
		if (Math.abs(p) < 0.05) return `<span class="delta flat">≈0% <span class="dl">${label}</span></span>`;
		const good = invert ? p < 0 : p > 0;
		return `<span class="delta ${good ? "up" : "down"}">${p > 0 ? "▲" : "▼"} ${Math.abs(p).toFixed(1)}% <span class="dl">${label}</span></span>`;
	}

	// ================= skeleton =================
	make_skeleton() {
		this.page.main.addClass("tz-inv");
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.page.main.removeClass("frappe-card");
		this.page.main.html(`
			<div class="topbar">
				<div><h1>Investor paneli</h1><div class="sub tz-ctx"></div></div>
				<div class="spacer"></div>
				<div class="daterange">
					<label>dan</label><input type="date" class="form-control tz-from" value="${this.state.from_date}">
					<label>gacha</label><input type="date" class="form-control tz-to" value="${this.state.to_date}">
					<div class="presets tz-presets">
						<button data-preset="month">Bu oy</button>
						<button data-preset="quarter">Chorak</button>
						<button data-preset="year">Bu yil</button>
					</div>
				</div>
				<button class="refresh tz-refresh"><span class="dot"></span> Yangilash</button>
			</div>
			<div class="tabnav tz-tabs"></div>
			<div class="tz-future" style="display:none"></div>
			<div class="tz-body"><div class="tz-loader">Ma'lumot yuklanyapti…</div></div>
		`);
		this.page.main.find(".tz-from").on("change", (e) => { this.state.from_date = e.target.value; this.load_data(); });
		this.page.main.find(".tz-to").on("change", (e) => { this.state.to_date = e.target.value; this.load_data(); });
		this.page.main.find(".tz-refresh").on("click", () => this.load_data());
		this.page.main.find(".tz-presets").on("click", "button", (e) => this.applyPreset($(e.currentTarget).data("preset")));

		const nav = this.page.main.find(".tz-tabs");
		this.tabs.forEach((t) => nav.append(`<button data-k="${t.key}" class="${t.key === this.active ? "on" : ""}">${t.label}</button>`));
		nav.on("click", "button", (e) => {
			this.active = $(e.currentTarget).data("k");
			nav.find("button").removeClass("on");
			$(e.currentTarget).addClass("on");
			this.renderTab();
		});

		// kassa/pul oqimi — bitta jadval: tanlovlar o'zaro istisno (birini bossa boshqasi o'chadi)
		const body = this.page.main.find(".tz-body");
		// valyuta va kirim/chiqim BIRGA ishlaydi (USD + davriy kirim = USD kirimlar ro'yxati)
		body.on("click", "[data-cf-ccy]", (e) => {
			const c = String($(e.currentTarget).data("cf-ccy"));
			this.cfCcy = (this.cfCcy === c) ? null : c;
			this.budgetView = null;   // budjet bilan esa birga emas
			this.renderTab();
		});
		// Hisoblar kesimi — hisobni bosib uning harakatlarini ochish/yopish
		body.on("click", "[data-cfacc]", (e) => {
			const a = String($(e.currentTarget).attr("data-cfacc"));
			this.cfAcc = (this.cfAcc === a) ? null : a;
			this.renderTab();
		});
		body.on("click", "[data-cf-flow]", (e) => {
			const f = String($(e.currentTarget).data("cf-flow"));
			this.cfFlow = (this.cfFlow === f) ? null : f;
			this.budgetView = null;
			this.renderTab();
		});
		body.on("click", "[data-budget]", (e) => {
			const k = String($(e.currentTarget).data("budget"));
			this.budgetView = (this.budgetView === k) ? null : k;
			this.cfCcy = null; this.cfFlow = null;
			this.renderTab();
		});
		// Umumiy tab — asosiy ko'rsatkich kartalari: bosilganda to'liq ma'lumot pastda ochiladi.
		// "Balance" kartasi esa to'g'ridan-to'g'ri Balans bo'limini ochadi.
		body.on("click", "[data-ov]", (e) => {
			const k = String($(e.currentTarget).data("ov"));
			if (k === "balance") { this.gotoTab("balance"); return; }
			this.ovDetail = (this.ovDetail === k) ? null : k;
			this.renderTab();
			if (this.ovDetail) {
				const el = this.page.main.find(".tz-ov-detail")[0];
				if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "start" });
			}
		});
		// Umumiy tab — kassa batafsil: hisob chipini bosib faqat o'sha hisob harakatini ko'rish
		body.on("click", "[data-ovcash-acc]", (e) => {
			const a = String($(e.currentTarget).attr("data-ovcash-acc"));
			const i = this.ovCashAccs.indexOf(a);
			if (i === -1) this.ovCashAccs.push(a); else this.ovCashAccs.splice(i, 1);
			this.loadOvCash(true);
		});
		// Kassa filtrlari — ko'p tanlovli menyular (hisoblar / operatsiya turi)
		body.on("click", "[data-mselbtn]", (e) => {
			e.stopPropagation();
			const k = String($(e.currentTarget).attr("data-mselbtn"));
			this.mselOpen = (this.mselOpen === k) ? null : k;
			if (k === "acc" || k === "op") this.paintCashFilter();
			else if (k === "perscat") this.paintPersonalFilter();
			else this.paintNachFilter();
		});
		body.on("click", ".tz-msel-menu", (e) => e.stopPropagation());
		body.on("change", "[data-mselopt]", (e) => {
			const k = String($(e.currentTarget).attr("data-mselopt"));
			const v = String($(e.currentTarget).val());
			const list = this.mselList(k);
			const i = list.indexOf(v);
			if (i === -1) list.push(v); else list.splice(i, 1);
			this.mselApply(k);
		});
		body.on("click", "[data-mselclear]", (e) => {
			e.stopPropagation();
			const k = String($(e.currentTarget).attr("data-mselclear"));
			this[this.MSEL[k]] = [];
			this.mselApply(k);
		});
		// menyudan tashqariga bosilsa — yopiladi
		$(document).off("click.tzmsel").on("click.tzmsel", () => {
			if (this.mselOpen) { this.mselOpen = null; this.repaintMsel(); }
		});
		// Umumiy tab — o'quvchilar paneli: sinfni bosib ochish/yopish, qidiruv
		body.on("click", "[data-ovsg]", (e) => {
			const g = String($(e.currentTarget).attr("data-ovsg"));
			if (this.ovStudMode === "classes") {
				// sinflar ro'yxati rejimida sinf bosilsa — to'liq rejimga o'tib, shu sinf ochiladi
				this.ovStudMode = "all";
				this.ovStudOpen = new Set([g]);
			} else if (this.ovStudOpen.has(g)) this.ovStudOpen.delete(g);
			else this.ovStudOpen.add(g);
			this.paintOvStudents();
		});
		body.on("input", ".tz-ovstud-filter", (e) => {
			this.ovStudQ = String(e.target.value || "").trim().toLowerCase();
			this.paintOvStudents();
		});
		// o'quvchilar paneli — tepadagi chiplar (faol/shartnoma/sinf/sinfsiz) rejimni almashtiradi
		body.on("click", "[data-ovsm]", (e) => {
			const m = String($(e.currentTarget).attr("data-ovsm"));
			this.ovStudMode = (this.ovStudMode === m) ? "all" : m;   // qayta bosilsa — hammasi
			if (this.ovStudMode === "classes") this.ovStudOpen.clear();
			this.paintOvStudents();
		});
		// kontragent filtrlari
		body.on("change", ".tz-kt-type", (e) => {
			this.ktFilter.party_type = e.target.value; this.ktFilter.party = ""; this.ktFilter.party_group = "";
			this.loadKontragentParties(); this.loadKontragentGroups(); this.loadKontragent();
		});
		body.on("change", ".tz-kt-party", (e) => { this.ktFilter.party = e.target.value; this.loadKontragent(); });
		body.on("change", ".tz-kt-group", (e) => { this.ktFilter.party_group = e.target.value; this.loadKontragent(); });
		body.on("change", ".tz-kt-ccy", (e) => { this.ktFilter.currency = e.target.value; this.loadKontragent(); });
		// DDS filtrlari
		body.on("change", ".tz-dds-mode", (e) => { this.ddsFilter.mode_of_payment = e.target.value; this.loadDds(); });
		body.on("change", ".tz-dds-type", (e) => {
			this.ddsFilter.party_type = e.target.value; this.ddsFilter.party = "";
			this.loadDdsParties(); this.loadDds();
		});
		body.on("change", ".tz-dds-party", (e) => { this.ddsFilter.party = e.target.value; this.loadDds(); });
		body.on("change", ".tz-dds-category", (e) => { this.ddsFilter.category = e.target.value; this.loadDds(); });
		body.on("click", "[data-dds-toggle]", (e) => {
			const k = String($(e.currentTarget).data("dds-toggle"));
			const rows = this.page.main.find(".dds-sub-" + k);
			if (!rows.length) return;
			const vis = rows.first().is(":visible");
			rows.css("display", vis ? "none" : "table-row");
			this.page.main.find(`.dds-arrow[data-arrow="${k}"]`).text(vis ? "▶" : "▼");
		});
		// Balans (balance sheet) — davr/checkbox'lar va daraxtni ochish/yopish
		body.on("change", ".tz-bs-per", (e) => { this.bsOpt.per = e.target.value || ""; this.bs = null; this.loadBs(); });
		body.on("change", ".tz-bs-acc", (e) => { this.bsOpt.acc = e.target.checked ? 1 : 0; this.bs = null; this.loadBs(); });
		body.on("change", ".tz-bs-fb", (e) => { this.bsOpt.fb = e.target.checked ? 1 : 0; this.bs = null; this.loadBs(); });
		body.on("click", "[data-bs-k]", (e) => {
			const k = String($(e.currentTarget).attr("data-bs-k"));
			if (this.bsOpen.has(k)) this.bsOpen.delete(k); else this.bsOpen.add(k);
			// daraxt Umumiy tabdagi debitorka/kreditorka panelida ham ishlatiladi
			if (this.active === "overview") this.paintOvBs(); else this.paintBs();
		});
		// O'quvchilar to'lovi tab — 5 ta KPI karta: bosilganda batafsil pastda ochiladi
		body.on("click", "[data-td]", (e) => {
			const k = String($(e.currentTarget).data("td"));
			this.tuitionCcy = null;
			this.tuitionDetail = (this.tuitionDetail === k) ? null : k;
			this.renderTab();
			if (this.tuitionDetail) {
				const el = this.page.main.find(".tz-tuition-detail")[0];
				if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "start" });
			}
		});
		// O'quvchilar to'lovi — valyuta chipi: shu valyutadagi to'lovlar ro'yxati ochiladi
		body.on("click", "[data-tccy]", (e) => {
			const c = String($(e.currentTarget).attr("data-tccy"));
			if (this.tuitionDetail === "payments" && this.tuitionCcy === c) {
				this.tuitionCcy = null; this.tuitionDetail = null;
			} else {
				this.tuitionDetail = "payments"; this.tuitionCcy = c;
			}
			this.renderTab();
			if (this.tuitionDetail) {
				const el = this.page.main.find(".tz-tuition-detail")[0];
				if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "start" });
			}
		});
		// Nachisleniya — Kirim/Chiqim tugmasi, toifa/valyuta chiplari, qidiruv
		body.on("click", "[data-nach-side]", (e) => {
			const s2 = String($(e.currentTarget).attr("data-nach-side"));
			if (this.nachSide === s2) return;
			this.nachSide = s2; this.nachClearFilters(); this.nachCcy = null; this.nachQ = "";
			this.paintNach();
		});
		body.on("click", "[data-nach-cat]", (e) => {
			const c = String($(e.currentTarget).attr("data-nach-cat"));
			const i = this.nachCats.indexOf(c);
			if (i === -1) this.nachCats.push(c); else this.nachCats.splice(i, 1);
			this.paintNach();
		});
		body.on("click", "[data-nach-ccy]", (e) => {
			const c = String($(e.currentTarget).attr("data-nach-ccy"));
			this.nachCcy = (this.nachCcy === c) ? null : c;
			this.paintNach();
		});
		body.on("input", ".tz-pers-search", (e) => {
			this.personalQ = String(e.target.value || "").trim().toLowerCase();
			this.paintPersonal(true);
		});
		body.on("input", ".tz-nach-filter", (e) => {
			this.nachQ = String(e.target.value || "").trim().toLowerCase();
			this.paintNach(true);
		});
		// o'quvchi bo'yicha qidiruv — HAR IKKALA ko'rinishda ham ishlaydi (tr[data-sname])
		body.on("input", ".tz-stud-filter", (e) => {
			const q = String(e.target.value || "").trim().toLowerCase();
			let shown = 0;
			this.page.main.find("tr[data-sname]").each((i, el) => {
				const match = !q || (el.getAttribute("data-sname") || "").indexOf(q) !== -1;
				el.style.display = match ? "" : "none";
				if (match) shown++;
			});
			this.page.main.find(".tz-stud-count").text(shown);
		});
	}

	gotoTab(key) {
		this.active = key;
		const nav = this.page.main.find(".tz-tabs");
		nav.find("button").removeClass("on");
		nav.find(`button[data-k="${key}"]`).addClass("on");
		this.renderTab();
	}

	applyPreset(p) {
		const t = frappe.datetime.get_today();
		const d = frappe.datetime.str_to_obj(t);
		let from;
		if (p === "month") from = frappe.datetime.month_start();
		else if (p === "year") from = d.getFullYear() + "-01-01";
		else if (p === "quarter") {
			const qm = Math.floor(d.getMonth() / 3) * 3 + 1;
			from = d.getFullYear() + "-" + String(qm).padStart(2, "0") + "-01";
		}
		this.state.from_date = from; this.state.to_date = t;
		this.page.main.find(".tz-from").val(from);
		this.page.main.find(".tz-to").val(t);
		this.load_data();
	}

	load_data() {
		this.kontragent = null;
		this.dds = null;
		this.bs = null;
		this.ovStudents = null;
		this.ovCash = null;
		this.cfAcc = null; this.cfAccTx = null;
		this.personal = null; this.personalCats = []; this.personalQ = "";
		this._ovBsAuto = null;
		this.nach = null;
		this.nachClearFilters(); this.nachCcy = null; this.nachQ = "";
		this.page.main.find(".tz-body").html(`<div class="tz-loader">Ma'lumot yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_dashboard_data",
			args: { from_date: this.state.from_date, to_date: this.state.to_date },
		}).then((r) => { this.data = r.message || {}; this.afterLoad(); })
			.catch(() => this.page.main.find(".tz-body").html(`<div class="empty-hint">Ma'lumotni yuklab bo'lmadi.</div>`));
	}

	afterLoad() {
		const m = this.data.meta || {};
		this.page.main.find(".tz-ctx").text(
			`${m.company || ""} · ${m.period ? m.period.label : ""} · taqqoslash: ${m.prev_label || ""}`);
		const fb = this.page.main.find(".tz-future");
		if (m.is_future) fb.show().html(`⚠️ Tanlangan oraliq kelajakda — ba'zi ko'rsatkichlar hali to'lmagan.`);
		else fb.hide();
		this.renderTab();
	}

	renderTab() {
		if (!this.data || !this.data.meta) return;
		const body = this.page.main.find(".tz-body");
		const fn = { overview: "renderOverview", cashflow: "renderCashflow", debts: "renderDebts", dds: "renderDds", tuition: "renderTuition", personal: "renderPersonal", balance: "renderBalance", nach: "renderNach" }[this.active];
		body.html(this[fn]());
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	// ================= UI atoms =================
	card(inner, cls) { return `<div class="card ${cls || ""}">${inner}</div>`; }
	sec(title, sub) { return `<div class="sec-h"><h2>${this.esc(title)}</h2>${sub ? `<span>${this.esc(sub)}</span>` : ""}</div>`; }

	kpi(o) {
		const badges = [this.badge(o.cmp, { invert: o.invert }), o.cmpYoy ? this.badge(o.cmpYoy, { invert: o.invert, label: (this.data.meta.yoy_label || "") + "ga" }) : ""].filter(Boolean).join("");
		const clickAttr = o.click ? o.click : "";
		return `<div class="card kpi ${o.cls || ""}" ${clickAttr}>
			<div class="lab"><span class="pin" style="background:${o.pin || "var(--brand)"}"></span> ${this.esc(o.label)}</div>
			<div class="val num" ${o.valColor ? `style="color:${o.valColor}"` : ""} ${o.tt ? `data-tt="${this.esc(o.tt)}"` : ""}>${o.value}${o.unit ? ` <span class="cur">${o.unit}</span>` : ""}</div>
			${o.sub ? `<div class="sub num">${o.sub}</div>` : ""}
			${o.noBadge ? "" : `<div class="badges">${badges || "<span class='muted-s'>taqqoslash yo'q</span>"}</div>`}
		</div>`;
	}

	moneyKpi(o) { // pul KPI — kompakt + to'liq tooltip. o.ccy — valyutani majburlash
		const cur = o.ccy || this.data.meta.currency;
		o.value = this.kc(o.raw);
		o.unit = o.unit || this.ccyLabel(cur);
		o.tt = this.fmt(o.raw) + " " + this.ccyLabel(cur);
		return this.kpi(o);
	}

	hbars(items, color) {
		if (!items || !items.length) return `<div class="empty-hint">Ma'lumot yo'q.</div>`;
		const max = Math.max(1, ...items.map((i) => Math.abs(i.amount)));
		return `<div class="hbars">` + items.map((it) => `
			<div class="hb">
				<div class="hb-t"><span>${this.esc(it.label)}</span><b class="num" data-tt="${this.fmt(it.amount)}">${this.kc(it.amount)}${it.currency && it.currency !== this.data.meta.currency ? " " + this.esc(it.currency) : ""}</b></div>
				<div class="hb-track"><span style="width:${Math.max(2, Math.abs(it.amount) / max * 100)}%;background:${color}"></span></div>
			</div>`).join("") + `</div>`;
	}

	donutSvg(segs, colors, big, cap) {
		let off = 0, c = "";
		segs.forEach((s, i) => {
			const pct = Math.max(0, s.pct || 0), seg = Math.max(0, pct - 1.2);
			c += `<circle cx="70" cy="70" r="54" fill="none" stroke="${colors[i % colors.length]}" stroke-width="18" pathLength="100" stroke-dasharray="${seg.toFixed(1)} ${(100 - seg).toFixed(1)}" stroke-dashoffset="${(-off).toFixed(1)}"/>`;
			off += pct;
		});
		return `<div class="donut"><svg width="140" height="140" viewBox="0 0 140 140" style="transform:rotate(-90deg)" aria-hidden="true">
			<circle cx="70" cy="70" r="54" fill="none" stroke="var(--line)" stroke-width="18"/>${c}</svg>
			<div class="center"><div class="big num">${big}</div><div class="cap">${cap}</div></div></div>`;
	}

	lineChart(labels, series) {
		if (!labels || !labels.length) return `<div class="empty-hint">Ma'lumot yo'q.</div>`;
		const W = 760, H = 240, pL = 54, pR = 16, pT = 18, pB = 30, n = labels.length;
		let max = 1; series.forEach((s) => s.data.forEach((v) => { if (v > max) max = v; }));
		const xat = (i) => pL + (n === 1 ? 0 : i * (W - pL - pR) / (n - 1));
		const yat = (v) => (H - pB) - (Math.max(0, v) / max) * (H - pT - pB);
		const line = (a) => a.map((v, i) => `${xat(i).toFixed(1)},${yat(v).toFixed(1)}`).join(" ");
		const grid = [0, .5, 1].map((f) => { const y = (H - pB) - f * (H - pT - pB); return `<line x1="${pL}" y1="${y}" x2="${W - pR}" y2="${y}" stroke="var(--line)"/><text x="${pL - 8}" y="${y + 4}" fill="var(--muted)" font-size="11" text-anchor="end">${this.m1(max * f)}</text>`; }).join("");
		const labs = labels.map((m, i) => (n <= 12) ? `<text x="${xat(i)}" y="${H - 8}" fill="var(--muted)" font-size="10.5" text-anchor="middle">${this.esc(m)}</text>` : "").join("");
		const paths = series.map((s) => {
			const area = s.fill ? `<polygon points="${line(s.data)} ${xat(n - 1).toFixed(1)},${H - pB} ${xat(0).toFixed(1)},${H - pB}" fill="${s.color}" opacity="0.09"/>` : "";
			return `${area}<polyline points="${line(s.data)}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${xat(n - 1)}" cy="${yat(s.data[n - 1])}" r="4" fill="${s.color}" stroke="var(--card)" stroke-width="2"/>`;
		}).join("");
		return `<svg width="100%" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"><g>${grid}</g>${paths}<g>${labs}</g></svg>`;
	}

	barChart(labels, values, opt) {
		opt = opt || {};
		if (!labels || !labels.length) return `<div class="empty-hint">Ma'lumot yo'q.</div>`;
		const max = Math.max(1, ...values.map((v) => Math.abs(v)));
		return `<div class="vbars">` + labels.map((l, i) => {
			const v = values[i], h = Math.max(3, Math.abs(v) / max * 100), neg = v < 0;
			return `<div class="col"><span class="vl num" data-tt="${this.fmt(v)}">${v ? this.m1(v) : ""}</span>
				<div class="bwrap"><div class="bar ${neg ? "neg" : "pos"}" style="height:${h}%;background:${neg ? "var(--bad)" : (opt.color || "var(--good)")}"></div></div>
				<span class="lb">${this.esc(l)}</span></div>`;
		}).join("") + `</div>`;
	}

	// ================= TAB: Overview =================
	renderOverview() {
		const o = this.data.overview;
		const c = o.cards || {};
		let h = this.sec("Asosiy ko'rsatkichlar", `${this.dmy(c.as_of || this.state.to_date)} holatiga · kartani bosing — to'liq ma'lumot pastda ochiladi`);
		h += `<div class="grid cols-5 mb">
			${this.ovStudentsCard(o, c.students_by_group || [])}
			${this.ovDebtCard("Debitorka (bizga qarz)", c.debitorka, "var(--good)", "var(--good-ink)", "debitorka")}
			${this.ovDebtCard("Kreditorka (biz qarz)", c.kreditorka, "var(--bad)", "var(--bad-ink)", "kreditorka")}
			${this.ovCashCard(c.cash || [])}
			${this.ovBalanceCard(c.balance)}
		</div>`;
		h += `<div class="tz-ov-detail">${this.ovDetailPanel()}</div>`;
		return h + this.note();
	}

	// ---- Umumiy tab: taqsimotli kartalar (mockup dizayni) ----
	ovAmount(v, cur, color) {
		return `<span class="num" style="color:${color}" data-tt="${this.fmt(v)} ${this.esc(cur)}">${this.kc(v)} <small>${this.esc(cur)}</small></span>`;
	}

	ovRow(label, right) {
		return `<div class="ov-row"><span class="ov-lab ell" data-tt="${label}">${label}</span>${right}</div>`;
	}

	ovTotals(list, ink) {
		return (list || []).length
			? list.map((cc) => `<div class="ov-total num" style="color:${ink}" data-tt="${this.fmt(cc.total)} ${this.esc(cc.currency)}">${this.kc(cc.total)} <span class="cur">${this.ccyLabel(cc.currency)}</span></div>`).join("")
			: `<div class="ov-total num muted-s">0</div>`;
	}

	ovOpenHint(key, label) {
		const on = this.ovDetail === key;
		return `<div class="ov-open">${on ? "▴ Yopish" : `▾ ${label || "Batafsil"}`}</div>`;
	}

	ovDebtCard(title, list, pin, ink, key) {
		list = list || [];
		const rows = list.map((cc) => (cc.items || []).map((it) =>
			this.ovRow(this.esc(it.label), this.ovAmount(it.amount, cc.currency, ink))).join("")).join("");
		return `<div class="card kpi ov-card clickable${this.ovDetail === key ? " active" : ""}" data-ov="${key}" style="border-top:3px solid ${pin}">
			<div class="lab"><span class="pin" style="background:${pin}"></span> ${title}</div>
			<div class="ov-totals">${this.ovTotals(list, ink)}</div>
			<div class="ov-cap">Toifalar kesimida</div>
			<div class="ov-list">${rows || `<div class="empty-hint">Qarzdorlik yo'q.</div>`}</div>
			${this.ovOpenHint(key, "Kontragentlar kesimida to'liq")}
		</div>`;
	}

	ovStudentsCard(o, groups) {
		const act = o.active_students || 0, con = o.contracted_students || 0;
		const pct = act ? Math.round(con / act * 100) : 0;
		const rows = groups.map((g) => this.ovRow(this.esc(g.label), `<span class="num">${g.students}</span>`)).join("");
		return `<div class="card kpi ov-card clickable${this.ovDetail === "students" ? " active" : ""}" data-ov="students" style="border-top:3px solid var(--c2)">
			<div class="lab"><span class="pin" style="background:var(--c2)"></span> O'quvchilar</div>
			<div class="ov-totals">
				<div class="ov-total num">${this.fmt(act)} <span class="cur">faol</span></div>
				<div class="ov-sub num">Shartnoma qilingan: <b style="color:var(--good-ink)">${this.fmt(con)}</b> · ${pct}%</div>
			</div>
			<div class="ov-cap">Sinflar kesimida</div>
			<div class="ov-list ov-2col">${rows || `<div class="empty-hint">Sinf (Student Group) ma'lumoti yo'q.</div>`}</div>
			${this.ovOpenHint("students", "To'liq ro'yxat (kim qaysi sinfda)")}
		</div>`;
	}

	ovCashCard(list) {
		list = list || [];
		const rows = list.map((cc) => (cc.items || []).map((it) =>
			this.ovRow(this.esc(this.acctName(it.label)),
				this.ovAmount(it.amount, cc.currency, it.amount < 0 ? "var(--bad-ink)" : "var(--ink)"))).join("")).join("");
		return `<div class="card kpi ov-card clickable${this.ovDetail === "cash" ? " active" : ""}" data-ov="cash" style="border-top:3px solid var(--brand)">
			<div class="lab"><span class="pin" style="background:var(--brand)"></span> Xisobdagi pullar</div>
			<div class="ov-totals">${this.ovTotals(list, "var(--brand-ink)")}</div>
			<div class="ov-cap">Hisoblar kesimida</div>
			<div class="ov-list">${rows || `<div class="empty-hint">Qoldiq yo'q.</div>`}</div>
			${this.ovOpenHint("cash", "Oxirgi harakatlar (tranzaksiyalar)")}
		</div>`;
	}

	ovBalanceCard(b) {
		if (!b) return `<div class="card kpi ov-card clickable" data-ov="balance" style="border-top:3px solid var(--c5)"><div class="lab"><span class="pin" style="background:var(--c5)"></span> Balance</div><div class="empty-hint">Balans ma'lumoti yo'q.</div>${this.ovOpenHint("balance", "Balans bo'limini ochish")}</div>`;
		const cur = b.currency, wc = b.working_capital;
		const de = b.debt_to_equity;
		return `<div class="card kpi ov-card clickable" data-ov="balance" style="border-top:3px solid var(--c5)">
			<div class="lab"><span class="pin" style="background:var(--c5)"></span> Balance</div>
			<div class="ov-totals">
				<div class="ov-sub">Working Capital (aylanma kapital)</div>
				<div class="ov-total num" style="color:${(wc || 0) < 0 ? "var(--bad-ink)" : "var(--good-ink)"}" data-tt="${wc == null ? "" : this.fmt(wc) + " " + this.esc(cur)}">${wc == null ? "—" : this.kc(wc)} <span class="cur">${this.ccyLabel(cur)}</span></div>
				<div class="ov-sub num">Debt-to-Equity: <b>${de == null ? "—" : String(de).replace(".", ",")}</b></div>
			</div>
			<div class="ov-cap">Jami (uzoq muddatli ham kiradi)</div>
			<div class="ov-list">
				${this.ovRow("Total Assets", this.ovAmount(b.assets, cur, "var(--good-ink)"))}
				${this.ovRow("Total Liabilities", this.ovAmount(-b.liabilities, cur, "var(--bad-ink)"))}
				${this.ovRow("Total Equity", this.ovAmount(b.equity, cur, b.equity < 0 ? "var(--bad-ink)" : "var(--good-ink)"))}
			</div>
			${this.ovOpenHint("balance", "Balans bo'limini ochish (to'liq)")}
		</div>`;
	}

	// ---- Umumiy tab: karta bosilganda ochiladigan batafsil panel ----
	ovDetailPanel() {
		const k = this.ovDetail;
		if (!k) return "";
		const c = (this.data.overview || {}).cards || {};
		const asOf = this.dmy(c.as_of || this.state.to_date);
		if (k === "students") {
			setTimeout(() => { this.ovStudMode = "all"; this.loadOvStudents(); }, 0);
			return this.card(`
				<div class="hd tz-tuition-hd"><div><h3>O'quvchilar — sinflar kesimida</h3><div class="meta">sinfni bosing — ichidagi o'quvchilar ochiladi · shartnoma holati bilan</div></div>
					<div class="tz-tuition-tools"><input type="text" class="tz-ovstud-filter" placeholder="O'quvchi yoki sinf qidirish…" autocomplete="off"></div></div>
				<div class="tz-ovstud-body"><div class="tz-loader">O'quvchilar yuklanyapti…</div></div>`, "mb ov-detail-card");
		}
		if (k === "debitorka" || k === "kreditorka") {
			setTimeout(() => this.loadOvBs(), 0);
			const isDeb = k === "debitorka";
			return this.card(`
				<div class="hd"><div><h3>${isDeb ? "Debitorka — bizga qarzdorlar (to'liq)" : "Kreditorka — biz qarzdormiz (to'liq)"}</h3>
					<div class="meta">${asOf} holatiga · ${this.ccyLabel(this.data.meta.currency)} (kompaniya valyutasi) · qatorni bosib ichini oching: hisob → tur → guruh → kontragent</div></div>
					<button class="tz-mini-btn" data-ov="balance">To'liq balans →</button></div>
				<div class="tz-ovbs-body"><div class="tz-loader">Yuklanyapti…</div></div>`, "mb ov-detail-card");
		}
		if (k === "cash") {
			setTimeout(() => this.loadOvCash(), 0);
			return this.card(`
				<div class="hd"><div><h3>Xisobdagi pullar — oxirgi harakatlar</h3>
					<div class="meta">${asOf} holatiga · eng yangi harakat tepada · hisoblarni va operatsiya turini filtrdan tanlang</div></div>
					<div class="kt-filter tz-cash-filter">${this.cashFilterHtml()}</div></div>
				<div class="tz-ovcash-body"><div class="tz-loader">Yuklanyapti…</div></div>`, "mb ov-detail-card");
		}
		return "";
	}

	// -- o'quvchilar batafsil: sinf kesimida yig'ma-ochilma ro'yxat --
	loadOvStudents() {
		const body = this.page.main.find(".tz-ovstud-body");
		if (!body.length) return;
		if (this.ovStudents) { this.paintOvStudents(); return; }
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_students_detail",
		}).then((r) => { this.ovStudents = r.message || {}; this.paintOvStudents(); })
			.catch(() => body.html(`<div class="empty-hint">O'quvchilar ro'yxatini yuklab bo'lmadi.</div>`));
	}

	paintOvStudents() {
		const body = this.page.main.find(".tz-ovstud-body");
		if (!body.length) return;
		body.html(this.renderOvStudents(this.ovStudents || {}));
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	renderOvStudents(d) {
		const q = this.ovStudQ || "";
		const mode = this.ovStudMode || "all";
		const onlyC = mode === "contracted";         // faqat shartnoma qilinganlar
		const onlyNG = mode === "nogroup";           // faqat sinfga biriktirilmaganlar
		const classesOnly = mode === "classes";      // faqat sinflar ro'yxati (yig'ilgan)
		const groups = d.groups || [];
		// tepadagi chiplar — BOSILADIGAN rejim filtrlari (qayta bosilsa hammasiga qaytadi)
		const chip = (m, v, cap, color) => `<span class="ccy-chip tz-ovsm${mode === m ? " active" : ""}" data-ovsm="${m}"><b class="num"${color ? ` style="color:${color}"` : ""}>${this.fmt(v)}</b> <span class="muted-s">${cap}</span></span>`;
		const chips = `<div class="ov-chips">
			${chip("all", d.total || 0, "faol o'quvchi")}
			${chip("contracted", d.contracted || 0, "shartnoma qilingan", "var(--good-ink)")}
			${chip("classes", d.group_count || 0, "sinf")}
			${d.no_group ? chip("nogroup", d.no_group, "sinfga biriktirilmagan", "var(--warn-ink)") : ""}
		</div>`;
		// to'lov summasi katakchasi: valyuta kesimida, to'liq raqam tooltip'da
		const paidCell = (paid, bold) => {
			if (!paid || !paid.length) return `<span class="muted-s">to'lov yo'q</span>`;
			return paid.map((p) =>
				`<div class="num" style="color:var(--good-ink);${bold ? "font-weight:750" : "font-weight:600"};white-space:nowrap" data-tt="${this.fmt(p.total)} ${this.esc(p.currency)}">${this.fmt(p.total)} <small>${this.esc(this.ccyLabel(p.currency))}</small></div>`).join("");
		};
		// sinf jamlari — ko'rsatilayotgan (filtrlangan) o'quvchilardan yig'iladi
		const aggBy = (list, key) => {
			const a = {};
			list.forEach((s) => (s[key] || []).forEach((p) => { a[p.currency] = (a[p.currency] || 0) + p.total; }));
			return Object.keys(a).map((c) => ({ currency: c, total: a[c] })).sort((x, y) => y.total - x.total);
		};
		const aggPaid = (list) => aggBy(list, "paid");
		// qarzdorlik katakchasi: qarz — qizil, avans (peredoplata) — yashil
		const debtCell = (debt, adv, bold) => {
			const w = bold ? "font-weight:750" : "font-weight:600";
			let h = (debt || []).map((p) =>
				`<div class="num" style="color:var(--bad-ink);${w};white-space:nowrap" data-tt="Qarz: ${this.fmt(p.total)} ${this.esc(p.currency)}">${this.mAmt(p.total, p.currency)} <small>${this.esc(this.ccyLabel(p.currency))}</small></div>`).join("");
			h += (adv || []).map((p) =>
				`<div class="num" style="color:var(--good-ink);font-weight:600;white-space:nowrap" data-tt="Avans (peredoplata): ${this.fmt(p.total)} ${this.esc(p.currency)}"><small>avans</small> ${this.mAmt(p.total, p.currency)} <small>${this.esc(this.ccyLabel(p.currency))}</small></div>`).join("");
			return h || `<span class="muted-s">—</span>`;
		};
		// oxirgi to'lov summasi katakchasi
		const lastAmtCell = (la) => la && la.amount
			? `<div class="num" style="font-weight:600;white-space:nowrap" data-tt="${this.fmt(la.amount)} ${this.esc(la.currency)}">${this.mAmt(la.amount, la.currency)} <small>${this.esc(this.ccyLabel(la.currency))}</small></div>`
			: `<span class="muted-s">—</span>`;
		// tarif: sinf qatorida — kategoriya kesimida nechtadan, o'quvchida — o'zi
		const tariffAgg = (list) => {
			const a = {};
			list.forEach((s) => { if (s.tariff) a[s.tariff] = (a[s.tariff] || 0) + 1; });
			const parts = Object.keys(a).sort().map((k) => `${a[k]} ${this.esc(k.toLowerCase())}`);
			return parts.length ? `<span class="num">${parts.join(" · ")}</span>` : `<span class="muted-s">—</span>`;
		};
		// summa katakchasi (so'm) — sinf qatorida jami, o'quvchida o'ziniki
		const tariffAmtCell = (v, bold) => (Number(v) > 0
			? `<div class="num" style="${bold ? "font-weight:750" : "font-weight:600"};white-space:nowrap" data-tt="${this.fmt(v)} so'm">${this.fmt(v)} <small>so'm</small></div>`
			: `<span class="muted-s">—</span>`);
		const finalSum = (list) => list.reduce((n, s) => n + (Number(s.final_amount) || 0), 0);
		const monthlySum = (list) => list.reduce((n, s) => n + (Number(s.monthly) || 0), 0);
		// shartnoma turi: sinf qatorida — nechta oylik/yillik, o'quvchida — o'zi
		const ctypeAgg = (list) => {
			const a = {};
			list.forEach((s) => { if (s.ctype) a[s.ctype] = (a[s.ctype] || 0) + 1; });
			const parts = Object.keys(a).sort().map((k) => `${a[k]} ${this.esc(k.toLowerCase())}`);
			return parts.length ? `<span class="num">${parts.join(" · ")}</span>` : `<span class="muted-s">—</span>`;
		};
		let rows = "", shown = 0;
		groups.forEach((g) => {
			const glab = String(g.label || "").toLowerCase();
			if (onlyNG && !g.no_group) return;                    // "sinfsiz" rejimi — faqat o'sha guruh
			let all = g.students || [];
			if (onlyC) all = all.filter((s) => s.contracted);
			if (onlyC && !all.length) return;                     // shartnomasiz sinf — ko'rsatilmaydi
			// qidiruvda: o'quvchi ismi YOKI sinf nomi mos kelsa ko'rsatamiz
			const studs = q
				? all.filter((s) => (String(s.name || "").toLowerCase() + " " + glab).indexOf(q) !== -1)
				: all;
			if (q && !studs.length) return;                       // qidiruvga mos emas — sinf yashirinadi
			// sinflar rejimida hammasi yig'iq; sinfsiz rejimida ochiq; qidiruvda ochiq
			const open = classesOnly ? false : (onlyNG || q) ? true : this.ovStudOpen.has(g.label);
			shown += studs.length;
			const gpaid = aggPaid(studs);
			const gdebt = aggBy(studs, "debt"), gadv = aggBy(studs, "advance");
			const payers = studs.filter((s) => s.pay_count).length;
			const contr = studs.filter((s) => s.contracted).length;
			// sinfdagi ENG SO'NGGI to'lov — sanasi eng katta o'quvchidan olinadi
			let glast = null;
			studs.forEach((s) => { if (s.last_pay && (!glast || s.last_pay > glast.last_pay)) glast = s; });
			rows += `<tr class="ovsg-h" data-ovsg="${this.esc(g.label)}">
				<td><span class="dds-arrow">${open ? "▼" : "▶"}</span> <b>${this.esc(g.label)}</b>${g.no_group ? ` <span class="muted-s">(Student Group biriktirilmagan)</span>` : ""}</td>
				<td class="r num"><b>${studs.length}</b> <span class="muted-s">o'quvchi</span></td>
				<td>${ctypeAgg(studs)}</td>
				<td>${tariffAgg(studs)}</td>
				<td class="r">${tariffAmtCell(finalSum(studs), true)}</td>
				<td class="r">${tariffAmtCell(monthlySum(studs), true)}</td>
				<td class="r">${paidCell(gpaid, true)}${payers ? `<div class="muted-s">${payers}/${studs.length} o'quvchi to'lagan</div>` : ""}</td>
				<td class="r">${glast ? lastAmtCell(glast.last_amt) : `<span class="muted-s">—</span>`}</td>
				<td class="r num" style="white-space:nowrap">${glast ? this.dmy(glast.last_pay) : `<span class="muted-s">—</span>`}</td>
				<td class="r">${debtCell(gdebt, gadv, true)}</td>
				<td class="num">${contr ? `<span class="tz-yes">${contr} faol</span>` : ""}${contr && studs.length - contr ? ` <span class="muted-s">·</span> ` : ""}${studs.length - contr ? `<span class="muted-s">${studs.length - contr} nofaol</span>` : ""}</td>
			</tr>`;
			if (open) rows += studs.map((s, i) => `
				<tr class="ovsg-s">
					<td class="ovsg-name ell" data-tt="${this.esc(s.name)}">${i + 1}. ${this.esc(s.name)}</td>
					<td></td>
					<td>${s.ctype ? `<span class="num">${this.esc(s.ctype)}</span>` : `<span class="muted-s">—</span>`}</td>
					<td>${s.tariff ? `<span class="num">${this.esc(s.tariff)}</span>` : `<span class="muted-s">—</span>`}</td>
					<td class="r">${tariffAmtCell(s.final_amount)}</td>
					<td class="r">${tariffAmtCell(s.monthly)}</td>
					<td class="r">${paidCell(s.paid)}${s.pay_count ? `<div class="muted-s">${s.pay_count} marta</div>` : ""}</td>
					<td class="r">${lastAmtCell(s.last_amt)}</td>
					<td class="r num" style="white-space:nowrap">${s.last_pay ? this.dmy(s.last_pay) : `<span class="muted-s">—</span>`}</td>
					<td class="r">${debtCell(s.debt, s.advance)}</td>
					<td>${s.contracted ? `<span class="tz-yes">Faol</span>` : `<span style="color:var(--warn-ink);font-weight:650">Nofaol</span>`}</td>
				</tr>`).join("");
		});
		if (!rows) rows = `<tr><td colspan="11" class="empty-hint">${q ? "Qidiruvga mos o'quvchi topilmadi."
			: onlyC ? "Shartnoma qilingan o'quvchi topilmadi."
			: onlyNG ? "Sinfga biriktirilmagan o'quvchi yo'q."
			: "O'quvchi topilmadi."}</td></tr>`;
		const cnt = q ? `Qidiruv: <b>${shown}</b> ta o'quvchi topildi.`
			: onlyC ? `${this.fmt(d.contracted || 0)} ta shartnoma qilingan o'quvchi ko'rsatilmoqda.`
			: onlyNG ? `${this.fmt(d.no_group || 0)} ta sinfga biriktirilmagan o'quvchi — ularni Student Group'ga qo'shish kerak.`
			: classesOnly ? `${this.fmt(d.group_count || 0)} ta sinf — sinfni bosib ichini oching.`
			: `${this.fmt(d.total || 0)} ta faol o'quvchi · ${this.fmt(d.group_count || 0)} ta sinf.`;
		return `${chips}
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sinf / O'quvchi</th><th class="r">O'quvchilar</th><th>Sh. turi</th><th>Tarif</th><th class="r">Yakuniy summa</th><th class="r">Oylik to'lov</th><th class="r">Jami to'lagan</th><th class="r">Oxirgi to'lov</th><th class="r">Oxirgi sana</th><th class="r">Qarzdorlik</th><th>Faolligi</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count">${cnt} To'lovlar — butun tarix bo'yicha, kassaga tushgan real pul. Qarzdorlik — buxgalteriya qoldig'i (nachisleniya − to'lov); manfiy qoldiq <b>avans</b> (peredoplata) deb ko'rsatiladi.</div>`;
	}

	// -- debitorka/kreditorka batafsil (balans daraxtining o'sha bo'lagi) --
	ovBsNode() {
		if (!this.bs) return null;
		return this.ovDetail === "debitorka"
			? ((this.bs.assets || []).find((n) => n.key === "deb") || null)
			: ((this.bs.liabilities || []).find((n) => n.key === "cred") || null);
	}

	loadOvBs() {
		const body = this.page.main.find(".tz-ovbs-body");
		if (!body.length) return;
		const paint = () => {
			const node = this.ovBsNode();
			// birinchi ochilishda daraxtning yuqori qatlamlarini avtomatik ochamiz
			if (node && this._ovBsAuto !== this.ovDetail) {
				this._ovBsAuto = this.ovDetail;
				this.bsOpen.add(node.key);
				(node.children || []).forEach((ch) => this.bsOpen.add(ch.key));
			}
			this.paintOvBs();
		};
		if (this.bs) { paint(); return; }
		body.html(`<div class="tz-loader">Yuklanyapti…</div>`);
		this.fetchBs((err) => {
			if (err) this.page.main.find(".tz-ovbs-body").html(`<div class="empty-hint">Ma'lumotni yuklab bo'lmadi.</div>`);
			else paint();
		});
	}

	paintOvBs() {
		const body = this.page.main.find(".tz-ovbs-body");
		if (!body.length) return;
		const node = this.ovBsNode();
		if (!node) { body.html(`<div class="empty-hint">Ma'lumot topilmadi.</div>`); return; }
		const multi = this.bsMulti();
		const head = multi
			? `<div class="bs-row bs-head"><span class="bs-lab"></span>${(this.bs.periods || []).map((p) => `<span class="bs-amt" data-tt="${this.esc(p.end)}">${this.esc(p.label)}</span>`).join("")}</div>`
			: "";
		body.html(`<div class="bs-scroll"><div class="bs-wrap${multi ? " bs-multi" : ""}">${head}${this.bsNode(node, 0)}</div></div>`);
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	// -- kassa batafsil: ikkita ko'p tanlovli filtr (hisoblar + Kassa operatsiya turi) --
	// Bo'sh tanlov = "hammasi". Menyu ochiq turganda ham qayta chizilaveradi, shuning uchun
	// ochiq menyu kaliti (ovCashMenu) alohida saqlanadi va chizishda tiklanadi.
	// Ko'p tanlovli filtrlar reestri: kalit -> holat massivi nomi va qayta chizish
	MSEL = { acc: "ovCashAccs", op: "ovCashOps", nachgrp: "nachGroups", nachcat: "nachCats",
		nachacct: "nachAccts", nachsinf: "nachSinfs", nachpos: "nachPoss", nachdkind: "nachDkinds",
		perscat: "personalCats" };

	mselList(key) { return this[this.MSEL[key]] || []; }

	mselApply(key) {
		if (key === "acc" || key === "op") { this.paintCashFilter(); this.loadOvCash(true); }
		else if (key === "perscat") { this.paintPersonal(); }
		else { this.paintNach(); }
	}

	repaintMsel() {
		this.paintCashFilter();
		this.paintNachFilter();
		this.paintPersonalFilter();
	}

	// Nachisleniya filtrlari: Guruh (kontragent turi/guruhi) va Toifa (qarshi hisob)
	nachFilterHtml() {
		const side = (this.nach && (this.nachSide === "credit" ? this.nach.credit : this.nach.debit)) || {};
		const opt = (list) => (list || []).map((x) => ({ value: x.label, label: `${x.label} (${x.count})` }));
		// Har bir kesim alohida filtr; ma'lumoti yo'q kesim umuman ko'rsatilmaydi
		// (masalan "Sinf" faqat kirimda, "Lavozim" faqat xodimlar bor tomonda).
		const dims = [
			["nachgrp", "Guruh", side.groups, this.nachGroups],
			["nachacct", "Qarz hisobi", side.accts, this.nachAccts],
			["nachsinf", "Sinf", side.sinfs, this.nachSinfs],
			["nachpos", "Lavozim", side.positions, this.nachPoss],
			["nachdkind", "Hujjat", side.dkinds, this.nachDkinds],
			["nachcat", "Toifa", side.cats, this.nachCats],
		];
		return dims.filter((d) => (d[2] || []).length > 1 || (d[3] || []).length)
			.map((d) => this.mselHtml(d[0], d[1], opt(d[2]), d[3])).join("");
	}

	nachAnyFilter() {
		return !!(this.nachGroups.length || this.nachCats.length || this.nachAccts.length
			|| this.nachSinfs.length || this.nachPoss.length || this.nachDkinds.length);
	}

	nachClearFilters() {
		this.nachGroups = []; this.nachCats = []; this.nachAccts = [];
		this.nachSinfs = []; this.nachPoss = []; this.nachDkinds = [];
	}

	paintNachFilter() {
		const box = this.page.main.find(".tz-nach-filter-box");
		if (box.length) box.html(this.nachFilterHtml());
	}

	mselHtml(key, label, options, selected) {
		const sel = selected || [];
		const cap = !sel.length ? `${label}: hammasi`
			: sel.length === 1 ? `${label}: ${this.esc(this.acctName(sel[0]))}`
			: `${label}: ${sel.length} ta tanlandi`;
		const items = options.length
			? options.map((o) => `<label class="tz-msel-item"><input type="checkbox" data-mselopt="${this.esc(key)}" value="${this.esc(o.value)}"${sel.indexOf(o.value) !== -1 ? " checked" : ""}><span>${this.esc(o.label)}</span></label>`).join("")
			: `<div class="tz-msel-empty">Yuklanyapti…</div>`;
		return `<div class="tz-msel${this.mselOpen === key ? " open" : ""}" data-msel="${this.esc(key)}">
			<button type="button" class="tz-msel-btn${sel.length ? " on" : ""}" data-mselbtn="${this.esc(key)}">${cap} <span class="tz-msel-car">▾</span></button>
			<div class="tz-msel-menu">
				<div class="tz-msel-list">${items}</div>
				<button type="button" class="tz-msel-clear" data-mselclear="${this.esc(key)}">Tanlovni tozalash</button>
			</div>
		</div>`;
	}

	cashFilterHtml() {
		const accs = ((this.ovCash || {}).accounts || [])
			.map((a) => ({ value: a.account, label: this.acctName(a.account) }));
		const ops = (((this.ovCash || {}).all_op_types) || ["Приход", "Расход", "Перемещения", "Конвертация"])
			.map((o) => ({ value: o, label: o }));
		return this.mselHtml("acc", "Hisoblar", accs, this.ovCashAccs)
			+ this.mselHtml("op", "Operatsiya", ops, this.ovCashOps);
	}

	paintCashFilter() {
		const box = this.page.main.find(".tz-cash-filter");
		if (box.length) box.html(this.cashFilterHtml());
	}

	// -- kassa batafsil (hisoblar + oxirgi harakatlar) --
	loadOvCash(force) {
		const body = this.page.main.find(".tz-ovcash-body");
		if (!body.length) return;
		const paint = () => {
			const b = this.page.main.find(".tz-ovcash-body");
			if (!b.length) return;
			b.html(this.renderOvCash(this.ovCash || {}));
			b.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
			this.paintCashFilter();
		};
		if (this.ovCash && !force) { paint(); return; }
		body.html(`<div class="tz-loader">Harakatlar yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_cash_detail",
			args: {
				to_date: this.state.to_date,
				accounts: JSON.stringify(this.ovCashAccs || []),
				op_types: JSON.stringify(this.ovCashOps || []),
			},
		}).then((r) => { this.ovCash = r.message || {}; paint(); })
			.catch(() => body.html(`<div class="empty-hint">Kassa harakatlarini yuklab bo'lmadi.</div>`));
	}

	renderOvCash(d) {
		const accounts = d.accounts || [];
		const picked = this.ovCashAccs || [];
		const chips = accounts.map((a) => `
			<button class="tz-acc-chip${picked.indexOf(a.account) !== -1 ? " active" : ""}" data-ovcash-acc="${this.esc(a.account)}" title="${this.fmt(a.balance)} ${this.esc(a.currency)} · ${this.esc(a.mode || "")}">
				<span class="t">${this.esc(this.acctName(a.account))}</span>
				<b class="num" style="color:${a.balance < 0 ? "var(--bad-ink)" : "var(--ink)"}">${this.kc(a.balance)} <small>${this.ccyLabel(a.currency)}</small></b>
			</button>`).join("");
		const single = !!d.account;
		const tx = d.transactions || [];
		const cols = single ? 7 : 7;
		const body = tx.length ? tx.map((x) => {
			const slug = String(x.voucher_type || "").toLowerCase().replace(/ /g, "-");
			const who = this.acctName(x.who || "");
			return `<tr>
				<td class="num" style="white-space:nowrap">${this.dmy(x.date)}</td>
				${single ? "" : `<td class="ell" data-tt="${this.esc(x.account)}">${this.esc(this.acctName(x.account))}</td>`}
				<td class="ell" data-tt="${this.esc(who)}">${who ? this.esc(who) : `<span class="muted-s">—</span>`}</td>
				<td class="r num" style="color:var(--good-ink)">${x.kirim ? this.fmt(x.kirim) : ""}</td>
				<td class="r num" style="color:var(--bad-ink)">${x.chiqim ? this.fmt(x.chiqim) : ""}</td>
				${single ? `<td class="r num" style="font-weight:700">${this.fmt(x.balance)}</td>` : ""}
				<td class="ell" style="max-width:260px;color:var(--muted);font-size:12px" data-tt="${this.esc(x.remarks)}">${x.remarks ? this.esc(x.remarks) : `<span class="muted-s">—</span>`}</td>
				<td>${x.voucher_no ? `<a class="tz-kassa-link" href="/app/${slug}/${encodeURIComponent(x.voucher_no)}" target="_blank" rel="noopener">${this.esc(x.voucher_no)}</a>` : "—"}</td>
			</tr>`;
		}).join("") : `<tr><td colspan="${cols}" class="empty-hint">Harakat topilmadi.</td></tr>`;
		const cur = d.currency;
		const thead = `<tr><th>Sana</th>${single ? "" : "<th>Hisob</th>"}<th>Kimdan / kimga</th><th class="r">Kirim</th><th class="r">Chiqim</th>${single ? `<th class="r">Qoldiq${cur ? " (" + this.esc(cur) + ")" : ""}</th>` : ""}<th>Izoh</th><th>Hujjat</th></tr>`;
		const opsOn = (this.ovCashOps || []);
		const opTxt = opsOn.length ? ` · operatsiya turi: <b>${opsOn.map((o) => this.esc(o)).join(", ")}</b>` : "";
		return `<div class="ov-chips">${chips}</div>
			<div class="kt-legend">${single
				? `<b>${this.esc(this.acctName(d.account))}</b> — oxirgi harakatlar, har qatorda o'sha kundan keyingi qoldiq. Chipni yana bosib filtrni olib tashlang.`
				: picked.length
					? `Tanlangan <b>${picked.length}</b> ta hisob birga${opTxt}. Yurish qoldig'i faqat bitta hisob tanlanganda (operatsiya filtrisiz) ko'rsatiladi.`
					: `Barcha kassa/bank hisoblari birga${opTxt} — hisob chipini yoki tepadagi filtrni ishlating.`}</div>
			<div class="tbl-wrap"><table><thead>${thead}</thead><tbody>${body}</tbody></table></div>
			<div class="kt-count">Oxirgi ${tx.length} ta harakat ko'rsatildi${tx.length >= (d.limit || 300) ? " (limitga yetdi — oraliqni qisqartiring)" : ""}.</div>`;
	}

	// ================= TAB: Cashflow =================
	cfMetricMeta() {
		return {
			opening: { label: "Boshlang'ich qoldiq", color: "var(--muted)" },
			kirim: { label: "Davr kirimi", color: "var(--good)" },
			chiqim: { label: "Davr chiqimi", color: "var(--bad)" },
			closing: { label: "Yakuniy qoldiq", color: "var(--brand)" },
		};
	}

	renderCashflow() {
		const cf = this.data.cashflow;
		const mm = this.cfMetricMeta();
		// Tanlangan valyutaga qarab KPI qiymatlari (USD tanlansa USD, UZS tanlansa UZS)
		let kt = cf.total, kpiCcy = this.data.meta.currency;
		if (this.cfCcy) {
			const bc = (cf.by_currency || []).find((b) => b.currency === this.cfCcy);
			if (bc) { kt = bc; kpiCcy = this.cfCcy; }
		}

		// TOP: valyuta jami (chap) | chiziq | budjet xarajati (o'ng) — tanlash tugmalari
		let h = this.sec("Valyuta kesimida va budjet xarajati", this.data.meta.period.label);
		h += this.topCombined(cf);

		// Kassa harakati KPI — tanlangan valyuta bo'yicha
		h += this.sec("Kassa harakati", `boshlang'ich → kirim → chiqim → yakuniy · kirim/chiqim ichki o'tkazmasiz (konvertatsiya/ko'chirma)${this.cfCcy ? " · " + this.esc(this.cfCcy) : ""}`);
		const kpi = (metric, raw, pin, valColor) => {
			const clickable = metric === "kirim" || metric === "chiqim";
			return this.moneyKpi({
				label: mm[metric].label, raw, pin, valColor, ccy: kpiCcy, noBadge: true,
				cls: clickable ? ("clickable" + (this.cfFlow === metric ? " active" : "")) : "",
				click: clickable ? `data-cf-flow="${metric}"` : "",
			});
		};
		h += `<div class="grid cols-4 mb">
			${kpi("opening", kt.opening, "var(--muted)")}
			${kpi("kirim", kt.kirim, "var(--good)", "var(--good-ink)")}
			${kpi("chiqim", kt.chiqim, "var(--bad)", "var(--bad-ink)")}
			${kpi("closing", kt.closing, "var(--brand)")}
		</div>`;

		// BITTA JADVAL — tanlovga qarab bittasi ko'rinadi (kirim/chiqim/valyuta/budjet)
		if (this.cfFlow) {
			h += this.flowDetailTable(cf, this.cfFlow);
		} else if (this.budgetView) {
			h += this.budgetBreakdown(cf);
		} else {
			h += this.accountsTable(cf);   // cfCcy bo'lsa shu valyuta bo'yicha, aks holda hammasi
		}

		// Hisob ustiga bosilganda — o'sha hisobni tashkil qilgan harakatlar
		if (!this.cfFlow && !this.budgetView && this.cfAcc) {
			h += `<div class="tz-cfacc-wrap"><div class="tz-loader">Harakatlar yuklanyapti…</div></div>`;
			setTimeout(() => this.loadCfAcc(), 0);
		}
		return h + this.note();
	}

	ccyCards(list) {
		const base = this.data.meta.currency;
		if (!list || !list.length) return `<div class="empty-hint">Valyuta ma'lumoti yo'q.</div>`;
		const cards = list.map((c) => {
			const isBase = c.currency === base, active = this.cfCcy === c.currency;
			return `<div class="ccy-card${isBase ? " base" : ""}${active ? " active" : ""}" data-cf-ccy="${this.esc(c.currency)}">
				<div class="ccy-top"><span class="ccy-code">${this.esc(c.currency)}</span>${isBase ? `<span class="ccy-tag">asosiy</span>` : ""}</div>
				<div class="ccy-close num" data-tt="${this.fmt(c.closing)} ${this.esc(c.currency)}">${this.fmt(c.closing)} <span class="cur">${this.ccyLabel(c.currency)}</span></div>
				<div class="ccy-flow">
					<span class="in num" data-tt="Kirim: ${this.fmt(c.kirim)}">▲ ${this.kc(c.kirim)}</span>
					<span class="out num" data-tt="Chiqim: ${this.fmt(c.chiqim)}">▼ ${this.kc(c.chiqim)}</span>
				</div>
				<div class="ccy-open num">Boshi: ${this.kc(c.opening)}</div>
			</div>`;
		}).join("");
		return `<div class="ccy-grid">${cards}</div>`;
	}

	budgetCells(b) {
		if (!b || !b.available) {
			return `<div class="empty-hint">Budjet guruhi topilmadi (Chart of Accounts'da "Budget/Budjet" nomli guruh yo'q).</div>`;
		}
		const ccy = this.ccyLabel(this.data.meta.currency);
		const bud = Math.max(0, b.budget), nor = Math.max(0, b.normal), tot = bud + nor || 1;
		const cell = (key, label, amount, color) => `
			<div class="bud-cell clickable${this.budgetView === key ? " active" : ""}" data-budget="${key}">
				<div class="bud-lab"><span class="sw" style="background:${color}"></span> ${this.esc(label)}</div>
				<div class="bud-val num" data-tt="${this.fmt(amount)} ${ccy}">${this.kc(amount)} <span class="cur">${ccy}</span></div>
				<div class="bud-pct num">${(amount / tot * 100).toFixed(1)}% · bosing ▾</div>
			</div>`;
		return `<div class="bud-grid">
			${cell("budget", b.budget_label, bud, "var(--c1)")}
			${cell("normal", b.normal_label, nor, "var(--c3)")}
		</div>`;
	}

	// TOP blok: chapda valyuta jami, o'ngda budjet xarajati — o'rtada chiziq
	topCombined(cf) {
		const ccy = this.ccyLabel(this.data.meta.currency), b = cf.budget;
		const budTotal = (b && b.available) ? Math.max(0, b.budget) + Math.max(0, b.normal) : 0;
		return this.card(`
			<div class="topsplit">
				<div class="topsplit-col">
					<div class="hd"><div><h3>Valyutalar kesimida jami</h3><div class="meta">Bosib jadvalni filtrlang · har valyuta o'z birligida</div></div></div>
					${this.ccyCards(cf.by_currency)}
				</div>
				<div class="topsplit-div"></div>
				<div class="topsplit-col">
					<div class="hd"><div><h3>Xarajat — budjet bo'yicha</h3><div class="meta">${this.data.meta.period.label} · budjetga kirgan / kirmagan</div></div>
						${(b && b.available) ? `<div class="focus-total num">Jami: ${this.fmt(budTotal)} ${ccy}</div>` : ""}</div>
					${this.budgetCells(b)}
				</div>
			</div>`, "mb");
	}

	// hisoblar kesimi jadvali (default; cfCcy bo'lsa shu valyuta bo'yicha filtr)
	// Hisob ustiga bosilganda — o'sha hisobning shu DAVRDAGI harakatlari
	// (kimdan/kimga, qaysi hujjat, kirim/chiqim, yurish qoldig'i bilan).
	loadCfAcc() {
		const wrap = this.page.main.find(".tz-cfacc-wrap");
		if (!wrap.length || !this.cfAcc) return;
		const paint = () => {
			const w = this.page.main.find(".tz-cfacc-wrap");
			if (!w.length) return;
			w.html(this.cfAccTable());
			w.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
		};
		if (this.cfAccTx && this.cfAccTx.account === this.cfAcc
			&& this.cfAccTx.from === this.state.from_date && this.cfAccTx.to === this.state.to_date) {
			paint(); return;
		}
		wrap.html(`<div class="tz-loader">Harakatlar yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_cash_detail",
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				accounts: JSON.stringify([this.cfAcc]), limit: 500,
			},
		}).then((r) => {
			this.cfAccTx = Object.assign({ account: this.cfAcc, from: this.state.from_date, to: this.state.to_date },
				r.message || {});
			paint();
		}).catch(() => wrap.html(`<div class="empty-hint">Harakatlarni yuklab bo'lmadi.</div>`));
	}

	cfAccTable() {
		const d = this.cfAccTx || {};
		const tx = d.transactions || [];
		const cur = d.currency || this.data.meta.currency;
		const tin = tx.reduce((n, x) => n + (x.kirim || 0), 0);
		const tout = tx.reduce((n, x) => n + (x.chiqim || 0), 0);
		const body = tx.length ? tx.map((x) => {
			const slug = String(x.voucher_type || "").toLowerCase().replace(/ /g, "-");
			const who = this.acctName(x.who || "");
			return `<tr>
				<td class="num" style="white-space:nowrap">${this.dmy(x.date)}</td>
				<td class="ell" data-tt="${this.esc(who)}">${who ? this.esc(who) : `<span class="muted-s">—</span>`}</td>
				<td class="ell" data-tt="${this.esc(x.op_type || "")}">${x.op_type ? this.esc(x.op_type) : `<span class="muted-s">—</span>`}</td>
				<td class="r num" style="color:var(--good-ink)">${x.kirim ? this.mAmt(x.kirim, cur) : ""}</td>
				<td class="r num" style="color:var(--bad-ink)">${x.chiqim ? this.mAmt(x.chiqim, cur) : ""}</td>
				<td class="r num" style="font-weight:700">${x.balance !== undefined ? this.mAmt(x.balance, cur) : ""}</td>
				<td class="ell" style="max-width:260px;color:var(--muted);font-size:12px" data-tt="${this.esc(x.remarks)}">${x.remarks ? this.esc(x.remarks) : `<span class="muted-s">—</span>`}</td>
				<td style="white-space:nowrap">${x.voucher_no ? `<a class="tz-kassa-link" href="/app/${slug}/${encodeURIComponent(x.voucher_no)}" target="_blank" rel="noopener">${this.esc(x.voucher_no)}</a>` : "—"}</td>
			</tr>`;
		}).join("") : `<tr><td colspan="8" class="empty-hint">Bu davrda harakat topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd"><div><h3>${this.esc(this.acctName(this.cfAcc))} — harakatlar</h3>
				<div class="meta">${this.data.meta.period.label} · eng yangisi tepada · qatorni bosib hujjatga o'ting · yana bosib yoping</div></div>
				<div class="focus-total num">Kirim: <b style="color:var(--good-ink)">${this.mAmt(tin, cur)}</b> · Chiqim: <b style="color:var(--bad-ink)">${this.mAmt(tout, cur)}</b> · ${tx.length} ta</div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>Kimdan / kimga</th><th>Operatsiya</th><th class="r">Kirim</th><th class="r">Chiqim</th><th class="r">Qoldiq</th><th>Izoh</th><th>Hujjat</th></tr></thead>
				<tbody>${body}</tbody>
			</table></div>
			<div class="kt-count">${tx.length >= (d.limit || 500) ? "Limitga yetdi — davrni qisqartiring." : ""}</div>`, "mb");
	}

	accountsTable(cf) {
		let accts = cf.accounts || [];
		if (this.cfCcy) accts = accts.filter((a) => a.currency === this.cfCcy);
		const rows = accts.length ? accts.map((a) => `
			<tr class="cf-acc-row${this.cfAcc === a.account ? " active" : ""}" data-cfacc="${this.esc(a.account)}">
			<td class="ell" data-tt="${this.esc(a.account)}"><span class="dds-arrow">${this.cfAcc === a.account ? "▼" : "▶"}</span> ${this.esc(this.acctName(a.account))}</td>
			<td class="ell">${this.esc(a.mode || "")}</td>
			<td class="r num">${this.fmt(a.opening)}${a.currency !== this.data.meta.currency ? " " + this.esc(a.currency) : ""}</td>
			<td class="r num" style="color:var(--good-ink)">${this.fmt(a.kirim)}</td>
			<td class="r num" style="color:var(--bad-ink)">${this.fmt(a.chiqim)}</td>
			<td class="r num" style="font-weight:700">${this.fmt(a.closing)}</td></tr>`).join("")
			: `<tr><td colspan="6" class="empty-hint">Hisob topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd"><div><h3>Hisoblar kesimida${this.cfCcy ? ` · ${this.esc(this.cfCcy)}` : ""}</h3><div class="meta">Hisob ustiga bosing — o'sha davrda uni tashkil qilgan harakatlar pastda ochiladi · yakun — haqiqiy qoldiq</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Hisob</th><th>Usul</th><th class="r">Boshi</th><th class="r">Kirim</th><th class="r">Chiqim</th><th class="r">Yakun</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>`, "mb");
	}

	// kirim/chiqim bosilganda — batafsil jadval: har bir to'lov KIM · QANCHA · QACHON (tanlangan valyuta bo'yicha)
	flowDetailTable(cf, dir) {
		const inflow = dir === "kirim";
		const curCode = this.cfCcy || this.data.meta.currency;   // valyuta tanlansa o'sha, aks holda asosiy
		const all = (inflow ? cf.categories.in_tx : cf.categories.out_tx) || [];
		const tx = all.filter((x) => (x.currency || this.data.meta.currency) === curCode);
		const ccy = this.ccyLabel(curCode);
		const color = inflow ? "var(--good-ink)" : "var(--bad-ink)";
		const title = inflow ? `Kirim — kimdan, qancha, qachon${this.cfCcy ? " · " + this.esc(curCode) : ""}` : `Chiqim — kimga, qancha, qachon${this.cfCcy ? " · " + this.esc(curCode) : ""}`;
		const whoHead = inflow ? "Kimdan" : "Kimga";
		const total = tx.reduce((s, x) => s + x.amount, 0);
		const body = tx.length ? tx.map((x) => `
			<tr>
				<td class="num" style="white-space:nowrap">${this.dmy(x.date)}</td>
				<td class="ell" data-tt="${this.esc(x.name)}">${this.esc(x.name)}</td>
				<td><span class="cat-badge">${this.esc(x.category_label)}</span></td>
				<td class="r num" style="color:${color};font-weight:600">${this.fmt(x.amount)}</td>
			</tr>`).join("")
			: `<tr><td colspan="4" class="empty-hint">Bu davrda ${inflow ? "kirim" : "chiqim"} harakati topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd"><div><h3>${title}</h3><div class="meta">${this.data.meta.period.label} · ${ccy} · sana bo'yicha (eng yangisi tepada)</div></div>
				<div class="focus-total num">Jami: ${this.fmt(total)} ${ccy} · ${tx.length} ta</div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>${whoHead}</th><th>Kategoriya</th><th class="r">Summa (${ccy})</th></tr></thead>
				<tbody>${body}</tbody>
			</table></div>
			${tx.length >= 300 ? `<div class="kt-count">Eng yangi 300 ta harakat ko'rsatildi.</div>` : ""}`, "mb budget-breakdown");
	}

	// budjet karta bosilganda — o'sha guruh tarkibi JADVALda: hisob (xarajat) va sarflangan summa
	budgetBreakdown(cf) {
		if (!this.budgetView) return "";
		const b = cf.budget;
		if (!b || !b.available) return "";
		const isBud = this.budgetView === "budget";
		const list = (isBud ? b.budget_accounts : b.normal_accounts) || [];
		const label = isBud ? b.budget_label : b.normal_label;
		const color = isBud ? "var(--c1)" : "var(--c3)";
		const ccy = this.ccyLabel(this.data.meta.currency);
		const total = list.reduce((s, x) => s + x.amount, 0) || 1;
		const body = list.length ? list.map((x, i) => `
			<tr>
				<td class="num muted-s" style="width:34px">${i + 1}</td>
				<td class="ell" data-tt="${this.esc(x.label)}"><span class="pin" style="display:inline-block;width:8px;height:8px;border-radius:3px;background:${color};margin-right:7px"></span>${this.esc(x.label)}</td>
				<td class="r num" style="font-weight:600">${this.fmt(x.amount)}</td>
				<td class="r num muted-s">${(x.amount / total * 100).toFixed(1)}%</td>
			</tr>`).join("")
			: `<tr><td colspan="4" class="empty-hint">Bu davrda bu guruhda xarajat topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd"><div><h3>${this.esc(label)} — tarkibi</h3><div class="meta">Qaysi xarajatga qancha sarflandi · ${this.data.meta.period.label}</div></div>
				<div class="focus-total num">Jami: ${this.fmt(total)} ${ccy}</div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>#</th><th>Xarajat hisobi</th><th class="r">Summa (${ccy})</th><th class="r">Ulush</th></tr></thead>
				<tbody>${body}</tbody>
				<tfoot><tr class="b"><td></td><td>Jami</td><td class="r num">${this.fmt(total)}</td><td class="r num">100%</td></tr></tfoot>
			</table></div>`, "mb budget-breakdown");
	}

	calendarCard(cal) {
		if (!cal || !cal.days_in_month) return this.card(`<div class="empty-hint">Kunlik ma'lumot yo'q.</div>`);
		const days = cal.days || {}, dim = cal.days_in_month, off = cal.first_weekday || 0;
		const vals = Object.values(days).filter((v) => v > 0), max = vals.length ? Math.max(...vals) : 0;
		const lvl = (v) => !v ? 0 : (!max ? 1 : (v / max > .66 ? 3 : (v / max > .33 ? 2 : 1)));
		let cells = "";
		for (let e = 0; e < off; e++) cells += `<div class="cell empty"></div>`;
		for (let dd = 1; dd <= dim; dd++) {
			const v = days[dd] || 0;
			cells += `<div class="cell h${lvl(v)}" data-tt="${dd}-${this.esc(cal.month_label)}: ${v ? this.fmt(v) : "yig'im yo'q"}"><span class="d">${dd}</span><span class="m">${v ? this.kcT(v) : ""}</span></div>`;
		}
		return this.card(`
			<div class="hd"><div><h3>Kunlik kassa kirimi</h3><div class="meta">${this.esc(cal.month_label)} ${cal.year} (oraliq oxirgi oyi)</div></div>
				<div class="legend"><div class="it"><span class="sw" style="background:var(--card-2);border:1px solid var(--line)"></span> Yo'q</div><div class="it"><span class="sw" style="background:var(--h1)"></span> Kam</div><div class="it"><span class="sw" style="background:var(--h2)"></span> O'rta</div><div class="it"><span class="sw" style="background:var(--h3)"></span> Ko'p</div></div></div>
			<div class="cal-head"><span>Du</span><span>Se</span><span>Ch</span><span>Pa</span><span>Ju</span><span>Sh</span><span>Ya</span></div>
			<div class="cal">${cells}</div>`);
	}

	// ================= TAB: Debts (kontragent) =================
	renderDebts() {
		const d = this.data.debts;
		let h = this.sec("Qarzdorlik holati", `${this.data.meta.period.label} oxiriga`);
		h += `<div class="grid cols-4 mb tz-debts-top">
			${this.moneyKpi({ label: "Jami debitorka (bizga qarz)", raw: d.receivable_total, cmp: d.receivable_cmp, invert: true, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.moneyKpi({ label: "Jami kreditorka (biz qarz)", raw: -d.payable_total, cmp: d.payable_cmp, invert: true, pin: "var(--bad)", valColor: "var(--bad-ink)" })}
			${this.ktTotPlaceholder()}
		</div>`;

		// kontragent otchot jadvali (filtr + jadval)
		const types = ["Customer", "Supplier", "Employee", "Shareholder", "Student"];
		const typeOpts = types.map((t) => `<option value="${t}"${this.ktFilter.party_type === t ? " selected" : ""}>${t}</option>`).join("");
		const ccyOpts = ["", "UZS", "USD"].map((c) => `<option value="${c}"${this.ktFilter.currency === c ? " selected" : ""}>${c || "Barcha valyuta"}</option>`).join("");
		h += this.card(`
			<div class="hd"><div><h3>Kontragent otchot</h3><div class="meta">Boshlang'ich qoldiq → davr harakati → yakuniy qoldiq · ${this.data.meta.period.label}</div></div>
				<div class="kt-filter">
					<select class="form-control tz-kt-type">${typeOpts}</select>
					<select class="form-control tz-kt-party"><option value="">Barcha kontragent</option></select>
					<select class="form-control tz-kt-group"><option value="">Barcha guruh</option></select>
					<select class="form-control tz-kt-ccy">${ccyOpts}</select>
				</div>
			</div>
			<div class="tz-kt-body"><div class="tz-loader">Kontragentlar yuklanyapti…</div></div>
		`);
		// jadval + party/guruh ro'yxatini yuklash
		setTimeout(() => { this.loadKontragentParties(); this.loadKontragentGroups(); this.loadKontragent(); }, 0);
		return h + this.note();
	}

	loadKontragentParties() {
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_kontragent_parties",
			args: { party_type: this.ktFilter.party_type },
		}).then((r) => {
			const list = r.message || [];
			const sel = this.page.main.find(".tz-kt-party");
			if (!sel.length) return;
			sel.html(`<option value="">Barcha kontragent (${list.length})</option>` +
				list.map((p) => `<option value="${this.esc(p.value)}"${this.ktFilter.party === p.value ? " selected" : ""}>${this.esc(p.label)}</option>`).join(""));
		});
	}

	loadKontragentGroups() {
		const sel = this.page.main.find(".tz-kt-group");
		if (!sel.length) return;
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_kontragent_groups",
			args: { party_type: this.ktFilter.party_type },
		}).then((r) => {
			const list = r.message || [];
			const sel2 = this.page.main.find(".tz-kt-group");
			if (!sel2.length) return;
			// tanlangan guruh yangi ro'yxatda bo'lmasa — tozalash
			if (this.ktFilter.party_group && list.indexOf(this.ktFilter.party_group) === -1) this.ktFilter.party_group = "";
			sel2.html(`<option value="">Barcha guruh</option>` +
				list.map((g) => `<option value="${this.esc(g)}"${this.ktFilter.party_group === g ? " selected" : ""}>${this.esc(g)}</option>`).join(""));
		});
	}

	loadKontragent() {
		const body = this.page.main.find(".tz-kt-body");
		if (!body.length) return;
		body.html(`<div class="tz-loader">Jadval yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_kontragent",
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				party_type: this.ktFilter.party_type, party: this.ktFilter.party || null,
				currency: this.ktFilter.currency || null,
				party_group: this.ktFilter.party_group || null,
			},
		}).then((r) => {
			this.kontragent = r.message || { rows: [], totals: [] };
			this.page.main.find(".tz-kt-body").html(this.renderKontragentTable(this.kontragent));
			this.page.main.find(".tz-kt-body [data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
			this.renderKtTotals(this.kontragent.totals || []);
		}).catch(() => body.html(`<div class="empty-hint">Kontragent ma'lumotini yuklab bo'lmadi.</div>`));
	}

	// Kontragent JAMI kartalari — tepadagi KPI qatorida, filtrga mos yangilanadi
	ktTotPlaceholder() {
		return `<div class="card kpi tz-kt-tot"><div class="lab"><span class="pin" style="background:var(--brand)"></span> Kontragent jami</div><div class="empty-hint" style="padding:10px 0">Yuklanyapti…</div></div>`;
	}

	ktBal(cr, dr, big) {
		// Кт = biz qarzmiz (qarzdorlik) — qizil va MINUS; Дт = bizga qarzdor (haqdorlik) — yashil musbat
		const cls = "num" + (big ? " ktt-big" : "");
		const kt = `<span class="${cls}" style="color:var(--bad-ink);font-weight:700">${this.fmt(-cr)} <small>Kт</small></span>`;
		const dt = `<span class="${cls}" style="color:var(--good-ink)">${this.fmt(dr)} <small>Дт</small></span>`;
		if (cr > 0.5 && dr > 0.5) return `<span class="ktt-two">${kt}${dt}</span>`;
		if (cr > 0.5) return kt;
		if (dr > 0.5) return dt;
		return `<span class="${cls} muted-s">0</span>`;
	}

	ktTotCard(t) {
		return `<div class="card kpi tz-kt-tot">
			<div class="lab"><span class="pin" style="background:var(--brand)"></span> Kontragent jami <span class="ktt-ccy">${this.esc(t.currency)}</span></div>
			<div class="ktt-rows">
				<div class="ktt-row"><span>Boshi (qoldiq)</span>${this.ktBal(t.opening_credit, t.opening_debit)}</div>
				<div class="ktt-row"><span>Davr Kт (kirim)</span><span class="num" style="color:var(--c5)">${this.fmt(t.period_credit)}</span></div>
				<div class="ktt-row"><span>Davr Дт (chiqim)</span><span class="num" style="color:var(--warn-ink)">${this.fmt(t.period_debit)}</span></div>
				<div class="ktt-row ktt-final"><span>Oxiri (qoldiq)</span>${this.ktBal(t.final_credit, t.final_debit, true)}</div>
			</div>
		</div>`;
	}

	renderKtTotals(totals) {
		const top = this.page.main.find(".tz-debts-top");
		if (!top.length) return;
		// UZS birinchi, keyin qolgan valyutalar
		const sorted = (totals || []).slice().sort((a, b) => (a.currency === "UZS" ? -1 : b.currency === "UZS" ? 1 : a.currency.localeCompare(b.currency)));
		const html = sorted.length
			? sorted.map((t) => this.ktTotCard(t)).join("")
			: `<div class="card kpi tz-kt-tot"><div class="lab"><span class="pin" style="background:var(--brand)"></span> Kontragent jami</div><div class="empty-hint" style="padding:10px 0">Filtr bo'yicha harakat yo'q.</div></div>`;
		top.find(".tz-kt-tot").remove();
		top.append(html);
	}

	renderKontragentTable(k) {
		const rows = k.rows || [];
		if (!rows.length) return `<div class="empty-hint" style="padding:22px 8px">Tanlangan filtr bo'yicha harakat topilmadi.</div>`;
		// Кт (biz qarzmiz) — qizil va minus · Дт (bizga qarzdor) — yashil musbat
		const bal = (cr, dr) => {
			if (cr > 0.5) return `<span class="num" style="color:var(--bad-ink);font-weight:700">${this.fmt(-cr)} <small>Kт</small></span>`;
			if (dr > 0.5) return `<span class="num" style="color:var(--good-ink)">${this.fmt(dr)} <small>Дт</small></span>`;
			return `<span class="num muted-s">0</span>`;
		};
		const body = rows.map((r) => `
			<tr>
				<td class="ell" data-tt="${this.esc(r.name)}">${this.esc(r.name)}</td>
				<td class="ell">${r.party_group ? this.esc(r.party_group) : `<span class="muted-s">—</span>`}</td>
				<td>${this.esc(r.currency)}</td>
				<td class="r">${bal(r.opening_credit, r.opening_debit)}</td>
				<td class="r num" style="color:var(--c5)">${this.fmt(r.period_credit)}</td>
				<td class="r num" style="color:var(--warn-ink)">${this.fmt(r.period_debit)}</td>
				<td class="r">${bal(r.final_credit, r.final_debit)}</td>
			</tr>`).join("");
		const tot = (k.totals || []).map((t) => `
			<tr class="b">
				<td>JAMI</td><td></td><td>${this.esc(t.currency)}</td>
				<td class="r">${this.ktBal(t.opening_credit, t.opening_debit)}</td>
				<td class="r num" style="color:var(--c5)">${this.fmt(t.period_credit)}</td>
				<td class="r num" style="color:var(--warn-ink)">${this.fmt(t.period_debit)}</td>
				<td class="r">${this.ktBal(t.final_credit, t.final_debit)}</td>
			</tr>`).join("");
		return `
			<div class="kt-legend"><b style="color:var(--bad-ink)">Kт (minus, qizil)</b> — biz qarzmiz (kreditor, bizning qarzdorligimiz) · <b style="color:var(--good-ink)">Дт (musbat)</b> — bizga qarzdor (debitor, haqdorligimiz)</div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Kontragent</th><th>Guruh</th><th>Valyuta</th><th class="r">Boshi (qoldiq)</th><th class="r">Davr Kт (kirim)</th><th class="r">Davr Дт (chiqim)</th><th class="r">Oxiri (qoldiq)</th></tr></thead>
				<tbody>${body}</tbody>
				<tfoot>${tot}</tfoot>
			</table></div>
			<div class="kt-count">${rows.length} ta kontragent ko'rsatildi${rows.length >= 500 ? " (500 ta bilan cheklangan)" : ""}.</div>`;
	}

	// ================= TAB: DDS (pul oqimi) =================
	renderDds() {
		const meta = this.data.meta;
		let h = this.sec("Pul oqimi hisoboti (DDS)", meta.period.label);
		const types = ["", "Customer", "Supplier", "Shareholder", "Employee"];
		const typeOpts = types.map((t) => `<option value="${t}"${this.ddsFilter.party_type === t ? " selected" : ""}>${t || "Barcha tur"}</option>`).join("");
		const cats = ["", "Покупатели", "Поставщики", "Учредители", "Расходы", "Дивиденд 1", "Дивиденд 2", "Дивиденд 3", "Сотрудники", "Перемещения"];
		const catOpts = cats.map((c) => `<option value="${c}"${this.ddsFilter.category === c ? " selected" : ""}>${c || "Barcha kategoriya"}</option>`).join("");
		h += this.card(`
			<div class="hd"><div><h3>Kassa pul oqimi</h3><div class="meta">Boshlang'ich qoldiq → kategoriyalar → yakuniy qoldiq · ${meta.period.label}</div></div>
				<div class="kt-filter">
					<select class="form-control tz-dds-mode"><option value="">Barcha kassa</option></select>
					<select class="form-control tz-dds-type">${typeOpts}</select>
					<select class="form-control tz-dds-party"><option value="">Barcha kontragent</option></select>
					<select class="form-control tz-dds-category">${catOpts}</select>
				</div>
			</div>
			<div class="tz-dds-body"><div class="tz-loader">Yuklanyapti…</div></div>
		`);
		setTimeout(() => { this.loadDdsParties(); this.loadDds(); }, 0);
		return h + this.note();
	}

	loadDds() {
		const body = this.page.main.find(".tz-dds-body");
		if (!body.length) return;
		body.html(`<div class="tz-loader">Jadval yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_dds",
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				mode_of_payment: this.ddsFilter.mode_of_payment || null,
				party_type: this.ddsFilter.party_type || null,
				party: this.ddsFilter.party || null,
				category: this.ddsFilter.category || null,
			},
		}).then((r) => {
			this.dds = r.message || {};
			this.fillDdsModes(this.dds.modes || []);
			const b = this.page.main.find(".tz-dds-body");
			b.html(this.renderDdsSummary(this.dds) + this.renderDdsTable(this.dds));
			b.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
		}).catch(() => body.html(`<div class="empty-hint">DDS ma'lumotini yuklab bo'lmadi.</div>`));
	}

	fillDdsModes(list) {
		const sel = this.page.main.find(".tz-dds-mode");
		if (!sel.length) return;
		sel.html(`<option value="">Barcha kassa</option>` +
			list.map((m) => `<option value="${this.esc(m)}"${this.ddsFilter.mode_of_payment === m ? " selected" : ""}>${this.esc(m)}</option>`).join(""));
	}

	loadDdsParties() {
		const sel = this.page.main.find(".tz-dds-party");
		if (!sel.length) return;
		if (!this.ddsFilter.party_type) { sel.html(`<option value="">Barcha kontragent</option>`); return; }
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_kontragent_parties",
			args: { party_type: this.ddsFilter.party_type },
		}).then((r) => {
			const list = r.message || [];
			const s = this.page.main.find(".tz-dds-party");
			if (!s.length) return;
			s.html(`<option value="">Barcha kontragent (${list.length})</option>` +
				list.map((p) => `<option value="${this.esc(p.value)}"${this.ddsFilter.party === p.value ? " selected" : ""}>${this.esc(p.label)}</option>`).join(""));
		});
	}

	renderDdsSummary(d) {
		const g = (v) => (Math.abs(v) > 0.005 ? `<span class="num" style="color:var(--good)">${this.fmt(v)}</span>` : `<span class="muted-s">—</span>`);
		const rr = (v) => (Math.abs(v) > 0.005 ? `<span class="num" style="color:var(--warn-ink)">${this.fmt(v)}</span>` : `<span class="muted-s">—</span>`);
		let rows = "";
		(d.categories || []).forEach((cat) => {
			const isExp = cat.key === "expense" && (d.expense_breakdown || []).length;
			const isDiv = cat.key === "dividend" && (d.dividend_breakdown || []).length;
			const tk = isExp ? "expense" : (isDiv ? "dividend" : "");
			rows += `<tr class="${tk ? "dds-parent" : ""}"${tk ? ` data-dds-toggle="${tk}" style="cursor:pointer"` : ""}>
				<td>${tk ? `<span class="dds-arrow" data-arrow="${tk}">▶</span> ` : ""}${this.esc(cat.label)}</td>
				<td class="r">${g(cat.kirim)}</td>
				<td class="r">${rr(cat.chiqim)}</td></tr>`;
			const bd = isDiv ? d.dividend_breakdown : (isExp ? d.expense_breakdown : null);
			if (bd) rows += bd.map((b) => `<tr class="dds-sub dds-sub-${tk}" style="display:none">
				<td class="dds-subcell ell" data-tt="${this.esc(b.label)}">${this.esc(b.label)}</td>
				<td class="r">${g(b.kirim)}</td>
				<td class="r">${rr(b.chiqim)}</td></tr>`).join("");
		});
		return this.card(`
			<div class="hd"><div><h3>Umumiy oqim</h3><div class="meta">Kategoriyalar kesimida kirim/chiqim</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Kategoriya</th><th class="r">Kirim</th><th class="r">Chiqim</th></tr></thead>
				<tbody>
					<tr class="b"><td>Начальный остаток (boshlang'ich)</td><td class="r" colspan="2">${this.fmt(d.opening)}</td></tr>
					${rows || `<tr><td colspan="3"><span class="muted-s">Harakat yo'q</span></td></tr>`}
					<tr class="b"><td>Конечный остаток (yakuniy)</td><td class="r" colspan="2">${this.fmt(d.closing)}</td></tr>
				</tbody>
				<tfoot><tr class="b"><td>Jami harakat</td>
					<td class="r"><span class="num" style="color:var(--good)">${this.fmt(d.total_kirim)}</span></td>
					<td class="r"><span class="num" style="color:var(--warn-ink)">${this.fmt(d.total_chiqim)}</span></td></tr></tfoot>
			</table></div>`, "mb");
	}

	renderDdsTable(d) {
		const tx = d.transactions || [];
		if (!tx.length) return this.card(`<div class="empty-hint" style="padding:22px 8px">Tanlangan filtr bo'yicha harakat topilmadi.</div>`, "mb");
		const body = tx.map((x) => `<tr>
			<td>${this.dmy(x.date)}</td>
			<td class="ell" data-tt="${this.esc(x.account)}">${this.esc(x.account)}</td>
			<td class="ell" data-tt="${this.esc(x.description)}">${this.esc(x.description)}</td>
			<td class="r num" style="color:var(--good)">${x.kirim ? this.fmt(x.kirim) : ""}</td>
			<td class="r num" style="color:var(--warn-ink)">${x.chiqim ? this.fmt(x.chiqim) : ""}</td>
			<td class="ell" data-tt="${this.esc(x.remarks)}">${this.esc(x.remarks)}</td>
			<td class="ell" data-tt="${this.esc(x.voucher_no)}">${this.esc(x.voucher_no)}</td>
		</tr>`).join("");
		return this.card(`
			<div class="hd"><div><h3>Harakatlar</h3><div class="meta">${d.tx_count} ta yozuv${d.tx_count > 800 ? " · eng yangi 800 tasi" : ""}</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>Kassa</th><th>Kategoriya / kontragent</th><th class="r">Kirim</th><th class="r">Chiqim</th><th>Izoh</th><th>Hujjat</th></tr></thead>
				<tbody>${body}</tbody>
			</table></div>`, "mb");
	}

	// ================= TAB: Tuition =================
	renderTuition() {
		const t = this.data.tuition;
		const p = (t && t.payments) || { by_currency: [], students: [], recent: [], total_count: 0, total_students: 0 };
		const main = (p.by_currency || [])[0] || null;   // eng katta valyuta buketi (asosan so'm)
		const td = this.tuitionDetail;
		let h = this.sec("O'quvchilar to'lovi", `To'lovlar (Payment Entry) asosida · kassaga tushgan real pul · ${this.esc(this.data.meta.period.label)} · kartani bosing — batafsil pastda ochiladi`);

		// ---- To'lov KPI'lari — har biri BOSILADIGAN, batafsili pastda ochiladi ----
		const kcls = (k) => "clickable" + (td === k ? " active" : "");
		h += `<div class="grid cols-5 mb">
			${this.kpi({ label: "Faol o'quvchilar", value: this.fmt(t.active), pin: "var(--c2)", noBadge: true, sub: "bosing: sinflar kesimida ro'yxat", cls: kcls("active"), click: `data-td="active"` })}
			${this.kpi({ label: "Shartnoma qilinganlar", value: this.fmt(t.contracted), pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true, sub: `faol ichida${t.active ? ` · ${Math.round((t.contracted || 0) / t.active * 100)}%` : ""} · bosing: ro'yxati`, cls: kcls("contracted"), click: `data-td="contracted"` })}
			${this.kpi({ label: "Davr to'lovlari", value: this.fmt(p.total_count), pin: "var(--brand)", valColor: "var(--brand-ink)", noBadge: true, sub: "ta to'lov · bosing: har biri kimdan-qachon", cls: kcls("payments"), click: `data-td="payments"` })}
			${this.kpi({ label: "To'lagan o'quvchilar", value: this.fmt(p.total_students), pin: "var(--c1)", noBadge: true, sub: "shu davrda · bosing: kim qancha to'lagan", cls: kcls("payers"), click: `data-td="payers"` })}
			${this.kpi({ label: "Davr yig'imi", value: (main ? this.mAmt(main.total, main.currency) : "0"), unit: main ? " " + this.esc(main.currency) : "", pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true, sub: "kassaga tushgan · bosing: to'lovlar ro'yxati", cls: kcls("payments"), click: `data-td="payments"` })}
		</div>`;

		// ---- Valyuta kesimi ----
		// Odatda: hamma o'quvchilar, chiplar BOSILADIGAN (shu valyutadagi to'lovlar ro'yxati ochiladi).
		// "Shartnoma qilinganlar" kartasi bosilganda: faqat shartnoma qilingan o'quvchilardan
		// tushgan pul (ma'lumot uchun, bosilmaydi — to'lovlar ro'yxati hammani ko'rsatadi).
		const onlyContr = td === "contracted";
		const ccyList = onlyContr ? (p.by_currency_contracted || []) : (p.by_currency || []);
		const ccyChips = ccyList.length
			? ccyList.map((b) => onlyContr
				? `<span class="ccy-chip"><b>${this.esc(b.currency)}</b> <b style="color:var(--good-ink)">${this.mAmt(b.total, b.currency)}</b> <span style="color:var(--muted);font-size:12px">· ${b.count} to'lov · ${b.students} o'quvchi</span></span>`
				: `<span class="ccy-chip tz-tccy${td === "payments" && this.tuitionCcy === b.currency ? " active" : ""}" data-tccy="${this.esc(b.currency)}"><b>${this.esc(b.currency)}</b> <b style="color:var(--good-ink)">${this.mAmt(b.total, b.currency)}</b> <span style="color:var(--muted);font-size:12px">· ${b.count} to'lov · ${b.students} o'quvchi · bosing ▾</span></span>`).join("")
			: `<span class="empty-hint">${onlyContr ? "Davrda shartnoma qilingan o'quvchilardan to'lov yo'q." : "Davrda to'lov yo'q."}</span>`;
		h += this.card(`<div class="hd"><div><h3>Davr yig'imi — valyuta kesimida${onlyContr ? ` <span style="color:var(--good-ink)">· faqat shartnoma qilinganlar</span>` : ""}</h3><div class="meta">${onlyContr
				? "shartnoma qilingan faol o'quvchilardan kassaga tushgan real pul, konvertatsiyasiz · hammasini ko'rish uchun kartani qayta bosing"
				: "kassaga tushgan real pul, konvertatsiyasiz · valyutani bosing — bu pul qanday yig'ilgani (to'lovma-to'lov) ochiladi"}</div></div></div>
			<div style="display:flex;flex-wrap:wrap;gap:10px;padding:2px">${ccyChips}</div>`, "mb");

		// ---- Batafsil panel — tanlangan kartaga qarab ----
		h += `<div class="tz-tuition-detail">${this.tuitionDetailPanel(t, p)}</div>`;
		return h + this.note();
	}

	// O'quvchilar to'lovi — karta bosilganda ochiladigan batafsil panel
	tuitionDetailPanel(t, p) {
		const k = this.tuitionDetail;
		if (!k) return "";
		if (k === "active" || k === "contracted") {
			// sinflar kesimidagi yig'ma-ochilma ro'yxat (Umumiy tabdagi bilan bir xil mexanizm)
			setTimeout(() => { this.ovStudMode = (k === "contracted") ? "contracted" : "all"; this.loadOvStudents(); }, 0);
			const title = k === "contracted" ? "Shartnoma qilingan o'quvchilar — sinflar kesimida" : "Faol o'quvchilar — sinflar kesimida";
			return this.card(`
				<div class="hd tz-tuition-hd"><div><h3>${title}</h3><div class="meta">sinfni bosing — ichidagi o'quvchilar ochiladi · jami to'lagani va oxirgi to'lovi bilan</div></div>
					<div class="tz-tuition-tools"><input type="text" class="tz-ovstud-filter" placeholder="O'quvchi yoki sinf qidirish…" autocomplete="off"></div></div>
				<div class="tz-ovstud-body"><div class="tz-loader">O'quvchilar yuklanyapti…</div></div>`, "mb ov-detail-card");
		}
		if (k === "payments") return this.tuitionPaymentsTable(p);
		if (k === "payers") return this.tuitionPayersTable(p);
		return "";
	}

	// Davr to'lovlari — har biri: kimdan, qachon, qancha, qaysi usulda, hujjat, izoh.
	// tuitionCcy berilsa faqat shu valyutadagi to'lovlar (valyuta chipi bosilganda).
	tuitionPaymentsTable(p) {
		const cf = this.tuitionCcy;
		const list = (p.recent || []).filter((r) => !cf || (r.currency || "") === cf);
		// jami — valyuta kesimida (aralash valyutani bitta raqamga qo'shib bo'lmaydi)
		const totByCcy = {};
		list.forEach((r) => { const c = r.currency || "?"; totByCcy[c] = (totByCcy[c] || 0) + (Number(r.amount) || 0); });
		const totalTxt = Object.keys(totByCcy).sort((a, b) => totByCcy[b] - totByCcy[a])
			.map((c) => `${this.mAmt(totByCcy[c], c)} ${this.esc(c)}`).join(" · ") || "0";
		const students = new Set(list.map((r) => r.student)).size;
		const rows = list.length ? list.map((r) => `
			<tr data-sname="${this.esc(String(r.student || "").toLowerCase())}">
				<td class="num" style="white-space:nowrap">${this.dmy(r.date)}</td>
				<td class="ell" data-tt="${this.esc(r.student)}">${this.esc(r.student)}</td>
				<td class="r num" style="color:var(--good-ink);font-weight:700">${this.mAmt(r.amount, r.currency)} ${this.esc(r.currency)}${r.orig_currency && r.orig_currency !== r.currency ? `<div style="font-size:11px;color:var(--muted);font-weight:400">o'quvchi to'ladi: ${this.mAmt(r.orig_amount, r.orig_currency)} ${this.esc(r.orig_currency)}</div>` : ""}</td>
				<td class="ell">${this.esc(r.mode || "—")}</td>
				<td style="white-space:nowrap">
					${r.name ? `<a class="tz-kassa-link" href="/app/payment-entry/${encodeURIComponent(r.name)}" target="_blank" rel="noopener" title="Payment Entry">${this.esc(r.name)}</a>` : "—"}
					${r.ref ? `<div><a class="tz-kassa-link" href="/app/kassa/${encodeURIComponent(r.ref)}" target="_blank" rel="noopener" title="Kassa">${this.esc(r.ref)}</a></div>` : ""}
				</td>
				<td style="max-width:340px;white-space:normal;color:var(--muted);font-size:12px" data-tt="${this.esc(r.remarks)}">${r.remarks ? this.esc(r.remarks).replace(/\n/g, " · ") : `<span class="muted-s">—</span>`}</td>
			</tr>`).join("")
			: `<tr><td colspan="6" class="empty-hint">Bu davrda${cf ? ` ${this.esc(cf)} da` : ""} to'lov topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd tz-tuition-hd"><div><h3>Davr to'lovlari — har biri${cf ? ` · faqat ${this.esc(cf)}` : ""}</h3>
				<div class="meta">kimdan · qachon · qancha · usul · hujjat · izoh — eng yangisi tepada · ${this.esc(this.data.meta.period.label)}</div></div>
				<div class="tz-tuition-tools">
					<div class="focus-total num">Jami: ${totalTxt} · ${list.length} to'lov · ${students} o'quvchi</div>
					<input type="text" class="tz-stud-filter" placeholder="O'quvchi qidirish…" autocomplete="off">
				</div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>Kimdan (o'quvchi)</th><th class="r">Summa</th><th>Usul</th><th>Hujjat</th><th>Izoh</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count"><span class="tz-stud-count">${list.length}</span> ta to'lov ko'rsatildi${(p.recent || []).length >= 400 ? " (eng yangi 400 tasi)" : ""}.</div>`, "mb ov-detail-card");
	}

	// To'lagan o'quvchilar — kim qancha to'lagan, necha marta, oxirgi to'lov qachon
	tuitionPayersTable(p) {
		const list = p.students || [];
		const rows = list.length ? list.map((s, i) => `
			<tr data-sname="${this.esc(String(s.name || "").toLowerCase())}">
				<td class="r num" style="color:var(--muted)">${i + 1}</td>
				<td class="ell" data-tt="${this.esc(s.name)}">${this.esc(s.name)}</td>
				<td class="r num">${s.count} marta</td>
				<td class="r num" style="color:var(--good-ink);font-weight:700">${this.mAmt(s.total, s.currency)} ${this.esc(s.currency)}</td>
				<td class="r num" style="white-space:nowrap">${s.last_date ? this.dmy(s.last_date) : "—"}</td>
			</tr>`).join("")
			: `<tr><td colspan="5" class="empty-hint">Bu davrda to'lov qilgan o'quvchi yo'q.</td></tr>`;
		return this.card(`
			<div class="hd tz-tuition-hd"><div><h3>To'lagan o'quvchilar — kim qancha</h3>
				<div class="meta">ko'pdan kamga · ${this.esc(this.data.meta.period.label)} davri ichida</div></div>
				<div class="tz-tuition-tools">
					<div class="focus-total num">${list.length} ta o'quvchi</div>
					<input type="text" class="tz-stud-filter" placeholder="O'quvchi qidirish…" autocomplete="off">
				</div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th class="r">#</th><th>O'quvchi</th><th class="r">Necha marta</th><th class="r">Jami to'lagan</th><th class="r">Oxirgi to'lov</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count"><span class="tz-stud-count">${list.length}</span> ta o'quvchi ko'rsatildi.</div>`, "mb ov-detail-card");
	}

	// ================= TAB: P&L =================
	// ================= TAB: Personal (kontragentlar kesimi) =================
	renderPersonal() {
		let h = this.sec("Personal", `${this.data.meta.period.label} · xodimlar, o'quvchilar va ta'minotchilar bir jadvalda`);
		h += this.card(`
			<div class="hd"><div><h3>Kontragentlar kesimida</h3>
				<div class="meta">Oklad — buxgalter oylik vedomostidan (Excel) · nachisleniya, to'langan va qarzdorlik — buxgalteriya provodkalaridan · davr: ${this.esc(this.data.meta.period.label)}</div></div>
				<div class="kt-filter tz-pers-filter-box">${this.personalFilterHtml()}</div></div>
			<div class="tz-pers-body"><div class="tz-loader">Yuklanyapti…</div></div>`, "mb");
		setTimeout(() => { if (this.personal) this.paintPersonal(); else this.loadPersonal(); }, 0);
		return h + this.note();
	}

	personalFilterHtml() {
		const cats = ((this.personal || {}).cats || [])
			.map((c) => ({ value: c.label, label: `${c.label} (${c.count})` }));
		return this.mselHtml("perscat", "Kategoriya", cats, this.personalCats);
	}

	paintPersonalFilter() {
		const box = this.page.main.find(".tz-pers-filter-box");
		if (box.length) box.html(this.personalFilterHtml());
	}

	loadPersonal() {
		const body = this.page.main.find(".tz-pers-body");
		if (!body.length) return;
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_personal",
			args: { from_date: this.state.from_date, to_date: this.state.to_date },
		}).then((r) => { this.personal = r.message || null; this.paintPersonal(); })
			.catch(() => body.html(`<div class="empty-hint">Personal ma'lumotini yuklab bo'lmadi.</div>`));
	}

	paintPersonal(keepFocus) {
		const body = this.page.main.find(".tz-pers-body");
		if (!body.length) return;
		body.html(this.personalTable());
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
		this.paintPersonalFilter();
		if (keepFocus) {
			const inp = body.find(".tz-pers-search")[0];
			if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
		}
	}

	personalTable() {
		const d = this.personal;
		if (!d) return `<div class="empty-hint">Ma'lumot yo'q.</div>`;
		const q = this.personalQ || "";
		// qarzdorlik: musbat — qarz (qizil), manfiy — avans/ortiqcha to'lov (yashil)
		const debtCell = (v, cur) => {
			if (Math.abs(v) < 0.5) return `<span class="muted-s">—</span>`;
			const pos = v > 0;
			return `<span class="num" style="color:${pos ? "var(--bad-ink)" : "var(--good-ink)"};font-weight:700;white-space:nowrap"
				data-tt="${pos ? "Qarzdorlik" : "Avans (ortiqcha to'langan)"}: ${this.fmt(Math.abs(v))} ${this.esc(cur)}">${this.mAmt(v, cur)} <small>${this.ccyLabel(cur)}</small></span>`;
		};
		const amt = (v, cur, color) => (Math.abs(v) > 0.5
			? `<span class="num" style="${color ? `color:${color};` : ""}white-space:nowrap">${this.mAmt(v, cur)} <small>${this.ccyLabel(cur)}</small></span>`
			: `<span class="muted-s">—</span>`);

		let rows = "", shown = 0;
		const ftot = {};
		(d.rows || []).forEach((r) => {
			if (this.personalCats.length && this.personalCats.indexOf(r.category) === -1) return;
			if (q && String(r.name || "").toLowerCase().indexOf(q) === -1) return;
			shown++;
			const t = ftot[r.currency] || (ftot[r.currency] = { nach: 0, paid: 0, debt: 0 });
			t.nach += r.nach; t.paid += r.paid; t.debt += r.debt;
			rows += `<tr>
				<td class="ell" data-tt="${this.esc(r.name)}">${this.esc(r.name)}</td>
				<td class="ell">${this.esc(r.category)}<div class="muted-s">${this.esc(r.pt_label)}</div></td>
				<td class="r">${amt(r.oklad, r.currency)}${r.rejim ? `<div class="muted-s">${this.fmt(r.kun)}/${this.fmt(r.rejim)} kun</div>` : ""}</td>
				<td class="r">${amt(r.nach, r.currency)}</td>
				<td class="r">${amt(r.paid, r.currency, "var(--good-ink)")}</td>
				<td class="r">${debtCell(r.debt, r.currency)}</td>
			</tr>`;
		});
		if (!rows) rows = `<tr><td colspan="6" class="empty-hint">${q || this.personalCats.length ? "Filtrga mos kontragent topilmadi." : "Kontragent topilmadi."}</td></tr>`;
		const tot = Object.keys(ftot).map((c) => `<div class="ov-total num" data-tt="${this.esc(c)}">
			<span style="font-size:12px;color:var(--muted)">${this.ccyLabel(c)}</span>
			nach: <b>${this.mAmt(ftot[c].nach, c)}</b> · to'landi: <b style="color:var(--good-ink)">${this.mAmt(ftot[c].paid, c)}</b>
			· qarz: <b style="color:${ftot[c].debt > 0 ? "var(--bad-ink)" : "var(--good-ink)"}">${this.mAmt(ftot[c].debt, c)}</b></div>`).join("");
		return `<div class="ov-totals">${tot}<div class="muted-s">${this.fmt(shown)} ta kontragent</div></div>
			<input type="text" class="tz-ovstud-filter tz-pers-search" placeholder="Ism bo'yicha qidirish…" value="${this.esc(q)}">
			<div class="tbl-wrap"><table>
				<thead><tr><th>F.I.Sh</th><th>Kategoriyasi</th><th class="r">Oylik okladi</th><th class="r">Nachisleniya summasi</th><th class="r">Oyda to'langan</th><th class="r">Qarzdorlik</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count">${d.truncated ? `Eng katta qarzdorlikdagi ${this.fmt((d.rows || []).length)} tasi ko'rsatildi (${this.fmt(d.truncated)} ta sig'madi).` : ""}</div>`;
	}

	renderPnl() {
		const p = this.data.pnl, ccy = this.ccyLabel(this.data.meta.currency), cur = p.current;
		let h = this.sec("Foyda va zarar (P&L)", `${this.data.meta.period.label} · accrual (hisoblangan)`);
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Daromad", raw: cur.income, cmp: p.income_cmp, cmpYoy: p.income_yoy, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.moneyKpi({ label: "Xarajat", raw: cur.expense, cmp: p.expense_cmp, cmpYoy: p.expense_yoy, invert: true, pin: "var(--bad)", valColor: "var(--bad-ink)" })}
			${this.moneyKpi({ label: "Sof foyda", raw: cur.net, cmp: p.net_cmp, cmpYoy: p.net_yoy, pin: "var(--brand)", valColor: cur.net < 0 ? "var(--bad-ink)" : "var(--good-ink)" })}
			${this.kpi({ label: "Rentabellik (margin)", value: cur.margin != null ? cur.margin : "—", unit: cur.margin != null ? "%" : "", pin: "var(--c5)", noBadge: true, sub: "Sof foyda / daromad" })}
		</div>`;

		const pv = p.prev, yy = p.yoy;
		const line = (lbl, a, b, c, bold) => `<tr class="${bold ? "b" : ""}"><td>${lbl}</td><td class="r num">${this.fmt(a)}</td><td class="r num">${this.fmt(b)}</td><td class="r num">${this.fmt(c)}</td></tr>`;
		h += this.card(`
			<div class="hd"><div><h3>Foyda hisoboti — taqqoslash</h3><div class="meta">${ccy}</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Ko'rsatkich</th><th class="r">Joriy davr</th><th class="r">Oldingi davr</th><th class="r">O'tgan yil</th></tr></thead>
				<tbody>
					${line("Daromad", cur.income, pv.income, yy.income)}
					${line("(−) Xarajat", cur.expense, pv.expense, yy.expense)}
					${line("= Sof foyda", cur.net, pv.net, yy.net, true)}
					<tr class="b"><td>Rentabellik</td><td class="r num">${cur.margin != null ? cur.margin + "%" : "—"}</td><td class="r num">${pv.margin != null ? pv.margin + "%" : "—"}</td><td class="r num">${yy.margin != null ? yy.margin + "%" : "—"}</td></tr>
				</tbody>
			</table></div>`, "mb");

		const eb = p.expense_breakdown || [];
		const colors = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--muted)"];
		const ebTot = eb.reduce((a, b) => a + b.amount, 0);
		const ebDonut = eb.length ? `<div class="donut-wrap">${this.donutSvg(eb, colors, this.m1(ebTot), "mln")}
			<div class="legend" style="flex-direction:column;gap:9px">${eb.map((it, i) => `<div class="it"><span class="sw" style="background:${colors[i % colors.length]}"></span> <span class="ell" style="max-width:120px">${this.esc(it.label)}</span> <b>${it.pct}%</b></div>`).join("")}</div></div>`
			: `<div class="empty-hint">Xarajat taqsimoti ma'lumoti yo'q.</div>`;
		h += `<div class="grid cols-2 mb">
			${this.card(`<div class="hd"><div><h3>Xarajat taqsimoti</h3><div class="meta">${this.data.meta.period.label}</div></div></div>${ebDonut}`)}
			${this.card(`<div class="hd"><div><h3>Sof foyda — 12 oy</h3><div class="meta">mln ${ccy} · yashil foyda, qizil zarar</div></div></div>${this.barChart(p.monthly.months, p.monthly.net, { color: "var(--good)" })}`)}
		</div>`;
		return h + this.note();
	}

	// ================= TAB: Balans (Balance Sheet) =================
	// ================= Nachisleniya tab =================
	renderNach() {
		let h = this.sec("Nachisleniyalar",
			`${this.data.meta.period.label} · kassaga tegmagan hisoblash yozuvlari — kirim (debet) va chiqim (kredit) nachisleniyalari bitta oynada`);
		h += this.card(`
			<div class="hd"><div><h3>Kirim / chiqim nachisleniyasi</h3>
				<div class="meta">Kirim — kontragent bizga qarz bo'ldi (o'quvchi, arenda, elektr stansiya...); chiqim — biz qarz bo'ldik (oylik, arenda, xarajatlar). To'lovlar bu yerga kirmaydi.</div></div>
				<div class="tz-nach-tools">
					<div class="kt-filter tz-nach-filter-box">${this.nachFilterHtml()}</div>
					<div class="tz-seg">
						<button class="tz-seg-opt${this.nachSide === "debit" ? " on" : ""}" data-nach-side="debit">Kirim (Debet)</button>
						<button class="tz-seg-opt${this.nachSide === "credit" ? " on" : ""}" data-nach-side="credit">Chiqim (Kredit)</button>
					</div>
				</div></div>
			<div class="tz-nach-body"><div class="tz-loader">Nachisleniyalar yuklanyapti…</div></div>`, "mb");
		setTimeout(() => { if (this.nach) this.paintNach(); else this.loadNach(); }, 0);
		return h + this.note();
	}

	loadNach() {
		const body = this.page.main.find(".tz-nach-body");
		if (!body.length) return;
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_nachisleniya",
			args: { from_date: this.state.from_date, to_date: this.state.to_date },
		}).then((r) => { this.nach = r.message || null; this.paintNach(); })
			.catch(() => body.html(`<div class="empty-hint">Nachisleniyalarni yuklab bo'lmadi.</div>`));
	}

	paintNach(keepFocus) {
		const body = this.page.main.find(".tz-nach-body");
		if (!body.length) return;
		// segment tugmasining holatini ham yangilaymiz (butun tabni qayta chizmasdan)
		this.page.main.find("[data-nach-side]").each((i, el) => {
			$(el).toggleClass("on", String($(el).attr("data-nach-side")) === this.nachSide);
		});
		body.html(this.renderNachSide());
		this.paintNachFilter();
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
		if (keepFocus) {
			const inp = body.find(".tz-nach-filter")[0];
			if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
		}
	}

	renderNachSide() {
		const d = this.nach;
		if (!d) return `<div class="empty-hint">Nachisleniya ma'lumoti yo'q.</div>`;
		const side = (this.nachSide === "credit" ? d.credit : d.debit) || {};
		const isDeb = this.nachSide !== "credit";
		const ink = isDeb ? "var(--good-ink)" : "var(--bad-ink)";
		// hech narsa yo'q — do'stona bo'sh holat (operatorlar endi kiritishadi)
		if (!(side.rows || []).length && !side.count) {
			return `<div class="empty-hint" style="padding:26px 10px">
				${isDeb
					? `Bu davrda <b>kirim nachisleniyasi</b> yo'q. Operatorlar Journal Entry orqali kiritganda (Дт — o'quvchi/arendator qarz hisobi, Кт — daromad hisobi) shu yerda avtomatik ko'rinadi.`
					: `Bu davrda <b>chiqim nachisleniyasi</b> yo'q. Operatorlar Journal Entry orqali kiritganda (Дт — xarajat hisobi, Кт — kontragent qarz hisobi) shu yerda avtomatik ko'rinadi.`}
			</div>`;
		}
		// jami (valyuta kesimida)
		const totals = `<div class="ov-totals">${(side.total_by_ccy || []).map((t) =>
			`<div class="ov-total num" style="color:${ink}" data-tt="${this.fmt(t.total)} ${this.esc(t.currency)}">${this.mAmt(t.total, t.currency)} <span class="cur">${this.ccyLabel(t.currency)}</span></div>`).join("")}
			<div class="muted-s">${this.fmt(side.count || 0)} ta nachisleniya · ${isDeb ? "kirim (bizga qarz yozildi)" : "chiqim (biz qarz bo'ldik)"}</div></div>`;
		// toifa chiplari (qarshi hisob — "nima uchun")
		const cats = (side.cats || []).map((c) => `
			<button class="tz-acc-chip${this.nachCats.indexOf(c.label) !== -1 ? " active" : ""}" data-nach-cat="${this.esc(c.label)}">
				<span class="t" data-tt="${this.esc(c.label)}">${this.esc(c.label)}</span>
				<b class="num" style="color:${ink}">${(c.by_ccy || []).map((x) => `${this.kc(x.total)} <small>${this.ccyLabel(x.currency)}</small>`).join(" · ")}</b>
				<span class="muted-s">${c.count} ta</span>
			</button>`).join("");
		// valyuta chiplari (2+ valyuta bo'lsa)
		const ccys = (side.total_by_ccy || []).length > 1
			? `<div class="ov-chips">${side.total_by_ccy.map((t) =>
				`<span class="ccy-chip tz-nachc${this.nachCcy === t.currency ? " active" : ""}" data-nach-ccy="${this.esc(t.currency)}"><b class="num">${this.mAmt(t.total, t.currency)}</b> <span class="muted-s">${this.ccyLabel(t.currency)}</span></span>`).join("")}</div>`
			: "";
		// jadval — toifa/valyuta/qidiruv filtrlari bilan
		const q = this.nachQ || "";
		let rows = "", shown = 0;
		const ftot = {};
		(side.rows || []).forEach((r) => {
			if (this.nachGroups.length && this.nachGroups.indexOf(r.group) === -1) return;
			if (this.nachAccts.length && this.nachAccts.indexOf(r.acct) === -1) return;
			if (this.nachSinfs.length && this.nachSinfs.indexOf(r.sinf) === -1) return;
			if (this.nachPoss.length && this.nachPoss.indexOf(r.pos) === -1) return;
			if (this.nachDkinds.length && this.nachDkinds.indexOf(r.dkind) === -1) return;
			if (this.nachCats.length && this.nachCats.indexOf(r.category) === -1) return;
			if (this.nachCcy && r.currency !== this.nachCcy) return;
			if (q && (String(r.party_name || "") + " " + String(r.remark || "")).toLowerCase().indexOf(q) === -1) return;
			shown++;
			ftot[r.currency] = (ftot[r.currency] || 0) + r.amount;
			const slug = String(r.voucher_type || "").toLowerCase().replace(/ /g, "-");
			rows += `<tr>
				<td class="num" style="white-space:nowrap">${this.dmy(r.date)}</td>
				<td class="ell" data-tt="${this.esc(r.party_name)}">${this.esc(r.party_name)}<div class="muted-s">${this.esc(r.group || r.pt_label)}</div></td>
				<td class="ell" data-tt="${this.esc(r.category)}">${this.esc(r.category)}</td>
				<td class="r num" style="color:${ink};font-weight:650;white-space:nowrap">${this.mAmt(r.amount, r.currency)} <small>${this.ccyLabel(r.currency)}</small></td>
				<td><a href="/app/${slug}/${encodeURIComponent(r.voucher_no)}" target="_blank" class="tz-kassa-link">${this.esc(r.voucher_no)}</a></td>
				<td class="ell" data-tt="${this.esc(r.remark)}">${r.remark ? this.esc(r.remark) : `<span class="muted-s">—</span>`}</td>
			</tr>`;
		});
		if (!rows) rows = `<tr><td colspan="6" class="empty-hint">${q || this.nachAnyFilter() || this.nachCcy ? "Filtrga mos nachisleniya topilmadi." : "Nachisleniya yo'q."}</td></tr>`;
		const ftotTxt = Object.keys(ftot).sort((a, b) => ftot[b] - ftot[a])
			.map((c) => `${this.mAmt(ftot[c], c)} ${this.ccyLabel(c)}`).join(" · ");
		return `${totals}
			<div class="ov-chips">${cats}</div>
			${ccys}
			<input type="text" class="tz-ovstud-filter tz-nach-filter" placeholder="Kontragent yoki izoh bo'yicha qidirish…" value="${this.esc(q)}">
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>Kontragent</th><th>Nima uchun (hisob)</th><th class="r">Summa</th><th>Hujjat</th><th>Izoh</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count"><b>${this.fmt(shown)}</b> ta yozuv ko'rsatilmoqda${ftotTxt ? ` · jami: <b class="num" style="color:${ink}">${ftotTxt}</b>` : ""}.${side.truncated ? ` Eng so'nggi ${this.fmt((side.rows || []).length)} tasi ko'rsatildi (${this.fmt(side.truncated)} ta eskisi sig'madi — davrni toraytiring).` : ""}</div>`;
	}

	renderBalance() {
		const perLabels = { "": "Jami", weekly: "Haftalik", monthly: "Oylik", quarterly: "Choraklik", half: "Yarim yillik", yearly: "Yillik" };
		const perOpts = Object.keys(perLabels).map((k) =>
			`<option value="${k}"${this.bsOpt.per === k ? " selected" : ""}>${perLabels[k]}${k ? "" : " (bitta ustun)"}</option>`).join("");
		const mode = this.bsOpt.acc
			? `${this.dmy(this.state.to_date)} holatiga (boshidan yig'ilgan)`
			: `${this.data.meta.period.label} — faqat davr harakati`;
		let h = this.sec("Balans (Balance Sheet)", `${mode} · ${this.ccyLabel(this.data.meta.currency)} (kompaniya valyutasi)`);
		h += this.card(`
			<div class="hd"><div><h3>Aktiv va passiv</h3><div class="meta">Qatorni bosib ichini oching · kontragent sof qoldig'i bo'yicha: bizga qarz — debitorkada, biz qarz — kreditorkada</div></div>
				<div class="bs-opts">
					<select class="form-control tz-bs-per" title="Davr ustunlari — solishtirish uchun">${perOpts}</select>
					<label class="bs-check"><input type="checkbox" class="tz-bs-acc"${this.bsOpt.acc ? " checked" : ""}> Yig'ilgan qiymat (boshidan)</label>
					<label class="bs-check"><input type="checkbox" class="tz-bs-fb"${this.bsOpt.fb ? " checked" : ""}> Default Finance Book yozuvlari</label>
				</div></div>
			<div class="tz-bs-body"><div class="tz-loader">Balans yuklanyapti…</div></div>`, "mb");
		setTimeout(() => { if (this.bs) this.paintBs(); else this.loadBs(); }, 0);
		return h + this.note();
	}

	// balansni serverdan olish — Balans tabi va Umumiy tabdagi debitorka/kreditorka paneli uchun umumiy
	fetchBs(cb) {
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_balance_sheet",
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				accumulated: this.bsOpt.acc, include_default_fb: this.bsOpt.fb,
				periodicity: this.bsOpt.per || null,
			},
		}).then((r) => { this.bs = r.message || null; cb && cb(); })
			.catch(() => { this.bs = null; cb && cb(true); });
	}

	loadBs() {
		const body = this.page.main.find(".tz-bs-body");
		if (!body.length) return;
		body.html(`<div class="tz-loader">Balans yuklanyapti…</div>`);
		this.fetchBs((err) => {
			if (err) this.page.main.find(".tz-bs-body").html(`<div class="empty-hint">Balansni yuklab bo'lmadi.</div>`);
			else this.paintBs();
		});
	}

	paintBs() {
		const body = this.page.main.find(".tz-bs-body");
		if (!body.length) return;
		if (!this.bs) { body.html(`<div class="empty-hint">Balans ma'lumoti yo'q.</div>`); return; }
		body.html(this.bsTree(this.bs));
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	bsMulti() { return ((this.bs && this.bs.periods) || []).length > 1; }

	bsFmt(n) { // balans uchun: to'liq son, kasr yaxlitlanmaydi (masalan 158 688,13)
		const v = Number(n) || 0;
		const [i, d] = Math.abs(v).toFixed(2).split(".");
		const s = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (d === "00" ? "" : "," + d);
		return (v < 0 ? "−" : "") + s;
	}

	bsCells(amounts, color) {
		return (amounts || []).map((v) => {
			const c = color || (v < 0 ? "var(--bad-ink)" : "var(--ink)");
			return `<span class="bs-amt num" style="color:${c}" data-tt="${this.bsFmt(v)} ${this.esc(this.bs.currency)}">${this.bsFmt(v)}</span>`;
		}).join("");
	}

	bsNode(n, depth) {
		const kids = n.children || [];
		const open = this.bsOpen.has(n.key);
		const ar = kids.length ? `<span class="bs-ar">${open ? "▼" : "▶"}</span>` : `<span class="bs-ar bs-ar-e"></span>`;
		let h = `<div class="bs-row bs-d${Math.min(depth, 4)}${kids.length ? " bs-click" : ""}"${kids.length ? ` data-bs-k="${this.esc(n.key)}"` : ""}>
			<span class="bs-lab" style="padding-left:${depth * 20}px"><span class="ell" data-tt="${this.esc(n.label)}">${ar}${this.esc(n.label)}</span>${n.count ? `<span class="bs-cnt">${n.count} ta</span>` : ""}</span>
			${this.bsCells(n.amounts || [n.amount])}</div>`;
		if (open && kids.length) h += kids.map((c) => this.bsNode(c, depth + 1)).join("");
		return h;
	}

	bsTotal(label, amounts, cls, color) {
		return `<div class="bs-row bs-total ${cls || ""}"><span class="bs-lab">${label}</span>${this.bsCells(amounts, color)}</div>`;
	}

	bsTree(b) {
		const t = b.totals || { assets: [b.total_assets], liabilities: [b.total_liabilities], equity: [b.total_equity], passive: [b.total_passive], check: [b.check] };
		const checkV = t.check || [b.check];
		const ok = checkV.every((x) => Math.abs(x || 0) < 1);
		const multi = this.bsMulti();
		const head = multi
			? `<div class="bs-row bs-head"><span class="bs-lab"></span>${(b.periods || []).map((p) => `<span class="bs-amt" data-tt="${this.esc(p.end)}">${this.esc(p.label)}</span>`).join("")}</div>`
			: "";
		let h = `<div class="bs-side-h">Aktiv</div>${head}`;
		h += (b.assets || []).map((n) => this.bsNode(n, 0)).join("");
		h += this.bsTotal("AKTIV JAMI", t.assets, "bs-grand", "var(--good-ink)");
		h += `<div class="bs-side-h" style="margin-top:22px">Passiv</div>${head}`;
		h += (b.liabilities || []).map((n) => this.bsNode(n, 0)).join("");
		h += this.bsTotal("Jami majburiyatlar", t.liabilities, "", "var(--bad-ink)");
		h += (b.equity || []).map((n) => this.bsNode(n, 0)).join("");
		h += this.bsTotal("Jami kapital", t.equity, "", null);
		h += this.bsTotal("PASSIV JAMI (majburiyat + kapital)", t.passive, "bs-grand", "var(--brand-ink)");
		h += this.bsTotal("BALANS FARQI (Aktiv − Passiv)", checkV, "bs-grand", ok ? "var(--good-ink)" : "var(--bad-ink)");
		h += `<div class="bs-eq${ok ? "" : " bad"}">${ok ? "✓ Balans to'g'ri: Aktiv = Majburiyat + Kapital (har ustunda)" : `⚠️ Balans farqi bor — yozuvlarni tekshiring`}</div>`;
		h += b.truncated ? `<div class="bs-trunc">Ustunlar ko'p bo'lgani uchun faqat oxirgi 13 davr ko'rsatildi (oraliqni qisqartiring).</div>` : "";
		return `<div class="bs-scroll"><div class="bs-wrap${multi ? " bs-multi" : ""}">${h}</div></div>`;
	}

	// ================= footer note =================
	note() {
		const w = (this.data.meta.warnings || []);
		const wh = w.length ? `<b>Diqqat:</b> ${w.map((x) => this.esc(x)).join(" ")} ` : "";
		return `<div class="note">${wh}Barcha raqamlar real vaqtda ERPNext'dan (GL Entry): kassa — Mode of Payment hisoblari; debitorka/kreditorka va kontragent — Receivable/Payable; foyda — Income/Expense; o'quvchi to'lovi — Education Fees; xodim avansi — Employee Advance. Budjet bo'linishi Chart of Accounts guruhiga tayanadi.</div>`;
	}
}
