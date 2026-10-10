// Copyright (c) 2026, Target Zenit — "Mening jadvalim" (o'qituvchi)
// Bugungi darslar (davomat olish tugmasi bilan) + haftalik jadval.
frappe.pages["mening-jadvalim"].on_page_load = function (wrapper) {
	new TZMeningJadvalim(wrapper);
};

const MJ_M = "target_zenit.target_zenit.page.mening_jadvalim.mening_jadvalim";

class TZMeningJadvalim {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Mening jadvalim"), single_column: true });
		this.oqituvchi = null;
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }
	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval tz-mening"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${MJ_M}.get_data`,
			args: { oqituvchi: this.oqituvchi },
			callback: (r) => { this.data = r.message || {}; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`),
		});
	}

	render() {
		const d = this.data;
		if (!d.oqituvchi) {
			this.body.html(`<div class="loading">Sizning hisobingizga o'qituvchi (Instructor) yozuvi bog'lanmagan.<br>
				Iltimos, administratorga murojaat qiling.</div>`);
			return;
		}
		const bugungi = (d.darslar || []).filter((x) => x.kun === d.bugun_kuni);
		const kunlar = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"];

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>${this.esc(d.oqituvchi_nomi || "Mening jadvalim")}</h1>
					<div class="sub">${this.esc(d.versiya || "")} · haftalik ${d.haftalik_soat || 0} dars · bugun ${this.esc(d.bugun_kuni)}</div>
				</div>
				<div class="spacer"></div>
				${d.menejer ? `<select class="foqituvchi">
					<option value="">— o'qituvchini tanlang —</option>
					${(d.oqituvchilar || []).map((o) => `<option value="${this.esc(o.name)}" ${o.name === d.oqituvchi ? "selected" : ""}>${this.esc(o.instructor_name)}</option>`).join("")}
				</select>` : ""}
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="card bugun">
				<div class="box-t">Bugungi darslar — ${this.esc(d.bugun_kuni)}</div>
				<div class="hint mini">Darsni belgilash uchun ustiga bosing</div>
				${bugungi.length ? bugungi.map((x) => `
					<div class="bugun-row clickable" data-jy="${this.esc(x.name)}" data-sana="${this.esc(x.sana)}" style="--h:${this.rang(x.fan)}">
						<div class="vaqt"><b>${x.dars_raqami}</b><span>${this.esc(x.boshlanish)}–${this.esc(x.tugash)}</span></div>
						<div class="info">
							<div class="fan">${this.esc(x.fan)}</div>
							<div class="guruh">${this.esc(x.guruh_nomi || x.guruh)}${x.sinflar ? ` · ${this.esc(x.sinflar)}` : ""}</div>
							<div class="reja">${this.rejaInfo(x)}</div>
						</div>
						<div class="acts">
							<button class="btn-belgila" data-jy="${this.esc(x.name)}" data-sana="${this.esc(x.sana)}">${x.bugun ? "✏️ O'zgartirish" : "📝 Darsni belgilash"}</button>
						</div>
						<div class="chev">›</div>
					</div>`).join("")
					: `<div class="empty">Bugun dars yo'q</div>`}
			</div>

			<div class="hafta">
				${kunlar.map((k) => {
					const list = (d.darslar || []).filter((x) => x.kun === k);
					return `<div class="card kun-card ${k === d.bugun_kuni ? "bugun-card" : ""}">
						<div class="box-t">${k} <span class="mini">${list.length} dars</span></div>
						${list.map((x) => `<div class="w-row clickable" data-jy="${this.esc(x.name)}" data-sana="${this.esc(x.sana)}" style="--h:${this.rang(x.fan)}">
							<span class="no">${x.dars_raqami}</span>
							<span class="t">${this.esc(x.boshlanish)}</span>
							<span class="f">${this.esc(x.fan)}</span>
							<span class="g">${this.esc(x.sinflar || x.guruh_nomi || "")}</span>
							${x.bugun ? `<span class="w-ok" title="O'tildi: ${this.esc((x.bugun || {}).mavzu || "")}">✓</span>` : ""}
						</div>`).join("") || `<div class="empty mini">—</div>`}
					</div>`;
				}).join("")}
			</div>
		`);

		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".foqituvchi").on("change", (e) => { this.oqituvchi = e.target.value; this.load(); });
		// Dars qatoriga bosilganda — to'liq ma'lumot dialogi
		this.body.find(".bugun-row.clickable, .w-row.clickable").on("click", (e) => {
			const r = $(e.currentTarget);
			this.darsDetal(r.data("jy"), r.data("sana"));
		});
		this.body.find(".btn-belgila").on("click", (e) => {
			e.stopPropagation();
			const b = $(e.currentTarget);
			this.darsDetal(b.data("jy"), b.data("sana"));
		});
	}

	// O'quv reja holati matni (keyingi mavzu / o'tilgan / reja yo'q)
	rejaInfo(x) {
		if (x.bugun) {
			return `<span class="r-ok">✓ O'tildi: ${this.esc(x.bugun.mavzu || "—")}</span>`;
		}
		if (!x.oquv_reja) return `<span class="r-mut">O'quv reja yo'q</span>`;
		const k = x.keyingi;
		const prog = `<span class="r-prog">${x.otildi || 0}/${x.jami || 0}</span>`;
		if (!k) return `<span class="r-ok">✓ Reja tugadi</span> ${prog}`;
		return `<span class="r-next">Keyingi: <b>${this.esc(k.mavzu || "(mavzu bo'sh)")}</b></span> ${prog}`;
	}

	// Darsni bosganda — to'liq ma'lumot dialogini ochadi
	darsDetal(jy, sana) {
		frappe.call({
			method: `${MJ_M}.dars_detali`,
			args: { jadval_yozuvi: jy, sana: sana },
			freeze: true,
			freeze_message: "Yuklanmoqda…",
			callback: (r) => { if (r.message) this.ochDialog(r.message); },
		});
	}

	ochDialog(d) {
		const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
		const dars = d.dars || {};
		const bor = !!d.oquv_reja;
		const kunNomi = esc(dars.kun || "");
		// Dars sarlavha ma'lumoti
		const bosh = `
			<div class="dd-head">
				<div class="dd-fan">${esc(dars.fan)} <span class="dd-guruh">${esc(dars.guruh_nomi)}</span></div>
				<div class="dd-meta">
					<span>📅 ${kunNomi}, ${esc(this.dmy(dars.sana))}</span>
					<span>🕐 ${esc(dars.boshlanish)}–${esc(dars.tugash)} (${dars.dars_raqami}-dars)</span>
					${dars.xona ? `<span>🚪 ${esc(dars.xona)}</span>` : ""}
					${dars.oqituvchi_nomi ? `<span>👤 ${esc(dars.oqituvchi_nomi)}</span>` : ""}
				</div>
			</div>`;
		// O'quv reja + mavzular ro'yxati
		let reja = "";
		if (!bor) {
			reja = `<div class="dd-noreja">⚠️ Bu dars uchun o'quv reja biriktirilmagan.<br>
				<a href="/app/oquv-reja/new" target="_blank">+ O'quv reja yaratish</a></div>`;
		} else {
			const pct = d.jami ? Math.round((d.otildi / d.jami) * 100) : 0;
			const rows = (d.mavzular || []).map((m) => `
				<div class="dd-m ${m.otildi ? "done" : ""} ${m.name === d.keyingi ? "next" : ""}">
					<span class="n">${m.tartib || ""}</span>
					<span class="t">${esc(m.mavzu || "(mavzu bo'sh)")}${m.bolim ? ` <i>${esc(m.bolim)}</i>` : ""}</span>
					<span class="s">${m.otildi ? "✓" : (m.name === d.keyingi ? "keyingi" : "")}</span>
				</div>`).join("");
			reja = `
				<div class="dd-reja-t">O'quv reja: <b>${esc(d.oquv_reja_nomi)}</b>
					<span class="dd-prog">${d.otildi}/${d.jami} (${pct}%)</span></div>
				<div class="dd-bar"><div style="width:${pct}%"></div></div>
				<div class="dd-mlist">${rows || "<div class='mini'>Mavzular kiritilmagan</div>"}</div>`;
		}

		const dlg = new frappe.ui.Dialog({
			title: __("Dars"),
			size: "large",
			fields: [
				{ fieldtype: "HTML", fieldname: "info", options: `<div class="dd-wrap">${bosh}${reja}</div>` },
				...(bor ? [
					{ fieldtype: "Section Break", label: __("Belgilash") },
					{
						fieldtype: "Select", fieldname: "mavzu", label: __("Qaysi mavzu o'tildi?"),
						options: (d.mavzular || []).map((m) => ({
							label: `${m.tartib || ""}. ${m.mavzu || "(bo'sh)"}${m.otildi ? " ✓" : ""}`,
							value: m.name,
						})),
						default: (d.bugun && d.bugun.reja_qatori) || d.keyingi || "",
					},
					{
						fieldtype: "Select", fieldname: "holat", label: __("Holat"),
						options: ["O'tildi", "Qisman", "O'tilmadi"].join("\n"),
						default: (d.bugun && d.bugun.holat) || "O'tildi",
					},
					{ fieldtype: "Small Text", fieldname: "izoh", label: __("Izoh (ixtiyoriy)"), default: (d.bugun && d.bugun.izoh) || "" },
				] : []),
			],
			primary_action_label: bor ? __("Saqlash") : __("Davomat olish"),
			primary_action: (v) => {
				if (!bor) { dlg.hide(); this.davomat(dars.jadval_yozuvi); return; }
				frappe.call({
					method: `${MJ_M}.dars_otdim`,
					args: {
						jadval_yozuvi: dars.jadval_yozuvi, sana: dars.sana,
						reja_qatori: v.mavzu || undefined, holat: v.holat, izoh: v.izoh || undefined,
					},
					freeze: true, freeze_message: "Saqlanmoqda…",
					callback: (r) => {
						if (r.message) {
							frappe.show_alert({ message: __("Saqlandi"), indicator: "green" });
							dlg.hide();
							this.load();
						}
					},
				});
			},
		});
		if (bor) {
			dlg.set_secondary_action_label(__("Davomat olish"));
			dlg.set_secondary_action(() => { dlg.hide(); this.davomat(dars.jadval_yozuvi); });
		}
		dlg.show();
	}

	davomat(jy) {
		frappe.call({
			method: `${MJ_M}.davomat_ochish`,
			args: { jadval_yozuvi: jy },
			freeze: true,
			freeze_message: "Dars ochilmoqda…",
			callback: (r) => {
				if (r.message && r.message.course_schedule) {
					frappe.set_route("Form", "Course Schedule", r.message.course_schedule);
				}
			},
		});
	}
}
