from typing import Iterable, List, Optional

def _to_list(x: Iterable[float]) -> List[float]:
    return list(x)

def true_range(prev_close: Optional[float], high: float, low: float) -> float:
    """
    True Range (TR) = max(high-low, |high-prev_close|, |low-prev_close|)
    Si prev_close est None (première bougie), TR = high - low
    """
    if prev_close is None:
        return float(high) - float(low)
    high = float(high); low = float(low); pc = float(prev_close)
    return max(high - low, abs(high - pc), abs(low - pc))

def atr(highs: Iterable[float], lows: Iterable[float], closes: Iterable[float], period: int = 14) -> float:
    """
    ATR simple (SMA des TR) sur 'period' dernières bougies.
    Pour V0 on fait simple: SMA(TR). Suffisant pour contraction.
    """
    H = _to_list(highs); L = _to_list(lows); C = _to_list(closes)
    n = len(H)
    if not (len(L) == n == len(C)) or n < 1:
        raise ValueError("Entrées incohérentes ou vides")
    if period < 1:
        raise ValueError("period doit être >= 1")
    start = max(0, n - period)
    tr_vals: List[float] = []
    prev_close: Optional[float] = None if start == 0 else C[start-1]
    for i in range(start, n):
        tr_vals.append(true_range(prev_close, H[i], L[i]))
        prev_close = C[i]
    return sum(tr_vals) / len(tr_vals)

def sma(values: Iterable[float], period: int) -> float:
    vals = _to_list(values)
    if len(vals) < period or period < 1:
        raise ValueError("Pas assez de valeurs pour SMA")
    window = vals[-period:]
    return sum(window) / period

def ema(values: Iterable[float], period: int) -> float:
    """
    EMA classique (alpha = 2/(period+1)) sur toutes les valeurs fournies,
    et on retourne la dernière EMA.
    """
    vals = _to_list(values)
    if period < 1 or len(vals) < 1:
        raise ValueError("Entrée EMA invalide")
    alpha = 2.0 / (period + 1.0)
    ema_val = float(vals[0])
    for v in vals[1:]:
        ema_val = alpha * float(v) + (1 - alpha) * ema_val
    return ema_val

def range_pct(high: float, low: float, close: float) -> float:
    """(High - Low) / Close * 100 (en %)"""
    high = float(high); low = float(low); close = float(close)
    if close == 0:
        raise ValueError("close ne peut pas être 0")
    return (high - low) / close * 100.0

def slope(values: Iterable[float], lookback: int = 3) -> float:
    """
    Pente simple: (dernier - valeur d'il y a 'lookback') / lookback
    Mesure le delta par bougie (unités de la série).
    """
    vals = _to_list(values)
    if lookback < 1 or len(vals) <= lookback:
        raise ValueError("Pas assez de valeurs pour slope")
    return (vals[-1] - vals[-1 - lookback]) / float(lookback)

def ema_slope(values: Iterable[float], period: int = 9, lookback: int = 3) -> float:
    """
    Pente de l'EMA: on calcule l'EMA sur l'historique, puis la même EMA
    tronquée de 'lookback' bougies, et on calcule la pente par bougie.
    """
    vals = _to_list(values)
    if len(vals) <= lookback:
        raise ValueError("Pas assez de valeurs pour ema_slope")
    # EMA courant
    ema_now = ema(vals, period)
    # EMA d'il y a 'lookback' bougies: on EMA jusqu'à len(vals)-lookback
    ema_past = ema(vals[:-lookback], period)
    return (ema_now - ema_past) / float(lookback)

def vol_avg(volumes: Iterable[float], period: int = 20) -> float:
    """Moyenne simple du volume (SMA)."""
    return sma(volumes, period)
