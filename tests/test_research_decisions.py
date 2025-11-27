from __future__ import annotations

import json
from math import isclose
from pathlib import Path
from typing import Dict, Any, List

from kobe.research.aggregate_decisions import aggregate_decisions
from kobe.research.export_decision_dataset import build_dataset
from kobe.research.analyze_decisions import build_families


def _write_sample_decisions(tmp_dir: Path) -> Path:
    """Crée un dossier logs/decisions avec un fichier JSONL de test."""
    log_dir = tmp_dir / "logs" / "decisions"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "2025-11-27_decisions.jsonl"

    base_context: Dict[str, Any] = {
        "regime": {"trend": "bull", "volatility": "normal"},
        "timeframes": {
            "15m": {"close": 100.0, "atr_pct_14": 0.5},
            "1h": {"close": 100.0, "atr_pct_14": 1.0},
            "4h": {"close": 100.0, "atr_pct_14": 2.0},
            "1d": {"close": 100.0, "atr_pct_14": 2.5},
        },
    }

    events: List[Dict[str, Any]] = [
        # 1) setup_detected avec contexte complet
        {
            "ts": "2025-11-27T10:00:00+00:00",
            "symbol": "BTCUSDC",
            "decision_stage": "setup_detected",
            "meta": {"strategy_version": "v4.3-test"},
            "context": base_context,
            "setup": {
                "id": "trend_breakout_15m_long",
                "side": "long",
                "quality": 0.75,
            },
        },
        # 2) proposal_built avec plan complet (permet de tester proposal_rr)
        {
            "ts": "2025-11-27T10:00:01+00:00",
            "symbol": "BTCUSDC",
            "decision_stage": "proposal_built",
            "meta": {"strategy_version": "v4.3-test"},
            "context": base_context,
            "setup": {
                "id": "trend_breakout_15m_long",
                "side": "long",
                "quality": 0.75,
            },
            "proposal": {
                "entry": 100.0,
                "stop": 98.0,
                "take": 104.0,
                "risk_pct": 0.25,
                "reasons": ["reason A", "reason B", "reason C"],
                "side": "long",
            },
        },
        # 3) no_proposal sans setup ni contexte détaillé
        {
            "ts": "2025-11-27T10:00:02+00:00",
            "symbol": "BTCUSDC",
            "decision_stage": "no_proposal",
            "meta": {"strategy_version": "v4.3-test"},
        },
    ]

    with path.open("w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")

    return log_dir


def test_aggregate_decisions_counts_and_regime(tmp_path: Path) -> None:
    log_dir = _write_sample_decisions(tmp_path)
    counts = aggregate_decisions(log_dir)

    # On doit avoir au moins deux clés différentes (setup_detected, no_proposal)
    assert counts, "aggregate_decisions doit renvoyer au moins un event agrégé"
    setup_key = None
    no_prop_key = None

    for key in counts:
        if key.setup_id == "trend_breakout_15m_long" and key.decision_stage == "setup_detected":
            setup_key = key
        if key.decision_stage == "no_proposal":
            no_prop_key = key

    assert setup_key is not None, "clé setup_detected manquante"
    assert counts[setup_key] == 1
    assert setup_key.regime_trend == "bull"
    assert setup_key.regime_volatility == "normal"

    assert no_prop_key is not None, "clé no_proposal manquante"
    assert counts[no_prop_key] == 1


def test_export_decision_dataset_flatten_and_rr(tmp_path: Path) -> None:
    log_dir = _write_sample_decisions(tmp_path)
    rows = build_dataset(log_dir)

    # On a 3 events de base
    assert len(rows) == 3

    # On recherche la ligne proposal_built
    proposal_rows = [r for r in rows if r.get("decision_stage") == "proposal_built"]
    assert proposal_rows, "aucune ligne proposal_built dans le dataset"
    row = proposal_rows[0]

    # Colonnes principales
    assert row["symbol"] == "BTCUSDC"
    assert row["regime_trend"] == "bull"
    assert row["regime_volatility"] == "normal"

    # Proposal et R:R
    assert row["proposal_entry"] == 100.0
    assert row["proposal_stop"] == 98.0
    assert row["proposal_take"] == 104.0
    assert row["proposal_risk_pct"] == 0.25
    assert row["proposal_num_reasons"] == 3
    # (take - entry) / (entry - stop) = (104 - 100) / (100 - 98) = 4 / 2 = 2.0
    assert isclose(row["proposal_rr"], 2.0, rel_tol=1e-6)

    # Flatten des timeframes
    assert "15m_close" in row
    assert row["15m_close"] == 100.0
    assert "15m_atr_pct_14" in row
    assert row["15m_atr_pct_14"] == 0.5


def test_analyze_decisions_family_stats_basic() -> None:
    # On construit un dataset minimal en mémoire et on vérifie les stats par famille.
    rows = [
        {
            "symbol": "BTCUSDC",
            "setup_id": "trend_breakout_15m_long",
            "regime_trend": "bull",
            "regime_volatility": "normal",
            "decision_stage": "proposal_built",
            "setup_quality": "0.8",
            "proposal_rr": "2.0",
        },
        {
            "symbol": "BTCUSDC",
            "setup_id": "trend_breakout_15m_long",
            "regime_trend": "bull",
            "regime_volatility": "normal",
            "decision_stage": "setup_detected",
            "setup_quality": "0.6",
            "proposal_rr": "2.5",
        },
        {
            "symbol": "BTCUSDC",
            "setup_id": "none",
            "regime_trend": "unknown",
            "regime_volatility": "unknown",
            "decision_stage": "no_proposal",
        },
    ]

    from kobe.research.analyze_decisions import build_families  # import local pour éviter cycles

    families = build_families(rows)
    assert len(families) == 2

    breakout_stats = None
    none_stats = None

    for key, stats in families.items():
        if key.setup_id == "trend_breakout_15m_long":
            breakout_stats = stats
        if key.setup_id == "none":
            none_stats = stats

    assert breakout_stats is not None, "famille trend_breakout_15m_long manquante"
    assert breakout_stats.total_events == 2
    assert breakout_stats.by_stage.get("proposal_built", 0) == 1
    assert breakout_stats.by_stage.get("setup_detected", 0) == 1
    assert len(breakout_stats.qualities or []) == 2
    assert len(breakout_stats.rr_values or []) == 2
    avg_quality = sum(breakout_stats.qualities or []) / len(breakout_stats.qualities or [1.0])
    assert isclose(avg_quality, 0.7, rel_tol=1e-6)

    assert none_stats is not None, "famille 'none' manquante"
    assert none_stats.total_events == 1
    assert none_stats.by_stage.get("no_proposal", 0) == 1
