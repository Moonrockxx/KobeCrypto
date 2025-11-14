#!/usr/bin/env bash
set -euo pipefail

# Paramètres tunables (avec valeurs par défaut)
export SCAN_INTERVAL_MIN="${SCAN_INTERVAL_MIN:-10}"
export COOLDOWN_MIN="${COOLDOWN_MIN:-30}"
export HEARTBEAT_MIN="${HEARTBEAT_MIN:-60}"
export TELEGRAM_DRYRUN="${TELEGRAM_DRYRUN:-0}"

# Fichiers runtime (LOG dans $HOME, PID/LOCK en /tmp)
LOG="${HOME}/kobe_runner.log"
PID="/tmp/kobe_runner.pid"
LOCK="/tmp/kobe_runner.lock"

# Mode debug : un seul tick, pas de pid/lock, pas de background
if [[ "${1:-}" == "--once" ]]; then
  echo "Mode --once : exécution unique de kobe.cli.schedule"
  exec python3 -u -m kobe.cli.schedule --once
fi

# Nettoyage d’un lock orphelin éventuel
[ -f "$LOCK" ] && rm -f "$LOCK" || true

# Single-instance guard via PID
if [ -f "$PID" ]; then
  OLD_PID="$(cat "$PID" 2>/dev/null || echo "")"
  if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" -o pid= >/dev/null 2>&1; then
    echo "Runner déjà actif (PID=${OLD_PID}), sortie sans relancer."
    exit 0
  fi
fi

# Création du lock courant (optionnel, juste indicatif)
echo "$$" > "$LOCK"

# Lancement protégé contre la veille (ne pas enlever -u)
# Les notifs start/stop/crash sont gérées par kobe.cli.schedule
caffeinate -dimsu python3 -u -m kobe.cli.schedule >> "$LOG" 2>&1 & echo $! > "$PID"

echo "PID: $(cat "$PID")"
echo "LOG: $LOG"
