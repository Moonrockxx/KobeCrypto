#!/usr/bin/env python3
import math

def _floor_to_step(x: float, step: float) -> float:
    if step <= 0: 
        return x
    return math.floor(x / step) * step

def size_for_risk(equity: float, risk_pct: float, entry: float, stop: float, lot_step: float = 0.001):
    """
    Calcule la quantité pour risquer `risk_pct` % de `equity` entre entry et stop.
    - equity: capital total (ex: 10000)
    - risk_pct: pourcentage de risque (ex: 0.5 => 0,5%)
    - entry, stop: prix d'entrée et stop
    - lot_step: incrément minimal de quantité (ex: 0.001)
    Retourne (qty, risk_amount).
    """
    if equity <= 0 or entry <= 0 or stop <= 0:
        raise ValueError("Paramètres invalides (equity/entry/stop).")
    dist = abs(entry - stop)
    if dist <= 0:
        raise ValueError("Entry et stop identiques.")
    risk_amount = equity * (risk_pct / 100.0)
    qty = risk_amount / dist
    qty = _floor_to_step(qty, lot_step)
    return max(qty, 0.0), risk_amount
