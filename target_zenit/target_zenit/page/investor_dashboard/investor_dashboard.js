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
		this.months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
		this.tabs = [
			{ key: "overview", label: "Umumiy" },
			{ key: "cashflow", label: "Kassa va pul oqimi" },
			{ key: "debts", label: "Qarzdorlik" },
			{ key: "dds", label: "Pul oqimi (DDS)" },
			{ key: "tuition", label: "O'quvchilar to'lovi" },
			{ key: "pnl", label: "Foyda (P&L)" },
		];
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
		// o'quvchilar to'lovi jadvali — ko'rinishni almashtirish (segment toggle)
		body.on("click", "[data-tv]", (e) => {
			const v = String($(e.currentTarget).data("tv"));
			if (this.tuitionView === v) return;
			this.tuitionView = v;
			this.renderTab();
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
		const fn = { overview: "renderOverview", cashflow: "renderCashflow", debts: "renderDebts", dds: "renderDds", tuition: "renderTuition", pnl: "renderPnl" }[this.active];
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
		const o = this.data.overview, ccy = this.ccyLabel(this.data.meta.currency);
		let h = this.sec("Asosiy ko'rsatkichlar", "Bir xil rangda — kassa qoldiqlaridan farqli");
		h += `<div class="grid cols-5 mb">
			${this.moneyKpi({ label: "Debitorka (bizga qarz)", raw: o.receivable.value, cmp: o.receivable, invert: true, pin: "var(--brand)", valColor: "var(--brand-ink)" })}
			${this.moneyKpi({ label: "Kreditorka (biz qarz)", raw: o.payable.value, cmp: o.payable, invert: true, pin: "var(--brand)", valColor: "var(--brand-ink)" })}
			${this.kpi({ label: "Faol o'quvchilar", value: this.fmt(o.active_students), pin: "var(--brand)", valColor: "var(--brand-ink)", noBadge: true, sub: o.collection_rate != null ? `To'lov yig'imi ${o.collection_rate}%` : "To'lov ma'lumoti cheklangan" })}
			${this.kpi({ label: "Shartnoma qilinganlar", value: this.fmt(o.contracted_students), pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true, sub: `faol o'quvchilar ichida${o.active_students ? ` · ${Math.round((o.contracted_students || 0) / o.active_students * 100)}%` : ""}` })}
			${this.moneyKpi({ label: "Davr xarajati", raw: o.expense.value, cmp: o.expense, invert: true, pin: "var(--brand)", valColor: "var(--brand-ink)" })}
		</div>`;

		h += this.sec("Kassa hisoblari (shotlar)", `${this.data.meta.period.label} oxiriga qoldiq · har shot alohida`);
		const accs = o.cash_accounts || [];
		h += accs.length
			? `<div class="grid cols-4 mb">` + accs.map((a, i) => this.cashAccCard(a, i)).join("") + `</div>`
			: this.card(`<div class="empty-hint">Kassa hisoblari topilmadi.</div>`, "mb");
		return h + this.note();
	}

	cashAccCard(a, i) {
		const col = this.acctColors[i % this.acctColors.length];
		const isForeign = a.currency !== this.data.meta.currency;
		const neg = a.closing < 0;
		return `<div class="card kpi acct" style="border-top:3px solid ${col}">
			<div class="lab"><span class="pin" style="background:${col}"></span> ${this.esc(this.acctName(a.account))}</div>
			<div class="val num" style="color:${neg ? "var(--bad-ink)" : col}" data-tt="${this.fmt(a.closing)} ${this.esc(a.currency)}">${this.kc(a.closing)} <span class="cur">${this.ccyLabel(a.currency)}</span></div>
			<div class="sub">${this.esc(a.mode || "—")}${isForeign ? ` · <b>${this.esc(a.currency)}</b>` : ""}</div>
		</div>`;
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
		const cf = this.data.cashflow, ccy = this.ccyLabel(this.data.meta.currency);
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
		const selected = this.cfFlow || this.budgetView || this.cfCcy;
		if (this.cfFlow) {
			h += this.flowDetailTable(cf, this.cfFlow);
		} else if (this.budgetView) {
			h += this.budgetBreakdown(cf);
		} else {
			h += this.accountsTable(cf);   // cfCcy bo'lsa shu valyuta bo'yicha, aks holda hammasi
		}

		// Grafiklar faqat hech narsa tanlanmaganda (default holat)
		if (!selected) {
			h += `<div class="grid cols-2 mb">
				${this.card(`<div class="hd"><div><h3>Kirim manbalari</h3><div class="meta">Pul qayerdan keldi</div></div></div>${this.hbars(cf.categories.in, "var(--good)")}`)}
				${this.card(`<div class="hd"><div><h3>Chiqim yo'nalishlari</h3><div class="meta">Pul qayerga ketdi</div></div></div>${this.hbars(cf.categories.out, "var(--bad)")}`)}
			</div>`;
			h += `<div class="grid cols-2 mb">
				${this.card(`<div class="hd"><div><h3>Kirim va chiqim — 12 oy</h3><div class="meta">mln ${ccy}</div></div>
					<div class="legend"><div class="it"><span class="sw" style="background:var(--good)"></span> Kirim</div><div class="it"><span class="sw" style="background:var(--bad)"></span> Chiqim</div></div></div>
					${this.lineChart(cf.monthly.months, [{ data: cf.monthly.expense, color: "var(--bad)", fill: true }, { data: cf.monthly.income, color: "var(--good)", fill: true }])}`)}
				${this.calendarCard(cf.daily)}
			</div>`;
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
	accountsTable(cf) {
		let accts = cf.accounts || [];
		if (this.cfCcy) accts = accts.filter((a) => a.currency === this.cfCcy);
		const rows = accts.length ? accts.map((a) => `
			<tr><td class="ell" data-tt="${this.esc(a.account)}">${this.esc(this.acctName(a.account))}</td>
			<td class="ell">${this.esc(a.mode || "")}</td>
			<td class="r num">${this.fmt(a.opening)}${a.currency !== this.data.meta.currency ? " " + this.esc(a.currency) : ""}</td>
			<td class="r num" style="color:var(--good-ink)">${this.fmt(a.kirim)}</td>
			<td class="r num" style="color:var(--bad-ink)">${this.fmt(a.chiqim)}</td>
			<td class="r num" style="font-weight:700">${this.fmt(a.closing)}</td></tr>`).join("")
			: `<tr><td colspan="6" class="empty-hint">Hisob topilmadi.</td></tr>`;
		return this.card(`
			<div class="hd"><div><h3>Hisoblar kesimida${this.cfCcy ? ` · ${this.esc(this.cfCcy)}` : ""}</h3><div class="meta">Kirim/chiqim ichki o'tkazmasiz (konvertatsiya/ko'chirma) · yakun — haqiqiy qoldiq</div></div></div>
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
		h += `<div class="grid mb" style="grid-template-columns:1fr 1fr">
			${this.moneyKpi({ label: "Jami debitorka (bizga qarz)", raw: d.receivable_total, cmp: d.receivable_cmp, invert: true, pin: "var(--warn)", valColor: "var(--warn-ink)" })}
			${this.moneyKpi({ label: "Jami kreditorka (biz qarz)", raw: d.payable_total, cmp: d.payable_cmp, invert: true, pin: "var(--c5)" })}
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
		}).catch(() => body.html(`<div class="empty-hint">Kontragent ma'lumotini yuklab bo'lmadi.</div>`));
	}

	renderKontragentTable(k) {
		const rows = k.rows || [];
		if (!rows.length) return `<div class="empty-hint" style="padding:22px 8px">Tanlangan filtr bo'yicha harakat topilmadi.</div>`;
		const bal = (cr, dr) => {
			if (cr > 0.5) return `<span class="num" style="color:var(--c5)">${this.fmt(cr)} <small>Kт</small></span>`;
			if (dr > 0.5) return `<span class="num" style="color:var(--warn-ink)">${this.fmt(dr)} <small>Дт</small></span>`;
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
				<td class="r">${bal(t.opening_credit, t.opening_debit)}</td>
				<td class="r num" style="color:var(--c5)">${this.fmt(t.period_credit)}</td>
				<td class="r num" style="color:var(--warn-ink)">${this.fmt(t.period_debit)}</td>
				<td class="r">${bal(t.final_credit, t.final_debit)}</td>
			</tr>`).join("");
		return `
			<div class="kt-legend"><b>Kт</b> — biz qarzmiz (kreditor) · <b>Дт</b> — bizga qarzdor (debitor)</div>
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
		const t = this.data.tuition, ccy = this.ccyLabel(this.data.meta.currency);
		const p = (t && t.payments) || { by_currency: [], students: [], recent: [], total_count: 0, total_students: 0 };
		// summa: so'm butun (kasrsiz), boshqa valyuta 2 kasr bilan
		const m2 = (n) => { n = Number(n) || 0; const neg = n < 0 ? "−" : ""; const a = Math.abs(n).toFixed(2).split("."); return neg + a[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ") + "," + a[1]; };
		const mAmt = (n, c) => (c === "UZS" ? this.fmt(n) : m2(n));
		const main = (p.by_currency || [])[0] || null;   // eng katta valyuta buketi (asosan so'm)
		let h = this.sec("O'quvchilar to'lovi", `To'lovlar (Payment Entry) asosida · kassaga tushgan real pul · ${this.esc(this.data.meta.period.label)}`);

		// ---- To'lov KPI'lari ----
		h += `<div class="grid cols-5 mb">
			${this.kpi({ label: "Faol o'quvchilar", value: this.fmt(t.active), pin: "var(--c2)", noBadge: true, sub: "jami ro'yxatda" })}
			${this.kpi({ label: "Shartnoma qilinganlar", value: this.fmt(t.contracted), pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true, sub: `faol ichida${t.active ? ` · ${Math.round((t.contracted || 0) / t.active * 100)}%` : ""}` })}
			${this.kpi({ label: "Davr to'lovlari", value: this.fmt(p.total_count), pin: "var(--brand)", valColor: "var(--brand-ink)", noBadge: true, sub: "ta to'lov yozuvi" })}
			${this.kpi({ label: "To'lagan o'quvchilar", value: this.fmt(p.total_students), pin: "var(--c1)", noBadge: true, sub: "shu davrda" })}
			${this.kpi({ label: "Davr yig'imi", value: (main ? mAmt(main.total, main.currency) : "0"), unit: main ? " " + this.esc(main.currency) : "", pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true, sub: (p.by_currency || []).length > 1 ? "boshqa valyuta pastda" : "kassaga tushgan" })}
		</div>`;

		// ---- Valyuta kesimi (KICHIK — chip ko'rinishida, cardga sig'adi) ----
		const ccyChips = (p.by_currency || []).length
			? p.by_currency.map((b) => `<span class="ccy-chip"><b>${this.esc(b.currency)}</b> <b style="color:var(--good-ink)">${mAmt(b.total, b.currency)}</b> <span style="color:var(--muted);font-size:12px">· ${b.count} to'lov · ${b.students} o'quvchi</span></span>`).join("")
			: `<span class="empty-hint">Davrda to'lov yo'q.</span>`;
		h += this.card(`<div class="hd"><div><h3>Davr yig'imi — valyuta kesimida</h3><div class="meta">kassaga tushgan real pul, konvertatsiyasiz</div></div></div>
			<div style="display:flex;flex-wrap:wrap;gap:10px;padding:2px">${ccyChips}</div>`, "mb");

		// ---- BITTA jadval + toggle: o'quvchilar kesimi (default) ⇄ har bir to'lov ----
		const view = this.tuitionView === "payments" ? "payments" : "students";
		let title, meta, thead, tbodyRows;
		if (view === "students") {
			title = "O'quvchilar kesimi — har biri qancha to'lagan";
			meta = `ko'pdan kamga · <span class="tz-stud-count">${(p.students || []).length}</span> ta o'quvchi`;
			thead = `<tr><th class="r">#</th><th>O'quvchi</th><th class="r">To'lovlar</th><th class="r">Jami</th><th class="r">Oxirgi</th></tr>`;
			tbodyRows = (p.students || []).length
				? p.students.map((s, i) => `<tr data-sname="${this.esc(String(s.name || "").toLowerCase())}">
					<td class="r num" style="color:var(--muted)">${i + 1}</td>
					<td class="ell" data-tt="${this.esc(s.name)}">${this.esc(s.name)}</td>
					<td class="r num">${s.count}</td>
					<td class="r num" style="font-weight:700">${mAmt(s.total, s.currency)} ${this.esc(s.currency)}</td>
					<td class="r">${this.esc(s.last_date || "")}</td></tr>`).join("")
				: `<tr><td colspan="5" class="empty-hint">Ma'lumot yo'q.</td></tr>`;
		} else {
			title = "Har bir to'lov — izohlari bilan";
			meta = `har bir to'lov · <span class="tz-stud-count">${(p.recent || []).length}</span> ta · kassir izohi (Kassa)`;
			thead = `<tr><th>Sana</th><th>O'quvchi</th><th class="r">Summa</th><th>Usul</th><th>Izoh</th><th>Kassa</th></tr>`;
			tbodyRows = (p.recent || []).length
				? p.recent.map((r) => `<tr data-sname="${this.esc(String(r.student || "").toLowerCase())}">
					<td>${this.esc(r.date)}</td>
					<td class="ell" data-tt="${this.esc(r.student)}">${this.esc(r.student)}</td>
					<td class="r num" style="color:var(--good-ink);font-weight:700">${mAmt(r.amount, r.currency)} ${this.esc(r.currency)}${r.orig_currency && r.orig_currency !== r.currency ? `<div style="font-size:11px;color:var(--muted);font-weight:400">o'quvchi: ${mAmt(r.orig_amount, r.orig_currency)} ${this.esc(r.orig_currency)}</div>` : ""}</td>
					<td class="ell">${this.esc(r.mode)}</td>
					<td style="max-width:340px;white-space:normal;color:var(--muted);font-size:12px" data-tt="${this.esc(r.remarks)}">${this.esc(r.remarks).replace(/\n/g, " · ")}</td>
					<td>${r.ref ? `<a class="tz-kassa-link" href="/app/kassa/${encodeURIComponent(r.ref)}" target="_blank" rel="noopener">${this.esc(r.ref)}</a>` : "—"}</td>
				</tr>`).join("")
				: `<tr><td colspan="6" class="empty-hint">To'lov topilmadi.</td></tr>`;
		}
		const seg = `<div class="tz-seg" role="tablist">
				<button class="tz-seg-opt${view === "students" ? " on" : ""}" data-tv="students">O'quvchilar kesimi</button>
				<button class="tz-seg-opt${view === "payments" ? " on" : ""}" data-tv="payments">Har bir to'lov</button>
			</div>`;
		h += this.card(`<div class="hd tz-tuition-hd">
				<div><h3>${title}</h3><div class="meta">${meta}</div></div>
				<div class="tz-tuition-tools">
					<input type="text" class="tz-stud-filter" placeholder="O'quvchi qidirish…" autocomplete="off">
					${seg}
				</div>
			</div>
			<div class="tbl-wrap"><table><thead>${thead}</thead><tbody>${tbodyRows}</tbody></table></div>`, "mb");

		// ---- Agar Education Fees ham ishlatilsa — billing bloklari qo'shiladi ----
		if (t.available) {
			h += `<div class="grid cols-4 mb">
				${this.moneyKpi({ label: "Hisoblangan (billed)", raw: t.billed, pin: "var(--c1)", noBadge: true })}
				${this.moneyKpi({ label: "Yig'ilgan (collected)", raw: t.collected, pin: "var(--good)", valColor: "var(--good-ink)", noBadge: true })}
				${this.kpi({ label: "Yig'im foizi", value: (t.rate != null ? t.rate : "—"), unit: t.rate != null ? "%" : "", pin: "var(--warn)", noBadge: true, sub: `Qoldiq qarz ${this.kc(t.outstanding)} ${ccy}` })}
				${this.kpi({ label: "Fees yozuvi", value: this.fmt(t.with_fees), pin: "var(--c2)", noBadge: true, sub: "ta o'quvchida" })}
			</div>`;
			const st = t.status, tot = st.paid + st.partial + st.debtor;
			const donut = tot ? `<div class="donut-wrap">
				${this.donutSvg([{ pct: st.paid / tot * 100 }, { pct: st.partial / tot * 100 }, { pct: st.debtor / tot * 100 }], ["var(--good)", "var(--warn)", "var(--bad)"], `${Math.round(st.paid / tot * 100)}%`, "to'ladi")}
				<div class="legend" style="flex-direction:column;gap:11px">
					<div class="it"><span class="sw" style="background:var(--good)"></span> To'liq to'ladi <b>${st.paid} ta</b></div>
					<div class="it"><span class="sw" style="background:var(--warn)"></span> Qisman <b>${st.partial} ta</b></div>
					<div class="it"><span class="sw" style="background:var(--bad)"></span> Qarzdor <b>${st.debtor} ta</b></div>
				</div></div>` : `<div class="empty-hint">To'lov holati ma'lumoti yo'q.</div>`;
			h += `<div class="grid cols-2 mb">
				${this.card(`<div class="hd"><div><h3>To'lov holati</h3><div class="meta">${tot} o'quvchi</div></div></div>${donut}`)}
				${this.classCard(t.by_class)}
			</div>`;
			h += this.partyTable("Eng katta qarzdor o'quvchilar", t.top_debtors, "var(--bad-ink)");
		}
		return h + this.note();
	}

	partyTable(title, top, color) {
		const rows = (top || []).length ? top.map((t) => `<tr><td class="ell" data-tt="${this.esc(t.name)}">${this.esc(t.name)}</td><td class="r num" style="color:${color}">${this.fmt(t.amount)}</td></tr>`).join("")
			: `<tr><td colspan="2" class="empty-hint">Ma'lumot yo'q.</td></tr>`;
		return this.card(`<div class="hd"><div><h3>${this.esc(title)}</h3></div></div><table><tbody>${rows}</tbody></table>`);
	}

	classCard(items) {
		if (!items || !items.length) return this.card(`<div class="hd"><div><h3>Sinf kesimi</h3></div></div><div class="empty-hint">Sinf bo'yicha ma'lumot yo'q.</div>`);
		const rows = items.map((c) => `
			<tr><td class="ell" data-tt="${this.esc(c.label)}">${this.esc(c.label)}</td>
			<td class="r num">${c.students}</td>
			<td class="r num">${this.kc(c.collected)} / ${this.kc(c.billed)}</td>
			<td class="r"><div class="mini-prog"><span style="width:${Math.min(100, c.rate)}%"></span></div><small class="num">${c.rate}%</small></td></tr>`).join("");
		return this.card(`<div class="hd"><div><h3>Sinf bo'yicha yig'im</h3><div class="meta">yig'ilgan / hisoblangan · foiz</div></div></div>
			<div class="tbl-wrap"><table><thead><tr><th>Sinf</th><th class="r">O'quvchi</th><th class="r">Yig'ilgan/Hisoblangan</th><th class="r">Foiz</th></tr></thead><tbody>${rows}</tbody></table></div>`);
	}

	// ================= TAB: P&L =================
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

	// ================= footer note =================
	note() {
		const w = (this.data.meta.warnings || []);
		const wh = w.length ? `<b>Diqqat:</b> ${w.map((x) => this.esc(x)).join(" ")} ` : "";
		return `<div class="note">${wh}Barcha raqamlar real vaqtda ERPNext'dan (GL Entry): kassa — Mode of Payment hisoblari; debitorka/kreditorka va kontragent — Receivable/Payable; foyda — Income/Expense; o'quvchi to'lovi — Education Fees; xodim avansi — Employee Advance. Budjet bo'linishi Chart of Accounts guruhiga tayanadi.</div>`;
	}
}
