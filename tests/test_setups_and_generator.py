from kobe.signals.setups import scan_setups
from kobe.signals.generator import generate_proposal_from_factors


def _make_breakout_snapshot():
    """Snapshot artificiel configuré pour déclencher le playbook breakout trend (long)."""
    return {
        "symbol": "BTCUSDC",
        "timeframes": {
            "15m": {
                "close": 100.0,
                "high": 100.1,
                "low": 99.0,
                "volume": 10.0,
                "ema_20": 98.0,
                "atr_pct_14": 0.5,
                "range_pct_20": 2.0,
                "trend_score": 0.4,
            },
            "1h": {
                "close": 100.0,
                "high": 100.1,
                "low": 98.0,
                "volume": 20.0,
                "ema_20": 97.0,
                "atr_pct_14": 1.0,   # < 2.0
                "range_pct_20": 3.0,  # < 4.0
                "trend_score": 0.5,
            },
            "4h": {
                "close": 100.0,
                "high": 102.0,
                "low": 95.0,
                "volume": 30.0,
                "ema_20": 96.0,
                "atr_pct_14": 1.5,
                "range_pct_20": 5.0,
                "trend_score": 0.8,   # > 0.6
            },
            "1d": {
                "close": 100.0,
                "high": 105.0,
                "low": 90.0,
                "volume": 40.0,
                "ema_20": 95.0,
                "atr_pct_14": 2.5,
                "range_pct_20": 10.0,
                "trend_score": 0.7,   # > 0.5
            },
        },
        "regime": {"trend": "bull", "volatility": "normal"},
    }


def test_scan_setups_breakout_candidate():
    snapshot = _make_breakout_snapshot()
    candidates = scan_setups(snapshot)

    assert candidates, "scan_setups doit produire au moins un candidat sur snapshot breakout."
    first = candidates[0]

    assert first["symbol"] == "BTCUSDC"
    assert first["side"] == "long"
    reasons = first.get("reasons") or []
    assert isinstance(reasons, list)
    assert len(reasons) >= 3, "Invariant projet : ≥ 3 raisons par signal."


def test_generate_proposal_from_factors_breakout():
    snapshot = _make_breakout_snapshot()
    p = generate_proposal_from_factors(snapshot)

    assert p is not None, "generate_proposal_from_factors doit renvoyer une Proposal sur snapshot breakout."
    assert p.symbol == "BTCUSDC"
    assert p.side == "long"

    # Prix cohérents (> 0) et structure de base OK
    assert p.entry > 0
    assert p.stop > 0
    assert p.take > 0

    assert len(p.reasons) >= 3
    assert 0 < p.risk_pct <= 0.5
    assert p.ttl_minutes > 0
