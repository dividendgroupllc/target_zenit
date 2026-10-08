# Dars jadvali — Arxitektura

**Sana:** 2026-10-08. **Asos:** `DARS_JADVALI_TADQIQOT.md` (I — jahon tajribasi, II — maktab Exceli, III — o'qituvchi skrinshotlari).
**Maqsad:** zavuch jadval tuzadigan, o'qituvchi "bugungi darslarim"ni ko'rib davomat oladigan, o'quvchi/ota-ona jadvalni ko'radigan tizim.

---

## 0. Asosiy qarorlar (qisqacha)

| № | Qaror | Sabab |
|---|---|---|
| 1 | **O'qish guruhi = ERPNext `Student Group`** (yangi doctype emas) | Davomat (`Student Attendance`) va `Course Schedule` unga tayyor bog'langan; sinf guruhlari (21 ta) allaqachon bor |
| 2 | **Jadval ikki qatlam:** haftalik shablon (`Jadval Yozuvi`) + sanali dars (`Course Schedule`) | Untis standarti; davomat/baho sanali darsga bog'lanadi, shablon esa bir butun tahrirlanadi |
| 3 | **Parallel blok** birinchi darajali obyekt | Maktab jadvalining yarmi blok (8A+8B+9A+9B → High/Middle/Low) — blok bir butun ko'chiriladi |
| 4 | Generatsiya **avtomatik solver emas**, "yordamlashuvchi qo'lda" | Dunyo amaliyoti: 80–90% qo'lda; mavjud jadval tayyor va toza (0 konflikt) — uni import qilish yetadi |
| 5 | **Xona — ixtiyoriy maydon** | Maktab jadvalni xonasiz yuritadi (Excel ham, PDF ham) |
| 6 | Mavjud Excel uchun **importer** yoziladi | 1000 yacheyka qo'lda kiritilmaydi; format barqaror |
| 7 | **Jadval versiyalanadi** (chorak emas, sanadan amal qiluvchi versiya) | Jadval odatda yil davomida barqaror, lekin o'zgarishi mumkin — nusxa olib tahrirlash, o'tmish tegilmaydi |
| 8 | **O'quvchi-guruh ro'yxatisiz ham ishga tushadi** | Ro'yxat hali yo'q (foydalanuvchi keyin kiritadi): guruhlar bo'sh yaratiladi, jadval to'liq ishlaydi, faqat daraja-guruh davomati ro'yxat kiritilgach yoqiladi |

---

## 1. Ma'lumot modeli

```
Qongiroq Jadvali (2 ta: kichik / katta sinflar)
   └─ qatorlar: № | 09:00–09:40 | tanaffusmi
                                   │
Student Group (ERPNext, uch turda) │        Dars Bloki
   ├─ Sinf:    "1 A(full)" …        │           └─ a'zo sinflar + guruhlar
   ├─ Daraja:  "MATH High 8-9" …    │
   └─ Tanlov:  "CHOICE Physics 9-11"│
                   │                │
                   ▼                ▼
            Jadval Yozuvi  (haftalik shablon: kun × dars × guruh → fan + o'qituvchi)
                   │  generatsiya (sana oralig'i, bayramlarsiz)
                   ▼
            Course Schedule (ERPNext, sanali) ──► Student Attendance (davomat)
                   │
                   ▼
            Jadval Ozgarishi (o'rinbosar / bekor / vaqt-xona almashtirish)

O'quv Reja (sinf × fan → haftasiga N soat)  ──► nazorat: "qo'yilgan vs kerak"
```

### 1.1 `Qongiroq Jadvali` + `Qongiroq Qatori` (child)
Maktabda **ikki variant** (Excel tasdiqladi): `1A–5A` va `5B–11B` — faqat 5-dars va tushlik farq qiladi.

- Bosh: `nomi`, `amal_qiladi` (qaysi sinflarga — child jadval yoki pattern), `faol`
- Qator: `dars_raqami` (1–10), `boshlanish`, `tugash`, `turi` (Dars / Tushlik / Poldnik)

| | 1A–5A | 5B–11B |
|---|---|---|
| 1–4 darslar | 09:00–11:55 (bir xil) | bir xil |
| **5-dars** | **12:45–13:25** | **12:00–12:40** |
| **Tushlik** | **12:00–12:40** | **12:45–13:25** |
| 6–8 | 13:30–15:40 | bir xil |
| Poldnik | 15:45–16:05 | bir xil |
| 9–10 | 16:10–17:35 | bir xil |

### 1.2 `Student Group` (mavjud doctype + custom fieldlar)
Uch turda ishlatiladi — `group_based_on` bilan ajratiladi:

| Tur | `group_based_on` | Misol | Nechta |
|---|---|---|---|
| **Sinf** | Batch | `1 A(full)`, `11 B(hybrid)` | 21 (bor) |
| **Daraja guruhi** | Course | `MATH High 8-9`, `ENGLISH Low 6-7` | ~25 (yaratiladi) |
| **Tanlov guruhi** | Activity | `CHOICE Physics 9-11`, `IT Python 7-8` | ~15 (yaratiladi) |

Qo'shiladigan custom fieldlar:
- `custom_guruh_turi` (Select: Sinf / Daraja / Tanlov / Qo'shimcha)
- `custom_daraja` (Select: High / Middle / Low / — )
- `custom_azo_sinflar` (child: qaysi sinflardan yig'ilgan — `8A, 8B, 9A, 9B`)
- `custom_blok` (Link: Dars Bloki)

> **O'quvchi a'zoligi keyin kiritiladi.** Guruh bo'sh bo'lsa ham jadval ishlaydi; `Student Group Student` jadvaliga ro'yxat tushgach davomat avtomatik yoqiladi. Hisobot: "a'zosi yo'q guruhlar: N ta".

### 1.3 `Dars Bloki`
Bir vaqtda birga o'tiladigan sinflar to'plami va uning ichidagi guruhlar.

- `nomi` (`MATH 8-9`), `fan`, `a'zo sinflar` (8A, 8B, 9A, 9B), `guruhlar` (High/Middle/Low Student Group'lari)
- Jadvalga qo'yilganda **bitta amalda** barcha guruhlarga dars yaratiladi; konflikt ham blok darajasida tekshiriladi

Excel'dan aniqlangan bloklar: `ENGLISH 8-9`, `ENGLISH 10-11`, `MATH 8-9`, `MATH 10-11`, `MATH 6-7`, `ENGLISH 6-7`, `MATH 5`, `ENGLISH 5`, `ENGLISH 3`, `ENGLISH 4`, `IT 5-6`, `IT 7-8`, `IT 9`, `IT 10-11`, `CHOICE 9-11`, `EXTRA 5-6`.

### 1.4 `Jadval Versiyasi` + `Jadval Yozuvi` (haftalik shablon)

**Versiya (tasdiqlangan qaror, 2026-10-08):** jadval chorakka bog'lanmaydi — u odatda yil davomida barqaror turadi, lekin **ehtiyoj tug'ilsa o'rtada o'zgarishi mumkin**. Shuning uchun chorak (Academic Term) majburiy emas, o'rniga **sanadan amal qiluvchi versiya**:

`Jadval Versiyasi`: `nomi` (masalan "2026-2027 asosiy", "2026-2027 — yanvardan"), `academic_year`, `amal_boshlanishi` (sana), `amal_tugashi` (bo'sh = muddatsiz), `holat` (Qoralama / Faol / Arxiv), `izoh` (nima o'zgardi).

Qoidalar:
- Bir vaqtda **faqat bitta Faol versiya** (sana oralig'i kesishmaydi — validatsiya)
- Yangi versiya **mavjudidan nusxa olib** yaratiladi ("Nusxalash" tugmasi) — noldan tuzish shart emas, faqat o'zgargan joyi tahrirlanadi
- Qoralama holatida ishlanadi, konflikt tekshiruvi ishlaydi, lekin **Course Schedule generatsiya qilinmaydi**
- Faol qilinganda: `amal_boshlanishi` dan keyingi darslar qayta generatsiya qilinadi; **o'tgan sanalar va davomat olingan darslar tegilmaydi**
- Eski versiya avtomatik Arxivga o'tadi (tarix saqlanadi: "1-sentabrdan 15-yanvargacha shunday edi")

`Jadval Yozuvi`: `versiya` (Link), `kun` (1–6), `dars_raqami`, `guruh` (Student Group), `fan` (Course), `o'qituvchi` (Instructor), `xona` (ixtiyoriy), `blok` (ixtiyoriy).

**Validatsiya (hard cheklovlar):**
1. Bitta guruh bir vaqtda ikki darsda bo'lmaydi
2. Bitta o'qituvchi bir vaqtda ikki joyda bo'lmaydi (blok ichidagi turli guruhlar — istisno emas, chunki ular turli o'qituvchida)
3. Bitta sinf bir vaqtda ikki blokda bo'lmaydi (sinf → guruhlari orqali tekshiriladi)
4. Xona berilgan bo'lsa — xona bandligi

### 1.5 `Course Schedule` (ERPNext, o'zgartirilmaydi)
Faol versiya shablonidan sana oralig'ida generatsiya qilinadi (versiyaning amal qilish oynasi ichida): dam olish kunlari va bayramlar chiqariladi. Davomat shunga bog'lanadi. Qayta generatsiya **idempotent** (mavjud yozuv ustiga yozmaydi, o'zgarganini yangilaydi).

### 1.6 `Jadval Ozgarishi` (o'rinbosarlik)
`sana`, `dars` (Course Schedule), `tur` (O'rinbosar / Bekor / Xona o'zgarishi / Vaqt o'zgarishi), `yangi_o'qituvchi`, `sabab`, `kim_kiritdi`.
Asl jadval **o'zgarmaydi** — ustiga yoziladi; o'quvchi/o'qituvchi ekranida "bugungi o'zgarishlar" alohida ko'rinadi.

### 1.7 `Oquv Reja` (curriculum) + `Oquv Reja Qatori`
`sinf` (yoki sinf darajasi) × `fan` → `haftalik_soat`. Jadval tuzilganda solishtiriladi:
«7A — MATH: kerak 8, qo'yilgan 8 ✓ · RUS: kerak 3, qo'yilgan 2 ✗».
Boshlang'ich ma'lumot **mavjud jadvaldan teskari hisoblab** to'ldiriladi (har sinf 50 soat — tayyor fakt).

### 1.8 `Instructor` (ERPNext) — Employee'dan generatsiya
24 ta o'qituvchi mavjud Employee bilan bog'lanadi (transliteratsiya lug'ati bilan), 7 tasi yangi, 5 tasi "vakant/rol" (AI VACANT, CHESS/MUSIC VAKANT, TUTOR, PERSONAL DEVELOPMENT) — `custom_vakant` belgisi bilan.

---

## 2. Ekranlar

### 2.1 `/app/dars-jadvali` — zavuch (asosiy ish stoli)
- **To'r:** qatorlar = 10 dars, ustunlar = 20 sinf (yoki tanlangan sinflar); kun tanlovi yuqorida (Du–Ju tab)
- Yacheykada: fan + o'qituvchi (daraja darsida — guruhlar ro'yxati), fan rangi barqaror
- **Konflikt indikatori** real vaqtda: qizil ramka + sabab ("Matyakubov L. shu vaqtda MATH 10-11 da")
- Yon panel: **o'quv reja hisoblagichi** (qolgan soatlar), **o'qituvchi yuklamasi** (haftalik jami, 40+ sariq)
- Amallar: yacheykani tahrirlash, blokni ko'chirish, nusxalash (kunni boshqa kunga), "Course Schedule generatsiya qilish"
- Filtrlar: sinf, o'qituvchi, fan, blok

### 2.2 `/app/mening-jadvalim` — o'qituvchi
- **"Bugungi darslarim"**: vaqt, fan, guruh, sinflar — har qatorda **«Davomat olish»** tugmasi (Course Schedule'ga o'tadi)
- Haftalik shaxsiy jadval (skrinshotlardagi PDF ko'rinishiga o'xshash)
- Haftalik yuklama jami; "bugun o'zgarish bor" belgisi

### 2.3 O'quvchi / ota-ona ko'rinishi (2-bosqich)
- Haftalik to'r; telefonda kunlik lenta; o'zgarishlar ajratilgan
- Portalda yoki Telegram bot orqali

### 2.4 Hisobotlar
- O'qituvchi yuklamasi (haftalik soat, norma bilan)
- O'quv reja bajarilishi (sinf × fan: kerak/qo'yilgan)
- O'qituvchisiz (vakant) darslar
- A'zosi kiritilmagan guruhlar
- Xona bandligi (xona yuritila boshlansa)

---

## 3. Import: mavjud Exceldan ko'chirish

`qarzdorlik/setup.py` uslubida idempotent skript: `dars_jadvali/import_excel.py`

**Bosqichlar (har biri alohida, dry-run bilan):**
1. **Fanlar** (33 ta Course) — `MATH`, `ENGLISH`, … + to'liq nomlar (Izoh varag'idan)
2. **Instructor** — 43 yozuv: Employee bilan bog'lash lug'ati, topilmaganlar hisobotga
3. **Qo'ng'iroq jadvali** — 2 variant
4. **Guruhlar va bloklar** — daraja/tanlov guruhlari yacheyka matnidan (`High: Matyakubov L.`), bloklar sinf to'plamidan
5. **Jadval Yozuvi** — 1000 yacheyka → shablon yozuvlari (blok darslari bir marta, guruh bo'yicha)
6. **O'quv reja** — teskari hisob (sinf × fan → haftalik soat)
7. **Tekshiruv hisoboti**: konfliktlar (kutilayotgani 0), o'qituvchi yuklamasi, bog'lanmagan ismlar

---

## 4. Edge-case katalogi

| № | Holat | Yechim |
|---|---|---|
| 1 | **Daraja guruhiga o'quvchilar hali biriktirilmagan** | Guruh bo'sh yaratiladi; jadval to'liq ishlaydi; davomat shu guruhda "ro'yxat yo'q" deb ko'rsatadi; hisobot: a'zosiz guruhlar |
| 2 | **Bir o'quvchi bir nechta guruhda** (sinf + math darajasi + english darajasi + CHOICE) | Normal holat; o'quvchi jadvali — uning hamma guruhlari darslari birlashmasi; **ziddiyat tekshiruvi**: bir vaqtda ikki guruhda bo'lsa — ogohlantirish |
| 3 | **O'quvchi daraja guruhini almashtirdi** (Low→Middle) | Guruh a'zoligi sanasi bilan; o'tmishdagi davomat tegilmaydi |
| 4 | **Vakant o'qituvchi** (AI, Chess, Music) | Dars bor, Instructor "vakant" turida; hisobotda ko'rinadi; o'qituvchi tayinlangach bitta joyda almashtiriladi |
| 5 | **O'qituvchi kasal/ta'tilda** | `Jadval Ozgarishi`: o'rinbosar yoki bekor; asl shablon o'zgarmaydi |
| 6 | **Bayram / dam olish kuni** | Generatsiyada `Holiday List` hisobga olinadi; qo'shimcha ish kuni bo'lsa qo'lda qo'shiladi |
| 7 | **Yil o'rtasida jadval o'zgardi** (ehtimoli bor, lekin kam) | Yangi `Jadval Versiyasi` nusxa olinadi → tahrirlanadi → `amal_boshlanishi` bilan Faol qilinadi; o'tgan darslar va davomat tegilmaydi |
| 8 | **Bitta o'qituvchi turli bloklarda turli daraja** (Karimxonov: 8-9 Middle, 10-11 high) | Normal; konflikt faqat **bir vaqtda** ikki joyda bo'lsa |
| 9 | **Blok ichida guruh soni o'zgardi** (3 daraja → 2) | Blok tahrirlanadi, guruhlar qo'shiladi/o'chiriladi; mavjud darslar saqlanadi |
| 10 | **5-dars ikki xil vaqt** | Guruhning sinfi qaysi qo'ng'iroq jadvaliga tegishli — shundan vaqt olinadi (1A–5A / 5B–11B) |
| 11 | **Hybrid sinflar** | Hozircha full bilan bir xil 50 soat (Excel tasdiqladi); farq chiqsa — guruhga alohida qo'ng'iroq/kunlar biriktiriladi |
| 12 | **Pre school** | Excelda yo'q; jadvalga kiritilmaydi (yoki alohida soddalashtirilgan jadval) |
| 13 | **Shanba** | Hozir yo'q; model 6 kunni qo'llab-quvvatlaydi (kun 1–6), kerak bo'lsa yoqiladi |
| 14 | **O'qituvchi yuklamasi normadan oshgan** (42, 40, 36 soat) | Bloklamaydi — ogohlantiradi; sozlamada norma (masalan 24) va chegara |
| 15 | **Ikki jadval versiyasi** (joriy ishlayapti + yangisi tayyorlanmoqda) | Qoralama versiyada bemalol ishlanadi (konflikt tekshiruvi ishlaydi), Faol qilinmaguncha o'quvchi/o'qituvchi ko'rmaydi |
| 16 | **Course Schedule qayta generatsiya / versiya almashtirish** | Idempotent: mavjud sanali dars o'zgarmagan bo'lsa tegilmaydi; o'zgargan — yangilanadi; olib tashlangan — bekor qilinadi (davomati bo'lsa — ogohlantirish) |
| 17 | **Davomat olingan darsni o'chirish** | Taqiqlanadi; avval davomatni bekor qilish kerak |
| 18 | **Excel qayta import** | manba_hujjat/idempotent kalit (kun+dars+guruh) bo'yicha — dublikat bo'lmaydi |
| 19 | **O'quvchi o'rtada kelib qo'shildi** | Sinf guruhiga qo'shilsa jadvali darhol ko'rinadi; daraja guruhlariga qo'lda biriktiriladi |
| 20 | **Instructor Employee'da yo'q** (7 kishi) | Import hisobotga chiqaradi; Instructor Employee'siz ham yaratiladi (keyin bog'lanadi) |

---

## 5. Bosqichlar

**1-bosqich (yadro, jadval ishlaydi):**
Qo'ng'iroq jadvali · Student Group custom fieldlari · Dars Bloki · Jadval Versiyasi · Jadval Yozuvi (+konflikt validatsiyasi) · Instructor generatsiya · **Excel importer** · Course Schedule generatsiya · `/app/dars-jadvali` (ko'rish + tahrirlash) · `/app/mening-jadvalim`

**2-bosqich (kundalik ish):**
O'rinbosarlik (Jadval Ozgarishi) · davomat tugmasi zanjiri · o'quv reja va nazorat hisobotlari · o'qituvchi yuklamasi paneli

**3-bosqich (tashqi ko'rinish):**
O'quvchi/ota-ona portali yoki Telegram bot · PDF eksport (sinf/o'qituvchi kesimida, hozirgi PDF ko'rinishiday) · o'zgarish bildirishnomalari

---

## 6. Ochiq savollar (bloklamaydi, defaultlar bilan boshlanadi)

1. Daraja/CHOICE guruhlariga o'quvchilar ro'yxati — **keyin kiritiladi** (foydalanuvchi tasdiqladi 2026-10-08); shungacha guruhlar bo'sh
2. `Poziljonova Nigina` ↔ bazadagi `Polvonova Nigina` — bitta odammi?
3. Employee'da yo'q 7 o'qituvchini HR kiritadimi yoki Instructor'da shundayligicha qoldiramizmi?
4. `(full)` / `(hybrid)` farqi (dars soni bir xil)
5. ~~Chorak (Academic Term) kerakmi?~~ **HAL QILINDI (2026-10-08):** chorakka bog'lanmaydi — jadval odatda barqaror, ehtiyoj bo'lsa o'zgaradi → sanadan amal qiluvchi `Jadval Versiyasi` mexanizmi (§1.4). Academic Term ixtiyoriy maydon sifatida qoladi.
6. Pre school jadvalga kiradimi?
