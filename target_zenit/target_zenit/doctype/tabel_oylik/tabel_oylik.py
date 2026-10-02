# Copyright (c) 2026, Target Zenit
"""Tabel Oylik — xodimning BITTA OY uchun belgilangan oylik ish haqi.

Oylik tabelda ish haqi har oyda har xil bo'lishi mumkin; SSA'ning
"shu sanadan boshlab amal qiladi" modelida bir oyni o'zgartirish keyingi
(o'z yozuvi yo'q) oylarga ham ta'sir qilardi. Bu doctype qiymatni OYga
qotiradi — yozuvi bor oy boshqa oylardagi o'zgarishlardan ta'sirlanmaydi
(Tabel Ish Kuni bilan bir xil g'oya)."""

from frappe.model.document import Document


class TabelOylik(Document):
    pass
