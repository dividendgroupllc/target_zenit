# Dars jadvali — Dunyo standartlari va bizning yo'l (TADQIQOT)

> Maqsad: Target International School uchun maktab jadvali (timetabling) modulini **jahon darajasida**
> qurish. Bu hujjat butun dunyodagi eng kuchli tizimlar, akademik/OR standartlari, solver
> texnologiyalari, barcha aktyor stsenariylari va edge-case'larni jamlaydi — keyin bizning bosqichli
> rejani beradi. Mavjud: [[target-zenit-dars-jadvali]] (DARS_JADVALI_ARXITEKTURA.md — 1-bosqich qurilgan),
> [[target-zenit-oquv-reja]] (OQUV_REJA_ARXITEKTURA.md).
> Sana: 2026-10-10. Holat: TADQIQOT (5 parallel tadqiqot sintezi).

> **Manba eslatmasi:** quyidagilar yetakchi tizimlarning rasmiy hujjatlari va akademik manbalaridan
> jamlangan; URL'lar kanonik, lekin og'ir qaror oldidan tekshirib ko'rish tavsiya etiladi.

---

## 0. Uch paradigma (avval shuni tushunish shart)

| Paradigma | Atom birligi | Kim ishlatadi | Bizga |
|---|---|---|---|
| **Yevropa — sinf asosidagi** | *Dars* = sinf(lar)×o'qituvchi(lar)×fan×xona, N soat/hafta | Untis, aSc, EDT, FET | ✅ **ASOSIY model** (K-11, sobit sinflar) |
| **AQSh — master-schedule + student sectioning** | *Seksiya*; o'quvchi "course request" beradi, solver har o'quvchini seksiyaga joylaydi | PowerSchool, Infinite Campus | Faqat **yuqori sinf tanlov fanlari** uchun qisman |
| **Universitet — distribution constraints** | Boy cheklov tili + sectioning | UniTime | Faqat **cheklov lug'ati** namuna |

**Xulosa:** Yevropa (sinf asosidagi) = yadromiz; AQSh sectioning = yuqori sinf electivlariga; UniTime cheklov tili = dizayn etaloni.

---

## 1. Ma'lumot modeli — XHSTT + tijorat tizimlari

### 1.1 XHSTT — xalqaro de-fakto standart (ITC 2011 formati)
Maktab jadvalining standart XML modeli (University of Twente / J. Kingston; 11+ davlat, ~50 instance).
Tamoyil: **sxema minimal, butun mantiq cheklovlarda**. To'rt bo'lim:

1. **Times** — vaqt slotlari (Time, TimeGroup, Day, Week).
2. **Resources** — ResourceType (Teacher/Room/Class/Student), Resource, ResourceGroup.
3. **Events** (darslar) — Event (duration + oldindan berilgan resurslar + to'ldirilishi kerak Role'lar), Course, EventGroup; duration>1 **split** bo'ladi.
4. **Constraints** — har biri `Required` (hard/soft), `Weight`, `CostFunction` (Sum/Linear/Quadratic). Natija = **(infeasibility, objective)** jufti.

### 1.2 Tijorat tizimlari modeli (muhim obyektlar)
- **Dars (Lesson/Unterricht/Cours)** = {sinf(lar)}+{o'qituvchi(lar)}+fan+xona+soat/hafta + bayroqlar (double, blok, **coupling/alignment**).
- **Coupling (Untis) / Alignement (EDT) / Option block (UK)** — parallel guruhlar (daraja/elektiv) bir slotda; bizда allaqachon bor (46 daraja guruhi, 6 qo'shma).
- **Period/Stunde** — joylangan dars (kun × dars-raqami yacheykasi).
- **Timetable version/scenario** — sanali versiyalar; bizда `Jadval Versiyasi` bor.
- **Substitution (Vertretung)** — asl jadvalga ustiga yoziladigan qatlam (asl o'zgarmaydi).

### 1.3 ERPNext poydevori (bizning substrat)
`Course Schedule` = joylangan dars (davomat shunga bog'langan — SAQLAYMIZ), `Student Group`, `Instructor`,
`Room`, `Course`, `Academic Term/Year`. Yetishmaydigan: grid UI, konflikt aniqlash, cheklov/mavjudlik
qatlami, substitution, ota-ona ko'rinishi — bularni ustiga quramiz (biz qisman qurganmiz).

---

## 2. To'liq cheklov katalogi (XHSTT 16 + FET taksonomiyasi + hard/soft)

Har cheklov **hard** (buzilmaydi) yoki **soft** (og'irlik bilan jarima) — bu **eng muhim dizayn qarori**.

### 2.1 XHSTT 16 ta kanonik cheklov turi
**Joylash:** AssignTime, AssignResource.
**Split/guruhlash:** SplitEvents, DistributeSplitEvents, PreferTimes, PreferResources,
AvoidSplitAssignments, **SpreadEvents** (kuniga ≤1 fan), **LinkEvents** (parallel — bir vaqtda),
**OrderEvents** (A→B, nazariya→amaliyot).
**Resurs:** **AvoidClashes** (ikki joyda bo'lmaslik), **AvoidUnavailableTimes** (bandlik/mavjudlik),
**LimitIdleTimes** (oynalar/gaps), **ClusterBusyTimes** (kam kunga jamlash — part-time), **LimitBusyTimes**
(kuniga min/max dars), **LimitWorkload** (umumiy yuklama).

### 2.2 Kategoriyalar bo'yicha kanonik checklist (bizning model uchun)
- **O'qituvchi:** ikki joyda emas (H) · mavjudlik/part-time (H) · afzal/qochiladigan vaqt (S) ·
  kuniga max dars + max ketma-ket (S) · oynalarni kamaytirish (S) · kam kunga jamlash (S) ·
  umumiy yuklama/kontrakt (H/S) · tushlik kafolati (H/S) · yomon slotlar adolatli taqsimi (S).
- **Sinf/guruh:** ikki joyda emas (H) · elektiv uchun individual o'quvchi konflikti (H) · kunda oyna
  yo'q/minimal (H/S) · kuniga max + muvozanatli (S) · tushlik (H) · fan taqiqlangan slotda emas (S).
- **Xona:** ikki band emas (H) · sig'im ≥ guruh (H imtihon / H/S dars) · tur/jihoz (lab/sport/IT) (H) ·
  mavjudlik (H) · xona barqarorligi (S) · binolar aro yurish vaqti (H/S).
- **Pedagogik:** haftalik soat kvotasi (H) · double/blok ketma-ket + bir xona (H/S) · haftaga yoyish
  ≥N kun (S) · ikki bir xil fan yonma-yon emas (S) · tartib/precedence (H/S) · parallel/band (H) ·
  qiyin fanlar ertalab (S).
- **Institutsional:** sobit/lock darslar (H) · kun/hafta tsikli (H) · har dars to'liq resursли (H) ·
  muvozanat/welfare (S) · infeasible bo'lsa soft fallback (S).

### 2.3 Taksonomiya (akademik)
School TT (sinf⇄o'qituvchi, bizning holat) · PE-CTT (enrolment-driven) · CB-CTT (curriculum-driven) ·
ETT (imtihon — spread) · Teacher assignment (kim nimani o'qitadi — yuqoridagi barchaning kirishi).

---

## 3. Aktyor-ba-aktyor edge-case katalogi (57 holat → guruhlangan)

### A. O'qituvchi (14)
Shaxsiy jadval (web+mobil) · **part-time/mavjudlik grid** (yashil=afzal, qizil=blok) · max soat kun/hafta ·
max ketma-ket · **oynalar/gaps** · **co-teaching** (2 o'qituvchi 1 sinf, atom karta) · **qo'shma sinf**
(1 o'qituvchi 9A+9B) · sinf rahbari + navbatchilik · **ishdan ketish→o'rinbosarlik** · standby/reserve ·
afzal/home xona · **fan malakasi matritsasi** · **binolar aro yurish vaqti** (0/1 slot + max transfer) ·
peripatetic/shared (hafta A/B).

### B. O'quvchi/sinf (12)
**Daraja setlari bir slotda** (High/Middle/Low parallel) · **elektiv bloklari** (A/B/C/D, o'quvchi tanlaydi) ·
**bir o'quvchi ko'p guruhda** (haqiqiy konflikt=individual o'quvchi) · **divisions** (sinf yarmi til/texnologiya) ·
qo'shma sinf · multigrade/composite · o'quvchi kunida oyna yo'q · tushlik (ikki navbat — canteen) ·
lab/sport/IT maxsus xona · yosh vs katta kuniga max · fan haftaga yoyilishi · fan sobit slotda (har kuni P1).

### C. Zavuch / akademik koordinator (10) — ENG MUHIM
**Versiya/qoralama/rollback** (PowerScheduler "scenarios") · what-if taqqoslash · **kunlik o'rinbosarlik**
(kim yopadi — Arbor Cover Dashboard, Free Staff Finder, filtrlar: bir fan→fakultet→bo'sh→PPA) ·
**adolat/cover limiti** (Untis counter; longitudinal) · **navbatchilik rosteri** (tanaffus/tushlik/darvoza) ·
xona konflikti aniqlash · **yuklama muvozanati + qamrov nazorati** · **o'rta-yil o'zgarishi o'tganlarga
tegmaydi** (effective-dated, tarix saqlanadi) · **jadvalni to'xtatish** (sayohat/imtihon/study leave) ·
o'zgarish so'rovini tasdiqlash (audit).

### D. Zavuch↔o'qituvchi (4)
Kim nimani o'qitadi (curriculum-led staffing + malaka matritsasi) · bandlikда qayta biriktirish + **xabar**
(push) · **"yetarli o'qituvchi bormi?"** (kerakli soat vs mavjud malaka+soat) · **bo'sh xodim qidirish**
(Free Staff Finder: "payshanba P4 bo'sh + fransuz biladigan kim?").

### E. Institutsional (15)
**Ikki xil qo'ng'iroq jadvali** (kichik/katta — bizда bor) · ba'zi kunlar farqli qo'ng'iroq · yarim kun/qisqa kun ·
**imtihon davri** normal jadvalni bosadi · bayramlar/kalendar (A/B tsikl desync bo'lmasin) · split-site/multi-campus ·
**double/triple** (ketma-ket + bir xona + tanaffusdan oshmaydi) · **blok (A/B day, 4×4)** · n-kunlik rotatsiya ·
ikki haftalik (Week A/B) · assembly/umumiy sobit hodisa · fan sobit haftakunga (suzish seshanba) ·
"birinchi/oxirgi dars emas" + yoyish · off-timetable/enrichment kun · **infeasibility hisoboti** (NEGA joylanmadi).

> To'liq 57 holat (scenario→nega qiyin→eng yaxshi tizim qanday hal qiladi) subagent hisobotida saqlanadi.

---

## 4. Generatsiya / solver yondashuvi

### 4.1 Texnologiyalar
| Engine | Til | Litsenziya | Baho |
|---|---|---|---|
| **Google OR-Tools CP-SAT** | **pure Python** | Apache-2.0, JVM yo'q | ✅ **Frappe uchun eng mos**; timetablingда MIP'dan ustun |
| Timefold (OptaPlanner fork) | Python API + **JVM** | Apache-2.0 (Enterprise pullik) | Kuchli (incremental, @PlanningPin), lekin JDK 17+ har serverда |
| FET | C++ desktop | GPL | Algoritm namunasi (recursive swapping); embed qilib bo'lmaydi |
| UniTime cpsolver | Java | Open | **Minimal-perturbation** + "feasible partial + nega joylanmadi" falsafasi |

### 4.2 Eng muhim haqiqat
**To'liq avto-solver YOLG'IZ — noto'g'ri birinchi mahsulot.** Barcha yetuk tizimlar **gibrid**:
avto + drag-drop + jonli konflikt + "qolgan soatlar" hisoblagich + **pin/lock**. Maktablar qora quti'ga
ishonmaydi va doim qo'lda tuzatish kerak. **"Feasible partial + nega joylanmadi"** (UniTime) = to'g'ri UX.

### 4.3 Tavsiya (~20 sinf / 50 o'qituvchi / 940 dars)
**Engine: OR-Tools CP-SAT, Frappe fon vazifasi (RQ), bosqichli manual→assisted→auto.**
- **Pin** = o'tilgan/lock darslar hech o'zgarmaydi (CP-SAT'da o'zgaruvchini fix qilish).
- **Feasibility pre-check** (arzon): har o'qituvchi kerakli dars ≤ bo'sh slot? har sinf ≤ hafta sloti?
  — solver'siz "o'qituvchi yetmaydi" ni darhol ko'rsatadi (Hall sharti uslubida).

---

## 5. O'quv reja ↔ dars ↔ bajarilish ↔ AI (dunyo modeli)

### 5.1 KTP (kalendar-tematik reja) — biz tanlagan model (to'g'ri)
G'arb: Curriculum Map→Unit→Lesson + standartlar + pacing (Atlas/Toddle/Chalk-Planboard/PowerSchool).
Post-sovet **KTP**: ФГОС→ishchi dastur→KTP (№ dars, bo'lim→mavzu, soat, dars turi, nazorat, **plan sana +
fakt sana bir qatorda**, korrektirovka). **Kundalik/eMaktab**: KTP import → jurnalда mavzu plandan keladi.
Biz aynan shu modeldamiz (Oquv Reja + Oquv Reja Qatori + Dars Bajarilishi).

### 5.2 Eng muhim 3 qaror (biznikiga mos)
1. **Plan = shablon; "o'tildi" holati HAR (plan-mavzu × sinf) da** — parallel sinflar mustaqil boradi
   (hicarl Compass: 8 sinf 8 progress bar; biz: Dars Bajarilishi per guruh). ✅ biz shunday qildik.
2. **Jurnal qatori = o'tildi yozuvi** (post-sovet): mavzu plandan, dars period'iga bog'langan — UK MIS'да
   zaif, bizда kuchli. ✅
3. **AI = maslahatchi, ustiga qatlam**: mavzu-moslik *tekshiruvi* ishonchli; sifat *baho* kalibrlangan +
   inson nazoratida bo'lishi shart (LLM↔inson moslik past — Wang & Demszky 2023).

### 5.3 AI pipeline + til
Audio → **ASR (Uzbek/Rus uchun fine-tuned Whisper, code-switch)** → diarizatsiya → LLM:
(a) **mavzu-moslik** (har plan-mavzu: covered/partial/not-evident + transkript dalil — grounded, baho emas),
(b) discourse (talk-time, savol, wait-time, uptake — TeachFX/M-Powering), (c) rubrika (LLM-RUBRIC kalibrlangan,
"strengths/growth/next steps" — ClassMind). **O'zbek past-resurs**: WER yuqori, fine-tune shart.
**Maxfiylik:** o'qituvchi audio egasi; zavuch qamrov+agregat ko'radi, xom audio rozilik bilan.

---

## 6. Eng qimmatli imkoniyatlar (olish uchun, qiymat bo'yicha)

1. **Ishdan ketish→o'rinbosarlik→adolatli cover→e'lon** pipeline + ranjlangan kandidat + fairness counter (**Untis** — tengi yo'q).
2. **"Lesson/Requirement" obyekti ≠ "Period"; + Coupling** parallel/elektiv uchun (bizда qisman bor).
3. **Cheklov qatlami og'irlik bilan** (FET kengligi + UniTime 7-darajali afzallik).
4. **O'qituvchi mavjudlik grid** (afzal/qoch/blok) — solver va qo'lga.
5. **Jonli konflikt + bo'sh/band highlight** drag-drop paytida + NEGA blok.
6. **Assisted avto + o'qib bo'ladigan infeasibility** ("X ning seshanbasini bo'shatsang sig'adi" — aSc).
7. **Ota-ona/o'quvchi/o'qituvchi app** kunlik lenta + jonli o'zgarish overlay + push (Pronote/WebUntis).
8. **Period-as-hub**: davomat+uy vazifa+mavzu+baho period'ga ulanadi (ERPNext Course Schedule).
9. **Cover yuklama muvozanati/budjet** (UK MIS).
10. **Student-request→build→sectioning** (yuqori sinf elektiv — PowerSchool/Edval).
11. **Minimal-perturbation re-solve** (UniTime — bitta o'zgarishda hammani qayta tuzmaslik).
12. **Hafta A/B + versiyalangan jadval** (sanali amal; biz versiyada bor).

---

## 7. Bizning holat vs dunyo (gap-analiz)

| Imkoniyat | Bizда |
|---|---|
| Sinf asosidagi model, parallel darajalar, qo'shma sinf, Student Group | ✅ bor |
| Jadval versiyasi (sanali) | ✅ bor |
| Konflikt validatsiyasi (guruh/o'qituvchi/sinf/xona) | ✅ bor (lekin auto-fix yo'q) |
| Excel import | ✅ bor (ataylab solver o'rniga) |
| O'quv reja (KTP) + per-sinf bajarilish + "o'tdim" dialog | ✅ 1-bosqich qurildi |
| **O'qituvchi mavjudlik grid (kun/dars + limit)** | ❌ (faqat haftalik norma) |
| **O'rinbosarlik/cover (kandidat + fairness)** | ❌ |
| **"Yetarli o'qituvchi?" feasibility pre-check** | ❌ |
| **Konflikt auto-fix + "nega joylanmadi"** | ❌ |
| **Assisted/auto generatsiya (CP-SAT)** | ❌ (hozircha manual+import) |
| **Ota-ona/o'quvchi ko'rinishi + push** | ❌ |
| **Effective-dated o'zgarish (tarix saqlanishi)** | qisman (versiya bor) |
| **Hafta A/B, n-kun rotatsiya** | ❌ (5 kun, bitta hafta) |
| **AI dars tahlili** | ❌ (reja tayyor, 2-bosqich) |

---

## 8. Bizning bosqichli reja (tavsiya)

**Bosqich A — Poydevorni mustahkamlash (jadval yadrosi):**
1. **O'qituvchi mavjudlik + limit** qatlami: Instructor'ga kun/dars grid (afzal/qoch/blok) + max kun/hafta,
   max ketma-ket. (eduvisit'даги teacher-load — biznikiga ko'chiriladi.)
2. **Feasibility pre-check**: "o'qituvchi/xona yetarlimi?" hisoboti (solver'siz, arzon).
3. **Konflikt paneli kengaytmasi**: "nega bo'sh" sabablari + "kim o'qita oladi" kandidatlar (malaka+bo'sh+limit).

**Bosqich B — O'rinbosarlik (eng yuqori operatsion qiymat):**
4. **Jadval O'zgarishi** (substitution) obyekti — asl jadval ustiga: bandlik → ta'sirlangan darslar →
   ranjlangan cover kandidat (bir fan→fakultet→bo'sh→PPA) + **fairness counter** → e'lon/push.

**Bosqich C — Assisted generatsiya:**
5. **Greedy auto-fill** (bo'sh slotlarga, pin'larни hurmat qilib) — FET uslubi, RQ fon vazifasi.
6. (Ixtiyoriy) **CP-SAT to'liq optimizatsiya** — pin+o'tilgan fix, vaqt limiti, accept/reject.

**Bosqich D — Ko'rinish + AI:**
7. **O'quvchi/ota-ona ko'rinishi** (kunlik lenta + o'zgarish overlay + Telegram/push).
8. **AI dars tahlili** (2-bosqich: audio→Whisper→Claude mavzu-moslik+rubrika) — [[target-zenit-oquv-reja]].

**Ko'ndalang qarorlar (boshidan):** har cheklov hard/soft+weight · effective-dated (tarix tegmaydi) ·
Course Schedule = period-hub · (kelajak) hafta A/B o'lchovini modeldaに ko'zda tutish.

---

## 9. Asosiy manbalar
XHSTT/ITC: utwente.nl/.../hstt/tutorial · patatconference.org/patat2014/.../2_15.pdf · unitime.org/itc2007 ·
itc2019.org/format · arxiv.org/html/2201.07525v1 · Pillay survey (Springer 10.1007/s10479-013-1321-8).
Solver: timefold.ai · github.com/google/or-tools/.../scheduling.md · lalescu.ro/liviu/fet · unitime.org.
Tijorat: untis.at + help.untis.at · asctimetables.com · index-education.com (EDT/Pronote) ·
docs.powerschool.com (PowerScheduler) · arbor-education.com · bromcom.com · timetabler.com · edval.education.
O'quv reja/AI: onatlas.com · chalk.com · hicarl.ai/compass · skolaro.com · emaktab.uz · teachfx.com ·
dorademszky.com (M-Powering) · arxiv.org/abs/2509.18020 (ClassMind) · aclanthology.org/2024.acl-long.745
(LLM-RUBRIC) · aclanthology.org/2023.bea-1.53 (Wang & Demszky) · huggingface.co/OvozifyLabs/whisper-small-uz-v1.

---

## 10. Jonli misollar (ishlab turgan demolar — o'rganildi)

Quyidagilar haqiqatan ishlab turgan, ochib ko'rsa bo'ladigan misollar.

### 10.1 ⭐ UniTime jonli demo — eng ilg'or ochiq tizim
**https://demo.unitime.org/** — login: **guest / guest** (faqat o'qish; baza har kecha tiklanadi).
"Woebegon College" haqiqiy test ma'lumotlari bilan. Guest ko'radi:
- **Course timetabling** — darslar vaqt×xona bo'yicha joylangan, distribution constraints (SameRoom/
  SameTime/Precedence/BackToBack/MaxDays... 7-darajali afzallik: Required→Prohibited)
- **Student sectioning** — o'quvchini seksiyaga avtomat joylash (request→build→load)
- **Examination timetabling** — imtihon jadvali (spread)
- **Event management** — xona bron qilish
- Login'siz ochiq havolalar ham bor (Class Schedule, Examination Schedule).
Nega aqlli: **minimal-perturbation** (o'zgarishda kam joy qayta tuziladi), konflikt statistikasi,
"feasible partial + nega joylanmadi" falsafasi. **Bizning cheklov lug'ati va UX uchun etalon.**

### 10.2 Timefold / OptaPlanner — School Timetabling jonli app + kod
Model: **Lesson = planning entity**, ikki variable (room + timeslot). Hard: room/teacher/studentGroup
bir vaqtda ikki joyda emas (har konflikt -1). Soft: afzalliklar. Algoritm: greedy → metaheuristika
(tabu/SA/late-acceptance); 400 dars = 10^1040 qidiruv fazosi (brute-force imkonsiz).
- Prezentatsiya: timefoldai.github.io/timefold-presentations/.../School_Timetabling.html
- Use-case + kod: optaplanner.io/learn/useCases/schoolTimetabling (quickstart manba kodi + video)
- Jonli app: app.timefold.ai
Nega aqlli: real-time score, @PlanningPin (lock), incremental scoring. **Bizning CP-SAT yo'nalishiga yaqin namuna.**

### 10.3 aSc TimeTables — maktablar e'lon qilgan jonli jadvallar
aSc "TimeTables Online → Publish for public viewing" bilan maktab jadvalini web'ga chiqaradi:
generatsiya qilingan to'r + o'qituvchi/sinf/xona ko'rinishlari, ommaga ko'rsatiladigan qismlar tanlanadi.
Nega aqlli: **infeasibility diagnostics** ("X ning seshanbasini bo'shatsang sig'adi"), drag-drop + jonli konflikt.

### 10.4 WebUntis — ommaviy jadvallar (login'siz)
Ko'p maktab WebUntis'da **public timetable** yoqadi — login'siz, maktabning WebUntis sahifasi chap
paneldan ko'riladi (real ishlab turgan production jadval + o'zgarish/o'rinbosarlik overlay + Untis Mobile app).
Help: help.untis.at/.../Public-Timetables. Nega aqlli: **Vertretungsplanung** (o'rinbosarlik) jonli ko'rinadi.

### 10.5 Edval / Tes Timetable — o'quvchi tanlovi optimizatori
tes.com/for-schools/timetable (ilgari Edval) — **student choice**: o'quvchilar fan tanlaydi, tizim
**birinchi tanlov qoniqishini maksimallashtiradi** (option bloklar), demo + portal. Nega aqlli: yuqori
sinf elektiv bloklari uchun sectioning namunasi.

### 10.6 FET — ochiq kodli, yuklab generatsiya qilib ko'rish
lalescu.ro/liviu/fet — bepul (GPL) desktop; namuna fayllar bilan jadval generatsiya qilib, HTML/CSV
chiqishini ko'rish mumkin. Nega foydali: recursive-swapping algoritmi + ~100 cheklov taksonomiyasi (checklist).
