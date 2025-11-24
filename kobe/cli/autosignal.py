from __future__ import annotations

import argparse

from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import format_proposal_for_telegram
from kobe.core.journal import log_proposal
from kobe.core.factors import get_market_snapshot


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kobe autosignal",
        description=(
            "Génère une proposal à partir du snapshot marché (Factor Engine V4.2), "
            "journalise et affiche un message actionnable."
        ),
    )
    p.add_argument(
        "--symbol",
        default="BTCUSDC",
        help="Symbole spot Binance (USDC only en V4.2, ex: BTCUSDC, ETHUSDC, SOLUSDC).",
    )
    p.add_argument(
        "--balance-usd",
        type=float,
        default=None,
        help="Capital en USD (pour sizing approx dans l'affichage Telegram).",
    )
    p.add_argument(
        "--leverage",
        type=float,
        default=1.0,
        help="Levier (pour sizing approx dans l'affichage Telegram).",
    )
    p.add_argument(
        "--debug-snapshot",
        action="store_true",
        help="Affiche le snapshot marché brut utilisé pour la génération.",
    )
    return p


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    symbol = args.symbol.upper()

    # 1) Snapshot marché enrichi via Factor Engine V4.2
    snapshot = get_market_snapshot(symbol)
    if args.debug_snapshot:
        print("📊 Snapshot marché utilisé pour la génération:")
        # On évite le pretty-print JSON complet pour ne pas polluer la sortie,
        # mais c'est suffisant pour du debug rapide.
        print(snapshot)

    # 2) Génération de la Proposal à partir du snapshot
    p = generate_proposal_from_factors(snapshot)
    if not p:
        print("⚙️  Aucun signal généré pour ce snapshot marché (aucun setup éligible).")
        return 0

    # 3) Journalisation
    log_proposal(p.model_dump())

    # 4) Affichage actionnable (sans envoi Telegram ici)
    msg = format_proposal_for_telegram(
        p,
        balance_usd=args.balance_usd,
        leverage=args.leverage,
    )
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
