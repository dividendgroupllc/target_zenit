# Dars jadvali va o'quv rejasi — jahon tajribasi tadqiqoti

**Sana:** 2026-10-07. **Maqsad:** Target Zenit uchun o'quvchi va o'qituvchilarga mo'ljallangan dars jadvali modulini qurishdan oldin dunyo standartlarini o'rganish.
**Holat:** faqat tadqiqot/tahlil — arxitektura va implementatsiya keyingi bosqichda.

---

## 0. Lokal bazadagi boshlang'ich holat (2026-10-07 tekshiruvi)

| Obyekt | Holat | Xulosa |
|---|---|---|
| Student Group (sinflar) | **21 ta** (1 A(full) … 11 B(hybrid), Pre school), 301 a'zolik | Sinflar tayyor — jadvalning "kim" o'qi bor |
| Academic Year | 1 (2026-2027) | bor |
| Academic Term (chorak) | **0** | kerak bo'ladi (chorak kesimi) |
| Course (fanlar) | **0** | fanlar katalogi yo'q — yaratish kerak |
| Instructor (o'qituvchi) | **0** | lekin Employee'da 40+ o'qituvchi lavozimi bor (English teacher ×8, Primary Education ×6, Tutor ×4, Mathematics ×2 …) → **Instructor Employee'ga bog'lanadi** |
| Room (xona) | **0** | sinfxonalar ro'yxati yo'q |
| Program | 0 | ixtiyoriy (ERPNext'da dastur/yo'nalish) |
| Course Schedule | **0** | jadval hali yo'q |

**Muhim nom belgisi:** sinf nomlarida `(full)` va `(hybrid)` bor — demak maktabda ikki xil o'qish rejimi mavjud. Jadval modeli buni hisobga olishi kerak (hybrid sinf kunlari/soatlari farq qilishi mumkin — aniqlash kerak, §10 savol 1).

---

## 1. Dunyoda "dars jadvali" uch xil mahsulotda yashaydi

| Oila | Vakillar | Nimaga kuchli | Cheklovi |
|---|---|---|---|
| **Timetable generator** (jadval tuzuvchi) | aSc TimeTables, Untis, FET (bepul), Prime Timetable, Edval | Avtomatik generatsiya, cheklovlar optimizatsiyasi, konflikt tekshiruvi | Alohida dastur; ERP bilan import/eksport orqali bog'lanadi |
| **SIS/MIS** (maktab boshqaruvi) | Arbor, Bromcom, PowerSchool, Veracross, Classter | O'qituvchi ish stoli, davomat, baho, ota-ona portali — jadval **kundalik ishning markazi** | Generatsiya kuchsizroq (ko'pincha tashqi generator bilan) |
| **LMS** (dars mazmuni) | Google Classroom, Toddle, ManageBac, Moodle | Uy vazifasi, materiallar, topshiriqlar | Jadval ikkinchi darajali, ko'pincha umuman yo'q |

**Xulosa:** bizga kerak bo'lgani — **SIS yondashuvi** (jadval = kundalik ishning markazi), ustiga **generatorning konflikt-tekshiruv mantiqi**, va keyinchalik LMS tomoni (uy vazifasi) ulanadi.

## 2. Untis / WebUntis — sanoat etaloni (Yevropa)

Dunyoda eng keng tarqalgan maktab jadval tizimi. Undan olinadigan asosiy saboqlar:

- **Jadval = shablon + kunlik voqelik.** Haftalik "ideal" jadval alohida, har kungi haqiqiy holat (almashtirish, bekor qilish, xona o'zgarishi) alohida qatlam. Bu eng muhim arxitektura qarori.
- **O'rinbosarlik (substitution planning)** — alohida va juda ishlangan modul: o'qituvchi kasalligini **o'zi mobil ilovada** belgilaydi → tizim o'sha kunning ochiq darslarini avtomatik hisoblaydi → dispetcher o'rinbosar tayinlaydi → o'quvchi/ota-ona/o'qituvchiga **push bildirishnoma** ketadi.
- **Mobil ilova** o'quvchi, ota-ona va o'qituvchiga bitta ilovada har xil ko'rinish beradi; bugungi o'zgarishlar alohida ajratib ko'rsatiladi.
- Optimizatsiya **og'irliklar (weights)** asosida: har cheklovga 0–100 orasida muhimlik beriladi.

## 3. aSc TimeTables / Edupage — avtomatik generatsiya

- **Kartochka metaforasi:** har dars — kartochka; qo'lda sudrab ko'chirish mumkin, tizim darhol qaysi joylar mumkin/mumkin emasligini ko'rsatadi (yashil/qizil).
- **Generatsiyadan oldin "maslahatchi" (advisor)**: ma'lumotlarni tekshirib, "bu cheklovlar bilan jadval chiqmaydi" deb oldindan ogohlantiradi — bu juda muhim UX: imkonsiz talabni generatsiyadan **oldin** aytadi.
- Generatsiya 100% avtomatik emas: amalda **80–90% avtomatik + qolganini qo'lda** tuzatish standart ish oqimi.

## 4. SIS oilasi (Arbor, Bromcom, PowerSchool) — o'qituvchi ish stoli

Bizga UX jihatidan eng kerakli qism:

- O'qituvchi tizimga kirganda **"Bugungi darslarim"** ro'yxatini ko'radi (vaqt, sinf, fan, xona).
- **Dars ustiga bosilsa — darhol davomat jurnali ochiladi** (Arbor: "My Classroom", Bromcom: "Lesson Dashboard"). Ya'ni jadval shunchaki ko'rinish emas, **ish boshlash nuqtasi**.
- Bitta dars kartasida: o'quvchilar ro'yxati, davomat, baho, xulq, o'tirish rejasi.
- Ota-ona ilovasida jadval + davomat + uy vazifasi bitta oqimda.

## 5. MDH / O'zbekiston: Kundalik (eMaktab)

- O'zbekistonda **davlat standarti** (Vazirlikning 2018-yil 251-son buyrug'i): elektron jurnal + kundalik. Jadval, davomat, baho, uy vazifasi bitta tizimda.
- Ko'rinishlar: o'quvchi/ota-ona uchun "kundalik" (hafta bo'yicha darslar + uy vazifasi + baho), o'qituvchi uchun "jurnal".
- **Amaliy xulosa:** xususiy maktab bo'lsa ham, ota-onalar aynan shu ko'rinishga o'rganib qolgan — bizning o'quvchi/ota-ona ekrani shu mantiqqa yaqin bo'lsa, o'rganish vaqti nolga tushadi.

## 6. Kanonik ma'lumot modeli (sintez)

Dunyo tizimlarida takrorlanadigan beshta qatlam:

### 6.1 Qo'ng'iroq jadvali (bell schedule / Period)
Dars raqami → boshlanish/tugash vaqti (1-dars 08:30–09:15, tanaffus...). Alohida obyekt bo'lishi shart: vaqtlar o'zgarganda butun jadval emas, bitta jadval o'zgaradi. Juma yoki boshlang'ich sinflar uchun **alohida variant** bo'lishi mumkin.

### 6.2 Haftalik shablon (Timetable Entry)
`sinf × hafta kuni × dars raqami → fan + o'qituvchi + xona`. Bu — "ideal jadval", semestr davomida o'zgarmaydi.
**Hafta sikli:** ko'p tizimlar A/B hafta (ikki haftalik sikl) ni qo'llab-quvvatlaydi. Maslahat: **faqat haqiqatan kerak bo'lsa yoqish** (Arbor hujjatida ham shunday deyiladi) — oddiy maktabda bitta haftalik sikl yetarli.

### 6.3 Kunlik dars (Lesson / Course Schedule)
Shablondan **kalendar bo'yicha generatsiya qilinadi** (dam olish kunlari va bayramlar chiqarib tashlanadi). Davomat, baho, uy vazifasi aynan shunga bog'lanadi.
> ERPNext'dagi `Course Schedule` aynan shu qatlam (sanali), lekin **shablon qatlami YO'Q** — bu asosiy bo'shliq (§9).

### 6.4 O'zgarishlar qatlami (Substitution)
O'qituvchi yo'q → dars: o'rinbosar / birlashtirish / bekor / xona almashtirish. Asl jadval **o'zgarmaydi**, ustiga "o'zgarish" yoziladi — tarix saqlanadi, kim qachon nimani o'zgartirgani ko'rinadi.

### 6.5 O'quv reja (curriculum plan)
`sinf × fan → haftasiga necha soat`. Bu jadvalning **manbasi va tekshiruvchisi**: jadval tuzilganda "7-sinfda matematika 5 soat bo'lishi kerak edi, 4 ta qo'yilibdi" degan nazorat avtomatik ishlaydi.
O'zbekiston DTS bo'yicha haftalik yuklama: 1-sinf 21 soat, 2–4 — 24, 5 — 29, 6 — 30, 7 — 35, 8 — 33, 9 — 34, 10–11 — 31 soat. Xususiy maktabda o'z rejasi bo'ladi, lekin **struktura aynan shu** va davlat normasi bilan solishtirish imkoniyati kerak.

## 7. Har bir foydalanuvchi nimani ko'radi

| Kim | Asosiy ekran | Kerakli xususiyatlar |
|---|---|---|
| **O'quvchi / ota-ona** | Haftalik to'r (dushanba–shanba × darslar), bugungi kun ajratilgan | O'zgarishlar qizil/belgili; telefon ekranida bir kunlik ko'rinishga o'tadi; uy vazifasi va baho shu yerdan |
| **O'qituvchi** | "Bugungi darslarim" + shaxsiy haftalik jadval | Dars kartasiga bosib **davomat olish**; bo'sh soatlar (okno) ko'rinadi; haftalik yuklamasi (soat) jami |
| **Sinf rahbari** | O'z sinfining jadvali + davomat yig'masi | Kim darsga kirmadi — kunlik xulosa |
| **Zavuch / admin** | Butun maktab to'ri: sinflar × soatlar | Konflikt indikatori, bo'sh xonalar, o'qituvchi yuklamasi balansi, o'rinbosar tayinlash |
| **Rahbar/investor** | Statistik kesim | O'qituvchi yuklamasi, xona bandligi %, o'tilmagan darslar |

**UI qoidalari (dunyo amaliyotidan):**
- Fan ranglari — har fanga barqaror rang (tez o'qish uchun); matn emas, rang bilan navigatsiya.
- Telefon: haftalik to'r emas, **kunlik lenta** (vertikal) — gorizontal aylantirish yomon UX.
- Bugungi o'zgarishlar doim tepada, alohida bo'limda.
- Dars kartasida minimal 4 narsa: fan, o'qituvchi, xona, vaqt.

## 8. Avtomatlashtirish: generatsiya qanchalik real?

**Hard cheklovlar** (buzilmaydi):
1. Bir o'qituvchi bir vaqtda ikki joyda bo'lolmaydi
2. Bir sinfda bir vaqtda ikki dars bo'lmaydi
3. Bir xonada bir vaqtda ikki dars bo'lmaydi (bo'linuvchi guruhlardan tashqari)
4. O'qituvchining mavjud emas (ta'til/band) vaqtlari
5. Xona sig'imi va maxsus xona talabi (sport zali, laboratoriya, kompyuter sinfi)

**Soft cheklovlar** (imkon qadar):
- O'quvchida "oyna" (bo'sh soat) bo'lmasin; o'qituvchida kamroq bo'lsin
- Og'ir fanlar (matematika, fizika) ertalabki soatlarga
- Bir fan kuniga 2 martadan ko'p bo'lmasin; haftaga teng taqsimlansin
- O'qituvchi kunlari jamlansin (haftada 2 kun o'rniga 5 kun kelmasin)
- Jismoniy tarbiyadan keyin darhol kontrol ish bo'lmasin

**Amaliy tavsiya:** to'liq avtomatik generator — alohida katta loyiha (genetik algoritm / CSP solver). Dunyoda ham 100% avtomatik ishlamaydi. **Optimal yo'l — "yordamlashuvchi qo'lda tuzish" (assisted manual):**
1. Zavuch sudrab-tashlab (drag&drop) jadval tuzadi
2. Tizim **real vaqtda** konfliktni ko'rsatadi (qizil) va bo'sh variantlarni (yashil) taklif qiladi
3. O'quv rejaga nisbatan qolgan soatlar hisoblagichi: "Matematika 7A: 5 dan 3 tasi qo'yildi"
4. Keyingi bosqichda — avtomatik to'ldirish (eng oson darslardan boshlab)

Bu yondashuv 1–2 oyda emas, **bir necha haftada** ishga tushadi va amalda zavuchlar uni afzal ko'radi (nazorat ularda qoladi).

## 9. ERPNext/Frappe Education — nima bor, nima yo'q

**Bor:**
- `Course Schedule` — sanali dars yozuvi: student_group, course, instructor, room, schedule_date, from_time/to_time, rang
- `Course Scheduling Tool` — ommaviy generatsiya: sinf + fan + o'qituvchi + xona + hafta kuni + sana oralig'i → Course Schedule'lar yaratadi, **konfliktni tekshiradi** (o'qituvchi, xona, sinf bandligi)
- `Student Group`, `Instructor`, `Room`, `Course`, `Program`, `Academic Term`
- Davomat: `Student Attendance` Course Schedule'ga bog'lanadi

**Yo'q (bizning bo'shliqlar):**
| Bo'shliq | Oqibati |
|---|---|
| **Qo'ng'iroq jadvali (Period) yo'q** | Har darsga vaqt qo'lda yoziladi; vaqt o'zgarsa hamma yozuv o'zgaradi |
| **Haftalik shablon yo'q** | Faqat "sanali nusxa"; jadvalni bir butun ko'rib tahrirlash imkoni yo'q |
| **Vizual jadval ko'rinishi yo'q** | Faqat ro'yxat/kalendar; sinf × soat to'ri yo'q |
| **O'rinbosarlik moduli yo'q** | Kasallik/almashtirish hisobga olinmaydi |
| **O'quv reja (soat normasi) yo'q** | "Qancha soat qo'yilishi kerak edi" nazorati yo'q |
| **Portal ko'rinishlari zaif** | O'quvchi/ota-ona uchun qulay jadval ekrani yo'q |
| **A/B hafta yo'q** | Kerak bo'lsa — qo'shimcha |

**Qaror yo'nalishi:** ERPNext'ning `Course Schedule` + davomat zanjirini **saqlab qolish** (davomat, baho, Fees bilan bog'langan), ustiga target_zenit ichida yetishmagan qatlamlarni qurish: Period (qo'ng'iroq), Timetable (haftalik shablon) + generatsiya, Substitution, O'quv reja, va 3 ta ekran (zavuch / o'qituvchi / o'quvchi-ota-ona). Bu — qarzdorlik CRM'da ishlagan formulaning aynan o'zi: **standart yadroni buzmay, ustiga ishchi qatlam**.

## 10. Target Zenit uchun aniqlanishi kerak bo'lgan savollar

1. **`(full)` va `(hybrid)` sinflar farqi nima?** Hybrid o'quvchilar haftaning ayrim kunlari keladimi yoki onlaynmi? Jadval ularga boshqacha tuzilishi kerakmi?
2. **Qo'ng'iroq jadvali:** kuniga nechta dars, dars necha daqiqa, tanaffuslar, juma/shanba farqi? Shanba o'qiladimi?
3. **Guruhga bo'linish:** ingliz tili/informatika kabi fanlarda sinf 2 guruhga bo'linadimi (bir vaqtda ikki o'qituvchi)? Bu modelga jiddiy ta'sir qiladi.
4. **Xonalar:** har sinfning o'z xonasi bormi (boshlang'ich), yoki o'quvchilar xonama-xona yuradimi? Maxsus xonalar ro'yxati (sport zali, laboratoriya, IT)?
5. **O'quv reja manbai:** davlat DTS soatlarimi yoki maktabning o'z rejasi? Fanlar ro'yxati qayerda (Excel bormi)?
6. **O'qituvchi ↔ Employee:** Instructor yozuvlarini mavjud 114 Employee'dan avtomatik yaratamizmi (lavozimida "teacher/Tutor" bo'lganlar)?
7. **Kim jadval tuzadi** (zavuch/o'quv bo'limi) va hozir qanday tuzilyapti (Excel?) — mavjud faylni ko'rsak, strukturani aynan shunga moslaymiz.
8. **O'quvchi/ota-ona ko'rishi kerakmi** hozirdanoq (portal/Telegram), yoki avval ichki (zavuch + o'qituvchi) qismi yetarlimi?

## Manbalar

- [Smootables: Best school timetable software 2026](https://smootables.com/en/best-school-timetable-software-2026) · [Top 10 school timetabling software](https://www.rajeshkumar.xyz/blog/school-timetabling-software/)
- [Untis: Online substitution planning](https://www.untis.at/en/products/webuntis/online-substitution-planning) · [Untis Mobile App](https://www.untis.at/en/products/webuntis/untis-mobile-app-1) · [Untis timetable scheduling](https://www.untis.at/en/products/untis-timetable-scheduling)
- [Arbor: Timetable periods and weekly cycles](https://support.arbor-education.com/hc/en-us/articles/360035035793-Timetable-Periods-and-weekly-cycles) · [Arbor: My Classroom](https://support.arbor-education.com/hc/en-us/articles/360012179858-My-Classroom-your-classroom-management-tool)
- [Bromcom: New Teachers Dashboard](https://docs.bromcom.com/knowledge-base/how-to-use-the-new-teachers-dashboard-secondary/) · [Bromcom: View user timetables](https://docs.bromcom.com/knowledge-base/how-to-view-user-timetables/)
- [Frappe/ERPNext: Course Scheduling Tool](https://docs.frappe.io/education/course-scheduling-tool) · [ERPNext: Course Schedule](https://docs.erpnext.com/docs/v13/user/manual/en/education/course-schedule)
- [UniTime: University course timetabling with soft constraints (PATAT)](https://www.unitime.org/papers/patat03.pdf) · [Dynamic timetable generation using CSP (Springer)](https://link.springer.com/chapter/10.1007/978-81-322-2517-1_73)
- [TimetableMaster: Bell schedule configuration](https://www.timetablemaster.com/help/individual-student-scheduler/bell-schedule) · [A/B block schedule](https://unlockingtime.org/school-schedules/AB-Block-Schedule)
- [eMaktab/Kundalik — O'zbekiston elektron jurnal](https://emaktab.uz/news/16) · [Kundalik'da dars jadvali yaratish](https://idum.uz/ru/archives/14535)
- [O'zbekiston 2025–2026 o'quv reja (Vazirlik buyrug'i, PDF)](https://xalqtaliminfo.uz/storage/documents/1744872734O'quv_reja_2026_xalq860.pdf) · [Gazeta.uz: yangi DTS va o'quv dasturlari](https://www.gazeta.uz/oz/2026/08/31/school-program/)

---

# II QISM. Maktabning haqiqiy jadvali (Excel tahlili)

**Manba:** `Umumiy_dars_jadvali.xlsx` — "TARGET International School — Yunusobod filiali: UMUMIY DARS JADVALI (1A–11B)".
Tahlil sanasi: 2026-10-07. Struktura to'liq ochildi: **1000 ta dars yacheykasi**, 0 ta konflikt.

## 1. Jadvalning fizik tuzilishi

| Parametr | Qiymat |
|---|---|
| Sinflar | **20 ta**: 1A 1B 2A 2B 3A 4A 5A 5B 6A 6B 7A 7B 8A 8B 9A 9B 10A 10B 11A 11B |
| Kunlar | **5** (Dushanba–Juma). Shanba yo'q |
| Kuniga darslar | **10 ta** (9-10 darslar — HOMEWORK / EXTRA / CHOICE) |
| Har sinf haftalik yuklama | **aniq 50 soat** (hamma 20 sinfda bir xil) |
| Dars davomiyligi | 40 daqiqa |
| Noyob fanlar | **33 xil** |
| Noyob o'qituvchilar | **43 ta** (4 tasi "vakant": AI, Chess, Music, TUTOR) |

**Qo'ng'iroq jadvali:**
```
1: 09:00–09:40   2: 09:45–10:25   3: 10:30–11:10   4: 11:15–11:55
5: 12:45–13:25*  6: 13:30–14:10   7: 14:15–14:55   8: 15:00–15:40
9: 16:10–16:50  10: 16:55–17:35
```
**\* 5-dars — ikki xil (kritik detal):** 1A–5A sinflar 12:45–13:25 (tushlik 12:00–12:40); 5B–11B sinflar 12:00–12:40 (tushlik 12:45–13:25). Poldnik tanaffusi 15:45–16:05 (8 va 9-darslar orasida). Qolgan hamma darslar vaqti bir xil.

> **Model talabi:** qo'ng'iroq jadvali bitta emas — kamida **ikki variant** (kichik/katta sinflar), faqat 5-dars va tushlik bilan farq qiladi.

## 2. Eng muhim topilma: "daraja" (level/set) guruhlari

Oddiy dars: bitta sinf — bitta o'qituvchi. Lekin jadvalning **katta qismi** darajalarga bo'lingan:

| Fan | Guruhlar | Izoh |
|---|---|---|
| MATH (3 daraja) | High / Middle / Low | har darajaga alohida o'qituvchi |
| ENGLISH (3 daraja) | High / Middle / Low | |
| ENGLISH (2 daraja), MATH (2 daraja) | 2 ta | kichik sinflarda |
| IT (4 daraja) | 4 ta | CyberSecurity, Mobile/Flutter, No-Code/AI, Physics-IT |
| CHOICE (5 daraja) | 5 ta | tanlov: Physics, Chemistry/Biology, IT, Math, English |
| EXTRA (2 daraja) | 2 ta | qo'shimcha English + Math |

**Parallel bloklar** — bir vaqtning o'zida bir nechta sinf birga qo'yiladi va daraja bo'yicha qayta taqsimlanadi:

| Blok | Sinflar | Haftada |
|---|---|---|
| ENGLISH (3 daraja) | 8A, 8B, 9A, 9B | 10× |
| ENGLISH (3 daraja) | 10A, 10B, 11A, 11B | 10× |
| MATH (3 daraja) | 8A, 8B, 9A, 9B | 10× |
| MATH (3 daraja) | 10A, 10B, 11A, 11B | 10× |
| CHOICE (5 daraja) | 9A, 9B, 10A, 10B, 11A, 11B | 10× |
| MATH / ENGLISH (3 daraja) | 6A, 6B, 7A, 7B | 8× har biri |
| IT (4 daraja) | 5A+5B+6A+6B / 7A+7B+8A+8B / 9A+9B / 10A+10B+11A+11B | 5–6× |
| MATH (2 daraja), ENGLISH (2 daraja) | 5A, 5B | 8× / 4× |
| EXTRA (2 daraja) | 5A, 5B, 6A, 6B | 4× |

> **Bu arxitekturaning eng muhim talabi.** Jadval "sinf → dars" emas, **"o'qish guruhi (teaching group) → dars"** modeliga qurilishi kerak:
> - oddiy dars: guruh = bitta sinf
> - daraja darsi: guruh = bir nechta sinfdan yig'ilgan daraja guruhi (masalan "Math High 8–9")
> - Davomat, baho, o'qituvchi yuklamasi aynan shu guruhga bog'lanadi, sinfga emas.
> ERPNext'da bu `Student Group` bilan ifodalanadi (`Student Group` ni "Batch" emas, "Activity/Course" turida ochish) — ya'ni **sinf-guruhlardan tashqari daraja-guruhlar ham yaratiladi**.

## 3. O'qituvchilar va yuklama

Haqiqiy yuklama (daraja bloklarida bir o'qituvchi bitta dars sanaladi — sinflar soniga ko'paytirilmaydi):

| O'qituvchi | Haftalik soat | | O'qituvchi | Haftalik soat |
|---|---|---|---|---|
| Erdullaeva J. (rus tili) | **42** | | Abdug'afforov A. | 28 |
| Matyakubov L. (math High) | **40** | | AI VACANT | 28 |
| Abdumajidova S. (math Low) | **36** | | Werner Fourie | 26 |
| Fozilova N. (1B rahbar) | 31 | | MR Dileep Mani | 26 |
| Abdugulomova M. (1A rahbar) | 31 | | Dushayev Fayoz | 26 |
| Musulmonov M. (IT) | 31 | | Kabulov J. (P.E.) | 25 |
| Lucille J. Ilao (2A) | 29 | | Mamatov Diyor (tarix) | 22 |

> **Diqqat:** 40+ soat — juda yuqori yuklama (haftada 50 slot mavjud). Bu yerda tizim **o'qituvchi yuklamasi nazorati** bera oladi (dunyo amaliyotida odatiy soft-cheklov: haftalik norma + ketma-ket darslar chegarasi).

**Konflikt tekshiruvi:** joriy jadvalda bir o'qituvchining bir vaqtda ikki joyda bo'lishi **topilmadi (0 ta)** — jadval toza tuzilgan, migratsiya uchun ishonchli asos.

**Sinf rahbarlari** (HOMEWORK darsidan aniqlandi — 1–4 sinflarda):
1A Abdugulomova M. · 1B Fozilova N. · 2A Lucille J. Ilao · 2B Anvarovna X. · 3A Adilova N. · 4A Nida Umair

## 4. Fanlar ro'yxati (33 ta) va ularning kodi

`MATH` `ENGLISH` `RUS` `UZBEK` `CHINESE` `SCIENCE` `PHYSICS` `GEO` `HISTORY` `HIST.U` (O'zbekiston tarixi) `HIST.W` (Jahon tarixi) `IT` `AI` `ROBOTICS` `CHESS` `ART` `MUSIC` `P.E / GYM` `MENTAL.M` (mental matematika) `MOR EDU` (axloq) `PER DEV` (Personal Development) `G PRES` (Group presentation) `FINANCE` `BUS` (Business) `ECO` (Economics) `HOMEWORK` (uy vazifasi soati, sinf rahbari bilan) `EXTRA` `CHOICE` + daraja variantlari.

**Namuna haftalik reja (o'quv reja rekonstruksiyasi):**
- **1A** (50): ENGLISH 10, HOMEWORK 10, MATH 8, RUS 5, CHESS 2, ROBOTICS 2, FINANCE 2, MENTAL.M 2 …
- **7A** (50): MATH 8, ENGLISH 8, IT 5, UZBEK 2, RUS 2, ROBOTICS 2, AI 2, MOR EDU 2 …
- **11B** (50): ENGLISH 10, MATH 10, CHOICE 10, IT 5, ECO 4, G PRES 2, FINANCE 2, AI 2 …

## 5. Bazadagi ma'lumot bilan solishtirish (migratsiya tayyorligi)

| Tekshiruv | Natija |
|---|---|
| Sinf nomlari | Excel `1A` ↔ baza `1 A(full)`; `1B` ↔ `1 B(hybrid)`. **Moslik to'liq** (3 va 4-sinfda faqat A bor — bazada ham shunday). Bazada qo'shimcha `Pre school` bor, Excelda yo'q |
| **`(full)` / `(hybrid)` ma'nosi** | Jadval bo'yicha B sinflar ham **to'liq 50 soat** o'qiydi — demak "hybrid" dars soniga ta'sir qilmaydi (to'lov/format belgisi bo'lsa kerak). **Tasdiqlash kerak** |
| O'qituvchilar ↔ Employee | 43 tadan **22 tasi avtomatik mos keldi**; ~11 tasi **transliteratsiya farqi** bilan bor (Erdullaeva↔Yerdullayeva, Djiyenbayeva↔Djiyenbaeva, Abdug'aniyev↔Abduganiyev, Mo'minjonov↔Mominjonov); **~10 tasi Employee'da umuman yo'q** (Werner Fourie, Matyakubov L., Karimxonov Abbos, Dushayev Fayoz, Rasulova M., Saidahmadov M., Poziljonova N., Jamolov Mavlonbek, Muxtorov Husan, Kumar) |
| Xonalar | Excelda **xona ustuni yo'q** — xonalar jadvalda yuritilmaydi |

## 6. Shu tahlildan kelib chiqadigan arxitektura talablari

1. **Teaching Group (o'qish guruhi) markaziy obyekt** — sinf emas. Oddiy dars uchun guruh = sinf; daraja darsi uchun guruh = bir nechta sinfdan yig'ilgan daraja guruhi. Har o'quvchi bir nechta guruhga a'zo (sinfi + matematika darajasi + ingliz darajasi + CHOICE tanlovi).
2. **Parallel blok** tushunchasi: "8A+8B+9A+9B, dushanba 1-dars, MATH" — bitta blok, ichida 3 ta guruh. Jadval tuzishda blok bir butun ko'chiriladi.
3. **Ikki xil qo'ng'iroq jadvali** (1A–5A va 5B–11B) — faqat 5-dars/tushlik farqi.
4. **Xona** majburiy emas (hozir yuritilmaydi) — ixtiyoriy maydon bo'lsin, keyin qo'shilsa ishlaydi.
5. **Vakant o'qituvchi** holati kerak (AI VACANT, Chess vakant, Music vakant) — dars bor, o'qituvchi yo'q; bu hisobotda ko'rinishi kerak.
6. **O'qituvchi yuklama nazorati** — 40+ soatlilar bor, tizim haftalik jamini ko'rsatib tursin.
7. **Import:** shu Excel formatini o'qiydigan importer yozish mumkin — struktura aniq va barqaror (kun/№/vaqt + 20 sinf ustuni, yacheykada `FAN\nO'qituvchi` yoki `FAN (N daraja)\nHigh: …\nMiddle: …\nLow: …`).

## 7. Yangilangan savollar (Excel tahlilidan keyin)

1. `(full)` va `(hybrid)` — dars soniga ta'sir qilmasa, farqi nimada? (to'lov? masofaviy kunlar?)
2. Daraja guruhlariga o'quvchilar **qanday taqsimlangan** — ro'yxat bormi (kim High, kim Middle, kim Low)? Bu jadvalni ishga tushirish uchun shart.
3. CHOICE (tanlov) darsiga o'quvchilar ro'yxati bormi (kim Physics, kim Chemistry...)?
4. Jadvalda yo'q ~10 o'qituvchi: ular Employee'ga kiritiladimi yoki soatbay/tashqi mutaxassismi?
5. Xona nazorati kerakmi (hozir yuritilmaydi), yoki faqat sinf+o'qituvchi yetarlimi?
6. Shanba umuman o'qilmaydimi (jadvalda yo'q)?
7. Pre school guruhi jadvalga kiradimi?
8. Jadval chorak davomida o'zgaradimi yoki yil davomida barqarormi? O'zgarish bo'lsa — kim va qanday kiritadi?

---

# III QISM. O'qituvchi jadvallari (skrinshotlar) tahlili

**Manba:** `~/Pictures/Screenshots/` — **39 ta PNG**, har biri bitta o'qituvchining shaxsiy jadvali
("TARGET International School · Yunusobod Filiali · <O'QITUVCHI> · Расписание учителя · N darslar/hafta").
Bular Excel bilan **bir xil ma'lumotdan** hosil qilingan ko'rinishlar (ma'lumot mos keldi: masalan Karimxonov Abbos 28 soat — Exceldan hisoblangani bilan aynan bir xil).

**Yangi beradigan qiymati:** Excelda ismlar qisqartirilgan (`Matyakubov L.`, `Anvarovna X.`), skrinshotlarda esa **to'liq ism** bor — bu Employee bazasi bilan bog'lash uchun hal qiluvchi.

## 1. To'liq ismlar jadvali (39 skrinshotdan)

| Excel'dagi qisqartma | To'liq ism (skrinshot) | Soat/hafta |
|---|---|---|
| Erdullaeva J. | **ERDULLAEVA JANAR** | 42 |
| Matyakubov L. | **MATYAKUBOV LUTFULLO HABIBULLO O'G'LI** | 40 |
| Abdumajidova S. | **ABDUMAJIDOVA SHOXSANAM** | 36 |
| Fozilova N. | **FOZILOVA NARGIZA** | 31 |
| Abdugulomova M. | **ABDUGULOMOVA MUXLISAXON** | 31 |
| Musulmonov M. | **MUSULMONOV MAMARAJAB** | 31 |
| Lucille J. Ilao | **LUCILLE JOHNALYN ILAO – 1A** | 29 |
| Anvarovna X. | **ANVAROVNA XOSIYAT** | 29 |
| Nida Umair | **NIDA UMAIR – 2A** | 29 |
| Adilova N. / Adilova Nigora | **ADILOVA NIGORA** | 29 |
| Karimxonov Abbos | **KARIMXONOV ABBOS** | 28 |
| Abdug'aniyev F. | **ABDUG'ANIYEV FIRDAVSBEK** | 28 |
| Saidahmadov M. | **SAIDAHMADOV MUHAMMADALI** | 28 |
| Abdug'afforov A. | **ABDUG'AFFOROV ABDURASHID** | 28 |
| — | **AI VACANT** (o'qituvchi yo'q) | 28 |
| — | **PERSONAL DEVELOPMENT** (fan nomi, o'qituvchi yo'q) | 28 |
| Boboyeva Sabrina | **BOBOYEVA SABRINA** | 26 |
| Werner Fourie | **WERNER FOURIE** | 26 |
| Dushayev Fayoz | **DUSHAYEV FAYOZ ANVAROVICH** | 26 |
| Kabulov J. | **KABULOV JAMSHID ILHOMOVICH** | 25 |
| Mamatov Diyor | **MAMATOV DIYOR ORIFOVICH** | 22 |
| Glory Ilao | **GLORY ILAO** | 21 |
| Usmonov I. | **USMONOV ISMOIL** | 21 |
| Nigmatov M. | **NIGMATOV MUHAMMADSODIQ** | 21 |
| Poziljonova N. | **POZILJONOVA NIGINA** | 21 |
| Saidazizova F. | **SAIDAZIZOVA FARANGIZ** | 20 |
| Mo'minjonov I. | **MO'MINJONOV ILYOSBEK** | 18 |
| Djiyenbayeva R. | **DJIYENBAYEVA ROBIYA ILYASOVNA** | 17 |
| Maulenova A. | **MAULENOVA AYDIN MUHAMBETOVNA** | 12 |
| Saydaxmedova S. | **SAYDAXMEDOVA SEVARA** | 12 |
| — | **CHESS VAKANT** | 12 |
| Jamolov Mavlonbek | **JAMOLOV MAVLONBEK** | 10 |
| Kumar | **KUMAR** (faqat shu — familiyasiz) | 10 |
| Adxamov Nasrullo | **ADXAMOV NASRULLO** | 8 |
| — | **TUTOR** (shaxs emas, rol) | 8 |
| Muxammadjonova D. | **MUXAMMADJONOVA DURDONA RUSTAMJON QIZI** | 7 |
| — | **MUSIC VAKANT** | 6 |

**Skrinshoti yo'q 5 o'qituvchi** (Excelda bor): MR Dileep Mani (26), Botirova Surayyo Z. (20), Rasulova M. (20), Anorqulov Lazizbek (20), Muxtorov Husan (12).

## 2. Employee bazasi bilan bog'lash — yakuniy holat

**Ishonchli mos keldi (24 ta)** — transliteratsiya farqlari bilan:

| Jadval | Employee | Lavozim |
|---|---|---|
| ERDULLAEVA JANAR | Yerdullayeva Janar | Russian language teacher |
| MATYAKUBOV LUTFULLO | Matyaqubov Lutfullo Habibullo o'g'li | Mathematics |
| ABDUMAJIDOVA SHOXSANAM | Abdumajidova Shoxsanam Ikromjon qizi | Mathematics teacher |
| KARIMXONOV ABBOS | Karimkhonov Abbosxon Doniyorxon o'g'li | English teacher |
| ABDUG'ANIYEV FIRDAVSBEK | Abduganiyev Firdavsbek Xabibullo o'gli | English teacher |
| DJIYENBAYEVA ROBIYA | Djiyenbaeva Robiya Ilyasovna | Tutor |
| MO'MINJONOV ILYOSBEK | Mominjonov Ilyosbek Shuxrat o'gli | Mathematics teacher |
| ANVAROVNA XOSIYAT | **Dadaboyeva Xosiyat Anvar qizi – 2B** | Primary Education |
| NIGMATOV MUHAMMADSODIQ | Muhammadsodiq Nigmatov | Mobile\Flutter |
| MR Dileep Mani | Dileep Mani | Business & Economics teacher |
| Rasulova M. | Rasuleva Malika Olimovna | Chinese teacher |
| Anorqulov Lazizbek | Anorqul Lazizbek Alisher o'gli | SAT English teacher |
| Botirova Surayyo Z. | Botirova Surayyo | English teacher |
| + Glory Ilao, Adilova Nigora, Nida Umair, Lucille J. Ilao, Fozilova Nargiza, Abdugulomova Muxlisaxon, Musulmonov Mamarajab, Usmonov Ismoil, Adxamov Nasrullo, Boboyeva Sabrina, Saidazizova Farangiz, Abdug'afforov Abdurashid, Kabulov Jamshid, Mamatov Diyor, Maulenova Aydin, Muxammadjonova Durdona | | |

**Employee bazasida YO'Q (7 ta) — kiritilishi kerak:**

| Jadval | Soat | Fan | Izoh |
|---|---|---|---|
| **WERNER FOURIE** | 26 | G PRES (Group presentation) | bazada umuman yo'q |
| **KUMAR** | 10 | CHOICE → Chemistry/Biology | faqat "Kumar" deb yozilgan, to'liq ism noma'lum |
| **DUSHAYEV FAYOZ ANVAROVICH** | 26 | ECO, BUS, FINANCE | bazada "Dushayev" familiyasi yo'q |
| **SAIDAHMADOV MUHAMMADALI** | 28 | FINANCE | bazada yo'q (Saidaxmedov Jamshid — boshqa shaxs, Direktor, Inactive) |
| **JAMOLOV MAVLONBEK** | 10 | CHOICE → Physics | bazada "Jamolov Alisher" bor (P.E., Inactive) — **boshqa shaxs** |
| **SAYDAXMEDOVA SEVARA** | 12 | — | bazada yo'q |
| **MUXTOROV HUSAN** | 12 | CHESS | bazada "Muxtorova Munisabonu" (Inactive) — boshqa shaxs |

**Shubhali (tasdiqlash kerak):** `POZILJONOVA NIGINA` (21 soat, IT→Python) ↔ bazadagi `Polvonova Nigina` (Python teacher) — ism va fan mos, familiya farq qiladi: bitta odammi yoki ikki xil kishimi?

**Shaxs bo'lmaganlar (Instructor sifatida yaratilmaydi, "vakant" holati bilan belgilanadi):** AI VACANT, CHESS VAKANT, MUSIC VAKANT, TUTOR, PERSONAL DEVELOPMENT.

## 3. Skrinshotlar tasdiqlagan qo'shimcha detallar

- O'qituvchi ko'rinishi (PDF) formati: `№ | vaqt | Dushanba..Juma` to'ri, yacheykada **fan nomi + vaqt + guruh/sinf belgilari** (masalan `Middle: 8A, 8B, 9A, 9B`), fanlar rangli.
- Daraja guruhlari o'qituvchi ko'rinishida aniq ko'rsatiladi: Karimxonov Abbos bir vaqtning o'zida **Middle (8–9)**, **high (10–11)** va **high (6–7)** guruhlarini olib boradi — ya'ni bitta o'qituvchi turli bloklarda turli darajani o'qitadi.
- Fan to'liq nomlari: `MOR EDU` = Moral Education, `CHOICE` ichidagilar: Physics / Chemistry-Biology / IT / Math / English.
- **Xona ma'lumoti bu yerda ham yo'q** — demak maktab jadvalni xonalarsiz yuritadi (tasdiqlandi).

## 4. Shundan kelib chiqadigan qo'shimcha talab

**Instructor yaratish strategiyasi:** 24 ta o'qituvchi mavjud Employee'dan avtomatik bog'lanadi (transliteratsiya lug'ati bilan), 7 tasi yangi kiritiladi (yoki HR bo'limi avval Employee'ga qo'shadi), 5 ta "vakant/rol" esa alohida turdagi yozuv sifatida yuritiladi — jadvalda dars bor, mas'ul yo'q; bu hisobotda ko'rinib turishi kerak ("o'qituvchi tayinlanmagan darslar: N ta").
