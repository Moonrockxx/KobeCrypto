import os
import json

from kobe.execution.binance_spot import BinanceSpot

def test_tp_sl_are_logged(monkeypatch, tmp_path):
    # 1) Rediriger le log exécuteur vers un fichier temporaire
    log_path = tmp_path / "executor_tp_sl.jsonl"
    os.environ["KOBE_EXECUTOR_LOG"] = str(log_path)

    # 2) Désactiver toute clé réelle et monkeypatcher _signed_post
    os.environ["BINANCE_API_KEY"] = ""
    os.environ["BINANCE_API_SECRET"] = ""

    def fake_signed_post(self, path, params=None, timeout=8):
        # On simule une réponse 'binance' sans toucher au réseau
        return {"orderId": 123456, "status": "NEW", "symbol": params.get("symbol")}

    monkeypatch.setattr(BinanceSpot, "_signed_post", fake_signed_post, raising=True)

    # 3) Appel de create_order avec TP/SL
    b = BinanceSpot()
    resp = b.create_order(
        "BTCUSDC",
        "BUY",
        0.01,
        take_price=70000.0,
        stop_price=67000.0,
    )

    # 4) On doit avoir la réponse fake, pas None
    assert isinstance(resp, dict)
    assert resp.get("orderId") == 123456

    # 5) Vérifier que le log contient bien take_price / stop_price
    assert log_path.exists(), "Le log exécuteur TP/SL devrait exister"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1

    evt = json.loads(lines[-1])
    assert evt.get("symbol") == "BTCUSDC"
    assert evt.get("take_price") == 70000.0
    assert evt.get("stop_price") == 67000.0
    assert evt.get("params", {}).get("quantity") == 0.01
