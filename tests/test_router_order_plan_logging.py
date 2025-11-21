from kobe.core import router
from kobe.core.modes import Mode
from kobe.signals.proposal import Proposal

def test_router_builds_order_plan_in_live(monkeypatch):
    events = []

    # 1) On capture les événements au lieu d'écrire dans les fichiers
    def fake_append(evt):
        events.append(evt)

    monkeypatch.setattr(router, "_append_order", fake_append, raising=True)

    # 2) Forcer Mode.LIVE pour ce test
    def fake_current_mode(cfg):
        return Mode.LIVE

    monkeypatch.setattr(router, "current_mode", fake_current_mode, raising=True)

    # Éviter toute dépendance au fichier config.yaml pendant ce test
    def fake_load_config(path="config.yaml"):
        # On renvoie une config minimale ; on teste le routage, pas le fichier de config
        return {}

    monkeypatch.setattr(router, "load_config", fake_load_config, raising=True)

    # 3) Forcer une taille de position suffisante pour ne PAS tomber dans TOO_SMALL
    def fake_position_size(balance_usd, risk_pct, entry, stop, leverage=1.0):
        # Par ex. 0.05 BTC
        return 0.05

    monkeypatch.setattr(router, "position_size", fake_position_size, raising=True)

    # 4) Fake BinanceSpot : pas de réseau, pas de vrai compte
    class FakeBinanceSpot:
        def __init__(self, *args, **kwargs):
            pass

        def check_account(self):
            # Simule un solde confortable en USDC
            return {
                "balances": [
                    {"asset": "USDC", "free": "1000"}
                ]
            }

        def get_price(self, symbol):
            return {"symbol": symbol, "price": "68000.0"}

        def create_order(self, symbol, side, quantity, order_type="MARKET", take_price=None, stop_price=None):
            # Simule un ordre MARKET accepté
            return {"orderId": "12345", "status": "NEW", "symbol": symbol}

        def build_order_plan(self, symbol, side, quantity, entry_price, take_price=None, stop_price=None, order_type="MARKET"):
            # On renvoie un plan minimaliste ; on teste le routage, pas le détail du plan ici
            return {
                "symbol": symbol,
                "side": side,
                "qty": float(quantity),
                "entry_price": float(entry_price),
                "take_price": float(take_price) if take_price is not None else None,
                "stop_price": float(stop_price) if stop_price is not None else None,
                "order_type": order_type,
            }

    monkeypatch.setattr(router, "BinanceSpot", FakeBinanceSpot, raising=True)

    # 5) Proposal valide (>= 3 raisons)
    p = Proposal(
        symbol="BTCUSDC", side="long",
        entry=68000.0, stop=67200.0, take=69600.0,
        risk_pct=0.25, size_pct=5.0,
        reasons=[
            "test order plan",
            "validation build_order_plan",
            "router logging"
        ]
    )

    mode, evt = router.place_from_proposal(p, balance_usd=10_000.0, leverage=1.0)

    # 6) Vérifications
    assert mode == Mode.LIVE
    assert isinstance(evt, dict)

    # On doit avoir au moins un event 'order_plan_built'
    plan_events = [e for e in events if e.get("router_action") == "order_plan_built"]
    assert len(plan_events) == 1

    pe = plan_events[0]
    assert pe.get("status") == "PLAN_ONLY"
    assert pe.get("exchange") == "binance_spot"
    assert isinstance(pe.get("order_plan"), dict)
    assert pe["order_plan"]["symbol"] == "BTCUSDC"
