from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, Any


DECISIONS_DIR_DEFAULT = "logs/decisions"


@dataclass(frozen=True)
class DecisionKey:
    day: date
    symbol: str
    regime_trend: str
    regime_volatility: str
    decision_stage: str
    setup_id: str


def _parse_ts(ts_str: str) -> datetime:
    """Parse un timestamp ISO8601 en datetime naïf UTC-safe.

    On reste tolérant: si le parse échoue, on remonte une ValueError et
    l'appelant décidera quoi faire.
    """
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt


def _iter_decision_files(log_dir: Path) -> Iterator[Path]:
    """Itère sur les fichiers *_decisions.jsonl dans le dossier donné."""
    if not log_dir.exists():
        return
    for p in sorted(log_dir.glob("*_decisions.jsonl")):
        if p.is_file():
            yield p


def _iter_events(
    log_dir: Path,
    since: Optional[date] = None,
    until: Optional[date] = None,
) -> Iterator[Dict[str, Any]]:
    """Lit toutes les lignes JSONL et yield des dicts d'events.

    - Filtre optionnellement par date (sur le champ ts si possible,
      sinon sur la date déduite du nom de fichier).
    """
    for path in _iter_decision_files(log_dir):
        # Date de fallback basée sur le nom de fichier: 2025-11-27_decisions.jsonl
        fallback_day: Optional[date] = None
        try:
            stem = path.name.split("_decisions", 1)[0]
            fallback_day = date.fromisoformat(stem)
        except Exception:
            fallback_day = None

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    # Ligne corrompue: on l'ignore.
                    continue

                ts_raw = evt.get("ts")
                day: Optional[date] = None
                if isinstance(ts_raw, str):
                    try:
                        day = _parse_ts(ts_raw).date()
                    except Exception:
                        day = fallback_day
                else:
                    day = fallback_day

                if day is None:
                    # Impossible de déterminer une date: on ignore l'event.
                    continue

                if since is not None and day < since:
                    continue
                if until is not None and day > until:
                    continue

                evt["_day"] = day.isoformat()
                yield evt


def _build_key(evt: Dict[str, Any]) -> DecisionKey:
    day = date.fromisoformat(str(evt.get("_day")))
    symbol = str(evt.get("symbol") or "UNKNOWN")
    stage = str(evt.get("decision_stage") or "unknown")

    context = evt.get("context") or {}
    regime = context.get("regime") or {}
    regime_trend = str(regime.get("trend") or "unknown")
    regime_volatility = str(regime.get("volatility") or "unknown")

    setup = evt.get("setup") or {}
    setup_id = str(setup.get("id") or "none")

    return DecisionKey(
        day=day,
        symbol=symbol,
        regime_trend=regime_trend,
        regime_volatility=regime_volatility,
        decision_stage=stage,
        setup_id=setup_id,
    )


def aggregate_decisions(
    log_dir: Path,
    since: Optional[date] = None,
    until: Optional[date] = None,
) -> Dict[DecisionKey, int]:
    """Agrège les events en comptant les occurrences par (jour, symbol, stage, setup_id)."""
    counts: Dict[DecisionKey, int] = {}
    for evt in _iter_events(log_dir, since=since, until=until):
        key = _build_key(evt)
        counts[key] = counts.get(key, 0) + 1
    return counts


def write_csv_summary(
    counts: Dict[DecisionKey, int],
    output_path: Path,
) -> None:
    """Écrit un CSV avec les agrégations de décisions."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "day",
                "symbol",
                "regime_trend",
                "regime_volatility",
                "decision_stage",
                "setup_id",
                "count",
            ]
        )
        for key, value in sorted(
            counts.items(),
            key=lambda kv: (
                kv[0].day,
                kv[0].symbol,
                kv[0].regime_trend,
                kv[0].regime_volatility,
                kv[0].decision_stage,
                kv[0].setup_id,
            ),
        ):
            writer.writerow(
                [
                    key.day.isoformat(),
                    key.symbol,
                    key.regime_trend,
                    key.regime_volatility,
                    key.decision_stage,
                    key.setup_id,
                    value,
                ]
            )


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agrégation des logs de décisions Kobe (V4.3)."
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=DECISIONS_DIR_DEFAULT,
        help="Dossier contenant les fichiers *_decisions.jsonl (défaut: logs/decisions).",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Date minimale (incluse) au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="Date maximale (incluse) au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="logs/decisions_summary.csv",
        help="Chemin du CSV de sortie (défaut: logs/decisions_summary.csv).",
    )

    args = parser.parse_args(argv)

    log_dir = Path(args.log_dir)
    since = _parse_date(args.since)
    until = _parse_date(args.until)
    output_csv = Path(args.output_csv)

    counts = aggregate_decisions(log_dir, since=since, until=until)

    if not counts:
        print("Aucun event trouvé dans la plage demandée.")
        return 0

    write_csv_summary(counts, output_csv)
    print(f"Résumé écrit dans: {output_csv}")

    # Petit résumé texte rapide
    total_events = sum(counts.values())
    stages = {}
    for key, value in counts.items():
        stages[key.decision_stage] = stages.get(key.decision_stage, 0) + value

    print(f"Total events: {total_events}")
    for stage, value in sorted(stages.items(), key=lambda kv: kv[0]):
        print(f"  - {stage}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
