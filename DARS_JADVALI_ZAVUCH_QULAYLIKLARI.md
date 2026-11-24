# Zavuch uchun dars jadvali qulayliklari — jahon tajribasi (TADQIQOT)

> Sana: 2026-11-18. Fokus: **zavuchning ish jarayoni** — jadvalni TUZISH (muharrir UX),
> AVTO-GENERATSIYA oqimi, va KUNLIK TUZATISH (o'rinbosarlik/zamena).
> Oldingi umumiy tadqiqot: `DARS_JADVALI_DUNYO_STANDARTLARI.md` (cheklovlar, model, solver).
> O'rganilgan tizimlar: aSc TimeTables/EduPage, Untis/WebUntis, Prime Timetable, Lantiv,
> TimeTabler (UK), Edval/Compass (AU), FET, UniTime, Arbor/SIMS/Bromcom (UK MIS),
> Pronote/EDT (FR), PowerSchool (US), Ректор, ХроноГраф/1С, НИКА, АВТОР (RU), Kundalik/eMaktab (UZ).

---

## 0. Bosh xulosa

Hamma yetuk tizimlarda zavuch ishi **uch alohida rejimga** bo'lingan, har birining o'z UX'i bor:

1. **Qurish** (yilda 1-2 marta): karta/laganda metaforasi + jonli rang-highlight + almashuv zanjirlari.
2. **Generatsiya** (yordamchi, qora quti emas): test → tahlil → halol progress → relaxation hisoboti.
3. **Kunlik operatsiya** (har kuni ertalab): asl jadval USTIDA delta-qatlam — bandlik → kandidat → e'lon.

Ikki ko'ndalang arxitektura saboqi: (a) **rejalashtirish dvigateli ↔ e'lon qatlami ajratilgan**,
orasida aniq "publish" qadami; (b) kunlik o'zgarishlar **asosiy jadvalga tegmaydi** — tipizatsiya
qilingan delta yozuvlari (o'z hisoblagichi, tarixi, semantikasi bilan).

---

## 1. TUZISH muharriri — de-fakto standart mexanizmlar (deyarli hammada)

1. **Karta + laganda (tray)**: darslar = rangli kartalar; joylanmagan kartalar ko'rinadigan
   lagandada (sinf/o'qituvchi bo'yicha filtr, soni badge bilan; bir xil kartalar yig'ilib 1 karta
   + miqdor). (aSc Control Panel, Prime, TimeTabler Priority List)
2. **Ko'tarilganda rang bo'yash** — eng muhim yadro interaksiya. Karta qo'lga olinishi bilan har
   slot jonli bo'yaladi: aSc **yashil=mumkin, ko'k=savolli, qizil=band, kulrang=mutlaqo mos emas**;
   Untis yashil + qizil/to'q sariq (pedagogik istalmagan); TimeTabler yashil kataklarni **1–5 sifat
   bahosi** bilan darajalaydi, `*1*` = tavsiya etilgan slot.
3. **Lock/pin**: o'ng tugma bilan karta qotiriladi (vizual belgi), generator unga tegmaydi.
   Hammada bor; FET butun qo'lda tahrirni "hammasini lock → keraklisini unlock → qayta generatsiya"
   (selektiv re-solve) orqali quradi. aSc ogohlantiradi: ortiqcha lock jadvalni yechimsiz qiladi.
4. **Konfliktni qattiq to'sish yoki baland ko'rsatish**: aSc boshqa sinf qatoriga tashlashga yo'l
   qo'ymaydi; TimeTabler "totally self-checking"; Prime konflikt kartani **qiyshaytirib** chizadi +
   toolbar'da xato/ogohlantirish hisoblagichi (bosilsa aybdor kataklar yonadi).
5. **Yumshoq ogohlantirish ≠ blok**: aSc'da xonasiz joyga tushgan karta **oq chiziq**, taqiqlangan
   joyga tushgani **qizil chiziq** oladi — "qo'yish-qo'ymaslik sening qaroring". Zavuchga ishonch.
6. **Siqib chiqarish dialogi (bounce-back)**: band slotga tashlasang, siqilgan karta "qo'lingga
   sakraydi" yoki dialog barcha to'qnashgan kartalarni ko'rsatadi: joyla (siqilganlar lagandaga) /
   bekor / aynan bitta kartani qo'lga olib zanjirni qo'lda davom ettir. (aSc, Untis "displace")
7. **Bir nechta sinxron ko'rinish**: master/sinf/o'qituvchi/xona yonma-yon; Prime'da sudralayotgan
   kartaning **soyasi barcha ochiq ko'rinishlarda** ko'rinadi; TimeTabler karta tanlanganda aynan shu
   darsga tegishli sinf+o'qituvchi lentalarini avtomatik ochadi.
8. **Chuqur undo/redo**: aSc 100 amal; Prime 100 holat + History paneli (istalgan holatga sakrash).
9. **Xona avto-biriktirish** tashlash paytida + bo'sh xona yo'q bo'lsa ogohlantirish holati.
10. **Chop etish/e'lon**: har obyekt (sinf/o'qituvchi/xona) uchun alohida chiqish, Excel/MIS eksport,
    Prime'da har obyektga deep-link web e'lon.

## 2. Kuchli, lekin hamma emas ("power" mexanizmlar)

11. **Zanjirli almashuv takliflari ("musiqiy stullar")** — eng yuqori qiymatli xususiyat:
    - **Untis**: 2/3/4 tomonlama almashuv zanjirlari, jadvalda **qizil strelkalar**, har variant
      uchun **Gain ustuni** (vazn sozlamalariga ko'ra ± ball) va **Consequence ustuni** (qoladigan
      eng yomon konflikt). Bir bosishda bajariladi.
    - **TimeTabler FIT**: sig'magan dars atrofida **16 qadamgacha** zanjir qidiradi, bir nechta
      to'liq yechimni ko'rsatib tanlatadi.
    - **UniTime Suggestions**: sinf bosilsa — hech narsani ochiqda qoldirmaydigan to'liq zanjirlar
      ro'yxati; tanlovlar **"what-if savatcha"ga** yig'ilib faqat `Assign`da qo'llanadi;
      `Search Deeper/Longer` tugmalari.
12. **"Nega bu yerga sig'maydi?" tushuntirishlari**: TimeTabler'da imkonsiz davr nuqtasi bosilsa
    sabab hisoboti ochiladi; aSc Test yiqilgan kartani **qo'lingga berib** Verification xato
    ro'yxatini ko'rsatadi; UniTime **conflict-based statistics** (qaysi cheklov necha marta joylashni
    to'sgani jadvali).
13. **Diagnostika hisoboti + bosib navigatsiya**: xato qatori bosilsa aybdor kartalar gridda
    bo'yaladi (aSc Check, Untis Diagnosis — har band o'z **vazni (Wtg)** bilan).
14. **Ko'rinadigan va sozlanadigan cheklov vaznlari**: Untis Weighting dialogi — ayni shkala ham
    optimizatorga, ham swap Gain raqamlariga beradi; Edval'da **rooming/staffing quality score**
    (tahrir narxi raqam bo'lib ko'rinadi).
15. **Nazoratli relaxation**: "hammasini joyla, eng arzon qoidalarni buz, QAYSILARINI buzganingni
    ayt" (aSc automatic relaxation / "Relaxed by importance").

## 3. Nodir marvaridlar (olishga arziydi)

16. **"Bu yerga nima sig'adi?" teskari qidiruv**: bo'sh slotga o'ng tugma → shu joyga qonuniy
    sig'adigan kartalar ro'yxati (aSc).
17. **Mashina tartiblagan navbat**: TimeTabler Priority List — qolgan darslarni **erkinlik
    darajasi** bo'yicha doim qayta saralab "keyingisini QAYSI joylash kerak"ni aytadi + tavsiya slot.
18. **Cheklovlarni to'g'ridan-to'g'ri gridga BO'YASH**: Prime Marker — qizil=taqiq,
    sariq=istalmagan (kun/hafta tolerantligi bilan), ko'k=majburiy; abstrakt forma o'rniga mo'yqalam.
19. **Joylashdan OLDINGI feasibility tahlillari**: Untis **CCC Analysis** (hech qachon parallel
    yurolmaydigan bog'langan darslarning eng uzun zanjiri; zanjir haftalik soati setkadan oshsa —
    matematik imkonsiz, generatsiyadan OLDIN ko'rinadi); TimeTabler Conflict Matrix / Combing Chart /
    Staff Deployment Analysis / Zarraga qoidasi; aSc Advisor.
20. **What-if savat, qoralama, minimal-perturbation**: UniTime MPP (yil o'rtasida qayta yechishda
    e'lon qilingan jadvalga o'zgartirishni minimallash); Lantiv **Planning mode vs Changes mode**
    (asosiy jadval ↔ kunlik o'zgarish ajratilgan).

---

## 4. Avto-generatsiya UX oqimi (aSc etalon + Untis/FET)

Zavuch solver'ga ishonishi uchun qora quti emas, **oshkora jarayon** kerak:

1. **Wizard**: maktab → setka (kun/dars) → fanlar → sinflar (dars shartnomalari) → o'qituvchilar →
   xonalar → tekshir-va-generatsiya.
2. **Generatsiyadan oldin Test**: butun fayl yoki **bitta qator** (sinf/o'qituvchi/xona alohida,
   izolyatsiyada joylab ko'rish) — haddan ortiq cheklangan qatorni uzun run'dan oldin tutadi.
3. **"Analyze by generation"**: 1 daqiqalik chegaralangan run, so'ng har karta bo'yaladi:
   **qizil = ko'p konflikt chiqargan, oq = muammosiz**. Yordam ataylab o'rgatadi: qizil karta ko'pincha
   muammoning o'zi emas, cheklovlar *kombinatsiyasi* — bu yumshatish kerak joyning issiqlik xaritasi.
4. **Halol progress**: joylanmagan hisoblagich ("1/809"), soniyasiga tekshirilgan jadval soni,
   har karta uchun **"lifebar"** (qayta-qayta yiqilsa qizaradi), yashil **eng yaxshi natija
   watermark**, ko'rinadigan backtracking. CTRL+Cancel — solver tiqilgan kartani qo'lingga beradi.
5. **Relaxation + iqror ro'yxati**: yumshoq cheklovlarni buzib tugatadi, keyin **aynan qaysilari
   buzilganini** ro'yxatlaydi — qabul qilish yoki qattiqlashtirish zavuch qarori. FET hiylasi:
   shubhali cheklovni 100% dan pastga tushirib solver'ga imkonsizlikni *isbotlatish*.
6. **Lock-va-qayta-generatsiya**: pin'lar regeneratsiyadan omon qoladi; "bitta yomon joyga
   qotirilgan dars butun jadvalni buzishi mumkin" ogohlantirishi; pin o'rniga "ruxsat etilgan
   pozitsiyalar" tavsiyasi.
7. **Variant taqqoslash**: "oxirgi saqlangan bilan solishtir" / "boshqa fayl bilan solishtir" —
   farq qilgan kartalar yonadi; har yaxshilash urinishidan oldin save-as odati. Untis Strategy A–E
   bir nechta **ballangan variant** chiqaradi.
8. **Sifat bahosi raqamda**: vaznlangan "bad-points" (o'qituvchi oynalari, istaklar buzilishi,
   xona ko'chishlari...) — tahrirdan keyin ham qayta hisoblanadi.

---

## 5. Post-sovet an'anasi (zavuchimizga eng tanish model)

### 5.1 Ректор'ning 4 bosqichli ish modeli — CIS zavuchning tayyor mental xaritasi
**Списки → Нагрузки → Расписание → Замены** (ma'lumotlar → yuklama/tarifikatsiya → setka → zamena).
Modul navigatsiyasini aynan shunday qurish kerak. Yuklama bosqichi **tarifikatsiya** (oylikka
tegishli soatlar, zamena jurnali bilan) bilan bitta manbadan chiqadi.

### 5.2 SanPiN / Sivkov qiyinchilik shkalasi — o'ziga xos post-sovet qatlami
- Har fanga sinf-diapazon bo'yicha **qiyinchilik balli** (5–11: Matematika 11, Chet tili 10,
  Fizika/Kimyo 9–13, ... Ashula 1).
- Qoidalar: kunlik ball yig'indisi **seshanba–chorshanbada cho'qqi**, dushanba/juma eng past
  ("tuya egri chizig'i"); og'ir fanlar 2–4-darslarda; ikki eng og'ir fan ketma-ket emas;
  **sinfga qarab kuniga maks dars** (1-sinf: 4; 2–4: 5; 5–6: 6; 7–11: 7) + haftalik soat limiti.
- Amalga oshirish: generatsiya cheklovi + **kunlik ball gistogrammasi** (ideal egri chiziq ustiga
  qo'yilgan) + bir bosishda **"muvofiqlik spravkasi"** (tekshiruvchilar so'raydigan hujjat:
  buzilishlar ro'yxati + norma havolalari). Shkala jadvali tahrirlanadigan bo'lsin (O'zR SanPiN).
### 5.3 Boshqa qimmatli CIS mexanizmlari
- **Методический день** va o'qituvchi istaklari — birinchi darajali xossa (afzal dam kuni,
  taqiq soatlar, part-time oynalari, maks oyna), erkin matn emas. (Ректор)
- **Scoped regeneration** (ХроноГраф): faqat bitta parallel / sinf / o'qituvchi / fan bo'yicha
  qayta hisoblash, qolganini muzlatib — tuzatish mavsumining qotil xususiyati.
- **Tez iteratsiya** (НИКА: <30s generatsiya → ko'r → qattiqlashtir → qayta).
- **Imkonsizlik blok-tahlili** (АВТОР): yechim yo'q bo'lsa manba ma'lumotlardagi qarama-qarshi
  blokni topib ko'rsatadi; muharrirda **almashtirishlarni sifat taqqosi bilan** taklif qiladi.
- **Zamena jurnali avto-to'ladi** (sinf, dars, kim, fan, soat) — oylik/tarifikatsiya artefakti.
- **Дневник.ру naqshi**: o'zgarish asl jadvalni qayta yozmaydi, **"zamena sifatida ko'rsatiladi"**;
  bekor qilingan dars tiklanadi.
- **СГО/Kundalik tuzog'i**: jurnal yozuvi (baho/davomat) bor darsni o'chirib bo'lmaydi — kech
  jadval tahriri jurnal bilan to'qnashadi → **qoralama/e'lon ajratish + effective-dated** shart.
- **Kundalik (eMaktab)**da avto-generatsiya YO'Q (faqat katak-katak kiritish + "O'qituvchini
  almashtirish" tugmasi) — bizning modul to'ldiradigan bo'shliq ayni shu.

---

## 6. Kunlik operatsiya moduli anatomiyasi (12 qobiliyat — hammada takrorlanadi)

1. **Bandlikni 3 resurs turi uchun kiritish**: o'qituvchi / sinf / xona; sana oralig'i, qisman kun;
   ofis/zavuch kiritadi yoki o'qituvchi appdan o'zi xabar beradi (ruxsat bilan).
2. **Avtomatik ta'sir hisobi**: bandlik saqlanishi bilan barcha yetim darslar (+ tanaffus
   navbatchiliklari) "ochiq" bo'lib chiqadi — hech narsa qo'lda qidirilmaydi.
3. **Bir ekranli kunlik dashboard** (ertalabki kokpit): bitta sana, barcha ochiq bandlar,
   svetofor (hal kerak / taklif qilingan / hal qilindi / qisman / kerak emas) + jonli hisob.
   (Arbor: qizil/sariq/yashil/to'q sariq/kulrang)
4. **Ranjlangan o'rinbosar takliflari** (universal mezonlar): shu soat bo'sh → standby navbatchi →
   shu sinfni boshqa joyda o'qitadi → shu fanni biladi → fairness hisoblagichi past → (UK) himoyalangan
   PPA vaqtida emas. Untis: top-3 kandidat, har qaror "bir bosish". Ректор 3 pog'onasi: shu soat
   oynasi bor → qo'shni darsi bor → shu kun bo'sh.
5. **Adolat hisoblagichi** (Untis **Zählwert**): har o'qituvchi uchun bergan zamena vs bekor
   bo'lib "yutgan" darslar; biriktirish paytida ko'rinadi VA taklif ranjiga qaytadi; qaysi hodisa
   turlari hisoblanishi sozlanadi. (Arbor: yilboshidan cover; Edval: "in-lieu" almashuv;
   Fransiya: shartnoma kvotasi)
6. **Boy o'zgarish-tur taksonomiyasi** (Untis Vertretungsart — asosiy dizayn saboG'i): zamena /
   faqat nazorat (dars o'tmay qarab turish) / bekor / ko'chirildi / birlashtirildi / xona
   almashdi / qisman zamena / **ozod bo'ldi** (sinfi sayohatda — kandidat hovuziga tushadi) /
   qo'shimcha dars / almashuv / keyin qoplanadigan dars. Har tur o'z to'lov/statistika/ko'rsatish
   semantikasiga ega.
7. **Standby va "permanence"** birinchi darajali natijalar: jadvalga rejalashtirilgan navbatchi
   soatlar (takliflarda birinchi turadi); Pronote'da "o'quvchilar nazoratli zalga" — alohida
   qaror turi, xonani bo'shatadi.
8. **Tadbir/imtihon overlay**: sayohat/imtihon sinfni muddatga darslardan chiqaradi,
   o'qituvchilarini kandidat hovuziga qo'yadi, xonalarni bloklaydi, qatnashmaydiganlarni boshqa
   sinfga biriktiradi — asosiy jadvalga TEGMASDAN.
9. **Effective-dated versiyalar**: yil o'rtasi qayta qurish sanali davr sifatida yashaydi; tarix,
   o'tgan zamenalar, yillik statistika saqlanadi. (Untis Perioden; EDT: ≥15 kun = "uzoq zamena",
   kunlik cover'dan alohida konstruksiya)
10. **Bir bosishda e'lon + nishonli bildirishnoma**: qoralama→publish darvozasi (Bromcom Auto
    Cover Summary — saqlashdan oldin ko'rib chiqish); publish'da faqat daxldorlarga push/SMS/email:
    o'rinbosarga (xohlasa avval roziligini so'rab), sinf o'quvchilari va ota-onalarga; bekor dars
    hammaning jonli jadvalida qizil, ko'rsat/yashir tugmasi bilan.
11. **Ko'p kanalli kunlik chiqish**: yo'lak/o'qituvxona monitori (avto-aylanuvchi, o'qituvchi va
    o'quvchi ko'rinishlari alohida), appda "bugun+ertaga", bosma kunlik varaq, har o'rinbosarga
    **cover slip** (sinf ro'yxati + xona + davomat vazifasi).
12. **Avtomatlashtirish + audit**: ixtiyoriy avto-biriktirish dvigateli — tartibini sudrab
    o'zgartirsa bo'ladigan ustuvorlik qoidalari + "Absolute" cheklovlar + saqlashdan oldin xulosa
    (Bromcom); hisobotlar (o'qituvchi-boshiga cover, bandlik tahlili, sinf-boshiga ta'sir) = audit
    izi; kim kiritadi / kim biriktiradi / kim e'lon qiladi — rolga bog'liq.

---

## 7. Bizga ko'chirish — ustuvorlik bo'yicha tavsiyalar

Bizda bor poydevor: `Jadval Versiyasi`+`Jadval Yozuvi` (sanali versiya), konflikt validatsiyasi,
Excel import/sinxron, `/app/dars-jadvali` zavuch ekrani, `Jadval Ozgarishi` (arxitekturada).

**A — darhol, arzon, katta qiymat (muharrir UX):**
1. Karta ko'tarilganda **slotlarni jonli bo'yash** (yashil/sariq/qizil + NEGA tooltip) — №2 standart.
2. **Laganda**: joylanmagan soatlar hisoblagichi (guruh×fan bo'yicha "qolgan soatlar") + filtr.
3. **Lock/pin** + undo/redo (kamida 20-30 qadam).
4. **"Bu yerga nima sig'adi?"** bo'sh katakka bosganda kandidat darslar ro'yxati (aSc; bizda
   ma'lumot modeli tayyor — guruh soat normasi bor).
5. **SanPiN/Sivkov balli gistogramma** har sinf uchun (kunlik ball + ideal egri chiziq) +
   "muvofiqlik spravkasi" chop etish — zavuch tekshiruvchilarga beradigan hujjat. Shkala jadvali
   sozlanadigan doctype.

**B — kunlik operatsiya (eng yuqori operatsion qiymat; `Jadval Ozgarishi` dizayniga kiritish):**
6. O'zgarish-tur taksonomiyasi (zamena/nazorat/bekor/ko'chirildi/xona/ozod-bo'ldi/qo'shimcha).
7. Ranjlangan kandidatlar (bo'sh → fan mos → sinfni biladi → fairness) + **Zählwert-uslub
   hisoblagich** (bergan vs yutgan).
8. Ertalabki svetofor-dashboard + bir bosishda e'lon (Telegram push bizning kanal).
9. Zamena jurnali → oylik tabelga oqim (bizda tabel moduli bor — tarifikatsiya bog'i tabiiy).

**C — generatsiya bosqichiga (CP-SAT rejamizga UX talablari):**
10. Per-qator **Test** (shu o'qituvchi/guruh alohida sig'adimi) + feasibility pre-check hisoboti.
11. Halol progress (joylanmagan hisoblagich + eng yaxshi natija) + **relaxation iqror ro'yxati**.
12. **Scoped regeneration** (bitta guruh/o'qituvchi, qolgani pin) — ХроноГраф/MPP uslubi.
13. Variant taqqoslash (ikki versiya diff — farq qilgan yozuvlar highlight) + sifat bali.

**D — power (keyinroq):**
14. Zanjirli almashuv takliflari (Untis Gain/Consequence; 2-3 qadam bilan boshlash yetarli).
15. Prime-uslub **marker** (taqiq/istalmagan/majburiy slotlarni gridga bo'yash) — o'qituvchi
    mavjudlik gridining tabiiy UI'si.

---

## 9. CHUQUR INTERAKSIYA TADQIQOTI (2026-11-24) — aniq mexanikalar va bizda tatbiqi

Ikki parallel tadqiqot: aSc muharriri (manual PDF + 13 help sahifa) va boshqa yetakchilar
(Untis/Prime/Edval/TimeTabler/Lantiv/UniTime/Skolaris/Timetable Master).

### 9.1 aSc muharririning aniq mexanikasi (etalon)
- **Bosib-olish / bosib-qo'yish** (hold-drag EMAS): bir bosish — kursor karta shakliga kiradi,
  ikkinchi bosish — joylanadi. Karta qo'ldaligida: yashil=mumkin, ko'k=savolli (?), qizil=band,
  kulrang=mutlaqo taqiq; kursor ostidagi kun/dars/sinf sarlavhalari sariq yonadi; o'z sinf qatori
  yashil — boshqa qatorga qo'yib BO'LMAYDI.
- **Siqib chiqarish zanjiri (signature)**: band katakka qo'ysang — o'sha sinfning bitta kartasi
  bo'lsa, u avtomatik QO'LGA O'TADI (zanjir davom etadi); boshqa sinf/bir nechta karta bo'lsa —
  dialog: joyla (siqilganlar lagandaga) / bekor / aynan bittasini qo'lga ol. Zanjirning hammasi
  BITTA undo amali.
- **Laganda (Control panel, pastda)**: filtr (sinf/o'qituvchi/fan/xona), bir xil kartalar yig'ilib
  1 karta + son; kartani olib tashlash = o'ng tugma Remove YOKI lagandaga sudrash YOKI **qo'ldagi
  kartaga o'ng tugma** (darhol lagandaga).
- **Warn-don't-block**: taqiq joyga ham qo'yish mumkin — karta qizil chiziq oladi (xonasiz=oq
  chiziq); to'liq tekshiruv Space (Verification) — xato qatori bosilsa aybdor kartalar bo'yaladi.
  Qattiq rad faqat 2 joyda: qulflangan karta (miltillaydi) va boshqa sinf qatori.
- Undo/Redo 100 amal (faqat karta pozitsiyalari); bo'sh katakka o'ng tugma = "nima sig'adi".

### 9.2 Boshqa tizimlar — asosiy farqlar
- **Untis**: drag paytida yashil tusi QANCHA TO'Q bo'lsa shuncha yaxshi (sifat gradatsiyasi);
  binafsha=xona band; ko'k strelka=almashuv mumkin, qizil strelkalar butun zanjirni chizadi;
  Tauschvorschläge: 2/3/4 tomonlama almashuvlar Gewinn(+/-ball) va Auswirkung ustunlari bilan.
- **Prime**: o'q bo'yicha qulflangan drag (sinf ko'rinishida faqat gorizontal — resursni
  adashib o'zgartirib bo'lmaydi); karta soyasi BARCHA ochiq ko'rinishlarda; konfliktga ruxsat —
  kartalar qiyshayadi + qo'ng'iroq hisoblagichi; History 100 holat.
- **TimeTabler**: Priority List — tizim KEYINGI qaysi darsni joylashni o'zi aytadi; tanlanganda
  slotlar 1–5 sifat bahosi, `*1*`=tavsiya; nuqta bosilsa "nega mumkin emas" hisoboti; FIT —
  16 qadamgacha "musiqiy stullar" zanjirlari ro'yxati.
- **Lantiv**: drag paytida har resurs uchun yashil/sariq/qizil chiziqchalar (conflict prediction
  stripes); real-time hamkorlik. **Timetable Master**: pastda parking panel. **FET**: interaktiv
  muharrir YO'Q (uchinchi tomon reFET/FET_edit-print to'ldiradi — muharrir shartligining isboti).
- **7 universal naqsh** (tarqalish bo'yicha): (1) ko'tarilgandayoq baholab bo'yash, (2) drag asosiy
  harakat + himoya relslari, (3) bir bosishli undo + ko'rinadigan tarix, (4) hisoblangan almashuv
  zanjirlari ball bilan — taklif, majbur emas, (5) rad etish o'rniga ruxsat + baland bayroq,
  (6) talab bo'yicha "nega" tushuntirish, (7) laganda birinchi darajali drag manba/manzil.

### 9.3 BIZDA TATBIQ QILINDI (2026-11-24, /app/dars-jadvali qayta qurildi)
1. **Bitta bosish = ko'tarish** (eski: bosish→dialog→"Ko'chirish" 3 qadam edi); ikkinchi bosish
   o'sha kartaga = bekor; Esc=bekor.
2. **Drag&drop ham ishlaydi** (pointer events, ghost karta, hover katak konturi; telefonda
   bosish-bosish qoladi).
3. **Laganda** — `Jadval Yozuvi.joylanmagan` (Check) + kun="",dars=0; validate konfliktni
   o'tkazib yuboradi; gridda ko'rinmaydi, get_data `laganda` ro'yxati; blok butun to'plami bilan
   tushadi/qaytadi. O'chirish endi ikki daraja: 🧺 lagandaga (so'roqsiz, undo bor) /
   🗑 butunlay (confirm bilan, kontekst menyuда).
4. **Siqib chiqarish (bounce)**: lagandadan kelgan karta band katakka bosilsa qarshi dars
   lagandaga chiqadi (`dars_siqib_joyla`), va aSc zanjiri — siqilgan karta avtomatik QO'LGA
   o'tadi (Esc=lagandada qoladi). Grid kartasi uchun band katak: toza almashuv SO'ROQSIZ
   (undo bor), ogohli almashuv — dialog: "baribir almashtir" / "qarshini lagandaga chiqar" / bekor.
5. **Kun chiplari mvbar'da**: karta qo'ldaligida har kun uchun bo'sh joy soni — boshqa kunga
   bir bosishda o'tiladi (bizning kun-tab grid'ida kross-kun ko'chirishning yechimi).
6. **Undo/Redo** (Ctrl+Z / Ctrl+Y, tugmalar bilan): move/swap/unplace/displace amallari,
   displace undo'si ketma-ket teskari chaqiriqlar bilan.
7. **O'ng tugma**: kartada kontekst menyu (ko'chirish/qulf/laganda/hujjat/o'chirish);
   karta qo'ldaligida o'ng tugma = lagandaga (aSc).
8. Xarita holatlari: ok/afzal/swap_ok/swap_warn/**siqish**(yangi, binafsha ⤓)/band(+sabab)/oz.
Keyingi nomzodlar (qilinmagan): Untis Gewinn balli zanjir takliflari (D14), TimeTabler uslubida
bo'sh slot sifat bahosi 1–5, Prime konflikt-ruxsat modeli (bizda validate qattiq — laganda bilan
yumshatilgan), laganda filtri (sinf bo'yicha).

## 8-bis. Qo'shimcha manbalar (2026-11-24 tadqiqoti)
aSc: automatictimetable.com/aScTimeTables_Manual_English.pdf (p.22–28, 44) · help.edupage.org
t538/t118 (ko'chirish, hotkeys), t522 (laganda), t526 (lock), t528 ("nima sig'adi"), t534 (undo),
t1026 (chiziqlar), t1014 (verify), u6303 (2025 Advisor), u7875 (2026 search). Untis:
untis.com/manual mpstunden_verplanen/verschieben/tauschen, mpplanungsfunktionen ·
webhelp.untis.at Tauschvorschläge. Prime: primetimetable.com/help + pdf user guide (axis-lock,
shadow, History 100, markers; "magnets" degan narsa YO'Q — marker/pin). TimeTabler:
timetabler.com/manualtimetabling + UsingtheVisualBuilderScreen.pdf. Lantiv:
timetabling-turbo.lantiv.com wiki Interactive_Timetabling. Edval E10: help.tes.com F3/F11,
harfli konflikt markerlari. UniTime: help.unitime.org/suggestions + patat10.pdf. Skolaris:
mistservices.co.uk. Timetable Master: timetablemaster.com updating-timetable.

## 8. Manbalar (asosiylari)

Muharrir UX: automatictimetable.com/aScTimeTables_Manual_English.pdf · help.asctimetables.com
(id=518 yashil pozitsiyalar, id=130 test, id=526 lock, id=271 taqqoslash) · help.edupage.org
(t113 relaxation, t1183 analyze, u4743 Advisor) · webhelp.untis.at (Planungsdialog,
Tauschvorschläge, Diagnose, CCC-Analyse) · primetimetable.com/help + /features-list + marker blog ·
scheduling-studio.lantiv.com/wiki/Studio8-Scheduling.html · timetabler.com/kb/UsingtheVisualBuilderScreen.pdf
+ /PDFs/Glossary.pdf + Conflict Matrix (kayako 192) · help.unitime.org/suggestions +
/manuals/courses-solver · unitime.org/papers/patat04.pdf (MPP) · lalescu.ro/liviu/fet/forum (2332, 3461).
Kunlik operatsiya: untis.at (online-substitution-planning, vertretungsart, monitor-html,
Perioden/time-range) · help.edupage.org (e1637, e1639) + asc_substitutions_en_L4.pdf ·
support.arbor-education.com (20071894175389 Cover, 4405437889553 free-up, cover slips) ·
docs.bromcom.com (automatic cover, prioritisation, exam-room cover) · capita-sims.co.uk Cover ·
docs.index-education.com (EDT absences/remplacements, permanence, RCD) · powerschool.com
SmartFind Express · edval.education (Edval Daily) · compass.education.
Post-sovet: rector.spb.ru (3 + 4s) · urok.1sept.ru/publication/78389 (zavuch amaliyoti) ·
nikasoft.ru/nika-lux · solutions.1c.ru/catalog/timetable/features · mmis.ru/programs/avtor ·
studfile.net ХроноГраф · support.dnevnik.ru (49, 51, 248) · it-mda.ru/NetSchool/SGO_adm_tt.php ·
help.emaktab.uz (4404178748690, 9816606294172) · base.garant.ru Sivkov shkalasi ·
kids4u.ru/proverit-raspisanie-sanpin.
