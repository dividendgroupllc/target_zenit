# Copyright (c) 2026, Target Zenit
# Qarzdorlik engine — qarz hisoblash va ish (case) boshqaruvi.
#
# Qarz manbai — Tolov Rejasi (jadval), lekin jadvaldagi SUMMALAR buxgalteriyadan
# keladi: har oy o'quv to'lovi uchun "O'qitish xizmati" Sales Invoice yoziladi
# (nachisleniya), kitob/forma/yotoqxona uchun esa alohida SI. Reja qatori shu
# nachisleniyaning oynasi: `amount` = nachislangan summa, `reja_amount` =
# shartnomadagi taxminiy oylik. Nachisleniya qilinmagan oy QARZ EMAS (amount=0,
# holat "Rejada" / "Nachisleniya yo'q") — shartnoma qoldig'i alohida ko'rsatiladi.
# To'lovlar (Payment Entry, Journal Entry) oylarga FIFO/bog'lanish bo'yicha
# taqsimlanadi; taqsimot alohida saqlanmaydi — har safar deterministik hisoblanadi.
#
# Kirish nuqtalari:
#   nightly()      — scheduler (daily)
#   on_payment()   — Payment Entry on_submit/on_cancel hook
#   recompute_plan() — bitta rejani qayta hisoblash (TR on_update ham chaqiradi)
from __future__ import annotations

from fnmatch import fnmatch

import frappe
from frappe.utils import add_days, date_diff, flt, getdate, nowdate

from target_zenit.qarzdorlik.setup import OY_NOMI

YOPIQ_STATUSLAR = ("Yopildi - To'landi", "Yopildi - Boshqa")

# Nachisleniya boshlanishidan OLDINGI oylar belgisi: o'quvchi o'quv yili
# o'rtasida qo'shilgan bo'lsa, reja qatorlari sentabrdan turadi, nachisleniya
# esa masalan oktabrdan boshlanadi. Bunday oy "nachisleniya yozilmagan" degan
# ogohlantirishga tushmasligi kerak — u shunchaki o'quvchiga tegishli emas.
IZOH_BOSHLANMAGAN = "Nachisleniya boshlanmagan"


def _settings():
	s = frappe.get_cached_doc("Qarzdorlik Sozlamalari")
	istisno = s.istisno_itemlar if s.istisno_itemlar is not None else "O'qitish xizmati"
	kuni = int(s.tolov_kuni or 0) or 5
	return frappe._dict(
		grace_days=s.grace_days if s.grace_days is not None else 3,
		tolov_kuni=min(max(kuni, 1), 28),
		tolerance=flt(s.tolerance) or 1000,
		min_threshold=flt(s.min_threshold) or 10000,
		buzilgan_vada_limit=s.buzilgan_vada_limit or 2,
		sla_soat=s.sla_soat or 48,
		default_masul=s.default_masul,
		biriktirish=[(r.sinf_pattern, r.masul) for r in (s.biriktirish or [])],
		istisno_itemlar=[x.strip() for x in istisno.split(",") if x.strip()],
	)


def _payments_since(customer: str, from_date) -> float:
	"""Mijozning from_date'dan beri SOF to'lovi, UZS'da (to'lov − qaytim)."""
	tolov, qaytim = _payments_split(customer, from_date)
	return tolov - qaytim


def _payments_split(customer: str, from_date):
	"""(to'lov, qaytim) — UZS'da, alohida. Jadvalda ikkalasi alohida ustunda
	ko'rinishi uchun kerak: "to'langan" brutto, "qaytim" esa qoldiqni oshiradi."""
	tolov = qaytim = 0.0
	for r in _tolov_qatorlari(customer, from_date):
		if r["qaytim"]:
			qaytim += r["uzs"]
		else:
			tolov += r["uzs"]
	return tolov, qaytim


def _tolov_qatorlari(customer: str, from_date) -> list[dict]:
	"""Mijozning BARCHA to'lov harakatlari UZS'da, bitta normallashgan ro'yxat.

	Ikki manba hisobga olinadi:
	  1. Payment Entry — kassa orqali (Receive = to'lov, Pay = qaytim);
	  2. Journal Entry — qo'lda provodka (debitorka hisobiga KREDIT = to'lov,
	     DEBET = qaytim/qo'shimcha hisoblanma). Buxgalter ba'zi to'lovlarni
	     (o'zaro hisob-kitob, bank, ko'chirma) Journal Entry bilan yozadi —
	     ular ham o'quvchining to'lovi sifatida ko'rinishi kerak.

	DIQQAT: kompaniya bazaviy valyutasi USD, shartnomalar esa UZS — shuning uchun
	bazaviy (USD) summalar to'g'ridan-to'g'ri ISHLATILMAYDI:
	  - UZS hisobdan/hisobga: account currency summasi;
	  - USD hisob: o'sha kungi USD->UZS kurs (Currency Exchange) bilan o'giriladi.

	Qaytar qiymat: [{name, doctype, posting_date, uzs (musbat), qaytim, mode, remarks}]
	"""
	if not customer:
		return []
	out = []

	for r in frappe.db.sql(
		"""SELECT name, posting_date, payment_type, paid_from_account_currency f,
		          paid_to_account_currency t, paid_amount, received_amount,
		          remarks, mode_of_payment
		   FROM `tabPayment Entry`
		   WHERE docstatus=1 AND party_type='Customer'
		     AND payment_type IN ('Receive', 'Pay')
		     AND party=%s AND posting_date >= %s""",
		(customer, from_date),
		as_dict=True,
	):
		uzs = _pe_uzs(r)
		if uzs <= 0.005:
			continue
		out.append(
			{
				"name": r.name,
				"doctype": "Payment Entry",
				"posting_date": r.posting_date,
				"uzs": uzs,
				"qaytim": r.payment_type == "Pay",
				"mode": r.mode_of_payment or "",
				"currency": r.f,
				"remarks": (r.remarks or "")[:140],
			}
		)

	# Journal Entry — bitta provodkada shu mijozga bir nechta qator bo'lishi
	# mumkin, shuning uchun hujjat bo'yicha yig'indisi olinadi (sof harakat).
	je_rows = frappe.db.sql(
		"""SELECT jea.parent nom, je.posting_date, je.voucher_type, je.user_remark,
		          jea.account_currency cur,
		          jea.debit_in_account_currency debit_acc,
		          jea.credit_in_account_currency credit_acc,
		          jea.debit debit_base, jea.credit credit_base
		   FROM `tabJournal Entry Account` jea
		   JOIN `tabJournal Entry` je ON je.name = jea.parent
		   JOIN `tabAccount` a ON a.name = jea.account
		   WHERE je.docstatus=1 AND jea.party_type='Customer' AND jea.party=%s
		     AND je.posting_date >= %s AND a.account_type='Receivable'""",
		(customer, from_date),
		as_dict=True,
	)
	je_map = {}
	for r in je_rows:
		# kredit = debitorka kamaydi = to'lov (musbat); debet = aksincha (manfiy)
		if r.cur == "UZS":
			net = flt(r.credit_acc) - flt(r.debit_acc)
		else:
			net = (flt(r.credit_base) - flt(r.debit_base)) * _usd_uzs_rate(r.posting_date)
		d = je_map.setdefault(
			r.nom,
			{
				"name": r.nom,
				"doctype": "Journal Entry",
				"posting_date": r.posting_date,
				"uzs": 0.0,
				"qaytim": False,
				"mode": r.voucher_type or "Journal Entry",
				"currency": r.cur,
				"remarks": (r.user_remark or "")[:140],
			},
		)
		d["uzs"] += net
	for d in je_map.values():
		# FAQAT sof KREDIT to'lov deb olinadi. Sof DEBET — bu QAYTIM EMAS:
		# bazada debitorkaga debet yozadigan provodkalar nachisleniya
		# (o'qish puli hisoblash, opening tuzatish, xodim bilan o'zaro hisob) —
		# ularni qaytim deb hisoblasak o'quvchining to'lovi kamayib, qarzi
		# ikki marta ko'rinardi. Haqiqiy qaytim kassadan beriladi (Payment Entry 'Pay').
		if d["uzs"] <= 0.005:
			continue
		out.append(d)

	out.sort(key=lambda x: (str(x["posting_date"]), x["name"]), reverse=True)
	return out


def _pe_uzs(r) -> float:
	"""Payment Entry qatorining UZS qiymati (yo'nalishdan qat'i nazar, musbat)."""
	if r.f == "UZS":
		return flt(r.paid_amount)
	if r.t == "UZS":
		return flt(r.received_amount)
	return flt(r.paid_amount) * _usd_uzs_rate(r.posting_date)


def _ref_uzs(r) -> float:
	"""Bog'langan summaning UZS qiymati.

	`Payment Entry Reference.allocated_amount` kontragent hisobi valyutasida
	bo'ladi (Receive'da paid_from, Pay'da paid_to). Bazada bu hisob UZS, lekin
	kompaniya bazaviy valyutasi USD — shuning uchun valyutani tekshirmasdan
	ishonib bo'lmaydi.
	"""
	cur = r.f if r.payment_type == "Receive" else r.t
	if cur == "UZS":
		return flt(r.allocated_amount)
	return flt(r.allocated_amount) * _usd_uzs_rate(r.posting_date)


def _linked_allocations(customer: str, from_date):
	"""Sales Invoice -> UZS'da bog'langan summa. (to'lov, qaytim) alohida.

	Faqat submit qilingan Payment Entry'lar. Kassir `Nachisleniya` maydonida
	SI tanlagan bo'lsa, kassa.py o'sha SI'ga reference qo'shadi — shu yerda
	aynan o'sha bog'lanishlar o'qiladi.
	"""
	if not customer:
		return {}, {}
	rows = frappe.db.sql(
		"""SELECT per.reference_name si, pe.payment_type,
		          pe.paid_from_account_currency f, pe.paid_to_account_currency t,
		          pe.posting_date, per.allocated_amount
		   FROM `tabPayment Entry Reference` per
		   JOIN `tabPayment Entry` pe ON pe.name = per.parent
		   WHERE per.reference_doctype='Sales Invoice'
		     AND pe.docstatus=1 AND pe.party_type='Customer'
		     AND pe.payment_type IN ('Receive', 'Pay')
		     AND pe.party=%s AND pe.posting_date >= %s""",
		(customer, from_date),
		as_dict=True,
	)
	tolov, qaytim = {}, {}
	for r in rows:
		hedef = qaytim if r.payment_type == "Pay" else tolov
		hedef[r.si] = hedef.get(r.si, 0.0) + _ref_uzs(r)

	# Journal Entry bilan nachisleniyaga bog'langan summalar (buxgalterlik
	# reconciliation / o'zaro hisob). Ularni ham shu yerda o'qish SHART: aks
	# holda JE summasi ham SI qatorini yopardi, ham o'quv to'lovi poliga
	# tushardi — ya'ni ikki marta hisoblanardi.
	for r in frappe.db.sql(
		"""SELECT jea.reference_name si, je.posting_date, jea.account_currency cur,
		          jea.debit_in_account_currency debit_acc,
		          jea.credit_in_account_currency credit_acc,
		          jea.debit debit_base, jea.credit credit_base
		   FROM `tabJournal Entry Account` jea
		   JOIN `tabJournal Entry` je ON je.name = jea.parent
		   WHERE je.docstatus=1 AND jea.party_type='Customer' AND jea.party=%s
		     AND je.posting_date >= %s
		     AND jea.reference_type='Sales Invoice' AND jea.reference_name IS NOT NULL""",
		(customer, from_date),
		as_dict=True,
	):
		if r.cur == "UZS":
			net = flt(r.credit_acc) - flt(r.debit_acc)
		else:
			net = (flt(r.credit_base) - flt(r.debit_base)) * _usd_uzs_rate(r.posting_date)
		if net > 0.005:            # kredit = nachisleniyani yopgan to'lov
			tolov[r.si] = tolov.get(r.si, 0.0) + net
	return tolov, qaytim


def _si_outstanding(customer: str, from_date) -> dict:
	"""Sales Invoice -> hujjatning O'ZIDAGI qoldiq (UZS).

	Nega kerak: bog'langan Payment Entry'dan tashqari nachisleniya boshqa yo'l
	bilan ham yopilishi mumkin (Journal Entry bilan tuzatish, chegirma, kredit-nota,
	buxgalterlik reconciliation). Faqat Payment Entry bog'lanishiga qarab
	hisoblasak, shunday yopilgan nachisleniya panelda NOTO'G'RI qarz bo'lib
	turardi va qarz yig'uvchilar to'lagan odamga qo'ng'iroq qilardi.
	"""
	if not customer:
		return {}
	rows = frappe.db.sql(
		"""SELECT name, grand_total, outstanding_amount
		   FROM `tabSales Invoice`
		   WHERE docstatus=1 AND customer=%s AND currency='UZS' AND posting_date >= %s""",
		(customer, from_date),
		as_dict=True,
	)
	return {r.name: (flt(r.grand_total), flt(r.outstanding_amount)) for r in rows}


def _tuition_si_months(customer: str, from_date, cfg) -> dict:
	"""O'quv to'lovi Sales Invoice -> "YYYY-MM".

	O'quv to'lovi uchun har oyda bitta SI yoziladi va u rejaning oylik qatori
	bilan AYNI narsani ifodalaydi, shuning uchun qator sifatida qo'shilmaydi
	(istisno itemlar). Lekin kassir to'lovni shu SI'ga bog'lagan bo'lsa, pul
	aynan o'sha oy qatoriga yozilishi kerak — moslik `custom_payment_month`
	bo'yicha, u bo'sh bo'lsa SI sanasi bo'yicha.
	"""
	if not customer or not cfg.istisno_itemlar:
		return {}
	rows = frappe.db.sql(
		"""SELECT DISTINCT si.name, si.custom_payment_month oy, si.posting_date
		   FROM `tabSales Invoice` si
		   JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   WHERE si.docstatus=1 AND si.customer=%s AND si.posting_date >= %s
		     AND sii.item_code IN %s""",
		(customer, from_date, tuple(cfg.istisno_itemlar)),
		as_dict=True,
	)
	out = {}
	for r in rows:
		oy = (r.oy or "").strip()[:7]
		out[r.name] = oy if len(oy) == 7 else getdate(r.posting_date).strftime("%Y-%m")
	return out


def get_payments(customer: str, from_date) -> list[dict]:
	"""To'lovlar ro'yxati UZS'da — Payment Entry va Journal Entry birgalikda,
	qaytimlar manfiy summa bilan (panelda ko'rsatish uchun)."""
	return [
		{
			"name": r["name"],
			"doctype": r["doctype"],
			"posting_date": r["posting_date"],
			"qaytim": 1 if r["qaytim"] else 0,
			"amount_uzs": -r["uzs"] if r["qaytim"] else r["uzs"],
			"currency": r["currency"],
			"mode_of_payment": r["mode"],
			"remarks": r["remarks"],
		}
		for r in _tolov_qatorlari(customer, from_date)
	]


def _usd_uzs_rate(date) -> float:
	rate = frappe.db.get_value(
		"Currency Exchange",
		{"from_currency": "USD", "to_currency": "UZS", "date": ["<=", date]},
		"exchange_rate",
		order_by="date desc",
	)
	return flt(rate) or 12000.0


def _plan_payment_window(tr) -> str:
	"""Rejaga hisoblanadigan to'lovlar boshlanish sanasi: o'quv yili boshidan
	2 oy oldin (avgust/iyul avanslari shu yilga tegishli). Oldingi yil to'lovlari
	aralashmasligi uchun."""
	try:
		start_year = int(str(tr.academic_year).split("-")[0])
	except Exception:
		start_year = getdate(nowdate()).year
	return f"{start_year}-07-01"


# ------------------------------------------------- o'quv nachisleniyasi
def _tuition_accruals(customer: str, from_date, cfg) -> dict:
	"""O'quv to'lovi nachisleniyalari OY bo'yicha: "YYYY-MM" -> {amount, sis, sana}.

	Bitta oyda bir nechta Sales Invoice bo'lishi mumkin (qo'shimcha hisoblash,
	tuzatish, o'rtada kelgan o'quvchi) — ular QO'SHILADI: oyning nachisleniyasi
	shu hujjatlar yig'indisi. Oy `custom_payment_month` ("За какой месяц")
	bo'yicha, u bo'sh bo'lsa hujjat sanasi bo'yicha aniqlanadi.
	"""
	if not customer or not cfg.istisno_itemlar:
		return {}
	rows = frappe.db.sql(
		"""SELECT si.name, si.posting_date, si.custom_payment_month oy,
		          SUM(sii.net_amount) amount
		   FROM `tabSales Invoice` si
		   JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   WHERE si.docstatus=1 AND si.customer=%s AND si.posting_date >= %s
		     AND si.currency='UZS' AND sii.item_code IN %s
		   GROUP BY si.name HAVING amount > 0""",
		(customer, from_date, tuple(cfg.istisno_itemlar)),
		as_dict=True,
	)
	out = {}
	for r in rows:
		oy = (r.oy or "").strip()[:7]
		if len(oy) != 7:
			oy = getdate(r.posting_date).strftime("%Y-%m")
		d = out.setdefault(oy, {"amount": 0.0, "sis": [], "sana": getdate(r.posting_date)})
		d["amount"] += flt(r.amount)
		d["sis"].append(r.name)
		d["sana"] = min(d["sana"], getdate(r.posting_date))
	return out


def _oy_muddati(oy: str, cfg):
	"""Oyning to'lov muddati: shartnoma bo'yicha oyning birinchi besh kunligi,
	ya'ni `tolov_kuni` (sozlamada, default 5)."""
	yil, oy_raqam = oy.split("-")
	return getdate(f"{yil}-{oy_raqam}-{cfg.tolov_kuni:02d}")


def _oy_label(oy: str) -> str:
	yil, oy_raqam = oy.split("-")
	return f"{OY_NOMI.get(int(oy_raqam), oy_raqam)} {yil}"


def sync_tuition(tr, cfg) -> bool:
	"""Oylik qatorlarni HAQIQIY nachisleniya bilan moslashtiradi.

	Har oylik qator uchun:
	  * nachisleniya bor  -> `amount` = nachislangan summa, `nachisleniya` =
	    hujjat raqam(lar)i, `due_date` = oyning to'lov kuni (5-kun);
	  * nachisleniya yo'q -> `amount` = 0 (qarz emas!), shartnomadagi taxminiy
	    summa `reja_amount`da saqlanadi va panelda "Reja" sifatida ko'rinadi.

	Nachisleniyasi bor, lekin rejada qatori yo'q oy (grant/investor farzandlari,
	o'quv yili o'rtasida kelganlar) uchun yangi qator ochiladi.

	Qator FIFO polidan chiqarilmaydi: o'quv to'lovi ko'pincha nachisleniyaga
	bog'lanmagan holda tushadi, shuning uchun oylik qatorlar (manba_hujjat YO'Q)
	avvalgidek FIFO bilan yopiladi — `nachisleniya` faqat summa manbai.
	"""
	acc = _tuition_accruals(tr.customer, _plan_payment_window(tr), cfg)
	changed = False

	# Eski kod o'quv nachisleniyasini `manba_hujjat` bilan qator qilgan edi —
	# uni oylik qatorga aylantiramiz (aks holda u SI qatori sifatida faqat
	# bog'langan to'lov bilan yopilardi va FIFO'dan chetda qolardi).
	for r in tr.oylar:
		if r.manba_hujjat and r.manba_hujjat in {si for a in acc.values() for si in a["sis"]}:
			frappe.db.set_value(
				"Tolov Rejasi Oyi",
				r.name,
				{"manba_hujjat": "", "nachisleniya": r.manba_hujjat, "izoh": "O'quv to'lovi"},
				update_modified=False,
			)
			r.manba_hujjat = ""
			r.nachisleniya = r.nachisleniya or ""
			changed = True

	oylar = {}
	for r in tr.oylar:
		if r.manba_hujjat or r.holat == "Bekor" or not r.due_date:
			continue
		oylar.setdefault(getdate(r.due_date).strftime("%Y-%m"), []).append(r)

	birinchi_oy = min(acc) if acc else None
	for oy, qatorlar in sorted(oylar.items()):
		a = acc.pop(oy, None)
		for i, r in enumerate(qatorlar):
			vals = {}
			# Muddat hamma oyda bir xil qoidada — shartnomadagi to'lov kuni
			# (kelgusi oylarda ham ko'rinib tursin).
			muddat = _oy_muddati(oy, cfg)
			if getdate(r.due_date) != muddat:
				vals["due_date"] = muddat
			# Shartnomadagi taxminiy summa bir marta saqlanadi (keyin o'zgarmaydi)
			if not flt(r.reja_amount) and flt(r.amount):
				vals["reja_amount"] = flt(r.amount)
			if a and i == 0:
				nach = ", ".join(sorted(a["sis"]))
				if abs(flt(r.amount) - flt(a["amount"])) > 0.005:
					vals["amount"] = flt(a["amount"])
				if (r.nachisleniya or "") != nach:
					vals["nachisleniya"] = nach
				if r.izoh == IZOH_BOSHLANMAGAN:
					vals["izoh"] = "O'quv to'lovi"
			else:
				# nachisleniya yo'q (yoki takroriy qator) -> summa 0, qarz emas
				if flt(r.amount):
					vals["amount"] = 0
				if r.nachisleniya:
					vals["nachisleniya"] = ""
				# Nachisleniya boshlanishidan oldingi oy — ogohlantirish emas
				boshlanmagan = bool(birinchi_oy) and oy < birinchi_oy
				izoh = IZOH_BOSHLANMAGAN if boshlanmagan else ""
				if boshlanmagan and r.izoh != IZOH_BOSHLANMAGAN:
					vals["izoh"] = izoh
				elif not boshlanmagan and r.izoh == IZOH_BOSHLANMAGAN:
					vals["izoh"] = ""
			if vals:
				frappe.db.set_value("Tolov Rejasi Oyi", r.name, vals, update_modified=False)
				for k, v in vals.items():
					r.set(k, v)
				changed = True

	# Rejada qatori yo'q nachisleniyalar -> yangi oylik qator
	for oy, a in sorted(acc.items()):
		tr.append(
			"oylar",
			{
				"oy_label": _oy_label(oy),
				"due_date": _oy_muddati(oy, cfg),
				"amount": flt(a["amount"]),
				"holat": "Kutilmoqda",
				"nachisleniya": ", ".join(sorted(a["sis"])),
				"izoh": "O'quv to'lovi (rejada yo'q oy)",
			},
		)
		changed = True

	return changed


# ------------------------------------------------- SI nachisleniya sinxroni
def sync_charges(tr) -> bool:
	"""O'qish pulidan BOSHQA nachisleniyalarni (Kitob, Forma, Yotoqxona...)
	Sales Invoice'lardan reja qatorlariga sinxronlaydi.

	O'quv to'lovi nachisleniyasi bu yerda EMAS — u oylik qatorlarga
	`sync_tuition()` orqali tushadi (oyiga bitta qator, FIFO bilan yopiladi).

	- O'qish puli ('istisno itemlar') olinmaydi — u oylik qatorlarda allaqachon bor.
	- Har SI -> bitta qator (itemlar nomi bilan), due_date = SI sanasi,
	  manba_hujjat = SI raqami (idempotent).
	- SI bekor qilingan bo'lsa -> qator Bekor.
	Qaytaradi: qatorlar o'zgardimi."""
	cfg = _settings()
	rows = frappe.db.sql(
		"""SELECT si.name, si.posting_date, si.currency,
		          GROUP_CONCAT(DISTINCT sii.item_code ORDER BY sii.idx SEPARATOR ' + ') itemlar,
		          SUM(sii.net_amount) amount
		   FROM `tabSales Invoice` si
		   JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   WHERE si.docstatus=1 AND si.customer=%s AND si.posting_date >= %s
		     AND si.currency='UZS' AND sii.item_code NOT IN %s
		   GROUP BY si.name HAVING amount > 0""",
		(tr.customer, _plan_payment_window(tr), tuple(cfg.istisno_itemlar) or ("",)),
		as_dict=True,
	)
	mavjud = {r.manba_hujjat: r for r in tr.oylar if r.manba_hujjat}
	changed = False

	for si in rows:
		label = f"{si.itemlar} ({getdate(si.posting_date).strftime('%d.%m.%Y')})"
		old = mavjud.pop(si.name, None)
		if old:
			if flt(old.amount) != flt(si.amount) or old.oy_label != label:
				frappe.db.set_value(
					"Tolov Rejasi Oyi",
					old.name,
					{"amount": flt(si.amount), "oy_label": label, "due_date": si.posting_date},
					update_modified=False,
				)
				changed = True
			continue
		tr.append(
			"oylar",
			{
				"oy_label": label,
				"due_date": si.posting_date,
				"amount": flt(si.amount),
				"holat": "Kutilmoqda",
				"manba_hujjat": si.name,
				"izoh": "Nachisleniya (SI)",
			},
		)
		changed = True

	# SI bekor bo'lgan/o'chirilgan qatorlar
	for r in mavjud.values():
		if r.holat != "Bekor":
			frappe.db.set_value("Tolov Rejasi Oyi", r.name, "holat", "Bekor", update_modified=False)
			changed = True

	if any(not r.name for r in tr.oylar):
		tr.save(ignore_permissions=True)
	return changed


# ------------------------------------------------------------- taqsimot
def _taqsimot(tr, rows, jami_tolov: float, jami_qaytim: float):
	"""To'lovlarni reja qatorlariga taqsimlaydi.

	Qoida (2026-10-12 qarori — `kassa.py` dagi mantiq bilan bir xil):

	  * **Kitob / Forma / Yotoqxona** (SI asosidagi qator) — FAQAT kassir o'sha
	    Sales Invoice'ga bog'lab submit qilgan to'lov hisoblanadi. Bog'lanmagan
	    bo'lsa qator to'lanmagan qoladi. Sabab: o'quvchida ikki xil to'lov bor
	    va avtomatik (FIFO) taqsimot noto'g'ri nachisleniyani yopib qo'yardi.
	  * **O'quv to'lovi SI'siga** bog'langan to'lov — o'sha SI oyining qatoriga
	    yoziladi (o'quv SI'si qator sifatida qo'shilmaydi, chunki oylik qator
	    allaqachon shu oyni ifodalaydi).
	  * **Bog'lanmagan to'lov** — oylik qatorlarga FIFO, eskisidan boshlab.

	Bog'langan pul FIFO polidan chiqariladi (ikki marta hisoblanmasligi uchun),
	lekin egasi topilmasa polga QAYTARILADI — pul jadvaldan yo'qolmasligi kerak.

	Qaytaradi: (alloc_map, qaytim_map, avans)
	"""
	cfg = _settings()
	window = _plan_payment_window(tr)
	# Qator sifatida qo'shilgan o'quv nachisleniyasi "oyga bog'lash" bosqichida
	# QAYTA ishlanmasligi kerak — aks holda bitta pul ikki marta hisoblanardi.
	qator_manba = {r.manba_hujjat for r in rows if r.manba_hujjat}
	oquv_si = {
		si: oy
		for si, oy in _tuition_si_months(tr.customer, window, cfg).items()
		if si not in qator_manba
	}
	return _taqsimla(
		rows,
		jami_tolov,
		jami_qaytim,
		*_linked_allocations(tr.customer, window),
		oquv_si,
		_si_outstanding(tr.customer, window),
	)


def _taqsimla(
	rows,
	jami_tolov: float,
	jami_qaytim: float,
	linked_t: dict,
	linked_q: dict,
	tuition_si: dict,
	si_qoldiq: dict,
):
	"""Taqsimotning toza (bazaga murojaat qilmaydigan) yadrosi.

	Bazadan ajratilgani ataylab: bu pul hisobi, shuning uchun alohida
	test qilinishi kerak — har bir qoida va chegara holati tekshiriladi.
	"""
	si_rows = [r for r in rows if r.manba_hujjat]
	oy_rows = [r for r in rows if not r.manba_hujjat]

	alloc, qaytim = {}, {}
	pool = jami_tolov - sum(linked_t.values())
	q_pool = jami_qaytim - sum(linked_q.values())
	ishlangan = set()

	# 1) SI qatorlari — faqat bog'langan to'lov, qaytim ham faqat bog'langan
	for r in si_rows:
		si = r.manba_hujjat
		ishlangan.add(si)
		got = linked_t.get(si, 0.0)
		a = min(got, flt(r.amount))

		# Buxgalteriya bilan solishtirish: nachisleniya Journal Entry yoki
		# kredit-nota bilan yopilgan bo'lsa, bog'langan to'lov bo'lmasa ham
		# qator yopilishi kerak. Bu farq POLDAN ayirilmaydi — u mijoz to'lovi
		# emas, shuning uchun o'quv to'lovi polini kamaytirmasligi kerak.
		jami_qold = si_qoldiq.get(si)
		if jami_qold:
			yopilgan = max(jami_qold[0] - jami_qold[1], 0.0)
			a = max(a, min(yopilgan, flt(r.amount)))

		alloc[r.name] = a
		pool += got - min(got, flt(r.amount))   # qator summasidan ortig'i polga qaytadi

		qq = linked_q.get(si, 0.0)
		q = min(qq, a)
		qaytim[r.name] = q
		q_pool += qq - q

	# 2) O'quv SI'siga bog'langan pul -> o'sha oyning qatoriga
	oy_map = {getdate(r.due_date).strftime("%Y-%m"): r for r in oy_rows}
	bogli_oy = {}
	for si, oy in tuition_si.items():
		ishlangan.add(si)
		got = linked_t.get(si, 0.0)
		qq = linked_q.get(si, 0.0)
		r = oy_map.get(oy)
		if not r:
			pool += got                      # bu oyning qatori yo'q -> umumiy polga
			q_pool += qq
			continue
		bor = bogli_oy.get(r.name, 0.0)
		a = min(got, max(flt(r.amount) - bor, 0.0))
		bogli_oy[r.name] = bor + a
		pool += got - a
		q = min(qq, a)
		qaytim[r.name] = qaytim.get(r.name, 0.0) + q
		q_pool += qq - q

	# 3) Bog'langan, lekin bu rejada egasi yo'q pul (oyna tashqarisidagi SI va h.k.)
	for si, got in linked_t.items():
		if si not in ishlangan:
			pool += got
	for si, qq in linked_q.items():
		if si not in ishlangan:
			q_pool += qq

	# 3b) Buxgalteriyada yopilgan o'quv nachisleniyasi (Journal Entry, kredit-nota —
	#     masalan grant/investor farzandlari). SI qatorlaridagi himoya to'rining
	#     o'quv to'lovi uchun aynasi. FIFO'dan OLDIN qo'yiladi: yopilgan oy
	#     band hisoblanadi, shuning uchun haqiqiy pul keyingi ochiq oyga tushadi.
	#     Bu summa POLDAN AYIRILMAYDI — u mijoz to'lovi emas.
	for r in oy_rows:
		nach = [x.strip() for x in str(r.get("nachisleniya") or "").split(",") if x.strip()]
		jami = qold = 0.0
		topildi = False
		for si in nach:
			t = si_qoldiq.get(si)
			if t:
				topildi = True
				jami += t[0]
				qold += t[1]
		if not topildi:
			continue
		yopilgan = min(max(jami - qold, 0.0), flt(r.amount))
		bor = bogli_oy.get(r.name, 0.0)
		if yopilgan > bor:
			bogli_oy[r.name] = yopilgan

	# 4) Bog'lanmagan pul — oylik qatorlarga FIFO
	for r in oy_rows:
		bor = bogli_oy.get(r.name, 0.0)
		a = min(max(pool, 0.0), max(flt(r.amount) - bor, 0.0))
		alloc[r.name] = bor + a
		pool -= a

	# 5) Bog'lanmagan qaytim — AVVAL taqsimlanmagan puldan (avans), keyin
	#    oxirgi to'langan OYLIK qatordan (LIFO).
	#
	#    Avans birinchi bo'lishi SHART: odatda qaytim aynan ORTIQCHA to'langan
	#    puldan beriladi (kassir ko'proq olgan, qolganini qaytargan). Uni oy
	#    qatoridan yechsak, to'liq to'langan oy yana "to'lanmagan" bo'lib
	#    ko'rinardi — holbuki o'sha oy uchun pul to'liq tushgan va ortiqchasi
	#    avansda turibdi. (2026-10-15: Kamiljonov X. — 53.83 mln to'lov,
	#    130 ming qaytim, 42 mln avans; panel 130 mingni qarz deb ko'rsatardi.)
	#
	#    SI qatorlariga tegilmaydi: ularning qaytimi faqat bog'langan bo'lishi kerak.
	left_q = max(q_pool, 0.0)
	avansdan = min(left_q, max(pool, 0.0))
	pool -= avansdan
	left_q -= avansdan
	for r in reversed(oy_rows):
		bor = qaytim.get(r.name, 0.0)
		take = min(left_q, max(alloc.get(r.name, 0.0) - bor, 0.0))
		qaytim[r.name] = bor + take
		left_q -= take
	if left_q > 0.005 and oy_rows:           # qaytim to'lovdan ko'p (kam uchraydi)
		b = oy_rows[0].name
		qaytim[b] = qaytim.get(b, 0.0) + left_q

	return alloc, qaytim, max(pool, 0.0)


# ---------------------------------------------------------------- recompute
def recompute_plan(tr_name: str, sync_case: bool = True):
	"""Bitta Tolov Rejasi: SI nachisleniya sinxroni + FIFO taqsimot ->
	qatorlar + jami maydonlar. Hamma yozuv db.set_value bilan
	(on_update rekursiyasi yo'q)."""
	tr = frappe.get_doc("Tolov Rejasi", tr_name)
	if tr.holat == "Bekor":
		return None

	frappe.flags.qarz_engine = True
	try:
		cfg = _settings()
		# Tartib muhim: avval o'quv nachisleniyasi (eski `manba_hujjat` qatorlarini
		# oylik qatorga aylantiradi), keyin kitob/forma sinxroni — aks holda
		# sync_charges o'sha qatorlarni "SI yo'q" deb Bekor qilib qo'yardi.
		changed = sync_tuition(tr, cfg)
		changed = sync_charges(tr) or changed
		if changed:
			tr = frappe.get_doc("Tolov Rejasi", tr_name)  # yangi qatorlar bilan qayta o'qish
		jami_tolov, jami_qaytim = _payments_split(tr.customer, _plan_payment_window(tr))
		today = getdate(nowdate())

		rows = sorted(
			[r for r in tr.oylar if r.holat != "Bekor"], key=lambda r: getdate(r.due_date)
		)
		alloc_map, qaytim_map, avans = _taqsimot(tr, rows, jami_tolov, jami_qaytim)

		qarz = 0.0
		eng_eski = None
		for r in rows:
			amount = flt(r.amount)
			alloc = alloc_map.get(r.name, 0.0)
			qayt = qaytim_map.get(r.name, 0.0)
			outstanding = amount - alloc + qayt
			muddat = getdate(r.due_date)

			if amount <= 0.005:
				# Nachisleniya qilinmagan oy — QARZ EMAS. Kelgusi oy "Rejada",
				# o'tgan oy esa "Nachisleniya yo'q" (buxgalter ko'rib tuzatishi uchun).
				# O'quvchi qo'shilishidan oldingi oylar ham oddiy "Rejada".
				holat = (
					"Rejada"
					if (muddat > today or r.izoh == IZOH_BOSHLANMAGAN)
					else "Nachisleniya yo'q"
				)
			elif outstanding <= 0.005:
				holat = "To'landi"
			elif alloc - qayt > 0:
				holat = "Qisman"
			elif muddat <= today:
				holat = "Muddati keldi"
			else:
				holat = "Kutilmoqda"

			if amount > 0.005 and muddat <= today and outstanding > 0.005:
				qarz += outstanding
				if eng_eski is None:
					eng_eski = muddat

			if (
				flt(r.paid_amount) != alloc
				or flt(r.qaytim) != qayt
				or flt(r.outstanding) != outstanding
				or r.holat != holat
			):
				frappe.db.set_value(
					"Tolov Rejasi Oyi",
					r.name,
					{"paid_amount": alloc, "qaytim": qayt,
					 "outstanding": outstanding, "holat": holat},
					update_modified=False,
				)

		jami = sum(flt(r.amount) for r in rows)
		# "Jami to'langan" — qatorlarga HAQIQATDA tushgan pul. Oldin bu barcha
		# to'lovlar (jami bilan cheklangan) edi; endi bog'lanmagan kitob/forma
		# puli qatorga tushmaydi, shuning uchun taqsimot natijasi olinadi —
		# aks holda jadval qatorlari bilan jami bir-biriga mos kelmasdi.
		frappe.db.set_value(
			"Tolov Rejasi",
			tr.name,
			{
				"jami_hisoblangan": jami,
				"jami_tolangan": sum(alloc_map.values()),
				"jami_qaytim": jami_qaytim,
				"qarz_bugun": qarz,
				"eng_eski_muddat": eng_eski,
				"avans_summa": avans,
			},
			update_modified=False,
		)

		if sync_case:
			_sync_case(tr, qarz, eng_eski)
		return qarz
	finally:
		frappe.flags.qarz_engine = False


# ---------------------------------------------------------------- xulosa
def _charge_breakdown(rows) -> list[dict]:
	"""Qo'shimcha nachisleniyalar (Kitob, Forma, Yotoqxona...) item bo'yicha.

	Bitta Sales Invoice'da bir nechta item bo'lishi mumkin (Kitob + Forma), reja
	qatori esa bitta — shuning uchun to'langan/qoldiq item ulushiga proportsional
	taqsimlanadi. Panelda "Kitob uchun buncha nachislangan, buncha to'langan"
	deb ko'rsatish uchun kerak.
	"""
	si_rows = [r for r in rows if r.manba_hujjat]
	if not si_rows:
		return []
	items = {}
	for d in frappe.db.sql(
		"""SELECT parent, item_code, SUM(net_amount) amount
		   FROM `tabSales Invoice Item` WHERE parent IN %s
		   GROUP BY parent, item_code""",
		(tuple({r.manba_hujjat for r in si_rows}),),
		as_dict=True,
	):
		items.setdefault(d.parent, []).append((d.item_code, flt(d.amount)))

	out = {}
	for r in si_rows:
		lst = items.get(r.manba_hujjat) or [(r.oy_label, flt(r.amount))]
		jami = sum(a for _, a in lst) or 1.0
		for nom, a in lst:
			ulush = a / jami
			d = out.setdefault(
				nom,
				{"nom": nom, "nachislangan": 0.0, "tolangan": 0.0,
				 "qaytim": 0.0, "qoldiq": 0.0, "qarz": 0.0, "soni": 0},
			)
			d["nachislangan"] += a
			d["tolangan"] += flt(r.paid_amount) * ulush
			d["qaytim"] += flt(r.qaytim) * ulush
			d["qoldiq"] += flt(r.outstanding) * ulush
			if getdate(r.due_date) <= getdate(nowdate()):
				d["qarz"] += flt(r.outstanding) * ulush
			d["soni"] += 1
	return sorted(out.values(), key=lambda x: -x["nachislangan"])


def plan_xulosa(tr) -> dict:
	"""Panel uchun batafsil xulosa — hammasi HAQIQIY nachisleniya asosida:

	  * `oquv` — o'quv to'lovi: shartnoma summasi, shundan nachislangani,
	    to'langani, muddati kelgan qarz, hali nachislanmagan qoldiq;
	  * `qoshimcha` — kitob/forma/yotoqxona: item bo'yicha nachislangan/to'langan;
	  * `oylar` — oyma-oy kesim (nachislangan, to'langan, qoldiq, muddat, holat);
	  * `jami` — ikkisining yig'indisi + avans.
	"""
	today = getdate(nowdate())
	rows = [r for r in tr.oylar if r.holat != "Bekor"]
	oy_rows = sorted(
		[r for r in rows if not r.manba_hujjat], key=lambda r: getdate(r.due_date)
	)

	oquv = {
		"shartnoma": flt(tr.yakuniy_summa) or sum(flt(r.reja_amount) for r in oy_rows),
		"nachislangan": 0.0, "tolangan": 0.0, "qaytim": 0.0, "qoldiq": 0.0,
		"qarz": 0.0, "muddati_kelmagan": 0.0, "nachislangan_oy": 0,
		"nachisleniyasiz_oy": 0, "nachisleniyasiz_summa": 0.0, "kelgusi_oy": 0,
		"kelgusi_summa": 0.0,
	}
	oylar = []
	for r in oy_rows:
		amount = flt(r.amount)
		qold = flt(r.outstanding)
		muddat = getdate(r.due_date)
		kechikish = date_diff(today, muddat) if (amount > 0.005 and qold > 0.005 and muddat <= today) else 0
		oylar.append(
			{
				"oy_label": r.oy_label,
				"due_date": r.due_date,
				"nachislangan": amount,
				"reja": flt(r.reja_amount),
				"tolangan": flt(r.paid_amount),
				"qaytim": flt(r.qaytim),
				"qoldiq": qold,
				"holat": r.holat,
				"nachisleniya": r.nachisleniya or "",
				"kechikish": kechikish,
			}
		)
		if amount > 0.005:
			oquv["nachislangan"] += amount
			oquv["tolangan"] += flt(r.paid_amount)
			oquv["qaytim"] += flt(r.qaytim)
			oquv["qoldiq"] += qold
			oquv["nachislangan_oy"] += 1
			if muddat <= today:
				oquv["qarz"] += qold
			else:
				oquv["muddati_kelmagan"] += qold
		elif muddat <= today:
			oquv["nachisleniyasiz_oy"] += 1
			oquv["nachisleniyasiz_summa"] += flt(r.reja_amount)
		else:
			oquv["kelgusi_oy"] += 1
			oquv["kelgusi_summa"] += flt(r.reja_amount)

	# Shartnomadan hali nachislanmagan qism (kelgusi oylar + yozilmagan oylar)
	oquv["nachislanmagan"] = max(oquv["shartnoma"] - oquv["nachislangan"], 0.0)

	qoshimcha = _charge_breakdown(rows)
	q_jami = {
		k: sum(x[k] for x in qoshimcha)
		for k in ("nachislangan", "tolangan", "qaytim", "qoldiq", "qarz")
	} if qoshimcha else dict.fromkeys(
		("nachislangan", "tolangan", "qaytim", "qoldiq", "qarz"), 0.0
	)

	return {
		"oquv": oquv,
		"oylar": oylar,
		"qoshimcha": qoshimcha,
		"qoshimcha_jami": q_jami,
		"jami": {
			"nachislangan": oquv["nachislangan"] + q_jami["nachislangan"],
			"tolangan": oquv["tolangan"] + q_jami["tolangan"],
			"qaytim": oquv["qaytim"] + q_jami["qaytim"],
			"qoldiq": oquv["qoldiq"] + q_jami["qoldiq"],
			"qarz": oquv["qarz"] + q_jami["qarz"],
			"avans": flt(tr.avans_summa),
		},
	}


# ------------------------------------------------------- mas'ul (oxirgi ishlagan)
# Qoida (2026-10-23): qarz ishining mas'uli — u bilan OXIRGI MARTA ISHLAGAN
# xodim. Uch manba hisobga olinadi:
#   * javob berilgan telefon qo'ng'irog'i (Telefon Qongirogi, suhbat > 0);
#   * panelda yozilgan qo'ng'iroq natijasi — Aloqa Yozuvi (natijasidan qat'i
#     nazar: "Javob yo'q" ham ish qilingani, menejer shu ish ustida ishlayapti);
#   * Qarz Ishi'ga qo'lda yozilgan komment.
# Eng YANGISI g'olib. Shu bilan ota-ona bilan aloqani boshlagan odam uni
# oxirigacha olib boradi va ish egasiz qolmaydi.
MASUL_ROLLAR = {"sales manager", "sales user", "sotuv meneger"}


def case_raqamlar(student: str, payer_phone=None) -> list[str]:
	"""Shu o'quvchiga tegishli normal raqamlar: to'lovchi + ota-onalar + o'quvchi.

	Telefon Qongirogi `normal_telefon` ("998XXXXXXXXX") bo'yicha saqlanadi,
	shuning uchun qidiruv ham shu ko'rinishda ketadi."""
	from target_zenit.telefoniya.utils import normalize_phone

	xom = [payer_phone]
	st = frappe.db.get_value(
		"Student", student,
		["student_mobile_number", "custom_payer_phone"], as_dict=True
	) or frappe._dict()
	xom += [st.custom_payer_phone, st.student_mobile_number]
	xom += frappe.db.sql_list(
		"""SELECT g.mobile_number FROM `tabStudent Guardian` sg
		   JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parenttype = 'Student' AND sg.parent = %s
		     AND g.mobile_number IS NOT NULL AND g.mobile_number != ''""",
		(student,),
	)
	out = []
	for x in xom:
		n = normalize_phone(x)
		if n and n not in out:
			out.append(n)
	return out


def _masul_bola_oladi(user: str | None) -> bool:
	"""Bu foydalanuvchini mas'ul qilib qo'yish mumkinmi.

	Xizmat hisoblari (Administrator, telefoniya integratsiyasi) va o'chirilgan
	foydalanuvchilarga ish biriktirilmaydi — aks holda ish ko'rinmas bo'lib
	qolardi. Rol nomi boshqacha bo'lishi mumkin, shuning uchun allaqachon
	mas'ul bo'lib ishlayotgan foydalanuvchi ham qabul qilinadi."""
	if not user or user in ("Administrator", "Guest"):
		return False
	if not frappe.db.get_value("User", user, "enabled"):
		return False
	if MASUL_ROLLAR & {r.lower() for r in frappe.get_roles(user)}:
		return True
	return bool(frappe.db.exists("Qarz Ishi", {"masul": user}))


def oxirgi_ishlagan(qarz_ishi: str, student: str | None = None, payer_phone: str | None = None):
	"""(user, vaqt, manba) — bu ish ustida oxirgi marta ishlagan xodim.

	Solishtiriladigan manbalar (eng yangisi olinadi):
	  * `Aloqa Yozuvi` — panelda yozilgan qo'ng'iroq natijasi/komment
	    (natijasi "Gaplashildi" bo'lishi SHART EMAS: javob bo'lmagani ham
	    qilingan ish, menejer shu mijoz bilan shug'ullanyapti);
	  * `Comment` — Qarz Ishi'ga qo'lda yozilgan izoh (tizim yozgan "Info"
	    izohlari hisobga olinmaydi);
	  * javob berilgan telefon qo'ng'irog'i (suhbat vaqti > 0) — raqam bo'yicha
	    shu o'quvchiga bog'langan.
	"""
	nomzodlar = []

	ay = frappe.get_all(
		"Aloqa Yozuvi",
		filters={"qarz_ishi": qarz_ishi},
		fields=["masul", "vaqt"],
		order_by="vaqt desc",
		limit_page_length=5,
	)
	for r in ay:
		if r.masul and r.vaqt:
			nomzodlar.append((r.vaqt, r.masul, "Aloqa Yozuvi"))
			break

	for r in frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": "Qarz Ishi",
			"reference_name": qarz_ishi,
			"comment_type": "Comment",
		},
		fields=["owner", "creation"],
		order_by="creation desc",
		limit_page_length=5,
	):
		if r.owner and r.owner != "Administrator":
			nomzodlar.append((r.creation, r.owner, "Komment"))
			break

	raqamlar = case_raqamlar(student, payer_phone) if student else []
	if raqamlar:
		for r in frappe.get_all(
			"Telefon Qongirogi",
			filters={
				"normal_telefon": ["in", raqamlar],
				"tugash_sababi": "Javob berildi",
				"suhbat_vaqti": [">", 0],
			},
			fields=["foydalanuvchi", "xodim", "boshlandi"],
			order_by="boshlandi desc",
			limit_page_length=10,
		):
			user = r.foydalanuvchi or (
				frappe.db.get_value("Employee", r.xodim, "user_id") if r.xodim else None
			)
			if user and r.boshlandi:
				nomzodlar.append((r.boshlandi, user, "Telefon Qongirogi"))
				break

	if not nomzodlar:
		return None, None, None
	vaqt, user, manba = max(nomzodlar, key=lambda x: str(x[0]))
	return user, vaqt, manba


def masul_yangila(qarz_ishi: str, izoh: bool = True) -> str | None:
	"""Ishni oxirgi gaplashgan xodimga biriktiradi. Qaytaradi: yangi mas'ul yoki None."""
	qi = frappe.db.get_value(
		"Qarz Ishi", qarz_ishi,
		["name", "student", "payer_phone", "masul", "ishlov_status"], as_dict=True,
	)
	if not qi or qi.ishlov_status in YOPIQ_STATUSLAR:
		return None

	user, vaqt, manba = oxirgi_ishlagan(qi.name, qi.student, qi.payer_phone)
	if not user or user == qi.masul or not _masul_bola_oladi(user):
		return None

	frappe.db.set_value("Qarz Ishi", qi.name, "masul", user, update_modified=False)
	if izoh:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Qarz Ishi",
				"reference_name": qi.name,
				"content": (
					f"Mas'ul avtomatik o'zgardi: {qi.masul or '—'} -> {user} "
					f"(oxirgi ishlagan — {manba}, {str(vaqt)[:16]})"
				),
			}
		).insert(ignore_permissions=True)
	return user


def masullarni_yangila() -> dict:
	"""Hamma ochiq ish bo'yicha mas'ulni oxirgi gaplashganga moslash (kechasi).

	Kun davomida hook'lar darhol yangilaydi; bu — xavfsizlik to'ri (hook
	ishlamay qolgan, qo'lda kiritilgan yoki eski qo'ng'iroq keyin yuklangan
	holatlar uchun)."""
	ozgardi = 0
	ishlar = frappe.get_all(
		"Qarz Ishi",
		filters={"ishlov_status": ["not in", list(YOPIQ_STATUSLAR)]},
		pluck="name",
	)
	for name in ishlar:
		try:
			if masul_yangila(name):
				ozgardi += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"qarzdorlik masul_yangila: {name}")
	return {"tekshirildi": len(ishlar), "ozgardi": ozgardi}


def qongiroq_masul(doc, method=None):
	"""Telefon Qongirogi hook: gaplashilgan qo'ng'iroqdan keyin shu raqamga
	tegishli ochiq qarz ishlari o'sha menejerga o'tadi."""
	try:
		if doc.tugash_sababi != "Javob berildi" or not (doc.suhbat_vaqti or 0):
			return
		if not doc.normal_telefon:
			return
		user = doc.foydalanuvchi or (
			frappe.db.get_value("Employee", doc.xodim, "user_id") if doc.xodim else None
		)
		if not _masul_bola_oladi(user):
			return
		for name in _raqam_boyicha_ishlar(doc.normal_telefon):
			masul_yangila(name)
	except Exception:
		# Qo'ng'iroq yozuvini qabul qilishni hech qachon bloklamaymiz
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik qongiroq_masul: {doc.name}")


def _raqam_boyicha_ishlar(normal: str) -> list[str]:
	"""Shu raqam tegishli bo'lgan ochiq qarz ishlari (to'lovchi/ota-ona/o'quvchi).

	Bitta so'rovda: raqamlar bazada erkin formatda yozilgan ("+998 90 123 45 67",
	"901234567"), shuning uchun ajratuvchilar tashlanib OXIRGI 9 RAQAM bo'yicha
	solishtiriladi — milliy raqamning o'zi, u yetarlicha noyob."""
	suffix = (normal or "")[-9:]
	if len(suffix) < 9:
		return []
	tozala = (
		"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE({0}, ' ', ''), '+', ''), '-', ''), '(', ''), ')', '')"
	)
	p = "%" + suffix
	return frappe.db.sql_list(
		f"""SELECT qi.name FROM `tabQarz Ishi` qi
		    LEFT JOIN `tabStudent` s ON s.name = qi.student
		    WHERE qi.ishlov_status NOT IN %(yopiq)s AND (
		          {tozala.format('qi.payer_phone')} LIKE %(p)s
		       OR {tozala.format('s.custom_payer_phone')} LIKE %(p)s
		       OR {tozala.format('s.student_mobile_number')} LIKE %(p)s
		       OR EXISTS (SELECT 1 FROM `tabStudent Guardian` sg
		                  JOIN `tabGuardian` g ON g.name = sg.guardian
		                  WHERE sg.parenttype = 'Student' AND sg.parent = qi.student
		                    AND {tozala.format('g.mobile_number')} LIKE %(p)s))""",
		{"yopiq": tuple(YOPIQ_STATUSLAR), "p": p},
	)


# ---------------------------------------------------------------- case sync
def _bucket(eng_eski, left_school: bool) -> str:
	if left_school:
		return "Ketgan-qarzli"
	if not eng_eski:
		return ""
	days = date_diff(nowdate(), eng_eski)
	if days <= 30:
		return "1-30"
	if days <= 60:
		return "31-60"
	if days <= 90:
		return "61-90"
	return "90+"


SOTUV_ROL = "Sotuv meneger"


def sotuv_menejermi(user: str) -> bool:
	"""Mas'ul bo'la oladimi: faol + "Sotuv meneger" roli bor."""
	return bool(user) and bool(frappe.db.get_value("User", user, "enabled")) and bool(
		frappe.db.exists("Has Role", {"role": SOTUV_ROL, "parenttype": "User", "parent": user})
	)


def sotuv_menejerlar() -> list[str]:
	"""Faol sotuv menejerlari — barqaror (nom) tartibda."""
	nomlar = frappe.get_all(
		"Has Role", filters={"role": SOTUV_ROL, "parenttype": "User"}, pluck="parent"
	)
	if not nomlar:
		return []
	return frappe.get_all(
		"User", filters={"name": ["in", nomlar], "enabled": 1},
		order_by="name", pluck="name",
	)


def _pick_masul(sinf: str, cfg) -> str:
	"""Qarz ishiga mas'ul tanlash — FAQAT sotuv menejerlari orasidan:
	(1) sozlamalardagi sinf-pattern biriktirishi (mas'uli sotuv menejeri
	bo'lsa), (2) default_masul (sotuv menejeri bo'lsa), (3) sinf bo'yicha
	BARQAROR taqsimot — barcha faol sotuv menejerlari orasida (bitta sinf
	doim bitta menejerga tushadi)."""
	for pattern, user in cfg.biriktirish:
		for p in str(pattern).split(","):
			if p.strip() and fnmatch(sinf or "", p.strip()) and sotuv_menejermi(user):
				return user
	if sotuv_menejermi(cfg.default_masul):
		return cfg.default_masul
	sotuv = sotuv_menejerlar()
	if sotuv:
		return sotuv[sum(ord(ch) for ch in (sinf or "")) % len(sotuv)]
	return "Administrator"      # sotuv menejeri umuman yo'q — oxirgi chora


def _payer_info(student_id: str, student=None):
	"""To'lovchi ism/tel zanjiri: Student.payer -> ota-ona (Guardian) -> o'quvchining o'zi."""
	if student is None:
		student = frappe.db.get_value(
			"Student",
			student_id,
			["custom_payer_name", "custom_payer_phone", "student_mobile_number"],
			as_dict=True,
		) or frappe._dict()
	if student.custom_payer_phone:
		return student.custom_payer_name, student.custom_payer_phone

	g = frappe.db.sql(
		"""SELECT COALESCE(g.guardian_name, sg.guardian_name) nm, g.mobile_number tel
		   FROM `tabStudent Guardian` sg
		   LEFT JOIN `tabGuardian` g ON g.name = sg.guardian
		   WHERE sg.parent = %s AND sg.parenttype = 'Student'
		     AND g.mobile_number IS NOT NULL AND g.mobile_number != ''
		   ORDER BY sg.idx LIMIT 1""",
		(student_id,),
		as_dict=True,
	)
	if g:
		return (student.custom_payer_name or g[0].nm), g[0].tel
	return student.custom_payer_name, student.student_mobile_number


def _sync_case(tr, qarz: float, eng_eski):
	cfg = _settings()
	open_case = frappe.db.get_value(
		"Qarz Ishi",
		{"student": tr.student, "ishlov_status": ["not in", list(YOPIQ_STATUSLAR)]},
		["name", "ishlov_status", "buzilgan_vadalar"],
		as_dict=True,
	)
	frappe.flags.qarz_engine = True

	# 1) Qarz yopildi -> ishni yopish
	if qarz <= cfg.tolerance:
		if open_case:
			qi = frappe.get_doc("Qarz Ishi", open_case.name)
			qi.ishlov_status = "Yopildi - To'landi"
			qi.yopilish_sababi = "To'landi"
			qi.qarz_summa = qarz
			qi.save(ignore_permissions=True)
			# ochiq va'dalar bajarildi hisoblanadi
			for p in frappe.get_all(
				"Tolov Vadasi", filters={"qarz_ishi": qi.name, "holat": "Ochiq"}, pluck="name"
			):
				frappe.db.set_value(
					"Tolov Vadasi",
					p,
					{"holat": "Bajarildi", "tekshirilgan_sana": nowdate()},
				)
		return

	left_school = bool(frappe.db.get_value("Student", tr.student, "date_of_leaving"))
	bucket = _bucket(eng_eski, left_school)

	# 2) Ochiq ish bor -> qarz ma'lumotlarini yangilash
	if open_case:
		frappe.db.set_value(
			"Qarz Ishi",
			open_case.name,
			{"qarz_summa": qarz, "eng_eski_muddat": eng_eski, "aging_bucket": bucket},
			update_modified=False,
		)
		return

	# 3) Yangi ish ochish: threshold + grace
	if qarz < cfg.min_threshold:
		return
	if eng_eski and date_diff(nowdate(), eng_eski) <= cfg.grace_days:
		return

	student = frappe.db.get_value(
		"Student",
		tr.student,
		["custom_payer_name", "custom_payer_phone", "student_mobile_number", "custom_sinf_guruh"],
		as_dict=True,
	) or frappe._dict()
	payer_name, payer_phone = _payer_info(tr.student, student)

	qi = frappe.get_doc(
		{
			"doctype": "Qarz Ishi",
			"student": tr.student,
			"tolov_rejasi": tr.name,
			"payer_name": payer_name,
			"payer_phone": payer_phone,
			"qarz_summa": qarz,
			"eng_eski_muddat": eng_eski,
			"aging_bucket": bucket,
			"masul": _pick_masul(student.custom_sinf_guruh, cfg),
			"ishlov_status": "Yangi",
			"keyingi_aloqa": nowdate(),
		}
	)
	qi.insert(ignore_permissions=True)


# ---------------------------------------------------------------- PTP check
def check_ptps():
	"""Muddati (+1 kun bufer) o'tgan ochiq va'dalar: to'lov tushganmi?"""
	cfg = _settings()
	deadline = add_days(nowdate(), -1)
	ptps = frappe.get_all(
		"Tolov Vadasi",
		filters={"holat": "Ochiq", "vada_sana": ["<=", deadline]},
		fields=["name", "qarz_ishi", "vada_summa", "creation", "masul", "student_name"],
	)
	for p in ptps:
		customer = frappe.db.get_value("Qarz Ishi", p.qarz_ishi, "customer")
		paid = _payments_since(customer, getdate(p.creation))
		if paid >= flt(p.vada_summa) - cfg.tolerance:
			holat = "Bajarildi"
		elif paid > 0:
			holat = "Qisman"
		else:
			holat = "Buzildi"
		frappe.db.set_value(
			"Tolov Vadasi",
			p.name,
			{"holat": holat, "amal_summa": paid, "tekshirilgan_sana": nowdate()},
		)
		if holat == "Bajarildi":
			continue

		# Qisman/Buzildi -> ish bugunga qaytadi
		qi = frappe.get_doc("Qarz Ishi", p.qarz_ishi)
		if qi.ishlov_status in YOPIQ_STATUSLAR:
			continue
		frappe.flags.qarz_engine = True
		if holat == "Buzildi":
			qi.buzilgan_vadalar = (qi.buzilgan_vadalar or 0) + 1
		qi.ishlov_status = (
			"Eskalatsiya"
			if (qi.buzilgan_vadalar or 0) >= cfg.buzilgan_vada_limit
			else "Va'da buzildi"
		)
		qi.keyingi_aloqa = nowdate()
		qi.save(ignore_permissions=True)
		frappe.flags.qarz_engine = False
		_todo(
			qi.masul,
			"Qarz Ishi",
			qi.name,
			f"Va'da bajarilmadi: {p.student_name or qi.student_name} — "
			f"{frappe.format_value(p.vada_summa, {'fieldtype': 'Currency'})} va'da, "
			f"tushgani {frappe.format_value(paid, {'fieldtype': 'Currency'})}",
		)


# ---------------------------------------------------------------- SLA
def check_sla():
	"""Yangi ish sla_soat ichida birinchi aloqasiz qolsa — mas'ulga ToDo."""
	cfg = _settings()
	rows = frappe.db.sql(
		"""SELECT name, masul, student_name FROM `tabQarz Ishi`
		   WHERE ishlov_status='Yangi' AND urinishlar_soni=0
		     AND TIMESTAMPDIFF(HOUR, creation, NOW()) > %s""",
		(cfg.sla_soat,),
		as_dict=True,
	)
	for r in rows:
		_todo(
			r.masul,
			"Qarz Ishi",
			r.name,
			f"SLA: {r.student_name} bo'yicha {cfg.sla_soat} soatdan beri birinchi aloqa yo'q",
		)


def _todo(user, ref_dt, ref_dn, description):
	"""Takrorlanmaydigan ochiq ToDo."""
	if frappe.db.exists(
		"ToDo",
		{
			"reference_type": ref_dt,
			"reference_name": ref_dn,
			"status": "Open",
			"allocated_to": user,
		},
	):
		return
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": user,
			"reference_type": ref_dt,
			"reference_name": ref_dn,
			"description": description,
			"priority": "High",
			"date": nowdate(),
		}
	).insert(ignore_permissions=True)


def _joriy_oquv_yili() -> str:
	t = getdate(nowdate())
	return f"{t.year}-{t.year + 1}" if t.month >= 7 else f"{t.year - 1}-{t.year}"


def ensure_tuition_plans():
	"""Shartnomali, lekin rejasi yo'q o'quvchilarga reja ochadi.
	Hook ishlamay qolgan holatlar uchun kechki xavfsizlik to'ri
	(ommaviy import, to'g'ridan-to'g'ri SQL tahriri va h.k.)."""
	from target_zenit.qarzdorlik.setup import joriy_oquv_yili, plan_yarat

	yil = joriy_oquv_yili()
	rows = frappe.db.sql(
		"""SELECT s.name FROM `tabStudent` s
		   WHERE s.enabled = 1 AND s.custom_shartnoma_qilindi = 1
		     AND (s.custom_monthly_payment > 0 OR s.custom_final_amount > 0)
		     AND (s.date_of_leaving IS NULL OR s.date_of_leaving = '')
		     AND NOT EXISTS (SELECT 1 FROM `tabTolov Rejasi` tr
		                     WHERE tr.student = s.name AND tr.holat != 'Bekor'
		                       AND tr.academic_year = %s)""",
		(yil,),
	)
	n = 0
	for (student,) in rows:
		try:
			yangi = plan_yarat(student, yil)
			if yangi:
				recompute_plan(yangi, sync_case=True)
				n += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"qarzdorlik ensure_tuition_plans: {student}")
	return n


def ensure_charge_plans():
	"""Faol rejasi YO'Q, lekin nachisleniyasi bor o'quvchilarga — masalan
	grant/investor farzandlari — faqat-nachisleniya reja ochadi. Shartnoma
	summasi bo'lmasa ham nachisleniya haqiqiy majburiyat: kitob-forma yoki
	hatto o'quv to'lovi nachislangan bo'lsa, u ko'rinishi va so'ralishi kerak."""
	cfg = _settings()
	rows = frappe.db.sql(
		"""SELECT si.customer, s.name student
		   FROM `tabSales Invoice` si
		   JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   JOIN `tabStudent` s ON s.customer = si.customer AND s.enabled = 1
		   WHERE si.docstatus=1 AND si.currency='UZS'
		     AND sii.item_code IS NOT NULL AND si.posting_date >= %s
		     AND NOT EXISTS (
		        SELECT 1 FROM `tabTolov Rejasi` tr
		        WHERE tr.student = s.name AND tr.holat != 'Bekor')
		   GROUP BY s.name""",
		(f"{_joriy_oquv_yili().split('-')[0]}-07-01",),
		as_dict=True,
	)
	for r in rows:
		try:
			tr = frappe.get_doc(
				{
					"doctype": "Tolov Rejasi",
					"student": r.student,
					"academic_year": _joriy_oquv_yili(),
					"holat": "Faol",
					"oylik_tolov": 0,
					"yakuniy_summa": 0,
					# sync_charges to'ldirishi uchun vaqtinchalik qator kerak emas —
					# oylar reqd bo'lgani uchun avval sinxronsiz bo'sh yaratib bo'lmaydi,
					# shuning uchun qatorlarni shu yerda yig'amiz:
					"oylar": _charge_rows_for(r.customer, cfg),
				}
			)
			if not tr.oylar:
				continue
			frappe.flags.qarz_engine = True
			tr.insert(ignore_permissions=True)
			frappe.flags.qarz_engine = False
			recompute_plan(tr.name, sync_case=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"qarzdorlik ensure_charge_plans: {r.student}")


def _charge_rows_for(customer: str, cfg) -> list[dict]:
	rows = frappe.db.sql(
		"""SELECT si.name, si.posting_date,
		          GROUP_CONCAT(DISTINCT sii.item_code ORDER BY sii.idx SEPARATOR ' + ') itemlar,
		          SUM(sii.net_amount) amount
		   FROM `tabSales Invoice` si
		   JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		   WHERE si.docstatus=1 AND si.customer=%s AND si.currency='UZS'
		     AND sii.item_code NOT IN %s
		     AND si.posting_date >= %s
		   GROUP BY si.name HAVING amount > 0""",
		(customer, tuple(cfg.istisno_itemlar) or ("",), f"{_joriy_oquv_yili().split('-')[0]}-07-01"),
		as_dict=True,
	)
	out = [
		{
			"oy_label": f"{r.itemlar} ({getdate(r.posting_date).strftime('%d.%m.%Y')})",
			"due_date": r.posting_date,
			"amount": flt(r.amount),
			"manba_hujjat": r.name,
			"izoh": "Nachisleniya (SI)",
		}
		for r in rows
	]
	# O'quv to'lovi nachisleniyasi — oylik qator (keyin sync_tuition yuritadi)
	for oy, a in sorted(
		_tuition_accruals(customer, f"{_joriy_oquv_yili().split('-')[0]}-07-01", cfg).items()
	):
		out.append(
			{
				"oy_label": _oy_label(oy),
				"due_date": _oy_muddati(oy, cfg),
				"amount": flt(a["amount"]),
				"nachisleniya": ", ".join(sorted(a["sis"])),
				"izoh": "O'quv to'lovi",
			}
		)
	return out


# ---------------------------------------------------------------- jobs/hooks
def nightly():
	"""Daily scheduler: hamma faol reja -> recompute + case sync; PTP; SLA.
	Har qadam alohida himoyalangan — bitta xato qolganini to'xtatmaydi."""
	try:
		ensure_tuition_plans()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: ensure_tuition_plans")
	try:
		ensure_charge_plans()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: ensure_charge_plans")
	for tr_name in frappe.get_all("Tolov Rejasi", filters={"holat": "Faol"}, pluck="name"):
		try:
			recompute_plan(tr_name, sync_case=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"qarzdorlik nightly: {tr_name}")
	try:
		check_ptps()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: check_ptps")
	try:
		check_sla()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: check_sla")
	try:
		masullarni_yangila()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "qarzdorlik nightly: masullarni_yangila")
	frappe.db.commit()


def on_payment(doc, method=None):
	"""PE submit/cancel — shu mijoz rejasini darhol qayta hisoblash.

	To'lov (Receive) ham, kassadan QAYTIM (Pay) ham hisobga olinadi — qaytim
	berilgan zahoti o'quvchining qarzi qayta hisoblanishi kerak."""
	try:
		if doc.party_type != "Customer" or doc.payment_type not in ("Receive", "Pay"):
			return
		for tr_name in frappe.get_all(
			"Tolov Rejasi",
			filters={"customer": doc.party, "holat": "Faol"},
			pluck="name",
		):
			recompute_plan(tr_name, sync_case=True)
	except Exception:
		# To'lov o'tkazishni hech qachon bloklamaymiz
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_payment: {doc.name}")


def on_journal_entry(doc, method=None):
	"""Journal Entry submit/cancel — provodkada mijoz (Customer) qatnashgan
	bo'lsa, shu o'quvchi(lar) rejasini darhol qayta hisoblash. Buxgalter to'lovni
	Journal Entry bilan yozsa ham panel darhol yangilanadi."""
	try:
		mijozlar = {
			r.party for r in (doc.accounts or []) if r.party_type == "Customer" and r.party
		}
		for mijoz in mijozlar:
			for tr_name in frappe.get_all(
				"Tolov Rejasi",
				filters={"customer": mijoz, "holat": "Faol"},
				pluck="name",
			):
				recompute_plan(tr_name, sync_case=True)
	except Exception:
		# Provodka o'tkazishni hech qachon bloklamaymiz
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_journal_entry: {doc.name}")


def on_invoice(doc, method=None):
	"""Sales Invoice submit/cancel — nachisleniya o'zgardi, shu o'quvchini yangilash."""
	try:
		for tr_name in frappe.get_all(
			"Tolov Rejasi",
			filters={"customer": doc.customer, "holat": "Faol"},
			pluck="name",
		):
			recompute_plan(tr_name, sync_case=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_invoice: {doc.name}")


def on_student_change(doc, method=None):
	"""O'quvchi o'zgarganda:
	  * shartnoma/tarif qo'yilsa -> To'lov Rejasi avtomatik ochiladi;
	  * ketsa -> kelgusi oylar Bekor, qolgan qarz 'Ketgan-qarzli' bucket."""
	try:
		# Yangi shartnomali o'quvchi (yoki tarifi endi to'ldirildi) -> reja
		if doc.get("custom_shartnoma_qilindi") and not doc.get("date_of_leaving"):
			from target_zenit.qarzdorlik.setup import plan_yarat

			yangi = plan_yarat(doc.name)
			if yangi:
				recompute_plan(yangi, sync_case=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik plan_yarat: {doc.name}")

	try:
		if not doc.date_of_leaving:
			return
		for tr_name in frappe.get_all(
			"Tolov Rejasi", filters={"student": doc.name, "holat": "Faol"}, pluck="name"
		):
			leaving = getdate(doc.date_of_leaving)
			tr = frappe.get_doc("Tolov Rejasi", tr_name)
			for r in tr.oylar:
				if getdate(r.due_date) > leaving and r.holat != "Bekor":
					frappe.db.set_value(
						"Tolov Rejasi Oyi", r.name, "holat", "Bekor", update_modified=False
					)
			recompute_plan(tr_name, sync_case=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"qarzdorlik on_student_change: {doc.name}")
