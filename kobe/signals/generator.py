from __future__ import annotations
from typing import Optional, Dict, Any
from random import choice
from kobe.signals.proposal import Proposal

def generate_proposal_from_factors(market: Dict[str, Any]) -> Optional[Proposal]:
    """
    Prototype de génération d'une proposal à partir de facteurs multi-sources.
    Renvoie None si pas assez de signaux convergents.
    """
    # --- 1. Collecte de signaux simples (mock V1) ---
    # Chaque facteur du dict est supposé être un score de confiance 0–1
    trend = market.get("trend_strength", 0)
    funding = market.get("funding_bias", 0)
    volatility = market.get("volatility", 0)
    dominance = market.get("btc_dominance", 0)
    news_sentiment = market.get("news_sentiment", 0)

    # --- 2. Décision de direction ---
    if trend > 0.6 and news_sentiment > 0.5:
        side = "long"
    elif trend < -0.6 and news_sentiment < -0.5:
        side = "short"
    else:
        return None  # Pas assez net

    # --- 3. Construction des niveaux ---
    price = float(market.get("price", 0))
    if price <= 0:
        return None

    if side == "long":
        entry = price
        stop = price * (1 - 0.012)  # -1.2 %
        take = price * (1 + 0.025)  # +2.5 %
    else:
        entry = price
        stop = price * (1 + 0.012)
        take = price * (1 - 0.025)

    # --- 4. Raisons cumulées ---
    reasons = []
    if abs(trend) > 0.6:
        reasons.append(f"Tendance {'haussière' if side=='long' else 'baissière'} forte ({trend:.2f})")
    if abs(news_sentiment) > 0.5:
        reasons.append(f"Sentiment news {'positif' if side=='long' else 'négatif'} ({news_sentiment:.2f})")
    if abs(funding) > 0.4:
        reasons.append(f"Funding {'longs' if funding>0 else 'shorts'} déséquilibré ({funding:.2f})")
    if volatility > 0.5:
        reasons.append(f"Volatilité élevée ({volatility:.2f})")
    if dominance > 0.55:
        reasons.append(f"Dominance BTC forte ({dominance:.2f})")

    # Moins de 3 raisons => pas de signal
    if len(reasons) < 3:
        return None

    # --- 5. Création de la Proposal ---
    p = Proposal(
        symbol=market.get("symbol", "BTCUSDT"),
        side=side,
        entry=round(entry, 2),
        stop=round(stop, 2),
        take=round(take, 2),
        risk_pct=0.25,
        size_pct=5.0,
        reasons=reasons[:5],
        ttl_minutes=45,
    )
    return p

# --- Test rapide (mock factors) ---
if __name__ == "__main__":
    market_sample = {
        "symbol": "ETHUSDT",
        "price": 2400.0,
        "trend_strength": 0.75,
        "funding_bias": 0.1,
        "volatility": 0.6,
        "btc_dominance": 0.58,
        "news_sentiment": 0.7,
    }
    p = generate_proposal_from_factors(market_sample)
    if p:
        print("✅ Proposal générée:", p.symbol, p.side, "→", len(p.reasons), "raisons.")
    else:
        print("⚙️  Aucun signal.")
