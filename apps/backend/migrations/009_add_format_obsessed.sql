-- 009_add_format_obsessed.sql
-- Ajoute le format visuel `post_obsessed` à la taxonomie.
--
-- Format éditorial hebdomadaire "Obsessed" de Views : interview récurrente
-- avec un·e créateur·trice (photographe, journaliste, réalisateur·trice,
-- créateur·trice de contenu...) qui partage ses obsessions — objets,
-- références culturelles, inspirations.
--
-- Caption reconnaissable :
--   "Cette semaine sur Obsessed, on a discuté avec [X] pour qu'[il·elle] nous
--    parle de ses obsessions ✨"
--
-- Volume brut dataset : ~15 posts identifiés par ILIKE '%obsessed%' dans les
-- captions, dont quelques faux positifs (ex. "Steelbook Obsessed"). L'ordre
-- de grandeur réel attendu est ~10-14 posts.
--
-- La description ci-dessous est une première passe basée sur la caption de
-- référence ; à affiner via l'UI Taxonomy (PATCH /v1/taxonomy/visual-formats/{id})
-- une fois le gabarit visuel observé.
--
-- Réversible : DELETE FROM visual_formats WHERE name = 'post_obsessed';
-- (à ne lancer que si aucune annotation ne référence encore le format)

BEGIN;

INSERT INTO visual_formats (name, description)
VALUES (
    'post_obsessed',
    'Format éditorial hebdomadaire Obsessed de Views. Interview récurrente avec un·e créateur·trice (photographe, journaliste, réalisateur·trice, créateur·trice de contenu...) qui partage ses obsessions : objets, références culturelles, inspirations. Caption reconnaissable : "Cette semaine sur Obsessed, on a discuté avec [invité·e] pour qu''[il·elle] nous parle de ses obsessions". Description visuelle à affiner après observation du gabarit récurrent (portrait de l''invité·e + slides des obsessions).'
)
ON CONFLICT (name) DO NOTHING;

COMMIT;
