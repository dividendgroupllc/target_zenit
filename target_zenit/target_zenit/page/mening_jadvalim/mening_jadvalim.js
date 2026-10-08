// Copyright (c) 2026, Target Zenit — "Mening jadvalim" (o'qituvchi)
// Bugungi darslar (davomat olish tugmasi bilan) + haftalik jadval.
frappe.pages["mening-jadvalim"].on_page_load = function (wrapper) {
	new TZMeningJadvalim(wrapper);
};

const MJ_M = "target_zenit.target_zenit.page.mening_jadvalim.mening_jadvalim";

class TZMeningJadvalim {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Mening jadvalim"), single_column: true });
		this.oqituvchi = null;
		this.make_skeleton();
		this.load();
	}

	esc(s) { return frappe.utils.escape_html(String(s == null ? "" : s)); }
	rang(fan) { let h = 0; for (const ch of String(fan || "")) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; }

	make_skeleton() {
		this.wrapper.find(".page-head").hide();
		this.wrapper.find(".layout-main-section-wrapper").addClass("tz-fullbleed-wrap");
		this.wrapper.find(".container").addClass("tz-container-fluid");
		this.body = $(`<div class="tz-jadval tz-mening"><div class="loading">Yuklanmoqda…</div></div>`)
			.appendTo(this.wrapper.find(".layout-main-section"));
	}

	load() {
		frappe.call({
			method: `${MJ_M}.get_data`,
			args: { oqituvchi: this.oqituvchi },
			callback: (r) => { this.data = r.message || {}; this.render(); },
			error: () => this.body.html(`<div class="loading">Xatolik.</div>`),
		});
	}

	render() {
		const d = this.data;
		if (!d.oqituvchi) {
			this.body.html(`<div class="loading">Sizning hisobingizga o'qituvchi (Instructor) yozuvi bog'lanmagan.<br>
				Iltimos, administratorga murojaat qiling.</div>`);
			return;
		}
		const bugungi = (d.darslar || []).filter((x) => x.kun === d.bugun_kuni);
		const kunlar = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma"];

		this.body.html(`
			<div class="topbar">
				<div>
					<h1>${this.esc(d.oqituvchi_nomi || "Mening jadvalim")}</h1>
					<div class="sub">${this.esc(d.versiya || "")} · haftalik ${d.haftalik_soat || 0} dars · bugun ${this.esc(d.bugun_kuni)}</div>
				</div>
				<div class="spacer"></div>
				${d.menejer ? `<select class="foqituvchi">
					<option value="">— o'qituvchini tanlang —</option>
					${(d.oqituvchilar || []).map((o) => `<option value="${this.esc(o.name)}" ${o.name === d.oqituvchi ? "selected" : ""}>${this.esc(o.instructor_name)}</option>`).join("")}
				</select>` : ""}
				<button class="refresh" data-act="reload"><span class="dot"></span> Yangilash</button>
			</div>

			<div class="card bugun">
				<div class="box-t">Bugungi darslar — ${this.esc(d.bugun_kuni)}</div>
				${bugungi.length ? bugungi.map((x) => `
					<div class="bugun-row" style="--h:${this.rang(x.fan)}">
						<div class="vaqt"><b>${x.dars_raqami}</b><span>${this.esc(x.boshlanish)}–${this.esc(x.tugash)}</span></div>
						<div class="info">
							<div class="fan">${this.esc(x.fan)}</div>
							<div class="guruh">${this.esc(x.guruh_nomi || x.guruh)}${x.sinflar ? ` · ${this.esc(x.sinflar)}` : ""}</div>
						</div>
						<button class="btn-dav" data-jy="${this.esc(x.name)}">Davomat olish</button>
					</div>`).join("")
					: `<div class="empty">Bugun dars yo'q</div>`}
			</div>

			<div class="hafta">
				${kunlar.map((k) => {
					const list = (d.darslar || []).filter((x) => x.kun === k);
					return `<div class="card kun-card ${k === d.bugun_kuni ? "bugun-card" : ""}">
						<div class="box-t">${k} <span class="mini">${list.length} dars</span></div>
						${list.map((x) => `<div class="w-row" style="--h:${this.rang(x.fan)}">
							<span class="no">${x.dars_raqami}</span>
							<span class="t">${this.esc(x.boshlanish)}</span>
							<span class="f">${this.esc(x.fan)}</span>
							<span class="g">${this.esc(x.sinflar || x.guruh_nomi || "")}</span>
						</div>`).join("") || `<div class="empty mini">—</div>`}
					</div>`;
				}).join("")}
			</div>
		`);

		this.body.find(`[data-act="reload"]`).on("click", () => this.load());
		this.body.find(".foqituvchi").on("change", (e) => { this.oqituvchi = e.target.value; this.load(); });
		this.body.find(".btn-dav").on("click", (e) => this.davomat($(e.currentTarget).data("jy")));
	}

	davomat(jy) {
		frappe.call({
			method: `${MJ_M}.davomat_ochish`,
			args: { jadval_yozuvi: jy },
			freeze: true,
			freeze_message: "Dars ochilmoqda…",
			callback: (r) => {
				if (r.message && r.message.course_schedule) {
					frappe.set_route("Form", "Course Schedule", r.message.course_schedule);
				}
			},
		});
	}
}
