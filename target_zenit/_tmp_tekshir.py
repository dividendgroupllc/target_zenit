import frappe


def run():
	from target_zenit import ism_sync

	print("--- 1) qolgan nomuvofiqlik ---")
	ism_sync.hisobot()

	# --- 2) jonli hook testi: o'quvchi ismini o'zgartiramiz ---
	qi = frappe.get_all("Qarz Ishi", fields=["name", "student", "student_name"], limit=1)
	if not qi:
		print("Qarz Ishi yo'q — test o'tkazilmadi")
		return
	qi = qi[0]
	stu = frappe.get_doc("Student", qi.student)
	eski_last = stu.last_name
	print(f"\nStudent {stu.name}: '{stu.student_name}' (Qarz Ishi nusxasi: '{qi.student_name}')")

	stu.last_name = (eski_last or "") + " TESTOV"
	stu.save(ignore_permissions=True)
	frappe.db.commit()
	yangi = frappe.db.get_value("Student", stu.name, "student_name")
	print(f"-> yangi student_name: '{yangi}'")

	for dt, lf in (("Qarz Ishi", "student"), ("Tolov Rejasi", "student"),
	               ("Dars Natijasi", "student"), ("Tolov Vadasi", "student"),
	               ("Aloqa Yozuvi", "student"), ("Fees", "student"),
	               ("Student Group Student", "student"), ("Terminal Checkin", "student")):
		rows = frappe.get_all(dt, filters={lf: stu.name}, fields=["name", "student_name" if dt != "Terminal Checkin" else "person_name"], limit=3)
		if rows:
			maydon = "student_name" if dt != "Terminal Checkin" else "person_name"
			holat = "✅" if all((r.get(maydon) or "") == yangi for r in rows) else "❌"
			print(f"  {holat} {dt}: {[r.get(maydon) for r in rows]}")
		else:
			print(f"  —  {dt}: yozuv yo'q")

	cust = frappe.db.get_value("Student", stu.name, "customer")
	if cust:
		print(f"  Customer.customer_name: '{frappe.db.get_value('Customer', cust, 'customer_name')}'")
		si = frappe.get_all("Sales Invoice", filters={"customer": cust}, fields=["name", "customer_name"], limit=2)
		print(f"  Sales Invoice: {[r.customer_name for r in si]}")
		ks = frappe.get_all("Kassa", filters={"party": cust, "party_type": "Customer"}, fields=["name", "party_name"], limit=2)
		print(f"  Kassa.party_name: {[r.party_name for r in ks]}")

	# --- 3) orqaga qaytarish ---
	stu = frappe.get_doc("Student", stu.name)
	stu.last_name = eski_last
	stu.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"\nqaytarildi: '{frappe.db.get_value('Student', stu.name, 'student_name')}'")
	print("--- 4) qaytargandan keyin nomuvofiqlik ---")
	ism_sync.hisobot()


def xodim_test():
	"""Xodim ismi o'zgarsa — Instructor -> Jadval Yozuvi zanjiri."""
	ins = frappe.get_all("Instructor", filters={"employee": ["is", "set"]},
	                     fields=["name", "employee", "instructor_name"], limit=20)
	tanlangan = None
	for i in ins:
		if frappe.db.count("Jadval Yozuvi", {"oqituvchi": i.name}):
			tanlangan = i
			break
	if not tanlangan:
		print("Jadval Yozuvisi bor Instructor topilmadi")
		return
	emp = frappe.get_doc("Employee", tanlangan.employee)
	eski = emp.last_name
	print(f"Employee {emp.name}: '{emp.employee_name}' | Instructor '{tanlangan.instructor_name}'")
	emp.last_name = (eski or "") + " TESTOV"
	emp.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"-> employee_name: '{frappe.db.get_value('Employee', emp.name, 'employee_name')}'")
	print(f"   Instructor.instructor_name: '{frappe.db.get_value('Instructor', tanlangan.name, 'instructor_name')}'")
	jy = frappe.get_all("Jadval Yozuvi", filters={"oqituvchi": tanlangan.name},
	                    fields=["name", "oqituvchi_nomi"], limit=3)
	print(f"   Jadval Yozuvi.oqituvchi_nomi: {[r.oqituvchi_nomi for r in jy]}")
	tb = frappe.get_all("Tabel Ish Kuni", filters={"xodim": emp.name}, fields=["xodim_ismi"], limit=2)
	print(f"   Tabel Ish Kuni.xodim_ismi: {[r.xodim_ismi for r in tb]}")
	emp = frappe.get_doc("Employee", emp.name)
	emp.last_name = eski
	emp.save(ignore_permissions=True)
	frappe.db.commit()
	print(f"qaytarildi: '{frappe.db.get_value('Employee', emp.name, 'employee_name')}'")
