from kobe.execution.binance_spot import BinanceSpot

def test_build_order_plan_full_tp_sl():
    b = BinanceSpot(key="dummy", secret="dummy")

    plan = b.build_order_plan(
        symbol="BTCUSDC",
        side="BUY",
        quantity=0.01234,
        entry_price=68000.0,
        take_price=69600.0,
        stop_price=67200.0,
    )

    assert plan["symbol"] == "BTCUSDC"
    assert plan["side"] == "BUY"
    assert plan["qty_original"] == 0.01234
    assert plan["qty_rounded"] == 0.012
    assert plan["order_type"] == "MARKET"
    assert plan["entry"] == {"type": "MARKET", "price": 68000.0}
    assert plan["take_profit"] == {"type": "LIMIT", "price": 69600.0}
    assert plan["stop_loss"] == {"type": "STOP_LIMIT", "price": 67200.0}
    assert plan["valid"] is True

def test_build_order_plan_too_small():
    b = BinanceSpot(key="dummy", secret="dummy")

    plan = b.build_order_plan(
        symbol="BTCUSDC",
        side="BUY",
        quantity=0.00000001,
        entry_price=68000.0,
        take_price=69600.0,
        stop_price=67200.0,
    )

    assert plan["symbol"] == "BTCUSDC"
    assert plan["side"] == "BUY"
    assert plan["valid"] is False
    assert plan["reason"] == "too_small"
