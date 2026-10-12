# O'qituvchi ish stoli ("Mening kunim") — dunyo tadqiqoti va arxitektura yo'nalishi

**Sana:** 2026-10-12
**Savol:** o'qituvchi uchun bir kunlik ish joyini (qaydnoma/kokpit) dunyodagi eng yaxshi namunalar
darajasida qanday tashkil qilish kerak — darsga kerak bo'lgan hamma narsa jadvalning o'zida,
yo'qlama/baho bir tegishda, guruhdan guruhga o'tish oson, o'quvchining o'zlashtirishi ko'rinib tursin.

Bog'liq hujjatlar: `DARS_JADVALI_DUNYO_STANDARTLARI.md` (jadval tuzish — zavuch tomoni),
`OQUV_REJA_ARXITEKTURA.md` (KTP + bajarilish), `DARS_JADVALI_ARXITEKTURA.md` (model).
Bu hujjat **faqat o'qituvchi tomoni** haqida.

---

## 0. Eng muhim 10 xulosa (agar boshqa hech narsa o'qilmasa)

1. **Dars = hub.** Dunyoning hamma yaxshi tizimida o'qituvchi "modul"larga emas, **bitta darsga**
   kiradi; davomat, baho, mavzu, uy vazifa, material, xulq, eslatma — hammasi shu darsга osilgan.
   (Arbor "Lesson Dashboard", ERPNext "Course Schedule", EduPage "lesson page".)
2. **Uch ekran qoidasi:** Kun lentasi → Dars kokpiti → O'quvchi kartasi. Undan chuqurroq ketish
   = o'qituvchini yo'qotish. Hamma narsa shu uch ekranda tugashi kerak.
3. **Yo'qlama 2 klik, 20 soniya.** Default = hamma keldi; faqat istisno belgilanadi
   (Class Charts: "behaviour in 2 clicks"; bizда allaqachon shu model).
4. **"Men nimani qilmadim" vidjeti** — Kundalik/eMaktab'ning eng kuchli g'oyasi: o'qituvchi
   kirishi bilan **qaysi darsга mavzu/uy vazifa/baho qo'yilmagani** ro'yxat bo'lib turadi.
   Bu tizimni "majburiyat"dan "yordamchi"ga aylantiradi.
5. **Kontekst ma'lumot darsning ichida bo'lishi shart** — sog'liq/allergiya, maxsus ehtiyoj,
   kechikish tarixi, ota-ona telefoni. Arbor buni "contextual details" qilib darsning o'zida beradi;
   o'qituvchi profilni qidirib ketmaydi.
6. **O'zlashtirish ko'rsatkichi = 3 belgi**: joriy daraja (ball/RAG rang), **trend** (↗︎→↘︎),
   va **xavf bayrog'i** (davomat/qarz/3 ta past baho ketma-ket). Grafiklar emas — belgi.
7. **Guruhdan guruhga o'tish — "‹ Oldingi dars / Keyingi dars ›"** tugmasi dars kokpitining ichida
   (Arbor'да aynan shunday). Jadvalga qaytib, bosib, kutish — eng ko'p vaqt yeydigan antipattern.
8. **O'qituvchi hech narsa yozmasligi kerak** — mavzu o'quv rejadan tanlanadi, uy vazifa oldingisidan
   nusxalanadi/shablondan olinadi, baho keypad'dan. Yozish = ixtiyoriy izoh.
9. **Mobil — birinchi navbatda telefon.** Bromcom/EduPage/Kundalik o'qituvchi ilovasi offlayn ishlaydi
   (EduPage hatto WearOS soatida yo'qlama). Bizда sinfda Wi-Fi ishonchsiz bo'lsa — offlayn navbat shart.
10. **Tezlik — funksiyadan muhimroq.** Dars 45 daqiqa; tizim 3 soniyadan ko'p kutsa, o'qituvchi
    qog'ozga qaytadi. Har bir amal **optimistik** (avval ekranda, keyin serverda) bo'lishi kerak.

---

## 1. Dunyo tizimlari — o'qituvchi tomoni profili

| Tizim | O'qituvchi uchun markaziy ekran | Nimasi o'rganishga arziydi |
|---|---|---|
| **Arbor** (UK) | *My Homepage* (kalendar, To-do, ogohlantirishlar, KPI) → *Lesson Dashboard* | Dars ekranining to'liqligi: registr, xulq, topshiriq, demografik/tibbiy flaglar, SEN/safeguarding eslatmalari, bulk amallar, dars rejasini drag&drop yuklash, **‹ oldingi/keyingi dars ›** navigatsiyasi |
| **Arbor My Classroom** | O'tirish sxemasi ustida yo'qlama+xulq | **Seating plan = data overlay**: o'quvchi rasmi + ball + flag bevosita joyida; "Student view" (proyektor uchun ma'lumotsiz rejim); tasodifiy o'quvchi tanlagich |
| **Bromcom Teacher App** | Bitta ekranda registr + xulq + xabar + uy vazifa | "**bespoke teacher dashboard — single screen**" falsafasi; 19 000+ o'qituvchi; safeguarding hodisasini darsdan yuborish |
| **PowerSchool PowerTeacher Pro** | Gradebook (an'anaviy + standartlarga asoslangan baho) | Baholash chuqurligi: kategoriyalar, vaznlar, standart bo'yicha o'zlashtirish, darsда tahlil ("class performance" ko'rinishi), hisobot shablonlari |
| **aSc EduPage** | Dars sahifasi: mavzu + davomat + baho + uy vazifa | **O'quv rejadan keyingi mavzuni tanlash** (bizda shu model bor); offlayn mobil; ota-ona elektron ma'lumotnomasi (absence note) |
| **WebUntis / Untis** | "Bugungi darslarim" + o'zgarishlar lentasi | **O'zgarish/o'rinbosarlik overlay'i** — asl jadval buzilmaydi, ustiga qatlam; push bildirishnoma |
| **Satchel One (SMHW)** | Uy vazifa hayot sikli | Uy vazifa: muddat, fayl, test/quiz, **resursni qayta ishlatish**, topshirish/tekshirish oqimi, AI yordamchi (Sidekick) differensial vazifa generatsiyasi |
| **Class Charts** | Ma'lumotga boy o'tirish sxemasi | "2 klik xulq", o'qituvchi tomonidan o'qituvchi uchun qurilgan; ish yukini kamaytirishni asosiy va'da qilib sotiladi |
| **Google Classroom** | Oqim + topshiriqlar | Sodda: material, topshiriq, baho — 3 obyekt. Murakkablikni rad etish darsi |
| **Teachmint** | Mobil o'qituvchi ilovasi + AI | AI: bir klikda dars/kviz generatsiyasi, uy vazifa yordami, reja tuzish |
| **Kundalik / eMaktab.Jurnal** (O'zbekiston) | Elektron jurnal: kunlik/haftalik/dars sahifasi | ⭐ **"Qaysi jurnalga mavzu/uy vazifa/baho qo'yilmagan" vidjetlari**; offlayn baho va mavzu kiritish; uy vazifani sinfga yoki alohida o'quvchiga berish va **boshqa sinfga nusxalash**; bahoni tuzatish cheklovi (muddat) |

**Lokal kontekst:** bizning o'qituvchilarimiz Kundalikni biladi. Demak UX tanishligi bo'yicha
"jurnal" metaforasi + "qoldirib ketganlarim" vidjeti — eng tez qabul qilinadigan yo'l.

---

## 2. Kanonik "o'qituvchining bir kuni" (dunyo namunalaridan yig'ilgan 7 bosqich)

| # | Vaqt | O'qituvchi nimani ko'rishi kerak | Qanday amal qiladi |
|---|---|---|---|
| 1 | **Ertalab kirganda** | Bugungi darslar lentasi; o'zgarishlar (bekor/o'rinbosarlik); mening bugungi o'rinbosarlik vazifalarim; kutilayotgan ishlar (mavzu/baho/uy vazifa qoldirilganlar); bugun yo'q bo'ladigan o'quvchilar (ruxsat olingan); e'lonlar | 1 ta ekran, hech narsa bosmasdan |
| 2 | **Dars oldidan (5 daq)** | Keyingi mavzu (KTP'dan), oldingi darsda nima o'tilgani, berilgan uy vazifa, material, xona, guruh tarkibi va o'zgarishlar (yangi o'quvchi/ketgan) | "Darsni ochish" |
| 3 | **Dars boshi (1 daq)** | O'quvchilar to'ri/o'tirish sxemasi, default "keldi" | Yo'q bo'lganlarni belgilash → avtomatik saqlanadi |
| 4 | **Dars davomida** | Kimni so'rash kerakligi (kam so'ralgan/past trend), o'quvchi kartasi (ballar, davomat, izoh, flaglar) | Ball qo'yish, izoh, xulq belgisi |
| 5 | **Dars oxiri (2 daq)** | O'tilgan mavzuni tasdiqlash, uy vazifa (oldingisini nusxalash yoki shablon), material biriktirish | 2 klik |
| 6 | **Kun oxiri** | Bugun bajarilmagan ishlar; ota-onaga xabar kerak bo'lganlar (3 marta yo'q, 2 marta vazifasiz) | Tanlab xabar yuborish |
| 7 | **Hafta/chorak oxiri** | Guruh bo'yicha o'zlashtirish, KTP qamrovi (reja vs fakt), chorak bahosini chiqarish | Hisobot/eksport |

Bu 7 bosqich — bizning ekran dizaynimiz uchun **tekshiruv ro'yxati**.

---

## 3. "Darsга biriktirilishi kerak bo'lgan hamma narsa" — payload katalogi

Dars (bizda `Jadval Yozuvi` + sana, ERPNext'da `Course Schedule`) atrofida dunyo tizimlari
quyidagilarni osadi. ✅ = bizda bor, 🟡 = qisman, ❌ = yo'q.

**Darsning o'zi**
- ✅ fan, guruh, xona, vaqt, dars raqami, o'qituvchi
- ✅ o'zgarish/bekor/o'rinbosar overlay
- ✅ rejadagi mavzu (KTP qatori) va "o'tdim" fakti (`Dars Bajarilishi`)
- ❌ dars maqsadi/natijalari (learning objectives) — proyektorga chiqariladigan matn
- ❌ dars materiali (fayl/havola) — hozir fayl faqat uy vazifada
- ❌ dars turi (yangi mavzu / takrorlash / nazorat ishi / laboratoriya)
- ❌ dars o'tilgan vaqt belgisi (registr qachon olingani — nazorat uchun)

**O'quvchilar**
- ✅ ro'yxat, davomat (Keldi/Kelmadi/Kasal/Qatnashmadi), bugungi baho
- ✅ chorak o'rtachasi, so'nggi 6 ball, chorak davomidagi yo'qliklar soni
- 🟡 o'quvchi kartasi (`baholash.oquvchi_karta` API bor — dars ekraniga ulanmagan)
- ❌ rasm (yuzni eslab qolish; yangi/o'rinbosar o'qituvchi uchun kritik)
- ❌ tibbiy/allergiya, maxsus ehtiyoj, pedagogik eslatma (Arbor "contextual details")
- ❌ ota-ona aloqasi (bir tegishda qo'ng'iroq/Telegram)
- ❌ kechikish (Late) holati — hozir faqat 4 ta davomat holati
- ❌ xulq/faollik belgisi (+/−), rag'bat ballari
- ❌ o'tirish sxemasi
- ❌ trend va xavf bayrog'i (↘︎, 3 ta ketma-ket past, davomat < 80%)

**Vazifa va baholash**
- ✅ uy vazifa (matn, muddat, max ball, fayl) + chorak tarixi
- ❌ uy vazifani **tekshirish** (kim qildi/qilmadi, ball) — `Uy Vazifa`da max_ball bor, lekin
  o'quvchi-ba-o'quvchi natija yo'q
- ❌ uy vazifani shablondan olish / oldingi guruhdan nusxalash (Kundalik, Satchel)
- ❌ baho turi/vazni (og'zaki, nazorat ishi, uy vazifa) — hozir `baho` yagona Int
- ❌ nazorat ishi/BSB-BSBB tipidagi alohida baholash obyekti

**O'qituvchining o'zi uchun**
- ❌ "qoldirilgan ishlar" vidjeti (mavzu/baho/uy vazifa qo'yilmagan darslar)
- ❌ shaxsiy eslatma (dars/guruh/o'quvchi bo'yicha)
- ❌ bildirishnoma (jadval o'zgardi, o'rinbosarlik berildi)

---

## 4. O'zlashtirish ko'rsatkichi — dunyo qanday ko'rsatadi

Dunyo amaliyotining umumiy yadrosi (Arbor "attainment", PowerTeacher "class performance",
UK MIS'dagi "flight path", RAG rang kodlash):

1. **Bitta raqam** — joriy daraja (bizda chorak o'rtachasi ✅).
2. **Bitta rang** — RAG: yashil (kutilganidan yuqori) / sariq (chegarada) / qizil (orqada).
   Rang **mutlaq ballga emas**, "kutilgan darajaga nisbatan"ga qo'yiladi.
3. **Bitta o'q** — trend: so'nggi 3-5 ball oldingi 3-5 balldan yuqorimi (↗︎ → ↘︎).
4. **Bayroqlar** — davomat %, ketma-ket yo'qlik, uy vazifa bajarmaslik, qarzdorlik (bizda bu
   ma'lumot `Qarz Ishi`da bor, lekin o'qituvchiga ko'rsatilmasligi kerak — bu sotuv bo'limining ishi).
5. **Sparkline** — so'nggi ballar chizig'i (bizda matn ko'rinishida bor: "5 4 5 3").

**Bizga tavsiya (hisoblash arzon, kesh talab qilmaydi):**
```
o'rtacha  = chorakdagi ballar o'rtachasi
trend     = so'nggi 3 ball o'rtachasi − oldingi 3 ball o'rtachasi   (±0.3 dan katta bo'lsa o'q)
davomat % = (darslar − yo'q)/darslar
rang      = qizil: o'rtacha < 3 YOKI davomat < 80% YOKI ketma-ket 3 ta past
            sariq: o'rtacha < 4 YOKI davomat < 90%
            yashil: qolgani
```
Dars kokpitidagi kartada: `Ism · 4.2 ↘︎ · 🔴` — uch belgi, boshqa hech narsa.

---

## 5. Mikro-UX qoidalari (dunyo tizimlaridan o'lchab olingan)

- **Default-present**: registr ochilganda hamma "keldi"; faqat istisno teriladi. (Bizda ✅)
- **Optimistik saqlash + undo**: bosilgan zahoti rang o'zgaradi, server fonda; xato bo'lsa qaytariladi.
- **Keypad**: baho uchun 5/4/3/2 katta tugma + ixtiyoriy raqamli kiritish. (Bizda ✅)
- **Klaviatura**: ↑↓ o'quvchi, 2–5 baho, H/K/Q davomat, Enter → keyingi. (Bizda ❌ — tez qo'shiladi)
- **Dars taymeri**: sarlavhada "dars tugashiga 12 daq" — registrni o'z vaqtida olishga undaydi.
- **‹ / › navigatsiya**: dars kokpitining o'zida oldingi/keyingi darsга o'tish (Arbor).
- **Guruh almashtirgich**: sarlavhadagi dropdown — bugungi darslarim ro'yxati.
- **Proyektor rejimi**: shaxsiy ma'lumotlarsiz ko'rinish (Arbor "Student view") — mavzu, uy vazifa,
  tasodifiy o'quvchi tanlagich.
- **Offlayn**: `localStorage` navbati + qayta urinish (EduPage/Kundalik darajasi).
- **Bitta ekran, scroll yo'q** — 15" noutbukda chap: o'quvchilar, o'ng: reja+uy vazifa. (Bizda ✅)

---

## 6. Gap-analiz: bizда hozir nima bor

Kod bo'yicha tekshirildi (`target_zenit/page/mening_jadvalim`, `page/dars_sessiya`,
`dars_jadvali/baholash.py`, `oquv_reja.py`).

**✅ Allaqachon dunyo darajasida:**
- `Mening jadvalim`: bugungi darslar lentasi + haftalik to'r + o'rinbosarlik vazifalari +
  o'zgarish overlay'i (bekor/o'rinbosar) + darsга bosib kirish.
- `Dars sessiyasi` kokpiti: bitta ekranda o'quvchilar (chorak o'rtachasi, so'nggi ballar, yo'qlik soni)
  + keypad (baho/davomat) + o'quv reja mavzulari ("o'tdim" belgilash) + uy vazifa formasi va tarixi.
- Dars = hub modeli (`Jadval Yozuvi` + sana → `Dars Natijasi`, `Dars Bajarilishi`, `Uy Vazifa`).
- Ruxsat qatlami: o'qituvchi faqat o'z darsini ko'radi (`_mening_instructorim`).

**❌ Dunyo namunalariga nisbatan yetishmayotgani (ustuvorlik tartibida):**

| # | Yetishmayotgan | Manba | Qiymat |
|---|---|---|---|
| 1 | **"Qoldirilgan ishlarim" vidjeti** (mavzu/baho/uy vazifa qo'yilmagan darslar) | Kundalik | ⭐⭐⭐ |
| 2 | **Darsdan darsга ‹/› o'tish** + guruh almashtirgich kokpit ichida | Arbor | ⭐⭐⭐ |
| 3 | **O'quvchi kartasi dars ichida** (tarix, davomat, izoh, ota-ona aloqasi) — API bor | Arbor | ⭐⭐⭐ |
| 4 | **Trend + RAG rang + xavf bayrog'i** | UK MIS | ⭐⭐⭐ |
| 5 | **Uy vazifani tekshirish** (kim qildi/ball) + nusxalash/shablon | Satchel, Kundalik | ⭐⭐⭐ |
| 6 | **Klaviatura bilan boshqarish + optimistik saqlash/undo** | hammasi | ⭐⭐ |
| 7 | **Kechikish (Late) + vaqt belgisi** | hammasi | ⭐⭐ |
| 8 | **Dars materiali/maqsadi biriktirish** | Arbor, Classroom | ⭐⭐ |
| 9 | **Kontekst flaglar** (tibbiy, maxsus ehtiyoj, pedagogik eslatma) | Arbor | ⭐⭐ |
| 10 | **O'quvchi rasmi + o'tirish sxemasi** | Class Charts, Arbor | ⭐⭐ |
| 11 | **Mobil/offlayn rejim** | EduPage, Bromcom | ⭐⭐ |
| 12 | **Baho turi/vazni, nazorat ishi obyekti** | PowerTeacher | ⭐ |
| 13 | **Proyektor rejimi + tasodifiy o'quvchi** | Arbor | ⭐ |
| 14 | **Bildirishnoma** (jadval o'zgardi / o'rinbosarlik) | WebUntis | ⭐ |

---

## 7. Tavsiya etilgan maket — "Mening kunim" (1-ekran)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Salom, Dilnoza Karimova          Dushanba, 12.10.2026      [🔄 Yangilash] │
│ Bugun: 5 dars · 2 ta ish qoldi · 1 o'zgarish                              │
├───────────────────────────────────────────────────────────────────────────┤
│ ⚠️ QOLDIRILGAN ISHLAR (2)                                                 │
│  • 09.10 Matematika 7A — baho qo'yilmagan            [Ochish]             │
│  • 10.10 Matematika 8B — mavzu belgilanmagan         [Ochish]             │
├───────────────────────────────────────────────────────────────────────────┤
│ BUGUNGI DARSLAR                                                           │
│ ┌────────────┐┌────────────┐┌────────────┐┌────────────┐┌────────────┐    │
│ │1· 08:30    ││2· 09:25 ⏱  ││3· 10:20    ││4· 11:15 🔄 ││5· 12:10 ⛔ │    │
│ │Matem. 7A   ││Matem. 8B   ││Matem. 7B   ││Matem. 9A   ││Matem. 9B   │    │
│ │§12 Kasrlar ││keyingi:§7  ││keyingi:§13 ││o'rinbosar: ││bekor:      │    │
│ │✓ o'tildi   ││HOZIR       ││            ││ A. Yusupov ││ tadbir     │    │
│ │24/25 · 4.1 ││            ││            ││            ││            │    │
│ └────────────┘└────────────┘└────────────┘└────────────┘└────────────┘    │
├───────────────────────────────────────────────────────────────────────────┤
│ DIQQAT TALAB QILADI                 │ HAFTAM                              │
│ • Aliyev S. (7A) — 3 dars yo'q      │ Du 5 · Se 4 · Ch 5 · Pa 4 · Ju 3    │
│ • Karimov J. (8B) — 3 ta past baho ↘│ Jami 21 dars · KTP qamrovi 62%      │
│ • 7B — uy vazifa 2 haftadan beri yo'q│                                     │
└───────────────────────────────────────────────────────────────────────────┘
```

**Dars kokpitiga qo'shiladigan sarlavha (2-ekran):**
```
‹ Oldingi dars │ Matematika · 7A ▾ │ 2-dars 09:25–10:10 · ⏱ 12 daq qoldi │ Keyingi dars ›
```

---

## 8. Bosqichli reja (tavsiya)

**Bosqich 1 — "qoldirmaslik" qatlami (eng katta qiymat / eng arzon):**
1. `Mening jadvalim`ga **"Qoldirilgan ishlarim"** paneli (oxirgi 14 kun: mavzu / baho / uy vazifa yo'q darslar).
2. Dars kokpitida **‹/› navigatsiya + bugungi darslar dropdown**i.
3. **Klaviatura boshqaruvi + optimistik saqlash + undo**.

**Bosqich 2 — o'quvchini ko'rish:**
4. Kartalarga **trend o'qi + RAG rang + xavf bayrog'i**.
5. Kartaga uzoq bosilganda / "i" tugmasi — **o'quvchi kartasi** (mavjud `oquvchi_karta` API'dan;
   tarix, davomat %, oxirgi izohlar, ota-ona aloqasi).
6. **Kechikish (Late)** holati + registr olingan vaqt.

**Bosqich 3 — vazifa sikli:**
7. **Uy vazifani tekshirish**: `Uy Vazifa Natijasi` (student, bajardi, ball, izoh) + kokpitda
   "oldingi vazifa" ustuni.
8. **Nusxalash/shablon**: "shu vazifani boshqa guruhga ber", "oldingi darsnikini takrorlash".
9. **Dars materiali** (fayl/havola) va dars maqsadi.

**Bosqich 4 — sinf boshqaruvi va mobil:**
10. O'quvchi rasmi + **o'tirish sxemasi** + proyektor rejimi + tasodifiy tanlagich.
11. Kontekst flaglar (tibbiy/maxsus ehtiyoj/pedagogik eslatma).
12. **Mobil layout + offlayn navbat**.

**Bosqich 5 — baholash chuqurligi:**
13. Baho turi/vazni (og'zaki / uy vazifa / nazorat ishi) va chorak bahosini avtomatik chiqarish.
14. Bildirishnomalar (jadval o'zgarishi, o'rinbosarlik) — Telegram/push.

---

## 9. Ochiq savollar (foydalanuvchiga — defaultlar bilan boshlash mumkin)

1. **Baho tizimi**: 5 ballik (hozirgi kod 1–100 ham qabul qiladi) — chorak bahosi qanday chiqadi:
   oddiy o'rtacha, vaznli, yoki qo'lda? Nazorat ishlari (BSB/BSBB) alohida hisoblanadimi?
2. **Kechikish** alohida holat bo'lsinmi (Keldi/Kechikdi/Kelmadi/Kasal/Sababli)?
3. **Uy vazifa tekshiriladimi** (har o'quvchiga ball) yoki faqat e'lon qilinadimi?
4. **Xulq/rag'bat ballari** kerakmi (Class Charts uslubi) yoki bizning maktabга ortiqchami?
5. **O'quvchi rasmlari** bazada bormi (o'tirish sxemasi va kartalar uchun shart)?
6. **O'qituvchi qaysi qurilmadan ishlaydi** — sinfda kompyuter bormi yoki telefon?
   (Bu mobil/offlayn bosqichining ustuvorligini belgilaydi.)
7. **Ota-onaga xabar** o'qituvchidan ketadimi yoki faqat ma'muriyatdan?
8. Dars materiali va o'quvchi ko'rinishi (o'quvchi kabineti) rejadami — bo'lsa, uy vazifa
   o'quvchiga qanday yetadi (hozir faqat o'qituvchi ko'radi)?

---

## 10. Manbalar

- Arbor — [Lesson Dashboard](https://support.arbor-education.com/hc/en-us/articles/203808082-Managing-my-class-from-the-Lesson-Dashboard-Overview),
  [My Classroom](https://support.arbor-education.com/hc/en-us/articles/360012179858-My-Classroom-your-classroom-management-tool),
  [My Homepage](https://support.arbor-education.com/hc/en-us/articles/360014867198-My-Homepage-your-personalised-Arbor-dashboard),
  [Teachers guide](https://support.arbor-education.com/hc/en-us/articles/115000129725-Introduction-to-Arbor-Guide-for-new-Teachers)
- Bromcom — [Teacher App](https://bromcom.com/news/new-version-teacher-app), [For Teachers docs](https://docs.bromcom.com/article-categories/for-teachers/)
- PowerSchool — [PowerTeacher Pro user guide](https://cdnsm5-ss20.sharpschool.com/UserFiles/Servers/Server_3068775/File/Powerschool/Teachers/Teacher%20Resources/ps12x_powerteacher_pro_user_guide.pdf)
- aSc EduPage — [edupage.org](https://www.edupage.org/), [mobil ilova](https://play.google.com/store/apps/details?id=air.org.edupage)
- Satchel One — [teamsatchel.com](https://www.teamsatchel.com/products/smhw.html), [uy vazifa va ish yuki](https://blog.teamsatchel.com/homework-teacher-workload/)
- Class Charts — [classcharts.com](https://www.classcharts.com/), [EdTech Impact sharhi](https://edtechimpact.com/products/class-charts/)
- Teachmint — [Classroom Platform](https://www.teachmint.com/en-us/products/classroom-platform)
- Kundalik/eMaktab — [imkoniyatlar](https://emaktab.uz/features), [Jurnallar bo'limi yangilandi](https://emaktab.uz/news/417), [eMaktab.Jurnal ilovasi](https://play.google.com/store/apps/details?id=uz.teacherJournal.app)
