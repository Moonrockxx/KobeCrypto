#!/usr/bin/env python3
"""
kobe.core.feed — WebSocket public Binance Spot (aggTrade).
- Demo: --demo => souscrit à <symbol>@aggTrade, imprime des ticks puis ferme.
- API: subscribe_agg_trade(symbol, limit=None, on_tick=None, stop_after=None)
       - limit: nombre max de ticks (si fourni)
       - stop_after(tick)->bool: si True, ferme immédiatement (prioritaire)
"""
import argparse, json, ssl
from dataclasses import dataclass
from typing import Callable, Optional
from websocket import WebSocketApp

BASE = "wss://stream.binance.com:9443/ws"

@dataclass
class Tick:
    symbol: str
    price: float
    qty: float
    ts: int
    is_buyer_maker: bool

def parse_agg_trade(msg: dict) -> Tick:
    return Tick(
        symbol=msg["s"],
        price=float(msg["p"]),
        qty=float(msg["q"]),
        ts=int(msg["T"]),
        is_buyer_maker=bool(msg["m"]),
    )

def subscribe_agg_trade(symbol: str,
                        limit: Optional[int] = None,
                        on_tick: Optional[Callable[[Tick], None]] = None,
                        stop_after: Optional[Callable[[Tick], bool]] = None):
    stream = f"{symbol.lower()}@aggTrade"
    url = f"{BASE}/{stream}"
    counter = {"n": 0}
    on_tick = on_tick or (lambda t: None)

    def _on_open(ws):
        print(f"[feed] CONNECTED {url}")

    def _on_message(ws, message: str):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return
        tick = parse_agg_trade(msg)
        on_tick(tick)
        counter["n"] += 1
        # arrêt conditionnel prioritaire
        if stop_after and stop_after(tick):
            print("[feed] stop_after triggered, closing.")
            ws.close()
            return
        if (limit is not None) and (counter["n"] >= limit):
            print("[feed] limit reached, closing.")
            ws.close()

    def _on_error(ws, err):
        print(f"[feed] ERROR: {err}")

    def _on_close(ws, code, reason):
        print(f"[feed] CLOSED code={code} reason={reason}")

    ws = WebSocketApp(
        url,
        on_open=_on_open,
        on_message=_on_message,
        on_error=_on_error,
        on_close=_on_close,
    )
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED})

def main():
    ap = argparse.ArgumentParser(description="Binance aggTrade demo")
    ap.add_argument("--demo", action="store_true", help="Souscrit à aggTrade et imprime des ticks.")
    ap.add_argument("--symbol", default="BTCUSDT", help="Symbole spot (ex: BTCUSDT).")
    ap.add_argument("--limit", type=int, default=10, help="Nombre de ticks à imprimer avant fermeture (démo).")
    args = ap.parse_args()

    if args.demo:
        def printer(t: Tick):
            print(f"{t.symbol} {t.price} x {t.qty} @ {t.ts} maker={t.is_buyer_maker}")
        subscribe_agg_trade(args.symbol, limit=args.limit, on_tick=printer)
    else:
        print("Je ne sais pas. Utilise --demo pour tester le flux aggTrade.")

if __name__ == "__main__":
    main()
