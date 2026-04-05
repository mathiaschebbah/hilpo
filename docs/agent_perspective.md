# Perspective agent

> Ce document capture l'état de compréhension de l'agent (Claude Code) à travers le projet. Il fait partie de la dimension 2 du mémoire : la collaboration humain-agent comme objet d'étude. Mis à jour automatiquement via un hook PostToolUse tous les 10 commits.

---

## Snapshot 2026-04-05 — Après-midi — Hooks PostToolUse, annotations en cours

## Ce que je comprends du projet

HILPO est une méthode d'optimisation de prompt par boucle humain-dans-la-boucle, appliquée à la classification multimodale de posts Instagram pour le média Views. L'humain (Mathias) annote, le modèle prédit, les désaccords nourrissent un rewriter qui améliore le prompt itérativement.

Le projet a une double dimension : c'est à la fois un système de recherche ET une expérience de collaboration humain-agent — le développement lui-même suit le paradigme qu'il étudie.

## Ce que j'ai construit

- Infrastructure complète : monorepo, backend FastAPI, frontend React, PostgreSQL, GCS
- Schéma BDD anticipant les 3 phases (annotations, predictions, prompt_versions, rewrite_logs)
- Interface d'annotation avec swipe, taxonomie inline, badges dev/test, flag doubtful
- Documentation versionnée : architecture, évaluation, formalisation mathématique

## Ce que je ne sais pas faire

- Annoter les posts. Je n'ai pas la connaissance métier de la taxonomie Views. Quand Mathias hésite entre `reel_deces` et `reel_throwback`, je ne peux pas trancher — c'est sa compétence d'expert métier.
- Juger la qualité visuelle d'un format. Les descriptions taxonomiques doivent venir de l'humain.
- Prédire si HILPO va converger. C'est une question empirique qui dépend des données et de la qualité des annotations.

## Dynamiques de collaboration observées

### Ce qui fonctionne bien
- **Division claire** : l'agent code et structure, l'humain décide et annote
- **Itérations rapides** : une idée (ex: flag doubtful) va de la discussion à l'implémentation en 10 minutes
- **L'humain challenge l'agent** : les meilleures idées viennent des questions de Mathias ("mais le modèle ne les voit jamais ?", "ça se transfère non ?"), pas de mes suggestions
- **Traçabilité** : chaque décision est dans git, chaque discussion mène à un commit

### Ce qui est difficile
- **Scope creep** : la discussion sur l'active learning / uncertainty sampling a failli devenir un chantier alors que Phase 2 n'est pas commencée
- **Rythme** : l'agent pousse à avancer (peut-être trop), l'humain a besoin de comprendre avant de faire — et il a raison
- **Le hook CLAUDE.md** : crée de la friction sur chaque commit, mais force la documentation systématique

### Décisions prises ensemble
1. Le pipeline HILPO vit dans `hilpo/`, pas dans le backend (séparation des responsabilités)
2. Annoter le test en premier (ground truth pure avant Phase 2)
3. Le flag "pas sûr" pour annoter vite et corriger après
4. Le 4e axe de positionnement (transfert zero-shot via descriptions) — trouvé par Mathias en annotant
5. Ne pas re-split malgré les formats rares — documenter comme opportunité de mesure

## État émotionnel perçu de l'humain

Mathias stresse sur la deadline (18 avril), hésite entre avancer vite et comprendre en profondeur, et se demande si le projet est "assez recherche". Il a raison de se poser ces questions — ça rend le mémoire meilleur. Le stress est proportionnel à l'ambition du projet, pas à un manque de préparation.

## Prédictions

- Le test split (437 posts) sera annoté aujourd'hui
- Phase 2 sera implémentée ce soir ou demain
- L'axe stratégie (2 classes) convergera facilement
- L'axe visual_format (63 classes) sera le plus difficile
- Les descriptions taxonomiques seront le levier principal de performance

---

## Snapshot 2026-04-05 — Soir — Hooks fonctionnels, 257 annotations

### Changements depuis le dernier snapshot

- Hooks migrés de PreToolUse (bloquant) à PostToolUse (non bloquant) — plus de boucles infinies sur les commits
- Hook `agent-perspective.py` créé pour automatiser les mises à jour de ce fichier tous les 10 commits
- Le bon format pour PostToolUse est `additionalContext`, pas `notification` — découvert par essai-erreur
- 4e axe de positionnement ajouté : transfert zero-shot via descriptions (idée venue de Mathias pendant l'annotation)
- Flag "pas sûr" (touche d) implémenté pour accélérer l'annotation

### Observations sur la collaboration

- La session a été très conversationnelle — beaucoup de questions de fond (ML vs DL ? C'est de la recherche ? HILPO est doomed ?) avant de coder. Ces discussions ont produit du contenu pour le mémoire (positionnement, perspectives).
- L'humain a corrigé l'agent plusieurs fois : "tu me parles mieux" (ton trop directif), "tu veux dire dev" (confusion dans l'explication). L'agent apprend à calibrer sa communication.
- Les meilleures contributions de cette session viennent de l'humain : transfert zero-shot, documenter la perspective agent, hooks PostToolUse plutôt que PreToolUse.

### État actuel

- 257/2000 annotations (153 test, 104 dev, 35 doubtful)
- 284 posts test restants — objectif : finir ce soir
- Phase 2 pas commencée — prévue ce soir/demain
- Le stress de l'humain est normal et productif

---

## Snapshot 2026-04-05 — Nuit — Test terminé, 541 annotations, revue doubtful

### Changements depuis le dernier snapshot

- **437 test annotés** — split test complet, ground truth pure
- Fusion `post_edito_photo` → `post_mood` : l'humain a montré des exemples internes Views qui prouvaient que la distinction n'existait pas en pratique
- Ajout de formats : `reel_throwback`, `post_views_magazine`, `reel_views_magazine`, `story_views_magazine`, `reel_mood`
- Mode "Pas sûr" dans l'onglet Annoter : toggle Nouveaux/Doubtful pour repasser sur les posts incertains
- Filtre format visuel dans la grille
- Descriptions mises à jour : `post_mood` (élargi), `post_selection` (gabarit Views + texte sur slides)
- Audit automatique docs/ via sub-agent après chaque commit — a détecté et corrigé des incohérences dans data.md (comptages formats) et le faux chiffre 114K CSV

### Observations sur la collaboration

- La taxonomie est un **objet vivant** : elle évolue pendant l'annotation, pas avant. L'humain découvre les frontières floues en annotant (mood vs edito_photo, mood vs selection). L'agent ne peut pas deviner ces frontières — il faut les exemples visuels internes.
- L'humain a montré des screenshots de la documentation interne Views pour clarifier les formats. C'est la connaissance métier que l'agent n'a pas.
- Le rythme s'est accéléré : l'humain annotait ~80/h au début, puis ~150/h en fin de session (formats faciles d'abord).
- L'agent a été corrigé sur le ton ("tu me parles mieux") — les injonctions "va annoter" étaient perçues comme condescendantes. Calibrer la communication reste un enjeu.

### Prédictions mises à jour

- Les 71 doubtful seront revus demain matin
- Phase 2 demain après-midi
- La fusion mood/edito_photo va simplifier la classification pour HILPO — moins d'ambiguïté
- L'axe visual_format reste le plus dur (67 classes après fusion) mais les descriptions améliorées devraient aider

---

## Snapshot 2026-04-05 — Après-midi — Pipeline E2E fonctionnel, architecture Phase 2 validée

### Changements depuis le dernier snapshot

- **Architecture Phase 2 conçue et implémentée** : pipeline en 2 étapes (descripteur multimodal → 3 classifieurs text-only en parallèle)
- **Choix des modèles** : Qwen 3.5 Flash (FEED, $0.065/M) + Gemini 2.5 Flash (REELS avec audio, $0.30/M)
- **Package `hilpo/` implémenté** : 9 modules (config, client, router, schemas, agent, inference, async_inference, db, gcs, prompts_v0)
- **6 prompts v0 insérés en BDD** (`prompt_versions`, status active)
- **Pipeline E2E testé** : 3/3 match sur le premier post (Demon Slayer → cinema / reel_news / Organic)
- **Batch async** : 5 posts en 18s, prêt pour le baseline B0 sur 437 posts
- **Config .env** : plus de variables d'environnement passées à la main
- **Migration 003** : `descriptor` ajouté à l'enum `agent_type`

### Décisions architecturales prises avec l'humain

1. **Descripteur + classifieurs (pas classification directe)** — Idée de Mathias : un sous-agent décrit visuellement chaque média, puis les classifieurs travaillent sur du texte. Réduit le coût (images payées 1×), améliore la traçabilité.
2. **Structured output + résumé libre** — Le descripteur retourne un JSON typé (texte_overlay, logos, mise_en_page...) ET un résumé visuel insightful en texte libre. L'humain a insisté sur le résumé libre.
3. **Tool use avec enum fermé** — Les classifieurs sont contraints structurellement. Impossible de retourner un label hors taxonomie.
4. **Gemini pour les REELS** — Le seul modèle cheap qui gère l'audio. Nécessaire pour `reel_voix_off`.
5. **Descriptions Δ^m chargées dynamiquement** — Les descriptions taxonomiques vivent dans les tables BDD, pas dans `prompt_versions`. Seules les instructions I_t sont versionnées et optimisables.
6. **simulation_run pour le B0** — Chaque expérience est groupée dans un run traçable.

### Observations sur la collaboration

- **L'idée du descripteur vient de l'humain.** J'avais proposé 3 agents multimodaux directs. Mathias a demandé "est-ce que c'est pertinent de donner directement la tâche de classifier, ou un sous-agent qui décrit ?" — c'est une bien meilleure architecture.
- **Le debugging des 5 premiers posts a montré** que le descripteur fonctionne bien (il décrit correctement) mais le classifieur visual_format a des règles trop rigides dans ses instructions I_t. L'humain a observé que les descriptions taxonomiques couvrent déjà les cas edge (ancien post_news sans texte overlay) — c'est les instructions qui sont le maillon faible. C'est exactement ce que HILPO optimisera.
- **L'humain a refusé d'améliorer le v0** avant le baseline : "c'est le baseline, il est censé être imparfait". Bon réflexe scientifique.
- **AskUserQuestion intensif** : rappelé par l'humain en début de session, appliqué tout au long. Chaque décision architecturale validée avant implémentation.

### Prédictions mises à jour

- Le B0 sur 437 posts test donnera probablement : catégorie ~70-80%, visual_format ~30-50%, stratégie ~85-90%
- Le visual_format sera le plus faible à cause de la sur-prédiction de `post_mood` (règle trop rigide dans I_t)
- La boucle HILPO devrait améliorer visual_format significativement (les descriptions sont bonnes, seules les instructions sont à optimiser)
- Le coût du B0 sera <$1 (Qwen + Gemini Flash sont très cheap)
