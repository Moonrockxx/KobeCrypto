from __future__ import annotations
import csv, json, time
from pathlib import Path
from typing import Dict, Any, Optional

from kobe.signals.proposal import Proposal, position_size
from kobe.core.adapter.base import Exchange, ExchangeError

POS_LOG_DIR = Path("logs")
POS_CSV_PATH = POS_LOG_DIR / "positions.csv"
POS_JSONL_PATH = POS_LOG_DIR / "positions.jsonl"

# Nous ajoutons "mode" (live/paper) et "exchange_order_id" pour tracer les vrais trades
CSV_COLS = [
    "ts_open", "ts_close", "id", "mode",
    "symbol", "side",
    "entry", "stop", "take",
    "qty", "leverage",
    "exit_price", "reason",
    "realized_pnl_usd", "status",
    "risk_pct", "size_pct", "exchange_order_id"
]

def _ensure():
    POS_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _ms() -> int:
    return int(time.time() * 1000)

def _gen_id(p: Proposal, mode: str) -> str:
    return f"pos-{mode}-{p.symbol.lower()}-{_ms()}"

def _append_row(evt: Dict[str, Any]) -> None:
    _ensure()
    # Sauvegarde JSONL
    with POS_JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    
    # Sauvegarde CSV
    write_header = not POS_CSV_PATH.exists()
    with POS_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if write_header:
            w.writeheader()
        w.writerow({k: evt.get(k, "") for k in CSV_COLS})

def simulate_open(p: Proposal, balance_usd: float, leverage: float = 1.0) -> Dict[str, Any]:
    """Ouvre une position simulée (Paper Trading)."""
    qty = position_size(balance_usd, p.risk_pct, p.entry, p.stop, leverage=leverage)
    evt = {
        "ts_open": _ms(),
        "ts_close": "",
        "id": _gen_id(p, "paper"),
        "mode": "paper",
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
        "exchange_order_id": "N/A"
    }
    _append_row(evt)
    return evt

def execute_live_open(p: Proposal, exchange: Exchange, balance_usd: float, leverage: float = 1.0) -> Dict[str, Any]:
    """Ouvre une position réelle sur l'exchange."""
    qty = position_size(balance_usd, p.risk_pct, p.entry, p.stop, leverage=leverage)
    
    # Binance requiert 'buy' ou 'sell'
    side_exchange = "buy" if p.side == "long" else "sell"
    
    try:
        # Envoi d'un ordre au marché pour garantir l'exécution immédiate
        order = exchange.create_order(
            symbol=p.symbol,
            side=side_exchange,
            type="market",
            qty=qty
        )
        
        # Le prix réel peut différer du prix théorique à cause du slippage
        real_entry = order.get('average') or order.get('price') or p.entry
            
        evt = {
            "ts_open": _ms(),
            "ts_close": "",
            "id": _gen_id(p, "live"),
            "mode": "live",
            "symbol": p.symbol,
            "side": p.side,
            "entry": float(real_entry),
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
            "exchange_order_id": order.get('id', "")
        }
        _append_row(evt)
        return evt
        
    except ExchangeError as e:
        # Si Binance refuse l'ordre (fonds insuffisants, lot invalide...), on capture l'erreur proprement
        print(f"❌ Échec de l'exécution Live sur {p.symbol}: {e}")
        return {"error": str(e), "status": "failed"}

def _pnl_usd(side: str, entry: float, exit_price: float, qty: float) -> float:
    if side == "long":
        return qty * (exit_price - entry)
    else:
        return qty * (entry - exit_price)

def simulate_close(open_evt: Dict[str, Any], price: float, reason: str = "manual") -> Dict[str, Any]:
    """Ferme une position dans les logs (fonctionne pour le Live et le Paper)."""
    entry = float(open_evt["entry"])
    qty = float(open_evt["qty"])
    side = str(open_evt["side"])
    pnl = _pnl_usd(side, entry, float(price), qty)

    evt = {**open_evt} # Copie des données d'ouverture
    evt.update({
        "ts_close": _ms(),
        "exit_price": float(price),
        "reason": reason,
        "realized_pnl_usd": float(pnl),
        "status": "closed",
    })
    _append_row(evt)
    return evt