from __future__ import annotations
import argparse, json
from kobe.core.secrets import load_env, load_config, merge_env_config, get_mode, get_exchange_keys
from kobe.core.modes import current_mode, Mode
from kobe.core.adapter.binance import BinanceAdapter
from kobe.core.router import place_from_proposal
from kobe.signals.proposal import Proposal

OK = "✅"
KO = "❌"
WARN = "⚠️"

def run_health_v2() -> int:
    env = load_env()
    cfg = merge_env_config(env, load_config())
    mode = current_mode(cfg)
    keys = get_exchange_keys(cfg, "binance")

    print(f"\n🔍 KobeCrypto V2 Health Check\n{'='*35}")
    print(f"Mode actif: {mode.value.upper()}")

    if mode == Mode.LIVE:
        if not env.get("ALLOW_LIVE"):
            print(f"{KO} LIVE interdit (variable ALLOW_LIVE manquante).")
            return 1
        if not (keys['key'] and keys['secret']):
            print(f"{KO} LIVE sans clés d'API valides.")
            return 1
        print(f"{OK} LIVE autorisé et clés détectées.")
        return 0

    # Paper/testnet checks
    adapter_ok = False
    try:
        ex = BinanceAdapter(api_key=keys["key"], api_secret=keys["secret"], testnet=keys["testnet"])
        mkts = ex.load_markets(max_markets=5)
        adapter_ok = len(mkts) > 0
    except Exception as e:
        print(f"{KO} Erreur adapter: {e}")
        adapter_ok = False

    if adapter_ok:
        print(f"{OK} Adapter Binance opérationnel (mock/testnet).")
    else:
        print(f"{WARN} Adapter non accessible.")

    try:
        demo = Proposal(
            symbol="BTCUSDT", side="long",
            entry=68000, stop=67200, take=69600,
            risk_pct=0.25, size_pct=5.0,
            reasons=["A","B","C"]
        )
        mode2, evt = place_from_proposal(demo, balance_usd=10_000.0)
        print(f"{OK} Router OK: {mode2.value.upper()} — {evt['status']}")
    except Exception as e:
        print(f"{KO} Router erreur: {e}")
        return 1

    print(f"{OK} Health check V2 terminé sans erreur critique.\n")
    return 0

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="kobe health-v2", description="Health check avancé pour KobeCrypto V2.")
    return ap

def main(argv=None) -> int:
    ap = build_parser()
    ap.parse_args(argv)
    return run_health_v2()

if __name__ == "__main__":
    raise SystemExit(main())
