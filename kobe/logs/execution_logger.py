from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional

# Permet de surcharger le dossier de logs (même logique que decision_logger)
_LOGS_DIR_ENV = "KOBE_LOGS_DIR"


class ExecutionStatus(str, Enum):
    """
    Statut standardisé d'une tentative d'exécution.

    - SUCCESS        : l'exchange a accepté l'ordre (orderId / status OK)
    - TOO_SMALL      : taille insuffisante (contraintes Binance LOT_SIZE / NOTIONAL)
    - EXCHANGE_ERROR : erreur côté exchange (4xx/5xx, problème réseau, etc.)
    - REJECTED       : rejet interne Kobe (risque, filtres, etc.)
    - CANCELLED      : plan d'ordres annulé (timeout, changement de contexte...)
    """
    SUCCESS = "success"
    TOO_SMALL = "too_small"
    EXCHANGE_ERROR = "exchange_error"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def _get_executions_log_path(ts: Optional[datetime] = None) -> Path:
    """
    Retourne le chemin vers le fichier JSONL des exécutions pour la date donnée.
    Crée le dossier logs/executions si nécessaire.
    """
    ts = ts or datetime.now(timezone.utc)
    base_dir = os.getenv(_LOGS_DIR_ENV, "logs")
    executions_dir = Path(base_dir) / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    filename = ts.strftime("%Y-%m-%d_executions.jsonl")
    return executions_dir / filename


@dataclass
class ExecutionEvent:
    """
    Évènement d'exécution standardisé.

    Le but est d'avoir assez d'infos pour reconstituer :
    - le contexte (symbol, side, exchange, mode),
    - le lien avec la Proposal / decision_id,
    - ce qui a été tenté (entry/stop/take, qty),
    - et si ça a réellement abouti sur l'exchange.
    """
    ts: str
    symbol: str
    side: str
    exchange: str
    mode: str  # "paper" / "testnet" / "live" (ou équivalent Mode.name)
    stage: str  # "attempt" / "result"
    status: str  # valeur de ExecutionStatus ou dérivé
    decision_id: Optional[str] = None
    proposal_id: Optional[str] = None
    order_kind: Optional[str] = None  # "entry" / "take_profit" / "stop_loss" / "plan"
    entry: Optional[float] = None
    stop: Optional[float] = None
    take: Optional[float] = None
    qty: Optional[float] = None

    # Détails API / erreurs éventuelles
    error: Optional[str] = None
    error_code: Optional[str] = None
    http_status: Optional[int] = None

    # Payload bruts (doivent rester raisonnables en taille)
    request_payload: Optional[Mapping[str, Any]] = None
    response_payload: Optional[Mapping[str, Any]] = None

    # Champ libre pour rattacher des infos Kobe spécifiques
    meta: Optional[Mapping[str, Any]] = None


def _serialize_event(event: ExecutionEvent) -> dict[str, Any]:
    """
    Prépare l'évènement pour JSON (conversion des Enum / objets).
    """
    data: dict[str, Any] = asdict(event)
    # Normalisation simple : status = str(...)
    data["status"] = str(data.get("status"))
    return data


def log_execution_event(event: ExecutionEvent) -> None:
    """
    Ajoute un évènement d'exécution dans le JSONL du jour.

    Cette fonction ne doit **jamais** faire planter l'exécuteur :
    toute erreur de fichier est attrapée et ignorée.
    """
    try:
        path = _get_executions_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            json.dump(_serialize_event(event), f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        # On ne veut pas que des problèmes de disque / droits cassent un trade.
        return


def log_execution_attempt(
    *,
    symbol: str,
    side: str,
    exchange: str,
    mode: str,
    decision_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    order_kind: Optional[str] = None,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    take: Optional[float] = None,
    qty: Optional[float] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> None:
    """
    Helper pour loguer le moment où Kobe tente d'exécuter un plan d'ordres
    (avant la réponse de l'exchange).
    """
    now = datetime.now(timezone.utc).isoformat()
    evt = ExecutionEvent(
        ts=now,
        symbol=symbol,
        side=side,
        exchange=exchange,
        mode=mode,
        stage="attempt",
        status=ExecutionStatus.SUCCESS.name,  # "SUCCESS" signifie ici "tentative émise"
        decision_id=decision_id,
        proposal_id=proposal_id,
        order_kind=order_kind,
        entry=entry,
        stop=stop,
        take=take,
        qty=qty,
        meta=dict(meta) if meta is not None else None,
    )
    log_execution_event(evt)


def log_execution_result(
    *,
    symbol: str,
    side: str,
    exchange: str,
    mode: str,
    status: ExecutionStatus,
    decision_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    order_kind: Optional[str] = None,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    take: Optional[float] = None,
    qty: Optional[float] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
    http_status: Optional[int] = None,
    request_payload: Optional[Mapping[str, Any]] = None,
    response_payload: Optional[Mapping[str, Any]] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> None:
    """
    Helper pour loguer le résultat final d'une exécution :
    - statut SUCCESS / TOO_SMALL / EXCHANGE_ERROR / ...
    - détails d'erreur / réponse exchange si dispo.
    """
    now = datetime.now(timezone.utc).isoformat()
    evt = ExecutionEvent(
        ts=now,
        symbol=symbol,
        side=side,
        exchange=exchange,
        mode=mode,
        stage="result",
        status=status.name,
        decision_id=decision_id,
        proposal_id=proposal_id,
        order_kind=order_kind,
        entry=entry,
        stop=stop,
        take=take,
        qty=qty,
        error=error,
        error_code=error_code,
        http_status=http_status,
        request_payload=dict(request_payload) if request_payload is not None else None,
        response_payload=dict(response_payload) if response_payload is not None else None,
        meta=dict(meta) if meta is not None else None,
    )
    log_execution_event(evt)
