from __future__ import annotations
import argparse, json, sys
from kobe.signals.proposal import Proposal

def _demo_payload() -> dict:
    # Démo déterministe avec ≥3 raisons non vides (attendu par le test CI)
    p = Proposal(
        symbol="BTCUSDT", side="long",
        entry=68000.0, stop=67200.0, take=69600.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=["Breakout M15", "Funding neutre", "Corrélation SPX en hausse"],
        ttl_minutes=45,
    )
    return {
        "symbol": p.symbol,
        "side": p.side,
        "entry": p.entry,
        "stop": p.stop,
        "take": p.take,
        "reasons": p.reasons,  # ≥3 non vides
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kobe.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan/démo CLI")
    p_scan.add_argument("--demo", action="store_true", help="Retourne une payload de démonstration")
    p_scan.add_argument("--json-only", action="store_true", help="Affiche uniquement le JSON")

    args = parser.parse_args(argv)

    if args.cmd == "scan" and args.demo:
        payload = _demo_payload()
        if args.json_only:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print("DEMO:", json.dumps(payload, ensure_ascii=False))
        return 0

    print("Commande non supportée. Utilise: scan --demo [--json-only]", file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
