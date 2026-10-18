// Copyright (c) 2026, Target Zenit — Yo'qlama (zavuch uchun)
// Kunlik yo'qlama: xodimlar x kunlar to'ri. PUL MA'LUMOTI YO'Q.
// Belgilangan kunlar ERPNext Attendance'ga yoziladi — oylik tabel shuni o'qiydi.
// UX: katak bosilganda KELDI/KELMADI tanlovi ochiladi (aylantirish emas);
// kategoriya filtri KO'P TANLOVLI chiplar; qidiruvda faqat jadval tanasi
// yangilanadi — fokus yo'qolmaydi.
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
		this.fKats = [];         // ish haqi kategoriyalari — KO'P TANLOV (bo'sh = hammasi)
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
			args: { yil: this.yil, oy: this.oy, kategoriya: JSON.stringify(this.fKats) },
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

	// Bitta xodim qatori HTML'i
	rowHtml(r) {
		const d = this.data, kunlar = d.kunlar || [];
		const kataklar = r.kunlik.map((c, i) => {
			const k = kunlar[i];
			const darsli = r.dars_kunlari.includes(new Date(k.sana).getDay() === 0 ? 6 : new Date(k.sana).getDay() - 1);
			// Ishga kirmagan / ishdan ketgan kunlar — oylik tabeldagi kabi "—"
			if (c.tashqari) {
				const izoh = c.tashqari === "ketgan"
					? `${r.ketgan_sana} da ishdan ketgan`
					: `${r.kirgan_sana} da ishga kirgan`;
				return `<td><button class="yc tashqari" disabled title="${k.sana} · ${izoh}">—</button></td>`;
			}
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
			<th class="nom" title="${this.esc(r.ism)}${r.lavozim ? ` — ${this.esc(r.lavozim)}` : ""}${r.fanlar && r.fanlar.length ? ` · fanlar: ${this.esc(r.fanlar.join(", "))}` : ""}${r.ketgan_sana ? ` — ${r.ketgan_sana} da ishdan ketgan` : ""}"><b>${this.esc(r.ism)}</b><span>${this.esc(r.lavozim || r.kategoriya || "")}${r.soatbay ? " · soatbay" : ""}</span>${r.fanlar && r.fanlar.length ? `<span class="fan">${this.esc(this.fanQisqa(r.fanlar))}</span>` : ""}${r.ketgan_sana ? `<span class="ketgan">ketgan: ${this.esc(r.ketgan_sana)}</span>` : ""}</th>
			${kataklar}
			<td class="jami"><b>${r.keldi}</b></td>
			<td class="jami kerak" title="${this.kerakIzoh(r)}">${r.kerak_kun}</td></tr>`;
	}

	// Fanlar ko'p bo'lsa ism ustuni cho'zilib ketmasin: 3 tasi + "+N"
	fanQisqa(fanlar) {
		return fanlar.length > 3
			? `${fanlar.slice(0, 3).join(", ")} +${fanlar.length - 3}`
			: fanlar.join(", ");
	}

	// "Kerak" ustuni izohi — son qayerdan olingani
	kerakIzoh(r) {
		if (r.kerak_manba === "jadval") {
			return `Dars jadvali bo'yicha: shu oyda ${r.kerak_kun} dars kuni`
				+ (r.fanlar && r.fanlar.length ? ` · ${r.fanlar.join(", ")}` : "");
		}
		const m = { oy: "shu oy uchun kiritilgan norma", xodim: "xodimning doimiy normasi",
			default: "default norma (o'qituvchi 21, boshqalar 26)" }[r.kerak_manba] || "norma";
		return `Norma ish kuni — ${m}`;
	}

	tbodyHtml() {
		const rows = this.qatorlar();
		return rows.map((r) => this.rowHtml(r)).join("")
			|| `<tr><td colspan="41" class="empty">Xodim topilmadi</td></tr>`;
	}

	// Qidiruvda FAQAT jadval tanasi yangilanadi — input fokusi saqlanadi
	paintBody() {
		this.body.find("table.ytbl tbody").html(this.tbodyHtml());
		this.body.find("th.nom-head").html(`Xodim (${this.qatorlar().length})`);
	}

	render() {
		$(".yq-pop").remove();
		const d = this.data;
		const kunlar = d.kunlar || [];

		const head = kunlar.map((k) =>
			`<th class="kun ${k.dam ? "dam" : ""}${k.sana === d.bugun ? " bugun" : ""}" title="${k.sana}">
				<span>${k.kun}</span><em>${k.hafta}</em></th>`).join("");

		// Kategoriya chiplari — KO'P TANLOV: bosilgani yonadi/o'chadi, bo'sh = hammasi
		const katlar = (d.kategoriyalar || []).map((k) =>
			`<button class="chip kchip ${this.fKats.indexOf(k) !== -1 ? "on" : ""}" data-kat="${this.esc(k)}">${this.esc(k)}</button>`).join("")
			+ `<button class="chip kchip ${this.fKats.indexOf("__none") !== -1 ? "on" : ""}" data-kat="__none">Belgilanmagan</button>`;

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
				<div class="chips kchips" title="Kategoriya — bir nechtasini tanlash mumkin">${katlar}</div>
				<div class="spacer"></div>
				<span class="legend"><i class="keldi"></i> keldi <i class="yoq"></i> kelmadi
					<i class="darsli"></i> darsi bor kun <i class="bosh"></i> belgilanmagan · <b>—</b> ishlamagan kun (kirmagan/ketgan) · katakni bosing — tanlov ochiladi</span>
			</div>

			<div class="card scroll-x">
				<table class="ytbl">
					<thead><tr><th class="nom nom-head">Xodim (${this.qatorlar().length})</th>${head}<th class="jami">Keldi</th><th class="jami kerak" title="Shu oyda necha kun kelishi kerak">Kerak</th></tr></thead>
					<tbody>${this.tbodyHtml()}</tbody>
				</table>
			</div>
		`);
		this.bind();
	}

	bind() {
		// Delegatlangan hodisalar — tbody qayta chizilganda ham ishlayveradi
		this.body.off(".yq");
		this.body.on("click.yq", "[data-act='reload']", () => this.load());
		this.body.on("click.yq", "[data-oy]", (e) => this.oyOzgart(Number($(e.currentTarget).data("oy"))));
		this.body.on("click.yq", ".kchip", (e) => {
			const k = String($(e.currentTarget).data("kat"));
			const i = this.fKats.indexOf(k);
			if (i === -1) this.fKats.push(k); else this.fKats.splice(i, 1);
			this.load();
		});
		this.body.on("input.yq", ".q", frappe.utils.debounce((e) => {
			this.q = e.target.value;
			this.paintBody();               // to'liq render EMAS — fokus joyida qoladi
		}, 150));
		this.body.on("click.yq", "button.yc:not(:disabled)", (e) => this.tanlovPop($(e.currentTarget)));
	}

	// Katak bosilganda tanlov popover: ✅ Keldi / ✖ Kelmadi (+ Tozalash)
	tanlovPop($btn) {
		$(".yq-pop").remove();
		const xodim = $btn.data("x"), sana = $btn.data("s");
		const qator = (this.data.qatorlar || []).find((r) => r.xodim === xodim);
		if (!qator) return;
		const belgilangan = $btn.hasClass("keldi") || $btn.hasClass("yoq");
		const $p = $(`<div class="yq-pop">
			<span class="t">${this.esc(qator.ism)} · ${this.esc(sana.slice(8))}-kun</span>
			<button class="p-keldi">✅ Keldi${qator.soatbay ? " (soat)" : ""}</button>
			<button class="p-yoq">✖ Kelmadi</button>
			${belgilangan ? `<button class="p-toza" title="Belgini olib tashlash">↺</button>` : ""}
		</div>`);
		$("body").append($p);
		const off = $btn.offset(), w = $p.outerWidth();
		let left = off.left + $btn.outerWidth() / 2 - w / 2;
		left = Math.max(8, Math.min(left, $(window).width() - w - 8));
		$p.css({ top: off.top + $btn.outerHeight() + 5, left: left });

		$p.find(".p-keldi").on("click", () => { $p.remove(); this.saqla($btn, qator, sana, "Keldi"); });
		$p.find(".p-yoq").on("click", () => { $p.remove(); this.saqla($btn, qator, sana, "Kelmadi"); });
		$p.find(".p-toza").on("click", () => { $p.remove(); this.saqla($btn, qator, sana, "tozalash"); });
		setTimeout(() => $(document).off("click.yqpop").on("click.yqpop", (e) => {
			if (!$(e.target).closest(".yq-pop").length) { $p.remove(); $(document).off("click.yqpop"); }
		}), 0);
	}

	// Serverga yozish + katakni JOYIDA yangilash (jadval qayta chizilmaydi)
	saqla($btn, qator, sana, holat) {
		const yuborish = (koef) => frappe.call({
			method: `${YQ_M}.belgila`,
			args: { xodim: qator.xodim, sana, holat, koef },
			callback: (r) => {
				const h = r.message && r.message.holat;
				$btn.removeClass("keldi yoq bosh");
				if (h === "Present") { $btn.addClass("keldi").text(qator.soatbay ? (r.message.koef || "") : "✓"); }
				else if (h === "Absent") { $btn.addClass("yoq").text("✕"); }
				else { $btn.addClass("bosh").text("·"); }
				const c = qator.kunlik.find((x) => x.sana === sana);
				if (c) { c.holat = h; c.koef = r.message.koef; }
				qator.keldi = qator.kunlik.filter((x) => x.holat === "Present").length;
				$btn.closest("tr").find("td.jami b").text(qator.keldi);
			},
			error: (err) => frappe.show_alert({ message: (err && err.message) || "Xatolik", indicator: "red" }),
		});

		if (holat === "Keldi" && qator.soatbay) {
			frappe.prompt([{ fieldname: "soat", fieldtype: "Float", label: "Necha soat ishladi", default: 8, reqd: 1 }],
				(v) => yuborish(v.soat), "Soatbay xodim", "Saqlash");
		} else {
			yuborish(null);
		}
	}
}
