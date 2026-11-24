// Copyright (c) 2026, Target Zenit — Dars jadvali (zavuch paneli)
// Sinflar x darslar to'ri, kun bo'yicha. Manba: Jadval Yozuvi (haftalik shablon).
// Muharrir — jahon standartlari (Untis/Prime/aSc/TimeTabler sintezi):
//   bitta bosish = kartani ko'tarish, sudrab tashlash (drag&drop) ham ishlaydi,
//   ko'tarilganda slotlar jonli baholanadi (yashil/sariq/qizil + NEGA),
//   toza almashuv so'roqsiz bajariladi (undo bor), laganda (joylanmagan kartalar),
//   band katakka siqib chiqarish (bounce), undo/redo (Ctrl+Z / Ctrl+Y).
frappe.pages["dars-jadvali"].on_page_load = function (wrapper) {
	new TZDarsJadvali(wrapper);
};

const DJ_M = "target_zenit.target_zenit.page.dars_jadvali.dars_jadvali";
const IMP_M = "target_zenit.dars_jadvali.import_excel";
const MH_M = "target_zenit.dars_jadvali.muharrir";
const OJ_M = "target_zenit.dars_jadvali.oqituvchi_jadval";
const MH_ROLLAR = ["System Manager", "Zavuch", "Academics User", "Education Manager", "Xojakbar_Operator"];

class TZDarsJadvali {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dars jadvali"), single_column: true });
		this.data = null;
		this.kun = "Dushanba";
		this.versiya = null;
		this.fSinf = "";
		this.moving = null;      // kochirish_xarita natijasi (karta "qo'lda")
		this.undoStack = [];     // amallar tarixi (move/swap/unplace/displace)
		this.redoStack = [];
		this.busy = false;       // parallel amal bosilishidan himoya
		this.canEdit = MH_ROLLAR.some((r) => frappe.user_roles.includes(r));
		this.make_skeleton();
		this.load();
		this.listen_import();
		this.bind_keys();
	}

	// Fon vazifasi tugaganda natijani ko'rsatish
	listen_import() {
		frappe.realtime.on("jadval_import_tugadi", (r) => {
			if (this.import_dlg) this.import_dlg.hide();
			this.show_import_result(r);
			this.load();
		});
	}

	bind_keys() {
		$(document).on("keydown.tzjadval", (e) => {
			if (!this.canEdit) return;
			if ($(e.target).is("input, textarea, select")) return;
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
				e.preventDefault(); this.undo_op();
			} else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
				e.preventDefault(); this.redo_op();
			} else if (e.key === "Escape") {
				this.cancel_move();
				this.close_ctx();
			} else if (e.key === "Delete" && this.moving && !this.moving.lagandadan) {
				e.preventDefault(); this.mv_lagandaga();
			}
		});
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	// Fan nomidan barqaror rang (har fan doim bir xil rangda)
	rang(fan) {
		let h = 0;
		for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360;
		return h;
	}

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load(cb) {
		frappe.call({
			method: `${DJ_M}.get_data`,
			args: { versiya: this.versiya },
			freeze: !cb,
			callback: (r) => {
				this.data = r.message || {};
				if (this.data.xatolik) {
					this.body.html(`<div class="loading">${this.esc(this.data.xatolik)}</div>`);
					return;
				}
				this.versiya = this.data.versiya;
				this.render();
				if (cb) cb();
			},
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	// Sinfga mos qo'ng'iroq jadvali (pattern bo'yicha, tartib bilan)
	vaqt(sinf, no) {
		const qs = Object.values(this.data.qongiroqlar || {}).sort((a, b) => a.tartib - b.tartib);
		for (const q of qs) {
			for (let p of String(q.sinf_pattern || "").split(",")) {
				p = p.trim();
				if (!p) continue;
				const rx = new RegExp("^" + p.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
				if (rx.test(sinf)) {
					const row = (q.qatorlar || []).find((x) => x.turi === "Dars" && x.no === no);
					return row ? `${row.b}–${row.t}` : "";
				}
			}
		}
		return "";
	}

	sinflar() {
		const all = this.data.sinflar || [];
		return this.fSinf ? all.filter((s) => s === this.fSinf) : all;
	}

	render() {
		const d = this.data;
		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Dars jadvali</h1>
					<div class="sub">${this.esc(d.versiya)} · ${d.jami_yozuv} ta dars · ${(d.sinflar || []).length} sinf</div>
				</div>
				<div class="spacer"></div>
				<select class="fversiya">
					${(d.versiyalar || []).map((v) =>
						`<option value="${this.esc(v.name)}" ${v.name === d.versiya ? "selected" : ""}>${this.esc(v.nomi)} — ${this.esc(v.holat)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="controls mb">
				<div class="chips kunlar">
					${(d.kunlar || []).map((k) => `<button class="chip ${this.kun === k ? "on" : ""}" data-kun="${k}">${k}</button>`).join("")}
				</div>
				<div class="spacer"></div>
				${this.canEdit ? `
					<button class="refresh" data-act="undo" ${this.undoStack.length ? "" : "disabled"} title="Ctrl+Z">↶${this.undoStack.length ? ` ${this.undoStack.length}` : ""}</button>
					<button class="refresh" data-act="redo" ${this.redoStack.length ? "" : "disabled"} title="Ctrl+Y">↷</button>` : ""}
				<select class="fsinf">
					<option value="">Barcha sinflar</option>
					${(d.sinflar || []).map((s) => `<option value="${this.esc(s)}" ${this.fSinf === s ? "selected" : ""}>${this.esc(s)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="yuklama">O'qituvchi yuklamasi</button>
				<button class="refresh primary" data-act="import">⬆ Exceldan import</button>
			</div>

			<div class="mvbar-wrap"></div>
			<div class="laganda-wrap"></div>
			<div class="jadval-wrap card"></div>
		`);
		this.render_mvbar();
		this.render_laganda();
		this.render_grid();
		this.bind();
	}

	// ------------- ko'chirish banneri ("karta qo'lda") -------------
	mv_kun_hisob() {
		// Har kun uchun: nechta bo'sh joy (ok/afzal) + nechta almashuv (swap_ok/siqish)
		const out = {};
		for (const k of this.data.kunlar || []) out[k] = { bosh: 0, swap: 0 };
		for (const [key, st] of Object.entries((this.moving && this.moving.xarita) || {})) {
			const kun = key.split("|")[0];
			if (!out[kun]) continue;
			if (st.holat === "ok" || st.holat === "afzal") out[kun].bosh++;
			else if (st.holat === "swap_ok" || st.holat === "siqish") out[kun].swap++;
		}
		return out;
	}

	render_mvbar() {
		const w = this.body.find(".mvbar-wrap");
		if (!this.moving) { w.empty(); return; }
		const m = this.moving;
		const blok = m.blok_hajmi > 1 ? ` · blok ×${m.blok_hajmi}` : "";
		const joy = m.lagandadan ? "lagandadan" : `${this.esc(m.kun)} ${m.dars_raqami}-dars`;
		const hisob = this.mv_kun_hisob();
		const kunlar = (this.data.kunlar || []).map((k) => {
			const h = hisob[k] || { bosh: 0, swap: 0 };
			const on = this.kun === k;
			return `<button class="mv-day ${on ? "on" : ""} ${h.bosh ? "has" : ""}" data-mvkun="${k}"
				title="${h.bosh} bo'sh joy, ${h.swap} almashuv">${k.slice(0, 2)}<span>${h.bosh}</span></button>`;
		}).join("");
		w.html(`<div class="mvbar">
			<span class="mv-ico">✋</span>
			<b>${this.esc(m.fan)}</b>&nbsp;— ${this.esc(m.guruh_nomi)}
			<span class="mv-sub">(${joy}${blok})</span>
			<span class="mv-days">${kunlar}</span>
			<span class="spacer"></span>
			${m.lagandadan ? "" : `
				<button class="refresh mini" data-act="mv-lock" title="Qulflash">🔒</button>
				<button class="refresh mini" data-act="mv-tray" title="Lagandaga olish (Del)">⤓ Laganda</button>`}
			<button class="refresh mini" data-act="mv-form" title="Hujjatni ochish">📄</button>
			<button class="refresh mini" data-act="mv-cancel">Bekor (Esc)</button>
		</div>
		<div class="mv-legend mv-sub">Katakka bosing yoki sudrab tashlang:
			<span class="lg-ok">yashil</span>=bo'sh joy · <span class="lg-sw">↔ sariq</span>=almashuv
			· <span class="lg-sq">⤓ binafsha</span>=siqib chiqarish · qizil=band (sababi ustida)</div>`);
		w.find(`[data-act="mv-cancel"]`).on("click", () => this.cancel_move());
		w.find(`[data-act="mv-lock"]`).on("click", () => {
			const y = m.yozuv;
			this.cancel_move(true);
			frappe.call({ method: `${MH_M}.qulf_toggle`, args: { yozuv: y }, callback: () => this.load() });
		});
		w.find(`[data-act="mv-tray"]`).on("click", () => this.mv_lagandaga());
		w.find(`[data-act="mv-form"]`).on("click", () => frappe.set_route("Form", "Jadval Yozuvi", m.yozuv));
		w.find("[data-mvkun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("mvkun");
			this.render();
		});
	}

	cancel_move(silent) {
		if (!this.moving) return;
		this.moving = null;
		if (!silent) this.render();
	}

	// ------------- laganda (joylanmagan kartalar) -------------
	render_laganda() {
		const w = this.body.find(".laganda-wrap");
		const list = this.data.laganda || [];
		if (!list.length && !this.moving) { w.empty(); return; }
		const cards = list.map((x) => {
			const h = this.rang(x.fan);
			const on = this.moving && this.moving.yozuv === x.name;
			return `<div class="lesson lg-card ${on ? "picked" : ""}" style="--h:${h}" data-name="${this.esc(x.name)}"
				title="${this.esc(x.guruh_nomi || "")}${x.oqituvchi ? " · " + this.esc(x.oqituvchi) : ""}">
				<div class="fan">${this.esc(x.fan)}${x.blok ? ` <span class="bk">blok</span>` : ""}</div>
				<div class="oqit">${this.esc(x.guruh_nomi || x.guruh || "")}</div>
			</div>`;
		}).join("");
		w.html(`<div class="laganda ${this.moving && !this.moving.lagandadan ? "drop-on" : ""}">
			<span class="lg-t">🧺 Laganda <b>${list.length}</b></span>
			<div class="lg-cards">${cards || `<span class="mv-sub">bo'sh — kartani shu yerga sudrab olib qo'ying</span>`}</div>
		</div>`);
		w.find(".lg-card").on("click", (e) => {
			e.stopPropagation();
			if (this._dragDone) { this._dragDone = false; return; }
			const name = $(e.currentTarget).data("name");
			if (this.moving && this.moving.yozuv === name) { this.cancel_move(); return; }
			if (this.canEdit) this.start_move(name);
		});
		if (this.canEdit) this.enable_drag(w.find(".lg-card"));
	}

	render_grid() {
		const d = this.data;
		const sinflar = this.sinflar();
		const rows = (d.darslar || []).map((no) => {
			const kataklar = sinflar.map((s) => {
				const list = (d.katak || {})[`${s}|${this.kun}|${no}`] || [];
				// Muharrir overlay: karta qo'lda bo'lsa slot holati bo'yaladi
				let mvCls = "", mvTitle = "";
				if (this.moving) {
					if ((this.moving.sinflar || []).includes(s)) {
						const st = (this.moving.xarita || {})[`${this.kun}|${no}`] || {};
						if (st.holat === "oz") mvCls = "mv-oz";
						else if (st.holat === "ok") mvCls = "mv-ok";
						else if (st.holat === "afzal") mvCls = "mv-afzal";
						else if (st.holat === "swap_ok") { mvCls = "mv-swap"; mvTitle = "↔ Almashuv: " + (st.bilan || []).join("; "); }
						else if (st.holat === "swap_warn") { mvCls = "mv-swap-warn"; mvTitle = "↔ Almashuv mumkin, lekin: " + (st.sabab || []).join("; "); }
						else if (st.holat === "siqish") { mvCls = "mv-siqish"; mvTitle = "⤓ Siqib chiqarish: " + (st.bilan || []).join("; ") + " lagandaga tushadi"; }
						else { mvCls = "mv-band"; mvTitle = (st.sabab || []).join("\n"); }
					} else mvCls = "mv-dim";
				}
				const attrs = `data-sinf="${this.esc(s)}" data-no="${no}" class="${list.length ? (list.length > 1 ? "multi" : "") : "bosh"} ${mvCls}" ${mvTitle ? `title="${this.esc(mvTitle)}"` : ""}`;
				if (!list.length) return `<td ${attrs}></td>`;
				const inner = list.map((x) => {
					const h = this.rang(x.fan);
					const blok = x.blok ? ` <span class="bk">${this.esc(x.guruh_nomi || "").split(" ")[1] || ""}</span>` : "";
					const lk = x.qulf ? `<span class="lk" title="Qulflangan">🔒</span>` : "";
					const picked = this.moving && this.moving.yozuv === x.name ? " picked" : "";
					return `<div class="lesson${picked}" style="--h:${h}" data-name="${this.esc(x.name)}" title="${this.esc(x.guruh_nomi || "")}">
						<div class="fan">${this.esc(x.fan)}${blok}${lk}</div>
						<div class="oqit">${this.esc(x.oqituvchi || "—")}</div>
					</div>`;
				}).join("");
				return `<td ${attrs}>${inner}</td>`;
			}).join("");
			const v = sinflar.length ? this.vaqt(sinflar[0], no) : "";
			return `<tr><th class="dars-no"><b>${no}</b><span>${this.esc(v)}</span></th>${kataklar}</tr>`;
		}).join("");

		this.body.find(".jadval-wrap").html(`
			<div class="scroll-x">
			<table class="grid ${this.moving ? "mv-mode" : ""}">
				<thead><tr><th class="dars-no">№</th>${sinflar.map((s) => `<th>${this.esc(s.replace(/\s*\((full|hybrid)\)/, ""))}<span>${this.esc(/hybrid/.test(s) ? "hybrid" : "full")}</span></th>`).join("")}</tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
		`);

		if (this.moving) {
			this.body.find("td[data-no]").on("click", (e) => {
				const no = Number($(e.currentTarget).data("no"));
				this.drop_to(this.kun, no, $(e.currentTarget));
			});
		}
		// Bitta bosish = kartani ko'tarish (muharrir); o'qiydiganlarga — hujjat
		this.body.find(".lesson").on("click", (e) => {
			e.stopPropagation();
			if (this._dragDone) { this._dragDone = false; return; } // drag'dan keyingi click emas
			const name = $(e.currentTarget).data("name");
			if (!this.canEdit) { frappe.set_route("Form", "Jadval Yozuvi", name); return; }
			if (this.moving) {
				if (this.moving.yozuv === name) { this.cancel_move(); return; }
				// Karta qo'lda — boshqa karta ustiga bosish = o'sha katakka tashlash
				const td = $(e.currentTarget).closest("td[data-no]");
				if (td.length) this.drop_to(this.kun, Number(td.data("no")), td);
				return;
			}
			this.start_move(name);
		});
		if (this.canEdit) {
			this.body.find(".lesson").on("contextmenu", (e) => {
				e.preventDefault(); e.stopPropagation();
				// aSc uslubi: karta qo'ldaligida o'ng tugma = lagandaga tashlash
				if (this.moving) { this.mv_lagandaga(); return; }
				this.ctx_menu($(e.currentTarget).data("name"), e.clientX, e.clientY);
			});
			this.enable_drag(this.body.find(".lesson"));
			if (!this.moving) {
				this.body.find("td.bosh").on("click", (e) => {
					const td = $(e.currentTarget);
					this.katak_dialog(td.data("sinf"), Number(td.data("no")));
				});
			}
		}
	}

	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".chip[data-kun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("kun");
			this.render();
		});
		this.body.find(".fsinf").on("change", (e) => { this.fSinf = e.target.value; this.render_grid(); });
		this.body.find(".fversiya").on("change", (e) => {
			this.versiya = e.target.value;
			this.undoStack = []; this.redoStack = []; this.moving = null;
			this.load();
		});
		this.body.find(`[data-act="yuklama"]`).on("click", () => this.yuklama_dialog());
		this.body.find(`[data-act="import"]`).on("click", () => this.import_dialog());
		this.body.find(`[data-act="undo"]`).on("click", () => this.undo_op());
		this.body.find(`[data-act="redo"]`).on("click", () => this.redo_op());
	}

	// ---------------- muharrir: ko'tarish / tashlash ----------------
	lesson_info(name) {
		for (const key in this.data.katak || {}) {
			for (const x of this.data.katak[key]) {
				if (x.name === name) return x;
			}
		}
		for (const x of this.data.laganda || []) if (x.name === name) return x;
		return null;
	}

	start_move(name, cb) {
		frappe.call({
			method: `${MH_M}.kochirish_xarita`,
			args: { yozuv: name },
			callback: (r) => {
				const m = r.message;
				if (!m) return;
				if (m.qulf) {
					frappe.show_alert({ message: "🔒 Dars qulflangan — o'ng tugma bilan qulfni oching.", indicator: "orange" });
					return;
				}
				this.moving = m;
				this.render();
				if (cb) cb();
			},
		});
	}

	// Katakka tashlash/bosish — holatga qarab: ko'chirish / almashuv / siqish
	drop_to(kun, no, td) {
		if (!this.moving || this.busy) return;
		const st = (this.moving.xarita || {})[`${kun}|${no}`] || {};
		if (td && td.hasClass("mv-dim")) return;
		if (st.holat === "oz") { this.cancel_move(); return; }
		if (st.holat === "ok" || st.holat === "afzal") return this.do_move(kun, no);
		if (st.holat === "swap_ok") return this.do_swap(kun, no);           // toza — so'roqsiz
		if (st.holat === "siqish") return this.do_siqish(kun, no);          // lagandaga — undo bor
		if (st.holat === "swap_warn") return this.swap_warn_dialog(kun, no, st);
		if (st.sabab && st.sabab.length)
			frappe.show_alert({ message: "⛔ " + this.esc(st.sabab[0]), indicator: "red" });
	}

	swap_warn_dialog(kun, no, st) {
		const bilan = (st.bilan || []).map((b) => this.esc(b)).join("; ");
		const d = new frappe.ui.Dialog({
			title: "Band katak — nima qilamiz?",
			size: "small",
			fields: [{
				fieldtype: "HTML",
				options: `<div class="tz-jadval tz-menu">
					<div class="mi"><b>${this.esc(this.moving.fan)} — ${this.esc(this.moving.guruh_nomi)}</b> → ${this.esc(kun)} ${no}-dars</div>
					<div class="mi">U yerda: <b>${bilan}</b></div>
					<div class="swap-warn-box">⚠ ${(st.sabab || []).map((s) => this.esc(s)).join("<br>⚠ ")}</div>
					<div class="menu-btns">
						<button class="refresh primary" data-w="swap">↔ Baribir almashtirish</button>
						<button class="refresh" data-w="siqish">⤓ Qarshi darsni lagandaga chiqarish</button>
						<button class="refresh" data-w="cancel">Bekor</button>
					</div>
				</div>`,
			}],
		});
		d.show();
		d.$body.find(`[data-w="swap"]`).on("click", () => { d.hide(); this.do_swap(kun, no); });
		d.$body.find(`[data-w="siqish"]`).on("click", () => { d.hide(); this.do_siqish(kun, no); });
		d.$body.find(`[data-w="cancel"]`).on("click", () => d.hide());
	}

	// Amal + undo yozuvi. op: {t, yozuv, from:{kun,no,tray}, to:{kun,no}, siqildi?}
	op_call(method, args, op, xabar) {
		this.busy = true;
		frappe.call({
			method, args, freeze: true,
			callback: () => {
				this.busy = false;
				if (op) { this.undoStack.push(op); this.redoStack = []; }
				this.moving = null;
				this.load(() => {
					if (xabar) frappe.show_alert({ message: xabar + " <span class='mv-sub'>(Ctrl+Z qaytaradi)</span>", indicator: "green" });
				});
			},
			error: () => {
				this.busy = false;
				// Hard konflikt — xarita eskirgan bo'lishi mumkin, qayta yuklaymiz
				const y = this.moving && this.moving.yozuv;
				this.load(() => { if (y) this.start_move(y); });
			},
		});
	}

	do_move(kun, no) {
		const m = this.moving;
		this.op_call(`${MH_M}.dars_kochir`, { yozuv: m.yozuv, kun, dars_raqami: no },
			{ t: "move", yozuv: m.yozuv, from: { kun: m.kun, no: m.dars_raqami, tray: m.lagandadan }, to: { kun, no } },
			`✓ ${this.esc(m.fan)} → ${this.esc(kun)} ${no}-dars`);
	}

	do_swap(kun, no) {
		const m = this.moving;
		this.op_call(`${MH_M}.dars_almashtir`, { yozuv: m.yozuv, kun, dars_raqami: no },
			{ t: "swap", yozuv: m.yozuv, from: { kun: m.kun, no: m.dars_raqami }, to: { kun, no } },
			`↔ Almashtirildi: ${this.esc(m.fan)} ↔ ${this.esc(kun)} ${no}-dars`);
	}

	do_siqish(kun, no) {
		const m = this.moving;
		this.busy = true;
		frappe.call({
			method: `${MH_M}.dars_siqib_joyla`,
			args: { yozuv: m.yozuv, kun, dars_raqami: no },
			freeze: true,
			callback: (r) => {
				this.busy = false;
				const res = r.message || {};
				this.undoStack.push({
					t: "displace", yozuv: m.yozuv,
					from: { kun: m.kun, no: m.dars_raqami, tray: m.lagandadan },
					to: { kun, no },
					siqildi: (res.siqildi || []).map((s) => s.yozuv),
				});
				this.redoStack = [];
				this.moving = null;
				const siq = res.siqildi || [];
				const nomlar = siq.map((s) => this.esc(s.fan)).join(", ");
				this.load(() => {
					// aSc zanjiri: siqilgan karta QO'LGA o'tadi — darhol yangi joy tanlanadi.
					// Esc bosilsa lagandada qolaveradi (hech narsa yo'qolmaydi).
					if (siq.length) {
						this.start_move(siq[0].yozuv, () => frappe.show_alert({
							message: `⤓ ${nomlar} qo'lingizda — joy tanlang (Esc = lagandada qoladi)`,
							indicator: "orange",
						}));
					} else {
						frappe.show_alert({ message: `⤓ Joylandi <span class='mv-sub'>(Ctrl+Z qaytaradi)</span>`, indicator: "green" });
					}
				});
			},
			error: () => {
				this.busy = false;
				const y = this.moving && this.moving.yozuv;
				this.load(() => { if (y) this.start_move(y); });
			},
		});
	}

	mv_lagandaga() {
		const m = this.moving;
		if (!m || m.lagandadan) return;
		this.op_call(`${MH_M}.lagandaga`, { yozuv: m.yozuv },
			{ t: "unplace", yozuv: m.yozuv, from: { kun: m.kun, no: m.dars_raqami } },
			`🧺 ${this.esc(m.fan)} lagandaga olindi`);
	}

	// ---------------- undo / redo ----------------
	_seq(calls, done) {
		// calls: [{method, args}] — ketma-ket bajariladi (tartib muhim)
		const next = (i) => {
			if (i >= calls.length) { done && done(); return; }
			frappe.call({
				method: calls[i].method, args: calls[i].args, freeze: true,
				callback: () => next(i + 1),
				error: () => { this.load(); },
			});
		};
		next(0);
	}

	undo_op() {
		if (this.busy || !this.undoStack.length) return;
		const op = this.undoStack.pop();
		this.moving = null;
		const fin = () => { this.redoStack.push(op); this.load(); };
		if (op.t === "move") {
			this._seq([op.from.tray
				? { method: `${MH_M}.lagandaga`, args: { yozuv: op.yozuv } }
				: { method: `${MH_M}.dars_kochir`, args: { yozuv: op.yozuv, kun: op.from.kun, dars_raqami: op.from.no } }], fin);
		} else if (op.t === "swap") {
			this._seq([{ method: `${MH_M}.dars_almashtir`, args: { yozuv: op.yozuv, kun: op.from.kun, dars_raqami: op.from.no } }], fin);
		} else if (op.t === "unplace") {
			this._seq([{ method: `${MH_M}.dars_kochir`, args: { yozuv: op.yozuv, kun: op.from.kun, dars_raqami: op.from.no } }], fin);
		} else if (op.t === "displace") {
			// 1) bizning kartani joyidan olamiz, 2) siqilganlarni qaytaramiz
			const calls = [op.from.tray
				? { method: `${MH_M}.lagandaga`, args: { yozuv: op.yozuv } }
				: { method: `${MH_M}.dars_kochir`, args: { yozuv: op.yozuv, kun: op.from.kun, dars_raqami: op.from.no } }];
			for (const nm of op.siqildi || []) {
				calls.push({ method: `${MH_M}.dars_kochir`, args: { yozuv: nm, kun: op.to.kun, dars_raqami: op.to.no } });
			}
			this._seq(calls, fin);
		}
	}

	redo_op() {
		if (this.busy || !this.redoStack.length) return;
		const op = this.redoStack.pop();
		this.moving = null;
		const fin = () => { this.undoStack.push(op); this.load(); };
		const M = {
			move: `${MH_M}.dars_kochir`, swap: `${MH_M}.dars_almashtir`,
			displace: `${MH_M}.dars_siqib_joyla`,
		};
		if (op.t === "unplace") {
			this._seq([{ method: `${MH_M}.lagandaga`, args: { yozuv: op.yozuv } }], fin);
		} else {
			this._seq([{ method: M[op.t], args: { yozuv: op.yozuv, kun: op.to.kun, dars_raqami: op.to.no } }], fin);
		}
	}

	// ---------------- sudrab tashlash (drag & drop) ----------------
	enable_drag(els) {
		els.on("pointerdown", (e) => {
			if (e.button !== 0 || this.busy) return;
			if (e.pointerType === "touch") return; // telefonda bosish-bosish rejimi
			const el = $(e.currentTarget);
			const name = el.data("name");
			const sx = e.clientX, sy = e.clientY;
			let dragging = false, ghost = null;
			// Xaritani darhol so'raymiz (sudrashni kutmay) — bo'yash tez chiqadi
			const fetchMap = !this.moving || this.moving.yozuv !== name;

			const mm = (ev) => {
				if (!dragging && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 7) return;
				if (!dragging) {
					dragging = true;
					if (fetchMap) this.start_move(name);
					ghost = el.clone().addClass("mv-ghost").css({ width: el.outerWidth() })
						.appendTo(document.body);
					document.body.classList.add("tz-dragging");
				}
				ghost.css({ left: ev.clientX + 10, top: ev.clientY + 8 });
				// Hover katakni belgilash
				ghost.hide();
				const under = document.elementFromPoint(ev.clientX, ev.clientY);
				ghost.show();
				this.body.find("td.mv-hover").removeClass("mv-hover");
				const td = under && under.closest ? under.closest("td[data-no]") : null;
				if (td) td.classList.add("mv-hover");
			};
			const up = (ev) => {
				$(document).off("pointermove.tzdrag pointerup.tzdrag");
				document.body.classList.remove("tz-dragging");
				if (ghost) ghost.remove();
				this.body.find("td.mv-hover").removeClass("mv-hover");
				if (!dragging) return; // oddiy click — click handler ishlaydi
				this._dragDone = true; // drag'dan keyingi click'ni yutamiz
				setTimeout(() => { this._dragDone = false; }, 150);
				const under = document.elementFromPoint(ev.clientX, ev.clientY);
				const td = under && under.closest ? under.closest("td[data-no]") : null;
				const tray = under && under.closest ? under.closest(".laganda") : null;
				if (td && this.moving && this.moving.yozuv === name) {
					this.drop_to(this.kun, Number(td.dataset.no), $(td));
				} else if (tray && this.moving && !this.moving.lagandadan) {
					this.mv_lagandaga();
				} else {
					this.cancel_move();
				}
			};
			$(document).on("pointermove.tzdrag", mm).on("pointerup.tzdrag", up);
		});
	}

	// ---------------- o'ng tugma menyusi ----------------
	close_ctx() { $(".tz-ctx").remove(); $(document).off("click.tzctx"); }

	ctx_menu(name, x, y) {
		this.close_ctx();
		const info = this.lesson_info(name) || {};
		const lagandada = (this.data.laganda || []).some((l) => l.name === name);
		const menu = $(`<div class="tz-jadval tz-ctx" style="left:${x}px;top:${y}px">
			<div class="ctx-t">${this.esc(info.fan || "")} — ${this.esc(info.guruh_nomi || info.guruh || "")}</div>
			<button data-c="move">✋ Ko'chirish</button>
			<button data-c="lock">${info.qulf ? "🔓 Qulfni ochish" : "🔒 Qulflash"}</button>
			${lagandada ? "" : `<button data-c="tray">🧺 Lagandaga olish</button>`}
			<button data-c="form">📄 Hujjat</button>
			<button data-c="del" class="danger">🗑 Butunlay o'chirish</button>
		</div>`).appendTo(document.body);
		// Ekrandan chiqib ketmasin
		const r = menu[0].getBoundingClientRect();
		if (r.right > window.innerWidth) menu.css("left", x - r.width);
		if (r.bottom > window.innerHeight) menu.css("top", y - r.height);
		setTimeout(() => $(document).on("click.tzctx", () => this.close_ctx()), 0);
		menu.find("[data-c]").on("click", (e) => {
			const c = $(e.currentTarget).data("c");
			this.close_ctx();
			if (c === "move") this.start_move(name);
			else if (c === "lock") frappe.call({ method: `${MH_M}.qulf_toggle`, args: { yozuv: name }, callback: () => this.load() });
			else if (c === "tray") this.start_move(name, () => this.mv_lagandaga());
			else if (c === "form") frappe.set_route("Form", "Jadval Yozuvi", name);
			else if (c === "del") {
				frappe.confirm(`«${this.esc(info.fan || "")} — ${this.esc(info.guruh_nomi || info.guruh || "")}» BUTUNLAY o'chirilsinmi? (qaytarib bo'lmaydi; vaqtincha olish uchun Laganda bor)`, () => {
					frappe.call({ method: `${OJ_M}.dars_ochir`, args: { name }, callback: () => this.load() });
				});
			}
		});
	}

	// -------- bo'sh katak: "bu yerga nima sig'adi?" (aSc teskari qidiruv) --------
	katak_dialog(sinf, no) {
		frappe.call({
			method: `${MH_M}.katak_kandidatlar`,
			args: { sinf, kun: this.kun, dars_raqami: no, versiya: this.versiya },
			freeze: true,
			callback: (r) => {
				const d = r.message || {};
				const koch = (d.kochirish || []);
				const mumkin = koch.filter((k) => k.mumkin);
				const yoq = koch.filter((k) => !k.mumkin);
				const dlg = new frappe.ui.Dialog({
					title: `${sinf.replace(/\s*\((full|hybrid)\)/, "")} · ${this.kun} ${no}-dars — nima sig'adi?`,
					size: "large",
					fields: [{ fieldtype: "HTML", fieldname: "body" }],
				});
				const joy = (k) => k.kun ? `${this.esc(k.kun)} ${k.dars_raqami}-dars` : "🧺 laganda";
				const rows_m = mumkin.map((k) => `
					<tr><td><b>${this.esc(k.fan)}</b> — ${this.esc(k.guruh_nomi)}${k.blok_hajmi > 1 ? ` <span class="mv-sub">(blok ×${k.blok_hajmi})</span>` : ""}</td>
					<td class="mv-sub">${joy(k)}</td>
					<td class="r"><button class="refresh mini" data-koch="${this.esc(k.yozuv)}">→ bu yerga</button></td></tr>`).join("");
				const rows_y = yoq.slice(0, 12).map((k) => `
					<tr class="dim"><td>${this.esc(k.fan)} — ${this.esc(k.guruh_nomi)}</td>
					<td class="mv-sub">${joy(k)}</td>
					<td class="mv-sub">${this.esc((k.sabab || []).join("; "))}</td></tr>`).join("");
				const rows_o = (d.bosh_oqituvchilar || []).slice(0, 25).map((o) => `
					<tr><td>${this.esc(o.nomi)}</td>
					<td class="r">${o.soat}${o.norma ? `/${o.norma}` : ""}</td>
					<td class="mv-sub">${this.esc((o.fanlar || []).join(", "))}</td>
					<td class="r"><button class="refresh mini" data-add="${this.esc(o.oqituvchi)}" data-nomi="${this.esc(o.nomi)}">+ dars</button></td></tr>`).join("");
				dlg.fields_dict.body.$wrapper.html(`<div class="tz-jadval">
					<div class="sec-t">Shu sinf darslaridan ko'chirish (${mumkin.length} ta mumkin)</div>
					<table class="tbl mini-tbl"><tbody>${rows_m || `<tr><td class="mv-sub">Ko'chirsa bo'ladigan dars yo'q</td></tr>`}</tbody></table>
					${rows_y ? `<details class="mt"><summary class="mv-sub">Sig'maydiganlar (${yoq.length}) — nega?</summary>
						<table class="tbl mini-tbl"><tbody>${rows_y}</tbody></table></details>` : ""}
					<div class="sec-t mt">Shu slotda bo'sh o'qituvchilar (${(d.bosh_oqituvchilar || []).length})</div>
					<table class="tbl mini-tbl"><thead><tr><th>O'qituvchi</th><th class="r">Soat</th><th>Fanlari</th><th></th></tr></thead>
					<tbody>${rows_o}</tbody></table>
				</div>`);
				dlg.show();
				dlg.$body.find("[data-koch]").on("click", (e) => {
					dlg.hide();
					const yozuv = $(e.currentTarget).data("koch");
					// Ko'chirish amali undo'ga tushishi uchun start_move → drop oqimi
					this.start_move(yozuv, () => this.drop_to(this.kun, no));
				});
				dlg.$body.find("[data-add]").on("click", (e) => {
					const oqit = $(e.currentTarget).data("add");
					const nomi = $(e.currentTarget).data("nomi");
					dlg.hide();
					this.dars_qosh_dialog(sinf, no, oqit, nomi);
				});
			},
		});
	}

	dars_qosh_dialog(sinf, no, oqituvchi, nomi) {
		const d = new frappe.ui.Dialog({
			title: `Dars qo'shish: ${this.kun} ${no}-dars · ${sinf}`,
			fields: [
				{ fieldname: "fan", fieldtype: "Link", options: "Course", label: "Fan", reqd: 1 },
				{ fieldname: "info", fieldtype: "HTML", options: `<div class="text-muted" style="font-size:12px">O'qituvchi: <b>${this.esc(nomi)}</b> · Guruh: ${this.esc(sinf)}</div>` },
			],
			primary_action_label: "Qo'shish",
			primary_action: (v) => {
				frappe.call({
					method: `${OJ_M}.dars_qosh`,
					args: { oqituvchi, kun: this.kun, dars_raqami: no, fan: v.fan, guruh: sinf, versiya: this.versiya },
					freeze: true,
					callback: () => { d.hide(); this.load(); },
				});
			},
		});
		d.show();
	}

	yuklama_dialog() {
		const rows = (this.data.yuklama || []).map((y) =>
			`<tr><td>${this.esc(y.oqituvchi)}</td><td class="r ${y.soat >= 35 ? "ogoh" : ""}">${y.soat}</td></tr>`).join("");
		new frappe.ui.Dialog({
			title: "O'qituvchilar haftalik yuklamasi",
			size: "small",
			fields: [{
				fieldtype: "HTML",
				options: `<div class="tz-jadval"><table class="tbl mini-tbl"><thead><tr><th>O'qituvchi</th><th class="r">Soat</th></tr></thead><tbody>${rows}</tbody></table></div>`,
			}],
		}).show();
	}

	// ---------------- Exceldan import ----------------
	import_dialog() {
		const dlg = new frappe.ui.Dialog({
			title: "Dars jadvalini Exceldan import qilish",
			fields: [
				{
					fieldtype: "HTML",
					options: `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">
						Maktabning "Umumiy dars jadvali" faylini yuklang (.xlsx).<br>
						Avval <b>sinov rejimi</b>da tekshiring — hech narsa yozilmaydi, faqat hisobot chiqadi.</div>`,
				},
				{ fieldname: "fayl", fieldtype: "Attach", label: "Excel fayl (.xlsx)", reqd: 1 },
				{
					fieldname: "versiya_nomi", fieldtype: "Data", label: "Jadval versiyasi nomi",
					default: this.versiya || "2026-2027 asosiy", reqd: 1,
					description: "Mavjud versiya bo'lsa — unga qo'shiladi, yo'q bo'lsa yangisi yaratiladi (Qoralama)",
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "dry_run", fieldtype: "Check", label: "Sinov rejimi (bazaga yozilmaydi)",
					default: 1,
				},
				{
					fieldname: "tozalash_avval", fieldtype: "Check",
					label: "Avval shu versiyaning eski yozuvlarini o'chirish",
					depends_on: "eval:!doc.dry_run",
					description: "Jadval qaytadan yuklanayotgan bo'lsa belgilang",
				},
			],
			primary_action_label: "Importni boshlash",
			primary_action: (v) => {
				frappe.call({
					method: `${IMP_M}.ui_import`,
					args: {
						file_url: v.fayl,
						versiya_nomi: v.versiya_nomi,
						dry_run: v.dry_run ? 1 : 0,
						tozalash_avval: v.tozalash_avval ? 1 : 0,
					},
					freeze: true,
					freeze_message: "Import navbatga qo'yilmoqda…",
					callback: () => {
						dlg.set_primary_action(null);
						dlg.set_message && dlg.set_message("");
						dlg.$body.html(`<div style="padding:24px;text-align:center">
							<div class="lds-dual-ring"></div>
							<p style="margin-top:10px"><b>Import ketmoqda…</b></p>
							<p style="font-size:12px;color:var(--text-muted)">
								Taxminan 1–2 daqiqa. Shu oyna o'zi yopilib, natija ko'rsatiladi.<br>
								Oynani yopsangiz ham import davom etadi.</p></div>`);
					},
				});
			},
		});
		this.import_dlg = dlg;
		dlg.show();
	}

	show_import_result(r) {
		if (!r) return;
		if (r.holat === "xato") {
			frappe.msgprint({ title: "Import xatosi", indicator: "red", message: this.esc(r.xabar) });
			return;
		}
		const o = r.oqituvchilar || {};
		const y = r.yozuvlar || {};
		const list = (arr) => (arr && arr.length ? arr.map((x) => this.esc(x)).join(", ") : "—");
		frappe.msgprint({
			title: r.dry_run ? "Sinov natijasi (bazaga yozilmadi)" : "Import tugadi",
			indicator: y.xato_soni ? "orange" : "green",
			message: `
				<table class="table table-bordered" style="font-size:13px">
					<tr><td>Excel yacheykalari</td><td><b>${r.yacheykalar || 0}</b></td></tr>
					<tr><td>Jadval yozuvlari</td><td><b>${y.yaratildi || 0}</b> yangi · ${y.bor_edi || 0} bor edi
						${y.xato_soni ? `· <span style="color:var(--red-600)">${y.xato_soni} xato</span>` : ""}</td></tr>
					<tr><td>Yangi fanlar</td><td>${r.fanlar_yangi || 0}</td></tr>
					<tr><td>O'qituvchilar</td><td>${o.jami || 0} ta — ${o.employee_bilan || 0} tasi xodim bazasiga bog'landi</td></tr>
					<tr><td>Bloklar / daraja guruhlari</td><td>${r.bloklar || 0} / ${r.daraja_guruhlari || 0}</td></tr>
					<tr><td>Xodim topilmaganlar</td><td style="font-size:12px">${list(o.employee_siz)}</td></tr>
					<tr><td>Vakant (o'qituvchisiz)</td><td style="font-size:12px">${list(o.vakant)}</td></tr>
				</table>
				${y.xato_namuna && y.xato_namuna.length
					? `<div style="margin-top:8px;font-size:12px"><b>Xatolar:</b><br>${y.xato_namuna.map((x) => this.esc(x)).join("<br>")}</div>`
					: ""}
				${r.dry_run ? `<div style="margin-top:10px;padding:8px;background:var(--bg-yellow);border-radius:6px;font-size:12px">
					Bu sinov edi — bazaga hech narsa yozilmadi. Haqiqiy import uchun "Sinov rejimi" belgisini olib tashlang.</div>` : ""}
			`,
		});
	}
}
