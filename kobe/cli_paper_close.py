from __future__ import annotations
import argparse, json, csv, os, sys, datetime as dt
from typing import Literal

Side = Literal["long","short"]

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _ensure_logs(logs_dir: str) -> tuple[str,str]:
    os.makedirs(logs_dir, exist_ok=True)
    jpath = os.path.join(logs_dir, "journal.jsonl")
    cpath = os.path.join(logs_dir, "journal.csv")
    return jpath, cpath

def _pnl(entry: float, price: float, side: Side, qty: float) -> float:
    return (price - entry) * qty if side == "long" else (entry - price) * qty

def close_trade(symbol: str, side: Side, entry: float, qty: float, price: float,
                reason: str = "manual", logs_dir: str = "logs") -> dict:
    jpath, cpath = _ensure_logs(logs_dir)
    pnl = _pnl(entry, price, side, qty)
    pnl_pct = ((price / entry) - 1.0) * (100 if side == "long" else -100)
    rec = {
        "ts": _now_iso(),
        "event": "paper_close",
        "symbol": symbol,
        "side": side,
        "entry": float(entry),
        "close": float(price),
        "qty": float(qty),
        "pnl": float(round(pnl, 8)),
        "pnl_pct": float(round(pnl_pct, 6)),
        "reason": reason,
    }
    with open(jpath, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
    header = ["ts","event","symbol","side","entry","close","qty","pnl","pnl_pct","reason"]
    write_header = not os.path.exists(cpath) or os.path.getsize(cpath) == 0
    with open(cpath, "a", newline="", encoding="utf-8") as cf:
        w = csv.DictWriter(cf, fieldnames=header)
        if write_header:
            w.writeheader()
        w.writerow({k: rec[k] for k in header})
    return rec

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m kobe.cli_paper_close",
        description="Ferme une position papier et journalise le résultat (JSONL/CSV)."
    )
    p.add_argument("--symbol", required=True, help="Ex: BTCUSDT")
    p.add_argument("--side", required=True, choices=["long","short"])
    p.add_argument("--entry", required=True, type=float, help="Prix d'entrée de la position")
    p.add_argument("--qty", required=True, type=float, help="Quantité de la position")
    p.add_argument("--price", required=True, type=float, help="Prix de clôture")
    p.add_argument("--reason", default="manual", help="Raison de clôture (manual/stop/target/...)")
    p.add_argument("--logs-dir", default="logs", help="Dossier des journaux (def: logs)")
    return p.parse_args(argv)

def main(argv=None):
    args = _parse_args(argv)
    rec = close_trade(
        symbol=args.symbol, side=args.side, entry=args.entry,
        qty=args.qty, price=args.price, reason=args.reason,
        logs_dir=args.logs_dir
    )
    print(json.dumps({"ok": True, "event": rec}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
