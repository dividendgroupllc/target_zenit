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

# FAQAT KO'RISH ruxsati beriladigan mavjud rollar (yangi rol yaratilmaydi).
# Investor va operator murojaatlar panelini ko'radi — nazorat uchun; yozish
# (izoh, qaror, yo'naltirish) ularga BERILMAYDI (2026-11-04 talabi).
KUZATUV_ROLLAR = ("investor", "Xojakbar_Operator", "Nigora_Moliya")

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
	"Murojaat Sozlamalari": (1, 1, 0, 0),
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

# Kuzatuvchiga ochiladigan doctype'lar — hammasi faqat o'qish
KUZATUV_PERMS = {
	"Murojaat": (1, 0, 0, 0),
	"Murojaat Kategoriyasi": (1, 0, 0, 0),
	"Murojaat Sozlamalari": (1, 0, 0, 0),
}

SAHIFALAR = ("murojaatlar",)


def after_migrate():
	rollarni_yarat()
	kategoriyalarni_yarat()
	ruxsatlarni_ber()
	sahifalarni_och()
	workspace_yarat()
	sotuvga_yorliq()
	sozlamalarni_tola()
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
	# Kuzatuvchilar: rol allaqachon mavjud bo'lsa — faqat o'qish
	for rol in KUZATUV_ROLLAR:
		if not frappe.db.exists("Role", rol):
			continue
		for dt, (r, w, c, d) in KUZATUV_PERMS.items():
			if not frappe.db.exists("DocType", dt):
				continue
			_perm(dt, rol, r, w, c, d)


def _standart_qatorlarni_kochir(doctype: str):
	"""Doctype JSON'idagi ruxsat qatorlarini Custom DocPerm'ga ko'chiradi (idempotent).

	MUHIM, VA BU YERDA BIR MARTA QIMMATGA TUSHGAN: doctype uchun BITTA Custom
	DocPerm qatori paydo bo'lishi bilan Frappe meta'si ruxsatlarni FAQAT shundan
	o'qiydi va app'ning JSON'idagi qatorlarni BUTUNLAY e'tiborsiz qoldiradi
	(`frappe/model/meta.py`: "Reset `permissions` with Custom DocPerm if exists").
	`bench migrate` ularni tiklamaydi.

	Eski kod CEO/Direktor uchun yalang'och Custom DocPerm qatori qo'shardi va
	shu bilan doctype'ning QOLGAN HAMMA rolini jimgina ruxsatdan mahrum qilardi.
	2026-11-11 da aniqlandi: `Telefon Qongirogi` shu yo'l bilan 8 ta rolini
	(jumladan `Telefoniya Agent`) yo'qotgan → telefondagi ilova har yuklashda
	HTTP 403 olgan → 198 ta qo'ng'iroq CRM'ga tushmagan. Rol foydalanuvchida
	TURGAN edi — shuning uchun tashqaridan hammasi joyidek ko'rinardi.

	Shu sabab har qo'shishdan OLDIN standart qatorlar ko'chiriladi, va allaqachon
	buzilgan saytlar ham shu yerda o'z-o'zidan tuzaladi.
	"""
	for p in frappe.get_all("DocPerm", fields="*", filters={"parent": doctype}):
		agar_bor = frappe.db.exists(
			"Custom DocPerm",
			{
				"parent": doctype,
				"role": p.role,
				"permlevel": cint(p.permlevel),
				"if_owner": cint(p.get("if_owner")),
			},
		)
		if agar_bor:
			continue
		qator = frappe.new_doc("Custom DocPerm")
		qator.update(p)
		qator.insert(ignore_permissions=True)


def _perm(doctype: str, rol: str, read: int, write: int, create: int, delete: int):
	nomi = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": rol, "permlevel": 0}, "name"
	)
	bor = frappe.db.get_value(
		"DocPerm", {"parent": doctype, "role": rol, "permlevel": 0}, "name"
	)
	custom_bor = bool(nomi) or bool(
		frappe.db.exists("Custom DocPerm", {"parent": doctype})
	)
	if bor and not custom_bor:
		return      # standart ruxsat JSON'da bor va u hali ham kuchda

	# Custom DocPerm aralashgan zahoti standart qatorlar kuchini yo'qotadi —
	# shuning uchun avval ularni ko'chirib olamiz (tafsilot yuqorida).
	_standart_qatorlarni_kochir(doctype)
	if bor:
		return      # endi standart qator Custom DocPerm'da ham bor

	nomi = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": rol, "permlevel": 0}, "name"
	)
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
		kerak = list(ROLLAR) + [r for r in KUZATUV_ROLLAR if frappe.db.exists("Role", r)]
		yangi = [r for r in kerak if r not in bor]
		if not yangi:
			continue
		for rol in yangi:
			doc.append("roles", {"role": rol})
		doc.save(ignore_permissions=True)


def sozlamalarni_tola():
	"""Standart rahbar BO'SH bo'lsa va yo'nalishda yagona rolli foydalanuvchi
	bo'lsa — uni yozib qo'yamiz. Shunda avto-biriktirish aniq odamga tushadi,
	rahbariyat hech narsa sozlamasa ham ishlaydi. Qo'lda tanlangan qiymatga
	TEGMAYDI."""
	if not frappe.db.exists("DocType", "Murojaat Sozlamalari"):
		return
	from target_zenit.target_zenit.doctype.murojaat.murojaat import rahbarlar

	doc = frappe.get_single("Murojaat Sozlamalari")
	ozgardi = False
	for maydon, yonalish in (("standart_ceo", "CEO"), ("standart_direktor", "Direktor")):
		if doc.get(maydon):
			continue
		nomzodlar = rahbarlar(yonalish)
		if len(nomzodlar) == 1:
			doc.set(maydon, nomzodlar[0])
			ozgardi = True
			print(f"Murojaat: standart {yonalish} -> {nomzodlar[0]}")
	if ozgardi:
		doc.save(ignore_permissions=True)
	frappe.cache().delete_value("murojaat_sozlamalari")


# ====================================================== workspace / yorliqlar
WORKSPACE = "Rahbariyat"

# Workspace kimga ko'rinadi. Kuzatuvchilar ham shu yerda: panelga kirish
# yo'lini bilishlari kerak. Yozish huquqi API tomonda to'xtatiladi.
WORKSPACE_ROLLAR = ("System Manager", "CEO", "Direktor", "Sales Manager",
                    "Sotuv meneger", "investor", "Xojakbar_Operator",
                    "Nigora_Moliya")


def workspace_yarat():
	"""CEO va direktor desk'ga kirganda murojaatlar paneli ko'rinib turishi
	kerak — ular URL yozib yurmaydi. Idempotent."""
	if frappe.db.exists("Workspace", WORKSPACE):
		_yorliq_qosh(WORKSPACE, [
			{"label": "Murojaatlar", "type": "Page", "link_to": "murojaatlar", "color": "Red"},
			{"label": "Murojaat sozlamalari", "type": "DocType",
			 "link_to": "Murojaat Sozlamalari", "color": "Grey"},
		])
		_workspace_rollar()
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
		"roles": [{"role": r} for r in WORKSPACE_ROLLAR],
		"shortcuts": [
			{"label": "Murojaatlar", "type": "Page", "link_to": "murojaatlar", "color": "Red"},
			{"label": "Murojaat kategoriyalari", "type": "DocType",
			 "link_to": "Murojaat Kategoriyasi", "doc_view": "List", "color": "Grey"},
			{"label": "Murojaat sozlamalari", "type": "DocType",
			 "link_to": "Murojaat Sozlamalari", "color": "Grey"},
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


def _workspace_rollar():
	"""Mavjud workspace'ga yetishmayotgan rollarni qo'shadi (o'chirmaydi)."""
	ws = frappe.get_doc("Workspace", WORKSPACE)
	bor = {r.role for r in ws.roles}
	yangi = [r for r in WORKSPACE_ROLLAR
	         if r not in bor and frappe.db.exists("Role", r)]
	if not yangi:
		return
	for rol in yangi:
		ws.append("roles", {"role": rol})
	ws.save(ignore_permissions=True)
	print(f"{WORKSPACE} workspace rollari: +{yangi}")


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
