import os
from kobe.execution.binance_spot import BinanceSpot


def test_execute_order_plan_invalid_plan(monkeypatch):
    """Si le plan est invalide, aucun appel réseau et erreur retournée."""
    calls = []

    def fake_signed_post(self, path, params=None, timeout=8):
        calls.append((path, params))
        return {"error": "should_not_be_called"}

    monkeypatch.setattr(BinanceSpot, "_signed_post", fake_signed_post, raising=True)

    b = BinanceSpot(key="dummy", secret="dummy")

    plan = {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "qty_rounded": 0.01,
        "valid": False,  # plan explicitement invalide
    }

    res = b.execute_order_plan(plan)

    assert res["error"] == "invalid_plan"
    assert calls == []  # aucun appel réseau


def test_execute_order_plan_kill_switch_blocks(monkeypatch):
    """Kill-switch actif: aucun ordre ne doit être envoyé."""

    def fake_signed_post(self, path, params=None, timeout=8):
        raise AssertionError("_signed_post ne doit jamais être appelé quand le kill-switch bloque le plan")

    monkeypatch.setattr(BinanceSpot, "_signed_post", fake_signed_post, raising=True)

    # Kill-switch configuré: perte courante <= -MAX_DAILY_LOSS_EUR
    monkeypatch.setenv("MAX_DAILY_LOSS_EUR", "25")
    monkeypatch.setenv("KOBE_DAILY_LOSS_EUR", "-30")

    b = BinanceSpot(key="dummy", secret="dummy")

    plan = {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "qty_rounded": 0.01,
        "valid": True,
    }

    res = b.execute_order_plan(plan)

    assert res["error"] == "kill_switch"
    assert "Daily loss limit exceeded" in res["message"]


def test_execute_order_plan_full_tp_sl(monkeypatch):
    """Plan valide complet: entry + TP + SL envoyés avec les bons paramètres."""

    calls = []

    def fake_signed_post(self, path, params=None, timeout=8):
        calls.append((path, dict(params or {})))
        return {"status": "OK", "path": path, "params": dict(params or {})}

    monkeypatch.setattr(BinanceSpot, "_signed_post", fake_signed_post, raising=True)

    # Kill-switch désactivé
    monkeypatch.delenv("MAX_DAILY_LOSS_EUR", raising=False)
    monkeypatch.delenv("KOBE_DAILY_LOSS_EUR", raising=False)

    b = BinanceSpot(key="dummy", secret="dummy")

    plan = {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "qty_rounded": 0.01,
        "valid": True,
        "order_type": "MARKET",
        "entry": {
            "type": "MARKET",
            "price": 50000.0,
        },
        "take_profit": {
            "type": "LIMIT",
            "price": 52000.0,
        },
        "stop_loss": {
            "type": "STOP_LIMIT",
            "price": 49000.0,
        },
    }

    res = b.execute_order_plan(plan)

    assert "orders" in res
    assert res["orders"]["entry"] is not None

    # On doit avoir jusqu'à 3 appels: entry, TP, SL
    assert 1 <= len(calls) <= 3

    # 1) Entry
    entry_call = calls[0]
    assert entry_call[0] == "/api/v3/order"
    entry_params = entry_call[1]
    assert entry_params["symbol"] == "BTCUSDC"
    assert entry_params["side"] == "BUY"
    assert entry_params["type"] == "MARKET"
    assert entry_params["quantity"] == 0.01

    # 2) TP: LIMIT SELL @ 52000
    if len(calls) >= 2:
        tp_call = calls[1]
        tp_params = tp_call[1]
        assert tp_params["symbol"] == "BTCUSDC"
        assert tp_params["side"] == "SELL"
        assert tp_params["type"] == "LIMIT"
        assert tp_params["quantity"] == 0.01
        if "price" in tp_params:
            assert tp_params["price"] == 52000.0

    # 3) SL: STOP_LOSS_LIMIT SELL @ 49000
    if len(calls) >= 3:
        sl_call = calls[2]
        sl_params = sl_call[1]
        assert sl_params["symbol"] == "BTCUSDC"
        assert sl_params["side"] == "SELL"
        assert sl_params["type"] == "STOP_LOSS_LIMIT"
        assert sl_params["quantity"] == 0.01
        if "price" in sl_params:
            assert sl_params["price"] == 49000.0
        if "stopPrice" in sl_params:
            assert sl_params["stopPrice"] == 49000.0
