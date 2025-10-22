#!/usr/bin/env python3
from pathlib import Path
import yaml

def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else Path("config.yaml")
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data
