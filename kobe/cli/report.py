from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Iterable

POS_LOG_DIR = Path("logs")
POS_CSV_PATH = POS_LOG_DIR / "positions.csv"
POS_JSONL_PATH = POS_LOG_DIR / "positions.jsonl"
PNL_CSV_PATH = POS_LOG_DIR / "pnl_daily.csv"
PNL_JSONL_PATH = POS_LOG_DIR / "pnl_daily.jsonl"

def _ensure():
    POS_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _utc_date_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).strftime("%Y-%m-%d")

def _read_positions() -> Iterable[Dict[str, Any]]:
    # lit JSONL si dispo (source la plus fidèle), sinon CSV
    if POS_JSONL_PATH.exists():
        for line in POS_JSONL_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            yield json.loads(line)
    elif POS_CSV_PATH.exists():
        with POS_CSV_PATH.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield row
    else:
        return []

def _aggregate_daily(positions: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    daily: Dict[str, Dict[str, Any]] = {}
    for evt in positions:
        if str(evt.get("status","")) != "closed":
            continue
        try:
            pnl = float(evt.get("realized_pnl_usd", 0) or 0)
            ts_close = int(float(evt.get("ts_close") or 0))
        except Exception:
            continue
        if ts_close <= 0:
            continue
        day = _utc_date_from_ms(ts_close)
        d = daily.setdefault(day, {"date": day, "trades": 0, "wins": 0, "losses": 0, "total_pnl_usd": 0.0})
        d["trades"] += 1
        d["total_pnl_usd"] += pnl
        if pnl > 0:
            d["wins"] += 1
        elif pnl < 0:
            d["losses"] += 1
    # post metrics
    for d in daily.values():
        t = max(1, d["trades"])
        d["win_rate"] = round(100.0 * d["wins"] / t, 2)
        d["avg_pnl_usd"] = round(d["total_pnl_usd"] / t, 2)
        d["total_pnl_usd"] = round(d["total_pnl_usd"], 2)
    return daily

def _write_daily(daily: Dict[str, Dict[str, Any]]) -> None:
    _ensure()
    # Écrit/écrase des snapshots complets (idempotent)
    rows = sorted(daily.values(), key=lambda r: r["date"])
    # JSONL
    PNL_JSONL_PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    # CSV
    cols = ["date","trades","wins","losses","win_rate","avg_pnl_usd","total_pnl_usd"]
    with PNL_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

def run_report(print_last: bool = True) -> Tuple[int, float]:
    positions = list(_read_positions())
    daily = _aggregate_daily(positions)
    _write_daily(daily)
    if not daily:
        if print_last:
            print("ℹ️ Aucun trade fermé — pas de PnL quotidien.")
        return 0, 0.0
    last_day = sorted(daily.keys())[-1]
    d = daily[last_day]
    if print_last:
        print(f"📊 PnL {last_day}: trades={d['trades']} | win_rate={d['win_rate']}% | total={d['total_pnl_usd']}$ | avg={d['avg_pnl_usd']}$")
    return d["trades"], d["total_pnl_usd"]

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kobe report", description="KobeCrypto — Reporting quotidien (PnL)")
    ap.add_argument("--quiet", action="store_true", help="N'affiche pas le résumé en console")
    return ap

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    run_report(print_last=not args.quiet)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
