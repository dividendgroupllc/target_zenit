// Copyright (c) 2026, Target Zenit
// «Chorak mavzularini biriktirish» — o'qituvchi uchun tez yo'l.
// Ro'yxatni (Word/Excel/KTP'dan) ko'chirib joylaydi → tizim qatorlarga ajratadi →
// tahrirlab tasdiqlaydi. Yoki boshqa rejadan (o'tgan yil / parallel sinf) nusxa oladi.
//
// Chaqirish:  tz_mavzu_dialog({ fan, guruh, guruh_nomi, onsave })
// Hamma desk sahifasida mavjud (app_include_js).

(function () {
	const M = "target_zenit.oquv_reja";

	const CSS = `
	.tz-mv { font-size: 13px; }
	.tz-mv .mv-tabs { display: flex; gap: 6px; margin-bottom: 12px; }
	.tz-mv .mv-tab { border: 1px solid var(--border-color, #e1e5ea); background: transparent;
		border-radius: 9px; padding: 6px 13px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
	.tz-mv .mv-tab.act { background: #eef4ff; border-color: #bed0f7; color: #1e4fb8; }
	.tz-mv .mv-top { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }
	.tz-mv .mv-top label { display: flex; flex-direction: column; font-size: 11px;
		color: var(--text-muted, #8a9099); gap: 3px; }
	.tz-mv .mv-top select, .tz-mv .mv-top input { border: 1px solid var(--border-color, #e1e5ea);
		border-radius: 8px; padding: 5px 8px; font-size: 12.5px; min-width: 150px;
		background: var(--card-bg, #fff); color: inherit; }
	.tz-mv .mv-top input[type=number] { min-width: 72px; }
	.tz-mv .mv-gt { font-size: 12px; font-weight: 600; margin: 6px 0 5px; }
	.tz-mv .mv-hint { font-size: 11px; color: var(--text-muted, #8a9099); font-weight: 400; }
	.tz-mv .mv-glist { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
	.tz-mv .mv-g { display: flex; align-items: center; gap: 6px; border: 1px solid var(--border-color, #e1e5ea);
		border-radius: 10px; padding: 5px 10px; cursor: pointer; font-weight: 400; margin: 0; }
	.tz-mv .mv-g.on { background: #f2fbf4; border-color: #bfe3c8; }
	.tz-mv .mv-gm { font-size: 10.5px; color: var(--text-muted, #8a9099); }
	.tz-mv .mv-matn { width: 100%; border: 1px solid var(--border-color, #e1e5ea); border-radius: 9px;
		padding: 9px 11px; font-size: 13px; font-family: inherit; background: var(--card-bg, #fff); color: inherit; }
	.tz-mv .mv-acts { display: flex; align-items: center; gap: 8px; margin: 8px 0 4px; flex-wrap: wrap; }
	.tz-mv .mv-pt { font-size: 12.5px; margin: 12px 0 6px; }
	.tz-mv .mv-ogoh { background: #fff8e8; border: 1px solid #e8d59a; color: #8a6400;
		border-radius: 9px; padding: 6px 10px; font-size: 11.5px; margin-bottom: 7px; }
	.tz-mv .mv-rows { max-height: 320px; overflow: auto; border: 1px solid var(--border-color, #e1e5ea); border-radius: 9px; }
	.tz-mv .mv-r { display: grid; grid-template-columns: 34px 130px 1fr 60px 120px 28px; gap: 5px;
		align-items: center; padding: 3px 7px; border-bottom: 1px solid var(--border-color, #eef1f4); }
	.tz-mv .mv-r:last-child { border-bottom: none; }
	.tz-mv .mv-r.mv-h { background: var(--bg-light-gray, #f4f5f6); font-size: 10.5px;
		text-transform: uppercase; color: var(--text-muted, #8a9099); position: sticky; top: 0; }
	.tz-mv .mv-n { text-align: center; color: var(--text-muted, #8a9099); font-size: 11px; }
	.tz-mv .mv-r input, .tz-mv .mv-r select { border: 1px solid transparent; border-radius: 6px;
		padding: 3px 6px; font-size: 12.5px; width: 100%; background: transparent; color: inherit; }
	.tz-mv .mv-r input:focus, .tz-mv .mv-r select:focus { border-color: #2f6fed; background: var(--card-bg, #fff); outline: none; }
	.tz-mv .mv-x { border: none; background: transparent; color: #d8443c; cursor: pointer; font-size: 12px; padding: 0; }
	.tz-mv .mv-nlist { display: flex; flex-direction: column; gap: 4px; max-height: 260px; overflow: auto; }
	.tz-mv .mv-n-row { display: flex; align-items: center; gap: 7px; border: 1px solid var(--border-color, #e1e5ea);
		border-radius: 9px; padding: 6px 10px; margin: 0; font-weight: 400; cursor: pointer; }
	`;

	function cssOnce() {
		if (document.getElementById("tz-mavzu-css")) return;
		const el = document.createElement("style");
		el.id = "tz-mavzu-css";
		el.textContent = CSS;
		document.head.appendChild(el);
	}

	const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));

	const NAMUNA = `1-bob. Natural sonlar:
1. Natural sonlar va ular ustida amallar
2. Qo'shish va ayirish — 2 soat
3. Ko'paytirish (2 soat)
[nazorat] 1-nazorat ishi

2-bob. Kasrlar:
Oddiy kasrlar | 2
Kasrlarni qisqartirish
Takrorlash`;

	class TZMavzuDialog {
		constructor(opts) {
			cssOnce();
			this.o = opts || {};
			this.rows = [];
			this.rejim = "qoshish";
			this.tab = "matn";
			this.load();
		}

		load() {
			frappe.call({
				method: `${M}.mening_fanlarim`, freeze: true,
				callback: (r) => { this.meta = r.message || {}; this.show(); },
			});
		}

		// Shu fan bo'yicha o'qituvchining guruhlari
		guruhlar() {
			const fan = this.fan;
			return (this.meta.juftliklar || []).filter((j) => j.fan === fan);
		}
		fanlar() {
			const m = {};
			(this.meta.juftliklar || []).forEach((j) => { m[j.fan] = (m[j.fan] || 0) + 1; });
			return Object.keys(m).sort();
		}

		show() {
			const fanlar = this.fanlar();
			this.fan = this.o.fan || fanlar[0];
			this.tanlangan = new Set(this.o.guruh ? [this.o.guruh] : []);

			this.dlg = new frappe.ui.Dialog({
				title: __("Chorak mavzularini biriktirish"),
				size: "extra-large",
				primary_action_label: __("Saqlash"),
				primary_action: () => this.saqla(),
			});
			this.dlg.$body.html(`<div class="tz-mv">
				<div class="mv-tabs">
					<button class="mv-tab act" data-t="matn">📋 Ro'yxatni joylash</button>
					<button class="mv-tab" data-t="nusxa">🗐 Boshqa rejadan nusxa</button>
				</div>
				<div class="mv-top">
					<label>Fan
						<select class="mv-fan">${fanlar.map((f) => `<option value="${esc(f)}" ${f === this.fan ? "selected" : ""}>${esc(f)}</option>`).join("")}</select>
					</label>
					<label>Chorak / bo'lim <span class="mv-hint">(satrda ko'rsatilmaganlarga)</span>
						<input type="text" class="mv-bolim" list="mv-chorak-list" placeholder="masalan 1-chorak">
						<datalist id="mv-chorak-list">${(this.meta.choraklar || []).map((c) => `<option value="${esc(c.term_name || c.name)}">`).join("")}</datalist>
					</label>
					<label>Har mavzuga soat
						<input type="number" class="mv-soat" min="1" max="20" value="1">
					</label>
					<label>Rejim
						<select class="mv-rejim">
							<option value="qoshish">Mavjud mavzularga qo'shish</option>
							<option value="almashtirish">Almashtirish (o'tilganlar saqlanadi)</option>
						</select>
					</label>
				</div>
				<div class="mv-guruhlar"></div>
				<div class="mv-pane mv-pane-matn">
					<textarea class="mv-matn" rows="9" placeholder="${esc(NAMUNA)}"></textarea>
					<div class="mv-acts">
						<button class="btn btn-sm btn-default mv-parse">Tahlil qilish →</button>
						<button class="btn btn-sm btn-link mv-namuna">namunani qo'yish</button>
						<span class="mv-hint">Har mavzu — alohida satr. «1.» raqamlar, «— 2 soat», «|» ustunlar va «1-bob:» sarlavhalari tushuniladi.</span>
					</div>
				</div>
				<div class="mv-pane mv-pane-nusxa" style="display:none">
					<div class="mv-nusxa-box"><div class="mv-hint">Yuklanmoqda…</div></div>
				</div>
				<div class="mv-preview"></div>
			</div>`);

			const $b = this.dlg.$body;
			$b.find(".mv-tab").on("click", (e) => {
				const t = $(e.currentTarget).data("t");
				this.tab = t;
				$b.find(".mv-tab").removeClass("act"); $(e.currentTarget).addClass("act");
				$b.find(".mv-pane-matn").toggle(t === "matn");
				$b.find(".mv-pane-nusxa").toggle(t === "nusxa");
				if (t === "nusxa") this.loadRejalar();
			});
			$b.find(".mv-fan").on("change", (e) => {
				this.fan = e.target.value; this.tanlangan = new Set(); this.renderGuruhlar();
				if (this.tab === "nusxa") this.loadRejalar();
			});
			$b.find(".mv-rejim").on("change", (e) => { this.rejim = e.target.value; });
			$b.find(".mv-parse").on("click", () => this.parse());
			$b.find(".mv-namuna").on("click", () => $b.find(".mv-matn").val(NAMUNA));
			if (this.o.chorak) $b.find(".mv-bolim").val(this.o.chorak);

			this.renderGuruhlar();
			this.dlg.show();
			setTimeout(() => $b.find(".mv-matn").focus(), 200);
		}

		renderGuruhlar() {
			const gs = this.guruhlar();
			if (this.o.guruh && gs.some((g) => g.guruh === this.o.guruh)) this.tanlangan.add(this.o.guruh);
			if (!this.tanlangan.size && gs.length === 1) this.tanlangan.add(gs[0].guruh);
			this.dlg.$body.find(".mv-guruhlar").html(`
				<div class="mv-gt">Qaysi guruh(lar)ga biriktirilsin? <span class="mv-hint">bir nechtasini belgilash mumkin — bitta reja hammasiga tegishli bo'ladi</span></div>
				<div class="mv-glist">${gs.length ? gs.map((g) => `
					<label class="mv-g ${this.tanlangan.has(g.guruh) ? "on" : ""}">
						<input type="checkbox" value="${esc(g.guruh)}" ${this.tanlangan.has(g.guruh) ? "checked" : ""}>
						<b>${esc(g.guruh_nomi)}</b>
						<span class="mv-gm">${g.oquv_reja ? `reja bor: ${g.mavzu_soni} mavzu (o'tilgan ${g.otilgan})` : "reja yo'q"}</span>
					</label>`).join("") : `<div class="mv-hint">Bu fandan jadvalda guruhingiz yo'q.</div>`}</div>`);
			this.dlg.$body.find(".mv-g input").on("change", (e) => {
				const v = e.target.value;
				if (e.target.checked) this.tanlangan.add(v); else this.tanlangan.delete(v);
				$(e.target).closest(".mv-g").toggleClass("on", e.target.checked);
			});
		}

		// ---------- Ro'yxatni tahlil qilish ----------
		parse() {
			const matn = this.dlg.$body.find(".mv-matn").val();
			const soat = this.dlg.$body.find(".mv-soat").val() || 1;
			if (!String(matn || "").trim()) { frappe.show_alert({ message: "Ro'yxat bo'sh", indicator: "orange" }); return; }
			frappe.call({
				method: `${M}.matn_parse`, args: { matn: matn, default_soat: soat }, freeze: true,
				callback: (r) => {
					const d = r.message || {};
					this.rows = d.qatorlar || [];
					this.renderPreview(d.ogohlantirish || []);
				},
			});
		}

		renderPreview(ogoh) {
			const turlar = ["Yangi mavzu", "Takrorlash", "Nazorat", "Amaliy", "Boshqa"];
			const jamiSoat = this.rows.reduce((a, b) => a + (Number(b.soat) || 0), 0);
			this.dlg.$body.find(".mv-preview").html(!this.rows.length ? "" : `
				<div class="mv-pt">Tekshirib chiqing — <b>${this.rows.length}</b> mavzu · <b>${jamiSoat}</b> soat
					<span class="mv-hint">matnni bosib tahrirlashingiz, ✕ bilan o'chirishingiz mumkin</span></div>
				${ogoh.length ? `<div class="mv-ogoh">⚠️ ${ogoh.map(esc).join(" · ")}</div>` : ""}
				<div class="mv-rows">
					<div class="mv-r mv-h"><span>№</span><span>Bo'lim</span><span>Mavzu</span><span>Soat</span><span>Turi</span><span></span></div>
					${this.rows.map((q, i) => `
					<div class="mv-r" data-i="${i}">
						<span class="mv-n">${i + 1}</span>
						<input class="mv-i-bolim" value="${esc(q.bolim || "")}" placeholder="—">
						<input class="mv-i-mavzu" value="${esc(q.mavzu || "")}">
						<input class="mv-i-soat" type="number" min="1" max="20" value="${q.soat || 1}">
						<select class="mv-i-tur">${turlar.map((t) => `<option ${t === q.dars_turi ? "selected" : ""}>${t}</option>`).join("")}</select>
						<button class="mv-x" title="o'chirish">✕</button>
					</div>`).join("")}
				</div>`);
			const $b = this.dlg.$body;
			$b.find(".mv-x").on("click", (e) => {
				const i = Number($(e.currentTarget).closest(".mv-r").data("i"));
				this.sync(); this.rows.splice(i, 1); this.renderPreview(ogoh);
			});
		}

		sync() {
			const $b = this.dlg.$body;
			$b.find(".mv-rows .mv-r[data-i]").each((idx, el) => {
				const $r = $(el); const i = Number($r.data("i"));
				if (!this.rows[i]) return;
				this.rows[i].bolim = $r.find(".mv-i-bolim").val() || null;
				this.rows[i].mavzu = $r.find(".mv-i-mavzu").val();
				this.rows[i].soat = Number($r.find(".mv-i-soat").val()) || 1;
				this.rows[i].dars_turi = $r.find(".mv-i-tur").val();
			});
			this.rows = this.rows.filter((q) => (q.mavzu || "").trim());
		}

		// ---------- Boshqa rejadan nusxa ----------
		loadRejalar() {
			const box = this.dlg.$body.find(".mv-nusxa-box");
			box.html(`<div class="mv-hint">Yuklanmoqda…</div>`);
			frappe.call({
				method: `${M}.reja_royxati`, args: { fan: this.fan },
				callback: (r) => {
					const list = r.message || [];
					box.html(!list.length ? `<div class="mv-hint">Bu fan bo'yicha mavzusi bor reja yo'q. «Ro'yxatni joylash» bo'limidan foydalaning.</div>` : `
						<div class="mv-gt">Qaysi rejadan nusxa olinsin?</div>
						<div class="mv-nlist">${list.map((p) => `
							<label class="mv-n-row"><input type="radio" name="mvnusxa" value="${esc(p.name)}">
								<b>${esc(p.nomi || p.name)}</b>
								<span class="mv-gm">${esc(p.sinf_daraja || "")} · ${p.mavzu_soni} mavzu · ${p.jami_soat || 0} soat · ${esc(p.holat)}</span>
							</label>`).join("")}</div>
						<div class="mv-acts"><button class="btn btn-sm btn-default mv-nusxa-ol">Nusxani ko'rish →</button></div>`);
					box.find(".mv-nusxa-ol").on("click", () => {
						const manba = box.find(`input[name="mvnusxa"]:checked`).val();
						if (!manba) { frappe.show_alert({ message: "Reja tanlang", indicator: "orange" }); return; }
						this.manba = manba;
						frappe.call({
							method: `${M}.reja_qatorlari`, args: { reja: manba }, freeze: true,
							callback: (rr) => { this.rows = rr.message || []; this.renderPreview([]); },
						});
					});
				},
			});
		}

		// ---------- Saqlash ----------
		saqla() {
			this.sync();
			const guruhlar = [...this.tanlangan];
			if (!guruhlar.length) { frappe.show_alert({ message: "Guruh tanlanmagan", indicator: "red" }); return; }
			if (!this.rows.length) { frappe.show_alert({ message: "Avval «Tahlil qilish»ni bosing", indicator: "orange" }); return; }
			const bolim = this.dlg.$body.find(".mv-bolim").val() || null;
			if (this.rejim === "almashtirish" && !window.confirm(
				"Mavjud mavzular o'chiriladi (o'tilgan darslarga bog'langanlari saqlanadi). Davom etamizmi?")) return;
			frappe.call({
				method: `${M}.mavzular_saqla`, freeze: true,
				freeze_message: __("Mavzular biriktirilmoqda…"),
				args: {
					fan: this.fan, guruhlar: JSON.stringify(guruhlar),
					qatorlar: JSON.stringify(this.rows),
					bolim: bolim, rejim: this.rejim,
					default_soat: this.dlg.$body.find(".mv-soat").val() || 1,
					academic_year: this.meta.academic_year || undefined,
				},
				callback: (r) => {
					const d = r.message || {};
					this.dlg.hide();
					frappe.msgprint({
						title: __("Mavzular biriktirildi"),
						indicator: "green",
						message: `<b>${esc(d.reja_nomi || d.oquv_reja)}</b><br>
							Qo'shildi: <b>${d.qoshildi}</b> mavzu${d.ochirildi ? ` · o'chirildi: ${d.ochirildi}` : ""}<br>
							Rejada jami: <b>${d.jami}</b> mavzu / ${d.jami_soat || 0} soat<br>
							Guruhlar: ${esc((d.guruhlar || []).join(", "))}
							${d.yangi_reja ? "<br><span class='text-muted'>Yangi o'quv reja yaratildi va «Faol» qilindi.</span>" : ""}`,
					});
					if (this.o.onsave) this.o.onsave(d);
				},
			});
		}
	}

	window.tz_mavzu_dialog = (opts) => new TZMavzuDialog(opts);
})();
