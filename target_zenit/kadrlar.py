# Copyright (c) 2026, Target Zenit
"""Kadrlar (Employee) bo'yicha umumiy yordamchilar.

Qoida: sahifalardagi ro'yxatlar QOTIB YOZILMAYDI — manba hujjat/maydonning
o'zidan olinadi. Ish haqi kategoriyasi `Employee.custom_ish_haqi_kategoriya`
(Select) maydonida yuritiladi: kadrlar yangi kategoriya qo'shsa yoki nomini
o'zgartirsa, sahifalardagi filtr ham o'zi yangilanishi kerak.
"""

from __future__ import annotations

import frappe

KATEGORIYA_MAYDON = "custom_ish_haqi_kategoriya"


def ish_haqi_kategoriyalari(uchragan=None) -> list[str]:
	"""Ish haqi kategoriyalari — maydon tartibida.

	`uchragan` berilsa (ma'lumotda haqiqatda uchragan qiymatlar), natija shunga
	qisqartiriladi: filtr ro'yxatida bo'sh variantlar turmaydi. Ma'lumotda bor,
	lekin Select variantlari ichida YO'Q qiymatlar (eski yozuvlar, masalan
	"Xodimlar") oxiriga qo'shiladi — aks holda ular filtrlab bo'lmas edi.
	"""
	maydon = frappe.get_meta("Employee").get_field(KATEGORIYA_MAYDON)
	variantlar = [
		x.strip() for x in str(getattr(maydon, "options", "") or "").split("\n") if x.strip()
	]

	if uchragan is None:
		return variantlar

	bor = {str(x).strip() for x in uchragan if x and str(x).strip()}
	natija = [k for k in variantlar if k in bor]
	natija += sorted(bor - set(variantlar))
	return natija or variantlar
