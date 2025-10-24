import json
import pathlib
import csv
from datetime import datetime, timezone
from typing import Iterable, Tuple

JSONL_PATH = pathlib.Path("logs/journal.jsonl")
CSV_PATH = JSONL_PATH.with_suffix('.csv')
CSV_HEADERS = [
    "ts", "type", "source", "symbol", "side",
    "entry", "stop", "tp", "qty", "risk_pct", "risk_amount",
    "reason1", "reason2", "reason3"
]

def _event_to_csv_row(event: dict) -> list:
    # Champs de base
    ts = event.get("ts")
    t = event.get("type")
    src = event.get("source")
    sym = event.get("symbol")
    side = event.get("side")
    entry = event.get("entry")
    stop = event.get("stop")
    tp = event.get("tp")
    qty = event.get("qty")
    risk_pct = event.get("risk_pct")
    # Montant de risque en devise si disponible (qty * |entry-stop|) ou champ direct
    if event.get("risk_amount") is not None:
        risk_amount = event.get("risk_amount")
    else:
        try:
            if qty is not None and entry is not None and stop is not None:
                risk_amount = float(qty) * abs(float(entry) - float(stop))
            else:
                risk_amount = None
        except Exception:
            risk_amount = None
    # Raisons (3 raisons max)
    rs = event.get("reasons") or []
    r1 = rs[0] if len(rs) > 0 else None
    r2 = rs[1] if len(rs) > 1 else None
    r3 = rs[2] if len(rs) > 2 else None
    return [ts, t, src, sym, side, entry, stop, tp, qty, risk_pct, risk_amount, r1, r2, r3]

def append_event(event: dict) -> None:
    # JSONL (comportement existant)
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # CSV (nouveau, DoD v0)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not CSV_PATH.exists()
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if need_header:
            w.writerow(CSV_HEADERS)
        w.writerow(_event_to_csv_row(event))

def _parse_ts(ts):
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            # epoch ms vs s
            if ts > 1e12:
                return datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(ts, str):
            s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        return None
    return None

def _iter_events_today(path: pathlib.Path) -> Iterable[dict]:
    if not path.exists():
        return []
    today = datetime.now(timezone.utc).date()
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        dt = _parse_ts(rec.get("ts"))
        if dt and dt.date() == today:
            out.append(rec)
    return out

def pnl_today(base_dir: str | pathlib.Path | None = None) -> Tuple[float, int]:
    """Retourne (total_pnl, nb_trades) pour aujourd'hui (UTC).
    Si base_dir est fourni, lit `base_dir/journal.jsonl`, sinon `JSONL_PATH`.
    Ne somme que les événements du jour portant un PnL (ex: event == 'paper_close').
    """
    path = (pathlib.Path(base_dir) / "journal.jsonl") if base_dir else JSONL_PATH
    trades = 0
    total = 0.0
    for rec in _iter_events_today(path):
        if rec.get("event") == "paper_close" or (rec.get("type") == "paper" and "pnl" in rec):
            try:
                pnl = float(rec.get("pnl", 0.0))
            except Exception:
                pnl = 0.0
            trades += 1
            total += pnl
    return round(total, 2), trades

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="kobe.cli_show_log", description="Afficher journal et PnL du jour")
    ap.add_argument("--tail", type=int, default=10, help="Dernières lignes à afficher avant le résumé PnL")
    ap.add_argument("--pnl-today", dest="pnl_today", action="store_true", help="Afficher le PnL du jour")
    args = ap.parse_args()

    # Affiche un aperçu du journal si demandé
    if args.tail and JSONL_PATH.exists():
        print(f"[show-log] dernières {args.tail} lignes :")
        for ln in JSONL_PATH.read_text(encoding="utf-8").splitlines()[-args.tail:]:
            print(ln)

    if args.pnl_today:
        total, n = pnl_today()
        print(f"[pnl-today] trades: {n}, total: {total:.2f}")
