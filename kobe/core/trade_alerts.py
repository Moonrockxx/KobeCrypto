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

def render_execution_message(p: Proposal, evt: dict, balance_usd: Optional[float] = None, leverage: float = 1.0) -> str:
    """
    Formatte un message Telegram pour un évènement d'exécution (réel ou simulé).
    p : proposal d'origine
    evt : évènement renvoyé par router.place_from_proposal / executor.
    """
    mode = str(evt.get("mode", "")).upper()
    status = str(evt.get("status", "UNKNOWN"))
    action = str(evt.get("action", ""))
    exchange = evt.get("exchange", "binance_spot")
    symbol = evt.get("symbol") or p.symbol
    side = (p.side or "").upper()
    qty = evt.get("qty")
    price = evt.get("price", p.entry)

    # En-tête: succès ou alerte selon le statut
    header = f"✅ EXÉCUTION {mode} — {symbol} {side}"
    if status.startswith("ERR") or status in ("KILL_SWITCH", "REJECTED"):
        header = f"⚠️ EXÉCUTION {mode} — {symbol} {side}"

    parts = [header]

    # Prix d'exécution
    if isinstance(price, (int, float)):
        parts.append(f"• Prix exec : {price:.4f}")
    else:
        parts.append(f"• Prix exec : {price}")

    # Quantité
    if qty is not None:
        try:
            parts.append(f"• Quantité : {float(qty):g}")
        except Exception:
            parts.append(f"• Quantité : {qty}")

    # Niveaux du trade
    parts.append(f"• TP : {p.take}  |  SL : {p.stop}")

    # Risque / taille (si dispo)
    try:
        parts.append(f"• Risque : {p.risk_pct:.3f}%  |  Taille : {p.size_pct:.3f}%")
    except Exception:
        pass

    # Order ID si présent
    order_id = evt.get("order_id")
    if order_id:
        parts.append(f"• Order ID : `{order_id}`")

    parts.append(f"• Exchange : {exchange}")
    if action:
        parts.append(f"• Action : {action}")
    parts.append(f"• Statut : `{status}`")

    # Raisons si présentes dans la proposal
    reasons = getattr(p, "reasons", None)
    if reasons:
        parts.append("")
        parts.append("📝 Raisons :")
        for r in reasons:
            parts.append(f"- {r}")

    return "\n".join(parts)


def send_execution_event(notifier: Optional[Notifier], p: Proposal, evt: dict, balance_usd: Optional[float] = None, leverage: float = 1.0) -> bool:
    """
    Envoie un message Telegram pour un évènement d'exécution (réel ou simulé).
    Suivi de la même logique que send_trade : si pas de Notifier, on imprime
    simplement le message sur stdout.
    """
    msg = render_execution_message(p, evt, balance_usd=balance_usd, leverage=leverage)
    if notifier is None:
        print(msg)
        return False
    try:
        notifier.send_sync(msg, disable_web_page_preview=True)
        return True
    except Exception as e:
        print(f"[trade_alerts] échec envoi Telegram (execution): {e}")
        print(msg)
        return False

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
