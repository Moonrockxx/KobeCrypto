

# -*- coding: utf-8 -*-
"""
Test: chaque signal émis par la démo doit contenir **exactement 3 raisons** non vides.

Stratégie de test:
- On lance la démo via la CLI: `python -m kobe.cli scan --demo --json-only`.
- Si la sortie est "None" (pas de signal aujourd'hui, ou clamp actif), on **skip** le test (non pertinent).
- Sinon, on parse le JSON et on vérifie que `reasons` est une liste de 3 chaînes non vides.

Remarque:
- Le clamp ≤1/jour peut renvoyer "None"; le skip évite les faux négatifs en CI locale.
"""
from __future__ import annotations
import json
import subprocess
import sys

import pytest


def _run_cli_demo_once() -> str:
    """Exécute la démo une fois et renvoie stdout (strippé)."""
    cmd = [sys.executable, "-m", "kobe.cli", "scan", "--demo", "--json-only"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "").strip()
    # En cas d'erreur, conserver stderr pour diagnostic
    if proc.returncode not in (0,):
        raise RuntimeError(f"CLI demo failed rc={proc.returncode}: {proc.stderr}")
    return out


def _assert_three_reasons(sig: dict) -> None:
    assert "reasons" in sig, "champ 'reasons' manquant dans le signal"
    reasons = sig["reasons"]
    assert isinstance(reasons, list), "'reasons' doit être une liste"
    assert len(reasons) == 3, f"'reasons' doit contenir exactement 3 éléments, reçu {len(reasons)}"
    for i, r in enumerate(reasons):
        assert isinstance(r, str), f"reason[{i}] n'est pas une chaîne"
        assert r.strip() != "", f"reason[{i}] est vide"


@pytest.mark.timeout(5)
def test_demo_signal_has_three_nonempty_reasons():
    out = _run_cli_demo_once()
    if out == "None" or out == "":
        pytest.skip("Aucun signal émis par la démo (jour sans signal ou clamp actif)")
    try:
        sig = json.loads(out)
    except Exception as e:
        pytest.fail(f"Sortie non-JSON de la démo: {out!r} (err={e})")
    _assert_three_reasons(sig)