# Copyright (c) 2026, Target Zenit
"""Eski qo'ng'iroq yozuvlarini to'g'ri xodimga biriktirish.

Nega kerak: boshida Android ilovasida ikkala telefonga ham BITTA akkaunt
(`sotuvmanager@gmail.com`) yozilgan edi, keyin har biriga alohida Employee ID
kiritildi. Yangi qo'ng'iroqlar to'g'ri keladi, eski yozuvlar esa hamon o'sha
umumiy akkauntda qolgan — hisobotlarda ikki menejer bitta odam bo'lib ko'rinadi.

Oqim:
  1) `koring()`      — eski yozuvlar qaysi belgilar bilan ajraladi (telefon
                       modeli, SIM, sana) — ya'ni qaysi qism kimniki;
  2) `biriktir(...)` — tanlangan qismni Employee'ga biriktiradi. Default
                       `dry_run=1`: avval nima o'zgarishini ko'rsatadi, hech
                       nimani yozmaydi.

Ishlatish (serverda):
    bench --site targetschool.erpcontrol.uz execute \\
        target_zenit.telefoniya.backfill.koring

    bench --site targetschool.erpcontrol.uz execute \\
        target_zenit.telefoniya.backfill.biriktir \\
        --kwargs "{'xodim':'HR-EMP-00068','sim':'+99890...','dry_run':1}"

    # ishonch hosil qilgach — dry_run 0 bilan qayta yuritiladi
"""

from __future__ import annotations

import frappe
from frappe import _

DT = "Telefon Qongirogi"
UMUMIY_AKKAUNT = "sotuvmanager@gmail.com"      # boshida ikkala telefonda shu edi


def _ruxsat() -> None:
	"""Ma'lumotni ommaviy o'zgartirish — faqat administrator."""
	if frappe.session.user == "Administrator":
		return
	if "System Manager" in frappe.get_roles():
		return
	frappe.throw(_("Bu amal faqat administrator uchun."), frappe.PermissionError)


def _filtr(foydalanuvchi=None, xodimsiz=1, qurilma=None, sim=None, dan=None, gacha=None):
	"""Qaysi yozuvlar ustida ishlayapmiz — bitta joyda (ko'rish ham, yozish ham)."""
	shart = ["1=1"]
	p = {}
	if foydalanuvchi:
		shart.append("tq.foydalanuvchi = %(u)s")
		p["u"] = foydalanuvchi
	if int(xodimsiz or 0):
		# Xodimi ALLAQACHON to'g'ri qo'yilgan yozuvlarga tegilmaydi
		shart.append("(tq.xodim IS NULL OR tq.xodim = '')")
	if qurilma:
		shart.append("tq.qurilma = %(q)s")
		p["q"] = qurilma
	if sim:
		shart.append("tq.sim_raqam = %(s)s")
		p["s"] = sim
	if dan:
		shart.append("tq.boshlandi >= %(d)s")
		p["d"] = f"{dan} 00:00:00"
	if gacha:
		shart.append("tq.boshlandi <= %(g)s")
		p["g"] = f"{gacha} 23:59:59"
	return " AND ".join(shart), p


def koring(foydalanuvchi: str = UMUMIY_AKKAUNT, xodimsiz: int = 0):
	"""Eski yozuvlar qanday belgilar bilan ajraladi — qaysi qism kimniki.

	Telefonni ajratadigan ustunlar: `qurilma` (model), `sim_raqam`, `ichki_raqam`
	va `xodim_id` (ilovaga kiritilgan qiymat). Qaysi biri farq qilsa — o'sha
	bo'yicha `biriktir()` chaqiriladi."""
	shart, p = _filtr(foydalanuvchi, xodimsiz=xodimsiz)

	jami = frappe.db.sql(
		f"SELECT COUNT(*) FROM `tab{DT}` tq WHERE {shart}", p)[0][0]
	print(f"=== '{foydalanuvchi}' akkauntidagi yozuvlar: {jami} ta "
	      f"{'(faqat xodimi yo‘qlari)' if xodimsiz else ''} ===\n")
	if not jami:
		print("Bunday yozuv yo'q — hammasi allaqachon biriktirilgan bo'lishi mumkin.")
		return

	for ustun, nom in (
		("qurilma", "Telefon modeli"),
		("sim_raqam", "SIM raqami"),
		("ichki_raqam", "Ichki raqam"),
		("xodim_id", "Ilovaga kiritilgan xodim ID"),
		("xodim", "Hozirgi xodim (bo'sh = biriktirilmagan)"),
	):
		qatorlar = frappe.db.sql(
			f"""SELECT COALESCE(NULLIF(tq.{ustun}, ''), '(bo‘sh)') qiymat, COUNT(*) n,
			           MIN(DATE(tq.boshlandi)) dan, MAX(DATE(tq.boshlandi)) gacha,
			           SUM(tq.yozuv_bor) yozuvli
			    FROM `tab{DT}` tq WHERE {shart}
			    GROUP BY qiymat ORDER BY n DESC""", p, as_dict=True)
		print(f"--- {nom} ---")
		for r in qatorlar:
			print(f"   {str(r.qiymat)[:42]:<44} {r.n:>5} ta  "
			      f"{r.dan} … {r.gacha}  (yozuvli {int(r.yozuvli or 0)})")
		print()

	print("--- Oylar bo'yicha ---")
	for r in frappe.db.sql(
		f"""SELECT DATE_FORMAT(tq.boshlandi, '%%Y-%%m') oy, COUNT(*) n
		    FROM `tab{DT}` tq WHERE {shart} GROUP BY oy ORDER BY oy""", p, as_dict=True):
		print(f"   {r.oy}  {r.n:>5} ta")

	print("\nKeyingi qadam: ajratuvchi ustunni tanlab, masalan:\n"
	      "   bench … execute target_zenit.telefoniya.backfill.biriktir \\\n"
	      "       --kwargs \"{'xodim':'HR-EMP-00068','sim':'<SIM raqami>','dry_run':1}\"\n"
	      "Ajratuvchi belgi bo'lmasa (ikkala telefon bir xil ko'rinsa) — sana\n"
	      "oralig'i bilan bo'ling: 'dan':'2026-09-01','gacha':'2026-09-30'.")


def biriktir(
	xodim: str,
	foydalanuvchi: str = UMUMIY_AKKAUNT,
	qurilma: str | None = None,
	sim: str | None = None,
	dan: str | None = None,
	gacha: str | None = None,
	xodimsiz: int = 1,
	dry_run: int = 1,
):
	"""Tanlangan yozuvlarni Employee'ga biriktiradi.

	`xodim` — Employee ID (masalan HR-EMP-00068). Xodimning `user_id` si bo'lsa,
	`foydalanuvchi` maydoni ham o'shanga o'tadi: ruxsat filtri va hisobotlar
	aynan shu maydonga qaraydi.

	Default `dry_run=1` — faqat ko'rsatadi. Yozish uchun `dry_run=0`.
	`xodimsiz=1` (default) — xodimi allaqachon qo'yilganlarga tegilmaydi."""
	_ruxsat()
	emp = frappe.db.get_value(
		"Employee", xodim, ["name", "employee_name", "user_id"], as_dict=True)
	if not emp:
		frappe.throw(_("Employee topilmadi: {0}").format(xodim))

	shart, p = _filtr(foydalanuvchi, xodimsiz, qurilma, sim, dan, gacha)
	nomlar = frappe.db.sql_list(
		f"SELECT tq.name FROM `tab{DT}` tq WHERE {shart} ORDER BY tq.boshlandi", p)

	print(f"Maqsad: {emp.name} — {emp.employee_name} "
	      f"(user_id: {emp.user_id or 'yo‘q'})")
	print(f"Shart: foydalanuvchi={foydalanuvchi!r} qurilma={qurilma!r} sim={sim!r} "
	      f"sana={dan!r}…{gacha!r} xodimsiz={xodimsiz}")
	print(f"Mos keladigan yozuvlar: {len(nomlar)} ta")
	if not nomlar:
		return {"jami": 0, "ozgardi": 0}

	namuna = frappe.db.sql(
		f"""SELECT tq.name, tq.boshlandi, tq.qurilma, tq.sim_raqam, tq.tashqi_raqam
		    FROM `tab{DT}` tq WHERE {shart} ORDER BY tq.boshlandi DESC LIMIT 5""",
		p, as_dict=True)
	print("Namuna (oxirgi 5 ta):")
	for r in namuna:
		print(f"   {r.name}  {str(r.boshlandi)[:16]}  {r.qurilma or '—'}  "
		      f"SIM {r.sim_raqam or '—'}  mijoz {r.tashqi_raqam or '—'}")

	if int(dry_run or 0):
		print("\nDRY RUN — hech nima o'zgartirilmadi. Yozish uchun dry_run=0 bilan qayta yuriting.")
		return {"jami": len(nomlar), "ozgardi": 0, "dry_run": 1}

	vals = {"xodim": emp.name}
	if emp.user_id:
		vals["foydalanuvchi"] = emp.user_id
	for i, nom in enumerate(nomlar, 1):
		frappe.db.set_value(DT, nom, vals, update_modified=False)
		if i % 500 == 0:
			frappe.db.commit()
			print(f"   … {i} ta")
	frappe.db.commit()
	print(f"\nTAYYOR: {len(nomlar)} ta yozuv {emp.name} ga biriktirildi"
	      f"{f' (foydalanuvchi: {emp.user_id})' if emp.user_id else ''}.")
	return {"jami": len(nomlar), "ozgardi": len(nomlar), "xodim": emp.name}


# ===========================================================================
# Umumiy akkauntni butunlay xodimga ko'chirish va eski userni o'chirishga
# tayyorlash. Holat: boshida ilovada `sotuvmanager@gmail.com` ishlatilgan,
# endi har telefonga Employee ID kiritildi — eski yozuvlar o'sha akkauntda
# qolgan va hisobotda "ikkinchi menejer" bo'lib chalg'itadi.
# ===========================================================================

# Eski akkauntga ishora qiladigan app maydonlari (ko'chirishga xavfsiz).
# Har biri: (doctype, maydon) — qiymati User bo'lgan Link maydon.
KOCHIRILADIGAN = [
	("Telefon Qongirogi", "foydalanuvchi"),
	("Qarz Ishi", "masul"),
	("Aloqa Yozuvi", "masul"),
	("Tolov Vadasi", "masul"),
	("ToDo", "allocated_to"),
	("Qarzdorlik Biriktirish", "masul"),
]


# Frappe User o'chirilganda O'ZI tozalaydigan tizim doctype'lari — bular
# to'siq emas, shunchaki ma'lumot uchun ko'rsatiladi.
TIZIM_IZLARI = {
	"Activity Log", "DocShare", "Contact", "Communication", "Notification Settings",
	"Energy Point Log", "Access Log", "Route History", "View Log", "Comment",
	"Dashboard Settings", "User Settings", "File", "Report View Settings",
}


def akkaunt_izlari(user: str = UMUMIY_AKKAUNT) -> dict:
	"""Shu foydalanuvchi qayerlarda ishlatilgan — o'chirishdan oldin ko'rish.

	Frappe User'ni Link maydonlari bo'sh bo'lmasa o'chirmaydi, shuning uchun
	avval shu ro'yxat tozalanishi kerak."""
	out = {}
	print(f"=== '{user}' qayerlarda uchraydi ===")
	for dt, maydon in KOCHIRILADIGAN:
		if not frappe.db.exists("DocType", dt):
			continue
		n = frappe.db.count(dt, {maydon: user})
		if n:
			out[f"{dt}.{maydon}"] = n
			print(f"   {dt}.{maydon:<14} {n:>6} ta")

	# Boshqa (app'ga tegishli bo'lmagan) Link maydonlari — faqat xabar beramiz
	boshqa = frappe.db.sql(
		"""SELECT df.parent dt, df.fieldname FROM `tabDocField` df
		   JOIN `tabDocType` dtp ON dtp.name = df.parent
		   WHERE df.fieldtype='Link' AND df.options='User' AND dtp.issingle=0
		     AND dtp.istable=0""", as_dict=True)
	for r in boshqa:
		if (r.dt, r.fieldname) in KOCHIRILADIGAN:
			continue
		try:
			n = frappe.db.count(r.dt, {r.fieldname: user})
		except Exception:
			continue
		if n:
			tizim = r.dt in TIZIM_IZLARI
			if not tizim:
				out[f"{r.dt}.{r.fieldname}"] = n
			print(f"   {r.dt}.{r.fieldname:<14} {n:>6} ta   "
			      f"{'(tizim — o‘chirishda o‘zi tozalanadi)' if tizim else '(qo‘lda tekshiring)'}")

	soz = frappe.db.get_single_value("Qarzdorlik Sozlamalari", "default_masul")
	if soz == user:
		out["Qarzdorlik Sozlamalari.default_masul"] = 1
		print("   Qarzdorlik Sozlamalari.default_masul — shu foydalanuvchi!")
	if not out:
		print("   (app ma'lumotlarida ishlatilmagan — o'chirsa bo'ladi)")
	return out


def akkauntni_kochir(
	xodim: str,
	eski: str = UMUMIY_AKKAUNT,
	hammasi: int = 1,
	dry_run: int = 1,
):
	"""Eski umumiy akkauntdagi HAMMA narsani xodimga (uning user_id siga) ko'chiradi.

	`hammasi=1` — qo'ng'iroqlardan tashqari qarz ishlari, aloqa yozuvlari,
	va'dalar va ToDo'lar ham ko'chadi (eski userni o'chirish uchun shart).
	`hammasi=0` — faqat telefon yozuvlari.
	Default `dry_run=1`."""
	_ruxsat()
	emp = frappe.db.get_value(
		"Employee", xodim, ["name", "employee_name", "user_id"], as_dict=True)
	if not emp:
		frappe.throw(_("Employee topilmadi: {0}").format(xodim))
	if not emp.user_id:
		frappe.throw(_("{0} ({1}) ning user_id si yo'q — avval Employee'ga "
		               "foydalanuvchi biriktiring.").format(emp.name, emp.employee_name))

	print(f"Eski akkaunt : {eski}")
	print(f"Yangi egasi  : {emp.name} — {emp.employee_name} (user: {emp.user_id})\n")

	reja = []
	n_tel = frappe.db.count(DT, {"foydalanuvchi": eski})
	reja.append((DT, "foydalanuvchi", n_tel))
	if int(hammasi or 0):
		for dt, maydon in KOCHIRILADIGAN:
			if dt == DT or not frappe.db.exists("DocType", dt):
				continue
			n = frappe.db.count(dt, {maydon: eski})
			if n:
				reja.append((dt, maydon, n))

	for dt, maydon, n in reja:
		print(f"   {dt}.{maydon:<14} {n:>6} ta -> {emp.user_id}")
	if not any(n for _, _, n in reja):
		print("   (ko'chiriladigan narsa yo'q)")
		return {"ozgardi": 0}

	if int(dry_run or 0):
		print("\nDRY RUN — hech nima o'zgartirilmadi. Yozish uchun dry_run=0.")
		return {"reja": {f"{d}.{m}": n for d, m, n in reja}, "ozgardi": 0, "dry_run": 1}

	jami = 0
	for dt, maydon, n in reja:
		if not n:
			continue
		if dt == DT:
			# Telefon yozuvida xodim maydoni ham to'ldiriladi
			frappe.db.sql(
				f"""UPDATE `tab{DT}` SET foydalanuvchi=%(u)s, xodim=%(x)s
				    WHERE foydalanuvchi=%(e)s""",
				{"u": emp.user_id, "x": emp.name, "e": eski})
		else:
			frappe.db.sql(
				f"UPDATE `tab{dt}` SET `{maydon}`=%(u)s WHERE `{maydon}`=%(e)s",
				{"u": emp.user_id, "e": eski})
		jami += n
		print(f"   {dt}.{maydon}: {n} ta ko'chirildi")
	frappe.db.commit()

	qoldi = akkaunt_izlari(eski)
	print(f"\nTAYYOR: {jami} ta yozuv {emp.name} ({emp.user_id}) ga o'tdi.")
	if qoldi:
		print("Eski akkauntni o'chirishdan oldin yuqoridagi qoldiqlarni tozalang.")
	else:
		print(f"Eski akkaunt bo'sh — endi o'chirish mumkin:\n"
		      f"   bench … execute target_zenit.telefoniya.backfill.akkauntni_ochir "
		      f"--kwargs \"{{'user':'{eski}'}}\"")
	return {"ozgardi": jami, "qoldi": qoldi}


def akkauntni_ochir(user: str = UMUMIY_AKKAUNT, dry_run: int = 1):
	"""Eski foydalanuvchini o'chiradi (izlari qolmagan bo'lsa).

	O'chirib bo'lmasa — nima to'sayotganini aytadi; o'shanda `akkauntni_kochir`
	bilan qoldiqni ko'chirib, qayta uriniladi. Muqobil: foydalanuvchini
	o'chirmasdan NOFAOL qilish (`enabled=0`) — tarix buzilmaydi."""
	_ruxsat()
	if not frappe.db.exists("User", user):
		print(f"'{user}' topilmadi — allaqachon o'chirilgan.")
		return {"holat": "yo'q"}
	izlar = akkaunt_izlari(user)
	if izlar:
		print("\nIzlar bor — avval ularni ko'chiring (akkauntni_kochir).")
		return {"holat": "to'siq", "izlar": izlar}
	if int(dry_run or 0):
		print("\nDRY RUN — o'chirilmadi. O'chirish uchun dry_run=0.")
		return {"holat": "tayyor", "dry_run": 1}
	try:
		frappe.delete_doc("User", user, ignore_permissions=True)
		frappe.db.commit()
		print(f"'{user}' o'chirildi.")
		return {"holat": "o'chirildi"}
	except Exception as e:
		frappe.db.rollback()
		print(f"O'chirib bo'lmadi: {type(e).__name__}: {str(e)[:300]}")
		print("Tavsiya: foydalanuvchini nofaol qiling (User -> Enabled belgisini oling) —"
		      " tarix saqlanadi, ro'yxatlarda ko'rinmaydi.")
		return {"holat": "xato", "sabab": str(e)[:300]}
