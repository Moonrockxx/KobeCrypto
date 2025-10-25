import types
import pytest

from kobe.core.adapter.binance import BinanceAdapter

class DummyResp:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self): 
        return
    def json(self):
        return self._payload

def test_load_markets_uses_mock_when_network_fails(monkeypatch):
    # Force _get à lever une exception réseau → fallback mock attendu
    ex = BinanceAdapter()
    def boom(*a, **k):
        raise Exception("network down")
    monkeypatch.setattr(ex, "_get", boom)
    mkts = ex.load_markets()
    # Fallback doit renvoyer au moins BTCUSDT/ETHUSDT
    assert "BTCUSDT" in mkts and "ETHUSDT" in mkts

def test_load_markets_filters_usdt_and_truncates(monkeypatch):
    # Simule une réponse /exchangeInfo contrôlée
    payload = {
        "symbols": [
            {"symbol": "BTCUSDT", "quoteAsset": "USDT"},
            {"symbol": "ETHUSDT", "quoteAsset": "USDT"},
            {"symbol": "BTCBUSD", "quoteAsset": "BUSD"},
            {"symbol": "FOOXYZ", "quoteAsset": "XYZ"},
        ]
    }
    ex = BinanceAdapter()
    monkeypatch.setattr(ex, "_get", lambda *a, **k: payload)
    mkts = ex.load_markets(quote_filter="USDT", max_markets=1)
    # Filtré sur USDT et tronqué à 1 élément
    assert list(mkts.keys()) == ["BTCUSDT"]

def test_create_order_mock_positive_flow():
    ex = BinanceAdapter()
    od = ex.create_order("BTCUSDT", "buy", "market", qty=0.001)
    assert od["status"].lower() == "filled"
    assert od["symbol"] == "BTCUSDT"
    assert od["qty"] == 0.001

def test_create_order_rejects_non_positive_qty():
    ex = BinanceAdapter()
    with pytest.raises(Exception):
        ex.create_order("BTCUSDT", "buy", "market", qty=0.0)
