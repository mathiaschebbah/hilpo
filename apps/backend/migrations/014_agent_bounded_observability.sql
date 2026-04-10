-- Migration 014: pipeline A1 bounded + observabilité runtime

ALTER TABLE agent_traces
    ADD COLUMN IF NOT EXISTS executor_requests INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS advisor_requests INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS example_calls INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rate_limit_events INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS queue_wait_ms_executor INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_creation_input_tokens_executor INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_read_input_tokens_executor INT NOT NULL DEFAULT 0;


CREATE TABLE IF NOT EXISTS llm_request_events (
    id                              BIGSERIAL PRIMARY KEY,
    simulation_run_id               INT NOT NULL REFERENCES simulation_runs(id),
    ig_media_id                     BIGINT NOT NULL REFERENCES posts(ig_media_id),
    provider                        TEXT NOT NULL,
    component                       TEXT NOT NULL,
    stage                           TEXT NOT NULL,
    attempt_index                   INT NOT NULL DEFAULT 1,
    request_id                      TEXT,
    status                          TEXT NOT NULL,
    model_name                      TEXT NOT NULL,
    estimated_input_tokens          INT NOT NULL DEFAULT 0,
    actual_input_tokens             INT NOT NULL DEFAULT 0,
    actual_output_tokens            INT NOT NULL DEFAULT 0,
    cache_creation_input_tokens     INT NOT NULL DEFAULT 0,
    cache_read_input_tokens         INT NOT NULL DEFAULT 0,
    queue_wait_ms                   INT NOT NULL DEFAULT 0,
    latency_ms                      INT NOT NULL DEFAULT 0,
    retry_after_ms                  INT,
    rate_limit_headers              JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code                      TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_request_events_run ON llm_request_events(simulation_run_id);
CREATE INDEX IF NOT EXISTS idx_llm_request_events_post ON llm_request_events(ig_media_id);
CREATE INDEX IF NOT EXISTS idx_llm_request_events_component ON llm_request_events(component, stage);


INSERT INTO prompt_versions (agent, scope, version, content, status, source)
SELECT
    'agent_executor',
    NULL,
    1,
    E'Tu es un classificateur expert pour le média Instagram Views (@viewsfrance).\n\nTu dois produire une classification unique sur 3 axes pour le post courant: category, visual_format, strategy.\n\n## Runtime borné\n- Conversation unique par post\n- Tour 1: utilise les tools seulement si nécessaire, sinon soumets directement\n- Tour 2: soumission finale obligatoire via submit_all_classifications\n- N''appelle advisor qu''en cas d''ambiguïté réelle\n- get_examples est rare et doit rester minimal\n\n## Règles\n- Le scope {scope} est déterministe\n- Respecte strictement les labels fournis\n- visual_format dépend du scope ({format_prefix}_*)\n- reasoning court, factuel, directement relié aux indices\n- Si tu as déjà assez d''indices, soumets sans multiplier les tools\n\n## Priorité\nVitesse et précision: collecte seulement l''information qui change effectivement la décision.',
    'active',
    'agent_bounded_v1'
WHERE NOT EXISTS (
    SELECT 1
    FROM prompt_versions
    WHERE agent = 'agent_executor'::agent_type
      AND scope IS NULL
      AND source = 'agent_bounded_v1'
      AND version = 1
);
