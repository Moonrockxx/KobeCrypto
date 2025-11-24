from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import Proposal


def test_generator_no_signal_when_factors_weak():
    # Snapshot incomplet / neutre → aucun setup détectable
    market = {
        "symbol": "BTCUSDC",
        "timeframes": {},
        "regime": {"trend": "range", "volatility": "normal"},
    }
    p = generate_proposal_from_factors(market)
    assert p is None


def test_generator_returns_valid_proposal_when_thresholds_met():
    # Snapshot artificiel construit pour activer le playbook
    # "trend_breakout_15m_long" dans kobe.signals.setups.scan_setups
    market = {
        "symbol": "BTCUSDC",
        "timeframes": {
            "15m": {
                "close": 100.0,
                "high": 100.1,
                "low": 99.0,
                "volume": 10.0,
                "ema_20": 99.5,
                "atr_pct_14": 0.5,
                "range_pct_20": 1.0,
                "trend_score": 0.4,
            },
            "1h": {
                "close": 100.0,
                "high": 100.5,
                "low": 98.5,
                "volume": 50.0,
                "ema_20": 99.0,
                "atr_pct_14": 1.5,   # < 2.0
                "range_pct_20": 3.0,  # < 4.0
                "trend_score": 0.7,
            },
            "4h": {
                "close": 100.0,
                "high": 101.0,
                "low": 97.0,
                "volume": 200.0,
                "ema_20": 99.0,
                "atr_pct_14": 2.0,
                "range_pct_20": 5.0,
                "trend_score": 0.8,   # > 0.6
            },
            "1d": {
                "close": 100.0,
                "high": 102.0,
                "low": 95.0,
                "volume": 500.0,
                "ema_20": 98.0,
                "atr_pct_14": 2.5,
                "range_pct_20": 6.0,
                "trend_score": 0.7,   # > 0.5
            },
        },
        "regime": {"trend": "bull", "volatility": "normal"},
    }

    p = generate_proposal_from_factors(market)
    assert isinstance(p, Proposal)
    assert p.side == "long"
    assert p.symbol == "BTCUSDC"
    assert p.entry > 0 and p.stop > 0 and p.take > 0

    # Cohérence niveaux :
    # pour un LONG: stop < entry < take
    assert p.stop < p.entry < p.take

    # Au moins 3 raisons explicites
    assert len(p.reasons) >= 3
