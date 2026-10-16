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
		tanlangan: [],      // xodimlar ko'p-tanlov filtri (bo'sh = hammasi)
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
		/* yo'qlama popover: keldi/kelmadi tanlovi */
		.ot-pop { position:absolute; z-index:1060; background:var(--card-bg); border:1px solid var(--border-color); border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,.18); padding:7px 8px; display:flex; gap:6px; align-items:center; }
		.ot-pop-t { font-size:11px; color:var(--text-muted); margin-right:2px; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
		.ot-pop button { border:1px solid var(--border-color); border-radius:8px; padding:6px 14px; cursor:pointer; font-size:13px; font-weight:600; background:var(--card-bg); color:var(--text-color); }
		.ot-pop .ot-pop-keldi { color:#1a7f4e; } .ot-pop .ot-pop-keldi:hover { background:rgba(26,127,78,.12); border-color:#1a7f4e; }
		.ot-pop .ot-pop-kelmadi { color:#c0392b; } .ot-pop .ot-pop-kelmadi:hover { background:rgba(192,57,43,.10); border-color:#c0392b; }
		/* xodimlar ko'p-tanlov filtri */
		.ot-xf { position:relative; }
		.ot-xf-btn { border:1px solid var(--border-color); background:var(--card-bg); border-radius:6px; padding:5px 12px; cursor:pointer; color:var(--text-color); font-size:13px; }
		.ot-xf-btn.faol { border-color:var(--primary); color:var(--primary); font-weight:600; }
		.ot-xf-menu { position:absolute; top:110%; left:0; z-index:1055; width:270px; max-height:330px; overflow:auto; background:var(--card-bg); border:1px solid var(--border-color); border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,.18); padding:8px; }
		.ot-xf-menu input.ot-xf-qidir { width:100%; margin-bottom:6px; border:1px solid var(--border-color); border-radius:6px; padding:4px 8px; background:var(--card-bg); color:var(--text-color); }
		.ot-xf-menu label { display:flex; gap:8px; align-items:center; padding:3px 5px; border-radius:6px; cursor:pointer; font-size:12.5px; margin:0; color:var(--text-color); }
		.ot-xf-menu label:hover { background:rgba(128,128,128,.08); }
		.ot-xf-menu label small { color:var(--text-muted); margin-left:auto; }
		.ot-xf-foot { display:flex; justify-content:flex-end; margin-top:6px; border-top:1px solid var(--border-color); padding-top:6px; }
		.ot-xf-foot button { border:0; background:transparent; color:var(--primary); cursor:pointer; font-size:12px; font-weight:600; }
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
		.ot-ketgan { display:block; font-size:10px; line-height:1.1; color:#c0392b; }
		.ot-soat-btnlar { display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
		.ot-soat-btnlar button { border:1px solid var(--border-color); background:var(--card-bg); border-radius:6px; padding:6px 14px; cursor:pointer; font-size:14px; font-weight:600; }
		.ot-soat-btnlar button:hover { border-color:var(--primary); color:var(--primary); }
		.ot-kun.default { color:var(--text-muted); }
		th.ot-yak-bosh { background:#fdecea !important; color:#c0392b; }
		.ot-c-bonus { min-width:90px; text-align:right; cursor:pointer; }
		.ot-c-kelgan { min-width:70px; font-weight:600; }
		.ot-c-ushlov { min-width:95px; text-align:right; cursor:pointer; color:#c0392b; }
		.ot-c-ushlov:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		.ot-c-ushlov.bosh { color:var(--text-muted); font-weight:400; }
		.ot-c-ushlov .qolda-b { color:#b26a00; font-size:10px; display:block; line-height:1; }
		.ot-c-bonus:hover, .ot-c-oylik-t:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		.ot-c-oylik-t { cursor:pointer; }
		.ot-c-jami { min-width:120px; text-align:right; font-weight:700; }
		td.ot-c-jami-t { cursor:pointer; }
		td.ot-c-jami-t:hover { outline:2px solid var(--primary); outline-offset:-2px; }
		td.ot-c-jami.qolda { color:#b26a00; }
		.ot-manba-kassa { color:#b26a00; font-size:10px; display:block; line-height:1; }
		.ot-manba-yoq { color:var(--text-muted); }
		.ot-jadval tfoot td { font-weight:700; border-top:2px solid var(--border-color); }
		.ot-plitkalar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
		.ot-plitka { border:1px solid var(--border-color); border-radius:8px; padding:8px 14px; background:var(--card-bg); min-width:130px; }
		.ot-plitka .son { font-size:17px; font-weight:700; }
		.ot-plitka .nom { font-size:11px; color:var(--text-muted); }
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

	// Qatorlarni qidiruv + tanlangan xodimlar bo'yicha ko'rsatish/yashirish
	function filtrla() {
		const q = holat.qidiruv || "", sel = holat.tanlangan;
		$joy.find("tbody tr").each(function () {
			const ism = String($(this).data("ism") || "");
			const xid = String($(this).data("xodim") || "");
			$(this).toggle(ism.includes(q) && (!sel.length || sel.indexOf(xid) !== -1));
		});
	}

	// ---------------------------------------------------------------- chizish
	function chiz() {
		const d = holat.data;
		// qayta chizishda qidiruv fokusi/kursori saqlansin
		const $eskiInp = $joy.find(".ot-qidiruv input");
		const fokusEdi = $eskiInp.length && $eskiInp.is(":focus");
		$(".ot-pop").remove();
		$joy.empty();

		let badge =
			d.holat === "Ochiq" ? '<span class="ot-badge ochiq">🟢 Ochiq</span>' :
			d.holat === "Yopilmoqda" ? '<span class="ot-badge yopilmoqda">⏳ Yopilmoqda...</span>' :
			'<span class="ot-badge yopiq">🔒 Yopiq</span>';
		if (d.faqat_oqish) badge += ' <span class="ot-badge yopiq" title="Sizning rolingiz tabelni faqat ko\'rishga ruxsat beradi">👁 Faqat o\'qish</span>';

		// Xodimlar ko'p-tanlov filtri menyusi (checkbox ro'yxat + ichki qidiruv)
		const xfOptlar = d.qatorlar.map((q) => `<label>
			<input type="checkbox" value="${frappe.utils.escape_html(q.xodim)}" ${holat.tanlangan.indexOf(q.xodim) !== -1 ? "checked" : ""}>
			<span>${frappe.utils.escape_html(q.ismi || q.xodim)}</span>
			<small>${frappe.utils.escape_html((q.lavozim || "").slice(0, 18))}</small></label>`).join("");

		const $bosh = $(`
			<div class="ot-bosh">
				<div class="ot-oy-nav">
					<button class="ot-orqa">◀</button>
					<div class="ot-oy-nomi">${d.oy_nomi} ${d.yil}</div>
					<button class="ot-olga">▶</button>
				</div>
				${badge}
				<span class="ot-info">${d.kun_soni} kun; norma ish kuni: o'qituvchi <b>21</b>, boshqalar <b>26</b> ("Ish kuni" ustunida o'zgartiriladi)</span>
				<div class="ot-xf">
					<button class="ot-xf-btn ${holat.tanlangan.length ? "faol" : ""}">👥 Xodimlar${holat.tanlangan.length ? ` · ${holat.tanlangan.length}` : ""} ▾</button>
					<div class="ot-xf-menu" style="display:none">
						<input class="ot-xf-qidir" type="text" placeholder="Ro'yxatdan qidirish...">
						<div class="ot-xf-list">${xfOptlar}</div>
						<div class="ot-xf-foot"><button class="ot-xf-toza">✕ Tozalash (hammasi)</button></div>
					</div>
				</div>
				<div class="ot-qidiruv"><input type="text" placeholder="🔍 Xodim / lavozim qidirish..." value="${frappe.utils.escape_html(holat.qidiruv)}"></div>
			</div>`);
		$bosh.find(".ot-orqa").on("click", oldingiOy);
		$bosh.find(".ot-olga").prop("disabled", !keyingiMumkin()).on("click", keyingiOy);
		$bosh.find(".ot-qidiruv input").on("input", function () {
			holat.qidiruv = $(this).val().toLowerCase();
			filtrla();
		});

		// Xodimlar filtri hodisalari
		const $xfBtn = $bosh.find(".ot-xf-btn"), $xfMenu = $bosh.find(".ot-xf-menu");
		const xfYangila = () => {
			$xfBtn.toggleClass("faol", !!holat.tanlangan.length)
				.html(`👥 Xodimlar${holat.tanlangan.length ? ` · ${holat.tanlangan.length}` : ""} ▾`);
			filtrla();
		};
		$xfBtn.on("click", (e) => { e.stopPropagation(); $xfMenu.toggle(); });
		$xfMenu.on("click", (e) => e.stopPropagation());
		$xfMenu.find(".ot-xf-qidir").on("input", function () {
			const s = $(this).val().toLowerCase();
			$xfMenu.find("label").each(function () {
				$(this).toggle($(this).text().toLowerCase().includes(s));
			});
		});
		$xfMenu.on("change", "input[type=checkbox]", function () {
			const v = $(this).val(), i = holat.tanlangan.indexOf(v);
			if (this.checked && i === -1) holat.tanlangan.push(v);
			if (!this.checked && i !== -1) holat.tanlangan.splice(i, 1);
			xfYangila();
		});
		$xfMenu.find(".ot-xf-toza").on("click", () => {
			holat.tanlangan = [];
			$xfMenu.find("input[type=checkbox]").prop("checked", false);
			xfYangila();
		});
		$(document).off("click.otxf").on("click.otxf", () => $xfMenu.hide());
		$joy.append($bosh);

		// plitkalar
		$joy.append(`
			<div class="ot-plitkalar">
				<div class="ot-plitka"><div class="son">${d.qatorlar.length}</div><div class="nom">Xodimlar</div></div>
				<div class="ot-plitka"><div class="son">${fmt(d.jami_oylik)}</div><div class="nom">Jami hisoblangan (so'm)</div></div>
				<div class="ot-plitka"><div class="son">${fmt(d.jami_bonus)}</div><div class="nom">Bonus − jarima (so'm)</div></div>
				<div class="ot-plitka"><div class="son">−${fmt((d.jami_nalog || 0) + (d.jami_pitaniya || 0))}</div><div class="nom">Nalog + pitaniya (so'm)</div></div>
			</div>`);

		// jadval
		let th = `<tr><th class="ot-c-nr">№</th><th class="ot-c-ism">Xodim</th><th class="ot-c-lavozim">Lavozim</th><th class="ot-c-oylik">Oylik (so'm)</th><th class="ot-c-ishkun" title="Norma ish kuni (oyiga)">Ish kuni</th>`;
		d.kunlar.forEach((k) => {
			th += `<th class="${k.yakshanba ? "ot-yak-bosh" : ""}" title="${k.sana}${k.yakshanba ? " (yakshanba)" : ""}">${k.kun}</th>`;
		});
		th += `<th title="Musbat — bonus, manfiy — jarima">Bonus/Jarima</th><th class="ot-c-kelgan" title="Yo'qlamada 1 belgilangan kunlar soni">Kelgan kun</th>`;
		th += `<th class="ot-c-ushlov" title="Soliq — QO'LDA kiritiladi, jamidan ayriladi">Nalog (so'm)</th>`;
		th += `<th class="ot-c-ushlov" title="Ovqat — avtomatik: kelgan kun × ${fmt(d.pitaniya_kunlik)} so'm; jamidan ayriladi (qo'lda ham o'zgartirsa bo'ladi)">Pitaniya (so'm)</th>`;
		th += `<th>Jami (so'm)</th></tr>`;

		let rows = "";
		d.qatorlar.forEach((q, i) => {
			let manba = "";
			if (q.oylik.manba === "kassa") manba = '<span class="ot-manba-kassa">Kassa taklifi*</span>';
			if (q.oylik.manba === "yoq") manba = '<span class="ot-manba-kassa ot-manba-yoq">kiritilmagan</span>';
			let tr = `<tr data-ism="${frappe.utils.escape_html(((q.ismi || "") + " " + (q.lavozim || "")).toLowerCase())}" data-xodim="${q.xodim}">
				<td class="ot-c-nr">${i + 1}</td>
				<td class="ot-c-ism" title="${frappe.utils.escape_html(q.ismi || q.xodim)}${q.ketgan_sana ? ` — ${q.ketgan_sana} da ishdan ketgan` : ""}">${frappe.utils.escape_html(q.ismi || q.xodim)}${q.ketgan_sana ? `<span class="ot-ketgan">ketgan: ${q.ketgan_sana}</span>` : ""}</td>
				<td class="ot-c-lavozim" title="${frappe.utils.escape_html(q.lavozim || "")}">${frappe.utils.escape_html(q.lavozim || "—")}</td>
				<td class="ot-c-oylik ot-c-oylik-t" data-i="${i}" title="${q.tolov_turi === "soat" ? "SOAT NARXI — bosib FAQAT shu oy uchun o'zgartiring" : "Bosib FAQAT shu oy uchun o'zgartiring — boshqa oylarga ta'sir qilmaydi"}">${fmt(q.oylik.summa)}${q.tolov_turi === "soat" ? '<span class="ot-manba-kassa" style="color:var(--text-muted)">soat narxi</span>' : ""}${manba}</td>
				${q.tolov_turi === "soat"
					? `<td class="ot-c-ishkun default" data-i="${i}" title="Soatbay xodim — norma ish kuni qatnashmaydi, hisob soatlardan">soatbay</td>`
					: `<td class="ot-c-ishkun ${q.ish_kuni_manba === "default" ? "default" : ""}" data-i="${i}" title="${q.ish_kuni_manba === "oy" ? "Shu oy uchun kiritilgan" : q.ish_kuni_manba === "xodim" ? "Xodimning doimiy normasi" : "Default"} norma ish kuni — bosib FAQAT shu oy uchun o'zgartiring (kunlik narx = oylik / shu son)">${q.ish_kuni}</td>`}`;
			q.kunlar.forEach((kq, j) => {
				const kd = d.kunlar[j];
				if (kq.holat === "kirmagan") {
					tr += `<td class="ot-kun kirmagan" title="Hali ishga kirmagan (${q.kirgan_sana || ""} da kirgan)">—</td>`;
				} else if (kq.holat === "ketgan") {
					tr += `<td class="ot-kun kirmagan" title="Ishdan ketgan (${q.ketgan_sana || ""})">—</td>`;
				} else {
					const cls = ["ot-kun"];
					if (kd.yakshanba) cls.push("yak");
					if (kq.holat === "saqlangan") cls.push("saqlangan");
					else cls.push("default");
					tr += `<td class="${cls.join(" ")}" data-i="${i}" data-j="${j}" title="${kd.sana} — ${q.tolov_turi === "soat" ? "bosib ishlagan soatini kiriting" : "bosing — keldi / kelmadi tanlovi ochiladi"}">${koefFmt(kq.koef)}</td>`;
				}
			});
			tr += `<td class="ot-c-bonus" data-i="${i}" title="Bosib o'zgartiring: musbat — bonus, manfiy — jarima"${q.bonus < 0 ? ' style="color:var(--red-600,#c0392b);font-weight:600"' : ""}>${q.bonus ? fmt(q.bonus) : "+"}</td>`;
			tr += q.tolov_turi === "soat"
				? `<td class="ot-c-kelgan" title="Oyda ishlagan soatlari">${koefFmt(q.koef_yigindi)} <small>soat</small></td>`
				: `<td class="ot-c-kelgan" title="Kelgan kunlari (1 belgilanganlar), norma: ${q.ish_kuni}">${koefFmt(q.koef_yigindi)}</td>`;
			tr += `<td class="ot-c-ushlov${q.nalog ? "" : " bosh"}" data-tur="nalog" data-i="${i}" title="Nalog qo'lda kiritiladi — bosib o'zgartiring (0 = nalog yo'q). Jamidan ayriladi.">${q.nalog ? "−" + fmt(q.nalog) : "+"}</td>`;
			const pitIzoh = q.pitaniya_manba === "qolda"
				? `QO'LDA kiritilgan pitaniya (avtomatik: ${q.kelgan_kun} kun × ${fmt(q.pitaniya_kunlik)} = ${fmt(q.pitaniya_avto)} so'm) — bosib o'zgartiring`
				: `Avtomatik: ${q.kelgan_kun} kelgan kun × ${fmt(q.pitaniya_kunlik)} so'm — bosib qo'lda o'zgartirsa bo'ladi`;
			tr += `<td class="ot-c-ushlov${q.pitaniya ? "" : " bosh"}" data-tur="pitaniya" data-i="${i}" title="${pitIzoh}">${q.pitaniya ? "−" + fmt(q.pitaniya) : "0"}${q.pitaniya_manba === "qolda" ? `<span class="qolda-b">qo'lda</span>` : ""}</td>`;
			const ushlovIzoh = `\nHisoblangan: ${fmt(q.hisob)} − nalog ${fmt(q.nalog)} − pitaniya ${fmt(q.pitaniya)} = ${fmt(q.jami)}`;
			const jamiIzoh = (q.jami_manba === "qolda"
				? `QO'LDA kiritilgan hisob summasi (avtomatik hisob: ${fmt(q.hisob_avto)} so'm) — bosib o'zgartiring, 0 kiritsangiz avtoga qaytadi`
				: `${q.tolov_turi === "soat" ? `Soat narxi: ${fmt(q.kunlik_narx)} so'm × ${koefFmt(q.koef_yigindi)} soat` : `Kunlik: ${fmt(q.kunlik_narx)} so'm × ${koefFmt(q.koef_yigindi)}`} — ming so'mga pastga yaxlitlangan. Bosib qo'lda o'zgartirsa bo'ladi`) + ushlovIzoh;
			tr += `<td class="ot-c-jami ot-c-jami-t${q.jami_manba === "qolda" ? " qolda" : ""}" data-i="${i}" title="${jamiIzoh}">${fmt(q.jami)}${q.jami_manba === "qolda" ? `<span class="ot-manba-kassa" style="color:#b26a00">qo'lda</span>` : ""}</td></tr>`;
			rows += tr;
		});

		const foot = `<tr><td class="ot-c-nr"></td><td class="ot-c-ism">JAMI</td><td class="ot-c-lavozim"></td><td class="ot-c-oylik"></td><td class="ot-c-ishkun"></td>
			<td colspan="${d.kunlar.length}"></td>
			<td style="text-align:right">${fmt(d.jami_bonus)}</td>
			<td class="ot-c-kelgan">${koefFmt(d.qatorlar.reduce((s, q) => s + (q.koef_yigindi || 0), 0))}</td>
			<td class="ot-c-ushlov">${fmt(d.jami_nalog)}</td>
			<td class="ot-c-ushlov">${fmt(d.jami_pitaniya)}</td>
			<td class="ot-c-jami">${fmt(d.jami_oylik)}</td></tr>`;

		const $orab = $(`<div class="ot-jadval-orab"><table class="ot-jadval">
			<thead>${th}</thead><tbody>${rows}</tbody><tfoot>${foot}</tfoot></table></div>`);
		$joy.append($orab);
		filtrla();
		if (fokusEdi) {
			const inp = $joy.find(".ot-qidiruv input")[0];
			if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
		}

		if (d.oylik_izoh_kerak !== false) {
			$joy.append(`<div class="ot-info" style="margin-top:8px">
				* "Kassa taklifi" — oylik hali kiritilmagan, Kassa'dagi oxirgi oy to'lovlaridan avtomatik taxmin. Oylikni tabelda katakni bosib yoki Employee hujjatidagi "Oylik ish haqi (shartnoma)" (Overview) maydonidan kiritish mumkin — ikkalasi sinxron.<br>
				Katak ranglari: <span style="color:#c0392b">qizil — yakshanba</span>, <span style="color:#1a56b0">ko'k — yo'qlamada belgilangan</span>, kulrang "0" — hali belgilanmagan (kelmagan hisoblanadi). Kunbay xodimda katak bosilsa KELDI/KELMADI tanlovi ochiladi; <b>soatbay</b> xodimda esa katak bosilganda o'sha kuni ishlagan SOATI kiritiladi (jami = soat narxi × soatlar).
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
			// Yo'qlama: kunbay — katak bosilganda KELDI/KELMADI tanlovi ochiladi
			// (bitta bosish bilan istalgan holat); soatbay — soat kiritish oynasi
			$orab.on("click", "td.ot-kun:not(.kirmagan)", function () {
				const i = $(this).data("i"), j = $(this).data("j");
				const q = d.qatorlar[i];
				if (q.tolov_turi === "soat") {
					soatDialog(q, d.kunlar[j], q.kunlar[j]);
					return;
				}
				koefPop($(this), q, j);
			});
			$orab.on("click", "td.ot-c-oylik-t", function () {
				oylikDialog(d.qatorlar[$(this).data("i")]);
			});
			$orab.on("click", "td.ot-c-bonus", function () {
				bonusDialog(d.qatorlar[$(this).data("i")]);
			});
			$orab.on("click", "td.ot-c-ushlov", function () {
				const q = d.qatorlar[$(this).data("i")];
				if ($(this).data("tur") === "nalog") nalogDialog(q);
				else pitaniyaDialog(q);
			});
			$orab.on("click", "td.ot-c-jami-t", function () {
				jamiDialog(d.qatorlar[$(this).data("i")]);
			});
			$orab.on("click", "td.ot-c-ishkun", function () {
				const q = d.qatorlar[$(this).data("i")];
				if (q.tolov_turi === "soat") return;   // soatbayda norma ish kuni yo'q
				ishKuniDialog(q);
			});
		}
	}

	// ---------------------------------------------------------------- dialoglar
	function soatDialog(q, kun, kq) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — ${kun.sana}`,
			fields: [
				{ fieldtype: "HTML", fieldname: "btnlar" },
				{
					fieldtype: "Float", fieldname: "soat", label: "Bugun ishlagan soati",
					default: kq.koef || 8, reqd: 1,
					description: "0 = kelmadi. Oy jami = soat narxi × oyda ishlagan soatlar.",
				},
			],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				saqlaKoef(q.xodim, kun.sana, v.soat);
			},
		});
		const $b = $('<div class="ot-soat-btnlar"></div>');
		[0, 2, 4, 6, 8, 10, 12].forEach((s) => {
			$(`<button>${s} soat</button>`).on("click", () => {
				dlg.hide();
				saqlaKoef(q.xodim, kun.sana, s);
			}).appendTo($b);
		});
		dlg.fields_dict.btnlar.$wrapper.append($b);
		dlg.show();
	}

	// Kunbay yo'qlama tanlovi — katak yonida kichik popover (keldi/kelmadi)
	function koefPop($td, q, j) {
		$(".ot-pop").remove();
		const d = holat.data, kun = d.kunlar[j];
		const $p = $(`<div class="ot-pop">
			<span class="ot-pop-t">${frappe.utils.escape_html(q.ismi || "")} · ${kun.sana.slice(8)}-kun</span>
			<button class="ot-pop-keldi">✅ Keldi</button>
			<button class="ot-pop-kelmadi">✖ Kelmadi</button></div>`);
		$("body").append($p);
		const off = $td.offset(), w = $p.outerWidth();
		let left = off.left + $td.outerWidth() / 2 - w / 2;
		left = Math.max(8, Math.min(left, $(window).width() - w - 8));
		$p.css({ top: off.top + $td.outerHeight() + 4, left: left });
		$p.find(".ot-pop-keldi").on("click", () => { $p.remove(); saqlaKoef(q.xodim, kun.sana, 1); });
		$p.find(".ot-pop-kelmadi").on("click", () => { $p.remove(); saqlaKoef(q.xodim, kun.sana, 0); });
		setTimeout(() => $(document).off("click.otpop").on("click.otpop", (e) => {
			if (!$(e.target).closest(".ot-pop").length) { $p.remove(); $(document).off("click.otpop"); }
		}), 0);
	}

	function saqlaKoef(xodim, sana, koef) {
		frappe.call({
			method: "target_zenit.target_zenit.api.oylik_tabel.set_koef",
			args: { xodim, sana, koef },
			callback: () => lokalKoef(xodim, sana, koef),
			error: () => yukla(),
		});
	}

	// Saqlangan katakni JOYIDA yangilash — butun jadval qayta chizilmaydi,
	// shuning uchun qidiruv fokusi, filtrlar va skroll o'z joyida qoladi
	function lokalKoef(xodim, sana, koef) {
		const d = holat.data;
		const i = d.qatorlar.findIndex((x) => x.xodim === xodim);
		const j = d.kunlar.findIndex((k) => k.sana === sana);
		if (i === -1 || j === -1) return yukla();
		const q = d.qatorlar[i];
		const eski = q.kunlar[j].koef || 0;
		q.kunlar[j].koef = koef;
		q.kunlar[j].holat = "saqlangan";
		q.koef_yigindi = (q.koef_yigindi || 0) - eski + koef;
		// kelgan kun (pitaniya bazasi) — soati/koefi 0 dan katta kunlar
		q.kelgan_kun = q.kunlar.filter((k) => (k.koef || 0) > 0).length;
		const eskiJami = q.jami, eskiPit = q.pitaniya;
		// pitaniya avtomatik bo'lsa kelgan kun bilan birga o'zgaradi
		q.pitaniya_avto = q.kelgan_kun * (q.pitaniya_kunlik || 0);
		if (q.pitaniya_manba !== "qolda") q.pitaniya = q.pitaniya_avto;
		// hisob — backend (_jami_yaxlitla) bilan bir xil: ming so'mga pastga
		q.hisob_avto = Math.floor((q.kunlik_narx * q.koef_yigindi + (q.bonus || 0)) / 1000) * 1000;
		if (q.jami_manba !== "qolda") q.hisob = q.hisob_avto;
		const ushlov = (q.nalog || 0) + (q.pitaniya || 0);
		q.jami = Math.max(0, q.hisob - ushlov);
		q.jami_avto = Math.max(0, q.hisob_avto - ushlov);
		d.jami_oylik += q.jami - eskiJami;
		d.jami_pitaniya += q.pitaniya - eskiPit;

		const $tr = $joy.find(`tbody tr[data-xodim="${xodim}"]`);
		$tr.find(`td.ot-kun[data-j="${j}"]`).removeClass("default").addClass("saqlangan").text(koefFmt(koef));
		$tr.find("td.ot-c-kelgan").html(q.tolov_turi === "soat"
			? `${koefFmt(q.koef_yigindi)} <small>soat</small>` : koefFmt(q.koef_yigindi));
		$tr.find("td.ot-c-jami-t").html(fmt(q.jami)
			+ (q.jami_manba === "qolda" ? `<span class="ot-manba-kassa" style="color:#b26a00">qo'lda</span>` : ""));
		if (q.pitaniya_manba !== "qolda") {
			$tr.find('td.ot-c-ushlov[data-tur="pitaniya"]')
				.toggleClass("bosh", !q.pitaniya)
				.text(q.pitaniya ? "−" + fmt(q.pitaniya) : "0");
		}
		$joy.find("tfoot td.ot-c-ushlov").eq(1).text(fmt(d.jami_pitaniya));
		$joy.find(".ot-plitka .son").eq(3).text("−" + fmt((d.jami_nalog || 0) + (d.jami_pitaniya || 0)));
		$joy.find("tfoot td.ot-c-kelgan").text(koefFmt(d.qatorlar.reduce((s, x) => s + (x.koef_yigindi || 0), 0)));
		$joy.find("tfoot td.ot-c-jami").text(fmt(d.jami_oylik));
		$joy.find(".ot-plitka .son").eq(1).text(fmt(d.jami_oylik));
	}

	function oylikDialog(q) {
		const izoh =
			q.oylik.manba === "kassa"
				? "Bu summa Kassa'dagi oxirgi oy to'lovlaridan taklif sifatida olingan. Saqlasangiz FAQAT shu oy uchun qotiriladi."
				: q.oylik.manba === "yoq"
					? "Bu xodimga hali oylik kiritilmagan (Kassa'da to'lov ham topilmadi)."
					: "FAQAT SHU OY uchun saqlanadi — boshqa oylarning oyligi o'zgarmaydi. (Eng so'nggi oy tahrirlansa Employee'dagi \"Oylik ish haqi (shartnoma)\" ham yangilanadi.)";
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
			title: `${q.ismi} — bonus / jarima (${holat.data.oy_nomi})`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Bonus / jarima (so'm)",
				default: q.bonus, reqd: 1,
				description: "Musbat — bonus, MANFIY — jarima (masalan -500000), 0 — olib tashlash",
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
			title: `${q.ismi} — ${holat.data.oy_nomi} uchun norma ish kuni`,
			fields: [{
				fieldtype: "Int", fieldname: "kun", label: `Ish kuni (${holat.data.oy_nomi} ${holat.data.yil})`,
				default: q.ish_kuni, reqd: 1,
				description: "Kunlik narx = oylik / shu son. FAQAT SHU OYGA saqlanadi — " +
					"boshqa oylarga ta'sir qilmaydi (kiritilmagan oylarda default: o'qituvchi 21, boshqalar 26).",
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

	function jamiDialog(q) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — jami oylik (${holat.data.oy_nomi} ${holat.data.yil})`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Jami oylik (so'm)",
				default: q.jami, reqd: 1,
				description: `Avtomatik hisob: ${fmt(q.jami_avto)} so'm. Qo'lda kiritilgan summa FAQAT shu oy uchun yakuniy JAMI bo'ladi (bonus ham ichida). 0 kiritsangiz avtomatik hisobga qaytadi.`,
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.set_jami",
					args: { xodim: q.xodim, yil: holat.yil, oy: holat.oy, summa: v.summa },
					freeze: true,
					callback: () => yukla(),
				});
			},
		});
		dlg.show();
	}

	function nalogDialog(q) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — nalog (${holat.data.oy_nomi} ${holat.data.yil})`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Nalog (so'm)",
				default: q.nalog, reqd: 0,
				description: "Qo'lda kiritiladi (avtomatik hisoblanmaydi). FAQAT shu oy uchun " +
					"saqlanadi va JAMI'dan ayriladi. 0 kiritsangiz — nalog olib tashlanadi.",
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				frappe.call({
					method: "target_zenit.target_zenit.api.oylik_tabel.set_nalog",
					args: { xodim: q.xodim, yil: holat.yil, oy: holat.oy, summa: v.summa || 0 },
					freeze: true,
					callback: () => yukla(),
				});
			},
		});
		dlg.show();
	}

	function pitaniyaDialog(q) {
		const dlg = new frappe.ui.Dialog({
			title: `${q.ismi} — pitaniya (${holat.data.oy_nomi} ${holat.data.yil})`,
			fields: [{
				fieldtype: "Currency", fieldname: "summa", label: "Pitaniya (so'm)",
				default: q.pitaniya, reqd: 0,
				description: `Avtomatik hisob: ${q.kelgan_kun} kelgan kun × ${fmt(q.pitaniya_kunlik)} = `
					+ `<b>${fmt(q.pitaniya_avto)}</b> so'm. Qo'lda kiritilgan summa FAQAT shu oy uchun `
					+ `amal qiladi (0 ham saqlanadi — "ushlanmaydi"). Avtomatik hisobga qaytarish uchun `
					+ `"🔄 Avtoga qaytarish" tugmasini bosing.`,
			}],
			primary_action_label: "Saqlash",
			primary_action: (v) => {
				dlg.hide();
				saqlaPitaniya(q, { summa: v.summa || 0 });
			},
			secondary_action_label: "🔄 Avtoga qaytarish",
			secondary_action: () => {
				dlg.hide();
				saqlaPitaniya(q, { avto: 1 });
			},
		});
		dlg.show();
	}

	function saqlaPitaniya(q, args) {
		frappe.call({
			method: "target_zenit.target_zenit.api.oylik_tabel.set_pitaniya",
			args: Object.assign({ xodim: q.xodim, yil: holat.yil, oy: holat.oy }, args),
			freeze: true,
			callback: () => yukla(),
		});
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
