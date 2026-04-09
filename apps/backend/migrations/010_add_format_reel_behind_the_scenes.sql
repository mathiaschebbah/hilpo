-- 010_add_format_reel_behind_the_scenes.sql
-- Ajoute le format visuel `reel_behind_the_scenes` à la taxonomie.
--
-- Reel montrant les coulisses d'une production, d'un shooting, d'un événement
-- ou d'une captation Views. Contenu b-roll, montage, captation live, sans
-- gabarit éditorial identifiable (opposé à reel_news ou reel_interview).
--
-- Description initiale minimale — à affiner via l'UI Taxonomy
-- (PATCH /v1/taxonomy/visual-formats/{id}) après observation du gabarit réel
-- sur les premières annotations.
--
-- Réversible : DELETE FROM visual_formats WHERE name = 'reel_behind_the_scenes';
-- (à ne lancer que si aucune annotation ne référence encore le format)

BEGIN;

INSERT INTO visual_formats (name, description)
VALUES (
    'reel_behind_the_scenes',
    'Reel coulisses : montage b-roll d''une production, d''un shooting, d''un événement ou d''une captation Views. Contenu brut ou faiblement monté sans gabarit éditorial identifiable, ni voix-off narrative dominante, ni interview formelle. Description à affiner après observation du gabarit récurrent.'
)
ON CONFLICT (name) DO NOTHING;

COMMIT;
