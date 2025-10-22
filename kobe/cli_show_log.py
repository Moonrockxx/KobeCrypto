from __future__ import annotations
import argparse, json, os, sys, datetime as dt
from typing import Iterable

def _utc_date_of(ts: str) -> dt.date:
    # "2025-10-22T18:15:27Z" -> date UTC
    ts = ts.strip().replace("Z", "+00:00")
    return dt.datetime.fromisoformat(ts).astimezone(dt.timezone.utc).date()

def iter_jsonl(path: str) -> Iterable[dict]:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # Ignore ligne corrompue, on continue
                continue

def tail_jsonl(path: str, n: int) -> list[dict]:
    if not os.path.exists(path): 
        return []
    # Tail naïf (suffisant v0)
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    for raw in lines[-n:]:
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out

def pnl_today(logs_dir: str = "logs") -> tuple[float, int]:
    """Somme des PnL (paper_close) de la date UTC du jour."""
    path = os.path.join(logs_dir, "journal.jsonl")
    today = dt.datetime.utcnow().date()
    total = 0.0
    count = 0
    for ev in iter_jsonl(path) or []:
        if ev.get("event") != "paper_close":
            continue
        try:
            if _utc_date_of(ev["ts"]) != today:
                continue
        except Exception:
            continue
        pnl = float(ev.get("pnl", 0.0))
        total += pnl
        count += 1
    return total, count

def _fmt_money(x: float) -> str:
    sign = "+" if x > 0 else ""  # garde le "-" si négatif
    return f"{sign}{x:.2f}"

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m kobe.cli_show_log",
        description="Affiche la queue du journal et le PnL du jour (paper)."
    )
    p.add_argument("--logs-dir", default="logs", help="Dossier journaux (def: logs)")
    p.add_argument("--tail", type=int, default=10, help="Afficher les N dernières lignes (def: 10)")
    p.add_argument("--pnl-today", action="store_true", help="Afficher la somme du PnL du jour (paper_close)")
    args = p.parse_args(argv)

    path = os.path.join(args.logs_dir, "journal.jsonl")

    # Tail
    if args.tail and args.tail > 0:
        rows = tail_jsonl(path, args.tail)
        if not rows:
            print("[show-log] aucun journal à afficher (journal.jsonl introuvable ou vide).")
        else:
            print(f"[show-log] dernières {len(rows)} lignes :")
            for r in rows:
                print(json.dumps(r, ensure_ascii=False))

    # PnL today
    if args.pnl_today:
        total, count = pnl_today(args.logs_dir)
        print(f"[pnl-today] trades: {count}, total: {_fmt_money(total)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
