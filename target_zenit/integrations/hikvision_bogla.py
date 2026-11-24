# Copyright (c) 2026, Target Zenit
# Terminal Checkin yozuvlarini Student/Employee ga ism bo'yicha bog'lash.
#
# Ishlatish tartibi (avval lokalda, keyin prodda):
#   bench --site <sayt> execute target_zenit.integrations.hikvision_bogla.tahlil   # dry-run
#   bench --site <sayt> execute target_zenit.integrations.hikvision_bogla.yoz      # yozish
#   bench --site <sayt> execute target_zenit.integrations.hikvision_bogla.kim_yoq  # kimning ma'lumoti yo'q
#
# Qoidalar:
# - Terminal ismida otasining ismi yo'q, bizda bor; imlo farqlari ham uchraydi
#   (Feruz/Firuz, Abbos/Abbosxon, x/h, har xil apostroflar) -> normalizatsiya +
#   taxminiy token moslik (prefiks yoki ~80% o'xshashlik), kamida 2 token.
# - Bitta odamda bir nechta terminal ID bo'lishi mumkin (qayta ro'yxatga olishlar) —
#   HAMMA IDlari tarixiy yozuvlarga bog'lanadi, Student.custom_hikvision_id /
#   Employee.attendance_device_id ga esa ENG OXIRGI faol ID yoziladi.
# - Teng ball chiqsa faol (enabled/Active) yozuv yutadi; baribir teng bo'lsa
#   (adash) — bog'lanmaydi, hisobotda ko'rinadi.

import re
from collections import defaultdict
from difflib import SequenceMatcher

import frappe

SUFFIKS = ("ogli", "qizi", "kizi", "ugli")


def norm(s: str) -> str:
	s = (s or "").lower()
	for a in ("ʼ", "’", "`", "‘", "ʻ", "´"):
		s = s.replace(a, "'")
	s = s.replace("õ", "o").replace("о", "o")  # lotin õ va kirill о
	s = s.replace("o'", "o").replace("g'", "g").replace("'", "")
	s = s.replace("kh", "h").replace("ye", "e")  # Kholmuradov/Xolmuradov, Yerdullayeva/Erdullaeva
	s = s.replace("x", "h")  # Xalimov/Halimov, Shaxruza/Shahruza
	s = re.sub(r"[^a-zа-яё0-9 ]", " ", s)
	return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list:
	return [w for w in norm(s).split() if w not in SUFFIKS]


def tok_mos(a: str, b: str) -> bool:
	"""Ikki token bir xil ismmi: aynan teng, biri ikkinchisining boshi
	(Abbos~Abbosxon), yoki ~80% o'xshash (Feruz~Firuz)."""
	if a == b:
		return True
	if len(a) >= 4 and len(b) >= 4:
		if a.startswith(b) or b.startswith(a):
			return True
		# taxminiy o'xshashlik faqat bosh harfi bir xil bo'lsa (Feruz~Firuz ha,
		# Utkirova~Toirova yo'q)
		if a[0] == b[0]:
			return SequenceMatcher(None, a, b).ratio() >= 0.8
	return False


def fuzzy_ball(tk1: list, tk2: list):
	"""(mos tokenlar soni, shundan aynan tenglari, tk1 dagi mos kelmaganlar)."""
	band = set()
	ball = aniq = 0
	qolgan = []
	for a in tk1:
		for j, b in enumerate(tk2):
			if j in band:
				continue
			if tok_mos(a, b):
				band.add(j)
				ball += 1
				aniq += a == b
				break
		else:
			qolgan.append(a)
	return ball, aniq, qolgan


def _terminal_odamlari():
	return frappe.db.sql(
		"""SELECT person_id, MAX(person_name) person_name, COUNT(*) c, MAX(event_time) oxirgi
		   FROM `tabTerminal Checkin`
		   WHERE person_id NOT LIKE 'st-%%'
		   GROUP BY person_id""",
		as_dict=True,
	)


def _tayyorla(rows, name_key):
	"""Har yozuvga token ro'yxati + 4-harf prefiks indeksi."""
	buckets = defaultdict(set)
	for i, r in enumerate(rows):
		r["_tk"] = tokens(r[name_key] or "")
		for t in r["_tk"]:
			buckets[t[:4]].add(i)
	return buckets


def _mos(pname, rows, buckets, faolmi):
	tk = tokens(pname)
	cand = set()
	for t in tk:
		cand |= buckets.get(t[:4], set())
	best_key, best_i, best_qolgan, tie = None, None, None, False
	for i in cand:
		ball, aniq, qolgan = fuzzy_ball(tk, rows[i]["_tk"])
		if ball < 2:
			continue
		key = (ball, aniq, 1 if faolmi(rows[i]) else 0)
		if best_key is None or key > best_key:
			best_key, best_i, best_qolgan, tie = key, i, qolgan, False
		elif key == best_key:
			tie = True
	if best_i is not None and not tie:
		# birinchi token (odatda familiya) mos kelmagan bo'lsa — shubhali
		shubhali = bool(tk) and tk[0] in (best_qolgan or []) and len(tk[0]) >= 5
		return best_i, best_key[0], shubhali
	return None, 0, False


def _xarita():
	"""person_id -> {doctype, name, ism, ball} xaritasini quradi."""
	students = frappe.db.sql(
		"SELECT name, student_name, enabled FROM `tabStudent`", as_dict=True
	)
	employees = frappe.db.sql(
		"SELECT name, employee_name, status FROM `tabEmployee`", as_dict=True
	)
	s_buckets = _tayyorla(students, "student_name")
	e_buckets = _tayyorla(employees, "employee_name")
	s_faol = lambda r: r["enabled"] == 1  # noqa: E731
	e_faol = lambda r: r["status"] == "Active"  # noqa: E731

	xarita, topilmadi = {}, []
	for p in _terminal_odamlari():
		pid, pname = p.person_id, (p.person_name or "").strip()
		# ID diapazoni bo'yicha ustuvorlik: 10xxx/11xxx — o'quvchi, qolgani — xodim
		talaba_birinchi = pid.isdigit() and len(pid) == 5 and pid[0] == "1"
		tartib = (
			[("Student", students, s_buckets, s_faol, "student_name"),
			 ("Employee", employees, e_buckets, e_faol, "employee_name")]
			if talaba_birinchi
			else [("Employee", employees, e_buckets, e_faol, "employee_name"),
			      ("Student", students, s_buckets, s_faol, "student_name")]
		)
		topildi = False
		for doctype, rows, buckets, faolmi, nf in tartib:
			i, ball, shubhali = _mos(pname, rows, buckets, faolmi)
			if i is not None:
				r = rows[i]
				xarita[pid] = {
					"doctype": doctype, "name": r["name"], "ism": r[nf],
					"ball": ball, "terminal_ism": pname, "shubhali": shubhali,
					"hodisa": p.c, "oxirgi": p.oxirgi,
				}
				topildi = True
				break
		if not topildi:
			topilmadi.append(p)
	return xarita, topilmadi


def tahlil():
	"""Dry-run: nima bog'lanishini ko'rsatadi, hech narsa yozmaydi."""
	xarita, topilmadi = _xarita()
	stu = {v["name"] for v in xarita.values() if v["doctype"] == "Student"}
	emp = {v["name"] for v in xarita.values() if v["doctype"] == "Employee"}
	print(f"Terminal IDlar: {len(xarita) + len(topilmadi)}")
	print(f"  bog'lanadi: {len(xarita)} ID -> {len(stu)} o'quvchi + {len(emp)} xodim")
	print(f"  topilmadi : {len(topilmadi)}")

	print("\nTOPILMAGANLAR (oxirgi faolligi bo'yicha):")
	for p in sorted(topilmadi, key=lambda x: str(x.oxirgi), reverse=True):
		print(f"  {p.person_id:>8} | {p.person_name:45} | hodisa={p.c:>5} | oxirgi={str(p.oxirgi)[:10]}")

	print("\nSHUBHALI (familiya mos emas — yoz() BULARNI O'TKAZIB YUBORADI):")
	for pid, v in xarita.items():
		if v["shubhali"]:
			print(f"  {pid:>8} | {v['terminal_ism']:38} -> {v['ism']:45} ({v['name']})")

	print("\nIMLO FARQI BILAN BOG'LANGANLAR (tekshirib chiqing):")
	for pid, v in xarita.items():
		if not v["shubhali"] and set(tokens(v["terminal_ism"])) - set(tokens(v["ism"])):
			print(f"  {pid:>8} | {v['terminal_ism']:38} -> {v['ism']:45} ({v['name']})")
	return {"bog'lanadi": len(xarita), "topilmadi": len(topilmadi)}


def yoz():
	"""Bog'lashni bazaga yozadi:
	1) Terminal Checkin: student/employee/person_type (tarixiy yozuvlar, hamma ID).
	2) Student.custom_hikvision_id / Employee.attendance_device_id: eng oxirgi ID
	   (webhook keyingi o'tishlarni o'zi tanishi uchun)."""
	xarita, topilmadi = _xarita()

	yangilandi = otkazildi = 0
	for pid, v in xarita.items():
		if v["shubhali"]:
			otkazildi += 1
			continue
		if v["doctype"] == "Student":
			frappe.db.sql(
				"""UPDATE `tabTerminal Checkin`
				   SET student=%s, employee=NULL, person_type='O''quvchi'
				   WHERE person_id=%s""",
				(v["name"], pid),
			)
		else:
			person_type = (
				"O'qituvchi"
				if frappe.db.exists("Instructor", {"employee": v["name"]})
				else "Xodim"
			)
			frappe.db.sql(
				"""UPDATE `tabTerminal Checkin`
				   SET employee=%s, student=NULL, person_type=%s
				   WHERE person_id=%s""",
				(v["name"], person_type, pid),
			)
		yangilandi += 1

	# Har Frappe yozuviga eng oxirgi (faol) terminal IDni biriktiramiz
	eng_oxirgi = {}  # (doctype, name) -> (oxirgi, pid)
	for pid, v in xarita.items():
		if v["shubhali"]:
			continue
		k = (v["doctype"], v["name"])
		if k not in eng_oxirgi or str(v["oxirgi"]) > str(eng_oxirgi[k][0]):
			eng_oxirgi[k] = (v["oxirgi"], pid)
	for (doctype, name), (_, pid) in eng_oxirgi.items():
		field = "custom_hikvision_id" if doctype == "Student" else "attendance_device_id"
		frappe.db.set_value(doctype, name, field, pid, update_modified=False)

	frappe.db.commit()
	print(f"Terminal ID bog'landi: {yangilandi} (topilmagan: {len(topilmadi)}, shubhali o'tkazildi: {otkazildi})")
	print(f"ID maydoni to'ldirildi: {len(eng_oxirgi)} ta Student/Employee")
	print("Topilmaganlar ro'yxati uchun: ...hikvision_bogla.tahlil")


def kim_yoq():
	"""FAOL Student/Employee'lardan terminalda UMUMAN ko'rinmaganlar ro'yxati.

	Avval yoz() ishga tushirilgan bo'lishi kerak (bog'lanishga tayanadi)."""
	stu = frappe.db.sql(
		"""SELECT s.name, s.student_name
		   FROM `tabStudent` s
		   LEFT JOIN `tabTerminal Checkin` t ON t.student = s.name
		   WHERE s.enabled=1 AND t.name IS NULL
		   GROUP BY s.name ORDER BY s.student_name""",
		as_dict=True,
	)
	emp = frappe.db.sql(
		"""SELECT e.name, e.employee_name, e.designation
		   FROM `tabEmployee` e
		   LEFT JOIN `tabTerminal Checkin` t ON t.employee = e.name
		   WHERE e.status='Active' AND t.name IS NULL
		   GROUP BY e.name ORDER BY e.employee_name""",
		as_dict=True,
	)
	print(f"=== TERMINALDA KO'RINMAGAN FAOL O'QUVCHILAR: {len(stu)} ===")
	for r in stu:
		print(f"  {r.name} | {r.student_name}")
	print(f"\n=== TERMINALDA KO'RINMAGAN FAOL XODIMLAR: {len(emp)} ===")
	for r in emp:
		print(f"  {r.name} | {r.employee_name} | {r.designation or ''}")
	return {"oquvchi_yoq": len(stu), "xodim_yoq": len(emp)}
