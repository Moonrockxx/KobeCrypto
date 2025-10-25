# Kobe Crypto — V2 Plan (Testnet-ready)

## Objectif
Passer d’un bot **paper** à un bot **testnet-ready** (et “live-capable” ultérieurement), avec un adaptateur d’exchange unifié, un mode commutable (paper/testnet/live), une gestion propre des clés, et des tests/mocks couvrant l’IO réseau.

---

## Portée (IN / OUT)
- **IN**
  - Sélecteur d’exchange (ex: Binance, Bybit, OKX) via `EXCHANGE=...`.
  - **Adapter unifié**: interface `Exchange` minimale (markets, balances, place/cancel/positions).
  - **Modes**: `paper` (par défaut), `testnet`, `live` (désactivé par défaut).
  - **.env** & `config.yaml`: source de vérité pour clés/testnet flags (jamais commit).
  - **Order router**: conversion Proposal → ordre(s) (limit/market + TP/SL OCO si dispo).
  - **Rate limit / Retry / Backoff** simples (limiter 429/5xx).
  - **Journal** enrichi pour ordres et fills simulés/réseau (CSV+JSONL).
  - **Tests** avec mocks (aucun appel réseau en CI).
- **OUT**
  - Stratégies avancées, smart-routing multi-venues, data premium.

---

## Architecture V2
```
kobe/
  core/
    adapter/
      base.py            # interface Exchange (ABC)
      binance.py         # impl. testnet via python-binance ou HTTP simple
      bybit.py           # stub/impl ultérieure
      okx.py             # stub/impl ultérieure
    router.py            # Proposal -> Orders ; mapping symbol/qty ; OCO si supporté
    secrets.py           # chargement clés (env/config) ; validations ; jamais commit
    modes.py             # enum Mode {PAPER, TESTNET, LIVE} + helpers
  cli/
    trade.py            # "place" sur mode courant (paper/testnet/live)
    keys.py             # check clés ; ping exchange ; afficher quel mode actif
```
**Interface `Exchange` (base.py)** — MVP
- `load_markets() -> dict`
- `get_balance(asset: str) -> float`
- `create_order(symbol, side, type, qty, price=None, params=None) -> dict`
- `cancel_order(id, symbol) -> dict`
- `fetch_open_orders(symbol=None) -> list[dict]`
- `fetch_positions(symbol=None) -> list[dict]`

---

## Sécurité & Secrets
- `.env` (LOCAL uniquement) : `EXCHANGE=binance`, `BINANCE_KEY=...`, `BINANCE_SECRET=...`, `BINANCE_TESTNET=1`.
- `config.yaml` référence le **mode** (`mode: paper|testnet|live`) et options non-sensibles.
- `.gitignore` **doit** ignorer `.env`, `*.key`, `*.pem`, `logs/`, `*.csv`, `*.jsonl`.
- Ajouter un **health check V2** qui refuse `live` si clés manquantes ou flag sécurité non activé.

---

## Modes d’exécution
- **paper** (défaut) : inchangé (simulateur local).
- **testnet** : requêtes réseau vers l’exchange testnet ; taille/restrictions de lot respectées.
- **live** : **verrouillé** par double opt-in (flag + env), et **désactivé par défaut**.

---

## Router (Proposal → Orders)
- Valide Proposal via `risk.validate_proposal`.
- Calcule la taille (qty) depuis `balance` et pas seulement `position_size` (arrondis lot/step).
- Place un ordre **entrée** (limit/market).
- Attache **TP/SL**:
  - si OCO natif supporté: crée OCO,
  - sinon, en **V2.1**: watchdog local (non inclus V2).
- Journalise chaque ordre/fill dans `logs/orders.{csv,jsonl}`.

---

## Tests (CI)
- **Unitaires**: mock d’`Exchange` (pas de réseau), tests router (long/short, arrondis, OCO absent).
- **Contract tests**: mini tests intégration _optionnels_ derrière un flag manuel (non exécutés en CI).
- **Health V2**: refuse `live` sans clés & sans flag `ALLOW_LIVE=1`.

---

## Roadmap V2 (checklist)
1. **Scaffold adapter**
   - `core/adapter/base.py` (ABC + exceptions)
   - `core/adapter/binance.py` (testnet minimal ; ou client HTTP fin)
2. **secrets.py** (chargement sécuritaire `.env` + config; validations)
3. **modes.py** (enum + helpers `current_mode()` ; lecture `config.yaml`)
4. **router.py** (Proposal → Orders ; sizing arrondi ; TP/SL (si OCO) ; journal)
5. **cli/keys.py** (affiche exchange, mode, clés présentes/absentes — jamais les valeurs)
6. **cli/trade.py** (exécuter une Proposal depuis CLI — en `paper` redirige vers simulateur actuel)
7. **tests** mocks adapter + router
8. **health V2** (vérifie mode et présence clés selon mode ; interdit live sans double opt-in)
9. **docs** MAJ README (V2 mode d’emploi testnet)

---

## Critères de sortie V2
- `mode: testnet` fonctionne en dry-run attendu (création d’ordres testnet).
- CI verte, aucun secret committé, README mis à jour.
- “live” reste verrouillé (double opt-in + warning clair).
