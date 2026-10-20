# Moodle 5.3 — production serverga o'rnatish ketma-ketligi

> Sana: 2026-10-19. Holat: **reja** — serverda hali bajarilmagan.
> Manba: moodledev.io/general/releases/5.3 (talablar), docs.moodle.org/503 (Apache/nginx,
> public papka), Moodle 5.1 public-root o'zgarishi.
> Bog'liq: `target_zenit/integrations/moodle.py`, `Moodle Settings` doctype.

## 0. Boshlang'ich shart: nima bor

| | Qiymat |
|---|---|
| Server | DigitalOcean droplet, **Ubuntu 24.04.4 LTS**, **2 vCPU / 3.8 GB RAM** (2 GB swap), disk 77 GB (60 GB bo'sh) |
| Frappe | **production** (supervisor + nginx + gunicorn :8000), `/home/frappe/frappe-bench`, OS user `frappe` |
| Sayt | `targetschool.erpcontrol.uz` (HTTPS, nginx :80/:443) |
| Frappe / ERPNext | v15.118 / v15.119 |
| Frappe bazasi | **MariaDB 10.11.14** |
| Redis | **:6379 band** (Frappe ishlatmoqda) |
| PHP | **o'rnatilmagan** |
| PostgreSQL | o'rnatilmagan (:5432 bo'sh) |
| Lokal farq | lokalda Ubuntu 22.04 + MariaDB 10.6; serverda 24.04 + 10.11 |
| Lokal (ishlayotgan) Moodle | 5.3+ (Build 20261013), `/opt/moodle`, web root `/opt/moodle/public`, PHP 8.3.35, Apache :8080 |

## 1. Eng muhim qaror: Moodle bazasi — PostgreSQL yoki MariaDB?

### Moodle 5.3 rasmiy talablari

| Baza | Minimal versiya |
|---|---|
| PostgreSQL | **17** |
| MariaDB | **11.4.0** |
| MySQL | 8.4 |
| MS SQL | 2019 |

PHP: minimal **8.3.0** (8.4 ham mayli), faqat 64-bit. `sodium` kengaytmasi majburiy,
`max_input_vars >= 5000`.

### Tahlil

**Tugun shu:** serverdagi MariaDB — **10.11.14**, Moodle 5.3 esa **11.4+** talab qiladi.
Ya'ni Frappe'ning bazasiga Moodle'ni "qo'shib qo'yish" imkoni yo'q. Uch yo'l bor:

| Yo'l | Nima bo'ladi | Xulosa |
|---|---|---|
| **A. MariaDB'ni 11.4'ga ko'tarish** | Bitta instansda ikkisi yashaydi, lekin **ishlab turgan ERP bazasi** 10.11 → 11.4 ga ko'chadi. Frappe v15 rasman 10.6-10.11 bilan sinovdan o'tgan; 11.4 — sinovsiz hudud. Moliya bazasi xatarga qo'yiladi. | **YO'Q** |
| **B. Ikkinchi MariaDB instansi (boshqa port)** | Bitta mashinada bir xil nomdagi ikki instans: `mysqld_multi`, ikki config, ikki data dir, `apt upgrade` ikkisiga ham tegadi. Chalkashlik yuqori, foyda yo'q. | Yo'q |
| **C. PostgreSQL 17 — alohida dvigatel** | Frappe'ning MariaDB'siga **umuman tegilmaydi**. PG 17 PGDG repodan toza o'rnatiladi, o'z porti (5432), o'z useri, o'z backupi. | **HA** |

**Qo'shimcha sabablar (C foydasiga):**

1. **Lokal/prod bir xil bo'ladi.** Lokalda PostgreSQL **17.11** allaqachon o'rnatilgan va
   ishlab turibdi (`pg_lsclusters`: 17/main online), Moodle 5.3 ham shu yerda ishlayapti —
   ya'ni lokal test muhiti prod bilan bir xil stackda bo'ladi. Serverda MariaDB'ga
   o'tsak, lokalda PG'da sinagan narsa prodda boshqacha xatoga uchraydi.
2. **"Ikki server" tamoyili.** Alohida dvigatel = eng kuchli izolyatsiya. Keyin Moodle'ni
   boshqa serverga ko'chirganda: `pg_dump` → yangi mashinada `pg_restore`, tamom.
   Frappe'ning bazasiga bu jarayonda hech kim tegmaydi.
3. **Texnik qulaylik.** Moodle MySQL/MariaDB'da `utf8mb4` + indeks uzunligi va qator
   o'lchami cheklovlariga uriladi (shuning uchun MariaDB'da `ROW_FORMAT`/
   `innodb_file_per_table` sozlashlari kerak). PostgreSQL'da bu muammolar yo'q.
4. **Narxi.** ~200-300 MB RAM va `pg_dump`/`psql` ni o'rganish. Boshqa xarajat yo'q.

### QAROR: **PostgreSQL 17**, Frappe'ning MariaDB 10.11'iga tegmaymiz.

## 1b. Resurs hisobi — bu server yetadimi?

Hozirgi holat: **3.8 GB RAM**, 1.6 GB Frappe stacki egallagan, **2.2 GB bo'sh**, 2 GB swap,
**2 vCPU**.

Moodle qo'shilgandan keyin taxminiy qo'shimcha yuk:

| Komponent | RAM |
|---|---|
| PHP-FPM (4 bola x ~100 MB) | ~400 MB |
| PostgreSQL 17 (shared_buffers 256 MB + ulanishlar) | ~400 MB |
| **Jami** | **~800 MB** |

Ya'ni 2.2 GB dan ~1.4 GB qoladi — **o'rnatish va API integratsiyasini sinash uchun yetadi.**

**Ammo ochiq aytish kerak:** 326 o'quvchi/o'qituvchi haqiqatan Moodle'da dars qila
boshlaganda (test topshirish, fayl yuklash, video) **2 vCPU** ikki tizimga yetmaydi —
PHP-FPM va gunicorn bir xil protsessorni talashadi, PostgreSQL va MariaDB bir xil page
cache'ni talashadi. Natijada Moodle sekinlashsa — bir vaqtda **moliya tizimi ham**
sekinlashadi, ya'ni xatar faqat o'quv jarayonida qolmaydi.

Shuning uchun tartib shunday:

1. **Hozir** — shu serverga o'rnatamiz, API sinovini o'tkazamiz, 2-3 kishida tekshiramiz.
   Yuk deyarli yo'q, muammo chiqmaydi.
2. **Haqiqiy foydalanishdan oldin** — ikki yo'ldan biri:
   - droplet'ni **4 vCPU / 8 GB** ga ko'tarish, yoki
   - Moodle'ni **alohida droplet**ga ko'chirish (afzal).

2-qoidalar to'plami (quyida) shu ko'chirishni arzon qiladi: PG dump ko'chiriladi, DNS
o'zgartiriladi, Frappe'da bitta maydon yangilanadi — kod umuman o'zgarmaydi.
Shuning uchun "keyin ikkita serverda yuritamiz" degan reja bugundan ta'minlanadi.

## 2. "Bitta serverda, lekin ikkita serverdek" qoidalari

Hozir ikkisi bir mashinada turadi, ammo **birorta ham umumiy resurs bo'lmaydi**.
Keyinchalik ajratganda faqat DNS va bitta sozlama o'zgaradi.

| # | Qoida | Amalda |
|---|---|---|
| 1 | **Faqat HTTPS API orqali gaplashadi** | Frappe'dagi `Moodle Settings.base_url` = `https://moodle.erpcontrol.uz` — **`localhost` emas, port emas, unix socket emas**. Ajratganda shu bitta maydon o'zgaradi, kod o'zgarmaydi. |
| 2 | **Umumiy baza yo'q** | Moodle — PostgreSQL (`moodle` DB, `moodleuser`), Frappe — MariaDB. Hech qachon biridan ikkinchisiga to'g'ridan-to'g'ri SQL yozilmaydi. `moodleuser` faqat `moodle` bazasiga huquqli. |
| 3 | **Umumiy fayl tizimi yo'q** | `moodledata` → `/var/moodledata` (bench daraxtidan tashqarida). `frappe` useri Moodle fayllarini o'qiy olmaydi, `www-data` Frappe saytlarini o'qiy olmaydi. Fayl almashinuvi faqat HTTP orqali. |
| 4 | **Umumiy OS user yo'q** | Moodle: `www-data` (php-fpm). Frappe: `frappe`. Bir-birining guruhiga qo'shilmaydi. |
| 5 | **nginx konfigi alohida faylda** | `bench` yaratgan konfig **qo'l bilan tahrirlanmaydi** (`bench setup nginx` uni qayta yozadi). Moodle uchun alohida `/etc/nginx/conf.d/moodle.conf` + alohida sertifikat. |
| 6 | **Cron alohida** | Moodle cron — tizim croni, `www-data` nomidan, har daqiqa. Frappe scheduler — supervisor ostida, `frappe` nomidan. Biri ikkinchisini chaqirmaydi. |
| 7 | **Redis alohida** | **:6379 ni Frappe egallagan** — Moodle unga ulanmaydi. Moodle standart **fayl keshida** ishlaydi; kerak bo'lsa keyin o'z instansi (:6380) beriladi. |
| 8 | **Backup alohida** | `pg_dump` + `moodledata` arxivi, o'z jadvali bilan. `bench backup` Moodle'ni bilmaydi va bilmasligi kerak. |
| 9 | **Autentifikatsiya haqiqiy** | Moodle WS tokeni Frappe'da `Password` maydonida. Token egasi — cheklangan `frappe.sync` useri, admin emas. Bugun ham xuddi tashqi tizim bilan gaplashayotgandek. |

**Lokal bilan bitta muhim farq:** lokalda Moodle **Apache** :8080 da turibdi. Serverda
Apache'ni ko'tarmaymiz — u nginx bilan :80/:443 uchun urishib qoladi. Serverda Moodle
**nginx + PHP-FPM** da ishlaydi.

## 3. O'rnatish ketma-ketligi

> **QAROR (2026-10-20): subdomen tayyor — `moodle.erpcontrol.uz` → `159.89.151.163`**
> (`targetschool.erpcontrol.uz` bilan **bitta IP**, nginx `server_name` bo'yicha ajratadi).
> Moodle birinchi marta to'g'ri nom bilan o'rnatiladi: vaqtinchalik 8081 porti va
> keyinchalik `wwwroot` ni almashtirish **bo'lmaydi**. 7-qadamdagi port varianti faqat
> zaxira reja sifatida hujjatda qoldirildi.
>
> Tekshirilgan (2026-10-20): DNS tarqalgan, :80 ochiq va noma'lum nomga 404 qaytaradi
> (certbot HTTP-01 o'tadi), :443 da hozir faqat `targetschool` sertifikati bor.
>
> **2-qadam (DNS) bajarilgan.** Qolgan tartib: 0, 1, 3, 4, 5, 6, 7, 8, 9-13 —
> ketma-ket, har birining oxiridagi tekshiruv o'tmasa keyingisiga o'tilmaydi.


### 0-qadam. Inventarizatsiya (serverda, faqat o'qish)

Avval serverda nima borligini aniq bilib olamiz — ayniqsa **RAM**, chunki Moodle +
PHP-FPM + PostgreSQL Frappe'ning yonida turadi:

```bash
lsb_release -ds; nproc; free -h; df -h /
php -v 2>/dev/null || echo "php yo'q"
mysql --version
systemctl is-active nginx supervisor
nginx -T 2>/dev/null | grep -E 'server_name|listen|include' | head -40
ls /etc/nginx/conf.d/ /etc/nginx/sites-enabled/
ss -lntp | grep -E ':80|:443|:3306|:5432|:6379|:11000'
```

Natijaga qarab: RAM < 4 GB bo'lsa swap yoki droplet kattalashtirish kerak bo'ladi.

### 1-qadam. Sug'urta

```bash
# Frappe bazasi (bench o'zi biladi)
cd /home/frappe/frappe-bench && bench --site targetschool.erpcontrol.uz backup --with-files
```
Va **DigitalOcean snapshot** — PHP/PG o'rnatish tizim paketlariga tegadi, orqaga yo'l kerak.

### 2-qadam. DNS — **bajarilgan**

`moodle.erpcontrol.uz` → `159.89.151.163` (A yozuv), `targetschool.erpcontrol.uz` bilan
bitta IP. Tasdiq: `getent ahostsv4 moodle.erpcontrol.uz`.
**Yangi IP sotib olish kerak bo'lmadi** — bitta IP cheksiz domenga xizmat qiladi, nginx
ularni `Host:` sarlavhasi (`server_name`) bo'yicha ajratadi, HTTPS'da SNI orqali.

### 3-qadam. PHP 8.3 + kengaytmalar

Server **Ubuntu 24.04**, uning standart PHP'si **8.3** — Moodle 5.3 talabiga to'g'ri keladi,
ya'ni `ondrej/php` PPA **kerak emas** (bu lokaldagi 22.04 dan farqi):

```bash
sudo apt update
sudo apt install -y php8.3-fpm php8.3-cli php8.3-pgsql php8.3-curl php8.3-gd \
  php8.3-intl php8.3-mbstring php8.3-soap php8.3-xml php8.3-zip php8.3-opcache
```
`sodium`, `iconv`, `openssl`, `tokenizer`, `simplexml`, `dom`, `ctype`, `zlib`, `exif`
asosiy paketga kiradi — `php -m` bilan tekshiriladi (lokalda hammasi bor).

`/etc/php/8.3/fpm/conf.d/99-moodle.ini`:
```ini
max_input_vars = 5000        ; Moodle majburiy talabi
memory_limit = 256M
post_max_size = 100M
upload_max_filesize = 100M
max_execution_time = 300
opcache.enable = 1
opcache.memory_consumption = 128
```

**Diqqat — bu serverda RAM tanqis (3.8 GB, 1.6 GB Frappe egallagan).** PHP-FPM pool'i
qattiq cheklanadi, bo'lmasa gunicorn/MariaDB OOM'ga uchraydi.
`/etc/php/8.3/fpm/pool.d/www.conf`:

```ini
pm = dynamic
pm.max_children = 4          ; 2 vCPU / 3.8 GB uchun; bola ~100 MB
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 2
pm.max_requests = 500        ; xotira oqishini kesib tashlaydi
```

### 4-qadam. PostgreSQL 17

```bash
# PGDG repo (Ubuntu 22.04 da standart PG — 14, bizga 17 kerak)
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
  https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt update && sudo apt install -y postgresql-17

# Faqat localhost'da tinglaydi (hozir shart, keyin ham shunday qoladi)
sudo -u postgres psql -c "SHOW listen_addresses;"

# Baza va user — parolni o'zing qo'yasan
sudo -u postgres psql <<'SQL'
CREATE USER moodleuser WITH PASSWORD 'KUCHLI_PAROL';
CREATE DATABASE moodle WITH OWNER moodleuser ENCODING 'UTF8'
  LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;
SQL
```
`moodleuser` boshqa hech qaysi bazaga huquq olmaydi — 2-qoida.

**Diqqat:** Ubuntu 24.04 standart PostgreSQL'i — 16, bizga **17** kerak, shuning uchun
PGDG repo baribir qo'shiladi.

Kichik RAM uchun sozlash (`/etc/postgresql/17/main/conf.d/99-moodle.conf`):
```ini
shared_buffers = 256MB       # MariaDB bilan page cache uchun urishmasin
work_mem = 8MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
max_connections = 50         # PHP-FPM 4 bola uchun yetarlidan ortiq
```

### 5-qadam. Moodle kodi

```bash
sudo git clone --branch MOODLE_503_STABLE --depth 1 \
  https://github.com/moodle/moodle.git /opt/moodle
sudo chown -R root:www-data /opt/moodle
sudo find /opt/moodle -type d -exec chmod 755 {} \;
sudo find /opt/moodle -type f -exec chmod 644 {} \;
```
Kod `root` ga tegishli, `www-data` faqat o'qiydi — web orqali kod o'zgartirilmaydi.

### 6-qadam. moodledata (web rootdan TASHQARIDA)

```bash
sudo mkdir -p /var/moodledata
sudo chown www-data:www-data /var/moodledata
sudo chmod 0770 /var/moodledata
```

### 7-qadam. nginx — alohida vhost

**1-yo'l (tanlangan):** subdomen tayyor bo'ladi, shuning uchun to'g'ridan-to'g'ri
`listen 443 ssl` + `server_name moodle.erpcontrol.uz` bilan quriladi — quyidagi nginx bloki
`listen 8081; server_name _;` o'rniga shunday bo'ladi:

```nginx
server {
    listen 80;
    server_name moodle.erpcontrol.uz;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name moodle.erpcontrol.uz;
    # ... qolgan hammasi (root, location bloklari) pastdagidek
}
```
So'ng `sudo certbot --nginx -d moodle.erpcontrol.uz` sertifikatni qo'yadi.
**Yangi IP kerak emas** — Frappe bilan bitta IP va bitta 443 portida yashaydi, nginx
ularni `server_name` (ya'ni `Host:` sarlavhasi) bo'yicha ajratadi.

---

**Zaxira reja (subdomen kechikib qolsa) — port bilan ikki bosqich:**

| | A bosqich (hozir) | B bosqich (subdomen kelganda) |
|---|---|---|
| Manzil | `http://SERVER_IP:8081` | `https://moodle.erpcontrol.uz` |
| nginx | `listen 8081` | `listen 443 ssl` qo'shiladi |
| Sertifikat | yo'q | certbot |
| Kim kiradi | faqat sen (ufw/DO firewall bilan IP cheklangan) | hamma |

**Port tanlovi: 8081.** Band portlar: 80, 443 (nginx), 3306 (MariaDB), 6379 (Redis),
8000 (gunicorn), 9000 (frappe socketio). 8081 bo'sh — o'rnatishdan oldin
`ss -lntp | grep 8081` bilan tasdiqlanadi.

**Moodle 5.1+ dan web root `/opt/moodle/public`** (kod ildizi emas!). Yangi fayl:
`/etc/nginx/conf.d/moodle.conf`

```nginx
server {
    listen 8081;
    server_name _;                 # bu portda faqat Moodle turadi

    root /opt/moodle/public;       # DIQQAT: /opt/moodle EMAS
    index index.php;

    client_max_body_size 100M;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~ [^/]\.php(/|$) {
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param PATH_INFO $fastcgi_path_info;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    }

    location ~ /\.(git|ht) { deny all; }
}
```

Tekshirish: `sudo nginx -t` → `sudo systemctl reload nginx`.
**Frappe'ning konfigi tahrirlanmaydi** — bu butunlay alohida fayl va alohida port.

**Xavfsizlik (A bosqich uchun majburiy):** 8081 da HTTPS yo'q, ya'ni admin paroli
ochiq matnda ketadi. Shuning uchun port butun internetga ochilmaydi — faqat o'z IP'ingga:

```bash
sudo ufw status                                   # ufw faolmi?
sudo ufw allow from <SENING_IP> to any port 8081 proto tcp
```

ufw o'chirilgan bo'lsa, shu qoida DigitalOcean Cloud Firewall'da qo'yiladi.
Frappe → Moodle chaqiruvlari shu mashinaning o'zida qoladi (tashqariga chiqmaydi),
ya'ni token tinglanish xatari yo'q.

**B bosqichda nima o'zgaradi** (subdomen kelganda):
1. `moodle.conf` ga `listen 443 ssl` + `server_name moodle.erpcontrol.uz` bloki qo'shiladi
2. `sudo certbot --nginx -d moodle.erpcontrol.uz`
3. `/opt/moodle/config.php` da `$CFG->wwwroot = 'https://moodle.erpcontrol.uz';`
4. `sudo -u www-data php8.3 /opt/moodle/admin/cli/purge_caches.php`
5. Frappe'da `Moodle Settings.base_url` → `https://moodle.erpcontrol.uz`
6. 8081 porti yopiladi

Hozir Moodle'da haqiqiy kontent yo'q, shuning uchun `wwwroot` ni keyin o'zgartirish
xatarsiz — kontent ichidagi havolalar hali yozilmagan.

### 8-qadam. Moodle CLI o'rnatish

`--wwwroot` **`/public` bilan tugamaydi** (Moodle buni xato deb hisoblaydi).
A bosqichda u port bilan beriladi — `SERVER_IP` o'rniga haqiqiy IP yoziladi:

```bash
cd /opt/moodle
sudo -u www-data php admin/cli/install.php \
  --lang=en \
  --wwwroot=https://moodle.erpcontrol.uz \
  --dataroot=/var/moodledata \
  --dbtype=pgsql \
  --dbhost=127.0.0.1 \
  --dbname=moodle \
  --dbuser=moodleuser \
  --dbpass='KUCHLI_PAROL' \
  --fullname="Target xususiy maktabi" \
  --shortname="Target" \
  --adminuser=admin \
  --adminpass='KUCHLI_ADMIN_PAROL' \
  --adminemail=admin@target.uz \
  --agree-license \
  --non-interactive
```

So'ng config.php ni qulflash (lokalda ham shunday: `root:www-data 0640`):
```bash
sudo chown root:www-data /opt/moodle/config.php
sudo chmod 0640 /opt/moodle/config.php
```

### 9-qadam. Moodle cron (Frappe scheduler'dan mustaqil)

```bash
echo '* * * * * www-data /usr/bin/php8.3 /opt/moodle/admin/cli/cron.php >/dev/null 2>&1' \
  | sudo tee /etc/cron.d/moodle
sudo chmod 644 /etc/cron.d/moodle
```
Moodle croni **har daqiqa** ishlashi kerak (navbat, xabarnoma, baho qayta hisoblash).
Bu Frappe'ning 07:00 cronidan butunlay boshqa narsa.

### 10-qadam. Web service (API) sozlash

Brauzerda, `https://moodle.erpcontrol.uz/admin`:

1. `Advanced features` → ✓ **Enable web services**
2. `Server → Web services → Manage protocols` → **REST protocol** yoqiladi
3. `Define roles → Add a new role` — arxetipsiz, context: **System**, nomi `Frappe Sync`:
   `webservice/rest:use`, `moodle/user:create`, `moodle/user:update`,
   `moodle/user:viewalldetails`, `moodle/user:viewdetails`
4. Yangi user `frappe.sync` (Manual accounts) + shu rolni system darajada berish
5. `External services → Add`: `Frappe Sync` / `frappe_sync`, ✓ Enabled,
   ✓ **Authorised users only**. Funksiyalar:
   `core_webservice_get_site_info`, `core_user_get_users_by_field`,
   `core_user_create_users`, `core_user_update_users`
6. `Authorised users` → `frappe.sync`
7. `Manage tokens → Add` → token olinadi
8. `Plugins → Authentication → Manual accounts` → `firstname`, `lastname`, `email`,
   `idnumber` → **Locked** (Frappe yagona manba, 1-qoida)

### 11-qadam. Frappe tomonini ulash

`Moodle Settings` da:
- Moodle manzili: `https://moodle.erpcontrol.uz` — **`localhost` yozilmaydi** (1-qoida:
  bir mashinada bo'lsa ham tashqi manzil orqali gaplashadi, ajratganda kod o'zgarmaydi)
- Token: 10-qadamdan
- ✓ Yoqilgan, ✓ **Test rejimi** (dastlab)

So'ng: `Ulanishni tekshirish` → `Hozir sinxronlash` (test rejimida) → `Moodle Sync Log`
ni o'qish → hammasi joyida bo'lsa test rejimini o'chirib haqiqiy sinxron.

Avto sinxron: Frappe scheduler, cron `0 7 * * *` → `moodle.daily_sync()` (kod tayyor).

### 12-qadam. Backup

```bash
# /etc/cron.d/moodle-backup — har kuni 02:30
30 2 * * * root pg_dump -U moodleuser -h 127.0.0.1 moodle | gzip > /var/backups/moodle/db-$(date +\%F).sql.gz
40 2 * * * root tar czf /var/backups/moodle/data-$(date +\%F).tar.gz /var/moodledata
```
Frappe backupidan **alohida** jadval, alohida joy — 8-qoida.

### 13-qadam. "Ikki server" intizomini tekshirish

O'rnatish tugagach shu ro'yxat bo'yicha o'tiladi:

- [ ] `Moodle Settings.base_url` = `https://moodle.erpcontrol.uz` (`localhost` yoki port **yo'q**)
- [ ] Frappe kodida Moodle bazasiga to'g'ridan-to'g'ri ulanish **yo'q** (faqat `moodle.py` HTTP)
- [ ] `moodleuser` faqat `moodle` bazasiga huquqli
- [ ] `frappe` useri `/opt/moodle` va `/var/moodledata` ni o'qiy olmaydi
- [ ] `bench` yaratgan nginx konfigi tahrirlanmagan
- [ ] Moodle Redis'ga ulanmagan yoki o'z instansida
- [ ] Moodle backupi alohida ishlaydi va tiklanishi sinalgan

Shu ro'yxat o'tsa, Moodle'ni boshqa serverga ko'chirish = PG dump ko'chirish + DNS
o'zgartirish + Frappe'da bitta maydonni yangilash.

## 4. Keyingi bosqichlar (hozir emas)

1. Kurs va sinf (cohort) sinxroni — `Student Group` (80 guruh) → Moodle cohort
2. Kursga yozish (enrolment) — `enrol_manual_enrol_users`
3. Bahoni Moodle'dan Frappe'ga qaytarish (teskari yo'nalish, faqat o'qish)
4. SSO — Frappe'ni OAuth2 provider qilib, bitta parol bilan kirish
