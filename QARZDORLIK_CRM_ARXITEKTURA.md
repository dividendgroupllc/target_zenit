# Qarzdorlik CRM — Arxitektura

> **HOLAT (2026-10-05): MVP (1-bosqich) QURILDI va target.local'da test qilindi.**
> Doctype'lar: Tolov Rejasi (+Oyi), Qarz Ishi, Aloqa Yozuvi, Tolov Vadasi, Qarzdorlik Sozlamalari (+Biriktirish).
> Engine: `target_zenit/qarzdorlik/engine.py` (nightly + PE hook), generatsiya: `qarzdorlik/setup.py`,
> test yordamchilari: `qarzdorlik/dev.py`. UI: `/app/qarzdorlik` page + "Qarzdorlik" workspace.
> Testlar o'tdi: FIFO taqsimot/avans, ish ochilishi (threshold+grace), AY→PTP→QI kaskadi, va'da buzilishi→ToDo.
> MUHIM: kompaniya bazaviy valyutasi USD — engine to'lovlarni UZS'da hisoblaydi (base_paid_amount ishlatilmaydi, §0 ga qarang).
> Prod'ga chiqarish: foydalanuvchi o'zi push qiladi; serverda `migrate` + `setup.generate_plans` (avval dry_run) + Sozlamalarni to'ldirish.

**Sana:** 2026-10-05. **Asos:** `QARZDORLIK_CRM_TADQIQOT.md` (jahon standartlari tadqiqoti).
**Maqsad:** savdo menejerlari o'quvchilar qarzini ko'rib, bo'lib olib, qo'ng'iroq qilib, status/komment/va'da bilan ishlashi uchun to'liq tizim.

---

## 0. Bazadagi real holat (arxitektura shunga qurilgan)

target.local tekshiruvi (2026-10-05):

| Fakt | Qiymat | Xulosa |
|---|---|---|
| Student | 565 (547 faol), hammasi Customer'ga bog'langan | o'quvchi↔mijoz bog'i tayyor |
| Shartnomali (custom_shartnoma_qilindi=1) | 271 | qarz faqat shartnomalilar bo'yicha |
| `Fees` / `Sales Invoice` (docstatus=1) | **0 / 1** | **hisob-kitob (accrual) hujjati YO'Q** |
| Payment Entry (Receive) | 438 (405 UZS, 33 USD) | to'lovlar faqat PE, GL'da avans sifatida |
| Student custom maydonlar | tariff, final_amount, discount, **monthly_payment**, payer_name/phone, contract_no/date | shartnoma ma'lumoti Student'ning o'zida |

**Prod'dan tasdiqlangan parametrlar (2026-10-05, foydalanuvchi + skrinshot EDU-STU-2026-00019):**
- To'lov davri: **1-sentabrdan 10 oy** (sentabr–iyun), oylik to'lov `custom_monthly_payment`da.
- Summalar mantig'i: `yakuniy (final) = oylik × 10`; `chegirma = tarif − yakuniy` (misol: 79M − 29M = 50M = 5M×10).
- **Hamma shartnoma UZS** — valyuta masalasi yo'q (USD faqat eski to'lovlar tarixida).
- Tarif/shartnoma summalari prod'da to'ldirilgan; **istisno: investor farzandlari va grant o'quvchilarda summa yozilmagan** — ular qarz nazoratiga kirmaydi (§6 №17).
- Shartnoma turi: "Oylik" (asosiy); boshqa tur uchrasa (masalan yillik oldindan) — TR bitta qator, muddat 1-sentabr.

**Markaziy qaror №1 — qarz manbai jadval (schedule-based), GL emas.**
GL'dagi Receivable faqat avanslarni ko'rsatadi (invoice yo'q), demak "qarz"ni GL'dan olish mumkin emas. Jahon standarti ham shu: FACTS/Blackbaud tuition tizimlari **to'lov rejasi (payment plan) vs tushgan to'lovlar** farqidan hisoblaydi, buxgalteriyadan emas. Bonus: jonli buxgalteriyaga hech narsa yozmaymiz (xavfsiz), USD yaxlitlash driftiga yangi nuqta qo'shilmaydi.

Qarz formulasi: `qarz(bugun) = Σ(muddat kelgan reja qatorlari) − Σ(taqsimlangan to'lovlar)`.

---

## 1. Umumiy sxema

```
Student (shartnoma maydonlari, mavjud)
   └─ To'lov Rejasi (TR)  ── oylik qatorlar (muddat, summa)      [hisob qatlami]
          │  nightly recompute + PE submit hook
          ▼
   Qarz Ishi (QI) ── bitta ochiq ish / o'quvchi                  [workflow qatlami]
          ├─ Aloqa Yozuvi (AY)  — har qo'ng'iroq/xabar
          ├─ To'lov Va'dasi (PTP) — strukturali va'da
          └─ status, mas'ul, keyingi aloqa sanasi
          ▼
   /app/qarzdorlik  — menejer ish stoli + rahbar paneli          [UI qatlami]
```

Ikki qatlam statusi (tadqiqot 6-bo'lim):
- **Hisob holati** — tizim hisoblaydi, menejer tegmaydi: `Joriy` / `Avansda` / `Qarzdor 1–30` / `31–60` / `61–90` / `90+` / `Ketgan-qarzli`.
- **Ishlov holati** — menejer qo'yadi (workflow): quyida §3.

---

## 2. Doctype'lar

### 2.1 `Tolov Rejasi` (TR-{YYYY}-{#####})
O'quvchi + o'quv yili uchun bitta hujjat. Submittable emas (amendable oddiy doc, track_changes=1).

Maydonlar: student (Link, req), academic_year, currency (UZS/USD), contract_amount, discount_amount, final_amount, holat (Faol/Yakunlangan/Bekor), `oylar` child table:

`Tolov Rejasi Oyi` (child): oy_label (2026-09), due_date, amount, prorated (check), izoh; **hisoblanadigan** (DB'da saqlanadi, nightly yangilanadi): paid_amount, outstanding, holat (Kutilmoqda/Muddati keldi/Qisman/To'landi/Bekor).

Generatsiya (tasdiqlangan qoida): **10 qator, due_date = 1-sentabr … 1-iyun (har oyning 1-i), amount = `custom_monthly_payment`**. Konsistensiya tekshiruvi: `final_amount != monthly × 10` bo'lsa — "Ma'lumot nomuvofiq" hisobotiga (jim o'tkazilmaydi). O'quv yili o'rtasida kelganga — joining_date'dan boshlab qolgan oylar (birinchi oy prorate — ochiq savol №1). Tugma yoki mass-skript bilan yaratiladi, so'ng qo'lda tahrir mumkin; chegirma o'zgarsa — **kelgusi oylardan** qayta hisob (o'tgan oylar tarixi buzilmaydi). `custom_tariff` = Grand/Investor yoki `final_amount`=0 bo'lgan o'quvchilarga TR yaratilmaydi.

**To'lov taqsimoti (allocation):** PE'lar o'quvchining Customer'i bo'yicha olinadi va **FIFO** (eng eski to'lanmagan oyga) taqsimlanadi. Taqsimot alohida jadvalda saqlanmaydi — har recompute'da deterministik qayta hisoblanadi (soddalik; kelishmovchilik bo'lmaydi).

### 2.2 `Qarz Ishi` (QI-{YYYY}-{#####}) — markaziy workflow obyekti
O'quvchi bo'yicha **bir vaqtda faqat bitta ochiq ish** (unique check: student + holat != Yopildi).

Maydonlar:
- student, tolov_rejasi, customer (fetch), sinf (fetch), payer_name/phone (ochilgan paytdagi snapshot + yangilash tugmasi)
- **qarz_summa, eng_eski_muddat, aging_bucket** — auto (nightly + PE hook)
- **masul** (Link User, req), biriktirilgan_sana
- **ishlov_status** (Select — kanban uchun ataylab Select, admissions saboqlari: kanban faqat Select oladi)
- **keyingi_aloqa** (Date, ochiq statuslarda **majburiy** — validate'da tekshiriladi)
- urinishlar_soni (auto: AY'lardan), oxirgi_aloqa (auto), buzilgan_vadalar (auto)
- aloqa_cheklovi (Select: Yo'q / Faqat SMS / Qo'ng'iroq mumkin emas), nizo_sababi (Text, Nizo statusida req)
- yopilish_sababi (Select: To'landi / Chegirma berildi / Ketdi / Boshqa), yopilgan_sana

Ochish/yopish — **faqat avtomatika**: qarz ≥ sozlamadagi threshold va grace o'tgan → ochiladi (mas'ul avto-biriktiriladi); qarz ≤ tolerance → "Yopildi–To'landi" (tarix saqlanadi, keyingi qarzda YANGI ish ochiladi — tarix aralashmaydi). Menejer faqat ishlov statusini yuritadi.

### 2.3 `Aloqa Yozuvi` (AY-{YYYY}-{######})
Har bir aloqa — alohida hujjat (child emas: ro'yxat/hisobot/permission qulay). Maydonlar:
- qarz_ishi (Link, req), student (fetch), masul (default: session user), vaqt (default: now)
- kanal (Qo'ng'iroq / SMS / Telegram / Yuzma-yuz / Boshqa)
- **aloqa_natijasi** (Gaplashildi / Javob yo'q / O'chirilgan / Noto'g'ri raqam / Qayta qo'ng'iroq so'radi / Band)
- **hisob_natijasi** (faqat Gaplashildi bo'lsa, req): Va'da berdi / Bo'lib to'lashga kelishildi / E'tiroz-nizo / "To'laganman" deydi / Rad etdi / Ma'lumot oldi
- komment (Text), **keyingi_harakat** (Select: Qayta qo'ng'iroq / Va'dani kutish / Eskalatsiya / Raqam aniqlash / Yopish so'rovi) + **keyingi_sana** (req — "keyinroq" taqiqlanadi, tadqiqot §5.4)
- Va'da maydonlari (hisob_natijasi=Va'da bo'lsa req): vada_summa, vada_sana → **after_insert'da avtomatik `Tolov Vadasi` yaratiladi**

after_insert: Qarz Ishi'ga keyingi_aloqa/oxirgi_aloqa/urinishlar ko'chiriladi, ishlov_status tegishlicha o'tadi. Edit cheklangan (faqat o'z yozuvini 1 soat ichida — audit).

### 2.4 `Tolov Vadasi` (PTP-{YYYY}-{#####})
qarz_ishi, student, masul, vada_sana, vada_summa, holat (**Ochiq / Bajarildi / Qisman / Buzildi / Bekor**), amal_summa (fakt), tekshirilgan_sana.

Nightly job: vada_sana (+1 ish kuni bufer) o'tgan Ochiq PTP'lar bo'yicha: shu kundan keyin PE tushganmi? To'liq → Bajarildi; qisman → Qisman (qoldiqqa yangi ishlov); yo'q → **Buzildi** → Qarz Ishi statusi "Va'da buzildi", keyingi_aloqa=bugun, menejerga bildirishnoma. 2 ta buzilgan PTP → avto-"Eskalatsiya" (sozlanadi).

### 2.5 `Qarzdorlik Sozlamalari` (Single)
- grace_days (muddatdan keyin necha kun kutish, default 3), tolerance (UZS, default 1000 — USD yaxlitlash drifti ±60 so'm muammosini yopadi), min_threshold (shundan kichik qarzga ish ochilmaydi)
- biriktirish child jadvali: sinf_pattern → masul (masalan `G1*,G2*` → user X); fallback: round-robin ("Sotuv meneger" roli bo'yicha)
- eskalatsiya_kun (default 30: shu kundan rahbarga ko'rinadi), buzilgan_vada_limit (2)
- avto_eslatma (2-bosqich): enabled, shablonlar (muddatdan 3 kun oldin / +1 / +7), jo'natish oynasi (09:00–20:00), SMS provayder

### 2.6 `Qarzdorlik Snapshot` (ixtiyoriy, 3-bosqich)
Oylik/haftalik agregat (jami qarz, bucket kesimi, collection rate) — trend grafiklari uchun, chunki jadval-asosli qarzni o'tmishga qarab qayta qurib bo'lmaydi.

---

## 3. Ishlov statusi — workflow

```
Yangi ──► Urinilmoqda ──► Gaplashildi–Va'da ──► (PTP bajarildi) ──► Yopildi–To'landi
  │            │                 │
  │            │                 └─► Va'da buzildi ──► (yana aloqa) ─► Urinilmoqda/Va'da
  │            ├─► Aloqa yo'q (N urinish, raqam topilmadi)
  │            └─► Gaplashildi–Nizo ──► Eskalatsiya ──► Hal qilindi / Yopildi–Boshqa
  │                      │
  └──────────────────────┴─► Bo'lib to'lash (kelishuv jadvali = TR qayta tahrirlanadi)
```

Statuslar (Select, kanban-ustunlar): `Yangi` · `Urinilmoqda` · `Gaplashildi – Va'da` · `Gaplashildi – Nizo` · `Bo'lib to'lash` · `Va'da buzildi` · `Aloqa yo'q` · `To'lov tekshirilmoqda` · `Eskalatsiya` · `Yopildi – To'landi` · `Yopildi – Boshqa`.

Qoidalar (validate):
- Ochiq statusda `keyingi_aloqa` bo'sh bo'lishi mumkin emas.
- `Gaplashildi – Va'da`ga faqat ochiq PTP bilan o'tiladi (AY orqali avto).
- `Nizo`da avto-eslatmalar **to'xtatiladi** (suppression — collections standarti) va nizo_sababi majburiy.
- `Yopildi–To'landi`ni faqat tizim qo'yadi (qarz ≤ tolerance); menejer "To'lov tekshirilmoqda"gacha olib keladi xolos.
- `Eskalatsiya`da rahbar (Sales Manager roli) bildirishnoma oladi; yopishni faqat rahbar qiladi.

---

## 4. UI

### 4.1 `/app/qarzdorlik` — menejer ish stoli (sotuv_dashboard uslubida desk Page)
- **Tepa panel:** qizil badge — «Qarzdorlar: N ta · jami X so'm» (MDH standarti), mening ishlarim / bugungilar / muddati o'tganlar schyotchiklari.
- **Chap — navbat ro'yxati:** default filtr `masul = men AND keyingi_aloqa <= bugun`, o'tib ketganlar qizil, tartib: keyingi_aloqa ↑. Filtrlar: bucket, status, sinf, menejer (rahbarga). Qator: o'quvchi, sinf, to'lovchi+tel (bosilsa `tel:` link), qarz, bucket, status, keyingi sana.
- **O'ng — ish kartasi** (qator bosilganda):
  - qarz detali: TR oylari jadvali (oy / summa / to'langan / qoldiq / holat)
  - to'lov tarixi (PE'lar), ota-ona/guardian telefonlari (sotuv_dashboard'dagi `_guardians_map` qayta ishlatiladi)
  - timeline: AY + PTP + status o'zgarishlari xronologik
  - **«Qo'ng'iroq natijasi» modali** — bitta forma: kanal→natija→(hisob natijasi)→komment→keyingi harakat+sana→(va'da summa/sana). Saqlash = AY + PTP + QI yangilash bitta tranzaksiyada. Menejerning 90% ishi shu modal.
- **Mass-amallar** (rahbar): mas'ulni almashtirish, SMS shablon yuborish (2-bosqich).

### 4.2 Rahbar paneli (shu page ichida tab)
- Aging jadvali (bucket × sinf), jami qarz dinamikasi (snapshot'dan)
- Menejer KPI: ochiq ishlar, bugungi qilingan/qolgan qo'ng'iroqlar, ulanish %, **PTP kept rate**, davrda yopilgan qarz summasi, o'rtacha birinchi aloqa vaqti
- Eskalatsiya ro'yxati, 2+ buzilgan va'dalar, 14+ kun harakatsiz ishlar ("stale" alert)

### 4.3 Qarz Ishi list view + kanban
Standart Frappe list (status rang indikatorlari) va kanban (ishlov_status Select bo'yicha) — page'ni yoqtirmaganlar uchun bepul alternativa.

---

## 5. Avtomatika

### 5.1 Hooks
```python
scheduler_events["daily"] += ["target_zenit.qarzdorlik.engine.nightly"]
doc_events["Payment Entry"] = {"on_submit": "...engine.on_payment", "on_cancel": "...engine.on_payment"}
doc_events["Student"] = {"on_update": "...engine.on_student_change"}  # ketdi/chegirma
```

### 5.2 `nightly()` tartibi (idempotent, har qadam alohida try/except + log)
1. Faol TR'lar bo'yicha recompute: PE FIFO taqsimot → oy qatorlari paid/outstanding/holat.
2. QI ochish (threshold+grace) / yopish (≤ tolerance) / qarz_summa+bucket yangilash.
3. PTP tekshiruvi (§2.4), buzilganlarga status+bildirishnoma.
4. SLA: yangi QI 48 soatda birinchi AY'siz qolsa → menejer+rahbarga ToDo.
5. Avto-biriktirish (yangi ishlar), ishdan ketgan (disabled user) mas'ullarning ochiq ishlarini qayta taqsimlash.
6. (2-bosqich) avto-eslatmalar navbati.

### 5.3 `on_payment(pe)` — real vaqt
PE submit bo'lishi bilan shu Customer'ning TR+QI qayta hisoblanadi: ota-ona to'lagan zahoti menejer ro'yxatidan tushadi (ertalabgacha kutmaydi). Cancel ham teskarisiga.

---

## 6. Edge-case katalogi va yechimlar

| № | Holat | Yechim |
|---|---|---|
| 1 | **Aka-uka: bitta to'lovchi, bir necha farzand** | Ish — o'quvchi kesimida (hisob aniq), lekin UI payer_phone bo'yicha guruhlaydi: kartada «Shu to'lovchining boshqa farzandlari: …» bloki, bitta qo'ng'iroqda hammasi; AY'ni bir farzandga yozganda «aka-ukalarga ham nusxa» checkbox. To'lov noto'g'ri farzand Customer'iga tushsa — kassir PE'ni to'g'rilaydi (CRM taxmin qilmaydi). |
| 2 | **Avans (oldindan to'lov)** | outstanding < 0 → hisob holati `Avansda`, qarzdor ro'yxatiga tushmaydi, FIFO kelgusi oyga o'zi yopiladi. |
| 3 | **O'rtada kelgan o'quvchi** | TR generatsiyasida joining_date dan prorate (kun/30 yoki sozlamadagi qoida). |
| 4 | **Ketgan o'quvchi (date_of_leaving)** | Kelgusi oylar `Bekor`; qoldiq qarz bo'lsa hisob holati `Ketgan-qarzli` (alohida bucket, alohida siyosat — avto-eslatma yo'q, faqat qo'lda). Eduvisit sync'da o'chsa ham shu yo'l. |
| 5 | **Chegirma/tarif o'zgardi** | TR'da «qayta hisoblash (sanadan)» tugmasi: faqat kelgusi oylar o'zgaradi, track_changes'da kim-qachon ko'rinadi. |
| 6 | **Valyuta** | Hamma shartnoma UZS (tasdiqlangan) — TR faqat UZS. Eski USD to'lovlar (33 PE) taqsimotda PE'ning base (UZS) summasi bilan olinadi; `tolerance` (1000 so'm) mayda yaxlitlash farqlarini yopadi. |
| 7 | **Qisman to'langan oy** | Oy holati `Qisman`, bucket **eng eski to'lanmagan due_date** bo'yicha (collections standarti). |
| 8 | **«Kecha to'laganman» deydi** | Status `To'lov tekshirilmoqda` + kassirga ToDo; PE (backdated ham) tushishi bilan on_payment avto-yopadi; 3 kunda tasdiqlanmasa qaytadi. |
| 9 | **Nizo (chegirma va'da qilingan edi…)** | Status `Nizo`: avto-eslatma suppression, sabab majburiy, rahbarga eskalatsiya; hal → TR tuzatiladi yoki ishlov davom etadi. |
| 10 | **«Menga qo'ng'iroq qilmang»** | QI.aloqa_cheklovi; modal ochilganda ogohlantiradi; avto-SMS oynasi 09:00–20:00, bayramlarda jim. |
| 11 | **Noto'g'ri raqam / N urinishda aloqa yo'q** | 5 urinishdan keyin avto-taklif: `Aloqa yo'q` + «raqam aniqlash» vazifasi; kartada guardian'larning barcha raqamlari zaxira sifatida. |
| 12 | **Ikki menejer bitta ota-onaga qo'ng'iroq qilishi** | Bitta ochiq QI + bitta mas'ul; boshqalarga read-only; aka-uka kartasi (№1) boshqa mas'ulning farzandini ham ko'rsatadi — «mas'ul: X» yorlig'i bilan. |
| 13 | **Menejer ishdan ketdi / ta'tilda** | nightly §5.2.5 avto-qayta taqsimlaydi; rahbarda mass-reassign. |
| 14 | **PTP sanasi dam olish kuniga tushdi** | Buzilish tekshiruvi +1 ish kuni bufer bilan. |
| 15 | **Ketma-ket buzilgan va'dalar** | buzilgan_vadalar ≥ limit (2) → avto-`Eskalatsiya`. |
| 16 | **Yillik rollover** | Yangi o'quv yiliga yangi TR; eski yil qoldig'i yangi TR'ga «O'tgan yil qarzi» qatori (due_date = 1-sentabr) bo'lib ko'chadi; eski QI yopilmay davom etadi (tarix bir joyda). |
| 17 | **Investor farzandi / grant o'quvchi** (summa ataylab yozilmagan — tasdiqlangan) | TR yaratilmaydi, hisob holati `Grant/Investor` — qarzdor ro'yxatiga hech qachon tushmaydi. Lekin `shartnoma_qilindi=1` va tarif=Kontrak bo'lib summa 0 bo'lsa — bu xato: «Ma'lumot yetishmaydi» hisobotiga chiqadi, jim o'tkazilmaydi. |
| 18 | **PE Customer'i Student'ga bog'lanmagan** (eski/qo'lda ochilgan mijozlar) | nightly «taqsimlanmagan to'lovlar» hisoboti — kassir bog'laydi. |
| 19 | **Rollar/maxfiylik** | `Sotuv meneger`: QI/AY/PTP CRUD (o'z ishlari write, boshqalari read), TR read-only, PE/GL'ga kirmaydi. Hamma doctype'larda track_changes=1. Telefonlar export — faqat rahbar. |
| 20 | **Kanban** | ishlov_status ataylab Select (Link emas) — Frappe kanban cheklovi (admissions'da bosib o'tilgan saboq). |

---

## 7. KPI va hisobotlar

- **Collection rate** = davr to'lovi / davr hisoblanmasi (TR'dan) — oy kesimida
- **Aging** snapshot + trend; **PTP kept rate** (menejer kesimida); **birinchi aloqa vaqti** (QI ochilishi → birinchi AY)
- Script report «Qarzdorlik reestri» (buxgalter uchun, Excel export): o'quvchi × oylar matritsasi

## 8. Bosqichlar

1. **MVP (yadro):** TR + QI + AY + PTP doctype'lari, engine (nightly + PE hook), avto-biriktirish, `/app/qarzdorlik` menejer ish stoli, workspace. *Shu bosqich bilan butun qo'lda jarayon ishlaydi.*
2. **Avtomatika:** avto-eslatmalar (SMS — Eskiz / Telegram), SLA bildirishnomalari, rahbar KPI paneli, snapshot+trend.
3. **Kengaytma:** payer-konsolidatsiya UI chuqurlashtirish, ota-ona portali/bot («qarzingiz: X, to'lash: link»), Payme/Click to'lov linki.

## 9. Savollar holati

**Javob olindi (2026-10-05):**
- ✅ Davriylik: 1-sentabrdan 10 oy, oylik to'lov `custom_monthly_payment`.
- ✅ Valyuta: hamma student UZS.
- ✅ Prod'da tarif/shartnoma summalari kiritilgan; investor farzandlari va grantlarda yozilmagan (ular nazoratdan tashqari).
- ✅ Sinf→menejer taqsimoti hozircha muhim emas — MVP'da qo'lda biriktirish (default round-robin), sozlama jadvali keyinroq to'ldiriladi.

**Keyinga qolgan (bloklamaydi, defaultlar bilan boshlanadi):**
1. O'rtada kelganning birinchi oyi prorate qilinadimi yoki to'liq oy olinadimi? (default: joining_date oyidan boshlab to'liq oylar)
2. Grace/tolerance/threshold qiymatlari (default: 3 kun / 1000 so'm / 10 000 so'm) — Sozlamalardan istalganda o'zgaradi.
3. SMS provayder (Eskiz?) va avto-eslatma matnlari — 2-bosqichda.
