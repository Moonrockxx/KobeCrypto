import argparse, json
from kobe.execution.proposal import build_spot_proposal

def main():
    ap = argparse.ArgumentParser(
        prog="kobe proposal-preview",
        description="Build d'une proposition spot (dry)."
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--side", choices=["BUY","SELL"], default="BUY")
    ap.add_argument("--entry", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--balance", type=float, required=True)
    ap.add_argument("--risk-pct", type=float, default=0.0025)
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--reasons", type=str, default="", help="Separees par ';'")
    args = ap.parse_args()

    reasons = [r.strip() for r in args.reasons.split(";") if r.strip()]
    out = build_spot_proposal(
        symbol=args.symbol, side=args.side, entry=args.entry, stop=args.stop,
        balance_usdc=args.balance, reasons=reasons, risk_pct=args.risk_pct, rr=args.rr
    )
    print(json.dumps(out, ensure_ascii=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
