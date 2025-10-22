from kobe.core.bars import AggToBars1m
class T:
    def __init__(self, price, qty, ts):
        self.symbol="BTCUSDT"; self.price=price; self.qty=qty; self.ts=ts

def test_bar_emission_on_minute_change():
    agg = AggToBars1m("BTCUSDT")
    assert agg.on_tick(T(100.0, 1.0, 0)) is None
    assert agg.on_tick(T(101.0, 2.0, 59000)) is None
    bar = agg.on_tick(T(102.0, 3.0, 60000))
    assert bar is not None
    assert bar.o == 100.0 and bar.h == 101.0 and bar.l == 100.0 and bar.c == 101.0
    assert abs(bar.v - 3.0) < 1e-9
