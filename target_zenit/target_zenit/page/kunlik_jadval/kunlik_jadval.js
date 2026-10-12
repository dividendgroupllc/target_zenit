// Copyright (c) 2026, Target Zenit — Kunlik jadval (o'quvchi/ota-ona/o'qituvchi ko'rinishi)
// Sana + sinf (yoki o'qituvchi) -> shu kun darslari KUNLIK LENTA ko'rinishida, o'zgarish overlay bilan
// (bekor = chizilgan, o'rinbosar = yangi o'qituvchi yashil). Telefonga mos.
frappe.pages["kunlik-jadval"].on_page_load = function (wrapper) {
	new TZKunlikJadval(wrapper);
};

const KJ_OB = "target_zenit.dars_jadvali.orinbosarlik";
const KJ_OJ = "target_zenit.dars_jadvali.oqituvchi_jadval";
const KJ_MJ = "target_zenit.target_zenit.page.mening_jadvalim.mening_jadvalim";

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
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-kj"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	menejermi() {
		return frappe.user.has_role(["System Manager", "Zavuch", "Academics User", "Education Manager"]);
	}
	boot() {
		frappe.call({
			method: `${KJ_OJ}.filtr_variantlari`,
			callback: (r) => {
				this.guruhlar = ((r.message || {}).guruhlar || []);
				const sinf = this.guruhlar.find((g) => g.custom_guruh_turi === "Sinf");
				if (sinf) this.guruh = sinf.name;
				frappe.call({
					method: `${KJ_OJ}.oqituvchilar`,
					callback: (r2) => { this.instructors = r2.message || []; this.bootPanel(); },
					error: () => this.bootPanel(),
				});
			},
			error: () => this.bootPanel(),
		});
	}
	// «Qiladigan ishlarim» — o'z instructorini ham shu chaqiruvdan olamiz
	bootPanel() {
		frappe.call({
			method: `${KJ_MJ}.kun_paneli`,
			callback: (r) => {
				this.panel = r.message || {};
				this.ozIns = this.panel.oqituvchi || null;
				// O'qituvchi o'z kunlik rejasiga tushsin (zavuch sinf ko'rinishida qoladi)
				if (this.ozIns && !this.menejermi()) { this.rejim = "oqituvchi"; this.oqituvchi = this.ozIns; }
				this.load();
			},
			error: () => this.load(),
		});
	}
	// Boshqa o'qituvchi tanlansa (zavuch) — uning ishlarini ham ko'rsatamiz
	loadPanel() {
		const args = {};
		if (this.oqituvchi && this.oqituvchi !== this.ozIns) {
			if (!this.menejermi()) { this.panel = null; this.renderTodo(); return; }
			args.oqituvchi = this.oqituvchi;
		}
		frappe.call({
			method: `${KJ_MJ}.kun_paneli`, args: args,
			callback: (r) => { this.panel = r.message || {}; this.renderTodo(); },
			error: () => { this.panel = null; this.renderTodo(); },
		});
	}
	load() {
		this.renderShell();
		this.renderTodo();
		if (this.rejim === "sinf") {
			if (!this.guruh) { this.renderBody({ darslar: [], xabar: "Sinf tanlang" }); return; }
			frappe.call({ method: `${KJ_OB}.guruh_kun`, args: { sana: this.sana, guruh: this.guruh }, callback: (r) => this.renderBody(r.message), error: () => this.renderBody(null) });
		} else {
			if (!this.oqituvchi) { this.renderBody({ darslar: [], xabar: "O'qituvchi tanlang" }); return; }
			if (!this.panel || (this.panel.oqituvchi || null) !== this.oqituvchi) this.loadPanel();
			// O'qituvchi rejimi = kunlik reja: oddiy lenta o'rniga to'liq kun qaydnomasi
			this.loadBatafsil();
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
			<div class="ctrl">
				<h1>Kunlik reja</h1>
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
			<div class="kj-split">
				<div class="feed"><div class="loading">Yuklanmoqda…</div></div>
				<aside class="todo-box"></aside>
			</div>
		`);
		this.body.find(".seg button").on("click", (e) => { this.rejim = $(e.currentTarget).data("r"); this.load(); });
		this.body.find(".fsana").on("change", (e) => { this.sana = e.target.value; this.load(); });
		this.body.find(".fsel").on("change", (e) => {
			if (this.rejim === "sinf") this.guruh = e.target.value;
			else { this.oqituvchi = e.target.value; this.panel = null; }
			this.load();
		});
		this.body.find(".nav").on("click", (e) => { this.sana = frappe.datetime.add_days(this.sana, Number($(e.currentTarget).data("d"))); this.load(); });
	}
	kunYakuni(y) {
		const el = (b, m, cls) => `<div class="ky ${cls || ""}"><b>${b}</b><span>${m}</span></div>`;
		return `<div class="ky-strip">
			${el(y.jami || 0, "dars")}
			${el(`${y.otilgan || 0}/${(y.jami || 0) - (y.bekor || 0)}`, "mavzu o'tildi", y.otilmagan ? "warn" : "ok")}
			${el(y.baho_soni || 0, "baho qo'ydim")}
			${el(y.ortacha != null ? y.ortacha : "—", "o'rtacha baho")}
			${el(y.yoq || 0, "yo'q", y.yoq ? "warn" : "")}
			${y.kechikdi ? el(y.kechikdi, "kechikdi", "warn") : ""}
			${el(`${y.uy_vazifa || 0}`, "uy vazifa berildi")}
			${y.uv_tekshirilmagan ? el(y.uv_tekshirilmagan, "tekshirilmagan", "warn") : ""}
			${y.qoshimcha ? el(y.qoshimcha, "qo'shimcha dars", "extra") : ""}
			${el(`${y.tugallangan || 0}/${(y.jami || 0) - (y.bekor || 0)}`, "to'liq tugallandi", (y.tugallangan === ((y.jami || 0) - (y.bekor || 0))) ? "ok" : "")}
		</div>`;
	}

	darsKarta(x) {
		const bekor = x.ozgarish && x.ozgarish.tur === "Bekor";
		const berilgan = x.ozgarish && x.ozgarish.tur === "O'rinbosar" && !x.qoshimcha;
		const j = x.jurnal || {}; const uv = x.uy_vazifa; const b = x.bajarilish;
		const reja = x.reja || {};
		const cl = x.checklist || { qadamlar: [] };
		const holatCls = bekor ? "b-bekor" : (berilgan ? "b-berilgan"
			: (cl.jami && cl.bajarilgan === cl.jami ? "b-tugal"
				: (x.holat_vaqt === "hozir" ? "b-hozir"
					: (x.holat_vaqt === "o'tgan" ? "b-qolgan" : "b-kelajak"))));
		const nishon = bekor ? `<span class="bg bekor">⛔ bekor qilindi${x.ozgarish.sabab ? " — " + this.esc(x.ozgarish.sabab) : ""}</span>`
			: berilgan ? `<span class="bg berilgan">🔄 ${this.esc(x.ozgarish.yangi_oqituvchi_nomi || "boshqa o'qituvchi")}ga berildi</span>`
			: x.qoshimcha ? `<span class="bg extra">➕ Zavuch yuklagan qo'shimcha dars${x.ozgarish && x.ozgarish.asl_oqituvchi_nomi ? ` (asl: ${this.esc(x.ozgarish.asl_oqituvchi_nomi)})` : ""}${x.ozgarish && x.ozgarish.sabab ? ` · ${this.esc(x.ozgarish.sabab)}` : ""}</span>`
			: x.holat_vaqt === "hozir" ? `<span class="bg hozir">⏱ HOZIR</span>` : "";

		return `<div class="bd-row ${holatCls}" data-jy="${this.esc(x.jadval_yozuvi)}" data-sana="${this.esc(this.batafsil.sana)}">
			<div class="bd-time">
				<div class="bd-no">${x.dars_raqami || ""}-dars</div>
				<div class="bd-hh">${this.esc(x.boshlanish)}</div>
				<div class="bd-mm">${this.esc(x.tugash)}</div>
			</div>
			<div class="bd-main">
				<div class="bd-head">
					<span class="bd-g">${this.esc(x.guruh_nomi)}</span>
					<span class="bd-f">${this.esc(x.fan)}</span>
					${x.xona ? `<span class="bd-x">🚪 ${this.esc(x.xona)}</span>` : ""}
					<span class="bd-n">👥 ${x.oquvchi_soni || 0}</span>
					${nishon}
				</div>
				${bekor ? "" : `
				<div class="bd-lines">
					<div class="bd-l">
						<span class="ik">📘</span>
						<span class="lb">Rejada:</span>
						<span class="vl">${reja.keyingi ? this.esc(reja.keyingi.mavzu || "—") : `<span class="mini">o'quv reja biriktirilmagan</span>`}</span>
						${reja.jami ? `<span class="mini">(reja ${reja.otildi || 0}/${reja.jami})</span>` : ""}
					</div>
					<div class="bd-l">
						<span class="ik">${b ? "✅" : "⬜"}</span>
						<span class="lb">O'tildi:</span>
						<span class="vl">${b ? `${this.esc(b.mavzu || "mavzu ko'rsatilmagan")}${b.holat && b.holat !== "O'tildi" ? ` <span class="mini">(${this.esc(b.holat)})</span>` : ""}${b.vaqt ? ` <span class="mini">${this.esc(b.vaqt)} da belgilandi</span>` : ""}${b.izoh ? `<div class="mini iz">${this.esc(b.izoh)}</div>` : ""}` : `<span class="mini warn-t">hali belgilanmagan</span>`}</span>
					</div>
					<div class="bd-l">
						<span class="ik">🧾</span>
						<span class="lb">Yo'qlama:</span>
						<span class="vl">${j.belgilangan ? `keldi ${j.keldi}${j.yoq ? ` · <b class="r">yo'q ${j.yoq}</b>` : ""}${j.kechikdi ? ` · <b class="y">kechikdi ${j.kechikdi}</b>` : ""}${j.oxirgi_vaqt ? ` <span class="mini">${this.esc(j.oxirgi_vaqt)}</span>` : ""}` : `<span class="mini warn-t">olinmagan (hamma keldi deb hisoblanadi)</span>`}</span>
					</div>
					<div class="bd-l">
						<span class="ik">🎯</span>
						<span class="lb">Baho:</span>
						<span class="vl">${j.baholangan ? `<b>${j.baholangan}</b> ta qo'ydim · o'rtacha <b>${j.ortacha}</b> <span class="mini">(${j.eng_past}…${j.eng_yuqori})</span>` : `<span class="mini">baho qo'yilmagan</span>`}</span>
					</div>
					<div class="bd-l">
						<span class="ik">🏠</span>
						<span class="lb">Uy vazifa:</span>
						<span class="vl">${uv ? `${this.esc((uv.vazifa || "").slice(0, 90))}${uv.max_ball ? ` <span class="mini">${uv.max_ball} ball</span>` : ""}${uv.muddat ? ` <span class="mini">→ ${this.esc(this.dmy(uv.muddat))}</span>` : ""}${uv.tekshiriladi ? `<div class="mini">${uv.tekshirilgan ? `tekshirildi ${uv.tekshirilgan}/${x.oquvchi_soni} · bajardi ${uv.bajardi}${uv.bajarmadi ? ` · bajarmadi ${uv.bajarmadi}` : ""}` : `<span class="warn-t">tekshirilmagan</span>`}</div>` : `<div class="mini">tekshirilmaydi</div>`}` : `<span class="mini">berilmagan</span>`}</span>
					</div>
				</div>
				<div class="bd-chips">
					${(cl.qadamlar || []).map((q) => `<span class="chip ${q.ok ? "ok" : "no"}">${q.ok ? "✓" : "○"} ${this.esc(q.nom)}</span>`).join("")}
					${cl.qolgan && cl.qolgan.length ? `<span class="chip rem">qoldi: ${this.esc(cl.qolgan.join(", "))}</span>` : ""}
					<span class="bd-go">Darsni ochish →</span>
				</div>`}
			</div>
		</div>`;
	}

	renderBatafsil() {
		const d = this.batafsil || {};
		const box = this.body.find(".feed");
		if (!box.length) return;
		const darslar = d.darslar || [];
		box.html(`
			<div class="card bugun-card2">
				<div class="box-t">📌 ${this.esc(d.kun || "")} ${this.esc(this.dmy(d.sana))} — kun qaydnomasi
					<span class="mini">${this.esc(this.oqNomi())} · nima qilindi, nima qolgan</span></div>
				${darslar.length ? this.kunYakuni(d.yakun || {}) : ""}
				${(d.qoshimcha || []).length ? `<div class="extra-ban">➕ Zavuch bugun sizga <b>${d.qoshimcha.length}</b> ta qo'shimcha dars yukladi — pastda «qo'shimcha dars» belgisi bilan ko'rsatilgan</div>` : ""}
				${darslar.length ? `<div class="bd-list">${darslar.map((x) => this.darsKarta(x)).join("")}</div>`
					: `<div class="empty">Bugun dars yo'q</div>`}
			</div>`);
		box.find(".bd-row").not(".b-bekor").on("click", (e) => {
			const r = $(e.currentTarget);
			frappe.set_route("dars-sessiya", r.data("jy"), r.data("sana"));
		});
	}

	oqNomi() {
		const t = (this.instructors || []).find((x) => x.name === this.oqituvchi);
		return (t && t.instructor_name) || this.oqituvchi || "";
	}
	trendBelgi(t) { return t > 0 ? `<span class="tr up">▲</span>` : (t < 0 ? `<span class="tr dn">▼</span>` : ""); }
	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

	// Kun qaydnomasi (o'qituvchi rejimi) — batafsil dars kartalari
	loadBatafsil() {
		const args = { sana: this.sana };
		if (this.oqituvchi && this.oqituvchi !== this.ozIns) {
			if (!this.menejermi()) { this.batafsil = null; this.renderBatafsil(); return; }
			args.oqituvchi = this.oqituvchi;
		}
		this.body.find(".feed").html(`<div class="loading">Kun qaydnomasi yuklanmoqda…</div>`);
		frappe.call({
			method: `${KJ_MJ}.bugun_batafsil`, args: args,
			callback: (r) => { this.batafsil = r.message || {}; this.renderBatafsil(); },
			error: () => { this.batafsil = null; this.body.find(".feed").html(`<div class="empty">Xatolik</div>`); },
		});
	}

	// ---------- «Qiladigan ishlarim» (kunlik reja) ----------
	renderTodo() {
		const box = this.body.find(".todo-box");
		if (!box.length) return;
		const split = this.body.find(".kj-split");
		const yoq = () => { box.empty(); split.removeClass("has-todo"); };
		if (this.rejim !== "oqituvchi" || !this.oqituvchi) { yoq(); return; }
		const p = this.panel || {};
		if ((p.oqituvchi || null) !== this.oqituvchi) { yoq(); return; }
		const q = p.qoldirilgan || [];
		const dq = p.diqqat || [];
		const ikon = { jurnal: "📝", mavzu: "📘", uy_vazifa: "🏠", uv_tekshirish: "✔️" };
		split.addClass("has-todo");
		if (!q.length && !dq.length) {
			box.html(`<div class="todo ok">✅ Qoldirilgan ish yo'q — jurnal, mavzu va uy vazifalar to'liq.</div>`);
			return;
		}
		box.html(`
			${q.length ? `<div class="todo">
				<div class="todo-t">⚠️ Qiladigan ishlarim <span class="mini">${p.qoldirilgan_jami || q.length} ta · oxirgi ${p.kun_soni || 14} kun</span></div>
				<div class="todo-l">${q.map((x) => `
					<div class="todo-r" data-jy="${this.esc(x.jadval_yozuvi)}" data-sana="${this.esc(x.sana)}">
						<span class="t-ik">${ikon[x.tur] || "•"}</span>
						<span class="t-d">${this.esc(this.dmy(x.sana))}</span>
						<span class="t-f">${this.esc(x.fan)} · ${this.esc(x.guruh_nomi || x.guruh)}</span>
						<span class="t-m">${this.esc(x.matn)}</span>
						<span class="t-go">Ochish →</span>
					</div>`).join("")}</div>
			</div>` : ""}
			${dq.length ? `<div class="todo diq">
				<div class="todo-t">🚩 Diqqat talab qiladi <span class="mini">${p.diqqat_jami || dq.length} o'quvchi · joriy chorak</span></div>
				<div class="todo-l">${dq.map((x) => `
					<div class="diq-r r-${this.esc(x.rang)}">
						<span class="d-dot"></span>
						<span class="d-nm">${this.esc(x.student_name)}</span>
						<span class="d-g">${this.esc(x.guruh_nomi || x.guruh)} · ${this.esc(x.fan)}</span>
						<span class="d-b">${x.ortacha != null ? x.ortacha : "—"}${x.trend > 0 ? " ▲" : (x.trend < 0 ? " ▼" : "")}</span>
						<span class="d-fl">${(x.bayroqlar || []).map((b) => `<span class="fl2">${this.esc(b)}</span>`).join("")}</span>
					</div>`).join("")}</div>
			</div>` : ""}`);
		box.find(".todo-r").on("click", (e) => {
			const r = $(e.currentTarget);
			frappe.set_route("dars-sessiya", r.data("jy"), r.data("sana"));
		});
	}
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }

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
