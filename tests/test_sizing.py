from kobe.core.sizing import size_for_risk
def test_size_for_risk_basic():
    qty, risk_amt = size_for_risk(equity=10000, risk_pct=0.5, entry=100.0, stop=95.0, lot_step=0.001)
    assert abs(risk_amt - 50.0) < 1e-9
    assert abs(qty - 10.0) < 1e-9  # 50$ / 5$ = 10
