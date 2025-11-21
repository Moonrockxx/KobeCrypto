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

    def execute_order_plan(self, plan: dict):
        """Exécuter un plan d'ordres construit par build_order_plan().

        Cette méthode est ADDITIVE par rapport à create_order(): elle n'en modifie
        pas le comportement. Elle prend un plan déjà validé (qty_rounded,
        entry/take_profit/stop_loss) et tente d'envoyer les ordres correspondants
        sur l'API spot Binance.

        - Si le plan est invalide (valid=False, qty_rounded<=0, symbol/side manquant),
          on journalise et on retourne une erreur sans appel réseau.
        - Kill-switch: on réapplique la même logique de limite journalière que
          create_order() avant de lancer l'ordre d'entrée.
        - On suppose un flux LONG classique (side=BUY) : les ordres de sortie
          (TP/SL) sont des SELL de la même quantité. Pour side=SELL, la méthode
          utilise l'inverse (BUY) pour la clôture.
        """
        ts = int(time.time() * 1000)

        symbol = plan.get("symbol")
        side = plan.get("side")
        qty = plan.get("qty_rounded")
        is_valid = plan.get("valid", False)

        # Validation minimale du plan reçu.
        if not is_valid or not symbol or not side or qty is None:
            ev = {
                "ts": ts,
                "symbol": symbol,
                "side": side,
                "qty_rounded": float(qty) if qty is not None else None,
                "status": "plan_invalid",
                "reason": "missing_fields_or_not_valid",
            }
            _log_executor_event(ev)
            return {
                "error": "invalid_plan",
                "message": "order plan is invalid or incomplete",
                "event": ev,
            }

        try:
            qty_float = float(qty)
        except (TypeError, ValueError):
            qty_float = 0.0

        if qty_float <= 0:
            ev = {
                "ts": ts,
                "symbol": symbol,
                "side": side,
                "qty_rounded": qty_float,
                "status": "plan_invalid",
                "reason": "non_positive_quantity",
            }
            _log_executor_event(ev)
            return {
                "error": "invalid_plan",
                "message": "non-positive quantity in order plan",
                "event": ev,
            }

        # Kill-switch journalier basé sur la perte en EUR (copie de create_order).
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

        if max_daily_loss > 0 and current_daily_loss <= -max_daily_loss:
            ev = {
                "ts": ts,
                "symbol": symbol,
                "side": side,
                "qty_rounded": qty_float,
                "status": "kill_switch_blocked_plan",
                "max_daily_loss_eur": max_daily_loss,
                "current_daily_loss_eur": current_daily_loss,
            }
            _log_executor_event(ev)
            return {
                "error": "kill_switch",
                "message": "Daily loss limit exceeded, refusing to execute order plan.",
                "event": ev,
            }

        # Construction des ordres d'après le plan.
        orders_resp: dict[str, object] = {
            "entry": None,
            "take_profit": None,
            "stop_loss": None,
        }

        # Ordre d'entrée (type par défaut = plan["order_type"] ou MARKET).
        entry_info = plan.get("entry") or {}
        order_type = entry_info.get("type", plan.get("order_type", "MARKET"))

        entry_params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": qty_float,
        }

        # Pour un LIMIT d'entrée, on utilise le prix d'entry du plan.
        if order_type == "LIMIT":
            price = entry_info.get("price")
            if price is not None:
                try:
                    entry_params["price"] = float(price)
                    entry_params["timeInForce"] = "GTC"
                except (TypeError, ValueError):
                    # Si le prix est invalide, on laisse Binance répondre une erreur.
                    pass

        resp_entry = self._signed_post("/api/v3/order", entry_params)
        ev_entry = {
            "ts": ts,
            "kind": "entry",
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "qty_rounded": qty_float,
            "params": entry_params,
            "response": resp_entry,
        }
        _log_executor_event(ev_entry)
        orders_resp["entry"] = resp_entry

        # Pour les ordres de sortie, on inverse le side (BUY → SELL, SELL → BUY).
        side_upper = str(side).upper()
        close_side = "SELL" if side_upper == "BUY" else "BUY"

        # Take-profit : LIMIT @ price, quantité complète.
        tp_info = plan.get("take_profit")
        if tp_info is not None:
            tp_price = tp_info.get("price")
            tp_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "LIMIT",
                "quantity": qty_float,
            }
            try:
                if tp_price is not None:
                    tp_params["price"] = float(tp_price)
                    tp_params["timeInForce"] = "GTC"
            except (TypeError, ValueError):
                # On laisse Binance renvoyer une erreur si le prix est invalide.
                pass

            resp_tp = self._signed_post("/api/v3/order", tp_params)
            ev_tp = {
                "ts": ts,
                "kind": "take_profit",
                "symbol": symbol,
                "side": close_side,
                "qty_rounded": qty_float,
                "params": tp_params,
                "response": resp_tp,
            }
            _log_executor_event(ev_tp)
            orders_resp["take_profit"] = resp_tp

        # Stop-loss : STOP_LOSS_LIMIT @ price/stopPrice, quantité complète.
        sl_info = plan.get("stop_loss")
        if sl_info is not None:
            sl_price = sl_info.get("price")
            sl_params = {
                "symbol": symbol,
                "side": close_side,
                "type": "STOP_LOSS_LIMIT",
                "quantity": qty_float,
            }
            try:
                if sl_price is not None:
                    price_val = float(sl_price)
                    sl_params["price"] = price_val
                    sl_params["stopPrice"] = price_val
                    sl_params["timeInForce"] = "GTC"
            except (TypeError, ValueError):
                # Même logique: Binance renverra une erreur si le prix est invalide.
                pass

            resp_sl = self._signed_post("/api/v3/order", sl_params)
            ev_sl = {
                "ts": ts,
                "kind": "stop_loss",
                "symbol": symbol,
                "side": close_side,
                "qty_rounded": qty_float,
                "params": sl_params,
                "response": resp_sl,
            }
            _log_executor_event(ev_sl)
            orders_resp["stop_loss"] = resp_sl

        return {
            "plan": plan,
            "orders": orders_resp,
        }

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
