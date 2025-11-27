from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

DECISIONS_DIR_DEFAULT = "logs/decisions"


def _parse_ts(ts_str: str) -> datetime:
    """Parse un timestamp ISO8601 en datetime (UTC-safe).

    Tolérant: remplace le suffixe 'Z' par '+00:00' si besoin.
    """
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def _iter_decision_files(log_dir: Path) -> Iterator[Path]:
    """Itère sur les fichiers *_decisions.jsonl du dossier."""
    if not log_dir.exists():
        return
    for p in sorted(log_dir.glob("*_decisions.jsonl")):
        if p.is_file():
            yield p


def _iter_events(
    log_dir: Path,
    since: Optional[date] = None,
    until: Optional[date] = None,
    stages_filter: Optional[Set[str]] = None,
) -> Iterator[Dict[str, Any]]:
    """Lit les events JSONL en appliquant filtres date/stage.

    - Fait un parse tolérant des timestamps.
    - Ignore les lignes corrompues.
    """
    for path in _iter_decision_files(log_dir):
        # Fallback date basée sur le nom du fichier: 2025-11-27_decisions.jsonl
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
                    # Ligne illisible → on skip proprement.
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
                    # Pas de date exploitable → on ignore l'event.
                    continue

                if since is not None and day < since:
                    continue
                if until is not None and day > until:
                    continue

                stage = str(evt.get("decision_stage") or "unknown")
                if stages_filter is not None and stage not in stages_filter:
                    continue

                evt["_day"] = day.isoformat()
                yield evt


def _compute_rr(entry: Optional[float], stop: Optional[float], take: Optional[float], side: Optional[str]) -> Optional[float]:
    """Calcule un ratio R:R théorique si possible.

    - Pour un long: (take - entry) / (entry - stop)
    - Pour un short: (entry - take) / (stop - entry)
    - Retourne None si les données sont insuffisantes ou incohérentes.
    """
    try:
        if entry is None or stop is None or take is None:
            return None
        if side is None:
            return None

        if side.lower() == "long":
            risk = entry - stop
            reward = take - entry
        elif side.lower() == "short":
            risk = stop - entry
            reward = entry - take
        else:
            return None

        if risk <= 0 or reward <= 0:
            return None
        return float(reward) / float(risk)
    except Exception:
        return None


def _flatten_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    """Aplati un event de décision en un dict 'flat' utilisable en CSV."""

    row: Dict[str, Any] = {}

    # Time / identifiants principaux
    ts_raw = evt.get("ts")
    ts_str = str(ts_raw) if ts_raw is not None else ""
    row["ts"] = ts_str

    day_str = str(evt.get("_day") or "")
    row["day"] = day_str

    row["symbol"] = str(evt.get("symbol") or "UNKNOWN")
    row["decision_stage"] = str(evt.get("decision_stage") or "unknown")

    # Meta
    meta = evt.get("meta") or {}
    row["strategy_version"] = str(meta.get("strategy_version") or "")

    # Contexte de marché
    context = evt.get("context") or {}
    regime = context.get("regime") or {}
    row["regime_trend"] = str(regime.get("trend") or "unknown")
    row["regime_volatility"] = str(regime.get("volatility") or "unknown")

    # Setup
    setup = evt.get("setup") or {}
    row["setup_id"] = str(setup.get("id") or "none")
    row["setup_side"] = str(setup.get("side") or "")
    row["setup_quality"] = setup.get("quality")

    # Proposal (plan de trade suggéré)
    proposal = evt.get("proposal") or {}
    entry = proposal.get("entry")
    stop = proposal.get("stop")
    take = proposal.get("take")
    side = proposal.get("side") or setup.get("side")

    row["proposal_entry"] = entry
    row["proposal_stop"] = stop
    row["proposal_take"] = take
    row["proposal_risk_pct"] = proposal.get("risk_pct")
    reasons = proposal.get("reasons") or []
    if isinstance(reasons, list):
        row["proposal_num_reasons"] = len(reasons)
    else:
        row["proposal_num_reasons"] = 0

    row["proposal_rr"] = _compute_rr(
        float(entry) if isinstance(entry, (int, float)) else None,
        float(stop) if isinstance(stop, (int, float)) else None,
        float(take) if isinstance(take, (int, float)) else None,
        str(side) if side is not None else None,
    )

    # Exécution (si présente)
    execution = evt.get("execution") or {}
    row["execution_status"] = str(execution.get("status") or "")
    row["execution_mode"] = str(execution.get("mode") or "")
    row["execution_price"] = execution.get("price")
    row["execution_qty"] = execution.get("qty")
    row["execution_exchange"] = execution.get("exchange")
    row["execution_order_id"] = execution.get("order_id")

    # Flatten timeframes si présents
    timeframes = context.get("timeframes") or {}
    if isinstance(timeframes, dict):
        for tf_name, tf_data in timeframes.items():
            if not isinstance(tf_data, dict):
                continue
            for key, value in tf_data.items():
                col = f"{tf_name}_{key}"
                row[col] = value

    return row


def build_dataset(
    log_dir: Path,
    since: Optional[date] = None,
    until: Optional[date] = None,
    stages_filter: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Construit une liste de lignes 'flat' à partir des logs de décisions."""
    rows: List[Dict[str, Any]] = []
    for evt in _iter_events(log_dir, since=since, until=until, stages_filter=stages_filter):
        flat = _flatten_event(evt)
        rows.append(flat)
    return rows


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_stage_filters(values: Optional[List[str]]) -> Optional[Set[str]]:
    if not values:
        return None
    return {v.strip() for v in values if v and v.strip()}


def write_dataset_csv(
    rows: List[Dict[str, Any]],
    output_path: Path,
) -> None:
    """Écrit un CSV à partir d'une liste de dicts flattenés.

    - Construit dynamiquement la liste des colonnes.
    - Garde un ordre raisonnable: d'abord les colonnes "core", puis le reste trié.
    """
    if not rows:
        print("Aucune ligne à écrire (dataset vide).")
        return

    # Colonnes core qu'on souhaite toujours voir en premier si présentes
    core_cols_order = [
        "ts",
        "day",
        "symbol",
        "decision_stage",
        "strategy_version",
        "regime_trend",
        "regime_volatility",
        "setup_id",
        "setup_side",
        "setup_quality",
        "proposal_entry",
        "proposal_stop",
        "proposal_take",
        "proposal_risk_pct",
        "proposal_rr",
        "proposal_num_reasons",
        "execution_status",
        "execution_mode",
        "execution_price",
        "execution_qty",
        "execution_exchange",
        "execution_order_id",
    ]

    # Collecte de toutes les colonnes observées
    all_keys: Set[str] = set()
    for row in rows:
        all_keys.update(row.keys())

    # On garde seulement les core qui existent réellement
    core_cols = [c for c in core_cols_order if c in all_keys]

    # Le reste trié alpha
    remaining_cols = sorted(k for k in all_keys if k not in core_cols)

    fieldnames = core_cols + remaining_cols

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export détaillé des décisions Kobe (V4.3) vers un dataset CSV.",
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
        "--stage",
        action="append",
        default=None,
        help=(
            "Filtre decision_stage (peut être répété, ex: "
            "--stage setup_detected --stage proposal_built). "
            "Si absent, inclut tous les stages."
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="logs/decisions_dataset.csv",
        help="Chemin du CSV de sortie (défaut: logs/decisions_dataset.csv).",
    )

    args = parser.parse_args(argv)

    log_dir = Path(args.log_dir)
    since = _parse_date(args.since)
    until = _parse_date(args.until)
    stages_filter = _parse_stage_filters(args.stage)
    output_csv = Path(args.output_csv)

    rows = build_dataset(log_dir, since=since, until=until, stages_filter=stages_filter)

    if not rows:
        print("Aucun event trouvé dans la plage/stages demandés.")
        return 0

    write_dataset_csv(rows, output_csv)
    print(f"Dataset écrit dans: {output_csv}")
    print(f"Nombre de lignes: {len(rows)}")

    # Petit breakdown rapide par stage
    by_stage: Dict[str, int] = {}
    for r in rows:
        st = str(r.get("decision_stage") or "unknown")
        by_stage[st] = by_stage.get(st, 0) + 1

    print("Répartition par decision_stage:")
    for st, cnt in sorted(by_stage.items(), key=lambda kv: kv[0]):
        print(f"  - {st}: {cnt}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
