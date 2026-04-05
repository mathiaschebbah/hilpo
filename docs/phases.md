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
- **Statut** : ✅ terminée — B0 exécuté sur 434/437 posts test (3 échoués). Résultats : catégorie 87.3%, visual_format 64.3%, stratégie 93.5%. Coût : $1.14. simulation_run id=2.

## Phase 3 — Rewriter agentique + simulation
- Agent rewriter qui propose de nouvelles versions des instructions I_t
- Prompt versionné en BDD avec CRUD + promotion/rollback
- Batching d'erreurs (B=30) avant déclenchement du rewriter
- **Simulation post-annotation** : l'humain annote d'abord, puis un script rejoue les annotations dans l'ordre et simule la boucle HILPO (équivalent au live sous les hypothèses du protocole)
- Évaluation passive sur les `eval_window` posts suivants (bloc consommé pour l'évaluation, non réinjecté dans le buffer) → promotion si `accuracy(candidate) >= accuracy(incumbent) + delta`
- Critère d'arrêt : `patience=3` rewrites consécutifs sans promotion (compteur global, pas par cible)
- Ablations triviales : rejouer avec B=1, 10, 30, 50 sans ré-annoter
- Contribution principale du mémoire
- Robustesse : promotion atomique (`promote_prompt`), tracking versions par run (`simulation_run_id`), contexte rewriter complet pour le descripteur
- **Statut** : implémenté et durci — rewriter.py + run_simulation.py fonctionnels, migration 005 appliquée. En attente des annotations dev pour le run complet.
