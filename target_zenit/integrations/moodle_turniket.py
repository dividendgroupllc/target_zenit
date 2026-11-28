# Copyright (c) 2026, Target Zenit
# TURNIKET KIRDI-CHIQDI -> MOODLE BILDIRISHNOMASI (real vaqt).
#
# OQIM: Hikvision terminal -> turniket app webhook (parse, dublikat, odamga
# bog'lash) -> Turniket Checkin after_insert hook (shu modul) -> navbat ->
# Moodle `local_targetzenit_push_checkin` -> egasiga (xodim yoki o'quvchi)
# standart Moodle bildirishnomasi: «Siz 08:52 da maktabga kirdingiz».
#
# QARORLAR (2026-11-28, foydalanuvchi bilan kelishilgan):
#   * Frappe BOSH TIZIM bo'lib qoladi — Moodle tayyor faktni oladi, hech
#     narsa hisoblamaydi. Har hodisa BIR MARTA uzatiladi, keyin Moodle
#     ichida lokal yashaydi (plagin jadvali + bildirishnoma).
#   * Dublikat eshigi MOODLE tomonida (checkinid unique) — shuning uchun
#     qayta yuborish (retry) xavfsiz: xabar ikki marta ketmaydi.
#   * `moodle_xabar` belgisi Turniket Checkin'da: 0 bo'lib qolganlarni
#     (Moodle o'chiq, navbat uzilgan) 10 daqiqalik zaxira cron qayta oladi.
#   * Vaqt epoch ko'rinishida ANIQ Asia/Tashkent bilan hisoblanadi
#     (O'zbekiston vaqti qoidasi) — server TZ'iga tayanib bo'lmaydi.
from __future__ import annotations

from zoneinfo import ZoneInfo

import frappe
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from target_zenit.integrations.moodle import _call, _settings

TZ = ZoneInfo("Asia/Tashkent")

# Frappe'dagi Select qiymati -> plagin kutadigan kichik harfli yo'nalish.
# Ro'yxatda yo'q (bo'sh) qiymat -> "otdi": xabar baribir ketadi, matni
# umumiyroq bo'ladi ("turniketdan o'tdingiz").
YONALISH = {"Kirdi": "kirdi", "Chiqdi": "chiqdi"}


def _yoqilganmi() -> bool:
	s = _settings()
	return bool(cint(s.enabled) and cint(s.get("sync_turniket")))


def _epoch(dt) -> int:
	"""Naive lokal datetime -> Unix epoch, qat'iy Asia/Tashkent bilan."""
	return int(get_datetime(dt).replace(tzinfo=TZ).timestamp())


def on_checkin_insert(doc, method=None):
	"""Yangi turniket hodisasi -> DARHOL Moodle'ga (navbatda).

	Navbatda bajariladi: Moodle javob bermasa yoki sekin bo'lsa, terminal
	webhook'i shu sababli qotib qolmasligi kerak. Odamga bog'lanmagan
	(noma'lum FPID) hodisa yuborilmaydi — Moodle'da egasi yo'q."""
	if not (doc.get("student") or doc.get("employee")):
		return
	if not _yoqilganmi():
		return
	frappe.enqueue(
		"target_zenit.integrations.moodle_turniket.push",
		queue="short", timeout=120, enqueue_after_commit=True,
		job_name=f"moodle_turniket:{doc.name}",
		nomlar=[doc.name],
	)


def push(nomlar):
	"""Berilgan Turniket Checkin'larni Moodle'ga uzatadi.

	Muvaffaqiyatda `moodle_xabar`=1 belgilanadi. Xato bo'lsa — belgisiz
	qoladi va zaxira cron keyinroq qayta uradi (Moodle tomonda checkinid
	unique, dublikat xabar ketmaydi)."""
	rows = frappe.get_all(
		"Turniket Checkin",
		filters={"name": ["in", list(nomlar)]},
		fields=["name", "student", "employee", "direction", "event_time", "terminal"],
		limit_page_length=0, ignore_permissions=True,
	)
	events, yuborilgan = [], []
	for r in rows:
		# Unikal ID qoidasi: bog'lanish faqat o'zgarmas docname bilan —
		# Employee.name / Student.name = Moodle user.idnumber
		idnumber = r.employee or r.student
		if not idnumber:
			continue
		events.append({
			"checkinid": r.name,
			"useridnumber": idnumber,
			"yonalish": YONALISH.get((r.direction or "").strip(), "otdi"),
			"vaqt": _epoch(r.event_time),
			"terminal": r.terminal or "",
		})
		yuborilgan.append(r.name)
	if not events:
		return
	natija = _call("local_targetzenit_push_checkin", {"events": events})
	for nom in yuborilgan:
		frappe.db.set_value("Turniket Checkin", nom, "moodle_xabar", 1,
							update_modified=False)
	return natija


def qolganlarni_yubor():
	"""ZAXIRA (10 daqiqalik cron): yuborilmay qolganlarni to'plab uzatish.

	Asosiy yo'l — hodisa kelgan zahoti (on_checkin_insert). Bu cron Moodle
	o'chiq turgan, worker uzilgan yoki sozlama keyin yoqilgan paytdagi
	hodisalarni oladi. Oyna 48 soat: undan eskisi endi «real vaqt xabari»
	emas, odamni yarim kechada eski push bilan bezovta qilmaymiz."""
	if not _yoqilganmi():
		return
	nomlar = []
	for r in frappe.get_all(
		"Turniket Checkin",
		filters={"moodle_xabar": 0,
				 "creation": [">=", add_to_date(now_datetime(), hours=-48)]},
		fields=["name", "student", "employee"],
		order_by="creation asc", limit_page_length=0, ignore_permissions=True,
	):
		if r.student or r.employee:
			nomlar.append(r.name)
	# 200 talik bo'laklar: bitta so'rov haddan katta bo'lmasin
	for i in range(0, len(nomlar), 200):
		push(nomlar[i:i + 200])


@frappe.whitelist()
def holat():
	"""Tezkor tekshiruv: nechta hodisa yuborilgan/kutmoqda (konsol uchun)."""
	frappe.only_for("System Manager")
	chegara = add_to_date(now_datetime(), hours=-48)
	return {
		"yoqilgan": _yoqilganmi(),
		"yuborilgan_48h": frappe.db.count("Turniket Checkin", {
			"moodle_xabar": 1, "creation": [">=", chegara]}),
		"kutmoqda_48h": frappe.db.count("Turniket Checkin", {
			"moodle_xabar": 0, "creation": [">=", chegara]}),
	}
