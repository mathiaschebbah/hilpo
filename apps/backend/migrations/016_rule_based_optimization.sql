-- Migration 016: Infrastructure pour l'optimisation structurée à patches atomiques.
--
-- Ajoute les tables pour :
-- 1. prompt_skeletons : partie fixe du prompt (intro/rôle)
-- 2. prompt_rules : règles typées DSL ordonnées par position
-- 3. signal_vocabulary : vocabulaire fini de signaux visuels par scope
-- 4. dev_split_assignment : partition dev-opt / dev-holdout (70/30)
-- 5. optimization_steps : log de chaque step d'optimisation

BEGIN;

-- ── Enums ──────────────────────────────────────────────────────────────────

CREATE TYPE rule_op_type AS ENUM (
    'add_rule', 'remove_rule', 'replace_rule', 'reorder_rule'
);

CREATE TYPE dsl_rule_type AS ENUM (
    'signal_to_label', 'disambiguation', 'priority', 'fallback', 'caption_policy'
);

-- ── prompt_skeletons ───────────────────────────────────────────────────────
-- Partie fixe du prompt, extraite une fois du v0. Jamais modifiée par l'optimiseur.

CREATE TABLE prompt_skeletons (
    id      SERIAL PRIMARY KEY,
    agent   agent_type NOT NULL,
    scope   media_product_type,
    text    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Contrainte d'unicité pour (agent, scope) incluant les NULLs
-- PostgreSQL 15+ supporte NULLS NOT DISTINCT
CREATE UNIQUE INDEX idx_skeleton_agent_scope
    ON prompt_skeletons (agent, scope) NULLS NOT DISTINCT;

-- ── prompt_rules ───────────────────────────────────────────────────────────
-- Règles typées DSL liées à un prompt_version.
-- Le prompt complet = skeleton + rules ORDER BY position.

CREATE TABLE prompt_rules (
    id                  SERIAL PRIMARY KEY,
    prompt_version_id   INTEGER NOT NULL REFERENCES prompt_versions(id),
    agent               agent_type NOT NULL,
    scope               media_product_type,
    position            INTEGER NOT NULL,
    rule_type           dsl_rule_type NOT NULL,
    rule_data           JSONB NOT NULL,
    compiled_text       TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (prompt_version_id, position)
);

CREATE INDEX idx_prompt_rules_version ON prompt_rules (prompt_version_id);

-- ── signal_vocabulary ──────────────────────────────────────────────────────
-- Vocabulaire fini de signaux visuels par scope, extrait des descriptions.

CREATE TABLE signal_vocabulary (
    id              SERIAL PRIMARY KEY,
    scope           media_product_type NOT NULL,
    signal_name     VARCHAR(60) NOT NULL,
    description     TEXT,
    source          VARCHAR(30) NOT NULL DEFAULT 'auto_extracted',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scope, signal_name)
);

-- ── dev_split_assignment ───────────────────────────────────────────────────
-- Partition 70/30 des posts annotés en dev-opt / dev-holdout.
-- Créée une fois, déterministe (seed=42), réutilisée entre runs.

CREATE TABLE dev_split_assignment (
    ig_media_id     BIGINT PRIMARY KEY REFERENCES posts(ig_media_id),
    sub_split       VARCHAR(12) NOT NULL CHECK (sub_split IN ('dev_opt', 'dev_holdout')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── optimization_steps ─────────────────────────────────────────────────────
-- Log de chaque step d'optimisation structurée.

CREATE TABLE optimization_steps (
    id                      SERIAL PRIMARY KEY,
    simulation_run_id       INTEGER NOT NULL REFERENCES simulation_runs(id),
    step_number             INTEGER NOT NULL,
    pass_number             INTEGER NOT NULL DEFAULT 1,
    target_agent            agent_type NOT NULL,
    target_scope            media_product_type,
    -- Opération
    op_type                 rule_op_type,
    op_index                INTEGER,
    op_rule_type            dsl_rule_type,
    op_rule_data            JSONB,
    -- Critique du critic
    critique_text           TEXT NOT NULL,
    critique_target_index   INTEGER,
    -- Évaluation
    j_before                REAL NOT NULL,
    j_after                 REAL,
    accepted                BOOLEAN NOT NULL DEFAULT FALSE,
    -- Hash pour le tabu
    state_hash_before       VARCHAR(64) NOT NULL,
    state_hash_after        VARCHAR(64),
    tabu_hit                BOOLEAN NOT NULL DEFAULT FALSE,
    skipped_invalid         BOOLEAN NOT NULL DEFAULT FALSE,
    -- Références prompts
    incumbent_prompt_id     INTEGER NOT NULL REFERENCES prompt_versions(id),
    candidate_prompt_id     INTEGER REFERENCES prompt_versions(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_opt_steps_run ON optimization_steps (simulation_run_id, step_number);

COMMIT;
