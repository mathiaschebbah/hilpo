"""Exceptions métier du moteur HILPO."""


class LLMCallError(RuntimeError):
    """Erreur d'appel LLM après épuisement des retries."""

