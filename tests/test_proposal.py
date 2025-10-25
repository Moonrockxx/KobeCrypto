from kobe.signals.proposal import Proposal, position_size

def test_valid_proposal_long():
    p = Proposal(
        symbol="BTCUSDT",
        side="long",
        entry=68000.0,
        stop=67200.0,
        take=69600.0,
        risk_pct=0.25,
        size_pct=5.0,
        reasons=["Breakout", "Funding neutre", "Corrélation SPX"],
    )
    assert p.side == "long"
    assert p.r_multiple() > 0
    assert not p.is_expired()
    assert 0 < p.r_multiple() < 3

def test_invalid_stop_take_long():
    from pytest import raises
    with raises(ValueError):
        Proposal(
            symbol="BTCUSDT",
            side="long",
            entry=68000.0,
            stop=69000.0,  # invalide : stop > entry
            take=70000.0,
            risk_pct=0.25,
            size_pct=5.0,
            reasons=["A", "B", "C"],
        )

def test_r_multiple_short():
    p = Proposal(
        symbol="BTCUSDT",
        side="short",
        entry=68000.0,
        stop=68600.0,
        take=66400.0,
        risk_pct=0.25,
        size_pct=5.0,
        reasons=["A", "B", "C"],
    )
    r = p.r_multiple()
    assert isinstance(r, float)
    assert r > 1.0

def test_position_size_basic():
    q = position_size(10000, 0.25, 68000.0, 67200.0, leverage=2.0)
    assert q > 0
    assert round(q, 6) != 0

def test_reasons_validation():
    from pytest import raises
    with raises(ValueError):
        Proposal(
            symbol="BTCUSDT",
            side="long",
            entry=68000.0,
            stop=67200.0,
            take=69600.0,
            risk_pct=0.25,
            size_pct=5.0,
            reasons=["Seulement deux", "Raisons"],  # <3
        )
