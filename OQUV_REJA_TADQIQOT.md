# O'quv reja + dars audio AI-tahlili — Dunyo tajribasi (TADQIQOT)

> Maqsad: Target International School uchun (1) **o'quv reja** (kurrikulum) kiritiladigan joy —
> har sinf × har fan × har dars uchun, dars jadvaliga ulangan; (2) keyinchalik **dars audiosini
> AI bilan tahlil** qilib, o'tilgan dars rejaga mos kelganini aniqlash. Bu hujjat — arxitektura
> tuzishdan OLDINGI tadqiqot: eng yaxshi dasturlar nima qilgan, bizdan oldingilar nimani ishlatgan,
> bizga qaysi variant tushadi. Qarang: [[target-zenit-dars-jadvali]] (DARS_JADVALI_ARXITEKTURA.md §1.7).

Sana: 2026-10-09. Holat: **faqat tadqiqot** — kod yoki doctype yaratilmadi.

---

## 0. Muammoning ikki qatlami

Foydalanuvchi tavsifi ikki alohida (lekin bog'liq) tizimni o'z ichiga oladi:

1. **O'quv reja (kurrikulum) modeli va kiritish** — o'qituvchi sana oralig'i + sinf(lar) + fanni
   tanlaydi, keyin "add row" bilan mavzular ro'yxatini yozadi (dars 1, dars 2, 3…), har mavzuga
   soat/vaqt/davomiylik. Dars jadvalidan sinf/kun/vaqt/o'qituvchi avtomat keladi. O'qituvchi "bu
   darsni o'tdim" deb tasdiqlaydi (approve).
2. **AI audio tahlili (2-bosqich)** — dars yakunlangach audio yuklanadi → AI transkripsiya qiladi →
   o'quv rejadagi mavzu bilan solishtiradi → "mavzuga mos keldimi, qanchalik foydali, qayerda xato"
   hisobot beradi.

Dunyoda bu ikki qatlam **alohida sanoatlar** sifatida rivojlangan. Quyida har biri bo'yicha yetakchi
yechimlar va bizga mosligi.

---

## 1-QATLAM: O'quv reja / kurrikulum modellashtirish

### 1.1 G'arb modeli — ierarxiya (Map → Scope&Sequence → Unit → Lesson)

Yetakchi platformalar (Toddle, Chalk/Planboard, PowerSchool C&I, OpenCurriculum, Atlas by Faria,
TeacherEase) deyarli bir xil ierarxiyani ishlatadi:

```
Curriculum Map  (fan × sinf darajasi — yillik ko'rinish)
   └── Scope & Sequence / Pacing Guide  (mavzular ketma-ketligi + taqsimlangan vaqt, kalendarda)
         └── Unit  (bob/mavzu bloki — bir necha hafta)
               └── Lesson plan  (bitta dars: maqsad, faoliyat, resurs, baholash)
```

- **Standartga bog'lash (standards alignment):** har dars/mavzu davlat standartiga (G'arbda — Common
  Core / state standards; bizda — **DTS / Davlat ta'lim standarti**) bog'lanadi. Qamrov hisobotlari
  shu bog'lanishdan chiqadi.
- **Pacing guide** = mavzularni o'quv yili bo'ylab taqsimlash (haftaga nechta soat, qachongacha
  tugatish). Kalendar timeline ustida ko'rsatiladi (OpenCurriculum avtomat generatsiya qiladi).
- **Toddle**: Map → Yearly plan → Unit → Daily lesson bitta joyda + "curriculum analytics"
  (alignment, pacing, coverage).

**Bizga tegishli xulosa:** bu ierarxiya kuchli, lekin to'liq (Map+Unit+Standards) bizga hozir
**og'irlik qiladi** — Target'da mavzular hali yo'q, DTS mapping hozir kerak emas. Bizga yengilroq,
dars-darajasidagi reja kerak → bu post-sovet KTP modeliga olib keladi.

### 1.2 Post-sovet modeli — KTP (kalendar-tematik reja) ← ENG MOS

Foydalanuvchi tavsifi aynan **КТП (календарно-тематическое планирование)** formatiga mos:

> КТP — fan ishchi dasturi (рабочая программа) + o'quv reja + kalendar jadval asosida tuziladigan
> jadval: **bo'lim/mavzu nomi, soat soni, dars turi, nazorat turi, dars sanasi**. Bo'limlar →
> darslarga bo'linadi, ketma-ket raqamlanadi, lekin aniq sanaga qattiq bog'lanmaydi (moslashuvchan
> tahrir). ([infourok.ru](https://infourok.ru/metodicheskie-rekomendacii-po-sostavleniyu-kalendarno-tematicheskogo-planirovaniya-ktp-4197055.html))

KTP jadvalidagi standart ustunlar (foydalanuvchi aytganlari bilan deyarli bir xil):

| № dars | Bo'lim / Mavzu | Soat | Sana (reja) | Sana (fakt) | Dars turi | Nazorat | Izoh |
|--------|----------------|------|-------------|-------------|-----------|---------|------|

Foydalanuvchi qo'shimcha so'raganlari: **boshlanish vaqti + necha minut** (dars jadvalidan avtomat),
**sinfdan-sinfgacha oraliq** (bir KTP bir nechta parallel sinfga), **o'qituvchi tasdiqi** (fakt sana).

### 1.3 Mintaqaviy amaliyot — Kundalik / eMaktab (O'zbekiston)

O'zbekiston maktablari **Kundalik.uz (eMaktab)** elektron jurnalini ishlatadi. O'qituvchi tanish
bo'lgan oqim:

- Jurnalda **dars tanlanadi → baho + davomat + uy vazifa + dars mavzusi** kiritiladi.
  ([emaktab.uz](https://emaktab.uz/news/417), [kun.uz](https://kun.uz/10435850))
- Mobil ilova (Kundalik.Teacher) oflayn ham mavzu/uy vazifa matnini o'zgartirishga ruxsat beradi.
- Dashboard'da "qaysi jurnalda mavzu/uy vazifa/baho qolgan" ko'rinadi (bajarilmagan ishlar ro'yxati).

**Bizga tegishli xulosa:** o'qituvchilar allaqachon "darsga mavzu biriktirish" oqimiga o'rganган.
Lekin Kundalik'da KTP **oldindan tuzilmaydi** — mavzu har kuni qo'lda yoziladi. Bizning ustunligimiz:
KTP ni oldindan tuzib qo'yib, dars jadvali orqali avtomat taklif qilish (o'qituvchi faqat tasdiqlaydi).

### 1.4 "Rejalashtirilgan vs o'tilgan" (coverage tracking) — eng muhim qatlam

Bu aynan foydalanuvchi maqsadi: reja bor, nima o'tilgani belgilanadi, farq (gap) ko'rinadi.

| Platforma | Yondashuv |
|-----------|-----------|
| **Skolaro** | Haftalik qamrovni kuzatadi, rejadan **chetlanishni bayroqlaydi**; o'qituvchi har hafta nima o'tilganini yangilaydi. ([skolaro.com](https://www.skolaro.com/lesson-planning-management-system)) |
| **Compass (hicarl.ai)** | **Scheduled = Planned**, **Completed = Taught**; nima o'tildi / nima rejada / nima qoldi ko'rsatadi. ([hicarl.ai](https://hicarl.ai/compass/)) |
| **Planboard (Chalk)** | Standartga bog'langan reja, maqsad→unit→dars bo'ylab **kuzatiladigan qamrov**, **gap hisoboti** (qayerda bo'shliq bor). |
| **PowerSchool C&I** | Reja LMS'ga oqadi, SIS bilan bog'lanadi; darsga standart qo'shiladi. |

**Umumiy naqsh:** har "reja bandi" (lesson/topic) ikki holatda bo'ladi — **Rejada** va **O'tildi**
(sana + o'qituvchi tasdiqi bilan). Farq avtomat hisoblanadi. Bu bizning `Oquv Reja Qatori`ga
"holat (Rejada/O'tildi), fakt_sana, tasdiqlagan o'qituvchi" maydonlarini beradi.

---

## 2-QATLAM: Dars audiosini AI bilan tahlil qilish

Bu yangi va tez rivojlanayotgan soha. Ikki tur mavjud: (A) **nutq-dinamikasi** tahlili (kim ko'p
gapirdi, savollar), (B) **mazmun/mavzu-moslik** tahlili (nima o'tildi, rejaga mos keldimi) —
bizga aynan B kerak, lekin A ham qo'shimcha qiymat beradi.

### 2.1 Sanoat yechimlari (nutq dinamikasi — tur A)

- **TeachFX** — eng mashhur. O'qituvchi mobil ilovada darsni yozadi → avtomat transkripsiya + NLP.
  Hisobot: **o'qituvchi/o'quvchi gapirish vaqti**, kutish vaqti (wait time), ochiq savollar, uzun
  o'quvchi javoblari, akademik lug'at, so'z buluti. Audio-only, qo'shimcha mehnat yo'q.
  ([teachfx.com](https://teachfx.com/), [ariusai.com](https://ariusai.com/products/teachfx/))
- **Edthena, IRIS Connect, Vosaic** — strukturali toifalarda fikr-mulohaza (video + audio);
  Edthena AI ko. ([edthena.com](https://www.edthena.com/teachfx-alternative/))
- **M-Powering Teachers (Stanford, Dora Demszky)** — ijobiy o'qituvchi-o'quvchi muloqotini
  aniqlaydi, **savol sifati** bo'yicha avtomat fikr; Utah'da 224 o'qituvchi bilan RCT.
  ([ed.stanford.edu](https://ed.stanford.edu/news/ai-classroom-lessons-field),
  [scale.stanford.edu](https://scale.stanford.edu/sites/default/files/ai23-875_v2.pdf))

### 2.2 Akademik yechimlar (mazmun/mavzu-moslik — tur B, bizga aynan kerak)

So'nggi 1-2 yilda LLM'lar bilan dars transkriptini **rubrika** bo'yicha baholash kuchli rivojlandi:

- **"Measuring Teaching with LLMs"** (ACL/AIME 2025) — transkriptni ko'p o'lchov bo'yicha baholash;
  **mavzu qamrovi (topic coverage)** alohida "objective scoring agent" bilan baholanadi — ya'ni
  "o'qituvchi aniq mazmunni o'tdimi" degan savolга to'g'ridan-to'g'ri javob.
  ([aclanthology.org](https://aclanthology.org/2025.aimecon-main.40.pdf))
- **LLM-RUBRIC** (ACL 2024) — ko'p o'lchovli, kalibrlangan rubrika baholash.
  ([aclanthology.org](https://aclanthology.org/2024.acl-long.745.pdf))
- **EduPanel** — o'qitish videolarini baholovchi **3-agentli LLM "hakamlar hay'ati"** (ishonchlilik,
  to'ldiruvchilik, inson ishonchini kalibrlash). ([arxiv.org](https://arxiv.org/pdf/2607.18529))
- **ClassMind** (2025) — **ko'p-modalli AI bilan dars kuzatuvi va fikr-mulohaza**ni masshtablash;
  to'liq pipeline: Whisper-Large-v3 + Pyannote diarizatsiya, savollarni Bloom taksonomiyasi bo'yicha
  klassifikatsiya. ([arxiv.org](https://arxiv.org/pdf/2509.18020))
- **CLASS framework** — klassik sinf kuzatuv rubrikasi; LLM'lar unga instansiya qilinmoqda.

**Muhim ogohlantirish:** LLM baholari ↔ inson ekspert baholari o'rtasidagi **moslik (alignment)**
hal qiluvchi muammo — avtomat baholashни ekspert bilan **kalibrlash** shart (aks holda noto'g'ri
"xato qildi" degan xulosa chiqishi mumkin). Shuning uchun AI = **yordamchi signal**, oxirgi qaror
zavuch/metodistда qolishi kerak.

### 2.3 Texnik pipeline (audio → matn → tahlil)

```
Audio (dars yozuvi, telefon/diktofon)
   │  ffmpeg 16kHz mono
   ▼
Transkripsiya (ASR)
   • Whisper large-v3 — Rus WER ~5.7% (FLEURS); O'zbek — kam-resursли, aniqlik pastroq
   • Variant: OpenAI API whisper-1 $0.36/soat yoki gpt-4o-mini-transcribe $0.18/soat
   • Self-host: RTX 3090 (~$700) ~2000 soatdan keyin o'zini oqlaydi (keyin ~bepul)
   ▼
Diarizatsiya (kim gapirdi) — Whisper o'zi QILMAYDI
   • pyannote.audio / WhisperX — o'qituvchi vs o'quvchi ajratish (DER metrikasi)
   ▼
LLM tahlil (Claude/GPT API orqali)
   • Kirish: transkript + o'quv rejadagi mavzu matni + rubrika
   • Chiqish: (1) mavzu-moslik % (rejadagi mavzu o'tildimi), (2) qamrov (reja bandlari bajarildimi),
     (3) sifat (tushuntirish, savol, misollar), (4) xato/bo'shliqlar, (5) nutq dinamikasi (ixtiyoriy)
```

Manbalar: [learnopencv ASR+diarization](https://learnopencv.com/automatic-speech-recognition/),
[AssemblyAI Whisper diarization](https://www.assemblyai.com/blog/whisper-speaker-diarization),
[Whisper API narxi](https://diyai.io/ai-tools/speech-to-text/openai-whisper-api-pricing-2026/).

**O'zbek tili muammosi:** Whisper o'zbekni qo'llaydi, lekin rus/inglizchaga nisbatan aniqlik past.
Target'da darslar ko'p **ingliz tilida** (English teacher ×8, SAT, Primary Education inglizcha) —
bu Whisper uchun QULAY (ingliz WER past). O'zbek/rus aralash darslar uchun test kerak. Variant:
ElevenLabs STT yoki Gemini Flash transkripsiya bilan solishtirib tanlash.

---

## 3. Bizga nima tushadi (tavsiya)

### 3.1 O'quv reja modeli — KTP + coverage tracking, dars jadvaliga ulangan

Eng mos: **KTP (kalendar-tematik reja)** yengil modeli + "Rejada/O'tildi" qamrov qatlami, mavjud
dars jadvali (jadval_yozuvi / Course Schedule) ustiga qurilgan. G'arbning to'liq Map+Unit+Standards
ierarxiyasi HOZIR kerak emas (mavzular yo'q, DTS mapping keyinroq).

Taklif qilinadigan doctype'lar (arxitektura bosqichida aniqlanadi — bu hali faqat yo'nalish):

- **`Oquv Reja`** (sarlavha): `fan` (Course), `sinf_dan`/`sinf_gacha` yoki `sinflar` (bir nechta
  parallel sinf), `academic_year`, `amal_sana_dan`/`amal_sana_gacha`, `oqituvchi` (ixtiyoriy —
  standart reja o'qituvchisiz ham bo'lishi mumkin), `holat` (Qoralama/Faol).
- **`Oquv Reja Qatori`** (child, KTP qatorlari): `tartib` (dars 1,2,3…), `bolim`, `mavzu`,
  `soat`/`davomiylik_min`, `reja_sana`, `fakt_sana`, `holat` (Rejada/O'tildi), `tasdiqlagan`,
  `audio` (2-bosqich), `ai_natija` (2-bosqich). ← mavzular HOZIR bo'sh, keyin to'ldiriladi.
- **Dars jadvaliga ulanish:** o'qituvchi `/app/mening-jadvalim` da darsга kirganda — sinf/fan/
  kun/vaqt **avtomat** keladi (jadval_yozuvi dan), tegishli KTP qatori taklif qilinadi, o'qituvchi
  "o'tdim" deb tasdiqlaydi → qator "O'tildi" + fakt_sana bo'ladi (Compass "Completed=Taught" naqshi).
- **Nazorat:** "7A — MATH: reja 34 dars, o'tildi 20, qoldi 14; rejadan 2 hafta orqada" (Skolaro/
  Planboard gap-hisoboti naqshi) — bu DARS_JADVALI_ARXITEKTURA.md §1.7 bilan bir xil g'oya.

### 3.2 AI tahlili — 2-bosqich, API orqali

- **Oqim:** dars tugaydi → o'qituvchi audio yuklaydi + "o'tdim" tasdiqlaydi → fon vazifasi:
  ASR (Whisper API) → diarizatsiya → **Claude API** (biz Anthropic ekotizimidamiz) transkript +
  KTP mavzusi + rubrikani solishtiradi → `ai_natija` (mavzu-moslik %, qamrov, sifat, xato) yoziladi.
- **Birinchi versiya eng sodda:** diarizatsiyasiz, faqat transkript + LLM mavzu-moslik ("bu darsda
  rejadagi mavzu o'tildimi, ha/yo'q + dalil"). Keyin nutq dinamikasi (TeachFX uslubi) qo'shiladi.
- **Kalibrlash shart:** dastlab AI xulosasini zavuch qo'lda tekshiradi (AI = signal, hakam emas).
- **Narx:** ~$0.2–0.4/soat ASR + LLM tahlili arzon (transkript ~5-10k token). Pilot uchun API,
  hajm oshsa self-host Whisper.

### 3.3 Nega bu bizga optimal

- Mavjud **dars jadvali** (934 yozuv, 80 guruh, Course Schedule) tayyor poydevor — KTP shunga ulanadi,
  qayta ishlash yo'q. Standart ERPNext yadrosini buzmaymiz (xuddi eduvisit/qarzdorlik formulasi).
- O'qituvchilarга tanish KTP + Kundalik oqimi — qarshilik kam.
- AI qismi API orqali modul sifatida keyin ulanadi — 1-bosqich (reja + tasdiq) AI'siz ham to'liq
  foydali (coverage nazorati o'zi qiymat).

---

## 4. Ochiq savollar (arxitekturadan oldin javob kerak)

1. **KTP manbai:** reja DTS/davlat dasturidan keladimi yoki har o'qituvchi o'zi tuzadimi? (Target
   xususiy, inglizcha — ehtimol o'z dasturi / Cambridge.)
2. **Standart vs shaxsiy:** bir fan-sinf uchun bitta **standart KTP** (barcha parallel sinfga), yoki
   har o'qituvchi o'z KTP'sini tuzadimi? (Foydalanuvchi "matematika standart bo'ladi" dedi → bitta
   standart + o'qituvchi tasdiqlab boradi.)
3. **Mavzu grануlyatsiyasi:** bitta jadval darsi (40 daq) = bitta KTP qatori, yoki bir mavzu bir
   necha darsга cho'ziladimi? (KTP'da soat = bir necha dars bo'lishi mumkin.)
4. **Audio manbai:** telefon/diktofon qo'lda yuklanadimi, yoki sinfda doimiy yozuv qurilmasimi?
   Rozilik (o'quvchi/ota-ona maxfiyligi) — audio yurisdiksiya masalasi.
5. **Til:** darslar asosan ingliz/o'zbek/rus — qaysi ulush? (ASR aniqligi uchun muhim.)
6. **Kim ko'radi:** AI natijasini faqat zavuch/metodist ko'radimi yoki o'qituvchining o'ziga ham
   fikr-mulohaza beriladimi? (M-Powering Teachers: o'qituvchiga o'sish uchun berish samarali.)

---

## 5. Manbalar (asosiylari)

**O'quv reja / coverage:** [Toddle](https://www.toddleapp.com/product/curriculum-planning/),
[OpenCurriculum](https://opencurriculum.org/), [Chalk/Planboard](https://www.chalk.com/schools/),
[PowerSchool C&I](https://www.powerschool.com/solutions/personalized-learning/curriculum-and-instruction/),
[Skolaro](https://www.skolaro.com/lesson-planning-management-system),
[Compass](https://hicarl.ai/compass/),
[КТП metodika](https://infourok.ru/metodicheskie-rekomendacii-po-sostavleniyu-kalendarno-tematicheskogo-planirovaniya-ktp-4197055.html),
[Kundalik/eMaktab](https://emaktab.uz/news/417).

**AI dars tahlili:** [TeachFX](https://teachfx.com/),
[Edthena](https://www.edthena.com/teachfx-alternative/),
[M-Powering Teachers (Stanford)](https://ed.stanford.edu/news/ai-classroom-lessons-field),
[Education Next — AI observations](https://www.educationnext.org/next-gen-classroom-observations-powered-by-ai/),
[ClassMind (arXiv 2509.18020)](https://arxiv.org/pdf/2509.18020),
[Measuring Teaching with LLMs (ACL 2025)](https://aclanthology.org/2025.aimecon-main.40.pdf),
[LLM-RUBRIC (ACL 2024)](https://aclanthology.org/2024.acl-long.745.pdf),
[EduPanel (arXiv 2607.18529)](https://arxiv.org/pdf/2607.18529).

**Texnik pipeline:** [ASR+diarization](https://learnopencv.com/automatic-speech-recognition/),
[WhisperX/pyannote](https://www.assemblyai.com/blog/whisper-speaker-diarization),
[Whisper API narxi 2026](https://diyai.io/ai-tools/speech-to-text/openai-whisper-api-pricing-2026/),
[Self-host Whisper](https://www.digitalapplied.com/blog/local-speech-to-text-whisper-self-hosted-transcription-2026).
