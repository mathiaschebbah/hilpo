"""Vocabulaire de signaux visuels pour la DSL MILPO.

Les signaux sont extraits des descriptions taxonomiques des formats visuels.
Chaque scope (FEED, REELS) a son propre vocabulaire fini.
"""

from __future__ import annotations

# ── Vocabulaire FEED — dérivé des 42 descriptions post_* ──────────────────
# Chaque signal correspond à un marqueur visuel observable dans les slides.

FEED_SIGNALS: dict[str, str] = {
    # Texte
    "texte_overlay_present": "texte éditorial visible sur l'image",
    "texte_overlay_absent": "aucun texte éditorial sur l'image",
    "texte_actualite": "texte d'actualité ou de news",
    "texte_dense": "paragraphes de texte dense, type article",
    "texte_editorial_gras": "titre en gras + sous-titre en normal overlay",
    "texte_citation_guillemets": "citation centrée avec guillemets décoratifs",
    "texte_liste_numerotee": "liste numérotée ou classement textuel",
    "texte_par_slide": "texte structuré répété sur chaque slide",
    # Logos
    "logo_views": "logo Views présent",
    "logo_specifique": "logo propriétaire (BLUEPRINT, REWIND, THROWBACK, 9 PIECES, MOODY)",
    "logo_marque": "logo de marque commerciale visible",
    "aucun_logo": "aucun logo visible",
    # Structure
    "carousel_structure": "carousel multi-slides avec structure éditoriale",
    "single_image": "post mono-image",
    "fond_couleur": "fond couleur uni ou texturé",
    "fond_photo_plein_cadre": "photo plein cadre en fond",
    "split_horizontal": "écran coupé en deux sections horizontales",
    "grille_captures_ecran": "grille de captures d'écran de films/séries",
    "frise_continue": "composition continue sur plusieurs slides (frise)",
    "fleche_swipe_opener": "flèche incitant à swiper sur la slide d'ouverture",
    "numerotation_rang": "numérotation ou rang comme principe organisateur",
    # Éléments visuels
    "chiffre_dominant": "chiffre/pourcentage/date visuellement dominant en grand",
    "calque_couleur": "calque de couleur semi-transparent sur l'image",
    "photo_portrait_shooting": "photo portrait de shooting exclusif",
    "annotation_fleche_ligne": "flèche/ligne/pastille pointant vers un élément de l'image",
    "zoom_circulaire_objet": "zoom circulaire sur un objet/accessoire",
    "montage_collage": "collage ou montage de plusieurs images",
    "recap_evenement": "récap photo/vidéo d'un événement couvert",
    "affiche_film": "affiche officielle de film",
    "pochette_album": "pochette d'album ou photo d'artiste avec infos musicales",
}

# ── Vocabulaire REELS — dérivé des descriptions reel_* ────────────────────

REELS_SIGNALS: dict[str, str] = {
    # Texte
    "texte_overlay_present": "texte éditorial visible sur la vidéo",
    "texte_overlay_absent": "aucun texte éditorial sur la vidéo",
    "texte_actualite": "texte d'actualité ou de news",
    "texte_citation_guillemets": "citation centrée avec guillemets décoratifs",
    # Logos
    "logo_views": "logo Views présent",
    "logo_specifique": "logo propriétaire (BLUEPRINT, etc.)",
    "aucun_logo": "aucun logo visible",
    # Audio/Vidéo
    "voix_off_narrative": "voix off narrative expliquant un sujet",
    "interview_face_camera": "interview face caméra, format assis",
    "montage_retrospectif": "montage rétrospectif avec dates/archives",
    "captation_live_evenement": "captation live ou montage d'un événement",
    "behind_the_scenes": "contenu coulisses, b-roll",
    "immersif_journee_avec": "format immersif suivant une personnalité",
    # Structure
    "chiffre_dominant": "chiffre/pourcentage visuellement dominant",
    "fond_couleur": "fond couleur uni ou texturé",
    "split_horizontal": "écran coupé en deux sections horizontales",
    "pochette_album": "pochette d'album ou photo artiste avec infos",
}


def get_signal_vocabulary(scope: str) -> dict[str, str]:
    """Retourne le vocabulaire {signal_name: description} pour un scope."""
    if scope == "FEED":
        return dict(FEED_SIGNALS)
    if scope == "REELS":
        return dict(REELS_SIGNALS)
    raise ValueError(f"Scope inconnu: {scope}")


def get_signal_names(scope: str) -> set[str]:
    """Retourne l'ensemble des noms de signaux pour un scope."""
    return set(get_signal_vocabulary(scope).keys())


def format_signal_vocabulary_for_prompt(scope: str) -> str:
    """Formate le vocabulaire pour injection dans un prompt LLM."""
    vocab = get_signal_vocabulary(scope)
    lines = [f"- `{name}` : {desc}" for name, desc in sorted(vocab.items())]
    return "\n".join(lines)
