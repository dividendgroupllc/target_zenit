# Copyright (c) 2026, Target Zenit
"""O'QUV REJA (KTP) — Excel orqali ommaviy yuklash.

MUAMMO: KTP moduli 2026-10-09 da qurilgan, lekin bazada bitta ham reja yo'q —
mavzularni bitta-bitta qo'lda kiritish real emas (28 fan x sinf darajalari x
4 chorak). Zam direktor butun yillik rejani bitta Excel bilan yuklasin.

QARORLAR (foydalanuvchi, 2026-11-08):
  1. Reja TANLANGAN GURUHLARGA tegishli. Parallel sinflar birga tanlanadi:
     «Matematika 5-sinf» 5A va 5B ga birdek. Lekin maktabda guruhlar faqat
     raqamli sinf emas — fan oqimlari («ENGLISH Low 6-7», «MATH High 5»),
     tanlov guruhlari («CHOICE IT 9-11»), qo'shma darslar («P.E 5A+5B») ham
     bor. Low va High da mavzular BIR XIL EMAS, shuning uchun har oqimga
     ALOHIDA reja yuklanadi (2026-11-09 tuzatishi). O'tilganlik Moodle
     tomonda kuzatiladi — Frappe faqat rejani saqlaydi.
  2. Fayl — BITTA varaq, ustunlar bilan.
  3. Mavzu darsga KETMA-KET, avtomatik biriktiriladi (Moodle tomonda,
     chorakdagi darslar sanasi bo'yicha).

FAYL FORMATI (sarlavha qatori majburiy, ustun tartibi muhim emas):

    Fan | Sinf | Chorak | № | Bo'lim | Mavzu | Soat | Dars turi

  Fan      — kod (MATH) yoki to'liq nom; ikkisi ham tanilади
  Sinf     — daraja raqami (5) yoki sinf nomi («5 A(full)»). FAQAT raqamli
             sinflar uchun. Oqim guruhlari («ENGLISH Low 6-7») bu ustun bilan
             ko'rsatilmaydi — ular sahifada tanlanadi.
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


def _guruh_malumot(fan: str | None = None) -> list[dict]:
	"""Jadvalda DARSI BOR guruhlar — turi, darajasi va bloki bilan.

	NEGA HAMMASI: maktabda guruhlar faqat «5 A», «5 B» emas. Fan oqimlari
	(«ENGLISH Low 6-7», «MATH High 5»), tanlov guruhlari («CHOICE IT 9-11»),
	qo'shma darslar («P.E - GYM 5A+5B») — bularning har biriga ALOHIDA reja
	kerak, chunki «ENGLISH Low» va «ENGLISH High» da mavzular bir xil emas.
	Avval guruh nomidan sinf raqami ajratilardi va raqamsiz guruhlar
	ro'yxatdan butunlay tushib qolardi (2026-11-09 da tuzatildi).

	`fan` berilsa — faqat SHU fandan darsi bor guruhlar (zavuch ENGLISH
	tanlasa, MATH oqimlarini ko'rishning ma'nosi yo'q)."""
	shart = "WHERE guruh IS NOT NULL AND guruh <> ''"
	qiymat: dict = {}
	if fan:
		shart += " AND fan = %(fan)s"
		qiymat["fan"] = fan

	darsli = frappe.db.sql(
		f"""SELECT guruh, COUNT(*) AS darslar
		      FROM `tabJadval Yozuvi` {shart}
		  GROUP BY guruh""", qiymat, as_dict=True)
	if not darsli:
		return []

	nomlar = [r.guruh for r in darsli]
	meta = frappe.get_meta("Student Group")
	maydonlar = ["name", "student_group_name"]
	for q in ("custom_guruh_turi", "custom_daraja", "custom_blok"):
		if meta.has_field(q):
			maydonlar.append(q)
	sg = {r.name: r for r in frappe.get_all(
		"Student Group", filters={"name": ["in", nomlar]},
		fields=maydonlar, limit_page_length=0)}

	out = []
	for r in darsli:
		g = sg.get(r.guruh) or {}
		turi = g.get("custom_guruh_turi") or (
			"Sinf" if _sinf_nomimi(r.guruh) else "Boshqa")
		out.append({
			"name": r.guruh,
			"nomi": g.get("student_group_name") or r.guruh,
			"turi": turi,
			"daraja": g.get("custom_daraja") or "",
			"blok": g.get("custom_blok") or "",
			# `sinf` FAQAT haqiqiy sinf guruhida: «ENGLISH Low 6-7» dan ham
			# raqam ajralib, u 6-sinf ro'yxatiga qo'shilib ketardi
			"sinf": _daraja(r.guruh) if turi == "Sinf" else "",
			"darslar": r.darslar,
		})
	out.sort(key=lambda x: (x["turi"], cint(x["sinf"]) or 99, x["name"]))
	return out


def _guruhlar() -> dict:
	"""daraja raqami -> [Student Group]. Excel'dagi «Sinf» ustuni uchun.

	Faqat RAQAMLI sinf guruhlari (5 A, 5 B …) — raqamsiz oqim guruhlariga
	«Sinf» ustuni bilan murojaat qilib bo'lmaydi, ular sahifada tanlanadi."""
	out: dict[str, list] = {}
	for g in _guruh_malumot():
		if g["sinf"]:
			out.setdefault(g["sinf"], []).append(g["name"])
	return out


def _sinf_nomimi(nom: str) -> bool:
	"""«5 A(full)» kabi RAQAM BILAN BOSHLANADIGAN sinf nomimi?

	`custom_guruh_turi` to'ldirilmagan guruhlar uchun zaxira usul. Oddiy
	«raqam bormi» tekshiruvi yaramaydi: «ENGLISH Low 6-7» da ham raqam bor."""
	return bool(re.match(r"\s*\d+\s*[A-Za-z(]", str(nom or "")))


def _daraja(xom) -> str:
	"""«5», «5-sinf», «5 A(full)» -> «5»."""
	m = re.search(r"\d+", str(xom or ""))
	return m.group(0) if m else ""


def _joriy_yil() -> str | None:
	from target_zenit.oquv_reja import _joriy_yil as yil

	return yil()


# ================================================================= tanlov (sahifa)
def _tanlovni_tekshir(fan, guruhlar) -> tuple:
	"""Sahifadagi tanlovni tekshiradi -> (fan, [guruh], yorliq).

	ESKI QOIDA OLIB TASHLANDI (2026-11-09): guruhlar bitta RAQAMLI sinf
	darajasidan bo'lishi shart emas. «ENGLISH Low 6-7» da 6 va 7-sinf
	o'quvchilari birga o'qiydi, «CHOICE IT 9-11» da esa 9, 10, 11 — bunday
	guruhga raqamli daraja tushunchasi mos kelmaydi. Reja endi TANLANGAN
	GURUHLAR bo'yicha aniqlanadi, `sinf_daraja` esa faqat YORLIQ.

	Yorliq: raqamli sinflar uchun «5», oqim guruhlari uchun esa guruhning
	bloki yoki darajasi («ENGLISH 6-7», «High») — hisobotlarda o'qish uchun."""
	if isinstance(guruhlar, str):
		guruhlar = frappe.parse_json(guruhlar) if guruhlar.strip().startswith("[") else [guruhlar]
	guruhlar = [g for g in (guruhlar or []) if g]

	if fan and not frappe.db.exists("Course", fan):
		frappe.throw(_("Fan topilmadi: {0}").format(fan))
	if not guruhlar:
		return (fan or None), [], None

	yoq = [g for g in guruhlar if not frappe.db.exists("Student Group", g)]
	if yoq:
		frappe.throw(_("Guruh topilmadi: {0}").format(", ".join(yoq)))

	return (fan or None), guruhlar, _yorliq(guruhlar)


def _yorliq(guruhlar: list) -> str:
	"""Tanlangan guruhlar uchun o'qiladigan yorliq (`sinf_daraja`).

	Bu YORLIQ — reja aynanligi guruhlar ro'yxati bilan belgilanadi
	(`_reja_topish`), yorliq esa faqat ro'yxatlarda ko'rinishi uchun.

	Sinf guruhlari -> «5» yoki «5-7». Oqim guruhlari -> bloki
	(«ENGLISH 6-7»), bo'lmasa guruh nomining o'zi. RAQAM AJRATILMAYDI:
	«ENGLISH Low 6-7» ni «6» deb belgilash Low va High ni ajratib
	bo'lmaydigan qilib qo'yardi."""
	malumot = {g["name"]: g for g in _guruh_malumot()}

	sinflar, oqimlar = [], []
	for g in guruhlar:
		m = malumot.get(g)
		if m and m["turi"] == "Sinf" and m["sinf"]:
			sinflar.append(m["sinf"])
		elif m is None and _sinf_nomimi(g) and _daraja(g):
			sinflar.append(_daraja(g))      # jadvalda darsi yo'q sinf guruhi
		else:
			oqimlar.append(g)

	if sinflar and not oqimlar:
		r = sorted(set(sinflar), key=cint)
		return r[0] if len(r) == 1 else f"{r[0]}-{r[-1]}"

	bloklar = {m["blok"] for m in (malumot.get(g) for g in oqimlar) if m and m["blok"]}
	if len(bloklar) == 1 and not sinflar:
		return next(iter(bloklar))[:140]

	return ", ".join(guruhlar)[:140]


@frappe.whitelist()
def tanlov(fan: str | None = None) -> dict:
	"""Sahifa uchun: fanlar va guruhlar ro'yxati.

	Faqat jadvalda DARSI BOR fan/guruhlar qaytariladi — arxiv guruhga reja
	biriktirish zavuchni chalg'itadi. `fan` berilsa, guruhlar SHU fanga
	qarab filtrlanadi: ENGLISH tanlansa ENGLISH oqimlari va sinflar
	ko'rinadi, MATH oqimlari esa yo'q."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	# Darsi bor fanlar + nechta dars (zavuch bo'sh fanni tanlamasligi uchun)
	darsli = {r.fan: r.darslar for r in frappe.db.sql(
		"""SELECT fan, COUNT(*) AS darslar FROM `tabJadval Yozuvi`
		    WHERE fan IS NOT NULL AND fan <> '' GROUP BY fan""", as_dict=True)}
	nomlar = {r.name: (r.course_name or r.name) for r in frappe.get_all(
		"Course", filters={"name": ["in", list(darsli)]} if darsli else None,
		fields=["name", "course_name"], limit_page_length=0)}
	fanlar = sorted(
		({"name": k, "nomi": nomlar.get(k, k), "darslar": v} for k, v in darsli.items()),
		key=lambda x: x["nomi"].lower())

	guruhlar = _guruh_malumot(fan)

	# Turlar bo'yicha guruhlab beramiz — sahifada shunday ko'rsatiladi
	TARTIB = ("Sinf", "Daraja", "Tanlov", "Qo'shma", "Boshqa")
	turlar: dict[str, list] = {}
	for g in guruhlar:
		turlar.setdefault(g["turi"], []).append(g)

	return {
		"oquv_yili": _joriy_yil(),
		"fan": fan,
		"fanlar": fanlar,
		"guruhlar_jami": len(guruhlar),
		"turlar": [
			{"turi": t, "guruhlar": turlar[t]}
			for t in sorted(turlar, key=lambda x: (TARTIB.index(x) if x in TARTIB else 99, x))
		],
	}


# ================================================================= o'qish
def _qatorlar(path: str, st_fan: str | None = None,
              st_daraja: str | None = None,
              sinfsiz: bool = False) -> tuple[list[dict], list[str]]:
	"""Excel -> normallashgan qatorlar + xatolar ro'yxati.

	`st_fan` / `st_daraja` — sahifada tanlangani. Fayl ustuni bo'sh bo'lsa
	shu qiymat olinadi (fayl ustuni bor bo'lsa — fayl ustuvor).

	`sinfsiz=True` — zavuch guruhlarni sahifada tanlagan, demak «Sinf»
	ustuni umuman tekshirilmaydi (oqim guruhlarida sinf raqami yo'q)."""
	kerak = ("mavzu",) if sinfsiz else _majburiy(st_fan, st_daraja)
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

		if sinfsiz:
			daraja = ""
		else:
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
def _reja_topish(fan: str, yorliq: str, yil: str, guruhlar: list,
                 aniq_tanlov: bool = False) -> frappe.Document:
	"""Shu fan uchun rejani topadi yoki yaratadi.

	ANIQLIK QOIDASI (2026-11-09): reja aynanligi — fan + o'quv yili +
	GURUHLAR. `sinf_daraja` faqat yorliq, u bo'yicha qidirish XATO edi:
	«ENGLISH Low 6-7» va «ENGLISH High 6-7» ikkisi ham «6-7» yorlig'ini
	oladi va bitta rejaga qo'shilib ketardi, natijada Low oqimining
	mavzulari High'ning mavzulari bilan almashardi.

	`aniq_tanlov=True` — zavuch guruhlarni sahifada o'zi tanlagan: FAQAT
	a'zolik bo'yicha qidiriladi. Aks holda (Excel'dagi «Sinf» ustuni bilan
	ishlanganda) yorliq bo'yicha qidirish ham qoladi — eski rejalarda guruh
	biriktirilmagan bo'lishi mumkin."""
	nom = None
	if guruhlar:
		qator = frappe.db.sql(
			"""SELECT r.name FROM `tabOquv Reja` r
			   JOIN `tabOquv Reja Guruhi` g ON g.parent = r.name
			  WHERE r.fan = %(fan)s AND r.academic_year = %(yil)s
			    AND r.holat != 'Arxiv' AND g.guruh IN %(guruhlar)s
			  LIMIT 1""",
			{"fan": fan, "yil": yil, "guruhlar": tuple(guruhlar)},
		)
		nom = qator[0][0] if qator else None

	if not nom and not aniq_tanlov and yorliq:
		nom = frappe.db.get_value(
			"Oquv Reja",
			{"fan": fan, "sinf_daraja": yorliq, "academic_year": yil,
			 "holat": ["!=", "Arxiv"]},
			"name",
		)

	if nom:
		return frappe.get_doc("Oquv Reja", nom)

	doc = frappe.new_doc("Oquv Reja")
	doc.fan = fan
	doc.sinf_daraja = yorliq
	doc.academic_year = yil
	doc.holat = "Faol"
	return doc


def _reja_nomi(fan: str, yorliq: str, guruhlar: list) -> str:
	"""Reja nomi. Bitta oqim guruhi bo'lsa — guruhning O'Z nomi, shunda
	ro'yxatda «ENGLISH — 6» ikki marta turmaydi va Low/High ajraladi."""
	if len(guruhlar) == 1 and not _sinf_nomimi(guruhlar[0]):
		return f"{fan} — {guruhlar[0]}"[:140]
	if yorliq and yorliq.replace("-", "").isdigit():
		return f"{fan} — {yorliq}-sinf"
	return f"{fan} — {yorliq or ', '.join(guruhlar)}"[:140]


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

	st_fan, st_guruhlar, st_yorliq = _tanlovni_tekshir(fan, guruhlar)
	aniq = bool(st_guruhlar)

	# ANIQ TANLOVDA Excel'dan sinf o'qilmaydi: «ENGLISH Low 6-7» guruhida
	# 6 va 7-sinf birga, ya'ni raqamli daraja ma'nosiz. Rejani guruhlar
	# belgilaydi, Excel esa faqat mavzular ro'yxatini beradi.
	qatorlar, xatolar = _qatorlar(path, st_fan, None if aniq else st_yorliq,
	                              sinfsiz=aniq)
	if not qatorlar:
		return {"holat": "xato", "xatolar": xatolar or ["O'qiladigan qator topilmadi"],
		        "qatorlar": 0}

	guruh_xarita = {} if aniq else _guruhlar()

	# Aniq tanlovda hamma qator BITTA rejaga; aks holda (fan, daraja) kesimida
	guruhlangan: dict[tuple, list] = {}
	for r in qatorlar:
		kalit = (r["fan"], "") if aniq else (r["fan"], r["daraja"])
		guruhlangan.setdefault(kalit, []).append(r)

	natija, jami_yangi = [], 0
	for (fan, daraja), qator in sorted(guruhlangan.items()):
		choraklar = {r["chorak"] for r in qator}
		guruhlar = st_guruhlar if aniq else guruh_xarita.get(daraja, [])
		yorliq = st_yorliq if aniq else daraja
		doc = _reja_topish(fan, yorliq, yil, guruhlar, aniq_tanlov=aniq)
		yangimi = not doc.get("name") or doc.get("__islocal")

		satr = {
			"fan": fan, "daraja": yorliq or "—", "reja": doc.get("name") or "(yangi)",
			"yangi_reja": bool(yangimi),
			"choraklar": sorted(c for c in choraklar if c) or ["(choraksiz)"],
			"mavzular": len(qator),
			"guruhlar": guruhlar,
		}
		jami_yangi += len(qator)

		if not cint(dry_run):
			doc.sinf_daraja = yorliq
			if not doc.nomi:
				doc.nomi = _reja_nomi(fan, yorliq, guruhlar)
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
		"yorliq": st_yorliq,
		"qatorlar": len(qatorlar),
		"rejalar": len(natija),
		"mavzular": jami_yangi,
		"xatolar": xatolar,
		"tafsilot": natija[:40],
	}


@frappe.whitelist()
def namuna_shablon() -> dict:
	"""Zam direktor uchun namuna shablon — IKKI varaq.

	«Mavzular» (asosiy) — sahifada fan va guruh tanlanadi, shuning uchun
	faylda Fan/Sinf ustunlari YO'Q. Zavuch uchun eng sodda yo'l.

	«Fan ustunli» — bitta fayl bilan bir necha fan va sinfni birdan yuklash
	kerak bo'lganda (masalan butun yillik KTP to'plami)."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	import io

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Font, PatternFill

	wb = Workbook()

	sarlavha_fill = PatternFill("solid", fgColor="1F4E78")
	sarlavha_font = Font(bold=True, color="FFFFFF")

	def varaq(ws, ustunlar, kengliklar, qatorlar):
		ws.append(ustunlar)
		for c in ws[1]:
			c.fill = sarlavha_fill
			c.font = sarlavha_font
			c.alignment = Alignment(horizontal="center", vertical="center")
		for q in qatorlar:
			ws.append(q)
		for harf, kenglik in zip(
			[chr(65 + i) for i in range(len(ustunlar))], kengliklar, strict=True
		):
			ws.column_dimensions[harf].width = kenglik
		ws.freeze_panes = "A2"

	# ---- 1-varaq: sahifa orqali yuklash (fan/sinf UI'da tanlanadi)
	ws = wb.active
	ws.title = "Mavzular"
	varaq(
		ws,
		["Chorak", "№", "Bo'lim", "Mavzu", "Soat", "Dars turi"],
		(8, 6, 26, 52, 7, 16),
		[
			[1, 1, "1-bob. Natural sonlar", "Natural sonlar va ular ustida amallar", 2, "Yangi mavzu"],
			[1, 2, "1-bob. Natural sonlar", "Qo'shish va ayirish", 2, "Yangi mavzu"],
			[1, 3, "1-bob. Natural sonlar", "Mashqlar yechish", 1, "Amaliy"],
			[1, 4, "1-bob. Natural sonlar", "Nazorat ishi (BSB)", 1, "Nazorat"],
			[2, 1, "2-bob. Kasrlar", "Oddiy kasr tushunchasi", 2, "Yangi mavzu"],
			[2, 2, "2-bob. Kasrlar", "Kasrlarni qiyoslash", 1, "Yangi mavzu"],
		],
	)

	# ---- 2-varaq: bir necha fan/sinf bitta faylda
	varaq(
		wb.create_sheet("Fan ustunli"),
		["Fan", "Sinf", "Chorak", "№", "Bo'lim", "Mavzu", "Soat", "Dars turi"],
		(14, 8, 8, 6, 24, 48, 7, 16),
		[
			["MATH", 5, 1, 1, "1-bob", "Natural sonlar", 2, "Yangi mavzu"],
			["MATH", 5, 1, 2, "1-bob", "Qo'shish va ayirish", 2, "Yangi mavzu"],
			["MATH", 6, 1, 1, "1-bob", "Butun sonlar", 2, "Yangi mavzu"],
			["ENGLISH", 5, 1, 1, "Unit 1", "Greetings and introductions", 1, "Yangi mavzu"],
		],
	)

	# ---- 3-varaq: qisqa qo'llanma
	yoriq = wb.create_sheet("Qo'llanma")
	for qator in (
		["USTUN", "MAJBURIYMI", "IZOH"],
		["Chorak", "ixtiyoriy", "1..4. Faylda qaysi choraklar bo'lsa, FAQAT o'shalar almashadi"],
		["№", "ixtiyoriy", "Chorak ichidagi tartib. Bo'sh bo'lsa fayldagi tartib olinadi"],
		["Bo'lim", "ixtiyoriy", "Bob/Unit nomi — mavzularni guruhlash uchun"],
		["Mavzu", "MAJBURIY", "Mavzusiz qator o'tkazib yuboriladi"],
		["Soat", "ixtiyoriy", "Mavzu necha darsga mo'ljallangan (bo'sh = 1)"],
		["Dars turi", "ixtiyoriy", "Bo'sh bo'lsa mavzu matnidan aniqlanadi (Nazorat/Amaliy/Takrorlash)"],
		["Fan", "tanlovga qarab", "Sahifada fan tanlangan bo'lsa shart emas. Kod (MATH) yoki to'liq nom"],
		["Sinf", "tanlovga qarab", "Sahifada guruh tanlangan bo'lsa shart emas. FAQAT raqamli sinf: «5» yoki «5 A(full)»"],
		[],
		["QOIDA", "", "Ustun TARTIBI muhim emas — sarlavha nomi bo'yicha topiladi"],
		["QOIDA", "", "Parallel sinflarni BIRGA belgilang: 5A va 5B bitta reja oladi"],
		["QOIDA", "", "Oqim guruhlariga ALOHIDA yuklang: ENGLISH Low 6-7 va ENGLISH High 6-7 - ikki xil reja"],
		["QOIDA", "", "Oqim/tanlov/qo'shma guruhlar sahifada tanlanadi, «Sinf» ustuni bilan emas"],
		["QOIDA", "", "Bitta chorakni alohida ham, butun yilni birdan ham yuklash mumkin"],
		["QOIDA", "", "Avval «Tekshirish» — hech narsa yozilmaydi, keyin «Tasdiqlash»"],
	):
		yoriq.append(qator)
	for c in yoriq[1]:
		c.fill = sarlavha_fill
		c.font = sarlavha_font
	for harf, kenglik in zip("ABC", (14, 16, 86), strict=True):
		yoriq.column_dimensions[harf].width = kenglik

	oqim = io.BytesIO()
	wb.save(oqim)

	fayl = frappe.get_doc({
		"doctype": "File", "file_name": "KTP_namuna_shablon.xlsx",
		"is_private": 1, "folder": "Home/Attachments",
		"content": oqim.getvalue(),
	})
	fayl.flags.ignore_permissions = True
	fayl.insert()
	return {"file_url": fayl.file_url, "file_name": fayl.file_name}
