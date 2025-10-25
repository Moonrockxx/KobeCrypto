from __future__ import annotations
import argparse, json, sys, csv
from pathlib import Path
from typing import Dict, Any, Iterable
import yaml

from kobe.core.risk import RiskConfig
from kobe.core.scheduler import build_scheduler
from kobe.core.factors import get_market_snapshot
from kobe.signals.generator import generate_proposal_from_factors

OK = "✅"
KO = "❌"
INFO = "ℹ️"

def load_cfg(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {"_error": f"{KO} config.yaml manquant — copie config.example.yaml → config.yaml"}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return {"_error": f"{KO} lecture config: {e}"}

def check_cfg_sections(cfg: dict) -> list[dict]:
    checks = []
    need = ["scheduler","news","risk","reporting","alerts","telegram"]
    for k in need:
        present = k in cfg
        checks.append({"name": f"cfg.{k}", "ok": present, "msg": OK if present else f"{KO} section absente"})
    return checks

def check_risk(cfg: dict) -> dict:
    try:
        rc = RiskConfig(**(cfg.get("risk", {}) or {}))
        ok = rc.max_trade_pct >= rc.max_proposal_pct > 0
        msg = OK if ok else f"{KO} incohérence risk: trade({rc.max_trade_pct}) < proposal({rc.max_proposal_pct})"
        return {"name":"risk.limits", "ok": ok, "msg": msg}
    except Exception as e:
        return {"name":"risk.limits", "ok": False, "msg": f"{KO} {e}"}

def check_telegram_flag(cfg: dict) -> dict:
    alerts = (cfg.get("alerts", {}) or {}).get("trades", {}) or {}
    enabled = bool(alerts.get("enabled", False))
    tg = cfg.get("telegram", {}) or {}
    token_ok = bool(tg.get("bot_token")) and not str(tg.get("bot_token","")).startswith("YOUR_")
    chat_ok = bool(tg.get("chat_id"))
    if enabled and not (token_ok and chat_ok):
        return {"name":"alerts.trades", "ok": False, "msg": f"{KO} enabled=true mais token/chat_id manquants"}
    return {"name":"alerts.trades", "ok": True, "msg": OK if not enabled else f"{OK} enabled=true & creds présents"}

def check_logs_writable() -> dict:
    try:
        Path("logs").mkdir(parents=True, exist_ok=True)
        t = Path("logs/.write_test")
        t.write_text("ok", encoding="utf-8"); t.unlink(missing_ok=True)
        return {"name":"logs.writable", "ok": True, "msg": OK}
    except Exception as e:
        return {"name":"logs.writable", "ok": False, "msg": f"{KO} {e}"}

def check_scheduler_construct(cfg: dict) -> dict:
    try:
        feeds = (cfg.get("news", {}) or {}).get("feeds", [])
        keywords = (cfg.get("news", {}) or {}).get("keywords_any", [])
        max_items = int((cfg.get("news", {}) or {}).get("max_items_per_run", 6))
        sch = cfg.get("scheduler", {}) or {}
        hours = sch.get("enabled_hours_utc", list(range(7,22)))
        every = int(sch.get("interval_minutes", 15))
        # Construction uniquement (ne lance pas)
        _ = build_scheduler(every, feeds, keywords, max_items, hours, notifier=None, use_telegram_for_news=False)
        return {"name":"scheduler.build", "ok": True, "msg": OK}
    except Exception as e:
        return {"name":"scheduler.build", "ok": False, "msg": f"{KO} {e}"}

def check_generator_pipeline() -> dict:
    try:
        snap = get_market_snapshot("BTCUSDT")
        _ = generate_proposal_from_factors(snap)  # None est acceptable
        return {"name":"generator.pipeline", "ok": True, "msg": OK}
    except Exception as e:
        return {"name":"generator.pipeline", "ok": False, "msg": f"{KO} {e}"}

def run_health(cfg_path: str, json_only: bool = False) -> int:
    out = {"checks": []}

    cfg = load_cfg(cfg_path)
    if "_error" in cfg:
        out["checks"].append({"name":"config.presence", "ok": False, "msg": cfg["_error"]})
        rc = 1
    else:
        out["checks"].append({"name":"config.presence", "ok": True, "msg": OK})
        out["checks"] += check_cfg_sections(cfg)
        out["checks"].append(check_risk(cfg))
        out["checks"].append(check_telegram_flag(cfg))
        out["checks"].append(check_logs_writable())
        out["checks"].append(check_scheduler_construct(cfg))
        out["checks"].append(check_generator_pipeline())
        # Code retour: 0 si toutes ok, sinon 1
        rc = 0 if all(c.get("ok") for c in out["checks"]) else 1

    if json_only:
        print(json.dumps(out, ensure_ascii=False))
    else:
        # Affichage lisible
        for c in out["checks"]:
            badge = OK if c.get("ok") else KO
            print(f"{badge} {c.get('name')}: {c.get('msg')}")
        if rc == 0:
            print("✅ Health check: OK")
        else:
            print("❌ Health check: des points à corriger")
    return rc

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kobe health", description="KobeCrypto — Health check configuration & scheduler")
    ap.add_argument("--config", default="config.yaml", help="Chemin du fichier config")
    ap.add_argument("--json-only", action="store_true", help="Sortie JSON compacte")
    return ap

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return run_health(args.config, json_only=args.json_only)

if __name__ == "__main__":
    raise SystemExit(main())
