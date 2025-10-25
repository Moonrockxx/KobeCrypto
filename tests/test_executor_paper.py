from pathlib import Path
from kobe.signals.proposal import Proposal
from kobe.core import executor as ex

def _setup_tmp_logs(tmp_path, monkeypatch):
    # Redirige tous les fichiers de positions vers un dossier temporaire
    monkeypatch.setattr("kobe.core.executor.POS_LOG_DIR", tmp_path)
    monkeypatch.setattr("kobe.core.executor.POS_CSV_PATH", tmp_path / "positions.csv")
    monkeypatch.setattr("kobe.core.executor.POS_JSONL_PATH", tmp_path / "positions.jsonl")

def test_long_tp_positive_pnl(tmp_path, monkeypatch):
    _setup_tmp_logs(tmp_path, monkeypatch)
    p = Proposal(
        symbol="BTCUSDT", side="long",
        entry=68000.0, stop=67200.0, take=69600.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=["A","B","C"]
    )
    open_evt = ex.simulate_open(p, balance_usd=10_000.0, leverage=2.0)
    closed_evt = ex.simulate_close(open_evt, price=p.take, reason="hit_tp")

    assert (tmp_path / "positions.csv").exists()
    assert (tmp_path / "positions.jsonl").exists()
    assert float(closed_evt["realized_pnl_usd"]) > 0.0
    assert closed_evt["status"] == "closed"

def test_short_sl_negative_pnl(tmp_path, monkeypatch):
    _setup_tmp_logs(tmp_path, monkeypatch)
    p = Proposal(
        symbol="ETHUSDT", side="short",
        entry=2400.0, stop=2430.0, take=2340.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=["A","B","C"]
    )
    open_evt = ex.simulate_open(p, balance_usd=5_000.0, leverage=1.0)
    # Ferme au prix du stop -> perte attendue sur une position short
    closed_evt = ex.simulate_close(open_evt, price=p.stop, reason="hit_sl")

    assert float(closed_evt["realized_pnl_usd"]) < 0.0
    assert closed_evt["status"] == "closed"
