import os, hmac, time, hashlib, urllib.parse, urllib.request, urllib.error, json

class BinanceSpot:
    """
    Squelette dry-run: expose check_account() pour valider la signature
    si (et seulement si) les clés sont présentes dans l'env; sinon no-op.
    Variables attendues (si fournies):
      - BINANCE_API_KEY
      - BINANCE_API_SECRET
      - BINANCE_BASE_URL (optionnelle, défaut: https://api.binance.com)
    """
    def __init__(self, key=None, secret=None):
        self.key = (key or os.getenv("BINANCE_API_KEY", "")).strip()
        self.secret = (secret or os.getenv("BINANCE_API_SECRET", "")).strip()
        self.base = os.getenv("BINANCE_BASE_URL", "https://api.binance.com").rstrip("/")

    def _signed_get(self, path, params=None, timeout=8):
        # Mode dry si aucune clé: ne rien imprimer, laisser l'appelant décider.
        if not self.key or not self.secret:
            return None
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        req = urllib.request.Request(url, headers={"X-MBX-APIKEY": self.key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def check_account(self):
        """Appel SIGNED simple pour vérifier permissions (si clés set)."""
        return self._signed_get("/api/v3/account", {})

    def _signed_post(self, path, params=None, timeout=8):
        """POST signé simple (pour create_order)."""
        if not self.key or not self.secret:
            return None
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        req = urllib.request.Request(
            url,
            method="POST",
            headers={"X-MBX-APIKEY": self.key}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": e.code, "message": e.read().decode("utf-8")}
        except Exception as e:
            return {"error": "exception", "message": str(e)}

    def get_price(self, symbol: str):
        """Prix spot simple via /api/v3/ticker/price."""
        url = f"{self.base}/api/v3/ticker/price?symbol={symbol}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            return {"error": "exception", "message": str(e)}

    def create_order(self, symbol, side, quantity, order_type="MARKET"):
        """
        Exécuter un ordre spot réel:
          side: BUY ou SELL
          order_type: MARKET (par défaut)
          quantity: quantité base (ex: 0.01 BTC)
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        return self._signed_post("/api/v3/order", params)
