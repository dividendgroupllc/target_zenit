# Copyright (c) 2026, Target Zenit
# Frappe -> Moodle: oylik tabel ma'lumotini uzatish.
#
# MAQSAD: o'qituvchi o'z oyligini Moodle'da ko'rsin — qancha kun kelgan,
# qancha oylik oladi, qancha bonus. Buxgalteriyaga kirmasdan, Moodle'dan.
#
# TAMOYIL: oylikni FAQAT Frappe hisoblaydi. Moodle'ga tayyor sonlar boradi va
# u hech narsani qayta hisoblamaydi — shu sababli ikki tizim orasida farq
# paydo bo'lmaydi. Yo'nalish bir tomonlama: Frappe yuboradi, Moodle qabul
# qiladi (Moodle'da Frappe kaliti saqlanmaydi).
#
# BOG'LANISH: `Employee.name` -> Moodle `user.idnumber`. Ism yoki email bilan
# hech qachon emas — ism o'zgaradi, unikal ID o'zgarmaydi.
#
# NIMA YUBORILADI (har xodim uchun bitta oy):
#   shartnoma oyligi, norma ish kuni, kunlik narx, ishlagan kun/soat,
#   kelgan kunlar, bonus/jarima, nalog, pitaniya, hisoblangan, qo'lga
#   + kunma-kun ro'yxat: koeffitsient va turniketdagi kirish/chiqish vaqti

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date

import frappe
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from target_zenit.integrations.moodle import _call, _settings
from target_zenit.target_zenit.api.oylik_tabel import _tabel_hisobla, _valyuta
from target_zenit.target_zenit.page.investor_dashboard.investor_dashboard import (
	personal_months,
)

# Bitta so'rovda nechta xodim yuboriladi.
# SABAB: Moodle REST so'rovni forma maydonlari ko'rinishida oladi — har xodim
# ~16 maydonga yoyiladi. PHP `max_input_vars` = 5000. 150 x 16 = 2400 —
# zaxirasi bilan xavfsiz.
OYLIK_BATCH = 150


def _turniket_vaqtlari(emp_ids, oy_boshi, oy_oxiri):
	"""Har xodim-kun uchun eng erta kirish va eng kech chiqish vaqti.

	Manba — Face ID turniketidan keladigan `Terminal Checkin`.

	BOG'LANISH IKKI YO'L BILAN: `Terminal Checkin.employee` to'ldirilgan bo'lsa
	o'sha, aks holda `person_id` -> `Employee.attendance_device_id`. Sabab:
	webhook odamni tanimasa `employee` bo'sh qoladi (hozir aksariyat yozuv
	shunday), lekin qurilma ID'si moslashtirilgandan keyin eski yozuvlar ham
	bog'lanishi kerak.

	Agar bog'lanish hali qilinmagan bo'lsa — bo'sh lug'at qaytadi va sahifada
	vaqt ustunlari "—" bo'lib turadi. Kelgan/kelmagan haqidagi RASMIY ma'lumot
	baribir tabeldagi koeffitsient (zam direktor qo'yadi), turniket vaqti esa
	qo'shimcha tafsilot.
	"""
	if not emp_ids:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT e.name AS employee,
		       DATE(tc.event_time) AS sana,
		       MIN(CASE WHEN tc.direction = 'Kirdi'  THEN tc.event_time END) AS kirish,
		       MAX(CASE WHEN tc.direction = 'Chiqdi' THEN tc.event_time END) AS chiqish,
		       MIN(tc.event_time) AS birinchi,
		       MAX(tc.event_time) AS oxirgi
		FROM `tabTerminal Checkin` tc
		INNER JOIN `tabEmployee` e
		        ON e.name = tc.employee
		        OR (IFNULL(tc.employee, '') = ''
		            AND IFNULL(e.attendance_device_id, '') != ''
		            AND e.attendance_device_id = tc.person_id)
		WHERE e.name IN %(emps)s
		  AND DATE(tc.event_time) BETWEEN %(boshi)s AND %(oxiri)s
		GROUP BY e.name, DATE(tc.event_time)
		""",
		{"emps": emp_ids, "boshi": oy_boshi, "oxiri": oy_oxiri},
		as_dict=True,
	)

	natija = {}
	for r in rows:
		# Turniket yo'nalishni bermagan bo'lsa (direction bo'sh) — kunning
		# birinchi va oxirgi o'tishini olamiz, bu baribir foydali.
		kirish = r.kirish or r.birinchi
		chiqish = r.chiqish or r.oxirgi
		if chiqish and kirish and chiqish == kirish:
			chiqish = None          # bitta o'tish bo'lsa "chiqish" deb ko'rsatmaymiz
		natija[(r.employee, getdate(r.sana).day)] = (
			kirish.strftime("%H:%M") if kirish else "",
			chiqish.strftime("%H:%M") if chiqish else "",
		)
	return natija


def _qatorlar(natija, vaqtlar):
	"""`_tabel_hisobla` natijasini Moodle kutgan ko'rinishga aylantiradi."""
	chiqish = []
	for q in natija["qatorlar"]:
		kunlar = []
		for i, kd in enumerate(natija["kunlar"]):
			kun = kd["kun"]
			katak = q["kunlar"][i] if i < len(q["kunlar"]) else {}
			if katak.get("koef") is None:
				continue            # kirmagan/ketgan kunlar — ko'rsatilmaydi
			kirish, chiq = vaqtlar.get((q["xodim"], kun), ("", ""))
			kunlar.append({
				"kun": kun,
				"koef": flt(katak.get("koef")),
				"kirish": kirish,
				"chiqish": chiq,
			})

		chiqish.append({
			"useridnumber": q["xodim"],
			"employeename": q["ismi"] or "",
			"lavozim": q["lavozim"] or "",
			"tolovturi": q["tolov_turi"],
			"normakun": cint(q["ish_kuni"]),
			"kelgankun": cint(q["kelgan_kun"]),
			"ishlagan": flt(q["koef_yigindi"]),
			"kunliknarx": flt(q["kunlik_narx"]),
			"oylik": flt(q["oylik"]["summa"]),
			"bonus": flt(q["bonus"]),
			"nalog": flt(q["nalog"]),
			"pitaniya": flt(q["pitaniya"]),
			"hisob": flt(q["hisob"]),
			"jami": flt(q["jami"]),
			"kunlarjson": json.dumps(kunlar, ensure_ascii=False),
		})
	return chiqish



# Hisob-kitob qatorlari bitta so'rovda nechta ketadi.
# Har qator ~8 maydon, PHP `max_input_vars` = 5000 -> 400 x 8 = 3200 xavfsiz.
HISOB_BATCH = 400


def _hisob_qatorlari(emp_ids):
	"""Har xodim uchun oy kesimida: nachisleniya / to'langan / qoldiq.

	MANBA BITTA: `investor_dashboard.personal_months` — investor paneli ham
	shu funksiyadan oziqlanadi. Mantiq bu yerda QAYTA YOZILMAYDI, aks holda
	o'qituvchi ko'rgan son direktor ko'rgan sondan farq qilib qolardi.

	Sekinroq (xodim boshiga 2 so'rov), lekin bu kunlik fon ishi — to'g'rilik
	tezlikdan muhimroq.
	"""
	qatorlar = []
	for emp in emp_ids:
		try:
			natija = personal_months("Employee", emp)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Moodle hisob-kitob: {emp}")
			continue
		for m in natija.get("months") or []:
			oy = str(m.get("oy") or "")
			if len(oy) != 7 or oy[4] != "-":
				continue              # "—" kabi noma'lum oy — yuborilmaydi
			qatorlar.append({
				"useridnumber": emp,
				"oy": oy,
				"valyuta": m.get("currency") or "UZS",
				# Yaxlitlash: hisobdan 10^-9 kabi qoldiqlar chiqadi, ular
				# "to'lanmagan" bo'lib ko'rinib qolmasligi kerak.
				"oylik": round(flt(m.get("oylik")), 2),
				"nach": round(flt(m.get("nach")), 2),
				"paid": round(flt(m.get("paid")), 2),
				"advance": round(flt(m.get("advance")), 2),
				"debt": round(flt(m.get("debt")), 2),
			})
	return qatorlar


def _hisobni_yubor(emp_ids, lines):
	"""Hisob-kitobni Moodle'ga uzatadi. Natija: qisqa xulosa."""
	qatorlar = _hisob_qatorlari(emp_ids)
	if not qatorlar:
		lines.append("Hisob-kitob: yuboriladigan qator yo'q.")
		return {"yangi": 0, "yangilandi": 0, "ochirildi": 0, "qator": 0}

	# Yurish belgisi: shu sinxronda yozilgan qatorlarni ajratish uchun.
	# Vaqt sifatida emas, shunchaki tenglik uchun ishlatiladi — Frappe va
	# Moodle soatlari farq qilishi mumkin.
	runid = int(now_datetime().timestamp())

	yangi = yangilandi = 0
	bolaklar = [
		qatorlar[i : i + HISOB_BATCH]
		for i in range(0, len(qatorlar), HISOB_BATCH)
	]
	oxirgi = {}
	for n, bolak in enumerate(bolaklar):
		sorov = {"runid": runid, "rows": bolak}
		# Eskirgan qatorlarni o'chirish OXIRGI bo'lak bilan — aks holda hali
		# yuborilmagan bo'lakning qatorlari o'chib ketardi.
		if n == len(bolaklar) - 1:
			sorov["keep"] = emp_ids
		oxirgi = _call("local_targetzenit_push_settlement", sorov)
		yangi += cint(oxirgi.get("yangi"))
		yangilandi += cint(oxirgi.get("yangilandi"))

	lines.append(
		f"Hisob-kitob: {len(qatorlar)} qator ({len(bolaklar)} bo'lak) | "
		f"yangi {yangi}, yangilandi {yangilandi}, "
		f"eskirgani o'chirildi {cint(oxirgi.get('ochirildi'))}"
	)
	return {
		"yangi": yangi,
		"yangilandi": yangilandi,
		"ochirildi": cint(oxirgi.get("ochirildi")),
		"qator": len(qatorlar),
	}

def sync(yil=None, oy=None, trigger="Qo'lda"):
	"""Bitta oyni Moodle'ga uzatadi. Yil/oy berilmasa — joriy oy.

	Qaytaradi: `Moodle Sync Log` nomi (jadval/kurs sinxronlari bilan bir xil).
	"""
	s = _settings()
	if not s.enabled:
		frappe.throw("Moodle Settings: integratsiya yoqilmagan.")

	bugun = getdate(nowdate())
	yil = cint(yil) or bugun.year
	oy = cint(oy) or bugun.month

	log = frappe.get_doc({
		"doctype": "Moodle Sync Log",
		"sync_type": "Oylik",
		"trigger_type": trigger,
		"status": "Ishlayapti",
		"started": now_datetime(),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

	lines = []
	try:
		natija = _tabel_hisobla(yil, oy, hamma_kunlar=False)
		holat = "Yopiq" if frappe.db.get_value(
			"Tabel Oyi", f"TAB-{yil}-{oy}", "holat") == "Yopiq" else "Ochiq"

		emp_ids = [q["xodim"] for q in natija["qatorlar"]]
		oy_oxiri = date(yil, oy, monthrange(yil, oy)[1])
		vaqtlar = _turniket_vaqtlari(emp_ids, date(yil, oy, 1), oy_oxiri)

		qatorlar = _qatorlar(natija, vaqtlar)
		lines.append(
			f"{yil}-{oy:02d} ({holat}): {len(qatorlar)} xodim | "
			f"turniket ma'lumoti bor kun: {len(vaqtlar)}"
		)
		if not qatorlar:
			lines.append("Tabelda xodim yo'q — yuborilmadi.")

		if s.dry_run:
			lines.append("TEST REJIMI: Moodle'ga yuborilmadi.")
			xulosa = {"yangi": 0, "yangilandi": 0, "ochirildi": 0, "boglanmagan": 0}
		elif not qatorlar:
			xulosa = {"yangi": 0, "yangilandi": 0, "ochirildi": 0, "boglanmagan": 0}
		else:
			valyuta = _valyuta()
			yangi = yangilandi = 0
			bolaklar = [
				qatorlar[i : i + OYLIK_BATCH]
				for i in range(0, len(qatorlar), OYLIK_BATCH)
			]
			oxirgi = {}
			for n, bolak in enumerate(bolaklar):
				sorov = {
					"yil": yil,
					"oy": oy,
					"holat": holat,
					"valyuta": valyuta,
					"rows": bolak,
				}
				# Ortiqcha qatorlarni o'chirish (tabeldan chiqib ketgan xodim)
				# OXIRGI bo'lak bilan birga ketadi — chaqiruv ichida avval
				# qatorlar yoziladi, keyin tozalash bo'ladi.
				#
				# NEGA ALOHIDA CHAQIRUV EMAS: `_flatten` bo'sh massivdan hech
				# qanday forma maydoni yasamaydi, ya'ni "rows": [] so'rovdan
				# butunlay yo'qoladi va Moodle "invalidparameter" deydi.
				# Shu yo'l bilan rows'siz chaqiruv umuman bo'lmaydi.
				#
				# NEGA BO'LAKLAR ICHIDA EMAS: tozalash 1-bo'lakda bo'lsa,
				# u hali yuborilmagan 2-bo'lak xodimlarini o'chirib tashlardi.
				if n == len(bolaklar) - 1:
					sorov["keep"] = [q["useridnumber"] for q in qatorlar]

				res = _call("local_targetzenit_push_payroll", sorov)
				yangi += cint(res.get("yangi"))
				yangilandi += cint(res.get("yangilandi"))
				oxirgi = res
				lines.append(
					f"  bo'lak {n + 1}/{len(bolaklar)}: {len(bolak)} xodim yuborildi"
				)

			xulosa = {
				"yangi": yangi,
				"yangilandi": yangilandi,
				"ochirildi": cint(oxirgi.get("ochirildi")),
				"boglanmagan": cint(oxirgi.get("boglanmagan")),
			}
			lines.append(
				f"Moodle qabul qildi: yangi {xulosa['yangi']}, "
				f"yangilandi {xulosa['yangilandi']}, "
				f"ortiqcha o'chirildi {xulosa['ochirildi']}"
			)
			# Oylar kesimida hisob-kitob — oylik qatorlaridan ALOHIDA:
			# u joriy oyga tegishli, bu esa xodimning BUTUN tarixi.
			xulosa["hisob"] = _hisobni_yubor(
				[q["useridnumber"] for q in qatorlar], lines)

			if xulosa["boglanmagan"]:
				lines.append(
					f"OGOHLANTIRISH: {xulosa['boglanmagan']} xodimning Moodle "
					"foydalanuvchisi topilmadi (idnumber mos kelmadi) — ular "
					"o'z oyligini Moodle'da ko'rmaydi."
				)

		log.db_set({
			"status": "Tugadi",
			"finished": now_datetime(),
			"created_count": xulosa["yangi"],
			"updated_count": xulosa["yangilandi"],
			"skipped_count": xulosa["ochirildi"],
			"error_count": xulosa["boglanmagan"],
			"details": "\n".join(lines)[:140000],
		})
		frappe.db.set_single_value(
			"Moodle Settings", "last_status",
			f"Oylik {yil}-{oy:02d}: {len(qatorlar)} xodim yuborildi",
		)
		frappe.db.commit()
		return log.name

	except Exception as e:
		frappe.db.rollback()
		lines.append(f"TO'XTADI: {e}")
		log.db_set({
			"status": "Xato",
			"finished": now_datetime(),
			"error_count": 1,
			"details": ("\n".join(lines) + "\n\n" + frappe.get_traceback())[:140000],
		})
		frappe.db.commit()
		frappe.log_error(title="Moodle oylik push", message=frappe.get_traceback())
		raise


def daily_sync():
	"""Scheduler: joriy oyni, oyning boshida esa o'tgan oyni ham yuboradi.

	NEGA o'tgan oy: oy yopilishi va tuzatishlar keyingi oyning birinchi
	kunlarida bo'ladi — xodim yopilgan oyning YAKUNIY sonini ko'rishi kerak.
	"""
	bugun = getdate(nowdate())
	try:
		sync(bugun.year, bugun.month, trigger="Avto (07:00)")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Moodle oylik sync (joriy oy)")

	if bugun.day <= 10:
		otgan_yil = bugun.year if bugun.month > 1 else bugun.year - 1
		otgan_oy = bugun.month - 1 if bugun.month > 1 else 12
		try:
			sync(otgan_yil, otgan_oy, trigger="Avto (07:00)")
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Moodle oylik sync (o'tgan oy)")


@frappe.whitelist()
def preview(yil=None, oy=None, limit=3):
	"""Moodle'ga TEGMASDAN nima yuborilishini ko'rsatadi (tekshirish uchun)."""
	frappe.only_for(("System Manager", "Administrator"))
	bugun = getdate(nowdate())
	yil = cint(yil) or bugun.year
	oy = cint(oy) or bugun.month

	natija = _tabel_hisobla(yil, oy, hamma_kunlar=False)
	emp_ids = [q["xodim"] for q in natija["qatorlar"]]
	oy_oxiri = date(yil, oy, monthrange(yil, oy)[1])
	vaqtlar = _turniket_vaqtlari(emp_ids, date(yil, oy, 1), oy_oxiri)
	qatorlar = _qatorlar(natija, vaqtlar)
	holat = bogllanish_holati(emp_ids)
	return {
		"yil": yil,
		"oy": oy,
		"xodim": len(qatorlar),
		"turniket_kun": len(vaqtlar),
		"moodleda_korinadi": holat["korinadi"],
		"korinmaydi": holat["korinmaydi"],
		"employeesiz_oqituvchi": holat["employeesiz_oqituvchi"],
		"namuna": qatorlar[: cint(limit)],
	}


def bogllanish_holati(emp_ids=None):
	"""Tabeldagi xodimlardan nechtasi Moodle'da o'z oyligini KO'RA OLADI.

	Moodle'ga faqat `Instructor` lar ko'chiriladi va ularning `idnumber` i —
	bog'langan `Employee.name`. Ya'ni xodim o'z oyligini Moodle'da ko'rishi
	uchun: (1) Instructor yozuvi bo'lishi, (2) o'sha Instructor'da `employee`
	to'ldirilgan bo'lishi kerak. Aks holda Moodle'da u umuman yo'q yoki
	`INSTR-<ism>` kaliti bilan turadi va oylik unga ulanmaydi.
	"""
	if emp_ids is None:
		emp_ids = [
			r.name for r in frappe.get_all(
				"Employee", filters={"custom_tabelda": 1}, fields=["name"],
				limit_page_length=0)
		]
	if not emp_ids:
		return {"korinadi": 0, "korinmaydi": 0, "employeesiz_oqituvchi": []}

	bogli = set(
		r.employee for r in frappe.get_all(
			"Instructor", filters={"employee": ["in", emp_ids]},
			fields=["employee"], limit_page_length=0)
	)
	employeesiz = [
		r.name for r in frappe.get_all(
			"Instructor", filters={"employee": ["in", ["", None]]},
			fields=["name"], limit_page_length=0)
	]
	return {
		"korinadi": len(bogli),
		"korinmaydi": len(emp_ids) - len(bogli),
		"employeesiz_oqituvchi": employeesiz,
	}


@frappe.whitelist()
def sync_now(yil=None, oy=None):
	"""Desk'dan qo'lda ishga tushirish."""
	frappe.only_for(("System Manager", "Administrator"))
	return sync(yil, oy, trigger="Qo'lda")
