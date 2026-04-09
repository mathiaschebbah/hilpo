-- 008_protegi_loop.sql
-- Tables additionnelles pour la boucle ProTeGi (mode --mode protegi du run_simulation).
--
-- Référence : Pryzant et al. 2023 (EMNLP), "Automatic Prompt Optimization with
-- Gradient Descent and Beam Search", arxiv 2305.03495.
--
-- Ne touche AUCUNE table existante. rewrite_logs reste utilisé tel quel : pour un
-- step protegi, on insère 1 row dans rewrite_logs pour le winner du Successive
-- Rejects, ce qui préserve la sémantique « 1 rewrite_log = 1 promotion attempt »
-- et la compatibilité avec les dashboards.
--
-- Ajoute :
--   * rewrite_gradients          — 1 row par appel critic (LLM_∇)
--   * rewrite_beam_candidates    — 1 row par candidat évalué (edit ou paraphrase)
--   * generation_kind enum       — 'edit' | 'paraphrase'
--
-- Réversible :
--   DROP TABLE IF EXISTS rewrite_beam_candidates;
--   DROP TABLE IF EXISTS rewrite_gradients;
--   DROP TYPE IF EXISTS generation_kind;

BEGIN;

-- ── Enum pour le type de génération d'un candidat ────────────────────────────

CREATE TYPE generation_kind AS ENUM ('edit', 'paraphrase');

-- ── rewrite_gradients : trace du LLM_∇ (critic) ──────────────────────────────
-- Une row par appel au critic. gradient_text contient les m critiques séparées
-- par double newline ; n_critiques permet de retrouver m sans reparser.

CREATE TABLE rewrite_gradients (
    id                  SERIAL PRIMARY KEY,
    simulation_run_id   INTEGER NOT NULL REFERENCES simulation_runs(id),
    iteration           INTEGER NOT NULL,
    target_agent        agent_type NOT NULL,
    target_scope        media_product_type,
    prompt_id           INTEGER NOT NULL REFERENCES prompt_versions(id),
    gradient_text       TEXT NOT NULL,
    n_critiques         INTEGER NOT NULL,
    model               TEXT NOT NULL,
    input_tokens        INTEGER NOT NULL,
    output_tokens       INTEGER NOT NULL,
    latency_ms          INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_gradients_run ON rewrite_gradients (simulation_run_id, iteration);

-- ── rewrite_beam_candidates : un row par candidat dans le beam ──────────────
-- Pour chaque step protegi : c rows kind='edit' (issus de LLM_δ) puis
-- éventuellement c·(p-1) rows kind='paraphrase' (issus de LLM_mc).
-- Tous les candidats sont évalués via multi_evaluate puis classés par
-- Successive Rejects. Le winner a is_winner=TRUE et sr_phase IS NULL ;
-- les autres ont sr_eliminated=TRUE et sr_phase = phase d'élimination.

CREATE TABLE rewrite_beam_candidates (
    id                    SERIAL PRIMARY KEY,
    simulation_run_id     INTEGER NOT NULL REFERENCES simulation_runs(id),
    iteration             INTEGER NOT NULL,
    target_agent          agent_type NOT NULL,
    target_scope          media_product_type,
    parent_prompt_id      INTEGER NOT NULL REFERENCES prompt_versions(id),
    candidate_prompt_id   INTEGER NOT NULL REFERENCES prompt_versions(id),
    gradient_id           INTEGER NOT NULL REFERENCES rewrite_gradients(id),
    generation_kind       generation_kind NOT NULL,
    -- Évaluation (NULL avant multi_evaluate)
    eval_accuracy         REAL,
    eval_sample_size      INTEGER,
    -- Successive Rejects (NULL avant SR ; phase=NULL ⇒ winner)
    sr_phase              INTEGER,
    sr_eliminated         BOOLEAN NOT NULL DEFAULT FALSE,
    is_winner             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_beam_candidates_run
    ON rewrite_beam_candidates (simulation_run_id, iteration);
CREATE INDEX idx_beam_candidates_gradient
    ON rewrite_beam_candidates (gradient_id);

COMMIT;
