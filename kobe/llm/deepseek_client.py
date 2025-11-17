import os, json, pathlib
import httpx

PRICING_IN  = float(os.getenv("DEEPSEEK_INPUT_EUR_PER_MTOK", "0.5"))
PRICING_OUT = float(os.getenv("DEEPSEEK_OUTPUT_EUR_PER_MTOK","1.0"))
BUDGET_EUR  = float(os.getenv("DEEPSEEK_BUDGET_EUR", "5"))  # défaut aligné SOP V4
MODEL       = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
API_KEY     = os.getenv("DEEPSEEK_API_KEY")
BASE_URL    = "https://api.deepseek.com"

BILLING = pathlib.Path("logs/deepseek_billing.json")
BILLING.parent.mkdir(parents=True, exist_ok=True)

def _load_bill():
    if BILLING.exists():
        try:
            return json.loads(BILLING.read_text())
        except:
            pass
    return {"eur_spent": 0.0, "calls": 0}

def _save_bill(d):
    BILLING.write_text(json.dumps(d, indent=2))

def _est_cost(in_tok, out_tok):
    return (in_tok/1000.0)*PRICING_IN + (out_tok/1000.0)*PRICING_OUT

def _load_envfile():
    # charge .secrets/kobe/deepseek.env si présent
    p = ".secrets/kobe/deepseek.env"
    if os.path.exists(p):
        for line in open(p):
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: 
                continue
            k,v=line.split("=",1); os.environ[k]=v

def chat_complete_json(prompt: str, max_tokens: int = 256, temperature: float = 0.2):
    # charge secrets tardivement pour usage CLI direct
    _load_envfile()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    model   = os.getenv("DEEPSEEK_MODEL", MODEL)

    # recharge dynamiquement le pricing et le budget après chargement du .env
    global PRICING_IN, PRICING_OUT, BUDGET_EUR
    try:
        PRICING_IN = float(os.getenv("DEEPSEEK_INPUT_EUR_PER_MTOK", str(PRICING_IN)))
    except Exception:
        pass
    try:
        PRICING_OUT = float(os.getenv("DEEPSEEK_OUTPUT_EUR_PER_MTOK", str(PRICING_OUT)))
    except Exception:
        pass
    try:
        BUDGET_EUR = float(os.getenv("DEEPSEEK_BUDGET_EUR", str(BUDGET_EUR)))
    except Exception:
        pass

    if not api_key:
        return (False, {"error":"missing_api_key"})

    # Estimation conservative avant appel (garde-fou)
    approx_in = min(len(prompt)//4, 4096)  # heuristique
    est_cost  = _est_cost(approx_in, max_tokens)
    bill = _load_bill()
    if bill["eur_spent"] + est_cost > BUDGET_EUR:
        return (False, {
            "error":"budget_block",
            "eur_spent_total": bill["eur_spent"],
            "eur_est_next": round(est_cost, 4),
            "budget_eur": BUDGET_EUR
        })

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json", "User-Agent":"KobeV3/1.0"}
    payload = {
        "model": model,
        "messages": [
            {"role":"system","content":"Réponds UNIQUEMENT en JSON valide."},
            {"role":"user","content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }

    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
            # si 402 / 401 / 4xx -> renvoyer erreur propre
            if r.status_code >= 400:
                try:
                    err = r.json()
                except Exception:
                    err = {"error":{"message":r.text or "HTTP error", "code":r.status_code}}
                return (False, {"error":"api_error","status": r.status_code, "details": err})
            data = r.json()
    except httpx.HTTPError as e:
        return (False, {"error":"network_error","details": str(e)})

    # Extraction message + usage
    text = (data.get("choices") or [{}])[0].get("message",{}).get("content","").strip()
    usage = data.get("usage", {}) or {}
    in_tok  = int(usage.get("prompt_tokens", approx_in))
    out_tok = int(usage.get("completion_tokens", max_tokens//2))
    cost = _est_cost(in_tok, out_tok)

    # Mise à jour billing seulement si succès
    bill["eur_spent"] += cost
    bill["calls"]     += 1
    _save_bill(bill)

    return (True, {"text": text, "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok, "eur_cost": round(cost,6), "eur_spent_total": round(bill["eur_spent"],6)}})
