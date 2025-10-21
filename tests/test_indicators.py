import math
from kobe.ta.indicators import true_range, atr, range_pct, ema, ema_slope, sma, slope, vol_avg

def test_atr_simple():
    # 3 bougies, ATR(3) = moyenne des TR = (1.0 + 1.5 + 2.0)/3 = 1.5
    highs  = [10.0, 11.0, 12.0]
    lows   = [ 9.0,  9.5, 10.0]
    closes = [ 9.5, 10.2, 11.0]
    val = atr(highs, lows, closes, period=3)
    assert abs(val - 1.5) < 1e-9

def test_range_pct_and_ema_slope():
    # range% simple
    rp = range_pct(110, 100, 105)  # = 9.5238095238%
    assert abs(rp - 9.5238095238) < 1e-6

    # série croissante -> ema_slope positive
    series = [1,2,3,4,5,6]
    e = ema(series, period=3)
    assert e > 0
    s = ema_slope(series, period=3, lookback=2)
    assert s > 0
