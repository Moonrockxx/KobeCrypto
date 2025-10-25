from __future__ import annotations
from pydantic import BaseModel, Field
from kobe.signals.proposal import Proposal

class RiskConfig(BaseModel):
    max_trade_pct: float = Field(0.5, gt=0, le=100)     # plafond absolu par trade (% capital)
    max_proposal_pct: float = Field(0.25, gt=0, le=100) # plafond absolu pour une proposal (% capital)

def _check_levels(p: Proposal) -> None:
    if p.side == "long":
        if not (p.stop < p.entry < p.take):
            raise ValueError("Niveaux incohérents: attendu LONG avec stop < entry < take.")
    else:
        if not (p.stop > p.entry > p.take):
            raise ValueError("Niveaux incohérents: attendu SHORT avec stop > entry > take.")

def _check_reasons(p: Proposal) -> None:
    if len([r for r in p.reasons if str(r).strip()]) < 3:
        raise ValueError("Au moins 3 raisons non vides sont requises.")

def validate_proposal(p: Proposal, cfg: RiskConfig, *, is_proposal: bool = True) -> bool:
    """
    Valide une Proposal par rapport aux garde-fous runtime.
    - Vérifie la cohérence des niveaux (stop/entry/take).
    - Vérifie le nombre de raisons (≥3).
    - Vérifie le plafond de risque (% capital) selon le contexte :
      * is_proposal=True  → p.risk_pct ≤ cfg.max_proposal_pct
      * is_proposal=False → p.risk_pct ≤ cfg.max_trade_pct
    Renvoie True si tout est OK, sinon lève ValueError.
    """
    _check_levels(p)
    _check_reasons(p)

    limit = cfg.max_proposal_pct if is_proposal else cfg.max_trade_pct
    if p.risk_pct > limit:
        kind = "proposal" if is_proposal else "trade"
        raise ValueError(
            f"Risque {p.risk_pct}% > plafond {limit}% ({kind}). Ajuste risk_pct ou la config."
        )
    return True
