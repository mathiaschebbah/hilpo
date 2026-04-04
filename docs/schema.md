# Schéma BDD

Fichier : [`apps/backend/migrations/001_initial_schema.sql`](../apps/backend/migrations/001_initial_schema.sql)

## Tables

| Table | Rôle |
|-------|------|
| `posts` | Posts Instagram bruts (import CSV) |
| `post_media` | Fichiers média individuels — images/vidéos, URLs GCS (import CSV) |
| `categories` | Lookup — 15 catégories éditoriales |
| `visual_formats` | Lookup — 44 formats visuels |
| `heuristic_labels` | Catégorisation v0 — heuristique imprécise (import CSV) |
| `sample_posts` | Échantillon 2000 posts + assignation dev/test par seed |
| `annotations` | Annotations humaines (corrections/validations) |
| `prompt_versions` | Prompts versionnés **par agent × scope** (type de post) |
| `predictions` | Prédictions par agent + match vs annotation humaine |
| `rewrite_logs` | Historique des réécritures de prompt (avant/après, raisonnement) |
| `api_calls` | Traçabilité complète des appels API (tokens, coût, latence) |
| `prompt_metrics` | Vue — accuracy agrégée par version de prompt × agent |

## Modèle multi-agents

Chaque agent a ses propres prompts, versionnés indépendamment et scopés par type de post :

```
prompt_versions.agent  = router | category | visual_format | strategy
prompt_versions.scope  = FEED | REELS | STORY | NULL (tous types)
```

Un seul prompt actif par combinaison `(agent, scope)` — index unique partiel.

## Contraintes clés

- `UNIQUE (agent, scope) WHERE status = 'active'` — un seul prompt actif par agent × scope
- `UNIQUE (ig_media_id, annotator)` — une annotation par post par annotateur
- `UNIQUE (parent_ig_media_id, media_order)` — ordre des médias dans un carousel
- `all_match GENERATED ALWAYS` — match global auto-calculé dans predictions
