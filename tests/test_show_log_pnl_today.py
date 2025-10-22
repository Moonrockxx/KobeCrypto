import os, json, tempfile, datetime as dt
from kobe.cli_show_log import pnl_today

def test_pnl_today_sum_only_today_events():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "journal.jsonl")
        # Evénement d'hier (ne doit PAS compter)
        y = (dt.datetime.utcnow() - dt.timedelta(days=1)).replace(microsecond=0).isoformat() + "Z"
        # Evénements d'aujourd'hui (doivent compter)
        t1 = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        t2 = t1
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": y, "event":"paper_close","pnl": 5.0})+"\n")
            f.write(json.dumps({"ts": t1,"event":"paper_close","pnl": 20.0})+"\n")
            f.write(json.dumps({"ts": t2,"event":"paper_close","pnl":-3.5})+"\n")
            f.write(json.dumps({"ts": t2,"event":"signal"})+"\n")  # ignoré
        total, count = pnl_today(td)
        assert count == 2
        assert abs(total - (20.0 - 3.5)) < 1e-9
