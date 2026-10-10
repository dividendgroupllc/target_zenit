// Copyright (c) 2026, Target Zenit
frappe.listview_settings["Telefon Qongirogi"] = {
	add_fields: ["tugash_sababi", "yozuv_bor", "suhbat_vaqti"],
	get_indicator(doc) {
		const rang = {
			"Javob berildi": "green",
			"Javob yo'q": "orange",
			Band: "orange",
			"O'chirilgan": "red",
			Xato: "red",
			"Bekor qilindi": "gray",
		};
		return [
			__(doc.tugash_sababi || "Noma'lum"),
			rang[doc.tugash_sababi] || "gray",
			"tugash_sababi,=," + (doc.tugash_sababi || ""),
		];
	},
};
