from __future__ import annotations
import argparse, sys, os, atexit, signal, time
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote as _q
from urllib.request import urlopen

from kobe.core.scheduler import build_scheduler, run_news_job
from kobe.core.notify import Notifier, TelegramConfig
from kobe.core.factors import get_market_snapshot
from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import format_proposal_for_telegram
from kobe.core.journal import log_proposal
from kobe.core.risk import validate_proposal, RiskConfig
from kobe.core.trade_alerts import send_trade
from apscheduler.triggers.interval import IntervalTrigger
from pytz import UTC
from kobe.cli.report import run_report
from apscheduler.triggers.cron import CronTrigger

LOCK_PATH = "/tmp/kobe_runner.lock"
HEARTBEAT_MIN = int(os.getenv("HEARTBEAT_MIN", "60"))  # SOP V4: heartbeat optionnel 60'
TELEGRAM_DRYRUN = os.getenv("TELEGRAM_DRYRUN", "0") == "1"

def _now_utc():
    return datetime.now(timezone.utc)

def _tg_send_from_cfg(tg_cfg: dict, msg: str):
    bot = (tg_cfg or {}).get("bot_token", "")
    chat = (tg_cfg or {}).get("chat_id", "")
    if not bot or not chat or TELEGRAM_DRYRUN:
        print(f"[telegram:{'dry' if TELEGRAM_DRYRUN else 'off'}] {msg}")
        return
    url = f"https://api.telegram.org/bot{_q(bot)}/sendMessage?chat_id={_q(chat)}&parse_mode=Markdown&text={_q(msg)}"
    try:
        with urlopen(url, timeout=10) as r:
            if r.status != 200:
                print(f"[telegram:error] HTTP {r.status}", file=sys.stderr)
    except Exception as e:
        print(f"[telegram:error] {e}", file=sys.stderr)

def _write_lock_or_exit():
    # si lock présent et pid encore vivant → on sort sans lancer un doublon
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r") as f:
                pid = int((f.read() or "0").strip())
            if pid and pid != os.getpid():
                try:
                    os.kill(pid, 0)
                    print(f"[lock] runner déjà actif (pid={pid})")
                    sys.exit(0)
                except Exception:
                    pass
        except Exception:
            pass
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))

def _clear_lock():
    try:
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
    except Exception:
        pass

def load_cfg(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit(
            "❌ Fichier config.yaml manquant. Copie d'abord config.example.yaml → config.yaml et renseigne Telegram."
        )
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_auto_proposal_job(
    symbol: str = "BTCUSDC",   # V4: défaut USDC
    risk_cfg: RiskConfig | None = None,
    notifier: Notifier | None = None,
    trades_alerts_enabled: bool = False,
) -> bool:
    """Génère automatiquement une proposal à partir des facteurs mock et renvoie True si un signal a été produit/envoyé."""
    snapshot = get_market_snapshot(symbol)
    p = generate_proposal_from_factors(snapshot)
    if not p:
        print("⚙️  Aucun signal auto détecté.")
        return False
    # Garde-fous de risque (avant tout log/affichage)
    if risk_cfg is not None:
        try:
            validate_proposal(p, risk_cfg, is_proposal=True)
        except Exception as e:
            print(f"[auto_proposal] rejet par risk guard: {e}")
            return False
    log_proposal(p.model_dump())
    msg = format_proposal_for_telegram(p, balance_usd=10000.0, leverage=2.0)
    if trades_alerts_enabled and notifier is not None:
        sent = send_trade(notifier, p, balance_usd=10000.0, leverage=2.0)
        if sent:
            return True
        else:
            print(msg)
            return True
    else:
        print(msg)
        return True

def _parse_hhmm(s: str) -> tuple[int, int]:
    parts = str(s).strip().split(":")
    h = int(parts[0]) if parts and parts[0] else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return h, m

def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="kobe schedule",
        description="KobeCrypto V1→V4 — Scheduler durci (news + proposals + reporting + runner notify)",
    )
    parser.add_argument("--once", action="store_true", help="Exécuter une seule fois (debug mode)")
    parser.add_argument("--config", default="config.yaml", help="Chemin vers le fichier config")
    parser.add_argument("--symbol", default="BTCUSDC", help="Symbole pour l’auto-proposal (ex: BTCUSDC)")  # V4
    args = parser.parse_args(argv)

    selected_symbol = args.symbol
    cfg = load_cfg(args.config)
    tg_cfg = cfg.get("telegram", {}) or {}
    scheduler_cfg = cfg.get("scheduler", {}) or {}
    news_cfg = cfg.get("news", {}) or {}

    feeds = news_cfg.get("feeds", [])
    keywords = news_cfg.get("keywords_any", [])
    max_items = news_cfg.get("max_items_per_run", 6)
    enabled_hours_utc = scheduler_cfg.get("enabled_hours_utc", list(range(7,22)))
    interval_minutes = int(os.getenv("SCAN_INTERVAL_MIN", str(scheduler_cfg.get("interval_minutes", 10))))
    risk_cfg_dict = cfg.get("risk", {}) or {}
    try:
        risk_cfg = RiskConfig(**risk_cfg_dict)
    except Exception:
        risk_cfg = RiskConfig()  # défauts sûrs

    reporting_daily_cfg = cfg.get("reporting", {}).get("daily", {})
    daily_enabled = bool(reporting_daily_cfg.get("enabled", True))
    daily_time = reporting_daily_cfg.get("time_utc", "21:00")
    _daily_hr, _daily_min = _parse_hhmm(daily_time)

    alerts_trades_cfg = (cfg.get("alerts", {}) or {}).get("trades", {}) or {}
    trades_alerts_enabled = bool(alerts_trades_cfg.get("enabled", False))

    # Notifier Telegram si token renseigné
    notifier = None
    if tg_cfg.get("bot_token") and not tg_cfg["bot_token"].startswith("YOUR_"):
        notifier = Notifier(TelegramConfig(**tg_cfg))
        print("✅ Mode Telegram actif (token détecté)")
    else:
        print("ℹ️ Mode console (aucun token Telegram renseigné)")

    # === SOP V4: lock + notify start/stop/crash + heartbeat ===
    def _on_exit(reason="normal"):
        _clear_lock()
        _tg_send_from_cfg(tg_cfg, f"🛑 Kobe V4 runner *stop* ({reason}) — {_now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        _write_lock_or_exit()
        atexit.register(_on_exit, reason="exit")
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda s, f: (_on_exit(reason=f"signal {s}"), sys.exit(0)))

        _tg_send_from_cfg(tg_cfg, f"▶️ Kobe V4 runner *start* — {_now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')} — interval={interval_minutes}m")
        if args.once:
            # run one-shot (news uniquement, conforme V3)
            run_news_job(feeds, keywords, max_items, enabled_hours_utc, notifier, use_telegram_for_news=False)
            return 0

        # Scheduler pour news + job auto_proposal
        sched = build_scheduler(
            interval_minutes, feeds, keywords, max_items, enabled_hours_utc,
            notifier, use_telegram_for_news=False
        )

        # === V4: Alignement strict + Cooldown anti-doublon ===========================
        # Forcer un minimum de 5 minutes par SOP
        try:
            interval_minutes = max(5, int(interval_minutes))
        except Exception:
            interval_minutes = max(5, 10)

        # Cooldown par symbole (min par défaut = 30)
        COOLDOWN_MIN = int(os.getenv("COOLDOWN_MIN", "30"))
        LAST_SENT_TS = {}

        def _cooldown_ok(sym: str) -> bool:
            ts = LAST_SENT_TS.get(sym)
            if not ts:
                return True
            return (_now_utc() - ts) >= timedelta(minutes=COOLDOWN_MIN)

        def _mark_sent(sym: str):
            LAST_SENT_TS[sym] = _now_utc()

        def _next_aligned(now: datetime, interval_min: int) -> datetime:
            # Aligne le premier tick sur :00/:10/:20… (ou toute division d'heure)
            step = max(5, int(interval_min))
            next_min = ((now.minute // step) + 1) * step
            aligned = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=next_min)
            if aligned <= now:
                aligned += timedelta(minutes=step)
            return aligned

        def _auto_job():
            sym = selected_symbol
            if not _cooldown_ok(sym):
                print(f"[cooldown] skip {sym} (COOLDOWN_MIN={COOLDOWN_MIN})")
                return
            produced = run_auto_proposal_job(sym, risk_cfg, notifier, trades_alerts_enabled)
            if produced:
                _mark_sent(sym)

        first_run = _next_aligned(_now_utc(), interval_minutes)
        print(f"🪩 Alignement activé — premier tick à {first_run.strftime('%H:%M:%S UTC')} (interval={interval_minutes}m)")

        from apscheduler.triggers.interval import IntervalTrigger as _I
        sched.add_job(_auto_job, trigger=_I(minutes=interval_minutes, start_date=first_run, timezone=UTC))
        # ============================================================================ 

        # Ajout heartbeat toutes les HEARTBEAT_MIN (si >0)
        if HEARTBEAT_MIN > 0:
            def _hb():
                print("[heartbeat] alive")
                _tg_send_from_cfg(tg_cfg, "💓 Runner OK — alive")
            sched.add_job(_hb, trigger=IntervalTrigger(minutes=HEARTBEAT_MIN, timezone=UTC))

        # Keepalive stdout toutes 30s pour debug long-run
        def _ka():
            print("[tick] keepalive")
        from apscheduler.triggers.interval import IntervalTrigger as _I
        sched.add_job(_ka, trigger=_I(seconds=30, timezone=UTC))

        # Reporting quotidien si activé
        if daily_enabled:
            sched.add_job(lambda: run_report(notifier), trigger=CronTrigger(hour=_daily_hr, minute=_daily_min, timezone=UTC))

        print("⏱️ Scheduler lancé — fenêtre UTC:", enabled_hours_utc, f"(toutes les {interval_minutes} min)")
        sched.start()
        # Boucle d'attente du scheduler (bloquant)
        try:
            while True:
                time.sleep(1)
        finally:
            pass

    except Exception as e:
        _tg_send_from_cfg(tg_cfg, f"❗️Runner crash: `{type(e).__name__}` — {e}")
        raise

if __name__ == "__main__":
    sys.exit(main() or 0)
