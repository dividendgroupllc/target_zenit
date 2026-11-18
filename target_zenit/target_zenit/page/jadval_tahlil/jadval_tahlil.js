// Copyright (c) 2026, Target Zenit — Jadval yetarlilik (feasibility) tahlili
// "Хватит ли учителей?" — jadval tuzishdan oldin sig'im yetadimi: o'qituvchi talab vs sig'im,
// sinf band vs grid, vakant darslar, fan malaka sig'imi.
frappe.pages["jadval-tahlil"].on_page_load = function (wrapper) {
	new TZJadvalTahlil(wrapper);
};

const JT_M = "target_zenit.dars_jadvali.jadval_tahlil";

class TZJadvalTahlil {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Jadval yetarlilik tahlili"), single_column: true });
		this.tab = "oqituvchilar";
		this.make_skeleton();
		this.load();
	}
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jt"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	load() {
		frappe.call({ method: `${JT_M}.tahlil`, callback: (r) => { this.d = r.message; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`) });
	}
	render() {
		const d = this.d; if (!d) return;
		const s = d.stats;
		this.body.html(`
			<div class="topbar"><div><h1>Jadval yetarlilik tahlili</h1>
				<div class="sub">Sig'im yetadimi — jadval tuzishdan oldin muammolarni ko'rsatadi · versiya: ${this.esc(d.versiya)}</div></div>
				<button class="refresh" data-act="reload">↻ Yangilash</button></div>
			<div class="cards">
				<div class="kpi"><div class="lab">Jami dars</div><div class="val">${s.jami_dars}</div></div>
				<div class="kpi ${s.vakant ? "bad" : "ok"}"><div class="lab">Vakant (o'qituvchisiz)</div><div class="val">${s.vakant}</div></div>
				<div class="kpi ${s.oq_muammo ? "bad" : "ok"}"><div class="lab">O'qituvchi sig'im muammosi</div><div class="val">${s.oq_muammo}</div></div>
				<div class="kpi ${s.sinf_muammo ? "bad" : "ok"}"><div class="lab">Sinf sig'im muammosi</div><div class="val">${s.sinf_muammo}</div></div>
			</div>
			<div class="tabs">
				<button data-t="oqituvchilar" class="${this.tab === "oqituvchilar" ? "on" : ""}">O'qituvchilar (${d.oqituvchilar.length})</button>
				<button data-t="sinflar" class="${this.tab === "sinflar" ? "on" : ""}">Sinflar (${d.sinflar.length})</button>
				<button data-t="fanlar" class="${this.tab === "fanlar" ? "on" : ""}">Fanlar (${d.fanlar.length})</button>
				${d.sanpin && d.sanpin.shkala_bor ? `<button data-t="sanpin" class="${this.tab === "sanpin" ? "on" : ""}">SanPiN yuklama${d.sanpin.muammoli ? ` (${d.sanpin.muammoli} ogoh)` : ""}</button>` : ""}
			</div>
			<div class="card tbl-wrap"></div>
		`);
		this.render_tab();
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".tabs button").on("click", (e) => { this.tab = $(e.currentTarget).data("t"); this.render(); });
	}
	badge(h) {
		if (h === "ok") return `<span class="pill ok">OK</span>`;
		if (h === "toliq") return `<span class="pill full">To'liq</span>`;
		if (h === "norma_oshgan") return `<span class="pill warn">Norma oshgan</span>`;
		if (h === "sigim_oshgan") return `<span class="pill bad">Sig'im oshgan</span>`;
		return `<span class="pill">${this.esc(h)}</span>`;
	}
	render_tab() {
		const d = this.d; let html = "";
		if (this.tab === "sanpin") {
			this.render_sanpin();
			return;
		}
		if (this.tab === "oqituvchilar") {
			html = `<table class="tbl"><thead><tr><th>O'qituvchi</th><th class="r">Talab (soat)</th><th class="r">Sig'im</th><th class="r">Norma</th><th class="r">Ish kuni</th><th class="r">Bo'sh</th><th>Holat</th></tr></thead><tbody>
				${d.oqituvchilar.map((o) => `<tr class="${o.holat !== "ok" ? "hl" : ""}">
					<td>${this.esc(o.nomi)}</td><td class="r">${o.talab}</td><td class="r">${o.sigim}</td>
					<td class="r">${o.norma || "—"}</td><td class="r">${o.kunlar_bor}</td>
					<td class="r ${o.bosh < 0 ? "red" : ""}">${o.bosh}</td><td>${this.badge(o.holat)}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Sig'im = mavjud kun/dars slotlari (mavjudlik + limitlardan), norma bo'lsa shu bilan cheklangan. «Sig'im oshgan» = talab > sig'im → jadval yig'ilmaydi (grafik kengaytirish yoki ikkinchi o'qituvchi kerak).</div>`;
		} else if (this.tab === "sinflar") {
			html = `<table class="tbl"><thead><tr><th>Sinf</th><th class="r">Band slot</th><th class="r">Sig'im (grid)</th><th class="r">Bo'sh</th><th>Holat</th></tr></thead><tbody>
				${d.sinflar.map((s) => `<tr class="${s.holat === "sigim_oshgan" ? "hl" : ""}">
					<td>${this.esc(s.sinf)}</td><td class="r">${s.band}</td><td class="r">${s.sigim}</td>
					<td class="r">${s.bosh}</td><td>${this.badge(s.holat)}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Sig'im = ${d.ndars} dars × 5 kun = ${d.grid_sigim}. «Sig'im oshgan» = darslar grid'ga sig'maydi (qo'ng'iroqqa dars qo'shish yoki soat kamaytirish kerak).</div>`;
		} else {
			html = `<table class="tbl"><thead><tr><th>Fan</th><th class="r">Talab (soat)</th><th class="r">O'qituvchilar</th><th class="r">Umumiy sig'im</th><th>Holat</th></tr></thead><tbody>
				${d.fanlar.map((f) => `<tr class="${f.kam ? "hl" : ""}">
					<td>${this.esc(f.fan)}</td><td class="r">${f.talab}</td><td class="r">${f.oqituvchilar_soni}</td>
					<td class="r">${f.umumiy_sigim}</td><td>${f.kam ? this.badge("sigim_oshgan") : this.badge("ok")}</td></tr>`).join("")}
				</tbody></table>
				<div class="note">Fanni o'tadigan o'qituvchilarning umumiy sig'imi talabдан kam bo'lsa — malakali o'qituvchi yetmaydi.</div>`;
		}
		this.body.find(".tbl-wrap").html(html);
	}

	// -------- SanPiN / Sivkov: kunlik qiyinchilik balli gistogrammasi --------
	render_sanpin() {
		const sp = this.d.sanpin || {};
		const kunlar = sp.kunlar || [];
		const maxBall = Math.max(1, ...(sp.sinflar || []).flatMap((s) => kunlar.map((k) => s.kunlik[k] || 0)));
		const rows = (sp.sinflar || []).map((s) => {
			const cells = kunlar.map((k) => {
				const v = s.kunlik[k] || 0;
				const p = Math.round((v / maxBall) * 100);
				const top = k === s.eng_ogir;
				return `<td class="r sp-cell ${top ? "sp-top" : ""}">
					<div class="sp-val">${v}</div><div class="sp-bar"><i style="width:${p}%"></i></div></td>`;
			}).join("");
			const og = (s.ogohlar || []).length;
			return `<tr class="${og ? "hl" : ""}">
				<td><b>${this.esc(s.sinf)}</b></td>${cells}
				<td class="r">${s.jami}</td>
				<td>${og ? `<details><summary class="pill warn">${og} ogoh</summary>
					<ul class="sp-og">${s.ogohlar.map((o) => `<li>${this.esc(o)}</li>`).join("")}</ul></details>`
					: `<span class="pill ok">OK</span>`}</td></tr>`;
		}).join("");
		this.body.find(".tbl-wrap").html(`
			<div class="sp-head">
				<div class="note" style="margin:0">Kunlik qiyinchilik balli (Sivkov/SanPiN shkalasi, parallel daraja darslari — slot bo'yicha bir marta).
					Me'yor: cho'qqi <b>seshanba–chorshanbada</b>, dushanba/juma yengil; ikki og'ir fan ketma-ket kelmasin.
					Ballarni <a href="/app/fan-qiyinchiligi">Fan Qiyinchiligi</a> ro'yxatida o'zgartirish mumkin.</div>
				<button class="refresh" data-act="spravka">🖨 Spravka</button>
			</div>
			<table class="tbl"><thead><tr><th>Sinf</th>${kunlar.map((k) => `<th class="r">${k.slice(0, 2)}</th>`).join("")}
				<th class="r">Jami</th><th>Holat</th></tr></thead><tbody>${rows}</tbody></table>
		`);
		this.body.find(`[data-act="spravka"]`).on("click", () => this.spravka());
	}

	// Tekshiruvchilar uchun bosma "muvofiqlik spravkasi" (post-sovet an'anasi)
	spravka() {
		const sp = this.d.sanpin || {};
		const kunlar = sp.kunlar || [];
		const sana = frappe.datetime.str_to_user(frappe.datetime.get_today());
		const rows = (sp.sinflar || []).map((s) => `
			<tr><td>${this.esc(s.sinf)}</td>${kunlar.map((k) => `<td style="text-align:right">${s.kunlik[k] || 0}</td>`).join("")}
			<td style="text-align:right"><b>${s.jami}</b></td>
			<td>${(s.ogohlar || []).map((o) => this.esc(o)).join("<br>") || "—"}</td></tr>`).join("");
		const w = window.open("", "_blank");
		w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Spravka — dars jadvali</title>
			<style>body{font-family:Arial,sans-serif;font-size:12px;margin:28px}
			h2{margin:0 0 2px}.sub{color:#555;margin-bottom:14px}
			table{border-collapse:collapse;width:100%}td,th{border:1px solid #999;padding:4px 7px}
			th{background:#eee}.note{margin-top:12px;font-size:11px;color:#444}</style></head><body>
			<h2>Dars jadvalining kunlik yuklama bo'yicha tahlili (spravka)</h2>
			<div class="sub">Versiya: ${this.esc(this.d.versiya)} · Sana: ${this.esc(sana)} ·
				Sivkov/SanPiN qiyinchilik shkalasi bo'yicha</div>
			<table><thead><tr><th>Sinf</th>${kunlar.map((k) => `<th>${k}</th>`).join("")}
				<th>Jami</th><th>Ogohlantirishlar</th></tr></thead><tbody>${rows}</tbody></table>
			<div class="note">Me'yor: haftalik yuklama cho'qqisi seshanba–chorshanbaga tushishi, dushanba va juma
				yengilroq bo'lishi, ikki eng og'ir fan ketma-ket kelmasligi tavsiya etiladi (Sivkov shkalasi, SanPiN).
				Ogohlantirish — qat'iy buzilish emas, zavuch e'tiboriga havola.</div>
			<div class="note" style="margin-top:24px">Tuzdi (zavuch): ______________________ &nbsp;&nbsp; Imzo: ________</div>
			</body></html>`);
		w.document.close();
		w.print();
	}
}
