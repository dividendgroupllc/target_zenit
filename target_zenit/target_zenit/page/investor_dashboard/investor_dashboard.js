// Copyright (c) 2026, Target Zenit — Investor paneli (professional, bo'limli)
frappe.pages["investor-dashboard"].on_page_load = function (wrapper) {
	new TZInvestorDashboard(wrapper);
};

class TZInvestorDashboard {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Investor paneli"), single_column: true });
		const d = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());
		this.state = { year: d.getFullYear(), month: d.getMonth() + 1 };
		this.data = null;
		this.active = "overview";
		this.months_uz = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
		this.tabs = [
			{ key: "overview", label: "Umumiy" },
			{ key: "cashflow", label: "Kassa va pul oqimi" },
			{ key: "debts", label: "Qarzdorlik" },
			{ key: "tuition", label: "O'quvchilar to'lovi" },
			{ key: "pnl", label: "Foyda (P&L)" },
		];
		this.make_skeleton();
		this.load_years();
		this.load_data();
	}

	// ================= helpers =================
	ccyLabel(c) { return c === "UZS" ? "so'm" : (c || ""); }
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }

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
		const invert = !!opt.invert, label = opt.label || "o'tgan oyga", p = cmp.delta_pct;
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
		// Butun ekranni to'ldirish: desk container max-width va padding cheklovini olib tashlash
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.page.main.removeClass("frappe-card");
		this.page.main.html(`
			<div class="topbar">
				<div><h1>Investor paneli</h1><div class="sub tz-ctx"></div></div>
				<div class="spacer"></div>
				<select class="form-control tz-year" style="width:auto;min-width:88px"></select>
				<select class="form-control tz-month" style="width:auto;min-width:118px"></select>
				<button class="refresh tz-refresh"><span class="dot"></span> Yangilash</button>
			</div>
			<div class="tabnav tz-tabs"></div>
			<div class="tz-future" style="display:none"></div>
			<div class="tz-body"><div class="tz-loader">Ma'lumot yuklanyapti…</div></div>
		`);
		const mo = this.page.main.find(".tz-month");
		this.months_uz.forEach((m, i) => mo.append(`<option value="${i + 1}">${m}</option>`));
		mo.val(this.state.month).on("change", () => { this.state.month = parseInt(mo.val()); this.load_data(); });
		this.page.main.find(".tz-year").on("change", (e) => { this.state.year = parseInt(e.target.value); this.load_data(); });
		this.page.main.find(".tz-refresh").on("click", () => this.load_data());
		const nav = this.page.main.find(".tz-tabs");
		this.tabs.forEach((t) => nav.append(`<button data-k="${t.key}" class="${t.key === this.active ? "on" : ""}">${t.label}</button>`));
		nav.on("click", "button", (e) => {
			this.active = $(e.currentTarget).data("k");
			nav.find("button").removeClass("on");
			$(e.currentTarget).addClass("on");
			this.renderTab();
		});
	}

	load_years() {
		frappe.call({ method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_years" }).then((r) => {
			const years = (r.message && r.message.length) ? r.message : [this.state.year];
			const sel = this.page.main.find(".tz-year").empty();
			years.forEach((y) => sel.append(`<option value="${y}">${y}</option>`));
			if (years.indexOf(this.state.year) < 0) this.state.year = years[0];
			sel.val(this.state.year);
		});
	}

	load_data() {
		this.page.main.find(".tz-body").html(`<div class="tz-loader">Ma'lumot yuklanyapti…</div>`);
		frappe.call({
			method: "target_zenit.target_zenit.page.investor_dashboard.investor_dashboard.get_dashboard_data",
			args: { year: this.state.year, month: this.state.month },
		}).then((r) => { this.data = r.message || {}; this.afterLoad(); })
			.catch(() => this.page.main.find(".tz-body").html(`<div class="empty-hint">Ma'lumotni yuklab bo'lmadi.</div>`));
	}

	afterLoad() {
		const m = this.data.meta || {};
		this.page.main.find(".tz-ctx").text(
			`${m.company || ""} · ${m.period ? m.period.label : ""} · taqqoslash: ${m.prev_label || ""} va ${m.yoy_label || ""}-yil`);
		const fb = this.page.main.find(".tz-future");
		if (m.is_future) fb.show().html(`⚠️ Tanlangan oy kelajakda — ba'zi ko'rsatkichlar hali to'lmagan.`);
		else fb.hide();
		this.renderTab();
	}

	renderTab() {
		if (!this.data || !this.data.meta) return;
		const body = this.page.main.find(".tz-body");
		const fn = { overview: "renderOverview", cashflow: "renderCashflow", debts: "renderDebts", tuition: "renderTuition", pnl: "renderPnl" }[this.active];
		body.html(this[fn]());
		body.find("[data-tt]").each((i, el) => { $(el).attr("title", $(el).data("tt")); });
	}

	// ================= UI atoms =================
	card(inner, cls) { return `<div class="card ${cls || ""}">${inner}</div>`; }
	sec(title, sub) { return `<div class="sec-h"><h2>${this.esc(title)}</h2>${sub ? `<span>${this.esc(sub)}</span>` : ""}</div>`; }

	kpi(o) {
		const badges = [this.badge(o.cmp, { invert: o.invert }), o.cmpYoy ? this.badge(o.cmpYoy, { invert: o.invert, label: (this.data.meta.yoy_label || "") + "-yilga" }) : ""].filter(Boolean).join("");
		return this.card(`
			<div class="lab"><span class="pin" style="background:${o.pin || "var(--brand)"}"></span> ${this.esc(o.label)}</div>
			<div class="val num" ${o.valColor ? `style="color:${o.valColor}"` : ""} ${o.tt ? `data-tt="${this.esc(o.tt)}"` : ""}>${o.value}${o.unit ? ` <span class="cur">${o.unit}</span>` : ""}</div>
			${o.sub ? `<div class="sub num">${o.sub}</div>` : ""}
			<div class="badges">${badges || "<span class='muted-s'>taqqoslash yo'q</span>"}</div>
		`, "kpi");
	}

	moneyKpi(o) { // pul KPI — kompakt + to'liq tooltip
		o.value = this.kc(o.raw);
		o.unit = o.unit || this.ccyLabel(this.data.meta.currency);
		o.tt = this.fmt(o.raw) + " " + this.ccyLabel(this.data.meta.currency);
		return this.kpi(o);
	}

	// horizontal bars list
	hbars(items, color) {
		if (!items || !items.length) return `<div class="empty-hint">Ma'lumot yo'q.</div>`;
		const max = Math.max(1, ...items.map((i) => Math.abs(i.amount)));
		return `<div class="hbars">` + items.map((it) => `
			<div class="hb">
				<div class="hb-t"><span>${this.esc(it.label)}</span><b class="num" data-tt="${this.fmt(it.amount)}">${this.kc(it.amount)}</b></div>
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

	lineChart(labels, series) { // series: [{name,data,color,fill}]
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

	barChart(labels, values, opt) { // ijobiy/salbiy ranglar
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

	trendStrip(trend) {
		if (!trend || !trend.length) return `<div class="empty-hint">Dinamika yo'q.</div>`;
		const max = Math.max(1, ...trend.map((t) => Math.abs(t.value)));
		return `<div class="trend">` + trend.map((t, i) => {
			const up = i === 0 || t.value >= trend[i - 1].value, h = Math.max(6, Math.abs(t.value) / max * 100);
			return `<div class="b ${up ? "up" : "dn"}" style="height:${h}%" data-tt="${this.esc(t.label)}: ${this.fmt(t.value)}"></div>`;
		}).join("") + `</div>`;
	}

	// ================= TAB: Overview =================
	renderOverview() {
		const o = this.data.overview, ccy = this.ccyLabel(this.data.meta.currency);
		let h = "";
		h += this.sec("Asosiy ko'rsatkichlar", `${this.data.meta.period.label} holatiga`);
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Sof balans (pozitsiya)", raw: o.net_balance.value, cmp: o.net_balance, pin: "var(--brand)", valColor: o.net_balance.value < 0 ? "var(--bad-ink)" : "" })}
			${this.moneyKpi({ label: "Umumiy kassa qoldig'i", raw: o.cash.value, cmp: o.cash, cmpYoy: o.cash_yoy, pin: "var(--c1)", sub: this.otherCash(o.cash_other) })}
			${this.moneyKpi({ label: "Oylik daromad", raw: o.income.value, cmp: o.income, cmpYoy: o.income_yoy, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.moneyKpi({ label: "Oylik xarajat", raw: o.expense.value, cmp: o.expense, cmpYoy: o.expense_yoy, invert: true, pin: "var(--bad)", valColor: "var(--bad-ink)" })}
		</div>`;
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Sof foyda", raw: o.net_profit.value, cmp: o.net_profit, cmpYoy: o.net_profit_yoy, pin: "var(--good)", valColor: o.net_profit.value < 0 ? "var(--bad-ink)" : "var(--good-ink)", sub: o.margin != null ? `Rentabellik ${o.margin}%` : "Rentabellik —" })}
			${this.moneyKpi({ label: "Debitorka (bizga qarz)", raw: o.receivable.value, cmp: o.receivable, invert: true, pin: "var(--warn)" })}
			${this.moneyKpi({ label: "Kreditorka (biz qarz)", raw: o.payable.value, cmp: o.payable, invert: true, pin: "var(--c5)" })}
			${this.kpi({ label: "Faol o'quvchilar", value: this.fmt(o.active_students), pin: "var(--c2)", sub: o.collection_rate != null ? `To'lov yig'imi ${o.collection_rate}%` : "To'lov ma'lumoti cheklangan" })}
		</div>`;

		// net position + trend
		const c = o.components;
		h += `<div class="grid cols-2 mb">
			${this.card(`
				<div class="hd"><div><h3>Sof moliyaviy pozitsiya</h3><div class="meta">Nimadan tashkil topgan</div></div></div>
				<div class="pos">
					<div class="pos-row"><span>Kassa (naqd + bank)</span><b class="num">${this.fmt(c.cash)}</b></div>
					<div class="pos-row"><span>+ Debitorka</span><b class="num" style="color:var(--good-ink)">+${this.fmt(c.receivable)}</b></div>
					<div class="pos-row"><span>− Kreditorka</span><b class="num" style="color:var(--bad-ink)">−${this.fmt(c.payable)}</b></div>
					<div class="pos-row"><span>− Xodim avanslari</span><b class="num" style="color:var(--bad-ink)">−${this.fmt(c.employee)}</b></div>
					<div class="pos-total"><span>SOF BALANS</span><b class="num">${this.fmt(o.net_balance.value)} ${ccy}</b></div>
				</div>`)}
			${this.card(`
				<div class="hd"><div><h3>Kassa qoldig'i dinamikasi</h3><div class="meta">Oxirgi 12 oy · ${ccy}</div></div></div>
				<div class="trend-lab">Har oy oxiridagi umumiy kassa</div>
				${this.trendStrip(o.balance_trend)}
				<div class="mini-legend"><span class="up-s"></span> o'sdi &nbsp; <span class="dn-s"></span> kamaydi</div>`)}
		</div>`;
		return h + this.note();
	}

	otherCash(arr) { return (!arr || !arr.length) ? "Yagona valyuta" : arr.map((o) => `+ ${this.kc(o.closing)} ${o.currency}`).join(" · "); }

	// ================= TAB: Cashflow =================
	renderCashflow() {
		const cf = this.data.cashflow, ccy = this.ccyLabel(this.data.meta.currency), t = cf.total;
		let h = this.sec("Kassa harakati", `${this.data.meta.period.label} · ochilish → kirim → chiqim → yopilish`);
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Oy boshidagi qoldiq", raw: t.opening, pin: "var(--muted)" })}
			${this.moneyKpi({ label: "Oylik kirim", raw: t.kirim, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.moneyKpi({ label: "Oylik chiqim", raw: t.chiqim, pin: "var(--bad)", valColor: "var(--bad-ink)" })}
			${this.moneyKpi({ label: "Oy oxiridagi qoldiq", raw: t.closing, pin: "var(--brand)" })}
		</div>`;

		// per-currency totals: Jami USD / Jami UZS ...
		h += this.ccyTotals(cf.by_currency);

		// accounts table
		const rows = (cf.accounts || []).length ? cf.accounts.map((a) => `
			<tr><td class="ell" data-tt="${this.esc(a.account)}">${this.esc(a.account)}</td>
			<td class="ell">${this.esc(a.mode || "")}</td>
			<td class="r num">${this.fmt(a.opening)}${a.currency !== this.data.meta.currency ? " " + this.esc(a.currency) : ""}</td>
			<td class="r num" style="color:var(--good-ink)">${this.fmt(a.kirim)}</td>
			<td class="r num" style="color:var(--bad-ink)">${this.fmt(a.chiqim)}</td>
			<td class="r num" style="font-weight:700">${this.fmt(a.closing)}</td></tr>`).join("")
			: `<tr><td colspan="6" class="empty-hint">Kassa hisoblari topilmadi.</td></tr>`;
		h += this.card(`
			<div class="hd"><div><h3>Hisoblar kesimida</h3><div class="meta">Har bir kassa/bank hisobi</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Hisob</th><th>Usul</th><th class="r">Ochilish</th><th class="r">Kirim</th><th class="r">Chiqim</th><th class="r">Yopilish</th></tr></thead>
				<tbody>${rows}</tbody>
				<tfoot><tr><td colspan="2">Jami (${ccy})</td><td class="r num">${this.fmt(t.opening)}</td><td class="r num" style="color:var(--good-ink)">${this.fmt(t.kirim)}</td><td class="r num" style="color:var(--bad-ink)">${this.fmt(t.chiqim)}</td><td class="r num">${this.fmt(t.closing)}</td></tr></tfoot>
			</table></div>
			${(cf.other || []).length ? `<div class="othccy">Boshqa valyuta: ${cf.other.map((o) => `${this.esc(o.currency)} ${this.fmt(o.closing)}`).join(" · ")}</div>` : ""}
		`, "mb");

		// categories in/out
		h += `<div class="grid cols-2 mb">
			${this.card(`<div class="hd"><div><h3>Kirim manbalari</h3><div class="meta">Pul qayerdan keldi</div></div></div>${this.hbars(cf.categories.in, "var(--good)")}`)}
			${this.card(`<div class="hd"><div><h3>Chiqim yo'nalishlari</h3><div class="meta">Pul qayerga ketdi</div></div></div>${this.hbars(cf.categories.out, "var(--bad)")}`)}
		</div>`;

		// 12m flow + daily calendar
		h += `<div class="grid cols-2 mb">
			${this.card(`<div class="hd"><div><h3>Kirim va chiqim — 12 oy</h3><div class="meta">mln ${ccy}</div></div>
				<div class="legend"><div class="it"><span class="sw" style="background:var(--good)"></span> Kirim</div><div class="it"><span class="sw" style="background:var(--bad)"></span> Chiqim</div></div></div>
				${this.lineChart(cf.monthly.months, [{ data: cf.monthly.expense, color: "var(--bad)", fill: true }, { data: cf.monthly.income, color: "var(--good)", fill: true }])}`)}
			${this.calendarCard(cf.daily)}
		</div>`;
		return h + this.note();
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
			<div class="hd"><div><h3>Kunlik kassa kirimi</h3><div class="meta">${this.esc(cal.month_label)} ${cal.year}</div></div>
				<div class="legend"><div class="it"><span class="sw" style="background:var(--card-2);border:1px solid var(--line)"></span> Yo'q</div><div class="it"><span class="sw" style="background:var(--h1)"></span> Kam</div><div class="it"><span class="sw" style="background:var(--h2)"></span> O'rta</div><div class="it"><span class="sw" style="background:var(--h3)"></span> Ko'p</div></div></div>
			<div class="cal-head"><span>Du</span><span>Se</span><span>Ch</span><span>Pa</span><span>Ju</span><span>Sh</span><span>Ya</span></div>
			<div class="cal">${cells}</div>`);
	}

	ccyTotals(list) {
		// Har valyuta bo'yicha jami (Jami USD, Jami UZS...). Bitta valyuta bo'lsa — yuqoridagi KPI yetarli, ko'rsatmaymiz.
		if (!list || list.length < 2) return "";
		const base = this.data.meta.currency;
		const cards = list.map((c) => {
			const isBase = c.currency === base;
			return `<div class="ccy-card${isBase ? " base" : ""}">
				<div class="ccy-top"><span class="ccy-code">${this.esc(c.currency)}</span>${isBase ? `<span class="ccy-tag">asosiy</span>` : ""}</div>
				<div class="ccy-close num" data-tt="${this.fmt(c.closing)} ${this.esc(c.currency)}">${this.fmt(c.closing)} <span class="cur">${this.ccyLabel(c.currency)}</span></div>
				<div class="ccy-flow">
					<span class="in num" data-tt="Kirim: ${this.fmt(c.kirim)}">▲ ${this.kc(c.kirim)}</span>
					<span class="out num" data-tt="Chiqim: ${this.fmt(c.chiqim)}">▼ ${this.kc(c.chiqim)}</span>
				</div>
				<div class="ccy-open num">Oy boshi: ${this.kc(c.opening)}</div>
			</div>`;
		}).join("");
		return this.card(`
			<div class="hd"><div><h3>Valyutalar kesimida jami</h3><div class="meta">Har valyuta o'z birligida (kurs bo'yicha jamlanmaydi)</div></div></div>
			<div class="ccy-grid">${cards}</div>`, "mb");
	}

	// ================= TAB: Debts =================
	renderDebts() {
		const d = this.data.debts, ccy = this.ccyLabel(this.data.meta.currency);
		let h = this.sec("Qarzdorlik holati", `${this.data.meta.period.label} oxiriga`);
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Debitorka (bizga qarz)", raw: d.receivable.total, cmp: d.receivable.cmp, invert: true, pin: "var(--warn)", valColor: "var(--warn-ink)" })}
			${this.moneyKpi({ label: "Kreditorka (biz qarz)", raw: d.payable.total, cmp: d.payable.cmp, invert: true, pin: "var(--c5)" })}
			${this.moneyKpi({ label: "Sof aylanma (deb − kred)", raw: d.net_working, pin: "var(--brand)", valColor: d.net_working < 0 ? "var(--bad-ink)" : "" })}
			${this.moneyKpi({ label: "Xodim avanslari", raw: d.employee.total, pin: "var(--c3)", sub: d.employee.available ? "" : "Employee Advance moduli yo'q" })}
		</div>`;

		// aging + top debtors
		const ag = d.receivable.aging || [];
		const agp = ag.map((a) => Math.max(0, a.amount));
		const agTot = agp.reduce((a, b) => a + b, 0) || 1;
		const sc = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
		const stack = ag.map((a, i) => `<span style="flex:0 0 ${Math.max(0, agp[i] / agTot * 100)}%;background:${sc[i]}" data-tt="${this.esc(a.label)}: ${this.fmt(a.amount)}"></span>`).join("");
		const agleg = ag.map((a, i) => `<div class="it"><span class="sw" style="background:${sc[i]}"></span> ${this.esc(a.label)} <b>${this.kc(a.amount)}</b></div>`).join("");
		h += `<div class="grid cols-2 mb">
			${this.card(`<div class="hd"><div><h3>Debitorka muddati (aging)</h3><div class="meta">Qancha eskirgan — shuncha xavfli · taxminiy</div></div></div>
				<div class="stack">${stack || ""}</div><div class="legend" style="margin-top:12px">${agleg}</div>`)}
			${this.partyTable("Eng katta debitorlar", d.receivable.top, "var(--warn-ink)")}
		</div>`;
		h += `<div class="grid cols-2 mb">
			${this.partyTable("Eng katta kreditorlar (ta'minotchilar)", d.payable.top, "var(--ink)")}
			${this.card(`<div class="hd"><div><h3>Xodim avanslari</h3><div class="meta">Yopilmagan qism</div></div></div>${this.empList(d.employee)}`)}
		</div>`;
		return h + this.note();
	}

	partyTable(title, top, color) {
		const rows = (top || []).length ? top.map((t) => `<tr><td class="ell" data-tt="${this.esc(t.name)}">${this.esc(t.name)}</td><td class="r num" style="color:${color}">${this.fmt(t.amount)}</td></tr>`).join("")
			: `<tr><td colspan="2" class="empty-hint">Ma'lumot yo'q.</td></tr>`;
		return this.card(`<div class="hd"><div><h3>${this.esc(title)}</h3></div></div><table><tbody>${rows}</tbody></table>`);
	}

	empList(emp) {
		if (!emp.available) return `<div class="empty-hint">HR (Employee Advance) moduli o'rnatilmagan.</div>`;
		if (!emp.top || !emp.top.length) return `<div class="empty-hint">Yopilmagan avans yo'q.</div>`;
		return `<div class="list">` + emp.top.map((t) => `<div class="it"><span class="av">${this.esc((t.name || "?").substr(0, 2).toUpperCase())}</span><div><div class="nm ell">${this.esc(t.name)}</div><div class="cl">avans</div></div><span class="amt">${this.fmt(t.amount)}</span></div>`).join("") + `</div>`;
	}

	// ================= TAB: Tuition =================
	renderTuition() {
		const t = this.data.tuition, ccy = this.ccyLabel(this.data.meta.currency);
		let h = this.sec("O'quvchilar to'lovi", "Education Fees asosida");
		if (!t.available) {
			h += this.card(`<div class="empty-hint" style="padding:26px 8px">
				<b>Education Fees ma'lumoti topilmadi.</b><br>O'quvchilar to'lovga (Fees) ulangach, bu bo'lim avtomatik to'ladi:
				hisoblangan/yig'ilgan summa, yig'im foizi, sinf kesimi, qarzdor o'quvchilar.<br>
				Hozircha faol o'quvchilar: <b>${this.fmt(t.active)}</b> ta.</div>`);
			return h + this.note();
		}
		h += `<div class="grid cols-4 mb">
			${this.kpi({ label: "Faol o'quvchilar", value: this.fmt(t.active), pin: "var(--c2)", sub: `${t.with_fees} tada to'lov yozuvi` })}
			${this.moneyKpi({ label: "Hisoblangan (billed)", raw: t.billed, pin: "var(--c1)" })}
			${this.moneyKpi({ label: "Yig'ilgan (collected)", raw: t.collected, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.kpi({ label: "Yig'im foizi", value: (t.rate != null ? t.rate : "—"), unit: t.rate != null ? "%" : "", pin: "var(--warn)", sub: `Qoldiq qarz ${this.kc(t.outstanding)} ${ccy}` })}
		</div>`;

		// status donut + by class
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

		// top debtors
		h += this.partyTable("Eng katta qarzdor o'quvchilar", t.top_debtors, "var(--bad-ink)");
		return h + this.note();
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
		const p = this.data.pnl, ccy = this.ccyLabel(this.data.meta.currency), cur = p.current, o = this.data.overview;
		let h = this.sec("Foyda va zarar (P&L)", `${this.data.meta.period.label} · accrual (hisoblangan)`);
		h += `<div class="grid cols-4 mb">
			${this.moneyKpi({ label: "Daromad", raw: cur.income, cmp: o.income, cmpYoy: o.income_yoy, pin: "var(--good)", valColor: "var(--good-ink)" })}
			${this.moneyKpi({ label: "Xarajat", raw: cur.expense, cmp: o.expense, cmpYoy: o.expense_yoy, invert: true, pin: "var(--bad)", valColor: "var(--bad-ink)" })}
			${this.moneyKpi({ label: "Sof foyda", raw: cur.net, cmp: o.net_profit, cmpYoy: o.net_profit_yoy, pin: "var(--brand)", valColor: cur.net < 0 ? "var(--bad-ink)" : "var(--good-ink)" })}
			${this.kpi({ label: "Rentabellik (margin)", value: cur.margin != null ? cur.margin : "—", unit: cur.margin != null ? "%" : "", pin: "var(--c5)", sub: "Sof foyda / daromad" })}
		</div>`;

		// comparison income statement table
		const pv = p.prev, yy = p.yoy;
		const line = (lbl, a, b, c, bold) => `<tr class="${bold ? "b" : ""}"><td>${lbl}</td><td class="r num">${this.fmt(a)}</td><td class="r num">${this.fmt(b)}</td><td class="r num">${this.fmt(c)}</td></tr>`;
		h += this.card(`
			<div class="hd"><div><h3>Foyda hisoboti — taqqoslash</h3><div class="meta">${ccy}</div></div></div>
			<div class="tbl-wrap"><table>
				<thead><tr><th>Ko'rsatkich</th><th class="r">${this.data.meta.period.label}</th><th class="r">${this.esc(this.data.meta.prev_label)}</th><th class="r">${this.esc(this.data.meta.yoy_label)}-yil</th></tr></thead>
				<tbody>
					${line("Daromad", cur.income, pv.income, yy.income)}
					${line("(−) Xarajat", cur.expense, pv.expense, yy.expense)}
					${line("= Sof foyda", cur.net, pv.net, yy.net, true)}
					<tr class="b"><td>Rentabellik</td><td class="r num">${cur.margin != null ? cur.margin + "%" : "—"}</td><td class="r num">${pv.margin != null ? pv.margin + "%" : "—"}</td><td class="r num">${yy.margin != null ? yy.margin + "%" : "—"}</td></tr>
				</tbody>
			</table></div>`, "mb");

		// expense donut + monthly net
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
		return `<div class="note">${wh}Barcha raqamlar real vaqtda ERPNext'dan (GL Entry): kassa — Mode of Payment hisoblari; debitorka/kreditorka — Receivable/Payable; foyda — Income/Expense; o'quvchi to'lovi — Education Fees; xodim avansi — Employee Advance. Aging va kategoriya taxminiy hisob-kitob asosida.</div>`;
	}
}
