from __future__ import annotations

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List


BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com").rstrip("/")


def fetch_klines(
    symbol: str,
    interval: str = "15m",
    limit: int = 200,
    base_url: str | None = None,
    timeout: int = 8,
) -> List[Dict[str, Any]]:
    """
    Wrapper minimal autour de /api/v3/klines.

    - symbol : paire spot Binance (ex: "BTCUSDC").
    - interval : timeframe Binance (ex: "15m", "1h", "4h", "1d").
    - limit : nombre de bougies à récupérer (max 1000 côté Binance).
    - base_url : permet de surcharger l'URL de base (utile pour des tests).

    Retour :
    - liste de dicts homogènes :
      {
        "open_time": int (ms),
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": float,
      }
    - [] en cas d'erreur réseau ou de réponse inattendue.
    """
    sym = symbol.upper().strip()
    base = (base_url or BINANCE_BASE_URL).rstrip("/")

    params = urllib.parse.urlencode(
        {
            "symbol": sym,
            "interval": interval,
            "limit": int(limit),
        }
    )
    url = f"{base}/api/v3/klines?{params}"

    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            data = json.loads(raw)
    except Exception:
        # On laisse l'appelant décider quoi faire d'une liste vide.
        return []

    if not isinstance(data, list):
        return []

    klines: List[Dict[str, Any]] = []
    for row in data:
        # Format attendu Binance: [ open_time, open, high, low, close, volume, ... ]
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            open_time = int(row[0])
            o = float(row[1])
            h = float(row[2])
            l = float(row[3])
            c = float(row[4])
            v = float(row[5])
        except (TypeError, ValueError):
            continue

        klines.append(
            {
                "open_time": open_time,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
        )

    return klines


if __name__ == "__main__":
    # Petit test manuel possible en local :
    # python -m kobe.data.binance_ohlc
    sym = os.getenv("KOBE_TEST_SYMBOL", "BTCUSDC")
    candles = fetch_klines(sym, interval="15m", limit=10)
    print(f"✅ fetch_klines({sym}) -> {len(candles)} bougies")
    if candles:
        print("Exemple de bougie:", candles[0])
