import pytest
from kobe.signals.proposal import Proposal
from kobe.core.risk import validate_proposal, RiskConfig

def test_accept_within_limits_proposal():
    cfg = RiskConfig(max_trade_pct=0.5, max_proposal_pct=0.25)
    p = Proposal(
        symbol="BTCUSDT", side="long",
        entry=68000.0, stop=67200.0, take=69600.0,
        risk_pct=0.20, size_pct=5.0,
        reasons=["A","B","C"]
    )
    assert validate_proposal(p, cfg, is_proposal=True) is True

def test_reject_over_limit_trade():
    # Ici on ne heurte pas Pydantic (risk_pct <= 0.25),
    # mais on force un plafond trade plus strict dans la config.
    cfg = RiskConfig(max_trade_pct=0.20, max_proposal_pct=0.25)
    p = Proposal(
        symbol="ETHUSDT", side="short",
        entry=2400.0, stop=2430.0, take=2340.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=["A","B","C"]
    )
    with pytest.raises(ValueError):
        validate_proposal(p, cfg, is_proposal=False)

def test_invalid_levels_rejected_by_model():
    # Le modèle Proposal rejette déjà les niveaux incohérents (avant le guard).
    with pytest.raises(ValueError):
        Proposal(
            symbol="BTCUSDT", side="long",
            entry=68000.0, stop=69000.0, take=70000.0,  # stop > entry → invalide
            risk_pct=0.25, size_pct=5.0,
            reasons=["A","B","C"]
        )

def test_too_few_reasons_rejected_by_model():
    # Le modèle Proposal impose ≥ 3 raisons non vides.
    with pytest.raises(ValueError):
        Proposal(
            symbol="BTCUSDT", side="long",
            entry=68000.0, stop=67200.0, take=69600.0,
            risk_pct=0.25, size_pct=5.0,
            reasons=["Seulement", "Deux"]
        )
