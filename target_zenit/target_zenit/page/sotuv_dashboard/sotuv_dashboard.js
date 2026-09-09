// Copyright (c) 2026, Target Zenit — Sotuv paneli
// Sotuv menejerlari uchun: o'quvchilar, guruhlar, shartnoma holati, ota-onalar.
// Moliyaviy tranzaksiyalar ko'rsatilmaydi.
frappe.pages["sotuv-dashboard"].on_page_load = function (wrapper) {
	new TZSotuvPanel(wrapper);
};

class TZSotuvPanel {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Sotuv paneli"), single_column: true });
		this.data = null;
		this.view = "groups"; // groups | list
		this.q = "";          // qidiruv matni
		this.fGroup = "";     // guruh filtri: "" hammasi | "__none" guruhsiz | guruh nomi
		this.fContract = "";  // "" hammasi | "yes" | "no"
		this.openGroups = new Set(); // ochilgan guruh kartalari
		this.make_skeleton();
		this.load();
	}

	// ================= helpers =================
	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }
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
	// o'quvchining ko'rsatiladigan telefoni: to'lovchi > ota-ona > o'quvchining o'zi
	phoneOf(s) {
		if (s.custom_payer_phone) return s.custom_payer_phone;
		const g = (s.guardians || []).find((x) => x.mobile_number);
		if (g) return g.mobile_number;
		return s.student_mobile_number || "";
	}
	contractBadge(s) {
		if (s.custom_shartnoma_qilindi) {
			const t = s.custom_shartnoma_turi ? ` · ${this.esc(s.custom_shartnoma_turi)}` : "";
			return `<span class="pill ok">Shartnomali${t}</span>`;
		}
		return `<span class="pill no">Shartnomasiz</span>`;
	}
	// o'quvchi ismi -> Student formasi (details) havolasi
	nameLink(s) {
		return `<a class="slink" href="/app/student/${encodeURIComponent(s.name)}" onclick="event.stopPropagation()">${this.esc(s.student_name)}</a>`;
	}

	// ================= skeleton / load =================
	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-sot"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: "target_zenit.target_zenit.page.sotuv_dashboard.sotuv_dashboard.get_data",
			callback: (r) => {
				this.data = r.message || { students: [], groups: [] };
				this.render();
			},
			error: () => {
				this.body.html(`<div class="loading">Ma'lumot yuklashda xatolik. Sahifani yangilab ko'ring.</div>`);
			},
		});
	}

	// ================= hisob-kitoblar =================
	stats(list) {
		const st = { total: list.length, active: 0, contracted: 0, oylik: 0, yillik: 0 };
		for (const s of list) {
			if (s.enabled) st.active++;
			if (s.custom_shartnoma_qilindi) {
				st.contracted++;
				if (s.custom_shartnoma_turi === "Oylik") st.oylik++;
				if (s.custom_shartnoma_turi === "Yillik") st.yillik++;
			}
		}
		return st;
	}

	filtered() {
		const q = this.q.trim().toLowerCase();
		return (this.data.students || []).filter((s) => {
			if (this.fGroup === "__none" && s.custom_sinf_guruh) return false;
			if (this.fGroup && this.fGroup !== "__none" && s.custom_sinf_guruh !== this.fGroup) return false;
			if (this.fContract === "yes" && !s.custom_shartnoma_qilindi) return false;
			if (this.fContract === "no" && s.custom_shartnoma_qilindi) return false;
			if (q) {
				const hay = [
					s.student_name, s.custom_sinf_guruh, s.custom_contract_no,
					s.custom_payer_name, s.custom_payer_phone, s.student_mobile_number,
					...(s.guardians || []).flatMap((g) => [g.guardian_name, g.mobile_number]),
				].join(" ").toLowerCase();
				if (!hay.includes(q)) return false;
			}
			return true;
		});
	}

	// guruh nomi -> o'quvchilar (filtrlangan ro'yxatdan)
	byGroup(list) {
		const map = new Map();
		for (const g of this.data.groups || []) map.set(g.name, []);
		const none = [];
		for (const s of list) {
			const g = s.custom_sinf_guruh;
			if (g) {
				if (!map.has(g)) map.set(g, []);
				map.get(g).push(s);
			} else none.push(s);
		}
		return { map, none };
	}

	// ================= render =================
	render() {
		const all = this.data.students || [];
		const st = this.stats(all);
		const noGroup = all.filter((s) => !s.custom_sinf_guruh).length;
		const pct = st.total ? Math.round((st.contracted / st.total) * 100) : 0;

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Sotuv paneli</h1>
					<div class="sub">O'quvchilar, guruhlar va shartnomalar · ${this.esc(frappe.datetime.str_to_user(frappe.datetime.get_today()))}</div>
				</div>
				<div class="spacer"></div>
				<button class="refresh" data-act="csv">⬇ CSV yuklab olish</button>
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="grid cols-5 mb kpis">
				<div class="card kpi"><div class="lab"><span class="pin"></span>Jami o'quvchilar</div>
					<div class="val">${this.fmt(st.total)}</div>
					<div class="sub">${this.fmt(st.active)} faol · ${this.fmt(st.total - st.active)} nofaol</div></div>
				<div class="card kpi"><div class="lab"><span class="pin g"></span>Shartnoma qilingan</div>
					<div class="val">${this.fmt(st.contracted)} <span class="cur">/ ${pct}%</span></div>
					<div class="sub">Oylik: ${this.fmt(st.oylik)} · Yillik: ${this.fmt(st.yillik)}</div></div>
				<div class="card kpi"><div class="lab"><span class="pin r"></span>Shartnomasiz</div>
					<div class="val">${this.fmt(st.total - st.contracted)}</div>
					<div class="sub">Sotuv uchun ishlanadigan baza</div></div>
				<div class="card kpi"><div class="lab"><span class="pin b"></span>Guruhlar</div>
					<div class="val">${this.fmt((this.data.groups || []).length)}</div>
					<div class="sub">Faol guruhlar soni</div></div>
				<div class="card kpi"><div class="lab"><span class="pin y"></span>Guruhga biriktirilmagan</div>
					<div class="val">${this.fmt(noGroup)}</div>
					<div class="sub">Guruh tanlanmagan o'quvchilar</div></div>
			</div>

			<div class="controls mb">
				<input type="text" class="q" placeholder="Qidiruv: ism, telefon, shartnoma №, ota-ona…" value="${this.esc(this.q)}">
				<select class="fgroup">
					<option value="">Barcha guruhlar</option>
					<option value="__none" ${this.fGroup === "__none" ? "selected" : ""}>Guruhsiz</option>
					${(this.data.groups || []).map((g) =>
						`<option value="${this.esc(g.name)}" ${this.fGroup === g.name ? "selected" : ""}>${this.esc(g.student_group_name || g.name)}</option>`).join("")}
				</select>
				<div class="chips">
					<button class="chip ${this.fContract === "" ? "on" : ""}" data-c="">Hammasi</button>
					<button class="chip ${this.fContract === "yes" ? "on" : ""}" data-c="yes">Shartnomali</button>
					<button class="chip ${this.fContract === "no" ? "on" : ""}" data-c="no">Shartnomasiz</button>
				</div>
				<div class="spacer"></div>
				<div class="chips views">
					<button class="chip ${this.view === "groups" ? "on" : ""}" data-v="groups">Guruhlar bo'yicha</button>
					<button class="chip ${this.view === "list" ? "on" : ""}" data-v="list">Ro'yxat</button>
				</div>
			</div>

			<div class="content"></div>
		`);

		this.renderContent();
		this.bind();
	}

	renderContent() {
		const list = this.filtered();
		const box = this.body.find(".content");
		if (this.view === "groups") box.html(this.groupsHtml(list));
		else box.html(this.listHtml(list));
		// natija soni
		this.body.find(".controls .q").attr("title", `${list.length} ta o'quvchi topildi`);
	}

	groupsHtml(list) {
		const { map, none } = this.byGroup(list);
		const blocks = [];
		const entries = [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], "uz", { numeric: true }));
		if (none.length) entries.push(["__none", none]);

		for (const [gname, studs] of entries) {
			if (!studs.length && (this.q || this.fContract || this.fGroup)) continue; // filtr paytida bo'sh guruhni yashirish
			const st = this.stats(studs);
			const open = this.openGroups.has(gname);
			const label = gname === "__none" ? "Guruhsiz o'quvchilar" : gname;
			blocks.push(`
				<div class="card gcard ${open ? "open" : ""}" data-g="${this.esc(gname)}">
					<div class="ghead" data-toggle="1">
						<span class="caret">${open ? "▾" : "▸"}</span>
						<span class="gname">${this.esc(label)}</span>
						<span class="gmeta">${st.total} o'quvchi</span>
						<span class="gmeta ok">${st.contracted} shartnomali</span>
						${st.oylik || st.yillik ? `<span class="gmeta">Oylik: ${st.oylik} · Yillik: ${st.yillik}</span>` : ""}
						<span class="spacer"></span>
						<span class="gbar"><span style="width:${st.total ? Math.round(st.contracted / st.total * 100) : 0}%"></span></span>
					</div>
					${open ? `<div class="gbody">${this.tableHtml(studs, false)}</div>` : ""}
				</div>`);
		}
		if (!blocks.length) return `<div class="card empty">Hech narsa topilmadi.</div>`;
		return blocks.join("");
	}

	listHtml(list) {
		if (!list.length) return `<div class="card empty">Hech narsa topilmadi.</div>`;
		return `<div class="card tcard">${this.tableHtml(list, true)}</div>`;
	}

	tableHtml(list, withGroup) {
		const rows = list.map((s, i) => {
			const g0 = (s.guardians || [])[0];
			const parent = g0
				? `${this.esc(g0.guardian_name)}${g0.relation ? ` <span class="mut">(${this.esc(g0.relation)})</span>` : ""}${(s.guardians.length > 1) ? ` <span class="mut">+${s.guardians.length - 1}</span>` : ""}`
				: `<span class="mut">—</span>`;
			return `
			<tr data-s="${this.esc(s.name)}">
				<td class="num mut">${i + 1}</td>
				<td class="strong">${this.nameLink(s)}${s.enabled ? "" : ` <span class="pill off">nofaol</span>`}</td>
				${withGroup ? `<td>${this.esc(s.custom_sinf_guruh || "—")}</td>` : ""}
				<td>${this.contractBadge(s)}</td>
				<td>${s.custom_contract_no ? `№ ${this.esc(s.custom_contract_no)}` : `<span class="mut">—</span>`}${s.custom_contract_date ? ` <span class="mut">· ${this.dmy(s.custom_contract_date)}</span>` : ""}</td>
				<td>${s.custom_tariff ? this.esc(s.custom_tariff) : `<span class="mut">—</span>`}</td>
				<td>${parent}</td>
				<td class="num">${this.tel(this.phoneOf(s)) || `<span class="mut">—</span>`}</td>
			</tr>`;
		}).join("");
		return `
		<div class="twrap"><table>
			<thead><tr>
				<th>#</th><th>F.I.Sh.</th>${withGroup ? "<th>Guruh</th>" : ""}
				<th>Shartnoma</th><th>Shartnoma № / sana</th><th>Tarif</th><th>Ota-onasi</th><th>Telefon</th>
			</tr></thead>
			<tbody>${rows}</tbody>
		</table></div>`;
	}

	// ================= o'quvchi kartasi (modal) =================
	showStudent(name) {
		const s = (this.data.students || []).find((x) => x.name === name);
		if (!s) return;
		const row = (l, v) => `<div class="drow"><div class="dl">${l}</div><div class="dv">${v || `<span class="mut">—</span>`}</div></div>`;
		const money = (v) => (v ? `${this.fmt(v)} so'm` : "");

		const guardians = (s.guardians || []).length
			? `<table class="dtable"><thead><tr><th>Ism</th><th>Qarindoshlik</th><th>Telefon</th><th>Email</th></tr></thead><tbody>
				${s.guardians.map((g) => `<tr>
					<td>${this.esc(g.guardian_name)}</td><td>${this.esc(g.relation) || "—"}</td>
					<td>${this.tel(g.mobile_number) || "—"}</td><td>${this.esc(g.email_address) || "—"}</td>
				</tr>`).join("")}
			</tbody></table>`
			: `<div class="mut">Ota-ona ma'lumoti kiritilmagan</div>`;

		const d = new frappe.ui.Dialog({ title: s.student_name, size: "large" });
		$(d.body).html(`
			<div class="tz-sot tz-sot-dialog">
				<div class="dopen"><a href="/app/student/${encodeURIComponent(s.name)}">↗ Student kartochkasini ochish (details)</a></div>
				<div class="dsec"><h4>Asosiy ma'lumot</h4>
					${row("Holati", s.enabled ? `<span class="pill ok">Faol</span>` : `<span class="pill off">Nofaol</span>`)}
					${row("Guruh", this.esc(s.custom_sinf_guruh))}
					${row("Ta'lim tili", this.esc(s.custom_edu_language))}
					${row("Tug'ilgan sana", this.dmy(s.date_of_birth))}
					${row("Jinsi", this.esc(s.gender))}
					${row("Telefon (o'quvchi)", this.tel(s.student_mobile_number))}
					${row("Email", this.esc(s.student_email_id))}
					${row("Manzil", this.esc([s.address_line_1, s.city].filter(Boolean).join(", ")))}
					${row("Qabul sanasi", this.dmy(s.joining_date))}
				</div>
				<div class="dsec"><h4>Shartnoma</h4>
					${row("Shartnoma", this.contractBadge(s))}
					${row("Shartnoma №", this.esc(s.custom_contract_no))}
					${row("Shartnoma sanasi", this.dmy(s.custom_contract_date))}
					${row("Shartnoma fayli", s.custom_shartnoma_file ? `<a href="${this.esc(s.custom_shartnoma_file)}" target="_blank" rel="noopener">PDF ochish</a>` : "")}
					${row("Tarif", this.esc(s.custom_tariff))}
					${row("Tarif summasi", money(s.custom_tariff_amount))}
					${row("Chegirma", money(s.custom_discount_amount))}
					${row("Yakuniy summa", money(s.custom_final_amount))}
					${row("To'lovchi", this.esc(s.custom_payer_name))}
					${row("To'lovchi telefoni", this.tel(s.custom_payer_phone))}
				</div>
				<div class="dsec"><h4>Ota-onalar</h4>${guardians}</div>
				${s.custom_izoh ? `<div class="dsec"><h4>Izoh</h4><div>${this.esc(s.custom_izoh)}</div></div>` : ""}
			</div>
		`);
		$(d.body).find(".dopen a").on("click", () => d.hide()); // formaga o'tishda modalni yopish
		d.show();
	}

	// ================= CSV =================
	downloadCsv() {
		const list = this.filtered();
		const head = ["F.I.Sh.", "Guruh", "Holati", "Shartnoma", "Shartnoma turi", "Shartnoma №", "Shartnoma sanasi",
			"Tarif", "To'lovchi", "To'lovchi tel", "Ota-onasi", "Ota-ona tel", "O'quvchi tel", "Tug'ilgan sana", "Ta'lim tili"];
		const rows = list.map((s) => {
			const g0 = (s.guardians || [])[0] || {};
			return [
				s.student_name, s.custom_sinf_guruh || "", s.enabled ? "Faol" : "Nofaol",
				s.custom_shartnoma_qilindi ? "Ha" : "Yo'q", s.custom_shartnoma_turi || "",
				s.custom_contract_no || "", s.custom_contract_date || "",
				s.custom_tariff || "", s.custom_payer_name || "", s.custom_payer_phone || "",
				g0.guardian_name || "", g0.mobile_number || "",
				s.student_mobile_number || "", s.date_of_birth || "", s.custom_edu_language || "",
			];
		});
		const csv = [head, ...rows]
			.map((r) => r.map((c) => `"${String(c == null ? "" : c).replace(/"/g, '""')}"`).join(","))
			.join("\n");
		const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }); // BOM — Excel uchun
		const a = document.createElement("a");
		a.href = URL.createObjectURL(blob);
		a.download = `oquvchilar_${frappe.datetime.get_today()}.csv`;
		a.click();
		URL.revokeObjectURL(a.href);
	}

	// ================= events =================
	bind() {
		const self = this;
		this.body.off("click input change");

		this.body.on("click", "[data-act=reload]", () => { this.body.html(`<div class="loading">Yuklanmoqda…</div>`); this.load(); });
		this.body.on("click", "[data-act=csv]", () => this.downloadCsv());

		let t = null;
		this.body.on("input", ".controls .q", function () {
			clearTimeout(t);
			t = setTimeout(() => { self.q = this.value; self.renderContent(); }, 200);
		});
		this.body.on("change", ".controls .fgroup", function () { self.fGroup = this.value; self.renderContent(); });
		this.body.on("click", ".controls .chip[data-c]", function () { self.fContract = $(this).data("c"); self.render(); });
		this.body.on("click", ".controls .chip[data-v]", function () { self.view = $(this).data("v"); self.render(); });

		this.body.on("click", ".gcard .ghead", function () {
			const g = $(this).closest(".gcard").data("g");
			if (self.openGroups.has(g)) self.openGroups.delete(g); else self.openGroups.add(g);
			self.renderContent();
		});
		this.body.on("click", "tbody tr[data-s]", function () { self.showStudent($(this).data("s")); });
	}
}
