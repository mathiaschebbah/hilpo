-- MILPO — Migration 002 : infrastructure expérimentale
-- Corrige la reproductibilité, les splits, le match auto, et prépare les simulations.

-- =============================================================
-- 1. ORDRE DE PRÉSENTATION DÉTERMINISTE
-- =============================================================

ALTER TABLE sample_posts
    ADD COLUMN presentation_order INTEGER;

-- =============================================================
-- 2. TABLE SIMULATION RUNS (Phase D)
-- =============================================================

CREATE TABLE simulation_runs (
    id          SERIAL PRIMARY KEY,
    seed        SMALLINT NOT NULL,
    batch_size  INTEGER NOT NULL DEFAULT 30,
    config      JSONB NOT NULL DEFAULT '{}',
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Résultats
    final_accuracy_category      REAL,
    final_accuracy_visual_format REAL,
    final_accuracy_strategy      REAL,
    prompt_iterations            INTEGER,
    total_api_calls              INTEGER,
    total_cost_usd               REAL
);

-- =============================================================
-- 3. EXPERIMENT_ID SUR API_CALLS ET PREDICTIONS
-- =============================================================

ALTER TABLE api_calls
    ADD COLUMN simulation_run_id INTEGER REFERENCES simulation_runs(id);

ALTER TABLE predictions
    ADD COLUMN simulation_run_id INTEGER REFERENCES simulation_runs(id);

CREATE INDEX idx_api_calls_simulation ON api_calls (simulation_run_id);
CREATE INDEX idx_predictions_simulation ON predictions (simulation_run_id);

-- =============================================================
-- 4. TRIGGER MATCH AUTO SUR PREDICTIONS
-- =============================================================

-- Fonction qui calcule le match en comparant avec l'annotation humaine
CREATE OR REPLACE FUNCTION compute_prediction_match()
RETURNS TRIGGER AS $$
DECLARE
    ann_value TEXT;
BEGIN
    -- Chercher la valeur annotée correspondante pour cet agent × post
    CASE NEW.agent
        WHEN 'category' THEN
            SELECT c.name INTO ann_value
            FROM annotations a
            JOIN categories c ON c.id = a.category_id
            WHERE a.ig_media_id = NEW.ig_media_id
            LIMIT 1;
        WHEN 'visual_format' THEN
            SELECT vf.name INTO ann_value
            FROM annotations a
            JOIN visual_formats vf ON vf.id = a.visual_format_id
            WHERE a.ig_media_id = NEW.ig_media_id
            LIMIT 1;
        WHEN 'strategy' THEN
            SELECT a.strategy::text INTO ann_value
            FROM annotations a
            WHERE a.ig_media_id = NEW.ig_media_id
            LIMIT 1;
        ELSE
            ann_value := NULL;
    END CASE;

    -- Si pas d'annotation, match reste NULL
    IF ann_value IS NOT NULL THEN
        NEW.match := (NEW.predicted_value = ann_value);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prediction_match
    BEFORE INSERT OR UPDATE ON predictions
    FOR EACH ROW
    EXECUTE FUNCTION compute_prediction_match();

-- =============================================================
-- 5. VUE MISE À JOUR (inclut simulation_run_id)
-- =============================================================

DROP VIEW IF EXISTS prompt_metrics;

CREATE VIEW prompt_metrics AS
SELECT
    pv.id AS prompt_version_id,
    pv.agent,
    pv.scope,
    pv.version,
    pv.status,
    pv.created_at,
    p.simulation_run_id,
    COUNT(p.id) AS total_predictions,
    AVG(p.match::int) AS accuracy
FROM prompt_versions pv
LEFT JOIN predictions p ON p.prompt_version_id = pv.id
GROUP BY pv.id, pv.agent, pv.scope, pv.version, pv.status, pv.created_at, p.simulation_run_id
ORDER BY pv.agent, pv.scope, pv.version;
