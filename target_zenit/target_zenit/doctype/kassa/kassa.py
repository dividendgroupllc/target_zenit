# Copyright (c) 2025, abdulloh and contributors
# For license information, please see license.txt

import re

import frappe
from erpnext.accounts.party import get_party_account as erpnext_get_party_account
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

# Konvertatsiya faqat shu valyutalar juftligida (UZS ↔ USD) amalga oshiriladi.
# Mode of Payment turi nomidan EMAS, ulangan cash account valyutasidan aniqlanadi.
CONVERSION_CURRENCIES = ("UZS", "USD")

# Standart ERPNext kontragent turlari (ledger'i party bo'yicha yuritiladi).
BASE_PARTY_TYPES = ("Customer", "Supplier", "Shareholder", "Employee")

# Xarajat papkalari shu guruh ichidan olinadi (Chart of Accounts -> Indirect Expenses).
EXPENSE_PARENT_ACCOUNT_NAME = "Indirect Expenses"

# Eski hujjatlarda uchraydigan qiymatlar. Yangi hujjatda tanlab bo'lmaydi (kassa.js
# ro'yxatdan yashiradi), lekin Select validatsiyasi arxivdagi hujjatni bloklamasligi
# uchun meta options ichida qoladi — aks holda eski yozuvni cancel/amend qilib bo'lmaydi.
LEGACY_PARTY_TYPES = ("Расходы", "Дивиденд", "Дивиденд 1", "Дивиденд 2", "Дивиденд 3")

# ---------------------------------------------------------------------------
# To'lov kategoriyasi (faqat o'quvchi/mijoz to'lovida)
# ---------------------------------------------------------------------------
# O'quvchida bir vaqtda bir necha xil qarz bo'ladi: har oylik o'quv to'lovi va
# bir martalik kitob / forma / yotoqxona. Nachisleniya (Sales Invoice) ham shu
# itemlar bilan yoziladi. Kassir to'lov QAYSI qarz uchun kelganini kategoriya
# bilan aytadi — tizim o'sha kategoriyadagi ochiq nachisleniyalarga avtomatik
# bog'laydi (eskisidan yangisiga).
#
# Eski (kategoriya yozilmagan) hujjatlar — o'quv to'lovi hisoblanadi: o'sha
# paytda kitob/forma uchun kassir `Nachisleniya` maydonini qo'lda tanlardi,
# bog'lanmagan pul esa qarzdorlik panelida oylik o'quv qatorlariga ketadi.
TOLOV_KATEGORIYALARI = ("O'quv to'lovi", "Kitob", "Forma", "Yotoqxona")
DEFAULT_TOLOV_KATEGORIYASI = "O'quv to'lovi"

# Kategoriya -> nachisleniya itemlari.
#   `itemlar`  — SI'da ishlatiladigan aniq item kodlari;
#   `guruhlar` — Item Group (kitob/forma kelajakda aniq nomlar bilan yozilsa ham
#                kategoriya ishlashi uchun; masalan "Cambridge Math 7" -> Kitob).
KATEGORIYA_ITEMLAR = {
    "O'quv to'lovi": {"itemlar": ["O'qitish xizmati"], "guruhlar": []},
    "Kitob": {"itemlar": ["Kitob"], "guruhlar": ["Kitoblar"]},
    "Forma": {"itemlar": ["Forma"], "guruhlar": ["Maktab formasi"]},
    "Yotoqxona": {"itemlar": ["Yotoqxona to'lovi"], "guruhlar": []},
}


def _kategoriya_sharti(category, args):
    """SI shu kategoriyadagi item(lar)ni o'z ichiga olishi sharti (SQL).

    `args` ichiga parametrlar qo'shiladi va shart matni qaytariladi; kategoriya
    noma'lum bo'lsa None (ya'ni filtr qo'llanmaydi).
    """
    cfg = KATEGORIYA_ITEMLAR.get(category)
    if not cfg:
        return None

    bloklar = []
    if cfg["itemlar"]:
        args["kat_itemlar"] = tuple(cfg["itemlar"])
        bloklar.append("x.item_code IN %(kat_itemlar)s")
    if cfg["guruhlar"]:
        args["kat_guruhlar"] = tuple(cfg["guruhlar"])
        bloklar.append("it.item_group IN %(kat_guruhlar)s")
    if not bloklar:
        return None

    return f"""EXISTS (SELECT 1 FROM `tabSales Invoice Item` x
                       LEFT JOIN `tabItem` it ON it.name = x.item_code
                       WHERE x.parent = si.name AND ({' OR '.join(bloklar)}))"""


def si_kategoriyalari(invoice) -> dict:
    """Sales Invoice itemlari qaysi kategoriyalarga tegishli: {kategoriya: summa}.

    Bazadagi haqiqat: nachisleniyalar aralash bo'lishi MUMKIN — 276 ta SI
    "Forma + Kitob" birga yozilgan. Shuning uchun bitta hujjat bir necha
    kategoriyaga tegishli bo'ladi.
    """
    if not invoice:
        return {}

    rows = frappe.db.sql("""
        SELECT sii.item_code, it.item_group, SUM(sii.net_amount) amount
        FROM `tabSales Invoice Item` sii
        LEFT JOIN `tabItem` it ON it.name = sii.item_code
        WHERE sii.parent = %s
        GROUP BY sii.item_code, it.item_group
    """, invoice, as_dict=True)

    ballar = {}
    for r in rows:
        for kat, cfg in KATEGORIYA_ITEMLAR.items():
            if r.item_code in cfg["itemlar"] or (r.item_group and r.item_group in cfg["guruhlar"]):
                ballar[kat] = ballar.get(kat, 0) + flt(r.amount)
                break
    return ballar


def aniqla_kategoriya(invoice, tanlangan=None):
    """Nachisleniyaga mos kategoriya.

    Kassir tanlagan kategoriya shu hujjatda BOR bo'lsa — uning tanlovi qoladi
    (aralash "Forma + Kitob" nachisleniyasida ikkisi ham to'g'ri javob).
    Aks holda eng ko'p summali item kategoriyasi olinadi.
    """
    ballar = si_kategoriyalari(invoice)
    if not ballar:
        return None
    if tanlangan and tanlangan in ballar:
        return tanlangan
    return max(ballar.items(), key=lambda kv: kv[1])[0]


@frappe.whitelist()
def get_invoice_category(invoice, category=None):
    """Kassa formasi uchun: tanlangan nachisleniyaga mos kategoriya.

    `category` — kassir hozir tanlab turgani; shu hujjatga mos bo'lsa o'zi qoladi.
    """
    return aniqla_kategoriya(invoice, category)


# party_name shu maydonlardan olinadi — hujjat nomidan (docname) emas.
# Customer nomi keyin tahrirlansa ham party_name yangi customer_name'ni oladi.
PARTY_NAME_FIELDS = {
    "Customer": "customer_name",
    "Supplier": "supplier_name",
    "Shareholder": "title",
    "Employee": "employee_name",
}


def get_account_currency_amount(company_amount, account_currency, company_currency, date):
    """Return amount/rate for a JE row in the row account currency."""
    if account_currency == company_currency:
        return flt(company_amount), 1

    exchange_rate = get_exchange_rate(account_currency, company_currency, date)
    if not exchange_rate or flt(exchange_rate) <= 0:
        frappe.throw(_("Не найден курс {0} к валюте компании {1}").format(account_currency, company_currency))

    return flt(flt(company_amount) / flt(exchange_rate)), flt(exchange_rate)


class Kassa(Document):
    def validate(self):
        self.set_default_company()
        self.set_cash_account()
        self.set_cash_account_currency()
        self.set_party_currency()
        self.set_party_name()
        self.set_student_group()
        self.set_payment_month()
        self.set_payment_category()
        self.set_display_currencies()
        self.set_payment_exchange_details()
        self.set_balance()
        self.validate_party()
        self.validate_transfer()
        self.validate_conversion()
        self.validate_amount()
        self.validate_currency()

    def on_submit(self):
        """Submit bo'lganda Payment Entry yoki Journal Entry yaratish"""
        if self.transaction_type in ["Приход", "Расход"]:
            if self.party_type in BASE_PARTY_TYPES:
                self.create_payment_entry()
            elif self.is_expense_entry():
                self.create_expense_journal_entry()
            else:
                # Jimgina o'tkazib yubormaymiz — aks holda hujjat submit bo'ladi-yu,
                # buxgalteriyada hech qanday provodka qolmaydi.
                frappe.throw(
                    _("Неизвестный тип контрагента: {0}. Выберите контрагента или папку расходов.").format(
                        self.party_type
                    )
                )
        elif self.transaction_type == "Перемещения":
            self.create_transfer_payment_entry()
        elif self.transaction_type == "Конвертация":
            self.create_conversion_payment_entry()

    def on_cancel(self):
        """Cancel bo'lganda bog'langan Payment Entry yoki Journal Entry ni cancel qilish"""
        self.cancel_linked_entries()

    def create_payment_entry(self):
        """Customer/Supplier/Employee uchun Payment Entry yaratish"""
        payment_type = "Receive" if self.transaction_type == "Приход" else "Pay"
        party_account = self.get_party_account()
        party_account_currency = frappe.get_cached_value("Account", party_account, "account_currency")
        cash_currency = self.cash_account_currency or frappe.get_cached_value(
            "Account", self.cash_account, "account_currency"
        )
        same_currency = cash_currency == party_account_currency

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = payment_type
        pe.posting_date = self.date
        pe.company = self.company
        pe.mode_of_payment = self.mode_of_payment
        pe.party_type = self.party_type
        pe.party = self.party

        # Set accounts
        pe.paid_from = self.get_paid_from_account(payment_type, party_account)
        pe.paid_to = self.get_paid_to_account(payment_type, party_account)

        if same_currency:
            pe.paid_amount = flt(self.amount)
            pe.received_amount = flt(self.amount)
        else:
            pe.source_exchange_rate = self.get_company_exchange_rate(
                frappe.get_cached_value("Account", pe.paid_from, "account_currency")
            )
            pe.target_exchange_rate = self.get_company_exchange_rate(
                frappe.get_cached_value("Account", pe.paid_to, "account_currency")
            )

            if payment_type == "Pay":
                pe.paid_amount = flt(self.amount)
                pe.received_amount = flt(self.credit_amount)
            else:
                pe.paid_amount = flt(self.credit_amount)
                pe.received_amount = flt(self.amount)

        # Set reference to Kassa
        pe.reference_no = self.name
        pe.reference_date = self.date
        pe.custom_payment_month = self.payment_month
        pe.remarks = self.remarks or f"Payment for {self.name}"

        # Xodim to'lovi bo'lsa — shu oy uchun yozilgan nachisleniyaga bog'lanadi.
        # Shunda "qaysi oy uchun" yorliqdan emas, haqiqiy nachisleniyadan kelib chiqadi
        # va qarzdorlik avtomatik yopiladi.
        self.allocate_employee_accruals(pe)
        # O'quvchi/mijoz to'lovi — ochiq nachisleniyalarga (Sales Invoice) bog'lanadi,
        # shunda "qaysi nachisleniya uchun to'langani" tizimda ko'rinadi.
        self.allocate_customer_invoices(pe)

        pe.flags.ignore_permissions = True
        pe.insert()
        pe.submit()

        self.set_linked_document("Payment Entry", pe.name)

        frappe.msgprint(_("Payment Entry {0} создан").format(
            frappe.utils.get_link_to_form("Payment Entry", pe.name)
        ))

    def allocate_employee_accruals(self, pe):
        """To'lovni shu oy uchun yozilgan nachisleniya(lar)ga taqsimlash.

        Eskisidan yangisiga: har nachisleniyaga qoldig'igacha yoziladi. Nachisleniya
        topilmasa hech narsa bog'lanmaydi — to'lov AVANS bo'lib qoladi va keyin
        nachisleniya yozilganda avtomatik ulanadi (journal_entry.py).
        """
        if self.party_type != "Employee" or not self.payment_month:
            return
        # To'lovning kontragent hisobi (Pay -> paid_to, Приход -> paid_from)
        party_account = pe.paid_to if pe.payment_type == "Pay" else pe.paid_from
        accruals = [a for a in get_employee_accruals(
            self.party, self.payment_month, self.company, account=party_account)
            if a.get("linkable")]
        if not accruals:
            return

        # Pay turida received_amount kontragent hisobi valyutasida bo'ladi
        left = flt(pe.received_amount or pe.paid_amount)
        for a in accruals:
            if left <= 0.005:
                break
            share = min(left, flt(a["outstanding"]))
            if share <= 0.005:
                continue
            pe.append("references", {
                "reference_doctype": "Journal Entry",
                "reference_name": a["journal_entry"],
                "total_amount": flt(a["total"]),
                "outstanding_amount": flt(a["outstanding"]),
                "allocated_amount": share,
            })
            left -= share

    def allocate_customer_invoices(self, pe):
        """To'lovni o'quvchining ochiq nachisleniyalariga (Sales Invoice) bog'lash.

        QAYSI nachisleniyaga — `payment_category` aytadi (o'quv to'lovi / kitob /
        forma / yotoqxona). O'sha kategoriyadagi ochiq nachisleniyalarga
        eskisidan yangisiga qarab yoziladi; ortgan pul avans bo'lib qoladi.

        Nega kategoriya kerak (2026-10-12 → 2026-10-16 qarori): o'quvchida bir
        vaqtda ikki xil qarz turadi — har oylik o'quv to'lovi va bir martalik
        kitob/forma/yotoqxona. Avval kategoriya bo'lmaganida avtomatik taqsimot
        noto'g'ri nachisleniyani yopib qo'yardi, shuning uchun o'chirilgan edi;
        endi kategoriya taqsimot maydonini toraytiradi va avtomatik bog'lash
        xavfsiz. Kassir aniq bitta hujjatni tanlasa (`sales_invoice`) — faqat
        o'shanga bog'lanadi.

        Eski (kategoriyasiz) to'lovlar o'zgarmaydi: bog'lanmagan pul qarzdorlik
        panelida oylik o'quv qatorlariga ketadi (o'quv to'lovi hisoblanadi).
        """
        if self.party_type != "Customer":
            return
        if self.transaction_type == "Расход":
            self.allocate_customer_refund(pe)
            return
        if self.transaction_type != "Приход":
            return

        party_account = pe.paid_from if pe.payment_type == "Receive" else pe.paid_to
        if self.sales_invoice:
            invoices = get_customer_invoices(
                self.party, self.company, account=party_account, invoice=self.sales_invoice)
        else:
            invoices = get_customer_invoices(
                self.party, self.company, account=party_account,
                category=self.payment_category or DEFAULT_TOLOV_KATEGORIYASI)
        if not invoices:
            return

        left = flt(pe.paid_amount if pe.payment_type == "Receive" else pe.received_amount)
        for inv in invoices:
            if left <= 0.005:
                break
            share = min(left, flt(inv["outstanding"]))
            if share <= 0.005:
                continue
            pe.append("references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": inv["name"],
                "total_amount": flt(inv["total"]),
                "outstanding_amount": flt(inv["outstanding"]),
                "allocated_amount": share,
            })
            left -= share

    def allocate_customer_refund(self, pe):
        """Qaytim (Расход) — ortiqcha to'langan nachisleniyaga bog'lash.

        Haqiqiy oqim (bazadagi yozuvlar bilan tekshirilgan): ota-ona dollar yoki
        yirik summa olib keladi, u o'quvchining hisobida (debitorka) turadi va
        nachisleniyalarni yopadi; ortgan qoldiq esa **avans** bo'lib qoladi
        ("kitob $200 dan qaytim" kabi). Qaytim shu avansdan beriladi — ya'ni
        buxgalteriyada u hech qanday nachisleniyaga bog'lanmaydi va bog'lanishi
        ham KERAK EMAS: o'quvchi hisobi avval kredit edi, qaytimdan keyin nolga
        keladi. `payment_category` + `sales_invoice` esa qaytim QAYSI to'lov
        uchun berilganini yozib qo'yadi (hisobot va qarzdorlik paneli uchun).

        ERPNext qoidasi (sinab ko'rilgan): Payment Entry qaytimini nachisleniyaga
        bog'lash FAQAT o'sha nachisleniya **ortiqcha to'langan** bo'lsa mumkin
        (outstanding < 0, manfiy allocation). To'liq to'langan nachisleniyaga
        bog'lash «has already been fully paid» xatosi bilan rad etiladi —
        unday hollarda buxgalter kredit-nota yozishi kerak.
        """
        if self.party_type != "Customer" or self.transaction_type != "Расход":
            return

        party_account = pe.paid_to if pe.payment_type == "Pay" else pe.paid_from
        invoices = get_overpaid_customer_invoices(
            self.party, self.company, account=party_account,
            category=None if self.sales_invoice else (self.payment_category
                                                      or DEFAULT_TOLOV_KATEGORIYASI),
            invoice=self.sales_invoice)
        if not invoices:
            return          # avans qaytarildi — bog'lanish shart emas

        left = flt(pe.received_amount if pe.payment_type == "Pay" else pe.paid_amount)
        for inv in invoices:
            if left <= 0.005:
                break
            share = min(left, flt(inv["overpaid"]))
            if share <= 0.005:
                continue
            pe.append("references", {
                "reference_doctype": "Sales Invoice",
                "reference_name": inv["name"],
                "total_amount": flt(inv["total"]),
                "outstanding_amount": -flt(inv["overpaid"]),
                "allocated_amount": -share,          # qaytim = manfiy taqsimot
            })
            left -= share

    def get_paid_from_account(self, payment_type, party_account=None):
        """Payment type ga qarab paid_from accountni olish"""
        if payment_type == "Receive":
            return party_account or self.get_party_account()
        else:
            return self.cash_account

    def get_paid_to_account(self, payment_type, party_account=None):
        """Payment type ga qarab paid_to accountni olish"""
        if payment_type == "Receive":
            return self.cash_account
        else:
            return party_account or self.get_party_account()

    def get_party_account(self):
        """ERPNext party ledger logikasi bo'yicha account olish."""
        if self.party_type in ["Customer", "Supplier", "Shareholder"]:
            return erpnext_get_party_account(self.party_type, self.party, self.company)

        if self.party_type == "Employee":
            # Nachisleniya qaysi qarz hisobida yozilgan bo'lsa — to'lov ham
            # O'SHA hisob orqali o'tadi. Aks holda ERPNext bog'lashni rad etadi
            # ("Journal Entry ... does not have account ..."), chunki to'lov va
            # nachisleniya har xil hisobda bo'lib qoladi.
            accrual_account = self.get_accrual_account()
            if accrual_account:
                return accrual_account
            payable_account = get_employee_payable_account(self.company)
            if payable_account:
                return payable_account

        frappe.throw(_("Не удалось определить счет контрагента для {0}").format(self.party_type))

    def get_accrual_account(self):
        """Shu xodim va oy uchun yozilgan eng eski to'lanmagan nachisleniyaning hisobi.

        Bir nechta hisobda nachisleniya bo'lsa — eng eskisi olinadi (avval eski
        qarz yopiladi). Nachisleniya bo'lmasa None qaytadi va odatdagi sozlangan
        hisob ishlatiladi.
        """
        if self.party_type != "Employee" or not self.party or not self.payment_month:
            return None
        accruals = get_employee_accruals(self.party, self.payment_month, self.company)
        return accruals[0]["account"] if accruals else None

    def is_party_multicurrency_payment(self):
        return (
            self.transaction_type in ["Приход", "Расход"]
            and self.party_type in BASE_PARTY_TYPES
            and self.cash_account
            and self.party
            and self.party_currency
            and self.cash_account_currency
            and self.cash_account_currency != self.party_currency
        )

    def get_company_exchange_rate(self, currency):
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        if not currency or currency == company_currency:
            return 1

        rate = get_exchange_rate(currency, company_currency, self.date)
        if not rate or flt(rate) <= 0:
            frappe.throw(_("Не найден курс {0} к валюте компании {1}").format(currency, company_currency))
        return flt(rate)

    def set_payment_exchange_details(self):
        """Приход/Расход uchun cash валютасидан party валютасига kurs va summa tayyorlash."""
        if not self.is_party_multicurrency_payment():
            if self.transaction_type in ["Приход", "Расход"]:
                self.exchange_rate = 0
                self.debit_amount = 0
                self.credit_amount = 0
                self.manual_credit_amount = 0
            return

        fetched_exchange_rate = get_exchange_rate(
            self.cash_account_currency, self.party_currency, self.date
        )
        if (
            not self.exchange_rate
            or flt(self.exchange_rate) <= 0
            or flt(self.exchange_rate) == 1
            or (flt(self.exchange_rate) < 0.001 and fetched_exchange_rate)
        ):
            self.exchange_rate = fetched_exchange_rate

        if not self.exchange_rate or flt(self.exchange_rate) <= 0:
            frappe.throw(
                _("Не найден курс {0} к {1} на дату {2}").format(
                    self.cash_account_currency, self.party_currency, self.date
                )
            )

        self.debit_amount = flt(self.amount)

        if cint(self.manual_credit_amount) and flt(self.credit_amount) > 0:
            self.credit_amount = flt(self.credit_amount, 2)
        else:
            self.credit_amount = flt(flt(self.amount) * flt(self.exchange_rate), 2)
            self.manual_credit_amount = 0

    def is_expense_entry(self):
        """Xarajat operatsiyasimi — ya'ni party_type xarajat papkasi (guruh account) mi.

        Eski hujjatlarda papka o'rniga "Расходы" turgan — ular ham xarajat sifatida
        qayta ishlanadi (amend qilinganda provodka to'g'ri yaratilsin).
        """
        if self.party_type == "Расходы" and self.expense_account:
            return True
        return is_expense_party_type(self.party_type, self.company)

    def create_expense_journal_entry(self):
        """Xarajat uchun Journal Entry yaratish.

        Yo'nalish operatsiya turiga bog'liq:
          Расход — kassadan pul chiqadi:            xarajat Dt / kassa Kt
          Приход — kassaga pul qaytadi (qaytarma):  kassa Dt / xarajat Kt
        """
        if not self.expense_account:
            frappe.throw(_("Пожалуйста, выберите счет расходов"))

        cost_center = get_expense_cost_center(self.expense_account)
        cash_account_currency = frappe.get_cached_value("Account", self.cash_account, "account_currency")
        company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
        expense_account_currency = frappe.get_cached_value("Account", self.expense_account, "account_currency") or company_currency

        is_inflow = self.transaction_type == "Приход"
        cash_side = "debit" if is_inflow else "credit"
        expense_side = "credit" if is_inflow else "debit"

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = self.date
        je.company = self.company
        je.cheque_no = self.name
        je.cheque_date = self.date
        je.custom_payment_month = self.payment_month
        je.user_remark = self.remarks or (
            f"Expense refund from {self.name}" if is_inflow else f"Expense payment from {self.name}"
        )

        is_multicurrency = cash_account_currency != company_currency

        if is_multicurrency:
            je.multi_currency = 1
            exchange_rate = get_exchange_rate(cash_account_currency, company_currency, self.date)
            if not exchange_rate or exchange_rate == 0:
                exchange_rate = 1
            company_amount = flt(self.amount) * exchange_rate
            expense_amount, expense_exchange_rate = get_account_currency_amount(
                company_amount, expense_account_currency, company_currency, self.date
            )

            je.append("accounts", {
                "account": self.cash_account,
                f"{cash_side}_in_account_currency": flt(self.amount),
                "account_currency": cash_account_currency,
                "exchange_rate": exchange_rate,
                cash_side: company_amount,
            })

            je.append("accounts", {
                "account": self.expense_account,
                "cost_center": cost_center,
                f"{expense_side}_in_account_currency": expense_amount,
                "account_currency": expense_account_currency,
                "exchange_rate": expense_exchange_rate,
                expense_side: company_amount,
            })
        else:
            je.append("accounts", {
                "account": self.cash_account,
                f"{cash_side}_in_account_currency": flt(self.amount),
                cash_side: flt(self.amount),
            })

            je.append("accounts", {
                "account": self.expense_account,
                "cost_center": cost_center,
                f"{expense_side}_in_account_currency": flt(self.amount),
                expense_side: flt(self.amount),
            })

        je.flags.ignore_permissions = True
        je.insert()
        je.submit()

        self.set_linked_document("Journal Entry", je.name)

        frappe.msgprint(_("Journal Entry {0} для расходов создан").format(
            frappe.utils.get_link_to_form("Journal Entry", je.name)
        ))

    def create_transfer_payment_entry(self):
        """Перемещения uchun Internal Transfer Payment Entry yaratish"""
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Internal Transfer"
        pe.posting_date = self.date
        pe.company = self.company
        pe.mode_of_payment = self.mode_of_payment

        # Set accounts - from and to
        pe.paid_from = self.cash_account
        pe.paid_to = self.cash_account_to
        pe.paid_amount = flt(self.amount)
        pe.received_amount = flt(self.amount)

        # Set reference to Kassa
        pe.reference_no = self.name
        pe.reference_date = self.date
        pe.remarks = self.remarks or f"Transfer from {self.name}"

        pe.flags.ignore_permissions = True
        pe.insert()
        pe.submit()

        self.set_linked_document("Payment Entry", pe.name)

        frappe.msgprint(_("Payment Entry {0} для перемещения создан").format(
            frappe.utils.get_link_to_form("Payment Entry", pe.name)
        ))

    def create_conversion_payment_entry(self):
        """Конвертация uchun Internal Transfer Payment Entry yaratish (kurs farqi bilan)"""
        from_currency = frappe.get_cached_value("Account", self.cash_account, "account_currency")
        to_currency = frappe.get_cached_value("Account", self.cash_account_to, "account_currency")

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Internal Transfer"
        pe.posting_date = self.date
        pe.company = self.company
        pe.mode_of_payment = self.mode_of_payment

        pe.paid_from = self.cash_account
        pe.paid_to = self.cash_account_to
        pe.paid_amount = flt(self.debit_amount)
        pe.received_amount = flt(self.credit_amount)
        pe.source_exchange_rate = self.get_company_exchange_rate(from_currency)
        pe.target_exchange_rate = self.get_company_exchange_rate(to_currency)

        pe.reference_no = self.name
        pe.reference_date = self.date
        pe.remarks = self.remarks or f"Conversion from {self.name}"

        pe.flags.ignore_permissions = True
        pe.insert()
        pe.submit()

        self.set_linked_document("Payment Entry", pe.name)

        frappe.msgprint(_("Payment Entry {0} для конвертации создан").format(
            frappe.utils.get_link_to_form("Payment Entry", pe.name)
        ))

    def cancel_linked_entries(self):
        """Bog'langan Payment Entry va Journal Entrylarni cancel qilish"""
        # Cancel Payment Entries
        payment_entries = frappe.get_all("Payment Entry",
            filters={"reference_no": self.name, "docstatus": 1},
            pluck="name")

        for pe_name in payment_entries:
            pe = frappe.get_doc("Payment Entry", pe_name)
            pe.flags.ignore_permissions = True
            pe.cancel()
            frappe.msgprint(_("Payment Entry {0} отменен").format(pe_name))

        # Cancel Journal Entries (linked via cheque_no)
        journal_entries = frappe.get_all("Journal Entry",
            filters={"cheque_no": self.name, "docstatus": 1},
            pluck="name")

        for je_name in journal_entries:
            je_doc = frappe.get_doc("Journal Entry", je_name)
            je_doc.flags.ignore_permissions = True
            je_doc.cancel()
            frappe.msgprint(_("Journal Entry {0} отменен").format(je_name))

    def set_linked_document(self, doctype, name):
        self.linked_doctype = doctype
        self.linked_entry = name
        self.db_set("linked_doctype", doctype, update_modified=False)
        self.db_set("linked_entry", name, update_modified=False)

    def set_default_company(self):
        """Set default company for Перемещения if not set"""
        if self.transaction_type == "Перемещения" and not self.company:
            default_company = frappe.db.get_single_value("Global Defaults", "default_company")
            if default_company:
                self.company = default_company
            else:
                frappe.throw(_("Пожалуйста, установите компанию по умолчанию в настройках"))

    def set_cash_account(self):
        """Mode of Payment dan cash accountni olish"""
        if self.mode_of_payment and self.company:
            cash_account = get_cash_account(self.mode_of_payment, self.company)
            if cash_account:
                self.cash_account = cash_account

        # Set cash_account_to for transfer/conversion
        if self.mode_of_payment_to and self.company:
            cash_account_to = get_cash_account(self.mode_of_payment_to, self.company)
            if cash_account_to:
                self.cash_account_to = cash_account_to

    def set_cash_account_currency(self):
        """Cash account valyutasini olish"""
        if self.cash_account:
            self.cash_account_currency = frappe.get_cached_value("Account", self.cash_account, "account_currency")
        if self.cash_account_to:
            self.cash_account_to_currency = frappe.get_cached_value(
                "Account", self.cash_account_to, "account_currency"
            )

    def set_party_currency(self):
        """Party default valyutasini olish"""
        if self.party and self.party_type in BASE_PARTY_TYPES and self.company:
            self.party_currency = get_party_currency(self.party_type, self.party, self.company)

    def set_party_name(self):
        """party_name'ni har doim kontragentning nom maydonidan (customer_name va h.k.)
        yangilash — docname'dan emas. Client to'ldirgan eski qiymat ustidan yoziladi."""
        if self.party and self.party_type in PARTY_NAME_FIELDS:
            self.party_name = (
                frappe.db.get_value(self.party_type, self.party, PARTY_NAME_FIELDS[self.party_type])
                or self.party
            )
        elif not self.party:
            self.party_name = None

    def set_payment_month(self):
        """Qaysi oy uchun to'lov ekani (YYYY-MM).

        Xodim o'tgan oyning oyligini yoki kelasi oydan avans olishi mumkin;
        o'quvchida ham shunday. Shuning uchun operator buni qo'lda o'zgartiradi.
        Bo'sh qolsa hujjat sanasining oyi qo'yiladi — odatdagi holat shu.
        """
        # Faqat XODIM uchun: o'tgan yoki kelasi oy oyligini olish holati xodimlarda uchraydi.
        # Mijoz/ta'minotchi va xarajat papkalarida bu maydon ishlatilmaydi.
        if self.transaction_type not in ("Приход", "Расход") or self.party_type != "Employee":
            self.payment_month = None
            return
        value = (self.payment_month or "").strip()
        if value:
            # faqat YYYY-MM ko'rinishini qabul qilamiz (hisobotlarda birlashtirish uchun)
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
                frappe.throw(
                    _("«За какой месяц» YYYY-MM ko'rinishida bo'lishi kerak (masalan 2026-08), kiritilgan: {0}")
                    .format(value)
                )
            self.payment_month = value
        else:
            # bo'sh bo'lsa — bugungi oy (hujjat sanasi orqaga surilgan bo'lsa ham
            # operator odatda joriy oy uchun to'laydi; kerak bo'lsa qo'lda tanlaydi)
            self.payment_month = frappe.utils.today()[:7]

    def set_payment_category(self):
        """To'lov kategoriyasi (o'quv to'lovi / kitob / forma / yotoqxona).

        Faqat o'quvchi (Customer) kirim to'lovida ishlatiladi — tizim shu
        kategoriyadagi ochiq nachisleniyalarga avtomatik bog'laydi.
        Bo'sh qolsa — o'quv to'lovi (eng ko'p uchraydigani).

        Kassir `Nachisleniya` maydonida aniq hisob-fakturani tanlasa, kategoriya
        SHU hujjatdan olinadi: Sales Invoice'dagi «Kassa (to'lov)» tugmasi ham
        shu yo'l bilan keladi, va tanlangan hujjat kategoriyadan ustun turadi.
        """
        if self.transaction_type not in ("Приход", "Расход") or self.party_type != "Customer":
            self.payment_category = None
            return

        if self.sales_invoice:
            kat = aniqla_kategoriya(self.sales_invoice, self.payment_category)
            if kat:
                self.payment_category = kat
                return

        if self.payment_category not in TOLOV_KATEGORIYALARI:
            self.payment_category = DEFAULT_TOLOV_KATEGORIYASI

    def set_student_group(self):
        """Customer o'quvchining Customer'i bo'lsa — uning sinfi (guruhi) ko'rsatiladi.
        To'lov qilishdan oldin qaysi sinf ekanini ko'rish uchun (faqat ma'lumot)."""
        if self.party_type == "Customer" and self.party:
            self.student_group = get_student_group(self.party) or None
        else:
            self.student_group = None

    def set_display_currencies(self):
        """Currency fieldlar uchun UI'da ishlatiladigan currency fieldlarni to'ldirish."""
        self.target_amount_currency = None

        if self.transaction_type == "Конвертация":
            self.target_amount_currency = self.cash_account_to_currency or self.party_currency or None
        elif self.is_party_multicurrency_payment():
            self.target_amount_currency = self.party_currency or None

    def set_balance(self):
        """Cash account balansini olish"""
        if self.cash_account:
            self.balance = get_account_balance(self.cash_account, self.company)

        # Set balance_to for transfer/conversion
        if self.cash_account_to:
            self.balance_to = get_account_balance(self.cash_account_to, self.company)

    def validate_party(self):
        """Party validatsiyasi.

        Kontragent turi yo standart party (Customer/Supplier/...), yo xarajat papkasi
        (Indirect Expenses ichidagi guruh account) bo'ladi.
        """
        if self.transaction_type not in ["Приход", "Расход"]:
            return

        if not self.party_type:
            frappe.throw(_("Пожалуйста, выберите тип контрагента"))

        if self.party_type in BASE_PARTY_TYPES:
            if not self.party:
                frappe.throw(_("Пожалуйста, выберите контрагента"))
            self.expense_account = None
            return

        # "Расходы" — eski hujjatlardagi qiymat, u ham xarajat sifatida qabul qilinadi
        if self.party_type != "Расходы" and not is_expense_party_type(self.party_type, self.company):
            frappe.throw(
                _("Неизвестный тип контрагента: {0}. Выберите контрагента или папку расходов.").format(
                    self.party_type
                )
            )

        if not self.expense_account:
            frappe.throw(_("Пожалуйста, выберите счет расходов"))
        validate_expense_account(self.expense_account, self.company, self.party_type)
        self.party = None

    def validate_transfer(self):
        """Transfer validatsiyasi"""
        if self.transaction_type == "Перемещения":
            if not self.mode_of_payment_to:
                frappe.throw(_("Пожалуйста, выберите способ оплаты (куда)"))

            if self.mode_of_payment == self.mode_of_payment_to:
                frappe.throw(_("Способ оплаты источника и назначения должны отличаться"))

            from_currency = frappe.get_cached_value("Account", self.cash_account, "account_currency") if self.cash_account else None
            to_currency = frappe.get_cached_value("Account", self.cash_account_to, "account_currency") if self.cash_account_to else None

            if not from_currency or not to_currency:
                frappe.throw(_("Не удалось определить валюту счетов для перемещения"))

            if from_currency != to_currency:
                frappe.throw(_("Для перемещения способы оплаты должны иметь одинаковую валюту"))

    def validate_conversion(self):
        """Conversion validatsiyasi.

        Valyuta hisob-kitobi mode of payment NOMI bilan emas, balki ulangan
        cash account'ning haqiqiy valyutasi (account_currency) bilan aniqlanadi.
        Shu sabab Р/С USD bo'lsa ham, UZS bo'lsa ham to'g'ri tomonga tushadi.
        """
        if self.transaction_type != "Конвертация":
            return

        if not self.mode_of_payment_to:
            frappe.throw(_("Пожалуйста, выберите способ оплаты (куда)"))

        if not self.exchange_rate or flt(self.exchange_rate) <= 0:
            frappe.throw(_("Пожалуйста, укажите курс обмена"))

        if flt(self.debit_amount) <= 0:
            frappe.throw(_("Пожалуйста, укажите сумму расхода"))

        if flt(self.credit_amount) <= 0:
            frappe.throw(_("Пожалуйста, укажите сумму прихода"))

        from_currency = frappe.get_cached_value("Account", self.cash_account, "account_currency") if self.cash_account else None
        to_currency = frappe.get_cached_value("Account", self.cash_account_to, "account_currency") if self.cash_account_to else None

        if not from_currency or not to_currency:
            frappe.throw(_("Не удалось определить валюту счетов для конвертации"))

        if from_currency not in CONVERSION_CURRENCIES or to_currency not in CONVERSION_CURRENCIES:
            frappe.throw(_("Для конвертации выберите счета в UZS или USD"))

        if from_currency == to_currency:
            frappe.throw(
                _("Для конвертации способы оплаты должны иметь разные валюты")
            )

    def validate_amount(self):
        """Summa validatsiyasi"""
        if self.transaction_type == "Конвертация":
            return

        if flt(self.amount) <= 0:
            frappe.throw(_("Сумма должна быть больше нуля"))

        if self.is_party_multicurrency_payment():
            if not self.exchange_rate or flt(self.exchange_rate) <= 0:
                frappe.throw(_("Пожалуйста, укажите курс обмена"))

            if flt(self.credit_amount) <= 0:
                frappe.throw(_("Не удалось рассчитать сумму в валюте контрагента"))

        # Rasxod uchun balansni tekshirish
        if self.transaction_type == "Расход" and flt(self.amount) > flt(self.balance):
            frappe.msgprint(
                _("Внимание: Сумма расхода ({0}) превышает остаток кассы ({1})").format(
                    frappe.format_value(self.amount, {"fieldtype": "Currency"}),
                    frappe.format_value(self.balance, {"fieldtype": "Currency"})
                ),
                indicator="orange",
                alert=True
            )

    def validate_currency(self):
        """Target Zenit'da payment oqimi cash account valyutasi bo'yicha account tanlaydi.

        Party currency foydalanuvchiga ma'lumot sifatida ko'rsatiladi, lekin
        Приход/Расход operatsiyasini bloklamaydi. Asosiy accounting account
        get_party_account_by_currency() orqali cash account currency bo'yicha tanlanadi.
        """
        return


@frappe.whitelist()
def get_cash_account(mode_of_payment, company):
    """Mode of Payment uchun cash accountni olish"""
    if not mode_of_payment or not company:
        return None

    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account"
    )
    return account


@frappe.whitelist()
def get_cash_account_with_currency(mode_of_payment, company):
    """Mode of Payment uchun cash account va currency olish"""
    if not mode_of_payment or not company:
        return {"account": None, "currency": None}

    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account"
    )

    if account:
        currency = frappe.get_cached_value("Account", account, "account_currency")
        return {"account": account, "currency": currency}

    return {"account": None, "currency": None}


def get_cash_mode_of_payment_currencies(company, currencies=None):
    """Kompaniyaning enabled mode of payment'lari va ulangan cash account valyutasi.

    Faqat shu kompaniya uchun cash account'i sozlangan usullar qaytariladi.
    ``currencies`` berilsa — faqat o'sha valyutadagilar bilan cheklanadi.
    """
    params = {"company": company}
    currency_condition = ""
    if currencies:
        currency_condition = "AND acc.account_currency IN %(currencies)s"
        params["currencies"] = tuple(currencies)

    return frappe.db.sql(
        f"""
        SELECT mpa.parent AS mode_of_payment, acc.account_currency AS currency
        FROM `tabMode of Payment Account` mpa
        INNER JOIN `tabAccount` acc ON acc.name = mpa.default_account
        INNER JOIN `tabMode of Payment` mop ON mop.name = mpa.parent
        WHERE mpa.company = %(company)s
            AND mop.enabled = 1
            {currency_condition}
        """,
        params,
        as_dict=True,
    )


def get_source_mode_currency(company, source_mode_of_payment):
    """Manba mode of payment'ning cash account valyutasi."""
    if not source_mode_of_payment:
        return None
    source_account = get_cash_account(source_mode_of_payment, company)
    if not source_account:
        return None
    return frappe.get_cached_value("Account", source_account, "account_currency")


def get_conversion_mode_of_payments(company, source_mode_of_payment=None):
    """Konvertatsiya uchun mos mode of payment'lar (UZS/USD, account valyutasi bo'yicha).

    ``source_mode_of_payment`` berilganda faqat undan FARQLI valyutadagi
    (qarama-qarshi tomon) usullar qaytariladi — manba USD bo'lsa UZS, aksincha.
    """
    rows = get_cash_mode_of_payment_currencies(company, CONVERSION_CURRENCIES)
    source_currency = get_source_mode_currency(company, source_mode_of_payment)

    result = []
    for row in rows:
        if source_mode_of_payment:
            if row.mode_of_payment == source_mode_of_payment:
                continue
            if not source_currency or row.currency == source_currency:
                continue
        result.append(row)
    return result


def get_transfer_mode_of_payments(company, source_mode_of_payment=None):
    """Перемещения uchun mos mode of payment'lar (account valyutasi bo'yicha).

    ``source_mode_of_payment`` berilganda faqat u bilan BIR XIL valyutadagi
    usullar qaytariladi — peremeshenie faqat bir xil valyuta o'rtasida bo'ladi.
    """
    rows = get_cash_mode_of_payment_currencies(company)
    source_currency = get_source_mode_currency(company, source_mode_of_payment)

    result = []
    for row in rows:
        if source_mode_of_payment:
            if row.mode_of_payment == source_mode_of_payment:
                continue
            if not source_currency or row.currency != source_currency:
                continue
        result.append(row)
    return result


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def conversion_mode_of_payment_query(doctype, txt, searchfield, start, page_len, filters):
    """Kassa konvertatsiyasidagi "Способ оплаты" Link maydonlari uchun query.

    ``filters.source_mode_of_payment`` berilsa — qarama-qarshi valyutadagi
    usullarni qaytaradi (manba tomon uchun esa berilmaydi).
    """
    filters = filters or {}
    company = filters.get("company")
    if not company:
        return []

    modes = get_conversion_mode_of_payments(company, filters.get("source_mode_of_payment"))
    return _format_mode_of_payment_query_result(modes, txt)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def transfer_mode_of_payment_query(doctype, txt, searchfield, start, page_len, filters):
    """Перемещения dagi "Способ оплаты (куда)" Link maydoni uchun query.

    Manba bilan BIR XIL valyutadagi usullarni qaytaradi.
    """
    filters = filters or {}
    company = filters.get("company")
    if not company:
        return []

    modes = get_transfer_mode_of_payments(company, filters.get("source_mode_of_payment"))
    return _format_mode_of_payment_query_result(modes, txt)


def _format_mode_of_payment_query_result(modes, txt):
    if txt:
        txt_lower = txt.lower()
        modes = [m for m in modes if txt_lower in (m.mode_of_payment or "").lower()]

    return [[m.mode_of_payment, m.currency] for m in modes]


@frappe.whitelist()
def get_party_currency(party_type, party, company):
    """Party uchun default currency olish"""
    if not party_type or not party or not company:
        return None

    currency = None

    if party_type in ["Customer", "Supplier"]:
        account = erpnext_get_party_account(party_type, party, company)
        if account:
            currency = frappe.get_cached_value("Account", account, "account_currency")
        if not currency:
            default_field = "default_currency"
            currency = frappe.get_cached_value(party_type, party, default_field)
        if not currency:
            currency = frappe.get_cached_value("Company", company, "default_currency")
    elif party_type == "Shareholder":
        account = erpnext_get_party_account(party_type, party, company)
        if account:
            currency = frappe.get_cached_value("Account", account, "account_currency")
        if not currency:
            currency = frappe.get_cached_value("Company", company, "default_currency")
    elif party_type == "Employee":
        # tartibsiz tanlov o'rniga — barqaror hisob (get_employee_payable_account)
        account = get_employee_payable_account(company)
        if account:
            currency = frappe.get_cached_value("Account", account, "account_currency")
        if not currency:
            currency = frappe.get_cached_value("Company", company, "default_currency")
    else:
        currency = frappe.get_cached_value("Company", company, "default_currency")

    return currency


@frappe.whitelist()
def get_account_balance(account, company):
    """Account balansini account currency da olish"""
    if not account:
        return 0

    # Get balance in account currency (debit_in_account_currency - credit_in_account_currency)
    balance = frappe.db.sql("""
        SELECT SUM(debit_in_account_currency) - SUM(credit_in_account_currency) as balance
        FROM `tabGL Entry`
        WHERE account = %s
        AND company = %s
        AND is_cancelled = 0
    """, (account, company), as_dict=True)

    if balance and balance[0].balance:
        return flt(balance[0].balance)
    return 0


def get_expense_parent_account(company):
    """Xarajat papkalari joylashgan guruh — "Indirect Expenses".

    CoA boshqa tilda bo'lsa yoki bu guruh bo'lmasa, Expense ildizi ishlatiladi.
    """
    if not company:
        return None

    account = frappe.db.get_value(
        "Account",
        {
            "company": company,
            "account_name": EXPENSE_PARENT_ACCOUNT_NAME,
            "is_group": 1,
            "root_type": "Expense",
        },
        ["name", "lft", "rgt"],
        as_dict=True,
    )
    if account:
        return account

    roots = frappe.get_all(
        "Account",
        filters={"company": company, "root_type": "Expense", "is_group": 1, "parent_account": ("is", "not set")},
        fields=["name", "lft", "rgt"],
        limit=1,
    )
    return roots[0] if roots else None


def get_expense_groups(company):
    """"Indirect Expenses" ichidagi papkalar (guruh account'lar).

    Shular Kassa'da "Тип контрагента" ro'yxatiga xarajat papkasi sifatida tushadi.
    """
    parent_account = get_expense_parent_account(company)
    if not parent_account:
        return []

    return frappe.get_all(
        "Account",
        filters={
            "company": company,
            "root_type": "Expense",
            "is_group": 1,
            "parent_account": parent_account.name,
        },
        fields=["name", "account_name"],
        order_by="lft asc",
    )


def is_expense_party_type(party_type, company=None):
    """party_type xarajat papkasi (Indirect Expenses ichidagi guruh) mi."""
    if not party_type or party_type in BASE_PARTY_TYPES:
        return False

    account = frappe.db.get_value(
        "Account", party_type, ["company", "root_type", "is_group", "parent_account"], as_dict=True
    )
    if not account or not cint(account.is_group) or account.root_type != "Expense":
        return False
    if company and account.company != company:
        return False

    parent_account = get_expense_parent_account(account.company)
    return bool(parent_account and account.parent_account == parent_account.name)


@frappe.whitelist()
def get_party_type_options(company=None):
    """Kassa'dagi "Тип контрагента" ro'yxati: standart party'lar + xarajat papkalari."""
    options = list(BASE_PARTY_TYPES)
    if company:
        options += [group.name for group in get_expense_groups(company)]
    return options


def get_expense_cost_center(expense_account):
    """Expense Cost Center jadvalidan cost center (doctype bo'lmasa — bo'sh)."""
    if not frappe.db.exists("DocType", "Expense Cost Center"):
        return None
    return frappe.db.get_value(
        "Expense Cost Center", {"expense_account": expense_account}, "cost_center"
    )


def _expense_scope(company, expense_group=None):
    """Xarajat hisoblari qidiriladigan soha: tanlangan papka yoki umumiy parent."""
    if expense_group and is_expense_party_type(expense_group, company):
        return frappe.db.get_value("Account", expense_group, ["name", "lft", "rgt"], as_dict=True)
    return get_expense_parent_account(company)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_expense_accounts(doctype, txt, searchfield, start, page_len, filters):
    """Tanlangan xarajat papkasi ichidagi leaf account'lar."""
    filters = filters or {}
    company = filters.get("company")
    scope = _expense_scope(company, filters.get("expense_group"))

    if not scope:
        return []

    return frappe.db.sql("""
        SELECT name, account_name
        FROM `tabAccount`
        WHERE company = %(company)s
        AND root_type = 'Expense'
        AND is_group = 0
        AND lft > %(parent_lft)s
        AND rgt < %(parent_rgt)s
        AND (name LIKE %(txt)s OR account_name LIKE %(txt)s)
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """, {
        "company": company,
        "parent_lft": scope.lft,
        "parent_rgt": scope.rgt,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_customer_invoice_options(doctype, txt, searchfield, start, page_len, filters):
    """`Nachisleniya` maydoni ro'yxati — o'quvchining shu KATEGORIYADAGI ochiq
    nachisleniyalari (kategoriya berilmasa — hammasi).

    Kassir qo'lda tanlaganda ham noto'g'ri kategoriyadagi hujjat chiqib
    qolmaydi: kategoriya o'zgarsa ro'yxat ham o'zgaradi.
    """
    filters = filters or {}
    customer = filters.get("customer")
    if not customer:
        return []

    # Kirimda — ochiq (to'lanmagan) nachisleniyalar; qaytimda esa PULI TUSHGAN
    # yoki ortiqcha to'langanlari (qaytim shular uchun beriladi).
    if cint(filters.get("for_refund")):
        pul_sharti = """(si.outstanding_amount < -0.005
                         OR si.outstanding_amount < si.grand_total - 0.005)"""
    else:
        pul_sharti = "si.outstanding_amount > 0.005"

    shart = ["si.docstatus = 1", "si.customer = %(c)s", pul_sharti, "si.name LIKE %(txt)s"]
    args = {"c": customer, "txt": f"%{txt}%", "start": start, "page_len": page_len}
    if filters.get("company"):
        args["co"] = filters["company"]
        shart.append("si.company = %(co)s")
    kat_shart = _kategoriya_sharti(filters.get("category"), args)
    if kat_shart:
        shart.append(kat_shart)

    return frappe.db.sql(f"""
        SELECT si.name, si.posting_date, si.outstanding_amount
        FROM `tabSales Invoice` si
        WHERE {' AND '.join(shart)}
        ORDER BY si.posting_date ASC, si.name ASC
        LIMIT %(start)s, %(page_len)s
    """, args)


def validate_expense_account(expense_account, company, expense_group=None):
    """Xarajat hisobi tanlangan papka ichidagi leaf account ekanini tekshirish."""
    scope = _expense_scope(company, expense_group)

    if not scope:
        frappe.throw(_("Не найдена группа расходов ({0}) для компании {1}").format(
            EXPENSE_PARENT_ACCOUNT_NAME,
            company,
        ))

    account = frappe.db.get_value(
        "Account",
        expense_account,
        ["company", "root_type", "is_group", "lft", "rgt"],
        as_dict=True,
    )

    if (
        not account
        or account.company != company
        or account.root_type != "Expense"
        or cint(account.is_group)
        or account.lft <= scope.lft
        or account.rgt >= scope.rgt
    ):
        frappe.throw(_("Счет расходов должен быть внутри счета {0}").format(
            scope.name
        ))


@frappe.whitelist()
def get_exchange_rate(from_currency, to_currency, date=None):
    """Currency Exchange dan kursni olish"""
    if not date:
        date = frappe.utils.today()

    exchange_rate = frappe.db.get_value(
        "Currency Exchange",
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "date": ("<=", date)
        },
        "exchange_rate",
        order_by="date desc"
    )

    if exchange_rate:
        return flt(exchange_rate)

    reverse_rate = frappe.db.get_value(
        "Currency Exchange",
        {
            "from_currency": to_currency,
            "to_currency": from_currency,
            "date": ("<=", date)
        },
        "exchange_rate",
        order_by="date desc"
    )

    if reverse_rate and flt(reverse_rate) > 0:
        return flt(1 / flt(reverse_rate), 9)

    return 0


@frappe.whitelist()
def get_student_group(customer):
    """Customer'ga bog'langan o'quvchining sinfi (Student Group).

    Asosiy manba — faol Student Group a'zoligi (bir nechta bo'lsa vergul bilan);
    topilmasa Student'dagi "Sinf (guruh)" maydoni ishlatiladi. O'quvchi bo'lmasa
    bo'sh qaytadi (oddiy Customer uchun maydon ko'rinmaydi)."""
    if not customer:
        return None

    students = frappe.get_all("Student", filters={"customer": customer},
                              fields=["name", "custom_sinf_guruh"], limit=5)
    if not students:
        return None

    groups = []
    for st in students:
        rows = frappe.db.sql("""
            SELECT sg.student_group_name
            FROM `tabStudent Group Student` sgs
            JOIN `tabStudent Group` sg ON sg.name = sgs.parent
            WHERE sgs.student = %s AND sgs.active = 1 AND IFNULL(sg.disabled, 0) = 0
            ORDER BY sg.student_group_name
        """, st.name)
        for (g,) in rows:
            if g and g not in groups:
                groups.append(g)
        if not rows and st.custom_sinf_guruh and st.custom_sinf_guruh not in groups:
            groups.append(st.custom_sinf_guruh)

    return ", ".join(groups) if groups else None


def get_employee_payable_account(company):
    """Xodimlar oyligi yuritiladigan qarz hisobi — ANIQ va BARQAROR tanlanadi.

    Ilgari bu yerda `frappe.db.get_value("Account", {...})` turardi: u tartibsiz
    (order_by'siz) birinchi uchragan Payable hisobni qaytarardi. Yangi Payable
    hisob yaratilganda natija jimgina o'zgarib, xodim to'lovlari ikki xil hisobga
    bo'linib ketgan. Shuning uchun tartib quyidagicha:
      1) Company'dagi "Xodimlar qarzi hisobi" sozlamasi
      2) bo'sh bo'lsa — xodim yozuvlari eng ko'p bo'lgan hisob (tarixga mos)
      3) u ham bo'lmasa — nomi bo'yicha barqaror birinchi hisob
    """
    if not company:
        return None

    configured = frappe.db.get_value("Company", company, "custom_employee_payable_account")
    if configured:
        return configured

    rows = frappe.db.sql(
        """
        SELECT ge.account, COUNT(*) n
        FROM `tabGL Entry` ge
        JOIN `tabAccount` a ON a.name = ge.account
             AND a.account_type = 'Payable' AND a.is_group = 0
        WHERE ge.is_cancelled = 0 AND ge.party_type = 'Employee' AND ge.company = %s
        GROUP BY ge.account ORDER BY n DESC, ge.account ASC LIMIT 1
        """,
        company,
    )
    if rows:
        return rows[0][0]

    return frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Payable", "is_group": 0},
        "name",
        order_by="name asc",
    )


def _employee_payable_accounts(company):
    """Xodimlar qarzi yuritiladigan hisoblar."""
    return frappe.get_all(
        "Account",
        filters={"company": company, "account_type": "Payable", "is_group": 0},
        pluck="name",
    )


@frappe.whitelist()
def get_employee_accruals(employee, payment_month, company=None, account=None):
    """Xodimga shu OY uchun yozilgan nachisleniyalar (Journal Entry) va ularning qoldig'i.

    Oy hujjatdagi "За какой месяц" maydonidan, u bo'sh bo'lsa hujjat sanasidan
    olinadi — dashboarddagi qoida bilan bir xil. Faqat qoldig'i bor (hali to'liq
    to'lanmagan) nachisleniyalar qaytariladi, eskisidan yangisiga tartibda.

    `account` — to'lovning kontragent hisobi. Nachisleniyalar BARCHA hisoblardan
    qaytariladi, lekin har biriga `linkable` belgisi qo'yiladi: faqat shu hisobdagi
    nachisleniyaga bog'lanish mumkin (ERPNext talabi — aks holda "does not have
    account ..." xatosi). Boshqa hisobdagilar ham ko'rsatiladi, operator nega
    bog'lanmayotganini bilsin.
    """
    from erpnext.accounts.doctype.payment_entry.payment_entry import (
        get_outstanding_on_journal_entry,
    )

    if not employee or not payment_month:
        return []
    company = company or frappe.db.get_single_value("Global Defaults", "default_company")
    accounts = _employee_payable_accounts(company)
    if not accounts:
        return []

    rows = frappe.db.sql(
        """
        SELECT DISTINCT ge.voucher_no vn, ge.posting_date d, ge.account acc,
               ge.account_currency cur
        FROM `tabGL Entry` ge
        JOIN `tabJournal Entry` je ON je.name = ge.voucher_no AND je.docstatus = 1
        WHERE ge.is_cancelled = 0 AND ge.voucher_type = 'Journal Entry'
          AND ge.party_type = 'Employee' AND ge.party = %(emp)s
          AND ge.account IN %(accs)s AND ge.credit_in_account_currency > 0
          AND COALESCE(NULLIF(je.custom_payment_month, ''),
                       DATE_FORMAT(ge.posting_date, '%%Y-%%m')) = %(oy)s
        ORDER BY ge.posting_date
        """,
        {"emp": employee, "accs": tuple(accounts), "oy": payment_month},
        as_dict=True,
    )

    out = []
    for r in rows:
        try:
            outstanding, total = get_outstanding_on_journal_entry(r.vn, "Employee", employee)
        except Exception:
            continue
        if flt(outstanding) <= 0.005:
            continue                      # to'liq yopilgan — ko'rsatmaymiz
        out.append({
            "journal_entry": r.vn, "date": str(r.d), "account": r.acc,
            "currency": r.cur, "total": flt(total), "outstanding": flt(outstanding),
            "paid": flt(total) - flt(outstanding),
            "payments": _accrual_payments(r.vn),
            "linkable": (not account) or (r.acc == account),
        })
    return out


def _accrual_payments(journal_entry):
    """Shu nachisleniyaga bog'langan to'lovlar — Kassa raqami bilan.

    Operator Payment Entry emas, Kassa bilan ishlaydi; shuning uchun mumkin
    bo'lsa Kassa raqami ko'rsatiladi.
    """
    rows = frappe.db.sql("""
        SELECT ple.voucher_no pe, ABS(ple.amount_in_account_currency) amt,
               pe.posting_date d, pe.reference_no kassa
        FROM `tabPayment Ledger Entry` ple
        LEFT JOIN `tabPayment Entry` pe ON pe.name = ple.voucher_no
        WHERE ple.against_voucher_no = %s AND ple.delinked = 0
          AND ple.voucher_no != %s
        ORDER BY pe.posting_date
    """, (journal_entry, journal_entry), as_dict=True)
    return [{
        "payment_entry": r.pe,
        "kassa": r.kassa if (r.kassa and frappe.db.exists("Kassa", r.kassa)) else None,
        "amount": flt(r.amt),
        "date": str(r.d) if r.d else "",
    } for r in rows]


@frappe.whitelist()
def get_kassa_payment_links(kassa):
    """Submit bo'lgan Kassa to'lovi qaysi nachisleniyalarga bog'langani.

    Kassa formasida "bu oy uchun nachisleniya" o'rniga — hujjat submit bo'lgach
    ALLAQACHON bog'langanini ko'rsatish uchun. Avans keyinroq (nachisleniya
    yozilganda) ulansa ham shu yerda ko'rinadi.
    """
    if not kassa:
        return {"payment_entry": None, "links": []}
    pe_name = frappe.db.get_value(
        "Payment Entry", {"reference_no": kassa, "docstatus": 1}, "name")
    if not pe_name:
        return {"payment_entry": None, "links": []}

    links = []
    # 1) Payment Entry'ning references jadvali. Keyinroq Payment Reconciliation
    #    orqali ulangan bog'lanishlar ham shu yerga tushadi, shuning uchun
    #    "qachon bog'landi" degan farq ishonchli emas — ko'rsatilmaydi.
    #    Xodim nachisleniyasi — Journal Entry, o'quvchi nachisleniyasi —
    #    Sales Invoice; ikkisi ham shu ro'yxatga tushadi.
    for r in frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": pe_name,
                     "reference_doctype": ["in", ["Journal Entry", "Sales Invoice"]]},
            fields=["reference_doctype", "reference_name", "allocated_amount"]):
        links.append({"doctype": r.reference_doctype,
                      "journal_entry": r.reference_name,
                      "amount": flt(r.allocated_amount)})

    # 2) Keyinroq Payment Reconciliation orqali ulanganlar (references'ga tushmaydi)
    seen = {x["journal_entry"] for x in links}
    for r in frappe.db.sql("""
            SELECT ple.against_voucher_type dt, ple.against_voucher_no je,
                   ABS(ple.amount_in_account_currency) amt
            FROM `tabPayment Ledger Entry` ple
            WHERE ple.voucher_no = %s AND ple.delinked = 0
              AND ple.against_voucher_no != ple.voucher_no
        """, pe_name, as_dict=True):
        if r.je and r.je not in seen:
            links.append({"doctype": r.dt or "Journal Entry",
                          "journal_entry": r.je, "amount": flt(r.amt)})
            seen.add(r.je)

    currency = frappe.db.get_value("Payment Entry", pe_name, "paid_to_account_currency")
    return {"payment_entry": pe_name, "links": links, "currency": currency}


@frappe.whitelist()
def get_customer_invoices(customer, company=None, account=None, invoice=None, category=None):
    """Mijozning (o'quvchining) ochiq nachisleniyalari — Sales Invoice qoldiqlari.

    Xodim nachisleniyalari (get_employee_accruals) bilan bir xil mantiq:
      * faqat qoldig'i bor hisob-fakturalar, eskisidan yangisiga;
      * `account` berilsa — faqat SHU qarz hisobidagilari bog'lanadi (ERPNext
        talabi), boshqalari ham qaytariladi, lekin `linkable=0` belgisi bilan;
      * `invoice` berilsa — faqat o'sha bitta hisob-faktura;
      * `category` berilsa — faqat shu kategoriya itemlari bor nachisleniyalar
        (o'quv to'lovi / kitob / forma / yotoqxona), ya'ni to'lov avtomatik
        bog'lanadigan maydon.

    Har qator uchun xodim jadvalidagidek `paid` (to'langani) va `payments`
    (qaysi kassalar orqali) ham qaytariladi.
    """
    if not customer:
        return []

    shart = ["si.docstatus = 1", "si.customer = %(c)s", "si.outstanding_amount > 0.005"]
    args = {"c": customer, "inv": invoice, "co": company}
    if company:
        shart.append("si.company = %(co)s")
    if invoice:
        shart.append("si.name = %(inv)s")
    if category and not invoice:
        kat_shart = _kategoriya_sharti(category, args)
        if kat_shart:
            shart.append(kat_shart)

    rows = frappe.db.sql(
        f"""SELECT si.name, si.posting_date, si.due_date, si.debit_to,
                   si.grand_total, si.outstanding_amount, si.currency,
                   (SELECT GROUP_CONCAT(DISTINCT sii.item_code ORDER BY sii.idx SEPARATOR ' + ')
                    FROM `tabSales Invoice Item` sii WHERE sii.parent = si.name) itemlar
            FROM `tabSales Invoice` si
            WHERE {' AND '.join(shart)}
            ORDER BY si.posting_date ASC, si.name ASC""",
        args, as_dict=True)

    out = []
    for r in rows:
        out.append({
            "name": r.name,
            "sana": str(r.posting_date),
            "muddat": str(r.due_date) if r.due_date else "",
            "itemlar": r.itemlar or "",
            "total": flt(r.grand_total),
            "outstanding": flt(r.outstanding_amount),
            "paid": flt(r.grand_total) - flt(r.outstanding_amount),
            "payments": _si_payments(r.name),
            "currency": r.currency,
            "account": r.debit_to,
            # Faqat to'lovning kontragent hisobidagi fakturaga bog'lanish mumkin
            "linkable": 1 if (not account or r.debit_to == account) else 0,
        })
    return [x for x in out if x["linkable"]] if account else out


@frappe.whitelist()
def get_overpaid_customer_invoices(customer, company=None, account=None, category=None, invoice=None):
    """Ortiqcha to'langan nachisleniyalar (outstanding < 0) — qaytim shularga bog'lanadi.

    ERPNext faqat shunday nachisleniyaga manfiy taqsimotni ruxsat beradi.
    """
    if not customer:
        return []

    shart = ["si.docstatus = 1", "si.customer = %(c)s", "si.outstanding_amount < -0.005"]
    args = {"c": customer, "co": company, "inv": invoice}
    if company:
        shart.append("si.company = %(co)s")
    if invoice:
        shart.append("si.name = %(inv)s")
    elif category:
        kat_shart = _kategoriya_sharti(category, args)
        if kat_shart:
            shart.append(kat_shart)

    rows = frappe.db.sql(
        f"""SELECT si.name, si.posting_date, si.debit_to, si.grand_total,
                   si.outstanding_amount, si.currency,
                   (SELECT GROUP_CONCAT(DISTINCT sii.item_code ORDER BY sii.idx SEPARATOR ' + ')
                    FROM `tabSales Invoice Item` sii WHERE sii.parent = si.name) itemlar
            FROM `tabSales Invoice` si
            WHERE {' AND '.join(shart)}
            ORDER BY si.posting_date ASC, si.name ASC""",
        args, as_dict=True)

    out = []
    for r in rows:
        out.append({
            "name": r.name,
            "sana": str(r.posting_date),
            "itemlar": r.itemlar or "",
            "total": flt(r.grand_total),
            "overpaid": abs(flt(r.outstanding_amount)),
            "currency": r.currency,
            "account": r.debit_to,
            "linkable": 1 if (not account or r.debit_to == account) else 0,
        })
    return [x for x in out if x["linkable"]] if account else out


@frappe.whitelist()
def get_customer_refund_info(customer, company=None, category=None, invoice=None):
    """Qaytim uchun ma'lumot: o'quvchining hisobida TURGAN pul va u qaysi to'lovlardan.

    Uch qism:
      * `avans`    — hisobda qolgan (nachisleniyaga bog'lanmagan) to'lovlar: har
                     biri qaysi Kassa orqali kelgani, qancha qolgani, qaysi
                     nachisleniyalarni yopgani bilan. Minus qatorlar — avval
                     berilgan qaytimlar.
      * `jami`     — hozir hisobda turgan pul (shundan qaytim berish mumkin).
      * `ortiqcha` — ortiqcha to'langan nachisleniyalar (qaytim ularga bog'lanadi).

    Manba — Payment Ledger Entry: PE'ning o'ziga qarshi qolgan qoldiq
    (`against_voucher_no = voucher_no`), ya'ni reconciliation hisobga olingan.
    """
    if not customer:
        return {"avans": [], "jami": 0, "ortiqcha": [], "currency": None}

    args = {"c": customer, "co": company}
    shart = ["ple.party_type = 'Customer'", "ple.party = %(c)s", "ple.delinked = 0",
             "ple.voucher_type = 'Payment Entry'", "ple.against_voucher_no = ple.voucher_no"]
    if company:
        shart.append("ple.company = %(co)s")

    rows = frappe.db.sql(
        f"""SELECT ple.voucher_no pe, ple.account_currency cur,
                   SUM(ple.amount_in_account_currency) net,
                   MAX(pe.posting_date) d, MAX(pe.reference_no) kassa,
                   MAX(pe.payment_type) typ
            FROM `tabPayment Ledger Entry` ple
            LEFT JOIN `tabPayment Entry` pe ON pe.name = ple.voucher_no
            WHERE {' AND '.join(shart)}
            GROUP BY ple.voucher_no, ple.account_currency
            HAVING ABS(SUM(ple.amount_in_account_currency)) > 0.005
            ORDER BY d ASC""",
        args, as_dict=True)

    avans, jami, currency = [], 0.0, None
    for r in rows:
        qoldiq = -flt(r.net)        # kredit (manfiy) = hisobda turgan pul
        jami += qoldiq
        currency = currency or r.cur
        siler = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": r.pe, "reference_doctype": "Sales Invoice"},
            fields=["reference_name", "allocated_amount"])
        avans.append({
            "payment_entry": r.pe,
            "kassa": r.kassa if (r.kassa and frappe.db.exists("Kassa", r.kassa)) else None,
            "date": str(r.d) if r.d else "",
            "turi": "qaytim" if r.typ == "Pay" else "to'lov",
            "qoldiq": qoldiq,
            "nachisleniyalar": [{"si": x.reference_name, "amount": flt(x.allocated_amount)}
                                for x in siler],
        })

    ortiqcha = get_overpaid_customer_invoices(
        customer, company, category=None if invoice else category, invoice=invoice)
    return {"avans": avans, "jami": jami, "ortiqcha": ortiqcha,
            "currency": currency or frappe.db.get_value("Company", company, "default_currency")}


def _si_payments(invoice):
    """Shu nachisleniyaga (Sales Invoice) bog'langan to'lovlar — Kassa raqami bilan.

    `_accrual_payments` (xodim nachisleniyasi) bilan bir xil: operator Payment
    Entry emas, Kassa bilan ishlaydi, shuning uchun mumkin bo'lsa Kassa
    raqami ko'rsatiladi.
    """
    rows = frappe.db.sql("""
        SELECT ple.voucher_no pe, ABS(ple.amount_in_account_currency) amt,
               pe.posting_date d, pe.reference_no kassa
        FROM `tabPayment Ledger Entry` ple
        LEFT JOIN `tabPayment Entry` pe ON pe.name = ple.voucher_no
        WHERE ple.against_voucher_no = %s AND ple.delinked = 0
          AND ple.voucher_no != %s
        ORDER BY pe.posting_date
    """, (invoice, invoice), as_dict=True)
    return [{
        "payment_entry": r.pe,
        "kassa": r.kassa if (r.kassa and frappe.db.exists("Kassa", r.kassa)) else None,
        "amount": flt(r.amt),
        "date": str(r.d) if r.d else "",
    } for r in rows]
