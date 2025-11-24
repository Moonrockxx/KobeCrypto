import pytest

from kobe.cli.schedule import run_auto_proposal_job
from kobe.signals.proposal import Proposal


def _make_dummy_proposal() -> Proposal:
    return Proposal(
        symbol="BTCUSDC",
        side="long",
        entry=100.0,
        stop=99.0,
        take=102.0,
        risk_pct=0.0025,
        size_pct=5.0,
        reasons=[
            "Trend H4 haussière",
            "Retest support propre",
            "Volatilité modérée",
        ],
        ttl_minutes=60,
    )


def test_auto_job_referee_skip(monkeypatch):
    captured = {}

    def fake_snapshot(symbol: str):
        return {
            "symbol": symbol,
            "regime": {"trend": "bull", "volatility": "normal"},
            "timeframes": {},
        }

    def fake_generator(snapshot):
        p = _make_dummy_proposal()
        captured["p"] = p
        return p

    def fake_review(snapshot, proposal_dict, enabled=True, max_tokens=256):
        return {
            "mode": "ok",
            "decision": "skip",
            "confidence": 0.8,
            "comment": "Setup jugé trop fragile (test).",
            "raw": {},
        }

    monkeypatch.setattr("kobe.cli.schedule.get_market_snapshot", fake_snapshot)
    monkeypatch.setattr("kobe.cli.schedule.generate_proposal_from_factors", fake_generator)
    monkeypatch.setattr("kobe.cli.schedule.review_signal", fake_review)

    ok = run_auto_proposal_job(
        symbol="BTCUSDC",
        risk_cfg=None,
        notifier=None,
        trades_alerts_enabled=False,
        referee_enabled=True,
    )

    # Le referee bloque le setup → pas de signal envoyé
    assert ok is False
    # La proposal a quand même été construite avant décision
    assert "p" in captured


def test_auto_job_referee_take_enriches_reasons(monkeypatch):
    captured = {}

    def fake_snapshot(symbol: str):
        return {
            "symbol": symbol,
            "regime": {"trend": "bull", "volatility": "normal"},
            "timeframes": {},
        }

    def fake_generator(snapshot):
        p = _make_dummy_proposal()
        captured["p"] = p
        return p

    def fake_review(snapshot, proposal_dict, enabled=True, max_tokens=256):
        return {
            "mode": "ok",
            "decision": "take",
            "confidence": 0.9,
            "comment": "Trade cohérent avec le contexte (test).",
            "raw": {},
        }

    monkeypatch.setattr("kobe.cli.schedule.get_market_snapshot", fake_snapshot)
    monkeypatch.setattr("kobe.cli.schedule.generate_proposal_from_factors", fake_generator)
    monkeypatch.setattr("kobe.cli.schedule.review_signal", fake_review)

    ok = run_auto_proposal_job(
        symbol="BTCUSDC",
        risk_cfg=None,
        notifier=None,
        trades_alerts_enabled=False,
        referee_enabled=True,
    )

    assert ok is True

    # Le referee doit avoir enrichi les raisons sans dépasser 5 au total
    p = captured["p"]
    assert any("Referee LLM" in r for r in p.reasons)
    assert len(p.reasons) <= 5
