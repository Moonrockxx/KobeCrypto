#!/usr/bin/env python3
"""
kobe.cli — CLI v0 (squelette)
Subcommandes prévues: scan, paper-fill, show-log (placeholders).
Cette étape implémente seulement `scan` avec un mode --demo.
"""
import argparse
import sys
import subprocess

def cmd_scan(args: argparse.Namespace) -> int:
    if args.demo:
        print("[cli] mode démo: appel de `python -m kobe.strategy.v0_breakout`")
        print("[cli] attendu: premier run -> imprime un Signal (long/short) avec raisons; second run (même jour) -> None (clamp 1/jour).")
        # On appelle la démo intégrée sans dépendre de la signature interne.
        return subprocess.call([sys.executable, "-m", "kobe.strategy.v0_breakout"])
    else:
        # Pont WS→maybe_signal non branché à cette étape.
        print("Je ne sais pas (branche WS→maybe_signal non implémentée dans cette étape).")
        print("Utilise `scan --demo` pour valider le chemin CLI end-to-end.")
        return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kobe", description="KobeCrypto CLI v0")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan du marché et éventuelle émission d’un signal (≤ 1/jour).")
    p_scan.add_argument("--demo", action="store_true", help="Exécute la démo intégrée de la stratégie v0.")
    p_scan.set_defaults(func=cmd_scan)

    # Placeholders (prochaines étapes)
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
