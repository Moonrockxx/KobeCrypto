from __future__ import annotations
import time, hashlib
from dataclasses import dataclass
from typing import List, Optional
import feedparser

@dataclass
class NewsItem:
    title: str
    link: str
    published_ts: int  # epoch seconds
    source: str

def _now_ts() -> int:
    return int(time.time())

def fetch_news(feeds: List[str],
               keywords_any: Optional[List[str]] = None,
               max_items: int = 6) -> List[NewsItem]:
    """
    Récupère des actus depuis des flux RSS, filtre par mots-clés (optionnel),
    déduplique et renvoie jusqu'à max_items items triés du plus récent au plus ancien.
    """
    keywords = [k.lower() for k in (keywords_any or [])]
    out: List[NewsItem] = []

    for url in feeds:
        d = feedparser.parse(url)
        for e in d.entries[:20]:
            title = getattr(e, "title", "") or ""
            link = getattr(e, "link", "") or ""
            published_parsed = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            ts = int(time.mktime(published_parsed)) if published_parsed else _now_ts()

            if keywords and not any(k in title.lower() for k in keywords):
                continue

            out.append(NewsItem(
                title=title.strip(),
                link=link.strip(),
                published_ts=ts,
                source=d.feed.get("title", "rss")
            ))

    # Tri par fraîcheur puis dédup par lien (fallback titre)
    out.sort(key=lambda x: x.published_ts, reverse=True)
    seen: set[str] = set()
    deduped: List[NewsItem] = []

    for it in out:
        key_src = it.link if it.link else it.title
        key = hashlib.md5(key_src.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
        if len(deduped) >= max_items:
            break

    return deduped
