# Copyright (c) 2026, Target Zenit
"""Murojaat moduli o'rnatmasi: CEO va Direktor rollari, kategoriya marshruti,
doctype ruxsatlari. Idempotent — har migrate'da xavfsiz qayta ishlaydi.

Rol PROD'da foydalanuvchiga QO'LDA tayinlanadi (User hujjatida) — bu yerda
faqat rolning o'zi, ruxsatlar va boshlang'ich kategoriyalar ta'minlanadi.
Direktor Employee'dan keladi: User ochilib `Employee.user_id` ga bog'lanadi,
rol esa shu user'ga beriladi (moliya_rol.py naqshi).
"""

import json

import frappe
from frappe.utils import cint

ROLLAR = ("CEO", "Direktor")

# Boshlang'ich marshrut jadvali: (kategoriya, kimga, muddat kun, odatdagi turi,
# kalit so'zlar — AI topgan matnni shu so'zlar bo'yicha kategoriyaga soladi)
KATEGORIYALAR = [
	# ---- CEO: pul, tashkiliy ishlar, xizmat ko'rsatish
	("Kitob / forma to'lovi", "CEO", 2, "Shikoyat", "kitob,forma,darslik,kiyim,uniforma"),
	("Moliya / chegirma", "CEO", 2, "So'rov", "chegirma,narx,qimmat,to'lov summasi,oylik to'lov,shartnoma summasi"),
	("Shartnoma / hujjat", "CEO", 3, "So'rov", "shartnoma,hujjat,ma'lumotnoma,spravka"),
	("Tashkiliy ishlar", "CEO", 3, "Muammo", "tashkiliy,boshqaruv,administrator,qabul,navbat"),
	("Transport", "CEO", 2, "Shikoyat", "avtobus,transport,haydovchi,yo'l,olib ketish,olib kelish,kechikib keldi,kutib qoldi"),
	("Ovqatlanish", "CEO", 2, "Shikoyat", "ovqat,oshxona,taom,nonushta,tushlik,pitaniya,sovuq ovqat,och qoldi"),
	("Bino / sharoit", "CEO", 5, "Shikoyat", "sinf sharoiti,issiq,sovuq,sovqot,isitish,konditsioner,hojatxona,toza,ta'mir,jihoz,parta,yorug'"),
	("Yotoqxona", "CEO", 3, "Shikoyat", "yotoqxona,internat,yotoq"),
	# ---- Direktor: o'quv-tarbiya jarayoni
	("Ta'lim sifati", "Direktor", 3, "Shikoyat", "ta'lim sifati,dars sifati,o'rganmadi,o'rganmayapti,bilim,darajasi past,yaxshi o'qitmaydi,darslar bo'sh"),
	("O'qituvchi ustidan shikoyat", "Direktor", 2, "Shikoyat", "o'qituvchi,ustoz,muallim,pedagog,almashtir"),
	("Tarbiyaviy ishlar", "Direktor", 2, "Shikoyat", "tarbiya,urish,janjal,bulling,xafa,kaltakladi,nizo,axloq"),
	("Bolalar nazorati", "Direktor", 1, "Muammo", "nazorat,qarovsiz,yo'qolib,kuzatuv,xavfsizlik"),
	("Dars jadvali", "Direktor", 3, "Muammo", "jadval,dars vaqti,kech boshlanadi,bo'sh dars"),
	("Baho / davomat", "Direktor", 3, "So'rov", "baho,davomat,yo'qlama,kelmadi,imtihon,chorak"),
	("Uy vazifa", "Direktor", 3, "Shikoyat", "uy vazifa,vazifa,ko'p,tekshirilmaydi"),
	("Tadbir / to'garak", "Direktor", 5, "Taklif", "tadbir,to'garak,sayohat,bayram,musobaqa,olimpiada"),
	# ---- Marshrut aniq bo'lmaganda: AI aytgan yo'nalish bo'yicha ikkiga bo'linadi
	# (kalit so'z topilmasa ham murojaat EGASIZ qolmasligi kerak)
	("Aniqlanmagan - tashkiliy", "CEO", 2, None, ""),
	("Aniqlanmagan - o'quv", "Direktor", 2, None, ""),
]

# doctype: (read, write, create, delete)
RAHBAR_PERMS = {
	"Murojaat": (1, 1, 1, 0),
	"Murojaat Kategoriyasi": (1, 1, 1, 0),
	# Murojaat kartasida o'quvchi, qarz holati, suhbat va ovoz yozuvi ko'rinadi
	"Student": (1, 0, 0, 0),
	"Guardian": (1, 0, 0, 0),
	"Qarz Ishi": (1, 0, 0, 0),
	"Aloqa Yozuvi": (1, 0, 0, 0),
	"Tolov Rejasi": (1, 0, 0, 0),
	"Tolov Vadasi": (1, 0, 0, 0),
	"Telefon Qongirogi": (1, 0, 0, 0),
	"Employee": (1, 0, 0, 0),
}

SAHIFALAR = ("murojaatlar",)


def after_migrate():
	rollarni_yarat()
	kategoriyalarni_yarat()
	ruxsatlarni_ber()
	sahifalarni_och()
	workspace_yarat()
	sotuvga_yorliq()
	frappe.db.commit()


def before_migrate():
	"""Rol doctype JSON'larida ishlatiladi — migrate'dan OLDIN bo'lishi shart,
	aks holda ruxsat qatori "link yo'q" deb tushib qoladi (moliya_rol.py tajribasi)."""
	rollarni_yarat()
	frappe.db.commit()


def rollarni_yarat():
	for rol in ROLLAR:
		if frappe.db.exists("Role", rol):
			continue
		frappe.get_doc({
			"doctype": "Role",
			"role_name": rol,
			"desk_access": 1,
			"is_custom": 1,
		}).insert(ignore_permissions=True)


def kategoriyalarni_yarat():
	"""Faqat YO'Q kategoriyani yaratadi. Mavjudining marshrutiga TEGMAYDI —
	rahbariyat qo'lda o'zgartirgan yo'nalish deploy'da qaytib ketmasligi kerak.

	Kalit so'zlar esa QO'SHILADI (birlashma): yangi versiyada aniqroq so'zlar
	paydo bo'lsa AI marshruti yaxshilanadi, admin qo'lda yozganlari esa
	o'chib ketmaydi."""
	for nomi, kimga, kun, turi, kalit in KATEGORIYALAR:
		if frappe.db.exists("Murojaat Kategoriyasi", nomi):
			_kalit_birlashtir(nomi, kalit)
			continue
		frappe.get_doc({
			"doctype": "Murojaat Kategoriyasi",
			"nomi": nomi,
			"yonaltirish": kimga,
			"sla_kun": kun,
			"turi_tavsiya": turi,
			"kalit_sozlar": kalit,
			"faol": 1,
		}).insert(ignore_permissions=True)


def _kalit_birlashtir(nomi: str, seed: str) -> None:
	"""Seed'dagi yangi kalit so'zlarni mavjud ro'yxatga qo'shadi (o'chirmaydi)."""
	if not seed:
		return
	joriy = frappe.db.get_value("Murojaat Kategoriyasi", nomi, "kalit_sozlar") or ""
	bor = {s.strip().lower() for s in joriy.replace("\n", ",").split(",") if s.strip()}
	yangi = [s.strip().lower() for s in seed.split(",") if s.strip() and s.strip().lower() not in bor]
	if not yangi:
		return
	frappe.db.set_value(
		"Murojaat Kategoriyasi", nomi, "kalit_sozlar",
		", ".join(sorted(bor | set(yangi))),
	)
	frappe.cache().delete_value("murojaat_kategoriyalar")


def ruxsatlarni_ber():
	for rol in ROLLAR:
		for dt, (r, w, c, d) in RAHBAR_PERMS.items():
			if not frappe.db.exists("DocType", dt):
				continue
			_perm(dt, rol, r, w, c, d)


def _perm(doctype: str, rol: str, read: int, write: int, create: int, delete: int):
	nomi = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": rol, "permlevel": 0}, "name"
	)
	bor = frappe.db.get_value(
		"DocPerm", {"parent": doctype, "role": rol, "permlevel": 0}, "name"
	)
	if bor:
		return      # standart ruxsat allaqachon doctype JSON'ida bor
	qiymat = {
		"read": cint(read), "write": cint(write), "create": cint(create),
		"delete": cint(delete), "report": 1, "export": cint(read), "print": cint(read),
	}
	if nomi:
		frappe.db.set_value("Custom DocPerm", nomi, qiymat)
		return
	doc = frappe.get_doc({
		"doctype": "Custom DocPerm", "parent": doctype, "parenttype": "DocType",
		"role": rol, "permlevel": 0, **qiymat,
	})
	doc.insert(ignore_permissions=True)


def sahifalarni_och():
	"""Page JSON'idagi rollar yetarli, lekin rol page'dan KEYIN yaratilgan
	bo'lsa qator tushib qolgan bo'ladi — shuni tiklaydi."""
	for sahifa in SAHIFALAR:
		if not frappe.db.exists("Page", sahifa):
			continue
		doc = frappe.get_doc("Page", sahifa)
		bor = {r.role for r in doc.roles}
		yangi = [r for r in ROLLAR if r not in bor]
		if not yangi:
			continue
		for rol in yangi:
			doc.append("roles", {"role": rol})
		doc.save(ignore_permissions=True)


# ====================================================== workspace / yorliqlar
WORKSPACE = "Rahbariyat"


def workspace_yarat():
	"""CEO va direktor desk'ga kirganda murojaatlar paneli ko'rinib turishi
	kerak — ular URL yozib yurmaydi. Idempotent."""
	if frappe.db.exists("Workspace", WORKSPACE):
		_yorliq_qosh(WORKSPACE, [
			{"label": "Murojaatlar", "type": "Page", "link_to": "murojaatlar", "color": "Red"},
		])
		return
	doc = frappe.get_doc({
		"doctype": "Workspace",
		"title": WORKSPACE,
		"label": WORKSPACE,
		"module": "target_zenit",
		"public": 1,
		"icon": "crm",
		"sequence_id": 90,
		# Workspace FAQAT rahbariyat va sotuvga ko'rinadi — aks holda "public"
		# workspace butun maktab xodimlariga chiqib ketadi
		"roles": [{"role": r} for r in ("System Manager", "CEO", "Direktor",
		                                "Sales Manager", "Sotuv meneger")],
		"shortcuts": [
			{"label": "Murojaatlar", "type": "Page", "link_to": "murojaatlar", "color": "Red"},
			{"label": "Murojaat kategoriyalari", "type": "DocType",
			 "link_to": "Murojaat Kategoriyasi", "doc_view": "List", "color": "Grey"},
		],
		"content": json.dumps([
			{"id": frappe.generate_hash(length=10), "type": "header",
			 "data": {"text": "<span class=\"h4\">Rahbariyat</span>", "col": 12}},
			{"id": frappe.generate_hash(length=10), "type": "shortcut",
			 "data": {"shortcut_name": "Murojaatlar", "col": 4}},
			{"id": frappe.generate_hash(length=10), "type": "shortcut",
			 "data": {"shortcut_name": "Murojaat kategoriyalari", "col": 4}},
		]),
	})
	doc.insert(ignore_permissions=True)
	print(f"Workspace yaratildi: {WORKSPACE}")


def sotuvga_yorliq():
	"""Sotuvchi ham "yuborgan murojaatim nima bo'ldi" ni ko'rishi kerak."""
	_yorliq_qosh("Sotuv Menejr", [
		{"label": "Murojaatlar", "type": "Page", "link_to": "murojaatlar", "color": "Blue"},
	])


def _yorliq_qosh(workspace: str, yorliqlar: list):
	"""Mavjud workspace'ga yorliq qo'shadi (bor bo'lsa tegmaydi).
	qarzdorlik/setup_workspace.py bilan bir xil naqsh."""
	if not frappe.db.exists("Workspace", workspace):
		return
	ws = frappe.get_doc("Workspace", workspace)
	mavjud = {s.label for s in ws.shortcuts}
	qoshildi = []
	for y in yorliqlar:
		if y["label"] in mavjud:
			continue
		ws.append("shortcuts", y)
		qoshildi.append(y["label"])
	if not qoshildi:
		return
	try:
		blocks = json.loads(ws.content or "[]")
	except Exception:
		blocks = []
	bor = {b.get("data", {}).get("shortcut_name") for b in blocks if b.get("type") == "shortcut"}
	for label in qoshildi:
		if label not in bor:
			blocks.append({
				"id": frappe.generate_hash(length=10), "type": "shortcut",
				"data": {"shortcut_name": label, "col": 3},
			})
	ws.content = json.dumps(blocks)
	ws.save(ignore_permissions=True)
	print(f"{workspace}: yorliq qo'shildi -> {qoshildi}")
