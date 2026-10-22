// Copyright (c) 2026, Target Zenit

frappe.ui.form.on("Moodle User Link", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Kirish ma'lumotlarini ko'rsatish"), () => {
			frappe.call({
				method: "target_zenit.integrations.moodle.parolni_korsat",
				args: { link_name: frm.doc.name },
				freeze: true,
				callback: (r) => {
					if (!r.message) return;
					const m = r.message;
					const esc = frappe.utils.escape_html;
					const parol = m.parol
						? `<code style="font-size:15px">${esc(m.parol)}</code>`
						: `<span class="text-muted">${__("saqlanmagan — parol faqat akkaunt yaratilganda yoziladi")}</span>`;
					frappe.msgprint({
						title: __("Moodle kirish ma'lumotlari"),
						message: `
							<table class="table table-bordered" style="margin:0">
								<tr><td width="35%"><b>${__("F.I.Sh.")}</b></td><td>${esc(m.full_name || "")}</td></tr>
								<tr><td><b>${__("Login")}</b></td><td><code style="font-size:15px">${esc(m.login || "")}</code></td></tr>
								<tr><td><b>${__("Boshlang'ich parol")}</b></td><td>${parol}</td></tr>
								<tr><td><b>${__("Email")}</b></td><td>${esc(m.email || "")}</td></tr>
								<tr><td><b>${__("Holat")}</b></td><td>${esc(m.holat || "")}</td></tr>
							</table>
							<p class="text-muted" style="margin-top:10px">
								${__("Bu parol faqat birinchi kirish uchun. Foydalanuvchi uni Moodle'da o'zgartirgandan keyin bu qiymat eskiradi.")}
							</p>`,
						indicator: m.parol ? "green" : "orange",
					});
				},
			});
		}).addClass("btn-primary");

		if (frm.doc.moodle_user_id) {
			frm.add_custom_button(__("Moodle'da ochish"), () => {
				frappe.db.get_single_value("Moodle Settings", "base_url").then((url) => {
					if (!url) {
						frappe.msgprint(__("Moodle Settings'da manzil kiritilmagan."));
						return;
					}
					window.open(`${url.replace(/\/$/, "")}/user/profile.php?id=${frm.doc.moodle_user_id}`, "_blank");
				});
			});
		}
	},
});
