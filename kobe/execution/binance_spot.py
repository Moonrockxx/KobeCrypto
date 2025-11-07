import os, hmac, time, hashlib, urllib.parse, urllib.request, json
class BinanceSpot:
    """
    Squelette dry-run: expose check_account() pour valider la signature
    si (et seulement si) les clés sont présentes dans l'env; sinon no-op.
    """
    def __init__(self, key=None, secret=None):
        self.key = key or os.getenv("BINANCE_API_KEY", "")
        self.secret = secret or os.getenv("BINANCE_API_SECRET", "")
        self.base = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")

    def _signed_get(self, path, params=None, timeout=8):
        if not self.key or not self.secret:
            print("ℹ️ BinanceSpot: aucune clé détectée — mode dry.")
            return None
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base}{path}?{query}&signature={sig}"
        req = urllib.request.Request(url, headers={"X-MBX-APIKEY": self.key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def check_account(self):
        # Appel SIGNED simple pour vérifier permissions (si clés set)
        return self._signed_get("/api/v3/account", {})
