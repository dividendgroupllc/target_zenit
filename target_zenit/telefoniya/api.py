# Copyright (c) 2026, Target Zenit
"""Telefoniya API — qo'ng'iroq yozuvlarini qabul qilish nuqtasi.

Ikki xil manba qo'llab-quvvatlanadi va ikkisi ham AYNAN SHU endpoint'ga
yuboradi, shunchaki maydon nomlari boshqacha:

  * **Asterisk** (PBX server) — `uniqueid`, `yonalish`, `tashqi_raqam`, ...
  * **Android** (sotuvchi telefonidagi ASMIZ Call ilovasi) — `client_call_id`,
    `direction`, `phone_number`, `employee_id`, ...

Maydon nomlari taqqoslanib bitta modelga keltiriladi (ALIAS jadvali), shuning
uchun ilovani qayta yozish kerak emas — faqat URL o'zgaradi.

Autentifikatsiya: Frappe token (`Authorization: token <api_key>:<api_secret>`).
Asterisk uchun alohida foydalanuvchi yaratiladi, roli "Telefoniya Agent" —
server kaliti o'g'irlansa ham boshqa ma'lumotga tegib bo'lmaydi.

Yuborish ikki bosqichda bo'lishi mumkin:
  1. Qo'ng'iroq tugadi -> metadata yuboriladi (fayl hali konvertatsiya qilinmagan)
  2. MP3 tayyor bo'ldi  -> xuddi shu uniqueid bilan fayl yuboriladi
Yoki ikkisi bitta so'rovda. Ikki holat ham qo'llab-quvvatlanadi.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils import cint, get_datetime

from target_zenit.telefoniya import matcher, storage
from target_zenit.telefoniya.utils import normalize_phone

DOCTYPE = "Telefon Qongirogi"

# Asterisk DIALSTATUS -> bizning "Natija" qiymatlari.
NATIJA_MAP = {
	"ANSWER": "Javob berildi",
	"ANSWERED": "Javob berildi",
	"NOANSWER": "Javob yo'q",
	"NO ANSWER": "Javob yo'q",
	"BUSY": "Band",
	"CONGESTION": "Xato",
	"CHANUNAVAIL": "O'chirilgan",
	"CANCEL": "Bekor qilindi",
	"FAILED": "Xato",
}

# Android ilovasi (ASMIZ Call) yuboradigan maydon nomlari -> bizning nomlar.
# Ilovaning o'zini o'zgartirmaslik uchun ikkisi ham qabul qilinadi.
ALIAS = {
	"uniqueid": ("uniqueid", "client_call_id"),
	"yonalish": ("yonalish", "direction"),
	"tashqi_raqam": ("tashqi_raqam", "phone_number"),
	"boshlandi": ("boshlandi", "started_at"),
	"suhbat_vaqti": ("suhbat_vaqti", "duration_sec"),
	"fayl_hash": ("fayl_hash", "file_hash"),
	"qurilma": ("qurilma", "device_model"),
	"kontakt_ism": ("kontakt_ism", "contact_name"),
	"ichki_raqam": ("ichki_raqam",),
	"xodim_id": ("xodim_id", "employee_id"),
}

YONALISH_MAP = {
	"outgoing": "Chiquvchi",
	"out": "Chiquvchi",
	"chiquvchi": "Chiquvchi",
	"incoming": "Kiruvchi",
	"in": "Kiruvchi",
	"kiruvchi": "Kiruvchi",
}


@frappe.whitelist()
def ingest_call():
	"""Qo'ng'iroq metadatasi va (ixtiyoriy) ovoz yozuvini qabul qiladi.

	Manbalar: Asterisk PBX yoki sotuvchi telefonidagi Android ilova.

	Idempotent: bir xil `uniqueid` bilan qayta yuborilsa yangi hujjat
	yaratilmaydi. Shu sababli yuklovchi xotirjam qayta urinishi mumkin —
	internet uzilsa yozuv navbatda turadi va keyin yuboriladi.
	"""
	form = frappe.form_dict
	yuklangan = frappe.request.files.get("file") if frappe.request else None
	fayl_hash = _m(form, "fayl_hash")

	# Android ilovasi `uniqueid` yubormaydi — uning barqaror kaliti fayl hash'i.
	# Shu sababli uniqueid ketma-ketlikda izlanadi.
	uniqueid = _m(form, "uniqueid") or (fayl_hash or "")[:32]
	if not uniqueid:
		frappe.throw(
			_("'uniqueid' yoki 'file_hash' majburiy"), frappe.ValidationError
		)

	mavjud = frappe.db.get_value(
		DOCTYPE, {"asterisk_uniqueid": uniqueid}, ["name", "yozuv_bor"], as_dict=True
	)
	if mavjud:
		# Hujjat bor. Yozuv hali yo'q va endi fayl kelgan bo'lsa — biriktiramiz.
		if yuklangan and not mavjud.yozuv_bor:
			qongiroq = frappe.get_doc(DOCTYPE, mavjud.name)
			_yozuvni_biriktir(qongiroq, yuklangan, fayl_hash)
			return _javob(qongiroq.name, takror=False, yozuv=True)
		return _javob(mavjud.name, takror=True, yozuv=bool(mavjud.yozuv_bor))

	manba = _manba(form)

	qongiroq = frappe.new_doc(DOCTYPE)
	qongiroq.asterisk_uniqueid = uniqueid
	qongiroq.manba = manba
	qongiroq.yonalish = YONALISH_MAP.get(_m(form, "yonalish").lower(), "Chiquvchi")
	qongiroq.ichki_raqam = _m(form, "ichki_raqam") or None
	qongiroq.tashqi_raqam = _m(form, "tashqi_raqam") or None
	qongiroq.sim_kanal = (form.get("sim_kanal") or "").strip() or None
	qongiroq.sim_raqam = (form.get("sim_raqam") or "").strip() or None
	qongiroq.boshlandi = _vaqt(_m(form, "boshlandi")) or frappe.utils.now_datetime()
	qongiroq.javob_berildi = _vaqt(form.get("javob_berildi"))
	qongiroq.tugadi = _vaqt(form.get("tugadi"))
	qongiroq.suhbat_vaqti = cint(_m(form, "suhbat_vaqti"))
	qongiroq.kim_tugatdi = _kim_tugatdi(form.get("kim_tugatdi"))
	qongiroq.maqsad = (form.get("maqsad") or "").strip() or None
	qongiroq.qurilma = _m(form, "qurilma") or None
	qongiroq.kontakt_ism = _m(form, "kontakt_ism") or None
	qongiroq.tugash_sababi = _natija(form.get("tugash_sababi")) or _natijani_taxmin(
		qongiroq.suhbat_vaqti
	)
	qongiroq.holat = "Yangi"

	# Android ilovasi ichki raqam emas, xodim identifikatorini yuboradi.
	xodim_id = _m(form, "xodim_id")
	qongiroq.xodim_id = xodim_id or None
	xodim = _xodimni_top(xodim_id)
	if xodim:
		qongiroq.xodim = xodim.get("name")
		qongiroq.foydalanuvchi = xodim.get("user_id")
	elif xodim_id:
		# Bog'lanmagan qo'ng'iroqni JIMGINA o'tkazib yuborish xavfli: sotuvchi
		# o'z qo'ng'irog'ini ko'rmaydi (ruxsat filtri) va hisobotda hech kimga
		# tegishli bo'lmaydi. Shuning uchun hujjatda ko'rinadigan belgi qoldiramiz.
		qongiroq.xato_matni = (
			f"Xodim topilmadi: {xodim_id!r}. Telefondagi 'employee_id' sozlamasini "
			f"tekshiring — Employee nomi, foydalanuvchi email'i yoki ichki raqam bo'lishi kerak."
		)

	qongiroq.insert()

	yozuv_bor = False
	if yuklangan:
		_yozuvni_biriktir(qongiroq, yuklangan, fayl_hash)
		yozuv_bor = True

	frappe.db.commit()
	return _javob(qongiroq.name, takror=False, yozuv=yozuv_bor)


def _m(form, nom: str) -> str:
	"""ALIAS jadvali bo'yicha birinchi to'ldirilgan qiymatni oladi."""
	for kalit in ALIAS.get(nom, (nom,)):
		qiymat = (form.get(kalit) or "").strip()
		if qiymat:
			return qiymat
	return ""


def _manba(form) -> str:
	"""Yozuv qaysi tizimdan kelganini aniqlaydi.

	Aniq ko'rsatilgan bo'lsa shu olinadi; aks holda Android ilovasiga xos
	maydonlar (telefon modeli, xodim id) bo'yicha taxmin qilinadi.
	"""
	aniq = (form.get("manba") or "").strip().title()
	if aniq in ("Asterisk", "Android", "Qo'Lda"):
		return "Asterisk" if aniq == "Asterisk" else ("Android" if aniq == "Android" else "Qo'lda")
	if form.get("device_model") or form.get("employee_id") or form.get("client_call_id"):
		return "Android"
	return "Asterisk"


def _xodimni_top(xodim_id: str):
	"""Android ilovasidagi "employee_id" ni Employee hujjatiga bog'laydi.

	Sozlashda xato bo'lmasligi uchun uch xil kiritish qabul qilinadi:
	Employee nomi (HR-EMP-0001), foydalanuvchi email'i, yoki ichki raqam.
	"""
	if not xodim_id:
		return None
	for filtr in (
		{"name": xodim_id},
		{"user_id": xodim_id},
		{"telefon_ichki_raqam": xodim_id},
	):
		try:
			topildi = frappe.get_all("Employee", filters=filtr, fields=["name", "user_id"], limit=1)
		except Exception:
			continue
		if topildi:
			return topildi[0]

	# Employee yozuvi bo'lmasa ham, foydalanuvchi bo'lsa qo'ng'iroq egasiz
	# qolmasligi kerak — aks holda sotuvchi o'z yozuvini eshita olmaydi.
	if frappe.db.exists("User", xodim_id):
		return {"name": None, "user_id": xodim_id}
	return None


def _natijani_taxmin(suhbat_vaqti) -> str | None:
	"""Android ilovasi qo'ng'iroq natijasini yubormaydi — davomiylikdan chiqaramiz.

	Telefon yozuvi faqat gaplashilgan qo'ng'iroqda paydo bo'ladi, shuning uchun
	davomiylik > 0 bo'lsa javob berilgan deb hisoblash xavfsiz.
	"""
	return "Javob berildi" if cint(suhbat_vaqti) > 0 else None


def _javob(nomi: str, takror: bool, yozuv: bool) -> dict:
	"""Javobni ikki xil nom bilan qaytaradi.

	Android ilovasi `call_id`/`duplicate` kalitlarini kutadi (asmiz_call
	davridan qolgan), Asterisk yuklovchisi esa `qongiroq`/`takror`. Ilovani
	o'zgartirmaslik uchun ikkisi ham beriladi.
	"""
	return {
		"status": "ok",
		"qongiroq": nomi,
		"takror": takror,
		"yozuv": yozuv,
		"call_id": nomi,
		"duplicate": takror,
	}


def _yozuvni_biriktir(qongiroq, yuklangan, kutilgan_hash: str | None):
	"""Yuklangan faylni tekshirib diskka yozadi va hujjatni yangilaydi."""
	content = yuklangan.stream.read()
	if not content:
		frappe.throw(_("Yuborilgan fayl bo'sh"), frappe.ValidationError)

	maks_mb = cint(frappe.db.get_single_value("Telefoniya Sozlamalari", "maks_fayl_mb")) or 25
	if len(content) > maks_mb * 1024 * 1024:
		frappe.throw(_("Fayl juda katta: {0} MB chegara").format(maks_mb), frappe.ValidationError)

	# Butunlikni tekshirish: hash'ni o'zimiz qayta hisoblaymiz. Yarim yuklangan
	# yoki buzilgan fayl shu yerda ushlanadi, aks holda "yozuv bor" deb
	# belgilangan buzuq fayl bilan qolib ketardik.
	haqiqiy_hash = hashlib.sha256(content).hexdigest()
	if kutilgan_hash and kutilgan_hash.strip().lower() != haqiqiy_hash:
		frappe.throw(
			_("Fayl hash mos kelmadi — yuklash buzilgan. Qayta yuboring."),
			frappe.ValidationError,
		)

	# Android telefonlari OEM'ga qarab turli formatda yozadi: Xiaomi/Samsung —
	# .m4a yoki .mp3, Honor — .amr. Kengaytmani saqlab qolamiz, aks holda
	# fayl nomi ".mp3" bo'lib turib ichida AMR bo'lib chiqadi.
	kengaytma = (yuklangan.filename or "x.mp3").rsplit(".", 1)[-1].lower()
	if kengaytma not in ("mp3", "wav", "ogg", "opus", "m4a", "amr", "aac", "3gp"):
		kengaytma = "mp3"

	nisbiy = storage.nisbiy_yol(qongiroq.asterisk_uniqueid, qongiroq.boshlandi, kengaytma)
	storage.saqla(nisbiy, content)

	qongiroq.db_set(
		{
			"fayl_yoli": nisbiy,
			"fayl_hash": haqiqiy_hash,
			"fayl_hajmi": len(content),
			"yozuv_bor": 1,
			"yozuv_ochirildi": 0,
			"holat": "Yozuv bor",
			# `xato_matni` ataylab tozalanmaydi: unda xodim bog'lanmagani kabi
			# yozuvga aloqasi yo'q ogohlantirishlar bo'lishi mumkin, va fayl
			# kelishi bilan ularni o'chirib yuborish muammoni yashirardi.
		},
		notify=True,
	)
	frappe.db.commit()


@frappe.whitelist()
def stream_recording(qongiroq: str):
	"""Yozuvni brauzerga beradi — pleer shu URL'ni o'qiydi.

	Fayl Frappe `files` papkasidan tashqarida, shuning uchun to'g'ridan-to'g'ri
	URL bilan olinmaydi. Ruxsat shu yerda tekshiriladi: menejer faqat o'z
	qo'ng'irog'ini, rahbar hammasini eshitadi.
	"""
	doc = frappe.get_doc(DOCTYPE, qongiroq)
	doc.check_permission("read")

	if not doc.yozuv_bor or not doc.fayl_yoli:
		frappe.throw(_("Bu qo'ng'iroqda ovoz yozuvi yo'q"), frappe.DoesNotExistError)
	if doc.yozuv_ochirildi:
		frappe.throw(_("Yozuv saqlash muddati tugab o'chirilgan"), frappe.DoesNotExistError)

	content = storage.oqi(doc.fayl_yoli)
	kengaytma = doc.fayl_yoli.rsplit(".", 1)[-1].lower()

	frappe.local.response.filename = f"{doc.name}.{kengaytma}"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
	# "inline" bo'lmasa brauzer faylni yuklab oladi, pleerda ijro etmaydi.
	frappe.local.response.display_content_as = "inline"
	frappe.local.response.content_type = {
		"mp3": "audio/mpeg",
		"wav": "audio/wav",
		"ogg": "audio/ogg",
		"opus": "audio/ogg",
		"m4a": "audio/mp4",
		"aac": "audio/aac",
		"3gp": "audio/3gpp",
		# AMR'ni brauzer ijro etmaydi — pleer "qo'llab-quvvatlanmaydi" deydi,
		# lekin fayl yuklab olinadi va tashqi pleerda eshitiladi.
		"amr": "audio/amr",
	}.get(kengaytma, "application/octet-stream")


@frappe.whitelist()
def lookup_number(raqam: str):
	"""Kiruvchi qo'ng'iroqni yo'naltirish uchun: raqam kimga tegishli.

	Asterisk buni qo'ng'iroq kelganda so'raydi va javobdagi ichki raqamga
	uzatadi — ota-ona o'zining menejeriga tushadi.
	"""
	normal = normalize_phone(raqam)
	natija = matcher.topish(normal)
	natija["normal_telefon"] = normal

	ichki, egasi = None, None
	if natija.get("admission_lead"):
		egasi = frappe.db.get_value("Admission Lead", natija["admission_lead"], "lead_owner")
	if egasi:
		xodim = frappe.db.get_value(
			"Employee", {"user_id": egasi}, ["name", "telefon_ichki_raqam"], as_dict=True
		)
		ichki = xodim and xodim.get("telefon_ichki_raqam")
	natija["lead_owner"] = egasi
	natija["ichki_raqam"] = ichki
	return natija


def eski_yozuvlarni_ochir():
	"""Saqlash muddati o'tgan yozuv fayllarini o'chiradi (kunlik scheduler).

	Faqat fayl o'chiriladi — qo'ng'iroq metadatasi (kim, kimga, qancha
	gaplashdi) hisobotlar uchun bazada qoladi.
	"""
	kun = cint(frappe.db.get_single_value("Telefoniya Sozlamalari", "saqlash_kuni"))
	if kun <= 0:
		return

	chegara = frappe.utils.add_days(frappe.utils.nowdate(), -kun)
	qatorlar = frappe.get_all(
		DOCTYPE,
		filters={"yozuv_bor": 1, "yozuv_ochirildi": 0, "boshlandi": ["<", chegara]},
		fields=["name", "fayl_yoli"],
		limit=2000,
	)
	for q in qatorlar:
		if q.fayl_yoli:
			storage.ochir(q.fayl_yoli)
		frappe.db.set_value(
			DOCTYPE, q.name, {"yozuv_ochirildi": 1, "yozuv_bor": 0}, update_modified=False
		)
	if qatorlar:
		frappe.db.commit()
		frappe.logger("telefoniya").info(f"{len(qatorlar)} ta eski yozuv o'chirildi")


def _vaqt(qiymat):
	"""ISO-8601 yoki Unix epoch -> Frappe datetime. Tanib bo'lmasa None."""
	if not qiymat:
		return None
	matn = str(qiymat).strip()
	if matn.replace(".", "", 1).isdigit() and len(matn.split(".")[0]) == 10:
		from datetime import datetime

		return datetime.fromtimestamp(float(matn))
	try:
		return get_datetime(matn.replace("T", " ")[:19])
	except Exception:
		return None


def _natija(qiymat):
	if not qiymat:
		return None
	matn = str(qiymat).strip()
	return NATIJA_MAP.get(matn.upper(), matn if matn in NATIJA_MAP.values() else None)


def _kim_tugatdi(qiymat):
	if not qiymat:
		return None
	matn = str(qiymat).strip().lower()
	if matn in ("manager", "menejer", "agent", "internal", "caller"):
		return "Menejer"
	if matn in ("customer", "mijoz", "client", "external", "callee"):
		return "Mijoz"
	return "Noma'lum"
