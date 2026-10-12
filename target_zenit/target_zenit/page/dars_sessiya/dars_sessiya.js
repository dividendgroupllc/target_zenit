// Copyright (c) 2026, Target Zenit — Dars sessiyasi (o'qituvchi kokpiti)
// Bitta ekranda dars uchun kerak bo'lgan HAMMA narsa:
//   CHAP  = o'quvchilar (rasm + chorak ballari + trend + rang) va tez baho/davomat keypad
//   O'NG  = oldingi dars (mavzu/kim yo'q edi) + o'quv reja mavzular + uy vazifa (va tekshirish)
//   TEPA  = ‹ oldingi dars / keyingi dars › navigatsiya, guruh almashtirgich, dars taymeri
// Klaviatura: ↑↓ o'quvchi · raqam = baho · K kechikdi · H yo'q · S kasal · Q qatnashmadi · Esc
// Kirish: frappe.set_route("dars-sessiya", jadval_yozuvi, sana)
frappe.pages["dars-sessiya"].on_page_load = function (wrapper) {
	new TZDarsSessiya(wrapper);
};

const DS_SES = "target_zenit.dars_jadvali.sessiya";
const DS_BAH = "target_zenit.dars_jadvali.baholash";
const DS_REJA = "target_zenit.oquv_reja";

class TZDarsSessiya {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dars sessiyasi"), single_column: true });
		this.sel = -1;      // klaviatura uchun tanlangan o'quvchi
		this.make_skeleton();
		this.readRoute();
		$(document).on("click.tzds", (e) => { if (!$(e.target).closest(".kp, .st-card").length) this.closeKp(); });
		$(document).on("keydown.tzds", (e) => this.onKey(e));
	}
	destroy() { $(document).off(".tzds"); if (this.timer) clearInterval(this.timer); }

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	dmy(s) { const p = String(s || "").slice(0, 10).split("-"); return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : ""; }
	bosh(n) { return String(n || "").trim().split(/\s+/).map((w) => w[0] || "").slice(0, 2).join("").toUpperCase(); }
	trendBelgi(t) { return t > 0 ? `<span class="tr up" title="o'sish">▲</span>` : (t < 0 ? `<span class="tr dn" title="pasayish">▼</span>` : ""); }

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-ds"><div class="loading">Yuklanmoqda…</div></div>`).appendTo(this.wrapper.find(".layout-main-section"));
	}
	readRoute() {
		const r = frappe.get_route();
		this.jy = r[1]; this.sana = r[2];
		if (!this.jy) { this.body.html(`<div class="empty">Dars tanlanmagan. «Mening jadvalim»dan oching.</div>`); return; }
		this.load();
	}
	otganKun() {
		const s = String((this.d && this.d.dars && this.d.dars.sana) || "").slice(0, 10);
		return s && s !== frappe.datetime.get_today();
	}
	// Dars kunlari bo'yicha surish (ustunlar = chorakdagi dars kunlari, yangisidan eskisiga)
	kunSurish(yon) {
		const cur = String(this.d.dars.sana).slice(0, 10);
		const kunlar = (this.d.ustunlar || []).map((u) => u.sana);
		if (!kunlar.length) { this.goTo(this.jy, frappe.datetime.add_days(cur, yon * 7)); return; }
		const i = kunlar.indexOf(cur);
		// kunlar xronologik: [0] = eng eski, oxirgisi = bugun
		const yangi = yon < 0 ? kunlar[i - 1] : kunlar[i + 1];
		if (!yangi) { frappe.show_alert({ message: yon < 0 ? "Bundan oldin dars yo'q" : "Bundan keyin dars yo'q", indicator: "orange" }); return; }
		this.goTo(this.jy, yangi);
	}

	// Boshqa darsга o'tish (sahifani qayta yuklamasdan)
	goTo(jy, sana) {
		if (!jy) return;
		this.jy = jy; this.sana = sana || this.sana; this.sel = -1;
		frappe.set_route("dars-sessiya", this.jy, this.sana);
		this.load();
	}
	load() {
		frappe.call({
			method: `${DS_SES}.sessiya_malumot`, args: { jadval_yozuvi: this.jy, sana: this.sana },
			callback: (r) => { this.d = r.message; this.render(); },
			error: () => this.body.html(`<div class="empty">Xatolik</div>`),
		});
	}

	// ---------------------------------------------------------------- umumiy karkas
	render() {
		const d = this.d; if (!d) return;
		const x = d.dars;
		const s = d.sozlamalar || {};
		const nav = d.navigatsiya || {};
		const legend = [
			`<span class="lg keldi">keldi</span>`,
			`<span class="lg b">baho</span>`,
			s.kechikish_yoqilgan ? `<span class="lg kech">K kechikdi</span>` : "",
			`<span class="lg h">H yo'q</span>`,
			`<span class="lg k">S kasal</span>`,
			`<span class="lg q">Q</span>`,
		].join("");

		this.body.html(`
			<div class="ds-head">
				<button class="back" title="Mening jadvalim">‹‹</button>
				<button class="nav-prev" ${nav.oldingi ? "" : "disabled"} title="${nav.oldingi ? this.esc(nav.oldingi.fan + " · " + (nav.oldingi.guruh_nomi || "")) : "oldingi dars yo'q"}">‹ Oldingi</button>
				<div class="ds-ttl">
					<div class="ds-title">
						${this.esc(x.fan)}
						<select class="ds-guruh" title="bugungi darslaringiz">
							${(nav.darslar || []).map((n) => `<option value="${this.esc(n.jadval_yozuvi)}" ${n.joriy ? "selected" : ""}>${this.esc(n.guruh_nomi || n.guruh)} · ${n.dars_raqami}-dars · ${this.esc(n.fan)}</option>`).join("") || `<option selected>${this.esc(x.guruh_nomi)}</option>`}
						</select>
					</div>
					<div class="ds-meta">
						<span class="kun-nav">
							<button class="kun-prev" title="oldingi dars kuni">‹</button>
							<input type="date" class="kun-sana" value="${this.esc(String(x.sana).slice(0, 10))}" title="dars kunini tanlash">
							<button class="kun-next" title="keyingi dars kuni">›</button>
						</span>
						${this.esc(x.kun)} · ${this.esc(x.boshlanish)}–${this.esc(x.tugash)} (${x.dars_raqami}-dars)${x.xona ? ` · ${this.esc(x.xona)}` : ""}${d.chorak ? ` · <span class="ch">${this.esc(d.chorak)}</span>` : ""}
						${this.otganKun() ? `<span class="ds-past">o'tgan kun — jurnalni to'ldirish mumkin <button class="kun-bugun">bugunga qaytish</button></span>` : ""}
						<span class="ds-timer"></span>
					</div>
				</div>
				<button class="nav-next" ${nav.keyingi ? "" : "disabled"} title="${nav.keyingi ? this.esc(nav.keyingi.fan + " · " + (nav.keyingi.guruh_nomi || "")) : "keyingi dars yo'q"}">Keyingi ›</button>
				<div class="ds-legend">${legend}</div>
			</div>
			${d.tuzatish_mumkin ? "" : `<div class="ds-lock">🔒 Bu darsning bahosini o'zgartirish muddati o'tgan (${s.tuzatish_muddati_kun} kun). Zavuchga murojaat qiling.</div>`}
			<div class="ds-grid">
				<div class="ds-left card"></div>
				<div class="ds-right">
					<div class="card sec-oldingi"></div>
					<div class="card sec-reja"></div>
					<div class="card sec-uv"></div>
				</div>
			</div>
		`);
		this.body.find(".back").on("click", () => frappe.set_route("mening-jadvalim"));
		this.body.find(".nav-prev").on("click", () => nav.oldingi && this.goTo(nav.oldingi.jadval_yozuvi, nav.sana));
		this.body.find(".nav-next").on("click", () => nav.keyingi && this.goTo(nav.keyingi.jadval_yozuvi, nav.sana));
		this.body.find(".ds-guruh").on("change", (e) => this.goTo(e.target.value, nav.sana));
		this.body.find(".kun-sana").on("change", (e) => { if (e.target.value) this.goTo(this.jy, e.target.value); });
		this.body.find(".kun-prev").on("click", () => this.kunSurish(-1));
		this.body.find(".kun-next").on("click", () => this.kunSurish(1));
		this.body.find(".kun-bugun").on("click", () => this.goTo(this.jy, frappe.datetime.get_today()));
		this.renderStudents();
		this.renderOldingi();
		this.renderReja();
		this.renderUV();
		this.startTimer();
	}

	// Dars taymeri — «tugashiga N daq» (faqat bugungi dars uchun)
	startTimer() {
		if (this.timer) clearInterval(this.timer);
		const x = this.d.dars;
		const bugun = frappe.datetime.get_today();
		if (String(x.sana).slice(0, 10) !== bugun || !x.boshlanish || !x.tugash) return;
		const mins = (t) => { const p = String(t).split(":"); return (+p[0]) * 60 + (+p[1] || 0); };
		const tick = () => {
			const now = new Date();
			const cur = now.getHours() * 60 + now.getMinutes();
			const b = mins(x.boshlanish), e = mins(x.tugash);
			let txt = "";
			if (cur < b) txt = `<span class="tm soon">⏱ ${b - cur} daq keyin boshlanadi</span>`;
			else if (cur <= e) txt = `<span class="tm live">⏱ HOZIR — tugashiga ${e - cur} daq</span>`;
			else txt = `<span class="tm past">dars tugagan</span>`;
			this.body.find(".ds-timer").html(" · " + txt);
		};
		tick();
		this.timer = setInterval(tick, 30000);
	}

	// ---------- CHAP: jurnal — o'quvchilar ketma-ket + chorak baholari katak-katak ----------
	// Ustunlar: eng yangisi (bugun) chapda, keyin kecha, undan oldingi…  Har katak bosilsa
	// shu kun uchun baho/davomat qo'yish keypad'i chiqadi (muddat sozlamasiga bo'ysunadi).
	katakHolat(k) {
		if (!k) return { cls: "", mark: "" };
		const t = k.davomat;
		if (t === "Kelmadi") return { cls: "s-h", mark: "H" };
		if (t === "Kasal") return { cls: "s-k", mark: "S" };
		if (t === "Qatnashmadi") return { cls: "s-q", mark: "Q" };
		if (t === "Kechikdi") return { cls: "s-kech", mark: k.baho != null && k.baho !== 0 ? String(k.baho) : "K" };
		if (k.baho) return { cls: "s-b", mark: String(k.baho) };
		return { cls: "", mark: "" };
	}
	// Bugungi katak (o'quvchi obyektidagi joriy holatdan)
	bugunKatak(o) {
		if (!o.davomat && o.baho == null) return null;
		return { baho: o.baho, davomat: o.davomat, kechikish_min: o.kechikish_min, baho_turi: o.baho_turi };
	}
	katakTitle(u, k) {
		const q = [`${this.dmy(u.sana)}`];
		if (u.mavzu) q.push(u.mavzu);
		if (k) {
			q.push(k.davomat === "Kechikdi" && k.kechikish_min ? `Kechikdi ${k.kechikish_min} daq` : k.davomat);
			if (k.baho) q.push(`baho ${k.baho}${k.baho_turi ? " · " + k.baho_turi : ""}`);
			if (k.izoh) q.push(k.izoh);
		}
		return q.filter(Boolean).join(" · ");
	}

	renderStudents() {
		const oq = this.d.oquvchilar || [];
		this.cols = this.d.ustunlar || [];
		this.bugunIdx = this.cols.findIndex((c) => c.bugun);
		if (!oq.length) { this.body.find(".ds-left").html(`<div class="sec-t">O'quvchilar</div><div class="empty">Ro'yxat yo'q</div>`); return; }
		oq.forEach((o) => { o.bugun_davomat = o.davomat; o.bugun_baho = o.baho; });

		// Har ustun uchun dars (jadval yozuvi) — o'tgan kun katagini saqlash uchun kerak
		this.colJy = this.cols.map((u, ci) => {
			for (const o of oq) {
				const k = (o.kataklar || [])[ci];
				if (k && k.jadval_yozuvi) return k.jadval_yozuvi;
			}
			return u.jadval_yozuvi || this.jy;
		});

		const kelmagan = oq.filter((o) => ["Kelmadi", "Kasal", "Qatnashmadi"].includes(o.davomat)).length;
		const kech = oq.filter((o) => o.davomat === "Kechikdi").length;
		const bahol = oq.filter((o) => o.baho).length;

		this.body.find(".ds-left").html(`
			<div class="sec-t">Jurnal <span class="mini">(${oq.length} o'quvchi) · bugun: ${bahol} baho · yo'q ${kelmagan}${kech ? ` · kechikkan ${kech}` : ""} — katakka bosib qo'yiladi, ↑↓ va raqamlar bilan ham</span></div>
			<div class="jr-wrap">
				<table class="jr">
					<thead><tr>
						<th class="c-no">№</th>
						<th class="c-nm">O'quvchi</th>
						<th class="c-avg" title="chorak o'rtachasi va trend">O'rt</th>
						${this.cols.map((u) => `<th class="c-d ${u.bugun ? "bugun" : ""} ${u.tahrir ? "" : "qulf"} ${u.kelajak ? "kel" : ""}"
							title="${this.esc([this.dmy(u.sana), u.mavzu, u.tahrir ? "" : "muddat o'tgan — zavuch tuzatadi"].filter(Boolean).join(" · "))}">
							<span class="c-dd">${this.esc(u.label)}</span>
							<span class="c-dl">${u.haqiqiy_bugun ? "bugun" : (u.tahrir ? (u.mavzu ? "✓" : "") : "🔒")}</span>
						</th>`).join("")}
						<th class="c-sp"></th>
					</tr></thead>
					<tbody>${oq.map((o, i) => this.rowHtml(o, i)).join("")}</tbody>
				</table>
			</div>`);
		this.bindRows();
		// Bugun (yoki tanlangan kun) eng o'ngda — jurnalni o'sha yerga surib qo'yamiz
		setTimeout(() => {
			const w = this.body.find(".jr-wrap")[0];
			if (!w) return;
			const $b = this.body.find(`.jr th.c-d.bugun`);
			if ($b.length) {
				const off = $b[0].offsetLeft - w.clientWidth + $b[0].offsetWidth + 24;
				w.scrollLeft = Math.max(0, off);
			} else {
				w.scrollLeft = w.scrollWidth;
			}
		}, 30);
	}

	rowHtml(o, i) {
		const avg = o.chorak_ortacha != null ? o.chorak_ortacha : "—";
		const rasm = o.rasm ? `<img src="${this.esc(o.rasm)}" alt="">` : `<span class="ini">${this.esc(this.bosh(o.student_name))}</span>`;
		const fl = (o.bayroqlar || []).length
			? `<span class="st-fl" title="${this.esc((o.bayroqlar || []).join(" · "))}">🚩${o.bayroqlar.length}</span>` : "";
		return `<tr class="jr-r r-${this.esc(o.rang || "yashil")} ${i === this.sel ? "sel" : ""}" data-i="${i}">
			<td class="c-no">${o.roll || i + 1}</td>
			<td class="c-nm">
				<span class="st-ph">${rasm}</span>
				<span class="nm-t">${this.esc(o.student_name)}</span>
				${fl}
				<button class="st-i" title="o'quvchi kartasi">i</button>
			</td>
			<td class="c-avg"><b>${avg}</b>${this.trendBelgi(o.trend)}${o.davomat_foiz != null ? `<span class="st-dv" title="davomat">${o.davomat_foiz}%</span>` : ""}</td>
			${this.cols.map((u, ci) => {
				const k = u.bugun ? this.bugunKatak(o) : (o.kataklar || [])[ci];
				const h = this.katakHolat(k);
				return `<td class="c-k ${h.cls} ${u.bugun ? "bugun" : ""} ${u.tahrir ? "" : "qulf"}" data-i="${i}" data-c="${ci}" title="${this.esc(this.katakTitle(u, k))}">${h.mark || "<span class='dot'>·</span>"}</td>`;
			}).join("")}
			<td class="c-sp"></td>
		</tr>`;
	}

	bindRows() {
		const self = this;
		this.body.find(".jr-r .c-k").on("click", function (e) {
			e.stopPropagation();
			const $c = $(this);
			self.sel = Number($c.data("i"));
			self.selCol = Number($c.data("c"));
			self.markSel();
			self.openKp($c);
		});
		// Ism / o'rtacha ustiga bosilsa — o'quvchi haqida TO'LIQ ma'lumot
		this.body.find(".jr-r .c-nm, .jr-r .c-avg, .jr-r .c-no").on("click", function (e) {
			if ($(e.target).closest(".st-i").length) return;
			const i = Number($(this).closest(".jr-r").data("i"));
			self.sel = i; self.markSel();
			self.oquvchiKarta(i);
		});
		this.body.find(".st-i").on("click", function (e) {
			e.stopPropagation();
			self.oquvchiKarta(Number($(this).closest(".jr-r").data("i")));
		});
	}

	refreshCard(i) {
		const o = this.d.oquvchilar[i];
		this.body.find(`.jr-r[data-i="${i}"]`).replaceWith(this.rowHtml(o, i));
		this.bindRows();
	}
	markSel() {
		this.body.find(".jr-r").removeClass("sel");
		this.body.find(".c-k").removeClass("selk");
		if (this.sel >= 0) {
			const $r = this.body.find(`.jr-r[data-i="${this.sel}"]`).addClass("sel");
			if (this.selCol != null) this.body.find(`.c-k[data-i="${this.sel}"][data-c="${this.selCol}"]`).addClass("selk");
			if ($r.length && $r[0].scrollIntoView) $r[0].scrollIntoView({ block: "nearest" });
		}
	}

	// ---------- Klaviatura (dunyo tizimlaridagi tezlik) ----------
	onKey(e) {
		if (!this.d || !(this.d.oquvchilar || []).length) return;
		if ($(e.target).is("input, textarea, select")) return;
		const n = this.d.oquvchilar.length;
		const s = this.d.sozlamalar || {};
		const k = e.key;
		if (this.selCol == null) this.selCol = this.bugunIdx;
		if (k === "ArrowDown") { this.sel = Math.min(n - 1, this.sel + 1); this.markSel(); e.preventDefault(); return; }
		if (k === "ArrowUp") { this.sel = Math.max(0, this.sel - 1); this.markSel(); e.preventDefault(); return; }
		if (k === "ArrowRight") { this.selCol = Math.min((this.cols || []).length - 1, (this.selCol || 0) + 1); this.markSel(); e.preventDefault(); return; }
		if (k === "ArrowLeft") { this.selCol = Math.max(0, (this.selCol || 0) - 1); this.markSel(); e.preventDefault(); return; }
		if (k === "Escape") { this.closeKp(); return; }
		if (this.sel < 0) return;
		const keyingi = () => { this.sel = Math.min(n - 1, this.sel + 1); this.markSel(); };
		const joriy = () => {
			const o = this.d.oquvchilar[this.sel];
			const kt = this.selCol === this.bugunIdx ? this.bugunKatak(o) : (o.kataklar || [])[this.selCol];
			return (kt && kt.davomat === "Kechikdi") ? "Kechikdi" : "Keldi";
		};
		if (/^[0-9]$/.test(k)) {
			const b = Number(k);
			if (b >= 1 && b <= (s.max_baho || 5)) { this.saveCell(this.sel, joriy(), b, null, keyingi); e.preventDefault(); }
			return;
		}
		const kl = k.toLowerCase();
		if (kl === "h") { this.saveCell(this.sel, "Kelmadi", null, null, keyingi); e.preventDefault(); }
		else if (kl === "s") { this.saveCell(this.sel, "Kasal", null, null, keyingi); e.preventDefault(); }
		else if (kl === "q") { this.saveCell(this.sel, "Qatnashmadi", null, null, keyingi); e.preventDefault(); }
		else if (kl === "k" && s.kechikish_yoqilgan) { this.saveCell(this.sel, "Kechikdi", null, s.kechikish_daqiqa, keyingi); e.preventDefault(); }
		else if (kl === "c") { this.saveCell(this.sel, "Keldi", null, null, keyingi); e.preventDefault(); }
		else if (k === "Delete" || k === "Backspace") { this.saveCell(this.sel, "Keldi", null, null, null); e.preventDefault(); }
		else if (k === "Enter") { keyingi(); e.preventDefault(); }
	}

	// ---------- Keypad ----------
	closeKp() { $(".kp").remove(); }
	openKp($cell) {
		this.closeKp();
		const i = Number($cell.data("i"));
		const ci = Number($cell.data("c"));
		if (this.cols[ci] && !this.cols[ci].tahrir) {
			frappe.show_alert({ message: `${this.dmy(this.cols[ci].sana)} — tuzatish muddati o'tgan`, indicator: "orange" });
			return;
		}
		const o = this.d.oquvchilar[i]; const self = this;
		const s = this.d.sozlamalar || {};
		const u = (this.cols || [])[ci] || {};
		const kt = u.bugun ? this.bugunKatak(o) : (o.kataklar || [])[ci];
		const max = s.max_baho || 5;
		const turlar = this.d.baho_turlari || [];
		const bahoTugma = max <= 10
			? Array.from({ length: max }, (_, n) => max - n).filter((b) => b >= 2)
				.map((b) => `<button class="kp-b" data-b="${b}">${b}</button>`).join("")
			: "";
		const kp = $(`<div class="kp">
			<div class="kp-nm">${this.esc(o.student_name)}
				<span class="mini">${u.bugun ? "bugun" : this.dmy(u.sana)}${o.chorak_ortacha != null ? ` · o'rtacha ${o.chorak_ortacha}` : ""}</span></div>
			${u.mavzu ? `<div class="kp-mv mini">${this.esc(u.mavzu)}</div>` : ""}
			<div class="kp-row kp-bahos">${bahoTugma}<input type="number" class="kp-in" min="1" max="${max}" placeholder="ball…"></div>
			${turlar.length ? `<div class="kp-row kp-turlar"><select class="kp-turi"><option value="">— baho turi —</option>${turlar.map((t) => `<option value="${this.esc(t.name)}" ${kt && kt.baho_turi === t.name ? "selected" : ""}>${this.esc(t.name)}${t.vazn && t.vazn !== 1 ? ` (×${t.vazn})` : ""}</option>`).join("")}</select></div>` : ""}
			<div class="kp-row kp-dav">
				<button class="kp-d keldi" data-d="Keldi">✓ Keldi</button>
				${s.kechikish_yoqilgan ? `<button class="kp-d kech" data-d="Kechikdi">K</button><input type="number" class="kp-kech" min="1" max="60" placeholder="daq" value="${this.esc((kt && kt.kechikish_min) || s.kechikish_daqiqa || "")}" title="necha daqiqa kechikdi">` : ""}
				<button class="kp-d h" data-d="Kelmadi">H</button>
				<button class="kp-d k" data-d="Kasal">S</button>
				<button class="kp-d q" data-d="Qatnashmadi">Q</button>
			</div>
			<div class="kp-row kp-foot"><button class="kp-clear">tozalash</button>
				<span class="kp-hint">raqam = baho · K · H · S · Q · ↑↓ ← →</span></div>
		</div>`).appendTo(this.body);
		const r = $cell[0].getBoundingClientRect(); const br = this.body[0].getBoundingClientRect();
		kp.css({
			top: (r.bottom - br.top + 4) + "px",
			left: Math.min(Math.max(0, r.left - br.left - 60), Math.max(0, br.width - 290)) + "px",
		});
		const turi = () => kp.find(".kp-turi").val() || null;
		const hol = () => (kt && kt.davomat === "Kechikdi") ? "Kechikdi" : "Keldi";
		kp.find(".kp-b").on("click", function () {
			self.saveCell(i, hol(), Number($(this).data("b")), kt && kt.kechikish_min, null, turi(), ci);
		});
		kp.find(".kp-in").on("keydown", function (e) {
			if (e.key === "Enter") { const v = Number($(this).val()); if (v) self.saveCell(i, hol(), v, null, null, turi(), ci); }
		});
		kp.find(".kp-d").on("click", function () {
			const dv = $(this).data("d");
			const kech = dv === "Kechikdi" ? (Number(kp.find(".kp-kech").val()) || null) : null;
			self.saveCell(i, dv, dv === "Kechikdi" ? (kt && kt.baho) : null, kech, null, turi(), ci);
		});
		kp.find(".kp-clear").on("click", () => self.saveCell(i, "Keldi", null, null, null, null, ci));
		kp.find(".kp-in").focus();
	}

	// Optimistik saqlash: avval ekran, keyin server (xato bo'lsa qaytariladi)
	saveCell(i, davomat, baho, kechikish_min, keyin, baho_turi, ci) {
		const self = this; const o = this.d.oquvchilar[i];
		if (ci == null) ci = (this.selCol != null ? this.selCol : this.bugunIdx);
		const u = (this.cols || [])[ci];
		if (!u) return;
		const bugunmi = !!u.bugun;
		if (!u.tahrir) {
			frappe.show_alert({ message: `${this.dmy(u.sana)} — tuzatish muddati o'tgan, zavuchga murojaat qiling`, indicator: "red" });
			return;
		}
		const eski = bugunmi
			? { davomat: o.davomat, baho: o.baho, kechikish_min: o.kechikish_min, baho_turi: o.baho_turi }
			: JSON.parse(JSON.stringify((o.kataklar || [])[ci] || null));

		const yangi = {
			davomat: davomat,
			baho: ["Keldi", "Kechikdi"].includes(davomat) ? (baho != null ? baho : null) : null,
			kechikish_min: kechikish_min || null,
			baho_turi: baho_turi || (eski && eski.baho_turi) || null,
			jadval_yozuvi: (eski && eski.jadval_yozuvi) || this.colJy[ci] || this.jy,
			izoh: eski && eski.izoh,
		};
		if (bugunmi) {
			o.davomat = yangi.davomat; o.baho = yangi.baho;
			o.kechikish_min = yangi.kechikish_min; o.baho_turi = yangi.baho_turi;
			o.bugun_davomat = o.davomat; o.bugun_baho = o.baho;
		}
		if (!o.kataklar) o.kataklar = [];
		o.kataklar[ci] = (yangi.davomat === "Keldi" && yangi.baho == null) ? null : yangi;
		this.refreshCard(i);
		this.closeKp();
		if (keyin) keyin();

		frappe.call({
			method: `${DS_BAH}.natija_saqla`,
			args: {
				jadval_yozuvi: yangi.jadval_yozuvi, sana: u.sana,
				qatorlar: JSON.stringify([{
					student: o.student, davomat: yangi.davomat, baho: yangi.baho,
					kechikish_min: yangi.kechikish_min, baho_turi: yangi.baho_turi,
				}]),
			},
			callback: () => { if (!bugunmi) self.yangilaOrtacha(); },
			error: () => {
				if (bugunmi) {
					Object.assign(o, eski);
					o.bugun_davomat = o.davomat; o.bugun_baho = o.baho;
				}
				o.kataklar[ci] = eski;
				self.refreshCard(i);
				frappe.show_alert({ message: "Saqlanmadi — qaytarildi", indicator: "red" });
			},
		});
	}
	// O'tgan kun o'zgarsa — o'rtacha/trend qayta hisoblanishi uchun jim yangilash
	yangilaOrtacha() {
		if (this.ortachaTimer) clearTimeout(this.ortachaTimer);
		this.ortachaTimer = setTimeout(() => this.load(), 1200);
	}

	// ---------- O'quvchi haqida TO'LIQ ma'lumot ----------
	// Qachon, qaysi fandan, qaysi darsда, QAYSI MAVZU uchun qanday baho olgani —
	// davomat, kechikish, uy vazifa va fan bo'yicha xulosa bilan birga.
	oquvchiKarta(i) {
		const o = this.d.oquvchilar[i];
		const self = this;
		const dlg = new frappe.ui.Dialog({ title: o.student_name, size: "extra-large" });
		dlg.$body.html(`<div class="ds-ok2"><div class="loading">Yuklanmoqda…</div></div>`);
		dlg.show();
		frappe.call({
			method: `${DS_BAH}.oquvchi_toliq`,
			args: { student: o.student },
			callback: (r) => {
				const d = r.message;
				if (!d) { dlg.$body.find(".ds-ok2").html(`<div class="empty">Ma'lumot yo'q</div>`); return; }
				self.kartaRender(dlg, d, o);
			},
			error: () => dlg.$body.find(".ds-ok2").html(`<div class="empty">Xatolik</div>`),
		});
	}

	kartaRender(dlg, d, o) {
		const self = this;
		const st = d.student || {};
		const u = d.umumiy || {};
		const rasm = st.image || o.rasm;
		const kpi = (b, m, cls) => `<div class="kpi ${cls || ""}"><b>${b}</b><span>${m}</span></div>`;
		const bayroq = (u.bayroqlar || []).map((b) => `<span class="fl">${this.esc(b)}</span>`).join("");

		dlg.$body.find(".ds-ok2").html(`
			<div class="ok2-top">
				<div class="ok2-ph">${rasm ? `<img src="${this.esc(rasm)}">` : `<span class="ini">${this.esc(this.bosh(st.student_name || o.student_name))}</span>`}</div>
				<div class="ok2-id">
					<div class="ok2-nm">${this.esc(st.student_name || o.student_name)}</div>
					<div class="ok2-sub">
						${(d.guruhlar || []).map((g) => `<span class="gz">${this.esc(g.nomi)}${g.roll ? ` · №${g.roll}` : ""}</span>`).join("")}
						${st.student_mobile_number ? `<span class="gz">📞 ${this.esc(st.student_mobile_number)}</span>` : ""}
						${st.date_of_birth ? `<span class="gz">🎂 ${this.esc(this.dmy(st.date_of_birth))}</span>` : ""}
					</div>
					${(d.vasiylar || []).length ? `<div class="ok2-sub mini">Ota-ona: ${(d.vasiylar).map((v) => `${this.esc(v.ism)}${v.aloqa ? ` (${this.esc(v.aloqa)})` : ""}${v.tel ? ` — ${this.esc(v.tel)}` : ""}`).join(" · ")}</div>` : ""}
				</div>
				<div class="ok2-kpi">
					${kpi(u.ortacha != null ? u.ortacha : "—", `umumiy o'rtacha ${this.trendBelgi(u.trend)}`, u.rang ? "r-" + u.rang : "")}
					${kpi(u.davomat_foiz != null ? u.davomat_foiz + "%" : "—", "davomat")}
					${kpi((d.tarix || []).filter((t) => ["Kelmadi", "Kasal", "Qatnashmadi"].includes(t.davomat)).length, "yo'qlik")}
					${kpi((d.tarix || []).filter((t) => t.davomat === "Kechikdi").length, "kechikish")}
					${kpi((d.uy_vazifalar || []).filter((x) => x.holat === "Bajarmadi").length, "uy vazifa yo'q")}
					${kpi((d.tarix || []).filter((t) => t.baho).length, "jami baho")}
				</div>
			</div>
			${bayroq ? `<div class="ok2-fl">${bayroq}</div>` : ""}

			<div class="ok2-t">Fanlar bo'yicha <span class="mini">qatorga bosib tarixni shu fanга filtrlang</span></div>
			<div class="ok2-tbl">
				<table class="ok2-fan">
					<thead><tr><th>Fan</th><th>So'nggi ballar</th><th>O'rtacha</th><th>Davomat</th><th>Yo'q</th><th>Kech</th><th>UV yo'q</th><th>Chorak</th></tr></thead>
					<tbody>${(d.fanlar || []).map((f) => {
						const ch = (d.chorak_baholari || []).filter((c) => c.fan === f.fan);
						return `<tr class="fan-r r-${this.esc(f.rang)}" data-fan="${this.esc(f.fan)}">
							<td class="f-nm">${this.esc(f.fan)}</td>
							<td class="f-bl">${(f.ballar || []).map((b) => `<span class="bq">${b}</span>`).join("") || "<span class='mini'>—</span>"}</td>
							<td class="f-av"><b>${f.ortacha != null ? f.ortacha : "—"}</b>${this.trendBelgi(f.trend)}</td>
							<td>${f.davomat_foiz != null ? f.davomat_foiz + "%" : "—"}</td>
							<td>${f.yoqlik || ""}</td>
							<td>${f.kechikish || ""}</td>
							<td>${f.uv_bajarmagan || ""}</td>
							<td>${ch.map((c) => `<span class="chb" title="${this.esc(c.chorak)}${c.qolda ? " (qo'lda)" : ""}">${c.baho}</span>`).join("") || "<span class='mini'>—</span>"}</td>
						</tr>`;
					}).join("") || `<tr><td colspan="8" class="mini">Yozuv yo'q</td></tr>`}</tbody>
				</table>
			</div>

			<div class="ok2-t">Baholar va davomat tarixi
				<span class="mini">qachon · qaysi fandan · qaysi darsда · qaysi mavzu uchun</span>
				<span class="ok2-filtr">
					<select class="f-fan"><option value="">hamma fan</option>${(d.fanlar || []).map((f) => `<option value="${this.esc(f.fan)}">${this.esc(f.fan)}</option>`).join("")}</select>
					<select class="f-chorak"><option value="">hamma chorak</option>${(d.choraklar || []).map((c) => `<option value="${this.esc(c.name)}">${this.esc(c.term_name || c.name)}</option>`).join("")}</select>
					<label class="f-only"><input type="checkbox" class="f-baho"> faqat baholar</label>
				</span>
			</div>
			<div class="ok2-tbl ok2-tarix"></div>

			${(d.uy_vazifalar || []).length ? `
			<div class="ok2-t">Uy vazifalar</div>
			<div class="ok2-tbl">
				<table class="ok2-uv">
					<thead><tr><th>Sana</th><th>Fan</th><th>Vazifa</th><th>Holat</th><th>Ball</th><th>Izoh</th></tr></thead>
					<tbody>${d.uy_vazifalar.map((x) => `<tr>
						<td class="nw">${this.esc(this.dmy(x.sana))}</td>
						<td>${this.esc(x.fan || "")}</td>
						<td>${this.esc((x.vazifa || "").slice(0, 90))}</td>
						<td class="uv-${this.esc((x.holat || "").toLowerCase())}">${this.esc(x.holat || "")}</td>
						<td class="nw">${x.ball != null ? x.ball : ""}${x.max_ball ? `/${x.max_ball}` : ""}</td>
						<td>${this.esc(x.izoh || "")}</td>
					</tr>`).join("")}</tbody>
				</table>
			</div>` : ""}

			<div class="ok2-act">
				<button class="btn btn-xs btn-default ok2-rep">📊 Baholar hisoboti</button>
				<button class="btn btn-xs btn-default ok2-form">👤 O'quvchi formasi</button>
			</div>
		`);

		// Tarix jadvali (filtrlanadigan)
		const tarixRender = () => {
			const fFan = dlg.$body.find(".f-fan").val();
			const fCh = dlg.$body.find(".f-chorak").val();
			const faqatBaho = dlg.$body.find(".f-baho").is(":checked");
			const rows = (d.tarix || []).filter((t) =>
				(!fFan || t.fan === fFan) && (!fCh || t.chorak === fCh) && (!faqatBaho || t.baho));
			dlg.$body.find(".ok2-tarix").html(`
				<table class="ok2-th">
					<thead><tr><th>Sana</th><th>Kun</th><th>Fan</th><th>Dars</th><th>Mavzu</th><th>Baho</th><th>Turi</th><th>Davomat</th><th>Izoh</th></tr></thead>
					<tbody>${rows.length ? rows.map((t) => `<tr class="${t.baho ? "has-b" : ""}">
						<td class="nw">${this.esc(this.dmy(t.sana))}</td>
						<td class="mini nw">${this.esc(t.kun || "")}</td>
						<td class="nw">${this.esc(t.fan || "")}</td>
						<td class="mini nw">${t.dars_raqami ? `${t.dars_raqami}-dars` : ""}${t.vaqt ? ` ${this.esc(t.vaqt)}` : ""}${t.guruh_nomi ? `<br>${this.esc(t.guruh_nomi)}` : ""}</td>
						<td>${t.mavzu ? `${t.mavzu_tartib ? `<span class="mt">${t.mavzu_tartib}.</span>` : ""}${this.esc(t.mavzu)}` : `<span class="mini">—</span>`}</td>
						<td class="b-c">${t.baho ? `<span class="bq big">${t.baho}</span>` : ""}</td>
						<td class="mini nw">${this.esc(t.baho_turi || "")}</td>
						<td class="nw dv dv-${this.esc((t.davomat || "").toLowerCase())}">${this.esc(t.davomat || "")}${t.davomat === "Kechikdi" && t.kechikish_min ? ` ${t.kechikish_min}daq` : ""}</td>
						<td class="mini">${this.esc(t.izoh || "")}</td>
					</tr>`).join("") : `<tr><td colspan="9" class="mini">Yozuv yo'q</td></tr>`}</tbody>
				</table>
				<div class="ok2-sum mini">${rows.length} yozuv · ${rows.filter((t) => t.baho).length} baho${rows.filter((t) => t.baho).length ? ` · o'rtacha ${(rows.filter((t) => t.baho).reduce((a, b) => a + b.baho, 0) / rows.filter((t) => t.baho).length).toFixed(1)}` : ""}</div>`);
		};
		tarixRender();
		dlg.$body.find(".f-fan, .f-chorak, .f-baho").on("change", tarixRender);
		dlg.$body.find(".fan-r").on("click", (e) => {
			dlg.$body.find(".f-fan").val($(e.currentTarget).data("fan"));
			tarixRender();
			dlg.$body.find(".ok2-tarix")[0].scrollIntoView({ block: "nearest", behavior: "smooth" });
		});
		dlg.$body.find(".ok2-rep").on("click", () => { dlg.hide(); frappe.set_route("baholar-hisoboti", { student: o.student }); });
		dlg.$body.find(".ok2-form").on("click", () => { dlg.hide(); frappe.set_route("Form", "Student", o.student); });
	}

	// ---------- O'NG 1: oldingi dars (nima o'tilgan, kim yo'q edi) ----------
	renderOldingi() {
		const p = this.d.oldingi;
		if (!p) { this.body.find(".sec-oldingi").html(`<div class="sec-t">Oldingi dars</div><div class="empty mini">Oldingi dars yozuvi yo'q</div>`); return; }
		const uv = p.uy_vazifa;
		this.body.find(".sec-oldingi").html(`
			<div class="sec-t">Oldingi dars <span class="mini">${this.esc(this.dmy(p.sana))}</span></div>
			<div class="ol-mavzu">${p.mavzu ? `📘 ${this.esc(p.mavzu)}` : `<span class="mini">mavzu belgilanmagan</span>`}${p.holat && p.holat !== "O'tildi" ? ` <span class="mini">(${this.esc(p.holat)})</span>` : ""}</div>
			${(p.yoq || []).length ? `<div class="ol-yoq"><span class="mini">o'tgan darsда yo'q edi:</span> ${p.yoq.map((y) => `<span class="yz">${this.esc(y.ism)}</span>`).join("")}</div>` : ""}
			${uv ? `<div class="ol-uv">
				<span class="mini">berilgan uy vazifa:</span> ${this.esc((uv.vazifa || "").slice(0, 120))}
				${uv.max_ball ? `<span class="uv-ball">${uv.max_ball}b</span>` : ""}
				${uv.tekshiriladi ? `<button class="btn-mini uv-check" data-uv="${this.esc(uv.name)}">✔️ Tekshirish</button>` : ""}
			</div>` : `<div class="ol-uv mini">oldingi darsда uy vazifa berilmagan</div>`}
		`);
		this.body.find(".uv-check").on("click", (e) => this.uvTekshirDialog($(e.currentTarget).data("uv")));
	}

	// ---------- Uy vazifani tekshirish dialogi (kim bajardi / ball) ----------
	uvTekshirDialog(uvName) {
		const self = this;
		frappe.call({
			method: `${DS_SES}.uy_vazifa_natijalari`, args: { uy_vazifa: uvName }, freeze: true,
			callback: (r) => {
				const d = r.message; if (!d) return;
				const dlg = new frappe.ui.Dialog({
					title: __("Uy vazifani tekshirish"), size: "large",
					primary_action_label: __("Saqlash"),
					primary_action: () => {
						const qatorlar = [];
						dlg.$body.find(".uvr").each(function () {
							const $r = $(this);
							qatorlar.push({
								student: $r.data("st"),
								holat: $r.find(".uv-h.act").data("h") || null,
								ball: $r.find(".uv-ball-in").val() || null,
							});
						});
						frappe.call({
							method: `${DS_SES}.uy_vazifa_natija_saqla`,
							args: { uy_vazifa: uvName, qatorlar: JSON.stringify(qatorlar) }, freeze: true,
							callback: () => {
								frappe.show_alert({ message: "Tekshiruv saqlandi", indicator: "green" });
								dlg.hide(); self.load();
							},
						});
					},
				});
				dlg.$body.html(`<div class="uv-dlg">
					<div class="uv-top"><b>${self.esc(d.vazifa || "")}</b>
						<span class="mini">${self.esc(self.dmy(d.sana))}${d.muddat ? ` → ${self.esc(self.dmy(d.muddat))}` : ""}${d.max_ball ? ` · max ${d.max_ball} ball` : ""} · tekshirilgan: ${d.tekshirilgan}/${d.jami}</span></div>
					<div class="uv-rows">${(d.qatorlar || []).map((q) => `
						<div class="uvr" data-st="${self.esc(q.student)}">
							<span class="uv-nm">${q.roll || ""}. ${self.esc(q.student_name)}</span>
							<span class="uv-hs">
								<button class="uv-h ${q.holat === "Bajardi" ? "act" : ""}" data-h="Bajardi">✓ bajardi</button>
								<button class="uv-h q ${q.holat === "Qisman" ? "act" : ""}" data-h="Qisman">~ qisman</button>
								<button class="uv-h n ${q.holat === "Bajarmadi" ? "act" : ""}" data-h="Bajarmadi">✕ yo'q</button>
							</span>
							<input type="number" class="uv-ball-in" min="0" max="${d.max_ball || 100}" placeholder="ball" value="${q.ball != null ? q.ball : ""}">
						</div>`).join("")}</div>
					<div class="uv-mass"><button class="btn btn-xs btn-default uv-all">Hammasi «bajardi»</button></div>
				</div>`);
				dlg.$body.find(".uv-h").on("click", function () {
					const $r = $(this).closest(".uvr");
					$r.find(".uv-h").removeClass("act"); $(this).addClass("act");
					if ($(this).data("h") === "Bajarmadi") $r.find(".uv-ball-in").val(0);
					else if ($(this).data("h") === "Bajardi" && !$r.find(".uv-ball-in").val() && d.max_ball) $r.find(".uv-ball-in").val(d.max_ball);
				});
				dlg.$body.find(".uv-all").on("click", () => {
					dlg.$body.find(".uvr").each(function () {
						const $r = $(this);
						$r.find(".uv-h").removeClass("act");
						$r.find(`.uv-h[data-h="Bajardi"]`).addClass("act");
						if (!$r.find(".uv-ball-in").val() && d.max_ball) $r.find(".uv-ball-in").val(d.max_ball);
					});
				});
				dlg.show();
			},
		});
	}

	// ---------- O'NG 2: o'quv reja — MAVZU HAR KUN UCHUN ALOHIDA ----------
	// Qaysi sanada turgan bo'lsangiz — o'sha kunning mavzusi ko'rinadi va saqlanadi.
	renderReja() {
		const reja = this.d.reja || {};
		const kunNomi = `${this.dmy(this.sana)}${this.d.dars && this.d.dars.kun ? " (" + this.esc(this.d.dars.kun) + ")" : ""}`;
		if (!reja.oquv_reja) {
			this.body.find(".sec-reja").html(`<div class="sec-t">O'quv reja</div>
				<div class="empty mini">Bu guruh va fan uchun mavzular hali biriktirilmagan.</div>
				<div class="mv-cta"><button class="btn-mini mavzu-biriktir">📘 Chorak mavzularini biriktirish</button>
				<div class="mini">Ro'yxatni ko'chirib joylashingiz yoki boshqa rejadan nusxa olishingiz mumkin</div></div>`);
			this.body.find(".mavzu-biriktir").on("click", () => this.mavzuDialog());
			return;
		}
		const mv = reja.mavzular || [];
		const keyingi = reja.keyingi;
		const bugun = reja.bugun || null;                 // SHU kunning yozuvi
		const sanalar = reja.mavzu_sanalar || {};          // qator -> [{sana, holat}]
		const joriy = String(this.sana).slice(0, 10);

		const list = mv.map((m) => {
			const kun = (sanalar[m.name] || []);
			const shuKun = kun.some((k) => k.sana === joriy);
			const boshqa = kun.filter((k) => k.sana !== joriy);
			const tt = kun.length ? `o'tilgan: ${kun.map((k) => this.dmy(k.sana) + (k.holat && k.holat !== "O'tildi" ? ` (${k.holat})` : "")).join(", ")}` : "";
			return `<div class="mv ${m.otildi ? "done" : ""} ${shuKun ? "shu-kun" : ""} ${!m.otildi && keyingi === m.name ? "next" : ""}"
				data-m="${this.esc(m.name)}" title="${this.esc(tt)}">
				<span class="mv-n">${m.tartib || ""}</span>
				<span class="mv-t">${this.esc(m.mavzu || "(bo'sh)")}${m.soat > 1 ? ` <span class="mini">${m.soat} soat</span>` : ""}</span>
				<span class="mv-s">${shuKun ? `<span class="shu">shu kun</span>`
					: (boshqa.length ? `<span class="oth">${this.esc(this.dmy(boshqa[boshqa.length - 1].sana))}</span>`
						: (keyingi === m.name ? "→" : ""))}</span>
			</div>`;
		}).join("");

		this.body.find(".sec-reja").html(`
			<div class="sec-t">O'quv reja <span class="mini">o'tilgan ${reja.otildi || 0}/${reja.jami || 0}</span></div>
			<div class="kun-mavzu ${bugun ? "bor" : "yoq"}">
				<div class="km-h">📅 <b>${kunNomi}</b> — shu kun mavzusi</div>
				${bugun ? `<div class="km-v">✅ ${this.esc(bugun.mavzu || "(mavzu nomi yo'q)")}
						${bugun.holat && bugun.holat !== "O'tildi" ? `<span class="km-hol">${this.esc(bugun.holat)}</span>` : ""}
						${bugun.izoh ? `<div class="mini">${this.esc(bugun.izoh)}</div>` : ""}</div>
					<div class="km-act"><button class="btn-mini ghost mavzu-ochir">🗑 Olib tashlash</button>
						<span class="mini">boshqasini tanlab «Belgilash»ni bossangiz — almashadi</span></div>`
				: `<div class="km-v yoq">⬜ Hali belgilanmagan — pastdan mavzuni tanlab «Belgilash»ni bosing</div>`}
			</div>
			<div class="mv-list">${list || "<div class='mini'>Mavzular yo'q</div>"}</div>
			<div class="mv-act">
				<b>${kunNomi}</b> uchun →
				<button class="btn-mini otdim">✅ Belgilash</button>
				<select class="mv-holat" title="qanday o'tildi">
					<option value="O'tildi">O'tildi</option>
					<option value="Qisman">Qisman</option>
					<option value="O'tilmadi">O'tilmadi</option>
				</select>
			</div>
			<div class="mv-act2">
				<button class="btn-mini alt mavzu-biriktir">📘 Mavzu qo'shish / almashtirish</button>
				<button class="btn-mini ghost reja-ochish">✏️ Rejani to'liq tahrirlash</button>
			</div>`);

		// Tanlov: shu kun yozuvi bo'lsa — o'sha, bo'lmasa keyingi o'tilmagan mavzu
		this.selMavzu = (bugun && bugun.reja_qatori) || keyingi || "";
		const hl = () => this.body.find(".mv").each((idx, el) => $(el).toggleClass("sel", $(el).data("m") === this.selMavzu));
		hl();
		this.body.find(".mv").on("click", (e) => { this.selMavzu = $(e.currentTarget).data("m"); hl(); });
		this.body.find(".otdim").on("click", () => {
			if (!this.selMavzu) { frappe.show_alert({ message: "Mavzu tanlang", indicator: "orange" }); return; }
			frappe.call({
				method: `${DS_REJA}.dars_otdim`,
				args: {
					jadval_yozuvi: this.jy, sana: this.sana, reja_qatori: this.selMavzu,
					holat: this.body.find(".mv-holat").val() || "O'tildi",
				}, freeze: true,
				callback: (r) => {
					if (r.message) {
						frappe.show_alert({ message: `${this.dmy(this.sana)} uchun mavzu belgilandi`, indicator: "green" });
						this.load();
					}
				},
			});
		});
		this.body.find(".mavzu-ochir").on("click", () => {
			frappe.confirm(`${this.dmy(this.sana)} kuni uchun belgilangan mavzu olib tashlanadimi?`, () => {
				frappe.call({
					method: `${DS_REJA}.mavzu_olib_tashla`,
					args: { jadval_yozuvi: this.jy, sana: this.sana }, freeze: true,
					callback: () => { frappe.show_alert({ message: "Olib tashlandi", indicator: "orange" }); this.load(); },
				});
			});
		});
		this.body.find(".mavzu-biriktir").on("click", () => this.mavzuDialog());
		this.body.find(".reja-ochish").on("click", () => frappe.set_route("Form", "Oquv Reja", reja.oquv_reja));
	}

	// ---------- O'NG 3: uy vazifa — HAR KUN UCHUN ALOHIDA ----------
	renderUV() {
		const uv = this.d.uy_vazifa || {}; const list = this.d.uy_vazifalar || [];
		const s = this.d.sozlamalar || {};
		const kunNomi = this.dmy(this.sana);
		const tarix = list.filter((u) => !u.bugungi).map((u) => `<div class="uv-item">
			<span class="uv-d">${this.esc(this.dmy(u.sana))}</span>
			<span class="uv-v">${this.esc(u.vazifa)}</span>
			${u.max_ball ? `<span class="uv-ball">${u.max_ball}b</span>` : ""}
			${u.fayl ? ` <a href="${this.esc(u.fayl)}" target="_blank">📄</a>` : ""}
			<button class="btn-mini uv-check2" data-uv="${this.esc(u.name)}" title="tekshirish">✔️</button>
			<button class="btn-mini ghost uv-kun" data-sana="${this.esc(u.sana)}" title="shu kunga o'tish">↗</button>
		</div>`).join("");
		this.body.find(".sec-uv").html(`
			<div class="sec-t">Uy vazifa <span class="mini">📅 ${this.esc(kunNomi)} kuni uchun${uv.name ? " · saqlangan" : " · hali berilmagan"}</span></div>
			<div class="uv-form ${uv.name ? "bor" : ""}">
				<textarea class="u-vazifa" rows="2" placeholder="${this.esc(kunNomi)} kuni berilgan uy vazifa…">${this.esc(uv.vazifa || "")}</textarea>
				<div class="urow">
					<input type="date" class="u-muddat" value="${this.esc(uv.muddat || "")}" title="topshirish muddati">
					<input type="number" class="u-ball" min="1" placeholder="ball" value="${uv.max_ball != null ? uv.max_ball : (s.uv_default_max_ball || "")}">
					<label class="u-tek" title="keyingi darsда «kim bajardi» ro'yxati chiqadi"><input type="checkbox" class="u-tekshir" ${(uv.name ? uv.tekshiriladi : s.uv_tekshirish) ? "checked" : ""}> tekshiriladi</label>
					<button class="btn-mini u-save">💾 Saqlash</button>
				</div>
				${uv.name ? `<div class="uv-prev">
					<button class="btn-mini uv-check2" data-uv="${this.esc(uv.name)}">✔️ Shu kun vazifasini tekshirish</button>
					<button class="btn-mini ghost uv-ochir">🗑 O'chirish</button>
				</div>` : ""}
			</div>
			${tarix ? `<div class="uv-t2">Chorakdagi boshqa kunlar</div><div class="uv-list">${tarix}</div>` : ""}`);
		this.body.find(".u-save").on("click", () => this.uvSaqla());
		this.body.find(".uv-ochir").on("click", () => {
			frappe.confirm(`${kunNomi} kuni uy vazifasi o'chiriladimi?`, () => {
				this.body.find(".u-vazifa").val("");
				this.uvSaqla();
			});
		});
		this.body.find(".uv-check2").on("click", (e) => this.uvTekshirDialog($(e.currentTarget).data("uv")));
		this.body.find(".uv-kun").on("click", (e) => this.goTo(this.jy, $(e.currentTarget).data("sana")));
	}

	uvSaqla() {
		frappe.call({
			method: `${DS_SES}.uy_vazifa_saqla`,
			args: {
				jadval_yozuvi: this.jy, sana: this.sana,
				vazifa: this.body.find(".u-vazifa").val(),
				muddat: this.body.find(".u-muddat").val() || undefined,
				max_ball: this.body.find(".u-ball").val() || undefined,
				tekshiriladi: this.body.find(".u-tekshir").is(":checked") ? 1 : 0,
			}, freeze: true,
			callback: (r) => {
				if (r.message) {
					frappe.show_alert({
						message: r.message.ochirildi ? "O'chirildi" : `${this.dmy(this.sana)} uchun saqlandi`,
						indicator: r.message.ochirildi ? "orange" : "green",
					});
					this.load();
				}
			},
		});
	}
}
