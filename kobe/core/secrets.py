from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import yaml

class SecretsError(Exception):
    """Erreur de chargement ou de validation des secrets."""
    pass

# --- Chargement combiné .env + config.yaml ---
def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Charge le fichier YAML principal."""
    p = Path(path)
    if not p.exists():
        raise SecretsError(f"config.yaml introuvable ({p})")
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise SecretsError(f"Erreur de lecture YAML: {e}")

def load_env(dotenv_path: str = ".env") -> Dict[str, str]:
    """Charge les variables d'environnement depuis .env sans écraser l'existant."""
    env_path = Path(dotenv_path)
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    return dict(os.environ)

def merge_env_config(env: Dict[str, str], config: Dict[str, Any]) -> Dict[str, Any]:
    """Fusionne .env et config.yaml (priorité à l'env)."""
    merged = {**config}
    merged["_env"] = {}
    for k, v in env.items():
        merged["_env"][k] = v
    return merged

# --- Modes d'exécution ---
VALID_MODES = {"paper", "testnet", "live"}

def get_mode(cfg: Dict[str, Any]) -> str:
    """Détermine le mode actif (paper/testnet/live)."""
    env = cfg.get("_env", {})
    mode_env = env.get("MODE") or env.get("KOBE_MODE")
    mode_cfg = cfg.get("mode") or "paper"
    mode = str(mode_env or mode_cfg).lower().strip()
    if mode not in VALID_MODES:
        raise SecretsError(f"Mode invalide: {mode}")
    if mode == "live" and not env.get("ALLOW_LIVE"):
        raise SecretsError("Mode live interdit sans variable ALLOW_LIVE=1 dans l'environnement.")
    return mode

# --- Clés Exchange ---
def get_exchange_keys(cfg: Dict[str, Any], exchange: str) -> Dict[str, str]:
    """Récupère les clés d'API depuis l'environnement ou le fichier config."""
    env = cfg.get("_env", {})
    prefix = exchange.upper()
    key = env.get(f"{prefix}_KEY") or ""
    secret = env.get(f"{prefix}_SECRET") or ""
    testnet = bool(int(env.get(f"{prefix}_TESTNET", "0")))
    if not key or not secret:
        print(f"⚠️  Clés manquantes pour {exchange} — mode paper/testnet uniquement.")
    return {"key": key, "secret": secret, "testnet": testnet}

# --- Health courte ---
def secrets_summary(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Résumé succinct pour CLI."""
    env = cfg.get("_env", {})
    summary = {
        "mode": get_mode(cfg),
        "has_env": bool(env),
        "has_binance_keys": bool(env.get("BINANCE_KEY")) and bool(env.get("BINANCE_SECRET")),
        "allow_live": env.get("ALLOW_LIVE") == "1",
    }
    return summary

if __name__ == "__main__":
    env = load_env()
    cfg = load_config()
    merged = merge_env_config(env, cfg)
    print("✅ Secrets chargés :", secrets_summary(merged))
