import json
import pytest

from kobe.llm import deepseek_client


def test_chat_complete_missing_api_key(monkeypatch):
    """Sans API key, le client doit renvoyer une erreur 'missing_api_key' sans appel réseau."""

    # On neutralise le chargement éventuel d'un .env local
    def fake_load_envfile():
        return None

    monkeypatch.setattr("kobe.llm.deepseek_client._load_envfile", fake_load_envfile)

    # On s'assure qu'aucune API key n'est visible
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    ok, resp = deepseek_client.chat_complete_json("test prompt", max_tokens=64)

    assert ok is False
    assert isinstance(resp, dict)
    assert resp.get("error") == "missing_api_key"


def test_chat_complete_budget_guard_blocks(monkeypatch):
    """Si le budget est ridiculement bas, le garde-fou budget doit bloquer AVANT l'appel HTTP."""

    def fake_load_envfile():
        return None

    monkeypatch.setattr("kobe.llm.deepseek_client._load_envfile", fake_load_envfile)

    # On force un budget très faible et un pricing simple
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-test")
    monkeypatch.setenv("DEEPSEEK_BUDGET_EUR", "0.0001")
    monkeypatch.setenv("DEEPSEEK_INPUT_EUR_PER_MTOK", "1.0")
    monkeypatch.setenv("DEEPSEEK_OUTPUT_EUR_PER_MTOK", "1.0")

    # Prompt suffisamment long pour que est_cost dépasse largement le budget
    prompt = "X" * 2000

    ok, resp = deepseek_client.chat_complete_json(prompt, max_tokens=256)

    assert ok is False
    assert isinstance(resp, dict)
    assert resp.get("error") == "budget_block"
    assert "eur_est_next" in resp
    assert "budget_eur" in resp
