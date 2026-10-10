# O'quv reja (KTP) + dars bajarilishi + AI tahlil — Arxitektura

> Tadqiqot: `OQUV_REJA_TADQIQOT.md`. Dars jadvali: `DARS_JADVALI_ARXITEKTURA.md`,
> [[target-zenit-dars-jadvali]]. Formula: standart ERPNext/jadval yadrosini buzmay, ustiga
> yupqa ishchi qatlam (xuddi eduvisit/qarzdorlik).
> Sana: 2026-10-09. Holat: **arxitektura** — hali kod yo'q.

## 0. Foydalanuvchi tasdiqlagan qarorlar

1. **KTP manbai = maktabning o'z dasturi** (DTS yoki Cambridge import emas — ichkarida tuziladi).
2. **Bitta standart KTP** har fan × sinf(daraja) uchun — barcha parallel sinfga (5A, 5B…) umumiy;
   o'qituvchi dars-ba-dars **tasdiqlab** boradi ("matematika standart bo'ladi").
3. **Aralash til** — fanga qarab (ingliz/o'zbek/rus); AI bosqichida ASR tili fandan olinadi.

## 1. Eng muhim dizayn qarori — reja (shablon) ≠ bajarilish (fakt)

Standart KTP bitta, lekin **5A 12-mavzuda, 5B 10-mavzuda** bo'lishi mumkin. Shuning uchun:

- **O'quv Reja** = standart shablon (mavzular ketma-ketligi, soat) — sanasiz, sinfga bog'lanmagan,
  fan × daraja uchun bitta.
- **Dars Bajarilishi** = fakt yozuv — har **(sinf × sana × mavzu)** uchun bitta, o'qituvchi
  tasdiqlaganda yaratiladi. Qamrov (coverage) shu fakt yozuvlardan **har sinf uchun alohida**
  hisoblanadi (Compass "Planned vs Completed", Skolaro/Planboard gap-hisoboti naqshi).

```
O'quv Reja (standart: MATH 5-sinf)        ← bitta, muallif o'qituvchi/metodist tuzadi
   └── O'quv Reja Qatori (№1 … №34: mavzu, soat)   ← shablon, sanasiz
                     │
   dars jadvali (jadval_yozuvi: 5A Du 3-dars) + sana
                     ▼
   Dars Bajarilishi (5A, 2026-09-03, №1 "Natural sonlar", O'tildi, o'qituvchi, [audio])
   Dars Bajarilishi (5B, 2026-09-04, №1 …)          ← har sinf mustaqil boradi
```

## 2. Ma'lumot modeli

### 2.1 `Oquv Reja` (standart KTP sarlavhasi)
| maydon | tur | izoh |
|--------|-----|------|
| `fan` | Link → Course | majburiy |
| `sinf_daraja` | Data/Select | masalan "5-sinf" (yoki `sinf_dan`/`sinf_gacha` oraliq) |
| `academic_year` | Link → Academic Year | |
| `nomi` | Data | avto: "MATH — 5-sinf (2026-2027)" |
| `muallif` | Link → Instructor/User | kim tuzdi |
| `til` | Select | O'zbek/Rus/Ingliz/Aralash — AI uchun ASR tili |
| `holat` | Select | Qoralama / Faol / Arxiv (bir fan-daraja-yilга bitta Faol) |
| `jami_soat` | Int (read-only) | qatorlardan yig'ilади |
| `qatorlar` | Table → Oquv Reja Qatori | |

Bir **fan × daraja × academic_year** uchun bitta Faol reja (validatsiya). Parallel sinflarга
qanday tegishli ekani darajadan kelib chiqadi (Student Group → sinf/daraja).

### 2.2 `Oquv Reja Qatori` (child — KTP qatorlari, shablon)
`tartib` (№ 1,2,3…), `bolim` (bob), `mavzu`, `soat` (necha dars), `davomiylik_min` (ixtiyoriy,
default jadvaldan 40), `dars_turi` (Yangi mavzu/Takror/Nazorat/Amaliy), `tavsif` (ixtiyoriy),
`resurs` (ixtiyoriy). **Mavzular HOZIR bo'sh — keyin to'ldiriladi** (foydalanuvchi: "hozircha
mavzular yo'q"). Qator add-qilib ketaveriladi (foydalanuvchi tavsifi).

### 2.3 `Dars Bajarilishi` (fakt — bitta dars o'tilgani)
| maydon | tur | izoh |
|--------|-----|------|
| `oquv_reja` / `reja_qatori` | Link | qaysi standart + qaysi mavzu |
| `guruh` | Link → Student Group | qaysi sinf (5A…) |
| `sana` | Date | |
| `oqituvchi` | Link → Instructor | jadvaldan avto |
| `jadval_yozuvi` | Link → Jadval Yozuvi | qaysi slot (kun/dars/vaqt) — avto |
| `course_schedule` | Link → Course Schedule | agar generatsiya qilingan bo'lsa (davomat shunga) |
| `boshlanish`/`davomiylik_min` | Time/Int | jadvaldan avto |
| `holat` | Select | O'tildi / Qisman / O'tilmadi |
| `izoh` | Small Text | o'qituvchi izohi |
| `audio` | Attach | **2-bosqich** |
| `ai_holat` | Select | Kutilmoqda/Tahlil qilindi/Xato — **2-bosqich** |
| `ai_moslik` | Percent | mavzu-moslik % — **2-bosqich** |
| `ai_natija` | JSON/Long Text | to'liq AI hisobot — **2-bosqich** |

Noyoblik: (guruh, sana, jadval_yozuvi) — bir slotda bir marta tasdiq.

### 2.4 Mavjud obyektlarga ulanish (yangi doctype EMAS)
- **Course** (fan), **Student Group** (sinf/guruh), **Instructor**, **Jadval Yozuvi**,
  **Course Schedule** — hammasi mavjud (dars jadvali modulidan). O'quv reja faqat ustiga ulanadi.
- Course Schedule bo'lsa — davomat bilan bitta dated-lesson obyektiga bog'lanadi; bo'lmasa
  (guruh+sana+jadval_yozuvi) yetarli (fallback).

## 3. Ekranlar

### 3.1 O'quv reja tuzish — `/app/oquv-reja` (yoki Desk list + form)
- Metodist/o'qituvchi: fan + daraja tanlaydi → qatorlarни add qilib mavzu+soat yozadi (KTP jadvali).
- "Faol" qilinganda nazoratga kiradi. Nusxalash (o'tgan yildan) — keyin.

### 3.2 O'qituvchi — `/app/mening-jadvalim` ichida (mavjud sahifa kengaytiriladi)
- "Bugungi darslarim" har qatorida (jadval_yozuvidan: sinf/fan/vaqt avto):
  - Tizim shu (fan, daraja) uchun **Faol O'quv Reja**ni topadi → shu sinf bo'yicha oxirgi Dars
    Bajarilishiga qarab **keyingi o'tilmagan mavzuni** taklif qiladi.
  - O'qituvchi **"✓ Shu darsni o'tdim"** bosadi (yoki boshqa mavzu tanlaydi / Qisman belgilaydi)
    → `Dars Bajarilishi` yoziladi, holat "O'tildi" + sana.
  - **2-bosqich:** tasdiqdan keyin "🎙 Audio yuklash" → fon tahlili.
- Qator yonida sinf progressi: "5A: 12/34 mavzu · rejadan 1 hafta orqada".

### 3.3 Nazorat — hisobot (zavuch/metodist)
- **Qamrov matritsasi:** sinf × fan → reja/o'tildi/qoldi, rejadan oldinda/orqada (Skolaro/Planboard).
- O'quvchi dashboard'iga ham qo'shilishi mumkin (keyin).

## 4. 2-BOSQICH — AI audio tahlili (modul, Claude API)

Oqim (dars tugagach):
```
O'qituvchi audio yuklaydi (Dars Bajarilishi.audio) + "o'tdim" tasdiqlangan
   ▼ frappe.enqueue (queue='long') — fon vazifasi
ASR: Whisper (API avval; O'quv Reja.til → ASR tili hint) → transkript
   ▼ (ixtiyoriy) pyannote diarizatsiya — o'qituvchi vs o'quvchi
LLM (Claude API): kirish = transkript + reja_qatori.mavzu + rubrika
   ▼
ai_moslik % + ai_natija: (1) mavzu o'tildimi (ha/yo'q + dalil), (2) qamrov,
   (3) sifat (tushuntirish/savol/misol), (4) xato/bo'shliq, (5) nutq dinamikasi (ixtiyoriy)
   ▼ publish_realtime → UI'da ko'rsatiladi
```
- **Eng sodda birinchi versiya:** diarizatsiyasiz, faqat transkript + Claude mavzu-moslik.
- **Kalibrlash:** AI = signal; zavuch tekshiradi (LLM↔inson moslik muammosi — tadqiqot §2.2).
- **Narx:** ~$0.2–0.4/soat ASR + arzon LLM; pilot API, hajm oshsa self-host Whisper.
- **Maxfiylik:** audio rozilik (o'quvchi/ota-ona) — siyosat kerak; audio File sifatida private.

## 5. Bosqichlar

1. **1-bosqich (AI'siz, mustaqil foydali):** Oquv Reja + Oquv Reja Qatori + Dars Bajarilishi
   doctype'lari; `/app/oquv-reja` tuzish; `/app/mening-jadvalim`ga "o'tdim" tasdiq + keyingi mavzu
   taklifi; qamrov hisoboti. **Mavzular bo'sh boshlanadi**, o'qituvchi/metodist to'ldiradi.
2. **2-bosqich (AI):** audio yuklash → Whisper → Claude mavzu-moslik → ai_natija; zavuch ko'rinishi.
3. **3-bosqich:** diarizatsiya + nutq dinamikasi (TeachFX uslubi), o'quvchi/ota-ona ko'rinishi,
   o'qituvchiga shaxsiy o'sish fikri (M-Powering Teachers).

## 6. Ochiq (bloklamaydi, default bilan boshlanadi)
- Bir mavzu bir necha darsга cho'zilsa — `soat`>1; bajarilish har dars uchun alohida yoziladimi yoki
  mavzu tugaganda bir marta? (Default: har dars slot = bitta Dars Bajarilishi, mavzu takrorlanishi mumkin.)
- Daraja ↔ Student Group moslashuvi: "5-sinf" → 5A,5B guruhlari qanday aniqlanadi (nom parse yoki
  custom_azo_sinflar/Batch). (Default: Student Group nomidan daraja ajratish + tekshiruv.)
- Audio manbai (qo'lda yuklash vs sinf qurilmasi) va rozilik siyosati.
