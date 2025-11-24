from __future__ import annotations

from typing import Optional, Dict, Any, List

from kobe.signals.proposal import Proposal
from kobe.signals.setups import scan_setups


def _choose_best_candidate(
    candidates: List[Dict[str, Any]], min_quality: float = 0.6
) -> Optional[Dict[str, Any]]:
    """Filtre et choisit le meilleur candidat en fonction de la quality."""
    if not candidates:
        return None
    filtered = [c for c in candidates if c.get("quality", 0.0) >= min_quality]
    if not filtered:
        return None
    filtered.sort(key=lambda c: float(c.get("quality", 0.0)), reverse=True)
    return filtered[0]


def _build_proposal_from_candidate(
    candidate: Dict[str, Any],
    market: Dict[str, Any],
) -> Optional[Proposal]:
    """Construit une Proposal à partir d'un candidat de setup + snapshot marché."""
    symbol = str(candidate.get("symbol") or market.get("symbol") or "BTCUSDC").upper()
    side = candidate.get("side")
    if side not in ("long", "short"):
        return None

    entry_hint = candidate.get("entry_hint") or {}
    stop_hint = candidate.get("stop_hint") or {}
    take_hint = candidate.get("take_hint") or {}

    try:
        entry = float(entry_hint.get("price", 0.0))
        stop = float(stop_hint.get("price", 0.0))
        take = float(take_hint.get("price", 0.0))
    except (TypeError, ValueError):
        return None

    if entry <= 0 or stop <= 0 or take <= 0:
        return None

    reasons = candidate.get("reasons") or []
    if len(reasons) < 3:
        # Invariant projet : ≥3 raisons explicites par signal
        return None

    quality = float(candidate.get("quality", 0.0))
    quality = max(0.0, min(1.0, quality))

    # Risk management : on conserve le risk_pct global de 0.25 par défaut.
    # size_pct pourrait être modulé plus tard en fonction de la volatilité / qualité.
    return Proposal(
        symbol=symbol,
        side=side,
        entry=round(entry, 2),
        stop=round(stop, 2),
        take=round(take, 2),
        risk_pct=0.25,
        size_pct=5.0,
        reasons=list(reasons)[:5],
        ttl_minutes=45,
    )


def generate_proposal_from_factors(market: Dict[str, Any]) -> Optional[Proposal]:
    """
    Génération d'une Proposal à partir du nouveau pipeline V4.2 :

    - `market` est un snapshot enrichi issu du Factor Engine (get_market_snapshot),
      incluant notamment:
        - "symbol"
        - "price"
        - "timeframes" (15m, 1h, 4h, 1d)
        - "regime" (trend, volatility)
        - anciens facteurs "plats" (trend_strength, funding_bias, volatility, etc.)
    - `scan_setups(market)` retourne des setups structurés (candidats),
    - on filtre / choisit le meilleur candidat,
    - on construit une Proposal exécutable.

    Renvoie None s'il n'y a aucun setup suffisamment qualitatif.
    """
    if not isinstance(market, dict):
        return None

    # 1) Scanner les setups possibles à partir du snapshot de marché.
    candidates = scan_setups(market)
    if not candidates:
        return None

    # 2) Filtrer et choisir le candidat le plus intéressant.
    best = _choose_best_candidate(candidates, min_quality=0.6)
    if not best:
        return None

    # 3) Construire la Proposal finale.
    proposal = _build_proposal_from_candidate(best, market)
    return proposal


# --- Test rapide (mock minimal) ---
if __name__ == "__main__":
    # Exemple ultra simplifié : dans la pratique, `market` doit venir
    # de kobe.core.factors.get_market_snapshot(symbol).
    market_sample = {
        "symbol": "BTCUSDC",
        "timeframes": {},
        "regime": {"trend": "range", "volatility": "normal"},
    }
    p = generate_proposal_from_factors(market_sample)
    if p:
        print("✅ Proposal générée:", p.symbol, p.side, "→", len(p.reasons), "raisons.")
    else:
        print("⚙️  Aucun signal.")
