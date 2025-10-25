from __future__ import annotations
import sys
import asyncio
from datetime import datetime, timezone
from typing import Sequence, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .news import fetch_news
from .notify import Notifier  # facultatif dans ce module

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _format_news(items) -> str:
    if not items:
        return f"📰 Kobe V1 — Veille actus ({_utc_now().strftime('%Y-%m-%d %H:%M UTC')})\n• Aucune actu pertinente."
    lines = [f"📰 Kobe V1 — Veille actus ({_utc_now().strftime('%Y-%m-%d %H:%M UTC')})"]
    for it in items:
        lines.append(f"• {it.title}\n{it.link}")
    return "\n\n".join(lines)

def _is_hour_enabled(enabled_hours_utc: Sequence[int]) -> bool:
    return _utc_now().hour in set(int(h) for h in enabled_hours_utc)

def run_news_job(
    feeds: Sequence[str],
    keywords: Sequence[str],
    max_items: int,
    enabled_hours_utc: Sequence[int],
    notifier: Optional[Notifier] = None,
    use_telegram_for_news: bool = False,
) -> None:
    """
    Récupère les news. N'envoie sur Telegram que si use_telegram_for_news=True.
    Sinon, affiche en console. Filtre par fenêtre horaire UTC.
    """
    if not _is_hour_enabled(enabled_hours_utc):
        return

    items = fetch_news(list(feeds), list(keywords), int(max_items))
    text = _format_news(items)

    if use_telegram_for_news and notifier is not None:
        # Notifier v21 est async → helper synchrone dispo
        try:
            notifier.send_sync(text, disable_web_page_preview=True)
        except Exception as e:
            print(f"[scheduler] Échec envoi Telegram (news), fallback console: {e}", file=sys.stderr)
            print(text)
    else:
        # Par défaut (V1): silence Telegram pour les news → console seulement
        print(text)

def build_scheduler(
    interval_minutes: int,
    feeds: Sequence[str],
    keywords: Sequence[str],
    max_items: int,
    enabled_hours_utc: Sequence[int],
    notifier: Optional[Notifier] = None,
    use_telegram_for_news: bool = False,
) -> BlockingScheduler:
    """
    Crée un scheduler qui déclenche toutes les `interval_minutes` et
    contrôle la fenêtre horaire en UTC à l'intérieur du job.
    """
    sched = BlockingScheduler()
    trigger = IntervalTrigger(minutes=int(interval_minutes))
    sched.add_job(
        run_news_job,
        trigger=trigger,
        args=[feeds, keywords, max_items, enabled_hours_utc, notifier, use_telegram_for_news],
        id="news-interval",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return sched
