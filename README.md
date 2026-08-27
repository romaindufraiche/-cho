# Project Alpha

Systeme personnel d'analyse boursiere augmentee par IA. Identifie des
opportunites actions (Europe + US) a horizon 2-16 semaines, en combinant
analyse evenementielle, fondamentale, technique, valorisation et risque,
avec suivi de these dans le temps.

**Usage strictement personnel.** Rien ici ne constitue un conseil en
investissement — voir [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md).

## Principe

```
Event -> Theme -> Company -> Price -> Trade -> Thesis tracking
```

Le systeme part des changements (resultats, guidance, contrats, M&A,
macro, geopolitique, ...), identifie les entreprises exposees, les score
sur 8 dimensions ponderees, calcule une zone d'achat / stop / objectifs, et
emet un signal — `NO TRADE` est un resultat valide et volontairement la
sortie par defaut.

## Demarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # optionnel: ajouter des cles API gratuites

# Fonctionne des l'installation, sans aucune cle API (source yfinance) :
project-alpha analyze --tickers AAPL,MSFT,MC.PA

# Backtest historique (section 9), 2020 -> aujourd'hui, avec benchmark :
project-alpha backtest --tickers AAPL,MSFT,SIE.DE,MC.PA --start 2020-01-01 --benchmark ^GSPC --out backtest.md

pytest
```

> **Backtest — limitation actuelle.** `project-alpha backtest` ne fait varier
> que les modules Technical/Momentum et Risk (25/100 du poids total) : les
> cinq autres modules (Catalyst, Fundamental, Expectations, Valuation, Smart
> Money) exigent des donnees point-in-time que la source gratuite utilisee
> ici (yfinance) n'expose pas pour des dates passees — les utiliser
> introduirait un biais de look-ahead. Voir `backtest/historical.py` pour le
> detail et la piste (SEC EDGAR XBRL, donnees datees) pour lever cette
> limitation.

## Architecture

```
src/project_alpha/
  data/
    models.py       # entites du data model (section 7 du cahier des charges)
    storage.py       # SQLite (prix) + JSONL append-only (recommandations, theses)
    sources/          # SEC EDGAR, FRED, ECB, Finnhub, Twelve Data, GNews, FMP, yfinance
  events/             # detection d'evenements + theme graph (V0, extensible par LLM en V3)
  scoring/            # 8 modules ponderes -> Quality / Opportunity / Price / score total
  signals/            # zone d'achat, stop, targets, position sizing, moteur de signal
  portfolio/           # garde-fous portefeuille (correlation, secteur, limites) + thesis tracker
  backtest/            # metriques (CAGR, Sharpe, ...) + simulateur + walk-forward splits
  reporting/           # generation de la newsletter (Markdown)
  pipeline.py           # orchestration bout-en-bout pour un ticker
  cli.py                 # `project-alpha analyze ...`
```

Chaque source de donnees externe est **optionnelle**: en l'absence de cle
API, le module de score correspondant retombe sur une valeur neutre (50/100)
plutot que de faire echouer le pipeline — conformement au principe "priorite
au gratuit / cout nul" du cahier des charges.

## Scoring (section 4)

| Module | Poids |
|---|---|
| Catalyst | 20 |
| Fundamental | 15 |
| Expectations / Revisions | 15 |
| Technical / Momentum | 15 |
| Valuation | 15 |
| Market Regime | 5 |
| Smart Money | 5 |
| Risk | 10 |

Trois scores diagnostiques (Quality / Opportunity / Price, voir
`scoring/composite.py`) evitent de confondre "excellente entreprise" et
"excellente action a acheter maintenant". Le signal final utilise le score
total pondere.

## Roadmap

| Phase | Etat | Livrable |
|---|---|---|
| V0 — Research | ✅ base posee | Collecte, normalisation, comparaison des fournisseurs |
| V1 — Quant Engine | ✅ base posee | Fondamentaux + technique + valuation + catalyst |
| V2 — Backtest | 🟡 squelette | Scoring, portfolio, walk-forward (a valider sur historique reel) |
| V3 — AI Research | ⬜ a faire | RAG, agents (bull/bear/synthese), sources tracees |
| V4 — Dashboard | ⬜ a faire | Market, opportunities, portfolio, backtest, thesis |
| V5 — Newsletter | 🟡 generation Markdown en place | Archivage automatise |
| V6 — Paper trading | ⬜ a faire | 2-3 mois minimum, portefeuille virtuel 100 000 € |
| V7 — Usage reel | ⬜ a faire | Apres validation du track record |

Ce depot livre une base V0/V1 fonctionnelle de bout en bout (donnees ->
score -> signal -> newsletter) plus les fondations de V2/V5, prete a etre
etendue phase par phase.

## Sources de donnees (section 6)

Toutes gratuites au demarrage: SEC EDGAR, AMF/Info-financiere, FRED/ALFRED,
ECB Data Portal, Massive (Polygon) Free, Twelve Data Free, Finnhub Free,
GNews Free, FMP Free, yfinance (prototype uniquement). Voir `.env.example`
pour la configuration.

## Principes non negociables

Voir [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) — no prediction without
evidence, no BUY obligatoire, LLM ≠ source de verite, aucune modification
retroactive, backtest avant confiance, entreprise ≠ action, these suivie
dans le temps.
