# Sotuv bo'limi nazorati (kontrol-list) — tadqiqot va arxitektura

**Sana:** 2026-10-08. **Maqsad:** investor dashboardiga savdo bo'limi nazorati paneli — qaysi menejer nechta ota-ona bilan gaplashgan, qo'ng'iroqlar soni, natijalari, vaqti va izohlari.

---

## 1. Hozirgi ma'lumot bazasi (audit)

Qarzdorlik CRM moduli allaqachon kerakli ma'lumotni yig'adi — yangi jarayon o'ylab topish shart emas:

| Manba | Nima bor | Holat (lokal) |
|---|---|---|
| **Aloqa Yozuvi** | `masul`, `vaqt`, `kanal`, `aloqa_natijasi`, `hisob_natijasi`, `komment`, `keyingi_harakat`, `keyingi_sana`, `vada_summa/sana`, `qarz_ishi` → o'quvchi; plus Frappe standart `owner`/`creation`/`modified` | **2 ta test yozuvi** (menejerlar hali boshlamagan) |
| **Qarz Ishi** | `masul`, `ishlov_status`, `urinishlar_soni`, `oxirgi_aloqa`, `keyingi_aloqa`, `buzilgan_vadalar`, `qarz_summa` | **228 ochiq ish** (226 "Yangi" — hali hech kim tegmagan) |
| **Tolov Vadasi (PTP)** | `vada_sana/summa`, `holat` (Ochiq/Bajarildi/Qisman/Buzildi), `masul` | 2 ta |
| **Payment Entry** | to'lovlar — natijani o'lchash uchun | 856 ta |
| Menejerlar | "Sotuv meneger" roli | 3 ta foydalanuvchi |

**Muhim xulosa:** panel bo'sh ma'lumot bilan ham to'g'ri ishlashi (va "hali ish boshlanmagan" holatini aniq ko'rsatishi) kerak — hozir aynan shunday.

**Ma'lumot sifati uchun ikki muhim detal:**
- `vaqt` — menejer qo'lda o'zgartira oladigan maydon; `creation` — tizim yozadi. Nazoratda **ikkalasi** kerak (quyida §4 anti-gaming).
- `owner` ≠ `masul` bo'lishi mumkin (rahbar boshqa menejer nomidan yozsa) — nazorat **owner** bo'yicha ham tekshirishi kerak.

## 2. Jahon amaliyoti — nimani o'lchashadi

Collections/call-center bo'yicha standart ko'rsatkichlar ikki guruhga bo'linadi va **ikkalasi birga** ko'rsatiladi (faqat biri — xato):

### 2.1 Faollik (activity) — "qancha ishladi"
- **Dials/calls per day** — kunlik qo'ng'iroqlar soni
- **Unique contacts** — nechta har xil ota-ona bilan ishlangani (bitta odamga 10 marta qo'ng'iroq ≠ 10 ta ish)
- **Coverage** — biriktirilgan ishlarning necha foiziga tegilgan

### 2.2 Natija (outcome) — "nima foyda berdi"
- **RPC / Right Party Contact rate** — ulanish foizi (gaplashildi ÷ urinishlar)
- **PTP conversion** — gaplashuvlarning necha foizi va'daga aylandi (yaxshi jamoada **50%+**)
- **PTP kept rate** — va'dalarning necha foizi bajarilgan (menejer sifatining eng ishonchli o'lchovi)
- **Collected per agent** — menejer bo'yicha yig'ilgan summa
- **Call-to-payment conversion** — qo'ng'iroqlarning necha foizi to'lovga olib keldi

### 2.3 Sifat (quality)
- **QA adherence** — yozuv to'liqligi (izoh bormi, keyingi sana qo'yilganmi). Sanoatda 80–95% talab qilinadi.
- **SLA** — yangi ish ochilgach birinchi aloqagacha vaqt

**Dizayn qoidalari (dashboard amaliyoti):**
- **Leaderboard + drill-down:** rahbar jamoa kesimini ko'radi, ustiga bosib **aynan qaysi qo'ng'iroq, qachon, nima izoh** — har bir raqam tekshirilishi mumkin bo'lsin.
- Faollik va natija yonma-yon: "100 qo'ng'iroq, 0 va'da" darhol ko'rinsin.
- Davr tanlovi (bugun / hafta / oy / ixtiyoriy) va menejer filtri.

## 3. Panel arxitekturasi

**Joylashuvi:** investor dashboardda yangi tab — **"Sotuv nazorati"** (hozirgi 9 tabdan keyin 10-chi).
Manba: `Aloqa Yozuvi` + `Qarz Ishi` + `Tolov Vadasi` + `Payment Entry` — **yangi doctype kerak emas**, hammasi jonli hisoblanadi.

### 3.1 Tepa qatori — davr bo'yicha jami (4 karta)
| Karta | Hisoblanishi |
|---|---|
| Qo'ng'iroqlar | `COUNT(Aloqa Yozuvi)` davrda |
| Gaplashilgan ota-onalar | `COUNT(DISTINCT qarz_ishi)` — `aloqa_natijasi='Gaplashildi'` |
| Olingan va'dalar | `COUNT(Tolov Vadasi)` + summasi |
| Yig'ilgan to'lov | davrda tushgan PE (shu menejerning ishlari bo'yicha) |

### 3.2 Asosiy jadval — menejerlar kesimi (leaderboard)

| Ustun | Ma'nosi |
|---|---|
| Menejer | ism + ochiq ishlari soni |
| Qo'ng'iroqlar | jami urinishlar |
| Ulandi | gaplashilgan (va **ulanish %**) |
| Ota-onalar | noyob o'quvchi/ish soni |
| Va'dalar | olingan PTP soni + summasi |
| **Va'da bajarildi %** | PTP kept rate |
| Yig'ildi | shu menejer ishlari bo'yicha davrda tushgan to'lov |
| Qamrov | biriktirilganlarning necha %iga tegilgan |
| Kechikkan | `keyingi_aloqa < bugun` bo'lgan ishlari (qizil) |
| **Sifat** | izohli va keyingi sanasi to'g'ri yozuvlar % |

Sarlavhani bosib tartiblash; menejerni bosib — pastda uning qo'ng'iroqlar lentasi.

### 3.3 Drill-down — qo'ng'iroqlar lentasi (kontrol-list o'zi)
Har qator = bitta aloqa:

`sana-vaqt | menejer | o'quvchi (sinf) | to'lovchi/telefon | kanal | aloqa natijasi | suhbat natijasi | va'da (summa/sana) | keyingi qadam + sana | izoh`

- Filtrlar: davr, menejer, natija, kanal, "faqat izohsizlar", "faqat va'dalar"
- Izoh to'liq ko'rinadi (kesilmaydi) — rahbar aynan nima deyilganini o'qiydi
- Qator bosilsa — Qarz Ishi kartasi ochiladi
- **Excel/CSV eksport**

### 3.4 Kunlik dinamika
Oddiy ustunli grafik: kun × qo'ng'iroqlar (menejerlar rangi bilan) — kim qaysi kuni ishlagani ko'rinadi. Bo'sh kunlar darhol ko'zga tashlanadi.

## 4. Anti-gaming (ishonchlilik) — muhim qism

Qo'ng'iroqlar qo'lda kiritilgani uchun raqamlar "chizilishi" mumkin. Himoyalar:

| Xavf | Himoya |
|---|---|
| Sanani orqaga surib yozish | Panel **`creation`** (tizim vaqti) bo'yicha hisoblaydi; `vaqt` bilan farq 2 soatdan oshsa — qator **"⏱ keyin kiritilgan"** belgisi bilan |
| Bo'sh/soxta izohlar | "Sifat" ustuni: izoh < 10 belgi bo'lsa sifatsiz hisoblanadi; "faqat izohsizlar" filtri |
| Bitta odamga ko'p qo'ng'iroq qilib son oshirish | **Noyob ota-onalar** ustuni faollik yonida turadi |
| Kunning oxirida hammasini birvarakay kiritish | Kunlik dinamikada **kiritilish soati** taqsimoti (masalan 18:00 da 40 ta yozuv — ogohlantirish) |
| Boshqa nomdan yozish | `owner ≠ masul` bo'lsa qatorda ko'rsatiladi |
| Yozuvni keyin tahrirlash | Hamma doctype'da `track_changes=1` — "tahrirlangan" belgisi + versiyaga havola |

## 5. Ruxsatlar

| Rol | Ko'radi |
|---|---|
| investor, System Manager, Sales Manager | **hamma menejerni** (to'liq nazorat) |
| Sotuv meneger | faqat **o'zini** (o'z statistikasi — motivatsiya uchun) |
| Xojakbar_Operator | hamma (operator nazorati) |

## 6. Edge-case'lar

1. **Ma'lumot yo'q (hozirgi holat)** — "Bu davrda aloqa yozuvi yo'q" + ochiq ishlar soni ko'rsatiladi, 0 ga bo'lish yo'q
2. **Menejer ishdan ketgan** — statistikasi tarixda qoladi, ro'yxatda "nofaol" belgisi bilan
3. **Ish boshqa menejerga o'tkazilgan** — qo'ng'iroq uni **qilgan** menejerga sanaladi (tarix), joriy ish esa yangi mas'ulga
4. **To'lov atributsiyasi** — to'lov qaysi menejerga yoziladi? Qoida: to'lov sanasida ishning mas'uli kim bo'lsa o'shanga (soddalik + tekshirilishi oson)
5. **Aka-uka (bitta qo'ng'iroq, 2 farzand)** — noyob ota-ona `payer_phone` bo'yicha sanaladi, ish soni emas
6. **Davr chegarasidagi va'da** — PTP kept rate va'da **sanasi** davrga tushganlar bo'yicha (yaratilgan sanasi emas)
7. **Bir kunda bir ishga bir necha qo'ng'iroq** — hammasi lentada, lekin "noyob" da bir marta
8. **Vaqt mintaqasi** — hamma hisob server vaqtida (Asia/Tashkent), kun 00:00–23:59

## 7. Bosqichlar

**1-bosqich:** "Sotuv nazorati" tabi — 4 karta, menejerlar jadvali, qo'ng'iroqlar lentasi (filtr + izohlar), davr tanlovi, CSV eksport.
**2-bosqich:** kunlik dinamika grafigi, anti-gaming belgilari (kech kiritilgan / tahrirlangan / izohsiz), sifat ustuni.
**3-bosqich:** menejer maqsadlari (kunlik norma: masalan 30 qo'ng'iroq) va bajarilish foizi; haftalik avto-hisobot (email/Telegram rahbarga).

## 8. Ochiq savollar

1. Menejer uchun **kunlik norma** bormi (masalan 30 qo'ng'iroq / 15 ulanish)? Bo'lsa — maqsadga nisbatan bajarilish ko'rsatiladi.
2. To'lov atributsiyasi: joriy mas'ulga (§6.4) ma'qulmi yoki "oxirgi gaplashgan menejer"ga?
3. Panel investor dashboardida tab bo'lsinmi yoki alohida sahifa (`/app/sotuv-nazorati`) ham kerakmi?
4. Qo'ng'iroq **davomiyligi** kerakmi? Hozir yozilmaydi — kerak bo'lsa Aloqa Yozuviga maydon qo'shiladi (yoki keyinchalik telefoniya integratsiyasi).

## Manbalar
- [Sedric: Call center KPIs for debt collection](https://www.sedric.ai/arm-resources/call-center-kpis-for-debt-collection) · [Tratta: Debt collection dashboard metrics](https://www.tratta.io/blog/debt-collection-dashboard) · [VCC Live: 11 critical debt collection KPIs](https://vcc.live/blog/critical-debt-collection-kpis/) · [Observe.ai: top 4 collections KPIs](https://www.observe.ai/blog/crushing-the-top-4-debt-collections-agencies-kpis)
- [Bold BI: Sales activity tracker dashboard](https://www.boldbi.com/dashboard-examples/sales/activity-tracker/) · [HubSpot: sales performance dashboards](https://blog.hubspot.com/sales/sales-dashboard) · [ClickToClose: real-time leaderboards](https://www.clicktoclose.ai/blog/best-real-time-sales-leaderboard-software-2026-tools-tested)
