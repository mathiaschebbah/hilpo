"""Configuration du moteur MILPO — charge .env automatiquement."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Cherche .env à la racine du projet, puis dans apps/backend/
_project_root = Path(__file__).resolve().parent.parent
for _env_path in [_project_root / ".env", _project_root / "apps" / "backend" / ".env"]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# OpenRouter
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modèles
#
# Descripteurs : Gemini 3.1 Flash Lite — analyse textuelle libre (plus de JSON structuré).
MODEL_DESCRIPTOR_FEED = "google/gemini-3.1-flash-lite-preview"
MODEL_DESCRIPTOR_REELS = "google/gemini-3.1-flash-lite-preview"

# Classifieurs : Qwen 3.5 Flash text-only via tool calling forcé
# (cf. commit 0b3bd8b — fix après bug json_schema strict sur enums binaires).
MODEL_CLASSIFIER = "qwen/qwen3.5-flash-02-23"

MODEL_REWRITER = os.environ.get("HILPO_MODEL_REWRITER", "openai/gpt-5.4")

# Modèles pour la boucle ProTeGi (mode --mode protegi).
# Par défaut tous = MODEL_REWRITER pour isoler l'effet de la décomposition
# algorithmique (critic / editor / paraphraser séparés) de l'effet d'un mélange
# de modèles. Surchargeable via env vars pour ablations.
MODEL_CRITIC = os.environ.get("HILPO_MODEL_CRITIC", MODEL_REWRITER)
MODEL_EDITOR = os.environ.get("HILPO_MODEL_EDITOR", MODEL_REWRITER)
MODEL_PARAPHRASER = os.environ.get("HILPO_MODEL_PARAPHRASER", MODEL_REWRITER)

# GCS
GCS_SIGNING_SA_EMAIL = os.environ.get("HILPO_GCS_SIGNING_SA_EMAIL", "")

# BDD
DATABASE_DSN = os.environ.get(
    "HILPO_DATABASE_DSN",
    "postgresql://hilpo:hilpo@localhost:5433/hilpo",
)
