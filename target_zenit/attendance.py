# Copyright (c) 2026, Target Zenit
# Terminal Checkin -> kunlik davomat.
# O'quvchilar: education'ning "Student Attendance" jadvaliga yoziladi.
# Scheduler har soatda bugungi kunni qayta hisoblaydi (idempotent — dublikat yozmaydi).

import frappe
from frappe.utils import nowdate


def sync_today():
	"""Scheduler chaqiradi: bugungi o'tishlardan davomat yozadi."""
	sync_student_attendance(nowdate())


def sync_student_attendance(date: str | None = None) -> dict:
	"""Berilgan kundagi Terminal Checkin'lardan Student Attendance yaratadi.

	O'quvchi o'sha kuni kamida bir marta terminaldan o'tgan bo'lsa — "Present".
	Guruhi (Student Group) topilmagan o'quvchi o'tkazib yuboriladi va
	natijada ro'yxat bilan qaytariladi — guruh biriktirilgach keyingi
	ishga tushishda avtomatik yoziladi.
	"""
	date = date or nowdate()
	result = {"date": date, "created": 0, "already": 0, "no_group": [], "errors": []}

	students = frappe.get_all(
		"Terminal Checkin",
		filters={
			"student": ["is", "set"],
			"event_time": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]],
		},
		distinct=True,
		pluck="student",
	)

	for student in students:
		if frappe.db.exists(
			"Student Attendance", {"student": student, "date": date, "docstatus": ["!=", 2]}
		):
			result["already"] += 1
			continue

		group = get_student_group(student)
		if not group:
			result["no_group"].append(student)
			continue

		try:
			frappe.get_doc(
				{
					"doctype": "Student Attendance",
					"student": student,
					"student_group": group,
					"date": date,
					"status": "Present",
				}
			).insert(ignore_permissions=True)
			result["created"] += 1
		except Exception as e:
			frappe.db.rollback()
			result["errors"].append(f"{student}: {e}")
			frappe.log_error(
				title="Student Attendance sync error",
				message=f"{student} / {date}\n{frappe.get_traceback()}",
			)

	frappe.db.commit()
	return result


def get_student_group(student: str) -> str | None:
	"""O'quvchining faol guruhini topadi (davomat uchun)."""
	rows = frappe.db.sql(
		"""
		select sgs.parent
		from `tabStudent Group Student` sgs
		join `tabStudent Group` sg on sg.name = sgs.parent
		where sgs.student = %s and sgs.active = 1 and sg.disabled = 0
		order by sg.group_based_on = 'Activity' desc, sg.modified desc
		limit 1
		""",
		student,
	)
	return rows[0][0] if rows else None
