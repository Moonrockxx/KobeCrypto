from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class _TF:
    close: float
    high: float
    low: float
    volume: float
    ema_20: float
    atr_pct_14: float
    range_pct_20: float
    trend_score: float


def _to_tf(data: Dict[str, Any] | None) -> _TF | None:
    if not data:
        return None
    try:
        return _TF(
            close=float(data.get("close", 0.0)),
            high=float(data.get("high", 0.0)),
            low=float(data.get("low", 0.0)),
            volume=float(data.get("volume", 0.0)),
            ema_20=float(data.get("ema_20", 0.0)),
            atr_pct_14=float(data.get("atr_pct_14", 0.0)),
            range_pct_20=float(data.get("range_pct_20", 0.0)),
            trend_score=float(data.get("trend_score", 0.0)),
        )
    except Exception:
        return None


def _atr_abs(price: float, atr_pct: float) -> float:
    """Convertit un ATR% en ATR absolu en prix."""
    if price <= 0:
        return 0.0
    if atr_pct <= 0:
        return 0.0
    return price * (atr_pct / 100.0)


def _dist_pct(price: float, ema_val: float) -> float:
    """Distance prix vs EMA en % du prix."""
    if price <= 0 or ema_val <= 0:
        return 0.0
    return (price - ema_val) / price * 100.0


def scan_setups(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Retourne une liste de setups candidats à partir d'un snapshot marché.

    Chaque candidat a la forme :
    {
      "id": "...",
      "symbol": "BTCUSDC",
      "side": "long" | "short",
      "quality": 0.0 à 1.0,
      "entry_hint": {"type": "...", "price": float},
      "stop_hint": {"type": "...", "price": float},
      "take_hint": {"type": "...", "price": float},
      "reasons": [str, ...],
    }
    """
    symbol = snapshot.get("symbol")
    timeframes = snapshot.get("timeframes") or {}
    regime = snapshot.get("regime") or {}

    if not symbol or not isinstance(timeframes, dict):
        return []

    tf_15 = _to_tf(timeframes.get("15m"))
    tf_1h = _to_tf(timeframes.get("1h"))
    tf_4h = _to_tf(timeframes.get("4h"))
    tf_1d = _to_tf(timeframes.get("1d"))

    trend_regime = regime.get("trend", "range")
    vol_regime = regime.get("volatility", "normal")

    candidates: List[Dict[str, Any]] = []

    # --- Playbook 1: Breakout dans le sens du trend (long) ---
    if tf_15 and tf_1h and tf_4h and tf_1d:
        if tf_4h.trend_score > 0.6 and tf_1d.trend_score > 0.5:
            if tf_1h.atr_pct_14 < 2.0 and tf_1h.range_pct_20 < 4.0:
                # Clôture 15m proche des plus hauts : breakout local
                if tf_15.close >= tf_15.high * 0.995:
                    entry = tf_15.close
                    atr_val = _atr_abs(entry, tf_1h.atr_pct_14)
                    if atr_val > 0:
                        stop = entry - 2.0 * atr_val
                        take = entry + 4.0 * atr_val

                        quality = 0.6
                        quality += min(0.2, (tf_4h.trend_score + tf_1d.trend_score) / 10.0)
                        quality = max(0.0, min(1.0, quality))

                        reasons = [
                            "Trend haussier fort sur 4h et daily.",
                            "Volatilité 1h en contraction avant le breakout.",
                            "Clôture 15m proche des plus hauts (breakout haussier).",
                        ]

                        candidates.append(
                            {
                                "id": "trend_breakout_15m_long",
                                "symbol": symbol,
                                "side": "long",
                                "quality": quality,
                                "entry_hint": {"type": "limit", "price": entry},
                                "stop_hint": {"type": "stop", "price": stop},
                                "take_hint": {"type": "take_profit", "price": take},
                                "reasons": reasons,
                            }
                        )

    # --- Playbook 2: Pullback dans un trend haussier (long) ---
    if tf_1h and tf_4h:
        if tf_4h.trend_score > 0.7 and tf_1h.trend_score > 0.7:
            # Prix qui revient vers l'EMA20 1h (pullback)
            dist_ema = _dist_pct(tf_1h.close, tf_1h.ema_20)
            if -2.5 <= dist_ema <= 0.0:
                atr_val = _atr_abs(tf_1h.close, tf_1h.atr_pct_14)
                if atr_val > 0:
                    entry = tf_1h.close
                    stop = entry - 1.5 * atr_val
                    take = entry + 3.0 * atr_val

                    quality = 0.65
                    quality += min(0.2, (tf_4h.trend_score + tf_1h.trend_score) / 10.0)
                    quality = max(0.0, min(1.0, quality))

                    reasons = [
                        "Trend 4h et 1h fortement haussier.",
                        "Pullback vers l'EMA20 1h (retest de zone de valeur).",
                        "ATR raisonnable pour placer un stop technique.",
                    ]

                    candidates.append(
                        {
                            "id": "trend_pullback_1h_long",
                            "symbol": symbol,
                            "side": "long",
                            "quality": quality,
                            "entry_hint": {"type": "limit", "price": entry},
                            "stop_hint": {"type": "stop", "price": stop},
                            "take_hint": {"type": "take_profit", "price": take},
                            "reasons": reasons,
                        }
                    )

    # --- Playbook 3: Mean reversion 15m (range / excès) ---
    if tf_15 and trend_regime in ("range", "bear") and vol_regime in ("calm", "normal"):
        dist_ema_15 = _dist_pct(tf_15.close, tf_15.ema_20)
        atr_val = _atr_abs(tf_15.close, tf_15.atr_pct_14)

        if atr_val > 0:
            # Excès haussier → short mean reversion
            if dist_ema_15 > 2.0:
                entry = tf_15.close
                stop = entry + 2.0 * atr_val
                take = entry - 3.0 * atr_val
                quality = 0.55

                reasons = [
                    "Marché en range avec volatilité modérée.",
                    "Prix 15m nettement au-dessus de l'EMA20 (excès haussier).",
                    "Setup de retour vers la moyenne (mean reversion short).",
                ]

                candidates.append(
                    {
                        "id": "mean_reversion_15m_short",
                        "symbol": symbol,
                        "side": "short",
                        "quality": max(0.0, min(1.0, quality)),
                        "entry_hint": {"type": "limit", "price": entry},
                        "stop_hint": {"type": "stop", "price": stop},
                        "take_hint": {"type": "take_profit", "price": take},
                        "reasons": reasons,
                    }
                )

            # Excès baissier → long mean reversion
            elif dist_ema_15 < -2.0:
                entry = tf_15.close
                stop = entry - 2.0 * atr_val
                take = entry + 3.0 * atr_val
                quality = 0.55

                reasons = [
                    "Marché en range avec volatilité modérée.",
                    "Prix 15m nettement en-dessous de l'EMA20 (excès baissier).",
                    "Setup de retour vers la moyenne (mean reversion long).",
                ]

                candidates.append(
                    {
                        "id": "mean_reversion_15m_long",
                        "symbol": symbol,
                        "side": "long",
                        "quality": max(0.0, min(1.0, quality)),
                        "entry_hint": {"type": "limit", "price": entry},
                        "stop_hint": {"type": "stop", "price": stop},
                        "take_hint": {"type": "take_profit", "price": take},
                        "reasons": reasons,
                    }
                )

    if not candidates:
        # Debug minimal pour comprendre pourquoi aucun setup n'est généré
        print(
            "[scan_setups][debug] aucun setup généré pour "
            f"{symbol} trend={trend_regime} vol={vol_regime} "
            f"tf_15={'ok' if tf_15 else 'none'} "
            f"tf_1h={'ok' if tf_1h else 'none'} "
            f"tf_4h={'ok' if tf_4h else 'none'} "
            f"tf_1d={'ok' if tf_1d else 'none'}"
        )
    return candidates


if __name__ == "__main__":
    # Petit test manuel possible en important un snapshot artificiel
    example = {
        "symbol": "BTCUSDC",
        "timeframes": {},
        "regime": {"trend": "range", "volatility": "normal"},
    }
    print("scan_setups(example) ->", scan_setups(example))
