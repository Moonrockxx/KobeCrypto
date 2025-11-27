from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any, Dict

import yaml


@dataclass(frozen=True)
class StrategyProfile:
    id: str
    version: str
    description: str | None = None
    raw: Dict[str, Any] | None = None


def _default_profile() -> StrategyProfile:
    """Profil de repli si le fichier est manquant ou invalide.

    Important: ce fallback DOIT rester conservateur.
    """
    return StrategyProfile(
        id="default",
        version="v4.3-dev",
        description="Fallback profile (strategy_profile.yaml manquant ou invalide).",
        raw=None,
    )


@lru_cache(maxsize=1)
def load_strategy_profile(path: Optional[str] = None) -> StrategyProfile:
    """Charge le profil de stratégie depuis un YAML dédié.

    - Fichier par défaut: <racine_projet>/config/strategy_profile.yaml
    - En cas d'erreur de lecture/parsing, on retourne un profil par défaut
      et on log l'erreur en console sans casser le runner.
    """
    if path is not None:
        p = Path(path)
    else:
        # __file__ = .../kobe/core/strategy_profile.py
        # parents[0] = .../kobe/core
        # parents[1] = .../kobe
        # parents[2] = .../
        root = Path(__file__).resolve().parents[2]
        p = root / "config" / "strategy_profile.yaml"

    try:
        if not p.exists():
            print(f"[strategy_profile] fichier introuvable: {p} → fallback.")
            return _default_profile()

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[strategy_profile] erreur de lecture/parsing {p}: {e} → fallback.")
        return _default_profile()

    if not isinstance(data, dict):
        print(f"[strategy_profile] contenu non dict dans {p} → fallback.")
        return _default_profile()

    profile_id = str(data.get("id") or "default")
    version = str(data.get("version") or "v4.3-dev")
    description = data.get("description")
    return StrategyProfile(
        id=profile_id,
        version=version,
        description=description,
        raw=data,
    )


def get_strategy_version() -> str:
    """Version de la stratégie (pour les logs, reports, etc.)."""
    return load_strategy_profile().version


def get_strategy_id() -> str:
    """Identifiant lisible du profil de stratégie."""
    return load_strategy_profile().id
