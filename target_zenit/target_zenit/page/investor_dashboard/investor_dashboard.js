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
		this.bsCat = null;          // Umumiy tabdagi to'liq ro'yxat — toifa kesimida (group_by=category)
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
		this.personalMonths = []; this.personalNach = [];   // "qaysi oy uchun" filtri (bo'sh = davr oylari)
		this.personalNach = [];     // nachisleniya holati: "qilingan" / "qilinmagan"
		this.persMonths = {};       // kontragent oy-kesimi keshi (pt|party -> months)
		this.cfAccTx = null;        // o'sha hisob harakatlari (kesh)
		this.months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
		this.tabs = [
			{ key: "overview", label: "Umumiy" },
			{ key: "cashflow", label: "Kassa va pul oqimi" },
			{ key: "kunlik", label: "Kunlik kassa" },
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
		// Personal — qatorni bosib kontragentning oy kesimini ochish/yopish
		body.on("click", "tr.pers-row", (e) => this.togglePersMonths($(e.currentTarget)));
		// Kassa filtrlari — ko'p tanlovli menyular (hisoblar / operatsiya turi)
		body.on("click", "[data-mselbtn]", (e) => {
			e.stopPropagation();
			const k = String($(e.currentTarget).attr("data-mselbtn"));
			this.mselOpen = (this.mselOpen === k) ? null : k;
			if (k === "acc" || k === "op") this.paintCashFilter();
			else if (k === "perscat" || k === "persmonth" || k === "persnach") this.paintPersonalFilter();
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
		body.on("change", ".tz-bs-per", (e) => { this.bsOpt.per = e.target.value || ""; this.bs = null; this.bsCat = null; this.loadBs(); });
		body.on("change", ".tz-bs-acc", (e) => { this.bsOpt.acc = e.target.checked ? 1 : 0; this.bs = null; this.bsCat = null; this.loadBs(); });
		body.on("change", ".tz-bs-fb", (e) => { this.bsOpt.fb = e.target.checked ? 1 : 0; this.bs = null; this.bsCat = null; this.loadBs(); });
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
		this.bsCat = null;
		this.ovStudents = null;
		this.ovCash = null;
		this.cfAcc = null; this.cfAccTx = null;
		this.personal = null; this.personalCats = []; this.personalQ = "";
		this.personalMonths = []; this.personalNach = [];
		this.persMonths = {};
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
		const fn = { overview: "renderOverview", cashflow: "renderCashflow", kunlik: "renderKunlik", debts: "renderDebts", dds: "renderDds", tuition: "renderTuition", personal: "renderPersonal", balance: "renderBalance", nach: "renderNach" }[this.active];
		body.html(this[fn]());
		if (this.active === "kunlik") this.mountKunlik(body.find(".tz-kunlik-host"));
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	// ============== TAB: Kunlik kassa (mustaqil modul, tzKunlikInit) ==============
	renderKunlik() {
		return `<div class="tz-kunlik-host"></div>`;
	}

	mountKunlik(host) {
		if (!host.length) return;
		if (this.kunlikEl) { host.replaceWith(this.kunlikEl); return; }  // tab almashganda holati saqlanadi
		const el = $("<div></div>");
		host.replaceWith(el);
		tzKunlikInit(el);
		this.kunlikEl = el;
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
					<div class="meta">${asOf} holatiga · ${this.ccyLabel(this.data.meta.currency)} (kompaniya valyutasi) · tepadagi karta bilan bir xil toifalar — qatorni bosib ichini oching: toifa → guruh → kontragent</div></div>
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
		if (!this.bsCat) return null;
		return this.ovDetail === "debitorka"
			? ((this.bsCat.assets || []).find((n) => n.key === "deb") || null)
			: ((this.bsCat.liabilities || []).find((n) => n.key === "cred") || null);
	}

	// Umumiy tab paneli TOIFA kesimida yuklanadi (group_by=category) — tepadagi
	// karta bilan nomma-nom va raqamma-raqam mos bo'lishi uchun; Balans tabi (this.bs)
	// esa hisob kesimida qoladi.
	fetchBsCat(cb) {
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_balance_sheet",
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				accumulated: this.bsOpt.acc, include_default_fb: this.bsOpt.fb,
				periodicity: this.bsOpt.per || null, group_by: "category",
			},
		}).then((r) => { this.bsCat = r.message || null; cb && cb(); })
			.catch(() => { this.bsCat = null; cb && cb(true); });
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
		if (this.bsCat) { paint(); return; }
		body.html(`<div class="tz-loader">Yuklanyapti…</div>`);
		this.fetchBsCat((err) => {
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
			? `<div class="bs-row bs-head"><span class="bs-lab"></span>${(this.bsCat.periods || []).map((p) => `<span class="bs-amt" data-tt="${this.esc(p.end)}">${this.esc(p.label)}</span>`).join("")}</div>`
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
		perscat: "personalCats", persmonth: "personalMonths", persnach: "personalNach" };

	mselList(key) { return this[this.MSEL[key]] || []; }

	mselApply(key) {
		if (key === "acc" || key === "op") { this.paintCashFilter(); this.loadOvCash(true); }
		else if (key === "perscat") { this.paintPersonal(); }
		else if (key === "persmonth" || key === "persnach") { this.loadPersonal(); }
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
		let h = this.sec("Personal", `faqat xodimlar (o'quvchilar — "O'quvchilar to'lovi" bo'limida)`);
		h += this.card(`
			<div class="hd"><div><h3>Xodimlar kesimida</h3>
				<div class="meta">Oylik ish haqi — Oylik tabeldan (har oyga o'z qiymati; qatorda ko'rinayotgan oylarning o'rtachasi) · qatordagi sonlar — oy kesimining JAMI'si (oy tanlanmasa butun tarix, tanlansa o'sha oylar) · to'langan — nachisleniyaga bog'langan to'lovlar (qachon to'langanidan qat'i nazar) · <b>qatorni bossangiz oy kesimi ochiladi</b> (qaysi oyga qancha yozildi / to'landi / qoldi)${(this.personalMonths || []).length ? ` · <b>${this.personalMonths.map((m) => this.esc(this.monthLabel(m))).join(", ")}</b>` : ` · butun tarix`}</div></div>
				<div class="kt-filter tz-pers-filter-box">${this.personalFilterHtml()}</div></div>
			<div class="tz-pers-body"><div class="tz-loader">Yuklanyapti…</div></div>`, "mb");
		setTimeout(() => { if (this.personal) this.paintPersonal(); else this.loadPersonal(); }, 0);
		return h + this.note();
	}

	// "2026-08" -> "2026 Avgust"
	monthLabel(v) {
		const MM = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
			"Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
		const m = /^(\d{4})-(\d{2})$/.exec(String(v || ""));
		return m ? `${m[1]} ${MM[parseInt(m[2], 10) - 1]}` : String(v || "");
	}

	personalFilterHtml() {
		const p = this.personal || {};
		const months = (p.months || [])
			.map((m) => ({ value: m.label, label: `${this.monthLabel(m.label)} (${m.count})` }));
		const cats = (p.cats || [])
			.map((c) => ({ value: c.label, label: `${c.label} (${c.count})` }));
		const nachOpts = [
			{ value: "qilingan", label: "Nachisleniya qilingan" },
			{ value: "qilinmagan", label: "Nachisleniya qilinmagan" },
		];
		return this.mselHtml("persmonth", "Oy", months, this.personalMonths)
			+ this.mselHtml("persnach", "Nachisleniya", nachOpts, this.personalNach)
			+ this.mselHtml("perscat", "Kategoriya", cats, this.personalCats);
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
			args: {
				from_date: this.state.from_date, to_date: this.state.to_date,
				months: JSON.stringify(this.personalMonths || []),
				nach_status: JSON.stringify(this.personalNach || []),
			},
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
		// Qoldiq: musbat — to'lanmay qolgan (qizil). Manfiy bo'lsa nachisleniyadan
		// ORTIQ to'langan — "+" bilan yashil ko'rsatiladi (avans/ortiqcha).
		const debtCell = (v, cur) => {
			if (Math.abs(v) < 0.5) return `<span class="muted-s">—</span>`;
			const over = v < 0;
			const txt = over ? "+" + this.mAmt(Math.abs(v), cur) : this.mAmt(v, cur);
			return `<span class="num" style="color:${over ? "var(--good-ink)" : "var(--bad-ink)"};font-weight:700;white-space:nowrap"
				data-tt="${over ? "Nachisleniyadan ORTIQ to'langan (avans)" : "Nachisleniyadan to'lanmay qolgan"}: ${this.fmt(Math.abs(v))} ${this.esc(cur)}">${txt} <small>${this.ccyLabel(cur)}</small></span>`;
		};
		const amt = (v, cur, color) => (Math.abs(v) > 0.5
			? `<span class="num" style="${color ? `color:${color};` : ""}white-space:nowrap">${this.mAmt(v, cur)} <small>${this.ccyLabel(cur)}</small></span>`
			: `<span class="muted-s">—</span>`);

		// Oylik ish haqi — Oylik tabeldan (SSA): har oyga o'z qiymati, qatorda
		// ko'rinayotgan oylarning o'rtachasi (nechta oy hisobga olingani bilan)
		const oylikCell = (r) => {
			if (r.oylik > 0.5) {
				const sub = r.oylik_n > 1
					? `o'rtacha (${this.fmt(r.oylik_n)} oy)`
					: "oyiga";
				return `${amt(r.oylik, r.currency)}<div class="muted-s" data-tt="Oylik tabelda oy uchun belgilangan ish haqi${r.oylik_n > 1 ? ` — ${this.fmt(r.oylik_n)} oyning o'rtachasi` : ""}">${sub}</div>`;
			}
			return `<span class="muted-s" data-tt="Oylik tabelda bu oylar uchun ish haqi kiritilmagan">kiritilmagan</span>`;
		};
		const paidCell = (r) => {
			if (Math.abs(r.paid) < 0.5) return `<span class="muted-s">—</span>`;
			const pct = r.nach > 0.5 ? Math.max(0, Math.min(100, (r.paid / r.nach) * 100)) : 100;
			return `${amt(r.paid, r.currency, "var(--good-ink)")}
				${r.advance > 0.5 ? `<div class="muted-s" data-tt="Nachisleniyaga bog'lanmagan ortiqcha to'lov">shundan ortiqcha: ${this.fmt(r.advance)}</div>` : ""}
				${r.nach > 0.5 ? `<div class="pers-bar" data-tt="Nachisleniyaning ${Math.round(pct)}% i to'langan"><i style="width:${pct}%${pct >= 99.5 ? ";background:var(--good)" : ""}"></i></div>` : ""}`;
		};
		let rows = "", shown = 0;
		const ftot = {};
		(d.rows || []).forEach((r, pi) => {
			if (this.personalCats.length && this.personalCats.indexOf(r.category) === -1) return;
			if (q && String(r.name || "").toLowerCase().indexOf(q) === -1) return;
			shown++;
			const t = ftot[r.currency] || (ftot[r.currency] = { nach: 0, paid: 0, debt: 0 });
			t.nach += r.nach; t.paid += r.paid; t.debt += r.debt;
			rows += `<tr class="pers-row" data-pi="${pi}">
				<td class="ell" data-tt="${this.esc(r.name)} — oy kesimini ochish uchun bosing"><span class="pers-chev">▸</span>${this.esc(r.name)}</td>
				<td class="ell">${this.esc(r.category)}<div class="muted-s">${this.esc(r.pt_label)}</div></td>
				<td class="r">${oylikCell(r)}</td>
				<td class="r">${r.no_nach ? `<span class="muted-s" data-tt="Bu davrda nachisleniya yozilmagan">nachisleniya yo'q</span>` : amt(r.nach, r.currency)}</td>
				<td class="r">${paidCell(r)}</td>
				<td class="r">${debtCell(r.debt, r.currency)}</td>
			</tr>
			<tr class="pers-detail" style="display:none"><td colspan="6"><div class="pers-months"></div></td></tr>`;
		});
		if (!rows) rows = `<tr><td colspan="6" class="empty-hint">${q || this.personalCats.length ? "Filtrga mos kontragent topilmadi." : "Kontragent topilmadi."}</td></tr>`;
		const tot = Object.keys(ftot).map((c) => `<div class="ov-total num" data-tt="${this.esc(c)}">
			<span style="font-size:12px;color:var(--muted)">${this.ccyLabel(c)}</span>
			nach: <b>${this.mAmt(ftot[c].nach, c)}</b> · to'landi: <b style="color:var(--good-ink)">${this.mAmt(ftot[c].paid, c)}</b>
			· qoldiq: <b style="color:${ftot[c].debt > 0 ? "var(--bad-ink)" : "var(--good-ink)"}">${ftot[c].debt < 0 ? "+" + this.mAmt(Math.abs(ftot[c].debt), c) : this.mAmt(ftot[c].debt, c)}</b></div>`).join("");
		return `<div class="ov-totals">${tot}<div class="muted-s">${this.fmt(shown)} ta kontragent</div></div>
			<input type="text" class="tz-ovstud-filter tz-pers-search" placeholder="Ism bo'yicha qidirish…" value="${this.esc(q)}">
			<div class="tbl-wrap"><table>
				<thead><tr><th>F.I.Sh</th><th>Kategoriyasi</th><th class="r">Oylik ish haqi</th><th class="r">Nachisleniya</th><th class="r">To'langan</th><th class="r">Qoldiq</th></tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
			<div class="kt-count">${d.truncated ? `Eng katta qarzdorlikdagi ${this.fmt((d.rows || []).length)} tasi ko'rsatildi (${this.fmt(d.truncated)} ta sig'madi).` : ""}</div>`;
	}

	// -- Personal: bitta kontragentning oy kesimi (qator ochilganda, lazy) --
	togglePersMonths($tr) {
		const $det = $tr.next("tr.pers-detail");
		if (!$det.length) return;
		if ($det.is(":visible")) { $det.hide(); $tr.removeClass("open"); return; }
		$det.show(); $tr.addClass("open");
		const r = ((this.personal && this.personal.rows) || [])[parseInt($tr.attr("data-pi"), 10)];
		if (r) this.loadPersMonths(r, $det.find(".pers-months"));
	}

	loadPersMonths(r, box) {
		// kesh kalitiga "Oy" filtri ham kiradi — filtr o'zgarsa qayta yuklanadi
		const key = r.party_type + "|" + r.party + "|" + (this.personalMonths || []).join(",");
		if (this.persMonths[key]) { box.html(this.persMonthsHtml(this.persMonths[key])); return; }
		box.html(`<div class="tz-loader">Oy kesimi yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_personal_months",
			args: { party_type: r.party_type, party: r.party,
				months: JSON.stringify(this.personalMonths || []) },
		}).then((res) => {
			this.persMonths[key] = res.message || { months: [] };
			box.html(this.persMonthsHtml(this.persMonths[key]));
			box.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
		}).catch(() => box.html(`<div class="empty-hint">Oy kesimini yuklab bo'lmadi.</div>`));
	}

	persMonthsHtml(d) {
		const ms = d.months || [];
		if (!ms.length) return `<div class="empty-hint">Bu kontragent bo'yicha nachisleniya/to'lov topilmadi.</div>`;
		const pill = (m) => {
			if (m.nach > 0.5 && Math.abs(m.debt) <= 0.5) return `<span class="pers-pill good">To'langan</span>`;
			if (m.nach > 0.5 && m.debt < -0.5) return `<span class="pers-pill good">Ortiq to'langan</span>`;
			if (m.nach > 0.5 && m.paid > 0.5) return `<span class="pers-pill warn">Qisman</span>`;
			if (m.nach > 0.5) return `<span class="pers-pill bad">To'lanmagan</span>`;
			return `<span class="pers-pill good">Avans</span>`;
		};
		const num = (v, cur, color) => (Math.abs(v) > 0.5
			? `<span class="num" style="${color ? `color:${color};` : ""}white-space:nowrap">${this.mAmt(v, cur)}</span>`
			: `<span class="muted-s">—</span>`);
		const rows = ms.map((m) => `<tr>
			<td>${this.esc(this.monthLabel(m.oy))} <small class="muted-s">${this.esc(m.currency)}</small></td>
			<td class="r">${m.oylik > 0.5 ? num(m.oylik, m.currency) : `<span class="muted-s" data-tt="Oylik tabelda bu oy uchun ish haqi kiritilmagan">—</span>`}</td>
			<td class="r">${num(m.nach, m.currency)}</td>
			<td class="r">${num(m.paid, m.currency, "var(--good-ink)")}${m.advance > 0.5 ? `<div class="muted-s" data-tt="Nachisleniyaga bog'lanmagan to'lov (avans)">shundan bog'lanmagan: ${this.fmt(m.advance)}</div>` : ""}</td>
			<td class="r">${m.debt > 0.5 ? num(m.debt, m.currency, "var(--bad-ink)")
				: (m.debt < -0.5 ? `<span class="num" style="color:var(--good-ink);white-space:nowrap">+${this.mAmt(-m.debt, m.currency)}</span>` : `<span class="muted-s">0</span>`)}</td>
			<td>${pill(m)}</td>
		</tr>`).join("");
		const tots = {};
		ms.forEach((m) => {
			const t = tots[m.currency] || (tots[m.currency] = { nach: 0, paid: 0, debt: 0, oySum: 0, oyN: 0 });
			t.nach += m.nach; t.paid += m.paid; t.debt += m.debt;
			if (m.oylik > 0.5) { t.oySum += m.oylik; t.oyN++; }
		});
		const trow = Object.keys(tots).map((c) => `<tr class="b"><td>JAMI <small class="muted-s">${this.esc(c)}</small></td>
			<td class="r num">${tots[c].oyN ? `<span data-tt="Oylik ish haqining ${this.fmt(tots[c].oyN)} oy bo'yicha o'rtachasi">${this.mAmt(tots[c].oySum / tots[c].oyN, c)}<div class="muted-s" style="font-weight:400">o'rtacha</div></span>` : `<span class="muted-s">—</span>`}</td>
			<td class="r num">${this.mAmt(tots[c].nach, c)}</td>
			<td class="r num" style="color:var(--good-ink)">${this.mAmt(tots[c].paid, c)}</td>
			<td class="r num" style="color:${tots[c].debt > 0.5 ? "var(--bad-ink)" : "var(--good-ink)"}">${tots[c].debt < -0.5 ? "+" + this.mAmt(-tots[c].debt, c) : this.mAmt(tots[c].debt, c)}</td>
			<td></td></tr>`).join("");
		return `<table class="pers-mtbl">
			<thead><tr><th>Oy</th><th class="r">Oylik ish haqi</th><th class="r">Nachisleniya</th><th class="r">To'langan</th><th class="r">Qoldiq</th><th>Holat</th></tr></thead>
			<tbody>${rows}${trow}</tbody></table>`;
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
				<td class="r">${r.monthly ? `<span class="num" style="white-space:nowrap" data-tt="Student kartochkasidagi kelishilgan oylik to'lov">${this.fmt(r.monthly)} <small>so'm</small></span>` : `<span class="muted-s">—</span>`}</td>
				<td class="r num" style="color:${ink};font-weight:650;white-space:nowrap">${this.mAmt(r.amount, r.currency)} <small>${this.ccyLabel(r.currency)}</small></td>
				<td><a href="/app/${slug}/${encodeURIComponent(r.voucher_no)}" target="_blank" class="tz-kassa-link">${this.esc(r.voucher_no)}</a></td>
				<td class="ell" data-tt="${this.esc(r.remark)}">${r.remark ? this.esc(r.remark) : `<span class="muted-s">—</span>`}</td>
			</tr>`;
		});
		if (!rows) rows = `<tr><td colspan="7" class="empty-hint">${q || this.nachAnyFilter() || this.nachCcy ? "Filtrga mos nachisleniya topilmadi." : "Nachisleniya yo'q."}</td></tr>`;
		const ftotTxt = Object.keys(ftot).sort((a, b) => ftot[b] - ftot[a])
			.map((c) => `${this.mAmt(ftot[c], c)} ${this.ccyLabel(c)}`).join(" · ");
		return `${totals}
			<div class="ov-chips">${cats}</div>
			${ccys}
			<input type="text" class="tz-ovstud-filter tz-nach-filter" placeholder="Kontragent yoki izoh bo'yicha qidirish…" value="${this.esc(q)}">
			<div class="tbl-wrap"><table>
				<thead><tr><th>Sana</th><th>Kontragent</th><th>Nima uchun (hisob)</th><th class="r">Oylik to'lov</th><th class="r">Summa</th><th>Hujjat</th><th>Izoh</th></tr></thead>
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

	bsMulti() {
		const b = this.active === "overview" ? (this.bsCat || this.bs) : this.bs;
		return ((b && b.periods) || []).length > 1;
	}

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

// (investor dashboardga ulangan — pastdagi tzKunlikInit)
// Dizayn: zamonaviy yorug' fintech-dashboard — ko'k (#2563eb) asosiy aksent,
// kirim yashil / chiqim qizil (jahon konvensiyasi), oq kartalar, yumshoq
// soyalar. Ranglar desk mavzusidan MUSTAQIL (qorong'i mavzuda ham yorug').

// ======================================================================
// KUNLIK KASSA bo'limi — investor dashboard ichida mustaqil modul.
// Berilgan konteynerga o'z UI'sini quradi (o'z filtrlari, o'z yuklanishi).
function tzKunlikInit($host) {

	// ---------------------------------------------------------------- dizayn tokenlari
	const C = {
		bg: "#f4f6fb", card: "#ffffff", line: "#e6eaf2", lineSoft: "#eef1f7",
		ink: "#0f172a", muted: "#64748b", faint: "#94a3b8",
		blue: "#2563eb", blueSoft: "#eff4ff", blueDark: "#1d4ed8",
		good: "#10b981", goodInk: "#047857", goodSoft: "#ecfdf5",
		bad: "#f43f5e", badInk: "#be123c", badSoft: "#fff1f2",
		slate: "#94a3b8", amber: "#f59e0b",
	};

	if (!document.getElementById("kunlik-kassa-css")) {
		const css = `
		.tz-kk { background:${C.bg}; border-radius:18px; padding:20px 22px 34px; margin-top:8px;
			color:${C.ink}; font-size:13px; -webkit-font-smoothing:antialiased; }
		.tz-kk * { box-sizing:border-box; }
		.tz-kk .num { font-variant-numeric:tabular-nums; }

		/* ---- sarlavha ---- */
		.tz-kk .kk-head { display:flex; align-items:center; gap:14px; margin-bottom:16px; flex-wrap:wrap; }
		.tz-kk .kk-title { font-size:20px; font-weight:800; letter-spacing:-.3px; color:${C.ink}; }
		.tz-kk .kk-title small { display:block; font-size:12px; font-weight:500; color:${C.muted}; margin-top:1px; }
		.tz-kk .kk-head-right { margin-left:auto; display:flex; align-items:center; gap:10px; }
		.tz-kk .kk-asof { font-size:11.5px; color:${C.faint}; }
		.tz-kk .kk-refresh { border:1px solid ${C.line}; background:${C.card}; color:${C.blue};
			border-radius:10px; padding:6px 14px; font-size:12.5px; font-weight:600; cursor:pointer; }
		.tz-kk .kk-refresh:hover { background:${C.blueSoft}; border-color:${C.blue}; }

		/* ---- filtr paneli ---- */
		.tz-kk .kk-filters { background:${C.card}; border:1px solid ${C.line}; border-radius:14px;
			padding:12px 14px; margin-bottom:16px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
			box-shadow:0 1px 2px rgba(16,24,40,.04); }
		.tz-kk .kk-seg { display:inline-flex; background:${C.bg}; border-radius:10px; padding:3px; gap:2px; }
		.tz-kk .kk-seg button { border:0; background:transparent; color:${C.muted}; border-radius:8px;
			padding:5px 13px; font-size:12.5px; font-weight:600; cursor:pointer; white-space:nowrap; }
		.tz-kk .kk-seg button:hover { color:${C.ink}; }
		.tz-kk .kk-seg button.active { background:${C.card}; color:${C.blue}; box-shadow:0 1px 3px rgba(16,24,40,.12); }
		.tz-kk input.kk-date { border:1px solid ${C.line}; border-radius:10px; padding:5px 10px;
			background:${C.card}; color:${C.ink}; width:128px; font-size:12.5px; }
		.tz-kk input.kk-date:focus { outline:2px solid ${C.blueSoft}; border-color:${C.blue}; }
		.tz-kk select.kk-sel { border:1px solid ${C.line}; border-radius:10px; padding:5px 10px;
			background:${C.card}; color:${C.ink}; font-size:12.5px; max-width:210px; cursor:pointer; }
		.tz-kk select.kk-sel.on { border-color:${C.blue}; background:${C.blueSoft}; color:${C.blueDark}; font-weight:600; }
		.tz-kk .kk-accs { display:flex; gap:7px; flex-wrap:wrap; }
		.tz-kk .kk-acc { border:1px solid ${C.line}; background:${C.card}; color:${C.muted}; border-radius:10px;
			padding:4px 11px; font-size:12px; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:7px; }
		.tz-kk .kk-acc .bal { font-weight:500; color:${C.faint}; font-size:11px; }
		.tz-kk .kk-acc:hover { border-color:${C.blue}; color:${C.blue}; }
		.tz-kk .kk-acc.active { background:${C.blueSoft}; border-color:${C.blue}; color:${C.blueDark}; }
		.tz-kk .kk-acc.active .bal { color:${C.blue}; }

		/* ---- KPI ---- */
		.tz-kk .kk-kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(188px, 1fr)); gap:12px; margin-bottom:16px; }
		.tz-kk .kk-kpi { background:${C.card}; border:1px solid ${C.line}; border-radius:14px; padding:14px 16px;
			box-shadow:0 1px 2px rgba(16,24,40,.04); min-height:92px; transition:border-color .12s, box-shadow .12s; }
		.tz-kk .kk-kpi.click { cursor:pointer; }
		.tz-kk .kk-kpi.click:hover { border-color:${C.blue}; box-shadow:0 2px 8px rgba(37,99,235,.10); }
		.tz-kk .kk-kpi.active { border-color:${C.blue}; box-shadow:0 0 0 2px ${C.blueSoft}, 0 2px 8px rgba(37,99,235,.12); background:linear-gradient(180deg, ${C.blueSoft}55, ${C.card}); }
		.tz-kk .kk-kpi .hint { float:right; font-size:10px; color:${C.faint}; font-weight:600; }
		.tz-kk .kk-kpi.active .hint { color:${C.blue}; }
		.tz-kk .kk-kpi .lab { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; color:${C.faint}; margin-bottom:6px; }
		.tz-kk .kk-kpi .val { font-size:21px; font-weight:800; letter-spacing:-.4px; line-height:1.1; white-space:nowrap; }
		.tz-kk .kk-kpi .val small { font-size:11.5px; font-weight:600; color:${C.faint}; margin-left:2px; }
		.tz-kk .kk-kpi .foot { display:flex; align-items:center; gap:8px; margin-top:8px; min-height:24px; }
		.tz-kk .kk-kpi .sub { font-size:11.5px; color:${C.muted}; }
		.tz-kk .kk-delta { font-size:11px; font-weight:700; border-radius:999px; padding:2px 8px; white-space:nowrap; }
		.tz-kk .kk-delta.up { background:${C.goodSoft}; color:${C.goodInk}; }
		.tz-kk .kk-delta.dn { background:${C.badSoft}; color:${C.badInk}; }
		.tz-kk .kk-delta.flat { background:${C.bg}; color:${C.muted}; }
		.tz-kk .kk-spark { margin-left:auto; flex:none; }

		/* ---- kartalar ---- */
		.tz-kk .kk-card { background:${C.card}; border:1px solid ${C.line}; border-radius:14px;
			padding:12px 14px; margin-bottom:12px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
		.tz-kk .kk-card-hd { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:8px; }
		.tz-kk .kk-card-hd h3 { font-size:13px; font-weight:800; letter-spacing:-.2px; margin:0; color:${C.ink}; }
		.tz-kk .kk-card-hd .meta { font-size:11.5px; color:${C.muted}; }
		.tz-kk .kk-card-hd .right { margin-left:auto; }
		.tz-kk .kk-grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
		@media (max-width: 980px) { .tz-kk .kk-grid2 { grid-template-columns:1fr; } }

		.tz-kk .kk-legend { display:flex; gap:16px; flex-wrap:wrap; font-size:11.5px; color:${C.muted}; align-items:center; }
		.tz-kk .kk-legend b { color:${C.ink}; font-weight:600; }
		.tz-kk .kk-legend .sw { width:10px; height:10px; border-radius:3px; display:inline-block; margin-right:6px; vertical-align:-1px; }
		.tz-kk .kk-legend .ln { width:18px; height:0; border-top:2.5px solid ${C.blue}; display:inline-block; margin-right:6px; vertical-align:3px; border-radius:2px; }

		.tz-kk svg { display:block; }
		.tz-kk svg text { font-family:inherit; }
		.tz-kk .kk-day-hit { cursor:pointer; }
		.tz-kk .kk-day-hit:hover rect.hover-bg { fill:${C.blue}; fill-opacity:.07; }

		/* ---- zamonaviy diagramma effektlari ---- */
		@keyframes kkGrowUp { from { transform:scaleY(0); } to { transform:scaleY(1); } }
		@keyframes kkPulse { 0% { opacity:.55; transform:scale(1); } 70% { opacity:0; transform:scale(2.6); } 100% { opacity:0; transform:scale(2.6); } }
		.tz-kk .kk-grow { transform-box:fill-box; transform-origin:center bottom; animation:kkGrowUp .45s cubic-bezier(.22,.9,.35,1) backwards; }
		.tz-kk .kk-growd { transform-box:fill-box; transform-origin:center top; animation:kkGrowUp .45s cubic-bezier(.22,.9,.35,1) backwards; }
		.tz-kk .kk-pulse { transform-box:fill-box; transform-origin:center center; animation:kkPulse 2.2s ease-out infinite; }
		.tz-kk .kk-hbars .hb-track i { transition:width .5s cubic-bezier(.22,.9,.35,1); box-shadow:0 1px 2px rgba(16,24,40,.18); }

		/* ---- kuzatuvchi tooltip (shisha karta) ---- */
		.kk-tip { position:fixed; z-index:9999; pointer-events:none; min-width:170px; max-width:280px;
			background:rgba(15,23,42,.92); -webkit-backdrop-filter:blur(6px); backdrop-filter:blur(6px);
			color:#e2e8f0; border-radius:12px; padding:10px 13px; font-size:12px; line-height:1.55;
			box-shadow:0 10px 30px rgba(2,6,23,.35), 0 2px 8px rgba(2,6,23,.25);
			font-variant-numeric:tabular-nums; }
		.kk-tip .t { font-weight:800; color:#fff; margin-bottom:5px; font-size:12.5px; }
		.kk-tip .row { display:flex; align-items:center; gap:7px; }
		.kk-tip .row b { margin-left:auto; color:#fff; font-weight:700; }
		.kk-tip .row i { width:8px; height:8px; border-radius:3px; flex:none; }
		.kk-tip .q { margin-top:5px; padding-top:5px; border-top:1px solid rgba(148,163,184,.25); color:#94a3b8; }
		.kk-tip .q b { color:#dbeafe; }

		/* ---- heatmap ---- */
		.tz-kk .kk-heat { display:flex; gap:22px; flex-wrap:wrap; }
		.tz-kk .kk-heat-oy .t { font-size:12px; font-weight:700; margin-bottom:6px; color:${C.ink}; }
		.tz-kk .kk-heat-grid { display:grid; grid-template-rows:repeat(7, 13px); grid-auto-flow:column; gap:2px; }
		.tz-kk .kk-heat-cell { width:13px; height:13px; border-radius:3px; background:${C.lineSoft}; cursor:pointer; }
		.tz-kk .kk-heat-cell.bosh { background:transparent; cursor:default; }
		.tz-kk .kk-heat-cell:hover { outline:2px solid ${C.blue}; outline-offset:1px; }

		/* ---- joriy vs oldingi davr taqqoslash ---- */
		.tz-kk .kk-cmp-row { margin-bottom:12px; }
		.tz-kk .kk-cmp-hd { display:flex; align-items:center; gap:8px; font-size:12px; font-weight:700; color:${C.ink}; margin-bottom:4px; }
		.tz-kk .kk-cmp-bar { display:flex; align-items:center; gap:8px; margin-bottom:3px; }
		.tz-kk .kk-cmp-bar i { display:block; height:14px; border-radius:4px; box-shadow:0 1px 2px rgba(16,24,40,.15);
			transition:width .5s cubic-bezier(.22,.9,.35,1); }
		.tz-kk .kk-cmp-bar.old i { height:9px; opacity:.3; box-shadow:none; }
		.tz-kk .kk-cmp-bar b { font-size:12px; color:${C.ink}; white-space:nowrap; }
		.tz-kk .kk-cmp-bar.old b { font-size:11px; color:${C.faint}; font-weight:500; }

		/* ---- gorizontal barlar ---- */
		.tz-kk .kk-hbars .hb { margin-bottom:6px; }
		.tz-kk .kk-hbars .hb.click { cursor:pointer; border-radius:8px; padding:3px 6px; margin:0 -6px 5px; }
		.tz-kk .kk-hbars .hb.click:hover { background:${C.blueSoft}; }
		.tz-kk .kk-hbars .hb.click.active { background:${C.blueSoft}; box-shadow:inset 2px 0 0 ${C.blue}; }

		/* ---- drill-down paneli ---- */
		.tz-kk .kk-drill { margin-top:12px; }
		.tz-kk .kk-drill-box { border:1px solid ${C.line}; border-left:3px solid ${C.blue}; border-radius:10px;
			background:#fafbff; padding:12px 14px; }
		.tz-kk .kk-drill-hd { display:flex; align-items:baseline; gap:10px; margin-bottom:8px; flex-wrap:wrap; }
		.tz-kk .kk-drill-hd b { font-size:13px; color:${C.ink}; }
		.tz-kk .kk-drill-hd .meta { font-size:11.5px; color:${C.muted}; }
		.tz-kk .kk-drill-x { margin-left:auto; border:0; background:transparent; color:${C.faint};
			font-size:15px; cursor:pointer; line-height:1; padding:2px 6px; }
		.tz-kk .kk-drill-x:hover { color:${C.badInk}; }
		.tz-kk .kk-drill-grid { display:grid; grid-template-columns:3fr 2fr; gap:14px; }
		@media (max-width: 860px) { .tz-kk .kk-drill-grid { grid-template-columns:1fr; } }
		.tz-kk .kk-hbars .hb-t { display:flex; justify-content:space-between; font-size:12.5px; margin-bottom:3px; gap:10px; }
		.tz-kk .kk-hbars .hb-t > span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:${C.ink}; }
		.tz-kk .kk-hbars .hb-t b { color:${C.ink}; font-weight:700; white-space:nowrap; }
		.tz-kk .kk-hbars .kum { color:${C.faint}; font-weight:500; font-size:11px; }
		.tz-kk .kk-hbars .hb-track { height:6px; border-radius:5px; background:${C.lineSoft}; overflow:hidden; }
		.tz-kk .kk-hbars .hb-track i { display:block; height:100%; border-radius:5px; }
		.tz-kk .kk-subtitle { font-size:12px; font-weight:800; color:${C.ink}; margin:2px 0 8px; }

		/* ---- jadval ---- */
		.tz-kk table.kk-tbl { width:100%; border-collapse:collapse; font-size:12.5px; }
		.tz-kk table.kk-tbl th { text-align:left; font-size:10.5px; font-weight:700; text-transform:uppercase;
			letter-spacing:.5px; color:${C.faint}; border-bottom:1px solid ${C.line}; padding:8px 10px; background:${C.card}; }
		.tz-kk table.kk-tbl td { padding:8px 10px; border-bottom:1px solid ${C.lineSoft}; color:${C.ink}; }
		.tz-kk table.kk-tbl th.r, .tz-kk table.kk-tbl td.r { text-align:right; }
		.tz-kk tr.kk-day { cursor:pointer; }
		.tz-kk tr.kk-day td { font-weight:600; }
		.tz-kk tr.kk-day:hover td { background:${C.blueSoft}; }
		.tz-kk tr.kk-day.sel > td:first-child { box-shadow:inset 3px 0 0 ${C.blue}; }
		.tz-kk tr.kk-day .chev { display:inline-block; width:16px; color:${C.faint}; transition:transform .15s; }
		.tz-kk tr.kk-day.open .chev { transform:rotate(90deg); color:${C.blue}; }
		.tz-kk tr.kk-day .hk { color:${C.faint}; font-weight:500; font-size:11.5px; margin-left:4px; }
		.tz-kk tr.kk-docs > td { background:#fafbfe; padding:10px 14px 14px; }
		.tz-kk tr.kk-docs table.kk-tbl th { background:transparent; }
		.tz-kk tr.kk-docs a { color:${C.blue}; font-weight:600; text-decoration:none; }
		.tz-kk .kk-ichki, .tz-kk .kk-ichki td { color:${C.faint} !important; }
		.tz-kk tfoot td { font-weight:800 !important; border-top:2px solid ${C.line}; background:${C.card}; }
		.tz-kk .kk-pos { color:${C.goodInk}; } .tz-kk .kk-neg { color:${C.badInk}; }
		.tz-kk .kk-badge-n { color:${C.faint}; font-weight:500; }

		.tz-kk .kk-print-btn { border:1px solid ${C.line}; background:${C.card}; color:${C.muted};
			border-radius:8px; padding:3px 11px; font-size:11px; font-weight:700; cursor:pointer; }
		.tz-kk .kk-print-btn:hover { border-color:${C.blue}; color:${C.blue}; }
		.tz-kk .kk-limit { display:inline-flex; align-items:center; gap:6px; font-size:11.5px; color:${C.muted}; }
		.tz-kk .kk-limit input { width:130px; border:1px solid ${C.line}; border-radius:8px; padding:3px 9px;
			background:${C.card}; color:${C.ink}; font-size:12px; text-align:right; }
		.tz-kk .kk-warn { display:inline-flex; align-items:center; gap:6px; background:${C.badSoft};
			color:${C.badInk}; border-radius:999px; padding:3px 12px; font-size:11.5px; font-weight:700; }
		.tz-kk .kk-loader, .tz-kk .kk-empty { padding:36px; text-align:center; color:${C.faint}; font-size:13px; }

		/* ---- kichik ekranlar ---- */
		@media (max-width: 760px) {
			.tz-kk { padding:12px 10px 24px; border-radius:12px; }
			.tz-kk .kk-title { font-size:17px; }
			.tz-kk .kk-kpi .val { font-size:18px; }
			.tz-kk .kk-kpis { grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:8px; }
			.tz-kk .kk-card { padding:12px; }
			.tz-kk .kk-filters { padding:10px; gap:8px; }
			.tz-kk .kk-head-right { width:100%; }
		}
		`;
		$("<style>", { id: "kunlik-kassa-css", text: css }).appendTo("head");
	}

	const $root = $('<div class="tz-kk"><div class="kk-loader">Yuklanyapti…</div></div>').appendTo($host.empty());

	// ---------------------------------------------------------------- holat
	const st = {
		from: null, to: null, preset: "oy",
		currency: "", accounts: null,
		data: null, dayDocs: {}, selDay: null,
		tur: "",                      // operatsiya turi: Приход/Расход/Перемещения/Конвертация
		ptype: "",                    // kontragent turi: Customer/Employee/Supplier/Shareholder/Xarajatlar
		kat: "", party: "",           // kategoriya / kontragent filtri
	};
	presetDates("oy");

	const fmt = (v) => (Number(v) || 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 });
	const m1 = (v) => { const a = Math.abs(v); return a >= 1e9 ? (v / 1e9).toFixed(1) + " mlrd" : a >= 1e6 ? (v / 1e6).toFixed(1) + " mln" : a >= 1e3 ? (v / 1e3).toFixed(0) + " ming" : fmt(v); };
	const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
	const dmy = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s); return m ? `${m[3]}.${m[2]}.${m[1]}` : s; };
	const HAFTA = ["Yak", "Du", "Se", "Chor", "Pay", "Ju", "Shan"];
	const OYLAR = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
	const hk = (s) => { const d = new Date(s + "T00:00:00"); return isNaN(d) ? "" : HAFTA[d.getDay()]; };
	const pm = (v) => (v < 0 ? "−" + fmt(Math.abs(v)) : "+" + fmt(v));
	const limitKey = () => "kk_min_limit_" + (st.currency || "UZS");
	const getLimit = () => { try { return Number(localStorage.getItem(limitKey())) || 0; } catch (e) { return 0; } };

	function presetDates(p) {
		const t = frappe.datetime.get_today();
		st.preset = p;
		if (p === "bugun") { st.from = t; st.to = t; }
		else if (p === "kecha") { const k = frappe.datetime.add_days(t, -1); st.from = k; st.to = k; }
		else if (p === "hafta") { st.from = frappe.datetime.add_days(t, -6); st.to = t; }
		else if (p === "oy") { st.from = t.slice(0, 8) + "01"; st.to = t; }
		else if (p === "otgan_oy") {
			const b = frappe.datetime.add_months(t.slice(0, 8) + "01", -1);
			st.from = b; st.to = frappe.datetime.add_days(t.slice(0, 8) + "01", -1);
		}
	}

	// ---------------------------------------------------------------- yuklash
	function load() {
		$root.html(`<div class="kk-loader">Yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.api.kunlik_kassa.get_data",
			args: {
				from_date: st.from, to_date: st.to, currency: st.currency,
				accounts: JSON.stringify(st.accounts || []),
				kategoriya: st.kat, party: st.party,
				tur: st.tur, party_type: st.ptype,
			},
		}).then((r) => {
			st.data = r.message || null;
			st.dayDocs = {};
			if (st.data) st.currency = st.data.currency;
			render();
		}).catch(() => $root.html(`<div class="kk-empty">Ma'lumotni yuklab bo'lmadi.</div>`));
	}

	// ---------------------------------------------------------------- render
	function render() {
		tipHide();
		const d = st.data;
		if (!d || d.empty) { $root.html(`<div class="kk-empty">Kassa hujjatlari topilmadi.</div>`); return; }
		const flowLegend = `<div class="kk-legend right">
			<span><span class="sw" style="background:${C.good}"></span>Kirim</span>
			<span><span class="sw" style="background:${C.bad}"></span>Chiqim</span>
			<span><span class="ln"></span>Sof oqim</span></div>`;
		const limit = getLimit();
		const past = limit ? d.days.filter((x) => x.balans < limit).length : 0;
		const balRight = `<div class="kk-legend right"><span class="kk-limit">min chegara:
			<input type="text" class="kk-limit-inp num" value="${limit ? fmt(limit) : ""}" placeholder="0"> ${esc(d.currency)}</span>
			${past ? `<span class="kk-warn">⚠ ${past} kun chegaradan past</span>` : ""}</div>`;

		$root.html(head(d) + filters(d) + kpis(d)
			+ card("Kunlar kesimi — kassa kitobi",
				"qatorni bosing — kun hujjatlari ochiladi · КО-4 — chop etiladigan kunlik varaq (doim filtrsiz, to'liq kun)"
				+ ((st.kat || st.party) ? ` · <b style="color:${C.blueDark}">filtr faol:</b> kirim/chiqim filtrlangan, qoldiq ustunlari umumiy` : ""), ledger(d))
			+ `<div class="kk-grid2">`
			+ card("Pul oqimi", (d.days.length > 16 ? "haftalar kesimida" : "kunlar kesimida") + " · chiziq — sof oqim" + (d.days.length > 16 ? "" : " · ustun bosilsa jadvalda kun ochiladi"), flowChart(d), flowLegend)
			+ card("Qoldiq dinamikasi", "kun oxiridagi qoldiq, ichki o'tkazmalar bilan", balanceChart(d), balRight)
			+ `</div><div class="kk-grid2">`
			+ card("Joriy davr vs oldingi davr", "eng muhim uch ko'rsatkich taqqoslamasi", compareChart(d))
			+ card("Davr waterfall", "boshi → kirimlar → chiqimlar → oxiri · ustun bosilsa tafsilot", waterfall(d) + `<div class="kk-drill"></div>`)
			+ `</div><div class="kk-grid2">`
			+ card("Chiqim kategoriyalari", "qatorni bosing — tafsilot pastda ochiladi", pareto(d.chiqim_kat, C.bad, d.kpi.chiqim, "Расход") + `<div class="kk-drill"></div>`)
			+ card("Kirim manbalari", "qatorni bosing — tafsilot pastda ochiladi", pareto(d.kirim_kat, C.good, d.kpi.kirim, "Приход") + `<div class="kk-drill"></div>`)
			+ `</div><div class="kk-grid2">`
			+ card("Top kontragentlar", "qatorni bosing — kontragent tafsiloti pastda ochiladi", topParties(d) + `<div class="kk-drill"></div>`)
			+ card("Kalendar", "kunlik sof oqim: yashil — plyus, qizil — minus · kunni bosing", heatmap(d))
			+ `</div>`);
		wire();
		if (st.selDay) openDay(st.selDay, true);
	}

	const card = (t, meta, body, right) => `<div class="kk-card">
		<div class="kk-card-hd"><h3>${t}</h3><span class="meta">${meta}</span>${right ? `<span class="right">${right}</span>` : ""}</div>${body}</div>`;

	function head(d) {
		let selAcc = (st.accounts && st.accounts.length)
			? "faqat: " + st.accounts.map((a) => a.replace(" - TZ", "")).join(", ")
			: "barcha hisoblar";
		const TURL = { "Приход": "Kirim", "Расход": "Chiqim", "Перемещения": "Ko'chirma", "Конвертация": "Konvertatsiya" };
		if (st.tur) selAcc += " · tur: " + (TURL[st.tur] || st.tur);
		if (st.ptype) selAcc += " · kontragent turi: " + st.ptype;
		if (st.kat) selAcc += " · kategoriya: " + st.kat;
		if (st.party) selAcc += " · kontragent: " + st.party;
		return `<div class="kk-head">
			<div class="kk-title">Kunlik kassa<small>${dmy(d.from_date)} – ${dmy(d.to_date)} · ${esc(d.currency)} · ${esc(selAcc)}</small></div>
			<div class="kk-head-right"><span class="kk-asof">yangilangan: ${esc(d.as_of)}</span>
			<button class="kk-refresh">⟳ Yangilash</button></div></div>`;
	}

	function filters(d) {
		const P = [["bugun", "Bugun"], ["kecha", "Kecha"], ["hafta", "7 kun"], ["oy", "Shu oy"], ["otgan_oy", "O'tgan oy"]];
		const presets = `<div class="kk-seg">` + P.map(([k, l]) =>
			`<button data-preset="${k}" class="${st.preset === k ? "active" : ""}">${l}</button>`).join("") + `</div>`;
		const curs = `<div class="kk-seg">` + (d.currencies || []).map((c) =>
			`<button data-ccy="${esc(c)}" class="${c === d.currency ? "active" : ""}">${esc(c)}</button>`).join("") + `</div>`;
		const curAccs = (d.accounts || []).filter((a) => a.currency === d.currency);
		const hammasi = !st.accounts || !st.accounts.length;
		const accs = `<div class="kk-accs">
			<span class="kk-acc ${hammasi ? "active" : ""}" data-acc-all title="Barcha ${esc(d.currency)} hisoblari birga">Hammasi</span>`
			+ curAccs.map((a) => {
				const act = !hammasi && a.selected;
				return `<span class="kk-acc ${act ? "active" : ""}" data-acc="${esc(a.account)}"
					title="Joriy qoldiq: ${fmt(a.balans)} ${esc(a.currency)} · bosing — FAQAT shu hisob · Ctrl+bosish — qo'shish/olib tashlash">${esc(a.account.replace(" - TZ", ""))}<span class="bal num">${m1(a.balans)}</span></span>`;
			}).join("") + `</div>`;
		const opt = (v, cur0, lbl) => `<option value="${esc(v)}" ${v === cur0 ? "selected" : ""}>${esc(lbl || v)}</option>`;
		// Operatsiya turi (kassadagi "kategoriya"): Приход/Расход/Ko'chirma/Konvertatsiya
		const TURLAR = [["", "Hammasi"], ["Приход", "Kirim"], ["Расход", "Chiqim"],
			["Перемещения", "Ko'chirma"], ["Конвертация", "Konvert."]];
		const turSeg = `<div class="kk-seg">` + TURLAR.map(([v, l]) =>
			`<button data-tur="${esc(v)}" class="${st.tur === v ? "active" : ""}">${l}</button>`).join("") + `</div>`;
		// Kontragent turi
		const PTLAR = [["", "Barcha kontragent turi"], ["Customer", "O'quvchi (Customer)"],
			["Employee", "Xodim (Employee)"], ["Supplier", "Ta'minotchi (Supplier)"],
			["Shareholder", "Ta'sischi (Shareholder)"], ["Xarajatlar", "Xarajat moddalari"]];
		const ptSel = `<select class="kk-sel ${st.ptype ? "on" : ""}" data-f="ptype" title="Kontragent turi bo'yicha filtr">
			${PTLAR.map(([v, l]) => opt(v, st.ptype, l)).join("")}</select>`;
		const katSel = `<select class="kk-sel ${st.kat ? "on" : ""}" data-f="kat" title="Tahlil kategoriyasi bo'yicha filtr">
			<option value="">Barcha kategoriya</option>${(d.kategoriyalar || []).map((k) => opt(k, st.kat)).join("")}</select>`;
		const partySel = `<select class="kk-sel ${st.party ? "on" : ""}" data-f="party" title="Kontragent bo'yicha filtr">
			<option value="">Barcha kontragent</option>${(d.kontragentlar || []).map((p) => opt(p, st.party)).join("")}</select>`;
		return `<div class="kk-filters">${presets}
			<input type="date" class="kk-date" data-d="from" value="${st.from}">
			<input type="date" class="kk-date" data-d="to" value="${st.to}">
			${curs}</div>
			<div class="kk-filters" style="margin-top:-8px">${turSeg}${ptSel}${katSel}${partySel}${accs}</div>`;
	}

	// ---------------------------------------------------------------- KPI
	const daysLen = () => (st.data ? st.data.days.length : 0);
	function delta(cur, prev, teskari) {
		if (!prev && !cur) return `<span class="kk-delta flat">—</span>`;
		if (!prev) return `<span class="kk-delta flat" title="Oldingi davrda harakat yo'q">yangi</span>`;
		const p = (cur - prev) / Math.abs(prev) * 100;
		const yax = teskari ? p < 0 : p > 0;
		const cls = Math.abs(p) < 0.5 ? "flat" : (yax ? "up" : "dn");
		return `<span class="kk-delta ${cls}" title="Oldingi ${daysLen()} kunlik davr: ${fmt(prev)}">${p > 0 ? "↑" : "↓"} ${Math.abs(p).toFixed(0)}%</span>`;
	}

	// Silliq egri chiziq (overshoot'siz kubik) — [x,y] nuqtalardan path
	function smoothPath(pts) {
		if (pts.length < 2) return "";
		let dd = `M${pts[0][0]},${pts[0][1]}`;
		for (let i = 1; i < pts.length; i++) {
			const a = pts[i - 1], b = pts[i], mx = ((a[0] + b[0]) / 2).toFixed(1);
			dd += ` C${mx},${a[1]} ${mx},${b[1]} ${b[0]},${b[1]}`;
		}
		return dd;
	}
	const uid = () => "kk" + Math.random().toString(36).slice(2, 8);
	// Gradient + soya definitsiyalari (har svg uchun unikal id'lar bilan)
	function defs(u) {
		return `<defs>
			<linearGradient id="${u}in" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="#34d399"/><stop offset="100%" stop-color="#059669"/></linearGradient>
			<linearGradient id="${u}out" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="#fb7185"/><stop offset="100%" stop-color="#e11d48"/></linearGradient>
			<linearGradient id="${u}anchor" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="#cbd5e1"/><stop offset="100%" stop-color="#94a3b8"/></linearGradient>
			<linearGradient id="${u}bal" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="${C.blue}" stop-opacity=".28"/>
				<stop offset="55%" stop-color="${C.blue}" stop-opacity=".10"/>
				<stop offset="100%" stop-color="${C.blue}" stop-opacity="0"/></linearGradient>
			<filter id="${u}soft" x="-30%" y="-30%" width="160%" height="170%">
				<feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#0f172a" flood-opacity=".16"/></filter>
			<filter id="${u}glow" x="-40%" y="-40%" width="180%" height="180%">
				<feGaussianBlur stdDeviation="3"/></filter>
		</defs>`;
	}

	function spark(vals, color) {
		if (!vals || vals.length < 2) return "";
		const W = 76, H = 26, mx = Math.max(...vals.map(Math.abs), 1);
		const P = vals.map((v, i) => [+(i / (vals.length - 1) * W).toFixed(1), +(H / 2 - v / mx * (H / 2 - 3)).toFixed(1)]);
		const dd = smoothPath(P);
		return `<svg class="kk-spark" width="${W}" height="${H}">
			<line x1="0" y1="${H / 2}" x2="${W}" y2="${H / 2}" stroke="${C.lineSoft}"/>
			<path d="${dd} L${W},${H} L0,${H} Z" fill="${color}" opacity=".10" stroke="none"/>
			<path d="${dd}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
			<circle cx="${P[P.length - 1][0]}" cy="${P[P.length - 1][1]}" r="2.6" fill="${color}" stroke="#fff" stroke-width="1.2"/></svg>`;
	}

	// ---- kuzatuvchi tooltip ----
	let $tip = null;
	function tipShow(html, ev) {
		if (!$tip) $tip = $('<div class="kk-tip" style="display:none"></div>').appendTo(document.body);
		$tip.html(html).show();
		tipMove(ev);
	}
	function tipMove(ev) {
		if (!$tip || !$tip.is(":visible")) return;
		const w = $tip.outerWidth() || 200, h = $tip.outerHeight() || 90;
		let x = ev.clientX + 16, y = ev.clientY + 16;
		if (x + w > window.innerWidth - 8) x = ev.clientX - w - 14;
		if (y + h > window.innerHeight - 8) y = ev.clientY - h - 12;
		$tip.css({ left: x + "px", top: y + "px" });
	}
	function tipHide() { if ($tip) $tip.hide(); }
	function dayTip(x) {
		return `<div class="t">${dmy(x.sana)} · ${hk(x.sana)}</div>
			<div class="row"><i style="background:${C.good}"></i>Kirim <b>${fmt(x.kirim)}</b></div>
			<div class="row"><i style="background:${C.bad}"></i>Chiqim <b>${fmt(x.chiqim)}</b></div>
			<div class="row"><i style="background:${C.blue}"></i>Sof oqim <b>${pm(x.net)}</b></div>
			<div class="q">Kun oxiri qoldiq: <b>${fmt(x.balans)}</b> · ${x.n} hujjat</div>`;
	}

	function kpis(d) {
		const k = d.kpi, cur = d.currency, L = k.largest;
		// kirim/chiqim kartalari KASSA KITOBI jadvalini filtrlaydi (tur filtri bilan bir)
		const kpi = (lab, val, foot, click, act) => `<div class="kk-kpi ${click ? "click" : "noclick"} ${act ? "active" : ""}" ${click || ""}>
			<div class="lab">${lab}${click ? `<span class="hint">${act ? "✕ filtrni yopish" : "filtr ▾"}</span>` : ""}</div>
			<div class="val num">${val}</div><div class="foot">${foot || ""}</div></div>`;
		return `<div class="kk-kpis">
			${kpi("Yakuniy qoldiq", `<span style="color:${C.blueDark}">${fmt(k.closing)}</span> <small>${esc(cur)}</small>`,
				`<span class="sub">boshi: ${fmt(k.opening)}</span>`)}
			${kpi("Davr sof oqimi", `<span class="${k.net < 0 ? "kk-neg" : "kk-pos"}">${pm(k.net)}</span>`,
				`${delta(k.net, k.prev.net, false)}${spark(d.days.map((x) => (x.kirim0 != null ? x.kirim0 - x.chiqim0 : x.net)), C.blue)}`)}
			${kpi("Kirim", `<span class="kk-pos">${fmt(k.kirim)}</span>`,
				`${delta(k.kirim, k.prev.kirim, false)}${spark(d.days.map((x) => (x.kirim0 != null ? x.kirim0 : x.kirim)), C.good)}`,
				'data-kpi-tur="Приход"', st.tur === "Приход")}
			${kpi("Chiqim", `<span class="kk-neg">${fmt(k.chiqim)}</span>`,
				`${delta(k.chiqim, k.prev.chiqim, true)}${spark(d.days.map((x) => (x.chiqim0 != null ? x.chiqim0 : x.chiqim)), C.bad)}`,
				'data-kpi-tur="Расход"', st.tur === "Расход")}
			${kpi("Runway", k.runway ? `≈ ${Math.round(k.runway)} <small>kun</small>` : "—",
				`<span class="sub">${k.avg_chiqim > 0 ? "o'rtacha kunlik chiqim: " + m1(k.avg_chiqim) : "chiqim yo'q"}</span>`)}
			${kpi("Eng katta tranzaksiya", L ? `<span class="${L.tur === "Приход" ? "kk-pos" : "kk-neg"}">${m1(L.amount)}</span>` : "—",
				`<span class="sub">${L ? `${dmy(L.sana)} · ${esc((L.party_name || L.kategoriya || "").slice(0, 26))}` : "davrda harakat yo'q"}</span>`,
				L ? `data-kpi-day="${L.sana}"` : "")}
		</div>`;
	}

	// Kunlik mini-bar diagramma (drill-down va KPI tafsilotlari uchun)
	function miniBars(days, val, color, signli) {
		const n = days.length;
		if (!n) return `<div class="kk-empty" style="padding:14px">Ma'lumot yo'q.</div>`;
		const u = uid();
		const W = 640, H = 120, pL = 52, pR = 8, pT = 8, pB = 20;
		const vals = days.map(val);
		const mx = Math.max(1, ...vals.map(Math.abs));
		const y0 = signli ? pT + (H - pT - pB) / 2 : H - pB;
		const scale = (H - pT - pB) / (signli ? 2 : 1);
		const slot = (W - pL - pR) / n, bw = Math.max(2.5, Math.min(22, slot * 0.62));
		const step = n <= 16 ? 1 : Math.ceil(n / 12);
		const fillOf = (v) => {
			if (signli) return v >= 0 ? `url(#${u}in)` : `url(#${u}out)`;
			if (color === C.good) return `url(#${u}in)`;
			if (color === C.bad) return `url(#${u}out)`;
			return color;
		};
		let bars = "", labs = "";
		days.forEach((x, i) => {
			const v = vals[i], cx = pL + slot * i + slot / 2;
			if (Math.abs(v) > 0.5) {
				const h = Math.max(2.5, Math.abs(v) / mx * scale);
				const y = v >= 0 ? y0 - h : y0;
				bars += `<rect class="${v >= 0 ? "kk-grow" : "kk-growd"}" style="animation-delay:${Math.min(0.3, i * 0.012).toFixed(2)}s"
					x="${(cx - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3.5"
					fill="${fillOf(v)}" filter="url(#${u}soft)"><title>${esc(dmy(x.sana))}: ${fmt(v)}</title></rect>`;
			}
			if (i % step === 0) labs += `<text x="${cx}" y="${H - 7}" font-size="10" fill="${C.faint}" text-anchor="middle">${Number(x.sana.slice(8, 10))}</text>`;
		});
		return `<svg width="100%" viewBox="0 0 ${W} ${H}">${defs(u)}
			<line x1="${pL}" y1="${y0}" x2="${W - pR}" y2="${y0}" stroke="${C.line}"/>
			<text x="${pL - 7}" y="${pT + 6}" font-size="10" fill="${C.faint}" text-anchor="end">${m1(mx)}</text>
			${bars}${labs}</svg>`;
	}

	// ---------------------------------------------------------------- oqim diagrammasi
	// Davr 16 kundan uzun bo'lsa HAFTALARGA yig'iladi (Xero/QuickBooks andozasi:
	// 30 ta ingichka ustun o'rniga 4-5 ta aniq taqqoslanadigan ustun)
	function flowBuckets(days) {
		if (days.length <= 16) {
			return days.map((x) => ({ ...x, dan: x.sana, gacha: x.sana, hafta: false }));
		}
		const map = new Map();
		days.forEach((x) => {
			const dt = new Date(x.sana + "T00:00:00");
			const ws = new Date(dt); ws.setDate(dt.getDate() - (dt.getDay() + 6) % 7);
			const key = `${ws.getFullYear()}-${String(ws.getMonth() + 1).padStart(2, "0")}-${String(ws.getDate()).padStart(2, "0")}`;
			let b = map.get(key);
			if (!b) { b = { sana: key, dan: x.sana, gacha: x.sana, kirim: 0, chiqim: 0, net: 0, n: 0, balans: 0, hafta: true }; map.set(key, b); }
			b.kirim += x.kirim; b.chiqim += x.chiqim; b.net += x.net; b.n += x.n;
			b.gacha = x.sana; b.balans = x.balans;
		});
		return [...map.values()];
	}

	function flowChart(d) {
		const days = d.days;
		if (!days.length) return `<div class="kk-empty">Ma'lumot yo'q.</div>`;
		const B = flowBuckets(days);
		st.flowBuckets = B;
		const haftalik = B.length && B[0].hafta;
		const n = B.length, u = uid();
		const W = 600, H = 190, pL = 56, pR = 10, pT = 10, pB = 24;
		const maxK = Math.max(1, ...B.map((x) => x.kirim));
		const maxC = Math.max(1, ...B.map((x) => x.chiqim));
		const span = maxK + maxC;
		const y0 = pT + (H - pT - pB) * (maxK / span);
		const yV = (v) => y0 - v / span * (H - pT - pB);
		const slot = (W - pL - pR) / n, bw = Math.max(6, Math.min(54, slot * 0.58));
		let bars = "", labs = "";
		B.forEach((x, i) => {
			const cx = pL + slot * i + slot / 2;
			const dl = Math.min(0.3, i * 0.04).toFixed(2);
			bars += `<g class="kk-day-hit" data-bucket="${i}" ${x.hafta ? "" : `data-day="${x.sana}"`}>
				<rect class="hover-bg" x="${(cx - slot / 2).toFixed(1)}" y="${pT}" width="${slot.toFixed(1)}" height="${H - pT - pB}" rx="6" fill="transparent"/>
				${x.kirim ? `<rect class="kk-grow" style="animation-delay:${dl}s" x="${(cx - bw / 2).toFixed(1)}" y="${yV(x.kirim).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(2.5, y0 - yV(x.kirim) - 1).toFixed(1)}" rx="4" fill="url(#${u}in)" filter="url(#${u}soft)"/>` : ""}
				${x.chiqim ? `<rect class="kk-growd" style="animation-delay:${dl}s" x="${(cx - bw / 2).toFixed(1)}" y="${(y0 + 2).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(2.5, yV(-x.chiqim) - y0 - 2).toFixed(1)}" rx="4" fill="url(#${u}out)" filter="url(#${u}soft)"/>` : ""}
			</g>`;
			const lbl = x.hafta ? `${Number(x.dan.slice(8, 10))}–${Number(x.gacha.slice(8, 10))}` : Number(x.sana.slice(8, 10));
			labs += `<text x="${cx}" y="${H - 9}" font-size="10" fill="${C.faint}" text-anchor="middle">${lbl}</text>`;
		});
		const P = B.map((x, i) => [+(pL + slot * i + slot / 2).toFixed(1), +yV(x.net).toFixed(1)]);
		const netPath = smoothPath(P);
		const gl = (v, strong) => `<line x1="${pL}" y1="${yV(v)}" x2="${W - pR}" y2="${yV(v)}" stroke="${strong ? C.line : C.lineSoft}" ${strong ? "" : 'stroke-dasharray="1 4" stroke-linecap="round"'}/>
			<text x="${pL - 7}" y="${yV(v) + 3.5}" font-size="10" fill="${C.faint}" text-anchor="end">${v ? m1(v) : "0"}</text>`;
		const last = P[P.length - 1];
		return `<svg width="100%" viewBox="0 0 ${W} ${H}">${defs(u)}
			${gl(maxK)}${gl(0, true)}${gl(-maxC)}
			${bars}
			<path d="${netPath}" fill="none" stroke="${C.blue}" stroke-width="5" opacity=".2" filter="url(#${u}glow)"/>
			<path d="${netPath}" fill="none" stroke="${C.blue}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
			<circle class="kk-pulse" cx="${last[0]}" cy="${last[1]}" r="4.5" fill="${C.blue}"/>
			<circle cx="${last[0]}" cy="${last[1]}" r="3.6" fill="${C.blue}" stroke="#fff" stroke-width="1.6"/>
			${labs}</svg>`;
	}

	// Joriy davr vs oldingi davr — eng kerakli uch ko'rsatkichni yonma-yon
	// taqqoslash (ERP snapshot andozasi: Xero Business Snapshot uslubi)
	function compareChart(d) {
		const k = d.kpi, p = k.prev || {};
		const rows = [
			{ label: "Kirim", cur: k.kirim, old: p.kirim || 0, color: C.good, teskari: false },
			{ label: "Chiqim", cur: k.chiqim, old: p.chiqim || 0, color: C.bad, teskari: true },
			{ label: "Sof oqim", cur: k.net, old: p.net || 0, color: C.blue, teskari: false },
		];
		const mx = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.cur), Math.abs(r.old)]));
		return `<div class="kk-cmp">` + rows.map((r) => `
			<div class="kk-cmp-row">
				<div class="kk-cmp-hd"><span>${r.label}</span>${delta(r.cur, r.old, r.teskari)}</div>
				<div class="kk-cmp-bar"><i style="width:${Math.max(1.5, Math.abs(r.cur) / mx * 100)}%;background:${r.color}"></i>
					<b class="num ${r.cur < 0 ? "kk-neg" : ""}">${fmt(r.cur)}</b></div>
				<div class="kk-cmp-bar old"><i style="width:${Math.max(1.5, Math.abs(r.old) / mx * 100)}%;background:${r.color}"></i>
					<b class="num">${fmt(r.old)}</b></div>
			</div>`).join("") + `
			<div class="kk-legend" style="margin-top:8px">
				<span><span class="sw" style="background:${C.ink};opacity:.85"></span>joriy davr (${d.days.length} kun)</span>
				<span><span class="sw" style="background:${C.ink};opacity:.3"></span>oldingi ${d.days.length} kun</span></div></div>`;
	}

	// ---------------------------------------------------------------- qoldiq diagrammasi
	function balanceChart(d) {
		const days = d.days, n = days.length;
		if (!n) return `<div class="kk-empty">Ma'lumot yo'q.</div>`;
		const limit = getLimit();
		const W = 600, H = 180, pL = 62, pR = 10, pT = 12, pB = 22;
		const vals = days.map((x) => x.balans).concat([d.kpi.opening]);
		if (limit) vals.push(limit);
		let lo = Math.min(...vals), hi = Math.max(...vals);
		if (hi === lo) hi = lo + 1;
		const pad = (hi - lo) * 0.1; lo -= pad; hi += pad;
		const yV = (v) => pT + (hi - v) / (hi - lo) * (H - pT - pB);
		const xV = (i) => pL + (n === 1 ? (W - pL - pR) / 2 : i * (W - pL - pR) / (n - 1));
		const pts = days.map((x, i) => `${xV(i).toFixed(1)},${yV(x.balans).toFixed(1)}`);
		const area = `${pts.join(" ")} ${xV(n - 1).toFixed(1)},${(H - pB).toFixed(1)} ${xV(0).toFixed(1)},${(H - pB).toFixed(1)}`;
		const grid = [hi - pad, (hi + lo) / 2, lo + pad].map((v) =>
			`<line x1="${pL}" y1="${yV(v)}" x2="${W - pR}" y2="${yV(v)}" stroke="${C.lineSoft}"/>
			 <text x="${pL - 8}" y="${yV(v) + 3.5}" font-size="10.5" fill="${C.faint}" text-anchor="end">${m1(v)}</text>`).join("");
		const limitLine = limit ? `<line x1="${pL}" y1="${yV(limit)}" x2="${W - pR}" y2="${yV(limit)}" stroke="${C.bad}" stroke-width="1.6" stroke-dasharray="6 4"/>
			<text x="${W - pR}" y="${yV(limit) - 5}" font-size="10.5" font-weight="700" fill="${C.badInk}" text-anchor="end">min ${m1(limit)}</text>` : "";
		const dots = days.map((x, i) => (limit && x.balans < limit)
			? `<circle cx="${xV(i)}" cy="${yV(x.balans)}" r="3.6" fill="${C.bad}" stroke="#fff" stroke-width="1.4"/>` : "").join("");
		const step = n <= 12 ? 1 : Math.ceil(n / 8);
		const labs = days.map((x, i) => i % step === 0 ? `<text x="${xV(i)}" y="${H - 7}" font-size="10.5" fill="${C.faint}" text-anchor="middle">${Number(x.sana.slice(8, 10))}</text>` : "").join("");
		const u = uid();
		const PP = days.map((x, i) => [+xV(i).toFixed(1), +yV(x.balans).toFixed(1)]);
		const dd = smoothPath(PP);
		const areaPath = `${dd} L${xV(n - 1).toFixed(1)},${(H - pB).toFixed(1)} L${xV(0).toFixed(1)},${(H - pB).toFixed(1)} Z`;
		// har kun uchun ko'rinmas ustun — hover tooltip + bosilsa jadvalda kun ochiladi
		const hits = days.map((x, i) => `<rect class="kk-day-hit hover-bg" data-day="${x.sana}"
			x="${(xV(i) - (n > 1 ? (xV(1) - xV(0)) / 2 : 20)).toFixed(1)}" y="${pT}" width="${(n > 1 ? xV(1) - xV(0) : 40).toFixed(1)}" height="${H - pT - pB}" fill="transparent"/>`).join("");
		const lastVal = days[n - 1].balans;
		const chipW = Math.max(60, String(m1(lastVal)).length * 7.5 + 18);
		const chipX = Math.min(PP[n - 1][0] + 10, W - pR - chipW);
		const chipY = Math.max(pT, PP[n - 1][1] - 26);
		return `<svg width="100%" viewBox="0 0 ${W} ${H}">${defs(u)}
			${grid}
			<path d="${areaPath}" fill="url(#${u}bal)" stroke="none"/>
			<path d="${dd}" fill="none" stroke="${C.blue}" stroke-width="6" opacity=".18" filter="url(#${u}glow)"/>
			<path d="${dd}" fill="none" stroke="${C.blue}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>
			<circle class="kk-pulse" cx="${PP[n - 1][0]}" cy="${PP[n - 1][1]}" r="5" fill="${C.blue}"/>
			<circle cx="${PP[n - 1][0]}" cy="${PP[n - 1][1]}" r="4" fill="${C.blue}" stroke="#fff" stroke-width="1.8"/>
			<g filter="url(#${u}soft)"><rect x="${chipX.toFixed(1)}" y="${chipY.toFixed(1)}" width="${chipW.toFixed(1)}" height="20" rx="10" fill="${C.blueDark}"/>
			<text x="${(chipX + chipW / 2).toFixed(1)}" y="${(chipY + 13.5).toFixed(1)}" font-size="11" font-weight="700" fill="#fff" text-anchor="middle">${m1(lastVal)}</text></g>
			${limitLine}${dots}${hits}${labs}</svg>`;
	}

	// ---------------------------------------------------------------- heatmap
	function heatmap(d) {
		const days = d.days;
		if (!days.length) return `<div class="kk-empty">Ma'lumot yo'q.</div>`;
		const maxAbs = Math.max(1, ...days.map((x) => Math.abs(x.net)));
		const oylar = {};
		days.forEach((x) => { const k = x.sana.slice(0, 7); (oylar[k] = oylar[k] || []).push(x); });
		return `<div class="kk-heat">` + Object.keys(oylar).sort().map((ok) => {
			const list = oylar[ok];
			const first = new Date(list[0].sana + "T00:00:00");
			const pad = (first.getDay() + 6) % 7;
			let cells = "";
			for (let i = 0; i < pad; i++) cells += `<span class="kk-heat-cell bosh"></span>`;
			list.forEach((x) => {
				let style = "";
				if (x.n && Math.abs(x.net) > 0.5) {
					const op = (0.3 + 0.7 * Math.abs(x.net) / maxAbs).toFixed(2);
					style = `background:${x.net > 0 ? C.good : C.bad};opacity:${op};`;
				} else if (x.n) style = `background:${C.slate};opacity:.5;`;
				cells += `<span class="kk-heat-cell" data-day="${x.sana}" style="${style}"></span>`;
			});
			const m = Number(ok.slice(5, 7));
			return `<div class="kk-heat-oy"><div class="t">${OYLAR[m - 1]} ${ok.slice(0, 4)}</div><div class="kk-heat-grid">${cells}</div></div>`;
		}).join("") + `</div>
		<div class="kk-legend" style="margin-top:10px">
			<span><span class="sw" style="background:${C.good}"></span>plyus kun</span>
			<span><span class="sw" style="background:${C.bad}"></span>minus kun</span>
			<span><span class="sw" style="background:${C.slate};opacity:.5"></span>sof ≈ 0</span>
			<span><span class="sw" style="background:${C.lineSoft}"></span>harakat yo'q</span></div>`;
	}

	// ---------------------------------------------------------------- waterfall
	function waterfall(d) {
		const TOP = 5;
		const squash = (list) => {
			const a = list.slice(0, TOP), rest = list.slice(TOP);
			if (rest.length) a.push({ label: `Boshqa (${rest.length})`, summa: rest.reduce((s, x) => s + x.summa, 0) });
			return a.filter((x) => x.summa > 0.5);
		};
		const kir = squash(d.kirim_kat), chi = squash(d.chiqim_kat);
		const steps = [{ label: "Boshi", v: d.kpi.opening, tip: "anchor" }]
			.concat(kir.map((x) => ({ label: x.label, v: x.summa, tip: "in" })))
			.concat(chi.map((x) => ({ label: x.label, v: -x.summa, tip: "out" })))
			.concat([{ label: "Oxiri", v: d.kpi.closing, tip: "anchor" }]);
		let run = d.kpi.opening, lo = Math.min(0, d.kpi.opening), hi = Math.max(0, d.kpi.opening);
		const pos = steps.map((s) => {
			if (s.tip === "anchor") { lo = Math.min(lo, s.v, 0); hi = Math.max(hi, s.v); return { ...s, a: 0, b: s.v }; }
			const a = run; run += s.v; const b = run;
			lo = Math.min(lo, a, b); hi = Math.max(hi, a, b);
			return { ...s, a, b };
		});
		if (hi === lo) hi = lo + 1;
		const u = uid();
		const W = 600, H = 200, pL = 62, pR = 8, pT = 14, pB = 50;
		const yV = (v) => pT + (hi - v) / (hi - lo) * (H - pT - pB);
		const n = pos.length, slot = (W - pL - pR) / n, bw = Math.min(48, slot * 0.68);
		let out = "", conns = "", prevX = null, prevY = null;
		pos.forEach((s, i) => {
			const x = pL + slot * i + (slot - bw) / 2;
			const yA = yV(Math.max(s.a, s.b)), hB = Math.max(3, Math.abs(yV(s.a) - yV(s.b)));
			const fill = s.tip === "anchor" ? `url(#${u}anchor)` : (s.tip === "in" ? `url(#${u}in)` : `url(#${u}out)`);
			const drill = (s.tip !== "anchor" && !/^Boshqa \(/.test(s.label))
				? ` data-tur="${s.tip === "in" ? "Приход" : "Расход"}" data-kat="${esc(s.label)}" style="cursor:pointer"` : "";
			out += `<g class="kk-wf-hit"${drill}><title>${esc(s.label)}: ${fmt(Math.abs(s.tip === "anchor" ? s.b : s.v))}${drill ? " — bosing, tafsilot ochiladi" : ""}</title>
				<rect class="kk-grow" style="animation-delay:${(i * 0.05).toFixed(2)}s" x="${x.toFixed(1)}" y="${yA.toFixed(1)}" width="${bw.toFixed(1)}" height="${hB.toFixed(1)}" rx="5" fill="${fill}" filter="url(#${u}soft)"/></g>
				<text x="${(x + bw / 2).toFixed(1)}" y="${(yA - 6).toFixed(1)}" font-size="9.5" font-weight="700" fill="${C.ink}" text-anchor="middle">${m1(s.tip === "anchor" ? s.b : Math.abs(s.v))}</text>`;
			const lbl = s.label.length > 14 ? s.label.slice(0, 13) + "…" : s.label;
			out += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - 42}" font-size="9.5" fill="${C.muted}" text-anchor="end" transform="rotate(-30 ${(x + bw / 2).toFixed(1)} ${H - 42})">${esc(lbl)}</text>`;
			const edgeY = yV(s.b).toFixed(1);
			if (prevX != null) conns += `<line x1="${prevX}" y1="${prevY}" x2="${x.toFixed(1)}" y2="${prevY}" stroke="${C.slate}" stroke-width="1" stroke-dasharray="2 3" opacity=".7"/>`;
			prevX = (x + bw).toFixed(1); prevY = edgeY;
		});
		return `<svg width="100%" viewBox="0 0 ${W} ${H}">${defs(u)}
			<line x1="${pL}" y1="${yV(0)}" x2="${W - pR}" y2="${yV(0)}" stroke="${C.line}"/>${conns}${out}</svg>`;
	}

	// ---------------------------------------------------------------- pareto / top
	function pareto(list, color, total, tur) {
		if (!list || !list.length) return `<div class="kk-empty">Davrda harakat yo'q.</div>`;
		const mx = Math.max(1, ...list.map((x) => x.summa));
		let kum = 0;
		return `<div class="kk-hbars">` + list.slice(0, 8).map((x) => {
			kum += x.summa;
			const ulush = total ? (x.summa / total * 100) : 0;
			const click = tur ? ` click" data-tur="${esc(tur)}" data-kat="${esc(x.label)}" title="Bosing — kategoriya tafsiloti pastda ochiladi` : "";
			return `<div class="hb${click}"><div class="hb-t">
				<span title="${esc(x.label)}">${esc(x.label)}</span>
				<b class="num">${fmt(x.summa)} <span class="kum">${ulush.toFixed(0)}% · kum. ${total ? (kum / total * 100).toFixed(0) : 0}%</span></b></div>
				<div class="hb-track"><i style="width:${Math.max(2, x.summa / mx * 100)}%;background:${color}"></i></div></div>`;
		}).join("") + `</div>`;
	}

	function topParties(d) {
		const blok = (title, list, color, tur) => {
			const mx = Math.max(1, ...list.map((y) => y.summa));
			return `<div style="margin-bottom:12px"><div class="kk-subtitle">${title}</div>`
				+ (list.length ? `<div class="kk-hbars">` + list.map((x) =>
					`<div class="hb click" data-tur="${esc(tur)}" data-party="${esc(x.label)}" title="Bosing — kontragent tafsiloti pastda ochiladi">
					<div class="hb-t"><span title="${esc(x.label)}">${esc(x.label)}</span><b class="num">${fmt(x.summa)}</b></div>
					<div class="hb-track"><i style="width:${Math.max(2, x.summa / mx * 100)}%;background:${color}"></i></div></div>`).join("") + `</div>`
					: `<div class="kk-empty" style="padding:8px">yo'q</div>`) + `</div>`;
		};
		return blok("Kirim — top 5", d.top_kirim || [], C.good, "Приход")
			+ blok("Chiqim — top 5", d.top_chiqim || [], C.bad, "Расход");
	}

	// ---------------------------------------------------------------- ledger
	function ledger(d) {
		// Har kunning BOSHIDAGI qoldig'i — oldingi kunning oxirgi qoldig'i
		// (kassa kitobi mantiqi: boshi -> kirim -> chiqim -> sof -> oxiri)
		const boshi = {};
		let prev = d.kpi.opening;
		d.days.forEach((x) => { boshi[x.sana] = prev; prev = x.balans; });

		const rows = d.days.filter((x) => x.n).slice().reverse().map((x) => `
			<tr class="kk-day" data-day="${x.sana}">
				<td><span class="chev">▸</span>${dmy(x.sana)}<span class="hk">${hk(x.sana)}</span></td>
				<td class="r num" style="color:${C.muted}">${fmt(boshi[x.sana])}</td>
				<td class="r num kk-pos">${x.kirim ? "+" + fmt(x.kirim) : "—"}</td>
				<td class="r num kk-neg">${x.chiqim ? "(" + fmt(x.chiqim) + ")" : "—"}</td>
				<td class="r num ${x.net < 0 ? "kk-neg" : "kk-pos"}">${pm(x.net)}</td>
				<td class="r num" style="color:${C.blueDark};font-weight:800">${fmt(x.balans)}</td>
				<td class="r num kk-badge-n">${x.n}</td>
				<td class="r"><button class="kk-print-btn" data-ko4="${x.sana}" title="КО-4 uslubidagi kunlik kassa varag'i">КО-4</button></td>
			</tr>
			<tr class="kk-docs" data-docs="${x.sana}" style="display:none"><td colspan="8"><div class="kk-loader" style="padding:10px">…</div></td></tr>`).join("");
		if (!rows) return `<div class="kk-empty">Davrda kassa harakati yo'q.</div>`;
		const k = d.kpi;
		return `<div style="overflow-x:auto"><table class="kk-tbl">
			<thead><tr><th>Sana</th><th class="r">Kun boshi</th><th class="r">Kirim (+)</th><th class="r">Chiqim (−)</th><th class="r">Sof oqim</th><th class="r">Kun oxiri</th><th class="r">Hujjat</th><th></th></tr></thead>
			<tbody>${rows}</tbody>
			<tfoot><tr><td>JAMI — ${d.days.length} kun (${k.faol_kun} faol)</td>
				<td class="r num" style="color:${C.muted}">${fmt(k.opening)}</td>
				<td class="r num kk-pos">+${fmt(k.kirim)}</td>
				<td class="r num kk-neg">(${fmt(k.chiqim)})</td>
				<td class="r num ${k.net < 0 ? "kk-neg" : "kk-pos"}">${pm(k.net)}</td>
				<td class="r num" style="color:${C.blueDark}">${fmt(k.closing)}</td>
				<td class="r num">${k.n}</td><td></td></tr></tfoot>
		</table></div>`;
	}

	function docsHtml(day, res) {
		const list = res.rows || [];
		const faol = [st.tur && "tur", st.ptype && "kontragent turi", st.kat && "kategoriya", st.party && "kontragent"].filter(Boolean);
		const filtrIzoh = faol.length ? " · filtr faol: " + faol.join(", ") : "";
		const rows = list.map((r) => `
			<tr class="${r.ichki ? "kk-ichki" : ""}">
				<td class="num">${esc(r.vaqt)}</td>
				<td><a href="/app/kassa/${encodeURIComponent(r.name)}" target="_blank">${esc(r.name)}</a></td>
				<td>${esc((r.usul || r.hisob || "").replace(" - TZ", ""))}</td>
				<td>${esc(r.kontragent || "—")}</td>
				<td>${esc(r.kategoriya)}${r.oy ? ` <span style="color:${C.faint}">(${esc(r.oy)})</span>` : ""}</td>
				<td class="r num ${r.ichki ? "" : (r.summa < 0 ? "kk-neg" : "kk-pos")}" style="font-weight:700">
					${r.summa < 0 ? "(" + fmt(Math.abs(r.summa)) + ")" : fmt(r.summa)}</td>
				<td style="color:${C.muted};max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(r.izoh)}">${esc(r.izoh)}</td>
			</tr>`).join("");
		return `<table class="kk-tbl" style="font-size:12px">
			<thead><tr><th>Vaqt</th><th>Hujjat</th><th>Kassa</th><th>Kontragent</th><th>Kategoriya</th><th class="r">Summa</th><th>Izoh</th></tr></thead>
			<tbody>${rows || `<tr><td colspan="7" class="kk-empty">Hujjat yo'q</td></tr>`}</tbody></table>
			<div style="font-size:11.5px;color:${C.muted};margin-top:6px">Kun boshi: <b class="num">${fmt(res.opening)}</b> · kun oxiri: <b class="num" style="color:${C.blueDark}">${fmt(res.closing)}</b> ${esc(res.currency)} · kulrang qatorlar — ichki ko'chirma (oqimga kirmaydi)${filtrIzoh}</div>`;
	}

	function openDay(day, scroll) {
		const $tr = $root.find(`tr.kk-day[data-day="${day}"]`);
		if (!$tr.length) return;
		$root.find("tr.kk-day").removeClass("sel");
		$tr.addClass("sel open");
		const $docs = $root.find(`tr[data-docs="${day}"]`);
		$docs.show();
		if (scroll && $tr[0] && $tr[0].scrollIntoView) $tr[0].scrollIntoView({ behavior: "smooth", block: "center" });
		if (st.dayDocs[day]) { $docs.children("td").html(docsHtml(day, st.dayDocs[day])); return; }
		frappe.call({
			method: "target_zenit.target_zenit.api.kunlik_kassa.get_day_docs",
			args: { sana: day, currency: st.currency, accounts: JSON.stringify(st.accounts || []),
				kategoriya: st.kat, party: st.party, tur: st.tur, party_type: st.ptype },
		}).then((r) => {
			st.dayDocs[day] = r.message || { rows: [] };
			$docs.children("td").html(docsHtml(day, st.dayDocs[day]));
		});
	}

	// ---------------------------------------------------------------- КО-4 print
	function printKo4(day) {
		const go = (res) => {
			const rows = (res.rows || []).map((r, i) => `
				<tr><td>${i + 1}</td><td>${esc(r.name)}</td>
				<td>${esc(r.kontragent || r.kategoriya)}${r.izoh ? ` — ${esc(r.izoh)}` : ""}</td>
				<td>${esc(r.kategoriya)}</td>
				<td class="r">${r.summa > 0 ? fmt(r.summa) : ""}</td>
				<td class="r">${r.summa < 0 ? fmt(Math.abs(r.summa)) : ""}</td></tr>`).join("");
			const tk = (res.rows || []).reduce((s, r) => s + (r.summa > 0 ? r.summa : 0), 0);
			const tc = (res.rows || []).reduce((s, r) => s + (r.summa < 0 ? -r.summa : 0), 0);
			const w = window.open("", "_blank");
			w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Kassa varag'i ${dmy(day)}</title><style>
				body{font-family:Arial,sans-serif;font-size:12px;margin:28px;color:#000}
				h2{text-align:center;margin:4px 0} .sub{text-align:center;margin-bottom:14px}
				table{width:100%;border-collapse:collapse;margin:10px 0}
				th,td{border:1px solid #000;padding:4px 6px} th{background:#f0f0f0}
				td.r{text-align:right;font-variant-numeric:tabular-nums} tr.b td{font-weight:bold}
				.sign{display:flex;justify-content:space-between;margin-top:36px;font-size:12px}
				.sign div{width:45%} .sign .l{border-bottom:1px solid #000;height:22px;margin-top:14px}
				@media print{button{display:none}}</style></head><body>
				<h2>KASSA VARAG'I (КО-4 uslubida)</h2>
				<div class="sub">Sana: <b>${dmy(day)} (${hk(day)})</b> · Valyuta: <b>${esc(res.currency)}</b> · Hisoblar: ${esc((st.accounts && st.accounts.length ? st.accounts : ["hammasi"]).join(", ").replace(/ - TZ/g, ""))}</div>
				<table><tr class="b"><td colspan="4">Kun boshidagi qoldiq</td><td class="r" colspan="2">${fmt(res.opening)}</td></tr></table>
				<table><thead><tr><th>№</th><th>Hujjat</th><th>Kimdan olindi / kimga berildi</th><th>Kategoriya</th><th>Kirim</th><th>Chiqim</th></tr></thead>
				<tbody>${rows || "<tr><td colspan=6>Harakat yo'q</td></tr>"}</tbody>
				<tfoot><tr class="b"><td colspan="4">Kun bo'yicha jami</td><td class="r">${fmt(tk)}</td><td class="r">${fmt(tc)}</td></tr>
				<tr class="b"><td colspan="4">Kun oxiridagi qoldiq</td><td class="r" colspan="2">${fmt(res.closing)}</td></tr></tfoot></table>
				<div>Hujjatlar soni: kirim — ${(res.rows || []).filter((r) => r.summa > 0 && !r.ichki).length} ta, chiqim — ${(res.rows || []).filter((r) => r.summa < 0 && !r.ichki).length} ta</div>
				<div class="sign"><div>Kassir: _______________<div class="l"></div>(F.I.Sh, imzo)</div>
				<div>Buxgalter: _______________<div class="l"></div>(F.I.Sh, imzo)</div></div>
				<button onclick="window.print()" style="margin-top:20px;padding:6px 18px">Chop etish</button>
				</body></html>`);
			w.document.close();
		};
		// КО-4 — RASMIY kunlik varaq: kategoriya/kontragent filtrisiz, to'liq kun
		const key = "ko4|" + day;
		if (st.dayDocs[key]) go(st.dayDocs[key]);
		else frappe.call({
			method: "target_zenit.target_zenit.api.kunlik_kassa.get_day_docs",
			args: { sana: day, currency: st.currency, accounts: JSON.stringify(st.accounts || []) },
		}).then((r) => { st.dayDocs[key] = r.message || { rows: [] }; go(st.dayDocs[key]); });
	}

	// ---------------------------------------------------------------- drill-down
	function loadDrill(tur, kat, party, $host) {
		if (!$host || !$host.length) return;
		$host.html(`<div class="kk-drill-box"><div class="kk-loader" style="padding:14px">Yuklanyapti…</div></div>`);
		frappe.call({
			method: "target_zenit.target_zenit.api.kunlik_kassa.get_breakdown",
			args: {
				from_date: st.from, to_date: st.to, currency: st.currency,
				accounts: JSON.stringify(st.accounts || []),
				tur: tur, kategoriya: kat, party: party,
			},
		}).then((r) => {
			const res = r.message || {};
			const color = tur === "Приход" ? C.good : C.bad;
			const nom = party || kat;
			const mx = Math.max(1, ...(res.top || []).map((x) => x.summa));
			const top = (res.top || []).length ? `<div class="kk-hbars">` + res.top.map((x) =>
				`<div class="hb"><div class="hb-t"><span title="${esc(x.label)}">${esc(x.label)}</span><b class="num">${fmt(x.summa)}</b></div>
				<div class="hb-track"><i style="width:${Math.max(2, x.summa / mx * 100)}%;background:${color}"></i></div></div>`).join("") + `</div>`
				: `<div class="kk-empty" style="padding:8px">yo'q</div>`;
			$host.html(`<div class="kk-drill-box">
				<div class="kk-drill-hd"><b>${esc(nom)}</b>
				<span class="meta">${tur === "Приход" ? "kirim" : "chiqim"} · jami <b class="num">${fmt(res.jami)}</b> · ${res.n || 0} hujjat</span>
				<button class="kk-drill-x" data-drill-close title="Yopish">✕</button></div>
				<div class="kk-drill-grid"><div>${miniBars(res.days || [], (x) => x.summa, color)}</div>
				<div><div class="kk-subtitle">${kat ? "Kontragentlar" : "Kategoriyalar"}</div>${top}</div></div></div>`);
			if ($host[0] && $host[0].scrollIntoView) $host[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
		}).catch(() => $host.html(`<div class="kk-drill-box"><div class="kk-empty">Tafsilotni yuklab bo'lmadi.</div></div>`));
	}

	// ---------------------------------------------------------------- hodisalar
	function wire() {
		$root.off(".kk");          // har render'da delegated handlerlar dublikat bo'lmasin
		// KPI kartalari — Kirim/Chiqim kassa kitobi jadvalini filtrlaydi
		$root.find("[data-kpi-tur]").on("click", function () {
			const t = String($(this).attr("data-kpi-tur"));
			st.tur = st.tur === t ? "" : t;
			st.selDay = null; load();
		});
		$root.find("[data-kpi-day]").on("click", function () {
			const day = String($(this).attr("data-kpi-day") || "");
			if (day) { st.selDay = day; openDay(day, true); }
		});
		// Operatsiya turi segmenti (filtr panelida)
		$root.find(".kk-seg button[data-tur]").on("click", function () {
			st.tur = String($(this).attr("data-tur") || "");
			st.selDay = null; load();
		});
		// Diagramma elementlari — bosilganda shu karta ichida tafsilot ochiladi
		$root.on("click.kk", ".hb.click, .kk-wf-hit[data-kat]", function () {
			const $el = $(this);
			const tur = String($el.attr("data-tur") || "");
			const kat = String($el.attr("data-kat") || "");
			const party = String($el.attr("data-party") || "");
			if (!tur || (!kat && !party)) return;
			const $card = $el.closest(".kk-card");
			$card.find(".hb.click").removeClass("active");
			if ($el.hasClass("hb")) $el.addClass("active");
			loadDrill(tur, kat, party, $card.find(".kk-drill").first());
		});
		$root.on("click.kk", "[data-drill-close]", function (e) {
			e.stopPropagation();
			const $card = $(this).closest(".kk-card");
			$card.find(".kk-drill").first().empty();
			$card.find(".hb.click").removeClass("active");
		});
		$root.find("[data-preset]").on("click", function () {
			presetDates(String($(this).data("preset"))); st.selDay = null; load();
		});
		$root.find("input.kk-date").on("change", function () {
			const k = $(this).data("d") === "from" ? "from" : "to";
			st[k] = $(this).val(); st.preset = ""; st.selDay = null; load();
		});
		$root.find("[data-ccy]").on("click", function () {
			st.currency = String($(this).data("ccy")); st.accounts = null; st.selDay = null; load();
		});
		$root.find("[data-acc-all]").on("click", function () {
			st.accounts = null; st.selDay = null; load();
		});
		// Hisob chiplari — ODDIY bosish bilan ko'p tanlov: "Hammasi" holatida
		// birinchi bosish faqat o'shani tanlaydi, keyingilari qo'shadi/olib tashlaydi
		$root.find("[data-acc]").on("click", function () {
			const a = String($(this).attr("data-acc"));
			const hamma = (st.data.accounts || []).filter((x) => x.currency === st.data.currency).map((x) => x.account);
			if (!st.accounts || !st.accounts.length) {
				st.accounts = [a];                       // hammasidan -> faqat shu
			} else {
				const sel = st.accounts.slice();
				const i = sel.indexOf(a);
				if (i === -1) sel.push(a); else sel.splice(i, 1);
				st.accounts = (!sel.length || sel.length === hamma.length) ? null : sel;
			}
			st.selDay = null; load();
		});
		// Kontragent turi / kategoriya / kontragent filtrlari
		$root.find("select.kk-sel").on("change", function () {
			const f = String($(this).data("f"));
			const v = String($(this).val());
			if (f === "kat") st.kat = v;
			else if (f === "ptype") st.ptype = v;
			else st.party = v;
			st.selDay = null; load();
		});
		$root.find(".kk-limit-inp").on("change", function () {
			const v = Number(String($(this).val()).replace(/[^\d.-]/g, "")) || 0;
			try { localStorage.setItem(limitKey(), String(v)); } catch (e) { /* xotira yopiq */ }
			render();
		});
		$root.find(".kk-refresh").on("click", () => { st.dayDocs = {}; load(); });
		$root.on("click.kk", "tr.kk-day", function (e) {
			if ($(e.target).closest("[data-ko4]").length) return;
			const day = String($(this).data("day"));
			const $docs = $root.find(`tr[data-docs="${day}"]`);
			if ($docs.is(":visible")) { $docs.hide(); $(this).removeClass("open sel"); return; }
			openDay(day, false);
		});
		$root.on("click.kk", "[data-ko4]", function (e) {
			e.stopPropagation(); printKo4(String($(this).attr("data-ko4")));
		});
		$root.on("click.kk", ".kk-day-hit, .kk-heat-cell[data-day]", function () {
			const day = String($(this).data("day") || $(this).attr("data-day") || "");
			if (day) { tipHide(); st.selDay = day; openDay(day, true); }
		});
		// Kuzatuvchi tooltip — oqim (kun/hafta), qoldiq ustunlari va heatmap kataklari
		$root.on("mousemove.kk", ".kk-day-hit, .kk-heat-cell[data-day]", function (ev) {
			const bi = $(this).attr("data-bucket");
			if (bi !== undefined && st.flowBuckets) {
				const b = st.flowBuckets[Number(bi)];
				if (b) {
					const title = b.hafta ? `${dmy(b.dan)} – ${dmy(b.gacha)} (hafta)` : `${dmy(b.dan)} · ${hk(b.dan)}`;
					tipShow(`<div class="t">${title}</div>
						<div class="row"><i style="background:${C.good}"></i>Kirim <b>${fmt(b.kirim)}</b></div>
						<div class="row"><i style="background:${C.bad}"></i>Chiqim <b>${fmt(b.chiqim)}</b></div>
						<div class="row"><i style="background:${C.blue}"></i>Sof oqim <b>${pm(b.net)}</b></div>
						<div class="q">Oxiridagi qoldiq: <b>${fmt(b.balans)}</b> · ${b.n} hujjat</div>`, ev);
					return;
				}
			}
			const day = String($(this).attr("data-day") || "");
			const x = ((st.data && st.data.days) || []).find((q) => q.sana === day);
			if (x) tipShow(dayTip(x), ev);
		});
		$root.on("mouseleave.kk", ".kk-day-hit, .kk-heat-cell[data-day]", tipHide);
	}

	load();
}
