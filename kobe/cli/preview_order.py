import argparse, json
from kobe.execution.risk import RiskConfig, compute_spot_qty

def main():
    ap = argparse.ArgumentParser(prog="kobe preview-order", description="Prévisualisation sizing spot (dry-run).")
    ap.add_argument("--symbol", required=True, help="ex: BTCUSDC")
    ap.add_argument("--side", choices=["BUY","SELL"], default="BUY")
    ap.add_argument("--entry", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--balance", type=float, required=True, help="Solde disponible en USDC")
    ap.add_argument("--risk-pct", type=float, default=0.0025, help="Risque cible (0.0025 = 0.25%) — cap 0.5%")
    ap.add_argument("--rr", type=float, default=2.0, help="Risk:Reward pour TP (défaut 2.0)")
    args = ap.parse_args()

    cfg = RiskConfig(risk_pct=args.risk_pct)
    data = compute_spot_qty(args.side, args.balance, args.entry, args.stop, cfg)
    r = data["risk_pct_applied"]; dist = data["dist_price"]; qty = data["qty"]

    if args.side == "BUY":
        tp = args.entry + args.rr * dist
        max_loss = (args.entry - args.stop) * qty
    else:
        tp = args.entry - args.rr * dist
        max_loss = (args.stop - args.entry) * qty

    out = {
        "symbol": args.symbol, "side": args.side,
        "entry": args.entry, "sl_price": args.stop, "tp_price": tp, "rr": args.rr,
        "risk_pct_applied": r, "risk_amount_usdc": round(data["risk_amount_usdc"], 2),
        "qty": qty, "max_loss_usdc": round(max_loss, 2),
        "notes": "dry-run preview — aucun ordre envoyé",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
