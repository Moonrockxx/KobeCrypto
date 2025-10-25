from __future__ import annotations
import math, time, random
from typing import Dict, Any

def get_market_snapshot(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """
    Fournit un snapshot déterministe (mock) des facteurs de marché pour V1.
    - price varie légèrement autour d'un pivot fixe
    - les autres facteurs oscillent de manière stable (sinusoïdes)
    """
    base_prices = {"BTCUSDT": 68000.0, "ETHUSDT": 2400.0, "SOLUSDT": 180.0}
    base = base_prices.get(symbol.upper(), 1000.0)
    now = time.time()
    cycle = math.sin(now / 600.0)  # oscillation ~10min

    # variation faible de prix ±0.3 %
    price = base * (1 + 0.003 * cycle)

    # facteurs pseudo-stables pour test
    trend_strength = round(cycle, 3)
    funding_bias = round(math.sin(now / 900.0) * 0.3, 3)
    volatility = round(abs(math.sin(now / 1200.0)), 3)
    btc_dominance = round(0.55 + 0.05 * math.sin(now / 1800.0), 3)
    news_sentiment = round(math.sin(now / 1500.0), 3)

    snapshot = {
        "symbol": symbol.upper(),
        "price": price,
        "trend_strength": trend_strength,
        "funding_bias": funding_bias,
        "volatility": volatility,
        "btc_dominance": btc_dominance,
        "news_sentiment": news_sentiment,
    }
    return snapshot

# Test local (doit afficher un dict stable)
if __name__ == "__main__":
    snap = get_market_snapshot("ETHUSDT")
    print("✅ Facteurs mock:", snap)
