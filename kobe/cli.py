#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import subprocess
import json

from kobe import __version__


# -----------------------------
# scan
# -----------------------------
def cmd_scan(args: argparse.Namespace) -> int:
    # --- DEMO ---
    if args.demo:
        if not args.json_only:
            print("[cli] mode démo: appel de `python -m kobe.strategy.v0_breakout`")
            print("[cli] attendu: premier run -> Signal; second run -> None (clamp 1/jour).")
        return subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])

    # --- LIVE ---
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
            if not args.json_only:
                print("[cli] decision: DEMO stratégie v0 (≤1 signal/jour, 3 raisons, stop)")
            rc = subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])
            append_event({
                "type": "decision",
                "source": "decide-demo",
                "symbol": args.symbol,
                "result": "signal" if rc == 0 else "none",
            })
            printed["decided"] = True

        def decide_real_once():
            if not args.decide_real or printed["decided"] or printed["n"] < args.bars:
                return
            if not args.json_only:
                print("[cli] decision: REAL stratégie v0 (breakout de contraction)")
            from kobe.strategy.v0_contraction_breakout import maybe_signal_from_bars
            sig = maybe_signal_from_bars(bars)
            if sig is None:
                print("None")
                append_event({
                    "type": "decision",
                    "source": "decide-real",
                    "symbol": args.symbol,
                    "result": "none",
                })
            else:
                print(json.dumps(sig, ensure_ascii=False))
                evt = dict(sig)
                evt.update({"type": "signal", "source": "decide-real", "result": "signal"})
                append_event(evt)
            printed["decided"] = True

        def on_tick(t):
            bar = agg.on_tick(t)
            if bar:
                payload = {
                    "type": "bar1m", "symbol": bar.symbol, "ts_open": bar.ts_open,
                    "o": bar.o, "h": bar.h, "l": bar.l, "c": bar.c, "v": bar.v
                }
                print(json.dumps(payload, ensure_ascii=False))
                bars.append(bar)
                printed["n"] += 1
                decide_demo_once()
                decide_real_once()

        def stop_after(_t):
            # on quitte après décision et au moins N barres
            return printed["n"] >= args.bars and printed["decided"]

        if not args.json_only:
            print(f"[cli] live: {args.symbol} → agrégation 1m ; target bars={args.bars} ; "
                  f"decide={args.decide} ; decide_real={args.decide_real}")
        subscribe_agg_trade(args.symbol, limit=None, on_tick=on_tick, stop_after=stop_after)
        return 0

    print("Je ne sais pas (scan live non demandé).\nUtilise `--live` ou `--demo`.")
    return 0


# -----------------------------
# paper-fill
# -----------------------------
def cmd_paper_fill(args: argparse.Namespace) -> int:
    from kobe.core.journal import append_event
    from kobe.core.sizing import size_for_risk
    from kobe.core.config import load_config

    data = sys.stdin.read().strip()
    if not data:
        print("Je ne sais pas.\nFournis un signal JSON via stdin (ex: `kobe scan --demo --json-only | kobe paper-fill --equity 10000`).")
        return 1
    if data == "None":
        print("None")
        return 0
    try:
        sig = json.loads(data)
    except Exception:
        print("Je ne sais pas.\nEntrée non-JSON.")
        return 1

    cfg = load_config(args.config) if args.config else {}
    symbol = sig.get("symbol")
    side = sig.get("side")
    entry = float(sig.get("entry"))
    stop = float(sig.get("stop"))
    risk_pct = float(sig.get("risk_pct", cfg.get("risk_pct", 0.5)))

    equity = args.equity if args.equity is not None else cfg.get("equity")
    if equity is None:
        print("Je ne sais pas.\nFournis --equity ou un config.yaml avec `equity:`.")
        return 1
    equity = float(equity)

    sl_bps = args.slippage_bps if args.slippage_bps is not None else cfg.get("slippage_bps", 2)
    sl_bps = int(sl_bps)

    if side not in ("long", "short"):
        print("Je ne sais pas.\nside attendu: long|short.")
        return 1

    qty, _risk_amount = size_for_risk(equity, risk_pct, entry, stop, lot_step=0.001)
    slip = sl_bps / 10000.0
    fill_entry = entry * (1.0 + slip) if side == "long" else entry * (1.0 - slip)
    max_loss_est = qty * abs(entry - stop)

    out = {
        "type": "paper", "source": "paper-fill",
        "symbol": symbol, "side": side,
        "entry": round(entry, 8), "stop": round(stop, 8), "risk_pct": risk_pct,
        "equity": equity, "qty": round(qty, 8), "fill_entry": round(fill_entry, 8),
        "slippage_bps": sl_bps, "max_loss_est": round(max_loss_est, 8),
    }
    print(json.dumps(out, ensure_ascii=False))
    append_event(out)
    return 0


# -----------------------------
# show-log (avec délégation --pnl-today)
# -----------------------------
def _delegate_show_log_to_cli_show_log(args: argparse.Namespace) -> int:
    """
    Délègue à `python -m kobe.cli_show_log` quand --pnl-today est demandé.
    Propage les flags connus (--tail). Imprime stdout tel quel. Remonte le code de retour.
    """
    cmd = [sys.executable, "-m", "kobe.cli_show_log"]
    if getattr(args, "tail", None) is not None:
        cmd += ["--tail", str(args.tail)]
    if getattr(args, "pnl_today", False):
        cmd += ["--pnl-today"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode != 0 and proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    return proc.returncode


def _cmd_show_log_local(args: argparse.Namespace) -> int:
    """Affiche simplement le JSONL local (fallback sans --pnl-today)."""
    from kobe.core.journal import JSONL_PATH
    pth = JSONL_PATH
    if not pth.exists():
        print("Je ne sais pas.\nAucun journal encore.")
        return 0
    for ln in pth.read_text(encoding="utf-8").splitlines()[-args.tail:]:
        print(ln)
    return 0


# -----------------------------
# parser
# -----------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kobe", description="KobeCrypto CLI v0")

    # Flag global --version (avant sous-commande)
    p.add_argument("--version", action="store_true", help="Affiche la version et quitte.")

    sub = p.add_subparsers(dest="cmd", required=False)  # pas 'required=True' pour permettre --version seul

    # scan
    p_scan = sub.add_parser("scan", help="Scan du marché et éventuelle émission d’un signal (≤ 1/jour).")
    p_scan.add_argument("--demo", action="store_true", help="Exécute la démo intégrée de la stratégie v0.")
    p_scan.add_argument("--live", action="store_true", help="Consomme le WS aggTrade et agrège en barres 1m.")
    p_scan.add_argument("--decide", action="store_true", help="Après N barres, appelle la démo stratégie v0.")
    p_scan.add_argument("--decide-real", action="store_true", help="Après N barres, applique la logique v0 réelle.")
    p_scan.add_argument("--symbol", default="BTCUSDT", help="Symbole spot (ex: BTCUSDT/ETHUSDT/SOLUSDT).")
    p_scan.add_argument("--bars", type=int, default=30, help="Nombre de barres 1m à accumuler avant décision.")
    p_scan.add_argument("--json-only", action="store_true", help="Sorties strictement JSON/None (silence sur le reste).")
    p_scan.set_defaults(func=cmd_scan)

    # paper-fill
    p_pf = sub.add_parser("paper-fill", help="Simule l’exécution (entrée/stop/TP) à partir d’un signal JSON via stdin.")
    p_pf.add_argument("--equity", type=float, required=False, help="Capital total (ex: 10000). Si absent, lit la config.")
    p_pf.add_argument("--slippage-bps", type=int, default=None, help="Glissement en bps (100 bps = 1%). Si absent, lit la config.")
    p_pf.add_argument("--config", default="config.yaml", help="Chemin du fichier de config YAML.")
    p_pf.set_defaults(func=cmd_paper_fill)

    # show-log
    p_log = sub.add_parser("show-log", help="Affiche les derniers enregistrements du journal.")
    p_log.add_argument("--tail", type=int, default=10, help="Nombre de lignes à afficher depuis la fin du journal.")
    p_log.add_argument("--pnl-today", dest="pnl_today", action="store_true",
                       help="Afficher le PnL du jour via le module dédié `kobe.cli_show_log`.")
    # la fonction sera déterminée dans main() car on doit router en fonction de --pnl-today
    p_log.set_defaults(func=None)

    return p


# -----------------------------
# main
# -----------------------------
def main(argv=None) -> int:
    parser = build_parser()

    # parse une première fois les flags globaux
    known, _ = parser.parse_known_args(argv)
    if getattr(known, "version", False):
        print(__version__)
        return 0

    # parse complet
    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        print(__version__)
        return 0

    # routing de show-log (pnl_today -> délégation, sinon local)
    if getattr(args, "cmd", None) == "show-log":
        if getattr(args, "pnl_today", False):
            return _delegate_show_log_to_cli_show_log(args)
        return _cmd_show_log_local(args)

    if hasattr(args, "func") and args.func is not None:
        ret = args.func(args)
        return ret if isinstance(ret, int) else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
