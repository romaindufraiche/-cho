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

# --capital dimensionne les positions suggerees sur ce capital (defaut: 500) :
project-alpha analyze --tickers AAPL,MSFT,MC.PA --capital 500

# Backtest historique (section 9), 2020 -> aujourd'hui, avec benchmark :
project-alpha backtest --tickers AAPL,MSFT,SIE.DE,MC.PA --start 2020-01-01 --benchmark ^GSPC --capital 500 --out backtest.md

# Poids appris sur l'historique reel (regression logistique) plutot que fixes
# a la main - requiert l'extra 'ml' :
pip install -e ".[dev,ml]"
project-alpha train-weights --extended
project-alpha backtest --tickers AAPL,MSFT,SIE.DE,MC.PA --start 2020-01-01 --benchmark ^GSPC --capital 500 --trained --out backtest.md

pytest
```

> **Backtest — limitation actuelle.** `project-alpha backtest` ne fait varier
> que les modules Technical/Momentum et Risk (25/100 du poids total) : les
> cinq autres modules (Catalyst, Fundamental, Expectations, Valuation, Smart
> Money) exigent des donnees point-in-time que la source gratuite utilisee
> ici (yfinance) n'expose pas pour des dates passees — les utiliser
> introduirait un biais de look-ahead. Voir `backtest/historical.py` pour le
> detail. `--trained` (voir section suivante) leve partiellement cette
> limitation pour Fundamental/Valuation sur les titres US via SEC EDGAR ;
> Catalyst, Expectations et Smart Money restent neutres quoi qu'il arrive,
> faute de source gratuite avec historique point-in-time.

## Poids appris (`train-weights`) plutot que fixes a la main

Les poids du cahier des charges (Catalyst 20, Fundamental 15, ...) sont des
poids de depart, pas des poids valides empiriquement. `project-alpha
train-weights` fitte une regression logistique sur ce qui s'est reellement
passe historiquement, avec un split train/test chronologique (pas de
shuffle) pour que les metriques rapportees soient honnetement hors
echantillon :

```bash
project-alpha train-weights --start 2012-01-01 --cutoff 2023-01-01           # Technical + Risk, tous titres
project-alpha train-weights --start 2012-01-01 --cutoff 2023-01-01 --extended  # + Fundamental/Valuation (SEC EDGAR, US uniquement)
```

Ce que ca entraine reellement, et ce que ca ne peut pas entrainer :

| Module | Poids | Entrainable aujourd'hui ? |
|---|---|---|
| Technical / Momentum | 15 | Oui — historique de prix complet (yfinance) |
| Risk (volatilite realisee) | 10 | Oui |
| Fundamental | 15 | Oui, **titres US uniquement** — XBRL SEC EDGAR, dates de depot reelles |
| Valuation | 15 | Oui, **titres US uniquement** — derive du P/E point-in-time |
| Catalyst | 20 | Non — pas de flux d'evenements historique et date gratuit |
| Expectations / Revisions | 15 | Non — pas d'historique de consensus analystes gratuit |
| Market Regime | 5 | Non (pas encore construit) |
| Smart Money | 5 | Non — 13F historique demanderait un pipeline dedie |

**Resultat honnete au 2026-08-27** (univers de 33 grandes capitalisations
US+Europe, 2012-2026, split train avant/test apres 2023-01-01) : le modele
Technical+Risk seul atteint une AUC hors echantillon de **~0.56** (a peine
mieux que le hasard, 0.50) ; le modele etendu Fundamental+Valuation (US
uniquement, echantillon plus petit) tombe a **~0.44** — probablement du
bruit d'echantillon plutot qu'un signal negatif reel, mais en tout cas
aucune preuve d'edge. Voir `ml/technical_risk_weights.json` et
`ml/full_weights.json` (coefficients, metriques, univers d'entrainement)
pour le detail. `--trained` sur `backtest` reste donc **opt-in et
experimental**, pas active par defaut (`analyze`, qui emet les
recommandations du jour, continue d'utiliser les poids fixes du cahier des
charges pour l'instant).

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
  ml/                   # poids Technical/Risk(+Fundamental/Valuation US) appris sur l'historique
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
