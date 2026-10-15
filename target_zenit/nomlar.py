# Copyright (c) 2026, Target Zenit
"""Ismni HAR DOIM manba hujjatdan o'qish — nusxadan emas.

Muammo: ko'p doctype'da ism NUSXA bo'lib yotadi (`fetch_from` surati yoki
qo'lda yozilgan Data maydon): `Jadval Yozuvi.oqituvchi_nomi`,
`Tabel Oylik.xodim_ismi`, `Instructor.instructor_name`, `Qarz Ishi.student_name`
va h.k. Xodimning ismi tuzatilsa (masalan pasport bo'yicha to'g'rilansa)
nusxalar eskicha qolib ketadi va sahifalarda bir odam ikki xil ism bilan
ko'rinadi. `ism_sync.py` nusxalarni grafik bo'yicha yangilaydi, lekin
SAHIFALAR nusxaga umuman qaramasligi kerak: ular ID bo'yicha jonli o'qiydi.

Qoida: sahifa ID (employee / instructor) ni saqlaydi, ismni esa shu yerdagi
funksiyalar beradi. Nusxalar hisobot va tarix uchun qoladi.
"""

from __future__ import annotations

import frappe


def xodim_nomlari(ids) -> dict:
	"""Employee ID -> jonli `employee_name`."""
	ids = {x for x in (ids or []) if x}
	if not ids:
		return {}
	return {
		e.name: e.employee_name
		for e in frappe.get_all(
			"Employee",
			filters={"name": ["in", list(ids)]},
			fields=["name", "employee_name"],
			limit_page_length=0,
			ignore_permissions=True,
		)
	}


def xodim_nomi(employee: str | None) -> str | None:
	return xodim_nomlari([employee]).get(employee) if employee else None


def oqituvchi_nomlari(ids) -> dict:
	"""Instructor ID -> jonli ism.

	Instructor hujjati Employee'ga bog'langan bo'lsa — ism EMPLOYEE'dan olinadi
	(kadrlar hujjati asosiy manba). Bog'lanmagan bo'lsa (tashqi o'qituvchi,
	vakant) `instructor_name` ishlatiladi, u bo'lmasa docname.
	"""
	ids = {x for x in (ids or []) if x}
	if not ids:
		return {}
	qatorlar = frappe.get_all(
		"Instructor",
		filters={"name": ["in", list(ids)]},
		fields=["name", "instructor_name", "employee"],
		limit_page_length=0,
		ignore_permissions=True,
	)
	emp_map = xodim_nomlari([r.employee for r in qatorlar])
	return {
		r.name: (emp_map.get(r.employee) or r.instructor_name or r.name) for r in qatorlar
	}


def oqituvchi_nomi(instructor: str | None) -> str | None:
	return oqituvchi_nomlari([instructor]).get(instructor) if instructor else None


def oqituvchi_toldir(qatorlar, id_maydon: str = "oqituvchi", nom_maydon: str = "oqituvchi_nomi"):
	"""Qatorlar ro'yxatidagi o'qituvchi ismini jonli qiymat bilan almashtiradi.

	`qatorlar` — dict yoki frappe._dict ro'yxati (bitta so'rovda hammasi).
	Ism topilmasa qatordagi eski qiymat buzilmaydi (tashqi/vakant o'qituvchi).
	"""
	nomlar = oqituvchi_nomlari([r.get(id_maydon) for r in qatorlar])
	for r in qatorlar:
		jonli = nomlar.get(r.get(id_maydon))
		if jonli:
			r[nom_maydon] = jonli
	return qatorlar
