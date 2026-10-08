// Copyright (c) 2026, Target Zenit
// O'quvchi shartnoma summalari — formada jonli hisob:
//   chegirma = tarif x foiz / 100  |  yakuniy = tarif - chegirma  |  oylik = yakuniy / 10
// Server tomoni (student_tarif.py) ham xuddi shunday hisoblaydi — import/API uchun.
frappe.ui.form.on("Student", {
	custom_tariff_amount(frm) { tz_tarif_foizdan(frm); },
	custom_discount_foiz(frm) { tz_tarif_foizdan(frm); },
	custom_discount_amount(frm) { tz_tarif_summadan(frm); },
});

const TZ_OYLAR = 10;

// Foiz (yoki tarif) o'zgardi -> chegirma summasini foizdan hisoblaymiz
function tz_tarif_foizdan(frm) {
	const tarif = flt(frm.doc.custom_tariff_amount);
	if (!tarif) return;
	const foiz = flt(frm.doc.custom_discount_foiz);
	const chegirma = Math.round((tarif * foiz) / 100);
	frm.set_value("custom_discount_amount", chegirma);
	tz_tarif_yakun(frm, tarif, chegirma);
}

// Chegirma summasi qo'lda kiritildi -> foizni ko'rsatamiz
function tz_tarif_summadan(frm) {
	const tarif = flt(frm.doc.custom_tariff_amount);
	if (!tarif) return;
	const chegirma = Math.min(Math.max(flt(frm.doc.custom_discount_amount), 0), tarif);
	const foiz = Math.round((chegirma / tarif) * 1000000) / 10000;
	if (flt(frm.doc.custom_discount_foiz).toFixed(4) !== foiz.toFixed(4)) {
		frm.set_value("custom_discount_foiz", foiz);
	}
	tz_tarif_yakun(frm, tarif, chegirma);
}

function tz_tarif_yakun(frm, tarif, chegirma) {
	const yakuniy = Math.round(tarif - chegirma);
	frm.set_value("custom_final_amount", yakuniy);
	frm.set_value("custom_monthly_payment", Math.round(yakuniy / TZ_OYLAR));
}
