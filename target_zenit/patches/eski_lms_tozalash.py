"""Eski (ishlatilmagan) Frappe LMS qatlamini bazadan o'chiradi — 2026-11-08.

Davomat, baho, uy vazifa va dars bajarilishi MOODLE'ga ko'chdi. Frappe'dagi
nusxalari hech qachon ishlatilmagan (barchasida 0 qator, `Baho Turi`da 5 seed
va `Dars Bajarilishi`da 1 demo qator) va faqat chalkashlik berardi: zavuch
qaysi tizimda ishlashini bilmay qolardi.

Frappe endi faqat REJAni saqlaydi (`Oquv Reja` + `Oquv Reja Qatori`) va uni
Moodle'ga push qiladi (`integrations/moodle_mavzu.py`). Jadvalning o'zi
(`Jadval Yozuvi`, `Jadval Versiyasi`, `Jadval Ozgarishi`) joyida qoladi.

Xavfsizlik: qatori bor doctype o'chirilmaydi — faqat ogohlantirish yoziladi,
shunda hech qanday haqiqiy ma'lumot yo'qolmaydi.
"""

import frappe

# Bizning doctype'larimiz (target_zenit) — butunlay o'chiriladi
OCHIRILADI = (
	"Dars Bajarilishi",
	"Dars Natijasi",
	"Uy Vazifa Natijasi",
	"Uy Vazifa",
	"Chorak Bahosi",
	"Baho Turi",
	"Baholash Sozlamalari",
)

# Seed qatorlari (haqiqiy ma'lumot emas) — bular bo'lsa ham o'chiramiz
SEED_CHEGARA = {"Baho Turi": 5, "Dars Bajarilishi": 1}


def execute():
	for dt in OCHIRILADI:
		if not frappe.db.exists("DocType", dt):
			continue
		soni = frappe.db.count(dt) if frappe.db.table_exists(dt) else 0
		if soni > SEED_CHEGARA.get(dt, 0):
			frappe.log_error(
				title="eski_lms_tozalash: o'tkazib yuborildi",
				message=f"«{dt}» da {soni} qator bor — qo'lda ko'rib chiqing.",
			)
			continue
		frappe.delete_doc("DocType", dt, force=True, ignore_missing=True,
		                  ignore_permissions=True, delete_permanently=True)
		print(f"  o'chirildi: {dt} ({soni} qator)")

	# `delete_doc` jadvalni har doim tashlamaydi — qolgan bo'sh jadvallarni
	# o'zimiz olib tashlaymiz (aks holda bazada «arvoh» jadval qoladi).
	for dt in OCHIRILADI:
		if frappe.db.exists("DocType", dt):
			continue  # yuqorida o'tkazib yuborilgan (qatori bor)
		if frappe.db.table_exists(dt):
			frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{dt}`")
			print(f"  jadval tashlandi: tab{dt}")
		# Single doctype qiymatlari
		frappe.db.delete("Singles", {"doctype": dt})

	# Sahifalar: dars kokpiti, yo'qlama, baho jurnali, kunlik reja
	for pg in ("dars-sessiya", "yoqlama", "baho-jurnali", "baholar-hisoboti", "kunlik-jadval"):
		if frappe.db.exists("Page", pg):
			frappe.delete_doc("Page", pg, force=True, ignore_missing=True,
			                  ignore_permissions=True, delete_permanently=True)
			print(f"  sahifa o'chirildi: {pg}")

	frappe.db.commit()
