# Conventions

## Collaboration

- **AskUserQuestion intensif** : utiliser AskUserQuestion pour valider les choix, clarifier les ambiguïtés et confirmer les directions avant d'agir. Ne pas deviner, demander.
- **Français avec accents** : tout contenu en français (README, docs, commentaires, messages de commit) doit utiliser les accents corrects (é, è, à, ù, etc.). Toujours relire avant d'écrire un fichier.

## Hooks d'interaction

- **Hook Stop natif** ([`.claude/hooks/check-claude-md.py`](../.claude/hooks/check-claude-md.py)) : à chaque fin de tâche, l'agent analyse les changements, propose une mise à jour de CLAUDE.md via AskUserQuestion, et commite si l'humain valide. Hook natif Claude Code (pas hookify — cf. bug cascade PreToolUse).
