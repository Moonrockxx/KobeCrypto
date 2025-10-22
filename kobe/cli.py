#!/usr/bin/env python3
"""
kobe.cli — CLI v0
Subcommandes: scan, paper-fill, show-log.
Cette version ajoute `scan --live`:
- souscrit au flux aggTrade Binance
- agrège en barres 1m
- imprime 1 barre 1m en JSON puis s'arrête (test minimal)
"""
import argparse
import sys
import subprocess
import json

def cmd_scan(args: argparse.Namespace) -> int:
    if args.demo:
        print("[cli] mode démo: appel de `python -m kobe.strategy.v0_breakout`")
        print("[cli] attendu: premier run -> Signal; second run -> None (clamp 1/jour).")
        return subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])

    if args.live:
        from kobe.core.feed import subscribe_agg_trade
        from kobe.core.bars import AggToBars1m

        agg = AggToBars1m(args.symbol)
        printed = {"n": 0}

        def on_tick(t):
            bar = agg.on_tick(t)
            if bar:
                payload = {
                    "type": "bar1m",
                    "symbol": bar.symbol,
                    "ts_open": bar.ts_open,
                    "o": bar.o, "h": bar.h, "l": bar.l, "c": bar.c, "v": bar.v,
                }
                print(json.dumps(payload))
                printed["n"] += 1

        def stop_after(_t):
            return printed["n"] >= args.bars

        print(f"[cli] live: {args.symbol} → agrégation 1m ; target bars={args.bars}")
        subscribe_agg_trade(args.symbol, limit=None, on_tick=on_tick, stop_after=stop_after)
        return 0

    # Pont WS→maybe_signal (décision) sera branché juste après ce test minimal.
    print("Je ne sais pas (scan live non demandé). Utilise `--live` ou `--demo`.")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kobe", description="KobeCrypto CLI v0")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan du marché et éventuelle émission d’un signal (≤ 1/jour).")
    p_scan.add_argument("--demo", action="store_true", help="Exécute la démo intégrée de la stratégie v0.")
    p_scan.add_argument("--live", action="store_true", help="Consomme le WS aggTrade et agrège en barres 1m.")
    p_scan.add_argument("--symbol", default="BTCUSDT", help="Symbole spot (ex: BTCUSDT/ETHUSDT/SOLUSDT).")
    p_scan.add_argument("--bars", type=int, default=1, help="Nombre de barres 1m à imprimer avant d'arrêter.")
    p_scan.set_defaults(func=cmd_scan)

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
