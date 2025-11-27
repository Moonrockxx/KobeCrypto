from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


DATASET_DEFAULT = "logs/decisions_dataset.csv"
ANALYSIS_DEFAULT = "logs/decisions_analysis.csv"


@dataclass(frozen=True)
class FamilyKey:
    symbol: str
    setup_id: str
    regime_trend: str
    regime_volatility: str


@dataclass
class FamilyStats:
    total_events: int = 0
    by_stage: Dict[str, int] | None = None
    qualities: List[float] | None = None
    rr_values: List[float] | None = None

    def __post_init__(self) -> None:
        if self.by_stage is None:
            self.by_stage = {}
        if self.qualities is None:
            self.qualities = []
        if self.rr_values is None:
            self.rr_values = []


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset introuvable: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def build_families(rows: List[Dict[str, Any]]) -> Dict[FamilyKey, FamilyStats]:
    families: Dict[FamilyKey, FamilyStats] = {}

    for row in rows:
        symbol = row.get("symbol") or "UNKNOWN"
        setup_id = row.get("setup_id") or "none"
        regime_trend = row.get("regime_trend") or "unknown"
        regime_volatility = row.get("regime_volatility") or "unknown"
        stage = row.get("decision_stage") or "unknown"

        key = FamilyKey(
            symbol=str(symbol),
            setup_id=str(setup_id),
            regime_trend=str(regime_trend),
            regime_volatility=str(regime_volatility),
        )

        if key not in families:
            families[key] = FamilyStats()

        stats = families[key]
        stats.total_events += 1
        stats.by_stage[stage] = stats.by_stage.get(stage, 0) + 1  # type: ignore[index]

        q = _safe_float(row.get("setup_quality"))
        if q is not None:
            stats.qualities.append(q)  # type: ignore[union-attr]

        rr = _safe_float(row.get("proposal_rr"))
        if rr is not None:
            stats.rr_values.append(rr)  # type: ignore[union-attr]

    return families


def write_analysis_csv(
    families: Dict[FamilyKey, FamilyStats],
    output_path: Path,
    min_events: int = 1,
) -> None:
    """Écrit un CSV d'analyse par famille (symbol/setup/regime)."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collecter tous les stages rencontrés pour avoir des colonnes dédiées
    all_stages: set[str] = set()
    for stats in families.values():
        all_stages.update(stats.by_stage.keys())  # type: ignore[union-attr]

    stage_cols = sorted(all_stages)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        header = [
            "symbol",
            "setup_id",
            "regime_trend",
            "regime_volatility",
            "total_events",
            "avg_setup_quality",
            "avg_proposal_rr",
            "num_quality_samples",
            "num_rr_samples",
        ] + [f"count_{st}" for st in stage_cols]

        writer.writerow(header)

        # Tri des familles pour un résultat lisible et stable
        for key, stats in sorted(
            families.items(),
            key=lambda kv: (
                kv[0].symbol,
                kv[0].setup_id,
                kv[0].regime_trend,
                kv[0].regime_volatility,
            ),
        ):
            if stats.total_events < min_events:
                continue

            avg_q = mean(stats.qualities) if stats.qualities else None  # type: ignore[arg-type]
            avg_rr = mean(stats.rr_values) if stats.rr_values else None  # type: ignore[arg-type]

            row: List[Any] = [
                key.symbol,
                key.setup_id,
                key.regime_trend,
                key.regime_volatility,
                stats.total_events,
                avg_q if avg_q is not None else "",
                avg_rr if avg_rr is not None else "",
                len(stats.qualities or []),
                len(stats.rr_values or []),
            ]

            by_stage = stats.by_stage or {}
            for st in stage_cols:
                row.append(by_stage.get(st, 0))

            writer.writerow(row)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse des décisions Kobe (V4.3) par famille (symbol/setup/regime).",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=DATASET_DEFAULT,
        help="Chemin vers le CSV de dataset détaillé (défaut: logs/decisions_dataset.csv).",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=ANALYSIS_DEFAULT,
        help="Chemin du CSV d'analyse (défaut: logs/decisions_analysis.csv).",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=1,
        help="Nombre minimum d'events par famille pour apparaître dans le rapport.",
    )

    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset)
    output_path = Path(args.output_csv)

    rows = load_dataset(dataset_path)
    if not rows:
        print(f"Dataset vide: {dataset_path}")
        return 0

    families = build_families(rows)
    write_analysis_csv(families, output_path, min_events=args.min_events)

    print(f"Analyse écrite dans: {output_path}")
    print(f"Nombre de familles: {len(families)}")

    # Petit récap console des familles les plus actives
    # Tri par nombre total d'events décroissant
    top = sorted(
        families.items(),
        key=lambda kv: kv[1].total_events,
        reverse=True,
    )

    print("Top familles (symbol, setup, regime_trend, regime_volatility, total_events):")
    for key, stats in top[:20]:
        print(
            f"  - {key.symbol}, {key.setup_id}, {key.regime_trend}, {key.regime_volatility}: "
            f"{stats.total_events} events"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
