from kobe.llm.signal_review import review_signal
from unittest import mock

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


@mock.patch("kobe.llm.signal_review.chat_complete_json")
def test_review_signal_network_error_fallback(mock_chat):
    # Simuler une panne réseau ou un dépassement de budget
    mock_chat.return_value = (False, {"error": "network_error"})
    
    snapshot = {"symbol": "BTCUSDC"}
    proposal = {"symbol": "BTCUSDC", "side": "long"}
    
    # Par défaut, le fallback doit être "skip"
    result = review_signal(snapshot, proposal)
    
    assert result["mode"] == "error"
    assert result["decision"] == "skip"
    assert result["confidence"] == 0.0
    assert "network_error" in result["comment"]

@mock.patch("kobe.llm.signal_review.chat_complete_json")
def test_review_signal_invalid_json_fallback(mock_chat):
    # Simuler une réponse texte qui n'est pas du JSON
    mock_chat.return_value = (True, {"text": "Désolé, je ne peux pas formater en JSON."})
    
    snapshot = {"symbol": "BTCUSDC"}
    proposal = {"symbol": "BTCUSDC", "side": "long"}
    
    result = review_signal(snapshot, proposal)
    
    assert result["mode"] == "error"
    assert result["decision"] == "skip"
    assert result["confidence"] == 0.0
    assert "non JSON ou invalide" in result["comment"]