# Architecture

## Agents

1. **Classificateur** : image → modele vision + prompt actif en BDD → prediction
2. **Rewriter** : prompt actuel + batch d'erreurs (tous les 30 posts) → nouveau prompt propose
3. **Evaluateur passif** : evalue le nouveau prompt sur les N posts suivants annotes par l'humain (pas de rejeu couteux des anciens)

## Flux

1. L'humain swipe un post dans l'interface
2. Le classificateur predit en parallele avec le prompt actif
3. L'humain confirme ou corrige → annotation stockee
4. Tous les B=30 erreurs, le rewriter propose un nouveau prompt
5. Le nouveau prompt est active si sa precision ne regresse pas sur les posts suivants
