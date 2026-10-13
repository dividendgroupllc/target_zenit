# Copyright (c) 2026, Target Zenit
"""Ism nusxalarini (snapshot) joriy ismga moslab turish.

NEGA KERAK
----------
Frappe'da `fetch_from` — JOIN emas, **nusxa**: qiymat hujjat saqlangan paytda
bir marta ko'chiriladi va keyin muzlab qoladi. Submit qilingan hujjatni qayta
saqlab bo'lmaydi, shuning uchun Student/Employee ismi (masalan pasport bo'yicha)
tahrirlanganda eski ism Fees, Sales Invoice, Qarz Ishi, Tolov Rejasi,
Dars Natijasi, Instructor, Tabel ... hujjatlarida qolib ketadi. Panellar va
hisobotlar aynan shu nusxalardan o'qiydi — natijada dashbordlarda eski ism
ko'rinadi yoki ism bo'yicha moslashtirish (turniket, import) buziladi.

Hujjatning docname'i (ID) o'zgarmaydi, shuning uchun pul hisobi buzilmaydi:
Fees / Sales Invoice / Payment Entry / GL Entry hammasi bir xil `EDU-STU-…`,
`HR-EMP-…` ga bog'langan holda qoladi. Buziladigan narsa — ko'rinadigan ism.

QANDAY ISHLAYDI
---------------
Nusxa maydonlari ro'yxati qo'lda yozilmaydi — DocField va Custom Field'dagi
`fetch_from` qiymatlaridan **avtomatik** yig'iladi. Shuning uchun yangi doctype
yoki yangi custom field qo'shilsa ham bu modulni tahrirlash kerak emas.
Zanjir ham quriladi:

    Student.student_name
        -> Qarz Ishi.student_name -> Tolov Vadasi / Aloqa Yozuvi .student_name
    Employee.employee_name
        -> Instructor.instructor_name -> Jadval Yozuvi.oqituvchi_nomi,
                                         Course Schedule.instructor_name
        -> Attendance / Salary Slip / Timesheet / Tabel * .employee_name

Yangilash to'g'ridan-to'g'ri SQL `UPDATE ... JOIN` bilan boradi: submit
qilingan hujjatlar ham tuzatiladi, `modified` tegilmaydi (versiya/timeline
shovqini yo'q), validatsiya qayta ishga tushmaydi.

KIRISH NUQTALARI
----------------
* hooks.py on_update: `student_on_update`, `employee_on_update`,
  `instructor_on_update`, `customer_on_update`, `supplier_on_update`
* `backfill()` — butun bazadagi eskirgan nusxalarni bir martada tuzatish
  (patch orqali `bench migrate` da avtomatik ishlaydi)
* `hisobot()` — hech narsa yozmaydi, faqat qaysi jadvalda nechta nomuvofiqlik
  borligini chiqaradi (diagnostika)
"""

from __future__ import annotations

import frappe

CACHE_KEY = "target_zenit_ism_sync_graph"

# Ism manbalari — zanjir shulardan boshlanadi
NAME_SOURCES = {
	"Student": "student_name",
	"Employee": "employee_name",
	"Customer": "customer_name",
	"Supplier": "supplier_name",
	"Instructor": "instructor_name",
}

# fetch_from'siz, qo'lda yuritiladigan nusxalar:
#   (doctype, link maydoni, nusxa maydoni, manba doctype, qo'shimcha SQL shart)
# Kassa.party_name — party_type'ga qarab boshqa manbadan olinadi (kassa.py dagi
# PARTY_NAME_FIELDS bilan bir xil ro'yxat).
# Terminal Checkin.person_name — turniket qurilmasi yuborgan ism; xom ko'rinishi
# `raw_data` maydonida saqlanib qoladi, shuning uchun ustiga yozish xavfsiz.
QOLDA_NUSXALAR = [
	("Kassa", "party", "party_name", "Customer", "t.party_type = 'Customer'"),
	("Kassa", "party", "party_name", "Supplier", "t.party_type = 'Supplier'"),
	("Kassa", "party", "party_name", "Employee", "t.party_type = 'Employee'"),
	("Terminal Checkin", "student", "person_name", "Student", None),
	("Terminal Checkin", "employee", "person_name", "Employee", None),
]


# ------------------------------------------------------------------ graf qurish
def _fetch_edges():
	"""DocField + Custom Field'dagi `<link>.<maydon>` ko'rinishidagi fetch_from lar."""
	rows = frappe.db.sql(
		"""SELECT parent AS dt, fieldname, fetch_from FROM `tabDocField`
		    WHERE IFNULL(fetch_from, '') != ''
		   UNION ALL
		   SELECT dt, fieldname, fetch_from FROM `tabCustom Field`
		    WHERE IFNULL(fetch_from, '') != ''""",
		as_dict=True,
	)
	out = []
	for r in rows:
		parts = (r.fetch_from or "").split(".")
		if len(parts) != 2:
			continue
		out.append((r.dt, parts[0].strip(), r.fieldname, parts[1].strip()))
	return out


def _link_dt(dt, fieldname):
	"""Link maydoni qaysi doctype'ga ketadi (custom field ham hisobga olinadi)."""
	try:
		df = frappe.get_meta(dt).get_field(fieldname)
	except Exception:
		return None
	return df.options if df and df.fieldtype == "Link" else None


def _graph():
	"""Ism nusxalari grafigi.

	Har bir manba doctype uchun BFS daraxti: daraja 0 — to'g'ridan-to'g'ri
	manbadan oladiganlar, daraja 1 — o'sha nusxadan oladiganlar, va h.k.

	Natija: {root_dt: [edge, ...]} — edge dict:
	  dt, link, snap, src_dt, src_field, shart, daraja, src_person_field
	`src_person_field` — manba hujjatidagi (src_dt) odamga ketadigan link
	maydoni; daraja 1 da shu orqali bitta odam bo'yicha cheklab yangilanadi.
	"""
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	edges = _fetch_edges()
	grafik = {}

	for root_dt, root_field in NAME_SOURCES.items():
		natija = []
		olingan = set()
		# navbat: (manba doctype, manba maydoni, daraja, manbadagi odam linki)
		navbat = [(root_dt, root_field, 0, None)]
		while navbat:
			src_dt, src_field, daraja, _ = navbat.pop(0)
			keyingi = []
			for dt, link, snap, fetched in edges:
				if fetched != src_field:
					continue
				if (dt, link, snap) in olingan:
					continue
				if _link_dt(dt, link) != src_dt:
					continue
				if (dt, snap) == (src_dt, src_field):
					continue
				e = {
					"dt": dt, "link": link, "snap": snap,
					"src_dt": src_dt, "src_field": src_field,
					"shart": None, "daraja": daraja,
					# daraja 1 uchun: src_dt dagi odamga ketadigan link
					"src_person_field": None if daraja == 0 else _person_field(natija, src_dt),
				}
				natija.append(e)
				olingan.add((dt, link, snap))
				keyingi.append((dt, snap, daraja + 1, link))
			navbat.extend(keyingi)

		# qo'lda yuritiladigan nusxalar — shu rootga tegishlilari
		for dt, link, snap, qsrc, shart in QOLDA_NUSXALAR:
			if qsrc != root_dt or (dt, link, snap) in olingan:
				continue
			natija.append({
				"dt": dt, "link": link, "snap": snap,
				"src_dt": root_dt, "src_field": root_field,
				"shart": shart, "daraja": 0, "src_person_field": None,
			})
			olingan.add((dt, link, snap))

		natija.sort(key=lambda e: e["daraja"])
		grafik[root_dt] = natija

	frappe.cache().set_value(CACHE_KEY, grafik)
	return grafik


def _person_field(natija, src_dt):
	"""src_dt ichida odamga (rootga) ketadigan link maydoni — oldingi edge'dan."""
	for e in natija:
		if e["dt"] == src_dt and e["daraja"] == 0:
			return e["link"]
	return None


def graf_cache_tozalash(doc=None, method=None):
	"""Custom Field / Property Setter o'zgarsa — graf qayta yig'ilsin."""
	frappe.cache().delete_value(CACHE_KEY)


# --------------------------------------------------------------- yangilash ishi
def _jadval_bormi(dt):
	try:
		return bool(frappe.db.table_exists(dt))
	except Exception:
		return False


def _yangila(e, docname=None, quruq=False):
	"""Bitta bog'lanish bo'yicha eskirgan nusxalarni yangilash.

	`docname` — bitta odam bo'yicha cheklash (on_update holati):
	  daraja 0 da `t.<link> = id`, daraja 1 da `s.<src_person_field> = id`.
	  Chuqurroq darajada cheklash o'rniga faqat nomuvofiq qatorlar yangilanadi
	  (ular juda kam bo'ladi, shart indeksga tushmasa ham arzon).
	`quruq=True` — hech narsa yozmaydi, nomuvofiqlar sonini qaytaradi.
	"""
	dt, link, snap = e["dt"], e["link"], e["snap"]
	src_dt, src_field = e["src_dt"], e["src_field"]
	if not (_jadval_bormi(dt) and _jadval_bormi(src_dt)):
		return 0

	where = [
		f"IFNULL(t.`{snap}`, '') != IFNULL(s.`{src_field}`, '')",
		f"IFNULL(t.`{link}`, '') != ''",
	]
	vals = {}
	if e.get("shart"):
		where.append(e["shart"])
	if docname:
		if e["daraja"] == 0:
			where.append(f"t.`{link}` = %(id)s")
			vals["id"] = docname
		elif e["daraja"] == 1 and e.get("src_person_field"):
			where.append(f"s.`{e['src_person_field']}` = %(id)s")
			vals["id"] = docname
	w = " AND ".join(where)
	t, s = f"`tab{dt}`", f"`tab{src_dt}`"

	try:
		if quruq:
			return frappe.db.sql(
				f"SELECT COUNT(*) FROM {t} t JOIN {s} s ON s.name = t.`{link}` WHERE {w}", vals
			)[0][0]
		frappe.db.sql(
			f"UPDATE {t} t JOIN {s} s ON s.name = t.`{link}` "
			f"SET t.`{snap}` = s.`{src_field}` WHERE {w}",
			vals,
		)
		return frappe.db.sql("SELECT ROW_COUNT()")[0][0] or 0
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"ism_sync {dt}.{snap}")
		return 0


def tarqat(root_dt, docname=None, quruq=False):
	"""Ism o'zgarishini zanjir bo'ylab tarqatish. Yangilangan qator sonini qaytaradi."""
	jami = 0
	for e in _graph().get(root_dt, []):
		jami += _yangila(e, docname=docname, quruq=quruq)
	return jami


# -------------------------------------------------------------------- hooklar
def _ozgardimi(doc, maydon):
	eski = doc.get_doc_before_save()
	return True if eski is None else (eski.get(maydon) or "") != (doc.get(maydon) or "")


def _on_update(doc, root_dt):
	if not _ozgardimi(doc, NAME_SOURCES[root_dt]):
		return
	try:
		tarqat(root_dt, doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"ism_sync tarqat: {root_dt} {doc.name}")


def student_on_update(doc, method=None):
	_on_update(doc, "Student")


def employee_on_update(doc, method=None):
	_on_update(doc, "Employee")


def instructor_on_update(doc, method=None):
	_on_update(doc, "Instructor")


def customer_on_update(doc, method=None):
	_on_update(doc, "Customer")


def supplier_on_update(doc, method=None):
	_on_update(doc, "Supplier")


# ------------------------------------------------------------- backfill/hisobot
def backfill(quruq=False):
	"""Bazadagi barcha eskirgan ism nusxalarini tuzatish.

	    bench --site <site> execute target_zenit.ism_sync.backfill
	    bench --site <site> execute target_zenit.ism_sync.hisobot   # quruq yurish
	"""
	graf = _graph()
	korilgan, satrlar, jami = set(), [], 0
	# Zanjir tartibi muhim: avval daraja 0 (Instructor.instructor_name),
	# keyin daraja 1 (Jadval Yozuvi.oqituvchi_nomi) — aks holda eski qiymat
	# ko'chib qolardi.
	for daraja in range(0, 6):
		for root_dt in NAME_SOURCES:
			for e in graf.get(root_dt, []):
				if e["daraja"] != daraja:
					continue
				kalit = (e["dt"], e["link"], e["snap"], e.get("shart"))
				if kalit in korilgan:
					continue
				korilgan.add(kalit)
				n = _yangila(e, quruq=quruq)
				if n:
					satrlar.append(f"  [{daraja}] {e['dt']}.{e['snap']}  <- {e['src_dt']}.{e['src_field']}: {n}")
					jami += n
	if not quruq:
		frappe.db.commit()
	print(f"{'NOMUVOFIQ (quruq yurish)' if quruq else 'TUZATILDI'} — jami {jami} qator")
	print("\n".join(satrlar) or "  (hammasi joyida)")
	return jami


def hisobot():
	"""Hech narsani o'zgartirmaydi — faqat nomuvofiqlik hisoboti."""
	return backfill(quruq=True)


def after_migrate():
	"""Har deploy'da ism nusxalarini moslab qo'yish (idempotent, arzon:
	faqat nomuvofiq qatorlar yangilanadi)."""
	try:
		graf_cache_tozalash()
		n = backfill()
		if n:
			frappe.logger().info(f"ism_sync: {n} ism nusxasi yangilandi")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "ism_sync after_migrate")


# ------------------------------------------------- odamni ishonchli aniqlash
def joriy_instructor(user: str | None = None) -> str | None:
	"""Foydalanuvchining Instructor yozuvi.

	Ism bo'yicha moslashtirish eng oxirgi chora: Education Settings'da
	`instructor_created_by = Full Name` bo'lgani uchun Instructor docname'i —
	ism satri, va u xodim ismi pasport bo'yicha o'zgartirilganda eskicha
	qolib ketadi. Shuning uchun tartib:

	  1) Employee.user_id -> Instructor.employee        (ID bo'yicha, ishonchli)
	  2) User.full_name   -> Employee.employee_name -> Instructor.employee
	  3) User.full_name   -> Instructor.instructor_name
	  4) User.full_name   == Instructor docname        (eski yozuvlar uchun)
	"""
	user = user or frappe.session.user
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if emp:
		ins = frappe.db.get_value("Instructor", {"employee": emp}, "name")
		if ins:
			return ins

	full_name = (frappe.db.get_value("User", user, "full_name") or "").strip()
	if not full_name:
		return None

	emp = frappe.db.get_value("Employee", {"employee_name": full_name}, "name")
	if emp:
		ins = frappe.db.get_value("Instructor", {"employee": emp}, "name")
		if ins:
			return ins

	ins = frappe.db.get_value("Instructor", {"instructor_name": full_name}, "name")
	if ins:
		return ins
	return frappe.db.exists("Instructor", full_name) or None


# ---------------------------------------------- ism bo'yicha mos keltirish
# Ismlar turli joylarda turlicha yozilgan: pasportda "Abduganiyev Firdavsbek
# Xabibullo o'gli", jadval Excelida "Abduganiyev F.", turniketda yana boshqacha.
# Shuning uchun ID yo'q bo'lgan joylarda so'z (token) bo'yicha moslashtiriladi.
def ism_tokenlari(ism: str) -> set:
	"""Taqqoslash uchun normallash: kichik harf, apostroflarsiz, 4+ belgili so'zlar."""
	import re

	s = (ism or "").lower()
	for a, b in (("‘", ""), ("’", ""), ("ʻ", ""), ("'", ""), ("`", ""), ("-", " ")):
		s = s.replace(a, b)
	s = re.sub(r"[^a-zа-яё ]", " ", s)
	for a, b in (("ye", "e"), ("kh", "x"), ("dj", "j"), ("gh", "g"), ("q", "k")):
		s = s.replace(a, b)
	return {w for w in s.split() if len(w) >= 4}


def eng_mos(ism: str, nomzodlar, kamida: int = 2):
	"""`nomzodlar` ichidan `ism`ga eng mos kelganini qaytaradi.

	`nomzodlar`: {kalit: ism} yoki ismlar ro'yxati. Kamida `kamida` ta so'z
	mos kelishi shart (familiya + ism), aks holda None — tasodifiy moslik
	bo'lmasligi uchun.
	"""
	kerak = ism_tokenlari(ism)
	if not kerak:
		return None
	juftlar = nomzodlar.items() if isinstance(nomzodlar, dict) else ((n, n) for n in nomzodlar)
	eng, ball_max = None, 0
	for kalit, nom in juftlar:
		ball = len(kerak & ism_tokenlari(nom))
		if ball > ball_max:
			eng, ball_max = kalit, ball
	return eng if ball_max >= kamida else None


def instructor_topish(ism: str, employee: str | None = None) -> str | None:
	"""Instructor'ni ishonchli topish — yangi dublikat yaratilmasligi uchun.

	Tartib: Employee (ID) -> instructor_name -> docname -> so'z bo'yicha moslik.
	Oxirgi qadam kerak, chunki Instructor docname'i (va eski yozuvlarda
	instructor_name) qisqa ism, Employee'da esa pasport ismi bo'lishi mumkin.
	"""
	if employee:
		ins = frappe.db.get_value("Instructor", {"employee": employee}, "name")
		if ins:
			return ins
	ism = (ism or "").strip()
	if not ism:
		return None
	ins = frappe.db.get_value("Instructor", {"instructor_name": ism}, "name")
	if ins:
		return ins
	if frappe.db.exists("Instructor", ism):
		return ism
	barchasi = {
		r.name: f"{r.instructor_name or ''} {r.name}"
		for r in frappe.get_all("Instructor", fields=["name", "instructor_name"], limit_page_length=0)
	}
	return eng_mos(ism, barchasi)
