from __future__ import annotations
from typing import Optional
from kobe.signals.proposal import Proposal, format_proposal_for_telegram
from kobe.core.notify import Notifier

def render_trade_message(p: Proposal, balance_usd: Optional[float] = None, leverage: float = 1.0) -> str:
    """
    Retourne un message Telegram actionnable pour un trade (n'envoie rien).
    Utilise le formatter centralisé des proposals.
    """
    return format_proposal_for_telegram(p, balance_usd=balance_usd, leverage=leverage)

def send_trade(notifier: Optional[Notifier], p: Proposal, balance_usd: Optional[float] = None, leverage: float = 1.0) -> bool:
    """
    Envoie le trade SI un Notifier valide est fourni, sinon ne fait rien.
    Retourne True si un envoi Telegram a été effectué, False sinon.
    """
    msg = render_trade_message(p, balance_usd=balance_usd, leverage=leverage)
    if notifier is None:
        # Mode silencieux (par défaut V1 tant que Telegram n'est pas configuré)
        print(msg)
        return False
    try:
        notifier.send_sync(msg, disable_web_page_preview=True)
        return True
    except Exception as e:
        # On ne fait pas échouer toute la pipeline pour un échec d'envoi
        print(f"[trade_alerts] échec envoi Telegram: {e}")
        print(msg)
        return False
