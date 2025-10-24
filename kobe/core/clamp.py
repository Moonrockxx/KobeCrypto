# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from datetime import datetime, timezone
from kobe.core.journal import JSONL_PATH

def _parse_ts(ts):
    if ts is None:
        return None
    try:
        # int/float epoch (ms ou s)
        if isinstance(ts, (int, float)):
            if ts > 1e12:  # ms
                return datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        # ISO 8601 (avec 'Z' supportée)
        if isinstance(ts, str):
            s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        return None
    return None

def emitted_signal_today() -> bool:
    """Retourne True si un event type='signal' est présent pour la date UTC du jour."""
    if not JSONL_PATH.exists():
        return False
    today = datetime.now(timezone.utc).date()
    try:
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "signal":
                continue
            dt = _parse_ts(rec.get("ts"))
            if dt and dt.date() == today:
                return True
    except Exception:
        # En cas d'erreur de lecture/parsing, on n'empêche pas la stratégie (fail open)
        return False
    return False
