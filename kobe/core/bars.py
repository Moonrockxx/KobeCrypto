#!/usr/bin/env python3
"""
kobe.core.bars — Agrégation ticks -> barres 1m (OHLCV) pour la v0.
Squelette minimal : accumule aggTrade par minute (ms // 60000).
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Bar1m:
    symbol: str
    ts_open: int  # ms
    o: float
    h: float
    l: float
    c: float
    v: float

class AggToBars1m:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self._minute = None
        self._bar: Optional[Bar1m] = None

    def on_tick(self, tick) -> Optional[Bar1m]:
        # tick.ts en ms
        minute = tick.ts // 60000
        if self._minute is None:
            self._minute = minute
            self._bar = Bar1m(self.symbol, minute*60000, tick.price, tick.price, tick.price, tick.price, tick.qty)
            return None
        if minute != self._minute:
            out = self._bar
            # nouvelle minute
            self._minute = minute
            self._bar = Bar1m(self.symbol, minute*60000, tick.price, tick.price, tick.price, tick.price, tick.qty)
            return out
        # mise à jour
        b = self._bar
        b.h = max(b.h, tick.price)
        b.l = min(b.l, tick.price)
        b.c = tick.price
        b.v += tick.qty
        return None
