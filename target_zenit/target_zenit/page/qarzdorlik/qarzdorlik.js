// Copyright (c) 2026, Target Zenit — Qarzdorlik paneli
// Savdo menejerlari uchun: qarzdorlar navbati, o'quvchi kartasi,
// "Qo'ng'iroq natijasi" modali. Qarz manbai — Tolov Rejasi (engine hisoblaydi).
frappe.pages["qarzdorlik"].on_page_load = function (wrapper) {
	new TZQarzPanel(wrapper);
};

const QARZ_M = "target_zenit.target_zenit.page.qarzdorlik.qarzdorlik";

class TZQarzPanel {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Qarzdorlik paneli"), single_column: true });
		this.data = null;
		this.selected = null;   // tanlangan ish nomi
		this.detail = null;     // get_case natijasi
		this.q = "";
		this.fManager = "";     // keyin load()da: o'zi menejer bo'lsa — o'zi
		this.fBucket = "";
		this.fStatus = "";
		this.fSinflar = new Set();  // sinf filtri — bir vaqtda bir nechta sinf
		this.fKetgan = 0;       // 0 = faol o'quvchilar, 1 = ketganlar ro'yxati
		this.fTurlar = new Set();   // qarz turi: o'quv to'lovi / Kitob / Forma / Yotoqxona…
		this.fQueue = "all";    // all | today | overdue
		this.make_skeleton();
		this.load(true);
	}

	// ================= helpers =================
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : "—"; }
	fmt(n) {
		n = Math.round(Number(n) || 0);
		const s = Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
		return (n < 0 ? "−" : "") + s;
	}
	tel(p) {
		p = String(p || "").trim();
		if (!p) return "";
		return `<a class="tel" href="tel:${this.esc(p.replace(/[^+\d]/g, ""))}" onclick="event.stopPropagation()">${this.esc(p)}</a>`;
	}
	today() { return frappe.datetime.get_today(); }
	// Sekundni 3:07 ko'rinishiga keltirish
	dur(sec) {
		sec = Math.round(Number(sec) || 0);
		if (!sec) return "0:00";
		const m = Math.floor(sec / 60), s2 = sec % 60;
		return `${m}:${String(s2).padStart(2, "0")}`;
	}
	dtm(s) {
		const v = String(s || "");
		return v ? `${this.dmy(v)} ${v.slice(11, 16)}` : "—";
	}

	statusPill(st) {
		const cls = {
			"Yangi": "new", "Urinilmoqda": "try", "Gaplashildi - Va'da": "ok",
			"Gaplashildi - Nizo": "warn", "Bo'lib to'lash": "ok", "Va'da buzildi": "bad",
			"Aloqa yo'q": "mut", "To'lov tekshirilmoqda": "blue", "Eskalatsiya": "bad",
		}[st] || "mut";
		return `<span class="pill st-${cls}">${this.esc(st)}</span>`;
	}
	// Kechikish belgisi: necha kun to'lanmay turganini ko'rsatadi (rang — bucket bo'yicha)
	bucketPill(b, eng_eski) {
		if (!b) return "";
		const cls = { "1-30": "b1", "31-60": "b2", "61-90": "b3", "90+": "b4", "Ketgan-qarzli": "b4" }[b] || "b1";
		let text = b;
		if (b !== "Ketgan-qarzli" && eng_eski) {
			const days = frappe.datetime.get_day_diff(this.today(), eng_eski);
			if (days > 0) text = `${days} kun`;
		}
		return `<span class="pill bk-${cls}" title="Eng eski to'lanmagan muddat: ${this.dmy(eng_eski)}">${this.esc(text)}</span>`;
	}

	// ================= load =================
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-qarz"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load(first) {
		frappe.call({
			method: `${QARZ_M}.get_data`,
			args: { ketganlar: this.fKetgan },
			callback: (r) => {
				this.data = r.message || { cases: [], stats: {}, managers: [] };
				if (first && !this.data.rahbar) this.fManager = this.data.me;
				this.render();
				if (this.selected) this.load_detail(this.selected, true);
			},
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	load_detail(name, silent) {
		this.selected = name;
		if (!silent) this.body.find(".detail").html(`<div class="loading">Yuklanmoqda…</div>`);
		frappe.call({
			method: `${QARZ_M}.get_case`,
			args: { name },
			callback: (r) => { this.detail = r.message; this.render_detail(); this.mark_selected(); },
		});
	}

	// ================= filter =================
	// Ochiq ishlardagi sinflar ro'yxati (tabiiy tartib: 1 A, 2 A, ... 10 A, 11 B)
	sinflar() {
		const m = new Map();
		for (const c of this.data.cases || []) {
			const k = c.sinf || "__none";
			m.set(k, (m.get(k) || 0) + 1);
		}
		return [...m.entries()]
			.map(([sinf, soni]) => ({ sinf, soni, paralel: (String(sinf).match(/^\s*(\d+)/) || [])[1] || "" }))
			.sort((a, b) => String(a.sinf).localeCompare(String(b.sinf), undefined, { numeric: true }));
	}

	// Sinflarni paralel (1..11) bo'yicha guruhlash — "9 va 10-sinflar"ni
	// bitta bosishda tanlash uchun
	paralellar() {
		const g = new Map();
		for (const x of this.sinflar()) {
			const k = x.paralel || "—";
			if (!g.has(k)) g.set(k, []);
			g.get(k).push(x);
		}
		return [...g.entries()].sort((a, b) => Number(a[0]) - Number(b[0]) || String(a[0]).localeCompare(b[0]));
	}

	// Qarz turlari — serverdan (Sales Invoice itemlaridan), qotib yozilmaydi
	turlar() {
		return Object.entries((this.data.stats || {}).turlar || {})
			.map(([tur, v]) => ({ tur, soni: v.soni, summa: v.summa }));
	}

	turLabel() {
		const n = this.fTurlar.size;
		if (!n) return "barchasi";
		return n <= 2 ? [...this.fTurlar].join(", ") : `${n} ta tanlandi`;
	}

	// Tanlangan tur bo'yicha qarz summasi (filtrlangan ro'yxat ichida)
	turSummasi(rows) {
		if (!this.fTurlar.size) return null;
		return rows.reduce((a, c) => a + [...this.fTurlar]
			.reduce((b, t) => b + ((c.qarz_turlari || {})[t] || 0), 0), 0);
	}

	sinfLabel() {
		const n = this.fSinflar.size;
		if (!n) return "barchasi";
		if (n <= 2) return [...this.fSinflar].map((x) => (x === "__none" ? "sinfsiz" : x)).join(", ");
		return `${n} ta tanlandi`;
	}

	filtered() {
		const q = this.q.trim().toLowerCase();
		const today = this.today();
		return (this.data.cases || []).filter((c) => {
			if (this.fManager && c.masul !== this.fManager) return false;
			if (this.fBucket && c.aging_bucket !== this.fBucket) return false;
			if (this.fStatus && c.ishlov_status !== this.fStatus) return false;
			if (this.fSinflar.size && !this.fSinflar.has(c.sinf || "__none")) return false;
			if (this.fQueue === "today" && !(c.keyingi_aloqa && c.keyingi_aloqa <= today)) return false;
			if (this.fQueue === "overdue" && !(c.keyingi_aloqa && c.keyingi_aloqa < today)) return false;
			if (this.fQueue === "gaplashilgan" && !(c.aloqa_soni > 0)) return false;
			if (this.fQueue === "yozuvli" && !(c.yozuv_soni > 0)) return false;
			if (this.fTurlar.size) {
				const bor = Object.keys(c.qarz_turlari || {});
				if (!bor.some((t) => this.fTurlar.has(t))) return false;
			}
			if (q) {
				const hay = [c.student_name, c.sinf, c.payer_name, c.payer_phone].join(" ").toLowerCase();
				if (!hay.includes(q)) return false;
			}
			return true;
		});
	}

	// ================= render =================
	render() {
		const st = this.data.stats || {};
		const buckets = st.buckets || {};
		const bchip = (b) =>
			`<button class="chip ${this.fBucket === b ? "on" : ""}" data-b="${b}">${b} <span class="n">${(buckets[b] || {}).soni || 0}</span></button>`;

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Qarzdorlik paneli</h1>
					<div class="sub">
						<span class="badge-qarz">${this.fKetgan ? "Ketganlar" : "Qarzdorlar"}: <b>${this.fmt(st.ochiq)}</b> ta · jami <b>${this.fmt(st.jami_qarz)}</b> so'm</span>
						${this.fKetgan ? `<span class="badge-ketgan">Maktabdan ketgan o'quvchilar ro'yxati</span>`
							: `<span class="mini">faqat faol o'quvchilar</span>`}
					</div>
				</div>
				<div class="spacer"></div>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="grid cols-7 mb kpis">
				<div class="card kpi click ${this.fQueue === "today" ? "sel" : ""}" data-queue="today">
					<div class="lab"><span class="pin b"></span>Bugun aloqa</div>
					<div class="val">${this.fmt(st.bugun)}</div><div class="sub">keyingi aloqa = bugun</div></div>
				<div class="card kpi click ${this.fQueue === "overdue" ? "sel" : ""}" data-queue="overdue">
					<div class="lab"><span class="pin r"></span>O'tib ketgan</div>
					<div class="val">${this.fmt(st.otgan)}</div><div class="sub">aloqa sanasi o'tgan</div></div>
				<div class="card kpi click ${this.fQueue === "gaplashilgan" ? "sel" : ""}" data-queue="gaplashilgan">
					<div class="lab"><span class="pin g"></span>Gaplashilgan</div>
					<div class="val">${this.fmt(st.gaplashilgan)}</div><div class="sub">kamida bir marta aloqa qilingan</div></div>
				<div class="card kpi click ${this.fQueue === "yozuvli" ? "sel" : ""}" data-queue="yozuvli"
					title="Ovoz yozuvi bor suhbat o'tkazilgan o'quvchilar — bosib ro'yxatini ko'rish">
					<div class="lab"><span class="pin b"></span>🎧 Qo'ng'iroq yozib olindi</div>
					<div class="val">${this.fmt(st.yozuvli)}</div>
					<div class="sub">${this.fmt(st.yozuv_jami)} ta yozuv · odam bilan gaplashilgan</div></div>
				<div class="card kpi"><div class="lab"><span class="pin y"></span>Va'da buzilgan</div>
					<div class="val">${this.fmt(st.vada_buzilgan)}</div><div class="sub">birinchi navbatda</div></div>
				<div class="card kpi"><div class="lab"><span class="pin r"></span>Eskalatsiya</div>
					<div class="val">${this.fmt(st.eskalatsiya)}</div><div class="sub">rahbar nazorati</div></div>
				<div class="card kpi click ${this.fQueue === "all" ? "sel" : ""}" data-queue="all">
					<div class="lab"><span class="pin g"></span>Jami ochiq</div>
					<div class="val">${this.fmt(st.ochiq)}</div><div class="sub">hamma ishlar</div></div>
			</div>

			<div class="controls mb">
				<input type="text" class="q" placeholder="Qidiruv: ism, sinf, to'lovchi, telefon…" value="${this.esc(this.q)}">
				<select class="fmanager">
					<option value="">Barcha menejerlar</option>
					${(this.data.managers || []).map((m) =>
						`<option value="${this.esc(m.name)}" ${this.fManager === m.name ? "selected" : ""}>${this.esc(m.full_name)}</option>`).join("")}
				</select>
				<div class="dd sinf-dd">
					<button class="dd-btn" type="button">Sinflar: <b>${this.esc(this.sinfLabel())}</b> ▾</button>
					<div class="dd-menu" hidden>
						${this.paralellar().map(([p, lst]) => `
							<div class="dd-grp">
								<label class="dd-g"><input type="checkbox" data-paralel="${this.esc(p)}"
									${lst.every((x) => this.fSinflar.has(x.sinf)) ? "checked" : ""}>
									<b>${p === "—" ? "Sinfsiz" : p + "-sinf"}</b>
									<span class="n">${lst.reduce((a, x) => a + x.soni, 0)}</span></label>
								${lst.map((x) => `<label class="dd-i"><input type="checkbox" data-sinf="${this.esc(x.sinf)}"
									${this.fSinflar.has(x.sinf) ? "checked" : ""}>
									${this.esc(x.sinf === "__none" ? "Sinfsiz" : x.sinf)}
									<span class="n">${x.soni}</span></label>`).join("")}
							</div>`).join("")}
						<button class="dd-clear" type="button">Tozalash</button>
					</div>
				</div>
				<div class="dd tur-dd">
					<button class="dd-btn" type="button">Qarz turi: <b>${this.esc(this.turLabel())}</b> ▾</button>
					<div class="dd-menu" hidden>
						${this.turlar().map((t) => `
							<label class="dd-i"><input type="checkbox" data-tur="${this.esc(t.tur)}"
								${this.fTurlar.has(t.tur) ? "checked" : ""}>
								${this.esc(t.tur)}
								<span class="n">${t.soni} ta · ${this.fmt(t.summa)}</span></label>`).join("")
						|| `<div class="mini" style="padding:4px">Qarz turi topilmadi</div>`}
						<button class="dd-clear" type="button">Tozalash</button>
					</div>
				</div>
				<select class="fstatus">
					<option value="">Barcha statuslar</option>
					${["Yangi", "Urinilmoqda", "Gaplashildi - Va'da", "Gaplashildi - Nizo", "Bo'lib to'lash",
						"Va'da buzildi", "Aloqa yo'q", "To'lov tekshirilmoqda", "Eskalatsiya"].map((s) =>
						`<option ${this.fStatus === s ? "selected" : ""}>${s}</option>`).join("")}
				</select>
				<div class="chips">${["1-30", "31-60", "61-90", "90+"].map(bchip).join("")}
					<button class="chip ${this.fKetgan ? "on" : ""}" data-act="ketgan"
						title="Maktabdan ketgan (nofaol) o'quvchilarning qarzi">Ketganlar <span class="n">${this.fmt(st.ketgan_soni)}</span></button></div>
			</div>

			<div class="split">
				<div class="list card"></div>
				<div class="detail card"><div class="empty">O'quvchini tanlang — karta shu yerda ochiladi</div></div>
			</div>
		`);

		this.render_list();
		this.bind();
		if (this.detail) this.render_detail();
	}

	render_list() {
		const rows = this.filtered();
		const today = this.today();
		// Jadval tepasidagi yakun — FILTRLANGAN ro'yxat bo'yicha
		const jami = rows.reduce((a, c) => a + (Number(c.qarz_summa) || 0), 0);
		const turJami = this.turSummasi(rows);
		const bosh = `<div class="list-head">
			<span>Qarzdorlar: <b>${this.fmt(rows.length)}</b> ta</span>
			<span>Jami qarz: <b class="money">${this.fmt(jami)}</b> so'm</span>
			${turJami !== null ? `<span class="tur-jami">${this.esc(this.turLabel())}: <b class="money">${this.fmt(turJami)}</b> so'm</span>` : ""}
			${rows.length !== (this.data.cases || []).length
				? `<span class="mini">(filtr: ${this.fmt((this.data.cases || []).length)} tadan)</span>` : ""}
		</div>`;
		const html = rows.length
			? `<table class="tbl">
				<thead><tr><th>O'quvchi / to'lovchi</th><th>Sinf</th><th class="r">Qarz (so'm)</th><th>Kechikish</th><th>Ishlov holati</th><th>Keyingi aloqa</th><th>Menejer</th></tr></thead>
				<tbody>
				${rows.map((c) => `
					<tr data-case="${this.esc(c.name)}" class="${this.selected === c.name ? "sel" : ""} ${c.keyingi_aloqa && c.keyingi_aloqa < today ? "late" : ""}">
						<td><div class="nm">${this.esc(c.student_name)}${c.qongiroq_soni > 0
							? ` <span class="pill st-blue" title="${c.qongiroq_soni} ta qo'ng'iroq${c.yozuv_soni ? `, ${c.yozuv_soni} ta ovoz yozuvi` : ""}${c.oxirgi_qongiroq ? `, oxirgisi ${this.dtm(c.oxirgi_qongiroq)}` : ""}">🎧 ${c.qongiroq_soni}</span>` : ""}${c.aloqa_soni > 0 ? ` <span class="pill st-ok" title="O'quvchi bo'yicha ${c.aloqa_soni} ta aloqa yozuvi${c.gaplashildi_soni > 0 ? `, ${c.gaplashildi_soni} marta gaplashildi` : ""}${c.shu_ishda !== c.aloqa_soni ? `; shu ishda ${c.shu_ishda} ta` : ""}">✓ ${c.aloqa_soni} aloqa</span>` : ""}</div>
							<div class="mini">${this.esc(c.payer_name || "")} ${this.tel(c.payer_phone)}</div></td>
						<td>${this.esc(c.sinf || "—")}</td>
						<td class="r money">${this.fmt(c.qarz_summa)}
							${Object.keys(c.qarz_turlari || {}).length
								? `<div class="mini tur-mini">${Object.entries(c.qarz_turlari)
									.map(([t, v]) => `${this.esc(t)} ${this.fmt(v)}`).join(" · ")}</div>` : ""}</td>
						<td>${this.bucketPill(c.aging_bucket, c.eng_eski_muddat)}</td>
						<td>${this.statusPill(c.ishlov_status)}</td>
						<td class="${c.keyingi_aloqa && c.keyingi_aloqa < today ? "red" : ""}">${this.dmy(c.keyingi_aloqa)}</td>
						<td class="mini">${this.esc((this.data.managers.find((m) => m.name === c.masul) || {}).full_name || c.masul || "")}</td>
					</tr>`).join("")}
				</tbody></table>`
			: `<div class="empty">Filtrga mos ish topilmadi</div>`;
		this.body.find(".list").html(bosh + html);
		this.body.find(".list tr[data-case]").on("click", (e) => this.load_detail($(e.currentTarget).data("case")));
	}

	mark_selected() {
		this.body.find(".list tr[data-case]").removeClass("sel");
		this.body.find(`.list tr[data-case="${this.selected}"]`).addClass("sel");
	}

	render_detail() {
		const d = this.detail;
		if (!d) return;
		const c = d.case;
		const phones = [];
		if (c.payer_phone) phones.push(`${this.esc(c.payer_name || "To'lovchi")}: ${this.tel(c.payer_phone)}`);
		for (const g of d.guardians || []) {
			// Ota-onada ikkita raqam bo'lishi mumkin (asosiy + qo'shimcha)
			const nom = `${this.esc(g.guardian_name)}${g.relation ? " (" + this.esc(g.relation) + ")" : ""}`;
			if (g.mobile_number) phones.push(`${nom}: ${this.tel(g.mobile_number)}`);
			if (g.alternate_number && g.alternate_number !== g.mobile_number)
				phones.push(`${nom} · 2: ${this.tel(g.alternate_number)}`);
		}
		if (d.student_phone) phones.push(`O'quvchi: ${this.tel(d.student_phone)}`);

		const cheklov = c.aloqa_cheklovi
			? `<div class="alert-cheklov">⚠ Aloqa cheklovi: <b>${this.esc(c.aloqa_cheklovi)}</b></div>` : "";

		const sibs = (d.siblings || []).length
			? `<div class="box"><div class="box-t">Shu to'lovchining boshqa farzandlari</div>
				${d.siblings.map((s) => `<div class="sib">${this.esc(s.student_name)} — <b>${this.fmt(s.qarz_summa)}</b> so'm
					${this.statusPill(s.ishlov_status)} <span class="mini">mas'ul: ${this.esc(s.masul)}</span></div>`).join("")}</div>` : "";

		// Oy qatorining odam tilidagi izohi — menejer telefonda aytadigan gap
		const oyIzoh = (m) => {
			const kech = m.kechikish ? ` <b class="neg">${m.kechikish} kun kechikdi</b>` : "";
			if (m.holat === "Rejada")
				return `<span class="mini">Nachisleniya hali qilinmagan (reja: ${this.fmt(m.reja)})</span>`;
			if (m.holat === "Nachisleniya yo'q")
				return `<span class="mini warn-t">Oy o'tdi, nachisleniya yozilmagan (reja: ${this.fmt(m.reja)})</span>`;
			if (m.holat === "To'landi")
				return `<span class="ok-t">${this.fmt(m.nachislangan)} nachislangan — to'liq to'langan</span>`;
			if (m.holat === "Qisman")
				return `${this.fmt(m.nachislangan)} nachislangan, ${this.fmt(m.tolangan)} to'langan, <b class="neg">${this.fmt(m.qoldiq)} qoldi</b>${kech}`;
			if (m.holat === "Muddati keldi")
				return `<b class="neg">${this.dmy(m.due_date)} da to'lanishi kerak edi — to'lanmadi (${this.fmt(m.qoldiq)})</b>${kech}`;
			return `<span class="mini">${this.dmy(m.due_date)} gacha to'lash kerak (${this.fmt(m.nachislangan)})</span>`;
		};

		const x = d.xulosa;
		const satr = (nom, v, cls) => `<tr class="${cls || ""}">
			<td>${nom}</td>
			<td class="r">${this.fmt(v.nachislangan)}</td>
			<td class="r">${this.fmt(v.tolangan)}</td>
			<td class="r money ${v.qoldiq > 1 ? "neg" : ""}">${this.fmt(v.qoldiq)}</td>
			<td class="r ${v.qarz > 1 ? "neg" : ""}">${this.fmt(v.qarz)}</td></tr>`;

		const xulosa = x ? `<div class="box xul">
			<div class="box-t">Umumiy ma'lumot — haqiqiy nachisleniya bo'yicha</div>
			<table class="tbl mini-tbl xul-tbl">
				<thead><tr><th>Nima uchun</th><th class="r">Nachislangan</th><th class="r">To'langan</th>
					<th class="r">To'lanmagan</th><th class="r">Shundan muddati kelgan</th></tr></thead>
				<tbody>
					${satr(`O'quv to'lovi <span class="mini">(${x.oquv.nachislangan_oy} oy nachislangan)</span>`, x.oquv)}
					${(x.qoshimcha || []).map((q) => satr(`${this.esc(q.nom)} <span class="mini">(${q.soni} ta hujjat)</span>`, q)).join("")}
					${satr("<b>JAMI</b>", x.jami, "xul-jami")}
				</tbody>
			</table>
			<div class="xul-shart">
				<div><span>Shartnoma summasi (o'quv)</span><b>${this.fmt(x.oquv.shartnoma)}</b></div>
				<div><span>Shundan nachislangan</span><b>${this.fmt(x.oquv.nachislangan)}</b></div>
				<div><span>Hali nachislanmagan (kelgusi oylar)</span><b>${this.fmt(x.oquv.nachislanmagan)}</b></div>
				<div><span>O'quv to'lovidan to'langan</span><b>${this.fmt(x.oquv.tolangan)}</b></div>
				<div><span>Muddati kelgan qarz</span><b class="${x.jami.qarz > 1 ? "neg" : ""}">${this.fmt(x.jami.qarz)}</b></div>
				<div><span>Avans (kelgusi oylarga)</span><b>${this.fmt(x.jami.avans)}</b></div>
			</div>
			${x.oquv.nachisleniyasiz_oy
				? `<div class="ogoh">⚠ ${x.oquv.nachisleniyasiz_oy} oy o'tgan, lekin nachisleniya yozilmagan
					(shartnoma bo'yicha ${this.fmt(x.oquv.nachisleniyasiz_summa)}). Bu summa qarz sifatida
					hisoblanmayapti — buxgalteriya nachisleniya yozishi kerak.</div>` : ""}
		</div>` : "";

		const months = `<div class="box"><div class="box-t">To'lov jadvali — oyma-oy nachisleniya</div>
			<table class="tbl mini-tbl"><thead><tr><th>Oy</th><th>Muddat</th><th class="r">Nachislangan</th>
				<th class="r">To'langan</th><th class="r">Qoldiq</th><th>Holat</th></tr></thead>
			<tbody>${(x ? x.oylar : []).map((m) => `
				<tr class="mh-${this.esc(m.holat)}">
					<td>${this.esc(m.oy_label)}${m.nachisleniya
						? ` <a class="mini" href="/app/sales-invoice/${encodeURIComponent(m.nachisleniya.split(",")[0].trim())}" target="_blank" title="${this.esc(m.nachisleniya)}">↗</a>` : ""}</td>
					<td class="${m.kechikish ? "red" : ""}">${this.dmy(m.due_date)}</td>
					<td class="r">${m.nachislangan ? this.fmt(m.nachislangan) : `<span class="mini">— (reja ${this.fmt(m.reja)})</span>`}</td>
					<td class="r">${this.fmt(m.tolangan)}${m.qaytim ? ` <span class="neg mini">−${this.fmt(m.qaytim)}</span>` : ""}</td>
					<td class="r money ${m.qoldiq > 1 ? "neg" : ""}">${this.fmt(m.qoldiq)}</td>
					<td>${oyIzoh(m)}</td></tr>`).join("")}
			</tbody></table>
			${(x && x.qoshimcha || []).length ? `<div class="box-t" style="margin-top:10px">Qo'shimcha nachisleniyalar (kitob, forma, yotoqxona)</div>
			<table class="tbl mini-tbl"><thead><tr><th>Nachisleniya</th><th>Sana</th><th class="r">Summa</th>
				<th class="r">To'langan</th><th class="r">Qoldiq</th><th>Holat</th></tr></thead>
			<tbody>${(d.months || []).filter((m) => m.manba_hujjat && m.holat !== "Bekor").map((m) => `
				<tr class="mh-${this.esc(m.holat)}"><td>${this.esc(m.oy_label)}
						<a class="mini" href="/app/sales-invoice/${encodeURIComponent(m.manba_hujjat)}" target="_blank">↗</a></td>
					<td>${this.dmy(m.due_date)}</td><td class="r">${this.fmt(m.amount)}</td>
					<td class="r">${this.fmt(m.paid_amount)}</td>
					<td class="r money ${m.outstanding > 1 ? "neg" : ""}">${this.fmt(m.outstanding)}</td>
					<td>${m.holat === "To'landi" ? `<span class="ok-t">to'langan</span>`
						: `<b class="neg">to'lanmagan</b>`}</td></tr>`).join("")}
			</tbody></table>` : ""}
		</div>`;

		const pays = `<div class="box"><div class="box-t">To'lovlar (${(d.payments || []).length})${(d.payments || []).some((p) => p.qaytim)
				? ` · sof: ${this.fmt((d.payments || []).reduce((a, p) => a + p.amount_uzs, 0))}` : ""}</div>
			${(d.payments || []).length ? `<table class="tbl mini-tbl"><tbody>
				${d.payments.slice(0, 12).map((p) => `
					<tr class="${p.qaytim ? "qaytim" : ""}"><td>
						<a href="/app/${frappe.router.slug(p.doctype || "Payment Entry")}/${encodeURIComponent(p.name)}"
						   target="_blank">${this.dmy(p.posting_date)}</a>
						${p.qaytim ? `<div class="mini">qaytim</div>` : ""}</td>
					<td class="r money ${p.qaytim ? "neg" : ""}">${this.fmt(p.amount_uzs)}</td>
					<td class="mini">${p.doctype === "Journal Entry" ? `<span class="tag-je">provodka</span> ` : ""}${this.esc(p.mode_of_payment || "")} ${p.currency !== "UZS" ? "(" + this.esc(p.currency) + ")" : ""}</td></tr>`).join("")}
			</tbody></table>` : `<div class="mini">To'lov yo'q</div>`}</div>`;

		const qlar = d.qongiroqlar || [];
		const calls = `<div class="box"><div class="box-t">Telefon suhbatlari (${qlar.length})${
				qlar.filter((q) => q.audio).length ? ` · ${qlar.filter((q) => q.audio).length} ta ovoz yozuvi` : ""}</div>
			${d.tel_hammasi ? "" : `<div class="mini" style="margin-bottom:6px">Faqat o'zingiz qilgan qo'ng'iroqlar ko'rsatilyapti.</div>`}
			${qlar.length ? qlar.map((q) => {
				const url = `/api/method/target_zenit.telefoniya.api.stream_recording?qongiroq=${encodeURIComponent(q.name)}`;
				const natija = q.tugash_sababi || "";
				const pill = natija === "Javob berildi" ? "st-ok" : natija ? "st-mut" : "st-mut";
				const izoh = q.izoh || q.ay_komment || "";
				return `<div class="call">
					<div class="call-head">
						<b>${this.dtm(q.boshlandi)}</b>
						<span class="call-dir ${q.yonalish === "Kiruvchi" ? "in" : "out"}">${q.yonalish === "Kiruvchi" ? "📥 kiruvchi" : "📤 chiquvchi"}</span>
						${q.suhbat_vaqti ? `<span class="mini">suhbat ${this.dur(q.suhbat_vaqti)}</span>` : ""}
						${natija ? `<span class="pill ${pill}">${this.esc(natija)}</span>` : ""}
						<span class="spacer"></span>
						<span class="mini">menejer: <b>${this.esc(q.menejer)}</b></span>
						<a class="mini" href="/app/telefon-qongirogi/${encodeURIComponent(q.name)}" target="_blank">↗</a>
					</div>
					<div class="mini">Kim bilan: ${this.esc(q.kim || "noma'lum")} · ${this.tel(q.tashqi_raqam) || ""}</div>
					${q.audio
						? `<audio class="call-audio" controls preload="none" src="${url}"></audio>`
						: `<div class="mini">${q.yozuv_ochirildi ? "Ovoz yozuvi saqlash muddati tugab o'chirilgan" : "Ovoz yozuvi yo'q"}</div>`}
					${izoh ? `<div class="call-note">${this.esc(izoh)}${
						q.ay_natija ? ` <span class="pill st-blue">${this.esc(q.ay_natija)}</span>` : ""}</div>` : ""}
				</div>`;
			}).join("") : `<div class="mini">Bu to'lovchi raqamlari bo'yicha qo'ng'iroq topilmadi</div>`}
		</div>`;

		const tl = `<div class="box"><div class="box-t">Timeline${(d.ays || []).some((a) => a.boshqa_ish)
			? ` <span class="mini">(o'quvchining butun aloqa tarixi)</span>` : ""}</div>
			${(d.ays || []).length ? d.ays.map((a) => `
				<div class="tl-item">
					<div class="tl-head"><b>${this.esc(a.kanal)}</b> · ${this.esc(a.aloqa_natijasi)}${a.hisob_natijasi ? " → " + this.esc(a.hisob_natijasi) : ""}
						<span class="mini">${this.esc(frappe.datetime.str_to_user(a.vaqt))} · ${this.esc(a.masul)}</span>${a.boshqa_ish
							? ` <span class="pill st-mut" title="Bu suhbat o'quvchining oldingi (yopilgan) ishida yozilgan: ${this.esc(a.qarz_ishi)}">oldingi ish</span>` : ""}</div>
					${a.komment ? `<div class="tl-body">${this.esc(a.komment)}</div>` : ""}
					${a.vada_summa ? `<div class="tl-ptp">Va'da: ${this.fmt(a.vada_summa)} so'm — ${this.dmy(a.vada_sana)}</div>` : ""}
					<div class="mini">Keyingi: ${this.esc(a.keyingi_harakat)} · ${this.dmy(a.keyingi_sana)}</div>
				</div>`).join("") : `<div class="mini">Hali aloqa bo'lmagan</div>`}
			${(d.ptps || []).length ? `<div class="box-t" style="margin-top:8px">Va'dalar</div>
				${d.ptps.map((p) => `<div class="sib">${this.dmy(p.vada_sana)} — <b>${this.fmt(p.vada_summa)}</b> so'm
					<span class="pill ${p.holat === "Bajarildi" ? "st-ok" : p.holat === "Buzildi" ? "st-bad" : "st-mut"}">${this.esc(p.holat)}</span></div>`).join("")}` : ""}
		</div>`;

		this.body.find(".detail").html(`
			<div class="d-head">
				<div>
					<div class="d-name"><a href="/app/student/${encodeURIComponent(c.student)}">${this.esc(c.student_name)}</a>
						<span class="mini">${this.esc(c.sinf || "")}</span></div>
					<div class="d-phones">${phones.join(" · ") || "<span class='mini'>Telefon yo'q</span>"}</div>
				</div>
				<div class="d-debt">
					<div class="d-sum">${this.fmt(c.qarz_summa)} <span class="cur">so'm</span></div>
					<div>${this.bucketPill(c.aging_bucket, c.eng_eski_muddat)} ${this.statusPill(c.ishlov_status)}</div>
				</div>
			</div>
			${cheklov}
			${d.hisob ? `<div class="box hisob">
				<div class="box-t">Hisob tafsiloti — nega shunday chiqdi</div>
				<div class="hisob-grid">
					<span>To'lov (kirim)</span><b>${this.fmt(d.hisob.jami_tolov)}</b>
					<span>Qaytim (chiqim)</span><b class="${d.hisob.jami_qaytim ? "neg" : ""}">${d.hisob.jami_qaytim ? "−" + this.fmt(d.hisob.jami_qaytim) : "0"}</b>
					<span>Sof to'lov</span><b>${this.fmt(d.hisob.sof)}</b>
					<span>Jadvalga (nachisleniyalarga) tushgan</span><b>${this.fmt(d.hisob.jadvalga_tushgan)}</b>
					<span>Avans — nachislanmagan oylarga</span><b>${this.fmt(d.hisob.taqsimlanmagan)}</b>
					<span>Jadvalga yozilgan qaytim</span><b class="${Math.abs(d.hisob.jadvalda_qaytim - d.hisob.jami_qaytim) > 1 ? "neg" : ""}">${this.fmt(d.hisob.jadvalda_qaytim)}</b>
				</div>
				${d.hisob.taqsimlanmagan > 1
					? `<div class="ogoh">ℹ Avansda ${this.fmt(d.hisob.taqsimlanmagan)} so'm turibdi.
						Kassada «Nachisleniya» tanlanmagan pul o'quv to'loviga FIFO (eski oydan boshlab)
						yoziladi; nachislangan oylar to'lanib bo'lgach ortgan summa kelgusi oylarga
						avans bo'lib qoladi va yangi nachisleniya yozilganda avtomatik o'sha oyga tushadi.
						Kitob/forma/yotoqxona esa faqat kassada o'sha nachisleniya tanlangan bo'lsa yopiladi.</div>` : ""}
				${Math.abs(d.hisob.jadvalda_qaytim - d.hisob.jami_qaytim) > 1
					? `<div class="ogoh">⚠ Jadvaldagi qaytim kassadagidan farq qilyapti — reja eski hisobda qolgan.
						«Qayta hisoblash» tugmasini bosing.</div>` : ""}
				<div class="mini">Davr: ${this.dmy(d.hisob.davr_boshi)} dan · oxirgi hisob: ${this.esc(d.hisob.hisoblangan)}
					· <a href="/app/tolov-rejasi/${encodeURIComponent(d.hisob.reja)}" target="_blank">reja ↗</a></div>
			</div>` : ""}
			<div class="d-actions">
				${qlar.length ? `<button class="btn-suhbat">🎧 Suhbatlar (${qlar.length})${
					qlar.filter((q) => q.ai_xulosa).length
						? ` · ${qlar.filter((q) => q.ai_xulosa).length} tahlil` : ""}</button>` : ""}
				<button class="btn-call">📞 Qo'ng'iroq natijasi</button>
				<button class="btn-recalc">↻ Qayta hisoblash</button>
				<a class="btn-doc" href="/app/qarz-ishi/${encodeURIComponent(c.name)}">Ishni ochish ↗</a>
				${this.data.rahbar ? `<button class="btn-reassign">Mas'ulni almashtirish</button>` : ""}
				${this.data.ketgan_huquqi
					? (c.ketgan || this.fKetgan
						? `<button class="btn-ketgan back">↩ Ketgan belgisini olish</button>`
						: `<button class="btn-ketgan">🚪 O'quvchi ketdi</button>`) : ""}
			</div>
			${sibs}${xulosa}${months}${pays}${calls}${tl}
		`);

		this.body.find(".btn-suhbat").on("click", () => this.suhbat_dialog());
		this.body.find(".btn-call").on("click", () => this.call_dialog());
		this.body.find(".btn-recalc").on("click", () => {
			frappe.call({
				method: `${QARZ_M}.qayta_hisobla`,
				args: { case: this.detail.case.name },
				freeze: true, freeze_message: "Qayta hisoblanmoqda…",
				callback: (r) => {
					this.detail = r.message;
					this.render_detail();
					frappe.show_alert({ message: "Qayta hisoblandi", indicator: "green" });
					this.load();
				},
			});
		});
		this.body.find(".btn-reassign").on("click", () => this.reassign_dialog());
		this.body.find(".btn-ketgan").on("click", (e) =>
			$(e.currentTarget).hasClass("back") ? this.ketgan_qaytar() : this.ketgan_dialog());
	}

	// Menyu ochiq holda ro'yxat va tugma yorlig'ini yangilash
	sinf_sync(refreshBoxes) {
		const dd = this.body.find(".sinf-dd");
		dd.find(".dd-btn b").text(this.sinfLabel());
		if (refreshBoxes) {
			dd.find("input[data-sinf]").each((i, el) =>
				(el.checked = this.fSinflar.has(String($(el).data("sinf")))));
		}
		dd.find("input[data-paralel]").each((i, el) => {
			const p = String($(el).data("paralel"));
			const lst = this.sinflar().filter((x) => (x.paralel || "—") === p);
			el.checked = lst.length > 0 && lst.every((x) => this.fSinflar.has(x.sinf));
		});
		this.render_list();
	}

	// ================= actions =================
	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".q").on("input", frappe.utils.debounce((e) => { this.q = e.target.value; this.render_list(); }, 250));
		this.body.find(".fmanager").on("change", (e) => { this.fManager = e.target.value; this.render_list(); });
		this.body.find(".fstatus").on("change", (e) => { this.fStatus = e.target.value; this.render_list(); });
		// Sinf tanlash dropdowni (bir vaqtda bir nechta sinf)
		const dd = this.body.find(".sinf-dd");
		dd.find(".dd-btn").on("click", (e) => { e.stopPropagation(); dd.find(".dd-menu").prop("hidden", (i, v) => !v); });
		dd.find(".dd-menu").on("click", (e) => e.stopPropagation());
		$(document).off("click.tzsinf").on("click.tzsinf", () => this.body.find(".dd-menu").prop("hidden", true));
		dd.find("input[data-sinf]").on("change", (e) => {
			const v = $(e.currentTarget).data("sinf");
			e.currentTarget.checked ? this.fSinflar.add(v) : this.fSinflar.delete(v);
			this.sinf_sync();
		});
		dd.find("input[data-paralel]").on("change", (e) => {
			const p = String($(e.currentTarget).data("paralel"));
			const on = e.currentTarget.checked;
			for (const x of this.sinflar()) {
				if ((x.paralel || "—") !== p) continue;
				on ? this.fSinflar.add(x.sinf) : this.fSinflar.delete(x.sinf);
			}
			this.sinf_sync(true);
		});
		dd.find(".dd-clear").on("click", () => { this.fSinflar.clear(); this.sinf_sync(true); });
		// Qarz turi dropdowni (kitob / forma / yotoqxona / o'quv to'lovi)
		const td = this.body.find(".tur-dd");
		td.find(".dd-btn").on("click", (e) => { e.stopPropagation(); td.find(".dd-menu").prop("hidden", (i, v) => !v); });
		td.find(".dd-menu").on("click", (e) => e.stopPropagation());
		td.find("input[data-tur]").on("change", (e) => {
			const v = String($(e.currentTarget).data("tur"));
			e.currentTarget.checked ? this.fTurlar.add(v) : this.fTurlar.delete(v);
			td.find(".dd-btn b").text(this.turLabel());
			this.render_list();
		});
		td.find(".dd-clear").on("click", () => {
			this.fTurlar.clear();
			td.find("input[data-tur]").prop("checked", false);
			td.find(".dd-btn b").text(this.turLabel());
			this.render_list();
		});
		this.body.find(`[data-act="ketgan"]`).on("click", () => {
			this.fKetgan = this.fKetgan ? 0 : 1;
			this.selected = null; this.detail = null;
			this.load();
		});
		this.body.find(".chips .chip").on("click", (e) => {
			const b = $(e.currentTarget).data("b");
			this.fBucket = this.fBucket === b ? "" : b;
			this.render();
		});
		this.body.find(".kpi.click").on("click", (e) => {
			this.fQueue = $(e.currentTarget).data("queue");
			this.render();
		});
	}

	// Suhbatlar oynasi: har yozuv uchun OVOZ + MATN + QISQA TAHLIL bir joyda.
	// Panel pastidagi ro'yxat qoladi, lekin bu oyna tepadan bir bosishda ochiladi —
	// menejer/rahbar audioni eshitib, matnini va AI xulosasini solishtiradi.
	suhbat_dialog() {
		const d = this.detail;
		if (!d) return;
		const qlar = (d.qongiroqlar || []).filter((q) => q.audio || q.transkript);
		if (!qlar.length) {
			frappe.msgprint(__("Bu to'lovchida ovoz yozuvi yoki transkript yo'q."));
			return;
		}

		const dlg = new frappe.ui.Dialog({
			title: __("Suhbatlar — {0}", [d.case.student_name]),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "ro'yxat" }],
		});

		dlg.fields_dict["ro'yxat"].$wrapper.html(
			`<div class="tz-suhbatlar">${qlar.map((q, i) => this.suhbat_karta(q, i)).join("")}</div>`
		);

		// Tahlil yo'q bo'lsa — shu oynadan buyurtma qilish mumkin
        dlg.$wrapper.on("click", ".sb-tahlil-btn", (e) => {
			const nom = $(e.currentTarget).data("q");
			$(e.currentTarget).prop("disabled", true).text(__("Tahlil qilinmoqda…"));
			frappe.call({
				method: "target_zenit.telefoniya.analiz.qolda",
				args: { qongiroq: nom },
				callback: (r) => {
					const m = r.message || {};
					if (m.holat === "tayyor") {
						dlg.hide();
						this.load_detail(d.case.name, true);
						frappe.show_alert({ message: __("Tahlil tayyor"), indicator: "green" });
					} else {
						frappe.show_alert({
							message: __("Tahlil bo'lmadi: {0}", [m.sabab || m.holat || "?"]),
							indicator: "orange",
						}, 8);
						$(e.currentTarget).prop("disabled", false).text(__("🤖 Tahlil qilish"));
					}
				},
			});
		});

		// Matnni yig'ish/ochish
		dlg.$wrapper.on("click", ".sb-matn-tgl", (e) => {
			const $b = $(e.currentTarget);
			const $m = $b.closest(".sb-card").find(".sb-matn");
			$m.toggleClass("yopiq");
			$b.text($m.hasClass("yopiq") ? __("matnni ko'rsatish") : __("matnni yashirish"));
		});

		dlg.show();
	}

	suhbat_karta(q, i) {
		const url = `/api/method/target_zenit.telefoniya.api.stream_recording?qongiroq=${encodeURIComponent(q.name)}`;
		const natija = q.tugash_sababi || "";
		const pill = natija === "Javob berildi" ? "st-ok" : "st-mut";

		// AI xulosasi qat'iy formatda keladi ("MAVZU: …") — qatorlarga ajratib chiqaramiz
		const xulosa = (q.ai_xulosa || "").trim();
		const qatorlar = xulosa ? xulosa.split(/\r?\n/).map((x) => x.trim()).filter(Boolean) : [];
		const tahlil = qatorlar.length
			? `<div class="sb-tahlil">${qatorlar.map((qt) => {
					const m = qt.match(/^([A-ZА-ЯЎҚҒҲ' ]{3,20}):\s*(.*)$/);
					if (!m) return `<div class="sb-t-row"><span class="sb-t-v">${this.esc(qt)}</span></div>`;
					const bosh = m[1].trim(), qiymat = (m[2] || "").trim();
					const yoq = /^(yo'q|yoq|—|-)$/i.test(qiymat);
					if (yoq) return "";
					const holat = bosh === "MIJOZ HOLATI"
						? ` sb-h-${/ijobiy/i.test(qiymat) ? "ok" : /qarshi/i.test(qiymat) ? "bad" : "mut"}` : "";
					const diqqat = bosh === "DIQQAT" ? " sb-diqqat" : "";
					return `<div class="sb-t-row${diqqat}">
						<span class="sb-t-k">${this.esc(bosh)}</span>
						<span class="sb-t-v${holat}">${this.esc(qiymat)}</span></div>`;
				}).join("")}</div>`
			: `<div class="sb-yoq">Qisqa tahlil yo'q
				${q.transkript ? `<button class="btn-mini sb-tahlil-btn" data-q="${this.esc(q.name)}">🤖 Tahlil qilish</button>` : ""}</div>`;

		return `<div class="sb-card">
			<div class="sb-head">
				<b>${this.dtm(q.boshlandi)}</b>
				<span class="call-dir ${q.yonalish === "Kiruvchi" ? "in" : "out"}">${q.yonalish === "Kiruvchi" ? "📥" : "📤"}</span>
				${q.suhbat_vaqti ? `<span class="mini">${this.dur(q.suhbat_vaqti)}</span>` : ""}
				${natija ? `<span class="pill ${pill}">${this.esc(natija)}</span>` : ""}
				<span class="spacer"></span>
				<span class="mini">${this.esc(q.menejer)}</span>
				<a class="mini" href="/app/telefon-qongirogi/${encodeURIComponent(q.name)}" target="_blank">↗</a>
			</div>
			<div class="sb-grid">
				<div class="sb-chap">
					${q.audio
						? `<audio class="sb-audio" controls preload="none" src="${url}"></audio>`
						: `<div class="mini">${q.yozuv_ochirildi ? "yozuv o'chirilgan" : "yozuv yo'q"}</div>`}
					${q.transkript
						? `<div class="sb-matn-bar">
								<span class="mini">${q.transkript_sozlar || 0} so'z</span>
								<button class="btn-mini ghost sb-matn-tgl">matnni ko'rsatish</button>
							</div>
							<div class="sb-matn yopiq">${this.esc(q.transkript)}</div>`
						: `<div class="mini">Transkript yo'q</div>`}
				</div>
				<div class="sb-ong">${tahlil}</div>
			</div>
		</div>`;
	}

	call_dialog() {
		const c = this.detail.case;
		const dlg = new frappe.ui.Dialog({
			title: `Qo'ng'iroq natijasi — ${c.student_name}`,
			fields: [
				{ fieldname: "kanal", fieldtype: "Select", label: "Kanal", options: "Qo'ng'iroq\nSMS\nTelegram\nYuzma-yuz\nBoshqa", default: "Qo'ng'iroq", reqd: 1 },
				{ fieldname: "aloqa_natijasi", fieldtype: "Select", label: "Aloqa natijasi", reqd: 1,
					options: "\nGaplashildi\nJavob yo'q\nBand\nQayta qo'ng'iroq so'radi\nO'chirilgan\nNoto'g'ri raqam" },
				{ fieldname: "hisob_natijasi", fieldtype: "Select", label: "Suhbat natijasi",
					options: "\nVa'da berdi\nBo'lib to'lashga kelishildi\nE'tiroz-nizo\nTo'laganman deydi\nRad etdi\nMa'lumot oldi",
					depends_on: "eval:doc.aloqa_natijasi=='Gaplashildi'",
					mandatory_depends_on: "eval:doc.aloqa_natijasi=='Gaplashildi'" },
				{ fieldname: "vada_summa", fieldtype: "Currency", label: "Va'da summasi", default: c.qarz_summa,
					depends_on: 'eval:doc.hisob_natijasi=="Va\'da berdi"' },
				{ fieldname: "vada_sana", fieldtype: "Date", label: "Va'da sanasi",
					depends_on: 'eval:doc.hisob_natijasi=="Va\'da berdi"' },
				{ fieldname: "komment", fieldtype: "Small Text", label: "Komment" },
				{ fieldtype: "Section Break" },
				{ fieldname: "keyingi_harakat", fieldtype: "Select", label: "Keyingi harakat", reqd: 1,
					options: "Qayta qo'ng'iroq\nVa'dani kutish\nEskalatsiya\nRaqam aniqlash\nBoshqa", default: "Qayta qo'ng'iroq" },
				{ fieldname: "keyingi_sana", fieldtype: "Date", label: "Keyingi sana", reqd: 1,
					default: frappe.datetime.add_days(this.today(), 1) },
			],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				// Va'da bo'lsa va menejer keyingi sanani o'zgartirmagan bo'lsa —
				// keyingi aloqa avtomatik va'dadan bir kun keyinga suriladi
				const dflt = frappe.datetime.add_days(this.today(), 1);
				if (v.hisob_natijasi === "Va'da berdi" && v.vada_sana && v.keyingi_sana === dflt) {
					v.keyingi_sana = frappe.datetime.add_days(v.vada_sana, 1);
				}
				frappe.call({
					method: `${QARZ_M}.save_call`,
					args: { payload: Object.assign({ qarz_ishi: c.name }, v) },
					freeze: true,
					callback: () => {
						dlg.hide();
						frappe.show_alert({ message: "Saqlandi", indicator: "green" });
						this.load();
						this.load_detail(c.name, true);
					},
				});
			},
		});
		dlg.show();
	}

	// O'quvchi maktabni tashladi — belgi Student hujjatiga yoziladi
	ketgan_dialog() {
		const c = this.detail.case;
		const dlg = new frappe.ui.Dialog({
			title: `O'quvchi ketdi — ${c.student_name}`,
			fields: [
				{ fieldtype: "HTML", options: `<div class="text-muted" style="font-size:12px;margin-bottom:6px">
					Student hujjatida <b>ketish sanasi</b> qo'yiladi va o'quvchi nofaol (enabled=0) bo'ladi.
					Ketish sanasidan keyingi oylar jadvaldan chiqadi, qolgan qarz esa
					«Ketganlar» ro'yxatida saqlanadi.</div>` },
				{ fieldname: "sana", fieldtype: "Date", label: "Ketgan sanasi", reqd: 1, default: this.today() },
				{ fieldname: "sabab", fieldtype: "Small Text", label: "Sabab (izoh)" },
			],
			primary_action_label: "Belgilash",
			primary_action: (v) => {
				frappe.confirm(`${c.student_name} — ketgan deb belgilansinmi?`, () => {
					frappe.call({
						method: `${QARZ_M}.ketgan_belgilash`,
						args: { case: c.name, sana: v.sana, sabab: v.sabab },
						freeze: true, freeze_message: "Belgilanmoqda…",
						callback: () => {
							dlg.hide();
							frappe.show_alert({ message: "Ketgan deb belgilandi", indicator: "orange" });
							this.selected = null; this.detail = null;
							this.load();
						},
					});
				});
			},
		});
		dlg.show();
	}

	ketgan_qaytar() {
		const c = this.detail.case;
		frappe.confirm(`${c.student_name} — «ketgan» belgisi olib tashlansinmi?`, () => {
			frappe.call({
				method: `${QARZ_M}.qaytardi`,
				args: { case: c.name },
				freeze: true,
				callback: () => {
					frappe.show_alert({ message: "Belgisi olindi", indicator: "green" });
					this.selected = null; this.detail = null;
					this.load();
				},
			});
		});
	}

	reassign_dialog() {
		const c = this.detail.case;
		// Mas'ul faqat SOTUV MENEJERI bo'la oladi — ro'yxat backenddan
		// (faol "Sotuv meneger" rolli foydalanuvchilar) keladi
		const sotuvchilar = (this.data && this.data.sotuv_menejerlar) || [];
		if (!sotuvchilar.length) {
			frappe.msgprint("Faol «Sotuv meneger» rolli foydalanuvchi topilmadi — avval rol biriktiring.");
			return;
		}
		const dlg = new frappe.ui.Dialog({
			title: "Mas'ulni almashtirish",
			fields: [{
				fieldname: "masul", fieldtype: "Select", label: "Yangi mas'ul (sotuv menejeri)", reqd: 1,
				options: sotuvchilar.map((m) => ({ value: m.name, label: `${m.full_name} (${m.name})` })),
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				frappe.call({
					method: `${QARZ_M}.reassign`,
					args: { case: c.name, masul: v.masul },
					callback: () => { dlg.hide(); this.load(); this.load_detail(c.name, true); },
				});
			},
		});
		dlg.show();
	}
}
