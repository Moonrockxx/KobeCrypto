import os, hmac, time, hashlib, urllib.parse, urllib.request, urllib.error, json
from decimal import Decimal, ROUND_DOWN

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
        # Normalisation de la quantité pour respecter le LOT_SIZE (stepSize).
        # On utilise le step défini dans la config (config.yaml: lot_step), avec
        # un fallback conservateur à 0.001 si absent.
        step_cfg = os.getenv("KOBE_LOT_STEP")
        try:
            from kobe.core.secrets import load_config
            cfg = load_config("config.yaml")
            step_val = cfg.get("lot_step", 0.001)
        except Exception:
            step_val = 0.001

        if step_cfg:
            try:
                step_val = float(step_cfg)
            except ValueError:
                pass

        step = Decimal(str(step_val))
        qty_dec = Decimal(str(quantity))

        # On arrondit toujours à l'inférieur pour ne jamais dépasser la taille calculée
        qty_rounded = qty_dec.quantize(step, rounding=ROUND_DOWN)

        # Sécurité: si après arrondi la quantité est <= 0, on ne tente pas l'ordre
        if qty_rounded <= 0:
            return {"error": "too_small", "message": f"quantity {quantity} too small after lot-size rounding"}

        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(qty_rounded),
        }
        return self._signed_post("/api/v3/order", params)
