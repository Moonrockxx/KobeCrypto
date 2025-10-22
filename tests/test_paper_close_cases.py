import os, json, tempfile, math, pytest
from kobe.cli_paper_close import close_trade

@pytest.mark.parametrize("case,side,entry,qty,price,exp_pnl,exp_pct", [
    ("short_gagnant", "short", 110.0, 2.0, 100.0, +20.0,  9.0909),  # (110-100)*2 ; pct ~ +9.09%
    ("long_perdant",  "long",  100.0, 2.0,  95.0, -10.0, -5.0000),  # (95-100)*2  ; pct -5.00%
])
def test_close_parametres(case, side, entry, qty, price, exp_pnl, exp_pct):
    with tempfile.TemporaryDirectory() as td:
        rec = close_trade(symbol="BTCUSDT", side=side, entry=entry, qty=qty, price=price, reason=case, logs_dir=td)
        assert rec["event"] == "paper_close"
        assert rec["symbol"] == "BTCUSDT"
        # PnL absolu
        assert abs(rec["pnl"] - exp_pnl) < 1e-9
        # PnL % (tolérance ~1e-3)
        assert math.isclose(rec["pnl_pct"], exp_pct, rel_tol=0, abs_tol=1e-3)
        # Traces écrites
        jpath = os.path.join(td, "journal.jsonl")
        cpath = os.path.join(td, "journal.csv")
        assert os.path.exists(jpath) and os.path.getsize(jpath) > 0
        assert os.path.exists(cpath) and os.path.getsize(cpath) > 0
        # Cohérence JSONL 1ère ligne
        with open(jpath, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())
            assert data["side"] == side
            assert data["pnl"] == rec["pnl"]
