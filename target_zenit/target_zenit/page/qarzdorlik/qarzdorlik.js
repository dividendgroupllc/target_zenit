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

	statusPill(st) {
		const cls = {
			"Yangi": "new", "Urinilmoqda": "try", "Gaplashildi - Va'da": "ok",
			"Gaplashildi - Nizo": "warn", "Bo'lib to'lash": "ok", "Va'da buzildi": "bad",
			"Aloqa yo'q": "mut", "To'lov tekshirilmoqda": "blue", "Eskalatsiya": "bad",
		}[st] || "mut";
		return `<span class="pill st-${cls}">${this.esc(st)}</span>`;
	}
	bucketPill(b) {
		if (!b) return "";
		const cls = { "1-30": "b1", "31-60": "b2", "61-90": "b3", "90+": "b4", "Ketgan-qarzli": "b4" }[b] || "b1";
		return `<span class="pill bk-${cls}">${this.esc(b)}</span>`;
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
	filtered() {
		const q = this.q.trim().toLowerCase();
		const today = this.today();
		return (this.data.cases || []).filter((c) => {
			if (this.fManager && c.masul !== this.fManager) return false;
			if (this.fBucket && c.aging_bucket !== this.fBucket) return false;
			if (this.fStatus && c.ishlov_status !== this.fStatus) return false;
			if (this.fQueue === "today" && !(c.keyingi_aloqa && c.keyingi_aloqa <= today)) return false;
			if (this.fQueue === "overdue" && !(c.keyingi_aloqa && c.keyingi_aloqa < today)) return false;
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
						<span class="badge-qarz">Qarzdorlar: <b>${this.fmt(st.ochiq)}</b> ta · jami <b>${this.fmt(st.jami_qarz)}</b> so'm</span>
					</div>
				</div>
				<div class="spacer"></div>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="grid cols-5 mb kpis">
				<div class="card kpi click ${this.fQueue === "today" ? "sel" : ""}" data-queue="today">
					<div class="lab"><span class="pin b"></span>Bugun aloqa</div>
					<div class="val">${this.fmt(st.bugun)}</div><div class="sub">keyingi aloqa = bugun</div></div>
				<div class="card kpi click ${this.fQueue === "overdue" ? "sel" : ""}" data-queue="overdue">
					<div class="lab"><span class="pin r"></span>O'tib ketgan</div>
					<div class="val">${this.fmt(st.otgan)}</div><div class="sub">aloqa sanasi o'tgan</div></div>
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
				<select class="fstatus">
					<option value="">Barcha statuslar</option>
					${["Yangi", "Urinilmoqda", "Gaplashildi - Va'da", "Gaplashildi - Nizo", "Bo'lib to'lash",
						"Va'da buzildi", "Aloqa yo'q", "To'lov tekshirilmoqda", "Eskalatsiya"].map((s) =>
						`<option ${this.fStatus === s ? "selected" : ""}>${s}</option>`).join("")}
				</select>
				<div class="chips">${["1-30", "31-60", "61-90", "90+"].map(bchip).join("")}</div>
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
		const html = rows.length
			? `<table class="tbl">
				<thead><tr><th>O'quvchi</th><th>Sinf</th><th class="r">Qarz</th><th>Yoshi</th><th>Status</th><th>Keyingi</th><th>Mas'ul</th></tr></thead>
				<tbody>
				${rows.map((c) => `
					<tr data-case="${this.esc(c.name)}" class="${this.selected === c.name ? "sel" : ""} ${c.keyingi_aloqa && c.keyingi_aloqa < today ? "late" : ""}">
						<td><div class="nm">${this.esc(c.student_name)}</div>
							<div class="mini">${this.esc(c.payer_name || "")} ${this.tel(c.payer_phone)}</div></td>
						<td>${this.esc(c.sinf || "—")}</td>
						<td class="r money">${this.fmt(c.qarz_summa)}</td>
						<td>${this.bucketPill(c.aging_bucket)}</td>
						<td>${this.statusPill(c.ishlov_status)}</td>
						<td class="${c.keyingi_aloqa && c.keyingi_aloqa < today ? "red" : ""}">${this.dmy(c.keyingi_aloqa)}</td>
						<td class="mini">${this.esc((this.data.managers.find((m) => m.name === c.masul) || {}).full_name || c.masul || "")}</td>
					</tr>`).join("")}
				</tbody></table>`
			: `<div class="empty">Filtrga mos ish topilmadi</div>`;
		this.body.find(".list").html(html);
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
		for (const g of d.guardians || [])
			if (g.mobile_number) phones.push(`${this.esc(g.guardian_name)}${g.relation ? " (" + this.esc(g.relation) + ")" : ""}: ${this.tel(g.mobile_number)}`);
		if (d.student_phone) phones.push(`O'quvchi: ${this.tel(d.student_phone)}`);

		const cheklov = c.aloqa_cheklovi
			? `<div class="alert-cheklov">⚠ Aloqa cheklovi: <b>${this.esc(c.aloqa_cheklovi)}</b></div>` : "";

		const sibs = (d.siblings || []).length
			? `<div class="box"><div class="box-t">Shu to'lovchining boshqa farzandlari</div>
				${d.siblings.map((s) => `<div class="sib">${this.esc(s.student_name)} — <b>${this.fmt(s.qarz_summa)}</b> so'm
					${this.statusPill(s.ishlov_status)} <span class="mini">mas'ul: ${this.esc(s.masul)}</span></div>`).join("")}</div>` : "";

		const months = `<div class="box"><div class="box-t">To'lov jadvali</div>
			<table class="tbl mini-tbl"><thead><tr><th>Oy</th><th>Muddat</th><th class="r">Summa</th><th class="r">To'langan</th><th class="r">Qoldiq</th><th>Holat</th></tr></thead>
			<tbody>${(d.months || []).map((m) => `
				<tr class="mh-${this.esc(m.holat)}"><td>${this.esc(m.oy_label)}</td><td>${this.dmy(m.due_date)}</td>
				<td class="r">${this.fmt(m.amount)}</td><td class="r">${this.fmt(m.paid_amount)}</td>
				<td class="r money">${this.fmt(m.outstanding)}</td><td>${this.esc(m.holat)}</td></tr>`).join("")}
			</tbody></table></div>`;

		const pays = `<div class="box"><div class="box-t">To'lovlar (${(d.payments || []).length})</div>
			${(d.payments || []).length ? `<table class="tbl mini-tbl"><tbody>
				${d.payments.slice(0, 12).map((p) => `
					<tr><td>${this.dmy(p.posting_date)}</td><td class="r money">${this.fmt(p.amount_uzs)}</td>
					<td class="mini">${this.esc(p.mode_of_payment || "")} ${p.currency !== "UZS" ? "(" + this.esc(p.currency) + ")" : ""}</td></tr>`).join("")}
			</tbody></table>` : `<div class="mini">To'lov yo'q</div>`}</div>`;

		const tl = `<div class="box"><div class="box-t">Timeline</div>
			${(d.ays || []).length ? d.ays.map((a) => `
				<div class="tl-item">
					<div class="tl-head"><b>${this.esc(a.kanal)}</b> · ${this.esc(a.aloqa_natijasi)}${a.hisob_natijasi ? " → " + this.esc(a.hisob_natijasi) : ""}
						<span class="mini">${this.esc(frappe.datetime.str_to_user(a.vaqt))} · ${this.esc(a.masul)}</span></div>
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
					<div>${this.bucketPill(c.aging_bucket)} ${this.statusPill(c.ishlov_status)}</div>
				</div>
			</div>
			${cheklov}
			<div class="d-actions">
				<button class="btn-call">📞 Qo'ng'iroq natijasi</button>
				<a class="btn-doc" href="/app/qarz-ishi/${encodeURIComponent(c.name)}">Ishni ochish ↗</a>
				${this.data.rahbar ? `<button class="btn-reassign">Mas'ulni almashtirish</button>` : ""}
			</div>
			${sibs}${months}${pays}${tl}
		`);

		this.body.find(".btn-call").on("click", () => this.call_dialog());
		this.body.find(".btn-reassign").on("click", () => this.reassign_dialog());
	}

	// ================= actions =================
	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".q").on("input", frappe.utils.debounce((e) => { this.q = e.target.value; this.render_list(); }, 250));
		this.body.find(".fmanager").on("change", (e) => { this.fManager = e.target.value; this.render_list(); });
		this.body.find(".fstatus").on("change", (e) => { this.fStatus = e.target.value; this.render_list(); });
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

	reassign_dialog() {
		const c = this.detail.case;
		const dlg = new frappe.ui.Dialog({
			title: "Mas'ulni almashtirish",
			fields: [{ fieldname: "masul", fieldtype: "Link", options: "User", label: "Yangi mas'ul", reqd: 1 }],
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
