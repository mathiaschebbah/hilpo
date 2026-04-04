# Architecture

## Pipeline multi-agents

Chaque post passe par un pipeline d'agents ultra-spécialisés pour éviter le context rot :

```
Post → Router → détecte le type (FEED/REELS/STORY)
                 ↓
         ┌───────┼───────┐
         ↓       ↓       ↓
    Agent       Agent    Agent
   catégorie  visual_f  stratégie
   (scopé)    (scopé)   (scopé)
```

### Agents

1. **Router** : détecte le type de post et dispatch vers les agents scopés
2. **Agent catégorie** : classifie parmi les 15 catégories éditoriales
3. **Agent visual_format** : classifie parmi les 44 formats visuels
4. **Agent stratégie** : détermine Organic vs Brand Content

### Prompts scopés

Chaque agent a un prompt par type de post. Ex : `agent_categorie × REELS` a son propre prompt, optimisé indépendamment de `agent_categorie × FEED`. Cela permet :
- D'adapter les instructions au média (vidéo vs image)
- D'optimiser chaque prompt sur son sous-ensemble de données
- D'utiliser Qwen 3.5 en mode vidéo pour les Reels

### Flux d'annotation (Phase 1-2)

1. L'humain ouvre l'interface de swipe
2. Un post s'affiche avec les labels v0 (heuristique) pré-remplis
3. L'humain confirme ou corrige → annotation stockée
4. En parallèle (Phase 2+), les agents prédisent → prédictions stockées
5. Comparaison annotation vs prédictions → match calculé

### Boucle HILPO (Phase 3)

1. Tous les B=30 erreurs d'un agent, le rewriter se déclenche
2. Le rewriter reçoit le prompt actif + le batch d'erreurs
3. Il propose un nouveau prompt → stocké en draft
4. Évaluation passive sur les posts suivants
5. Si accuracy ≥ ancienne → promotion en actif, sinon → rejeté
