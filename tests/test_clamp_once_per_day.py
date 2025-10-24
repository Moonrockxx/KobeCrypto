# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import json
import kobe.core.clamp as clamp

def _write_jsonl(p, rows):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

def test_emitted_signal_today_true(tmp_path, monkeypatch):
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(clamp, "JSONL_PATH", journal, raising=False)

    today_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = [
        {"type": "paper", "ts": today_ts, "note": "not a signal"},
        {"type": "signal", "ts": today_ts, "symbol": "BTCUSDT"}
    ]
    _write_jsonl(journal, rows)
    assert clamp.emitted_signal_today() is True

def test_emitted_signal_today_false(tmp_path, monkeypatch):
    journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(clamp, "JSONL_PATH", journal, raising=False)

    yday_ts = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    rows = [
        {"type": "signal", "ts": yday_ts, "symbol": "ETHUSDT"},
        {"type": "paper", "ts": yday_ts, "note": "not today"}
    ]
    _write_jsonl(journal, rows)
    assert clamp.emitted_signal_today() is False
