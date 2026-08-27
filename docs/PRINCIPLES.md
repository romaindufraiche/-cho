# Principes non negociables

Repris tels quels du cahier des charges (section 15) — toute evolution du
code doit rester compatible avec ces regles.

- **No prediction without evidence.** Chaque affirmation importante garde
  sa source, son URL, sa date et un niveau de confiance (`SourceRef`).
- **No BUY obligatoire.** Le systeme peut recommander `CASH` / `NO_TRADE` —
  c'est la sortie par defaut du moteur de signal, jamais un cas d'erreur.
- **LLM ≠ source de verite.** Les donnees financieres sont deterministes et
  sourcees ; le LLM (V3) intervient apres ingestion et calcul, pour la
  recherche, la synthese et la redaction — jamais pour produire un chiffre.
- **Aucune modification retroactive.** Les recommandations sont
  horodatees et versionnees (`data_version`, `scoring_version`,
  `model_version`, `prompt_version`) et stockees en append-only.
- **Backtest avant confiance.** Une bonne narration ne remplace pas une
  validation statistique (walk-forward, cross-provider checks).
- **Entreprise ≠ action.** Une excellente entreprise peut etre une mauvaise
  position au mauvais prix — d'ou la separation Quality / Opportunity /
  Price scores.
- **These suivie dans le temps.** On vend lorsque la these ou la structure
  de risque est invalidee, pas uniquement parce qu'un objectif arbitraire
  est atteint (`portfolio/thesis.py`, `signals/engine.evaluate_open_position`).

## Disclaimer

Document et code a usage personnel. Les exemples de titres, prix, objectifs
et scores sont illustratifs et ne constituent pas une recommandation
d'investissement.
