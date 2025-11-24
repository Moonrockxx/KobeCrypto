from kobe.llm.signal_review import review_signal


def test_review_signal_bypass_mode():
    snapshot = {
        "symbol": "BTCUSDC",
        "regime": {"trend": "bull", "volatility": "normal"},
        "timeframes": {},
    }
    proposal = {
        "symbol": "BTCUSDC",
        "side": "long",
        "entry": 100.0,
        "stop": 95.0,
        "take": 110.0,
        "reasons": [
            "Trend haussier H4.",
            "Pullback vers zone de valeur.",
            "Volatilité modérée.",
        ],
    }

    result = review_signal(snapshot, proposal, enabled=False)

    assert result["mode"] == "bypass"
    assert result["decision"] == "take"
    assert result["confidence"] == 1.0
    assert "Referee LLM désactivé" in result["comment"]
    assert result["raw"] is None