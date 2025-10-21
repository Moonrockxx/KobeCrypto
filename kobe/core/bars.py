import asyncio, json
from datetime import datetime
import websockets

WSS_BASE = "wss://stream.binance.com:9443/ws"

def _fmt_ts(ms:int)->str:
    try:
        return datetime.fromtimestamp(ms/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms)

async def print_closed_klines(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 3):
    stream = f"{symbol.lower()}@kline_{interval}"
    url = f"{WSS_BASE}/{stream}"
    print(f"[bars] connecting to {url} ...")
    count = 0
    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            while count < limit:
                msg = await ws.recv()
                data = json.loads(msg)
                k = data.get("k")
                # kline payload: see Binance docs; 'x' = candle closed
                if not isinstance(k, dict) or not k.get("x", False):
                    continue
                o = float(k.get("o", "0"))
                h = float(k.get("h", "0"))
                l = float(k.get("l", "0"))
                c = float(k.get("c", "0"))
                v = float(k.get("v", "0"))
                t_end = int(k.get("T", k.get("t", 0)))
                print(f"{_fmt_ts(t_end)} {symbol} {interval} o={o} h={h} l={l} c={c} v={v}")
                count += 1
    except KeyboardInterrupt:
        print("[bars] interrupted by user")
    finally:
        print(f"[bars] done ({count} closed candles)")

if __name__ == "__main__":
    asyncio.run(print_closed_klines("BTCUSDT", "1m", limit=3))
