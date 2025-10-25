from __future__ import annotations
import time, random
from typing import Any, Dict, List, Optional
import requests

from kobe.core.adapter.base import Exchange, ExchangeError, NetworkError


class BinanceAdapter(Exchange):
    """
    Implémentation simplifiée (mock/testnet) de l'interface Exchange pour Binance.
    Aucun appel réel requis pour les tests unitaires : les retours sont simulés.
    """

    name = "Binance"
    supports_testnet = True
    BASE_URL = "https://testnet.binance.vision/api/v3"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        self.api_key = api_key or "demo_key"
        self.api_secret = api_secret or "demo_secret"
        self.testnet = testnet

    # --- utils internes ---
    def _simulate_delay(self):
        time.sleep(0.05)

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Appel GET basique (mockable)."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params or {}, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise NetworkError(str(e))

    # --- implémentations Exchange ---
    def load_markets(self) -> Dict[str, Any]:
        """Charge la liste des paires depuis le testnet (ou mock fallback)."""
        try:
            data = self._get("/exchangeInfo")
            return {s["symbol"]: s for s in data.get("symbols", [])}
        except Exception:
            # fallback mock
            return {
                "BTCUSDT": {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT"},
                "ETHUSDT": {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT"},
            }

    def get_balance(self, asset: str) -> float:
        """Retourne un solde fictif constant."""
        self._simulate_delay()
        mock_balances = {"BTC": 0.25, "USDT": 10000.0, "ETH": 1.5}
        return mock_balances.get(asset.upper(), 0.0)

    def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        qty: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Crée un ordre simulé (pas d'appel réel)."""
        self._simulate_delay()
        if qty <= 0:
            raise ExchangeError("Quantité invalide.")
        order_id = str(random.randint(1000000, 9999999))
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side.lower(),
            "type": type.lower(),
            "price": price or 0.0,
            "qty": qty,
            "status": "FILLED",
            "timestamp": int(time.time() * 1000),
        }

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        self._simulate_delay()
        return {"id": order_id, "symbol": symbol, "status": "CANCELED"}

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        self._simulate_delay()
        return []  # aucun ordre ouvert dans mock

    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        self._simulate_delay()
        return [{"symbol": "BTCUSDT", "positionAmt": 0.0, "entryPrice": 0.0}]


# --- test manuel ---
if __name__ == "__main__":
    ex = BinanceAdapter()
    mkts = ex.load_markets()
    print("✅ Markets:", list(mkts.keys())[:2])
    print("✅ Balance BTC:", ex.get_balance("BTC"))
    o = ex.create_order("BTCUSDT", "buy", "market", 0.001)
    print("✅ Order:", o)
