// Copyright (c) 2026, Target Zenit — Dars jadvali (zavuch paneli)
// Sinflar x darslar to'ri, kun bo'yicha. Manba: Jadval Yozuvi (haftalik shablon).
// Muharrir qatlami (jahon standartlari: aSc/Untis/Prime): karta ko'tarilganda
// slotlar jonli bo'yaladi (yashil=mumkin/qizil=band+NEGA), lock/pin, undo,
// bo'sh katakka "bu yerga nima sig'adi" teskari qidiruv.
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
		this.undo = [];          // [{yozuv, kun, dars}] — ko'chirishlarni qaytarish
		this.canEdit = MH_ROLLAR.some((r) => frappe.user_roles.includes(r));
		this.make_skeleton();
		this.load();
		this.listen_import();
	}

	// Fon vazifasi tugaganda natijani ko'rsatish
	listen_import() {
		frappe.realtime.on("jadval_import_tugadi", (r) => {
			if (this.import_dlg) this.import_dlg.hide();
			this.show_import_result(r);
			this.load();
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

	load() {
		frappe.call({
			method: `${DJ_M}.get_data`,
			args: { versiya: this.versiya },
			freeze: true,
			callback: (r) => {
				this.data = r.message || {};
				if (this.data.xatolik) {
					this.body.html(`<div class="loading">${this.esc(this.data.xatolik)}</div>`);
					return;
				}
				this.versiya = this.data.versiya;
				this.render();
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
				${this.canEdit ? `<button class="refresh" data-act="undo" ${this.undo.length ? "" : "disabled"}>↶ Qaytarish${this.undo.length ? ` (${this.undo.length})` : ""}</button>` : ""}
				<select class="fsinf">
					<option value="">Barcha sinflar</option>
					${(d.sinflar || []).map((s) => `<option value="${this.esc(s)}" ${this.fSinf === s ? "selected" : ""}>${this.esc(s)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="yuklama">O'qituvchi yuklamasi</button>
				<button class="refresh primary" data-act="import">⬆ Exceldan import</button>
			</div>

			<div class="mvbar-wrap"></div>
			<div class="jadval-wrap card"></div>
		`);
		this.render_mvbar();
		this.render_grid();
		this.bind();
	}

	// ------------- ko'chirish banneri ("karta qo'lda") -------------
	render_mvbar() {
		const w = this.body.find(".mvbar-wrap");
		if (!this.moving) { w.empty(); return; }
		const m = this.moving;
		const blok = m.blok_hajmi > 1 ? ` · blok: ${m.blok_hajmi} parallel dars birga ko'chadi` : "";
		w.html(`<div class="mvbar">
			<span class="mv-ico">✋</span>
			<b>${this.esc(m.fan)}</b>&nbsp;— ${this.esc(m.guruh_nomi)}
			<span class="mv-sub">(hozir: ${this.esc(m.kun)} ${m.dars_raqami}-dars${blok})</span>
			<span class="mv-hint">Yashil = bo'sh joy · Sariq ↔ = almashuv · kun tablari bilan boshqa kunga ham o'tiladi</span>
			<span class="spacer"></span>
			<button class="refresh" data-act="mv-cancel">Bekor (Esc)</button>
		</div>`);
		w.find(`[data-act="mv-cancel"]`).on("click", () => this.cancel_move());
	}

	cancel_move() {
		this.moving = null;
		$(document).off("keyup.tzmv");
		this.render();
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
						else if (st.holat === "almashuv") { mvCls = "mv-swap"; mvTitle = "↔ Almashuv: " + (st.bilan || []).join("; "); }
						else { mvCls = "mv-band"; mvTitle = (st.sabab || []).join("\n"); }
					} else mvCls = "mv-dim";
				}
				const attrs = `data-sinf="${this.esc(s)}" data-no="${no}" class="${list.length ? (list.length > 1 ? "multi" : "") : "bosh"} ${mvCls}" ${mvTitle ? `title="${this.esc(mvTitle)}"` : ""}`;
				if (!list.length) return `<td ${attrs}></td>`;
				const inner = list.map((x) => {
					const h = this.rang(x.fan);
					const blok = x.blok ? ` <span class="bk">${this.esc(x.guruh_nomi || "").split(" ")[1] || ""}</span>` : "";
					const lk = x.qulf ? `<span class="lk" title="Qulflangan">🔒</span>` : "";
					return `<div class="lesson" style="--h:${h}" data-name="${this.esc(x.name)}" title="${this.esc(x.guruh_nomi || "")}">
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
			// Faqat mumkin bo'lgan kataklar bosiladi
			this.body.find("td.mv-ok, td.mv-afzal").on("click", (e) => {
				const no = Number($(e.currentTarget).data("no"));
				this.do_move(this.kun, no);
			});
			this.body.find("td.mv-swap").on("click", (e) => {
				const no = Number($(e.currentTarget).data("no"));
				const st = (this.moving.xarita || {})[`${this.kun}|${no}`] || {};
				const bilan = (st.bilan || []).map((b) => this.esc(b)).join("; ");
				frappe.confirm(
					`<b>${this.esc(this.moving.fan)} — ${this.esc(this.moving.guruh_nomi)}</b> ↔ <b>${bilan}</b><br>O'rinlari almashtirilsinmi?`,
					() => this.do_swap(this.kun, no)
				);
			});
			return;
		}
		this.body.find(".lesson").on("click", (e) => {
			e.stopPropagation();
			this.lesson_menu($(e.currentTarget).data("name"));
		});
		if (this.canEdit) {
			this.body.find("td.bosh").on("click", (e) => {
				const td = $(e.currentTarget);
				this.katak_dialog(td.data("sinf"), Number(td.data("no")));
			});
		}
	}

	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".chip[data-kun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("kun");
			this.render();
		});
		this.body.find(".fsinf").on("change", (e) => { this.fSinf = e.target.value; this.render_grid(); });
		this.body.find(".fversiya").on("change", (e) => { this.versiya = e.target.value; this.undo = []; this.load(); });
		this.body.find(`[data-act="yuklama"]`).on("click", () => this.yuklama_dialog());
		this.body.find(`[data-act="import"]`).on("click", () => this.import_dialog());
		this.body.find(`[data-act="undo"]`).on("click", () => this.undo_move());
	}

	// ---------------- muharrir: dars menyusi / ko'chirish / qulf ----------------
	lesson_info(name) {
		for (const key in this.data.katak || {}) {
			for (const x of this.data.katak[key]) {
				if (x.name === name) return x;
			}
		}
		return null;
	}

	lesson_menu(name) {
		const x = this.lesson_info(name);
		if (!x) return;
		if (!this.canEdit) {
			frappe.set_route("Form", "Jadval Yozuvi", name);
			return;
		}
		const dlg = new frappe.ui.Dialog({
			title: `${x.fan} — ${x.guruh_nomi || x.guruh}`,
			size: "small",
			fields: [{
				fieldtype: "HTML",
				options: `<div class="tz-jadval tz-menu">
					<div class="mi"><span class="mi-l">O'qituvchi</span><b>${this.esc(x.oqituvchi || "—")}</b></div>
					${x.blok ? `<div class="mi"><span class="mi-l">Blok</span><b>${this.esc(x.blok)}</b> <span class="mv-sub">(parallel darslar birga ko'chadi)</span></div>` : ""}
					${x.qulf ? `<div class="mi"><span class="mi-l">Holat</span><b>🔒 Qulflangan</b></div>` : ""}
					<div class="menu-btns">
						<button class="refresh primary" data-m="move" ${x.qulf ? "disabled" : ""}>✋ Ko'chirish</button>
						<button class="refresh" data-m="lock">${x.qulf ? "🔓 Qulfni ochish" : "🔒 Qulflash"}</button>
						<button class="refresh" data-m="form">📄 Hujjat</button>
						<button class="refresh danger" data-m="del">🗑 O'chirish</button>
					</div>
				</div>`,
			}],
		});
		dlg.show();
		dlg.$body.find(`[data-m="move"]`).on("click", () => { dlg.hide(); this.start_move(name); });
		dlg.$body.find(`[data-m="lock"]`).on("click", () => {
			dlg.hide();
			frappe.call({ method: `${MH_M}.qulf_toggle`, args: { yozuv: name }, callback: () => this.load() });
		});
		dlg.$body.find(`[data-m="form"]`).on("click", () => { dlg.hide(); frappe.set_route("Form", "Jadval Yozuvi", name); });
		dlg.$body.find(`[data-m="del"]`).on("click", () => {
			dlg.hide();
			frappe.confirm(`«${this.esc(x.fan)} — ${this.esc(x.guruh_nomi || x.guruh)}» darsini o'chirasizmi?`, () => {
				frappe.call({ method: `${OJ_M}.dars_ochir`, args: { name }, callback: () => this.load() });
			});
		});
	}

	start_move(name) {
		frappe.call({
			method: `${MH_M}.kochirish_xarita`,
			args: { yozuv: name },
			freeze: true,
			callback: (r) => {
				const m = r.message;
				if (!m) return;
				if (m.qulf) { frappe.msgprint("Dars qulflangan — avval qulfni oching."); return; }
				this.moving = m;
				$(document).on("keyup.tzmv", (e) => { if (e.key === "Escape") this.cancel_move(); });
				this.render();
			},
		});
	}

	do_move(kun, no, yozuv) {
		const target = yozuv || (this.moving && this.moving.yozuv);
		if (!target) return;
		frappe.call({
			method: `${MH_M}.dars_kochir`,
			args: { yozuv: target, kun, dars_raqami: no },
			freeze: true,
			callback: (r) => {
				const res = r.message || {};
				if (res.eski) this.undo.push({ yozuv: target, kun: res.eski.kun, dars: res.eski.dars_raqami });
				this.moving = null;
				$(document).off("keyup.tzmv");
				this.load();
			},
		});
	}

	do_swap(kun, no) {
		const target = this.moving && this.moving.yozuv;
		if (!target) return;
		frappe.call({
			method: `${MH_M}.dars_almashtir`,
			args: { yozuv: target, kun, dars_raqami: no },
			freeze: true,
			callback: (r) => {
				const res = r.message || {};
				if (res.eski) this.undo.push({ yozuv: target, kun: res.eski.kun, dars: res.eski.dars_raqami, swap: 1 });
				this.moving = null;
				$(document).off("keyup.tzmv");
				this.load();
			},
		});
	}

	undo_move() {
		const u = this.undo.pop();
		if (!u) return;
		frappe.call({
			method: `${MH_M}.${u.swap ? "dars_almashtir" : "dars_kochir"}`,
			args: { yozuv: u.yozuv, kun: u.kun, dars_raqami: u.dars },
			freeze: true,
			callback: () => this.load(),
			error: () => this.undo.push(u),
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
				const rows_m = mumkin.map((k) => `
					<tr><td><b>${this.esc(k.fan)}</b> — ${this.esc(k.guruh_nomi)}${k.blok_hajmi > 1 ? ` <span class="mv-sub">(blok ×${k.blok_hajmi})</span>` : ""}</td>
					<td class="mv-sub">${this.esc(k.kun)} ${k.dars_raqami}-dars</td>
					<td class="r"><button class="refresh mini" data-koch="${this.esc(k.yozuv)}">→ bu yerga</button></td></tr>`).join("");
				const rows_y = yoq.slice(0, 12).map((k) => `
					<tr class="dim"><td>${this.esc(k.fan)} — ${this.esc(k.guruh_nomi)}</td>
					<td class="mv-sub">${this.esc(k.kun)} ${k.dars_raqami}</td>
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
					this.do_move(this.kun, no, $(e.currentTarget).data("koch"));
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
