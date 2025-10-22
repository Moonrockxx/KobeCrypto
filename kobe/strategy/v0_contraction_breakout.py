#!/usr/bin/env python3
"""
Stratégie v0 — Breakout de contraction (barres 1m)
- 0 ou 1 signal / jour (clamp par date locale)
- 3 raisons (contraction ATR, cassure HH/LL_20, volume relatif >1.5x)
- stop obligatoire (ATR-based), risk 0,5% (paper only)
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json, math

STATE_PATH = Path.home() / ".kobe_state.json"

@dataclass
class Bar:
    symbol: str
    ts_open: int
    o: float; h: float; l: float; c: float; v: float

def _read_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_state(st: dict):
    STATE_PATH.write_text(json.dumps(st), encoding="utf-8")

def _clamped_today() -> bool:
    st = _read_state()
    return st.get("last_date") == date.today().isoformat()

def _persist_today():
    st = _read_state()
    st["last_date"] = date.today().isoformat()
    _write_state(st)

def _true_range(prev_c, h, l):
    return max(h - l, abs(h - prev_c), abs(l - prev_c))

def _median(values):
    s = sorted(values)
    n = len(s)
    if n == 0: return 0.0
    mid = n // 2
    return (s[mid] if n % 2 else 0.5*(s[mid-1]+s[mid]))

def _atr14(bars):
    if len(bars) < 15: return None
    trs = []
    for i in range(1, len(bars)):
        prev_c = bars[i-1].c
        b = bars[i]
        trs.append(_true_range(prev_c, b.h, b.l))
    if len(trs) < 14: return None
    return sum(trs[-14:]) / 14.0

def _highest(bars, n):
    if len(bars) < n: return None
    return max(b.h for b in bars[-n:])

def _lowest(bars, n):
    if len(bars) < n: return None
    return min(b.l for b in bars[-n:])

def maybe_signal_from_bars(bars_in: list) -> dict | None:
    # Normaliser en @dataclass locale si besoin
    bars = [Bar(b.symbol, b.ts_open, b.o, b.h, b.l, b.c, b.v) for b in bars_in]
    if len(bars) < 25:
        return None

    symbol = bars[-1].symbol
    cbar   = bars[-1]

    atr = _atr14(bars)
    if atr is None or atr <= 0:
        return None

    # Contraction: ATR actuel < 0.7 × médiane ATR 20 précédentes
    past_atrs = []
    tmp = []
    for i in range(1, len(bars)):
        tr = _true_range(bars[i-1].c, bars[i].h, bars[i].l)
        tmp.append(tr)
        if len(tmp) >= 14:
            past_atrs.append(sum(tmp[-14:]) / 14.0)
    if len(past_atrs) < 21:
        return None
    med_atr20 = _median(past_atrs[-21:-1])  # exclut l'actuel
    contracted = atr < 0.7 * med_atr20 if med_atr20 > 0 else False

    # Breakout HH/LL_20
    HH_N = 20
    LL_N = 20
    hh20 = _highest(bars[:-1], HH_N)  # hors barre courante
    ll20 = _lowest(bars[:-1], LL_N)

    # Volume relatif sur 20 dernières (hors actuelle)
    vols = [b.v for b in bars[:-1]][-20:]
    med_vol = _median(vols) if len(vols) >= 5 else 0.0
    rel_vol = (cbar.v / med_vol) if med_vol > 0 else 0.0
    vol_ok  = rel_vol >= 1.5

    long_break  = hh20 is not None and cbar.c > hh20
    short_break = ll20 is not None and cbar.c < ll20

    side = None
    if contracted and vol_ok and long_break:
        side = "long"
    elif contracted and vol_ok and short_break:
        side = "short"

    if not side:
        return None

    if _clamped_today():
        return None

    # Stop basé sur ATR
    entry = cbar.c
    if side == "long":
        stop = round(entry - 1.5 * atr, 2)
    else:
        stop = round(entry + 1.5 * atr, 2)

    reasons = []
    reasons.append(f"Contraction: ATR14 {atr:.2f} < 0.7×médiane20 {med_atr20:.2f}")
    if side == "long":
        reasons.append(f"Cassure: close {entry:.2f} > HH20 {hh20:.2f}")
    else:
        reasons.append(f"Cassure: close {entry:.2f} < LL20 {ll20:.2f}")
    reasons.append(f"Volume relatif: {rel_vol:.2f}× ≥ 1.5×")

    signal = {
        "symbol": symbol,
        "side": side,
        "entry": round(entry, 2),
        "stop": stop,
        "risk_pct": 0.5,
        "reasons": reasons,
        "note": "LIVE v0 — paper only; aucune promesse de gain.",
    }
    _persist_today()
    return signal
