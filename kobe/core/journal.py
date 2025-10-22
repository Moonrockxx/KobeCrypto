#!/usr/bin/env python3
from pathlib import Path
import json, csv, time

LOG_DIR = Path("logs")
JSONL_PATH = LOG_DIR / "journal.jsonl"
CSV_PATH = LOG_DIR / "journal.csv"
CSV_COLS = ["ts","type","source","symbol","side","entry","stop","risk_pct","result"]

def _ensure():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def append_event(event: dict):
    _ensure()
    evt = dict(event)
    evt.setdefault("ts", int(time.time()*1000))
    # JSONL
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    # CSV (colonnes stables, valeurs manquantes vides)
    write_header = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if write_header:
            w.writeheader()
        row = {k: evt.get(k, "") for k in CSV_COLS}
        w.writerow(row)
