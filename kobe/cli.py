#!/usr/bin/env python3
import argparse, sys, subprocess, json
def cmd_scan(args: argparse.Namespace) -> int:
    if args.demo:
        print("[cli] mode démo: appel de `python -m kobe.strategy.v0_breakout`")
        return subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])

    if args.live:
        from kobe.core.feed import subscribe_agg_trade
        from kobe.core.bars import AggToBars1m

        agg = AggToBars1m(args.symbol)
        bars = []
        printed = {"n": 0, "decided": False}

        def decide_real_once():
            if not args.decide_real or printed["decided"]:
                return
            from kobe.strategy.v0_contraction_breakout import maybe_signal_from_bars
            print("[cli] decision: REAL stratégie v0 (breakout de contraction)")
            sig = maybe_signal_from_bars(bars)
            print("None" if sig is None else json.dumps(sig, ensure_ascii=False))
            printed["decided"] = True

        def on_tick(t):
            bar = agg.on_tick(t)
            if bar:
                payload = {
                    "type": "bar1m",
                    "symbol": bar.symbol,
                    "ts_open": bar.ts_open,
                    "o": bar.o, "h": bar.h, "l": bar.l, "c": bar.c, "v": bar.v,
                }
                print(json.dumps(payload, ensure_ascii=False))
                bars.append(bar)
                printed["n"] += 1
                if args.decide:
                    print("[cli] decision: DEMO stratégie v0 (≤1 signal/jour, 3 raisons, stop)")
                    subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])
                decide_real_once()

        def stop_after(_t):
            return printed["n"] >= args.bars

        print(f"[cli] live: {args.symbol} → agrégation 1m ; target bars={args.bars} ; decide={args.decide} ; decide_real={args.decide_real}")
        subscribe_agg_trade(args.symbol, limit=None, on_tick=on_tick, stop_after=stop_after)
        return 0

    print("Je ne sais pas (scan live non demandé). Utilise `--live` ou `--demo`.")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kobe", description="KobeCrypto CLI v0")
    sub = p.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="Scan du marché et éventuelle émission d’un signal (≤ 1/jour).")
    p_scan.add_argument("--demo", action="store_true", help="Exécute la démo intégrée de la stratégie v0.")
    p_scan.add_argument("--live", action="store_true", help="Consomme le WS aggTrade et agrège en barres 1m.")
    p_scan.add_argument("--decide", action="store_true", help="Après 1 barre, appelle la démo stratégie v0 (signal ou None).")
    p_scan.add_argument("--decide-real", action="store_true", help="Après N barres, applique la logique v0 réelle sur les barres.")
    p_scan.add_argument("--symbol", default="BTCUSDT", help="Symbole spot (ex: BTCUSDT/ETHUSDT/SOLUSDT).")
    p_scan.add_argument("--bars", type=int, default=30, help="Nombre de barres 1m à accumuler avant décision.")
    p_scan.set_defaults(func=cmd_scan)
    # placeholders
    p_pf = sub.add_parser("paper-fill", help="Simule l’exécution (entrée/stop/TP). [à implémenter]")
    p_pf.set_defaults(func=lambda a: print("Je ne sais pas (paper-fill pas encore implémenté)."))
    p_log = sub.add_parser("show-log", help="Affiche les derniers enregistrements du journal. [à implémenter]")
    p_log.set_defaults(func=lambda a: print("Je ne sais pas (show-log pas encore implémenté)."))
    return p

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        ret = args.func(args)
        return ret if isinstance(ret, int) else 0
    parser.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
