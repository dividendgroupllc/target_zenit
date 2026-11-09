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

	load(fan) {
		this.body.html(`<div class="ry-load">${__("Yuklanmoqda")}…</div>`);
		frappe.call({
			method: `${RY_M}.tanlov`,
			args: { fan: fan || undefined },
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
								<option value="">— ${__("fanni tanlang")} —</option>
								${(t.fanlar || []).map((f) =>
									`<option value="${this.esc(f.name)}" ${f.name === t.fan ? "selected" : ""}>${this.esc(f.nomi)} (${f.darslar} ${__("dars")})</option>`).join("")}
							</select>
						</label>
						<label>${__("Guruhni qidirish")}
							<input type="text" class="ry-qidir" placeholder="${__("masalan: Low, 6-7, Python")}">
						</label>
					</div>
					<div class="ry-guruhlar"></div>
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
		// Fan o'zgarsa — guruhlar ro'yxati SHU fanga qarab qayta yuklanadi
		this.body.find(".ry-fan").on("change", (e) => { this.bekor(); this.load(e.target.value); });
		this.body.find(".ry-qidir").on("input", (e) => {
			this.qidiruv = e.target.value; this.guruhlarChiz();
		});
		this.guruhlarChiz();

		// Fan o'zgarganda sahifa qayta chiziladi — yuklangan fayl va qidiruv
		// matni yo'qolib ketmasligi kerak (zavuch faylni qaytadan tanlamasin)
		if (this.qidiruv) this.body.find(".ry-qidir").val(this.qidiruv);
		if (this.fayl) {
			this.body.find(".ry-fname").text(this.fayl.file_name || this.fayl.file_url);
			this.body.find(`[data-act="tekshir"]`).prop("disabled", false);
		}
	}

// Guruhlar TURLARGA ajratilgan holda: Sinf (5 A, 5 B…), Daraja (ENGLISH
	// Low 6-7, MATH High 5…), Tanlov (CHOICE IT 9-11), Qo'shma (P.E 5A+5B).
	// Maktabda 79 guruh bor va ularning aksariyati raqamli sinf EMAS — oqim
	// guruhlarining har biriga alohida reja kerak, chunki Low va High da
	// mavzular bir xil bo'lmaydi.
	guruhlarChiz() {
		const box = this.body.find(".ry-guruhlar");
		const t = this.tanlov;
		const turlar = t.turlar || [];
		if (!t.fan) {
			box.html(`<div class="ry-hint">${__("Guruhlar fan tanlangandan keyin ko'rinadi — shu fandan darsi bor guruhlar.")}</div>`);
			return;
		}
		if (!turlar.length) {
			box.html(`<div class="ry-warn">${__("Bu fandan jadvalda darsi bor guruh topilmadi.")}</div>`);
			return;
		}
		const q = (this.qidiruv || "").toLowerCase();
		const mos = (g) => !q || g.nomi.toLowerCase().includes(q)
			|| (g.daraja || "").toLowerCase().includes(q) || (g.blok || "").toLowerCase().includes(q);

		box.html(`
			<div class="ry-gt">
				<b>${__("Guruhlar")}</b> — ${__("rejani olishi kerak guruhlarni belgilang")}
				<span class="ry-gsay"></span>
			</div>
			${turlar.map((tr) => {
				const list = (tr.guruhlar || []).filter(mos);
				if (!list.length) return "";
				return `<div class="ry-gtur">
					<div class="ry-gturt">${this.esc(tr.turi)}
						<a href="#" data-tur="${this.esc(tr.turi)}" data-act="g-tur">${__("barchasi")}</a></div>
					<div class="ry-gl">
						${list.map((g) => `<label class="ry-g" title="${this.esc(g.blok || g.daraja || "")}">
							<input type="checkbox" value="${this.esc(g.name)}" data-tur="${this.esc(tr.turi)}">
							<span>${this.esc(g.nomi)}</span>
							<i>${g.darslar}</i></label>`).join("")}
					</div>
				</div>`;
			}).join("")}
			<div class="ry-hint">${__("Bir xil mavzular bir nechta guruhga tegishli bo'lsa (masalan 5 A va 5 B) — ularni birga belgilang, bitta reja yaratiladi. Low va High kabi oqimlarga esa ALOHIDA yuklang.")}</div>
		`);

		box.find(`[data-act="g-tur"]`).on("click", (e) => {
			e.preventDefault();
			const tur = $(e.currentTarget).data("tur");
			const inp = box.find(`input[data-tur="${tur}"]`);
			const hammasi = inp.filter(":checked").length === inp.length;
			inp.prop("checked", !hammasi);
			this.bekor();
		});
		box.find("input").on("change", () => this.bekor());
		this.sanaChiz();
	}

	// Nechta guruh belgilangani — tasdiqlashdan oldin ko'rinib turishi uchun
	sanaChiz() {
		const n = this.tanlanganGuruhlar().length;
		this.body.find(".ry-gsay").text(n ? ` · ${n} ${__("tanlandi")}` : "");
	}

		// Tanlov o'zgarganda tasdiq tugmalarini yopamiz — tekshirilmagan narsa saqlanmaydi
	bekor() {
		this.sanaChiz();
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
				// UCH XIL JAVOB: xato / yuborilmadi (sababi bilan) / tayyor.
				// «Yuborildi: 0 mavzu» deb ko'rsatish eng yomoni edi —
				// foydalanuvchi nima qilish kerakligini bilmaydi.
				let xabar;
				let rang = "green";
				if (m.xato) {
					rang = "red";
					xabar = this.esc(m.xato).replace(/\n/g, "<br>");
				} else if (m.holat === "o'chirilgan") {
					rang = "orange";
					xabar = __("Moodle integratsiyasi o'chirilgan (Moodle Settings -> Enabled).");
				} else if (m.holat === "yuborilmadi" || !m.yuborildi) {
					rang = "orange";
					xabar = `<b>${__("Yuborilmadi — yuboriladigan mavzu topilmadi.")}</b>`
						+ `<br><br>${__("Sababi")}: ${this.esc(m.sabab || "—")}`
						+ (m.oquv_yili ? `<br>${__("O'quv yili")}: <b>${this.esc(m.oquv_yili)}</b>` : "")
						+ ((m.guruhsiz_rejalar || []).length
							? `<br>${__("Guruhsiz rejalar")}: ${m.guruhsiz_rejalar.map((x) => this.esc(x)).join(", ")}` : "")
						+ ((m.mavzusiz_rejalar || []).length
							? `<br>${__("Mavzusiz rejalar")}: ${m.mavzusiz_rejalar.map((x) => this.esc(x)).join(", ")}` : "");
				} else {
					xabar = __("Yuborildi: {0} mavzu · {1} darsga biriktirildi{2}", [
						m.yuborildi || 0,
						m.biriktirildi || 0,
						m.sigmagan ? ` · ${m.sigmagan} ${__("mavzu darsga sig'madi")}` : "",
					]) + ((m.ogohlantirish || []).length
						? `<ul>${m.ogohlantirish.map((x) => `<li>${this.esc(x)}</li>`).join("")}</ul>` : "");
				}
				frappe.msgprint({ title: __("Moodle"), indicator: rang, message: xabar });
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
