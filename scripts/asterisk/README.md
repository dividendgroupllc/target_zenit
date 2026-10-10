# Telefoniya — Asterisk tomoni

Bu papkadagi fayllar **Asterisk serverida** (maktabdagi kompyuter) ishlaydi.
Frappe tomoni `target_zenit/telefoniya/` da.

## Ma'lumot oqimi

```
GoIP-4 ──SIP──> Asterisk ──> MixMonitor (stereo WAV)
                   │
                   ├─ qo'ng'iroq tugadi ──> qongiroq_tugadi.sh ──> navbat/*.json
                   └─ yozuv yopildi ──────> yozuvni_tayyorla.sh ──> navbat/*.mp3
                                                                      │
                            yuklovchi.py (systemd timer, 30s) ────────┘
                                   │ HTTPS POST
                                   ▼
                    Frappe: telefoniya.api.ingest_call
```

**Nega navbat orqali:** Asterisk'ning qo'ng'iroq yo'lida HTTP so'rov qilish mumkin
emas — tarmoq sekinlashsa telefoniya ushlanib qoladi. Shuning uchun ma'lumot
diskdagi navbatga yoziladi, yuborishni alohida xizmat bajaradi. Natijada
internet bir hafta uzilsa ham bitta yozuv yo'qolmaydi.

## O'rnatish

### 1. Kerakli paketlar
```bash
sudo apt install asterisk ffmpeg python3
```
`yuklovchi.py` faqat standart kutubxonadan foydalanadi — `pip install` kerak emas.

### 2. Skriptlarni joylash
```bash
sudo install -m 755 qongiroq_tugadi.sh    /usr/local/bin/
sudo install -m 755 yozuvni_tayyorla.sh   /usr/local/bin/
sudo install -m 755 yuklovchi.py          /usr/local/bin/telefoniya-yuklovchi
```

### 3. Sozlama
```bash
sudo cp telefoniya.conf.namuna /etc/target-zenit-telefoniya.conf
sudo chown asterisk:asterisk  /etc/target-zenit-telefoniya.conf
sudo chmod 600                /etc/target-zenit-telefoniya.conf
sudo nano                     /etc/target-zenit-telefoniya.conf   # CRM_URL va CRM_TOKEN
```
Fayl ichida API kaliti bor — `chmod 600` majburiy.

### 4. Navbat papkasi
```bash
sudo mkdir -p /var/spool/target-zenit-telefoniya/{nav,done,xato}
sudo chown -R asterisk:asterisk /var/spool/target-zenit-telefoniya
```

### 5. Yuklovchi xizmati
```bash
sudo cp telefoniya-yuklovchi.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telefoniya-yuklovchi.timer
systemctl list-timers telefoniya-yuklovchi.timer
```

### 6. Dialplan
```bash
sudo cp dialplan.namuna.conf /etc/asterisk/extensions_target_zenit.conf
# extensions.conf oxiriga:  #include extensions_target_zenit.conf
sudo asterisk -rx "dialplan reload"
```

## Frappe tomonida

1. **Foydalanuvchi:** yangi User, roli **Telefoniya Agent**.
   Settings → API Access → *Generate Keys* → `api_key:api_secret` ni
   `CRM_TOKEN` ga yozing.
2. **Sozlamalar:** `Telefoniya Sozlamalari` — saqlash muddati, SIM limiti,
   yozuvlar papkasi (bo'sh qoldirilsa `private/call-recordings` ishlatiladi).
3. **Menejerlar:** har bir `Employee` kartasida **Ichki telefon raqami**
   (101, 102 …) to'ldirilishi kerak — qo'ng'iroq menejerga shu orqali bog'lanadi.

## Tekshirish

```bash
# Navbatni qo'lda ishga tushirish (log ko'rinadi)
sudo -u asterisk TELEFONIYA_CONF=/etc/target-zenit-telefoniya.conf \
     /usr/local/bin/telefoniya-yuklovchi

# Navbat holati
ls -l /var/spool/target-zenit-telefoniya/nav    # yuborilmaganlar
ls -l /var/spool/target-zenit-telefoniya/xato   # muammoli — tekshirish kerak
journalctl -t telefoniya -n 50                  # Asterisk skriptlari logi
journalctl -u telefoniya-yuklovchi -n 50        # yuklovchi logi
```

## Muammolarni aniqlash

| Belgi | Sabab |
|---|---|
| `nav/` to'lib ketgan | CRM'ga ulanish yo'q. `CRM_URL`/`CRM_TOKEN` va tarmoqni tekshiring |
| `xato/` da fayllar | CRM ma'lumotni rad etgan (4xx). Yuklovchi logida sababi bor |
| MP3 yaratilmaydi | `ffmpeg` yo'q yoki `XOM` papkasi yozuvlarni ko'rmaydi |
| Qo'ng'iroq bor, yozuv yo'q | Dialplan'da `MixMonitor` chaqirilmagan, yoki javob berilmagan qo'ng'iroq (normal) |
| Yozuv mono | `MixMonitor(...,b,...)` dagi `b` yo'q. **Stereo majburiy** — "kim gapirdi" shunga bog'liq |

## Muhim eslatmalar

- **Stereo yozuvdan voz kechmang.** Chap kanal = menejer, o'ng = mijoz.
  Yozuv bir marta yoziladi; keyin stereoga o'tib bo'lmaydi.
- **SIM limiti.** Bitta SIM'ga kuniga 40-60 chiquvchi qo'ng'iroqdan oshmasin,
  aks holda operator SIM-box deb bloklaydi. Round-robin 3-bosqichda qo'shiladi.
- **Qonuniy ogohlantirish.** Suhbat yozilayotgani haqida ogohlantirish
  dialplan'da `Playback` bilan beriladi — "Shaxsiy ma'lumotlar to'g'risida"gi
  qonun talabi.
