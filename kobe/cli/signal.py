from __future__ import annotations
import argparse, sys
from kobe.signals.proposal import Proposal, format_proposal_for_telegram
from kobe.core.journal import log_proposal

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kobe signal",
        description="Génère une proposal (trade), la journalise et affiche le message actionnable."
    )
    p.add_argument("--symbol", required=True, help="Ex: BTCUSDT")
    p.add_argument("--side", required=True, choices=["long","short"])
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--take", type=float, required=True)
    p.add_argument("--risk-pct", type=float, default=0.25, help="Risque % capital (≤ 0.25 pour proposal)")
    p.add_argument("--size-pct", type=float, default=5.0, help="Taille cible en % du capital (indicatif)")
    p.add_argument("--ttl", type=int, default=45, help="Validité en minutes (par défaut 45)")
    p.add_argument("--reason", action="append", default=[], help="Raison (peut être répété ≥3x)")
    p.add_argument("--balance-usd", type=float, default=None, help="Capital pour sizing approx (optionnel)")
    p.add_argument("--leverage", type=float, default=1.0, help="Levier pour sizing approx (optionnel)")
    return p

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    if len([r for r in args.reason if r.strip()]) < 3:
        ap.error("Fournir au moins 3 --reason.")

    p = Proposal(
        symbol=args.symbol,
        side=args.side,
        entry=args.entry,
        stop=args.stop,
        take=args.take,
        risk_pct=args.risk_pct,
        size_pct=args.size_pct,
        reasons=args.reason,
        ttl_minutes=args.ttl,
    )

    # Journalisation (CSV + JSONL)
    log_proposal(p.model_dump())

    # Affichage du message actionnable (pas d’envoi Telegram ici)
    msg = format_proposal_for_telegram(p, balance_usd=args.balance_usd, leverage=args.leverage)
    print(msg)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
