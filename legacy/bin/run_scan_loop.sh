#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# venv
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# charge un .env style KEY=VAL en ignorant lignes vides et #commentaires
load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue ;; *=*) export "$line" ;;
    esac
  done < "$f"
}

load_env_file ".secrets/kobe/telegram.env"
load_env_file ".secrets/kobe/deepseek.env"

log_dir="logs"
mkdir -p "$log_dir"
log_file="$log_dir/runner.log"

align_to_next_quarter() {
  local now next sleep_s
  now=$(date -u +%s)
  next=$(( ((now/900)+1)*900 ))
  sleep_s=$(( next - now ))
  sleep "$sleep_s"
}

sleep_until_0700_utc() {
  # portable (sans GNU date -d)
  python - <<'PY'
import datetime, time, sys
u=datetime.datetime.utcnow()
today_7=datetime.datetime(u.year,u.month,u.day,7,0,0)
if u<today_7: delta=today_7-u
else: delta=(today_7+datetime.timedelta(days=1))-u
time.sleep(delta.total_seconds())
PY
}

echo "[runner] start $(date -u '+%F %T') UTC" | tee -a "$log_file"
align_to_next_quarter

while true; do
  hour_utc=$(date -u +%H)
  if [ "$hour_utc" -ge 07 ] && [ "$hour_utc" -lt 21 ]; then
    ts="$(date -u '+%F %T')"
    echo "[runner] tick $ts UTC → scan_once_v3" | tee -a "$log_file"
    python3 -m kobe.cli.scan_once_v3 --symbols BTCUSDC,ETHUSDC,SOLUSDC >>"$log_file" 2>&1 || \
      echo "[runner] WARN $(date -u '+%F %T') scan_once_v3 exit non-zero" | tee -a "$log_file"
    align_to_next_quarter
  else
    echo "[runner] hors plage (07–21 UTC). Dodo jusqu'à 07:00 UTC…" | tee -a "$log_file"
    sleep_until_0700_utc
    align_to_next_quarter
  fi
done
