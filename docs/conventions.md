# Conventions

## Collaboration

- **AskUserQuestion intensif** : utiliser AskUserQuestion pour valider les choix, clarifier les ambiguïtés et confirmer les directions avant d'agir. Ne pas deviner, demander.
- **Français avec accents** : tout contenu en français (README, docs, commentaires, messages de commit) doit utiliser les accents corrects (é, è, à, ù, etc.). Toujours relire avant d'écrire un fichier.

## API REST

- Endpoints versionnés sous `/v1/`
- POST retourne `201 Created` + header `Location`
- Exceptions custom + handler global (pas de try/catch dans les routers)

## Typographie frontend

- Pas de `font-mono` sur les labels UI — mono réservé aux données numériques (compteurs, pourcentages)
- Taille minimum `text-[11px]` pour les métadonnées, `text-xs` (12px) pour les labels, `text-sm` (14px) pour les contrôles
- Pas de `uppercase tracking-wider` sur les labels de formulaire
- `max-w-prose` sur les blocs de texte (caption)
- `tabular-nums` uniquement sur les données numériques alignées

## Hooks d'interaction

- **Hook PreToolUse sur git commit** ([`.claude/hooks/check-claude-md.py`](../.claude/hooks/check-claude-md.py)) : avant chaque `git commit`, l'agent analyse les changements, propose une mise à jour de CLAUDE.md via AskUserQuestion, et inclut les docs dans le commit si l'humain valide. Les commits `docs: update CLAUDE.md` passent sans blocage (évite la boucle infinie).
