# Student.custom_sinf_guruh (Link -> Student Group) — operator uchun yagona kirish nuqtasi.
# Student saqlanganda: tanlangan guruhga qo'shadi, boshqa guruhlardan chiqaradi.
# Bo'sh qoldirilsa — a'zoliklarga tegilmaydi (guruh tayinlash to'liq operator qo'lida).
# Har yili 1-sentabrda yearly_promotion() hammani bir sinf yuqoriga ko'chiradi (G4A -> G5A).

import re

import frappe
from frappe.utils import getdate, nowdate

FIELD = "custom_sinf_guruh"

# G4A, G10B kabi nomlar: raqam +1 bo'ladi, harf saqlanadi.
# "Elit 1", "Pre-School", "Test", "11" kabi guruhlarga tegilmaydi.
PROMOTE_RE = re.compile(r"^G(\d{1,2})([A-Za-z]+)$")
FINAL_GRADE = 11  # 11-sinf ko'chirilmaydi (bitiruvchi)


def on_student_update(doc, method=None):
	group = doc.get(FIELD)
	if not group:
		return

	current = frappe.get_all(
		"Student Group Student", filters={"student": doc.name}, pluck="parent"
	)
	if current == [group]:
		return

	# Boshqa guruhlardan chiqarish
	for g in set(current) - {group}:
		grp = frappe.get_doc("Student Group", g)
		grp.students = [r for r in grp.students if r.student != doc.name]
		grp.flags.ignore_mandatory = True
		grp.save(ignore_permissions=True)

	# Tanlangan guruhga qo'shish
	if group not in current:
		grp = frappe.get_doc("Student Group", group)
		grp.append(
			"students",
			{
				"student": doc.name,
				"student_name": doc.student_name,
				"active": 1 if doc.enabled else 0,
			},
		)
		grp.flags.ignore_mandatory = True
		grp.save(ignore_permissions=True)


def _get_or_create_group(group_name):
	if frappe.db.exists("Student Group", {"student_group_name": group_name}):
		return
	grp = frappe.new_doc("Student Group")
	grp.student_group_name = group_name
	grp.group_based_on = "Activity"
	grp.academic_year = frappe.db.get_value(
		"Academic Year", {}, "name", order_by="year_start_date desc"
	)
	grp.flags.ignore_mandatory = True
	grp.insert(ignore_permissions=True)


def _studied_last_year(s, year):
	"""O'tgan o'quv yilida (1-sent ... 31-may) bizda o'qiganini tekshiradi.

	Yozgi qabulda keyingi yil uchun kiritilgan yangi o'quvchi bu tekshiruvdan
	o'tmaydi — uning guruhi allaqachon yangi yilniki, ko'chirilmasligi kerak.
	"""
	# 1) O'tgan o'quv yilida turniketdan o'tgan bo'lsa — aniq o'qigan
	if frappe.db.exists(
		"Terminal Checkin",
		{
			"student": s.name,
			"event_time": ["between", [f"{year - 1}-09-01", f"{year}-05-31 23:59:59"]],
		},
	):
		return True
	# 2) O'quv yili tugashidan oldin ro'yxatga olingan (yozgi qabul emas)
	joined = s.joining_date or getdate(s.creation)
	return getdate(joined) < getdate(f"{year}-06-01")


@frappe.whitelist()
def yearly_promotion():
	"""Yangi o'quv yili: o'tgan yili o'qigan faol o'quvchilarni bir sinf yuqoriga ko'chiradi.

	G4A -> G5A (harf saqlanadi), kerak bo'lsa yangi guruh ochiladi.
	Yozda keyingi yil uchun qabul qilingan yangi o'quvchilarga tegilmaydi.
	Bir yilda faqat bir marta ishlaydi (takror chaqirilsa hech narsa qilmaydi).
	Scheduler har yili 1-sentabrda chaqiradi; qo'lda ham chaqirsa bo'ladi.
	"""
	year = nowdate()[:4]
	if frappe.db.get_default("sinf_promotion_year") == year:
		return "allaqachon bajarilgan"

	moved, skipped_new = 0, 0
	students = frappe.get_all(
		"Student",
		filters={"enabled": 1, FIELD: ["like", "G%"]},
		fields=["name", FIELD, "joining_date", "creation"],
	)
	for s in students:
		m = PROMOTE_RE.match(s.get(FIELD) or "")
		if not m:
			continue
		grade = int(m.group(1))
		if grade >= FINAL_GRADE:
			continue
		if not _studied_last_year(s, int(year)):
			skipped_new += 1
			continue
		target = f"G{grade + 1}{m.group(2)}"
		_get_or_create_group(target)
		doc = frappe.get_doc("Student", s.name)
		doc.set(FIELD, target)
		doc.flags.ignore_mandatory = True
		doc.save(ignore_permissions=True)  # hook a'zolikni yangi guruhga ko'chiradi
		moved += 1

	frappe.db.set_default("sinf_promotion_year", year)
	return f"{moved} ta o'quvchi keyingi sinfga ko'chirildi, {skipped_new} ta yangi qabul tegilmadi"
