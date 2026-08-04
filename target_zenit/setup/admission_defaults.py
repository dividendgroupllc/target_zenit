# Copyright (c) 2026, Target Zenit
# Standart qabul bosqichlari va statuslarini yuklash.
# Ishga tushirish: bench --site target.local execute target_zenit.setup.admission_defaults.setup_admission_defaults

import frappe

# (bosqich, tartib, ota-onaga ko'rinadigan nom)
STAGES = [
	("Murojaat", 10, "Murojaatingiz qabul qilindi"),
	("Tashrif belgilandi", 20, "Maktab tashrifi belgilandi"),
	("Tashrif bo'ldi", 30, "Maktab tashrifi"),
	("Ariza boshlandi", 40, "Ariza to'ldirilmoqda"),
	("Ariza to'liq", 50, "Ariza qabul qilindi"),
	("Imtihon-Suhbat", 60, "Imtihon va suhbat"),
	("Taklif yuborildi", 70, "Qabul taklifi"),
	("Depozit to'landi", 80, "To'lov tasdiqlandi"),
	("Qabul qilindi", 90, "Tabriklaymiz, qabul qilindingiz!"),
	("Qayta ro'yxat", 100, "Yangi o'quv yiliga ro'yxat"),
]

# (status, bosqich, turi, faqat_ichki, tartib)
STATUSES = [
	("Yangi", "Murojaat", "Active", 0, 10),
	("Aloqa qilindi", "Murojaat", "Active", 0, 20),
	("Javob bermadi", "Murojaat", "Inactive", 1, 30),
	("Qiziqmadi", "Murojaat", "Inactive", 1, 40),
	("Tashrif kutilmoqda", "Tashrif belgilandi", "Active", 0, 10),
	("Tashrifga kelmadi", "Tashrif belgilandi", "Inactive", 1, 20),
	("Fikr yuritmoqda", "Tashrif bo'ldi", "Active", 0, 10),
	("Tashrifdan keyin voz kechdi", "Tashrif bo'ldi", "Inactive", 1, 20),
	("Ariza to'ldirilmoqda", "Ariza boshlandi", "Active", 0, 10),
	("Ariza chala qoldi", "Ariza boshlandi", "Inactive", 1, 20),
	("Hujjatlar tekshirilmoqda", "Ariza to'liq", "Active", 0, 10),
	("Imtihonga yozildi", "Imtihon-Suhbat", "Active", 0, 10),
	("Imtihondan o'tmadi", "Imtihon-Suhbat", "Inactive", 0, 20),
	("Javob kutilmoqda", "Taklif yuborildi", "Active", 0, 10),
	("Taklif rad etildi", "Taklif yuborildi", "Inactive", 0, 20),
	("Navbatda", "Taklif yuborildi", "Waitlist", 0, 30),
	("To'lov tasdiqlandi", "Depozit to'landi", "Active", 0, 10),
	("O'qishni boshladi", "Qabul qilindi", "Active", 0, 10),
	("Qayta ro'yxat jarayonda", "Qayta ro'yxat", "Active", 0, 10),
]

SOURCES = [
	"Instagram DM",
	"Instagram reklama",
	"Telegram",
	"Tavsiya (og'zaki)",
	"Veb-sayt",
	"Qo'ng'iroq",
	"Maktab oldidan o'tgan",
]


def setup_admission_defaults():
	for stage_name, sort_order, parent_facing in STAGES:
		if not frappe.db.exists("Admission Stage", stage_name):
			frappe.get_doc(
				{
					"doctype": "Admission Stage",
					"stage_name": stage_name,
					"sort_order": sort_order,
					"parent_facing_name": parent_facing,
				}
			).insert(ignore_permissions=True)

	for status_name, stage, status_type, internal_only, sort_order in STATUSES:
		if not frappe.db.exists("Admission Status", status_name):
			frappe.get_doc(
				{
					"doctype": "Admission Status",
					"status_name": status_name,
					"stage": stage,
					"status_type": status_type,
					"internal_only": internal_only,
					"sort_order": sort_order,
				}
			).insert(ignore_permissions=True)

	for source in SOURCES:
		if not frappe.db.exists("Lead Source", source):
			frappe.get_doc({"doctype": "Lead Source", "source_name": source}).insert(
				ignore_permissions=True
			)

	frappe.db.commit()
	print(f"OK: {len(STAGES)} bosqich, {len(STATUSES)} status, {len(SOURCES)} manba tayyor")
