from __future__ import annotations
import csv, json, time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any, Optional
from kobe.signals.proposal import Proposal, position_size

# Fichiers de logs (même hygiène que journal)
POS_LOG_DIR = Path("logs")
POS_CSV_PATH = POS_LOG_DIR / "positions.csv"
POS_JSONL_PATH = POS_LOG_DIR / "positions.jsonl"

CSV_COLS = [
    "ts_open", "ts_close", "id",
    "symbol", "side",
    "entry", "stop", "take",
    "qty", "leverage",
    "exit_price", "reason",
    "realized_pnl_usd", "status",
    "risk_pct", "size_pct",
]

def _ensure():
    POS_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _ms() -> int:
    return int(time.time() * 1000)

def _gen_id(p: Proposal) -> str:
    # id simple horodaté (compatible CSV/JSONL)
    return f"pos-{p.symbol.lower()}-{_ms()}"

def _append_row(evt: Dict[str, Any]) -> None:
    _ensure()
    # JSONL
    with POS_JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    # CSV
    write_header = not POS_CSV_PATH.exists()
    with POS_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if write_header:
            w.writeheader()
        w.writerow({k: evt.get(k, "") for k in CSV_COLS})

def simulate_open(p: Proposal, balance_usd: float, leverage: float = 1.0) -> Dict[str, Any]:
    """
    Ouvre une position papier à partir d'une Proposal.
    - Calcule une taille approx en base (qty) avec position_size()
    - Log l'ouverture dans positions.csv/jsonl (status=open)
    """
    qty = position_size(balance_usd, p.risk_pct, p.entry, p.stop, leverage=leverage)
    pos_id = _gen_id(p)
    evt = {
        "ts_open": _ms(),
        "ts_close": "",
        "id": pos_id,
        "symbol": p.symbol,
        "side": p.side,
        "entry": float(p.entry),
        "stop": float(p.stop),
        "take": float(p.take),
        "qty": float(qty),
        "leverage": float(leverage),
        "exit_price": "",
        "reason": "",
        "realized_pnl_usd": "",
        "status": "open",
        "risk_pct": float(p.risk_pct),
        "size_pct": float(p.size_pct),
    }
    _append_row(evt)
    return evt

def _pnl_usd(side: str, entry: float, exit_price: float, qty: float) -> float:
    # qty est en base (coin). PnL USD ≈ qty * (exit - entry) pour LONG, inversé pour SHORT.
    if side == "long":
        return qty * (exit_price - entry)
    else:
        return qty * (entry - exit_price)

def simulate_close(open_evt: Dict[str, Any], price: float, reason: str = "manual") -> Dict[str, Any]:
    """
    Ferme une position papier.
    - Calcule le PnL réalisé
    - Ajoute une nouvelle ligne 'closed' (on NE modifie PAS la ligne 'open')
    """
    entry = float(open_evt["entry"])
    qty = float(open_evt["qty"])
    side = str(open_evt["side"])
    pnl = _pnl_usd(side, entry, float(price), qty)

    evt = {
        "ts_open": open_evt["ts_open"],
        "ts_close": _ms(),
        "id": open_evt["id"],
        "symbol": open_evt["symbol"],
        "side": side,
        "entry": entry,
        "stop": float(open_evt["stop"]),
        "take": float(open_evt["take"]),
        "qty": qty,
        "leverage": float(open_evt["leverage"]),
        "exit_price": float(price),
        "reason": reason,
        "realized_pnl_usd": float(pnl),
        "status": "closed",
        "risk_pct": float(open_evt["risk_pct"]),
        "size_pct": float(open_evt["size_pct"]),
    }
    _append_row(evt)
    return evt
