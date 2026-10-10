#!/bin/bash
# Asterisk hangup handler'dan chaqiriladi. Qo'ng'iroq metadatasini navbatga
# JSON ko'rinishida yozadi.
#
# ⚠️ Bu skript Asterisk'ning qo'ng'iroq yo'lida ishlaydi — shu sababli
# ichida HTTP so'rov YO'Q. Tarmoq sekinlashsa Asterisk'ni ushlab qolmasligi
# kerak. Yuborishni alohida xizmat (yuklovchi.py) bajaradi.
#
# Argumentlar (dialplan'dan):
#   $1 uniqueid   $2 yonalish(outgoing|incoming)  $3 ichki_raqam  $4 tashqi_raqam
#   $5 sim_kanal  $6 boshlandi(epoch)  $7 javob_berildi(epoch, 0=javob yo'q)
#   $8 tugadi(epoch)  $9 suhbat_vaqti(s)  $10 dialstatus  $11 kim_tugatdi

set -u
CONF="${TELEFONIYA_CONF:-/etc/target-zenit-telefoniya.conf}"
[ -r "$CONF" ] && . "$CONF"
SPOOL="${SPOOL:-/var/spool/target-zenit-telefoniya}"

UNIQUEID="${1:-}"
[ -z "$UNIQUEID" ] && { logger -t telefoniya "uniqueid bo'sh — tashlab ketildi"; exit 1; }

mkdir -p "$SPOOL/nav"

# JSON qiymatlarini xavfsiz qochirish (qo'shtirnoq va teskari slash).
j() { printf '%s' "${1:-}" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

# epoch 0 yoki bo'sh bo'lsa JSON'da null bo'lsin.
e() { [ -n "${1:-}" ] && [ "${1:-0}" != "0" ] && printf '"%s"' "$1" || printf 'null'; }

TMP="$SPOOL/nav/.$UNIQUEID.json.tmp"
cat > "$TMP" <<JSON
{
  "uniqueid": "$(j "$UNIQUEID")",
  "yonalish": "$(j "${2:-outgoing}")",
  "ichki_raqam": "$(j "${3:-}")",
  "tashqi_raqam": "$(j "${4:-}")",
  "sim_kanal": "$(j "${5:-}")",
  "boshlandi": $(e "${6:-}"),
  "javob_berildi": $(e "${7:-}"),
  "tugadi": $(e "${8:-}"),
  "suhbat_vaqti": "${9:-0}",
  "tugash_sababi": "$(j "${10:-}")",
  "kim_tugatdi": "$(j "${11:-}")"
}
JSON

# Atomar ko'chirish: yuklovchi yarim yozilgan JSON'ni o'qib qolmasin.
mv -f "$TMP" "$SPOOL/nav/$UNIQUEID.json"
logger -t telefoniya "metadata navbatga qo'yildi: $UNIQUEID"
