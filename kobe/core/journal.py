#!/usr/bin/env python3
from pathlib import Path
import json, csv, time

LOG_DIR = Path("logs")
JSONL_PATH = LOG_DIR / "journal.jsonl"
CSV_PATH = LOG_DIR / "journal.csv"
CSV_COLS = ["ts","type","source","symbol","side","entry","stop","risk_pct","result"]

def _ensure():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

import uuid

CSV_COLS = [
    "ts",
    "signal_id",
    "symbol",
    "side",
    "entry",
    "stop",
    "take",
    "risk_pct",
    "size_pct",
    "result",
    "reasons",
]

def log_proposal(proposal: dict, result: str = "pending"):
    """
    Enregistre une proposition de trade dans les journaux CSV et JSONL.
    - proposal: dict issu d'un Proposal.model_dump()
    - result: "pending" | "executed" | "cancelled" | "hit_tp" | "hit_sl"
    """
    _ensure()
    ts = int(time.time() * 1000)
    signal_id = proposal.get("signal_id") or f"p-{uuid.uuid4().hex[:8]}"
    evt = {
        "ts": ts,
        "signal_id": signal_id,
        "symbol": proposal.get("symbol", ""),
        "side": proposal.get("side", ""),
        "entry": proposal.get("entry", ""),
        "stop": proposal.get("stop", ""),
        "take": proposal.get("take", ""),
        "risk_pct": proposal.get("risk_pct", ""),
        "size_pct": proposal.get("size_pct", ""),
        "result": result,
        "reasons": "; ".join(proposal.get("reasons", [])),
    }

    # JSONL
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    # CSV
    write_header = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if write_header:
            w.writeheader()
        w.writerow({k: evt.get(k, "") for k in CSV_COLS})
