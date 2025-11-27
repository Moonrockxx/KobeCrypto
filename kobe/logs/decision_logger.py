from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Permet éventuellement de surcharger l'emplacement des logs via une variable d'environnement.
_LOGS_DIR_ENV = "KOBE_LOGS_DIR"


def _get_decisions_log_path(ts: datetime | None = None) -> Path:
    """
    Retourne le chemin vers le fichier JSONL des décisions pour la date donnée.
    Crée le dossier logs/decisions si nécessaire.
    """
    if ts is None:
        ts = datetime.now(timezone.utc)

    # Si l'utilisateur définit KOBE_LOGS_DIR, on respecte ce chemin.
    base_dir = os.getenv(_LOGS_DIR_ENV)
    if base_dir:
        base = Path(base_dir)
    else:
        # Par défaut: racine du projet / logs / decisions
        # Ce fichier est kobe/logs/decision_logger.py → parents[2] ≈ racine du repo.
        base = Path(__file__).resolve().parents[2] / "logs" / "decisions"

    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # On ne casse jamais le runner pour un problème de dossier de logs.
        print(f"[decision_logger] impossible de créer le dossier de logs {base}: {e}")

    filename = ts.strftime("%Y-%m-%d_decisions.jsonl")
    return base / filename


def log_decision(event: Mapping[str, Any]) -> None:
    """
    Ajoute un événement de décision dans un fichier JSONL.

    - Ajoute un timestamp 'ts' en UTC si absent.
    - Ne lève jamais d'exception vers l'appelant (sécurité du runner).
    """
    try:
        # Copie défensive pour ne pas surprendre l'appelant.
        data = dict(event)  # type: ignore[arg-type]
    except Exception:
        # Si ce n'est pas mappable, on encapsule.
        data = {"value": repr(event)}

    ts_value = data.get("ts")
    if isinstance(ts_value, datetime):
        ts_dt = ts_value.astimezone(timezone.utc)
        data["ts"] = ts_dt.isoformat()
    elif isinstance(ts_value, str):
        # On garde la string telle quelle, mais on essaye de s'en servir pour choisir le fichier.
        try:
            ts_dt = datetime.fromisoformat(ts_value)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        except Exception:
            ts_dt = datetime.now(timezone.utc)
            data["ts"] = ts_dt.isoformat()
    else:
        ts_dt = datetime.now(timezone.utc)
        data["ts"] = ts_dt.isoformat()

    path = _get_decisions_log_path(ts_dt)

    try:
        line = json.dumps(data, ensure_ascii=False, default=str)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        # On log l'erreur mais on ne casse pas la boucle d'appel.
        print(f"[decision_logger] erreur lors de l'écriture dans {path}: {e}")
