from __future__ import annotations
import argparse, sys, os
from typing import List
from kobe.signals.proposal import Proposal
from kobe.core.router import place_from_proposal
from kobe.core.risk import RiskConfig
from kobe.core.trade_alerts import send_execution_event
from kobe.core.notify import Notifier, TelegramConfig

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="kobe trade",
        description="Exécute une Proposal selon le mode actif (paper/testnet)."
    )
    ap.add_argument("--symbol", required=True, help="Symbole (ex: BTCUSDT)")
    ap.add_argument("--side", required=True, choices=["long", "short"], help="Direction du trade")
    ap.add_argument("--entry", required=True, type=float, help="Prix d'entrée")
    ap.add_argument("--stop", required=True, type=float, help="Stop-loss")
    ap.add_argument("--take", required=True, type=float, help="Take-profit")
    ap.add_argument("--risk-pct", type=float, default=0.25, help="Risque % du capital")
    ap.add_argument("--size-pct", type=float, default=5.0, help="Taille % du capital")
    ap.add_argument("--reason", action="append", default=[], help="Raisons (au moins 3)")
    ap.add_argument("--balance-usd", type=float, default=10000.0, help="Capital simulé (USD)")
    ap.add_argument("--leverage", type=float, default=2.0, help="Effet de levier")
    return ap

def main(argv: List[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    if len(args.reason) < 3:
        print("❌  Trois raisons minimum sont requises (--reason ...)")
        return 1

    try:
        p = Proposal(
            symbol=args.symbol,
            side=args.side,
            entry=args.entry,
            stop=args.stop,
            take=args.take,
            risk_pct=args.risk_pct,
            size_pct=args.size_pct,
            reasons=args.reason,
        )
        print(f"🚀  Exécution de {p.symbol} ({p.side.upper()}) — risk {p.risk_pct}% / size {p.size_pct}%")
        mode, evt = place_from_proposal(
            p,
            balance_usd=args.balance_usd,
            leverage=args.leverage,
            risk_cfg=RiskConfig(max_trade_pct=0.5, max_proposal_pct=0.25),
        )
        print(f"✅  Mode: {mode.value.upper()} — statut: {evt['status']} — ordre enregistré.")

        # Notification Telegram en LIVE si possible (utilise send_execution_event).
        try:
            mode_str = str(getattr(mode, "value", mode)).upper()
        except Exception:
            mode_str = "UNKNOWN"

        if mode_str == "LIVE":
            tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            tg_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
            notifier = None
            if tg_token and tg_chat:
                try:
                    cfg = TelegramConfig(bot_token=tg_token, chat_id=tg_chat)
                    notifier = Notifier(cfg)
                except Exception as e_init:
                    print(f"[trade] échec init Notifier Telegram: {e_init}")
            try:
                # send_execution_event gère le cas notifier=None (print stdout)
                send_execution_event(
                    notifier,
                    p,
                    evt,
                    balance_usd=args.balance_usd,
                    leverage=args.leverage,
                )
            except Exception as e_exec:
                print(f"[trade] erreur send_execution_event: {e_exec}")

        return 0
    except Exception as e:
        print(f"❌  Erreur: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
