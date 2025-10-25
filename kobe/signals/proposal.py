from __future__ import annotations
from typing import List, Literal, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, model_validator

Side = Literal["long", "short"]

class Proposal(BaseModel):
    """
    Proposition de trade minimale V1.
    - risk_pct: pourcentage de capital risqué (max 0.25% pour une proposal selon SOP V1)
    - size_pct: taille cible du trade en % du capital (indicatif; sizing exact calculé avec position_size)
    - reasons: au moins 3 raisons
    - ttl_minutes: durée de validité (après quoi on ignore le signal)
    """
    symbol: str
    side: Side
    entry: float
    stop: float
    take: float
    risk_pct: float = Field(..., gt=0, le=0.25, description="Risque % capital, ≤ 0.25% pour proposal")
    size_pct: float = Field(..., gt=0, le=100, description="Taille cible % capital (indicatif)")
    reasons: List[str]
    ttl_minutes: int = Field(60, gt=0, le=1440)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _validate_levels_and_reasons(self) -> "Proposal":
        if self.side == "long":
            if not (self.stop < self.entry < self.take):
                raise ValueError("Pour LONG: stop < entry < take.")
        else:  # short
            if not (self.stop > self.entry > self.take):
                raise ValueError("Pour SHORT: stop > entry > take.")
        if len([r for r in self.reasons if r.strip()]) < 3:
            raise ValueError("Fournir au moins 3 raisons.")
        return self

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now > self.created_at + timedelta(minutes=self.ttl_minutes)

    def r_multiple(self) -> Optional[float]:
        """Renvoie le multiple de R (gain potentiel / risque)."""
        r = abs(self.entry - self.stop)
        if r <= 0:
            return None
        if self.side == "long":
            return (self.take - self.entry) / r
        return (self.entry - self.take) / r

def position_size(balance_usd: float, risk_pct: float, entry: float, stop: float, leverage: float = 1.0) -> float:
    """
    Calcule une taille approximative (en coin/base) pour risquer `risk_pct` du capital.
    Hypothèse produit linéaire: risk_amount = qty * |entry - stop|.
    qty ≈ (balance * risk_pct/100) / |entry - stop| / entry * leverage
    """
    if balance_usd <= 0 or entry <= 0 or stop <= 0:
        raise ValueError("Paramètres invalides pour le sizing.")
    risk_amount = balance_usd * (risk_pct / 100.0)
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        raise ValueError("entry et stop ne doivent pas être égaux.")
    qty = (risk_amount / risk_per_unit) * leverage / entry
    return max(qty, 0.0)

def format_proposal_for_telegram(p: Proposal, balance_usd: Optional[float] = None, leverage: float = 1.0) -> str:
    """Formate un message Telegram actionnable (n'envoie rien)."""
    rm = p.r_multiple()
    rm_txt = f"{rm:.2f}R" if rm is not None else "—"

    size_line = ""
    if balance_usd is not None:
        try:
            qty = position_size(balance_usd, p.risk_pct, p.entry, p.stop, leverage)
            size_line = f"\nTaille approx: {qty:.4f} {p.symbol} (lev {leverage}x, risque {p.risk_pct}%)"
        except Exception:
            size_line = ""

    header = f"⚡️ PROPOSAL {p.side.upper()} {p.symbol}"
    lines = [
        header,
        f"Entrée: {p.entry}",
        f"Stop: {p.stop}",
        f"Take: {p.take}",
        f"Risque: {p.risk_pct}% (≤0.25%) | Payoff: {rm_txt}",
        f"TTL: {p.ttl_minutes} min | Créé: {p.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    msg = "\n".join(lines) + size_line
    reasons = "\n - ".join(p.reasons)
    msg += f"\nRaisons:\n - {reasons}"
    return msg
