# Copyright (c) 2026, Target Zenit
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from target_zenit.telefoniya import storage
from target_zenit.telefoniya.utils import format_phone, normalize_phone


class TestRaqamNormallash(FrappeTestCase):
	def test_ozbek_formatlari(self):
		"""Odamlar kiritadigan barcha ko'rinish bitta kanonik qiymatga tushishi kerak."""
		kutilgan = "998901234567"
		for xom in (
			"+998 90 123 45 67",
			"998901234567",
			"901234567",
			"0901234567",
			"+998(90)123-45-67",
			"90 123 45 67",
			"00998901234567",
			"8998901234567",
		):
			self.assertEqual(normalize_phone(xom), kutilgan, f"xato: {xom}")

	def test_shahar_raqami(self):
		self.assertEqual(normalize_phone("712001122"), "998712001122")
		# 7 raqamli qisqa raqamga hudud kodi qo'shiladi
		self.assertEqual(normalize_phone("2001122"), "998712001122")
		self.assertEqual(normalize_phone("2001122", hudud_kodi="62"), "998622001122")

	def test_chet_el_raqamiga_tegmaydi(self):
		"""Chet el raqamiga 998 qo'shib yuborish xato bo'lardi."""
		self.assertEqual(normalize_phone("+7 495 123 45 67"), "74951234567")

	def test_bosh_qiymatlar(self):
		for xom in ("", None, "yo'q", "---"):
			self.assertIsNone(normalize_phone(xom))

	def test_korsatish(self):
		self.assertEqual(format_phone("998901234567"), "+998 90 123 45 67")
		self.assertEqual(format_phone(None), "")


class TestYozuvSaqlash(FrappeTestCase):
	def test_yol_sana_boyicha_bolinadi(self):
		yol = storage.nisbiy_yol("1760087423.481", "2026-10-10 14:30:00")
		self.assertEqual(yol, "2026/10/10/1760087423.481.mp3")

	def test_papkadan_chiqib_ketishga_yol_yoq(self):
		"""`fayl_yoli` bazadan keladi — u bilan papkadan tashqariga chiqib
		bo'lmasligi kerak, aks holda istalgan fayl o'qib olinardi."""
		for yomon in ("../../../../etc/passwd", "../../site_config.json", "2026/../../../etc/hosts"):
			with self.assertRaises(frappe.ValidationError):
				storage.oqi(yomon)

	def test_yaroqsiz_id_rad_etiladi(self):
		"""ID jimgina tuzatilmaydi — rad etiladi. Aks holda ikki xil ID bitta
		fayl nomiga tushib, bir yozuv ikkinchisini o'chirib yuborardi."""
		for yomon in ("../../x", "a/b", "", None, ".yashirin", "a" * 200, "x..y"):
			with self.assertRaises(frappe.ValidationError, msg=f"rad etilmadi: {yomon!r}"):
				storage.nisbiy_yol(yomon, "2026-10-10 14:30:00")

	def test_haqiqiy_asterisk_idlari_qabul_qilinadi(self):
		for yaxshi in ("1760087423.481", "asterisk-1760087423.481", "ABC_123"):
			self.assertTrue(storage.nisbiy_yol(yaxshi, "2026-10-10 14:30:00").endswith(f"{yaxshi}.mp3"))

	def test_baza_papka_files_dan_tashqarida(self):
		"""Yozuvlar `files` ichida bo'lsa har bir backup'ga tushib ketardi."""
		baza = storage.baza_papka()
		self.assertNotIn(os.path.join("private", "files"), baza)
		self.assertNotIn(os.path.join("public", "files"), baza)
