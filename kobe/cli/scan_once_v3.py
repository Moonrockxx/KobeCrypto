import os, json, argparse, datetime as dt, re
import httpx
from kobe.llm.deepseek_client import chat_complete_json

BINANCE_BASE = "https://api.binance.com"

def load_envfile(path):
    if os.path.exists(path):
        for line in open(path):
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1); os.environ[k]=v

def fetch_24h(symbol):
    url=f"{BINANCE_BASE}/api/v3/ticker/24hr"
    with httpx.Client(timeout=10.0) as c:
        r=c.get(url, params={"symbol":symbol})
        r.raise_for_status()
        d=r.json()
    return {
        "symbol": symbol,
        "price": float(d["lastPrice"]),
        "priceChangePercent": float(d["priceChangePercent"]),
        "highPrice": float(d["highPrice"]),
        "lowPrice": float(d["lowPrice"]),
        "volume": float(d["volume"])
    }

def precheck_setup(snapshot_item, min_abs_change=2.0, min_volume=1000.0):
    """
    Renvoie (ok, reason). ok=True si setup "mouvant" détecté.
    Heuristique simple : |variation 24h| >= min_abs_change ET volume >= min_volume.
    """
    chg = abs(snapshot_item["priceChangePercent"])
    vol = snapshot_item["volume"]
    if chg >= min_abs_change and vol >= min_volume:
        return True, f"abs_change={chg:.2f}% & volume={vol:.0f}>=min"
    return False, f"no_move(abs={chg:.2f}%, vol={vol:.0f})"

PROMPT_TMPL = """Tu es un assistant de trading. Retourne STRICTEMENT un JSON valide (sans texte autour).
Contrainte de risque: risk_pct ≤ 0.5 (par défaut 0.25).
Champs obligatoires: symbol, side in ["LONG","SHORT"], entry, stop, take_profit, risk_pct, leverage, reasons (array >=3).
Base toi sur ces données spot 24h (Binance):
{market_snapshot}
Réponds uniquement avec l'objet JSON demandé.
"""

def parse_json_strict(s: str):
    s = s.strip()
    m = re.match(r"```json\s*(.*?)\s*```", s, re.S)
    if m: s = m.group(1)
    return json.loads(s)

def build_telegram_text(proposal: dict):
    reasons = "\n".join([f"• {r}" for r in proposal.get("reasons", [])[:5]])
    return (
        "📈 *Kobe V3 — Proposition de trade*\n"
        f"• *Symbole* : {proposal['symbol']}\n"
        f"• *Sens* : {proposal['side']}\n"
        f"• *Entry* : {proposal['entry']}\n"
        f"• *Stop* : {proposal['stop']}\n"
        f"• *TP* : {proposal['take_profit']}\n"
        f"• *Risque* : {proposal.get('risk_pct', 0.25)}%\n"
        f"• *Leverage* : {proposal.get('leverage','1x')}\n"
        f"*Raisons :*\n{reasons or '—'}"
    )

def send_telegram(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_TO")
    if not token or not chat_id:
        return {"sent": False, "reason":"missing_env"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}
    with httpx.Client(timeout=10.0) as c:
        r=c.post(url, json=payload)
        try:
            j=r.json()
        except Exception:
            j={"ok":False,"status":r.status_code,"text":r.text[:200]}
    return {"sent": bool(j.get("ok")), "response": j}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT", help="Liste séparée par des virgules")
    ap.add_argument("--risk-pct", type=float, default=0.25)
    ap.add_argument("--dry", action="store_true", help="N'envoie pas Telegram")
    ap.add_argument("--env-telegram", default=".secrets/kobe/telegram.env")
    ap.add_argument("--min-abs-change", type=float, default=2.0, help="Seuil |variation 24h| en % pour considérer un setup")
    ap.add_argument("--min-volume", type=float, default=1000.0, help="Seuil volume 24h pour considérer un setup")
    args=ap.parse_args()

    load_envfile(args.env_telegram)
    now=dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()
    symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    snapshot=[]
    for sym in symbols:
        try:
            snapshot.append(fetch_24h(sym))
        except Exception as e:
            print(f"ERR fetch {sym}: {e}")

    # Pré-filtre setup
    candidates=[]
    reasons={}
    for it in snapshot:
        ok, reason = precheck_setup(it, args.min_abs_change, args.min_volume)
        reasons[it["symbol"]]=reason
        if ok:
            candidates.append(it)
    result = {"ts": now, "symbols": symbols, "precheck": reasons}

    if not candidates:
        # log NO_SETUP et sortir proprement
        result.update({"llm_ok": False, "status": "NO_SETUP"})
        with open("logs/signals.jsonl","a",encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False)+"\n")
        print("SCAN NO_SETUP")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("TELEGRAM SKIP (no setup)")
        return

    # sinon, appeler DeepSeek sur le snapshot de candidats uniquement
    market_snapshot=json.dumps(candidates, ensure_ascii=False, indent=2)
    # garde-fou risk
    risk = min(max(args.risk_pct, 0.05), 0.5)
    prompt = PROMPT_TMPL.format(market_snapshot=market_snapshot)
    ok, res = chat_complete_json(prompt, max_tokens=300)
    result.update({"llm_ok": ok, "raw": res})

    proposal = None
    if ok:
        try:
            proposal = parse_json_strict(res["text"])
            proposal["risk_pct"] = min(float(proposal.get("risk_pct", risk)), 0.5)
            result["proposal"]=proposal
        except Exception as e:
            result["llm_ok"]=False
            result["error"]="parse_json_failed"
            result["parse_exception"]=str(e)

    with open("logs/signals.jsonl","a",encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False)+"\n")

    print("SCAN OK" if result.get("llm_ok") else "SCAN ERR")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if proposal and not args.dry:
        text=build_telegram_text(proposal)
        t=send_telegram(text)
        if t.get("sent"):
            print("TELEGRAM OK")
        else:
            print("TELEGRAM SKIP/ERR:", t.get("reason") or t.get("response"))
    else:
        print("TELEGRAM SKIP (no proposal or --dry)")

if __name__=="__main__":
    main()
