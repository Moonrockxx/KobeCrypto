from dataclasses import dataclass
from typing import Literal

@dataclass
class RiskConfig:
    # Défauts SOP V4: 0.25% avec CAP dur à 0.5%
    risk_pct: float = 0.0025     # 0.25%
    max_risk_pct: float = 0.005  # 0.5%
    fee_pct: float = 0.001       # 0.10% (aller simple, simplifié)
    slippage_pct: float = 0.0005 # 0.05% (hypothèse conservative)

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_spot_qty(
    side: Literal["BUY","SELL"],
    balance_usdc: float,
    entry: float,
    stop: float,
    cfg: RiskConfig
) -> dict:
    assert entry > 0 and stop > 0 and balance_usdc > 0
    r = _clamp(cfg.risk_pct, 0.0, cfg.max_risk_pct)
    dist = abs(entry - stop)
    dist_eff = dist * (1 + cfg.fee_pct + cfg.slippage_pct)
    if dist_eff <= 0:
        raise ValueError("Distance E-SL nulle/invalide.")
    risk_amount = balance_usdc * r
    qty = risk_amount / dist_eff
    return {
        "risk_pct_applied": r,
        "risk_amount_usdc": risk_amount,
        "dist_price": dist,
        "dist_effective": dist_eff,
        "qty": qty,
    }
