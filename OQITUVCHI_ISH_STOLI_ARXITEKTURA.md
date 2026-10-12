# O'qituvchi ish stoli — Arxitektura va qurilgan ishlar

**Sana:** 2026-10-12 · **Holat:** 1-bosqich lokalda (target.local) qurildi va test o'tdi, prod qolgan.
Tadqiqot: [`OQITUVCHI_ISH_STOLI_TADQIQOT.md`](OQITUVCHI_ISH_STOLI_TADQIQOT.md)

---

## 0. Foydalanuvchi tasdiqlagan qarorlar

1. **Baho tizimi va chorak bahosi usuli — zavuch belgilaydi** (sozlamalar ekrani: 5/10/100 ballik,
   o'rtacha / vaznli / qo'lda).
2. **Kechikish hisobga olinadi** — alohida davomat holati + daqiqa + «necha kechikish = 1 yo'qlik».
3. **Uy vazifa biriktirilsa — tekshiriladi** (har o'quvchiga: bajardi / qisman / bajarmadi + ball).
4. **O'quvchi rasmlari bor** → dars kokpitida yuz ko'rinadi.
5. **O'qituvchilar ko'pchiligi kompyuterda** → desktop-first; mobil keyingi bosqichda.
6. **Bugungi kun to'liq batafsil ko'rinsin** — nima qilingan, nima qolgan, zavuch yuklagan
   qo'shimcha darslar ham.

---

## 1. Yangi ma'lumot modeli

| Doctype | Turi | Vazifasi |
|---|---|---|
| **Baholash Sozlamalari** | Single | Zavuchning yagona boshqaruv paneli: shkala, chorak usuli, yaxlitlash, kechikish, uy vazifa, RAG chegaralari |
| **Baho Turi** | Master | Og'zaki / Uy vazifa / Mustaqil ish / Nazorat ishi / Chorak nazorati + **vazn** (vaznli hisob uchun) |
| **Chorak Bahosi** | Tranzaksiya | Chorak yakuniy bahosi: `hisoblangan` (tizim) + `baho` (yakuniy) + `qolda` bayrog'i |
| **Uy Vazifa Natijasi** | Tranzaksiya | Uy vazifa tekshiruvi: o'quvchi × holat × ball |

**Mavjud doctype'larga qo'shilgan maydonlar:**
- `Dars Natijasi`: davomat'ga **«Kechikdi»** holati, `kechikish_min`, `baho_turi`
- `Uy Vazifa`: `tekshiriladi` (Check)

> ⚠️ Tuzatilgan xato: `Dars Natijasi.before_save` ilgari «Keldi»dan boshqa har qanday holatda bahoni
> o'chirib tashlar edi — kechikkan o'quvchi bahosi yo'qolardi. Endi `soz.BORLIK` (Keldi/Kechikdi) bo'yicha.

---

## 2. Yagona qoida manbasi — `dars_jadvali/sozlamalar.py`

Hamma ekran va hisobot **faqat shu moduldan** o'qiydi, shuning uchun zavuch qoidani bir joyda
o'zgartirsa — hamma joy moslashadi. Kesh: `tz_baholash_sozlamalari` (10 daq, saqlashda tozalanadi).

| Funksiya | Nima qiladi |
|---|---|
| `olish()` | Sozlamalar dict (yozuv yo'q bo'lsa `DEFAULT` — 5 ballik) |
| `davomat_holatlari()` | Kechikish o'chirilgan bo'lsa «Kechikdi» ro'yxatdan chiqadi |
| `chorak_hisobla(ballar)` | O'rtacha / vaznli hisob + yaxlitlash + `min_baho_soni` tekshiruvi |
| `trend(ballar)` | So'nggi 3 ball vs oldingi 3 ball → `+1 / 0 / -1` (shkalaga proporsional sezgirlik) |
| `korsatkich(...)` | O'quvchining qisqa ko'rsatkichi: o'rtacha + trend + **RAG rang** + davomat % + bayroqlar |
| `tuzatish_mumkinmi(sana)` | Bahoni tuzatish muddati (zavuch uchun cheklov yo'q) |
| `yaxlit(x)` | Matematik / yuqoriga / pastga |

**RAG qoidasi (sozlamadan):** qizil — o'rtacha < 3 **yoki** davomat < 80% **yoki** N ta ketma-ket past baho;
sariq — o'rtacha < 4 yoki davomat < 90% yoki uy vazifa limitdan ko'p bajarilmagan.
`MIN_DARSLAR = 4` — bundan kam dars o'tilgan bo'lsa davomat foizi ko'rsatiladi, lekin **xavf qilib
belgilanmaydi** (1 darsdan «0%» chiqmasligi uchun).

---

## 3. Backend API

**`dars_jadvali/sessiya.py`** (dars kokpiti)
- `sessiya_malumot(jadval_yozuvi, sana)` — kengaytirildi: o'quvchi **rasmi**, `trend/rang/davomat_foiz/bayroqlar`,
  `navigatsiya` (bugungi darslar + oldingi/keyingi), `oldingi` (o'tgan darsning mavzusi, kim yo'q edi,
  berilgan uy vazifa), `baho_turlari`, `sozlamalar`, `tuzatish_mumkin`
- `uy_vazifa_natijalari(uy_vazifa)` / `uy_vazifa_natija_saqla(...)` — tekshiruv ro'yxati va saqlash
- `uy_vazifa_saqla(...)` — `tekshiriladi` + sozlamadan default max ball

**`dars_jadvali/chorak.py`** (yangi)
- `chorak_jadval(guruh, fan, chorak)` — har o'quvchining ballari, tizim taklifi, mavjud chorak bahosi, RAG
- `chorak_saqla(...)` — upsert (qo'lda o'zgartirish `qolda=1` bilan belgilanadi)
- `chorak_avto(...)` — tizim hisobini hammaga qo'yish; **qo'lda tuzatilganlar tegilmaydi**

**`page/mening_jadvalim/mening_jadvalim.py`**
- `kun_paneli(oqituvchi)` — ⭐ «Qoldirilgan ishlarim» (oxirgi 14 kun: jurnal / mavzu / uy vazifa /
  tekshirilmagan vazifa; dars umuman yuritilmagan bo'lsa — bitta jamlangan qator) + «Diqqat talab qiladi»
- `bugun_batafsil(oqituvchi, sana)` — bir kunlik to'liq qaydnoma (pastda)

**`dars_jadvali/baholash.py`** — «Kechikdi», `baho_turi`, max baho validatsiyasi, tuzatish muddati,
hisobotlarda kechikish hisobi.

---

## 4. Ekranlar

### 4.1 `/app/baholash-sozlamalari` — ZAVUCH (yangi)
Besh bo'lim: **1** shkala (eng yuqori baho / o'tish / past chegarasi — shkala tanlanganda avtomatik
moslashadi) · **2** chorak bahosi (usul, yaxlitlash, min baho soni, tuzatish muddati) · **3** davomat va
kechikish · **4** uy vazifa · **5** o'zlashtirish rangi va xavf chegaralari.
Yorliqlar: Zavuch paneli → «Baholash sozlamalari», «Baho turlari», «Chorak baholari».

### 4.2 `/app/mening-jadvalim` — O'QITUVCHI, kun qaydnomasi
1. **⚠️ Qoldirilgan ishlarim** — bosilsa to'g'ri darsга o'tadi.
2. **📌 Bugun** — `kun yakuni` raqamlar qatori: *N dars · mavzu o'tildi X/Y · N baho qo'ydim ·
   o'rtacha · yo'q · kechikdi · uy vazifa · tekshirilmagan · qo'shimcha dars · to'liq tugallandi*.
3. **Har dars uchun batafsil qator** (vaqt ustuni + 5 qator ma'lumot):
   `📘 Rejada` (KTP keyingi mavzu + qamrov) · `✅ O'tildi` (mavzu, vaqt, izoh) ·
   `🧾 Yo'qlama` (keldi / yo'q / kechikdi + olingan vaqt) · `🎯 Baho` (nechta, o'rtacha, eng past…yuqori) ·
   `🏠 Uy vazifa` (matn, ball, muddat, tekshirildi N/M, bajardi/bajarmadi).
   Pastida **checklist chiplari**: Yo'qlama · Baho · Mavzu · Uy vazifa · Tekshiruv (✓ yashil / ○ kulrang)
   va «qoldi: …».
   Ranglar: ko'k = HOZIR ketayotgan dars · yashil = to'liq tugallangan · sariq = o'tgan, lekin ish qolgan ·
   qizil chiziq + ustidan chizilgan = bekor · **ko'k «➕ Zavuch yuklagan qo'shimcha dars»**.
4. **🚩 Diqqat talab qiladi** — o'quvchi, guruh, o'rtacha + trend, bayroqlar.
5. Haftalik to'r (avvalgidek) + boshqa kunlardagi qo'shimcha darslar.

### 4.3 `/app/dars-sessiya` — O'QITUVCHI, dars kokpiti
- **Tepa:** `‹ Oldingi` / `Keyingi ›` + **bugungi darslar dropdown**i (guruhdan guruhga bir tegishda) +
  dars taymeri («HOZIR — tugashiga 12 daq») + muddat qulfi ogohlantirishi.
- **Chap:** o'quvchi kartalari — **rasm** (yoki bosh harflar), chorak o'rtachasi, **trend o'qi**,
  davomat %, so'nggi ballar, 🚩 bayroq soni, **o'ng chetda RAG rangi**, bugungi belgi.
  `i` tugmasi → **o'quvchi kartasi** (KPI'lar + chorak tarixi + to'liq kartaga o'tish).
- **Keypad:** baho tugmalari (shkaladan), baho turi, `✓ Keldi`, `K` + daqiqa, `H`, `S`, `Q`.
- **Klaviatura:** ↑↓ o'quvchi · raqam = baho · `K` kechikdi · `H` yo'q · `S` kasal · `Q` · `C` keldi · Esc.
- **Optimistik saqlash** — avval ekran, keyin server; xato bo'lsa qaytariladi.
- **O'ng:** «Oldingi dars» (mavzu, kim yo'q edi, uy vazifa + «✔️ Tekshirish») · o'quv reja mavzular +
  «o'tdim» · uy vazifa formasi (`tekshiriladi` belgisi bilan) + chorak tarixi.
- **Uy vazifa tekshiruv dialogi:** har o'quvchi uchun bajardi/qisman/yo'q + ball, «Hammasi bajardi» tugmasi.

---

## 5. Test natijalari (target.local, 2026-10-12)

`bench migrate` toza o'tdi; sozlamalar va 5 ta baho turi avtomatik yaratildi.
Funksional test (yozib → o'qib → tozalab):
- Kechikish + baho + baho turi saqlanishi ✓ (bu yerda doctype xatosi topilib tuzatildi)
- Max baho validatsiyasi ✓ («Baho 5 dan katta bo'lishi mumkin emas»)
- Uy vazifa tekshiruvi 3/17, «bajarmadi» → ball 0 ✓
- Chorak: o'rtacha/vaznli hisob, `min_baho_soni` cheklovi, qo'lda tuzatishdan keyin avto hisob
  uni **o'tkazib yuborishi** ✓
- Kun qaydnomasi: jurnal 8 belgilangan / 6 baho / o'rtacha 4.0 / 2 yo'q / 1 kechikdi,
  uy vazifa 3 tekshirilgan, **checklist 5/5** ✓
- Zavuch qo'shimcha yuklamasi kun qaydnomasida «qo'shimcha dars» bo'lib chiqdi ✓
- Qoldirilgan ishlar shovqini 180 → 59 ga tushdi (jamlangan qator)
- Ikki sahifa ham serverdan to'g'ri yuklanadi (script/style yetkaziladi) ✓

---

## 5.1 Chorak mavzularini bir martada biriktirish (2026-10-12, qo'shildi)

**Muammo:** ilgari o'qituvchi `Oquv Reja` formasida qatorlarni bittalab qo'shishi kerak edi —
chorakka 20-30 mavzu uchun juda sekin.

**Yechim:** global dialog `tz_mavzu_dialog()` (`public/js/mavzu_import.js`, `app_include_js` orqali
hamma desk sahifasida mavjud). Ikki yo'l:

1. **Ro'yxatni joylash** — mavzular ro'yxatini Word/Excel/KTP'dan ko'chirib joylaydi.
   `oquv_reja.matn_parse()` satrlarni tahlil qiladi:
   - raqamlash: `1.` `12)` `-` `*` olib tashlanadi
   - soat: `— 2 soat`, `(3 soat)`, `| 2`, `; 2`
   - ustunlar: `bo'lim | mavzu | soat` yoki `;` yoki tab
   - bo'lim sarlavhalari: `# ...`, `== 2-chorak ==`, `1-bob. Kasrlar:`, oxiri `:` bo'lgan qisqa satr
   - dars turi avtomatik: «nazorat/bsb/imtihon» → Nazorat · «takror/umumlash» → Takrorlash ·
     «amaliy/laborator/mashq» → Amaliy; qo'lda: `[nazorat] ...`
2. **Boshqa rejadan nusxa** — o'tgan yil yoki parallel sinf rejasidan
   (`reja_royxati` → `reja_qatorlari` → `rejadan_nusxa`).

Keyin **tahrirlanadigan ko'rib chiqish jadvali** (№ / bo'lim / mavzu / soat / turi / o'chirish)
chiqadi — tasdiqdan oldin tuzatish mumkin.

**Backend (`oquv_reja.py`):** `matn_parse` · `mening_fanlarim` (o'qituvchiga o'z fan×guruhlari,
zavuchga butun maktab) · `mavzular_saqla` · `reja_royxati` · `reja_qatorlari` · `rejadan_nusxa`.

**Muhim xatti-harakatlar:**
- Reja bo'lmasa — **o'zi yaratiladi** va «Faol» qilinadi (nomi avto: `MATH — 5 (2026-2027)`).
- Bir nechta guruh belgilansa — **bitta reja** hammasiga biriktiriladi (`sinflar` jadvali orqali).
- `rejim="almashtirish"` — mavjud qatorlar o'chiriladi, lekin **`Dars Bajarilishi` bog'langan
  (o'tilgan) qatorlar saqlanadi** — tarix buzilmaydi.
- «Chorak / bo'lim» maydoni — satrda bo'lim ko'rsatilmagan mavzularga qo'yiladi (sarlavha ustun).
- O'qituvchi faqat **o'zi dars beradigan** fan×guruhga yozadi (`_ruxsat_fan`); zavuchga cheklov yo'q.

**Kirish nuqtalari:** dars kokpitida «Chorak mavzularini biriktirish» (reja yo'q bo'lsa) va
«Mavzu qo'shish» (reja bor bo'lsa) · «Mening jadvalim» tepasida «Mavzular» tugmasi.

**Test (target.local):** 8 satrlik aralash formatdagi ro'yxat → 8 mavzu / 13 soat, bo'limlar va dars
turlari to'g'ri aniqlandi; yangi reja yaratildi va kokpitda «keyingi mavzu» darhol chiqdi;
nusxa olish va «almashtirish» rejimi ishladi; menejer 307 fan×guruh juftligini ko'radi.

---

## 5.2 Jurnal ko'rinishi va ekranlar taqsimoti (2026-10-12, qayta ishlangan)

**Dars kokpitining chap tarafi — jurnal matritsasi** (kartalar o'rniga):
- O'quvchilar **ketma-ket** (qator-qator), chapdagi uch ustun qotib turadi: № · rasm+ism · o'rtacha+trend.
- Yonida **chorakdagi barcha baholar katak-katak**, **xronologik tartibda**: o'tgan kunlar chapda,
  bugun (yoki tanlangan kun) eng o'ngda — qog'oz jurnal kabi; ochilganda jadval o'ng chetga suriladi. Katakda baho yoki `H` (kelmadi) / `S` (kasal) / `Q` / `K` (kechikdi) turadi; ustun
  sarlavhasida sana, tooltipda o'tilgan mavzu.
- **Har qanday katak bosilsa** — shu kun uchun keypad ochiladi, ya'ni o'tgan kun jurnalini ham
  to'ldirish/tuzatish mumkin (`Dars Natijasi.jadval_yozuvi` o'sha kundagi darsdan olinadi).
  Server `tuzatish_muddati_kun` ni tekshiradi: o'qituvchiga 7 kun, zavuchga cheklovsiz.
- Klaviatura: `↑↓` o'quvchi · `←→` kun (ustun) · raqam = baho · `K/H/S/Q/C` · `Delete` tozalash.
- O'tgan kun o'zgarsa — o'rtacha/trend qayta hisoblanishi uchun 1.2 s dan keyin jim yangilanadi.
- Backend: `sessiya_malumot` qaytaradigan `ustunlar` (sana, label, bugun, mavzu) va har o'quvchidagi
  `kataklar` (ustunlarга mos; `{baho, davomat, kechikish_min, baho_turi, jadval_yozuvi, izoh}`).

**To'liq kenglik:** `dars-sessiya` va `kunlik-jadval` sahifalarida `.tz-fullbleed-wrap` /
`.tz-container-fluid` CSS qoidalari yo'q edi (har sahifa o'z CSS'ini yuklaydi) — shuning uchun Frappe
konteyneri kenglikni cheklab turardi; qo'shildi. Kunlik rejada eski `max-width: 760px` ham olib tashlandi.

**O'tgan sanalar bilan ishlash (2026-10-12):**
- `ustunlar` endi **chorakdagi barcha dars kunlari** (jurnali bo'sh kunlar ham) — haftalik jadvaldan
  hisoblanadi (`_chorak_dars_kunlari`: `Jadval Yozuvi.kun` → hafta kuni, chorak boshidan bugungacha),
  har ustunda o'sha kundagi `jadval_yozuvi` (guruhда bir fandan bir necha slot bo'lsa ham to'g'ri
  dars biriktiriladi) va `tahrir` bayrog'i (tuzatish muddati bo'yicha).
- Kokpit sarlavhasida **sana boshqaruvi**: `‹ oldingi dars kuni` · sana tanlagich · `keyingi kun ›`
  (+ «bugunga qaytish»). Tanlangan kun o'tgan bo'lsa — «o'tgan kun — jurnalni to'ldirish mumkin» belgisi.
- Tanlangan kun uchun **hammasi ishlaydi**: yo'qlama/baho (katak yoki keypad), **o'tilgan mavzuni
  belgilash** (`dars_otdim(sana=...)`) va **uy vazifa** — panellar sarlavhasida o'sha sana ko'rinadi.
- Muddati o'tgan ustunlar **qulflanadi** (🔒, chizilgan fon) va bosilmaydi; server ham tekshiradi.
  Sozlama: *Baholash Sozlamalari → Bahoni tuzatish muddati (kun)*; **0 = cheklovsiz** (hozir 0 qilingan).

**O'quvchi haqida to'liq karta (2026-10-12):** jurnalda **ism/o'rtacha ustiga bosilsa** katta dialog
ochiladi (`baholash.oquvchi_toliq`):
- **Yuqorida:** rasm, ism, guruh(lar)+jurnal raqami, tug'ilgan sana, telefon, ota-ona (ism/aloqa/tel)
  va KPI'lar: umumiy o'rtacha+trend · davomat % · yo'qlik · kechikish · bajarilmagan uy vazifa · jami baho;
  pastida xavf bayroqlari.
- **Fanlar bo'yicha jadval:** fan · so'nggi 12 ball · o'rtacha+trend · davomat % · yo'q · kech ·
  UV yo'q · qo'yilgan chorak baholari. Qatorga bosilsa tarix shu fanга filtrlanadi.
- **Baholar va davomat tarixi** (asosiy talab): *sana · hafta kuni · fan · nechanchi dars va vaqti ·
  guruh · **qaysi mavzu uchun** (KTP tartib raqami bilan) · baho · baho turi · davomat (kechikish
  daqiqasi bilan) · izoh*. Filtrlar: fan, chorak, «faqat baholar»; pastida yozuv/baho soni va o'rtacha.
- **Uy vazifalar:** sana · fan · vazifa · holat (bajardi/qisman/bajarmadi) · ball/max · izoh.
- Tugmalar: «📊 Baholar hisoboti» va «👤 O'quvchi formasi».

Mavzu tarixga `Dars Bajarilishi` (guruh+fan+sana) orqali bog'lanadi, dars vaqti/raqami esa
`Jadval Yozuvi`dan olinadi.

**Mavzu va uy vazifa — HAR KUN UCHUN ALOHIDA (2026-10-12):**
- Kokpitda qaysi sanada turgan bo'lsangiz, o'sha kunning ma'lumoti ko'rinadi va saqlanadi
  (`Dars Bajarilishi` va `Uy Vazifa` ikkisi ham `(jadval_yozuvi, sana)` bo'yicha yagona).
- O'quv reja panelida yuqorida **«📅 09.10 (Juma) — shu kun mavzusi»** bloki: belgilangan bo'lsa
  mavzu + holat (O'tildi/Qisman) + izoh va «🗑 Olib tashlash»; belgilanmagan bo'lsa sariq eslatma.
- Mavzular ro'yxatida: **«shu kun»** yashil yorlig'i (aynan shu sanada o'tilgan),
  boshqa kunda o'tilgani esa o'sha sana bilan ko'rsatiladi; tooltipda hamma o'tilgan kunlar.
- «Belgilash» tugmasi yonida **holat tanlagich** (O'tildi / Qisman / O'tilmadi) — tanlangan sanaga yoziladi.
- Uy vazifa paneli sarlavhasi: «📅 09.10 kuni uchun · saqlangan / hali berilmagan»; «🗑 O'chirish»
  tugmasi faqat shu kun vazifasini o'chiradi; chorakdagi boshqa kunlar ro'yxatidan «↗» bilan
  o'sha kunga o'tiladi.
- Yangi endpoint: `oquv_reja.mavzu_olib_tashla(jadval_yozuvi, sana)`; `sessiya_malumot` qaytaradigan
  `reja.mavzu_sanalar` (reja qatori → o'tilgan kunlar) va `reja.bugun` (tanlangan kun yozuvi).
- Test: bugun «Test mavzu A» + A-vazifa, 3 kun oldin «Test mavzu B (Qisman)» + B-vazifa — har biri
  o'z kunida ko'rindi; bugungi mavzu olib tashlanganda 3 kun oldingisi saqlanib qoldi.

**O'quv reja dars kokpitidan boshqariladi:** reja yo'q bo'lsa «📘 Chorak mavzularini biriktirish»,
bor bo'lsa «📘 Mavzu qo'shish / almashtirish» + «✏️ Rejani to'liq tahrirlash» (Oquv Reja formasi).

**Ekranlar taqsimoti (foydalanuvchi talabi):**
| Sahifa | Nima turadi |
|---|---|
| `/app/kunlik-jadval` — **kunlik reja** | **Ekran ikkiga bo'lingan.** CHAP: o'qituvchi rejimida **kun qaydnomasi** (kun yakuni raqamlari + har dars uchun reja/o'tildi/yo'qlama/baho/uy vazifa + checklist chiplari + «➕ zavuch yuklagan qo'shimcha dars»), sinf rejimida — avvalgi kunlik lenta. O'NG: ⚠️ **Qiladigan ishlarim** + 🚩 **Diqqat talab qiladi** — sobit 340px, yopishib turadi (1000px dan tor ekranda bir ustunga tushadi). **Kun qaydnomasi asosiy element:** sahifaning eski `max-width:760px` cheklovi olib tashlandi, qaydnoma butun ekran kengligini oladi, dars qatorining ma'lumot satrlari ikki-uch ustunga yoyiladi, shriftlar kattalashtirildi; sarlavha boshqaruv qatoriga ko'chdi. Sana strelkalari bilan istalgan kunning qaydnomasi ko'riladi. O'qituvchi kirganda avtomatik **o'z** kunlik rejasiga tushadi (rejim=o'qituvchi); zavuch boshqa o'qituvchini tanlab uning ishlarini ko'radi. |
| `/app/mening-jadvalim` | **Faqat jadval:** haftalik to'r + boshqa kunlardagi qo'shimcha darslar. Kun qaydnomasi, qiladigan ishlar va diqqat ro'yxati **kunlik rejaga ko'chirildi**; bu yerda «📌 Bugun — N dars · Kunlik rejani ochish →» chaqiruvi va sarlavha ostida «⚠️ N ish qoldi · 🚩 N o'quvchi — kunlik rejada» havolasi qoldi. |
| `/app/dars-sessiya` | Dars kokpiti: jurnal matritsasi + o'quv reja + uy vazifa. |

---

## 6. Keyingi bosqichlar (tadqiqotdagi tartibda)

1. **Chorak bahosi ekrani** (`/app/chorak-baholari` sahifa) — hozir doctype list + API bor, vizual
   jadval (o'quvchi × ballar × taklif × yakuniy) qolgan.
2. Kontekst flaglar (tibbiy / maxsus ehtiyoj / pedagogik eslatma) va ota-onaga bir tegishda aloqa.
3. O'tirish sxemasi + proyektor rejimi + tasodifiy o'quvchi tanlagich.
4. Dars materiali va dars maqsadi (fayl/havola) biriktirish.
5. Mobil layout + offlayn navbat (o'qituvchilar kompyuterda ishlagani uchun ustuvorligi past).
6. Baho turini chorak bahosiga bog'lash bo'yicha hisobotlar; bildirishnomalar (jadval o'zgarishi).
