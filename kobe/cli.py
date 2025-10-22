#!/usr/bin/env python3
import argparse, sys, subprocess, json, os
def cmd_scan(args: argparse.Namespace) -> int:
    if args.demo:
        print("[cli] mode démo: appel de `python -m kobe.strategy.v0_breakout`")
        return subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])

    if args.live:
        from kobe.core.feed import subscribe_agg_trade
        from kobe.core.bars import AggToBars1m
        from kobe.core.journal import append_event

        agg = AggToBars1m(args.symbol)
        bars = []
        printed = {"n": 0, "decided": False}

        def decide_demo_once():
            if not args.decide or printed["decided"] or printed["n"] < args.bars:
                return
            print("[cli] decision: DEMO stratégie v0 (≤1 signal/jour, 3 raisons, stop)")
            rc = subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])
            append_event({
                "type":"decision","source":"decide-demo","symbol":args.symbol,
                "result":"signal" if rc==0 else "none"
            })
            printed["decided"] = True

        def decide_real_once():
            if not args.decide_real or printed["decided"] or printed["n"] < args.bars:
                return
            from kobe.strategy.v0_contraction_breakout import maybe_signal_from_bars
            print("[cli] decision: REAL stratégie v0 (breakout de contraction)")
            sig = maybe_signal_from_bars(bars)
            if sig is None:
                print("None")
                append_event({"type":"decision","source":"decide-real","symbol":args.symbol,"result":"none"})
            else:
                print(json.dumps(sig, ensure_ascii=False))
                evt = dict(sig); evt.update({"type":"signal","source":"decide-real","result":"signal"})
                append_event(evt)
            printed["decided"] = True

        def on_tick(t):
            bar = agg.on_tick(t)
            if bar:
                payload = {
                    "type": "bar1m", "symbol": bar.symbol, "ts_open": bar.ts_open,
                    "o": bar.o, "h": bar.h, "l": bar.l, "c": bar.c, "v": bar.v,
                }
                print(json.dumps(payload, ensure_ascii=False))
                bars.append(bar)
                printed["n"] += 1
                decide_demo_once()
                decide_real_once()

        def stop_after(_t):
            # On laisse tourner jusqu'à atteindre args.bars barres ET effectuer la décision
            return printed["n"] >= args.bars and printed["decided"]

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
    p_scan.add_argument("--decide", action="store_true", help="Après N barres, appelle la démo stratégie v0.")
    p_scan.add_argument("--decide-real", action="store_true", help="Après N barres, applique la logique v0 réelle.")
    p_scan.add_argument("--symbol", default="BTCUSDT", help="Symbole spot (ex: BTCUSDT/ETHUSDT/SOLUSDT).")
    p_scan.add_argument("--bars", type=int, default=30, help="Nombre de barres 1m à accumuler avant décision.")
    p_scan.set_defaults(func=cmd_scan)

    p_pf = sub.add_parser("paper-fill", help="Simule l’exécution (entrée/stop/TP). [à implémenter]")
    p_pf.set_defaults(func=lambda a: print("Je ne sais pas (paper-fill pas encore implémenté)."))

    p_log = sub.add_parser("show-log", help="Affiche les derniers enregistrements du journal.")
    p_log.add_argument("--tail", type=int, default=10, help="Nombre de lignes à afficher depuis la fin du journal.")
    def _show(a):
        from pathlib import Path
        from kobe.core.journal import JSONL_PATH
        p = JSONL_PATH
        if not p.exists():
            print("Je ne sais pas. Aucun journal encore.")
            return
        lines = p.read_text(encoding="utf-8").splitlines()
        for ln in lines[-a.tail:]:
            print(ln)
    p_log.set_defaults(func=_show)

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
