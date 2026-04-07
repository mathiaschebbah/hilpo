"""Schemas Pydantic pour le pipeline MILPO."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class StrictBaseModel(BaseModel):
    """Base model avec schéma strict pour les structured outputs."""

    model_config = ConfigDict(extra="forbid")


# ── Features extraites par le descripteur ──────────────────────


class TexteOverlay(StrictBaseModel):
    present: bool
    type: str | None  # actualite, citation, chiffre, titre_editorial, liste_numerotee, annotation, description_produit
    contenu_resume: str | None


class Logos(StrictBaseModel):
    views: bool
    specifique: str | None  # BLUEPRINT, MOODY_MONDAY, MOODY_SUNDAY, REWIND, 9_PIECES, THROWBACK, VIEWS_ESSENTIALS, VIEWS_RESEARCH, VIEWS_TV
    marque_partenaire: str | None


class MiseEnPage(StrictBaseModel):
    fond: str | None  # photo_plein_cadre, couleur_unie, texture, collage, split_screen
    nombre_slides: int
    structure: str | None  # slide_unique, gabarit_repete, opener_contenu_closer, collage_grille


class ContenuPrincipal(StrictBaseModel):
    personnes_visibles: bool
    type_personne: str | None  # artiste, athlete, personnalite, anonyme
    screenshots_film: bool
    pochettes_album: bool
    zoom_objet: bool
    photos_evenement: bool


class AudioVideo(StrictBaseModel):
    voix_off_narrative: bool
    interview_face_camera: bool
    musique_dominante: bool
    type_montage: str | None  # captation_live, montage_edite, face_camera, b_roll_narration


class AnalyseCaption(StrictBaseModel):
    longueur: int
    mentions_marques: list[str]
    hashtags_format: str | None
    mention_partenariat: bool
    sujet_resume: str | None


class IndicesBrandContent(StrictBaseModel):
    produit_mis_en_avant: bool
    mention_partenariat_caption: bool
    logo_marque_commerciale: bool


class DescriptorFeatures(StrictBaseModel):
    """Output structuré du descripteur multimodal."""

    resume_visuel: str
    texte_overlay: TexteOverlay
    logos: Logos
    mise_en_page: MiseEnPage
    contenu_principal: ContenuPrincipal
    audio_video: AudioVideo
    analyse_caption: AnalyseCaption
    indices_brand_content: IndicesBrandContent


# ── Résultat de classification d'un post ───────────────────────


class PostPrediction(StrictBaseModel):
    """Prédictions pour un post (3 axes)."""

    ig_media_id: int
    category: str
    visual_format: str
    strategy: str
    features: DescriptorFeatures


class RewritePayload(StrictBaseModel):
    """Payload structuré attendu du rewriter."""

    reasoning: str
    new_instructions: str

    @field_validator("reasoning", "new_instructions")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


def build_json_schema_response_format(name: str, schema: dict) -> dict:
    """Construit un response_format json_schema strict pour chat.completions."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def build_classifier_response_schema(labels: list[str]) -> dict:
    """Schéma strict (label + confidence) pour un classifieur MILPO.

    Réutilisé par build_classifier_tool() pour les paramètres du tool function.
    """

    return {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "enum": labels,
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": ["label", "confidence"],
        "additionalProperties": False,
    }


def build_classifier_tool(axis: str, labels: list[str]) -> dict:
    """Construit la définition tool/function pour un classifieur MILPO.

    On utilise l'API tool calling (function calling) plutôt que
    response_format=json_schema parce que tool calling est universellement
    supporté par tous les providers OpenRouter, alors que json_schema strict
    n'est pas honoré par certains providers (notamment Qwen 3.5 Flash sur
    les enums binaires : il renvoie un float au lieu d'un objet).
    """

    return {
        "type": "function",
        "function": {
            "name": f"classify_{axis}",
            "description": f"Classifie le post sur l'axe '{axis}'.",
            "parameters": build_classifier_response_schema(labels),
        },
    }


class ClassifierDecision(StrictBaseModel):
    """Décision structurée d'un classifieur (label + confidence).

    Utilisée pour valider les arguments parsés depuis tool_call.function.arguments.
    """

    label: str
    confidence: Literal["high", "medium", "low"]
