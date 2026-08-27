# Backtest 2020-10-21 -> 2026-03-26

- Modele d'entree: heuristic
- Capital: 500.00 -> 499.95 (-0.05)
- Trades: 39
- CAGR: -0.0
- Alpha vs ^GSPC: -0.1388
- Precision du signal (win rate): 0.3077
- Taux d'objectif atteint: 0.3077
- Avg win / avg loss: 0.1233 / -0.0551
- Expectancy: -0.0002
- Profit factor: 0.9943
- Max drawdown: -0.0078
- Volatilite (annualisee): 0.0195
- Sharpe / Sortino: -0.0239 / -0.054

## Trades par ticker
- AAPL: 7
- AMZN: 2
- ASML.AS: 0
- GOOGL: 3
- MC.PA: 7
- MSFT: 4
- NVDA: 0
- OR.PA: 5
- SAP.DE: 6
- SIE.DE: 5

---
Ce backtest ne fait varier que les modules Technical/Momentum et Risk (25/100 du poids total) ; Catalyst, Fundamental, Expectations, Valuation et Smart Money restent neutres (50/100) car leurs donnees point-in-time ne sont pas disponibles via la source gratuite utilisee ici. Voir backtest/historical.py pour le detail.