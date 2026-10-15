// Copyright (c) 2026, Target Zenit — "Mening jadvalim" (o'qituvchi)
// Bugungi darslar (davomat olish tugmasi bilan) + haftalik jadval + hafta navigatsiyasi.
// Dars audiosi bu sahifada EMAS — «dars sessiyasi» kokpitidagi mavzu kartasida.
frappe.pages["mening-jadvalim"].on_page_load = function (wrapper) {
	new TZMeningJadvalim(wrapper);
};

const MJ_M = "target_zenit.target_zenit.page.mening_jadvalim.mening_jadvalim";

class TZMeningJadvalim {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Mening jadvalim"), single_column: true });
		this.oqituvchi = null;
		this.hafta = 0;          // 0 = shu hafta, -1 = o'tgan, +1 = keyingi
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }
	kunQisqa(k) { return ({ Dushanba: "Du", Seshanba: "Se", Chorshanba: "Ch", Payshanba: "Pa", Juma: "Ju", Shanba: "Sh" })[k] || k; }
	ozgInfo(x) {
		const o = x.ozgarish; if (!o) return "";
		if (o.tur === "Bekor") return `<div class="ozg bekor">⛔ Bu dars bugun bekor qilindi${o.sabab ? ` — ${this.esc(o.sabab)}` : ""}</div>`;
		if (o.tur === "O'rinbosar") return `<div class="ozg cover">🔄 O'rinbosar: <b>${this.esc(o.yangi_oqituvchi_nomi || "")}</b> (siz bu darsга kirmaysiz)</div>`;
		return "";
	}
	// Hafta yorlig'i: «12–16 okt» (shu hafta bo'lsa — «Shu hafta»)
	haftaLabel(d) {
		const oy = ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"];
		const b = String(d.hafta_boshi || "").split("-"), o = String(d.hafta_oxiri || "").split("-");
		if (b.length !== 3) return "Hafta";
		const diapazon = `${+b[2]}–${+o[2]} ${oy[+b[1] - 1] || ""}`;
		return d.shu_hafta ? `Shu hafta · ${diapazon}` : diapazon;
	}

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
			args: { oqituvchi: this.oqituvchi, hafta: this.hafta },
			callback: (r) => { this.data = r.message || {}; this.render(); this.loadPanel(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`),
		});
	}

	// «Qoldirilgan ishlarim» + «Diqqat talab qiladi» — alohida (sahifa tez chiqishi uchun)
	loadPanel() {
		frappe.call({
			method: `${MJ_M}.kun_paneli`,
			args: { oqituvchi: this.oqituvchi },
			callback: (r) => { this.panel = r.message || {}; this.renderPanel(); },
		});
	}

	trendBelgi(t) { return t > 0 ? `<span class="tr up">▲</span>` : (t < 0 ? `<span class="tr dn">▼</span>` : ""); }

	// «Qiladigan ishlarim», kun qaydnomasi va «Diqqat talab qiladi» — endi
	// «Kunlik reja» (/app/kunlik-jadval) sahifasida. Bu sahifa faqat JADVAL.
	renderPanel() {
		const p = this.panel || {};
		const qJami = p.qoldirilgan_jami || 0;
		const dJami = p.diqqat_jami || 0;
		const q = [];
		if (qJami) q.push(`⚠️ ${qJami} ish qoldi`);
		if (dJami) q.push(`🚩 ${dJami} o'quvchi diqqat talab qiladi`);
		this.body.find(".sub-q").html(q.length
			? ` · <a class="q-link" href="#">${q.join(" · ")} — kunlik rejada</a>` : "");
		this.body.find(".q-link").on("click", (e) => { e.preventDefault(); frappe.set_route("kunlik-jadval"); });
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
					<div class="sub">${this.esc(d.versiya || "")} · haftalik ${d.haftalik_soat || 0} dars · bugun ${this.esc(d.bugun_kuni)}<span class="sub-q"></span></div>
				</div>
				<div class="spacer"></div>
				${d.menejer ? `<select class="foqituvchi">
					<option value="">— o'qituvchini tanlang —</option>
					${(d.oqituvchilar || []).map((o) => `<option value="${this.esc(o.name)}" ${o.name === d.oqituvchi ? "selected" : ""}>${this.esc(o.instructor_name)}</option>`).join("")}
				</select>` : ""}
				<button class="refresh" data-act="mavzu" title="Butun chorak mavzularini bir martada biriktirish">📘 Mavzular</button>
				<span class="hafta-nav">
					<button class="refresh" data-act="h-prev" title="o'tgan hafta">‹</button>
					<button class="refresh h-lbl" data-act="h-bugun" title="shu haftaga qaytish">${this.haftaLabel(d)}</button>
					<button class="refresh" data-act="h-next" title="keyingi hafta">›</button>
				</span>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="card kunlik-cta">
				<div class="kc-l">
					<b>📌 Bugun — ${this.esc(d.bugun_kuni)}:</b> ${bugungi.length} dars
					<span class="mini">kun qaydnomasi (nima o'tildi, nechta baho, uy vazifa) va qilinmagan ishlar «Kunlik reja»da</span>
				</div>
				<button class="kc-go" data-act="kunlik">Kunlik rejani ochish →</button>
			</div>

			${(d.cover_vazifalar || []).filter((c) => c.sana !== d.bugun_sana).length ? `
			<div class="card cover-card">
				<div class="box-t">🔄 Zavuch yuklagan qo'shimcha darslar (shu hafta, boshqa kunlar)</div>
				${d.cover_vazifalar.filter((c) => c.sana !== d.bugun_sana).map((c) => `
					<div class="cv-row">
						<div class="cv-when"><b>${this.esc(this.kunQisqa(c.kun))}</b> ${this.esc(this.dmy(c.sana))}<span>${this.esc(c.boshlanish)}–${this.esc(c.tugash)}</span></div>
						<div class="cv-info"><b>${this.esc(c.fan)}</b> · ${this.esc(c.guruh_nomi)}<div class="mini">asl o'qituvchi: ${this.esc(c.asl_oqituvchi_nomi || "—")}${c.sabab ? ` · ${this.esc(c.sabab)}` : ""}</div></div>
					</div>`).join("")}
			</div>` : ""}

			<div class="hafta">
				${kunlar.map((k) => {
					const list = (d.darslar || []).filter((x) => x.kun === k);
					return `<div class="card kun-card ${(k === d.bugun_kuni && d.shu_hafta) ? "bugun-card" : ""}">
						<div class="box-t">${k} <span class="mini">${list.length} dars</span></div>
						${list.map((x) => `<div class="w-row clickable ${x.ozgarish ? (x.ozgarish.tur === "Bekor" ? "w-bekor" : "w-cover") : ""}" data-jy="${this.esc(x.name)}" data-sana="${this.esc(x.sana)}" style="--h:${this.rang(x.fan)}" ${x.ozgarish ? `title="${x.ozgarish.tur === "Bekor" ? "Bekor qilindi" : "O'rinbosar: " + this.esc(x.ozgarish.yangi_oqituvchi_nomi || "")}"` : ""}>
							<span class="no">${x.dars_raqami}</span>
							<span class="t">${this.esc(x.boshlanish)}${x.tugash ? "–" + this.esc(x.tugash) : ""}</span>
							<span class="f">${this.esc(x.fan)}</span>
							<span class="g">${this.esc(x.sinflar || x.guruh_nomi || "")}</span>
							${x.ozgarish ? `<span class="w-chg">${x.ozgarish.tur === "Bekor" ? "✕" : "↷"}</span>` : (x.bugun ? `<span class="w-ok" title="O'tildi: ${this.esc((x.bugun || {}).mavzu || "")}">✓</span>` : "")}
						</div>`).join("") || `<div class="empty mini">—</div>`}
					</div>`;
				}).join("")}
			</div>
		`);

		if (this.panel) this.renderPanel();
		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(`[data-act="h-prev"]`).on("click", () => { this.hafta -= 1; this.load(); });
		this.body.find(`[data-act="h-next"]`).on("click", () => { this.hafta += 1; this.load(); });
		this.body.find(`[data-act="h-bugun"]`).on("click", () => { if (this.hafta) { this.hafta = 0; this.load(); } });
		this.body.find(`[data-act="kunlik"]`).on("click", () => frappe.set_route("kunlik-jadval"));
		this.body.find(`[data-act="mavzu"]`).on("click", () => {
			if (!window.tz_mavzu_dialog) { frappe.show_alert({ message: "Sahifani yangilang (Ctrl+Shift+R)", indicator: "orange" }); return; }
			window.tz_mavzu_dialog({ onsave: () => this.load() });
		});
		this.body.find(".foqituvchi").on("change", (e) => { this.oqituvchi = e.target.value; this.load(); });
		// Darsga (bugungi karta yoki haftalik yacheyka) bosilsa — dars sessiyasi kokpiti
		this.body.find(".today-card.clickable, .w-row.clickable").on("click", (e) => {
			const r = $(e.currentTarget);
			frappe.set_route("dars-sessiya", r.data("jy"), r.data("sana"));
		});
	}

	// Baho/Davomat jurnali — dars o'quvchilari ro'yxati
	jurnalDialog(jy, sana) {
		const self = this;
		frappe.call({
			method: `${MJ_M}.jurnal_oquvchilari`,
			args: { jadval_yozuvi: jy, sana: sana },
			freeze: true, freeze_message: "Yuklanmoqda…",
			callback: (r) => { if (r.message) self.ochJurnal(r.message); },
		});
	}

	ochJurnal(d) {
		const self = this;
		const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
		const DAV = ["Keldi", "Kelmadi", "Kasal", "Qatnashmadi"];
		if (!(d.oquvchilar || []).length) {
			frappe.msgprint(__("Bu guruhda o'quvchilar ro'yxati yo'q (hali kiritilmagan)."));
			return;
		}
		const rows = d.oquvchilar.map((o, i) => `
			<tr data-student="${esc(o.student)}">
				<td class="r">${o.roll || i + 1}</td>
				<td>${esc(o.student_name)}</td>
				<td><select class="j-dav">${DAV.map((v) => `<option value="${v}" ${o.davomat === v ? "selected" : ""}>${v}</option>`).join("")}</select></td>
				<td><input type="number" class="j-baho" min="1" max="100" value="${o.baho != null ? o.baho : ""}" ${o.davomat !== "Keldi" ? "disabled" : ""}></td>
			</tr>`).join("");
		const html = `
			<div class="jur-head">${esc(d.fan)} · ${esc(d.guruh_nomi)} · ${esc(d.kun)}, ${d.dars_raqami}-dars · ${esc(self.dmy(d.sana))} ${d.chorak ? `· <span class="ch">${esc(d.chorak)}</span>` : ""}</div>
			<div class="jur-hint">«Keldi» belgilash shart emas — faqat <b>kelmaganlar</b>ni belgilang va kerakli <b>baho</b>larni qo'ying.</div>
			<div class="jur-wrap"><table class="jur-tbl"><thead><tr><th class="r">№</th><th>O'quvchi</th><th>Davomat</th><th>Baho</th></tr></thead><tbody>${rows}</tbody></table></div>`;
		const dlg = new frappe.ui.Dialog({
			title: __("Baho / Davomat jurnali"), size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "j", options: html }],
			primary_action_label: __("Saqlash"),
			primary_action: () => {
				const qatorlar = [];
				dlg.$wrapper.find("tbody tr").each(function () {
					const $t = $(this);
					const dav = $t.find(".j-dav").val();
					const bval = $t.find(".j-baho").val();
					qatorlar.push({ student: $t.data("student"), davomat: dav, baho: bval ? Number(bval) : null });
				});
				frappe.call({
					method: `${MJ_M}.jurnal_saqla`,
					args: { jadval_yozuvi: d.jadval_yozuvi, sana: d.sana, qatorlar: JSON.stringify(qatorlar) },
					freeze: true, freeze_message: "Saqlanmoqda…",
					callback: (r) => { if (r.message) { frappe.show_alert({ message: __("Saqlandi: ") + r.message.saqlandi, indicator: "green" }); dlg.hide(); } },
				});
			},
		});
		// Davomat != Keldi bo'lsa baho o'chiriladi
		dlg.$wrapper.on("change", ".j-dav", function () {
			const $b = $(this).closest("tr").find(".j-baho");
			if ($(this).val() === "Keldi") $b.prop("disabled", false);
			else { $b.prop("disabled", true).val(""); }
		});
		dlg.show();
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
		dlg.set_secondary_action_label(__("📋 Baho / Davomat"));
		dlg.set_secondary_action(() => { dlg.hide(); this.jurnalDialog(dars.jadval_yozuvi, dars.sana); });
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
