// Oylik tabel — xodimlar stavka-kunlik jadvali.
// Ma'lumot manbai: target_zenit.target_zenit.api.oylik_tabel (orqada HRMS: Attendance / SSA / Additional Salary).

frappe.pages["oylik-tabel"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Oylik tabel",
		single_column: true,
	});

	$(wrapper).addClass("ot-full");

	const holat = {
		yil: null,
		oy: null,
		data: null,
		qidiruv: "",
	};

	// ---------------------------------------------------------------- CSS
	if (!document.getElementById("oylik-tabel-css")) {
		const css = `
		.ot-full .container { max-width: 100% !important; }
		.ot-bosh { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:8px 0 12px; }
		.ot-oy-nav { display:flex; align-items:center; gap:6px; }
		.ot-oy-nav button { border:1px solid var(--border-color); background:var(--card-bg); border-radius:6px; padding:4px 10px; cursor:pointer; font-size:14px; }
		.ot-oy-nav button:disabled { opacity:.35; cursor:default; }
		.ot-oy-nomi { font-size:16px; font-weight:600; min-width:150px; text-align:center; }
		.ot-badge { padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
		.ot-badge.ochiq { background:#d4edda; color:#155724; }
		.ot-badge.yopiq { background:#e2e3e5; color:#383d41; }
		.ot-badge.yopilmoqda { background:#fff3cd; color:#856404; }
		.ot-info { font-size:12px; color:var(--text-muted); }
		.ot-qidiruv { margin-left:auto; }
		.ot-qidiruv input { border:1px solid var(--border-color); border-radius:6px; padding:5px 10px; background:var(--card-bg); color:var(--text-color); width:220px; }
		.ot-jadval-orab { overflow-x:auto; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg); }
		table.ot-jadval { border-collapse:separate; border-spacing:0; width:max-content; min-width:100%; font-size:12.5px; }
		.ot-jadval th, .ot-jadval td { border-bottom:1px solid var(--border-color); border-right:1px solid var(--border-color); padding:4px 6px; text-align:center; white-space:nowrap; background:var(--card-bg); }
		.ot-jadval thead th { position:sticky; top:0; z-index:3; font-weight:600; background:var(--control-bg, var(--card-bg)); }
		.ot-jadval .ot-c-nr { position:sticky; left:0; z-index:2; min-width:34px; }
		.ot-jadval .ot-c-ism { position:sticky; left:34px; z-index:2; text-align:left; min-width:180px; max-width:180px; overflow:hidden; text-overflow:ellipsis; }
		.ot-jadval .ot-c-lavozim { position:sticky; left:214px; z-index:2; text-align:left; min-width:120px; max-width:120px; overflow:hidden; text-overflow:ellipsis; font-size:11.5px; color:var(--text-muted); }
		.ot-jadval .ot-c-oylik { position:sticky; left:334px; z-index:2; min-width:110px; max-width:110px; text-align:right; overflow:hidden; }
		.ot-jadval .ot-c-ishkun { position:sticky; left:444px; z-index:2; min-width:62px; box-shadow:2px 0 3px rgba(0,0,0,.06); }
		td.ot-c-ishkun { cursor:pointer; font-weight:600; }
		td.ot-c-ishkun:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		td.ot-c-ishkun.default { font-weight:400; color:var(--text-muted); }
		.ot-jadval thead .ot-c-nr, .ot-jadval thead .ot-c-ism, .ot-jadval thead .ot-c-lavozim, .ot-jadval thead .ot-c-oylik, .ot-jadval thead .ot-c-ishkun { z-index:4; }
		.ot-kun { min-width:34px; cursor:pointer; }
		.ot-kun:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		.ot-kun.yak { background:#fdecea !important; color:#c0392b; font-weight:600; }
		.ot-kun.saqlangan { background:#e7f1ff !important; font-weight:700; color:#1a56b0; }
		.ot-kun.kirmagan { background:var(--control-bg, #f5f5f5) !important; color:var(--text-muted); cursor:default; }
		.ot-kun.default { color:var(--text-muted); }
		th.ot-yak-bosh { background:#fdecea !important; color:#c0392b; }
		.ot-c-bonus { min-width:90px; text-align:right; cursor:pointer; }
		.ot-c-bonus:hover, .ot-c-oylik-t:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		.ot-c-oylik-t { cursor:pointer; }
		.ot-c-jami { min-width:120px; text-align:right; font-weight:700; }
		.ot-manba-kassa { color:#b26a00; font-size:10px; display:block; line-height:1; }
		.ot-manba-yoq { color:var(--text-muted); }
		.ot-jadval tfoot td { font-weight:700; border-top:2px solid var(--border-color); }
		.ot-plitkalar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
		.ot-plitka { border:1px solid var(--border-color); border-radius:8px; padding:8px 14px; background:var(--card-bg); min-width:130px; }
		.ot-plitka .son { font-size:17px; font-weight:700; }
		.ot-plitka .nom { font-size:11px; color:var(--text-muted); }
		.ot-koef-btnlar { display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
		.ot-koef-btnlar button { border:1px solid var(--border-color); background:var(--card-bg); border-radius:6px; padding:6px 16px; cursor:pointer; font-size:14px; font-weight:600; }
		.ot-koef-btnlar button:hover { border-color:var(--primary); color:var(--primary); }
		`;
		$("<style id='oylik-tabel-css'>").text(css).appendTo("head");
	}

	const $joy = $('<div class="ot-wrap"></div>').appendTo(page.main);

	// ---------------------------------------------------------------- format
	const nf = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
	const fmt = (n) => nf.format(n || 0);
	const koefFmt = (k) => {
		if (k === null || k === undefined) return "—";
		return parseFloat(k.toFixed(4)).toString().replace(".", ",");
	};

	// ---------------------------------------------------------------- yuklash
	function yukla() {
		frappe.call({
			method: "target_zenit.target_zenit.api.oylik_tabel.get_tabel",
			args: { yil: holat.yil, oy: holat.oy },
			freeze: true,
			freeze_message: "Tabel yuklanmoqda...",
			callback: (r) => {
				if (!r.message) return;
				holat.data = r.message;
				holat.yil = r.message.yil;
				holat.oy = r.message.oy;
				chiz();
			},
		});
	}

	function oldingiOy() {
		let { yil, oy } = holat;
		oy -= 1;
		if (oy < 1) { oy = 12; yil -= 1; }
		holat.yil = yil; holat.oy = oy;
		yukla();
	}

	function keyingiOy() {
		let { yil, oy } = holat;
		oy += 1;
		if (oy > 12) { oy = 1; yil += 1; }
		holat.yil = yil; holat.oy = oy;
		yukla();
	}

	function keyingiMumkin() {
		const bugun = frappe.datetime.str_to_obj(frappe.datetime.get_today());
		let { yil, oy } = holat;
		oy += 1;
		if (oy > 12) { oy = 1; yil += 1; }
		return yil < bugun.getFullYear() || (yil === bugun.getFullYear() && oy <= bugun.getMonth() + 1);
	}

	// ---------------------------------------------------------------- chizish
	function chiz() {
		const d = holat.data;
		$joy.empty();

		const badge =
			d.holat === "Ochiq" ? '<span class="ot-badge ochiq">🟢 Ochiq</span>' :
			d.holat === "Yopilmoqda" ? '<span class="ot-badge yopilmoqda">⏳ Yopilmoqda...</span>' :
			'<span class="ot-badge yopiq">🔒 Yopiq</span>';

		const $bosh = $(`
			<div class="ot-bosh">
				<div class="ot-oy-nav">
					<button class="ot-orqa">◀</button>
					<div class="ot-oy-nomi">${d.oy_nomi} ${d.yil}</div>
					<button class="ot-olga">▶</button>
				</div>
				${badge}
				<span class="ot-info">${d.kun_soni} kun; norma ish kuni: o'qituvchi <b>21</b>, boshqalar <b>26</b> ("Ish kuni" ustunida o'zgartiriladi)</span>
				<div class="ot-qidiruv"><input type="text" placeholder="🔍 Xodim / lavozim qidirish..." value="${frappe.utils.escape_html(holat.qidiruv)}"></div>
			</div>`);
		$bosh.find(".ot-orqa").on("click", oldingiOy);
		$bosh.find(".ot-olga").prop("disabled", !keyingiMumkin()).on("click", keyingiOy);
		$bosh.find("input").on("input", function () {
			holat.qidiruv = $(this).val().toLowerCase();
			$joy.find("tbody tr").each(function () {
				const ism = $(this).data("ism") || "";
				$(this).toggle(ism.includes(holat.qidiruv));
			});
		});
		$joy.append($bosh);

		// plitkalar
		$joy.append(`
			<div class="ot-plitkalar">
				<div class="ot-plitka"><div class="son">${d.qatorlar.length}</div><div class="nom">Xodimlar</div></div>
				<div class="ot-plitka"><div class="son">${fmt(d.jami_oylik)}</div><div class="nom">Jami hisoblangan (so'm)</div></div>
				<div class="ot-plitka"><div class="son">${fmt(d.jami_bonus)}</div><div class="nom">Jami bonus (so'm)</div></div>
			</div>`);

		// jadval
		let th = `<tr><th class="ot-c-nr">№</th><th class="ot-c-ism">Xodim</th><th class="ot-c-lavozim">Lavozim</th><th class="ot-c-oylik">Oylik (so'm)</th><th class="ot-c-ishkun" title="Norma ish kuni (oyiga)">Ish kuni</th>`;
		d.kunlar.forEach((k) => {
			th += `<th class="${k.yakshanba ? "ot-yak-bosh" : ""}" title="${k.sana}${k.yakshanba ? " (yakshanba)" : ""}">${k.kun}</th>`;
		});
		th += `<th>Bonus</th><th>Jami (so'm)</th></tr>`;

		let rows = "";
		d.qatorlar.forEach((q, i) => {
			let manba = "";
			if (q.oylik.manba === "kassa") manba = '<span class="ot-manba-kassa">Kassa taklifi*</span>';
			if (q.oylik.manba === "yoq") manba = '<span class="ot-manba-kassa ot-manba-yoq">kiritilmagan</span>';
			let tr = `<tr data-ism="${frappe.utils.escape_html(((q.ismi || "") + " " + (q.lavozim || "")).toLowerCase())}" data-xodim="${q.xodim}">
				<td class="ot-c-nr">${i + 1}</td>
				<td class="ot-c-ism" title="${frappe.utils.escape_html(q.ismi || q.xodim)}">${frappe.utils.escape_html(q.ismi || q.xodim)}</td>
				<td class="ot-c-lavozim" title="${frappe.utils.escape_html(q.lavozim || "")}">${frappe.utils.escape_html(q.lavozim || "—")}</td>
				<td class="ot-c-oylik ot-c-oylik-t" data-i="${i}" title="Bosib o'zgartiring (Employee hujjati bilan sinxron)">${fmt(q.oylik.summa)}${manba}</td>
				<td class="ot-c-ishkun ${q.ish_kuni_manba === "default" ? "default" : ""}" data-i="${i}" title="Norma ish kuni — bosib o'zgartiring (kunlik narx = oylik / shu son)">${q.ish_kuni}</td>`;
			q.kunlar.forEach((kq, j) => {
				const kd = d.kunlar[j];
				if (kq.holat === "kirmagan") {
					tr += `<td class="ot-kun kirmagan" title="Hali ishga kirmagan">—</td>`;
				} else {
					const cls = ["ot-kun"];
					if (kd.yakshanba) cls.push("yak");
					if (kq.holat === "saqlangan") cls.push("saqlangan");
					else cls.push("default");
					tr += `<td class="${cls.join(" ")}" data-i="${i}" data-j="${j}" title="${kd.sana} — bosib o'zgartiring">${koefFmt(kq.koef)}</td>`;
				}
			});
			tr += `<td class="ot-c-bonus" data-i="${i}" title="Bosib o'zgartiring">${q.bonus ? fmt(q.bonus) : "+"}</td>`;
			tr += `<td class="ot-c-jami" title="Kunlik: ${fmt(q.kunlik_narx)} so'm × ${koefFmt(q.koef_yigindi)}">${fmt(q.jami)}</td></tr>`;
			rows += tr;
		});

		const foot = `<tr><td class="ot-c-nr"></td><td class="ot-c-ism">JAMI</td><td class="ot-c-lavozim"></td><td class="ot-c-oylik"></td><td class="ot-c-ishkun"></td>
			<td colspan="${d.kunlar.length}"></td>
			<td style="text-align:right">${fmt(d.jami_bonus)}</td>
			<td class="ot-c-jami">${fmt(d.jami_oylik)}</td></tr>`;

		const $orab = $(`<div class="ot-jadval-orab"><table class="ot-jadval">
			<thead>${th}</thead><tbody>${rows}</tbody><tfoot>${foot}</tfoot></table></div>`);
		$joy.append($orab);

		if (d.oylik_izoh_kerak !== false) {
			$joy.append(`<div class="ot-info" style="margin-top:8px">
				* "Kassa taklifi" — oylik hali kiritilmagan, Kassa'dagi oxirgi oy to'lovlaridan avtomatik taxmin. Oylikni tabelda katakni bosib yoki Employee hujjatidagi "Oylik ish haqi (shartnoma)" (Overview) maydonidan kiritish mumkin — ikkalasi sinxron.<br>
				Katak ranglari: <span style="color:#c0392b">qizil — yakshanba</span>, <span style="color:#1a56b0">ko'k — yo'qlamada belgilangan</span>, kulrang "0" — hali belgilanmagan (kelmagan hisoblanadi). Kim kelgan bo'lsa katagini bosib "1" qilinadi.
			</div>`);
		}

		// tugmalar
		page.clear_inner_toolbar();
		if (d.yopish_mumkin) {
			page.add_inner_button("🔒 Oyni yopish", () => oyYop(d));
		}
		if (d.ochish_mumkin) {
			page.add_inner_button("🔓 Oyni qayta ochish", () => oyOch(d));
		}
		page.add_inner_button("📋 O'zgarishlar jurnali", () => {
			frappe.set_route("List", "Tabel Ozgarish Jurnali", { oy: `${d.yil}-${String(d.oy).padStart(2, "0")}` });
		});

		// hodisalar
		if (d.tahrir_mumkin) {
			$orab.on("click", "td.ot-kun:not(.kirmagan)", function () {
				const i = $(this).data("i"), j = $(this).data("j");
				koefDialog(d.qatorlar[i], d.kunlar[j], d.qatorlar[i].kunlar[j]);
			});
			$orab.on("click", "td.ot-c-oylik-t", function () {
				oylikDialog(d.qatorlar[$(this).data("i")]);
			});
			$orab.on("click", "td.ot-c-bonus", function () {
				bonusDialog(d.qatorlar[$(this).data("i")]);
			});
			$orab.on("click", "td.ot-c-ishkun", function () {
				ishKuniDialog(d.qatorlar[$(this).data("i")]);
			});
		}
	}

	// ---------------------------------------------------------------- dialoglar
	function koefDialog(q, kun, kq) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — ${kun.sana}`,
			fields: [
				{ fieldtype: "HTML", fieldname: "btnlar" },
				{
					fieldtype: "Float", fieldname: "koef", label: "Stavka koeffitsienti",
					default: kq.koef, reqd: 1,
					description: "1 = to'liq kun, 0.5 = yarim kun, 2 = ikki smena, 0 = ishlamadi",
				},
			],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				saqlaKoef(q.xodim, kun.sana, v.koef);
			},
		});
		const $b = $('<div class="ot-koef-btnlar"></div>');
		[0, 0.5, 1, 1.5, 2].forEach((k) => {
			$(`<button>${String(k).replace(".", ",")}</button>`).on("click", () => {
				dlg.hide();
				saqlaKoef(q.xodim, kun.sana, k);
			}).appendTo($b);
		});
		dlg.fields_dict.btnlar.$wrapper.append($b);
		dlg.show();
	}

	function saqlaKoef(xodim, sana, koef) {
		frappe.call({
			method: "target_zenit.target_zenit.api.oylik_tabel.set_koef",
			args: { xodim, sana, koef },
			freeze: true,
			callback: () => yukla(),
		});
	}

	function oylikDialog(q) {
		const izoh =
			q.oylik.manba === "kassa"
				? "Bu summa Kassa'dagi oxirgi oy to'lovlaridan taklif sifatida olingan. Saqlasangiz rasmiy tasdiqlanadi va Employee hujjatiga ham yoziladi."
				: q.oylik.manba === "yoq"
					? "Bu xodimga hali oylik kiritilmagan (Kassa'da to'lov ham topilmadi)."
					: "O'zgartirilsa shu oyning BOSHIDAN amal qiladi va Employee hujjatidagi \"Oylik ish haqi (shartnoma)\" maydoni ham yangilanadi.";
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — oylik summa`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Oylik (so'm)",
				default: q.oylik.summa, reqd: 1, description: izoh,
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.set_oylik",
					args: { xodim: q.xodim, yil: holat.yil, oy: holat.oy, summa: v.summa },
					freeze: true,
					callback: () => yukla(),
				});
			},
		});
		dlg.show();
	}

	function bonusDialog(q) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — bonus (${holat.data.oy_nomi})`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Bonus (so'm)",
				default: q.bonus, reqd: 1, description: "0 kiritsangiz bonus olib tashlanadi",
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.set_bonus",
					args: { xodim: q.xodim, yil: holat.yil, oy: holat.oy, summa: v.summa },
					freeze: true,
					callback: () => yukla(),
				});
			},
		});
		dlg.show();
	}

	function ishKuniDialog(q) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — norma ish kuni`,
			fields: [{
				fieldtype: "Int", fieldname: "kun", label: "Ish kuni (oyiga)",
				default: q.ish_kuni, reqd: 1,
				description: "Kunlik narx = oylik / shu son. Default: o'qituvchi 21, boshqalar 26. " +
					"Xodimning o'ziga saqlanadi — keyingi oylarga ham amal qiladi.",
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.set_ish_kuni",
					args: { xodim: q.xodim, yil: holat.yil, oy: holat.oy, kun: v.kun },
					freeze: true,
					callback: () => yukla(),
				});
			},
		});
		dlg.show();
	}

	function oyYop(d) {
		frappe.confirm(
			`<b>${d.oy_nomi} ${d.yil}</b> tabelini yopmoqchimisiz?<br><br>
			• Yo'qlamada belgilanmagan kunlar 0 (kelmagan) hisoblanadi<br>
			• Barcha davomat va bonuslar rasmiy tasdiqlanadi (HRMS)<br>
			• Yopilgandan keyin tahrirlab bo'lmaydi ("Oyni qayta ochish" tugmasi bilan qayta ochiladi)`,
			() => {
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.oy_yop",
					args: { yil: d.yil, oy: d.oy },
					freeze: true,
					freeze_message: "Oy yopilmoqda (fonda davom etadi)...",
					callback: () => yukla(),
				});
			}
		);
	}

	function oyOch(d) {
		frappe.confirm(`<b>${d.oy_nomi} ${d.yil}</b> tabelini qayta ochmoqchimisiz?`, () => {
			frappe.call({
				method: "target_zenit.target_zenit.api.oylik_tabel.oy_och",
				args: { yil: d.yil, oy: d.oy },
				freeze: true,
				callback: () => yukla(),
			});
		});
	}

	// ---------------------------------------------------------------- realtime
	frappe.realtime.on("tabel_update", (m) => {
		if (m && m.xabar) frappe.show_alert({ message: m.xabar, indicator: m.holat === "Yopiq" ? "green" : "orange" });
		if (m && m.yil === holat.yil && m.oy === holat.oy) yukla();
	});

	yukla();
};
