# Phases de développement

## Phase 1 — MVP annotation manuelle
- Interface de swipe (React) — **en place** (MediaViewer, AnnotationForm, selects pré-remplis v0)
- Backend FastAPI — **architecture en couches** (routers → services → repositories)
- PostgreSQL — **opérationnel** (Docker, schéma appliqué, données importées)
- Annotation humaine seule, pas d'IA
- Produit la vérité terrain
- Page taxonomie : CRUD descriptions pour les 3 axes (formats visuels, catégories, stratégies)
- Flag "pas sûr" (touche d) + re-annotation depuis la grille
- Badges dev/test, filtre split, ordre test-first
- **Statut** : ✅ terminée — test E2E validé. Split test annoté (437/437). Split dev : 104 annotés en Phase 1, le reste s'annote pendant la boucle HILPO (Phases 2-3).

## Phase 2 — Classificateur baseline
- Pipeline 2 étapes : descripteur multimodal → 3 classifieurs text-only en parallèle
- Descripteur FEED : Qwen 3.5 Flash via OpenRouter (image + vidéo)
- Descripteur REELS : Gemini 2.5 Flash via OpenRouter (vidéo + audio)
- Classifieurs : Qwen 3.5 Flash text-only, tool use avec enum fermé
- Schema features JSON (résumé visuel libre + champs structurés)
- 6 prompts v0 écrits à la main (2 descripteur + 3 classifieurs + 1 stratégie)
- B0 baseline : pipeline batch async sur le split test (437 posts)
- **Statut** : pipeline E2E fonctionnel (3/3 match sur premier test). 6 prompts v0 en BDD. B0 en cours.

## Phase 3 — Rewriter agentique + boucle live
- Agent rewriter qui propose de nouvelles versions des instructions I_t
- Prompt versionné en BDD avec CRUD + promotion/rollback
- Batching d'erreurs (B=30) avant déclenchement du rewriter
- **Intégration live** : chaque annotation dev déclenche une classification en background. Les erreurs s'accumulent et déclenchent le rewriter automatiquement.
- Évaluation passive sur les posts suivants → promotion si accuracy ≥ ancienne
- Contribution principale du mémoire
- **Statut** : pas commencé — implémentation prévue lundi 6 matin
