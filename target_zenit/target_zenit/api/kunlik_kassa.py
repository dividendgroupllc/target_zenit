# Copyright (c) 2026, Target Zenit
"""Kunlik kassa — kunlik pul kirimi/chiqimi paneli (manba: Kassa doctype).

Jahon amaliyoti sintezi (1C Кассовая книга, SAP FBCJ, Odoo, POS Z-report,
treasury dashboardlar) asosida:
  * KPI: qoldiq, davr sof oqimi, kirim/chiqim (oldingi davr bilan taqqos),
    runway (pul necha kunga yetadi), eng katta tranzaksiya
  * kunlik diverging oqim + qoldiq chizig'i + kalendar heatmap
  * kategoriya/kontragent kesimlari (waterfall va Pareto uchun)
  * kun bo'yicha guruhlangan ledger (ochilsa — hujjatlar), КО-4 uslubida print

Summalar semantikasi (kassa.py bilan bir xil):
  Приход: cash_account +amount | Расход: cash_account -amount
  Перемещения/Конвертация: cash_account -debit_amount,
                           cash_account_to +credit_amount
Oqim (kirim/chiqim) FAQAT Приход/Расход; ko'chirma/konvertatsiya ichki
harakat — oqimga kirmaydi, lekin QOLDIQ hisobida to'liq qatnashadi.
Valyutalar aralashtirilmaydi — bitta valyuta hisoblari birga ko'rsatiladi.
"""

from __future__ import annotations

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

# Kunlik kassa — investor dashboardning bo'limi; ruxsat o'sha sahifadan olinadi
SAHIFA = "investor-dashboard"


def _guard():
    """Kirish — investor dashboard sahifasining (Page) rollari bo'yicha."""
    rollar = frappe.get_all(
        "Has Role", filters={"parent": SAHIFA, "parenttype": "Page"}, pluck="role"
    ) or ["System Manager"]
    if not set(rollar) & set(frappe.get_roles()):
        frappe.throw(_("Kunlik kassa bo'limiga ruxsatingiz yo'q"), frappe.PermissionError)


def _as_list(val):
    if not val:
        return []
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except Exception:
            val = [val]
    return [str(x) for x in val if x]


# Barcha hisob harakatlari (qoldiq uchun): (hisob, sana) -> imzoli summa.
# UNION: 1-qism har hujjatning o'z hisobiga ta'siri, 2-qism ko'chirma/
# konvertatsiyaning QABUL hisobiga ta'siri.
HARAKAT_UNION = """
    SELECT k.`date` sana, k.cash_account acc,
           CASE WHEN k.transaction_type = 'Приход' THEN k.amount
                WHEN k.transaction_type = 'Расход' THEN -k.amount
                ELSE -k.debit_amount END sgn
    FROM `tabKassa` k
    WHERE k.docstatus = 1 AND IFNULL(k.cash_account, '') != ''
    UNION ALL
    SELECT k.`date`, k.cash_account_to, k.credit_amount
    FROM `tabKassa` k
    WHERE k.docstatus = 1
      AND k.transaction_type IN ('Перемещения', 'Конвертация')
      AND IFNULL(k.cash_account_to, '') != ''
"""


def _hisoblar():
    """Kassada ishlatilgan barcha hisoblar va valyutalari."""
    out = {}
    for r in frappe.db.sql("""
        SELECT cash_account acc, COALESCE(NULLIF(cash_account_currency, ''), 'UZS') cur
        FROM `tabKassa` WHERE docstatus = 1 AND IFNULL(cash_account, '') != ''
        GROUP BY acc, cur
        UNION
        SELECT cash_account_to, COALESCE(NULLIF(cash_account_to_currency, ''), 'UZS')
        FROM `tabKassa` WHERE docstatus = 1 AND IFNULL(cash_account_to, '') != ''
    """, as_dict=True):
        out.setdefault(r.acc, r.cur)
    return out


def _kategoriya(tur, party_type, expense_account_name):
    """Hujjatning tahlil kategoriyasi (1C'dagi 'статья ДДС' o'rnida)."""
    pt = (party_type or "").strip()
    exp = (expense_account_name or "").strip()
    if tur == "Приход":
        nom = {"Customer": "O'quvchilar to'lovi", "Shareholder": "Ta'sischi kiritmasi",
               "Supplier": "Ta'minotchidan qaytim", "Employee": "Xodimdan qaytim"}.get(pt)
        return nom or exp or "Boshqa kirim"
    if pt == "Employee":
        return "Xodimlar (oylik)"
    if pt == "Supplier":
        return "Ta'minotchilar"
    if pt == "Customer":
        return "O'quvchiga qaytarish"
    return exp or (pt if pt else "Boshqa xarajat")


def _tanlov(currency=None, accounts=None):
    """Valyuta + hisob tanlovini hal qiladi -> (cur, sel_accounts, hamma_hisoblar)."""
    hisoblar = _hisoblar()
    curlar = sorted({c for c in hisoblar.values()})
    cur = currency if currency in curlar else ("UZS" if "UZS" in curlar else (curlar[0] if curlar else "UZS"))
    cur_accs = [a for a, c in hisoblar.items() if c == cur]
    sel = [a for a in _as_list(accounts) if a in cur_accs] or cur_accs
    return cur, sel, hisoblar, curlar


def _oqim_qatorlar(sel, f, t):
    """Davr oqimi — hujjat guruhlari kesimida (kategoriya/kontragent filtrini
    Python'da qo'llash uchun; kategoriya SQL'da hisoblanmaydi)."""
    return frappe.db.sql("""
        SELECT `date` sana, transaction_type tur, party_type,
               expense_account_name, party_name,
               SUM(amount) s, COUNT(*) n, MAX(amount) mx
        FROM `tabKassa`
        WHERE docstatus = 1 AND transaction_type IN ('Приход', 'Расход')
          AND cash_account IN %(sel)s AND `date` BETWEEN %(f)s AND %(t)s
        GROUP BY sana, tur, party_type, expense_account_name, party_name
    """, {"sel": sel, "f": str(f), "t": str(t)}, as_dict=True)


# "Xarajatlar" kontragent turi — kassadagi xarajat psevdo-turlari birlashmasi
XARAJAT_PT = ("Budget xarajati - TZ", "Xarajatlar - TZ", "Расходы")


def _pt_mos(row_pt, party_type):
    """Qator kontragent turi tanlangan turga mosmi."""
    if not party_type:
        return True
    pt = (row_pt or "").strip()
    if party_type == "Xarajatlar":
        return pt in XARAJAT_PT or pt == ""
    return pt == party_type


def _mos(r, kategoriya, party, tur=None, party_type=None):
    """Guruh qatori tanlangan filtrlar to'plamiga mos keladimi."""
    if tur in ("Приход", "Расход") and r.tur != tur:
        return False
    if tur in ("Перемещения", "Конвертация"):
        return False      # ichki harakat rejimi — oqim qatorlari qatnashmaydi
    if kategoriya and _kategoriya(r.tur, r.party_type, r.expense_account_name) != kategoriya:
        return False
    if party and (r.party_name or "").strip() != party:
        return False
    if not _pt_mos(r.party_type, party_type):
        return False
    return True


@frappe.whitelist()
def get_data(from_date=None, to_date=None, currency=None, accounts=None,
             kategoriya=None, party=None, tur=None, party_type=None):
    _guard()
    t0 = getdate(to_date or nowdate())
    f0 = getdate(from_date) if from_date else add_days(t0, -29)
    if f0 > t0:
        f0, t0 = t0, f0
    cur, sel, hisoblar, curlar = _tanlov(currency, accounts)
    if not sel:
        return {"empty": True, "currencies": curlar}
    davr_kun = (t0 - f0).days + 1
    kategoriya = (kategoriya or "").strip()
    party = (party or "").strip()
    tur = (tur or "").strip()
    party_type = (party_type or "").strip()

    # ── Qoldiqlar (barcha harakat turlari bilan) ────────────────────────────
    opening = flt(frappe.db.sql(f"""
        SELECT COALESCE(SUM(h.sgn), 0) FROM ({HARAKAT_UNION}) h
        WHERE h.acc IN %(sel)s AND h.sana < %(f)s
    """, {"sel": sel, "f": str(f0)})[0][0])

    kun_harakat = {str(r.sana): flt(r.s) for r in frappe.db.sql(f"""
        SELECT h.sana, SUM(h.sgn) s FROM ({HARAKAT_UNION}) h
        WHERE h.acc IN %(sel)s AND h.sana BETWEEN %(f)s AND %(t)s
        GROUP BY h.sana
    """, {"sel": sel, "f": str(f0), "t": str(t0)}, as_dict=True)}

    hisob_qoldiq = {r.acc: flt(r.s) for r in frappe.db.sql(f"""
        SELECT h.acc, SUM(h.sgn) s FROM ({HARAKAT_UNION}) h
        WHERE h.acc IN %(accs)s GROUP BY h.acc
    """, {"accs": list(hisoblar)}, as_dict=True)}

    # ── Oqim: kunlik kirim/chiqim (faqat Приход/Расход) ─────────────────────
    # Filtr menyulari uchun TO'LIQ ro'yxatlar (filtr qo'llanmasdan oldin)
    qatorlar = _oqim_qatorlar(sel, f0, t0)
    kat_royxat = defaultdict(float)
    party_royxat = defaultdict(float)
    for r in qatorlar:
        kat_royxat[_kategoriya(r.tur, r.party_type, r.expense_account_name)] += flt(r.s)
        pn = (r.party_name or "").strip()
        if pn:
            party_royxat[pn] += flt(r.s)

    # oqim  — TUR filtri BILAN (jadval/diagramma uchun)
    # oqim0 — TUR filtrisiz  (KPI kartalar uchun: Kirim bosilganda Chiqim
    #         kartasi 0 bo'lib qolmasin — ikkala tomon haqiqiy summada qoladi)
    oqim, oqim0 = {}, {}
    for r in qatorlar:
        if _mos(r, kategoriya, party, None, party_type):
            d0 = oqim0.setdefault(str(r.sana), {"kirim": 0.0, "chiqim": 0.0, "n": 0})
            d0["kirim" if r.tur == "Приход" else "chiqim"] += flt(r.s)
            d0["n"] += cint(r.n)
        if not _mos(r, kategoriya, party, tur, party_type):
            continue
        d = oqim.setdefault(str(r.sana), {"kirim": 0.0, "chiqim": 0.0, "n": 0})
        d["kirim" if r.tur == "Приход" else "chiqim"] += flt(r.s)
        d["n"] += cint(r.n)

    # Tur = ko'chirma/konvertatsiya tanlansa — kunlar ro'yxati shu hujjatlar
    # sonidan tuziladi (ular oqimga kirmaydi, jadvalda ochib ko'riladi)
    ichki_n = {}
    if tur in ("Перемещения", "Конвертация"):
        ichki_n = {str(r.sana): cint(r.n) for r in frappe.db.sql("""
            SELECT `date` sana, COUNT(*) n FROM `tabKassa`
            WHERE docstatus = 1 AND transaction_type = %(tur)s
              AND (cash_account IN %(sel)s OR cash_account_to IN %(sel)s)
              AND `date` BETWEEN %(f)s AND %(t)s
            GROUP BY sana
        """, {"tur": tur, "sel": sel, "f": str(f0), "t": str(t0)}, as_dict=True)}

    days, bal = [], opening
    d0 = f0
    while d0 <= t0:
        key = str(d0)
        o = oqim.get(key) or {"kirim": 0.0, "chiqim": 0.0, "n": 0}
        o0 = oqim0.get(key) or {"kirim": 0.0, "chiqim": 0.0, "n": 0}
        bal += kun_harakat.get(key, 0.0)
        n = ichki_n.get(key, 0) if ichki_n else o["n"]
        days.append({"sana": key, "kirim": o["kirim"], "chiqim": o["chiqim"],
                     "net": o["kirim"] - o["chiqim"], "n": n, "balans": bal,
                     "kirim0": o0["kirim"], "chiqim0": o0["chiqim"]})
        d0 = add_days(d0, 1)
    closing = bal

    # ── Oldingi davr (taqqoslash uchun; TUR filtrisiz — KPI bilan bir xil) ──
    pf, pt_ = add_days(f0, -davr_kun), add_days(f0, -1)
    prev = {"kirim": 0.0, "chiqim": 0.0}
    # Reyting jadvallaridagi "% Δ" ustuni uchun — oldingi davr kesimi
    prev_kat = {"Приход": defaultdict(float), "Расход": defaultdict(float)}
    prev_party = {"Приход": defaultdict(float), "Расход": defaultdict(float)}
    for r in _oqim_qatorlar(sel, pf, pt_):
        if _mos(r, kategoriya, party, None, party_type):
            prev["kirim" if r.tur == "Приход" else "chiqim"] += flt(r.s)
            prev_kat[r.tur][_kategoriya(r.tur, r.party_type, r.expense_account_name)] += flt(r.s)
            pn0 = (r.party_name or "").strip()
            if pn0:
                prev_party[r.tur][pn0] += flt(r.s)
    prev["net"] = prev["kirim"] - prev["chiqim"]

    # ── Diagramma uchun "oxirgi bir oy" (to_date'dan orqaga 30 kun) ────────
    # Foydalanuvchi qisqa davr tanlasa ham (masalan 1–8 oktabr), kunlik
    # diagramma to'liq oyni ko'rsatadi: 8 sentabr → 8 oktabr.
    oy_f = add_days(t0, -30)
    oylik_kirim = defaultdict(float)
    oylik_chiqim = defaultdict(float)
    oylik_n = defaultdict(int)
    for r in _oqim_qatorlar(sel, oy_f, t0):
        if not _mos(r, kategoriya, party, None, party_type):
            continue
        if r.tur == "Приход":
            oylik_kirim[str(r.sana)] += flt(r.s)
        else:
            oylik_chiqim[str(r.sana)] += flt(r.s)
        oylik_n[str(r.sana)] += cint(r.n)
    oylik_days = []
    dx = oy_f
    while dx <= t0:
        k = str(dx)
        oylik_days.append({"sana": k, "kirim": oylik_kirim.get(k, 0.0),
                           "chiqim": oylik_chiqim.get(k, 0.0),
                           "net": oylik_kirim.get(k, 0.0) - oylik_chiqim.get(k, 0.0),
                           "n": oylik_n.get(k, 0)})
        dx = add_days(dx, 1)

    # ── Runway: oxirgi 30 kunlik o'rtacha kunlik chiqim ─────────────────────
    chiqim30 = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) FROM `tabKassa`
        WHERE docstatus = 1 AND transaction_type = 'Расход'
          AND cash_account IN %(sel)s AND `date` BETWEEN %(f)s AND %(t)s
    """, {"sel": sel, "f": str(add_days(t0, -29)), "t": str(t0)})[0][0])
    avg_chiqim = chiqim30 / 30.0
    runway = (closing / avg_chiqim) if avg_chiqim > 0.005 and closing > 0 else None

    # ── Kategoriyalar va kontragentlar (filtrlangan qatorlardan) ───────────
    kat = {"Приход": defaultdict(lambda: {"summa": 0.0, "n": 0}),
           "Расход": defaultdict(lambda: {"summa": 0.0, "n": 0})}
    topd = {"Приход": defaultdict(lambda: {"summa": 0.0, "n": 0}),
            "Расход": defaultdict(lambda: {"summa": 0.0, "n": 0})}
    eng = None
    for r in qatorlar:
        if not _mos(r, kategoriya, party, tur, party_type):
            continue
        k = kat[r.tur][_kategoriya(r.tur, r.party_type, r.expense_account_name)]
        k["summa"] += flt(r.s)
        k["n"] += cint(r.n)
        pn = (r.party_name or "").strip()
        if pn:
            tp = topd[r.tur][pn]
            tp["summa"] += flt(r.s)
            tp["n"] += cint(r.n)
        if eng is None or flt(r.mx) > flt(eng.mx):
            eng = r

    def _delta(cur, old):
        """Oldingi davrga nisbatan o'zgarish: (oldingi summa, foiz yoki None)."""
        old = flt(old)
        if old <= 0.005:
            return old, None          # oldingi davrda bo'lmagan -> foiz ma'nosiz
        return old, round((flt(cur) - old) / old * 100, 1)

    def _kat_list(tur):
        out = []
        for lbl, v in kat[tur].items():
            old, pct = _delta(v["summa"], prev_kat[tur].get(lbl, 0))
            out.append({"label": lbl, "summa": v["summa"], "n": v["n"],
                        "prev": old, "delta_pct": pct})
        return sorted(out, key=lambda x: -x["summa"])

    def _top_list(tur, limit=8):
        out = []
        for lbl, v in topd[tur].items():
            old, pct = _delta(v["summa"], prev_party[tur].get(lbl, 0))
            out.append({"label": lbl, **v, "prev": old, "delta_pct": pct})
        return sorted(out, key=lambda x: -x["summa"])[:limit]

    top = {tur: _top_list(tur) for tur in ("Приход", "Расход")}

    # ── Eng katta tranzaksiya (filtr doirasida) ─────────────────────────────
    largest = None
    if eng is not None:
        row = frappe.db.sql("""
            SELECT name, `date` sana, transaction_type tur, amount,
                   party_name, expense_account_name, party_type
            FROM `tabKassa`
            WHERE docstatus = 1 AND transaction_type = %(tur)s
              AND cash_account IN %(sel)s AND amount = %(mx)s
              AND IFNULL(party_name, '') = %(pn)s
              AND `date` BETWEEN %(f)s AND %(t)s
            LIMIT 1
        """, {"tur": eng.tur, "sel": sel, "mx": eng.mx,
              "pn": (eng.party_name or ""), "f": str(f0), "t": str(t0)}, as_dict=True)
        largest = row[0] if row else None
    if largest:
        largest["kategoriya"] = _kategoriya(largest.tur, largest.party_type,
                                            largest.expense_account_name)

    # KPI jami — TUR filtrisiz (kirim0/chiqim0), jadval esa filtrlangan qoladi
    tot_k = sum(x["kirim0"] for x in days)
    tot_c = sum(x["chiqim0"] for x in days)
    return {
        "currency": cur, "currencies": curlar,
        "kategoriya": kategoriya, "party": party,
        "tur": tur, "party_type": party_type,
        "kategoriyalar": sorted(kat_royxat, key=lambda k: -kat_royxat[k]),
        "kontragentlar": sorted(party_royxat, key=lambda k: -party_royxat[k])[:200],
        "accounts": [{"account": a, "currency": c,
                      "balans": flt(hisob_qoldiq.get(a) or 0), "selected": a in sel}
                     for a, c in sorted(hisoblar.items())],
        "kpi": {
            "opening": opening, "closing": closing,
            "kirim": tot_k, "chiqim": tot_c, "net": tot_k - tot_c,
            "n": sum(x["n"] for x in days),
            "faol_kun": sum(1 for x in days if x["n"]),
            "prev": prev, "runway": runway, "avg_chiqim": avg_chiqim,
            "largest": largest,
        },
        "days": days,
        "oylik_days": oylik_days,
        "kirim_kat": _kat_list("Приход"), "chiqim_kat": _kat_list("Расход"),
        "top_kirim": top["Приход"], "top_chiqim": top["Расход"],
        "from_date": str(f0), "to_date": str(t0),
        "as_of": str(now_datetime())[:16],
    }


@frappe.whitelist()
def get_breakdown(from_date=None, to_date=None, currency=None, accounts=None,
                  tur=None, kategoriya=None, party=None):
    """Drill-down: bitta KATEGORIYA yoki KONTRAGENT bo'yicha tafsilot —
    kunlik dinamika + qarshi kesim (kategoriya bosilsa — kontragentlari,
    kontragent bosilsa — kategoriyalari). Diagramma bosilganda chaqiriladi."""
    _guard()
    t0 = getdate(to_date or nowdate())
    f0 = getdate(from_date) if from_date else add_days(t0, -29)
    cur, sel, _h, _c = _tanlov(currency, accounts)
    if not sel or tur not in ("Приход", "Расход"):
        return {"days": [], "top": []}

    rows = frappe.db.sql("""
        SELECT `date` sana, party_type, expense_account_name, party_name,
               SUM(amount) s, COUNT(*) n
        FROM `tabKassa`
        WHERE docstatus = 1 AND transaction_type = %(tur)s
          AND cash_account IN %(sel)s AND `date` BETWEEN %(f)s AND %(t)s
        GROUP BY sana, party_type, expense_account_name, party_name
    """, {"tur": tur, "sel": sel, "f": str(f0), "t": str(t0)}, as_dict=True)

    kategoriya = (kategoriya or "").strip()
    party = (party or "").strip()
    days = defaultdict(lambda: {"summa": 0.0, "n": 0})
    top = defaultdict(lambda: {"summa": 0.0, "n": 0})
    jami, n_jami = 0.0, 0
    for r in rows:
        kat = _kategoriya(tur, r.party_type, r.expense_account_name)
        pn = (r.party_name or "").strip()
        if kategoriya and kat != kategoriya:
            continue
        if party and pn != party:
            continue
        days[str(r.sana)]["summa"] += flt(r.s)
        days[str(r.sana)]["n"] += cint(r.n)
        jami += flt(r.s)
        n_jami += cint(r.n)
        # qarshi kesim: kategoriya tanlansa — kontragentlar, aks holda kategoriyalar
        qarshi = (pn or "(kontragentsiz)") if kategoriya else kat
        top[qarshi]["summa"] += flt(r.s)
        top[qarshi]["n"] += cint(r.n)

    kunlar = []
    d0 = f0
    while d0 <= t0:
        v = days.get(str(d0)) or {"summa": 0.0, "n": 0}
        kunlar.append({"sana": str(d0), "summa": v["summa"], "n": v["n"]})
        d0 = add_days(d0, 1)
    top_list = sorted([{"label": k, **v} for k, v in top.items()],
                      key=lambda x: -x["summa"])[:7]
    return {"days": kunlar, "top": top_list, "jami": jami, "n": n_jami,
            "tur": tur, "kategoriya": kategoriya, "party": party, "currency": cur}


@frappe.whitelist()
def get_day_docs(sana=None, currency=None, accounts=None, kategoriya=None, party=None,
                 tur=None, party_type=None):
    """Bitta kunning hujjatlari (ledger qatori ochilganda / КО-4 print uchun).

    Ko'chirma/konvertatsiya tanlangan hisoblarga ta'sir qiladigan OYOQLARGA
    bo'lib qaytariladi (ichki=1) — jadvalda kulrang, oqim jamiga kirmaydi,
    qoldiqqa esa kiradi. Kategoriya/kontragent filtri berilsa — faqat mos
    kirim/chiqim hujjatlari (ichki ko'chirmalar ko'rsatilmaydi)."""
    _guard()
    if not sana:
        frappe.throw(_("Sana ko'rsatilmagan"))
    sana = str(getdate(sana))
    cur, sel, _hh, _cc = _tanlov(currency, accounts)
    kategoriya = (kategoriya or "").strip()
    party = (party or "").strip()
    tur = (tur or "").strip()
    party_type = (party_type or "").strip()
    if not sel:
        return {"rows": []}

    rows = []
    for k in frappe.db.sql("""
        SELECT name, creation, transaction_type tur, mode_of_payment,
               mode_of_payment_to, cash_account, cash_account_to,
               amount, debit_amount, credit_amount,
               party_type, party_name, expense_account_name,
               payment_month, remarks, owner
        FROM `tabKassa`
        WHERE docstatus = 1 AND `date` = %(sana)s
          AND (cash_account IN %(sel)s
               OR (transaction_type IN ('Перемещения', 'Конвертация')
                   AND cash_account_to IN %(sel)s))
        ORDER BY creation
    """, {"sana": sana, "sel": sel}, as_dict=True):
        asos = {"name": k.name, "vaqt": str(k.creation)[11:16], "kim": k.owner,
                "izoh": (k.remarks or "").strip(), "oy": (k.payment_month or "").strip()}
        if k.tur in ("Приход", "Расход"):
            if tur and k.tur != tur:
                continue      # tur filtri: faqat tanlangan operatsiya turi
            kat_nomi = _kategoriya(k.tur, k.party_type, k.expense_account_name)
            if kategoriya and kat_nomi != kategoriya:
                continue
            if party and (k.party_name or "").strip() != party:
                continue
            if not _pt_mos(k.party_type, party_type):
                continue
            summa = flt(k.amount) if k.tur == "Приход" else -flt(k.amount)
            rows.append({**asos, "tur": k.tur, "hisob": k.cash_account,
                         "usul": k.mode_of_payment,
                         "kontragent": (k.party_name or "").strip() or (k.expense_account_name or "").strip(),
                         "kategoriya": kat_nomi,
                         "summa": summa, "ichki": 0})
        elif tur in ("Приход", "Расход") or kategoriya or party or party_type:
            continue          # ichki ko'chirmalar bu filtrlarga kirmaydi
        elif tur and k.tur != tur:
            continue          # tur = ko'chirma/konvertatsiya: faqat o'shanisi
        else:
            lbl = "Ko'chirma" if k.tur == "Перемещения" else "Konvertatsiya"
            if k.cash_account in sel:
                rows.append({**asos, "tur": lbl, "hisob": k.cash_account,
                             "usul": k.mode_of_payment,
                             "kontragent": f"→ {k.mode_of_payment_to or k.cash_account_to}",
                             "kategoriya": lbl, "summa": -flt(k.debit_amount), "ichki": 1})
            if k.cash_account_to in sel:
                rows.append({**asos, "tur": lbl, "hisob": k.cash_account_to,
                             "usul": k.mode_of_payment_to,
                             "kontragent": f"← {k.mode_of_payment or k.cash_account}",
                             "kategoriya": lbl, "summa": flt(k.credit_amount), "ichki": 1})

    # Kun boshi/oxiri qoldig'i (КО-4 print uchun) — har doim TO'LIQ kun bo'yicha
    # (kategoriya/kontragent filtri qoldiqni o'zgartirmaydi)
    opening = flt(frappe.db.sql(f"""
        SELECT COALESCE(SUM(h.sgn), 0) FROM ({HARAKAT_UNION}) h
        WHERE h.acc IN %(sel)s AND h.sana < %(sana)s
    """, {"sel": sel, "sana": sana})[0][0])
    kun_sum = flt(frappe.db.sql(f"""
        SELECT COALESCE(SUM(h.sgn), 0) FROM ({HARAKAT_UNION}) h
        WHERE h.acc IN %(sel)s AND h.sana = %(sana)s
    """, {"sel": sel, "sana": sana})[0][0])
    return {"rows": rows, "opening": opening, "closing": opening + kun_sum,
            "sana": sana, "currency": cur}
