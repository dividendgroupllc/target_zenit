# Copyright (c) 2026, Target Zenit
"""Mavjud Qarz Ishi'larga oxirgi aloqa izohini yozib qo'yish.

Yangi `oxirgi_komment` maydoni bundan keyin Aloqa Yozuvi kaskadida to'ladi;
bu patch eski yozuvlar uchun bir martalik to'ldirish (idempotent)."""

import frappe


def execute():
	if not frappe.get_meta("Qarz Ishi").has_field("oxirgi_komment"):
		return
	# Har ish uchun eng so'nggi (vaqt bo'yicha) izohli aloqa yozuvi
	qatorlar = frappe.db.sql(
		"""SELECT ay.qarz_ishi, ay.komment
		   FROM `tabAloqa Yozuvi` ay
		   JOIN (SELECT qarz_ishi, MAX(vaqt) oxirgi
		         FROM `tabAloqa Yozuvi`
		         WHERE IFNULL(komment, '') <> '' AND IFNULL(qarz_ishi, '') <> ''
		         GROUP BY qarz_ishi) t
		     ON t.qarz_ishi = ay.qarz_ishi AND t.oxirgi = ay.vaqt
		   WHERE IFNULL(ay.komment, '') <> ''""",
		as_dict=True,
	)
	n = 0
	for r in qatorlar:
		if not frappe.db.exists("Qarz Ishi", r.qarz_ishi):
			continue
		if frappe.db.get_value("Qarz Ishi", r.qarz_ishi, "oxirgi_komment"):
			continue
		frappe.db.set_value("Qarz Ishi", r.qarz_ishi, "oxirgi_komment", r.komment,
							update_modified=False)
		n += 1
	print(f"Qarz Ishi oxirgi izohi to'ldirildi: {n} ta")
