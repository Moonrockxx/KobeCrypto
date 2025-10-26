import yaml, math, time, urllib.parse, urllib.request, json

# --- Chargement config locale ---
cfg = yaml.safe_load(open("config.yaml","r",encoding="utf-8"))
tg = cfg.get("alerts",{}).get("trades",{}).get("telegram",{})
token = tg.get("bot_token"); chat_id = str(tg.get("chat_id"))
assert token and chat_id, "Token/chat_id Telegram manquants dans config.yaml"

# --- Paramètres demo (proposal prudente) ---
symbol = "BTCUSDT"
side = "long"  # long | short
equity = float(cfg.get("risk",{}).get("equity_usdt", 10000))  # default 10k si non présent
risk_pct = float(cfg.get("risk",{}).get("proposal_risk_pct", 0.25)) / 100.0  # 0.25% par défaut

# Prix demo cohérents (adapter au besoin)
entry  = 113000.0
stop   = 112100.0 if side=="long" else 113900.0
target = 114200.0 if side=="long" else 111800.0

# --- Sizing (risque en $ / distance stop) ---
risk_usd = equity * risk_pct
dist = abs(entry - stop)
qty = max(risk_usd / dist, 0.0001)  # qty en BTC si BTCUSDT (approx spot)
# Arrondi propre (3 décimales pour BTC)
qty = math.floor(qty*1000)/1000

# --- Confiance (démo statique 0–100) ---
confidence = 78

# --- Message format SOP ---
lines = [
  f"⚡ Signal {symbol} ({side})",
  f"Entrée : {entry:,.0f} $",
  f"Stop   : {stop:,.0f} $   Taille : {qty} BTC (≈ {risk_usd:,.0f} $ risque)",
  f"Objectif : {target:,.0f} $",
  f"Confiance : {confidence}/100",
  "🕒 À exécuter sur Binance Testnet (config actuelle)",
]
text = "\n".join(lines)

# --- Envoi Telegram ---
url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
  "chat_id": chat_id,
  "text": text,
  "parse_mode": "HTML",
  "disable_web_page_preview": True
}
data = urllib.parse.urlencode(payload).encode()
req = urllib.request.Request(url, data=data)
with urllib.request.urlopen(req, timeout=10) as r:
    resp = json.loads(r.read().decode("utf-8"))
    assert resp.get("ok"), f"Telegram error: {resp}"
print("DEMO_SIGNAL_SENT ✅")
