# Données

## Source

21 425 posts Instagram en BDD (21 065 @viewsfrance + 360 @miramagazine). L'échantillon de 2 000 posts est filtré sur **@viewsfrance uniquement** (ig_user_id = 17841403755827826).

## Fichiers (dans data/, gitignored)

| Fichier | Lignes | Description |
|---------|--------|-------------|
| `core_posts_rows.csv` | 21 425 | Posts (ig_media_id, shortcode, caption, timestamp, media_type, media_product_type, ...) |
| `core_post_categories_rows.csv` | 19 353 | Catégorisation heuristique v0 (category, subcategory, strategy, visual_format) |
| `core_post_media_rows.csv` | 84 019 | Médias individuels (URLs GCS, dimensions, durée, position dans le carousel) |

## Relations

```
core_posts.ig_media_id  ←1:1→  core_post_categories.ig_media_id
core_posts.ig_media_id  ←1:N→  core_post_media.parent_ig_media_id
```

- 2 072 posts sans catégorisation, 2 posts sans média
- En moyenne ~4 médias par post (carousels)

## Heuristique v0

Les catégories du CSV proviennent d'une pipeline de classification précédente construite par Mathias chez Views. Cette heuristique est **imprécise et incomplète**. MILPO vise à la remplacer par une pipeline performante et applicable en production.

L'interface d'annotation pré-remplira les catégories v0 — l'humain confirme ou corrige.

## Axes de classification

- **Format visuel** : 68 classes en BDD, scopées par `media_product_type` :
  - `post_*` : 44 formats (FEED)
  - `reel_*` : 16 formats (REELS)
  - `story_*` : 8 formats (STORY)
  - 68/68 formats ont une description textuelle (critère visuel discriminant pour chaque format)
  - Note : le CSV d'origine contenait 45 formats (38 post + 7 reel). Évolutions pendant l'annotation documentées ci-dessous.
- **Catégorie éditoriale** : 15 classes (mode, musique, sport, cinéma, société, art_culture, photographie, people, architecture_design, technologie, voyages, lifestyle, business, histoire, gastronomie)
- **Stratégie** : 2 classes (Organic, Brand Content)

## Splits

- Échantillon actif : 2 000 posts (seed=42), split 1 563 dev / 437 test (~78/22)
- Stratification sur `media_product_type`

## Distribution du dataset

La distribution des formats visuels suit une **loi de puissance** : 8 formats couvrent 82% du dataset, 19 formats ont ≤ 1 occurrence dans le test.

| Tranche | Formats | % du test |
|---------|---------|-----------|
| > 10 posts | 8 formats | 81.7% |
| 2-10 posts | 16 formats | 13.3% |
| 1 seul post | 19 formats | 4.3% |

Le split test **préserve fidèlement** la distribution du dataset complet (20K posts) — les écarts de proportion sont < 4% pour tous les formats.

### Points notables

- **post_news domine** : 34% du test (37.8% du dataset complet)
- **Brand Content** : 9.4% du test — déséquilibré mais reflète la réalité du feed Views
- **0 stories** dans le test — trop rares (3% du dataset total, non échantillonnées)
- **16 formats uniquement dans test** (absents du dev) — tous à 1-2 occurrences. Sert de test de transfert zero-shot via descriptions.
- **2 catégories absentes** du test : nourriture, humour (trop rares)

### Implications méthodologiques

Le F1 macro sera reporté **avec et sans les classes rares** (< 5 occurrences) pour isoler l'effet de la longue traîne. Ce n'est pas un biais d'échantillonnage — c'est la distribution réelle du dataset. C'est un argument pour MILPO : les méthodes supervisées échouent sur la longue traîne (pas d'exemples), MILPO peut classifier via les descriptions taxonomiques.

## Travail sur la taxonomie — Observations d'annotation

La taxonomie a évolué pendant l'annotation au contact des données réelles. Ce travail itératif est documenté ici car il informe directement la qualité des descriptions injectées dans le prompt MILPO (Δ^m).

### Fusions réalisées

| Avant | Après | Raison |
|-------|-------|--------|
| `post_edito_photo` | → `post_mood` | La distinction n'existait pas en pratique chez Views. Les deux formats = photos sans texte sur l'image. La description interne Views confirme : "photos esthétiques avec des visuels forts, sans texte". |
| `post_retour_en_images` | → `post_wrap_up` | Même gabarit visuel (recap événement). La distinction organic/brand est capturée par l'axe stratégie, pas le format visuel. |
| `reel_evenement` | → `reel_wrap_up` | Idem — captation live et montage post-événement fusionnés. |

### Formats ajoutés pendant l'annotation

| Format | Raison |
|--------|--------|
| `reel_throwback` | Reels anniversaire/hommage distincts de `reel_deces` (info décès) |
| `post_views_magazine` / `reel_views_magazine` / `story_views_magazine` | Promotion du magazine papier Views |
| `reel_mood` | Équivalent reel du post_mood |
| `post_views_tv` | Promotion de contenus Views TV (documentaires YouTube) |
| `reel_blueprint` | Interviews exclusives Views, identifiables par le logo Blueprint |

### Critères discriminants clarifiés

**Le format visuel se détermine par ce qu'on voit SUR l'image, pas par la caption.**

| Critère | Format |
|---------|--------|
| Aucun texte, aucun overlay, pas de logo → | `post_mood` |
| Texte d'actualité en overlay + logo Views → | `post_news` |
| Gabarit structuré avec texte sur chaque slide → | `post_selection` |
| Texte dense type article + fond couleur → | `post_article` |
| Photo + texte gras/normal en overlay + logo → | `post_serie_mood_texte` |

**Exception :** les `post_news` anciens (2018-2020) n'ont pas de texte sur l'image — la news est uniquement dans la caption. La description couvre les deux versions (récente avec overlay, ancienne sans). Le modèle utilise la caption comme signal complémentaire pour ces cas.

### Évolution temporelle des captions

L'analyse des `post_mood` révèle une évolution nette de la longueur des captions :

| Période | Caption moyenne | Style |
|---------|:---------:|-------|
| 2018-2020 | ~160 chars | "Mood. 📸" — vibe pur |
| 2021-2023 | ~410 chars | Description éditoriale courte |
| 2024-2025 | ~890 chars | Mini-articles, contexte détaillé |

Le format visuel reste identique (photos sans texte), mais la stratégie de caption a évolué vers du contenu plus éditorial. **La longueur de caption n'est pas un critère de format visuel** — un post_mood avec 900 caractères de caption reste un post_mood si l'image n'a pas de texte.

### Formats à 0 occurrence dans le sample

8 formats POST et 3 formats REEL existent dans la taxonomie mais n'apparaissent pas dans l'échantillon de 2000 posts. Ils ont été vérifiés visuellement sur le feed Instagram Views :

| Format | Vérifié | Source |
|--------|---------|--------|
| `post_rewind` | ✅ | Posts de décembre 2023/2024, logo REWIND |
| `post_blueprint` | ✅ | Identifiable par "Blueprint" dans la caption |
| `post_views_research` | ✅ | Études menées par Views ("notre étude sur la mode et l'écologie") |
| `post_objets` | ✅ | PSD interne octobre 2025, zoom circulaire sur accessoire |
| `post_ourviews` | ✅ | Format historique 2016-2017, #ourviews |
| `reel_blueprint` | ✅ | ~10 reels identifiés par caption |
| `reel_deces` | ✅ | Version reel de post_deces |
| `reel_double_selection` | ✅ | Version reel de post_double_selection |

Ces formats servent de test de **transfert zero-shot** : le modèle devra les classifier uniquement via leur description textuelle, sans avoir vu d'exemple pendant l'optimisation.
