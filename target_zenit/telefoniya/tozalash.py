# Copyright (c) 2026, Target Zenit
"""Takrorlangan qo'ng'iroq hujjatlarini topish va tozalash.

NEGA KERAK: 2026-11-11 gacha bitta ovoz yozuvi CRM'da bir necha marta hujjat
ochardi. Sababi ikki tomonlama edi:
  * telefondagi ilova MIUI o'sib turgan faylni bir necha marta skaner qilib,
    har safar BOSHQA `client_call_id` bilan yangi qator yaratardi;
  * server esa takrorlanishni faqat `uniqueid` bo'yicha tekshirardi, mazmun
    bo'yicha emas.
Ikkisi ham tuzatildi (`api.ingest_call` endi `fayl_hash` bo'yicha ham tekshiradi,
ilova esa bitta faylga bitta qator yuritadi). Bu modul esa ALLAQACHON yaratilgan
ortiqcha hujjatlarni yig'ishtiradi.

Ishlatish (oldin DOIM quruq rejimda):
    bench --site <sayt> execute target_zenit.telefoniya.tozalash.takrorlarni_tozala
    bench --site <sayt> execute target_zenit.telefoniya.tozalash.takrorlarni_tozala \
        --kwargs "{'dry_run': 0}"
"""

import collections

import frappe

from target_zenit.telefoniya import storage

DOCTYPE = "Telefon Qongirogi"


def takrorlarni_tozala(dry_run=1, limit=5000):
	"""Bir xil `fayl_hash` li hujjatlardan bittasini qoldirib, qolganini o'chiradi.

	`dry_run` (standart) — hech narsa o'chirilmaydi, faqat hisobot chiqadi.

	Qaysi biri QOLADI: eng "to'la" hujjat — transkripti, AI xulosasi, izohi,
	o'quvchi bog'lanishi borlari ustun. Teng bo'lsa eng ESKISI qoladi (uning
	tarixi va havolalari ko'proq).

	Murojaat hujjatiga bog'langan qo'ng'iroq HECH QACHON o'chirilmaydi — havola
	uzilib qolmasligi kerak; u hisobotda alohida ko'rsatiladi.
	"""
	dry_run = int(dry_run)

	qatorlar = frappe.get_all(
		DOCTYPE,
		filters={"fayl_hash": ["is", "set"]},
		fields=[
			"name", "fayl_hash", "fayl_yoli", "boshlandi", "tashqi_raqam",
			"transkript", "ai_xulosa", "izoh", "student", "creation",
		],
		limit_page_length=limit,
		order_by="creation asc",
	)

	guruhlar = collections.defaultdict(list)
	for q in qatorlar:
		guruhlar[q.fayl_hash].append(q)
	takror = {h: g for h, g in guruhlar.items() if len(g) > 1}

	ochirildi = bogliq = 0
	hisobot = []

	for h, guruh in takror.items():
		guruh.sort(key=lambda q: (-_tolalik(q), q.creation))
		qoladi, ortiqcha = guruh[0], guruh[1:]

		for q in ortiqcha:
			if frappe.db.exists("Murojaat", {"telefon_qongirogi": q.name}):
				bogliq += 1
				hisobot.append(f"  SAQLANDI (murojaatga bog'langan): {q.name}")
				continue

			hisobot.append(
				f"  {'[quruq] ' if dry_run else ''}o'chiriladi {q.name} "
				f"-> qoladi {qoladi.name}  ({q.tashqi_raqam} {q.boshlandi})"
			)
			if dry_run:
				ochirildi += 1
				continue

			# TARTIB MUHIM: avval hujjat, keyin fayl. Fayl tizimi tranzaksiyaga
			# kirmaydi — faylni oldin o'chirsak va tranzaksiya qaytsa (xato yoki
			# rollback), hujjat qoladi-yu yozuvi yo'qoladi.
			frappe.delete_doc(DOCTYPE, q.name, ignore_permissions=True, force=True)

			# Ovoz fayli: faqat QOLADIGAN hujjatnikidan boshqa bo'lsa o'chiriladi.
			# Har hujjat o'z nusxasini saqlaydi (yo'l `uniqueid` dan quriladi),
			# lekin ehtiyot shart tekshiramiz — qolgan hujjat yozuvsiz qolmasin.
			if q.fayl_yoli and q.fayl_yoli != qoladi.fayl_yoli:
				try:
					storage.ochir(q.fayl_yoli)
				except Exception as e:
					frappe.logger("telefoniya").warning(f"{q.fayl_yoli} o'chmadi: {e}")

			ochirildi += 1

	if not dry_run and ochirildi:
		frappe.db.commit()

	xulosa = (
		f"Jami qo'ng'iroq: {len(qatorlar)} | noyob yozuv: {len(guruhlar)} | "
		f"takrorlangan yozuv: {len(takror)} ta\n"
		f"{'O‘CHIRILADI (quruq rejim)' if dry_run else 'O‘CHIRILDI'}: {ochirildi} ta hujjat | "
		f"murojaatga bog'langani uchun saqlandi: {bogliq} ta"
	)
	print(xulosa)
	for satr in hisobot[:50]:
		print(satr)
	if len(hisobot) > 50:
		print(f"  … yana {len(hisobot) - 50} ta satr")
	if dry_run:
		print("\nHech narsa o'chirilmadi. Rostdan o'chirish uchun: --kwargs \"{'dry_run': 0}\"")
	return xulosa


def _tolalik(q) -> int:
	"""Hujjatning "to'laligi" — qaysi nusxani saqlashni hal qiladi."""
	return sum(
		1
		for maydon in ("transkript", "ai_xulosa", "izoh", "student")
		if (q.get(maydon) or "").strip()
	)
