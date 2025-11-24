from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from kobe.llm.deepseek_client import chat_complete_json


def _build_referee_prompt(snapshot: Dict[str, Any], proposal: Dict[str, Any]) -> str:
    """
    Construit un prompt pour DeepSeek afin de reviewer une proposition de trade.

    L'objectif n'est PAS de réinventer la proposal, mais de:
    - dire si le trade semble raisonnable ou non,
    - indiquer "take" / "skip" / "adjust",
    - donner un commentaire concis et un niveau de confiance 0..1.
    """
    symbol = proposal.get("symbol", snapshot.get("symbol", "BTCUSDC"))
    side = proposal.get("side", "long")
    entry = proposal.get("entry")
    stop = proposal.get("stop")
    take = proposal.get("take")
    reasons = proposal.get("reasons", [])

    regime = (snapshot.get("regime") or {})
    timeframes = (snapshot.get("timeframes") or {})

    payload = {
        "instruction": (
            "Tu es un risk-manager systématique. "
            "Tu reçois un snapshot de marché + une proposition de trade déjà construite. "
            "Ton rôle est d'évaluer si le trade est raisonnable, de donner TAKE/SKIP/ADJUST, "
            "un commentaire concis (max 3 phrases) et un niveau de confiance 0..1. "
            "Réponds UNIQUEMENT en JSON valide, sans texte autour."
        ),
        "snapshot": {
            "symbol": symbol,
            "regime": regime,
            "timeframes": timeframes,
        },
        "proposal": {
            "symbol": symbol,
            "side": side,
            "entry": entry,
            "stop": stop,
            "take": take,
            "reasons": reasons,
        },
        "expected_schema": {
            "decision": "take | skip | adjust",
            "confidence": "float de 0.0 à 1.0",
            "comment": "string, max 3 phrases",
            "adjustments": {
                "entry": "float ou null",
                "stop": "float ou null",
                "take": "float ou null",
            },
        },
    }

    return json.dumps(payload, ensure_ascii=False)


def review_signal(
    snapshot: Dict[str, Any],
    proposal: Dict[str, Any],
    enabled: bool = True,
    max_tokens: int = 256,
) -> Dict[str, Any]:
    """
    Couche referee optionnelle par DeepSeek.

    - Si enabled=False -> ne fait aucun appel réseau, renvoie un mode 'bypass'.
    - Si budget ou API DeepSeek indisponible -> renvoie mode 'error' avec détails.
    - Si succès -> renvoie:
      {
        "mode": "ok",
        "decision": "take|skip|adjust",
        "confidence": float,
        "comment": str,
        "raw": {...}  # JSON brut DeepSeek
      }
    """
    if not enabled:
        return {
            "mode": "bypass",
            "decision": "take",
            "confidence": 1.0,
            "comment": "Referee LLM désactivé (bypass).",
            "raw": None,
        }

    prompt = _build_referee_prompt(snapshot, proposal)
    ok, resp = chat_complete_json(prompt, max_tokens=max_tokens, temperature=0.15)

    if not ok:
        # resp contient déjà un dict d'erreur {"error": "...", ...}
        return {
            "mode": "error",
            "decision": "take",  # Par défaut on ne bloque pas le trade,
            "confidence": 0.0,
            "comment": f"Referee DeepSeek indisponible: {resp.get('error')}",
            "raw": resp,
        }

    text = resp.get("text", "")
    try:
        parsed = json.loads(text)
    except Exception:
        return {
            "mode": "error",
            "decision": "take",
            "confidence": 0.0,
            "comment": "Réponse DeepSeek non JSON ou invalide.",
            "raw": {"text": text},
        }

    decision = str(parsed.get("decision", "take")).lower().strip()
    if decision not in ("take", "skip", "adjust"):
        decision = "take"

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    comment = str(parsed.get("comment", "")).strip()
    if not comment:
        comment = "Aucun commentaire fourni par le referee."

    return {
        "mode": "ok",
        "decision": decision,
        "confidence": confidence,
        "comment": comment,
        "raw": parsed,
    }


if __name__ == "__main__":
    # Petit test manuel (sans garantie de succès si pas d'API KEY / budget).
    fake_snapshot = {
        "symbol": "BTCUSDC",
        "regime": {"trend": "bull", "volatility": "normal"},
        "timeframes": {},
    }
    fake_proposal = {
        "symbol": "BTCUSDC",
        "side": "long",
        "entry": 100.0,
        "stop": 95.0,
        "take": 110.0,
        "reasons": [
            "Trend haussier H4.",
            "Pullback vers zone de valeur.",
            "Volatilité modérée.",
        ],
    }
    result = review_signal(fake_snapshot, fake_proposal, enabled=False)
    print(result)
