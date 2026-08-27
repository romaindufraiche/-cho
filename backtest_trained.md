# Backtest 2020-10-21 -> 2026-08-07

- Modele d'entree: ml-trained (experimental)
- Capital: 500.00 -> 510.33 (+10.33)
- Trades: 148
- CAGR: 0.0035
- Alpha vs ^GSPC: -0.1353
- Precision du signal (win rate): 0.2838
- Taux d'objectif atteint: 0.2838
- Avg win / avg loss: 0.1941 / -0.0552
- Expectancy: 0.0156
- Profit factor: 1.3941
- Max drawdown: -0.0148
- Volatilite (annualisee): 0.0402
- Sharpe / Sortino: 0.8856 / 1.61

## Trades par ticker
- AAPL: 11
- AMZN: 11
- ASML.AS: 17
- GOOGL: 15
- MC.PA: 24
- MSFT: 17
- NVDA: 0
- OR.PA: 19
- SAP.DE: 18
- SIE.DE: 16

---
Poids appris (regression logistique, validation train/test chronologique - voir ml/technical_risk_weights.json et ml/full_weights.json), pas fixes a la main : Technical+Risk pour tous les titres, Fundamental+Valuation en plus pour les titres avec depots SEC EDGAR (US uniquement - les titres europeens restent sur Technical+Risk seul). Catalyst, Expectations et Smart Money restent neutres, aucune source gratuite avec historique point-in-time disponible ici. Performance hors echantillon faible (AUC ~0.44-0.56, proche du hasard) : a traiter comme experimental, pas comme un edge valide.