// Copyright (c) 2026, Target Zenit — Dars jadvali (zavuch paneli)
// Sinflar x darslar to'ri, kun bo'yicha. Manba: Jadval Yozuvi (haftalik shablon).
frappe.pages["dars-jadvali"].on_page_load = function (wrapper) {
	new TZDarsJadvali(wrapper);
};

const DJ_M = "target_zenit.target_zenit.page.dars_jadvali.dars_jadvali";
const IMP_M = "target_zenit.dars_jadvali.import_excel";

class TZDarsJadvali {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dars jadvali"), single_column: true });
		this.data = null;
		this.kun = "Dushanba";
		this.versiya = null;
		this.fSinf = "";
		this.fOqituvchi = "";
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
				<select class="fsinf">
					<option value="">Barcha sinflar</option>
					${(d.sinflar || []).map((s) => `<option value="${this.esc(s)}" ${this.fSinf === s ? "selected" : ""}>${this.esc(s)}</option>`).join("")}
				</select>
				<button class="refresh" data-act="yuklama">O'qituvchi yuklamasi</button>
				<button class="refresh primary" data-act="import">⬆ Exceldan import</button>
			</div>

			<div class="jadval-wrap card"></div>
		`);
		this.render_grid();
		this.bind();
	}

	render_grid() {
		const d = this.data;
		const sinflar = this.sinflar();
		const rows = (d.darslar || []).map((no) => {
			const kataklar = sinflar.map((s) => {
				const list = (d.katak || {})[`${s}|${this.kun}|${no}`] || [];
				if (!list.length) return `<td class="bosh"></td>`;
				const inner = list.map((x) => {
					const h = this.rang(x.fan);
					const blok = x.blok ? ` <span class="bk">${this.esc(x.guruh_nomi || "").split(" ")[1] || ""}</span>` : "";
					return `<div class="lesson" style="--h:${h}" data-name="${this.esc(x.name)}" title="${this.esc(x.guruh_nomi || "")}">
						<div class="fan">${this.esc(x.fan)}${blok}</div>
						<div class="oqit">${this.esc(x.oqituvchi || "—")}</div>
					</div>`;
				}).join("");
				return `<td class="${list.length > 1 ? "multi" : ""}">${inner}</td>`;
			}).join("");
			const v = sinflar.length ? this.vaqt(sinflar[0], no) : "";
			return `<tr><th class="dars-no"><b>${no}</b><span>${this.esc(v)}</span></th>${kataklar}</tr>`;
		}).join("");

		this.body.find(".jadval-wrap").html(`
			<div class="scroll-x">
			<table class="grid">
				<thead><tr><th class="dars-no">№</th>${sinflar.map((s) => `<th>${this.esc(s.replace(/\s*\((full|hybrid)\)/, ""))}<span>${this.esc(/hybrid/.test(s) ? "hybrid" : "full")}</span></th>`).join("")}</tr></thead>
				<tbody>${rows}</tbody>
			</table></div>
		`);
		this.body.find(".lesson").on("click", (e) => {
			const n = $(e.currentTarget).data("name");
			frappe.set_route("Form", "Jadval Yozuvi", n);
		});
	}

	bind() {
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".chip[data-kun]").on("click", (e) => {
			this.kun = $(e.currentTarget).data("kun");
			this.render();
		});
		this.body.find(".fsinf").on("change", (e) => { this.fSinf = e.target.value; this.render_grid(); });
		this.body.find(".fversiya").on("change", (e) => { this.versiya = e.target.value; this.load(); });
		this.body.find(`[data-act="yuklama"]`).on("click", () => this.yuklama_dialog());
		this.body.find(`[data-act="import"]`).on("click", () => this.import_dialog());
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
