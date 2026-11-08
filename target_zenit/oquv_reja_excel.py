# Copyright (c) 2026, Target Zenit
"""O'QUV REJA (KTP) — Excel orqali ommaviy yuklash.

MUAMMO: KTP moduli 2026-10-09 da qurilgan, lekin bazada bitta ham reja yo'q —
mavzularni bitta-bitta qo'lda kiritish real emas (28 fan x sinf darajalari x
4 chorak). Zam direktor butun yillik rejani bitta Excel bilan yuklasin.

QARORLAR (foydalanuvchi, 2026-11-08):
  1. Reja PARALLEL SINFLARGA BITTA: «Matematika 5-sinf» 5A, 5B, 5C ga
     birdek tegishli. O'tilganlik esa har sinf uchun alohida kuzatiladi
     (bu MOODLE tomonda kuzatiladi — Frappe faqat rejani saqlaydi).
  2. Fayl — BITTA varaq, ustunlar bilan.
  3. Mavzu darsga KETMA-KET, avtomatik biriktiriladi (Moodle tomonda,
     chorakdagi darslar sanasi bo'yicha).

FAYL FORMATI (sarlavha qatori majburiy, ustun tartibi muhim emas):

    Fan | Sinf | Chorak | № | Bo'lim | Mavzu | Soat | Dars turi

  Fan      — kod (MATH) yoki to'liq nom; ikkisi ham tanilади
  Sinf     — daraja raqami (5) yoki guruh nomi («5 A(full)»); raqam ajratiladi
  Chorak   — 1..4. Faylda qaysi choraklar bo'lsa, FAQAT o'shalar almashadi —
             shuning uchun bitta chorakni alohida ham, butun yilni birdan ham
             yuklash mumkin.
  №        — chorak ichidagi tartib. Bo'sh bo'lsa fayldagi tartib olinadi.
  Soat     — mavzu necha darsga mo'ljallangan (bo'sh = 1)

IKKI REJIM:
  A) FAYLDAN — Excel'da «Fan» va «Sinf» ustunlari bor: bitta fayl bilan
     bir necha fan va sinfni birdan yuklash mumkin.
  B) TANLOVDAN — zavuch sahifada fan va guruhlarni o'zi tanlaydi, Excel'da
     esa faqat «Chorak | № | Bo'lim | Mavzu | Soat» qoladi. Zam direktor
     uchun shu yo'l soddaroq, shuning uchun sahifada (/app/oquv-reja-yuklash)
     standart rejim shu.
  Ikkisi aralashsa ham ishlaydi: tanlov faqat fayl ustuni BO'SH bo'lgan
  qatorlarga qo'llanadi.

ISHGA TUSHIRISH:
    bench --site <sayt> execute target_zenit.oquv_reja_excel.import_excel \\
        --kwargs "{'path': '/home/.../ktp.xlsx', 'dry_run': 1}"
"""

from __future__ import annotations

import os
import re

import frappe
from frappe import _
from frappe.utils import cint

# Sarlavha nomlari — kichik harfda, bo'sh joysiz solishtiriladi
USTUNLAR = {
	"fan": ("fan", "subject", "предмет", "fankodi", "fan_kodi"),
	"sinf": ("sinf", "sinfdaraja", "daraja", "class", "класс", "guruh"),
	"chorak": ("chorak", "term", "quarter", "четверть"),
	"tartib": ("№", "no", "n", "tartib", "raqam", "order"),
	"bolim": ("bolim", "bo'lim", "bölim", "bo`lim", "bobnomi", "bob", "unit", "раздел"),
	"mavzu": ("mavzu", "topic", "тема", "darsmavzusi"),
	"soat": ("soat", "soatlar", "hours", "часы", "darssoni"),
	"dars_turi": ("darsturi", "dars_turi", "tur", "type", "типурока"),
	"tavsif": ("tavsif", "izoh", "description", "описание"),
	"resurs": ("resurs", "resource", "manba", "ресурс"),
}

MAJBURIY = ("fan", "sinf", "mavzu")


def _majburiy(fan: str | None, daraja: str | None) -> tuple:
	"""Sahifada fan/sinf tanlangan bo'lsa, ular Excel'da bo'lishi shart emas."""
	if fan and daraja:
		return ("mavzu",)
	if fan:
		return ("sinf", "mavzu")
	if daraja:
		return ("fan", "mavzu")
	return MAJBURIY


def _kalit(matn) -> str:
	"""Sarlavhani solishtirish uchun soddalashtiradi."""
	return re.sub(r"[\s_.\-]+", "", str(matn or "").strip().lower())


def _ustun_xaritasi(sarlavha: list) -> dict:
	"""Excel sarlavhasidan {maydon: ustun indeksi}."""
	xarita = {}
	for i, nom in enumerate(sarlavha):
		k = _kalit(nom)
		if not k:
			continue
		for maydon, variantlar in USTUNLAR.items():
			if maydon in xarita:
				continue
			if k in {_kalit(v) for v in variantlar}:
				xarita[maydon] = i
				break
	return xarita


def _fayl_yoli(path: str) -> str:
	"""Frappe `/files/...` havolasini ham, oddiy yo'lni ham qabul qiladi."""
	if path.startswith(("/files/", "/private/files/")):
		return frappe.get_site_path(path.lstrip("/").replace("files/", "public/files/", 1)) \
			if path.startswith("/files/") else frappe.get_site_path(path.lstrip("/"))
	return path


def _oqish(path: str) -> list[list]:
	from openpyxl import load_workbook

	yol = _fayl_yoli(path)
	if not os.path.exists(yol):
		frappe.throw(_("Fayl topilmadi: {0}").format(yol))
	wb = load_workbook(yol, data_only=True, read_only=True)
	ws = wb[wb.sheetnames[0]]
	return [list(r) for r in ws.iter_rows(values_only=True)]


# ======================================================== nomlarni bog'lash
def _fanlar() -> dict:
	"""Kod va nom bo'yicha Course xaritasi."""
	out = {}
	# `course_code` bu o'rnatmada yo'q — faqat mavjud maydonlar so'raladi
	maydonlar = ["name", "course_name"]
	meta = frappe.get_meta("Course")
	for qoshimcha in ("course_code", "custom_fan_kodi"):
		if meta.has_field(qoshimcha):
			maydonlar.append(qoshimcha)

	for c in frappe.get_all("Course", fields=maydonlar, limit_page_length=0):
		for v in (c.get(m) for m in maydonlar):
			if v:
				out.setdefault(_kalit(v), c.name)
	return out


def _guruhlar() -> dict:
	"""daraja raqami -> [Student Group]. Faqat jadvalda DARSI BOR guruhlar:
	arxiv/bo'sh guruhlarni rejaga biriktirishning ma'nosi yo'q."""
	darsli = {
		r.guruh for r in frappe.db.sql(
			"SELECT DISTINCT guruh FROM `tabJadval Yozuvi`", as_dict=True) if r.guruh
	}
	out: dict[str, list] = {}
	for nom in sorted(darsli):
		m = re.match(r"\s*(\d+)", str(nom))
		if m:
			out.setdefault(m.group(1), []).append(nom)
	return out


def _daraja(xom) -> str:
	"""«5», «5-sinf», «5 A(full)» -> «5»."""
	m = re.search(r"\d+", str(xom or ""))
	return m.group(0) if m else ""


def _joriy_yil() -> str | None:
	from target_zenit.oquv_reja import _joriy_yil as yil

	return yil()


# ================================================================= tanlov (sahifa)
def _tanlovni_tekshir(fan, guruhlar) -> tuple:
	"""Sahifadagi tanlovni tekshiradi -> (fan, [guruh], daraja).

	Guruhlar BITTA darajadan bo'lishi shart: reja «fan x sinf darajasi» kesimida
	saqlanadi, 5A va 6A ni bitta rejaga qo'yish mavzular ketma-ketligini buzadi.
	Shuning uchun aralash tanlov darhol tushunarli xato bilan to'xtatiladi."""
	if isinstance(guruhlar, str):
		guruhlar = frappe.parse_json(guruhlar) if guruhlar.strip().startswith("[") else [guruhlar]
	guruhlar = [g for g in (guruhlar or []) if g]

	if fan and not frappe.db.exists("Course", fan):
		frappe.throw(_("Fan topilmadi: {0}").format(fan))
	if not guruhlar:
		return (fan or None), [], None

	darajalar = {_daraja(g) for g in guruhlar}
	darajalar.discard("")
	if len(darajalar) > 1:
		frappe.throw(_(
			"Guruhlar bitta sinf darajasidan bo'lishi kerak — tanlanganlar: {0}. "
			"Har bir daraja uchun alohida yuklang."
		).format(", ".join(sorted(darajalar))))
	if not darajalar:
		frappe.throw(_("Guruh nomidan sinf darajasi aniqlanmadi: {0}").format(", ".join(guruhlar)))

	yoq = [g for g in guruhlar if not frappe.db.exists("Student Group", g)]
	if yoq:
		frappe.throw(_("Guruh topilmadi: {0}").format(", ".join(yoq)))
	return (fan or None), guruhlar, next(iter(darajalar))


@frappe.whitelist()
def tanlov() -> dict:
	"""Sahifa uchun: fanlar ro'yxati + daraja bo'yicha guruhlar.

	Faqat jadvalda DARSI BOR guruhlar qaytariladi — arxiv guruhga reja
	biriktirish zavuchni chalg'itadi."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	fanlar = frappe.get_all("Course", fields=["name", "course_name"],
	                        order_by="course_name asc", limit_page_length=0)
	guruh_xarita = _guruhlar()
	nomlar = {}
	if guruh_xarita:
		hammasi = [g for lst in guruh_xarita.values() for g in lst]
		nomlar = {r.name: (r.student_group_name or r.name) for r in frappe.get_all(
			"Student Group", filters={"name": ["in", hammasi]},
			fields=["name", "student_group_name"], limit_page_length=0)}

	return {
		"oquv_yili": _joriy_yil(),
		"fanlar": fanlar,
		"darajalar": [
			{"daraja": d, "guruhlar": [{"name": g, "nomi": nomlar.get(g, g)}
			                           for g in guruh_xarita[d]]}
			for d in sorted(guruh_xarita, key=lambda x: cint(x))
		],
	}


# ================================================================= o'qish
def _qatorlar(path: str, st_fan: str | None = None,
              st_daraja: str | None = None) -> tuple[list[dict], list[str]]:
	"""Excel -> normallashgan qatorlar + xatolar ro'yxati.

	`st_fan` / `st_daraja` — sahifada tanlangani. Fayl ustuni bo'sh bo'lsa
	shu qiymat olinadi (fayl ustuni bor bo'lsa — fayl ustuvor)."""
	kerak = _majburiy(st_fan, st_daraja)
	xom = _oqish(path)
	if not xom:
		return [], ["Fayl bo'sh"]

	# Sarlavha qatorini topamiz: majburiy ustunlar uchragan birinchi qator
	xarita, bosh = {}, 0
	for i, qator in enumerate(xom[:10]):
		x = _ustun_xaritasi(qator)
		if all(m in x for m in kerak):
			xarita, bosh = x, i + 1
			break
	if not xarita:
		return [], [
			"Sarlavha qatori topilmadi. Kerakli ustunlar: "
			+ ", ".join(kerak) + " (va ixtiyoriy: chorak, №, bo'lim, soat, dars turi)"
		]

	fanlar, guruhlar = _fanlar(), _guruhlar()
	natija, xatolar = [], []
	nomalum_fan, nomalum_sinf = set(), set()

	def qiymat(qator, maydon):
		i = xarita.get(maydon)
		if i is None or i >= len(qator):
			return None
		v = qator[i]
		return str(v).strip() if v is not None and str(v).strip() != "" else None

	for n, qator in enumerate(xom[bosh:], start=bosh + 1):
		if not any(v is not None and str(v).strip() != "" for v in qator):
			continue        # bo'sh qator
		mavzu = qiymat(qator, "mavzu")
		if not mavzu:
			continue        # mavzusiz qator — ajratuvchi bo'lishi mumkin

		fan_xom = qiymat(qator, "fan")
		fan = (fanlar.get(_kalit(fan_xom)) if fan_xom else None) or st_fan
		if not fan:
			nomalum_fan.add(fan_xom or "(bo'sh)")
			continue

		daraja = _daraja(qiymat(qator, "sinf")) or (st_daraja or "")
		if not daraja or daraja not in guruhlar:
			nomalum_sinf.add(qiymat(qator, "sinf") or "(bo'sh)")
			continue

		chorak = _daraja(qiymat(qator, "chorak"))
		if chorak and chorak not in ("1", "2", "3", "4"):
			xatolar.append(f"{n}-qator: chorak 1..4 bo'lishi kerak ({chorak})")
			continue

		natija.append({
			"qator_raqami": n,
			"fan": fan,
			"daraja": daraja,
			"chorak": chorak or "",
			"tartib": cint(qiymat(qator, "tartib")),
			"bolim": qiymat(qator, "bolim") or "",
			"mavzu": mavzu,
			"soat": max(cint(qiymat(qator, "soat")), 0) or 1,
			"dars_turi": qiymat(qator, "dars_turi") or "",
			"tavsif": qiymat(qator, "tavsif") or "",
			"resurs": qiymat(qator, "resurs") or "",
		})

	if nomalum_fan:
		xatolar.append("Tanilmagan fan: " + ", ".join(sorted(nomalum_fan))
		               + " — Course ro'yxatida bormi?")
	if nomalum_sinf:
		xatolar.append("Tanilmagan sinf: " + ", ".join(sorted(nomalum_sinf))
		               + " — bu darajada jadvalda darsi bor guruh yo'q")
	return natija, xatolar


# ================================================================= yozish
def _reja_topish(fan: str, daraja: str, yil: str, guruhlar: list) -> frappe.Document:
	"""Shu fan × daraja × yil uchun rejani topadi yoki yaratadi.

	QIDIRUV TARTIBI: avval yorliq (`sinf_daraja`), keyin guruh a'zoligi —
	eski rejalarda yorliq bo'lmasligi mumkin. Topilmasa yangisi ochiladi."""
	nom = frappe.db.get_value(
		"Oquv Reja",
		{"fan": fan, "sinf_daraja": daraja, "academic_year": yil,
		 "holat": ["!=", "Arxiv"]},
		"name",
	)
	if not nom and guruhlar:
		qator = frappe.db.sql(
			"""SELECT r.name FROM `tabOquv Reja` r
			   JOIN `tabOquv Reja Guruhi` g ON g.parent = r.name
			  WHERE r.fan = %(fan)s AND r.academic_year = %(yil)s
			    AND r.holat != 'Arxiv' AND g.guruh IN %(guruhlar)s
			  LIMIT 1""",
			{"fan": fan, "yil": yil, "guruhlar": tuple(guruhlar)},
		)
		nom = qator[0][0] if qator else None

	if nom:
		return frappe.get_doc("Oquv Reja", nom)

	doc = frappe.new_doc("Oquv Reja")
	doc.fan = fan
	doc.sinf_daraja = daraja
	doc.academic_year = yil
	doc.holat = "Faol"
	return doc


def _guruhlarni_bogla(doc, guruhlar: list) -> int:
	"""Rejaga shu darajadagi guruhlarni biriktiradi (mavjudiga tegmaydi)."""
	bor = {g.guruh for g in (doc.get("sinflar") or [])}
	qoshildi = 0
	for g in guruhlar:
		if g not in bor:
			doc.append("sinflar", {"guruh": g})
			qoshildi += 1
	return qoshildi


def _qatorlarni_almashtir(doc, yangi: list, choraklar: set) -> dict:
	"""FAQAT fayldagi choraklarning qatorlarini almashtiradi.

	NEGA SHUNDAY: zam direktor 2-chorakni yuklaganda 1-chorak mavzulari
	(va ular bo'yicha o'tilganlik) yo'qolmasligi kerak. Choraksiz (eski)
	qatorlar ham saqlanadi — ular butun yilga tegishli deb hisoblanadi."""
	eski = list(doc.get("qatorlar") or [])
	qoladi = [r for r in eski if str(r.chorak or "") not in choraklar]

	doc.set("qatorlar", [])
	for r in qoladi:
		doc.append("qatorlar", {
			"tartib": r.tartib, "chorak": r.chorak, "bolim": r.bolim,
			"mavzu": r.mavzu, "soat": r.soat, "davomiylik_min": r.davomiylik_min,
			"dars_turi": r.dars_turi, "tavsif": r.tavsif, "resurs": r.resurs,
		})
	for r in yangi:
		doc.append("qatorlar", {
			"tartib": r["tartib"], "chorak": r["chorak"], "bolim": r["bolim"],
			"mavzu": r["mavzu"], "soat": r["soat"],
			"dars_turi": r["dars_turi"] or _tur(r["mavzu"]),
			"tavsif": r["tavsif"], "resurs": r["resurs"],
		})
	# Tartib raqamlari: chorak ichida ketma-ket, bo'sh bo'lsa o'zi qo'yiladi
	hisob: dict[str, int] = {}
	for r in doc.get("qatorlar"):
		ch = str(r.chorak or "")
		hisob[ch] = hisob.get(ch, 0) + 1
		if not cint(r.tartib):
			r.tartib = hisob[ch]
	return {"saqlandi": len(qoladi), "yangi": len(yangi)}


def _tur(mavzu: str) -> str:
	from target_zenit.oquv_reja import _tur_aniqla

	return _tur_aniqla(mavzu)


@frappe.whitelist()
def import_excel(path: str, dry_run: int = 1, academic_year: str | None = None,
                 fan: str | None = None, guruhlar=None) -> dict:
	"""Excel faylni o'qib, o'quv rejalarini yaratadi/yangilaydi.

	`dry_run=1` (standart) — hech narsa yozilmaydi, faqat nima bo'lishi
	ko'rsatiladi. Zam direktor avval shuni ko'rib, keyin tasdiqlaydi.

	`fan` + `guruhlar` — sahifadagi tanlov (B rejimi). Berilsa, reja AYNI
	shu guruhlarga biriktiriladi, Excel'da esa Fan/Sinf ustunlari shart emas."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	yil = academic_year or _joriy_yil()
	if not yil:
		frappe.throw(_("Joriy o'quv yili aniqlanmadi — Academic Year ro'yxatini tekshiring."))

	st_fan, st_guruhlar, st_daraja = _tanlovni_tekshir(fan, guruhlar)
	qatorlar, xatolar = _qatorlar(path, st_fan, st_daraja)
	if not qatorlar:
		return {"holat": "xato", "xatolar": xatolar or ["O'qiladigan qator topilmadi"],
		        "qatorlar": 0}

	guruh_xarita = _guruhlar()

	# (fan, daraja) bo'yicha guruhlaymiz
	guruhlangan: dict[tuple, list] = {}
	for r in qatorlar:
		guruhlangan.setdefault((r["fan"], r["daraja"]), []).append(r)

	natija, jami_yangi = [], 0
	for (fan, daraja), qator in sorted(guruhlangan.items()):
		choraklar = {r["chorak"] for r in qator}
		# Tanlov bo'lsa — aynan tanlangan guruhlar; aks holda shu darajadagi
		# jadvalda darsi bor barcha parallel guruhlar
		guruhlar = (st_guruhlar if (st_guruhlar and daraja == st_daraja)
		            else guruh_xarita.get(daraja, []))
		doc = _reja_topish(fan, daraja, yil, guruhlar)
		yangimi = not doc.get("name") or doc.get("__islocal")

		satr = {
			"fan": fan, "daraja": daraja, "reja": doc.get("name") or "(yangi)",
			"yangi_reja": bool(yangimi),
			"choraklar": sorted(c for c in choraklar if c) or ["(choraksiz)"],
			"mavzular": len(qator),
			"guruhlar": guruhlar,
		}
		jami_yangi += len(qator)

		if not cint(dry_run):
			doc.sinf_daraja = daraja
			if not doc.nomi:
				doc.nomi = f"{fan} — {daraja}-sinf"
			_guruhlarni_bogla(doc, guruhlar)
			satr.update(_qatorlarni_almashtir(doc, qator, choraklar))
			doc.flags.ignore_permissions = True
			doc.save()
			satr["reja"] = doc.name
		natija.append(satr)

	if not cint(dry_run):
		frappe.db.commit()

	return {
		"holat": "tayyor",
		"dry_run": cint(dry_run),
		"oquv_yili": yil,
		"tanlangan_fan": st_fan,
		"tanlangan_guruhlar": st_guruhlar,
		"qatorlar": len(qatorlar),
		"rejalar": len(natija),
		"mavzular": jami_yangi,
		"xatolar": xatolar,
		"tafsilot": natija[:40],
	}


@frappe.whitelist()
def namuna_shablon() -> dict:
	"""Zam direktor uchun bo'sh shablon (ustun nomlari + bitta namuna qator)."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	from openpyxl import Workbook

	wb = Workbook()
	ws = wb.active
	ws.title = "KTP"
	ws.append(["Fan", "Sinf", "Chorak", "№", "Bo'lim", "Mavzu", "Soat", "Dars turi"])
	ws.append(["MATH", 5, 1, 1, "Natural sonlar",
	           "Natural sonlar va ular ustida amallar", 2, "Yangi mavzu"])
	ws.append(["MATH", 5, 1, 2, "Natural sonlar", "Qo'shish va ayirish", 2, "Yangi mavzu"])
	ws.append(["ENGLISH", 5, 1, 1, "Unit 1", "Greetings and introductions", 1, "Yangi mavzu"])

	for ustun, kenglik in zip("ABCDEFGH", (14, 8, 8, 6, 24, 46, 7, 14), strict=True):
		ws.column_dimensions[ustun].width = kenglik

	import io

	oqim = io.BytesIO()
	wb.save(oqim)

	fayl = frappe.get_doc({
		"doctype": "File", "file_name": "KTP_shablon.xlsx",
		"is_private": 1, "folder": "Home/Attachments",
		"content": oqim.getvalue(),
	})
	fayl.flags.ignore_permissions = True
	fayl.insert()
	return {"file_url": fayl.file_url, "file_name": fayl.file_name}
