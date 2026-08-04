# Target Zenit — Maktab CRM arxitekturasi (loyiha hujjati)

> Sana: 2026-08-04. Manba: dunyodagi yetakchi maktab CRM tizimlari bo'yicha chuqur tadqiqot
> (19 manba, har bir fakt 3 mustaqil tekshiruvdan o'tgan).
> Holat: **faqat arxitektura bosqichi** — hali kod yozilmagan.

---

## 1. Uchta yetakchi tizim taqqoslamasi

| Jihat | **OpenApply** (Faria) | **Finalsite Enrollment** (sobiq SchoolAdmin) | **LeadSquared** (Education CRM) |
|---|---|---|---|
| Kimga | Xalqaro/xususiy maktablar | AQSH xususiy maktablari | Ta'lim vertikali (maktab+universitet), rivojlanayotgan bozorlar |
| Kuchli tomoni | **Ota-ona portali**: bitta akkauntda barcha farzandlar (aka-uka avtomatik bog'lanadi), ariza holati, hujjat yuklash, tadbirlar, to'lovlar | **Bosqich+Status modeli**: har bosqich ichida cheksiz ichki statuslar, har biri Active/Inactive/Waitlist turiga ega | **Kommunikatsiya avtomatikasi**: email/SMS/WhatsApp/qo'ng'iroq, drip-kampaniyalar, muddat eslatmalari |
| Voronka | Checklist orqali: status/dasturga qarab qadamlar o'zgaradi (To Do, Tour, Submission, Interview) | Inquiry → Applicant → Application Complete → Accepted → Enrollment → Enrolled | Prospect → Inquiry → Applicant → Accepted → Enrollment confirmed (to'lov!) → Enrolled |
| Avtomatika | Xulq-atvorga qarab tarmoqlanuvchi ketma-ketliklar (Finalsite bilan) | Behavior-triggered workflows (qaysi kontentga qiziqqaniga qarab keyingi xabar) | Ariza tugallanmasa → menejerga signal; deadline eslatmalari; autoresponder |
| Analitika | Voronka + segmentatsiya (sinf, hudud, bosqich) | Voronka dashboard | Manba bo'yicha murojaatlar, bosqichlararo konversiya, menejer unumdorligi, yillar taqqoslash |

**Umumiy xulosa — uchchalasi ham bir xil yadroga kelib to'xtagan:**
1. **Kanonik voronka** (6–8 bosqich): Murojaat → Tashrif/Tur → Ariza boshlandi → Ariza to'liq → Imtihon/Suhbat → Taklif → **Depozit to'landi** → Qabul qilindi. Depozit — alohida bosqich, "qabul"dan oldin.
2. **Ikki darajali holat**: Bosqich (stage) + uning ichidagi Statuslar. Har status turi: `Active` (jarayonda) / `Inactive` (shu bosqichda tushib qoldi) / `Waitlist` (navbatda). Ichki statuslar ota-onaga ko'rinmaydi.
3. **Oila-markazli model**: yozuv o'quvchida emas, **oilada** — bitta ota-ona yozuviga bir nechta farzand bog'lanadi, barcha muloqot oila kartochkasiga yoziladi.
4. **Har bosqichda checklist** — ota-ona keyingi qadamni doim biladi.
5. **KPI standarti**: bosqichlararo konversiya, manba tahlili (qaysi reklama ishlayapti), **24 soat ichida birinchi aloqa** (speed-to-lead), yillik taqqoslash.

**Muhim benchmark (tasdiqlangan):**
- Murojaat → Ariza konversiyasi tajribali xususiy maktablarda **20–35%** (yangi maktablarda 10–20%).
- Ota-onalarning **66%** i tanlagan maktabining javob tezligini "yuqori" deb baholagan (tanlamaganlarida 37%).
- Shaxsiylashtirilgan email ~**86%** ijobiy qabul qilinadi — ommaviy SMS'dan yaxshiroq.

---

## 2. Frappe stackdagi holat (tekshirilgan)

| Komponent | Nima beradi | Kamchilik |
|---|---|---|
| **Frappe Education** (rasmiy, ochiq kodli) | Student Admission (e'lon+veb-forma) → Student Applicant → Student/Program Enrollment, Guardian, Fees | Ariza statuslari faqat 4 ta: Applied/Approved/Rejected/Admitted. **Arizagacha bo'lgan voronka umuman yo'q** (murojaat, tur, suhbat, manba, drip) |
| **Frappe CRM** (alohida app) | Lead→Deal pipeline, Kanban, yagona muloqot jurnali, WhatsApp integratsiyasi (frappe_whatsapp, Meta Cloud API) | Savdo uchun qurilgan; maktab tushunchalari (oila, farzand, sinf) yo'q. Telegram rasmiy yo'q |
| **ERPNext CRM moduli** (saytda bor) | Lead/Opportunity | Savdo terminologiyasi, maktabga moslash qiyin |

**Qaror:** Arizadan keyingi qism uchun **Frappe Education** o'rnatiladi (backend). Arizagacha bo'lgan CRM qatlami — **target_zenit ichida custom doctype'lar** (Frappe CRM dizayn naqshlaridan nusxa olib). Bu bitta app ichida to'liq nazorat beradi.

---

## 3. Taklif etilayotgan arxitektura (doctype'lar)

### Yadro (pipeline)
- **Admission Stage** (master): nom, tartib raqami, ota-onaga ko'rinadigan nomi.
  Standart to'plam: `Murojaat → Tashrif belgilandi → Tashrif bo'ldi → Ariza boshlandi → Ariza to'liq → Imtihon/Suhbat → Taklif yuborildi → Depozit to'landi → Qabul qilindi` (+ parallel: `Qayta ro'yxat`).
- **Admission Status** (master, Stage'ga Link): nom, `status_type` = Active/Inactive/Waitlist, `internal_only` (ota-onaga ko'rinmaydi).
- **Admission Lead** (asosiy hujjat): oila Link, farzand ma'lumoti (ism, tug'ilgan yil, mo'ljal sinf), Stage+Status, **manba** (source: Instagram/Telegram/tavsiya/…), mas'ul menejer, birinchi aloqa vaqti (SLA hisobi uchun), o'quv yili.

### Oila-markazli qism
- **Family (Oila)**: ota/ona FIO, telefonlar, manzil; child table orqali farzandlar. Bir oila — bir nechta Admission Lead (har farzandga bittadan), aka-uka avtomatik bog'lanadi.
- Muloqot jurnali: Frappe'ning standart **Communication** + WhatsApp/Telegram xabarlari timeline'da.

### Jarayon qismlari
- **Admission Checklist Template** (Stage'ga bog'liq) → **Checklist Item** (lead ichida): hujjat yuklash, forma, tur, suhbat.
- **Tour/Event** (tashrif jadvali): sana, sig'im, yozilganlar; Lead'dan bron qilinadi.
- **Deposit/To'lov**: mavjud `Kassa` doctype yoki ERPNext Payment Entry bilan bog'lanadi — `Depozit to'landi` bosqichiga o'tish to'lov tasdig'iga bog'lanadi.

### Avtomatika (hooks + scheduler)
- Yangi murojaatda: menejerga topshiriq + **24 soat SLA** taymeri, kechiksa eskalatsiya.
- Bosqich o'zgarganda: ota-onaga xabar (WhatsApp/Telegram/SMS shablon).
- Ariza boshlanib tugallanmasa (N kun): menejerga signal.
- Drip-ketma-ketliklar: segment bo'yicha (sinf, manba) rejalashtirilgan xabarlar.
- Kanal ustuvorligi (Target Zenit reali): **Instagram DM (asosiy kirish kanali — ota-onalar shu yerdan yozadi)** > Telegram > WhatsApp > SMS > email.

### Instagram DM integratsiyasi (asosiy kanal)

Ota-onalar asosan Instagram'dan yozadi → DM'lar CRM ichida o'qilishi va javob berilishi kerak.

**Talablar (Meta rasmiy API, bepul):**
- Instagram **Business/Professional** akkaunt + unga bog'langan **Facebook sahifa**.
- **Meta Developer App** (developers.facebook.com), ruxsatlar: `instagram_business_basic`, `instagram_business_manage_messages`.
- Test rejimida 25 tagacha foydalanuvchi bilan App Review'siz ishlaydi; jonli rejim uchun **Meta App Review** kerak.
- Token: qisqa muddatli (1 soat) → uzoq muddatli (~60 kun), avtomatik yangilash scheduler'da.

**Arxitektura (target_zenit ichida):**
1. **Webhook endpoint** (`/api/method/target_zenit...instagram_webhook`): Meta har yangi DM kelganda POST yuboradi (GET verify ham bo'ladi; javob 20 soniyadan tez bo'lishi shart — qabul qilib navbatga qo'yamiz).
2. **Instagram Message** doctype: yo'nalish (kirish/chiqish), IG user id, matn, vaqt, Lead'ga Link.
3. **Avto-lead**: notanish IG user'dan birinchi xabar kelsa → yangi `Admission Lead` (source = Instagram DM), mas'ul menejerga topshiriq + 24h SLA.
4. **Javob yozish**: CRM ichidan (Lead sahifasida chat paneli) → Graph API orqali yuboriladi.
5. **Qoidalar (Meta cheklovi):** ota-ona yozgach **24 soat** ichida erkin javob; keyin 7 kungacha faqat "Human Agent" tegi bilan support-javob. **Birinchi bo'lib (cold) DM yozib bo'lmaydi** — chiquvchi drip'lar Telegram/SMS orqali ketadi.
6. Limit: ~200 API call/soat — maktab hajmi uchun bemalol yetadi.

**Bosqichli reja:** (1) webhook + o'qish + avto-lead → (2) CRM'dan javob yozish → (3) App Review'dan o'tish → (4) keyin xohlasak komment/mention triggerlari.
**Zaxira variant:** App Review cho'zilsa — vaqtincha vositachi servis (ManyChat/Wazzup/Zernio, ~$6-15/oy) webhook orqali bizning API'ga uzatadi.

### Analitika (dashboard)
- Voronka: har bosqichda nechta lead, bosqichlararo konversiya % (benchmark: murojaat→ariza 20–35%).
- Manba bo'yicha: qaysi kanal nechta qabulga olib keldi (reklama ROI).
- Menejer unumdorligi: birinchi aloqa mediana vaqti, yopilgan leadlar.
- Yillik taqqoslash (o'quv yili bo'yicha).

---

## 4. Ochiq savollar (keyingi bosqichda hal qilinadi)
1. Frappe Education'ni o'rnatamizmi yoki Student/Guardian'ni ham o'zimiz yozamizmi?
2. Telegram bot: frappe_telegram community app yoki custom bot? (O'zbekistonda Telegram asosiy kanal)
3. WhatsApp Business API O'zbekistonda rasmiy ulanish yo'li va narxi.
4. Sinf bo'yicha o'rin/sig'im rejalashtirish (Waitlist boshqaruvi) — alohida doctype kerakmi?
5. Ota-ona portali: Frappe web forms yetadimi yoki alohida portal sahifalar kerakmi?
