# Qarzdorlik CRM — jahon tajribasi tadqiqoti

**Sana:** 2026-10-05. **Maqsad:** Target Zenit (xususiy maktab) uchun o'quvchilar qarzdorligi bo'yicha ishlash (collections) CRM qurishdan oldin dunyo standartlarini o'rganish. Bu hujjat — faqat tadqiqot/tahlil; arxitektura keyingi bosqichda.

> Eslatma: oldingi `CRM_ARCHITECTURE.md` — **qabul (admissions)** CRM haqida. Bu hujjat — **mavjud o'quvchilarning to'lov qarzdorligi** bilan ishlash haqida. Bular ikki alohida modul.

---

## 1. Bozor manzarasi: maktab "CRM" aslida 3 xil bo'ladi

Dunyoda "maktab CRM" deganda uch xil mahsulot tushuniladi:

1. **Admissions CRM** — yangi o'quvchi jalb qilish voronkasi (OpenApply, Finalsite). Bizda allaqachon qurilgan.
2. **Tuition/Fee Management** — billing, to'lov rejalari, avtomatik eslatmalar (FACTS, Blackbaud Tuition, TUIO, Classter). Bu "pul yig'ish mexanikasi".
3. **Collections/Follow-up workflow** — qarzdor bilan **odam** ishlashi: qo'ng'iroq, status, va'da, komment. G'arb maktab tizimlarida bu qatlam kuchsiz (chunki ularda autopay standart), lekin umumiy **accounts receivable collections** sohasida juda puxta standartlashgan.

Target Zenit talabi = 2-qatlamning hisobot qismi (qarz ro'yxati — bizda GL asosida bor) + **3-qatlamning to'liq workflow'i**. Demak asosiy o'rganish manbai — maktab tizimlari EMAS, balki collections workflow standarti + MDH/Hindiston ta'lim CRM'lari.

## 2. G'arb yetakchilari (AQSh/Yevropa xususiy maktablari)

| Tizim | Kimga | Kuchli tarafi |
|---|---|---|
| **FACTS Tuition Management** | AQSh xususiy/diniy maktablar de-fakto standarti | To'lov rejalari (oylik avtoyechim), muvaffaqiyatsiz to'lovni avto-qayta urinish (retry), overdue bo'lganda avto-eslatma, delinquency hisobotlari, "jiddiy qarzda qo'lda aralashuv trigger nuqtasi" tushunchasi |
| **Blackbaud Tuition** | Yirik maktablar (fundraising bilan birga) | Masshtab, buxgalteriya bilan juftlik |
| **Veracross** | Yirik mustaqil maktablar | Hammasi bitta bazada: SIS + billing + general ledger (oila hisobi va buxgalteriya birga) |
| **TUIO, Classter, Classe365** | Kichik/o'rta maktablar | Arzonroq, invoice + avto-eslatma + onlayn to'lov |

**Asosiy saboqlar:**
- Eslatmalar ikki triggerli: **jadval bo'yicha** (to'lov kuni yaqin) va **overdue holat bo'yicha** (muddat o'tdi).
- Avtomatika birinchi, odam ikkinchi: tizim avval o'zi eslatadi/qayta urinadi; menejer faqat **belgilangan trigger nuqtadan** keyin kirishadi (masalan 2 eslatma + 15 kun o'tdi).
- Eskalatsiya siyosati oldindan yozilgan bo'ladi: eslatma → qattiqroq xat → xizmat cheklash (baho/hujjat berish to'xtatiladi) → shartnoma masalasi.
- Hisobot: outstanding balans ro'yxati, collection rate, aging.

**Kamchiligi bizga nisbatan:** "menejer qo'ng'iroq qilib status qo'yadi" ish stoli ularda deyarli yo'q — bizning bozorda esa aynan shu asosiy jarayon.

## 3. Hindiston modeli — telecalling CRM (Meritto, LeadSquared, ExtraaEdge)

Bizning talabga ish uslubi jihatidan eng yaqin G'arb-tipidagi mahsulotlar:
- **Counsellor assignment** — har bir kontakt aniq bir xodimga biriktiriladi (qoida asosida: manba/sinf/yuklama bo'yicha avto-taqsimlash).
- **Call log + follow-up date** — har qo'ng'iroq yoziladi, natija (disposition) tanlanadi, **keyingi aloqa sanasi majburiy** qo'yiladi.
- **Kunlik ish stoli**: menejer kuniga kirganda "bugun aloqa qilinishi kerak" ro'yxatini ko'radi (o'tkazib yuborilganlar qizil).
- **Rahbar paneli**: har menejer bo'yicha kunlik qo'ng'iroqlar soni, ulanganlar, status siljishi, overdue follow-up'lar real vaqtda.

## 4. MDH modeli — AlfaCRM, Hollihop, МойКласс

Postsovet xususiy maktab/o'quv markazlari standarti; UX jihatdan bizga eng tanish:
- **Qarzdorlar ro'yxati** doim ko'rinib turadi: qizil badge — qarzdorlar soni + jami qarz summasi; bosilsa ro'yxat ochiladi.
- Ro'yxatdan **mass-amal**: shablon bo'yicha SMS/email (qarz summasi avtomatik qo'yiladi), mas'ulni almashtirish, statusni bir bosishda o'zgartirish.
- Har o'quvchida: mas'ul menejer, status, kommentlar lentasi, eslatma-vazifalar.

## 5. Collections (qarz undirish) jahon standarti — asosiy kontseptlar

Bu soha (accounts receivable collections) maktablardan qat'i nazar juda aniq standartlashgan. CRM dizayni shularga tayanishi kerak:

### 5.1 Aging buckets + eskalatsiya zinasi
Qarzlar muddati bo'yicha guruhlanadi: **0–30 / 31–60 / 61–90 / 90+ kun**. Har zinaning o'z ohangi:
- 1–30 kun: yumshoq eslatma ("ehtimol unutgandir" prezumpsiyasi)
- 31–60 kun: qat'iy kuzatuv + telefon qo'ng'irog'i
- 61–90 kun: rahbarga eskalatsiya, oqibatlar aniq aytiladi
- 90+ kun: yakuniy talab, shartnoma choralari

**Muhim fakt:** 90 kundan keyin undirish ehtimoli ~50% ga, 120+ kunda ~25% ga tushadi — tezkor birinchi aloqa eng katta leverage.

### 5.2 Call disposition — ikki o'lchov alohida
Qo'ng'iroq natijasini **aloqa natijasi** va **hisob natijasi**ga ajratish kerak (bir statusga aralashtirmaslik):
- **Aloqa natijasi (contact outcome):** javob yo'q / ovozli pochta / gaplashildi / noto'g'ri raqam / qayta qo'ng'iroq so'radi
- **Hisob natijasi (account outcome):** to'lov va'dasi / nizo-e'tiroz / to'lov qilindi deydi / chegirma-bo'lib to'lash so'radi / ma'lumot so'radi
- Har yozuv **3 savolga** javob berishi shart: nima bo'ldi? hisob holati qanday? keyingi qadam kim tomonidan qachon?

### 5.3 Promise to Pay (PTP) — markaziy obyekt
"Falonchi kuni to'layman dedi" — bu oddiy komment emas, **strukturali yozuv**: summa + sana + kim yozdi. Standart:
- PTP sanasi kelganda tizim avtomatik tekshiradi: to'lov tushdimi? Tushmasa — **PTP buzildi** statusi bilan avtomatik qayta ro'yxatga chiqadi (keyingi odam suhbatni qayta tiklamay davom ettira oladi).
- "Keyinroq gaplashamiz" degan ochiq vazifa taqiqlanadi — har doim aniq sana + mas'ul.
- KPI: **PTP kept rate** (va'dalarning necha % bajarildi) — menejer sifatining asosiy o'lchovi.

### 5.4 Majburiy maydonlar triadasi
Har bir faollik yozuvida: **keyingi harakat + mas'ul + sana**. Bu bo'lmasa ro'yxat "o'lik kommentlar daftari"ga aylanadi.

## 6. Sintez: kanonik status modeli (dunyo standartidan)

Ikki daraja tavsiya etiladi (admissions CRM'dagi Stage+Status tajribasiga mos):

**Hisob holati (avtomatik, puldan kelib chiqadi):** Qarzsiz → Qarzdor (0–30 / 31–60 / 61–90 / 90+) → Qisman to'landi → Yopildi. Buni menejer emas, tizim GL/to'lovdan hisoblaydi.

**Ishlov holati (menejer qo'yadi):**
1. Yangi — hali aloqa qilinmagan
2. Urinilmoqda — dozvon bo'lmadi (urinishlar soni bilan)
3. Gaplashildi — **to'lov va'dasi** (PTP: sana + summa)
4. Gaplashildi — e'tiroz/nizo (sabab bilan)
5. Bo'lib to'lash kelishildi (jadval bilan)
6. PTP buzildi — qayta aloqa kerak
7. Eskalatsiya (rahbarga)
8. Yopildi — to'landi / Yopildi — boshqa sabab (chegirma, ketdi)

Plus har yozuvda: mas'ul menejer, keyingi aloqa sanasi, kommentlar timeline.

## 7. Standart KPI'lar

- **Collection rate** — hisoblangan to'lovning necha % yig'ildi (oy/chorak)
- **DSO / o'rtacha qarz yoshi**
- **PTP kept rate** — va'dalar bajarilish %
- **First contact time** — qarz paydo bo'lgach birinchi aloqagacha kunlar
- Menejer bo'yicha: kunlik qo'ng'iroqlar, ulanish %, yopilgan qarz summasi

## 8. Target Zenit uchun xulosa (arxitektura KEYIN, lekin yo'nalish)

- Qarz ro'yxatining manbasi bizda allaqachon bor (GL asosidagi debitorka — investor dashboardda ishlatilgan mantiq). Qurilishi kerak bo'lgani — **follow-up qatlami**: biriktirish + status + PTP + komment + "bugungi ro'yxat" ish stoli.
- MDH UX (qarzdorlar ro'yxati + badge) + Hindiston telecalling intizomi (majburiy keyingi sana, kunlik ish stoli, rahbar paneli) + collections standarti (PTP obyekt sifatida, aging, ikki o'lchovli disposition) = qurilish formulasi.
- G'arb tizimlaridan olinadigan g'oya: avto-eslatmalar (SMS/Telegram) menejer qo'ng'irog'idan OLDIN ishlasin — menejer vaqti faqat "avtomatika uddalamagan" hisoblar uchun.

## Manbalar

- [Sycamore: Best SIS for Private K-12 2026](https://sycamoreleaf.com/best-sis-us-private-k12-schools-2026/), [Independent school software compared](https://sycamoreleaf.com/best-school-software-independent-k12-schools/)
- [FACTS Tuition Management](https://factsmgt.com/products/financial-management/tuition-management/), [FACTS: Optimising late tuition fees approach](https://factsmgt.com/blog/optimising-schools-approach-late-tuition-fees/)
- [Blackbaud Tuition Management review](https://www.spotsaas.com/blog/blackbaud-tuition-management-review)
- [Classter: School billing guide](https://www.classter.com/blog/edtech/school-billing-and-tuition-management-software-a-complete-guide-for-administrators/), [Classe365 fee management guide](https://www.classe365.com/blog/best-payment-methods-for-collecting-school-and-tuition-fees-with-fee-management-software/)
- [Meritto Education CRM](https://www.meritto.com/education-crm/), [LeadSquared Higher Ed CRM](https://www.leadsquared.com/higher-education-admissions-crm/), [Education CRM comparison](https://www.xale.in/best-education-crm)
- [AlfaCRM o'quv markaz CRM](https://alfacrm.pro/news/useful-info/crm_sistema_dlya_uchebnogo_centra), [МойКласс CRM](https://moyklass.com/crm)
- [ProspectBoss: AR call dispositions](https://prospectboss.com/accounts-receivable-call-dispositions/), [Iris: Promise-to-pay tracking](https://www.irisinsights.ai/blog/promise-to-pay-tracking-software-the-missing-link-that-turns-call-notes-into-recoveries/)
- [HighRadius: Dunning letters](https://www.highradius.com/resources/Blog/dunning-letter-what-it-is-when-to-send-it-and-how-to-write-one/), [Dunning process stages](https://clearreceivables.com/blog/dunning-process-explained), [Aging report guide](https://www.invoicebutler.com/blog/aging-report-guide-accounts-receivable-payable)
- [Convera: Past due tuition recovery](https://convera.com/blog/cross-border-payments/blog-past-due-tuition-recovery-universities/)
