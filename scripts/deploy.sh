#!/usr/bin/env bash
# target_zenit production deploy — idempotent, qulflangan, rollback'li
set -Eeuo pipefail
exec </dev/null   # stdin orqali kelganda buyruqlar stdin'ni "yeb" qo'ymasin

# --- Sozlamalar (workflow env orqali beradi, defaultlar bor) ---
APP="target_zenit"
SITE="${SITE_NAME:?XATO: SITE_NAME berilmagan}"
BENCH_DIR="${BENCH_DIR:-/home/frappe/frappe-bench}"
BRANCH="${DEPLOY_BRANCH:-main}"
HEALTH_URL="${HEALTH_URL:-https://${SITE}/api/method/ping}"
LOCK_FILE="/tmp/deploy-${APP}.lock"
LOG_DIR="$HOME/deploy-logs"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
echo "=== Deploy boshlandi: $(date -Is) | site=$SITE branch=$BRANCH ==="

# --- bench PATH muammosi: non-interactive SSH'da ~/.local/bin PATH'da bo'lmaydi ---
if command -v bench >/dev/null; then BENCH=$(command -v bench)
elif [ -x "$HOME/.local/bin/bench" ]; then BENCH="$HOME/.local/bin/bench"
else echo "XATO: bench topilmadi"; exit 1; fi

# --- Fresh-install qo'riqchisi ---
[ -d "$BENCH_DIR/apps/$APP/.git" ] || { echo "XATO: $BENCH_DIR/apps/$APP yo'q — bu workflow faqat YANGILASH uchun"; exit 1; }
[ -d "$BENCH_DIR/sites/$SITE" ]    || { echo "XATO: sayt topilmadi: $SITE. Mavjudlari:"; ls "$BENCH_DIR/sites"; exit 1; }

# --- Qulf: parallel deploy bloklanadi ---
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "XATO: boshqa deploy hozir ketyapti"; exit 1; }

cd "$BENCH_DIR/apps/$APP"

# --- Joriy holatni eslab qolish (rollback uchun) ---
PREV_COMMIT=$(git rev-parse HEAD)
REMOTE=$(git remote | head -1)
git fetch "$REMOTE" "$BRANCH"
NEW_COMMIT=$(git rev-parse "$REMOTE/$BRANCH")
if [ "$PREV_COMMIT" = "$NEW_COMMIT" ]; then
    echo "Yangi commit yo'q ($PREV_COMMIT). Deploy shart emas."
    exit 0
fi
echo "Yangilanish: $PREV_COMMIT -> $NEW_COMMIT"

BACKUP_INFO="(backup hali olinmagan edi)"

# --- Rollback ---
rollback() {
    trap - ERR
    echo "!!! XATO — kod eski holatga qaytarilmoqda: $PREV_COMMIT"
    cd "$BENCH_DIR/apps/$APP"
    git reset --hard "$PREV_COMMIT"
    cd "$BENCH_DIR"
    ./env/bin/pip install -q -e "apps/$APP" || true
    "$BENCH" build --app "$APP" || true
    "$BENCH" restart || true
    echo "!!! Kod qaytarildi. DIQQAT: migrate qisman o'tgan bo'lsa, DB'ni"
    echo "!!! qo'lda tiklash kerak bo'lishi mumkin. Backup: $BACKUP_INFO"
    echo "=== Deploy MUVAFFAQIYATSIZ: $(date -Is) ==="
    exit 1
}
trap rollback ERR

# --- Kodni yangilash (pull EMAS — serverdagi tasodifiy o'zgarish konflikt bermasin) ---
git reset --hard "$REMOTE/$BRANCH"
cd "$BENCH_DIR"

# --- Python dependency'lar ('|| true' YO'Q — xato bo'lsa yiqilsin) ---
./env/bin/pip install -q --upgrade -e "apps/$APP"

# --- Frontend assets ---
"$BENCH" build --app "$APP"

# --- Migratedan OLDIN DB backup (rollback sug'urtasi) ---
BACKUP_INFO=$("$BENCH" --site "$SITE" backup --compress | tail -5)
echo "Backup tayyor: $BACKUP_INFO"

# --- Migrate (v15 o'zi bench_migrate filelock oladi, cache'ni o'zi tozalaydi) ---
"$BENCH" --site "$SITE" migrate

# --- Restart: faqat SHU bench'ning web+workers guruhlari (restart all EMAS) ---
"$BENCH" restart

# --- Health check: o'tmasa — bu ham xato, rollback ---
trap - ERR
sleep 8
for i in 1 2 3; do
    if curl -fsS --max-time 10 "$HEALTH_URL" | grep -q "pong"; then
        echo "Health check OK"
        echo "=== Deploy MUVAFFAQIYATLI: $(date -Is) — $NEW_COMMIT ==="
        exit 0
    fi
    echo "Health check $i-urinish o'tmadi, 10s kutilmoqda..."
    sleep 10
done
echo "!!! Sayt javob bermayapti"
rollback
