#!/bin/bash
# MixMonitor post-process orqali chaqiriladi — yozuv fayli YOPILGANIDAN keyin.
# Xom stereo WAV'ni MP3'ga siqib navbatga qo'yadi.
#
# Argument: $1 = xom WAV fayl nomi (MixMonitor bergan), $2 = uniqueid

set -u
CONF="${TELEFONIYA_CONF:-/etc/target-zenit-telefoniya.conf}"
[ -r "$CONF" ] && . "$CONF"
SPOOL="${SPOOL:-/var/spool/target-zenit-telefoniya}"
XOM="${XOM:-/var/spool/asterisk/monitor}"
MP3_BITRATE="${MP3_BITRATE:-48k}"

WAV="${1:-}"
UNIQUEID="${2:-}"
[ -z "$UNIQUEID" ] && { logger -t telefoniya "yozuv: uniqueid bo'sh"; exit 1; }

# MixMonitor faqat fayl nomini berishi mumkin — to'liq yo'lga keltiramiz.
case "$WAV" in
	/*) ;;
	*) WAV="$XOM/$WAV" ;;
esac

[ -f "$WAV" ] || { logger -t telefoniya "yozuv topilmadi: $WAV"; exit 1; }

mkdir -p "$SPOOL/nav"
TMP="$SPOOL/nav/.$UNIQUEID.mp3.tmp"
MP3="$SPOOL/nav/$UNIQUEID.mp3"

# -ac 2 : stereo saqlanadi (chap=menejer, o'ng=mijoz) — diarizatsiya uchun shart.
# -ar 16000 : 16 kHz, telefon audiosi uchun yetarli va STT shuni kutadi.
# -f mp3 : chiqish fayli ".tmp" kengaytmasi bilan atomar yoziladi, shuning
# uchun ffmpeg formatni nomidan aniqlay olmaydi — aniq ko'rsatiladi.
if ffmpeg -nostdin -loglevel error -y -i "$WAV" \
	-ac 2 -ar 16000 -codec:a libmp3lame -b:a "$MP3_BITRATE" -f mp3 "$TMP"; then
	mv -f "$TMP" "$MP3"
	rm -f "$WAV"
	logger -t telefoniya "yozuv navbatga qo'yildi: $UNIQUEID ($(stat -c%s "$MP3") bayt)"
else
	rm -f "$TMP"
	logger -t telefoniya "ffmpeg xatosi: $WAV"
	exit 1
fi
