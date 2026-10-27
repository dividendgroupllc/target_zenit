# Copyright (c) 2026, Target Zenit
# Sotuv bo'limi nazorati — alohida sahifa (2026-10-26 gacha investor dashboard
# ichidagi "Sotuv nazorati" bo'limi edi, butunlay shu yerga ko'chirildi).
#
# Ikki qism: menejerlar kesimi (reyting — faollik va natija yonma-yon) va
# qo'ng'iroqlar lentasi (kontrol-list: kim, kim bilan, qachon, qanday natija).
# Manbalar: Aloqa Yozuvi, Qarz Ishi, Tolov Vadasi, Payment Entry.
from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, flt, today

# Sahifani ocha oladigan rollar: rahbariyat/nazorat + sotuv bo'limi.
# Sotuv menejeri o'z statistikasini ko'radi (`_oz_ishini_korsin`), qolganlar —
# hamma menejerni.
ALLOWED_ROLES = [
    "System Manager",
    "Sales Manager",
    "Sales User",
    "Sotuv meneger",
    "investor",
    "Xojakbar_Operator",
    "Operator",
    "Accounts Manager",
    "Nigora_Moliya",
]


def _guard():
    allowed = {r.lower() for r in ALLOWED_ROLES}
    if not (allowed & {r.lower() for r in frappe.get_roles()}):
        frappe.throw(
            "Ruxsat yo'q. Sotuv nazorati sahifasi uchun sotuv yoki rahbariyat roli kerak.",
            frappe.PermissionError,
        )


SOTUV_YOPIQ = ("Yopildi - To'landi", "Yopildi - Boshqa")


def _oz_ishini_korsin() -> bool:
    """Sotuv menejeri faqat o'z statistikasini ko'radi; rahbar/investor — hammani."""
    roles = {r.lower() for r in frappe.get_roles()}
    rahbar = {"system manager", "sales manager", "investor", "xojakbar_operator",
              "accounts manager", "operator"}
    return not (rahbar & roles)


@frappe.whitelist()
def get_data(from_date=None, to_date=None, masul=None, limit=500):
    """Menejerlar kesimi (leaderboard) + qo'ng'iroqlar lentasi (kontrol-list)."""
    _guard()
    to_date = to_date or today()
    from_date = from_date or add_days(to_date, -30)

    faqat_ozi = _oz_ishini_korsin()
    if faqat_ozi:
        masul = frappe.session.user

    shart, params = ["ay.creation BETWEEN %(f)s AND %(t)s"], {
        "f": f"{from_date} 00:00:00", "t": f"{to_date} 23:59:59"}
    if masul:
        shart.append("ay.masul = %(m)s")
        params["m"] = masul
    where = " AND ".join(shart)

    # --- qo'ng'iroqlar lentasi ---
    aloqalar = frappe.db.sql(
        f"""SELECT ay.name, ay.creation, ay.vaqt, ay.owner, ay.masul, ay.kanal,
                   ay.aloqa_natijasi, ay.hisob_natijasi, ay.komment,
                   ay.keyingi_harakat, ay.keyingi_sana, ay.vada_summa, ay.vada_sana,
                   ay.qarz_ishi, ay.student_name, ay.student,
                   qi.sinf, qi.payer_name, qi.payer_phone, qi.qarz_summa,
                   qi.customer,
                   TIMESTAMPDIFF(MINUTE, ay.vaqt, ay.creation) kechikish_min,
                   (ay.modified > DATE_ADD(ay.creation, INTERVAL 1 MINUTE)) tahrirlangan
            FROM `tabAloqa Yozuvi` ay
            LEFT JOIN `tabQarz Ishi` qi ON qi.name = ay.qarz_ishi
            WHERE {where}
            ORDER BY ay.creation DESC
            LIMIT {int(limit)}""",
        params, as_dict=True)

    user_nomlari = {u.name: (u.full_name or u.name) for u in frappe.get_all(
        "User", fields=["name", "full_name"], limit_page_length=0)}

    for a in aloqalar:
        a["masul_nomi"] = user_nomlari.get(a.masul, a.masul)
        a["boshqa_kiritdi"] = 1 if (a.owner and a.masul and a.owner != a.masul) else 0
        # Sifat: izoh bor va mazmunli + keyingi sana bor
        a["sifatli"] = 1 if (a.komment or "").strip().__len__() >= 10 and a.keyingi_sana else 0
        # "Keyin kiritilgan": hodisa vaqti bilan yozuv vaqti orasida 2+ soat
        a["kech_kiritilgan"] = 1 if flt(a.kechikish_min) >= 120 else 0

    # --- menejerlar kesimi ---
    jadval = _sotuv_leaderboard(from_date, to_date, masul)

    jami = {
        "qongiroq": len(aloqalar),
        "gaplashildi": sum(1 for a in aloqalar if a.aloqa_natijasi == "Gaplashildi"),
        "ota_onalar": len({a.payer_phone or a.qarz_ishi for a in aloqalar
                           if a.aloqa_natijasi == "Gaplashildi"}),
        "vada_soni": sum(1 for a in aloqalar if a.hisob_natijasi == "Va'da berdi"),
        "vada_summa": sum(flt(a.vada_summa) for a in aloqalar),
        "yigildi": sum(flt(m["yigildi"]) for m in jadval),
        "sifatsiz": sum(1 for a in aloqalar if not a["sifatli"]),
    }
    return {
        "from_date": from_date, "to_date": to_date,
        "faqat_ozi": faqat_ozi,
        "jami": jami,
        "menejerlar": jadval,
        "aloqalar": aloqalar,
        "ochiq_ishlar": frappe.db.count(
            "Qarz Ishi", {"ishlov_status": ["not in", list(SOTUV_YOPIQ)]}),
    }


def _sotuv_leaderboard(from_date, to_date, masul=None):
    """Menejerlar kesimi: faollik + natija yonma-yon (jahon amaliyoti)."""
    m_shart = " AND ay.masul = %(m)s" if masul else ""
    params = {"f": f"{from_date} 00:00:00", "t": f"{to_date} 23:59:59", "m": masul}

    # 1) Faollik: qo'ng'iroqlar, ulanish, noyob ota-onalar, sifat
    faollik = frappe.db.sql(
        f"""SELECT ay.masul,
                   COUNT(*) qongiroq,
                   SUM(ay.aloqa_natijasi = 'Gaplashildi') ulandi,
                   COUNT(DISTINCT CASE WHEN ay.aloqa_natijasi='Gaplashildi'
                         THEN COALESCE(NULLIF(qi.payer_phone,''), ay.qarz_ishi) END) ota_onalar,
                   SUM(ay.hisob_natijasi = 'Va''da berdi') vada_soni,
                   COALESCE(SUM(ay.vada_summa), 0) vada_summa,
                   SUM(CHAR_LENGTH(COALESCE(ay.komment,'')) >= 10
                       AND ay.keyingi_sana IS NOT NULL) sifatli,
                   MAX(ay.creation) oxirgi_faollik
            FROM `tabAloqa Yozuvi` ay
            LEFT JOIN `tabQarz Ishi` qi ON qi.name = ay.qarz_ishi
            WHERE ay.creation BETWEEN %(f)s AND %(t)s {m_shart}
            GROUP BY ay.masul""",
        params, as_dict=True)

    # 2) Ochiq ishlar, qamrov, kechikkanlar — joriy mas'ul bo'yicha
    ishlar = frappe.db.sql(
        f"""SELECT qi.masul,
                   COUNT(*) ochiq_ish,
                   SUM(qi.keyingi_aloqa < %(bugun)s) kechikkan,
                   SUM(qi.urinishsiz) tegilmagan,
                   COALESCE(SUM(qi.qarz_summa), 0) qarz
            FROM (SELECT masul, keyingi_aloqa, qarz_summa,
                         (urinishlar_soni = 0) urinishsiz
                  FROM `tabQarz Ishi`
                  WHERE ishlov_status NOT IN ('Yopildi - To''landi', 'Yopildi - Boshqa')
                  {' AND masul = %(m)s' if masul else ''}) qi
            GROUP BY qi.masul""",
        {"bugun": today(), "m": masul}, as_dict=True)

    # 3) Va'dalar bajarilishi — va'da SANASI davrga tushganlar bo'yicha
    vadalar = frappe.db.sql(
        f"""SELECT tv.masul,
                   COUNT(*) vada_muddati_keldi,
                   SUM(tv.holat = 'Bajarildi') bajarildi,
                   SUM(tv.holat = 'Buzildi') buzildi
            FROM `tabTolov Vadasi` tv
            WHERE tv.vada_sana BETWEEN %(f)s AND %(t)s
              AND tv.holat != 'Bekor' {' AND tv.masul = %(m)s' if masul else ''}
            GROUP BY tv.masul""",
        {"f": from_date, "t": to_date, "m": masul}, as_dict=True)

    # 4) Yig'ilgan to'lov — ishning JORIY mas'uliga yoziladi (kelishilgan qoida)
    yigildi = frappe.db.sql(
        f"""SELECT qi.masul, COALESCE(SUM(
                     CASE WHEN pe.paid_from_account_currency = 'UZS' THEN pe.paid_amount
                          WHEN pe.paid_to_account_currency = 'UZS' THEN pe.received_amount
                          ELSE 0 END), 0) summa
            FROM `tabPayment Entry` pe
            JOIN `tabQarz Ishi` qi ON qi.customer = pe.party
            WHERE pe.docstatus = 1 AND pe.payment_type = 'Receive'
              AND pe.party_type = 'Customer'
              AND pe.posting_date BETWEEN %(f)s AND %(t)s
              {' AND qi.masul = %(m)s' if masul else ''}
            GROUP BY qi.masul""",
        {"f": from_date, "t": to_date, "m": masul}, as_dict=True)

    user_nomlari = {u.name: (u.full_name or u.name) for u in frappe.get_all(
        "User", fields=["name", "full_name", "enabled"], limit_page_length=0)}
    faol_userlar = {u.name: u.enabled for u in frappe.get_all(
        "User", fields=["name", "enabled"], limit_page_length=0)}

    qator = {}

    def olish(user):
        if user not in qator:
            qator[user] = {
                "masul": user, "nomi": user_nomlari.get(user, user),
                "faol": bool(faol_userlar.get(user, 0)),
                "qongiroq": 0, "ulandi": 0, "ota_onalar": 0, "vada_soni": 0,
                "vada_summa": 0.0, "sifatli": 0, "oxirgi_faollik": None,
                "ochiq_ish": 0, "kechikkan": 0, "tegilmagan": 0, "qarz": 0.0,
                "vada_muddati_keldi": 0, "bajarildi": 0, "buzildi": 0, "yigildi": 0.0,
            }
        return qator[user]

    for r in faollik:
        q = olish(r.masul)
        q.update({k: r[k] for k in ("qongiroq", "ulandi", "ota_onalar", "vada_soni",
                                    "sifatli", "oxirgi_faollik")})
        q["vada_summa"] = flt(r.vada_summa)
    for r in ishlar:
        q = olish(r.masul)
        q.update({"ochiq_ish": cint(r.ochiq_ish), "kechikkan": cint(r.kechikkan),
                  "tegilmagan": cint(r.tegilmagan), "qarz": flt(r.qarz)})
    for r in vadalar:
        q = olish(r.masul)
        q.update({"vada_muddati_keldi": cint(r.vada_muddati_keldi),
                  "bajarildi": cint(r.bajarildi), "buzildi": cint(r.buzildi)})
    for r in yigildi:
        olish(r.masul)["yigildi"] = flt(r.summa)

    out = []
    for q in qator.values():
        q["ulanish_foiz"] = round(q["ulandi"] / q["qongiroq"] * 100) if q["qongiroq"] else 0
        q["vada_foiz"] = round(q["vada_soni"] / q["ulandi"] * 100) if q["ulandi"] else 0
        q["kept_foiz"] = (round(q["bajarildi"] / q["vada_muddati_keldi"] * 100)
                          if q["vada_muddati_keldi"] else None)
        q["qamrov_foiz"] = (round((q["ochiq_ish"] - q["tegilmagan"]) / q["ochiq_ish"] * 100)
                            if q["ochiq_ish"] else None)
        q["sifat_foiz"] = round(q["sifatli"] / q["qongiroq"] * 100) if q["qongiroq"] else None
        out.append(q)
    out.sort(key=lambda x: (-x["qongiroq"], -x["yigildi"]))
    return out


# ===========================================================================
# Telefon suhbatlari kesimi — kim bilan qachon gaplashdi, ovoz yozuvi, matn,
# AI tahlil va ota-onalarning maktab bo'yicha takliflari.
# Manba: Telefon Qongirogi (raqam bo'yicha o'quvchiga bog'lanadi).
# ===========================================================================
TAKLIF_KALITLAR = ("TAKLIF VA SHIKOYAT", "MIJOZ TAKLIFI")
TAKLIF_YOQ = ("taklif yo'q", "taklif yoq", "yo'q", "yoq", "-", "—", "")
MAKS_TRANSKRIPT = 6000      # bitta javobda ortiqcha og'irlik qilmasin


def _taklif(ai_xulosa: str | None) -> str | None:
    """AI xulosasidan ota-onaning maktab bo'yicha taklifi/shikoyatini ajratadi.

    "Taklif yo'q" bo'lsa None qaytaradi — shunda ro'yxatga faqat haqiqiy
    takliflar tushadi."""
    for qator in str(ai_xulosa or "").splitlines():
        q = qator.strip()
        for kalit in TAKLIF_KALITLAR:
            if q.upper().startswith(kalit + ":"):
                matn = q[len(kalit) + 1:].strip()
                return None if matn.lower() in TAKLIF_YOQ else matn
    return None


def _xulosa_qatori(ai_xulosa: str | None, kalit: str) -> str:
    for qator in str(ai_xulosa or "").splitlines():
        q = qator.strip()
        if q.upper().startswith(kalit + ":"):
            return q[len(kalit) + 1:].strip()
    return ""


def _raqam_xarita() -> dict:
    """normal raqam -> {student, student_name, sinf, qarz_ishi}.

    Telefon Qongirogi'dagi raqamni o'quvchiga bog'lash uchun: to'lovchi,
    ota-onalar (Guardian) va o'quvchining o'z raqami. Ism/sinf JONLI o'qiladi
    (nusxadan emas)."""
    from target_zenit.telefoniya.utils import normalize_phone

    xarita = {}

    def qosh(raw, student, nomi, sinf):
        n = normalize_phone(raw)
        if n and n not in xarita:
            xarita[n] = {"student": student, "student_name": nomi, "sinf": sinf}

    for s in frappe.get_all(
        "Student",
        fields=["name", "student_name", "custom_sinf_guruh", "custom_payer_phone",
                "student_mobile_number"],
        limit_page_length=0,
    ):
        qosh(s.custom_payer_phone, s.name, s.student_name, s.custom_sinf_guruh)
        qosh(s.student_mobile_number, s.name, s.student_name, s.custom_sinf_guruh)

    for g in frappe.db.sql(
        """SELECT sg.parent student, s.student_name, s.custom_sinf_guruh sinf,
                  g.mobile_number tel
           FROM `tabStudent Guardian` sg
           JOIN `tabGuardian` g ON g.name = sg.guardian
           JOIN `tabStudent` s ON s.name = sg.parent
           WHERE sg.parenttype = 'Student'
             AND g.mobile_number IS NOT NULL AND g.mobile_number != ''
           ORDER BY sg.idx""",
        as_dict=True,
    ):
        qosh(g.tel, g.student, g.student_name, g.sinf)

    # Ochiq qarz ishi USTUN: bitta raqam bir nechta o'quvchiga tegishli bo'lishi
    # mumkin (ota-onaning ikki farzandi) — sotuv qo'ng'irog'i esa qarz bo'yicha
    # bo'ladi, shuning uchun qarz ishi bor farzand tanlanadi.
    for qi in frappe.get_all(
        "Qarz Ishi",
        filters={"ishlov_status": ["not in", list(SOTUV_YOPIQ)]},
        fields=["name", "student", "student_name", "sinf", "payer_phone"],
        order_by="qarz_summa desc",
        limit_page_length=0,
    ):
        n = normalize_phone(qi.payer_phone)
        if not n or xarita.get(n, {}).get("qarz_ishi"):
            continue      # shu raqamga qarzi kattaroq ish allaqachon biriktirilgan
        xarita[n] = {"student": qi.student, "student_name": qi.student_name,
                     "sinf": qi.sinf, "qarz_ishi": qi.name}
    return xarita


@frappe.whitelist()
def get_telefon(from_date=None, to_date=None, masul=None, limit=1200):
    """Telefon suhbatlari: menejer kesimi, kunlik faollik, o'quvchilar kesimi,
    suhbatlar ro'yxati (ovoz + matn + AI) va ota-onalar takliflari."""
    _guard()
    to_date = to_date or today()
    from_date = from_date or add_days(to_date, -30)
    if _oz_ishini_korsin():
        masul = frappe.session.user

    shart = ["tq.boshlandi BETWEEN %(f)s AND %(t)s"]
    params = {"f": f"{from_date} 00:00:00", "t": f"{to_date} 23:59:59", "m": masul}
    if masul:
        shart.append("tq.foydalanuvchi = %(m)s")

    qongiroqlar = frappe.db.sql(
        f"""SELECT tq.name, tq.boshlandi, tq.yonalish, tq.tugash_sababi, tq.holat,
                   tq.suhbat_vaqti, tq.yozuv_bor, tq.yozuv_ochirildi, tq.fayl_yoli,
                   tq.normal_telefon, tq.tashqi_raqam, tq.kontakt_ism, tq.izoh,
                   tq.foydalanuvchi, tq.xodim, tq.transkript_sozlar,
                   tq.ai_xulosa, tq.ai_model, tq.student
            FROM `tabTelefon Qongirogi` tq
            WHERE {" AND ".join(shart)}
            ORDER BY tq.boshlandi DESC
            LIMIT {int(limit)}""",
        params, as_dict=True)

    xarita = _raqam_xarita()
    userlar = {u.name: (u.full_name or u.name) for u in frappe.get_all(
        "User", fields=["name", "full_name"], limit_page_length=0)}
    xodimlar = {e.name: e.employee_name for e in frappe.get_all(
        "Employee", fields=["name", "employee_name"], limit_page_length=0)}

    menejer = {}
    oquvchi = {}
    kunlik = {}
    takliflar = []

    for q in qongiroqlar:
        mos = xarita.get(q.normal_telefon) or {}
        q["student"] = q.student or mos.get("student")
        q["student_name"] = mos.get("student_name") or q.kontakt_ism or ""
        q["sinf"] = mos.get("sinf") or ""
        q["qarz_ishi"] = mos.get("qarz_ishi")
        user = q.foydalanuvchi or (
            frappe.db.get_value("Employee", q.xodim, "user_id") if q.xodim else None)
        q["masul"] = user
        q["menejer"] = userlar.get(user) or xodimlar.get(q.xodim) or "—"
        q["audio"] = 1 if (q.yozuv_bor and not q.yozuv_ochirildi and q.fayl_yoli) else 0
        q["gaplashildi"] = 1 if (q.tugash_sababi == "Javob berildi" and flt(q.suhbat_vaqti) > 0) else 0
        q["mavzu"] = _xulosa_qatori(q.ai_xulosa, "MAVZU")
        q["natija"] = _xulosa_qatori(q.ai_xulosa, "NATIJA")
        taklif = _taklif(q.ai_xulosa)
        q["taklif"] = taklif or ""
        q["transkript_bor"] = 1 if cint(q.transkript_sozlar) else 0
        q.pop("fayl_yoli", None)

        sana = str(q.boshlandi)[:10]
        kalit = user or "—"
        m = menejer.setdefault(kalit, {
            "masul": kalit, "nomi": q["menejer"], "qongiroq": 0, "gaplashildi": 0,
            "daqiqa": 0.0, "mijozlar": set(), "oquvchilar": set(), "kunlar": set(),
            "yozuv": 0, "tahlil": 0, "taklif": 0, "oxirgi": None,
        })
        m["qongiroq"] += 1
        m["gaplashildi"] += q["gaplashildi"]
        m["daqiqa"] += flt(q.suhbat_vaqti) / 60.0
        m["kunlar"].add(sana)
        m["yozuv"] += q["audio"]
        m["tahlil"] += 1 if q.ai_xulosa else 0
        m["taklif"] += 1 if taklif else 0
        if q["gaplashildi"] and q.normal_telefon:
            m["mijozlar"].add(q.normal_telefon)
            if q["student"]:
                m["oquvchilar"].add(q["student"])
        if not m["oxirgi"] or str(q.boshlandi) > str(m["oxirgi"]):
            m["oxirgi"] = q.boshlandi

        kunlik.setdefault(sana, {}).setdefault(kalit, 0)
        kunlik[sana][kalit] += 1

        if q["student"]:
            o = oquvchi.setdefault(q["student"], {
                "student": q["student"], "student_name": q["student_name"],
                "sinf": q["sinf"], "qarz_ishi": q["qarz_ishi"],
                "qongiroq": 0, "gaplashildi": 0, "daqiqa": 0.0,
                "menejerlar": set(), "oxirgi": None, "oxirgi_mavzu": "", "taklif": 0,
            })
            o["qongiroq"] += 1
            o["gaplashildi"] += q["gaplashildi"]
            o["daqiqa"] += flt(q.suhbat_vaqti) / 60.0
            o["menejerlar"].add(q["menejer"])
            o["taklif"] += 1 if taklif else 0
            if not o["oxirgi"] or str(q.boshlandi) > str(o["oxirgi"]):
                o["oxirgi"] = q.boshlandi
                o["oxirgi_mavzu"] = q["mavzu"] or q["natija"] or (q.izoh or "")

        if taklif:
            takliflar.append({
                "qongiroq": q.name, "sana": q.boshlandi, "menejer": q["menejer"],
                "student": q["student"], "student_name": q["student_name"],
                "sinf": q["sinf"], "matn": taklif,
                "holat": _xulosa_qatori(q.ai_xulosa, "MIJOZ HOLATI"),
            })

    for m in menejer.values():
        m["mijozlar_soni"] = len(m["mijozlar"])
        m["oquvchilar_soni"] = len(m["oquvchilar"])
        m["kunlar_soni"] = len(m["kunlar"])
        m["kunlik_ortacha"] = round(m["qongiroq"] / m["kunlar_soni"], 1) if m["kunlar_soni"] else 0
        m["daqiqa"] = round(m["daqiqa"], 1)
        for k in ("mijozlar", "oquvchilar", "kunlar"):
            m.pop(k)
    qarzlar = {}
    if oquvchi:
        for r in frappe.get_all(
            "Qarz Ishi",
            filters={"student": ["in", list(oquvchi)],
                     "ishlov_status": ["not in", list(SOTUV_YOPIQ)]},
            fields=["student", "qarz_summa", "name", "masul", "ishlov_status"],
        ):
            qarzlar[r.student] = r
    for sid, o in oquvchi.items():
        o["menejerlar"] = sorted(o["menejerlar"])
        o["daqiqa"] = round(o["daqiqa"], 1)
        qi = qarzlar.get(sid)
        o["qarz"] = flt(qi.qarz_summa) if qi else 0.0
        o["qarz_ishi"] = (qi.name if qi else None) or o.get("qarz_ishi")
        o["ishlov_status"] = qi.ishlov_status if qi else ""
        o["masul"] = qi.masul if qi else ""

    menejerlar = sorted(menejer.values(), key=lambda x: (-x["qongiroq"], -x["daqiqa"]))
    oquvchilar = sorted(oquvchi.values(), key=lambda x: (-x["qongiroq"], -x["daqiqa"]))
    kunlar = sorted(kunlik)

    return {
        "from_date": from_date, "to_date": to_date,
        "faqat_ozi": bool(masul),
        "jami": {
            "qongiroq": len(qongiroqlar),
            "gaplashildi": sum(q["gaplashildi"] for q in qongiroqlar),
            "daqiqa": round(sum(flt(q.suhbat_vaqti) for q in qongiroqlar) / 60.0, 1),
            "mijozlar": len({q.normal_telefon for q in qongiroqlar
                             if q["gaplashildi"] and q.normal_telefon}),
            "oquvchilar": len({q["student"] for q in qongiroqlar if q["student"]}),
            "yozuv": sum(q["audio"] for q in qongiroqlar),
            "tahlil": sum(1 for q in qongiroqlar if q.ai_xulosa),
            "taklif": len(takliflar),
            "bogllanmagan": sum(1 for q in qongiroqlar if not q["student"]),
        },
        "menejerlar": menejerlar,
        "oquvchilar": oquvchilar,
        "kunlar": kunlar,
        "kunlik": kunlik,
        "takliflar": takliflar,
        "qongiroqlar": qongiroqlar,
    }


@frappe.whitelist()
def get_suhbat(qongiroq: str) -> dict:
    """Bitta suhbatning to'liq matni va tahlili (ro'yxatda yuborilmaydi — og'ir).

    Ruxsat Telefon Qongirogi qoidasi bo'yicha tekshiriladi: menejer o'zinikini,
    rahbariyat/sotuv bo'limi hammasini."""
    _guard()
    doc = frappe.get_doc("Telefon Qongirogi", qongiroq)
    doc.check_permission("read")
    return {
        "name": doc.name,
        "boshlandi": doc.boshlandi,
        "transkript": doc.transkript or "",
        "transkript_sozlar": doc.transkript_sozlar or 0,
        "ai_xulosa": doc.ai_xulosa or "",
        "ai_model": doc.ai_model or "",
        "taklif": _taklif(doc.ai_xulosa) or "",
    }
