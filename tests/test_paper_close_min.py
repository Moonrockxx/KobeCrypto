import os, json, tempfile
from kobe.cli_paper_close import close_trade

def test_close_long_positive():
    with tempfile.TemporaryDirectory() as td:
        rec = close_trade(
            symbol="BTCUSDC", side="long",
            entry=100.0, qty=2.0, price=110.0,
            reason="test", logs_dir=td
        )
        assert rec["event"] == "paper_close"
        assert rec["symbol"] == "BTCUSDC"
        assert abs(rec["pnl"] - 20.0) < 1e-9
        jpath = os.path.join(td, "journal.jsonl")
        assert os.path.exists(jpath)
        with open(jpath, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
            assert data["pnl"] == rec["pnl"]
        cpath = os.path.join(td, "journal.csv")
        assert os.path.exists(cpath) and os.path.getsize(cpath) > 0
