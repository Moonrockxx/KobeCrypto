#!/usr/bin/env python3
"""
DEMO v0_breakout
- 1 seul signal/jour (clamp par date locale)
- 3 raisons explicatives
- stop obligatoire
- risk/trade 0,5% (paper only)
"""
from datetime import date
from pathlib import Path
import json, hashlib

STATE_PATH = Path.home() / ".kobe_demo_state.json"

def already_emitted_today() -> bool:
    try:
        st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return st.get("last_date") == date.today().isoformat()
    except Exception:
        return False

def persist_today():
    STATE_PATH.write_text(json.dumps({"last_date": date.today().isoformat()}), encoding="utf-8")

def main():
    if already_emitted_today():
        print("None")
        return

    # Choix d'un symbole du jour (déterministe) pour la démo
    today = date.today().isoformat()
    assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    idx = int(hashlib.sha256(today.encode()).hexdigest(), 16) % len(assets)
    symbol = assets[idx]

    # Prix "maquettes" plausibles pour la démo (aucun ordre réel)
    bases = {"BTCUSDT": 67000.0, "ETHUSDT": 3500.0, "SOLUSDT": 150.0}
    base = bases[symbol]
    entry = round(base, 2)
    stop = round(base * 0.985, 2)  # ~1,5% sous l'entrée (démo)

    signal = {
        "symbol": symbol,
        "side": "long",
        "entry": entry,
        "stop": stop,
        "risk_pct": 0.5,  # 0,5 %
        "reasons": [
            "Contraction de volatilité (ATR en baisse) — démo",
            "Cassure du plus haut récent — démo",
            "Volume relatif >1.5× sur la bougie de cassure — démo",
        ],
        "note": "DEMO — ne pas trader; valeurs fictives pour valider le chemin CLI.",
    }
    print(json.dumps(signal, ensure_ascii=False))
    persist_today()

if __name__ == "__main__":
    main()
