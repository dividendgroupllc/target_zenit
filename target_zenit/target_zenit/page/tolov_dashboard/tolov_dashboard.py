# Copyright (c) 2026, Target Zenit
"""Oquvchilar to'lov paneli ("Оплаты учеников") — sinf x o'quvchi jadvali:
forma / kitob va oyma-oy nachisleniya qoldig'i va to'langan summa.

Manba — qarzdorlik enginesi tayyorlagan "Tolov Rejasi" (reja qatorlari):
  * oylik qatorlar (manba_hujjat bo'sh) — har oy "O'qitish xizmati" SI
    (nachisleniya): amount = nachislangan, paid_amount = to'langan,
    outstanding = qoldiq (qaytim ham hisobga olingan);
  * qo'shimcha qatorlar (manba_hujjat = SI nomi) — Kitob / Forma / Yotoqxona:
    bitta SI'da bir nechta item bo'lishi mumkin, shuning uchun to'langan va
    qoldiq item ulushiga PROPORTSIONAL taqsimlanadi (engine._charge_breakdown
    bilan bir xil mantiq).

Panel FAQAT KO'RSATKICH — hech narsa yozmaydi (to'lov Kassa'da kiritiladi).

Ustun nomlari ruscha: Группа / Ученик / Форма остатка / Форма /
Книга остатка / Книга / [Общежитие остатка / Общежитие] / <Месяц> остатка / <Месяц>.
Yotoqxona ustunlari tepadagi belgi (checkbox) bosilganda qo'shiladi va
jadvalda FAQAT yotoqxona nachisleniyasi/to'lovi bor o'quvchilar qoladi.

Ruxsat: sahifa (Page) rollari orqali — rollar UI'dan qo'shiladi.
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

SAHIFA = "tolov-dashboard"

# Qo'shimcha nachisleniya itemlari -> ustun kaliti
FORMA_ITEM = "Forma"
KITOB_ITEM = "Kitob"
# Yotoqxona — faqat tepadagi checkbox bosilganda ko'rinadi (hamma o'quvchi
# yotoqxonada turmaydi, shuning uchun alohida ustun va alohida ro'yxat)
YOTOQXONA_ITEM = "Yotoqxona to'lovi"
QOSHIMCHA_KALIT = {FORMA_ITEM: "forma", KITOB_ITEM: "kitob", YOTOQXONA_ITEM: "yotoqxona"}

# Reja qatoridagi oy nomi (o'zbekcha) -> ruscha ustun nomi
OY_RUS = {
	"Yanvar": "Январь", "Fevral": "Февраль", "Mart": "Март", "Aprel": "Апрель",
	"May": "Май", "Iyun": "Июнь", "Iyul": "Июль", "Avgust": "Август",
	"Sentabr": "Сентябрь", "Oktabr": "Октябрь", "Noyabr": "Ноябрь", "Dekabr": "Декабрь",
}
OY_RAQAM = {nom: i for i, nom in enumerate(OY_RUS, start=1)}


def _ruxsat_tekshir():
	"""Kirish huquqi sahifaning (Page) rol ro'yxatidan olinadi — rollar UI'dan
	qo'shiladi/olinadi, kodga qotirilmaydi."""
	rollar = frappe.get_all(
		"Has Role", filters={"parent": SAHIFA, "parenttype": "Page"}, pluck="role"
	) or ["System Manager"]
	if not set(rollar) & set(frappe.get_roles()):
		frappe.throw(_("Ruxsat yo'q"), frappe.PermissionError)


def _royxat(qiymat):
	"""Filtr qiymati: JSON ro'yxat, bitta satr yoki bo'sh -> ro'yxat."""
	if not qiymat:
		return []
	if isinstance(qiymat, (list, tuple)):
		return [str(x) for x in qiymat if x]
	s = str(qiymat).strip()
	if s.startswith("["):
		try:
			return [str(x) for x in json.loads(s) if x]
		except Exception:
			return []
	return [s] if s else []


def _oy_kalit(oy_label):
	"""'Sentabr 2026' -> ('2026-09', 'Сентябрь', 2026) ; tanimasa None."""
	m = re.match(r"^\s*([A-Za-z']+)\s+(\d{4})\s*$", str(oy_label or ""))
	if not m:
		return None
	nom, yil = m.group(1), cint(m.group(2))
	raqam = OY_RAQAM.get(nom)
	if not raqam:
		return None
	return f"{yil}-{raqam:02d}", OY_RUS[nom], yil


def _sinf_tartib(sinf):
	"""'10 B(hybrid)' -> (10, 'B(hybrid)') — sinflar raqam bo'yicha tartiblanadi."""
	m = re.match(r"^\s*(\d+)\s*(.*)$", str(sinf or ""))
	return (cint(m.group(1)), m.group(2)) if m else (999, str(sinf or ""))


def _item_ulushlari(si_nomlari):
	"""SI -> [(item_code, summa)] : qo'shimcha nachisleniyani item bo'yicha bo'lish."""
	if not si_nomlari:
		return {}
	out = {}
	for d in frappe.db.sql(
		"""SELECT parent, item_code, SUM(net_amount) amount
		   FROM `tabSales Invoice Item` WHERE parent IN %s GROUP BY parent, item_code""",
		(tuple(si_nomlari),), as_dict=True,
	):
		out.setdefault(d.parent, []).append((d.item_code, flt(d.amount)))
	return out


@frappe.whitelist()
def get_data(sinflar=None, oylar=None, yotoqxona=0):
	"""Panel ma'lumoti.

	sinflar   — tanlangan sinflar (bo'sh = hammasi)
	oylar     — tanlangan oy kalitlari "YYYY-MM" (bo'sh = default: hozirgi oy va
	            undan keyingi nachisleniya qilingan oylar)
	yotoqxona — 1 bo'lsa: yotoqxona ustunlari qo'shiladi va faqat yotoqxona
	            to'lovi bor o'quvchilar ko'rsatiladi
	"""
	_ruxsat_tekshir()
	tanlangan_sinflar = set(_royxat(sinflar))
	tanlangan_oylar = set(_royxat(oylar))
	faqat_yotoqxona = cint(yotoqxona)

	rejalar = frappe.get_all(
		"Tolov Rejasi",
		filters={"holat": "Faol"},
		fields=["name", "student", "student_name", "sinf", "customer"],
		limit_page_length=0,
	)
	if tanlangan_sinflar:
		rejalar = [r for r in rejalar if (r.sinf or "") in tanlangan_sinflar]
	reja_map = {r.name: r for r in rejalar}

	# Barcha sinflar (filtr ro'yxati uchun) — tanlovdan QAT'I NAZAR
	barcha_sinflar = sorted(
		{(r.sinf or "").strip() for r in frappe.get_all(
			"Tolov Rejasi", filters={"holat": "Faol"}, fields=["sinf"], limit_page_length=0)
			if (r.sinf or "").strip()},
		key=_sinf_tartib,
	)

	qatorlar_db = []
	if reja_map:
		qatorlar_db = frappe.db.sql(
			"""SELECT parent, oy_label, due_date, amount, paid_amount, qaytim,
					  outstanding, manba_hujjat, holat
			   FROM `tabTolov Rejasi Oyi`
			   WHERE parent IN %s AND IFNULL(holat,'') <> 'Bekor'""",
			(tuple(reja_map),), as_dict=True,
		)

	# ---- oylar: nachisleniya qilingan oylar (amount > 0) ----
	oy_meta = {}
	for r in qatorlar_db:
		if r.manba_hujjat or flt(r.amount) <= 0.005:
			continue
		k = _oy_kalit(r.oy_label)
		if k:
			oy_meta[k[0]] = {"kalit": k[0], "nom": k[1], "yil": k[2]}
	mavjud_oylar = [oy_meta[k] for k in sorted(oy_meta)]

	bugun = getdate(nowdate())
	joriy_kalit = f"{bugun.year}-{bugun.month:02d}"
	if tanlangan_oylar:
		korinadigan = [o for o in mavjud_oylar if o["kalit"] in tanlangan_oylar]
	else:
		# default: hozirgi oy va undan KEYINGI nachisleniyali oylar
		korinadigan = [o for o in mavjud_oylar if o["kalit"] >= joriy_kalit]
		if not korinadigan:                      # hali joriy oyga nachisleniya yo'q
			korinadigan = mavjud_oylar[-1:]
	korinadigan_kalitlar = [o["kalit"] for o in korinadigan]

	# Bir nechta yil ko'rinsa ustun nomiga yil qo'shiladi (Сентябрь 2026)
	yillar = {o["yil"] for o in korinadigan}
	for o in korinadigan:
		o["label"] = o["nom"] if len(yillar) <= 1 else f"{o['nom']} {o['yil']}"

	# ---- qo'shimcha (Kitob / Forma) item ulushlari ----
	si_nomlari = {r.manba_hujjat for r in qatorlar_db if r.manba_hujjat}
	si_itemlar = _item_ulushlari(si_nomlari)

	# ---- qatorlarni yig'ish ----
	def bosh():
		return {"nachislangan": 0.0, "tolangan": 0.0, "ostatka": 0.0}

	natija = {}
	for nom, r in reja_map.items():
		natija[nom] = {
			"reja": nom,
			"student": r.student,
			"ism": r.student_name or r.student,
			"sinf": (r.sinf or "").strip(),
			"customer": r.customer,
			"forma": bosh(), "kitob": bosh(), "yotoqxona": bosh(),
			"oylar": {k: bosh() for k in korinadigan_kalitlar},
		}

	for r in qatorlar_db:
		q = natija.get(r.parent)
		if not q:
			continue
		if not r.manba_hujjat:
			k = _oy_kalit(r.oy_label)
			if not k or k[0] not in q["oylar"]:
				continue
			d = q["oylar"][k[0]]
			d["nachislangan"] += flt(r.amount)
			d["tolangan"] += flt(r.paid_amount)
			d["ostatka"] += flt(r.outstanding)
			continue
		# Kitob / Forma: SI item ulushiga proportsional
		lst = si_itemlar.get(r.manba_hujjat) or []
		jami = sum(a for _, a in lst)
		if not jami:
			continue
		for item, summa in lst:
			kalit = QOSHIMCHA_KALIT.get(item)
			if not kalit:
				continue                      # boshqa itemlar bu panelda yo'q
			ulush = summa / jami
			d = q[kalit]
			d["nachislangan"] += flt(r.amount) * ulush
			d["tolangan"] += flt(r.paid_amount) * ulush
			d["ostatka"] += flt(r.outstanding) * ulush

	qatorlar = sorted(
		natija.values(), key=lambda q: (_sinf_tartib(q["sinf"]), q["ism"] or "")
	)
	# Yotoqxona belgisi: faqat yotoqxona nachisleniyasi yoki to'lovi borlar
	yotoqxonalilar = [q for q in qatorlar
					  if q["yotoqxona"]["nachislangan"] > 0.005 or q["yotoqxona"]["tolangan"] > 0.005]
	if faqat_yotoqxona:
		qatorlar = yotoqxonalilar

	# ---- jami (pastdagi yig'indi qatori) ----
	def _yigindi(olish):
		return {k: sum(olish(q)[k] for q in qatorlar) for k in ("nachislangan", "tolangan", "ostatka")}

	jami = {
		"forma": _yigindi(lambda q: q["forma"]),
		"kitob": _yigindi(lambda q: q["kitob"]),
		"yotoqxona": _yigindi(lambda q: q["yotoqxona"]),
		"oylar": {
			k: {p: sum(q["oylar"][k][p] for q in qatorlar)
				for p in ("nachislangan", "tolangan", "ostatka")}
			for k in korinadigan_kalitlar
		},
	}

	return {
		"qatorlar": qatorlar,
		"oylar": korinadigan,
		"mavjud_oylar": mavjud_oylar,
		"sinflar": barcha_sinflar,
		"tanlangan_sinflar": sorted(tanlangan_sinflar, key=_sinf_tartib),
		"tanlangan_oylar": sorted(tanlangan_oylar),
		"joriy_oy": joriy_kalit,
		"jami": jami,
		"soni": len(qatorlar),
		"yotoqxona": faqat_yotoqxona,
		"yotoqxona_soni": len(yotoqxonalilar),
	}
