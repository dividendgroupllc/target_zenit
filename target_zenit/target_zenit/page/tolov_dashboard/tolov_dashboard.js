// Оплаты учеников — sinf x o'quvchi jadvali: forma / kitob / (yotoqxona) va
// oyma-oy nachisleniya qoldig'i + to'langan summa.
// Manba: target_zenit...tolov_dashboard.get_data (qarzdorlik enginesi rejalari).
// Panel FAQAT KO'RSATKICH — hech narsa yozmaydi.

frappe.pages["tolov-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Оплаты учеников",
		single_column: true,
	});

	const holat = {
		data: null,
		sinflar: [],        // tanlangan sinflar (bo'sh = hammasi)
		oylar: [],          // tanlangan oy kalitlari "YYYY-MM" (bo'sh = default)
		yotoqxona: 0,       // tepadagi belgi: yotoqxona ustunlari + ro'yxati
		qidiruv: "",
	};

	const $joy = $('<div class="td-wrap"></div>').appendTo(page.main);
	const nf = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
	const fmt = (n) => nf.format(Math.round(n || 0));
	const esc = (s) => frappe.utils.escape_html(String(s == null ? "" : s));
	// 0 bo'lsa chiziqcha — jadval "0" lar bilan to'lib ketmasin
	const son = (n) => (Math.abs(n || 0) < 0.5 ? "—" : fmt(n));

	function yukla() {
		frappe.call({
			method: "target_zenit.target_zenit.page.tolov_dashboard.tolov_dashboard.get_data",
			args: {
				sinflar: JSON.stringify(holat.sinflar),
				oylar: JSON.stringify(holat.oylar),
				yotoqxona: holat.yotoqxona,
			},
			freeze: true,
			freeze_message: "Загрузка…",
			callback: (r) => {
				if (!r.message) return;
				holat.data = r.message;
				chiz();
			},
		});
	}

	// Qidiruv bo'yicha qatorlarni ko'rsatish/yashirish (serverga bormaydi)
	function filtrla() {
		const q = (holat.qidiruv || "").toLowerCase();
		let korinadi = 0;
		$joy.find("tbody tr").each(function () {
			const mos = !q || String($(this).data("q") || "").includes(q);
			$(this).toggle(mos);
			if (mos) korinadi += 1;
		});
		$joy.find(".td-soni").text(korinadi);
	}

	// Ko'p tanlovli filtr (sinflar / oylar) — checkbox ro'yxat + ichki qidiruv
	function filtrMenyu({ nom, belgi, variantlar, tanlangan, ozgardi }) {
		const $f = $(`<div class="td-f">
			<button class="td-btn ${tanlangan.length ? "faol" : ""}">${belgi}${tanlangan.length ? ` · ${tanlangan.length}` : ""} ▾</button>
			<div class="td-f-menu" style="display:none">
				<input class="td-f-qidir" type="text" placeholder="Поиск…">
				<div class="td-f-list">${variantlar.map((v) => `<label>
					<input type="checkbox" value="${esc(v.kalit)}" ${tanlangan.indexOf(v.kalit) !== -1 ? "checked" : ""}>
					<span>${esc(v.nom)}</span></label>`).join("")}</div>
				<div class="td-f-foot">
					<button class="td-f-toza">✕ Сбросить</button>
					<button class="td-f-ok">Применить</button>
				</div>
			</div></div>`);
		const $btn = $f.find(".td-btn"), $menu = $f.find(".td-f-menu");
		$btn.on("click", (e) => { e.stopPropagation(); $(".td-f-menu").not($menu).hide(); $menu.toggle(); });
		$menu.on("click", (e) => e.stopPropagation());
		$menu.find(".td-f-qidir").on("input", function () {
			const s = $(this).val().toLowerCase();
			$menu.find("label").each(function () { $(this).toggle($(this).text().toLowerCase().includes(s)); });
		});
		$menu.find(".td-f-ok").on("click", () => {
			$menu.hide();
			ozgardi($menu.find("input[type=checkbox]:checked").map((i, el) => el.value).get());
		});
		$menu.find(".td-f-toza").on("click", () => { $menu.hide(); ozgardi([]); });
		$f.attr("data-nom", nom);
		return $f;
	}

	function chiz() {
		const d = holat.data;
		$joy.empty();

		// ---- sarlavha va filtrlar ----
		const $bosh = $(`<div class="td-bosh">
			<div>
				<h1>Оплаты учеников</h1>
				<div class="td-sub">Начисление и оплата: форма, книга${d.yotoqxona ? ", общежитие" : ""} и по месяцам ·
					учеников: <b class="td-soni">${d.soni}</b></div>
			</div>
			<div class="td-spacer"></div>
			<label class="td-btn ${d.yotoqxona ? "faol" : ""}" style="display:flex;gap:6px;align-items:center"
				title="Показать столбцы общежития и только тех учеников, у кого есть оплата за общежитие">
				<input type="checkbox" class="td-yotoq" ${d.yotoqxona ? "checked" : ""}> Общежитие
				<span class="td-bosh-guruh">(${d.yotoqxona_soni})</span>
			</label>
			<div class="td-qidiruv"><input type="text" placeholder="🔍 Поиск: ученик / группа" value="${esc(holat.qidiruv)}"></div>
		</div>`);

		$bosh.find(".td-spacer").after(
			filtrMenyu({
				nom: "sinf", belgi: "👥 Группы",
				variantlar: d.sinflar.map((s) => ({ kalit: s, nom: s })),
				tanlangan: holat.sinflar,
				ozgardi: (v) => { holat.sinflar = v; yukla(); },
			}),
			filtrMenyu({
				nom: "oy", belgi: "📅 Месяцы",
				variantlar: d.mavjud_oylar.map((o) => ({
					kalit: o.kalit,
					nom: `${o.nom} ${o.yil}${o.kalit === d.joriy_oy ? " · текущий" : ""}`,
				})),
				tanlangan: holat.oylar,
				ozgardi: (v) => { holat.oylar = v; yukla(); },
			})
		);
		$bosh.find(".td-yotoq").on("change", function () {
			holat.yotoqxona = this.checked ? 1 : 0;
			yukla();
		});
		$bosh.find(".td-qidiruv input").on("input", function () {
			holat.qidiruv = $(this).val().toLowerCase();
			filtrla();
		});
		$joy.append($bosh);
		$(document).off("click.tdf").on("click.tdf", () => $(".td-f-menu").hide());

		// ---- plitkalar: jami ostatka / to'lovlar ----
		const oyOst = d.oylar.reduce((s, o) => s + d.jami.oylar[o.kalit].ostatka, 0);
		const oyTol = d.oylar.reduce((s, o) => s + d.jami.oylar[o.kalit].tolangan, 0);
		const jamiOst = d.jami.forma.ostatka + d.jami.kitob.ostatka + oyOst
			+ (d.yotoqxona ? d.jami.yotoqxona.ostatka : 0);
		$joy.append(`<div class="td-plitkalar">
			<div class="td-plitka"><div class="son qizil">${fmt(jamiOst)}</div><div class="nom">Общий остаток (сум)</div></div>
			<div class="td-plitka"><div class="son qizil">${fmt(oyOst)}</div><div class="nom">Остаток по месяцам</div></div>
			<div class="td-plitka"><div class="son">${fmt(oyTol)}</div><div class="nom">Оплачено по месяцам</div></div>
			<div class="td-plitka"><div class="son qizil">${fmt(d.jami.forma.ostatka)}</div><div class="nom">Форма остаток</div></div>
			<div class="td-plitka"><div class="son qizil">${fmt(d.jami.kitob.ostatka)}</div><div class="nom">Книга остаток</div></div>
			${d.yotoqxona ? `<div class="td-plitka"><div class="son qizil">${fmt(d.jami.yotoqxona.ostatka)}</div><div class="nom">Общежитие остаток</div></div>` : ""}
		</div>`);

		// ---- jadval sarlavhasi ----
		// Har bir blok (forma / kitob / yotoqxona / oy) ikki ustun: остатка + оплата
		const bloklar = [
			{ kalit: "forma", nom: "Форма" },
			{ kalit: "kitob", nom: "Книга" },
		];
		if (d.yotoqxona) bloklar.push({ kalit: "yotoqxona", nom: "Общежитие" });
		const oyBloklar = d.oylar.map((o) => ({ kalit: o.kalit, nom: o.label, oy: true }));

		let th = `<tr><th class="td-c-sinf">Группа</th><th class="td-c-ism">Ученик</th>`;
		bloklar.concat(oyBloklar).forEach((b) => {
			th += `<th class="ost-bosh${b.oy ? " oy-bosh" : ""}">${esc(b.nom)} остатка</th>`;
			th += `<th${b.oy ? ' class="oy-bosh"' : ""}>${esc(b.nom)}</th>`;
		});
		th += "</tr>";

		// ---- qatorlar ----
		const katak = (v, tur) =>
			`<td class="${tur}${Math.abs(v || 0) < 0.5 ? " nol" : ""}">${son(v)}</td>`;
		let rows = "";
		d.qatorlar.forEach((q) => {
			let tr = `<tr data-q="${esc(((q.sinf || "") + " " + (q.ism || "")).toLowerCase())}">
				<td class="td-c-sinf">${esc(q.sinf || "—")}</td>
				<td class="td-c-ism" title="${esc(q.ism)}">${esc(q.ism)}</td>`;
			bloklar.forEach((b) => {
				tr += katak(q[b.kalit].ostatka, "ost") + katak(q[b.kalit].tolangan, "tol");
			});
			d.oylar.forEach((o) => {
				const v = q.oylar[o.kalit] || { ostatka: 0, tolangan: 0 };
				tr += katak(v.ostatka, "ost") + katak(v.tolangan, "tol");
			});
			rows += tr + "</tr>";
		});
		if (!rows) {
			const ustun = 2 + (bloklar.length + d.oylar.length) * 2;
			rows = `<tr><td colspan="${ustun}" class="td-empty">Ничего не найдено</td></tr>`;
		}

		// ---- jami qatori ----
		let foot = `<tr><td class="td-c-sinf">ИТОГО</td><td class="td-c-ism">${d.soni} ученик</td>`;
		bloklar.forEach((b) => {
			foot += `<td class="ost">${son(d.jami[b.kalit].ostatka)}</td><td>${son(d.jami[b.kalit].tolangan)}</td>`;
		});
		d.oylar.forEach((o) => {
			const j = d.jami.oylar[o.kalit];
			foot += `<td class="ost">${son(j.ostatka)}</td><td>${son(j.tolangan)}</td>`;
		});
		foot += "</tr>";

		$joy.append(`<div class="td-orab"><table class="td-jadval">
			<thead>${th}</thead><tbody>${rows}</tbody><tfoot>${foot}</tfoot></table></div>`);
		$joy.append(`<div class="td-sub" style="margin-top:8px">
			«Остатка» — начислено минус оплачено (красным). Месяцы берутся из начислений:
			по умолчанию текущий месяц и следующие; в фильтре можно выбрать любые прошлые месяцы.
			Форма и книга считаются по позициям счёта (Forma / Kitob) пропорционально.
		</div>`);
		filtrla();

		page.clear_inner_toolbar();
		page.add_inner_button("↻ Обновить", () => yukla());
	}

	yukla();
};
