from __future__ import annotations
from typing import Dict, Any

from kobe.execution.binance_spot import BinanceSpot

def get_market_snapshot(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """Retourne un snapshot de marché basé sur le prix spot réel Binance.

    - `price` est le dernier prix spot retourné par `/api/v3/ticker/price`.
    - Les autres facteurs (trend_strength, funding_bias, volatility, btc_dominance,
      news_sentiment) sont laissés neutres (0.0) en attendant un scanner plus riche.

    Si l'appel réseau échoue ou que le prix est invalide, `price` vaut 0.0 et
    l'appelant est libre de ne pas générer de signal.
    """
    sym = symbol.upper()

    # Utilise l'adaptateur BinanceSpot pour récupérer le prix spot public.
    spot = BinanceSpot()
    price: float = 0.0
    try:
        resp = spot.get_price(sym)
        if isinstance(resp, dict):
            raw_price = resp.get("price")
            if raw_price is not None:
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    price = 0.0
    except Exception:
        # En cas d'erreur réseau ou autre, on laisse price=0.0
        price = 0.0

    snapshot: Dict[str, Any] = {
        "symbol": sym,
        "price": price,
        # Facteurs neutres (aucune donnée factice) en attendant mieux
        "trend_strength": 0.0,
        "funding_bias": 0.0,
        "volatility": 0.0,
        "btc_dominance": 0.0,
        "news_sentiment": 0.0,
    }
    return snapshot


if __name__ == "__main__":
    # Test rapide: imprime un snapshot LIVE pour inspection manuelle.
    snap = get_market_snapshot("ETHUSDT")
    print("✅ Snapshot marché:", snap)
