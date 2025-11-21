import os, hmac, time, hashlib, urllib.parse, urllib.request, urllib.error, json
from decimal import Decimal, ROUND_DOWN

def _log_executor_event(event: dict, path: str | None = None) -> None:
    """
    Journalisation minimaliste des appels exécuteur dans logs/executor.jsonl.

    - path: permet de surcharger le chemin pour des tests si besoin.
    - en cas d'erreur de fichier, on ne fait qu'ignorer (pas de crash exécuteur).
    """
    try:
        log_path = path or os.getenv("KOBE_EXECUTOR_LOG", "logs/executor.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        # On ne doit jamais faire planter l'exécuteur à cause de la journalisation
        return

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

    def build_order_plan(self, symbol, side, quantity, entry_price, take_price=None, stop_price=None, order_type="MARKET"):
        """
        Construire un plan d'ordres (entry/TP/SL) sans exécuter quoi que ce soit.

        Cette méthode est purement déclarative: elle applique la même logique
        de normalisation de quantité que create_order(), puis retourne une
        structure décrivant les 3 blocs d'ordres:
          - entry: ordre d'entrée (actuellement type=order_type, ex: MARKET)
          - take_profit: LIMIT @ take_price (si fourni)
          - stop_loss: STOP_LIMIT @ stop_price (si fourni)
        """
        # Normalisation de la quantité pour respecter le LOT_SIZE (stepSize).
        # On réutilise la même logique que dans create_order, en la dupliquant
        # ici pour ne pas dépendre d'effets de bord réseau.
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

        qty_rounded = qty_dec.quantize(step, rounding=ROUND_DOWN)

        # Si après arrondi la quantité est <= 0, on signale un plan invalide.
        if qty_rounded <= 0:
            return {
                "symbol": symbol,
                "side": side,
                "qty_original": float(quantity),
                "qty_rounded": float(qty_rounded),
                "valid": False,
                "reason": "too_small",
            }

        plan = {
            "symbol": symbol,
            "side": side,
            "qty_original": float(quantity),
            "qty_rounded": float(qty_rounded),
            "order_type": order_type,
            "entry": {
                "type": order_type,
                "price": float(entry_price),
            },
            "take_profit": None,
            "stop_loss": None,
        }

        if take_price is not None:
            plan["take_profit"] = {
                "type": "LIMIT",
                "price": float(take_price),
            }

        if stop_price is not None:
            plan["stop_loss"] = {
                "type": "STOP_LIMIT",
                "price": float(stop_price),
            }

        plan["valid"] = True
        return plan

    def create_order(self, symbol, side, quantity, order_type="MARKET", take_price=None, stop_price=None):
        """
        Exécuter un ordre spot réel:
          side: BUY ou SELL
          order_type: MARKET (par défaut)
          quantity: quantité base (ex: 0.01 BTC)
        """
        # Kill-switch journalier basé sur la perte en EUR.
        #
        # MAX_DAILY_LOSS_EUR : limite journalière (en EUR) configurée via l'env
        # KOBE_DAILY_LOSS_EUR : perte courante du jour (en EUR, valeur négative)
        max_daily_loss_env = os.getenv("MAX_DAILY_LOSS_EUR")
        try:
            max_daily_loss = float(max_daily_loss_env) if max_daily_loss_env else 0.0
        except ValueError:
            max_daily_loss = 0.0

        current_daily_loss_env = os.getenv("KOBE_DAILY_LOSS_EUR")
        try:
            current_daily_loss = float(current_daily_loss_env) if current_daily_loss_env else 0.0
        except ValueError:
            current_daily_loss = 0.0

        # Si la perte courante est <= -MAX_DAILY_LOSS_EUR, on bloque tout nouvel ordre.
        if max_daily_loss > 0 and current_daily_loss <= -max_daily_loss:
            ev = {
                "ts": int(time.time() * 1000),
                "symbol": symbol,
                "side": side,
                "qty_original": float(quantity),
                "order_type": order_type,
                "status": "kill_switch_blocked",
                "max_daily_loss_eur": max_daily_loss,
                "current_daily_loss_eur": current_daily_loss,
            }
            _log_executor_event(ev)
            return {
                "error": "kill_switch",
                "message": "Daily loss limit exceeded, refusing new orders.",
            }

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
            ev = {
                "ts": int(time.time() * 1000),
                "symbol": symbol,
                "side": side,
                "qty_original": float(quantity),
                "qty_rounded": float(qty_rounded),
                "order_type": order_type,
                "status": "too_small",
            }
            _log_executor_event(ev)
            return {"error": "too_small", "message": f"quantity {quantity} too small after lot-size rounding"}

        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(qty_rounded),
        }

        resp = self._signed_post("/api/v3/order", params)

        ev = {
            "ts": int(time.time() * 1000),
            "symbol": symbol,
            "side": side,
            "qty_original": float(quantity),
            "qty_rounded": float(qty_rounded),
            "order_type": order_type,
            "take_price": float(take_price) if take_price is not None else None,
            "stop_price": float(stop_price) if stop_price is not None else None,
            "params": params,
            "response": resp,
        }
        _log_executor_event(ev)

        return resp
