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

### Dim 5 avril — Phase 2 : pipeline + baseline ✅
- ~~Architecture Phase 2~~ ✅ (descripteur + 3 classifieurs)
- ~~Package hilpo/ implémenté~~ ✅ (9 modules)
- ~~Pipeline E2E fonctionnel~~ ✅ (3/3 match premier test)
- ~~6 prompts v0 en BDD~~ ✅
- ~~Script baseline B0 async~~ ✅
- ~~B0 sur 437 posts test~~ ✅ (87.3% / 64.3% / 93.5%, $1.14)

### Lun 6 — Phase 3 : rewriter + annotation dev
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Implémenter rewriter.py + loop.py (simulation, pas live) |
| Après-midi (4h) | Annoter ~400-800 posts dev (rapide, pas d'attente modèle) |
| Soir (2h) | Lancer simulation HILPO sur les posts annotés → premiers résultats |

### Mar 7 — Annotation sprint
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter 400 posts dev |
| Après-midi (3h) | Annoter 400 posts dev |
| Soir (2h) | Relancer simulation avec plus de données → vérifier convergence |

### Mer 8 — Fin annotation + simulation finale
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Annoter derniers ~400 posts dev |
| Après-midi (2h) | Kappa intra-annotateur (re-swipe 50 posts à l'aveugle) |
| Après-midi (1h) | Simulation finale + éval vN sur test |
| Soir (2h) | Analyser résultats, ablations (rejouer avec B=1, 10, 50) |

### Jeu 9 — Métriques + figures
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Calculer toutes les métriques (F1, kappa, McNemar) |
| Après-midi (3h) | Courbe de convergence + tableaux + matrice de confusion |
| Soir (2h) | Commencer related work (2h d'écriture) |

### Ven 10 — Simulations + baselines
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Ablations batch size (B=1, 10, 30, 50) |
| Après-midi (3h) | Baseline B2 (few-shot) |
| Soir (2h) | Figures matplotlib/seaborn |

## Semaine 2 — Simulations + rédaction

### Sam 11 — Baselines + ablations
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Baselines B4-B5 (CLIP) si faisable |
| Après-midi (3h) | Ablation A5 (sans rollback) |
| Soir (2h) | Finaliser métriques + McNemar |

### Dim 12 — Rédaction : cadrage
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Introduction + problématique |
| Après-midi (3h) | Related work |
| Soir (2h) | Relecture |

### Lun 13 — Rédaction : méthode
| Créneau | Activité |
|---------|----------|
| Matin (3h) | Méthode + formalisation |
| Après-midi (3h) | Architecture + protocole expérimental |
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
| Lun 6 | 400-800 | 400-800 dev | Annotation pure (rapide) + simulation le soir |
| Mar 7 | 800 | 1200 dev | Annotation pure + simulation |
| Mer 8 | ~360 | ~1560 dev | Fin annotation + simulation finale + éval test |

Note : le split test (437) est déjà annoté. L'annotation dev est découplée de l'optimisation — on annote d'abord, on simule ensuite. Ablations triviales (rejouer avec différents B).

## Appels API estimés

| Poste | Appels |
|-------|--------|
| B0 baseline test (437 posts) | ~1 750 |
| Classification live dev (~1 560 posts) | ~6 240 |
| Rewriter (~50 triggers) | ~50 |
| Éval finale (test × vN) | ~1 750 |
| Simulations + ablations | ~3 000 |
| Baselines few-shot | ~800 |
| **Total** | **~13 590** |
