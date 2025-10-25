from __future__ import annotations
import argparse, sys, json
from kobe.signals.generator import generate_proposal_from_factors
from kobe.signals.proposal import format_proposal_for_telegram
from kobe.core.journal import log_proposal

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kobe autosignal",
        description="Génère une proposal à partir de facteurs fournis en CLI, journalise et affiche."
    )
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--price", type=float, required=True)

    # Facteurs (scores -1..1 ou 0..1 selon sémantique)
    p.add_argument("--trend-strength", type=float, default=0.0, help="Force de tendance (négatif=baissier, positif=haussier)")
    p.add_argument("--funding-bias", type=float, default=0.0, help="Biais de funding (-1 shorts dominent, +1 longs dominent)")
    p.add_argument("--volatility", type=float, default=0.0, help="Volatilité 0..1")
    p.add_argument("--btc-dominance", type=float, default=0.5, help="Dominance BTC 0..1")
    p.add_argument("--news-sentiment", type=float, default=0.0, help="Sentiment news (-1..+1)")

    # Options d'affichage
    p.add_argument("--balance-usd", type=float, default=None, help="Capital (pour sizing approx)")
    p.add_argument("--leverage", type=float, default=1.0, help="Levier (pour sizing approx)")
    return p

def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    market = {
        "symbol": args.symbol,
        "price": args.price,
        "trend_strength": args.trend_strength,
        "funding_bias": args.funding_bias,
        "volatility": args.volatility,
        "btc_dominance": args.btc_dominance,
        "news_sentiment": args.news_sentiment,
    }

    p = generate_proposal_from_factors(market)
    if not p:
        print("⚙️  Aucun signal généré (conditions insuffisantes).")
        return 0

    # Journalisation
    log_proposal(p.model_dump())

    # Affichage actionnable (sans envoi Telegram ici)
    msg = format_proposal_for_telegram(p, balance_usd=args.balance_usd, leverage=args.leverage)
    print(msg)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
