from __future__ import annotations

import json
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional

from kobe.data.binance_ohlc import fetch_klines
from kobe.ta.indicators import atr, ema, ema_slope, range_pct


# Timeframes utilisées par le Factor Engine.
# Les "limit" sont choisies pour avoir assez d'historique
# pour ATR / EMA / slopes sans exploser la latence.
_TIMEFRAMES: Mapping[str, int] = {
    "15m": 200,
    "1h": 240,
    "4h": 240,
    "1d": 365,
}


# On se limite volontairement aux paires USDC utilisables depuis l'Europe.
_SUPPORTED_SYMBOLS = {"BTCUSDC", "ETHUSDC", "SOLUSDC"}


@dataclass
class TimeframeSnapshot:
    close: float
    high: float
    low: float
    volume: float
    ema_20: float
    atr_pct_14: float
    range_pct_20: float
    trend_score: float  # -1 (fort bear) → +1 (fort bull)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _compute_timeframe_snapshot(candles: List[Dict[str, Any]]) -> Optional[TimeframeSnapshot]:
    """
    Transforme une liste de bougies (dict) en métriques de timeframe.
    Retourne None si on n'a pas assez de profondeur pour des indicateurs stables.
    """
    if not candles or len(candles) < 30:
        return None

    closes = [_safe_float(c["close"]) for c in candles]
    highs = [_safe_float(c["high"]) for c in candles]
    lows = [_safe_float(c["low"]) for c in candles]
    volumes = [_safe_float(c["volume"]) for c in candles]

    last = candles[-1]
    last_close = _safe_float(last.get("close"), 0.0)
    last_high = _safe_float(last.get("high"), last_close)
    last_low = _safe_float(last.get("low"), last_close)
    last_vol = _safe_float(last.get("volume"), 0.0)

    if last_close <= 0:
        return None

    # ATR (en % du prix) sur 14 périodes
    try:
        atr_abs = atr(highs, lows, closes, period=14)
        atr_pct_14 = (atr_abs / last_close) * 100.0 if last_close > 0 else 0.0
    except ValueError:
        atr_pct_14 = 0.0

    # EMA20
    try:
        ema_20 = ema(closes, period=20)
    except ValueError:
        ema_20 = last_close

    # Range (high/low) des ~20 dernières bougies en % du close
    hi_20 = max(highs[-20:])
    lo_20 = min(lows[-20:])
    try:
        range_pct_20 = range_pct(hi_20, lo_20, last_close)
    except ValueError:
        range_pct_20 = 0.0

    # Trend score basé sur la pente de l'EMA20.
    # ema_slope renvoie un delta par bougie (unités de prix).
    # On le normalise par le prix et on le rescale grossièrement sur [-1, 1].
    try:
        slope_val = ema_slope(closes, period=20, lookback=5)
        raw = slope_val / last_close
        trend_score = max(-1.0, min(1.0, raw * 100.0))  # ~0.5%/bar → 0.5
    except ValueError:
        trend_score = 0.0

    return TimeframeSnapshot(
        close=last_close,
        high=last_high,
        low=last_low,
        volume=last_vol,
        ema_20=ema_20,
        atr_pct_14=atr_pct_14,
        range_pct_20=range_pct_20,
        trend_score=trend_score,
    )


def _derive_regime(timeframes: Dict[str, TimeframeSnapshot]) -> Dict[str, str]:
    """
    Synthèse qualitative "regime" à partir des métriques numériques.
    On reste volontairement simple & explicable.
    """
    tf = timeframes

    trend_scores: List[float] = []
    for key in ("4h", "1d", "1h"):
        snap = tf.get(key)
        if snap is not None:
            trend_scores.append(snap.trend_score)

    if trend_scores:
        avg_trend = mean(trend_scores)
    else:
        avg_trend = 0.0

    if avg_trend > 0.25:
        trend_regime = "bull"
    elif avg_trend < -0.25:
        trend_regime = "bear"
    else:
        trend_regime = "range"

    # Volatilité: on se base sur l'ATR% H1 si dispo, sinon 4h ou 15m.
    vol_sources: List[float] = []
    for key in ("1h", "4h", "15m"):
        snap = tf.get(key)
        if snap is not None:
            vol_sources.append(snap.atr_pct_14)

    vol = mean(vol_sources) if vol_sources else 0.0

    if vol < 1.0:
        vol_regime = "calm"
    elif vol < 3.0:
        vol_regime = "normal"
    else:
        vol_regime = "storm"

    return {
        "trend": trend_regime,
        "volatility": vol_regime,
    }


def _aggregate_top_level_factors(symbol: str, timeframes: Dict[str, TimeframeSnapshot]) -> Dict[str, Any]:
    """
    Crée les anciens facteurs "plats" (trend_strength, volatility, etc.)
    pour rester compatible avec generate_proposal_from_factors.
    """
    # Prix: on privilégie 15m puis 1h, puis 4h, sinon 0.
    price = 0.0
    for key in ("15m", "1h", "4h", "1d"):
        snap = timeframes.get(key)
        if snap is not None:
            price = snap.close
            break

    # Trend strength: moyenne simple des trend_score multi-TF.
    trend_scores = [snap.trend_score for snap in timeframes.values()]
    trend_strength = mean(trend_scores) if trend_scores else 0.0

    # Volatility scalaire 0–1 à partir de l'ATR% moyen.
    atr_vals = [snap.atr_pct_14 for snap in timeframes.values()]
    if atr_vals:
        atr_avg = mean(atr_vals)
        volatility = max(0.0, min(1.0, atr_avg / 5.0))  # 0–5% → 0–1
    else:
        volatility = 0.0

    # Pour l'instant, on ne branche pas encore des données réelles pour ces facteurs;
    # on les laisse neutres en attendant les sources dédiées (funding, dominance, news).
    funding_bias = 0.0
    btc_dominance = 0.0
    news_sentiment = 0.0

    return {
        "symbol": symbol,
        "price": price,
        "trend_strength": trend_strength,
        "funding_bias": funding_bias,
        "volatility": volatility,
        "btc_dominance": btc_dominance,
        "news_sentiment": news_sentiment,
    }


def get_market_snapshot(symbol: str = "BTCUSDC") -> Dict[str, Any]:
    """
    Factor Engine V4.2 — snapshot de marché enrichi pour un symbole.

    - Récupère des bougies OHLCV multi-timeframes via l'API publique `/api/v3/klines`.
    - Calcule quelques indicateurs de base (ATR%, EMA, range, trend_score).
    - Retourne un dict structuré:
      {
        "symbol": ...,
        "price": ...,
        "timeframes": {
            "15m": {...},
            "1h": {...},
            "4h": {...},
            "1d": {...},
        },
        "regime": {
            "trend": "bull|bear|range",
            "volatility": "calm|normal|storm",
        },
        # + anciens facteurs "plats" pour compatibilité:
        "trend_strength": ...,
        "funding_bias": ...,
        "volatility": ...,
        "btc_dominance": ...,
        "news_sentiment": ...,
      }

    Si un appel réseau échoue, le snapshot est dégradé mais reste bien formé
    (prix à 0.0, timeframes vides, facteurs neutres).
    """
    sym = symbol.upper().strip()

    if sym not in _SUPPORTED_SYMBOLS:
        # On laisse la possibilité d'utiliser d'autres paires, mais on signale l'anomalie
        # en renvoyant un snapshot neutre. Les appels amont peuvent décider de l'ignorer.
        return {
            "symbol": sym,
            "price": 0.0,
            "timeframes": {},
            "regime": {"trend": "range", "volatility": "normal"},
            "trend_strength": 0.0,
            "funding_bias": 0.0,
            "volatility": 0.0,
            "btc_dominance": 0.0,
            "news_sentiment": 0.0,
        }

    tf_snapshots: Dict[str, TimeframeSnapshot] = {}

    for tf, limit in _TIMEFRAMES.items():
        candles = fetch_klines(sym, interval=tf, limit=limit)
        snap = _compute_timeframe_snapshot(candles)
        if snap is not None:
            tf_snapshots[tf] = snap

    # Si aucun timeframe exploitable, on renvoie un snapshot neutre.
    if not tf_snapshots:
        return {
            "symbol": sym,
            "price": 0.0,
            "timeframes": {},
            "regime": {"trend": "range", "volatility": "normal"},
            "trend_strength": 0.0,
            "funding_bias": 0.0,
            "volatility": 0.0,
            "btc_dominance": 0.0,
            "news_sentiment": 0.0,
        }

    regime = _derive_regime(tf_snapshots)
    top = _aggregate_top_level_factors(sym, tf_snapshots)

    # On expose aussi les métriques brutes par timeframe pour le Setup Engine.
    timeframes_dict: Dict[str, Dict[str, Any]] = {}
    for tf, snap in tf_snapshots.items():
        timeframes_dict[tf] = {
            "close": snap.close,
            "high": snap.high,
            "low": snap.low,
            "volume": snap.volume,
            "ema_20": snap.ema_20,
            "atr_pct_14": snap.atr_pct_14,
            "range_pct_20": snap.range_pct_20,
            "trend_score": snap.trend_score,
        }

    snapshot: Dict[str, Any] = {
        **top,
        "timeframes": timeframes_dict,
        "regime": regime,
    }
    return snapshot


if __name__ == "__main__":
    # Test rapide: imprime un snapshot LIVE pour inspection manuelle.
    # Nécessite un accès réseau à l'API publique Binance.
    snap = get_market_snapshot("BTCUSDC")
    print("✅ Snapshot marché enrichi:", json.dumps(snap, ensure_ascii=False, indent=2))
