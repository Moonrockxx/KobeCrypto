import json, csv
from pathlib import Path
from kobe.signals.proposal import Proposal
from kobe.core.journal import log_proposal, LOG_DIR, CSV_PATH, JSONL_PATH

def test_log_proposal_creates_files(tmp_path, monkeypatch):
    # Redirige les logs vers un dossier temporaire
    monkeypatch.setattr("kobe.core.journal.LOG_DIR", tmp_path)
    monkeypatch.setattr("kobe.core.journal.CSV_PATH", tmp_path / "journal.csv")
    monkeypatch.setattr("kobe.core.journal.JSONL_PATH", tmp_path / "journal.jsonl")

    p = Proposal(
        symbol="BTCUSDT",
        side="long",
        entry=68000.0,
        stop=67200.0,
        take=69600.0,
        risk_pct=0.25,
        size_pct=5.0,
        reasons=["Breakout", "Funding neutre", "Corrélation SPX"],
    )

    log_proposal(p.model_dump())

    # Vérifie existence des fichiers
    assert (tmp_path / "journal.csv").exists()
    assert (tmp_path / "journal.jsonl").exists()

    # Vérifie contenu JSONL
    data_json = [json.loads(l) for l in (tmp_path / "journal.jsonl").read_text().splitlines()]
    assert data_json and isinstance(data_json[0], dict)
    assert "symbol" in data_json[0]
    assert data_json[0]["symbol"] == "BTCUSDT"

    # Vérifie contenu CSV
    with open(tmp_path / "journal.csv", newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 1
    row = reader[0]
    assert row["symbol"] == "BTCUSDT"
    assert row["side"] == "long"
    assert float(row["risk_pct"]) == 0.25
