-- 005_prompt_version_run_tracking.sql
-- Tracke l'origine des versions de prompt par run de simulation.

ALTER TABLE prompt_versions
    ADD COLUMN IF NOT EXISTS simulation_run_id INTEGER
    REFERENCES simulation_runs(id);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_simulation
    ON prompt_versions (simulation_run_id);

-- Unicité des versions à l'intérieur d'un run seulement.
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_version_unique_per_run
    ON prompt_versions (simulation_run_id, agent, scope, version) NULLS NOT DISTINCT
    WHERE simulation_run_id IS NOT NULL;
