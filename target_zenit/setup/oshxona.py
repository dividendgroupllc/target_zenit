# Copyright (c) 2026, Target Zenit
# Oshxona (maktab oshxonasi) hisobini o'rnatish — lokal va production uchun bitta skript.
#
# Idempotent va moslashuvchan: mavjudini topsa ishlatadi/tuzatadi, yo'q bo'lsagina yaratadi.
#
# Nima qiladi:
#   1. CoA: "5230 - Oshxona" guruhi (Indirect Expenses ostida — Kassa'da alohida
#      "Тип контрагента" bo'lib chiqadi), ichida:
#        5231 - Oziq-ovqat mahsulotlari  (mavjud "Oziq-ovqat - TZ" shu nomga o'tadi,
#                                         "5207 - Oziq-ovqat" dublikat unga merge bo'ladi)
#        5232 - Oshxona jihozlari va inventar
#        5233 - Oshxona boshqa xarajatlari
#   2. Stock: "1420 - Oshxona ombori" schyoti. Oshxona warehouse'i:
#        - nomida "oshxona" bor mavjud warehouse topilsa — schyoti 1420 ga to'g'rilanadi
#          (faqat sklad harakati bo'lmasa; bo'lsa — ogohlantiradi, tegmaydi);
#        - topilmasa — "Oshxona ombori" yangi yaratiladi.
#   3. "Oziq-ovqat" Item Group: yo'q bo'lsa yaratiladi; bor bo'lsa default'lari
#      to'ldiriladi (expense = 5231, warehouse = oshxona ombori, cost center).
#   4. Boshlang'ich itemlar va Dona/Litr UOM'lari FAQAT guruh bo'sh bo'lsa yaratiladi
#      (production'da itemlar allaqachon kiritilgan — ularga tegilmaydi).
#
# Ishga tushirish:
#   bench --site <site> execute target_zenit.setup.oshxona.run

import frappe
from erpnext.accounts.doctype.account.account import merge_account, update_account_number

COMPANY = "Target Zenit"
ABBR = "TZ"

OSHXONA_GROUP = f"5230 - Oshxona - {ABBR}"
MAHSULOT_ACC = f"5231 - Oziq-ovqat mahsulotlari - {ABBR}"
STOCK_ACC = f"1420 - Oshxona ombori - {ABBR}"
ITEM_GROUP = "Oziq-ovqat"

BOSHLANGICH_ITEMLAR = [
	("Guruch", "Kg"), ("Un", "Kg"), ("Makaron", "Kg"), ("Shakar", "Kg"), ("Tuz", "Kg"),
	("Grechka", "Kg"), ("Mosh", "Kg"), ("Loviya", "Kg"), ("No'xat", "Kg"),
	("Kartoshka", "Kg"), ("Piyoz", "Kg"), ("Sabzi", "Kg"), ("Pomidor", "Kg"),
	("Bodring", "Kg"), ("Karam", "Kg"), ("Bulg'or qalampiri", "Kg"), ("Lavlagi", "Kg"),
	("Olma", "Kg"), ("Banan", "Kg"), ("Limon", "Kg"),
	("Mol go'shti", "Kg"), ("Qo'y go'shti", "Kg"), ("Tovuq go'shti", "Kg"),
	("Sariyog'", "Kg"), ("O'simlik yog'i", "Litr"), ("Sut", "Litr"), ("Qatiq", "Litr"),
	("Tuxum", "Dona"), ("Non", "Dona"), ("Choy", "Kg"),
]


def run():
	log = []

	# ── 1. Chart of Accounts ──────────────────────────────────────
	_account(log, "5230", "Oshxona", f"5200 - Indirect Expenses - {ABBR}",
		is_group=1, account_type="Indirect Expense")

	if frappe.db.exists("Account", f"Oziq-ovqat - {ABBR}"):
		doc = frappe.get_doc("Account", f"Oziq-ovqat - {ABBR}")
		if doc.parent_account != OSHXONA_GROUP:
			doc.parent_account = OSHXONA_GROUP
			doc.flags.ignore_permissions = True
			doc.save()
			log.append("Ko'chirildi: Oziq-ovqat -> 5230 - Oshxona")
		update_account_number(doc.name, "Oziq-ovqat mahsulotlari", "5231")
		log.append(f"Nomlandi: {MAHSULOT_ACC}")
	elif frappe.db.exists("Account", MAHSULOT_ACC):
		log.append(f"Mavjud: {MAHSULOT_ACC}")
	else:
		frappe.throw("Oziq-ovqat account topilmadi")

	# 5207 dublikat: bo'sh bo'lsa o'chiriladi; yozuvi bo'lsa 5231 ga merge qilinadi.
	# Merge "Account Type ham teng bo'lsin" deb talab qiladi — avval moslab olamiz.
	dublikat = f"5207 - Oziq-ovqat - {ABBR}"
	if frappe.db.exists("Account", dublikat):
		if not frappe.db.exists("GL Entry", {"account": dublikat}):
			frappe.delete_doc("Account", dublikat, ignore_permissions=True)
			log.append("O'chirildi: bo'sh dublikat 5207 - Oziq-ovqat")
		else:
			asosiy = frappe.db.get_value(
				"Account", MAHSULOT_ACC, ["account_type", "account_currency"], as_dict=True
			)
			frappe.db.set_value("Account", dublikat, {
				"account_type": asosiy.account_type or "",
				"account_currency": asosiy.account_currency,
			})
			merge_account(dublikat, MAHSULOT_ACC)
			log.append(f"Merge: 5207 -> {MAHSULOT_ACC}")

	_account(log, "5232", "Oshxona jihozlari va inventar", OSHXONA_GROUP,
		account_type="Expense Account")
	_account(log, "5233", "Oshxona boshqa xarajatlari", OSHXONA_GROUP,
		account_type="Expense Account")
	_account(log, "1420", "Oshxona ombori", f"1400 - Stock Assets - {ABBR}",
		root_type="Asset", account_type="Stock")

	# ── 2. Warehouse: mavjudini moslaymiz, bo'lmasa yaratamiz ─────
	warehouse = _oshxona_warehouse(log)

	# ── 3. Item Group: yaratish yoki default'larini to'ldirish ────
	_item_group(log, warehouse)

	# ── 4. Boshlang'ich itemlar — faqat guruh bo'sh bo'lsa ────────
	if frappe.db.count("Item", {"item_group": ITEM_GROUP}):
		soni = frappe.db.count("Item", {"item_group": ITEM_GROUP})
		log.append(f"Itemlar: guruhda {soni} ta mavjud — yangilari yaratilmadi")
	else:
		for uom, whole in [("Dona", 1), ("Litr", 0)]:
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc(
					{"doctype": "UOM", "uom_name": uom, "must_be_whole_number": whole}
				).insert(ignore_permissions=True)
				log.append(f"UOM: {uom}")
		created = 0
		for nom, uom in BOSHLANGICH_ITEMLAR:
			if frappe.db.exists("Item", nom):
				continue
			frappe.get_doc({
				"doctype": "Item",
				"item_code": nom,
				"item_name": nom,
				"item_group": ITEM_GROUP,
				"stock_uom": uom,
				"is_stock_item": 1,
				"is_sales_item": 0,
				"is_purchase_item": 1,
				"include_item_in_manufacturing": 0,
			}).insert(ignore_permissions=True)
			created += 1
		log.append(f"Itemlar: {created} ta boshlang'ich yaratildi")

	# ── 5. Kassa party_type sinxroni ──────────────────────────────
	from target_zenit.setup.kassa_party_types import sync_party_type_options

	options = sync_party_type_options()
	log.append(
		"Kassa party_type: Oshxona " + ("BOR" if OSHXONA_GROUP in options else "YO'Q!")
	)

	frappe.db.commit()
	print("=== TAYYOR ===")
	for line in log:
		print(" •", line)


def itemlar_omborini_tuzat():
	"""Oziq-ovqat itemlaridagi item-darajali default omborni oshxona omboriga ko'chirish.

	Itemlar UI'dan yaratilganda Stock Settings'dagi default ombor ("Asosiy sklad")
	har itemning o'z Item Default qatoriga yozilib qolgan. Item darajasidagi qiymat
	Item Group default'idan USTUN turadi, shuning uchun guruhga qo'ygan sozlamamiz
	ishlamay qolgan. Bu funksiya item-darajali qatorlarni to'g'rilaydi.

	Ishga tushirish:
	  bench --site <site> execute target_zenit.setup.oshxona.itemlar_omborini_tuzat
	"""
	mavjud = frappe.get_all(
		"Warehouse",
		filters={"company": COMPANY, "is_group": 0, "warehouse_name": ["like", "%oshxona%"]},
		pluck="name",
	)
	if not mavjud:
		frappe.throw("Oshxona warehouse topilmadi — avval run() ishga tushirilsin")
	ombor = mavjud[0]

	frappe.db.sql(
		"""
		UPDATE `tabItem Default` d
		JOIN `tabItem` i ON i.name = d.parent
		SET d.default_warehouse = %(ombor)s
		WHERE d.parenttype = 'Item'
		  AND i.item_group = %(guruh)s
		  AND (d.default_warehouse IS NULL OR d.default_warehouse != %(ombor)s)
		""",
		{"ombor": ombor, "guruh": ITEM_GROUP},
	)
	frappe.db.commit()
	soni = frappe.db.count("Item", {"item_group": ITEM_GROUP})
	print(f"=== TAYYOR === {ITEM_GROUP} guruhidagi {soni} ta itemning default ombori: {ombor}")


def _oshxona_warehouse(log):
	"""Oshxona warehouse'ini topish/yaratish va 1420 schyotga ulash.

	Production'da "Target oshxona ombori  - TZ" allaqachon bor (1410 ga ulangan) —
	uni qayta yaratmaymiz, schyotini to'g'rilaymiz. Schyot almashtirish faqat
	sklad harakati bo'lmaganda xavfsiz, aks holda eski yozuvlar 1410 da,
	yangilari 1420 da bo'lib balans ikkiga bo'linadi.
	"""
	mavjud = frappe.get_all(
		"Warehouse",
		filters={"company": COMPANY, "is_group": 0, "warehouse_name": ["like", "%oshxona%"]},
		fields=["name", "account"],
	)
	if mavjud:
		wh = mavjud[0]
		if wh.account != STOCK_ACC:
			harakat = frappe.db.count(
				"Stock Ledger Entry", {"warehouse": wh.name, "is_cancelled": 0}
			)
			if harakat:
				log.append(
					f"DIQQAT: {wh.name} schyoti {wh.account} da qoldi — "
					f"{harakat} ta sklad yozuvi bor, qo'lda ko'rib chiqing"
				)
			else:
				frappe.db.set_value("Warehouse", wh.name, "account", STOCK_ACC)
				log.append(f"Warehouse: {wh.name} schyoti {STOCK_ACC} ga ulandi")
		else:
			log.append(f"Warehouse: {wh.name} (schyot to'g'ri)")
		return wh.name

	name = f"Oshxona ombori - {ABBR}"
	frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": "Oshxona ombori",
		"company": COMPANY,
		"parent_warehouse": f"All Warehouses - {ABBR}",
		"account": STOCK_ACC,
	}).insert(ignore_permissions=True)
	log.append(f"Warehouse yaratildi: {name}")
	return name


def _item_group(log, warehouse):
	"""Item Group'ni yaratish yoki mavjudining default'larini to'ldirish."""
	cost_center = f"Main - {ABBR}"
	if not frappe.db.exists("Cost Center", cost_center):
		cost_center = frappe.get_cached_value("Company", COMPANY, "cost_center")

	if not frappe.db.exists("Item Group", ITEM_GROUP):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": ITEM_GROUP,
			"parent_item_group": "All Item Groups",
			"item_group_defaults": [{
				"company": COMPANY,
				"expense_account": MAHSULOT_ACC,
				"default_warehouse": warehouse,
				"buying_cost_center": cost_center,
			}],
		}).insert(ignore_permissions=True)
		log.append(f"Item Group yaratildi: {ITEM_GROUP}")
		return

	ig = frappe.get_doc("Item Group", ITEM_GROUP)
	row = next((d for d in ig.item_group_defaults if d.company == COMPANY), None)
	if not row:
		row = ig.append("item_group_defaults", {"company": COMPANY})
	ozgardi = False
	for field, value in (
		("expense_account", MAHSULOT_ACC),
		("default_warehouse", warehouse),
		("buying_cost_center", cost_center),
	):
		if not row.get(field):
			row.set(field, value)
			ozgardi = True
	if ozgardi:
		ig.flags.ignore_permissions = True
		ig.save()
		log.append(f"Item Group default'lari to'ldirildi: {ITEM_GROUP}")
	else:
		log.append(f"Item Group: {ITEM_GROUP} (default'lar joyida)")


def _account(log, number, name, parent, root_type="Expense", account_type="", is_group=0):
	full = f"{number} - {name} - {ABBR}"
	if frappe.db.exists("Account", full):
		return
	frappe.get_doc({
		"doctype": "Account",
		"company": COMPANY,
		"parent_account": parent,
		"account_name": name,
		"account_number": number,
		"is_group": is_group,
		"root_type": root_type,
		"account_type": account_type,
		"account_currency": "USD",
	}).insert(ignore_permissions=True)
	log.append(f"Account: {full}")
