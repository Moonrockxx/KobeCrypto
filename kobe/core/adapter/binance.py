from __future__ import annotations
import ccxt
from typing import Any, Dict, List, Optional

from kobe.core.adapter.base import (
    Exchange,
    ExchangeError,
    AuthenticationError,
    NetworkError,
)

class BinanceAdapter(Exchange):
    """
    Implémentation de l'interface Exchange pour Binance utilisant CCXT.
    Gère automatiquement la connexion, les signatures, le Rate Limiting et les erreurs réseau.
    """

    name = "Binance"
    supports_testnet = True

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        self.testnet = testnet
        
        # Initialisation du client CCXT pour Binance
        self.client = ccxt.binance({
            'apiKey': api_key or '',
            'secret': api_secret or '',
            'enableRateLimit': True,  # Sécurité pour ne pas se faire bannir par Binance
            'options': {
                'defaultType': 'spot' # Le bot opère sur le marché Spot
            }
        })
        
        if self.testnet:
            self.client.set_sandbox_mode(True)

    def _format_symbol(self, symbol: str) -> str:
        """Convertit 'BTCUSDC' en format standard CCXT 'BTC/USDC'."""
        if "/" not in symbol and len(symbol) > 4:
            # Séparation basique (adaptable selon les paires)
            if symbol.endswith("USDC"):
                return symbol.replace("USDC", "/USDC")
            elif symbol.endswith("USDT"):
                return symbol.replace("USDT", "/USDT")
        return symbol

    def _handle_error(self, e: Exception) -> None:
        """Traduit les exceptions CCXT vers les exceptions internes de base.py."""
        if isinstance(e, ccxt.AuthenticationError):
            raise AuthenticationError(f"Problème d'authentification Binance: {str(e)}")
        elif isinstance(e, ccxt.NetworkError):
            raise NetworkError(f"Erreur réseau Binance: {str(e)}")
        elif isinstance(e, ccxt.BaseError):
            raise ExchangeError(f"Erreur d'exécution Binance: {str(e)}")
        else:
            raise ExchangeError(f"Erreur inattendue: {str(e)}")

    def load_markets(self, quote_filter: Optional[str] = "USDC", max_markets: Optional[int] = None) -> Dict[str, Any]:
        try:
            markets = self.client.load_markets()
            result = {}
            for unified_symbol, market_data in markets.items():
                # On recrée le format interne sans slash (ex: 'BTC/USDC' -> 'BTCUSDC')
                internal_symbol = unified_symbol.replace("/", "")
                
                if quote_filter and market_data.get('quote') != quote_filter.upper():
                    continue
                
                result[internal_symbol] = market_data
            
            if isinstance(max_markets, int) and max_markets > 0:
                items = list(result.items())[:max_markets]
                result = {k: v for k, v in items}
                
            return result
        except Exception as e:
            self._handle_error(e)

    def get_balance(self, asset: str) -> float:
        try:
            # fetch_free_balance renvoie le solde réellement disponible (non bloqué dans un ordre)
            balance = self.client.fetch_free_balance()
            return float(balance.get(asset.upper(), 0.0))
        except Exception as e:
            self._handle_error(e)

    def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        qty: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if qty <= 0:
            raise ExchangeError("Quantité invalide. Elle doit être supérieure à 0.")
        
        ccxt_symbol = self._format_symbol(symbol)
        
        try:
            return self.client.create_order(
                symbol=ccxt_symbol,
                type=type.lower(),
                side=side.lower(),
                amount=qty,
                price=price,
                params=params or {}
            )
        except Exception as e:
            self._handle_error(e)

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        ccxt_symbol = self._format_symbol(symbol)
        try:
            return self.client.cancel_order(order_id, ccxt_symbol)
        except Exception as e:
            self._handle_error(e)

    def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        ccxt_symbol = self._format_symbol(symbol) if symbol else None
        try:
            return self.client.fetch_open_orders(ccxt_symbol)
        except Exception as e:
            self._handle_error(e)

    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        # En Spot, il n'y a pas de concept de "Position" au sens des Futures.
        # On renvoie une liste vide pour respecter la signature de base.py
        return []

# --- test manuel ---
if __name__ == "__main__":
    # Test basique sans clés API (mode public)
    ex = BinanceAdapter(testnet=False)
    
    print("Chargement des marchés (filtré sur USDC)...")
    mkts = ex.load_markets(quote_filter="USDC", max_markets=5)
    print("✅ Marchés trouvés :", list(mkts.keys()))
    
    # Sans clés API, la balance va générer une AuthenticationError (ce qui est normal et prouve que la sécurité fonctionne)
    try:
        balance = ex.get_balance("USDC")
        print("Balance:", balance)
    except AuthenticationError as e:
        print("✅ Sécurité confirmée (Authentification requise pour lire le solde) :", str(e))