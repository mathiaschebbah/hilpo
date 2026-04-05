# Perspective agent — Snapshot du 5 avril 2026

> Ce document capture l'état de compréhension de l'agent (Claude Code) à un instant T du projet. Il fait partie de la dimension 2 du mémoire : la collaboration humain-agent comme objet d'étude.

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
