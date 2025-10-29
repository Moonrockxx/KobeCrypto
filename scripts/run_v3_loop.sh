#!/usr/bin/env bash
# Kobe V3 runner (POSTE 2): boucle 15m 07–21 UTC, logs journaliers, chargement secrets locaux.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

# 0) Python venv (non versionné)
if [ ! -d ".venv" ]; then
  /usr/bin/python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip -q install --upgrade pip >/dev/null
[ -f requirements.txt ] && pip -q install -r requirements.txt >/dev/null

# 1) Secrets optionnels (jamais commit): .secrets/kobe/*.env (clé=valeur)
load_env() { local f="$1"; [ -f "$f" ] || return 0
  while IFS= read -r line; do
    case "$line" in ''|\#*) continue ;; *=*) export "$line" ;;
    esac
  done < "$f"
}
load_env ".secrets/kobe/telegram.env"
load_env ".secrets/kobe/deepseek.env"

# 2) Config locale (non versionnée)
if [ ! -f "config.yaml" ] && [ -f "config.example.yaml" ]; then
  cp config.example.yaml config.yaml
fi

LOG_DAY="logs/runner_$(date -u +%F).log"

usage(){ cat <<EOF
Usage: $0 [--check|--run]
  --check  : exécute les vérifications (santé + 1 cycle scheduler) puis s'arrête
  --run    : lance la boucle 15m (07–21 UTC) via kobe.scheduler_run (recommandé)
EOF
}

case "${1:-}" in
  --check)
    echo "== CHECK: health =="
    python -m kobe.cli.health_v2 | tee -a "$LOG_DAY"
    echo "== CHECK: 1 cycle schedule =="
    python -m kobe.cli.schedule --once | tee -a "$LOG_DAY"
    echo "== CHECK terminé =="
    ;;
  --run)
    echo "== RUN: boucle V3 (voir $LOG_DAY) =="
    # README recommande caffeinate + module scheduler_run
    # Log horodaté; rotation quotidienne par nom de fichier.
    exec caffeinate -i bash -c 'python -m kobe.scheduler_run 2>&1 | ts "[%Y-%m-%d %H:%M:%S UTC]" | tee -a "'"$LOG_DAY"'"'
    ;;
  *)
    usage; exit 1;;
esac
