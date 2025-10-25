# KobeCrypto — Version minimale (paper trading)# KobeCrypto — V1 baseline (scheduler + paper trading + CI)

KobeCrypto est un bot **paper trading éducatif**, conçu pour proposer **au maximum 1 idée actionnable par jour**.  
Il fonctionne en mode simulation complète : **aucun ordre réel** n’est envoyé.

---

## 🔍 Fonctionnement

Kobe analyse le marché toutes les 15 minutes (07h–21h UTC) :

1. **Veille actus** silencieuse (pas de message Telegram).  
2. **Auto‑proposal** : génération d’une idée de trade si les facteurs convergent.  
3. **Risk guard** : rejette tout signal incohérent ou dépassant le risque max (≤ 0.5 %).  
4. **Journalisation** automatique (proposals, positions papier, PnL).  
5. **Reporting quotidien** (résumé du PnL simulé à 21:00 UTC).  

> Par défaut, Telegram est désactivé.  
> Il peut être activé uniquement pour les **trades** (jamais pour les news).

---

## ⚙️ Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🧩 Configuration (`config.yaml`)

Copie le modèle et adapte-le :
```bash
cp config.example.yaml config.yaml
```

Exemple :
```yaml
telegram:
  bot_token: ""         # Token du bot Telegram (laisser vide pour désactiver)
  chat_id: ""           # ID du chat Telegram

scheduler:
  enabled_hours_utc: [7,8,9,10,11,12,13,14,15,16,17,18,19,20,21]
  interval_minutes: 15

news:
  feeds:
    - "https://www.coindesk.com/arc/outboundfeeds/rss/"
    - "https://cointelegraph.com/rss"
    - "https://www.theblock.co/rss"
  keywords_any: ["BTC","ETH","Solana","ETF","SEC","funding","on-chain"]
  max_items_per_run: 6

alerts:
  trades:
    enabled: false        # true → envoi Telegram des trades (jamais les news)

reporting:
  daily:
    enabled: true
    time_utc: "21:00"

risk:
  max_trade_pct: 0.5
  max_proposal_pct: 0.25

paper:
  auto_close: false       # pour tests : ferme auto les positions simulées
```

> Les logs (`logs/*.csv`, `logs/*.jsonl`) sont ignorés par Git.

---

## 🚀 Utilisation

### Lancer le scheduler (veille + proposals + reporting)
```bash
source .venv/bin/activate
python -m kobe.cli.schedule
```

Mode debug (un seul cycle) :
```bash
python -m kobe.cli.schedule --once
```

---

### Générer une proposal manuelle
```bash
python -m kobe.cli.signal \
  --symbol BTCUSDT --side long \
  --entry 68000 --stop 67200 --take 69600 \
  --reason "Breakout" --reason "Funding neutre" --reason "SPX corrélé +" \
  --risk-pct 0.25 --size-pct 5
```

### Auto‑signal avec facteurs fournis
```bash
python -m kobe.cli.autosignal \
  --symbol ETHUSDT --price 2400 \
  --trend-strength 0.75 --news-sentiment 0.7 \
  --funding-bias 0.1 --volatility 0.6 --btc-dominance 0.58
```

### Reporting manuel (PnL)
```bash
python -m kobe.cli.report
```

---

## 📂 Journaux

| Type | Fichier | Description |
|------|----------|-------------|
| Proposals | `logs/journal.csv` / `.jsonl` | Idées de trade générées |
| Positions | `logs/positions.csv` / `.jsonl` | Trades simulés (open/close) |
| PnL | `logs/pnl_daily.csv` / `.jsonl` | Résumé du jour |

---

## 🧠 Architecture

- `kobe/core/` → cœur (scheduler, journal, risk, executor, alerts)
- `kobe/signals/` → logique des proposals
- `kobe/cli/` → commandes CLI
- `tests/` → tests unitaires Pytest
- `docs/` → documentation

---

## 🧪 Tests & CI

Lancer tous les tests :
```bash
pytest -q
```

CI GitHub : exécution automatique sur chaque push/PR.

---

## 📬 Telegram (trade‑only)

1. Crée ton bot avec **BotFather** et récupère :
   - `bot_token`
   - `chat_id` (via `@userinfobot`)
2. Mets `alerts.trades.enabled: true` dans `config.yaml`.
3. Relance le scheduler :
   ```bash
   python -m kobe.cli.schedule
   ```
4. Tu recevras les trades validés (jamais les news).

---

## 🗺️ Roadmap

| Version | État | Contenu |
|----------|------|---------|
| **V1.0.0** | ✅ | Scheduler, auto‑proposal, journal, tests, CI |
| **V1.1** | 🏗️ | Executor papier, risk guard, reporting, Telegram trades |
| **V2.0** | 🚧 | Passage testnet, API exchange, données temps réel |

---

## ⚠️ Avertissement

> KobeCrypto est un projet éducatif.  
> Il ne fournit **aucun conseil financier** et n’exécute **aucun ordre réel**.  
> Les marchés sont risqués : n’investissez que ce que vous pouvez perdre.