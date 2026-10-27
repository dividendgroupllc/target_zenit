// Copyright (c) 2026, Target Zenit
// Sotuv nazorati — BITTA sahifada, ichiga kiradigan (drill-down) ko'rinish.
//
// Nega shunday: investor avval ikki panel orasida yurardi (qarzdorlik paneli —
// kim bilan gaplashildi; sotuv nazorati — tushum va kommentlar), keyin esa
// 6 ta yonma-yon bo'lim bo'ldi va ma'lumot yana sochilib ketdi. Endi uchta
// "qarash nuqtasi" bor — MENEJER, O'QUVCHI, TAKLIF — va har qator bosilganda
// o'sha odamning/o'quvchining HAMMA ma'lumoti shu yerning o'zida ochiladi:
// kunlik faollik, kim bilan gaplashgani, suhbat (ovoz + matn + AI tahlil),
// panelga yozgan kommentlari, va'dalari va tushumi.
//
// Umumiy bundle: /app/sotuv-nazorati sahifasi shuni ishlatadi (desk sahifa
// JS'lari bir-birini ko'rmaydi, shuning uchun app_include_js orqali yuklanadi).
window.TZSotuvNazoratiView = class TZSotuvNazoratiView {
	constructor(o) {
		this.$w = o.wrapper;
		this.state = { from_date: o.from_date, to_date: o.to_date };
		this.withToolbar = !!o.toolbar;
		this.M = "target_zenit.target_zenit.page.sotuv_nazorati.sotuv_nazorati";
		this.lens = "menejer";      // menejer | oquvchi | taklif
		this.ochiq = null;          // ochilgan qator kaliti (menejer yoki student)
		this.drillTab = "kunlik";   // menejer ichidagi bo'lim
		this.aloqa = null;
		this.tel = null;
		this.matnlar = {};          // qongiroq -> to'liq transkript (talab bo'yicha)
		this.skeleton();
		this.load();
	}

	// ======================= yordamchilar =======================
	esc(x) { return frappe.utils.escape_html(String(x == null ? "" : x)); }
	fmt(n) {
		n = Math.round(Number(n) || 0);
		const s = Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
		return (n < 0 ? "−" : "") + s;
	}
	kc(n) {
		const v = Number(n) || 0, a = Math.abs(v), sg = v < 0 ? "−" : "";
		if (a >= 1e9) return sg + (a / 1e9).toFixed(2).replace(".", ",") + " mlrd";
		if (a >= 1e6) return sg + (a / 1e6).toFixed(1).replace(".", ",") + " mln";
		if (a >= 1e3) return sg + Math.round(a / 1e3) + " ming";
		return sg + Math.round(a);
	}
	dt(x) { return x ? frappe.datetime.str_to_user(String(x).slice(0, 16)) : "—"; }
	kun(x) { return x ? frappe.datetime.str_to_user(String(x).slice(0, 10)) : ""; }
	dur(sec) {
		sec = Math.round(Number(sec) || 0);
		return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
	}
	pct(v) { return v === null || v === undefined ? "—" : `${v}%`; }

	// Qarzdorlik panelida shu o'quvchini ochish: ish nomi bo'lsa shu bo'yicha,
	// bo'lmasa o'quvchi ID bo'yicha (panel o'zi topadi).
	panelUrl(student, qarz_ishi) {
		if (qarz_ishi) return `/app/qarzdorlik?case=${encodeURIComponent(qarz_ishi)}`;
		if (student) return `/app/qarzdorlik?student=${encodeURIComponent(student)}`;
		return "/app/qarzdorlik";
	}

	sverkaUrl(customer) {
		const b = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		const yil = b.getMonth() + 1 >= 7 ? b.getFullYear() : b.getFullYear() - 1;
		return `/app/query-report/Akt Sverka?${new URLSearchParams({
			party_type: "Customer", party: customer,
			from_date: `${yil}-07-01`, to_date: frappe.datetime.get_today(),
		})}`;
	}

	// ======================= karkas =======================
	skeleton() {
		this.$w.addClass("tz-sn").html(`
			${this.withToolbar ? `
			<div class="sn-top">
				<div class="sn-davr">
					<label>Davr:</label>
					<input type="date" class="sn-from" value="${this.state.from_date}">
					<span>—</span>
					<input type="date" class="sn-to" value="${this.state.to_date}">
					<div class="tz-seg sn-preset">
						<button data-preset="7">7 kun</button>
						<button data-preset="30" class="on">30 kun</button>
						<button data-preset="month">Bu oy</button>
						<button data-preset="prev">O'tgan oy</button>
					</div>
				</div>
				<div class="sn-tools"><button class="sn-refresh"><span class="dot"></span> Yangilash</button></div>
			</div>` : ""}
			<div class="sn-kpi"></div>
			<div class="sn-lens tz-seg"></div>
			<div class="sn-body"><div class="tz-loader">Yuklanyapti…</div></div>`);

		if (this.withToolbar) {
			this.$w.find(".sn-from").on("change", (e) => { this.state.from_date = e.target.value; this.load(); });
			this.$w.find(".sn-to").on("change", (e) => { this.state.to_date = e.target.value; this.load(); });
			this.$w.find(".sn-refresh").on("click", () => this.load());
			this.$w.find(".sn-preset button").on("click", (e) => this.preset($(e.currentTarget).data("preset")));
		}
	}

	preset(p) {
		const t = frappe.datetime.get_today();
		let from = t, to = t;
		if (String(p) === "7") from = frappe.datetime.add_days(t, -7);
		else if (String(p) === "30") from = frappe.datetime.add_days(t, -30);
		else if (p === "month") from = frappe.datetime.month_start();
		else if (p === "prev") {
			from = frappe.datetime.add_months(frappe.datetime.month_start(), -1);
			to = frappe.datetime.add_days(frappe.datetime.month_start(), -1);
		}
		this.state.from_date = from; this.state.to_date = to;
		this.$w.find(".sn-from").val(from);
		this.$w.find(".sn-to").val(to);
		this.$w.find(".sn-preset button").removeClass("on");
		this.$w.find(`.sn-preset button[data-preset="${p}"]`).addClass("on");
		this.load();
	}

	setPeriod(from_date, to_date) {
		this.state.from_date = from_date;
		this.state.to_date = to_date;
		this.load();
	}

	// ======================= ma'lumot =======================
	load() {
		this.$w.find(".sn-body").html(`<div class="tz-loader">Yuklanyapti…</div>`);
		const args = { from_date: this.state.from_date, to_date: this.state.to_date };
		Promise.all([
			frappe.call({ method: `${this.M}.get_data`, args }),
			frappe.call({ method: `${this.M}.get_telefon`, args }),
		]).then(([a, t]) => {
			this.aloqa = (a && a.message) || null;
			this.tel = (t && t.message) || null;
			this.matnlar = {};
			this.paint();
		}).catch(() => this.$w.find(".sn-body").html(
			`<div class="empty-hint">Ma'lumotni yuklab bo'lmadi.</div>`));
	}

	// Menejer kaliti bo'yicha birlashtirilgan qator (telefon + panel yozuvlari)
	menejerlar() {
		const tel = (this.tel && this.tel.menejerlar) || [];
		const alo = (this.aloqa && this.aloqa.menejerlar) || [];
		const map = {};
		for (const t of tel) map[t.masul] = Object.assign({ masul: t.masul, nomi: t.nomi }, { tel: t });
		for (const a of alo) {
			map[a.masul] = map[a.masul] || { masul: a.masul, nomi: a.nomi };
			map[a.masul].alo = a;
			map[a.masul].nomi = a.nomi || map[a.masul].nomi;
		}
		return Object.values(map).map((m) => {
			const t = m.tel || {}, a = m.alo || {};
			return {
				masul: m.masul, nomi: m.nomi || m.masul,
				qongiroq: t.qongiroq || 0, gaplashildi: t.gaplashildi || 0,
				daqiqa: t.daqiqa || 0, mijozlar: t.mijozlar_soni || 0,
				oquvchilar: t.oquvchilar_soni || 0, kunlar: t.kunlar_soni || 0,
				kunlik: t.kunlik_ortacha || 0, yozuv: t.yozuv || 0, tahlil: t.tahlil || 0,
				taklif: t.taklif || 0, oxirgi: t.oxirgi || a.oxirgi_faollik,
				yozuvlar: a.qongiroq || 0, vada_soni: a.vada_soni || 0,
				vada_summa: a.vada_summa || 0, kept_foiz: a.kept_foiz,
				yigildi: a.yigildi || 0, ochiq_ish: a.ochiq_ish || 0, qarz: a.qarz || 0,
				kechikkan: a.kechikkan || 0, sifat_foiz: a.sifat_foiz, faol: a.faol !== 0,
			};
		}).sort((x, y) => y.qongiroq - x.qongiroq || y.yigildi - x.yigildi);
	}

	suhbatlari(kalit, tur) {
		const q = (this.tel && this.tel.qongiroqlar) || [];
		return tur === "student" ? q.filter((x) => x.student === kalit)
			: q.filter((x) => (x.masul || "—") === kalit);
	}

	yozuvlari(kalit, tur) {
		const a = (this.aloqa && this.aloqa.aloqalar) || [];
		return tur === "student" ? a.filter((x) => x.student === kalit)
			: a.filter((x) => x.masul === kalit);
	}

	// ======================= chizish =======================
	paint() {
		this.$w.find(".sn-kpi").html(this.kpi());
		const t = (this.tel && this.tel.jami) || {};
		const lenslar = [
			["menejer", `👤 Menejerlar (${this.fmt(this.menejerlar().length)})`],
			["oquvchi", `🎓 O'quvchilar (${this.fmt(((this.tel || {}).oquvchilar || []).length)})`],
			["taklif", `💡 Ota-ona takliflari (${this.fmt(t.taklif)})`],
		];
		this.$w.find(".sn-lens").html(lenslar.map(([k, l]) =>
			`<button class="tz-seg-opt${this.lens === k ? " on" : ""}" data-lens="${k}">${l}</button>`).join(""));
		this.$w.find("[data-lens]").off("click").on("click", (e) => {
			this.lens = String($(e.currentTarget).data("lens"));
			this.ochiq = null;
			this.paint();
		});

		const body = this.$w.find(".sn-body");
		body.html({
			menejer: () => this.menejerJadval(),
			oquvchi: () => this.oquvchiJadval(),
			taklif: () => this.taklifJadval(),
		}[this.lens]());
		this.bind(body);
	}

	bind(body) {
		body.find("[data-ochish]").off("click").on("click", (e) => {
			const k = String($(e.currentTarget).data("ochish"));
			this.ochiq = this.ochiq === k ? null : k;
			this.paint();
		});
		body.find("[data-drill]").off("click").on("click", (e) => {
			e.stopPropagation();
			this.drillTab = String($(e.currentTarget).data("drill"));
			this.paint();
		});
		body.find("[data-csv]").off("click").on("click", (e) => {
			e.stopPropagation();
			this.csv(String($(e.currentTarget).data("csv")));
		});
		// Suhbat matnini talab bo'yicha yuklash (ro'yxatda yuborilmaydi — og'ir)
		body.find("[data-matn]").off("click").on("click", (e) => {
			e.stopPropagation();
			const $b = $(e.currentTarget), nom = String($b.data("matn"));
			const $box = $b.closest(".sb-card").find(".sb-matn");
			if (this.matnlar[nom] !== undefined) {
				$box.toggleClass("yopiq");
				$b.text($box.hasClass("yopiq") ? "matnni ko'rsatish" : "matnni yashirish");
				return;
			}
			$b.prop("disabled", true).text("yuklanyapti…");
			frappe.call({ method: `${this.M}.get_suhbat`, args: { qongiroq: nom } })
				.then((r) => {
					this.matnlar[nom] = (r.message || {}).transkript || "";
					$box.text(this.matnlar[nom] || "Transkript yo'q").removeClass("yopiq");
					$b.prop("disabled", false).text("matnni yashirish");
				})
				.catch(() => $b.prop("disabled", false).text("matn ochilmadi"));
		});
	}

	kpi() {
		const a = (this.aloqa && this.aloqa.jami) || {};
		const t = (this.tel && this.tel.jami) || {};
		const ozi = (this.aloqa && this.aloqa.faqat_ozi) || (this.tel && this.tel.faqat_ozi);
		return `${ozi ? `<div class="empty-hint" style="padding:2px 0">Faqat o'z ko'rsatkichingiz.</div>` : ""}
			<div class="tz-sotuv-kpi">
				<div class="k"><span class="l">Suhbatlar</span><span class="v">${this.fmt(t.gaplashildi)}</span>
					<span class="s">${this.fmt(t.qongiroq)} qo'ng'iroqdan · ${this.fmt(t.daqiqa)} daqiqa</span></div>
				<div class="k"><span class="l">Gaplashilgan mijoz</span><span class="v">${this.fmt(t.mijozlar)}</span>
					<span class="s">${this.fmt(t.oquvchilar)} o'quvchi aniqlandi</span></div>
				<div class="k"><span class="l">Ovoz / AI tahlil</span><span class="v">${this.fmt(t.yozuv)} / ${this.fmt(t.tahlil)}</span>
					<span class="s">${this.fmt(t.bogllanmagan)} qo'ng'iroq bog'lanmagan</span></div>
				<div class="k"><span class="l">Ota-ona takliflari</span><span class="v">${this.fmt(t.taklif)}</span>
					<span class="s">AI tahlilidan ajratilgan</span></div>
				<div class="k"><span class="l">Va'dalar</span><span class="v">${this.fmt(a.vada_soni)}</span>
					<span class="s">${this.kc(a.vada_summa)} · ${this.fmt(a.qongiroq)} panel yozuvi</span></div>
				<div class="k"><span class="l">Davrda tushgan to'lov</span><span class="v">${this.kc(a.yigildi)}</span>
					<span class="s">menejerlarga biriktirilgan o'quvchilardan</span></div>
			</div>`;
	}

	// ======================= 1) MENEJERLAR =======================
	menejerJadval() {
		const rows = this.menejerlar().map((m, i) => {
			const ochiq = this.ochiq === m.masul;
			return `<tr class="sn-bosh-qator ${ochiq ? "on" : ""}" data-ochish="${this.esc(m.masul)}">
					<td class="r sn-orin">${ochiq ? "▾" : i + 1}</td>
					<td><b>${this.esc(m.nomi)}</b>${m.faol ? "" : ` <span class="tz-chip">nofaol</span>`}
						<div class="tz-sub">${this.esc(m.masul)}</div></td>
					<td class="r"><b>${this.fmt(m.gaplashildi)}</b><div class="tz-sub">${this.fmt(m.qongiroq)} urinish</div></td>
					<td class="r">${this.fmt(m.daqiqa)}<div class="tz-sub">daqiqa</div></td>
					<td class="r">${this.fmt(m.kunlik)}<div class="tz-sub">kuniga · ${this.fmt(m.kunlar)} kun</div></td>
					<td class="r">${this.fmt(m.mijozlar)}<div class="tz-sub">${this.fmt(m.oquvchilar)} o'quvchi</div></td>
					<td class="r">${this.fmt(m.yozuvlar)}<div class="tz-sub">panel yozuvi</div></td>
					<td class="r">${this.fmt(m.vada_soni)}<div class="tz-sub">${this.kc(m.vada_summa)}</div></td>
					<td class="r ${m.kept_foiz !== null && m.kept_foiz < 50 ? "neg" : ""}">${this.pct(m.kept_foiz)}
						<div class="tz-sub">va'da bajarildi</div></td>
					<td class="r"><b>${this.kc(m.yigildi)}</b><div class="tz-sub">${this.fmt(m.ochiq_ish)} ish · ${this.kc(m.qarz)}</div></td>
					<td class="r">${m.taklif ? `<span class="tz-chip warn">${this.fmt(m.taklif)}</span>` : "—"}</td>
					<td class="nowrap">${this.dt(m.oxirgi)}</td>
				</tr>
				${ochiq ? `<tr class="sn-drill"><td colspan="12">${this.menejerIchi(m)}</td></tr>` : ""}`;
		}).join("");

		return `<div class="card">
			<div class="hd"><div><h3>Menejerlar — umumiy hisobot</h3>
				<div class="meta">Qatorni bosing: o'sha menejerning kunlik faolligi, mijozlari,
					suhbatlari (ovoz + matn + AI) va panelga yozgan kommentlari shu yerda ochiladi</div></div>
				<div class="tz-nach-tools"><button class="tz-seg-opt" data-csv="menejer">⬇ CSV</button></div></div>
			<div class="tbl-wrap"><table class="tz-sotuv-tbl sn-master">
				<thead><tr><th class="r">#</th><th>Menejer</th><th class="r">Gaplashdi</th>
					<th class="r">Suhbat</th><th class="r">Kunlik</th><th class="r">Mijoz</th>
					<th class="r">Yozuv</th><th class="r">Va'da</th><th class="r">Bajarildi</th>
					<th class="r">Tushum</th><th class="r">Taklif</th><th>Oxirgi faollik</th></tr></thead>
				<tbody>${rows || `<tr><td colspan="12" class="empty-hint">Bu davrda faollik yo'q</td></tr>`}</tbody>
			</table></div></div>`;
	}

	menejerIchi(m) {
		const tablar = [
			["kunlik", "Kunlik faollik"],
			["mijozlar", "Kim bilan gaplashdi"],
			["suhbatlar", "Suhbatlar (ovoz + matn + AI)"],
			["yozuvlar", "Panel yozuvlari"],
		];
		const nav = `<div class="tz-seg sn-drill-nav">${tablar.map(([k, l]) =>
			`<button class="tz-seg-opt${this.drillTab === k ? " on" : ""}" data-drill="${k}">${l}</button>`).join("")}</div>`;
		return nav + `<div class="sn-drill-body">${({
			kunlik: () => this.drillKunlik(m),
			mijozlar: () => this.drillMijozlar(m),
			suhbatlar: () => this.drillSuhbatlar(this.suhbatlari(m.masul, "masul")),
			yozuvlar: () => this.drillYozuvlar(this.yozuvlari(m.masul, "masul")),
		}[this.drillTab] || (() => ""))()}</div>`;
	}

	drillKunlik(m) {
		const kunlar = (this.tel && this.tel.kunlar) || [];
		const kunlik = (this.tel && this.tel.kunlik) || {};
		if (!kunlar.length) return `<div class="empty-hint">Qo'ng'iroq yo'q</div>`;
		const qiymat = kunlar.map((k) => (kunlik[k] || {})[m.masul] || 0);
		const maks = Math.max(1, ...qiymat);
		const jami = qiymat.reduce((a, b) => a + b, 0);
		return `<div class="sn-bars">${kunlar.map((k, i) => `
			<div class="sn-bar" title="${k}: ${qiymat[i]} qo'ng'iroq">
				<div class="sn-bar-v" style="height:${Math.round((qiymat[i] / maks) * 100)}%"></div>
				<div class="sn-bar-n">${qiymat[i] || ""}</div>
				<div class="sn-bar-k">${String(k).slice(8, 10)}.${String(k).slice(5, 7)}</div>
			</div>`).join("")}</div>
			<div class="tz-sub" style="margin-top:6px">Jami ${this.fmt(jami)} qo'ng'iroq ·
				${this.fmt(m.kunlar)} ish kuni · kuniga o'rtacha <b>${this.fmt(m.kunlik)}</b> ·
				suhbat ${this.fmt(m.daqiqa)} daqiqa</div>`;
	}

	drillMijozlar(m) {
		const suhbatlar = this.suhbatlari(m.masul, "masul");
		const guruh = {};
		for (const q of suhbatlar) {
			const k = q.student || `tel:${q.normal_telefon || q.name}`;
			const g = guruh[k] || (guruh[k] = {
				student: q.student, nomi: q.student_name || q.tashqi_raqam || "noma'lum",
				sinf: q.sinf, qarz_ishi: q.qarz_ishi, soni: 0, gaplashildi: 0,
				daqiqa: 0, oxirgi: null, mavzu: "", taklif: 0,
			});
			g.soni += 1; g.gaplashildi += q.gaplashildi ? 1 : 0;
			g.daqiqa += (Number(q.suhbat_vaqti) || 0) / 60;
			g.taklif += q.taklif ? 1 : 0;
			if (!g.oxirgi || String(q.boshlandi) > String(g.oxirgi)) {
				g.oxirgi = q.boshlandi;
				g.mavzu = q.mavzu || q.natija || "";
			}
		}
		const rows = Object.values(guruh).sort((a, b) => b.soni - a.soni).map((g) => `
			<tr><td>${g.student ? `<a href="/app/student/${encodeURIComponent(g.student)}" target="_blank">${this.esc(g.nomi)}</a>`
					: this.esc(g.nomi)}<div class="tz-sub">${this.esc(g.sinf || "")}</div></td>
				<td class="r">${this.fmt(g.soni)}</td>
				<td class="r">${this.fmt(g.gaplashildi)}</td>
				<td class="r">${g.daqiqa.toFixed(1)}</td>
				<td class="nowrap">${this.dt(g.oxirgi)}</td>
				<td class="tz-komment">${this.esc(g.mavzu || "—")}</td>
				<td class="r">${g.taklif ? `<span class="tz-chip warn">${g.taklif}</span>` : "—"}</td>
				<td>${g.student || g.qarz_ishi
					? `<a class="tz-sverka" href="${this.panelUrl(g.student, g.qarz_ishi)}" target="_blank"
						title="Qarzdorlik panelida ochish">qarzdorlik ↗</a>` : ""}</td></tr>`).join("");
		return `<div class="tbl-wrap"><table class="tz-sotuv-tbl">
			<thead><tr><th>Kim bilan</th><th class="r">Qo'ng'iroq</th><th class="r">Gaplashdi</th>
				<th class="r">Daqiqa</th><th>Oxirgi</th><th>Nima haqida (AI)</th>
				<th class="r">Taklif</th><th></th></tr></thead>
			<tbody>${rows || `<tr><td colspan="8" class="empty-hint">Suhbat yo'q</td></tr>`}</tbody></table></div>`;
	}

	drillSuhbatlar(qlar) {
		if (!qlar.length) return `<div class="empty-hint">Suhbat yo'q</div>`;
		return `<div class="tz-suhbatlar">${qlar.slice(0, 60).map((q) => this.suhbatKarta(q)).join("")}
			${qlar.length > 60 ? `<div class="tz-sub">… birinchi 60 tasi ko'rsatildi (${this.fmt(qlar.length)} tadan)</div>` : ""}</div>`;
	}

	drillYozuvlar(list) {
		if (!list.length) return `<div class="empty-hint">Panelda yozuv yo'q</div>`;
		const rows = list.map((a) => `
			<tr><td class="nowrap">${this.dt(a.creation)}</td>
				<td><a href="${this.panelUrl(a.student, a.qarz_ishi)}" target="_blank">${this.esc(a.student_name || "—")}</a>
					<div class="tz-sub">${this.esc(a.sinf || "")}</div></td>
				<td>${a.aloqa_natijasi === "Gaplashildi"
					? `<b>${this.esc(a.aloqa_natijasi)}</b>${a.hisob_natijasi ? ` → ${this.esc(a.hisob_natijasi)}` : ""}`
					: this.esc(a.aloqa_natijasi)}
					${a.vada_summa ? `<div class="tz-sub">Va'da: ${this.kc(a.vada_summa)} — ${this.kun(a.vada_sana)}</div>` : ""}</td>
				<td class="tz-komment">${this.esc(a.komment || "—")}</td>
				<td class="nowrap">${this.esc(a.keyingi_harakat || "—")}<div class="tz-sub">${this.kun(a.keyingi_sana)}</div></td>
				<td>${[a.kech_kiritilgan ? `<span class="tz-chip warn">⏱ keyin kiritilgan</span>` : "",
					a.boshqa_kiritdi ? `<span class="tz-chip warn">👤 ${this.esc(a.owner)}</span>` : "",
					!a.sifatli ? `<span class="tz-chip neg">izoh to'liq emas</span>` : ""].filter(Boolean).join(" ")}</td></tr>`).join("");
		return `<div class="tbl-wrap"><table class="tz-sotuv-tbl">
			<thead><tr><th>Vaqt</th><th>O'quvchi</th><th>Natija</th><th>Komment</th>
				<th>Keyingi qadam</th><th>Belgilar</th></tr></thead>
			<tbody>${rows}</tbody></table></div>`;
	}

	// ======================= 2) O'QUVCHILAR =======================
	oquvchiJadval() {
		const list = (this.tel && this.tel.oquvchilar) || [];
		const rows = list.map((o) => {
			const ochiq = this.ochiq === o.student;
			return `<tr class="sn-bosh-qator ${ochiq ? "on" : ""}" data-ochish="${this.esc(o.student)}">
					<td>${ochiq ? "▾ " : ""}<b>${this.esc(o.student_name)}</b>
						<div class="tz-sub">${this.esc(o.sinf || "")}</div></td>
					<td class="r"><b>${this.fmt(o.gaplashildi)}</b><div class="tz-sub">${this.fmt(o.qongiroq)} qo'ng'iroq</div></td>
					<td class="r">${this.fmt(o.daqiqa)}<div class="tz-sub">daqiqa</div></td>
					<td>${this.esc((o.menejerlar || []).join(", "))}</td>
					<td class="nowrap">${this.dt(o.oxirgi)}</td>
					<td class="tz-komment">${this.esc(o.oxirgi_mavzu || "—")}</td>
					<td class="r ${o.qarz > 1000 ? "neg" : ""}">${o.qarz ? this.kc(o.qarz) : "—"}
						<div class="tz-sub">${this.esc(o.ishlov_status || "")}</div></td>
					<td class="r">${o.taklif ? `<span class="tz-chip warn">${this.fmt(o.taklif)}</span>` : "—"}</td>
				</tr>
				${ochiq ? `<tr class="sn-drill"><td colspan="8">
					<div class="sn-drill-head">
						<a href="${this.panelUrl(o.student, o.qarz_ishi)}" target="_blank">Qarzdorlik panelida ochish ↗</a>
						${o.qarz_ishi ? ` · <a href="/app/qarz-ishi/${encodeURIComponent(o.qarz_ishi)}" target="_blank">qarz ishi ↗</a>` : ""}
						${o.student ? ` · <a href="/app/student/${encodeURIComponent(o.student)}" target="_blank">o'quvchi ↗</a>` : ""}
					</div>
					${this.drillYozuvlar(this.yozuvlari(o.student, "student"))}
					${this.drillSuhbatlar(this.suhbatlari(o.student, "student"))}</td></tr>` : ""}`;
		}).join("");

		return `<div class="card">
			<div class="hd"><div><h3>O'quvchilar — kim bilan nima haqida gaplashildi</h3>
				<div class="meta">Qatorni bosing: shu oila bilan bo'lgan hamma suhbat (ovoz, matn, AI tahlil)
					va menejer kommentlari ochiladi</div></div>
				<div class="tz-nach-tools"><button class="tz-seg-opt" data-csv="oquvchi">⬇ CSV</button></div></div>
			<div class="tbl-wrap"><table class="tz-sotuv-tbl sn-master">
				<thead><tr><th>O'quvchi</th><th class="r">Gaplashildi</th><th class="r">Suhbat</th>
					<th>Menejer(lar)</th><th>Oxirgi</th><th>Nima haqida (AI)</th>
					<th class="r">Qarz</th><th class="r">Taklif</th></tr></thead>
				<tbody>${rows || `<tr><td colspan="8" class="empty-hint">Qo'ng'iroqlar o'quvchilarga bog'lanmadi</td></tr>`}</tbody>
			</table></div></div>`;
	}

	// ======================= 3) TAKLIFLAR =======================
	taklifJadval() {
		const list = (this.tel && this.tel.takliflar) || [];
		const rows = list.map((t) => `
			<tr><td class="nowrap">${this.dt(t.sana)}</td>
				<td>${t.student ? `<a href="/app/student/${encodeURIComponent(t.student)}" target="_blank">${this.esc(t.student_name)}</a>`
					: this.esc(t.student_name || "—")}<div class="tz-sub">${this.esc(t.sinf || "")}</div></td>
				<td>${this.esc(t.menejer)}</td>
				<td class="sn-taklif">${this.esc(t.matn)}</td>
				<td>${t.holat ? `<span class="tz-chip${/qarshi/i.test(t.holat) ? " neg" : ""}">${this.esc(t.holat)}</span>` : ""}</td>
				<td>${t.student || t.qarz_ishi
					? `<a class="tz-sverka" href="${this.panelUrl(t.student, t.qarz_ishi)}" target="_blank"
						title="Qarzdorlik panelida shu o'quvchini ochish">qarzdorlik ↗</a>` : ""}</td></tr>`).join("");
		return `<div class="card">
			<div class="hd"><div><h3>Ota-onalarning taklif va shikoyatlari</h3>
				<div class="meta">AI tahlilidan ajratilgan — maktab bo'yicha fikrlar (o'qituvchi, nazorat,
					tadbir, sharoit). To'lov bo'yicha e'tirozlar bu yerga kirmaydi.</div></div>
				<div class="tz-nach-tools"><button class="tz-seg-opt" data-csv="taklif">⬇ CSV</button></div></div>
			<div class="tbl-wrap"><table class="tz-sotuv-tbl">
				<thead><tr><th>Sana</th><th>O'quvchi</th><th>Menejer</th><th>Taklif / shikoyat</th>
					<th>Mijoz holati</th><th></th></tr></thead>
				<tbody>${rows || `<tr><td colspan="6" class="empty-hint">Bu davrda taklif/shikoyat qayd etilmagan</td></tr>`}</tbody>
			</table></div></div>`;
	}

	// ======================= suhbat kartasi =======================
	suhbatKarta(q) {
		const url = `/api/method/target_zenit.telefoniya.api.stream_recording?qongiroq=${encodeURIComponent(q.name)}`;
		const xulosa = (q.ai_xulosa || "").trim();
		const qatorlar = xulosa ? xulosa.split(/\r?\n/).map((x) => x.trim()).filter(Boolean) : [];
		const TAKLIF = "TAKLIF VA SHIKOYAT", ESKI = "MIJOZ TAKLIFI";
		if (xulosa && !qatorlar.some((x) => x.toUpperCase().startsWith(TAKLIF + ":")
				|| x.toUpperCase().startsWith(ESKI + ":"))) qatorlar.push(`${TAKLIF}: Taklif yo'q`);

		const tahlil = qatorlar.length
			? `<div class="sb-tahlil">${qatorlar.map((qt) => {
					const m = qt.match(/^([A-ZА-ЯЎҚҒҲ' ]{3,20}):\s*(.*)$/);
					if (!m) return `<div class="sb-t-row"><span class="sb-t-v">${this.esc(qt)}</span></div>`;
					const bosh = m[1].trim(), qiymat = (m[2] || "").trim();
					const yoq = /^(yo'q|yoq|taklif yo'q|—|-|)$/i.test(qiymat);
					if (bosh === TAKLIF || bosh === ESKI) {
						return `<div class="sb-t-row${yoq ? "" : " sb-taklif-bor"}">
							<span class="sb-t-k">${TAKLIF}</span>
							<span class="sb-t-v${yoq ? " sb-t-yoq" : " sb-t-taklif"}">${this.esc(yoq ? "Taklif yo'q" : qiymat)}</span></div>`;
					}
					if (yoq) return "";
					const holat = bosh === "MIJOZ HOLATI"
						? ` sb-h-${/ijobiy/i.test(qiymat) ? "ok" : /qarshi/i.test(qiymat) ? "bad" : "mut"}` : "";
					return `<div class="sb-t-row${bosh === "DIQQAT" ? " sb-diqqat" : ""}">
						<span class="sb-t-k">${this.esc(bosh)}</span>
						<span class="sb-t-v${holat}">${this.esc(qiymat)}</span></div>`;
				}).join("")}</div>`
			: `<div class="sb-yoq">AI tahlil yo'q</div>`;

		return `<div class="sb-card">
			<div class="sb-head">
				<b>${this.dt(q.boshlandi)}</b>
				<span class="tz-chip">${q.yonalish === "Kiruvchi" ? "📥" : "📤"}</span>
				${q.suhbat_vaqti ? `<span class="tz-sub">${this.dur(q.suhbat_vaqti)}</span>` : ""}
				${q.tugash_sababi ? `<span class="tz-chip${q.tugash_sababi === "Javob berildi" ? "" : " neg"}">${this.esc(q.tugash_sababi)}</span>` : ""}
				<span class="spacer"></span>
				<span class="tz-sub">${this.esc(q.menejer)} · ${this.esc(q.student_name || q.tashqi_raqam || "")}</span>
				${q.student || q.qarz_ishi
					? `<a class="tz-sverka" href="${this.panelUrl(q.student, q.qarz_ishi)}" target="_blank"
						title="Qarzdorlik panelida shu o'quvchini ochish">qarzdorlik ↗</a>` : ""}
			</div>
			<div class="sb-grid">
				<div class="sb-chap">
					${q.audio ? `<audio class="sb-audio" controls preload="none" src="${url}"></audio>`
						: `<div class="tz-sub">${q.yozuv_ochirildi ? "yozuv o'chirilgan" : "yozuv yo'q"}</div>`}
					${q.transkript_bor ? `<div class="sb-matn-bar">
							<span class="tz-sub">${this.fmt(q.transkript_sozlar)} so'z</span>
							<button class="tz-seg-opt" data-matn="${this.esc(q.name)}">matnni ko'rsatish</button></div>
						<div class="sb-matn yopiq"></div>`
						: `<div class="tz-sub">Transkript yo'q</div>`}
				</div>
				<div class="sb-ong">${tahlil}</div>
			</div></div>`;
	}

	// ======================= CSV =======================
	csv(tur) {
		let rows = [], nom = tur;
		if (tur === "menejer") {
			rows = [["#", "Menejer", "Gaplashdi", "Qo'ng'iroq", "Suhbat (daqiqa)", "Kunlik o'rtacha",
				"Ish kuni", "Noyob mijoz", "O'quvchi", "Panel yozuvi", "Va'da", "Va'da summa",
				"Va'da bajarildi %", "Tushum", "Ochiq ish", "Qarz", "Taklif", "Oxirgi faollik"]];
			this.menejerlar().forEach((m, i) => rows.push([i + 1, m.nomi, m.gaplashildi, m.qongiroq,
				m.daqiqa, m.kunlik, m.kunlar, m.mijozlar, m.oquvchilar, m.yozuvlar, m.vada_soni,
				m.vada_summa, m.kept_foiz, m.yigildi, m.ochiq_ish, m.qarz, m.taklif,
				String(m.oxirgi || "").slice(0, 16)]));
		} else if (tur === "oquvchi") {
			rows = [["O'quvchi", "Sinf", "Gaplashildi", "Qo'ng'iroq", "Suhbat (daqiqa)", "Menejerlar",
				"Oxirgi suhbat", "Nima haqida", "Qarz", "Holat", "Taklif"]];
			((this.tel && this.tel.oquvchilar) || []).forEach((o) => rows.push([o.student_name, o.sinf,
				o.gaplashildi, o.qongiroq, o.daqiqa, (o.menejerlar || []).join(" / "),
				String(o.oxirgi || "").slice(0, 16), o.oxirgi_mavzu, o.qarz, o.ishlov_status, o.taklif]));
		} else {
			nom = "taklif";
			rows = [["Sana", "O'quvchi", "Sinf", "Menejer", "Taklif / shikoyat", "Mijoz holati", "Qo'ng'iroq"]];
			((this.tel && this.tel.takliflar) || []).forEach((t) => rows.push([
				String(t.sana || "").slice(0, 16), t.student_name, t.sinf, t.menejer,
				(t.matn || "").replace(/\n/g, " "), t.holat, t.qongiroq]));
		}
		const csv = rows.map((r) => r.map((c) => `"${String(c == null ? "" : c).replace(/"/g, '""')}"`).join(",")).join("\n");
		const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
		const a = document.createElement("a");
		a.href = URL.createObjectURL(blob);
		a.download = `sotuv-${nom}-${this.state.from_date}_${this.state.to_date}.csv`;
		a.click();
	}
};
