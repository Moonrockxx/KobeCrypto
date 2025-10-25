from __future__ import annotations
from enum import Enum
from typing import Dict, Any
from kobe.core.secrets import get_mode

class Mode(str, Enum):
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"

def current_mode(cfg: Dict[str, Any]) -> Mode:
    """Retourne le Mode courant à partir de la config fusionnée (.env + config)."""
    m = get_mode(cfg)
    if m == "paper":
        return Mode.PAPER
    if m == "testnet":
        return Mode.TESTNET
    if m == "live":
        return Mode.LIVE
    # sécurité: ne devrait jamais arriver avec get_mode()
    return Mode.PAPER

def is_paper(cfg: Dict[str, Any]) -> bool:
    return current_mode(cfg) == Mode.PAPER

def is_testnet(cfg: Dict[str, Any]) -> bool:
    return current_mode(cfg) == Mode.TESTNET

def is_live(cfg: Dict[str, Any]) -> bool:
    return current_mode(cfg) == Mode.LIVE
