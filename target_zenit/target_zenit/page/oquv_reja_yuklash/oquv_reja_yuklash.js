// Copyright (c) 2026, Target Zenit
//
// MAVZULARNI YUKLASH (KTP) — zam direktor uchun.
//
// OQIM: fan + guruhlarni tanla → Excel yukla → TEKSHIR (hech narsa yozilmaydi)
// → natijani ko'r → TASDIQLA (Oquv Reja saqlanadi) → MOODLE'ga yubor.
//
// «Tekshir» bosqichi ataylab majburiy: 900+ mavzuni ko'rmasdan saqlash
// zavuchni tuzatib bo'lmaydigan ahvolda qoldiradi (noto'g'ri chorak, tanilmagan
// fan). Shuning uchun «Tasdiqla» tugmasi dry-run natijasidan keyin ochiladi.

const RY_M = "target_zenit.oquv_reja_excel";
const RY_MOODLE = "target_zenit.integrations.moodle_mavzu";

frappe.pages["oquv-reja-yuklash"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Mavzularni yuklash (KTP)"),
		single_column: true,
	});
	new TZRejaYuklash(page);
};

class TZRejaYuklash {
	constructor(page) {
		this.page = page;
		this.body = $(`<div class="tz-ry"></div>`).appendTo(page.main);
		this.fayl = null;       // {file_url, file_name}
		this.tekshirildi = null; // oxirgi dry-run natijasi
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }

	load() {
		this.body.html(`<div class="ry-load">${__("Yuklanmoqda")}…</div>`);
		frappe.call({
			method: `${RY_M}.tanlov`,
			callback: (r) => { this.tanlov = r.message || {}; this.render(); },
			error: () => this.body.html(`<div class="ry-load">${__("Xatolik")}.</div>`),
		});
	}

	render() {
		const t = this.tanlov;
		const darajalar = t.darajalar || [];
		this.body.html(`
			<div class="ry-head">
				<div>
					<h1>${__("Mavzularni yuklash")}</h1>
					<div class="ry-sub">${__("O'quv yili")}: <b>${this.esc(t.oquv_yili || "—")}</b>
						· ${__("Excel'dan o'quv rejasiga, so'ng Moodle dars jadvaliga")}</div>
				</div>
				<button class="btn btn-default btn-sm" data-act="shablon">⬇ ${__("Namuna shablon")}</button>
			</div>

			<div class="ry-step">
				<div class="ry-n">1</div>
				<div class="ry-c">
					<div class="ry-t">${__("Fan va guruhlarni tanlang")}</div>
					<div class="ry-grid">
						<label>${__("Fan")}
							<select class="ry-fan">
								<option value="">— ${__("Excel'dagi «Fan» ustunidan olinadi")} —</option>
								${(t.fanlar || []).map((f) =>
									`<option value="${this.esc(f.name)}">${this.esc(f.course_name || f.name)}</option>`).join("")}
							</select>
						</label>
						<label>${__("Sinf darajasi")}
							<select class="ry-daraja">
								<option value="">— ${__("Excel'dagi «Sinf» ustunidan olinadi")} —</option>
								${darajalar.map((d) =>
									`<option value="${this.esc(d.daraja)}">${this.esc(d.daraja)}-${__("sinf")}
										(${(d.guruhlar || []).length} ${__("guruh")})</option>`).join("")}
							</select>
						</label>
					</div>
					<div class="ry-guruhlar"></div>
					<div class="ry-hint">${__("Reja parallel guruhlarga bitta bo'ladi. Guruh tanlanmasa — shu darajadagi barcha guruhlar biriktiriladi.")}</div>
				</div>
			</div>

			<div class="ry-step">
				<div class="ry-n">2</div>
				<div class="ry-c">
					<div class="ry-t">${__("Excel faylni yuklang")}</div>
					<div class="ry-file">
						<button class="btn btn-default btn-sm" data-act="fayl">📄 ${__("Fayl tanlash")}</button>
						<span class="ry-fname">${__("fayl tanlanmagan")}</span>
					</div>
					<div class="ry-hint">${__("Ustunlar")}: <code>Chorak | № | Bo'lim | Mavzu | Soat | Dars turi</code>
						— ${__("yuqorida fan/sinf tanlangan bo'lsa «Fan» va «Sinf» ustunlari shart emas")}</div>
				</div>
			</div>

			<div class="ry-step">
				<div class="ry-n">3</div>
				<div class="ry-c">
					<div class="ry-t">${__("Tekshirish va tasdiqlash")}</div>
					<div class="ry-acts">
						<button class="btn btn-default btn-sm" data-act="tekshir" disabled>🔍 ${__("Tekshirish")}</button>
						<button class="btn btn-primary btn-sm" data-act="saqla" disabled>✓ ${__("Tasdiqlash va saqlash")}</button>
						<button class="btn btn-default btn-sm" data-act="moodle" disabled>↗ ${__("Moodle'ga yuborish")}</button>
					</div>
					<div class="ry-natija"></div>
				</div>
			</div>
		`);

		this.body.find(`[data-act="shablon"]`).on("click", () => this.shablon());
		this.body.find(`[data-act="fayl"]`).on("click", () => this.faylTanla());
		this.body.find(`[data-act="tekshir"]`).on("click", () => this.yubor(1));
		this.body.find(`[data-act="saqla"]`).on("click", () => this.tasdiq());
		this.body.find(`[data-act="moodle"]`).on("click", () => this.moodle());
		this.body.find(".ry-daraja").on("change", (e) => this.guruhlarChiz(e.target.value));
		// Tanlov o'zgarsa — eski tekshiruv natijasi endi to'g'ri emas
		this.body.find(".ry-fan, .ry-daraja").on("change", () => this.bekor());
	}

	guruhlarChiz(daraja) {
		const d = (this.tanlov.darajalar || []).find((x) => x.daraja === daraja);
		const box = this.body.find(".ry-guruhlar");
		if (!d) { box.empty(); return; }
		box.html(`
			<div class="ry-gt">${__("Guruhlar")}
				<a href="#" data-act="g-all">${__("hammasi")}</a> ·
				<a href="#" data-act="g-none">${__("hech biri")}</a></div>
			<div class="ry-gl">
				${(d.guruhlar || []).map((g) => `
					<label class="ry-g"><input type="checkbox" value="${this.esc(g.name)}" checked>
						<span>${this.esc(g.nomi)}</span></label>`).join("")}
			</div>`);
		box.find(`[data-act="g-all"]`).on("click", (e) => {
			e.preventDefault(); box.find("input").prop("checked", true); this.bekor();
		});
		box.find(`[data-act="g-none"]`).on("click", (e) => {
			e.preventDefault(); box.find("input").prop("checked", false); this.bekor();
		});
		box.find("input").on("change", () => this.bekor());
	}

	// Tanlov o'zgarganda tasdiq tugmalarini yopamiz — tekshirilmagan narsa saqlanmaydi
	bekor() {
		this.tekshirildi = null;
		this.body.find(`[data-act="saqla"], [data-act="moodle"]`).prop("disabled", true);
	}

	tanlanganGuruhlar() {
		return this.body.find(".ry-guruhlar input:checked").map((i, el) => el.value).get();
	}

	shablon() {
		frappe.call({
			method: `${RY_M}.namuna_shablon`, freeze: true,
			callback: (r) => { if (r.message) window.open(r.message.file_url); },
		});
	}

	faylTanla() {
		new frappe.ui.FileUploader({
			restrictions: { allowed_file_types: [".xlsx", ".xls"] },
			on_success: (fayl) => {
				this.fayl = fayl;
				this.body.find(".ry-fname").text(fayl.file_name || fayl.file_url);
				this.body.find(`[data-act="tekshir"]`).prop("disabled", false);
				this.bekor();
			},
		});
	}

	yubor(dry_run) {
		if (!this.fayl) { frappe.msgprint(__("Avval Excel faylni yuklang.")); return; }
		const guruhlar = this.tanlanganGuruhlar();
		frappe.call({
			method: `${RY_M}.import_excel`,
			args: {
				path: this.fayl.file_url,
				dry_run: dry_run,
				fan: this.body.find(".ry-fan").val() || undefined,
				guruhlar: guruhlar.length ? JSON.stringify(guruhlar) : undefined,
			},
			freeze: true,
			freeze_message: dry_run ? __("Tekshirilmoqda…") : __("Saqlanmoqda…"),
			callback: (r) => {
				const m = r.message || {};
				this.natijaChiz(m, dry_run);
				if (m.holat === "tayyor" && m.rejalar) {
					if (dry_run) {
						this.tekshirildi = m;
						this.body.find(`[data-act="saqla"]`).prop("disabled", false);
					} else {
						this.body.find(`[data-act="moodle"]`).prop("disabled", false);
						frappe.show_alert({ message: __("Saqlandi"), indicator: "green" });
					}
				}
			},
		});
	}

	tasdiq() {
		const m = this.tekshirildi;
		if (!m) { frappe.msgprint(__("Avval «Tekshirish»ni bosing.")); return; }
		frappe.confirm(
			__("{0} reja, {1} mavzu saqlanadi. Fayldagi choraklarning eski mavzulari almashtiriladi. Davom etasizmi?",
				[m.rejalar, m.mavzular]),
			() => this.yubor(0));
	}

	moodle() {
		frappe.call({
			method: `${RY_MOODLE}.push_now`, freeze: true,
			freeze_message: __("Moodle'ga yuborilmoqda…"),
			callback: (r) => {
				const m = r.message || {};
				frappe.msgprint({
					title: __("Moodle"),
					indicator: m.xato ? "red" : "green",
					message: m.xato
						? this.esc(m.xato)
						: __("Yuborildi: {0} mavzu, {1} dars biriktirildi.",
							[m.qatorlar || 0, m.biriktirildi ?? "—"]),
				});
			},
		});
	}

	natijaChiz(m, dry_run) {
		const box = this.body.find(".ry-natija");
		if (m.holat === "xato") {
			box.html(`<div class="ry-err"><b>${__("Yuklanmadi")}:</b><ul>
				${(m.xatolar || []).map((x) => `<li>${this.esc(x)}</li>`).join("")}</ul></div>`);
			return;
		}
		box.html(`
			<div class="ry-ok ${dry_run ? "ry-dry" : ""}">
				${dry_run ? `<b>${__("Tekshiruv")}</b> — ${__("hech narsa yozilmadi")}`
				          : `<b>${__("Saqlandi")}</b>`}
				· ${m.qatorlar} ${__("qator")} · ${m.rejalar} ${__("reja")} · ${m.mavzular} ${__("mavzu")}
			</div>
			${(m.xatolar || []).length ? `<div class="ry-warn"><b>${__("Diqqat")}:</b><ul>
				${m.xatolar.map((x) => `<li>${this.esc(x)}</li>`).join("")}</ul></div>` : ""}
			<table class="ry-tbl">
				<thead><tr>
					<th>${__("Fan")}</th><th>${__("Sinf")}</th><th>${__("Choraklar")}</th>
					<th class="r">${__("Mavzu")}</th><th>${__("Guruhlar")}</th><th>${__("Reja")}</th>
				</tr></thead>
				<tbody>
					${(m.tafsilot || []).map((s) => `<tr>
						<td>${this.esc(s.fan)}</td>
						<td>${this.esc(s.daraja)}</td>
						<td>${(s.choraklar || []).map((c) => `<span class="ry-ch">${this.esc(c)}</span>`).join("")}</td>
						<td class="r"><b>${s.mavzular}</b>${s.saqlandi ? `<span class="mini"> +${s.saqlandi} ${__("eski")}</span>` : ""}</td>
						<td class="mini">${(s.guruhlar || []).map((g) => this.esc(g)).join(", ") || "—"}</td>
						<td class="mini">${s.yangi_reja ? `<span class="ry-new">${__("yangi")}</span> ` : ""}${this.esc(s.reja)}</td>
					</tr>`).join("")}
				</tbody>
			</table>
			${dry_run ? `<div class="ry-hint">${__("To'g'ri bo'lsa «Tasdiqlash va saqlash»ni bosing.")}</div>` : ""}
		`);
	}
}
