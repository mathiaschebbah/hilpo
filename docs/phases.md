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
- **Statut** : ✅ terminée — test E2E validé. Split test annoté (437/437). Split dev : 104 annotés en Phase 1, le reste s'annote pendant la boucle MILPO (Phases 2-3).

## Phase 2 — Classificateur baseline
- Pipeline 2 étapes : descripteur multimodal → 3 classifieurs text-only en parallèle
- Descripteur (FEED + REELS) : **Gemini 3 Flash Preview** via OpenRouter (image + vidéo + audio + texte, jusqu'à 20 slides)
- Classifieurs : Qwen 3.5 Flash text-only, tool calling forcé avec enum fermé
- Schema features JSON (résumé visuel libre + champs structurés)
- 6 prompts v0 écrits à la main (2 descripteur scope FEED/REELS + 3 classifieurs + 1 stratégie)
- B0 baseline : pipeline batch async sur le split test (437 posts)
- **Statut** : ✅ terminée. **Run id=7 (2026-04-06)** : 437/437 posts classifiés (100% couverture, première fois sans aucun échec), accuracies 86.7% / 65.4% / 94.5%, coût $2.68, durée 25.4 min. Configuration finale : descripteur Gemini 3 Flash Preview pour FEED+REELS (commit `7e352ab`), classifieurs Qwen 3.5 Flash + tool calling forcé (commit `0b3bd8b`), prompts v0 lockés via [migration 006](../apps/backend/migrations/006_seed_prompts_v0.sql). Détails complets dans [evaluation.md](evaluation.md#résultats-b0--baseline-zero-shot-v0).

## Phase 3 — Rewriter agentique + simulation
- Agent rewriter qui propose de nouvelles versions des instructions I_t
- Prompt versionné en BDD avec CRUD + promotion/rollback
- Batching d'erreurs (B=30) avant déclenchement du rewriter
- **Simulation post-annotation** : l'humain annote d'abord, puis un script rejoue les annotations dans l'ordre et simule la boucle MILPO (équivalent au live sous les hypothèses du protocole)
- Évaluation passive sur les `eval_window` posts suivants (bloc consommé pour l'évaluation, non réinjecté dans le buffer) → promotion si `accuracy(candidate) >= accuracy(incumbent) + delta`
- Critère d'arrêt : `patience=3` rewrites consécutifs sans promotion (compteur global, pas par cible)
- Ablations triviales : rejouer avec B=1, 10, 30, 50 sans ré-annoter
- **Adaptation de ProTeGi (Pryzant et al. 2023)** au cas multimodal industriel — voir [related_work.md](related_work.md) pour la comparaison méthodologique détaillée
- Robustesse : promotion atomique (`promote_prompt`), tracking versions par run (`simulation_run_id`), contexte rewriter complet pour le descripteur
- Prompts v0 comme état initial : `run_simulation.py` charge les 6 prompts uniquement depuis la BDD via `load_prompt_state_from_db(conn)` (plus de hardcoding côté Python)
- **Statut** : implémenté et durci — rewriter.py + run_simulation.py fonctionnels, migrations 005 et 006 appliquées. En attente des annotations dev pour le run complet.
