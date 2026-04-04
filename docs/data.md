# Donnees

## Source

Posts Instagram @viewsfrance — 2000 posts a classifier.

## Fichiers disponibles

- `core_posts_rows.csv` — posts (ig_media_id, shortcode, ig_user_id, caption, timestamp, media_type, media_product_type, followed_post, suspected, authors_checked, inserted_at, boosted_post)
- `core_post_categories_rows.csv` — categories (ig_media_id, category, subcategory, strategy, visual_format)
- Donnees pas encore completes, a analyser une fois toutes deposees

## Axes de classification

- **Template visuel** : 20 classes (templates PSD) → liste a documenter
- **Categorie editoriale** : 15 classes → liste a documenter
- **Type** : brand vs organique (colonne `strategy` dans le CSV categories)

## Splits

- 5 splits aleatoires stratifies (seeds 1-5)
- 1600 dev / 400 test (80/20)
- Stratification sur template × brand (40 strates)
