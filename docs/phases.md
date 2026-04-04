# Phases de developpement

## Phase 1 — MVP annotation manuelle
- Interface de swipe (React)
- Annotation humaine seule, pas d'IA
- Produit la verite terrain
- **Statut** : pas commence

## Phase 2 — Classificateur baseline
- Integration API modele vision
- Prompt statique v0 ecrit a la main
- Le modele predit en parallele de l'humain
- Mesure du taux d'accord → baseline
- **Statut** : pas commence

## Phase 3 — Rewriter agentique
- Agent rewriter qui propose de nouvelles versions du prompt
- Prompt versionne en BDD avec CRUD
- Batching d'erreurs (B=30) avant declenchement
- Evaluation passive sur les posts suivants
- Contribution principale du memoire
- **Statut** : pas commence
