# KobeCrypto — MVP v0 (paper only)

Projet éducatif minimal pour produire **≤ 1 signal/jour** (BTCUSDT, ETHUSDT + 1 altcoin), **explicable (3 raisons)**, avec **stop obligatoire** et **risque 0,5 %/trade**.  
**Aucune promesse de gain.** Usage pédagogique uniquement.

---

## Objectif v0 (abrégé)

- **Flux marché public** via WebSocket Binance.
- **Agrégation** ticks → barres 1m.
- **Stratégie** “breakout de contraction” (ATR14 en contraction + cassure HH/LL_20 + volume relatif ≥ 1.5×).
- **Clamp**: au plus **1 signal/jour**.
- **Sizing** par risque monétaire (**0,5 %**) dépendant du **stop**.
- **Paper trading** (remplissage simulé).
- **Journal** CSV/JSONL.
- **CLI**: `scan`, `paper-fill`, `show-log`.
- **2 tests unitaires**.
- **README** et **.gitignore**.  
> Aucun secret committé.

---

## Prérequis

- macOS / Linux, Python **3.10+** (recommandé 3.11), `git`.
- Accès internet pour le flux public Binance (pas de clé API).
- Terminal avec `bash`/`zsh`.

---

## Installation (≈ 5 minutes)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Si besoin pour les tests / imports locaux :
export PYTHONPATH=$PWD

# Préparer un YAML local (non versionné) :
cp -n config.example.yaml config.yaml 2>/dev/null || true
```
> **Hygiène Git** : ne jamais committer `config.yaml`, `logs/`, `*.csv`, `*.jsonl`, `.env`, `data/`.

---

## Configuration rapide (`config.yaml`)

- Définir (au besoin) : `equity`, `risk_pct`, `slippage_bps`, `lot_step`, etc.
- Ce fichier **n’est pas versionné** (voir `.gitignore`).  
Le binaire `paper-fill` peut lire ces valeurs si elles ne sont pas passées en CLI.

---

## Commandes rapides (démo)

La démo produit au premier run un signal JSON puis **`None`** ensuite (à cause du **clamp** journalier).

```bash
python -m kobe.cli scan --demo --json-only
```

---

## Live & décision (réelle v0)

Accumule `N` barres 1m en live, applique la logique **vraie** (contraction + breakout + volume relatif), puis émet un signal **ou** `None`.

```bash
# Exemple : 20 barres, décision réelle, sortie stricte JSON/None
python -m kobe.cli scan --live --bars 20 --decide-real --json-only
```

**Sortie signal (exemple)** :
```json
{
  "symbol": "BTCUSDT",
  "side": "long",
  "entry": 64350.0,
  "stop": 63500.0,
  "risk_pct": 0.5,
  "reasons": [
    "ATR14 en contraction",
    "Cassure HH_20",
    "Volume relatif >= 1.5x"
  ]
}
```

---

## Pipeline → paper trading

`paper-fill` lit un signal **depuis `stdin`**, calcule la **quantité** pour 0,5 % de risque, applique le **slippage** et **journalise** l’ordre papier.

```bash
# 1) Démo → fill papier
python -m kobe.cli scan --demo --json-only | python -m kobe.cli paper-fill --config config.yaml

# 2) Réel → fill papier
python -m kobe.cli scan --live --bars 20 --decide-real --json-only | python -m kobe.cli paper-fill --config config.yaml
```

---

## Journal & audit

- Fichiers : `logs/journal.jsonl` et `logs/journal.csv`.
- Chaque évènement (décision `signal/none`, `paper` fill, etc.) est écrit avec horodatage.

```bash
python -m kobe.cli show-log --tail 10
```

---

## Tests unitaires

```bash
pytest -q
```
> En cas de `ModuleNotFoundError: kobe`, activer la venv et/ou :  
> `export PYTHONPATH=$PWD`

---

## Explicabilité (pourquoi c’est solide)

1. **≤ 1 signal/jour** : le clamp empêche le sur-trading.
2. **3 raisons par signal** : contraction ATR, cassure de range (HH/LL_20), volume relatif.
3. **Stop obligatoire** + **sizing 0,5 %** : la perte maximale est bornée par design.
4. **Journal persistant** (CSV/JSONL) : audit simple, traçabilité A→Z.

---

## FAQ courte

- **« Rien ne sort en live » ?** Normal si conditions non réunies **ou** si un signal a déjà été émis aujourd’hui (clamp).
- **« ImportError sur `kobe` » ?** Venv + `export PYTHONPATH=$PWD`.
- **« Secrets ? »** Aucun requis. Ne **jamais** committer `config.yaml` ni les logs/data.

---

## Version

Vérifier que l’export de version fonctionne des deux côtés :

```bash
python -m kobe.cli --version
python -m kobe --version
```
> Attendu : `0.0.1`

---

## Licence & disclaimer

Usage **éducatif** uniquement. Aucune promesse de performance ni de gain.  
© 2025 KobeCrypto contributors. Voir `LICENSE` si présent.
