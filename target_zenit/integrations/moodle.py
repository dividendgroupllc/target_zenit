# Copyright (c) 2026, Target Zenit
# Frappe -> Moodle (5.x) foydalanuvchi sinxroni.
#
# YO'NALISH: faqat Frappe -> Moodle (push). Frappe — yagona haqiqat manbasi;
# Moodle'da qo'lda o'zgartirilgan ism/email keyingi sinxronda qaytariladi.
# Shuning uchun Moodle tomonida profil maydonlari "Locked" qilinishi kerak
# (Plugins -> Authentication -> Manual accounts).
#
# HOZIR YUBORILADIGAN MA'LUMOT (1-bosqich):
#   Student   (enabled=1)                      -> Moodle foydalanuvchi
#   Instructor(status=Active, vakant emas)     -> Moodle foydalanuvchi
# Kurs, guruh (cohort), kursga yozish, baho — KEYINGI bosqichlar.
#
# SINXRON KALITI: Frappe ID -> Moodle `idnumber`
#   o'quvchi    : Student docname        (EDU-STU-2026-00012)
#   o'qituvchi  : Employee ID            (HR-EMP-00153)
#   employee'si yo'q o'qituvchi: INSTR-<Instructor docname>
# Hech qachon ism yoki email bo'yicha moslashtirilmaydi.
#
# HECH QACHON O'CHIRILMAYDI: Frappe'da o'chirilgan/ketgan bo'lsa Moodle'da
# faqat `suspended=1` qilinadi — baho va dars tarixi saqlanib qoladi.
#
# Ishga tushirish:
#   Qo'lda  : Moodle Settings -> "Hozir sinxronlash" (sync_now)
#   Avtomat : scheduler cron "0 7 * * *" -> daily_sync()

from __future__ import annotations

import hashlib
import json
import re
import secrets
import string

import frappe
import requests
from frappe.utils import now_datetime

TIMEOUT = 60
# Moodle core_user_create_users/update_users bitta so'rovda nechta odam
BATCH = 25
# idnumber bo'yicha qidirishda bitta so'rovga nechta qiymat
LOOKUP_BATCH = 100

# O'zbek lotin harflarini Moodle username uchun ASCII'ga keltirish.
# Moodle standart sozlamada username'da faqat a-z 0-9 _ - . @ ni qabul qiladi.
# DIQQAT: avval matn kichik harfga o'tkaziladi, keyin shu jadval qo'llanadi —
# shuning uchun kalitlar faqat kichik harfda.
TRANSLIT = {
	"ʼ": "", "'": "", "`": "", "’": "", "‘": "", "ʻ": "",
	"ё": "e", "й": "y", "ц": "ts", "у": "u", "к": "k", "е": "e", "н": "n",
	"г": "g", "ш": "sh", "щ": "sh", "з": "z", "х": "x", "ъ": "", "ф": "f",
	"ы": "i", "в": "v", "а": "a", "п": "p", "р": "r", "о": "o", "л": "l",
	"д": "d", "ж": "j", "э": "e", "я": "ya", "ч": "ch", "с": "s", "м": "m",
	"и": "i", "т": "t", "ь": "", "б": "b", "ю": "yu",
	# o'zbek kirillidagi qo'shimcha harflar
	"ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}


# ---------------------------------------------------------------- Sozlamalar

def _settings():
	return frappe.get_cached_doc("Moodle Settings")


def _conf():
	"""Sozlamani tekshirib (url, token) qaytaradi. Yetishmasa xato."""
	s = _settings()
	base = (s.base_url or "").strip().rstrip("/")
	token = s.get_password("token", raise_exception=False)
	if not base:
		frappe.throw("Moodle Settings: Moodle manzili (base URL) kiritilmagan.")
	if not token:
		frappe.throw("Moodle Settings: Web service token kiritilmagan.")
	return s, base, token


# ---------------------------------------------------------------- HTTP qatlami

def _flatten(obj, prefix=""):
	"""Moodle REST ichma-ich massivni `users[0][username]` ko'rinishida kutadi."""
	out = {}
	if isinstance(obj, dict):
		for k, v in obj.items():
			key = f"{prefix}[{k}]" if prefix else str(k)
			out.update(_flatten(v, key))
	elif isinstance(obj, (list, tuple)):
		for i, v in enumerate(obj):
			out.update(_flatten(v, f"{prefix}[{i}]"))
	else:
		if isinstance(obj, bool):
			obj = 1 if obj else 0
		out[prefix] = obj
	return out


class MoodleError(Exception):
	pass


def _call(wsfunction, payload=None):
	"""Moodle web service chaqiruvi. Moodle xatoni ham HTTP 200 bilan qaytaradi."""
	_s, base, token = _conf()
	url = f"{base}/webservice/rest/server.php"
	data = {
		"wstoken": token,
		"wsfunction": wsfunction,
		"moodlewsrestformat": "json",
	}
	data.update(_flatten(payload or {}))

	try:
		r = requests.post(url, data=data, timeout=TIMEOUT)
	except requests.RequestException as e:
		raise MoodleError(f"Moodle'ga ulanib bo'lmadi: {e}") from e

	if r.status_code == 403:
		# Moodle web service o'chirilgan bo'lsa shu holat qaytadi (tanasi bo'sh).
		raise MoodleError(
			"Moodle 403 qaytardi. Tekshiring: (1) Advanced features -> Enable web services, "
			"(2) Manage protocols -> REST protocol yoqilgan, (3) token to'g'ri va "
			"frappe.sync 'Authorised users' ro'yxatida."
			+ (f" Javob: {r.text[:200]}" if r.text.strip() else "")
		)
	if r.status_code != 200:
		raise MoodleError(f"HTTP {r.status_code}: {r.text[:300]}")

	try:
		res = r.json()
	except ValueError:
		raise MoodleError(f"JSON emas javob keldi: {r.text[:300]}") from None

	if isinstance(res, dict) and res.get("exception"):
		raise MoodleError(
			f"{res.get('errorcode')}: {res.get('message')}"
			+ (f" ({res['debuginfo']})" if res.get("debuginfo") else "")
		)
	return res


# ---------------------------------------------------------------- Yordamchilar

def _translit(text):
	t = (text or "").lower()
	for src, dst in TRANSLIT.items():
		t = t.replace(src, dst)
	t = re.sub(r"[^a-z0-9.]+", ".", t)
	t = re.sub(r"\.+", ".", t).strip(".")
	return t


def _split_name(full):
	"""O'zbekcha F.I.O. ("Abduvaliev Javohir Jamshidovich") -> (ism, familiya).

	Moodle `firstname` va `lastname` ni alohida talab qiladi va ikkisi ham
	bo'sh bo'lmasligi kerak. Bizda birinchi so'z — familiya.
	"""
	parts = (full or "").split()
	if not parts:
		return "-", "-"
	if len(parts) == 1:
		return parts[0], "-"
	return " ".join(parts[1:]), parts[0]


def _password():
	"""Moodle parol siyosatiga mos (uzunlik, raqam, katta/kichik harf, belgi)."""
	alpha = string.ascii_lowercase
	upper = string.ascii_uppercase
	digits = string.digits
	special = "!@#$%*"
	chars = (
		[secrets.choice(upper), secrets.choice(digits), secrets.choice(special)]
		+ [secrets.choice(alpha + digits) for _ in range(7)]
	)
	secrets.SystemRandom().shuffle(chars)
	return "".join(chars)


def _hash(payload):
	return hashlib.md5(
		json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
	).hexdigest()


def _username_free(candidate):
	"""Moodle'da bu username bo'shmi? (yangi foydalanuvchi uchun bir marta)"""
	res = _call("core_user_get_users_by_field", {"field": "username", "values": [candidate]})
	return not res


def _make_username(full_name, idnumber, taken):
	"""Login yasash: familiya.ism -> bo'sh bo'lmasa raqam qo'shiladi.

	`taken` — shu sinxron ichida band qilinganlar (Moodle'ga hali yozilmagan).
	Bir marta yasalib Moodle User Link'da saqlanadi va boshqa o'zgarmaydi.
	"""
	parts = (full_name or "").split()
	base = _translit(".".join(parts[:2])) if len(parts) >= 2 else _translit(full_name)
	if not base:
		base = _translit(idnumber) or "user"
	base = base[:80]

	candidate = base
	i = 1
	while candidate in taken or not _username_free(candidate):
		i += 1
		candidate = f"{base}{i}"
		if i > 50:
			candidate = f"{base}.{secrets.token_hex(3)}"
			break
	taken.add(candidate)
	return candidate


# ---------------------------------------------------------------- Frappe tomoni

def _students():
	"""(idnumber, Student, F.I.Sh., faolmi) ro'yxati."""
	rows = frappe.get_all(
		"Student",
		fields=["name", "student_name", "first_name", "enabled", "date_of_leaving"],
		limit_page_length=0,
	)
	out = []
	for r in rows:
		full = (r.student_name or r.first_name or "").strip()
		active = bool(r.enabled) and not r.date_of_leaving
		out.append({
			"idnumber": r.name,
			"person_type": "Student",
			"reference_name": r.name,
			"full_name": full,
			"active": active,
		})
	return out


def _instructors():
	"""(idnumber, Instructor, F.I.Sh., faolmi) ro'yxati.

	Kalit — Employee ID (barqaror). Employee'si yo'q o'qituvchida Instructor
	docname'dan yasaladi; Instructor docname ismdan iborat, ism o'zgarsa kalit
	ham o'zgaradi va Moodle'da ikkinchi akkaunt paydo bo'ladi — shuning uchun
	bunday o'qituvchilar logda ogohlantirish sifatida ko'rinadi.
	"""
	rows = frappe.get_all(
		"Instructor",
		fields=["name", "instructor_name", "employee", "status", "custom_vakant"],
		limit_page_length=0,
	)
	out = []
	for r in rows:
		full = (r.instructor_name or r.name or "").strip()
		key = r.employee or f"INSTR-{r.name}"
		out.append({
			"idnumber": key,
			"person_type": "Instructor",
			"reference_name": r.name,
			"full_name": full,
			"active": (r.status == "Active") and not r.custom_vakant,
			"no_employee": not r.employee,
		})
	return out


# ---------------------------------------------------------------- Moodle tomoni

def _moodle_by_idnumber(idnumbers):
	"""idnumber -> Moodle user dict. Bo'sh/yo'qlar javobga tushmaydi."""
	found = {}
	values = [i for i in idnumbers if i]
	for i in range(0, len(values), LOOKUP_BATCH):
		chunk = values[i : i + LOOKUP_BATCH]
		res = _call("core_user_get_users_by_field", {"field": "idnumber", "values": chunk})
		for u in res or []:
			if u.get("idnumber"):
				found[u["idnumber"]] = u
	return found


def _create_users(users):
	"""Moodle'da yaratadi. Partiya butunlay rad etilsa, bittalab qayta uriniladi.

	Qaytaradi: (yaratilganlar {username: moodle_id}, xatolar {username: matn})
	"""
	created, errors = {}, {}
	try:
		res = _call("core_user_create_users", {"users": users})
		for u in res or []:
			created[u["username"]] = u["id"]
		return created, errors
	except MoodleError as batch_err:
		if len(users) == 1:
			errors[users[0]["username"]] = str(batch_err)
			return created, errors

	# Partiya atomar — bittasi yiqilsa hammasi yiqiladi. Aybdorni ajratamiz.
	for u in users:
		c, e = _create_users([u])
		created.update(c)
		errors.update(e)
	return created, errors


def _update_users(users):
	"""Moodle'da yangilaydi (id majburiy). Xato bo'lsa bittalab ajratiladi."""
	errors = {}
	if not users:
		return errors
	try:
		_call("core_user_update_users", {"users": users})
		return errors
	except MoodleError as batch_err:
		if len(users) == 1:
			errors[str(users[0].get("id"))] = str(batch_err)
			return errors
	for u in users:
		errors.update(_update_users([u]))
	return errors


# ---------------------------------------------------------------- Sinxron yadrosi

def sync(trigger="Qo'lda", limit=0):
	"""Asosiy sinxron. Moodle Sync Log yozuvini qaytaradi.

	`limit` > 0 bo'lsa — SINOV rejimi: faqat shuncha faol odam bilan ishlanadi.
	Bu qiymat hech qayerda saqlanmaydi (faqat qo'lda chaqirilganda beriladi),
	ya'ni 07:00 dagi avto sinxron hech qachon cheklanib qolmaydi.
	"""
	s, _base, _token = _conf()
	if not s.enabled:
		frappe.throw("Moodle Settings: integratsiya yoqilmagan (Yoqilgan belgisini qo'ying).")

	log = frappe.get_doc({
		"doctype": "Moodle Sync Log",
		"trigger_type": trigger,
		"status": "Ishlayapti",
		"started": now_datetime(),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

	lines = []
	stat = {"created": 0, "updated": 0, "suspended": 0, "skipped": 0, "errors": 0}
	dry = bool(s.dry_run)
	if dry:
		lines.append("TEST REJIMI: Moodle'ga hech narsa yozilmaydi.")

	try:
		people = []
		if s.sync_students:
			people += _students()
		if s.sync_teachers:
			people += _instructors()
		if not people:
			lines.append("Sinxron qamrovi bo'sh — o'quvchi ham, o'qituvchi ham belgilanmagan.")

		limit = int(limit or 0)
		if limit > 0:
			people = [p for p in people if p["active"]][:limit]
			lines.append(
				f"SINOV REJIMI: faqat {len(people)} faol odam bilan ishlanadi (limit={limit}). "
				"Qolganlar bu yurishda butunlay chetlab o'tiladi."
			)

		links = {
			d.name: d
			for d in frappe.get_all(
				"Moodle User Link",
				fields=["name", "moodle_user_id", "moodle_username", "moodle_email",
						"sync_hash", "status", "full_name", "person_type", "reference_name"],
				limit_page_length=0,
			)
		}
		# Kalit o'zgarganini aniqlash uchun ikkinchi indeks: kim -> bog'lanish.
		# Masalan Instructor'ga keyin Employee bog'lansa, kalit INSTR-<ism> dan
		# HR-EMP-xxxxx ga o'zgaradi — bunda YANGI akkaunt ochmaymiz.
		by_ref = {
			(d.person_type, d.reference_name): d
			for d in links.values()
			if d.reference_name
		}
		existing = _moodle_by_idnumber([p["idnumber"] for p in people])
		lines.append(
			f"Frappe: {len(people)} odam | Moodle'da idnumber bo'yicha topildi: {len(existing)}"
			f" | mahalliy bog'lanish: {len(links)}"
		)

		domain = (s.email_domain or "target.local").strip().lstrip("@")
		auth = s.auth_method or "manual"
		taken = {l.moodle_username for l in links.values() if l.moodle_username}

		to_create, to_update, new_links, to_rename = [], [], {}, []

		for p in people:
			key = p["idnumber"]
			link = links.get(key)
			mdl = existing.get(key)
			firstname, lastname = _split_name(p["full_name"])
			suspended = 0 if p["active"] else 1

			if not p["active"] and not link and not mdl:
				# Ketgan/o'chirilgan odamga yangi akkaunt ochmaymiz
				stat["skipped"] += 1
				continue

			if p.get("no_employee"):
				lines.append(f"OGOHLANTIRISH {key}: Instructor'da Employee bog'lanmagan — kalit ism asosida.")

			if not s.suspend_on_leave and suspended:
				suspended = 0

			shape = _hash({
				"f": firstname, "l": lastname, "s": suspended,
				"id": mdl.get("id") if mdl else None,
			})

			if mdl:
				# Moodle'da bor — mahalliy bog'lanishni to'g'rilab, kerak bo'lsa yangilaymiz
				if link and link.sync_hash == shape and link.moodle_user_id == mdl.get("id"):
					stat["skipped"] += 1
					continue
				to_update.append({
					"id": mdl["id"],
					"firstname": firstname,
					"lastname": lastname,
					"suspended": suspended,
				})
				new_links[key] = {
					**p,
					"moodle_user_id": mdl["id"],
					"moodle_username": mdl.get("username"),
					"moodle_email": mdl.get("email"),
					"sync_hash": shape,
					"suspended": suspended,
					"op": "update",
				}
			else:
				eski = by_ref.get((p["person_type"], p["reference_name"]))
				if eski and eski.name != key and eski.moodle_user_id:
					# Shu odam uchun akkaunt BOR, lekin boshqa kalit bilan ochilgan
					# (masalan Instructor'ga keyinroq Employee bog'landi).
					# Ikkinchi akkaunt ochmaymiz — borining idnumber'ini yangilaymiz.
					lines.append(
						f"KALIT O'ZGARDI: {eski.name} -> {key} ({p['full_name']}) — "
						"mavjud Moodle akkaunti yangilanadi, yangisi ochilmaydi."
					)
					to_update.append({
						"id": eski.moodle_user_id,
						"idnumber": key,
						"firstname": firstname,
						"lastname": lastname,
						"suspended": suspended,
					})
					to_rename.append((eski.name, key))
					new_links[key] = {
						**p,
						"moodle_user_id": eski.moodle_user_id,
						"moodle_username": eski.moodle_username,
						"moodle_email": eski.moodle_email,
						"sync_hash": shape,
						"suspended": suspended,
						"op": "rekey",
					}
					continue

				if suspended:
					# Moodle'da yo'q va faol emas — yaratmaymiz
					stat["skipped"] += 1
					continue
				username = (link.moodle_username if link and link.moodle_username
							else _make_username(p["full_name"], key, taken))
				email = (link.moodle_email if link and link.moodle_email
						 else f"{username}@{domain}")
				password = _password()
				to_create.append({
					"username": username,
					"password": password,
					"firstname": firstname,
					"lastname": lastname,
					"email": email,
					"idnumber": key,
					"auth": auth,
				})
				new_links[key] = {
					**p,
					"moodle_username": username,
					"moodle_email": email,
					"initial_password": password,
					"sync_hash": shape,
					"suspended": 0,
					"op": "create",
				}

		lines.append(f"Reja: yaratish {len(to_create)}, yangilash {len(to_update)}, o'zgarmagan {stat['skipped']}")

		if dry:
			for u in to_create[:20]:
				lines.append(f"  [test] yaratiladi: {u['username']} | {u['lastname']} {u['firstname']} | {u['idnumber']}")
			if len(to_create) > 20:
				lines.append(f"  ... va yana {len(to_create) - 20} ta")
			stat["created"] = len(to_create)
			stat["updated"] = len(to_update)
		else:
			# --- Yaratish
			for i in range(0, len(to_create), BATCH):
				chunk = to_create[i : i + BATCH]
				created, errors = _create_users(chunk)
				for username, mid in created.items():
					key = next(k for k, v in new_links.items() if v.get("moodle_username") == username)
					new_links[key]["moodle_user_id"] = mid
					stat["created"] += 1
				for username, err in errors.items():
					key = next((k for k, v in new_links.items() if v.get("moodle_username") == username), None)
					if key:
						new_links[key]["error"] = err
					stat["errors"] += 1
					lines.append(f"XATO yaratishda {username}: {err}")

			# --- Yangilash
			for i in range(0, len(to_update), BATCH):
				chunk = to_update[i : i + BATCH]
				errors = _update_users(chunk)
				ok = len(chunk) - len(errors)
				stat["updated"] += ok
				for mid, err in errors.items():
					stat["errors"] += 1
					lines.append(f"XATO yangilashda (moodle id {mid}): {err}")

		stat["suspended"] = sum(1 for v in new_links.values() if v.get("suspended"))

		# Kalit o'zgarganlar: mahalliy yozuvni yangi nomga ko'chiramiz (tarix saqlanadi)
		if not dry:
			for eski_nom, yangi_nom in to_rename:
				try:
					frappe.rename_doc("Moodle User Link", eski_nom, yangi_nom,
									  force=True, ignore_permissions=True)
				except Exception as e:
					stat["errors"] += 1
					lines.append(f"XATO nom o'zgartirishda {eski_nom} -> {yangi_nom}: {e}")

		_save_links(new_links, dry)

		frappe.db.set_single_value("Moodle Settings", "last_sync", now_datetime())
		frappe.db.set_single_value(
			"Moodle Settings",
			"last_status",
			f"{'TEST — ' if dry else ''}yaratildi {stat['created']}, yangilandi {stat['updated']}, "
			f"to'xtatildi {stat['suspended']}, o'zgarmagan {stat['skipped']}, xato {stat['errors']}",
		)

		log.db_set({
			"status": "Xato" if stat["errors"] and not stat["created"] and not stat["updated"] else "Tugadi",
			"finished": now_datetime(),
			"created_count": stat["created"],
			"updated_count": stat["updated"],
			"suspended_count": stat["suspended"],
			"skipped_count": stat["skipped"],
			"error_count": stat["errors"],
			"details": "\n".join(lines)[:140000],
		})
		frappe.db.commit()
		return log.name

	except Exception as e:
		frappe.db.rollback()
		lines.append(f"TO'XTADI: {e}")
		log.db_set({
			"status": "Xato",
			"finished": now_datetime(),
			"error_count": stat["errors"] + 1,
			"details": ("\n".join(lines) + "\n\n" + frappe.get_traceback())[:140000],
		})
		frappe.db.set_single_value("Moodle Settings", "last_status", f"XATO: {e}")
		frappe.db.commit()
		frappe.log_error(title="Moodle sync", message=frappe.get_traceback())
		raise


def _save_links(new_links, dry):
	"""Moodle User Link yozuvlarini yangilaydi/yaratadi."""
	if dry:
		return
	for key, v in new_links.items():
		values = {
			# autoname "field:idnumber" — nom o'zgarganda maydon ham yangilanib tursin
			"idnumber": key,
			"person_type": v["person_type"],
			"reference_name": v["reference_name"],
			"full_name": v["full_name"],
			"moodle_user_id": v.get("moodle_user_id") or 0,
			"moodle_username": v.get("moodle_username"),
			"moodle_email": v.get("moodle_email"),
			"sync_hash": v.get("sync_hash"),
			"status": "Xato" if v.get("error") else ("To'xtatilgan" if v.get("suspended") else "Faol"),
			"last_synced": now_datetime(),
			"error": (v.get("error") or "")[:500],
		}
		if v.get("initial_password") and not v.get("error"):
			values["initial_password"] = v["initial_password"]

		if frappe.db.exists("Moodle User Link", key):
			doc = frappe.get_doc("Moodle User Link", key)
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({
				"doctype": "Moodle User Link",
				"idnumber": key,
				**values,
			})
			doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------- Kirish nuqtalari

@frappe.whitelist()
def parolni_korsat(link_name):
	"""Moodle User Link'dagi boshlang'ich parolni ochib beradi.

	Frappe `Password` maydonining qiymatini brauzerga yubormaydi (formada ****),
	shuning uchun uni ko'rsatishning yagona yo'li — shu usul. Faqat System Manager.
	"""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Moodle User Link", link_name)
	parol = doc.get_password("initial_password", raise_exception=False)
	return {
		"login": doc.moodle_username,
		"parol": parol or "",
		"email": doc.moodle_email,
		"full_name": doc.full_name,
		"holat": doc.status,
	}


@frappe.whitelist()
def preview(limit=10):
	"""Moodle'ga MUROJAAT QILMASDAN nima yuborilishini ko'rsatadi.

	Token hali yo'q paytda ham ishlaydi — ism bo'linishi, login va kalit
	to'g'ri yasalayotganini tekshirish uchun.
	"""
	frappe.only_for("System Manager")
	s = _settings()
	domain = (s.email_domain or "target.local").strip().lstrip("@")

	people = []
	if s.sync_students:
		people += _students()
	if s.sync_teachers:
		people += _instructors()

	faol = [p for p in people if p["active"]]
	namuna = []
	for p in faol[: int(limit)]:
		firstname, lastname = _split_name(p["full_name"])
		base = ".".join(p["full_name"].split()[:2])
		username = _translit(base)
		namuna.append({
			"kim": p["person_type"],
			"kalit (idnumber)": p["idnumber"],
			"familiya (lastname)": lastname,
			"ism (firstname)": firstname,
			"login": username,
			"email": f"{username}@{domain}",
		})

	return {
		"jami": len(people),
		"faol": len(faol),
		"nofaol": len(people) - len(faol),
		"o_quvchi": sum(1 for p in people if p["person_type"] == "Student"),
		"o_qituvchi": sum(1 for p in people if p["person_type"] == "Instructor"),
		"employee_yo_q_o_qituvchi": sum(1 for p in people if p.get("no_employee")),
		"namuna": namuna,
	}


@frappe.whitelist()
def test_connection():
	"""Moodle Settings'dagi tugma: token va ruxsatlarni tekshiradi."""
	frappe.only_for("System Manager")
	info = _call("core_webservice_get_site_info")
	funcs = {f["name"] for f in info.get("functions", [])}
	kerak = {
		"core_user_get_users_by_field",
		"core_user_create_users",
		"core_user_update_users",
	}
	return {
		"sitename": info.get("sitename"),
		"release": info.get("release"),
		"username": info.get("username"),
		"userid": info.get("userid"),
		"yetishmayotgan_funksiyalar": sorted(kerak - funcs),
	}


@frappe.whitelist()
def sync_now(limit=0):
	"""Moodle Settings'dagi "Hozir sinxronlash" / "Sinov sinxroni" tugmasi."""
	frappe.only_for("System Manager")
	return sync(trigger="Qo'lda", limit=limit)


def daily_sync():
	"""Scheduler: har kuni 07:00 (hooks.py -> cron "0 7 * * *")."""
	s = _settings()
	if not s.enabled:
		return
	sync(trigger="Avto (07:00)")
