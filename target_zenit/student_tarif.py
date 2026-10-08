# Copyright (c) 2026, Target Zenit
# O'quvchi shartnoma summalarini avtomatik hisoblash:
#
#   chegirma summasi = tarif x chegirma foizi / 100
#   yakuniy summa    = tarif - chegirma
#   oylik to'lov     = yakuniy / 10   (o'quv yili sentabr-iyun, 10 oy)
#
# Foiz — kirituvchi uchun qulaylik, lekin HAQIQAT MANBAI chegirma SUMMASI:
# eski shartnomalarda chegirma yumaloq foiz emas (masalan 19 000 000 / 79 000 000 =
# 24.0506%) — foizdan qayta hisoblasak so'mlarda og'ish chiqadi. Shuning uchun:
#   - foiz o'zgarsa  -> summa foizdan hisoblanadi
#   - summa qo'lda kiritilsa -> foiz summadan ko'rsatiladi (ma'lumot uchun)
from __future__ import annotations

import frappe
from frappe.utils import flt

OYLAR_SONI = 10


def hisobla(doc, method=None):
	"""Student validate hook — summalarni muvofiqlashtiradi.

	Ustuvorlik (aniq va bashorat qilinadigan bo'lishi uchun):
	  1) Chegirma SUMMASI qo'lda o'zgartirilgan bo'lsa -> foiz summadan ko'rsatiladi
	  2) Aks holda foiz > 0 bo'lsa -> summa foizdan hisoblanadi (tarif o'zgarsa ham)
	  3) Foiz 0 va summa o'zgarmagan bo'lsa -> summa saqlanadi, foiz ko'rsatiladi
	"""
	tarif = flt(doc.get("custom_tariff_amount"))
	if tarif <= 0:
		# Grant/investor farzandlari: tarif yo'q — hech narsa hisoblanmaydi
		return

	foiz = flt(doc.get("custom_discount_foiz"))
	chegirma = flt(doc.get("custom_discount_amount"))

	oldingi = doc.get_doc_before_save()
	summa_ozgardi = (
		oldingi is not None
		and abs(flt(oldingi.get("custom_discount_amount")) - chegirma) > 0.5
	)
	# Foiz yoki tarif o'zgarganidagina summani foizdan qayta hisoblaymiz.
	# Aks holda summa tegilmaydi — chunki foiz 4 xonagacha yumaloqlangan va
	# yumaloq bo'lmagan chegirmalarda (24.0506%) har saqlashda so'mlar siljirdi.
	foiz_ozgardi = oldingi is not None and abs(flt(oldingi.get("custom_discount_foiz")) - foiz) > 0.00005
	tarif_ozgardi = oldingi is not None and abs(flt(oldingi.get("custom_tariff_amount")) - tarif) > 0.5
	yangi_yozuv = oldingi is None

	if summa_ozgardi or (foiz <= 0 and chegirma > 0):
		foiz = chegirma / tarif * 100.0
	elif foiz > 0 and (foiz_ozgardi or tarif_ozgardi or yangi_yozuv):
		chegirma = tarif * foiz / 100.0
	elif foiz <= 0:
		chegirma = 0.0

	chegirma = min(max(chegirma, 0), tarif)  # 0 dan tarifgacha
	yakuniy = tarif - chegirma

	doc.custom_discount_foiz = round(foiz, 4)
	doc.custom_discount_amount = round(chegirma)
	doc.custom_final_amount = round(yakuniy)
	doc.custom_monthly_payment = round(yakuniy / OYLAR_SONI)


def backfill_foiz(dry_run: int = 1):
	"""Mavjud shartnomalarda chegirma foizini to'ldirish (bir martalik, idempotent)."""
	rows = frappe.get_all(
		"Student",
		filters={"custom_tariff_amount": [">", 0]},
		fields=["name", "custom_tariff_amount", "custom_discount_amount", "custom_discount_foiz"],
		limit_page_length=0,
	)
	n = 0
	for r in rows:
		foiz = round(flt(r.custom_discount_amount) / flt(r.custom_tariff_amount) * 100, 4)
		if abs(flt(r.custom_discount_foiz) - foiz) < 0.0001:
			continue
		n += 1
		if not dry_run:
			frappe.db.set_value("Student", r.name, "custom_discount_foiz", foiz, update_modified=False)
	if not dry_run:
		frappe.db.commit()
	print(f"{'[sinov] ' if dry_run else ''}Foiz to'ldirildi: {n} / {len(rows)} o'quvchi")
	return n


STUDENT_FIELDS = {
	"Student": [
		{
			"fieldname": "custom_discount_foiz",
			"label": "Chegirma foizi (%)",
			"fieldtype": "Percent",
			"insert_after": "custom_tariff_amount",
			"description": "Foizni yozsangiz chegirma summasi, yakuniy summa va oylik to'lov o'zi hisoblanadi",
			"precision": "4",
		},
	]
}


def setup_fields():
	"""custom_discount_foiz maydoni + hisoblanadigan maydonlarni read-only qilish."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	create_custom_fields(STUDENT_FIELDS, update=True)

	# Yakuniy summa va oylik to'lov — avtomatik hisoblanadi, qo'lda yozilmaydi
	for fieldname, label in (
		("custom_final_amount", "Yakuniy summa (avtomatik: tarif − chegirma)"),
		("custom_monthly_payment", f"Oylik to'lov (avtomatik: yakuniy / {OYLAR_SONI})"),
	):
		make_property_setter("Student", fieldname, "read_only", 1, "Check", validate_fields_for_doctype=False)
		make_property_setter("Student", fieldname, "description", label, "Text", validate_fields_for_doctype=False)
	print("Student tarif maydonlari: OK")


def after_migrate():
	try:
		setup_fields()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "student_tarif setup")
