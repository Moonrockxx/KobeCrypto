# KobeCrypto V4 — Mode d’emploi Poste 2 (Binance réel)

## 1. Pré-requis secrets & config

Sur Poste 2, dans le répertoire du projet (ex: `~/KobeCrypto`) :

- Fichier `.secrets/kobe/binance.env` avec au minimum :

  - `BINANCE_API_KEY=...`
  - `BINANCE_API_SECRET=...`
  - `BINANCE_MODE=real`
  - `BINANCE_RECVWINDOW_MS=5000`
  - `QUOTE_ASSET=USDC`
  - `MAX_DAILY_LOSS_EUR=25`    # kill-switch journalier

- Fichier `.secrets/kobe/telegram.env` :

  - `TELEGRAM_BOT_TOKEN=...`
  - `TELEGRAM_CHAT_ID=...`

- Fichier `.secrets/kobe/deepseek.env` :

  - `DEEPSEEK_API_KEY=...`
  - `DEEPSEEK_MODEL=deepseek-chat`
  - `DEEPSEEK_BUDGET_EUR=5`

## 2. Variables d’environnement V4

Sur Poste 2, avant de lancer quoi que ce soit en LIVE :

```bash
export KOBE_EXECUTE_PLAN=1          # active l'auto-exécution du plan (entry + TP/SL) en LIVE
export EXECUTE_ORDER_PLAN=1         # même intention côté scheduler si utilisé
export KOBE_RUNNER_HEARTBEAT=0      # pas de heartbeat Telegram automatique
```

Le kill-switch journalier est contrôlé par `MAX_DAILY_LOSS_EUR` (dans `.secrets/kobe/binance.env`)
et la variable `KOBE_DAILY_LOSS_EUR` mise à jour par le programme.

## 3. Vérifier la santé du système (test à la main)

Depuis le répertoire du projet :

```bash
source .venv/bin/activate

# 1) Healthcheck global
python3 -m kobe.cli.health_v2

# 2) Lancer un cycle de scheduler V4 (scan + DeepSeek + éventuelle proposal)
python3 -m kobe.cli.schedule --once
```

Attendu :

- Messages Telegram du type `Kobe V4 - runner start` / `runner stop (exit)`.
- Si un setup est détecté et validé par DeepSeek :
  - une proposal formatée est envoyée sur Telegram,
  - les détails sont journalisés dans `logs/journal.jsonl` et `logs/orders.jsonl`.

En mode LIVE avec `KOBE_EXECUTE_PLAN=1`, un plan d'ordres COMPLET (entry + TP + SL)
peut être envoyé sur Binance spot, en respectant le kill-switch.

## 4. Lancer le runner sur Poste 2

### Option A — Runner V4 dédié

Pour lancer le runner V4 simple (scan périodique + Telegram runner) :

```bash
source .venv/bin/activate

caffeinate -dimsu python3 -m kobe.cli.run_v4   --interval 600   --heartbeat 3600
```

- Lock `/tmp/kobe_runner.lock` : empêche les doublons de runner.
- Start / stop / crash : messages Telegram dédiés.
- Heartbeat : désactivé tant que `KOBE_RUNNER_HEARTBEAT=0`.

### Option B — Scheduler complet (V4 intégré)

Pour utiliser le scheduler global (news + signaux + V4) en boucle :

```bash
source .venv/bin/activate

caffeinate -dimsu python3 -m kobe.cli.schedule --loop
```

(À adapter ensuite dans un service systemd/launchd si besoin.)

## 5. Check-list avant premier trade réel

1. Vérifier le solde `USDC` sur Binance (par ex. ~33.6 USDC pour les premiers tests).
2. Vérifier `MAX_DAILY_LOSS_EUR` dans `.secrets/kobe/binance.env` (par ex. 25).
3. Vérifier que `KOBE_EXECUTE_PLAN=1` est bien exporté (et `EXECUTE_ORDER_PLAN=1` si usage scheduler).
4. Vérifier que le risque par trade est configuré bas (autour de 0.25 %) dans la proposal.
5. Surveiller en parallèle :
   - les messages Telegram (proposals + exécutions),
   - `logs/executor.jsonl` (détails Binance),
   - `logs/orders.jsonl` (router).

En cas de doute, désactiver immédiatement `KOBE_EXECUTE_PLAN` (unset ou `=0`) et
relancer le runner pour repasser en mode "log only" (plan d'ordres construit mais non exécuté).
