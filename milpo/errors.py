"""Exceptions métier du moteur MILPO."""


class LLMCallError(RuntimeError):
    """Erreur d'appel LLM après épuisement des retries."""

