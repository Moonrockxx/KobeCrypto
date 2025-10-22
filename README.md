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

