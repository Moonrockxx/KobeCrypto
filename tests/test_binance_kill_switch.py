import os
import json
from pathlib import Path

from kobe.execution.binance_spot import BinanceSpot

def test_kill_switch_blocks_order(monkeypatch, tmp_path):
    # 1) Forcer les variables du kill-switch
    os.environ["MAX_DAILY_LOSS_EUR"] = "25"
    os.environ["KOBE_DAILY_LOSS_EUR"] = "-30"  # perte journalière déjà au-delà du max

    # 2) Rediriger le log exécuteur vers un fichier de test
    log_path = tmp_path / "executor_kill_switch.jsonl"
    os.environ["KOBE_EXECUTOR_LOG"] = str(log_path)

    # 3) Monkeypatch pour garantir qu'aucun POST signé n'est appelé
    def fake_signed_post(self, path, params=None, timeout=8):
        raise AssertionError("BinanceSpot._signed_post ne doit jamais être appelé quand le kill-switch est actif")

    monkeypatch.setattr(BinanceSpot, "_signed_post", fake_signed_post, raising=True)

    # 4) Appel de create_order : doit être bloqué par le kill-switch AVANT tout appel réseau
    b = BinanceSpot(key="dummy", secret="dummy")
    resp = b.create_order("BTCUSDC", "BUY", 0.01)

    assert isinstance(resp, dict)
    assert resp.get("error") == "kill_switch"

    # 5) Vérifier que l'event est bien logué avec le bon statut
    assert log_path.exists(), "Le fichier de log du kill-switch devrait exister"

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 1
    evt = json.loads(lines[-1])
    assert evt.get("status") == "kill_switch_blocked"
    assert evt.get("symbol") == "BTCUSDC"
