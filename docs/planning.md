# Planning — 4 au 18 avril 2026

> Deadline : **samedi 18 avril 2026**
> Principe : **les annotations passent toujours avant le code**

## Semaine 1 — Annotations + Phases 2-3

### Sam 4 avril — Infrastructure ✅
- ~~Structure monorepo~~ ✅
- ~~Schéma BDD~~ ✅
- ~~Backend FastAPI~~ ✅
- ~~Frontend React swipe~~ ✅
- ~~GCS URLs signées~~ ✅
- ~~Import CSV + splits~~ ✅
- ~~Test E2E~~ ✅

### Dim 5 avril — Annotation sprint 1
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 200 posts |
| Après-midi (3h) | Annoter 200 posts |
| Soir (2h) | Implémenter Phase 2 (API Qwen, prompt v0, logging) |

### Lun 6 — Annotation sprint 2 + Phase 2 live
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 200 posts |
| Après-midi (3h) | Annoter 200 posts + Phase 2 live |
| Soir (2h) | Debug Phase 2 + premier batch de prédictions |

### Mar 7 — Annotation sprint 3 + début rewriter
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 200 posts |
| Après-midi (3h) | Annoter 200 posts + implémenter rewriter |
| Soir (2h) | Rewriter : test sur erreurs accumulées |

### Mer 8 — Annotation sprint 4 + boucle HILPO
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 200 posts |
| Après-midi (3h) | Annoter 200 posts + boucle HILPO active |
| Soir (2h) | Vérifier prompt v1 généré, lancer éval |

### Jeu 9 — Fin annotation + kappa
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 200 posts + re-swipe 50 posts (kappa intra) |
| Après-midi (3h) | Derniers 200 posts (cumulé : 2000) |
| Soir (2h) | Éval prompt v0 vs vN sur split test (400 posts) |

### Ven 10 — Analyse des résultats
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Calculer toutes les métriques (F1, kappa, McNemar) |
| Après-midi (3h) | Courbe de convergence + tableaux |
| Soir (2h) | Commencer related work (2h d'écriture) |

## Semaine 2 — Simulations + rédaction

### Sam 11 — Simulations
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Script de simulation 5 splits × ablations |
| Après-midi (3h) | Suite simulations |
| Soir (2h) | Baselines B2 (few-shot) |

### Dim 12 — Baselines + ablations
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Baselines B4-B5 (CLIP) + ablation A5 |
| Après-midi (3h) | Finaliser métriques + McNemar |
| Soir (2h) | Figures matplotlib/seaborn |

### Lun 13 — Rédaction : cadrage
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Introduction + problématique + related work |
| Après-midi (3h) | Méthode + formalisation |
| Soir (2h) | Relecture méthode |

### Mar 14 — Rédaction : résultats
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Résultats (figures + tableaux) |
| Après-midi (3h) | Discussion |
| Soir (2h) | Relecture résultats |

### Mer 15 — Rédaction : discussion + abstract
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Discussion + limites + perspectives |
| Après-midi (3h) | Abstract + conclusion |
| Soir (2h) | Relecture complète |

### Jeu 16 — Polish
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Bibliographie + polish |
| Après-midi (3h) | Relecture finale |
| Soir (2h) | Buffer |

### Ven 17 — Derniers ajustements
- Corrections finales
- Vérification code reproductible

### Sam 18 — **Rendu**

## Annotation par jour

| Jour | Posts | Cumulé | Phase active |
|------|-------|--------|--------------|
| Dim 5 | 400 | 400 | Phase 1 seule |
| Lun 6 | 400 | 800 | Phase 1 → 2 |
| Mar 7 | 400 | 1200 | Phase 2 |
| Mer 8 | 400 | 1600 | Phase 2 → 3 |
| Jeu 9 | 400 | 2000 | Phase 3 |

## Appels API estimés

| Poste | Appels |
|-------|--------|
| Classification live | ~2000 |
| Rewriter | ~65 |
| Éval finale (test × v0 + vN) | ~800 |
| Simulations (30 runs × ~65) | ~1950 |
| Baselines few-shot | ~800 |
| **Total** | **~5615** |
