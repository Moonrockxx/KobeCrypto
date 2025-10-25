from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import Proposal

def test_generator_no_signal_when_factors_weak():
    market = {
        "symbol": "BTCUSDT",
        "price": 68000.0,
        "trend_strength": 0.2,     # trop faible
        "news_sentiment": 0.1,     # trop faible
        "funding_bias": 0.0,
        "volatility": 0.2,
        "btc_dominance": 0.5,
    }
    p = generate_proposal_from_factors(market)
    assert p is None

def test_generator_returns_valid_proposal_when_thresholds_met():
    market = {
        "symbol": "ETHUSDT",
        "price": 2400.0,
        "trend_strength": 0.75,    # > 0.6 → LONG
        "news_sentiment": 0.7,     # > 0.5 → LONG
        "funding_bias": 0.45,      # ajoute une raison
        "volatility": 0.7,         # ajoute une raison
        "btc_dominance": 0.58,     # ajoute une raison
    }
    p = generate_proposal_from_factors(market)
    assert isinstance(p, Proposal)
    assert p.side == "long"
    assert p.symbol == "ETHUSDT"
    assert p.entry > 0 and p.stop > 0 and p.take > 0
    # cohérence niveaux LONG: stop < entry < take
    assert p.stop < p.entry < p.take
    # au moins 3 raisons
    assert len(p.reasons) >= 3
