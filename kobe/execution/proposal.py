from dataclasses import dataclass
from typing import List, Literal, Dict
from .risk import RiskConfig, compute_spot_qty

@dataclass
class SpotProposal:
    symbol: str
    side: Literal["BUY","SELL"]
    entry: float
    stop: float
    tp: float
    qty: float
    rr: float
    risk_pct: float
    risk_amount_usdc: float
    reasons: List[str]

def build_spot_proposal(
    symbol: str,
    side: Literal["BUY","SELL"],
    entry: float,
    stop: float,
    balance_usdc: float,
    reasons: List[str],
    risk_pct: float = 0.0025,
    rr: float = 2.0,
) -> Dict[str, object]:
    # Guard: at least 3 reasons
    reasons = [r.strip() for r in reasons if r and r.strip()]
    if len(reasons) < 3:
        return {"status": "rejected", "reason": "not_enough_reasons", "min_reasons": 3, "got": len(reasons)}

    cfg = RiskConfig(risk_pct=risk_pct)
    data = compute_spot_qty(side, balance_usdc, entry, stop, cfg)
    dist = data["dist_price"]
    qty  = data["qty"]
    tp   = entry + rr * dist if side == "BUY" else entry - rr * dist

    sp = SpotProposal(
        symbol=symbol, side=side, entry=entry, stop=stop, tp=tp, qty=qty,
        rr=rr, risk_pct=data["risk_pct_applied"],
        risk_amount_usdc=data["risk_amount_usdc"], reasons=reasons
    )

    # Telegram message in strict ASCII
    lines = [
        f"[PROPOSAL] {sp.symbol} {sp.side}",
        f"Entry: {sp.entry:.4f} | SL: {sp.stop:.4f} | TP: {sp.tp:.4f} | RR={sp.rr:.2f}",
        f"Qty: {sp.qty:.8f} | Risk: {sp.risk_pct*100:.2f}% (~{sp.risk_amount_usdc:.2f} USDC)",
        "Reasons:",
    ] + [f" - {r}" for r in sp.reasons]
    text = "\n".join(lines)

    return {
        "status": "ok",
        "proposal": {
            "symbol": sp.symbol, "side": sp.side, "entry": sp.entry,
            "stop": sp.stop, "tp": sp.tp, "qty": sp.qty, "rr": sp.rr,
            "risk_pct": sp.risk_pct, "risk_amount_usdc": sp.risk_amount_usdc,
            "reasons": sp.reasons,
        },
        "text": text,
        "notes": "dry-build - aucun ordre envoye",
    }
