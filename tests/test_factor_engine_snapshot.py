import sys
import types

try:
    # Si le module existe vraiment (en local), on l'utilise.
    import kobe.data.binance_ohlc as _binance_ohlc  # type: ignore[unused]
except ModuleNotFoundError:
    # En CI (ou environnement incomplet), on crée un module factice
    pkg = types.ModuleType("kobe.data")
    mod = types.ModuleType("kobe.data.binance_ohlc")

    def _dummy_fetch_klines(symbol: str, interval: str, limit: int):
        # Cette fonction sera systématiquement monkeypatchée dans les tests.
        raise RuntimeError("fetch_klines should be monkeypatched in tests")

    mod.fetch_klines = _dummy_fetch_klines
    sys.modules["kobe.data"] = pkg
    sys.modules["kobe.data.binance_ohlc"] = mod

from kobe.core.factors import get_market_snapshot
import pytest


def _make_fake_candles(n: int, base: float = 100.0, spread: float = 1.0):
    candles = []
    for i in range(n):
        close = base + (i * 0.01)
        high = close + spread * 0.5
        low = close - spread * 0.5
        volume = 10.0 + i
        candles.append(
            {
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return candles


def test_get_market_snapshot_structure(monkeypatch):
    """Vérifie que le Factor Engine renvoie un snapshot bien formé pour BTCUSDC."""

    def fake_fetch_klines(symbol: str, interval: str, limit: int):
        # On ignore symbol/interval pour ce test, on renvoie juste assez de bougies.
        return _make_fake_candles(max(limit, 50))

    # On monkeypatch la fonction réseau pour éviter tout appel réel à Binance.
    monkeypatch.setattr("kobe.core.factors.fetch_klines", fake_fetch_klines)

    snap = get_market_snapshot("BTCUSDC")

    # Clés top-level attendues
    for key in (
        "symbol",
        "price",
        "timeframes",
        "regime",
        "trend_strength",
        "funding_bias",
        "volatility",
        "btc_dominance",
        "news_sentiment",
    ):
        assert key in snap, f"clé manquante dans snapshot: {key}"

    assert snap["symbol"] == "BTCUSDC"
    assert isinstance(snap["timeframes"], dict)
    assert isinstance(snap["regime"], dict)

    # Structure des timeframes
    for tf in ("15m", "1h", "4h", "1d"):
        tf_snap = snap["timeframes"].get(tf)
        assert tf_snap is not None, f"timeframe manquante: {tf}"

        for k in (
            "close",
            "high",
            "low",
            "volume",
            "ema_20",
            "atr_pct_14",
            "range_pct_20",
            "trend_score",
        ):
            assert k in tf_snap, f"champ manquant dans {tf}: {k}"

    # Regime cohérent
    trend = snap["regime"].get("trend")
    vol = snap["regime"].get("volatility")
    assert trend in {"bull", "bear", "range"}
    assert vol in {"calm", "normal", "storm"}

    # Prix top-level > 0 grâce aux timeframes simulées
    assert snap["price"] > 0.0
