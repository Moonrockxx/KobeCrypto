from __future__ import annotations
import argparse
import sys
import yaml
from pathlib import Path

from kobe.core.scheduler import build_scheduler, run_news_job
from kobe.core.notify import Notifier, TelegramConfig
from kobe.core.factors import get_market_snapshot
from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import format_proposal_for_telegram
from kobe.core.journal import log_proposal
from apscheduler.triggers.interval import IntervalTrigger
from pytz import UTC

def load_cfg(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(
            "❌ Fichier config.yaml manquant. Copie d'abord config.example.yaml → config.yaml et renseigne Telegram."
        )
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_auto_proposal_job(symbol: str = "BTCUSDT"):
    """Génère automatiquement une proposal à partir des facteurs mock et la log si valide (silencieux Telegram)."""
    snapshot = get_market_snapshot(symbol)
    p = generate_proposal_from_factors(snapshot)
    if not p:
        print("⚙️  Aucun signal auto détecté.")
        return
    log_proposal(p.model_dump())
    msg = format_proposal_for_telegram(p, balance_usd=10000.0, leverage=2.0)
    print(msg)

def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="kobe schedule",
        description="KobeCrypto V1 — Scheduler principal (veille actus + signaux trades)",
    )
    parser.add_argument("--once", action="store_true", help="Exécuter une seule fois (debug mode)")
    parser.add_argument("--config", default="config.yaml", help="Chemin vers le fichier config")
    args = parser.parse_args(argv)

    cfg = load_cfg(args.config)
    tg_cfg = cfg.get("telegram", {})
    scheduler_cfg = cfg.get("scheduler", {})
    news_cfg = cfg.get("news", {})

    feeds = news_cfg.get("feeds", [])
    keywords = news_cfg.get("keywords_any", [])
    max_items = news_cfg.get("max_items_per_run", 6)
    enabled_hours_utc = scheduler_cfg.get("enabled_hours_utc", list(range(7,22)))
    interval_minutes = scheduler_cfg.get("interval_minutes", 15)

    # Création Notifier si token renseigné (sinon None)
    notifier = None
    if tg_cfg.get("bot_token") and not tg_cfg["bot_token"].startswith("YOUR_"):
        notifier = Notifier(TelegramConfig(**tg_cfg))
        print("✅ Mode Telegram actif (token détecté)")
    else:
        print("ℹ️ Mode console (aucun token Telegram renseigné)")

    if args.once:
        run_news_job(
            feeds, keywords, max_items, enabled_hours_utc,
            notifier, use_telegram_for_news=False
        )
        return 0

    # Scheduler pour news + job auto_proposal
    sched = build_scheduler(
        interval_minutes, feeds, keywords, max_items, enabled_hours_utc,
        notifier, use_telegram_for_news=False
    )

    def _auto_job_wrapper():
        try:
            run_auto_proposal_job("BTCUSDT")
        except Exception as e:
            print(f"[auto_proposal_job] erreur: {e}")

    print("⚙️  Ajout du job auto_proposal (toutes les", interval_minutes, "min)")
    sched.add_job(
        _auto_job_wrapper,
        trigger=IntervalTrigger(minutes=interval_minutes, timezone=UTC),
        id="auto-proposal",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    print("⏱️ Scheduler lancé — fenêtre UTC:", enabled_hours_utc, f"(toutes les {interval_minutes} min)")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Scheduler arrêté manuellement.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
