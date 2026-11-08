# Copyright (c) 2026, Target Zenit
"""Frappe -> Moodle: o'quv reja (KTP) mavzularini uzatish.

EGALIK TAQSIMOTI:
  * mavzular RO'YXATI — Frappe: zam direktor Excel bilan yuklaydi
    (`oquv_reja_excel.py`), reja fan x sinf darajasiga tegishli;
  * DARSGA BIRIKTIRISH — Moodle: qaysi kuni dars bor, bayram qachon,
    jadval o'zgardimi — bularning hammasi `_slot` da. Frappe'ga slot
    ro'yxatini tashish ortiqcha aylanma bo'lardi.

Reja PARALLEL SINFLARGA bitta, lekin Moodle'ga HAR GURUH uchun alohida
yuboriladi: 5A va 5B jadvali har xil (bayram, almashtirish), shuning uchun
biriktirish ham har guruhda mustaqil ketishi kerak.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

from target_zenit.integrations.moodle import MoodleError, _call, _settings

# Bitta so'rovda nechta qator. Moodle REST so'rovni forma maydonlari
# ko'rinishida oladi: har qator ~9 maydon, PHP `max_input_vars` = 5000.
# 300 x 9 = 2700 — zaxirasi bilan xavfsiz.
BATCH = 300


def _qatorlar(academic_year: str, fan: str | None = None) -> list[dict]:
	"""Faol rejalarni Moodle kutadigan ko'rinishga yoyadi (har guruhga alohida)."""
	filtr = {"academic_year": academic_year, "holat": "Faol"}
	if fan:
		filtr["fan"] = fan

	out = []
	for reja in frappe.get_all("Oquv Reja", filters=filtr, pluck="name"):
		doc = frappe.get_doc("Oquv Reja", reja)
		guruhlar = [g.guruh for g in (doc.sinflar or [])]
		if not guruhlar:
			continue        # guruhsiz reja hech qayerga tushmaydi
		for q in doc.qatorlar:
			if not (q.mavzu or "").strip():
				continue
			for guruh in guruhlar:
				out.append({
					"subjectkey": doc.fan,
					"groupkey": guruh,
					"chorak": cint(q.chorak),
					"tartib": cint(q.tartib),
					"bolim": q.bolim or "",
					"mavzu": q.mavzu,
					"soat": max(cint(q.soat), 1),
					"darsturi": q.dars_turi or "",
					"frappereja": doc.name,
				})
	return out


def push(academic_year: str | None = None, fan: str | None = None,
         trigger: str = "Qo'lda") -> dict:
	"""Rejalarni Moodle'ga yuboradi va u yerda darslarga biriktiradi."""
	s = _settings()
	if not cint(s.enabled):
		return {"holat": "o'chirilgan"}

	from target_zenit.oquv_reja import _joriy_yil

	yil = academic_year or _joriy_yil()
	if not yil:
		return {"holat": "xato", "xato": "Joriy o'quv yili aniqlanmadi"}

	qatorlar = _qatorlar(yil, fan)
	if not qatorlar:
		return {"holat": "yuborilmadi", "sabab": "Faol reja yo'q", "oquv_yili": yil}

	jami = {"ochirildi": 0, "qoshildi": 0, "biriktirildi": 0,
	        "bosh_slot": 0, "sigmagan": 0}
	ogohlantirish: list[str] = []
	xato = None

	for i in range(0, len(qatorlar), BATCH):
		bolak = qatorlar[i:i + BATCH]
		# Biriktirish FAQAT oxirgi bo'lakdan keyin: har bo'lakda qayta
		# hisoblash bekorga vaqt oladi va oraliq holatda noto'g'ri chiqadi
		oxirgimi = (i + BATCH) >= len(qatorlar)
		try:
			res = _call("local_targetzenit_push_mavzular", {
				"academicyear": yil, "rows": bolak,
				"biriktir": 1 if oxirgimi else 0,
			})
		except MoodleError as e:
			xato = str(e)
			frappe.log_error(xato, "Moodle mavzu push")
			break
		if isinstance(res, dict):
			for k in jami:
				jami[k] += cint(res.get(k))
			ogohlantirish += res.get("ogohlantirish") or []

	natija = {"holat": "xato" if xato else "tayyor", "oquv_yili": yil,
	          "yuborildi": len(qatorlar), **jami,
	          "ogohlantirish": ogohlantirish[:20], "trigger": trigger}
	if xato:
		natija["xato"] = xato[:500]
	return natija


def on_reja_update(doc, method=None):
	"""Reja saqlanganda — faqat o'sha fan Moodle'da yangilanadi.

	Navbatda bajariladi: Moodle sekin javob bersa zam direktorning
	saqlash amali shu sababli to'xtab qolmasligi kerak."""
	if doc.holat != "Faol" or not cint(_settings().enabled):
		return
	frappe.enqueue(
		"target_zenit.integrations.moodle_mavzu.push",
		queue="short", timeout=600, enqueue_after_commit=True,
		job_name=f"moodle_mavzu:{doc.name}",
		academic_year=doc.academic_year, fan=doc.fan, trigger="Reja saqlandi",
	)


def daily_sync():
	"""Kunlik zaxira: jadval o'zgargan bo'lsa biriktirish qayta hisoblanadi."""
	if not cint(_settings().enabled):
		return
	push(trigger="Jadval")


@frappe.whitelist()
def push_now(academic_year: str | None = None, fan: str | None = None) -> dict:
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))
	return push(academic_year=academic_year, fan=fan, trigger="Qo'lda")


@frappe.whitelist()
def preview(limit: int = 10) -> dict:
	"""Nima yuborilishini so'rovsiz ko'rish."""
	frappe.only_for(("System Manager", "Zavuch", "Academics User", "Education Manager"))

	from target_zenit.oquv_reja import _joriy_yil

	yil = _joriy_yil()
	qatorlar = _qatorlar(yil) if yil else []
	juftlar = {(q["subjectkey"], q["groupkey"]) for q in qatorlar}
	return {
		"oquv_yili": yil,
		"qatorlar": len(qatorlar),
		"juftlar": len(juftlar),
		"namuna": qatorlar[:cint(limit)],
	}
