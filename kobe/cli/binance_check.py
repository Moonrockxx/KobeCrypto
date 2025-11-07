import sys, json
from kobe.execution.binance_spot import BinanceSpot

def main(argv=None):
    _ = argv or sys.argv[1:]
    client = BinanceSpot()
    res = client.check_account()
    if res is None:
        print("INFO BinanceSpot: mode dry (aucune clé détectée).")
        return 0
    out = {
        "canTrade": res.get("canTrade"),
        "accountType": res.get("accountType"),
        "n_balances": len(res.get("balances", [])),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
