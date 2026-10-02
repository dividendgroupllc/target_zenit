# Copyright (c) 2026, Target Zenit
"""Oylik tabel — xodimlar stavka-kunlik davomat jadvali va oylik hisobi.

Old tomoni: Page "oylik-tabel" (jadval-ekran, katak bosib tahrirlash).
Orqa tomonda HRMS'ning haqiqiy hujjatlari ma'lumot yig'adi:
  - kunlik koeffitsient -> Attendance (custom_koef maydoni bilan)
  - oylik (baza) summa  -> "Tabel Oylik" (HAR OYga alohida qotirilgan qiymat;
    bo'lmasa Salary Structure Assignment, "Target Oylik" strukturasi) —
    bir oyni o'zgartirish boshqa oyga ta'sir qilmaydi
  - bonus               -> Additional Salary ("Bonus" komponenti)

Hisob (Employee.custom_tolov_turi bo'yicha):
  - Kunbay (default): kunlik narx = oylik / SHU OYDAGI norma ish kuni
    (Tabel Ish Kuni yozuvi -> Employee.custom_ish_kuni -> default 21/26),
    jami = kunlik narx * kelgan kunlar (0/1) + bonus.
  - Soatbay (o'qituvchilar): kataklarga SOAT yoziladi (0-24), shartnoma
    summasi (custom_oylik/SSA base) = SOAT NARXI,
    jami = soat narxi * oyda ishlagan soatlar + bonus.
JAMI ming so'mga PASTGA yaxlitlanadi (1 600 500 -> 1 600 000) —
nachisleniya/to'lov uchun aniq, tekis summa (amaldagi to'lov odati bilan mos).

Yo'qlama: barcha kunlar default 0 — har kuni zam direktor belgilaydi,
kim kelgan bo'lsa 1 qilinadi (faqat 0/1: keldi yoki kelmadi).
Belgilanmagan kun = kelmagan.

Oy yopilganda: belgilangan qoralamalar submit qilinadi (0 kunlarga yozuv
yaratilmaydi), tabel qulflanadi.
"""

import calendar
from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

SAHIFA = "oylik-tabel"
STRUKTURA = "Target Oylik"
BONUS_KOMPONENT = "Bonus"

OY_NOMLARI = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May", 6: "Iyun",
    7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

STATUS_KOEF = {"Present": 1.0, "Work From Home": 1.0, "Half Day": 0.5, "Absent": 0.0, "On Leave": 0.0}

# Norma ish kuni (oyiga) — HAR OY UCHUN ALOHIDA bo'lishi mumkin (sentabr 26,
# avgust 5 ...). Qidiruv tartibi: (1) "Tabel Ish Kuni" yozuvi (xodim+yil+oy),
# (2) Employee.custom_ish_kuni (doimiy norma), (3) default: o'qituvchi 21,
# qolgan barcha xodimlar 26.
DEFAULT_ISH_KUNI = 26
OQITUVCHI_ISH_KUNI = 21

# Hisoblangan oylik (JAMI) ming so'mga PASTGA yaxlitlanadi (kesiladi) —
# nachisleniya/to'lov uchun tekis summa. Foydalanuvchi amaliyoti: 445 3xx
# chiqsa 445 000 beriladi, 1 600 500 chiqsa ham 1 600 000 — doim pastga.
JAMI_YAXLITLASH = 1000


def _jami_yaxlitla(summa):
    """Ming so'mga pastga kesish: 1 600 999 -> 1 600 000."""
    return int(flt(summa) / JAMI_YAXLITLASH) * JAMI_YAXLITLASH


def _default_ish_kuni(lavozim):
    l = (lavozim or "").lower()
    if "teacher" in l or "o'qituvchi" in l or "oqituvchi" in l or "o‘qituvchi" in l or "o’qituvchi" in l:
        return OQITUVCHI_ISH_KUNI
    return DEFAULT_ISH_KUNI


def _oy_ish_kuni_map(yil, oy, emp_ids):
    """Shu oy uchun qo'lda kiritilgan norma ish kunlari: {xodim: kun}."""
    if not emp_ids:
        return {}
    return {r.xodim: cint(r.kun) for r in frappe.get_all(
        "Tabel Ish Kuni",
        filters={"yil": cint(yil), "oy": cint(oy), "xodim": ["in", emp_ids]},
        fields=["xodim", "kun"],
    )}


def _oy_oylik_map(yil, oy, emp_ids):
    """Shu oy uchun OYga qotirilgan oylik ish haqi: {xodim: summa} ("Tabel Oylik").
    Yozuvi bor oy — boshqa oylardagi o'zgarishlardan ta'sirlanmaydi."""
    if not emp_ids:
        return {}
    return {r.xodim: flt(r.summa) for r in frappe.get_all(
        "Tabel Oylik",
        filters={"yil": cint(yil), "oy": cint(oy), "xodim": ["in", emp_ids]},
        fields=["xodim", "summa"],
    )}


def _oy_oylik_yoz(xodim, yil, oy, summa):
    """Xodimning SHU OY uchun oylik yozuvini yaratish/yangilash ("Tabel Oylik").
    Qaytadi: eski qiymat (yozuv bo'lmagan bo'lsa None)."""
    yil, oy = cint(yil), cint(oy)
    mavjud = frappe.db.get_value(
        "Tabel Oylik", {"xodim": xodim, "yil": yil, "oy": oy}, ["name", "summa"], as_dict=True
    )
    if mavjud:
        frappe.db.set_value("Tabel Oylik", mavjud.name, "summa", flt(summa))
        return flt(mavjud.summa)
    frappe.get_doc({
        "doctype": "Tabel Oylik",
        "xodim": xodim, "yil": yil, "oy": oy, "summa": flt(summa),
    }).insert(ignore_permissions=True)
    return None


def _oy_amaldagi_oylik(xodim, yil, oy):
    """Oy uchun HOZIR amal qilayotgan oylik: "Tabel Oylik" yozuvi -> SSA
    (oy oxirigacha eng so'nggisi). Hech biri yo'q bo'lsa None."""
    rec = frappe.db.get_value(
        "Tabel Oylik", {"xodim": xodim, "yil": cint(yil), "oy": cint(oy)}, "summa"
    )
    if rec is not None:
        return flt(rec)
    oy_oxiri = _oy_chegara(yil, oy)[1]
    r = frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": xodim, "docstatus": 1, "from_date": ["<=", oy_oxiri]},
        fields=["base"], order_by="from_date desc", limit=1,
    )
    return flt(r[0].base) if r else None


def _keyingi_oylarni_muzlat(xodim, yil, oy):
    """Shu oydan KEYINGI ochilgan (Tabel Oyi mavjud) oylarda xodimning o'z
    "Tabel Oylik" yozuvi bo'lmasa — hozirgi amaldagi qiymatini oyga qotirib
    qo'yadi. Shunda bu oydagi o'zgarish keyingi oylarga "oqib o'tmaydi"."""
    yil, oy = cint(yil), cint(oy)
    for t in frappe.get_all("Tabel Oyi", fields=["yil", "oy"]):
        if (cint(t.yil), cint(t.oy)) <= (yil, oy):
            continue
        if frappe.db.exists("Tabel Oylik", {"xodim": xodim, "yil": t.yil, "oy": t.oy}):
            continue
        joriy = _oy_amaldagi_oylik(xodim, t.yil, t.oy)
        if joriy is not None:
            _oy_oylik_yoz(xodim, t.yil, t.oy, joriy)


def _oy_jami_map(yil, oy, emp_ids):
    """Shu oy uchun QO'LDA kiritilgan yakuniy JAMI summalar: {xodim: summa}.
    Bor bo'lsa avtomatik hisob o'rniga shu summa (bonus ham ichida) olinadi."""
    if not emp_ids:
        return {}
    return {r.xodim: flt(r.summa) for r in frappe.get_all(
        "Tabel Jami",
        filters={"yil": cint(yil), "oy": cint(oy), "xodim": ["in", emp_ids]},
        fields=["xodim", "summa"],
    )}


# ---------------------------------------------------------------- ruxsat

# Bu rollar tabelni faqat KO'RADI — hech narsani o'zgartira olmaydi
FAQAT_OQISH_ROLLARI = {"investor"}


def _ruxsat_rollari():
    """Kirish huquqi sahifaning (Page) role ro'yxatidan olinadi —
    egasi Page hujjatida rol qo'shsa/olib tashlasa, shu yerda ham amal qiladi."""
    rollar = frappe.get_all(
        "Has Role",
        filters={"parent": SAHIFA, "parenttype": "Page"},
        pluck="role",
    )
    return rollar or ["System Manager"]


def _rol_tekshir():
    """O'qish huquqi: sahifa rollaridan bittasi bo'lsa yetarli."""
    if not set(_ruxsat_rollari()) & set(frappe.get_roles()):
        frappe.throw(_("Oylik tabelga ruxsatingiz yo'q"), frappe.PermissionError)


def _tahrir_mumkinmi():
    """Tahrir huquqi: sahifa rollaridan faqat-o'qish bo'lmagani ham bo'lishi kerak
    (masalan, foydalanuvchida faqat 'investor' bo'lsa — ko'radi, o'zgartirmaydi)."""
    rollar = set(_ruxsat_rollari()) & set(frappe.get_roles())
    return any(r.strip().lower() not in FAQAT_OQISH_ROLLARI for r in rollar)


def _tahrir_tekshir():
    _rol_tekshir()
    if not _tahrir_mumkinmi():
        frappe.throw(_("Oylik tabel siz uchun faqat o'qish rejimida — o'zgartirish mumkin emas"),
                     frappe.PermissionError)


# ---------------------------------------------------------------- yordamchi

def _oy_chegara(yil, oy):
    yil, oy = cint(yil), cint(oy)
    if not (1 <= oy <= 12) or yil < 2020 or yil > 2100:
        frappe.throw(_("Oy/yil noto'g'ri"))
    kun_soni = calendar.monthrange(yil, oy)[1]
    return date(yil, oy, 1), date(yil, oy, kun_soni), kun_soni


def _tabel_doc(yil, oy):
    """Oy uchun Oylik Tabel hujjatini olish (bo'lmasa yaratish)."""
    nom = frappe.db.get_value("Tabel Oyi", {"yil": cint(yil), "oy": cint(oy)})
    if nom:
        return frappe.get_doc("Tabel Oyi", nom)
    doc = frappe.get_doc({"doctype": "Tabel Oyi", "yil": cint(yil), "oy": cint(oy), "holat": "Ochiq"})
    doc.insert(ignore_permissions=True)
    return doc


def _ochiq_tekshir(yil, oy):
    holat = frappe.db.get_value("Tabel Oyi", {"yil": cint(yil), "oy": cint(oy)}, "holat") or "Ochiq"
    if holat != "Ochiq":
        frappe.throw(_("{0} {1} tabeli yopiq — tahrirlab bo'lmaydi").format(OY_NOMLARI[cint(oy)], yil))


def _jurnal(xodim, xodim_ismi, oy_str, maydon, eski, yangi, sana=None):
    frappe.get_doc({
        "doctype": "Tabel Ozgarish Jurnali",
        "xodim": xodim,
        "xodim_ismi": xodim_ismi,
        "oy": oy_str,
        "sana": sana,
        "maydon": maydon,
        "eski": eski if eski is not None else "",
        "yangi": yangi if yangi is not None else "",
        "kim": frappe.session.user,
    }).insert(ignore_permissions=True)


def _kompaniya():
    return frappe.defaults.get_global_default("company")


def _valyuta(company=None):
    """Maosh hujjatlari (SSA, Additional Salary, struktura) DOIM UZS'da.
    Kompaniya valyutasi USD — uni ishlatmaymiz: maoshlar so'mda kelishilgan,
    Kassa/nachisleniya oqimi ham o'z UZS logikasida ishlayveradi."""
    return "UZS"


def _bonus_komponent_ta_minla():
    if not frappe.db.exists("Salary Component", BONUS_KOMPONENT):
        frappe.get_doc({
            "doctype": "Salary Component",
            "salary_component": BONUS_KOMPONENT,
            "salary_component_abbr": "BON",
            "type": "Earning",
        }).insert(ignore_permissions=True)


def _struktura_ta_minla():
    """"Target Oylik" Salary Structure (Basic = base formulasi bilan)."""
    company = _kompaniya()
    if not frappe.db.exists("Salary Structure", STRUKTURA):
        doc = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": STRUKTURA,
            "company": company,
            "payroll_frequency": "Monthly",
            "currency": _valyuta(company),
            "earnings": [{
                "salary_component": "Basic",
                "amount_based_on_formula": 1,
                "formula": "base",
            }],
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        doc.submit()
    else:
        doc = frappe.get_doc("Salary Structure", STRUKTURA)
        if doc.docstatus == 0:
            doc.flags.ignore_permissions = True
            doc.submit()
    return STRUKTURA


def _kassa_taklif(emp_ids, oy_boshi):
    """Har xodim uchun default oylik taklifi — Kassa'da xodimga qilingan
    to'lovlarning eng oxirgi to'liq oyi yig'indisi (joriy tabel oyidan oldingi)."""
    if not emp_ids:
        return {}
    chegara = oy_boshi.strftime("%Y-%m")
    rows = frappe.db.sql(
        """select party, date_format(`date`, '%%Y-%%m') as oy, sum(amount) as summa
           from `tabKassa`
           where docstatus = 1 and party_type = 'Employee'
             and transaction_type = 'Расход' and party in %(emps)s
             and date_format(`date`, '%%Y-%%m') < %(chegara)s
           group by party, oy""",
        {"emps": emp_ids, "chegara": chegara},
        as_dict=True,
    )
    eng_oxirgi = {}
    for r in rows:
        if r.party not in eng_oxirgi or r.oy > eng_oxirgi[r.party][0]:
            eng_oxirgi[r.party] = (r.oy, flt(r.summa))
    return {p: v[1] for p, v in eng_oxirgi.items()}


def _oylik_maydon_yoz(xodim, summa):
    """SSA yozilganda Employee.custom_oylik ("Oylik ish haqi (shartnoma)",
    Overview tabida) ham sinxron yangilanadi (db.set_value — hook qayta
    ishga tushmaydi)."""
    frappe.db.set_value("Employee", xodim, "custom_oylik", flt(summa), update_modified=False)


# ---------------------------------------------------------------- Employee hook

def employee_oylik_ssa(doc, method=None):
    """Employee saqlanganda: custom_oylik ("Oylik ish haqi (shartnoma)",
    Overview tabida) to'ldirilgan/o'zgartirilgan bo'lsa — Salary Structure
    Assignment avto-yaratiladi.

    from_date = saqlangan kun (bugun), xodim keyinroq ishga kirsa — kirish
    sanasi. Tabel va payroll SSA'dan o'qiyveradi."""
    if doc.flags.get("tabel_ssa_yaratilmasin"):
        return
    summa = flt(doc.get("custom_oylik"))
    if summa <= 0:
        return

    old = doc.get_doc_before_save()
    if old is not None and flt(old.get("custom_oylik")) == summa:
        return  # oylik o'zgarmagan — boshqa maydon saqlangan

    # amaldagi eng oxirgi SSA allaqachon shu summa bo'lsa — takror yozmaymiz
    joriy = frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": doc.name, "docstatus": 1},
        fields=["base"],
        order_by="from_date desc",
        limit=1,
    )
    if joriy and flt(joriy[0].base) == summa:
        return

    _bonus_komponent_ta_minla()
    _struktura_ta_minla()

    from_date = getdate(nowdate())
    if doc.date_of_joining and getdate(doc.date_of_joining) > from_date:
        from_date = getdate(doc.date_of_joining)

    # yangi qiymat shu sanadan g'olib bo'lishi uchun shu (va undan keyingi)
    # from_date'li eski SSA'lar bekor qilinadi — tabel set_oylik bilan
    # (from_date = oy boshi) aralashganda eski yozuv "yashirib" qo'ymasin
    eski = None
    for r in frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": doc.name, "from_date": [">=", from_date], "docstatus": 1},
        pluck="name",
    ):
        s = frappe.get_doc("Salary Structure Assignment", r)
        eski = flt(s.base)
        s.flags.ignore_permissions = True
        s.cancel()

    company = doc.company or _kompaniya()
    ssa = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": doc.name,
        "salary_structure": STRUKTURA,
        "from_date": from_date,
        "company": company,
        "currency": _valyuta(company),
        "base": summa,
    })
    ssa.flags.ignore_permissions = True
    ssa.insert(ignore_permissions=True)
    ssa.submit()

    _jurnal(doc.name, doc.employee_name, f"{from_date.year}-{from_date.month:02d}",
            "Oylik summa (Employee'dan)",
            str(eski) if eski is not None else "", str(summa))
    frappe.msgprint(
        _("Oylik {0} so'm — {1} dan amal qiladi (Salary Structure Assignment yaratildi)").format(
            frappe.format_value(summa, {"fieldtype": "Currency"}), from_date
        ),
        alert=True, indicator="green",
    )


# ---------------------------------------------------------------- asosiy hisob

def _tabel_hisobla(yil, oy, hamma_kunlar=False):
    """Tabelning to'liq holatini hisoblaydi (get_tabel ham, oy yopish ham ishlatadi).

    hamma_kunlar=True — oyning barcha kunlari (yopishda backfill uchun),
    aks holda faqat bugungacha bo'lgan kunlar ko'rsatiladi.
    """
    yil, oy = cint(yil), cint(oy)
    bugun = getdate(nowdate())
    oy_boshi, oy_oxiri, kun_soni = _oy_chegara(yil, oy)

    if oy_boshi > bugun:
        frappe.throw(_("Kelajak oy uchun tabel ochilmaydi"))

    if hamma_kunlar or oy_oxiri <= bugun:
        korinadigan = kun_soni
    else:
        korinadigan = bugun.day

    kunlar = []
    yakshanbalar = set()
    for k in range(1, kun_soni + 1):
        if date(yil, oy, k).weekday() == 6:
            yakshanbalar.add(k)
    for k in range(1, korinadigan + 1):
        kunlar.append({"kun": k, "sana": str(date(yil, oy, k)), "yakshanba": k in yakshanbalar})

    ish_kunlari = kun_soni - len(yakshanbalar)

    # Faqat "Oylik tabelda" belgisi qo'yilgan xodimlar — Active'lar ko'p (180+),
    # tabelga esa faqat hozir real ishlayotganlar kiradi.
    # Ishdan KETGANLAR (status=Left + relieving_date) ketgan OYIGACHA ko'rinadi:
    # o'sha oyda ketgan kunigacha ishlagan — undan keyingi kunlar "—" bo'ladi,
    # keyingi oylardan esa butunlay chiqib ketadi (belgini olish ham shart emas).
    xodimlar = frappe.get_all(
        "Employee",
        filters={"custom_tabelda": 1, "date_of_joining": ["<=", oy_oxiri]},
        fields=["name", "employee_name", "designation", "custom_ish_kuni",
                "custom_tolov_turi", "date_of_joining", "status", "relieving_date"],
        order_by="employee_name asc",
    )
    saralangan = []
    for x in xodimlar:
        ketgan = getdate(x.relieving_date) if x.relieving_date else None
        if x.status != "Active" and (not ketgan or ketgan < oy_boshi):
            continue                   # ketgan sanasi yo'q yoki bu oydan oldin ketgan
        if ketgan and ketgan < oy_boshi:
            continue                   # sana qo'yilgan, status hali almashmagan bo'lsa ham
        saralangan.append(x)
    xodimlar = saralangan
    emp_ids = [x.name for x in xodimlar]

    # Shu oy uchun qo'lda kiritilgan norma ish kunlari, oylik va jami summalar
    oy_ish_kuni = _oy_ish_kuni_map(yil, oy, emp_ids)
    oy_oylik = _oy_oylik_map(yil, oy, emp_ids)
    oy_jami = _oy_jami_map(yil, oy, emp_ids)

    # Oylik (baza): avval SHU OYga qotirilgan "Tabel Oylik" yozuvi,
    # bo'lmasa SSA'dan; bo'lmasa Kassa taklifi
    base_map = {}
    if emp_ids:
        for r in frappe.get_all(
            "Salary Structure Assignment",
            filters={"employee": ["in", emp_ids], "docstatus": 1, "from_date": ["<=", oy_oxiri]},
            fields=["employee", "base", "from_date"],
            order_by="from_date asc",
        ):
            base_map[r.employee] = flt(r.base)  # keyingi from_date ustun keladi
    kassa_map = _kassa_taklif(emp_ids, oy_boshi)

    # Kunlik koeffitsientlar: Attendance
    davomat = {}
    if emp_ids:
        for r in frappe.get_all(
            "Attendance",
            filters={
                "employee": ["in", emp_ids],
                "docstatus": ["<", 2],
                "attendance_date": ["between", [oy_boshi, oy_oxiri]],
            },
            fields=["employee", "attendance_date", "custom_koef", "status", "docstatus"],
        ):
            koef = flt(r.custom_koef) if r.custom_koef is not None else STATUS_KOEF.get(r.status, 1.0)
            davomat[(r.employee, getdate(r.attendance_date).day)] = koef

    # Bonuslar: Additional Salary
    bonus_map = {}
    if emp_ids:
        for r in frappe.get_all(
            "Additional Salary",
            filters={
                "employee": ["in", emp_ids],
                "docstatus": ["<", 2],
                "salary_component": BONUS_KOMPONENT,
                "payroll_date": ["between", [oy_boshi, oy_oxiri]],
            },
            fields=["employee", "amount"],
        ):
            bonus_map[r.employee] = bonus_map.get(r.employee, 0) + flt(r.amount)

    qatorlar = []
    for x in xodimlar:
        kirgan = getdate(x.date_of_joining) if x.date_of_joining else None
        soatbay = (x.custom_tolov_turi or "").strip() == "Soatbay"
        if x.name in oy_oylik:
            # shu oyga qotirilgan qiymat — boshqa oylar o'zgarsa ham o'zgarmaydi
            oylik = {"summa": oy_oylik[x.name], "manba": "oy"}
        elif x.name in base_map:
            oylik = {"summa": base_map[x.name], "manba": "ssa"}
        elif x.name in kassa_map and not soatbay:
            # Kassa taklifi oylik summa — soatbayning SOAT NARXI sifatida yaroqsiz
            oylik = {"summa": kassa_map[x.name], "manba": "kassa"}
        else:
            oylik = {"summa": 0.0, "manba": "yoq"}

        ketgan = getdate(x.relieving_date) if x.relieving_date else None
        kun_qatori = []
        koef_yigindi = 0.0
        for kd in kunlar:
            k = kd["kun"]
            sana_k = date(yil, oy, k)
            if kirgan and sana_k < kirgan:
                kun_qatori.append({"koef": None, "holat": "kirmagan"})
                continue
            if ketgan and sana_k > ketgan:
                # ishdan ketgan kundan keyingi kunlar — xuddi kirishdan oldingidek "—"
                kun_qatori.append({"koef": None, "holat": "ketgan"})
                continue
            if (x.name, k) in davomat:
                koef = davomat[(x.name, k)]
                holat = "saqlangan"
            else:
                # yo'qlama belgilanmagan kun = kelmagan (zam direktor kelganlarni 1 qiladi)
                koef = 0.0
                holat = "default"
            koef_yigindi += koef
            kun_qatori.append({"koef": koef, "holat": holat})

        bonus = bonus_map.get(x.name, 0.0)
        if soatbay:
            # Soatbay: kataklarda SOATLAR, shartnoma summasi = SOAT NARXI,
            # jami = soat narxi * ishlagan soatlar. Norma ish kuni qatnashmaydi.
            ish_kuni, ik_manba = 0, "soat"
            kunlik_narx = flt(oylik["summa"])          # bu yerda: 1 soat narxi
        else:
            # Kunbay: kunlik narx xodimning SHU OYDAGI norma ish kuniga bo'linadi:
            # oy uchun kiritilgani -> xodimning doimiy normasi -> default
            if x.name in oy_ish_kuni:
                ish_kuni, ik_manba = oy_ish_kuni[x.name], "oy"
            elif cint(x.custom_ish_kuni):
                ish_kuni, ik_manba = cint(x.custom_ish_kuni), "xodim"
            else:
                ish_kuni, ik_manba = _default_ish_kuni(x.designation), "default"
            kunlik_narx = (oylik["summa"] / ish_kuni) if ish_kuni else 0.0
        # nachisleniya uchun aniq summa — ming so'mga pastga yaxlitlanadi;
        # qo'lda kiritilgan jami bo'lsa — o'sha ustun keladi (bonus ham ichida)
        jami_avto = _jami_yaxlitla(kunlik_narx * koef_yigindi + bonus)
        if x.name in oy_jami:
            jami, jami_manba = oy_jami[x.name], "qolda"
        else:
            jami, jami_manba = jami_avto, "avto"

        qatorlar.append({
            "xodim": x.name,
            "ismi": x.employee_name,
            "lavozim": x.designation or "",
            "tolov_turi": "soat" if soatbay else "kun",
            "ish_kuni": ish_kuni,
            "ish_kuni_manba": ik_manba,
            "kirgan_sana": str(kirgan) if kirgan else None,
            "ketgan_sana": str(ketgan) if ketgan else None,
            "oylik": oylik,
            "kunlar": kun_qatori,
            "koef_yigindi": koef_yigindi,
            "kunlik_narx": kunlik_narx,
            "bonus": bonus,
            "jami": jami,
            "jami_avto": jami_avto,
            "jami_manba": jami_manba,
        })

    return {
        "yil": yil,
        "oy": oy,
        "oy_nomi": OY_NOMLARI[oy],
        "bugun": str(bugun),
        "kun_soni": kun_soni,
        "ish_kunlari": ish_kunlari,
        "kunlar": kunlar,
        "qatorlar": qatorlar,
        "jami_oylik": sum(q["jami"] for q in qatorlar),
        "jami_bonus": sum(q["bonus"] for q in qatorlar),
    }


# ---------------------------------------------------------------- whitelisted

@frappe.whitelist()
def get_tabel(yil=None, oy=None):
    _rol_tekshir()                     # o'qish — investor ham ko'radi
    bugun = getdate(nowdate())
    yil = cint(yil) or bugun.year
    oy = cint(oy) or bugun.month

    natija = _tabel_hisobla(yil, oy)
    tabel = _tabel_doc(yil, oy)
    oy_oxiri = _oy_chegara(yil, oy)[1]

    tahrir = _tahrir_mumkinmi()        # investor kabi faqat-o'qish rollarida False
    natija["holat"] = tabel.holat
    natija["faqat_oqish"] = not tahrir
    natija["tahrir_mumkin"] = tahrir and tabel.holat == "Ochiq"
    natija["yopish_mumkin"] = tahrir and tabel.holat == "Ochiq" and bugun >= oy_oxiri
    natija["ochish_mumkin"] = tahrir and tabel.holat == "Yopiq"
    return natija


@frappe.whitelist()
def set_koef(xodim, sana, koef):
    """Bitta kun katakchasini o'zgartirish -> Attendance yoziladi."""
    _tahrir_tekshir()
    sana = getdate(sana)
    koef = flt(koef)
    if sana > getdate(nowdate()):
        frappe.throw(_("Kelajak kunga yozib bo'lmaydi"))
    _ochiq_tekshir(sana.year, sana.month)

    emp = frappe.db.get_value(
        "Employee", xodim,
        ["name", "employee_name", "company", "date_of_joining", "relieving_date",
         "custom_tolov_turi"], as_dict=True
    )
    if not emp:
        frappe.throw(_("Xodim topilmadi"))

    # Kunbay: faqat 0/1 (keldi/kelmadi). Soatbay: kunlik ishlagan SOATLARI (0-24)
    if (emp.custom_tolov_turi or "").strip() == "Soatbay":
        if koef < 0 or koef > 24:
            frappe.throw(_("Soat 0 dan 24 gacha bo'lishi kerak"))
    elif koef not in (0.0, 1.0):
        frappe.throw(_("Faqat 0 (kelmadi) yoki 1 (keldi) kiritiladi"))
    if emp.date_of_joining and sana < getdate(emp.date_of_joining):
        frappe.throw(_("Xodim {0} da ishga kirgan — undan oldingi kunga yozib bo'lmaydi").format(emp.date_of_joining))
    if emp.relieving_date and sana > getdate(emp.relieving_date):
        frappe.throw(_("Xodim {0} da ishdan ketgan — undan keyingi kunga yozib bo'lmaydi").format(emp.relieving_date))

    status = "Present" if koef else "Absent"

    mavjud = frappe.get_all(
        "Attendance",
        filters={"employee": xodim, "attendance_date": sana, "docstatus": ["<", 2]},
        fields=["name", "docstatus", "custom_koef", "status"],
        limit=1,
    )
    eski = None
    if mavjud:
        eski_r = mavjud[0]
        eski = flt(eski_r.custom_koef) if eski_r.custom_koef is not None else STATUS_KOEF.get(eski_r.status)
        doc = frappe.get_doc("Attendance", eski_r.name)
        doc.flags.ignore_permissions = True
        if doc.docstatus == 1:
            # yopilib qayta ochilgan oy — eskisi bekor qilinib yangisi yoziladi
            doc.cancel()
            mavjud = None
        else:
            doc.status = status
            doc.custom_koef = koef
            doc.save(ignore_permissions=True)

    if not mavjud:
        doc = frappe.get_doc({
            "doctype": "Attendance",
            "naming_series": "HR-ATT-.YYYY.-",
            "employee": xodim,
            "attendance_date": sana,
            "status": status,
            "custom_koef": koef,
            "company": emp.company or _kompaniya(),
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)

    _jurnal(xodim, emp.employee_name, f"{sana.year}-{sana.month:02d}", "Kun koeffitsienti",
            "default" if eski is None else str(eski), str(koef), sana=sana)
    return {"ok": True, "koef": koef}


@frappe.whitelist()
def set_oylik(xodim, yil, oy, summa):
    """Oylik summani FAQAT SHU OY uchun o'rnatish -> "Tabel Oylik" (+ SSA).

    Har oyning oyligi alohida saqlanadi — bir oyni o'zgartirish boshqa oyga
    ta'sir qilmaydi:
      * qiymat "Tabel Oylik" yozuvi bilan OYga qotiriladi;
      * o'z yozuvi bo'lmagan KEYINGI ochilgan oylar avval joriy qiymatida
        muzlatiladi (o'zgarish ularga "oqib o'tmaydi");
      * SSA ham oy boshidan yoziladi (HRMS/payroll mosligi uchun), lekin
        faqat SHU OY ichidagi eski SSA'lar bekor qilinadi — keyingi
        oylarning SSA'lariga tegilmaydi."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    summa = flt(summa)
    if summa < 0:
        frappe.throw(_("Oylik manfiy bo'lmaydi"))
    _ochiq_tekshir(yil, oy)
    oy_boshi, oy_oxiri, _kun = _oy_chegara(yil, oy)

    emp = frappe.db.get_value(
        "Employee", xodim, ["name", "employee_name", "company", "date_of_joining"], as_dict=True
    )
    if not emp:
        frappe.throw(_("Xodim topilmadi"))

    _bonus_komponent_ta_minla()
    _struktura_ta_minla()

    # 1) Keyingi ochilgan oylarni (o'z yozuvi yo'qlarini) joriy qiymatida muzlatish
    _keyingi_oylarni_muzlat(xodim, yil, oy)

    # 2) Qiymatni shu OYga qotirish
    eski = _oy_amaldagi_oylik(xodim, yil, oy)
    _oy_oylik_yoz(xodim, yil, oy, summa)

    # 3) SSA (HRMS/payroll o'qiydi): from_date xodim kirgan kunidan oldin bo'lolmaydi
    from_date = oy_boshi
    if emp.date_of_joining and getdate(emp.date_of_joining) > oy_boshi:
        from_date = getdate(emp.date_of_joining)

    # faqat SHU OY ichidagi eski SSA'lar bekor qilinadi (Employee hook'i yozgani
    # ham shu oyda bo'lsa) — keyingi oylarning SSA'lari o'z joyida qoladi
    for r in frappe.get_all(
        "Salary Structure Assignment",
        filters={"employee": xodim, "docstatus": 1,
                 "from_date": ["between", [from_date, oy_oxiri]]},
        pluck="name",
    ):
        doc = frappe.get_doc("Salary Structure Assignment", r)
        doc.flags.ignore_permissions = True
        doc.cancel()

    company = emp.company or _kompaniya()
    doc = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": xodim,
        "salary_structure": STRUKTURA,
        "from_date": from_date,
        "company": company,
        "currency": _valyuta(company),
        "base": summa,
    })
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    doc.submit()

    # Employee.custom_oylik — "hozirgi" oylik: faqat eng so'nggi tabel oyi
    # (undan keyin ochilgan oy yo'q) tahrirlanganda sinxronlanadi, eski oyni
    # tuzatish xodimning joriy oyligini o'zgartirmaydi
    keyingi_bor = any(
        (cint(t.yil), cint(t.oy)) > (yil, oy)
        for t in frappe.get_all("Tabel Oyi", fields=["yil", "oy"])
    )
    if not keyingi_bor:
        _oylik_maydon_yoz(xodim, summa)

    _jurnal(xodim, emp.employee_name, f"{yil}-{oy:02d}", "Oylik summa",
            str(eski) if eski is not None else "", str(summa))
    return {"ok": True, "summa": summa}


@frappe.whitelist()
def set_ish_kuni(xodim, yil, oy, kun):
    """Xodimning norma ish kunini FAQAT SHU OY uchun o'rnatish -> "Tabel Ish Kuni".

    Har oyning normasi har xil bo'lishi mumkin (sentabr 26, avgust 5 ...),
    shuning uchun qiymat oyga biriktiriladi. Yozuv bo'lmagan oylarda xodimning
    doimiy normasi (Employee.custom_ish_kuni) yoki default (21/26) amal qiladi."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    kun = cint(kun)
    if not (1 <= kun <= 31):
        frappe.throw(_("Ish kuni 1 dan 31 gacha bo'lishi kerak"))
    _ochiq_tekshir(yil, oy)

    emp = frappe.db.get_value(
        "Employee", xodim,
        ["name", "employee_name", "designation", "custom_ish_kuni"], as_dict=True,
    )
    if not emp:
        frappe.throw(_("Xodim topilmadi"))

    mavjud = frappe.db.get_value(
        "Tabel Ish Kuni", {"xodim": xodim, "yil": yil, "oy": oy}, ["name", "kun"], as_dict=True
    )
    if mavjud:
        eski = cint(mavjud.kun)
        frappe.db.set_value("Tabel Ish Kuni", mavjud.name, "kun", kun)
    else:
        eski = cint(emp.custom_ish_kuni) or _default_ish_kuni(emp.designation)
        doc = frappe.get_doc({
            "doctype": "Tabel Ish Kuni",
            "xodim": xodim, "yil": yil, "oy": oy, "kun": kun,
        })
        doc.insert(ignore_permissions=True)

    _jurnal(xodim, emp.employee_name, f"{yil}-{oy:02d}", "Ish kuni (oy)",
            str(eski), str(kun))
    return {"ok": True, "kun": kun}


@frappe.whitelist()
def set_bonus(xodim, yil, oy, summa):
    """Oy oxiridagi bonus -> Additional Salary (Bonus komponenti, qoralama)."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    summa = flt(summa)
    if summa < 0:
        frappe.throw(_("Bonus manfiy bo'lmaydi"))
    _ochiq_tekshir(yil, oy)
    oy_boshi, oy_oxiri, _kun = _oy_chegara(yil, oy)

    emp = frappe.db.get_value(
        "Employee", xodim,
        ["name", "employee_name", "company", "date_of_joining"], as_dict=True,
    )
    if not emp:
        frappe.throw(_("Xodim topilmadi"))

    _bonus_komponent_ta_minla()
    _struktura_ta_minla()

    # HRMS Additional Salary xodimda SSA bo'lishini talab qiladi — yo'q bo'lsa,
    # tabelda ko'rinib turgan qiymat (Kassa taklifi yoki 0) bilan yaratib qo'yamiz
    if not frappe.db.exists(
        "Salary Structure Assignment", {"employee": xodim, "docstatus": 1}
    ):
        from_date = oy_boshi
        if emp.date_of_joining and getdate(emp.date_of_joining) > oy_boshi:
            from_date = getdate(emp.date_of_joining)
        company = emp.company or _kompaniya()
        taklif = _kassa_taklif([xodim], oy_boshi).get(xodim, 0.0)
        ssa = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": xodim,
            "salary_structure": STRUKTURA,
            "from_date": from_date,
            "company": company,
            "currency": _valyuta(company),
            "base": flt(taklif),
        })
        ssa.flags.ignore_permissions = True
        ssa.insert(ignore_permissions=True)
        ssa.submit()
        _oylik_maydon_yoz(xodim, flt(taklif))

    mavjud = frappe.get_all(
        "Additional Salary",
        filters={
            "employee": xodim,
            "salary_component": BONUS_KOMPONENT,
            "payroll_date": ["between", [oy_boshi, oy_oxiri]],
            "docstatus": ["<", 2],
        },
        fields=["name", "docstatus", "amount"],
    )
    eski = sum(flt(r.amount) for r in mavjud) if mavjud else None

    for r in mavjud:
        doc = frappe.get_doc("Additional Salary", r.name)
        doc.flags.ignore_permissions = True
        if doc.docstatus == 1:
            doc.cancel()
        else:
            frappe.delete_doc("Additional Salary", r.name, ignore_permissions=True, force=True)

    if summa > 0:
        company = emp.company or _kompaniya()
        doc = frappe.get_doc({
            "doctype": "Additional Salary",
            "employee": xodim,
            "company": company,
            "salary_component": BONUS_KOMPONENT,
            "currency": _valyuta(company),
            "amount": summa,
            "payroll_date": oy_oxiri,
            # Bonus "Target Oylik" strukturasiga kirmaydi — u ustidan yozish
            # emas, QO'SHIMCHA to'lov; aks holda HRMS xato beradi
            "overwrite_salary_structure_amount": 0,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)

    _jurnal(xodim, emp.employee_name, f"{yil}-{oy:02d}", "Bonus",
            str(eski) if eski is not None else "", str(summa))
    return {"ok": True, "summa": summa}


@frappe.whitelist()
def set_jami(xodim, yil, oy, summa):
    """Yakuniy JAMI oylikni qo'lda o'rnatish (FAQAT shu oy uchun) -> "Tabel Jami".

    Qo'lda kiritilgan summa avtomatik hisob o'rnini bosadi (bonus ham ichida
    hisoblanadi). 0 yoki bo'sh kiritilsa — qo'lda qiymat O'CHIRILADI va
    avtomatik hisobga qaytadi."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    summa = flt(summa)
    if summa < 0:
        frappe.throw(_("Summa manfiy bo'lmaydi"))
    _ochiq_tekshir(yil, oy)

    emp = frappe.db.get_value("Employee", xodim, ["name", "employee_name"], as_dict=True)
    if not emp:
        frappe.throw(_("Xodim topilmadi"))

    mavjud = frappe.db.get_value(
        "Tabel Jami", {"xodim": xodim, "yil": yil, "oy": oy}, ["name", "summa"], as_dict=True
    )
    eski = flt(mavjud.summa) if mavjud else None

    if summa == 0:
        # qo'lda qiymatni olib tashlash — avtomatik hisobga qaytadi
        if mavjud:
            frappe.delete_doc("Tabel Jami", mavjud.name, ignore_permissions=True, force=True)
            _jurnal(xodim, emp.employee_name, f"{yil}-{oy:02d}", "Jami (qo'lda)",
                    str(eski), "avto hisobga qaytarildi")
        return {"ok": True, "summa": 0, "avto": True}

    if mavjud:
        frappe.db.set_value("Tabel Jami", mavjud.name, "summa", summa)
    else:
        frappe.get_doc({
            "doctype": "Tabel Jami",
            "xodim": xodim, "yil": yil, "oy": oy, "summa": summa,
        }).insert(ignore_permissions=True)

    _jurnal(xodim, emp.employee_name, f"{yil}-{oy:02d}", "Jami (qo'lda)",
            str(eski) if eski is not None else "avto", str(summa))
    return {"ok": True, "summa": summa}


@frappe.whitelist()
def oy_yop(yil, oy):
    """Oyni yopish: bo'sh kunlar Attendance bilan to'ldiriladi (default),
    hammasi submit bo'ladi, oylik summalar SSA sifatida saqlanadi, tabel qulflanadi.
    Og'ir ish — fonda (background job) bajariladi."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    _ochiq_tekshir(yil, oy)
    oy_oxiri = _oy_chegara(yil, oy)[1]
    if getdate(nowdate()) < oy_oxiri:
        frappe.throw(_("Oy hali tugamagan — {0} dan keyin yopish mumkin").format(oy_oxiri))

    tabel = _tabel_doc(yil, oy)
    tabel.db_set("holat", "Yopilmoqda")
    frappe.enqueue(
        "target_zenit.target_zenit.api.oylik_tabel._oy_yop_job",
        queue="long",
        timeout=7200,
        yil=yil,
        oy=oy,
        foydalanuvchi=frappe.session.user,
    )
    return {"ok": True, "holat": "Yopilmoqda"}


def _oy_yop_job(yil, oy, foydalanuvchi):
    try:
        _bonus_komponent_ta_minla()
        _struktura_ta_minla()
        natija = _tabel_hisobla(yil, oy, hamma_kunlar=True)
        oy_boshi, oy_oxiri, _kun = _oy_chegara(yil, oy)

        for q in natija["qatorlar"]:
            emp = q["xodim"]
            company = frappe.db.get_value("Employee", emp, "company") or _kompaniya()

            # 0) Oylik va ish kunini OYga qotirish — yopilgan oy keyinchalik
            # boshqa oylardagi (yoki Employee'dagi) o'zgarishlardan ta'sirlanmasin
            if q["oylik"]["manba"] != "oy" and flt(q["oylik"]["summa"]) > 0:
                _oy_oylik_yoz(emp, yil, oy, q["oylik"]["summa"])
            if q["tolov_turi"] == "kun" and q["ish_kuni_manba"] != "oy" and cint(q["ish_kuni"]):
                frappe.get_doc({
                    "doctype": "Tabel Ish Kuni",
                    "xodim": emp, "yil": yil, "oy": oy, "kun": cint(q["ish_kuni"]),
                }).insert(ignore_permissions=True)

            # 1) Oylik summa SSA'da yo'q bo'lsa — ko'rsatilgan qiymat bilan saqlab qo'yamiz
            if q["oylik"]["manba"] != "ssa":
                from_date = oy_boshi
                kirgan = getdate(q["kirgan_sana"]) if q["kirgan_sana"] else None
                if kirgan and kirgan > oy_boshi:
                    from_date = kirgan
                if not frappe.db.exists(
                    "Salary Structure Assignment",
                    {"employee": emp, "from_date": from_date, "docstatus": 1},
                ):
                    ssa = frappe.get_doc({
                        "doctype": "Salary Structure Assignment",
                        "employee": emp,
                        "salary_structure": STRUKTURA,
                        "from_date": from_date,
                        "company": company,
                        "currency": _valyuta(company),
                        "base": q["oylik"]["summa"],
                    })
                    ssa.flags.ignore_permissions = True
                    ssa.insert(ignore_permissions=True)
                    ssa.submit()
                    _oylik_maydon_yoz(emp, q["oylik"]["summa"])

            # 2) Belgilanmagan kunlar 0 (kelmagan) — yozuv yaratilmaydi,
            # hisobda baribir 0 bo'lib qoladi

        # 3) Oydagi barcha qoralama Attendance'larni submit qilish
        for nom in frappe.get_all(
            "Attendance",
            filters={"docstatus": 0, "attendance_date": ["between", [oy_boshi, oy_oxiri]]},
            pluck="name",
        ):
            doc = frappe.get_doc("Attendance", nom)
            doc.flags.ignore_permissions = True
            doc.submit()

        # 4) Bonus qoralamalarini submit qilish
        for nom in frappe.get_all(
            "Additional Salary",
            filters={
                "docstatus": 0,
                "salary_component": BONUS_KOMPONENT,
                "payroll_date": ["between", [oy_boshi, oy_oxiri]],
            },
            pluck="name",
        ):
            doc = frappe.get_doc("Additional Salary", nom)
            doc.flags.ignore_permissions = True
            doc.submit()

        tabel = _tabel_doc(yil, oy)
        tabel.db_set("holat", "Yopiq")
        tabel.db_set("yopgan_kim", foydalanuvchi)
        tabel.db_set("yopilgan_vaqt", now_datetime())
        _jurnal(None, "", f"{yil}-{oy:02d}", "Oy holati", "Ochiq", "Yopiq")
        frappe.db.commit()
        frappe.publish_realtime(
            "tabel_update",
            {"yil": yil, "oy": oy, "holat": "Yopiq", "xabar": f"{OY_NOMLARI[oy]} {yil} tabeli yopildi ✅"},
        )
    except Exception:
        frappe.db.rollback()
        tabel = _tabel_doc(yil, oy)
        tabel.db_set("holat", "Ochiq")
        frappe.db.commit()
        frappe.log_error(title="Oylik tabel yopishda xato", message=frappe.get_traceback())
        frappe.publish_realtime(
            "tabel_update",
            {"yil": yil, "oy": oy, "holat": "Ochiq", "xabar": "Oy yopishda xato — tizim jurnalini ko'ring ❌"},
        )


@frappe.whitelist()
def oy_och(yil, oy):
    """Yopiq oyni qayta ochish (sahifaga ruxsati bor rollar)."""
    _tahrir_tekshir()
    yil, oy = cint(yil), cint(oy)
    tabel = _tabel_doc(yil, oy)
    if tabel.holat != "Yopiq":
        frappe.throw(_("Bu oy yopiq emas"))
    tabel.db_set("holat", "Ochiq")
    _jurnal(None, "", f"{yil}-{oy:02d}", "Oy holati", "Yopiq", "Ochiq")
    return {"ok": True}
