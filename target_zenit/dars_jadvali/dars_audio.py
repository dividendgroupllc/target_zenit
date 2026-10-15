# Copyright (c) 2026, Target Zenit
# Dars audio yozuvi (AI tahlilidan OLDINGI bosqich — faqat yozib olish va biriktirish).
#
# Oqim:  brauzer MediaRecorder → har 15 soniyada bo'lak → serverga yuklanadi
#        (private/files/dars_audio_tmp/<sid>/000001.part) → «To'xtatish» bosilganda
#        bo'laklar tartib bilan BAYT-BA-BAYT birlashtiriladi (opus/webm oqimi uchun
#        bu to'g'ri — ffmpeg kerak emas) → File yaratiladi va `Dars Bajarilishi`
#        (sana + mavzu + o'qituvchi + guruh) ning `audio` maydoniga biriktiriladi.
#
# Nega bo'lak-bo'lak: brauzer yopilsa/uzilsa ham yozilgan qism serverda qoladi —
# keyin «Saqlash» bilan tugatiladi (audio_holat → audio_tugat).
from __future__ import annotations

import json
import os
import re
import shutil

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, nowdate

from target_zenit.oquv_reja import _menejermi, _mening_instructorim, dars_otdim

TMP_PAPKA = "dars_audio_tmp"
MAX_BOLAK = 8 * 1024 * 1024        # bitta bo'lak uchun shift (odatda ~50 KB)
MAX_SESSIYA = 120 * 1024 * 1024    # bitta dars yozuvi uchun shift (~24 kbps da 11 soat)
SID_RE = re.compile(r"^[A-Za-z0-9_.-]{4,180}$")

MIME_EXT = {
	"audio/webm": "webm",
	"audio/ogg": "ogg",
	"audio/mp4": "m4a",
	"audio/mpeg": "mp3",
	"audio/aac": "aac",
}


# ---------------------------------------------------------------- yordamchilar
def _ext(mime: str | None) -> str:
	asos = (mime or "").split(";")[0].strip().lower()
	return MIME_EXT.get(asos, "webm")


def _xavfsiz(s, uzunlik: int = 40) -> str:
	return re.sub(r"[^A-Za-z0-9_-]+", "-", str(s or "")).strip("-")[:uzunlik] or "x"


def _sid(jadval_yozuvi: str, sana: str) -> str:
	"""Sessiya id = (dars sloti + sana) — bitta darsga bitta yozuv papkasi."""
	return f"{_xavfsiz(jadval_yozuvi, 120)}__{_xavfsiz(sana, 12)}"


def _tmp_root() -> str:
	return frappe.get_site_path("private", "files", TMP_PAPKA)


def _sess_dir(sid: str) -> str:
	if not SID_RE.match(sid or ""):
		frappe.throw(_("Yozuv sessiyasi id'si xato."))
	return os.path.join(_tmp_root(), sid)


def _meta_oqi(sid: str) -> dict:
	yol = os.path.join(_sess_dir(sid), "meta.json")
	if not os.path.exists(yol):
		frappe.throw(_("Yozuv sessiyasi topilmadi (yoki allaqachon saqlangan)."))
	with open(yol, encoding="utf-8") as f:
		meta = json.load(f)
	# id'ni meta'dan qayta hisoblab tekshiramiz — papka nomi bilan o'ynab bo'lmasin
	if _sid(meta.get("jadval_yozuvi", ""), meta.get("sana", "")) != sid:
		frappe.throw(_("Yozuv sessiyasi mos kelmadi."))
	_ruxsat(meta.get("jadval_yozuvi"))
	return meta


def _ruxsat(jadval_yozuvi: str | None) -> str | None:
	"""Menejer YOKI shu darsning o'z o'qituvchisi. Qaytaradi: instructor."""
	oqituvchi = frappe.db.get_value("Jadval Yozuvi", jadval_yozuvi, "oqituvchi") if jadval_yozuvi else None
	if _menejermi():
		return oqituvchi
	meniki = _mening_instructorim()
	if not meniki or (oqituvchi and oqituvchi != meniki):
		frappe.throw(_("Faqat shu darsning o'qituvchisi dars audiosini yozishi mumkin."), frappe.PermissionError)
	return oqituvchi or meniki


def _bolaklar(sdir: str) -> list[str]:
	if not os.path.isdir(sdir):
		return []
	return sorted(f for f in os.listdir(sdir) if f.endswith(".part"))


def _hajm(sdir: str) -> int:
	return sum(os.path.getsize(os.path.join(sdir, f)) for f in _bolaklar(sdir))


# ---------------------------------------------------------------- 1) boshlash
@frappe.whitelist()
def audio_boshla(jadval_yozuvi: str, sana: str | None = None, mime: str | None = None) -> dict:
	"""«⏺ Yozishni boshlash» — sessiya papkasi va meta.json yaratadi."""
	sana = str(sana or nowdate())[:10]
	oqituvchi = _ruxsat(jadval_yozuvi)
	jy = frappe.get_doc("Jadval Yozuvi", jadval_yozuvi)

	sid = _sid(jadval_yozuvi, sana)
	sdir = _sess_dir(sid)
	if os.path.isdir(sdir) and _bolaklar(sdir):
		# tugallanmagan yozuv bor — ustiga yozmaymiz, foydalanuvchi hal qiladi
		frappe.throw(_("Bu dars uchun tugallanmagan yozuv bor. Avval uni saqlang yoki o'chiring."))
	os.makedirs(sdir, exist_ok=True)

	meta = {
		"jadval_yozuvi": jy.name,
		"sana": sana,
		"guruh": jy.guruh,
		"guruh_nomi": jy.guruh_nomi or jy.guruh,
		"fan": jy.fan,
		"oqituvchi": oqituvchi,
		"mime": (mime or "audio/webm"),
		"ext": _ext(mime),
		"boshlandi": str(now_datetime()),
		"user": frappe.session.user,
	}
	with open(os.path.join(sdir, "meta.json"), "w", encoding="utf-8") as f:
		json.dump(meta, f, ensure_ascii=False)

	return {"sessiya": sid, "boshlandi": meta["boshlandi"]}


# ---------------------------------------------------------------- 2) bo'lak
@frappe.whitelist()
def audio_bolak(sessiya: str, nomer: int) -> dict:
	"""Bitta bo'lakni saqlaydi. Fayl multipart'da `bolak` nomi bilan keladi."""
	_meta_oqi(sessiya)
	sdir = _sess_dir(sessiya)

	fayllar = getattr(frappe.request, "files", None) or {}
	up = fayllar.get("bolak")
	if not up:
		frappe.throw(_("Bo'lak fayli kelmadi."))
	data = up.stream.read() if hasattr(up, "stream") else up.read()
	if not data:
		return {"nomer": cint(nomer), "hajm": 0}
	if len(data) > MAX_BOLAK:
		frappe.throw(_("Bo'lak juda katta."))
	if _hajm(sdir) + len(data) > MAX_SESSIYA:
		frappe.throw(_("Yozuv hajmi chegarasidan oshdi — yozuvni to'xtatib saqlang."))

	n = cint(nomer)
	if n < 0 or n > 999999:
		frappe.throw(_("Bo'lak raqami xato."))
	with open(os.path.join(sdir, f"{n:06d}.part"), "wb") as f:
		f.write(data)
	return {"nomer": n, "hajm": len(data)}


# ---------------------------------------------------------------- 3) tugatish
@frappe.whitelist()
def audio_tugat(sessiya: str) -> dict:
	"""Bo'laklarni birlashtirib, `Dars Bajarilishi`ga biriktiradi."""
	meta = _meta_oqi(sessiya)
	sdir = _sess_dir(sessiya)
	parts = _bolaklar(sdir)
	if not parts:
		_tozala(sdir)
		frappe.throw(_("Yozuvda ovoz bo'lagi yo'q — hech narsa saqlanmadi."))

	# Uzilish bo'lganmi? (bo'lak raqamlarida bo'shliq) — ogohlantiramiz, lekin saqlaymiz
	raqamlar = [int(p[:6]) for p in parts]
	uzilish = (max(raqamlar) - min(raqamlar) + 1) != len(raqamlar)

	# --- shu kun/mavzu yozuvini topish yoki yaratish
	db = _dars_bajarilishi(meta)

	# --- yakuniy fayl
	tugadi = now_datetime()
	nomi = "dars-audio-{guruh}-{fan}-{sana}-{vaqt}-{rnd}.{ext}".format(
		guruh=_xavfsiz(meta.get("guruh_nomi"), 24),
		fan=_xavfsiz(meta.get("fan"), 24),
		sana=meta.get("sana"),
		vaqt=tugadi.strftime("%H%M"),
		rnd=frappe.generate_hash(length=6),
		ext=meta.get("ext") or "webm",
	)
	yakuniy = frappe.get_site_path("private", "files", nomi)
	with open(yakuniy, "wb") as chiq:
		for p in parts:
			with open(os.path.join(sdir, p), "rb") as kir:
				shutil.copyfileobj(kir, chiq, 1024 * 1024)
	hajm = os.path.getsize(yakuniy)

	fayl = frappe.get_doc({
		"doctype": "File",
		"file_name": nomi,
		"file_url": f"/private/files/{nomi}",
		"is_private": 1,
		"file_size": hajm,
		"content_type": meta.get("mime"),
		"attached_to_doctype": "Dars Bajarilishi",
		"attached_to_name": db["name"],
		"attached_to_field": "audio",
	}).insert(ignore_permissions=True)

	frappe.db.set_value("Dars Bajarilishi", db["name"], "audio", fayl.file_url)
	frappe.db.commit()
	_tozala(sdir)

	return {
		"file_url": fayl.file_url,
		"hajm": hajm,
		"hajm_mb": round(hajm / 1048576, 2),
		"bolaklar": len(parts),
		"uzilish": uzilish,
		"dars_bajarilishi": db["name"],
		"mavzu": db.get("mavzu"),
		"guruh_nomi": meta.get("guruh_nomi"),
		"sana": meta.get("sana"),
		"boshlandi": meta.get("boshlandi"),
		"tugadi": str(tugadi),
	}


def _dars_bajarilishi(meta: dict) -> dict:
	"""Audio biriktiriladigan yozuv: (guruh + sana + slot) bo'yicha bor bo'lsa — o'sha,
	bo'lmasa — keyingi o'tilmagan mavzu bilan yaratiladi (o'qituvchi keyin mavzuni
	almashtirsa ham audio shu yozuvda qoladi)."""
	mavjud = frappe.db.get_value(
		"Dars Bajarilishi",
		{"guruh": meta["guruh"], "sana": meta["sana"], "jadval_yozuvi": meta["jadval_yozuvi"]},
		["name", "mavzu"], as_dict=True,
	)
	if mavjud:
		return {"name": mavjud.name, "mavzu": mavjud.mavzu}

	natija = dars_otdim(
		jadval_yozuvi=meta["jadval_yozuvi"], guruh=meta["guruh"], fan=meta["fan"],
		sana=meta["sana"], holat="O'tildi",
	)
	return {"name": natija["name"], "mavzu": natija.get("mavzu")}


# ---------------------------------------------------------------- holat / bekor
@frappe.whitelist()
def audio_holat(jadval_yozuvi: str, sana: str | None = None) -> dict:
	"""Sahifa yuklanganda: tugallanmagan yozuv bormi, biriktirilgan audio bormi."""
	sana = str(sana or nowdate())[:10]
	_ruxsat(jadval_yozuvi)
	sid = _sid(jadval_yozuvi, sana)
	sdir = os.path.join(_tmp_root(), sid)
	parts = _bolaklar(sdir)
	guruh = frappe.db.get_value("Jadval Yozuvi", jadval_yozuvi, "guruh")
	db = frappe.db.get_value(
		"Dars Bajarilishi", {"guruh": guruh, "sana": sana, "jadval_yozuvi": jadval_yozuvi},
		["name", "mavzu", "audio"], as_dict=True,
	)
	# Biriktirilgan audio haqida ma'lumot (sahifada pleyer ostida ko'rsatiladi)
	audio = (db or {}).get("audio")
	fayl = frappe.db.get_value(
		"File", {"file_url": audio}, ["file_size", "creation", "file_name"], as_dict=True
	) if audio else None

	return {
		"sessiya": sid,
		"tugallanmagan": bool(parts),
		"bolaklar": len(parts),
		"hajm_mb": round(_hajm(sdir) / 1048576, 2) if parts else 0,
		"audio": audio,
		"audio_hajm_mb": round((fayl.file_size or 0) / 1048576, 2) if fayl else None,
		"audio_vaqt": str(fayl.creation)[11:16] if fayl and fayl.creation else None,
		"audio_nomi": fayl.file_name if fayl else None,
		"mavzu": (db or {}).get("mavzu"),
		"dars_bajarilishi": (db or {}).get("name"),
	}


@frappe.whitelist()
def audio_bekor(sessiya: str) -> dict:
	"""Tugallanmagan yozuvni o'chirish."""
	_meta_oqi(sessiya)
	_tozala(_sess_dir(sessiya))
	return {"ok": 1}


def _tozala(sdir: str) -> None:
	try:
		shutil.rmtree(sdir, ignore_errors=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "dars_audio tozalash")
