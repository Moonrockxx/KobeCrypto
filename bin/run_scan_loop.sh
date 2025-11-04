#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

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
  local now_utc target_utc sleep_s today_0700 next_0700
  now_utc=$(date -u +%s)
  today_0700=$(date -u -d "$(date -u +%F) 07:00:00" +%s 2>/dev/null || true)
  if [ -z "${today_0700:-}" ]; then
    today_0700=$(python - <<'PY'
import datetime, time
u=datetime.datetime.utcnow()
t=datetime.datetime(u.year,u.month,u.day,7,0,0)
print(int(t.timestamp()))
PY
)
  fi
  if [ "$now_utc" -lt "$today_0700" ]; then next_0700="$today_0700"; else next_0700=$(( today_0700 + 86400 )); fi
  sleep_s=$(( next_0700 - now_utc ))
  sleep "$sleep_s"
}

echo "[runner] start $(date -u '+%F %T') UTC" | tee -a "$log_file"

align_to_next_quarter

while true; do
  hour_utc=$(date -u +%H)
  if [ "$hour_utc" -ge 07 ] && [ "$hour_utc" -lt 21 ]; then
    ts="$(date -u '+%F %T')"
    echo "[runner] tick $ts UTC → scan_once_v3" | tee -a "$log_file"
    python -m kobe.cli.scan_once_v3 --once >>"$log_file" 2>&1 || \
      echo "[runner] WARN $(date -u '+%F %T') scan_once_v3 exit non-zero" | tee -a "$log_file"
    align_to_next_quarter
  else
    echo "[runner] hors plage (07–21 UTC). Dodo jusqu'à 07:00 UTC…" | tee -a "$log_file"
    sleep_until_0700_utc
    align_to_next_quarter
  fi
done
