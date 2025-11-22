#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_DAY="$LOG_DIR/runner_$(date -u +%F).log"

[ -d .venv ] || /usr/bin/python3 -m venv .venv
source .venv/bin/activate
python3 -m pip -q install --upgrade pip >/dev/null 2>&1 || true

load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue ;; *=*) export "$line" ;; esac
  done < "$f"
}
load_env_file ".secrets/kobe/telegram.env"
load_env_file ".secrets/kobe/deepseek.env"

# Timestamp portable (macOS ok)
stamp() {
  while IFS= read -r line; do
    printf '[%s UTC] %s\n' "$(date -u '+%F %T')" "$line"
  done
}

case "${1:-}" in
  --check)
    echo "== CHECK: health + 1 cycle ==" | tee -a "$LOG_DAY"
    python3 -m kobe.cli.health_v2 2>&1 | stamp | tee -a "$LOG_DAY"
    python3 -m kobe.cli.schedule --once 2>&1 | stamp | tee -a "$LOG_DAY"
    ;;

  --run|*)
    echo "== RUN: boucle V3 (07–21 UTC) == (voir $LOG_DAY)" | tee -a "$LOG_DAY"
    while true; do
      H=$(date -u +"%H")
      if [ "$H" -ge 7 ] && [ "$H" -le 21 ]; then
        python3 -m kobe.scheduler_run 2>&1 | stamp | tee -a "$LOG_DAY"
      else
        echo "[${DATE:-$(date -u '+%F %T')} UTC] [Kobe] ⏭️ Hors 07–21 UTC" | tee -a "$LOG_DAY"
      fi
      sleep 900
    done
    ;;
esac
