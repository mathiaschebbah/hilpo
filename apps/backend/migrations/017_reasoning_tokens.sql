-- Migration 017: colonne reasoning_tokens sur api_calls.
--
-- Gemini (via endpoint OpenAI-compatible) facture les reasoning tokens
-- au tarif output mais ne les compte PAS dans usage.completion_tokens.
-- On veut les logger séparément pour l'analyse post-run :
--   - cost: output_tokens = reasoning + completion visible (déjà corrigé v5.3)
--   - analyse: combien de tokens dépensés en CoT vs en réponse visible
--
-- Runs historiques (1-119) : reasoning_tokens = 0 par défaut (donnée perdue).

BEGIN;

ALTER TABLE api_calls
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN api_calls.reasoning_tokens IS
    'Tokens de chain-of-thought interne (inclus dans output_tokens pour le cost, exposés ici pour analyse). Gemini : total - prompt - completion visible. 0 pour les runs historiques antérieurs à v5.3.';

COMMIT;
