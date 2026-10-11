# Copyright (c) 2026, Target Zenit
# Kassa <-> Sales Invoice bog'lanishlarini BEKOR QILISH (tuzatish skripti).
#
# Sabab (2026-10-12 qarori): o'quvchilarda ikki xil to'lov bor —
#   * har oylik o'quv to'lovi (hech narsaga bog'lanmaydi, qarzdorlik panelida
#     oyma-oy FIFO bilan ko'rinadi);
#   * bir martalik kitob / forma / yotoqxona (buni kassir Kassa'dagi
#     "Nachisleniya" maydonida O'ZI tanlaydi).
# Avvalgi kodda to'lov ochiq nachisleniyalarga avtomatik (FIFO) taqsimlanardi —
# bu noto'g'ri nachisleniyalarni yopib qo'ygan. Kod tuzatildi (avto taqsimot
# olib tashlandi), bu skript esa allaqachon yaratilgan ulanishlarni yechadi.
#
# Ishlatish (serverda):
#   bench --site <sayt> execute target_zenit.qarzdorlik.kassa_tuzatish.korish
#   bench --site <sayt> execute target_zenit.qarzdorlik.kassa_tuzatish.bekor_qil \
#         --kwargs "{'dry_run': 0}"
import frappe
from frappe.utils import flt


def _qatorlar(manba="kassa"):
	"""Bog'langan (PE -> Sales Invoice) qatorlar.
	manba='kassa'  -> faqat Kassa orqali yaratilgan to'lovlar (avto FIFO shular);
	manba='hammasi'-> barcha Payment Entry'lar (qo'lda yozilganlari ham)."""
	join = (
		"JOIN `tabKassa` k ON k.linked_entry = r.parent AND k.docstatus = 1"
		if manba == "kassa"
		else "LEFT JOIN `tabKassa` k ON k.linked_entry = r.parent AND k.docstatus = 1"
	)
	return frappe.db.sql(
		f"""SELECT r.name ref, r.parent pe, r.reference_name si,
		           r.allocated_amount summa, pe.posting_date sana, pe.party,
		           pe.paid_from hisob, k.name kassa, k.sales_invoice tanlangan
		    FROM `tabPayment Entry Reference` r
		    JOIN `tabPayment Entry` pe ON pe.name = r.parent AND pe.docstatus = 1
		    {join}
		    WHERE r.reference_doctype = 'Sales Invoice'
		      AND r.docstatus = 1 AND r.allocated_amount > 0
		      AND pe.party_type = 'Customer'
		    ORDER BY pe.posting_date, r.parent""",
		as_dict=True,
	)


def korish():
	"""DIAGNOSTIKA — hech narsani o'zgartirmaydi. Nima bog'langanini ko'rsatadi."""
	kassa = _qatorlar("kassa")
	hammasi = _qatorlar("hammasi")
	avto = [r for r in kassa if not r.tanlangan]
	qolda = [r for r in kassa if r.tanlangan]
	kassasiz = [r for r in hammasi if not r.kassa]

	print("=" * 72)
	print("SALES INVOICE'GA BOG'LANGAN TO'LOVLAR")
	print("=" * 72)
	print(f"  Kassa orqali, nachisleniya TANLANMAGAN (avto FIFO — XATO): {len(avto):>4} qator")
	print(f"  Kassa orqali, nachisleniya tanlangan (kassir o'zi qilgan): {len(qolda):>4} qator")
	print(f"  Kassa'siz Payment Entry (qo'lda / import):                 {len(kassasiz):>4} qator")
	print(f"  Jami bog'langan qator: {len(hammasi)} | ta'sirlangan SI: "
	      f"{len({r.si for r in hammasi})} ta | summa: {sum(flt(r.summa) for r in hammasi):,.0f}")
	if avto:
		print("\n  Avto bog'langanlar (ilk 20):")
		for r in avto[:20]:
			print(f"    {r.sana}  {str(r.party)[:26]:28} {flt(r.summa):>12,.0f}  ->  {r.si}")
	return {"avto": len(avto), "qolda": len(qolda), "kassasiz": len(kassasiz)}


def bekor_qil(dry_run=1, manba="kassa"):
	"""Bog'lanishlarni yechadi (ERPNext'ning o'z unlink mexanizmi bilan:
	Payment Entry Reference + GL Entry + Payment Ledger tozalanadi, SI qoldig'i
	va statusi qayta hisoblanadi). To'lovning o'zi ham, nachisleniyaning o'zi ham
	BEKOR QILINMAYDI — faqat ular orasidagi bog'lanish uziladi.

	dry_run=1 -> faqat ko'rsatadi; dry_run=0 -> bajaradi.
	manba='kassa' -> faqat Kassa to'lovlari; 'hammasi' -> barchasi."""
	from erpnext.accounts.utils import (
		unlink_ref_doc_from_payment_entries,
		update_voucher_outstanding,
	)

	dry_run = int(dry_run)
	rows = _qatorlar(manba)
	if not rows:
		print("Bog'langan qator yo'q — tuzatish kerak emas.")
		return

	# SI bo'yicha guruhlash
	si_map = {}
	for r in rows:
		si_map.setdefault(r.si, []).append(r)

	print(f"{'KO' + chr(39) + 'RISH (dry_run)' if dry_run else 'BAJARILMOQDA'}: "
	      f"{len(rows)} qator, {len(si_map)} nachisleniya, "
	      f"{sum(flt(r.summa) for r in rows):,.0f} summa")
	frappe.flags.mute_messages = True
	tuzatildi = xato = 0

	for si, refs in si_map.items():
		inv = frappe.db.get_value(
			"Sales Invoice", si,
			["debit_to", "customer", "outstanding_amount", "grand_total", "status"], as_dict=True)
		if not inv:
			continue
		if dry_run:
			print(f"  {si}  qoldiq {flt(inv.outstanding_amount):>12,.0f} / "
			      f"{flt(inv.grand_total):>12,.0f} [{inv.status}] <- "
			      f"{len(refs)} to'lov, {sum(flt(r.summa) for r in refs):,.0f}")
			continue
		try:
			ref_doc = frappe.get_doc("Sales Invoice", si)
			for r in {x.pe for x in refs}:
				unlink_ref_doc_from_payment_entries(ref_doc, r)
			update_voucher_outstanding("Sales Invoice", si, inv.debit_to, "Customer", inv.customer)
			frappe.db.commit()
			yangi = frappe.db.get_value(
				"Sales Invoice", si, ["outstanding_amount", "status"], as_dict=True)
			print(f"  ✓ {si}: qoldiq {flt(inv.outstanding_amount):,.0f} -> "
			      f"{flt(yangi.outstanding_amount):,.0f} [{yangi.status}]")
			tuzatildi += 1
		except Exception as e:
			frappe.db.rollback()
			xato += 1
			print(f"  ✗ {si}: {type(e).__name__}: {str(e)[:120]}")

	frappe.flags.mute_messages = False
	if dry_run:
		print("\nHech narsa o'zgartirilmadi. Bajarish uchun: --kwargs \"{'dry_run': 0}\"")
		return

	qoldi = len(_qatorlar(manba))
	print(f"\nTuzatildi: {tuzatildi} nachisleniya | xato: {xato} | "
	      f"qolgan bog'lanish: {qoldi}")
	print("Keyingi qadam: bench ... execute target_zenit.qarzdorlik.engine.nightly")
