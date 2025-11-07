#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Activer venv si présent
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Charger secrets Telegram (jamais commités)
if [ -f ".secrets/kobe/telegram.env" ]; then
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue ;; *=*) export "$line" ;;
    esac
  done < .secrets/kobe/telegram.env
fi

# Paramètres SOP V4 (override via env)
export SCAN_INTERVAL_MIN="${SCAN_INTERVAL_MIN:-10}"
export COOLDOWN_MIN="${COOLDOWN_MIN:-30}"
export HEARTBEAT_MIN="${HEARTBEAT_MIN:-60}"
export TELEGRAM_DRYRUN="${TELEGRAM_DRYRUN:-0}"

# Fichiers runtime (LOG dans $HOME, PID/LOCK en /tmp)
LOG="${HOME}/kobe_runner.log"
PID="/tmp/kobe_runner.pid"
LOCK="/tmp/kobe_runner.lock"

# Nettoyage d’un lock orphelin
[ -f "$LOCK" ] && rm -f "$LOCK" || true

# Lancement protégé contre la veille (ne pas enlever -u)
# Les notifs start/stop/crash sont gérées par schedule.py
caffeinate -dimsu python3 -u -m kobe.cli.schedule >> "$LOG" 2>&1 & echo $! > "$PID"
echo "PID: $(cat "$PID")"
echo "LOG: $LOG"
