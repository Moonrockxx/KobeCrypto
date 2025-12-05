from __future__ import annotations
import csv, json, time, os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from kobe.signals.proposal import Proposal, position_size
from kobe.core.risk import validate_proposal, RiskConfig
from kobe.core.executor import simulate_open
from kobe.core.secrets import load_env, load_config, merge_env_config, get_exchange_keys
from kobe.core.modes import current_mode, Mode
from kobe.execution.binance_spot import BinanceSpot
from kobe.core.adapter.binance import BinanceAdapter
from kobe.logs.execution_logger import ExecutionStatus, log_execution_result

# Journal des ordres (papier & testnet)
ORDERS_LOG_DIR = Path("logs")
ORDERS_CSV_PATH = ORDERS_LOG_DIR / "orders.csv"
ORDERS_JSONL_PATH = ORDERS_LOG_DIR / "orders.jsonl"

CSV_COLS = [
    "ts", "mode", "symbol", "side", "qty", "price",
    "router_action", "exchange", "order_id", "status",
    "risk_pct", "size_pct",
]

def _ensure_dirs():
    ORDERS_LOG_DIR.mkdir(parents=True, exist_ok=True)

def _ts_ms() -> int:
    return int(time.time() * 1000)

def _append_order(evt: Dict[str, Any]) -> None:
    _ensure_dirs()
    # JSONL
    with ORDERS_JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
    # CSV
    write_header = not ORDERS_CSV_PATH.exists()
    with ORDERS_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if write_header:
            w.writeheader()
        w.writerow({k: evt.get(k, "") for k in CSV_COLS})

def _build_evt(
    mode: Mode, p: Proposal, qty: float, price: float, action: str,
    exchange: str = "paper", order_id: str = "", status: str = "OK"
) -> Dict[str, Any]:
    return {
        "ts": _ts_ms(),
        "mode": mode.value,
        "symbol": p.symbol,
        "side": p.side,
        "qty": float(qty),
        "price": float(price),
        "router_action": action,
        "exchange": exchange,
        "order_id": order_id,
        "status": status,
        "risk_pct": float(p.risk_pct),
        "size_pct": float(p.size_pct),
    }

def _log_execution_from_evt(mode: Mode, p: Proposal, qty: float, evt: Dict[str, Any]) -> None:
    """Pont entre le journal 'orders' historique et le nouveau execution_logger.

    On:
    - lit evt["status"] / evt["router_action"] / evt["exchange"]
    - mappe ça vers un ExecutionStatus standardisé
    - pousse l'event dans logs/executions/*.jsonl

    Cette fonction NE DOIT JAMAIS faire planter le router: toute erreur est swallow.
    """
    try:
        raw_status = str(evt.get("status", "") or "")
        router_action = str(evt.get("router_action", "") or "")
        exchange = str(evt.get("exchange", "") or "unknown")

        upper = raw_status.upper()
        exec_status = ExecutionStatus.SUCCESS

        if upper == "TOO_SMALL":
            exec_status = ExecutionStatus.TOO_SMALL
        elif upper.startswith("ERR:") or "HTTP" in upper or "ERROR" in upper:
            exec_status = ExecutionStatus.EXCHANGE_ERROR
        elif upper.startswith("KILL_SWITCH"):
            exec_status = ExecutionStatus.REJECTED

        log_execution_result(
            symbol=p.symbol,
            side=p.side,
            exchange=exchange,
            mode=mode.value,
            status=exec_status,
            entry=p.entry,
            stop=p.stop,
            take=p.take,
            qty=qty,
            meta={
                "router_action": router_action,
                "raw_status": raw_status,
            },
        )
    except Exception:
        # On ne veut jamais casser la chaîne d'exécution
        return

def place_from_proposal(
    p: Proposal,
    *,
    balance_usd: float,
    leverage: float = 1.0,
    cfg_path: str = "config.yaml",
    risk_cfg: Optional[RiskConfig] = None,
) -> Tuple[Mode, Dict[str, Any]]:
    """
    Route une Proposal selon le mode courant :
    - PAPER  : simulate_open() (journal positions) + journal 'orders'
    - TESTNET: adapter.create_order() (mock Binance) + journal 'orders'
    - LIVE   : BinanceSpot.create_order() (réel, via API spot) + journal 'orders'
    Renvoie (mode, event_dict)
    """
    # Chargement config + mode
    env = load_env()
    cfg = merge_env_config(env, load_config(cfg_path))
    mode = current_mode(cfg)
    rcfg = risk_cfg or RiskConfig(
        max_trade_pct=cfg.get("risk", {}).get("max_trade_pct", 0.5),
        max_proposal_pct=cfg.get("risk", {}).get("max_proposal_pct", 0.25),
    )

    # Si on est en LIVE, on remplace le balance_usd simulé par le solde réel USDC du compte Binance.
    if mode == Mode.LIVE:
        try:
            ex_bal = BinanceSpot()
            acc = ex_bal.check_account()
            quote = env.get("QUOTE_ASSET", "USDC")
            free = None
            for b in acc.get("balances", []):
                if b.get("asset") == quote:
                    try:
                        free = float(b.get("free", "0") or 0.0)
                    except (TypeError, ValueError):
                        free = 0.0
                    break
            if free is not None and free > 0:
                balance_usd = free
        except Exception:
            # En cas d'erreur de récupération du solde, on garde balance_usd tel quel
            pass

    # Risk guard
    validate_proposal(p, rcfg, is_proposal=False)  # on exécute => comparer au plafond 'trade'

    # Sizing (qty en base)
    qty = position_size(balance_usd, p.risk_pct, p.entry, p.stop, leverage=leverage)

    # Garde de sécurité pour le mode LIVE :
    # si la quantité est trop petite, on n'envoie pas d'ordre à Binance
    # (les filtres LOT_SIZE/NOTIONAL rejetteraient l'ordre).
    if mode == Mode.LIVE and qty < 0.01:
        evt = _build_evt(
            mode,
            p,
            qty,
            price=p.entry,
            action="skip_too_small",
            exchange="binance_spot",
            order_id="",
            status="TOO_SMALL",
        )
        _append_order(evt)
        _log_execution_from_evt(mode, p, qty, evt)
        return mode, evt

    if mode == Mode.PAPER:
        # simulateur local
        open_evt = simulate_open(p, balance_usd=balance_usd, leverage=leverage)
        evt = _build_evt(mode, p, qty, price=p.entry, action="simulate_open", exchange="paper", status="OPENED")
        _append_order(evt)
        _log_execution_from_evt(mode, p, qty, evt)
        return mode, evt

    if mode == Mode.TESTNET:
        keys = get_exchange_keys(cfg, "binance")
        ex = BinanceAdapter(api_key=keys["key"], api_secret=keys["secret"], testnet=keys["testnet"])
        # on place un market (mock) — l’adapter renvoie FILLED
        side = "buy" if p.side == "long" else "sell"
        od = ex.create_order(p.symbol, side, "market", qty, price=None, params=None)
        evt = _build_evt(
            mode, p, qty, price=od.get("price", 0.0), action="create_order",
            exchange="binance", order_id=str(od.get("id", "")), status=str(od.get("status",""))
        )
        _append_order(evt)
        _log_execution_from_evt(mode, p, qty, evt)
        return mode, evt

    if mode == Mode.LIVE:
        # Exécution réelle via BinanceSpot (spot)
        ex = BinanceSpot()
        side = "BUY" if p.side == "long" else "SELL"

        # Feature flag : exécution du plan complet (entry + TP + SL).
        # Par défaut, on conserve le comportement historique (create_order).
        execute_plan_flag_raw = env.get("EXECUTE_ORDER_PLAN") or os.getenv("KOBE_EXECUTE_PLAN")
        execute_plan_flag = str(execute_plan_flag_raw).lower() in ("1", "true", "yes")

        if execute_plan_flag:
            # Prix spot actuel (fallback sur entry si indisponible)
            price_info = ex.get_price(p.symbol)
            if isinstance(price_info, dict) and "price" in price_info:
                try:
                    price = float(price_info["price"])
                except (TypeError, ValueError):
                    price = float(p.entry)
            else:
                price = float(p.entry)

            plan = None
            try:
                plan = ex.build_order_plan(
                    symbol=p.symbol,
                    side=side,
                    quantity=qty,
                    entry_price=p.entry,
                    take_price=p.take,
                    stop_price=p.stop,
                    order_type="MARKET",
                )
            except Exception:
                # En cas d'erreur de construction du plan, on journalise et on retombe
                # sur le chemin create_order() classique pour ne rien casser.
                plan_evt = {
                    "ts": _ts_ms(),
                    "mode": mode.value,
                    "symbol": p.symbol,
                    "side": p.side,
                    "qty": float(qty),
                    "price": float(p.entry),
                    "router_action": "order_plan_error",
                    "exchange": "binance_spot",
                    "order_id": "",
                    "status": "PLAN_ERROR",
                    "risk_pct": float(p.risk_pct),
                    "size_pct": float(p.size_pct),
                }
                _append_order(plan_evt)
                execute_plan_flag = False  # fallback

            if execute_plan_flag and plan and plan.get("valid"):
                # journal du plan avant exécution
                plan_evt = {
                    "ts": _ts_ms(),
                    "mode": mode.value,
                    "symbol": p.symbol,
                    "side": p.side,
                    "qty": float(qty),
                    "price": float(p.entry),
                    "router_action": "order_plan_execute",
                    "exchange": "binance_spot",
                    "order_id": "",
                    "status": "PLAN_EXECUTE",
                    "risk_pct": float(p.risk_pct),
                    "size_pct": float(p.size_pct),
                    "order_plan": plan,
                }
                _append_order(plan_evt)

                od = ex.execute_order_plan(plan)
                order_id = ""
                status = "UNKNOWN"
                action = "execute_order_plan"
                if isinstance(od, dict):
                    if od.get("error") == "kill_switch":
                        status = "KILL_SWITCH"
                        action = "kill_switch_blocked_plan"
                    elif "error" in od:
                        err = od.get("error")
                        msg = od.get("message", "")
                        status = f"ERR:{err}:{msg}"
                    else:
                        orders = od.get("orders") or {}
                        entry_resp = orders.get("entry") or {}
                        if isinstance(entry_resp, dict):
                            order_id = str(entry_resp.get("orderId", ""))
                            status = str(entry_resp.get("status", "NEW"))
                        else:
                            status = "OK"

                evt = _build_evt(
                    mode, p, qty, price=price, action=action,
                    exchange="binance_spot", order_id=order_id, status=status
                )
                _append_order(evt)
                _log_execution_from_evt(mode, p, qty, evt)
                return mode, evt

            # fallback si plan invalide ou erreur : on garde l'ancien chemin
            # (pas de return ici, on laisse tomber dans le bloc suivant)

        # Ancien comportement LIVE (par défaut / fallback)
        # Prix spot actuel (fallback sur entry si indisponible)
        price_info = ex.get_price(p.symbol)
        if isinstance(price_info, dict) and "price" in price_info:
            try:
                price = float(price_info["price"])
            except (TypeError, ValueError):
                price = float(p.entry)
        else:
            price = float(p.entry)

        od = ex.create_order(p.symbol, side, qty, take_price=p.take, stop_price=p.stop)

        # --- V4: construction du plan complet entry/TP/SL (sans exécution) ---
        try:
            plan = ex.build_order_plan(
                symbol=p.symbol,
                side=side,
                quantity=qty,
                entry_price=p.entry,
                take_price=p.take,
                stop_price=p.stop,
                order_type="MARKET",
            )
            plan_evt = {
                "ts": _ts_ms(),
                "mode": mode.value,
                "symbol": p.symbol,
                "side": p.side,
                "qty": float(qty),
                "price": float(p.entry),
                "router_action": "order_plan_built",
                "exchange": "binance_spot",
                "order_id": "",
                "status": "PLAN_ONLY",
                "risk_pct": float(p.risk_pct),
                "size_pct": float(p.size_pct),
                "order_plan": plan,
            }
            _append_order(plan_evt)
        except Exception:
            pass

        order_id = ""
        status = "UNKNOWN"
        action = "create_order"
        if isinstance(od, dict):
            # Cas particulier : kill-switch journalier activé côté exécuteur
            if od.get("error") == "kill_switch":
                status = "KILL_SWITCH"
                action = "kill_switch_blocked"
            elif "error" in od:
                err = od.get("error")
                msg = od.get("message", "")
                status = f"ERR:{err}:{msg}"
            else:
                order_id = str(od.get("orderId", ""))
                status = str(od.get("status", "NEW"))

        evt = _build_evt(
            mode, p, qty, price=price, action=action,
            exchange="binance_spot", order_id=order_id, status=status
        )
        _append_order(evt)
        _log_execution_from_evt(mode, p, qty, evt)
        return mode, evt

    raise RuntimeError("Mode inconnu pour place_from_proposal.")

if __name__ == "__main__":
    # Smoke test simple (PAPER par défaut si MODE non défini dans .env)
    from kobe.signals.proposal import Proposal
    demo = Proposal(
        symbol="BTCUSDC", side="long",
        entry=68000.0, stop=67200.0, take=69600.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=["A","B","C"]
    )
    m, e = place_from_proposal(demo, balance_usd=10_000.0, leverage=2.0)
    print("✅ Router:", m, e["status"])
