from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


# --- Exceptions spécifiques exchange ---
class ExchangeError(Exception):
    """Erreur générique liée à un exchange."""
    pass


class AuthenticationError(ExchangeError):
    """Clés invalides ou manquantes."""
    pass


class NetworkError(ExchangeError):
    """Erreur réseau ou de connectivité (timeout, DNS, etc.)."""
    pass


# --- Interface de base ---
class Exchange(ABC):
    """
    Interface abstraite commune à tous les exchanges.
    Chaque implémentation doit respecter cette signature pour rester interchangeable.
    """

    name: str = "AbstractExchange"
    supports_testnet: bool = False

    @abstractmethod
    def load_markets(self) -> Dict[str, Any]:
        """Charge et renvoie les métadonnées des marchés disponibles."""
        raise NotImplementedError

    @abstractmethod
    def get_balance(self, asset: str) -> float:
        """Renvoie le solde disponible pour un actif donné."""
        raise NotImplementedError

    @abstractmethod
    def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        qty: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Crée un ordre (market ou limit)."""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Annule un ordre par ID."""
        raise NotImplementedError

    @abstractmethod
    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Liste les ordres ouverts."""
        raise NotImplementedError

    @abstractmethod
    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Renvoie les positions actives (si applicable)."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Exchange name={self.name}>"
