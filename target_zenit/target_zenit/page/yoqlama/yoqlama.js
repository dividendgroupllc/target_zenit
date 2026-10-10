// Copyright (c) 2026, Target Zenit — Yo'qlama (zavuch uchun)
// Kunlik yo'qlama: xodimlar x kunlar to'ri. PUL MA'LUMOTI YO'Q.
// Belgilangan kunlar ERPNext Attendance'ga yoziladi — oylik tabel shuni o'qiydi.
frappe.pages["yoqlama"].on_page_load = function (wrapper) {
	new TZYoqlama(wrapper);
};

const YQ_M = "target_zenit.yoqlama";

class TZYoqlama {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Yo'qlama"), single_column: true });
		const b = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		this.yil = b.getFullYear();
		this.oy = b.getMonth() + 1;
		this.faqatOqituvchi = 0;   // default: barcha xodimlar (kategoriya filtri bilan kesishmasin)
		this.fKategoriya = "";   // ish haqi kategoriyasi (tabel) filtri
		this.q = "";
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	oyNomi(o) {
		return ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
			"Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"][o] || o;
	}

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval tz-yoqlama"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${YQ_M}.get_data`,
			args: { yil: this.yil, oy: this.oy, faqat_oqituvchi: this.faqatOqituvchi,
				kategoriya: this.fKategoriya || null },
			callback: (r) => { this.data = r.message; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik. Sahifani yangilang.</div>`),
		});
	}

	oyOzgart(delta) {
		let o = this.oy + delta, y = this.yil;
		if (o < 1) { o = 12; y -= 1; }
		if (o > 12) { o = 1; y += 1; }
		this.oy = o; this.yil = y;
		this.load();
	}

	qatorlar() {
		const q = this.q.trim().toLowerCase();
		const rows = (this.data.qatorlar || []);
		return q ? rows.filter((r) => `${r.ism} ${r.lavozim}`.toLowerCase().includes(q)) : rows;
	}

	render() {
		const d = this.data;
		const kunlar = d.kunlar || [];
		const rows = this.qatorlar();

		const head = kunlar.map((k) =>
			`<th class="kun ${k.dam ? "dam" : ""}${k.sana === d.bugun ? " bugun" : ""}" title="${k.sana}">
				<span>${k.kun}</span><em>${k.hafta}</em></th>`).join("");

		const tana = rows.map((r) => {
			const kataklar = r.kunlik.map((c, i) => {
				const k = kunlar[i];
				const darsli = r.dars_kunlari.includes(new Date(k.sana).getDay() === 0 ? 6 : new Date(k.sana).getDay() - 1);
				let cls = "yc", matn = "";
				if (c.holat === "Present") { cls += " keldi"; matn = r.soatbay ? (c.koef || "") : "✓"; }
				else if (c.holat === "Absent") { cls += " yoq"; matn = "✕"; }
				else if (k.kelajak) { cls += " kelajak"; }
				else if (k.dam) { cls += " dam"; }
				else { cls += " bosh"; matn = "·"; }
				if (darsli && !k.dam) cls += " darsli";
				// Zavuch faqat BUGUNGI kunni belgilaydi; qolgan kunlar ko'rinadi, lekin tegilmaydi
				const bugunmi = k.sana === d.bugun;
				const bloklangan = k.kelajak || !d.oy_ochiq || (d.faqat_bugun && !bugunmi);
				if (bugunmi) cls += " bugun";
				return `<td><button class="${cls}" data-x="${this.esc(r.xodim)}" data-s="${k.sana}"
					${bloklangan ? "disabled" : ""}
					title="${k.sana}${darsli ? " · darsi bor" : ""}${d.faqat_bugun && !bugunmi ? " · faqat bugungi kun belgilanadi" : ""}">${matn}</button></td>`;
			}).join("");
			return `<tr>
				<th class="nom"><b>${this.esc(r.ism)}</b><span>${this.esc(r.kategoriya || r.lavozim || "")}${r.soatbay ? " · soatbay" : ""}</span></th>
				${kataklar}
				<td class="jami"><b>${r.keldi}</b></td></tr>`;
		}).join("");

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>Yo'qlama</h1>
					<div class="sub">Kunlik yo'qlama · belgilangan kunlar oylik tabelga avtomatik tushadi${d.faqat_bugun
						? ` · <b>faqat bugungi kun (${this.esc(frappe.datetime.str_to_user(d.bugun))}) belgilanadi</b>` : ""}</div>
				</div>
				<div class="spacer"></div>
				<div class="chips">
					<button class="chip" data-oy="-1">‹</button>
					<button class="chip on">${this.oyNomi(this.oy)} ${this.yil}</button>
					<button class="chip" data-oy="1">›</button>
				</div>
				${d.oy_ochiq ? "" : `<span class="pill-yopiq">Oy yopilgan — o'zgartirib bo'lmaydi</span>`}
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="controls mb">
				<input type="text" class="q" placeholder="Qidiruv: ism yoki lavozim…" value="${this.esc(this.q)}">
				<div class="chips">
					<button class="chip ${this.faqatOqituvchi ? "on" : ""}" data-f="1">Faqat o'qituvchilar</button>
					<button class="chip ${this.faqatOqituvchi ? "" : "on"}" data-f="0">Barcha xodimlar</button>
				</div>
				<select class="fkategoriya" title="Ish haqi kategoriyasi (tabel)">
					<option value="">Barcha kategoriyalar</option>
					${(d.kategoriyalar || []).map((k) =>
						`<option value="${this.esc(k)}" ${this.fKategoriya === k ? "selected" : ""}>${this.esc(k)}</option>`).join("")}
					<option value="__none" ${this.fKategoriya === "__none" ? "selected" : ""}>Belgilanmagan</option>
				</select>
				<div class="spacer"></div>
				<span class="legend"><i class="keldi"></i> keldi <i class="yoq"></i> kelmadi
					<i class="darsli"></i> darsi bor kun <i class="bosh"></i> belgilanmagan</span>
			</div>

			<div class="card scroll-x">
				<table class="ytbl">
					<thead><tr><th class="nom">Xodim (${rows.length})</th>${head}<th class="jami">Keldi</th></tr></thead>
					<tbody>${tana || `<tr><td colspan="40" class="empty">Xodim topilmadi</td></tr>`}</tbody>
				</table>
			</div>
		`);
		this.bind();
	}

	bind() {
		this.body.find("[data-act='reload']").on("click", () => this.load());
		this.body.find("[data-oy]").on("click", (e) => this.oyOzgart(Number($(e.currentTarget).data("oy"))));
		this.body.find(".fkategoriya").on("change", (e) => {
			this.fKategoriya = e.target.value;
			this.load();
		});
		this.body.find("[data-f]").on("click", (e) => {
			this.faqatOqituvchi = Number($(e.currentTarget).data("f"));
			this.load();
		});
		this.body.find(".q").on("input", frappe.utils.debounce((e) => { this.q = e.target.value; this.render(); }, 250));
		this.body.find("button.yc").on("click", (e) => this.belgila($(e.currentTarget)));
	}

	// Bosilganda aylanadi: bo'sh -> Keldi -> Kelmadi -> bo'sh
	belgila($btn) {
		const xodim = $btn.data("x"), sana = $btn.data("s");
		const hozir = $btn.hasClass("keldi") ? "Keldi" : $btn.hasClass("yoq") ? "Kelmadi" : "";
		const keyingi = hozir === "" ? "Keldi" : hozir === "Keldi" ? "Kelmadi" : "tozalash";
		const qator = (this.data.qatorlar || []).find((r) => r.xodim === xodim);

		const yuborish = (koef) => frappe.call({
			method: `${YQ_M}.belgila`,
			args: { xodim, sana, holat: keyingi, koef },
			callback: (r) => {
				const h = r.message && r.message.holat;
				$btn.removeClass("keldi yoq bosh");
				if (h === "Present") { $btn.addClass("keldi").text(qator.soatbay ? (r.message.koef || "") : "✓"); }
				else if (h === "Absent") { $btn.addClass("yoq").text("✕"); }
				else { $btn.addClass("bosh").text("·"); }
				// kunlik ma'lumotni yangilaymiz (jami uchun)
				const c = qator.kunlik.find((x) => x.sana === sana);
				if (c) { c.holat = h; c.koef = r.message.koef; }
				qator.keldi = qator.kunlik.filter((x) => x.holat === "Present").length;
				$btn.closest("tr").find("td.jami b").text(qator.keldi);
			},
			error: (err) => frappe.show_alert({ message: (err && err.message) || "Xatolik", indicator: "red" }),
		});

		if (keyingi === "Keldi" && qator && qator.soatbay) {
			frappe.prompt([{ fieldname: "soat", fieldtype: "Float", label: "Necha soat ishladi", default: 8, reqd: 1 }],
				(v) => yuborish(v.soat), "Soatbay xodim", "Saqlash");
		} else {
			yuborish(null);
		}
	}
}
