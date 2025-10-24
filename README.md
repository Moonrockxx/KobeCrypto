# KobeCrypto — Version minimale (paper trading)

KobeCrypto est un petit outil qui **propose au maximum 1 idée de trade par jour** sur le Bitcoin, l’Ether et une petite altcoin.  
C’est **100 % papier** (simulation) : on observe, on comprend, on apprend — pas d’argent réel.

---

## Comment ça marche (en clair)
1. Le programme **regarde le marché en temps réel** et attend des moments où **le prix se resserre** puis **part franchement** (cassure d’un côté).
2. S’il y a un setup propre, il **propose 1 signal** : sens (achat/vente), **prix d’entrée**, **stop** (niveau de sécurité) et **risque 0,5 %**.
3. Ce signal peut être **rempli en papier** (simulation), et **enregistré** dans un journal pour suivi.

> **Important** : il y a **au plus 1 signal par jour**. Souvent, il n’y en a **aucun** — c’est volontaire.

---

## Installation rapide (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

C’est tout. Aucune clé API à fournir pour commencer.

---

## Premier essai (démo, données intégrées)
Affiche un exemple de signal (ou "None") sans toucher au marché réel.

```bash
python -m kobe.cli scan --demo --json-only
```

---

## En “vrai” (live, marché public)
Regarde le flux en direct et décide s’il y a un signal aujourd’hui.

```bash
python -m kobe.cli scan --live --bars 20 --json-only
# Astuce : il est normal d'obtenir "None" la plupart du temps.
```

---

## Interpréter la sortie
- **"None"** : pas de signal aujourd’hui → on ne fait rien.
- **Un petit JSON** (ex.) :
  ```json
  {
    "symbol": "BTCUSDT",
    "side": "long",
    "entry": 64350.0,
    "stop": 63500.0,
    "risk_pct": 0.5,
    "reasons": [
      "Prix resserré puis cassure",
      "Rupture du range récent",
      "Volume suffisant"
    ]
  }
  ```
  - **side** : sens ("long" = achat, "short" = vente)
  - **entry** : prix proposé
  - **stop** : filet de sécurité si le marché va contre nous
  - **risk_pct** : part du capital mise en jeu sur l’idée (ici **0,5 %**)
  - **reasons** : 3 raisons simples qui expliquent le signal

---

## Paper trading (simulation) : quoi faire
1) **Remplir** la proposition en papier (calcule la quantité, applique le stop, et journalise) :
```bash
python -m kobe.cli scan --demo --json-only | python -m kobe.cli paper-fill
# ou avec le live :
# python -m kobe.cli scan --live --bars 20 --json-only | python -m kobe.cli paper-fill
```

2) **Lire le journal** (ce qui a été simulé) :
```bash
python -m kobe.cli show-log --tail 10
```

3) **Ce que vous ne faites pas** : pas d’ordre réel sur un échange. Le but est d’apprendre la logique et le suivi **sans risque**.

---

## Rappels utiles
- **≤ 1 signal/jour** (il est normal d’avoir "None").
- **Stop toujours présent** et **risque fixe 0,5 %** pour cadrer la perte potentielle.
- **Aucune promesse de gain**. Projet éducatif uniquement.
- Évitez de publier vos fichiers locaux de configuration ou de journaux sur internet.

---

## Version
```bash
python -m kobe.cli --version
```

## Clamp ≤1 signal/jour (UTC)

**Pourquoi ?** Le MVP garantit **0 ou 1 signal/jour**. Si un signal a déjà été émis **aujourd’hui (UTC)**, `scan` renvoie **`None`** (démo & réel). Aucune promesse de gain. Objectif : discipline et reproductibilité.

**Comment ça marche ?**
- La CLI vérifie le journal JSONL : s’il existe un `{"type":"signal","ts":...}` daté du jour (UTC), tout nouveau `scan` renvoie `None`.
- Chemin démo : `kobe.strategy.v0_breakout` ; chemin réel : `v0_contraction_breakout`.
- Le clamp journalise une décision `{"type":"decision","source":"clamp","result":"none","reason":"already_emitted_today"}`.

**Exemple rapide**
```bash
# 1er run (peut produire un Signal JSON)
python -m kobe.cli scan --demo --json-only
# 2e run le même jour → clamp → None
python -m kobe.cli scan --demo --json-only
```

**Notes**
- Horloge de référence : UTC (timestamp ISO8601/epoch).
- Le clamp n’empêche pas la journalisation d’événements non-signal (paper-fill, etc.).
- Secrets/data/logs restent non committés (voir `.gitignore`).

---

## Roadmap ultra-simple (V0 → V1)

- **V0 (en place)** : CLI locale paper-only ; stratégie *breakout de contraction* ; 0–1 signal/jour ; risque **0,5 %** ; **stop obligatoire** ; 3 raisons ; `scan` · `paper-fill` · `show-log` ; journal CSV/JSONL ; 2+ tests ; README ; .gitignore.
- **V1 (prochaine)** : mêmes garde-fous + PnL/jour consolidé natif dans la CLI ; sélection d’1 altcoin plus nette ; plus de tests & docs ; ergonomie CLI (messages d’erreur et exemples).

# Lexique débutant

---

## Lexique débutant

- **Long** : acheter en pensant que le prix va monter.  
- **Short** : vendre (ou simuler une vente) en pensant que le prix va baisser.  
- **Stop** : niveau de sécurité où la position serait coupée si le marché va contre nous.  
- **Risk_pct** : pourcentage du capital risqué par trade. Dans la v0, c’est **0,5 %**.  
- **Slippage (bps)** : glissement entre le prix attendu et le prix d’exécution (1 bps = 0,01 %).  
- **Lot_step** : taille minimale d’un ordre (ex. 0,001 BTC).  
- **Clamp ≤1/jour** : limite stricte d’un seul signal maximum par jour.  
- **PnL (Profit and Loss)** : gain ou perte réalisé(e) sur un trade (en devise ou en %).  

---

**v0 ATTEINTE ✅** — tous les critères du SOP sont remplis :  
- CLI exécutable, config YAML complète, WS Binance, stratégie breakout, risk sizing 0,5 %, clamp, journal CSV+JSONL, tests unitaires, README + lexique + .env.example.  
- Version stable pour usage paper-trading éducatif.