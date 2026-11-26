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
		this.fSinflar = [];      // tanlangan guruhlar (bo'sh = barchasi)
		this.view = "kunlik";    // "kunlik" | "haftalik"
		this.pickerOpen = false; // guruh tanlash paneli ochiqmi
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
		if (!this.fSinflar.length) return all;
		return all.filter((s) => this.fSinflar.includes(s));
	}

	sinf_nomi(s) {
		return (this.data.sinf_nomlari || {})[s] || s;
	}

	group_picker_html() {
		const n = this.fSinflar.length;
		const label = n === 0 ? "Barcha guruhlar"
			: (n === 1 ? this.sinf_nomi(this.fSinflar[0]) : `${n} ta guruh`);
		const items = (this.data.sinflar || []).map((s) => {
			const on = this.fSinflar.includes(s);
			return `<label class="gp-item ${on ? "on" : ""}"><input type="checkbox" data-gp="${this.esc(s)}" ${on ? "checked" : ""}> ${this.esc(this.sinf_nomi(s))}</label>`;
		}).join("");
		return `<div class="grp-picker ${this.pickerOpen ? "open" : ""}">
			<button class="refresh gp-btn" data-act="gp-toggle">🏫 ${this.esc(label)} ▾</button>
			<div class="gp-panel">
				<div class="gp-head">
					<button class="gp-mini" data-act="gp-all">Barchasi</button>
					<button class="gp-mini" data-act="gp-none">Tozalash</button>
				</div>
				<div class="gp-list">${items}</div>
			</div>
		</div>`;
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
				${this.holat_badge()}
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="controls mb">
				<div class="chips view-toggle">
					<button class="chip ${this.view === "kunlik" ? "on" : ""}" data-view="kunlik">📅 Kunlik</button>
					<button class="chip ${this.view === "haftalik" ? "on" : ""}" data-view="haftalik">🗓 Haftalik</button>
				</div>
				${this.view === "kunlik" ? `<div class="chips kunlar">
					${(d.kunlar || []).map((k) => `<button class="chip ${this.kun === k ? "on" : ""}" data-kun="${k}">${k}</button>`).join("")}
				</div>` : ""}
				${this.group_picker_html()}
				<div class="spacer"></div>
				${this.canEdit ? `
					<button class="refresh" data-act="undo" ${this.undoStack.length ? "" : "disabled"} title="Ctrl+Z">↶${this.undoStack.length ? ` ${this.undoStack.length}` : ""}</button>
					<button class="refresh" data-act="redo" ${this.redoStack.length ? "" : "disabled"} title="Ctrl+Y">↷</button>
					${this.publish_btn()}` : ""}
				<button class="refresh" data-act="pdf">🖨 PDF / Chop etish</button>
				<button class="refresh" data-act="yuklama">O'qituvchi yuklamasi</button>
				<button class="refresh primary" data-act="import">⬆ Exceldan import</button>
			</div>

			${this.canEdit ? this.versiya_banner() : ""}
			<div class="mvbar-wrap"></div>
			<div class="laganda-wrap"></div>
			<div class="jadval-wrap card"></div>
		`);
		this.render_mvbar();
		this.render_laganda();
		this.render_grid();
		this.bind();
	}

	// ------------- versiya holati / e'lon qilish (publish gate) -------------
	cur_versiya() {
		return (this.data.versiyalar || []).find((v) => v.name === this.data.versiya) || {};
	}

	holat_badge() {
		const h = (this.cur_versiya().holat || "");
		const map = {
			"Qoralama": ["qoralama", "📝 Qoralama"],
			"Faol": ["faol", "🟢 Faol (jonli)"],
			"Arxiv": ["arxiv", "🗄 Arxiv"],
		};
		const [cls, txt] = map[h] || ["", h];
		return `<span class="holat-badge ${cls}">${txt}</span>`;
	}

	publish_btn() {
		const h = this.cur_versiya().holat;
		if (h === "Qoralama")
			return `<button class="refresh primary" data-act="publish">💾 Saqlash va e'lon qilish</button>`;
		return `<button class="refresh" data-act="make-draft" title="Faol versiyaga tegmay, tahrir uchun nusxa">📝 Tahrir uchun qoralama</button>`;
	}

	versiya_banner() {
		const h = this.cur_versiya().holat;
		if (h === "Qoralama")
			return `<div class="versiya-banner draft">📝 <b>Qoralama rejimi</b> — o'zgarishlaringiz hali jonli emas.
				O'qituvchilar va Moodle ularni <b>«Saqlash va e'lon qilish»</b> bosilgunicha ko'rmaydi.</div>`;
		if (h === "Faol")
			return `<div class="versiya-banner live">🟢 <b>Jonli versiya</b> — har o'zgarish darhol jonli (lekin Moodle 07:20 gacha yangilanmaydi).
				Xavfsiz tahrir uchun <b>«Tahrir uchun qoralama»</b> yarating.</div>`;
		return "";
	}

	make_draft() {
		frappe.confirm(
			`<b>${this.esc(this.cur_versiya().nomi || this.versiya)}</b> dan tahrir uchun yangi <b>Qoralama</b> nusxa yaratilsinmi?<br>
			<span class="text-muted" style="font-size:12px">Jonli (Faol) jadvalga tegilmaydi. Qoralamada bemalol o'zgartirib, keyin «Saqlash va e'lon qilish» bilan jonli qilasiz.</span>`,
			() => {
				frappe.call({
					method: `${MH_M}.qoralama_yarat`,
					args: { versiya: this.versiya },
					freeze: true,
					freeze_message: "Qoralama yaratilmoqda…",
					callback: (r) => {
						const m = r.message || {};
						this.versiya = m.versiya;
						this.undoStack = []; this.redoStack = []; this.moving = null;
						this.load(() => frappe.show_alert({
							message: `📝 Qoralama yaratildi: <b>${this.esc(m.nomi)}</b> — endi bemalol tahrir qiling`,
							indicator: "blue",
						}));
					},
				});
			}
		);
	}

	publish_dialog() {
		frappe.call({
			method: `${MH_M}.versiya_holati`,
			args: { versiya: this.versiya },
			freeze: true,
			callback: (r) => {
				const v = r.message || {};
				const eskiFaol = (v.boshqa_faol || []).map((x) => this.esc(x.nomi)).join(", ");
				const d = new frappe.ui.Dialog({
					title: "Saqlash va e'lon qilish",
					fields: [
						{
							fieldtype: "HTML",
							options: `<div class="tz-jadval tz-menu">
								<div class="mi"><span class="mi-l">Versiya</span><b>${this.esc(v.nomi || this.versiya)}</b></div>
								<div class="mi"><span class="mi-l">Darslar</span><b>${v.dars_soni || 0}</b> ta${v.lagandada ? ` <span class="mv-sub">(+ lagandada ${v.lagandada} ta joylanmagan)</span>` : ""}</div>
								${eskiFaol ? `<div class="mi"><span class="mi-l">Arxivlanadi</span><b>${eskiFaol}</b> <span class="mv-sub">(hozirgi jonli versiya)</span></div>` : ""}
								<div class="mi"><span class="mi-l">Moodle</span>${v.moodle_yoqilgan ? "🟢 yoqilgan — avto yuboriladi" : "⚪ o'chirilgan — yuborilmaydi"}</div>
							</div>
							${v.lagandada ? `<div class="swap-warn-box">⚠ Lagandada ${v.lagandada} ta joylanmagan dars bor — ular jadvalga tushmaydi. Avval joylang yoki e'tiborsiz qoldiring.</div>` : ""}`,
						},
						{
							fieldname: "amal_sanasi", fieldtype: "Date", label: "Qaysi sanadan kuchga kirsin",
							default: frappe.datetime.get_today(), reqd: 1,
							description: "Odatda bugun. Moodle shu sanadan oldingi (o'tgan) kunlarni o'zgartirmaydi.",
						},
						{
							fieldname: "moodle", fieldtype: "Check", label: "Moodle'ga darhol yuborish",
							default: v.moodle_yoqilgan ? 1 : 0, read_only: v.moodle_yoqilgan ? 0 : 1,
						},
					],
					primary_action_label: "E'lon qilish",
					primary_action: (vals) => {
						d.hide();
						frappe.confirm(
							`<b>${this.esc(v.nomi || this.versiya)}</b> jonli (Faol) qilinsinmi?<br>
							<span class="text-muted" style="font-size:12px">${eskiFaol ? `«${eskiFaol}» arxivlanadi. ` : ""}${vals.moodle ? "Moodle'ga yuboriladi. " : ""}Buni keyin yana qoralama orqali o'zgartirsa bo'ladi.</span>`,
							() => {
								frappe.call({
									method: `${MH_M}.eln_qil`,
									args: { versiya: this.versiya, amal_sanasi: vals.amal_sanasi, moodle: vals.moodle ? 1 : 0 },
									freeze: true,
									freeze_message: "E'lon qilinmoqda…",
									callback: (rr) => {
										const res = rr.message || {};
										this.undoStack = []; this.redoStack = [];
										this.load(() => frappe.msgprint({
											title: "✓ E'lon qilindi",
											indicator: "green",
											message: `<b>${this.esc(v.nomi || this.versiya)}</b> endi jonli (Faol).<br>
												Kuchga kirish sanasi: <b>${this.esc(res.amal_sanasi || "")}</b><br>
												Moodle: ${this.esc(res.moodle || "—")}`,
										}));
									},
								});
							}
						);
					},
				});
				d.show();
			},
		});
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

	// Bitta katak <td> (kunlik va haftalik ko'rinish uchun umumiy). Overlay
	// kalit `${kun}|${no}` bo'yicha — har xil kundagi kataklar to'g'ri bo'yaladi.
	cell_td(s, kun, no) {
		const d = this.data;
		const list = (d.katak || {})[`${s}|${kun}|${no}`] || [];
		let mvCls = "", mvTitle = "";
		if (this.moving) {
			if ((this.moving.sinflar || []).includes(s)) {
				const st = (this.moving.xarita || {})[`${kun}|${no}`] || {};
				if (st.holat === "oz") mvCls = "mv-oz";
				else if (st.holat === "ok") mvCls = "mv-ok";
				else if (st.holat === "afzal") mvCls = "mv-afzal";
				else if (st.holat === "swap_ok") { mvCls = "mv-swap"; mvTitle = "↔ Almashuv: " + (st.bilan || []).join("; "); }
				else if (st.holat === "swap_warn") { mvCls = "mv-swap-warn"; mvTitle = "↔ Almashuv mumkin, lekin: " + (st.sabab || []).join("; "); }
				else if (st.holat === "siqish") { mvCls = "mv-siqish"; mvTitle = "⤓ Siqib chiqarish: " + (st.bilan || []).join("; ") + " lagandaga tushadi"; }
				else { mvCls = "mv-band"; mvTitle = (st.sabab || []).join("\n"); }
			} else mvCls = "mv-dim";
		}
		const attrs = `data-sinf="${this.esc(s)}" data-no="${no}" data-kun="${this.esc(kun)}" class="${list.length ? (list.length > 1 ? "multi" : "") : "bosh"} ${mvCls}" ${mvTitle ? `title="${this.esc(mvTitle)}"` : ""}`;
		if (!list.length) return `<td ${attrs}></td>`;
		const kechki = no > (d.regular_max || 10);
		const inner = list.map((x) => {
			const h = this.rang(x.fan);
			const blok = x.blok ? ` <span class="bk">${this.esc(x.guruh_nomi || "").split(" ")[1] || ""}</span>` : "";
			const lk = x.qulf ? `<span class="lk" title="Qulflangan">🔒</span>` : "";
			const picked = this.moving && this.moving.yozuv === x.name ? " picked" : "";
			// Kechki darsда: vaqt (zam direktor kiritgan) + biriktirilgan o'quvchi soni
			let extra = "";
			if (kechki) {
				const vaqt = (x.boshlanish || x.tugash) ? `${this.esc(x.boshlanish || "")}–${this.esc(x.tugash || "")}` : "";
				const az = (d.guruh_azolari || {})[x.guruh];
				extra = `<div class="k-meta">${vaqt ? `🕘 ${vaqt}` : `<span class="k-warn">🕘 vaqt yo'q</span>`}${az != null ? ` · 👥 ${az}` : ""}</div>`;
			}
			return `<div class="lesson${picked}${kechki ? " kechki-lesson" : ""}" style="--h:${h}" data-name="${this.esc(x.name)}" title="${this.esc(x.guruh_nomi || "")}">
				<div class="fan">${this.esc(x.fan)}${blok}${lk}</div>
				<div class="oqit">${this.esc(x.oqituvchi || "—")}</div>
				${extra}
			</div>`;
		}).join("");
		return `<td ${attrs}>${inner}</td>`;
	}

	sinf_header_th(s) {
		const disp = this.sinf_nomi(s);
		const label = disp.replace(/\s*\((full|hybrid)\)/, "");
		const sub = /hybrid/.test(disp) ? "hybrid" : (/full/.test(disp) ? "full" : "");
		const ed = this.canEdit && !this.moving;
		return `<th class="sinf-h${ed ? " editable" : ""}" ${ed ? `data-sinf-h="${this.esc(s)}" title="Nomini o'zgartirish"` : ""}>${this.esc(label)}${sub ? `<span>${sub}</span>` : ""}${ed ? `<span class="rn">✎</span>` : ""}</th>`;
	}

	render_grid() {
		if (this.view === "haftalik") return this.render_weekly();
		return this.render_daily();
	}

	// Kunlik: ustunlar = guruhlar, qatorlar = darslar, bitta kun
	render_daily() {
		const d = this.data;
		const sinflar = this.sinflar();
		const rows = (d.darslar || []).map((no) => {
			const kataklar = sinflar.map((s) => this.cell_td(s, this.kun, no)).join("");
			const v = sinflar.length ? this.vaqt(sinflar[0], no) : "";
			return `<tr><th class="dars-no"><b>${no}</b><span>${this.esc(v)}</span></th>${kataklar}</tr>`;
		}).join("");
		this.body.find(".jadval-wrap").html(`
			<div class="scroll-x">
			<table class="grid ${this.moving ? "mv-mode" : ""}">
				<thead><tr><th class="dars-no">№</th>${sinflar.map((s) => this.sinf_header_th(s)).join("")}</tr></thead>
				<tbody>${rows}${this.kechki_rows(sinflar.map((s) => ({ s, kun: this.kun })), sinflar.length)}</tbody>
			</table></div>
		`);
		this.bind_cells();
	}

	// Kechki (qo'shimcha) darslar bandi — oddiy darslardan keyin.
	// ustunlar: [{s, kun}] (kunlik = bir kun har sinf; haftalik = bir sinf har kun).
	kechki_rows(ustunlar, colspan) {
		const d = this.data;
		const kechki = d.kechki_darslar || [];
		const ed = this.canEdit && !this.moving;
		if (!kechki.length && !ed) return "";
		let html = `<tr class="kechki-sep"><th class="dars-no">🌙</th><td colspan="${colspan}">Kechki (qo'shimcha) darslar</td></tr>`;
		html += kechki.map((no) =>
			`<tr><th class="dars-no kechki-no"><b>${no}</b><span>kechki</span></th>${ustunlar.map((u) => this.cell_td(u.s, u.kun, no)).join("")}</tr>`
		).join("");
		if (ed) {
			html += `<tr class="kechki-add"><th class="dars-no">＋</th>${ustunlar.map((u) =>
				`<td class="k-add" data-sinf="${this.esc(u.s)}" data-kun="${this.esc(u.kun)}"><button class="k-add-btn" title="Kechki dars qo'shish">＋ kechki</button></td>`).join("")}</tr>`;
		}
		return html;
	}

	// Haftalik: tanlangan HAR guruh uchun alohida jadval — ustunlar = kunlar
	render_weekly() {
		const d = this.data;
		const kunlar = d.kunlar || [];
		const tanlangan = this.fSinflar.length ? this.fSinflar : (d.sinflar || []);
		if (!this.fSinflar.length && (d.sinflar || []).length > 3) {
			this.body.find(".jadval-wrap").html(
				`<div class="loading">🗓 Haftalik ko'rinish uchun yuqoridagi <b>«🏫 Barcha guruhlar»</b> tugmasidan bir yoki bir nechta guruh tanlang — ularning butun haftalik jadvali shu yerda chiqadi.</div>`);
			return;
		}
		const bloklar = tanlangan.map((s) => {
			const rows = (d.darslar || []).map((no) => {
				const cells = kunlar.map((k) => this.cell_td(s, k, no)).join("");
				const v = this.vaqt(s, no);
				return `<tr><th class="dars-no"><b>${no}</b><span>${this.esc(v)}</span></th>${cells}</tr>`;
			}).join("");
			const ed = this.canEdit && !this.moving;
			return `<div class="week-block">
				<div class="week-title">🏫 ${this.esc(this.sinf_nomi(s))}
					${ed ? `<span class="rn-week" data-sinf-h="${this.esc(s)}" title="Nomini o'zgartirish">✎</span>` : ""}</div>
				<div class="scroll-x">
				<table class="grid week ${this.moving ? "mv-mode" : ""}">
					<thead><tr><th class="dars-no">№</th>${kunlar.map((k) => `<th>${this.esc(k)}</th>`).join("")}</tr></thead>
					<tbody>${rows}${this.kechki_rows(kunlar.map((k) => ({ s, kun: k })), kunlar.length)}</tbody>
				</table></div></div>`;
		}).join("");
		this.body.find(".jadval-wrap").html(bloklar);
		this.bind_cells();
	}

	// Kataklar uchun umumiy hodisalar (kunlik + haftalik). Katak o'z kunini
	// data-kun dan oladi — shuning uchun haftalik ko'rinishda ham to'g'ri ishlaydi.
	bind_cells() {
		if (this.moving) {
			this.body.find("td[data-no]").on("click", (e) => {
				const td = $(e.currentTarget);
				this.drop_to(td.data("kun"), Number(td.data("no")), td);
			});
		}
		this.body.find(".lesson").on("click", (e) => {
			e.stopPropagation();
			if (this._dragDone) { this._dragDone = false; return; }
			const name = $(e.currentTarget).data("name");
			if (!this.canEdit) { frappe.set_route("Form", "Jadval Yozuvi", name); return; }
			if (this.moving) {
				if (this.moving.yozuv === name) { this.cancel_move(); return; }
				const td = $(e.currentTarget).closest("td[data-no]");
				if (td.length) this.drop_to(td.data("kun"), Number(td.data("no")), td);
				return;
			}
			this.start_move(name);
		});
		if (this.canEdit) {
			this.body.find(".lesson").on("contextmenu", (e) => {
				e.preventDefault(); e.stopPropagation();
				if (this.moving) { this.mv_lagandaga(); return; }
				this.ctx_menu($(e.currentTarget).data("name"), e.clientX, e.clientY);
			});
			this.enable_drag(this.body.find(".lesson"));
			if (!this.moving) {
				this.body.find("td.bosh").on("click", (e) => {
					const td = $(e.currentTarget);
					this.katak_dialog(td.data("sinf"), Number(td.data("no")), td.data("kun"));
				});
				this.body.find("th.sinf-h.editable, .rn-week").on("click", (e) => {
					this.rename_group_dialog($(e.currentTarget).data("sinf-h"));
				});
				this.body.find("td.k-add .k-add-btn").on("click", (e) => {
					const td = $(e.currentTarget).closest("td.k-add");
					this.kechki_dialog(td.data("sinf"), td.data("kun"));
				});
			}
		}
	}

	// ------------- kechki guruhga o'quvchi biriktirish -------------
	oquvchi_dialog(guruh) {
		frappe.call({
			method: `${MH_M}.guruh_oquvchilari`,
			args: { guruh },
			freeze: true,
			callback: (r) => {
				const d = r.message || {};
				const byClass = {};
				(d.nomzodlar || []).forEach((n) => { (byClass[n.sinf] = byClass[n.sinf] || []).push(n); });
				const sections = Object.keys(byClass).map((sinf) =>
					`<div class="sec-t mt">${this.esc(this.sinf_nomi(sinf))} <span class="mv-sub">(${byClass[sinf].length})</span></div>
					<div class="o-list">${byClass[sinf].map((n) =>
						`<label class="gp-item ${n.azo ? "on" : ""}"><input type="checkbox" class="o-st" value="${this.esc(n.student)}" ${n.azo ? "checked" : ""}> ${this.esc(n.nomi || n.student)}</label>`).join("")}</div>`).join("");
				const dlg = new frappe.ui.Dialog({
					title: `👥 ${this.esc(d.nomi || guruh)} — o'quvchilar`,
					size: "large",
					fields: [{ fieldtype: "HTML", fieldname: "body" }],
					primary_action_label: "Saqlash",
					primary_action: () => {
						const ids = dlg.$wrapper.find(".o-st:checked").map((i, e) => e.value).get();
						frappe.call({
							method: `${MH_M}.guruh_oquvchilari_saqla`,
							args: { guruh, studentlar: JSON.stringify(ids) },
							freeze: true,
							callback: (rr) => {
								dlg.hide();
								this.load(() => frappe.show_alert({
									message: `👥 ${(rr.message || {}).soni || 0} o'quvchi biriktirildi`, indicator: "green",
								}));
							},
						});
					},
				});
				dlg.fields_dict.body.$wrapper.html(`<div class="tz-jadval">
					<div class="mv-sub">Belgilangan o'quvchilar shu guruhga a'zo bo'ladi — kechki dars ularning jadvalida ko'rinadi.
					A'zo sinflar: ${this.esc((d.sinflar || []).map((s) => this.sinf_nomi(s)).join(", "))}</div>
					<div style="margin:8px 0"><button class="gp-mini" data-o="all">Barchasi</button>
						<button class="gp-mini" data-o="none">Tozalash</button></div>
					${sections || `<div class="mv-sub mt">Nomzod o'quvchi topilmadi (a'zo sinflarda o'quvchi yo'q).</div>`}
				</div>`);
				dlg.$body.find(`[data-o="all"]`).on("click", () => dlg.$body.find(".o-st").prop("checked", true));
				dlg.$body.find(`[data-o="none"]`).on("click", () => dlg.$body.find(".o-st").prop("checked", false));
				dlg.show();
			},
		});
	}

	// ------------- kechki (qo'shimcha) dars qo'shish -------------
	kechki_dialog(sinf, kun) {
		const all = this.data.sinflar || [];
		const checks = all.map((s) =>
			`<label class="gp-item ${s === sinf ? "on" : ""}"><input type="checkbox" class="k-sinf" value="${this.esc(s)}" ${s === sinf ? "checked" : ""}> ${this.esc(this.sinf_nomi(s))}</label>`).join("");
		const BITTA = "Bitta guruh (1 ustoz)";
		const dlg = new frappe.ui.Dialog({
			title: `🌙 Kechki dars qo'shish · ${kun}`,
			size: "large",
			fields: [
				{ fieldname: "fan", fieldtype: "Link", options: "Course", label: "Fan", reqd: 1 },
				{ fieldname: "boshlanish", fieldtype: "Time", label: "Boshlanish (soat)", reqd: 1 },
				{ fieldname: "cbt", fieldtype: "Column Break" },
				{ fieldname: "tugash", fieldtype: "Time", label: "Tugash (soat)", reqd: 1 },
				{ fieldname: "sb_s", fieldtype: "Section Break" },
				{ fieldname: "sinflar_html", fieldtype: "HTML", label: "Qatnashadigan sinflar" },
				{ fieldname: "rejim", fieldtype: "Select", label: "Guruh turi", default: BITTA,
					options: `${BITTA}\nDarajalarga bo'lingan (bir necha ustoz)` },
				{ fieldname: "oqituvchi", fieldtype: "Link", options: "Instructor", label: "O'qituvchi",
					depends_on: `eval:doc.rejim=='${BITTA}'` },
				{ fieldname: "dsec", fieldtype: "Section Break", label: "Darajalar (High / Middle / Low …)",
					depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "d1_nom", fieldtype: "Data", label: "1-daraja nomi", default: "High", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "d1_oqit", fieldtype: "Link", options: "Instructor", label: "1-daraja ustozi", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "cb1", fieldtype: "Column Break" },
				{ fieldname: "d2_nom", fieldtype: "Data", label: "2-daraja nomi", default: "Middle", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "d2_oqit", fieldtype: "Link", options: "Instructor", label: "2-daraja ustozi", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "sec3", fieldtype: "Section Break", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "d3_nom", fieldtype: "Data", label: "3-daraja nomi (ixtiyoriy)", depends_on: `eval:doc.rejim!='${BITTA}'` },
				{ fieldname: "d3_oqit", fieldtype: "Link", options: "Instructor", label: "3-daraja ustozi", depends_on: `eval:doc.rejim!='${BITTA}'` },
			],
			primary_action_label: "Qo'shish",
			primary_action: (v) => {
				const sinflar = dlg.$wrapper.find(".k-sinf:checked").map((i, e) => e.value).get();
				if (!sinflar.length) { frappe.msgprint("Kamida bitta sinf tanlang."); return; }
				let darajalar = [];
				if (v.rejim === BITTA) {
					darajalar = [{ nom: "", oqituvchi: v.oqituvchi || null }];
				} else {
					[[v.d1_nom, v.d1_oqit], [v.d2_nom, v.d2_oqit], [v.d3_nom, v.d3_oqit]].forEach(([n, o]) => {
						if ((n && n.trim()) || o) darajalar.push({ nom: (n || "").trim(), oqituvchi: o || null });
					});
					if (!darajalar.length) { frappe.msgprint("Kamida bitta daraja kiriting."); return; }
				}
				frappe.call({
					method: `${MH_M}.kechki_dars_qosh`,
					args: { versiya: this.versiya, kun, fan: v.fan,
						sinflar: JSON.stringify(sinflar), darajalar: JSON.stringify(darajalar),
						boshlanish: v.boshlanish || null, tugash: v.tugash || null },
					freeze: true,
					callback: (r) => {
						dlg.hide();
						const res = r.message || {};
						this.load(() => frappe.show_alert({
							message: `🌙 Kechki dars qo'shildi (${res.dars_raqami}-slot, ${(res.yaratilgan || []).length} yozuv). Endi o'quvchi biriktiring: dars kartasiga o'ng tugma → 👥`,
							indicator: "green",
						}));
					},
				});
			},
		});
		dlg.fields_dict.sinflar_html.$wrapper.html(
			`<div class="tz-jadval"><div class="gp-list" style="max-height:150px;border:1px solid var(--line);border-radius:8px;padding:6px">${checks}</div>
			<div class="mv-sub" style="margin-top:4px">Bir nechta sinf tanlansa — birga o'qiydigan (qo'shma/kross) kechki guruh bo'ladi.</div></div>`);
		dlg.show();
	}

	// ------------- guruh nomini o'zgartirish (sinf / daraja / tanlov / blok) -------------
	rename_group_dialog(guruh, hozir) {
		hozir = hozir || (this.data.sinf_nomlari || {})[guruh] || guruh;
		const d = new frappe.ui.Dialog({
			title: "Guruh nomini o'zgartirish",
			fields: [
				{
					fieldtype: "HTML",
					options: `<div class="tz-jadval tz-menu">
						<div class="mi"><span class="mi-l">Hozirgi nom</span><b>${this.esc(hozir)}</b></div>
						<div class="mv-sub">Faqat ko'rinadigan nom o'zgaradi. Guruhdagi <b>darslar</b> va
						<b>o'quvchilar</b> tegilmaydi; ichki ID va Moodle bog'lanishi barqaror qoladi.
						Yangi nom barcha jadval versiyalarida ko'rinadi.</div>
					</div>`,
				},
				{ fieldname: "yangi", fieldtype: "Data", label: "Yangi nom", reqd: 1, default: hozir },
			],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				const yangi = (v.yangi || "").trim();
				if (!yangi || yangi === hozir) { d.hide(); return; }
				frappe.call({
					method: `${MH_M}.guruh_nomini_ozgartir`,
					args: { guruh: guruh, yangi_nomi: yangi },
					freeze: true,
					callback: (r) => {
						d.hide();
						const res = r.message || {};
						this.load(() => frappe.show_alert({
							message: `✓ Nom o'zgartirildi: <b>${this.esc(res.yangi || yangi)}</b> (${res.darslar || 0} dars)` +
								(res.moodle === "navbatga qo'yildi" ? " · Moodle'ga yuborilmoqda" : ""),
							indicator: "green",
						}));
					},
				});
			},
		});
		d.show();
	}

	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".chip[data-kun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("kun");
			this.render();
		});
		// Kunlik / Haftalik ko'rinish
		this.body.find(".view-toggle [data-view]").on("click", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.render();
		});
		// Guruh tanlagich (ko'p tanlov)
		this.body.find(`[data-act="gp-toggle"]`).on("click", (e) => {
			e.stopPropagation();
			this.pickerOpen = !this.pickerOpen;
			this.render();
		});
		this.body.find(`[data-act="gp-all"]`).on("click", () => {
			this.fSinflar = [...(this.data.sinflar || [])];
			this.render();
		});
		this.body.find(`[data-act="gp-none"]`).on("click", () => {
			this.fSinflar = [];
			this.render();
		});
		this.body.find(".gp-panel input[data-gp]").on("change", (e) => {
			const s = $(e.currentTarget).data("gp");
			if (e.currentTarget.checked) {
				if (!this.fSinflar.includes(s)) this.fSinflar.push(s);
			} else {
				this.fSinflar = this.fSinflar.filter((x) => x !== s);
			}
			this.render();
		});
		// Panel ochiq bo'lsa — tashqariga bosilganda yopiladi
		if (this.pickerOpen) {
			setTimeout(() => {
				$(document).on("click.tzgp", (e) => {
					if (!$(e.target).closest(".grp-picker").length) {
						this.pickerOpen = false;
						$(document).off("click.tzgp");
						this.render();
					}
				});
			}, 0);
		}
		this.body.find(".fversiya").on("change", (e) => {
			this.versiya = e.target.value;
			this.undoStack = []; this.redoStack = []; this.moving = null;
			this.load();
		});
		this.body.find(`[data-act="yuklama"]`).on("click", () => this.yuklama_dialog());
		this.body.find(`[data-act="pdf"]`).on("click", () => this.pdf_dialog());
		this.body.find(`[data-act="import"]`).on("click", () => this.import_dialog());
		this.body.find(`[data-act="undo"]`).on("click", () => this.undo_op());
		this.body.find(`[data-act="redo"]`).on("click", () => this.redo_op());
		this.body.find(`[data-act="publish"]`).on("click", () => this.publish_dialog());
		this.body.find(`[data-act="make-draft"]`).on("click", () => this.make_draft());
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
					// Qulflangan — to'g'ridan-to'g'ri ochishni taklif qilamiz
					frappe.confirm(
						`🔒 <b>${this.esc(m.fan)} — ${this.esc(m.guruh_nomi)}</b> qulflangan.<br>Qulfni ochib ko'chirishga tayyorlaymizmi?`,
						() => frappe.call({
							method: `${MH_M}.qulf_toggle`, args: { yozuv: name }, freeze: true,
							callback: () => this.load(() => this.start_move(name, cb)),
						})
					);
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
					this.drop_to(td.dataset.kun || this.kun, Number(td.dataset.no), $(td));
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
			${info.guruh ? `<button data-c="students">👥 O'quvchilar biriktirish</button>` : ""}
			${info.guruh ? `<button data-c="rename">✎ Guruh nomini o'zgartirish</button>` : ""}
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
			else if (c === "lock") frappe.call({
				method: `${MH_M}.qulf_toggle`, args: { yozuv: name }, freeze: true,
				callback: (r) => this.load(() => frappe.show_alert({
					message: (r.message || {}).qulf ? "🔒 Qulflandi" : "🔓 Qulf ochildi", indicator: "blue",
				})),
			});
			else if (c === "tray") this.start_move(name, () => this.mv_lagandaga());
			else if (c === "students") this.oquvchi_dialog(info.guruh);
			else if (c === "rename") this.rename_group_dialog(info.guruh, info.guruh_nomi || info.guruh);
			else if (c === "form") frappe.set_route("Form", "Jadval Yozuvi", name);
			else if (c === "del") {
				frappe.confirm(`«${this.esc(info.fan || "")} — ${this.esc(info.guruh_nomi || info.guruh || "")}» BUTUNLAY o'chirilsinmi? (qaytarib bo'lmaydi; vaqtincha olish uchun Laganda bor)`, () => {
					frappe.call({ method: `${OJ_M}.dars_ochir`, args: { name }, callback: () => this.load() });
				});
			}
		});
	}

	// -------- bo'sh katak: "bu yerga nima sig'adi?" (aSc teskari qidiruv) --------
	katak_dialog(sinf, no, kun) {
		kun = kun || this.kun;
		frappe.call({
			method: `${MH_M}.katak_kandidatlar`,
			args: { sinf, kun: kun, dars_raqami: no, versiya: this.versiya },
			freeze: true,
			callback: (r) => {
				const d = r.message || {};
				const koch = (d.kochirish || []);
				const mumkin = koch.filter((k) => k.mumkin);
				const yoq = koch.filter((k) => !k.mumkin);
				const dlg = new frappe.ui.Dialog({
					title: `${this.esc(this.sinf_nomi(sinf)).replace(/\s*\((full|hybrid)\)/, "")} · ${kun} ${no}-dars — nima sig'adi?`,
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
					this.start_move(yozuv, () => this.drop_to(kun, no));
				});
				dlg.$body.find("[data-add]").on("click", (e) => {
					const oqit = $(e.currentTarget).data("add");
					const nomi = $(e.currentTarget).data("nomi");
					dlg.hide();
					this.dars_qosh_dialog(sinf, no, oqit, nomi, kun);
				});
			},
		});
	}

	dars_qosh_dialog(sinf, no, oqituvchi, nomi, kun) {
		kun = kun || this.kun;
		const d = new frappe.ui.Dialog({
			title: `Dars qo'shish: ${kun} ${no}-dars · ${this.esc(this.sinf_nomi(sinf))}`,
			fields: [
				{ fieldname: "fan", fieldtype: "Link", options: "Course", label: "Fan", reqd: 1 },
				{ fieldname: "info", fieldtype: "HTML", options: `<div class="text-muted" style="font-size:12px">O'qituvchi: <b>${this.esc(nomi)}</b> · Guruh: ${this.esc(this.sinf_nomi(sinf))}</div>` },
			],
			primary_action_label: "Qo'shish",
			primary_action: (v) => {
				frappe.call({
					method: `${OJ_M}.dars_qosh`,
					args: { oqituvchi, kun: kun, dars_raqami: no, fan: v.fan, guruh: sinf, versiya: this.versiya },
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

	// ---------------- PDF / chop etish (maktab doskasi uchun) ----------------
	pdf_dialog() {
		const tanlangan = this.fSinflar.length;
		const d = new frappe.ui.Dialog({
			title: "🖨 Dars jadvalini chop etish / PDF",
			fields: [
				{ fieldname: "maktab", fieldtype: "Data", label: "Maktab nomi (sarlavha)",
					default: "Target International School", reqd: 1 },
				{ fieldname: "rejim", fieldtype: "Select", label: "Ko'rinish", default: "Har sinf — haftalik varaq",
					options: "Har sinf — haftalik varaq\nHar kun — umumiy to'r" },
				{ fieldname: "cb0", fieldtype: "Column Break" },
				{ fieldname: "qamrov", fieldtype: "Select", label: "Qaysi guruhlar",
					default: tanlangan ? "Tanlangan guruhlar" : "Barcha sinflar",
					options: "Barcha sinflar\nTanlangan guruhlar" },
				{ fieldname: "yonalish", fieldtype: "Select", label: "Varaq yo'nalishi", default: "Bo'yiga (portrait)",
					options: "Bo'yiga (portrait)\nEniga (landscape)" },
				{ fieldname: "sb", fieldtype: "Section Break" },
				{ fieldname: "oqituvchi", fieldtype: "Check", label: "O'qituvchi ismi ko'rsatilsin", default: 1 },
				{ fieldname: "cb1", fieldtype: "Column Break" },
				{ fieldname: "kechki", fieldtype: "Check", label: "Kechki darslar ham", default: 1 },
			],
			primary_action_label: "Chop etish / PDF",
			primary_action: (v) => {
				d.hide();
				this.print_schedule({
					maktab: v.maktab || "Target International School",
					rejim: v.rejim,
					qamrov: v.qamrov,
					landscape: v.yonalish.indexOf("Eniga") >= 0,
					oqituvchi: !!v.oqituvchi,
					kechki: !!v.kechki,
				});
			},
		});
		d.show();
	}

	// Bitta katak ichidagi darslar (chop uchun)
	_pcell(sinf, kun, no, opts, regMax) {
		const list = (this.data.katak || {})[`${sinf}|${kun}|${no}`] || [];
		if (!list.length) return "";
		return list.map((x) => {
			const t = (no > regMax && (x.boshlanish || x.tugash))
				? `<div class="pt">${this.esc(x.boshlanish || "")}–${this.esc(x.tugash || "")}</div>` : "";
			const tc = opts.oqituvchi && x.oqituvchi ? `<div class="ptc">${this.esc(x.oqituvchi)}</div>` : "";
			return `<div class="pl"><div class="ps">${this.esc(x.fan)}</div>${tc}${t}</div>`;
		}).join("");
	}

	print_schedule(opts) {
		const d = this.data;
		const kunlar = d.kunlar || [];
		const regMax = d.regular_max || 10;
		const EN_KUN = {
			"Dushanba": "Monday", "Seshanba": "Tuesday", "Chorshanba": "Wednesday",
			"Payshanba": "Thursday", "Juma": "Friday", "Shanba": "Saturday",
		};
		const enk = (k) => EN_KUN[k] || k;
		const bugun = frappe.datetime.get_today();
		const nums = [...(d.darslar || []), ...(opts.kechki ? (d.kechki_darslar || []) : [])];
		const sinflar = opts.qamrov === "Tanlangan guruhlar" && this.fSinflar.length
			? this.fSinflar : (d.sinflar || []);

		// Sarlavha: bitta qator — to'liq logo (emblema + maktab nomi) CHAPDA,
		// o'rtada "Class Timetable" + to'liq sinf/kun nomi. Versiya matni yo'q.
		const logo = "/assets/target_zenit/images/logo-target-full.png";
		const head = (big) => `<div class="phead">
			<img class="plogo" src="${logo}" alt="Target International School">
			<div class="pcenter"><div class="pdj">Class Timetable</div><div class="pcls">${big}</div></div>
		</div>`;

		let body = "";
		if (opts.rejim.indexOf("Har kun") >= 0) {
			// Per day — whole-school grid (columns = classes)
			body = kunlar.map((k) => {
				const rows = nums.map((no) => {
					const isK = no > regMax;
					const cells = sinflar.map((s) => `<td class="${isK ? "ke" : ""}">${this._pcell(s, k, no, opts, regMax)}</td>`).join("");
					const t = isK ? "" : this.vaqt(sinflar[0] || "", no);
					return `<tr class="${isK ? "kerow" : ""}"><th class="pno">${no}${t ? `<span>${this.esc(t)}</span>` : ""}</th>${cells}</tr>`;
				}).join("");
				return `<div class="sheet">${head(this.esc(enk(k)))}
					<table class="ptbl"><thead><tr><th class="pno">No.</th>${sinflar.map((s) => `<th>${this.esc(this.sinf_nomi(s))}</th>`).join("")}</tr></thead>
					<tbody>${rows}</tbody></table>
					<div class="pfoot">Printed: ${bugun}</div></div>`;
			}).join("");
		} else {
			// Per class — weekly sheet (columns = days)
			body = sinflar.map((s) => {
				const rows = nums.map((no) => {
					const isK = no > regMax;
					const t = isK ? "" : this.vaqt(s, no);
					const cells = kunlar.map((k) => `<td class="${isK ? "ke" : ""}">${this._pcell(s, k, no, opts, regMax)}</td>`).join("");
					return `<tr class="${isK ? "kerow" : ""}"><th class="pno">${no}${t ? `<span>${this.esc(t)}</span>` : ""}</th>${cells}</tr>`;
				}).join("");
				return `<div class="sheet">${head(this.esc(this.sinf_nomi(s)))}
					<table class="ptbl"><thead><tr><th class="pno">No.</th>${kunlar.map((k) => `<th>${this.esc(enk(k))}</th>`).join("")}</tr></thead>
					<tbody>${rows}</tbody></table>
					<div class="pfoot">Printed: ${bugun}</div></div>`;
			}).join("");
		}

		const html = `<!doctype html><html><head><meta charset="utf-8"><title>Class Timetable — ${this.esc(opts.maktab)}</title>
		<style>
		@page { size: A4 ${opts.landscape ? "landscape" : "portrait"}; margin: 12mm; }
		* { box-sizing: border-box; }
		body { font-family: "Segoe UI", Arial, sans-serif; color: #111; margin: 0; }
		.sheet { page-break-after: always; padding: 0; }
		.sheet:last-child { page-break-after: auto; }
		.phead { position: relative; display: flex; align-items: center; justify-content: center;
			min-height: 60px; margin-bottom: 10px; border-bottom: 3px double #0a2342; padding-bottom: 8px; }
		.plogo { position: absolute; left: 0; top: 50%; transform: translateY(-50%); height: 56px; width: auto; }
		.pcenter { text-align: center; }
		.pdj { font-size: 13px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase; color: #777; }
		.pcls { font-size: 30px; font-weight: 800; color: #0a2342; }
		.ptbl { width: 100%; border-collapse: collapse; table-layout: fixed; }
		.ptbl th, .ptbl td { border: 1.2px solid #222; padding: 4px 5px; vertical-align: top; }
		.ptbl thead th { background: #2d2d2d; color: #fff; font-size: 14px; text-align: center; padding: 7px 4px; }
		.ptbl th.pno { width: 54px; text-align: center; background: #efefef; color: #111; font-size: 15px; }
		.ptbl th.pno span { display: block; font-size: 9px; font-weight: 400; color: #555; }
		.ptbl thead th.pno { background: #2d2d2d; color: #fff; }
		.ptbl td { height: 40px; }
		.pl { margin-bottom: 3px; }
		.pl:last-child { margin-bottom: 0; }
		.ps { font-weight: 700; font-size: 13px; }
		.ptc { font-size: 10px; color: #555; }
		.pt { font-size: 9px; color: #7a52d8; font-weight: 600; }
		tr.kerow th.pno, tr.kerow td.ke { background: #f4f1fb; }
		tr.kerow td.ke { border-top: 2px solid #7a52d8; }
		.pfoot { margin-top: 8px; font-size: 10px; color: #888; text-align: right; }
		@media screen { body { background: #ddd; } .sheet { background: #fff; max-width: ${opts.landscape ? "1050px" : "780px"}; margin: 14px auto; padding: 24px; box-shadow: 0 2px 10px rgba(0,0,0,.2); } }
		</style></head><body>${body || '<div class="sheet"><div class="phead"><div class="pcenter"><div class="pcls">No data</div></div></div></div>'}
		<script>window.onload=function(){setTimeout(function(){try{window.focus();window.print();}catch(e){}},300);};<\/script>
		</body></html>`;

		const w = window.open("", "tz_jadval_pdf");
		if (!w) { frappe.msgprint("Chop oynasi ochilmadi — brauzer pop-up'ni bloklagan bo'lishi mumkin. Ruxsat bering va qayta urining."); return; }
		w.document.open();
		w.document.write(html);
		w.document.close();
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
