"""Cache d'évaluation déterministe pour l'optimisation structurée MILPO.

Rend J déterministe en cachant les prédictions par
(post_id, axis, prompt_hash, scope, model).
Même post + même prompt → même prédiction, éliminant le bruit LLM
de la décision accept/reject.
"""

from __future__ import annotations

import hashlib


class EvalCache:
    """Cache les prédictions de classification pour le déterminisme de J."""

    def __init__(self) -> None:
        self._cache: dict[tuple[int, str, str, str, str], str] = {}
        self._hits = 0
        self._misses = 0

    def _key(
        self,
        post_id: int,
        axis: str,
        prompt_hash: str,
        scope: str,
        model: str,
    ) -> tuple[int, str, str, str, str]:
        return (post_id, axis, prompt_hash, scope, model)

    def get(
        self,
        post_id: int,
        axis: str,
        prompt_hash: str,
        scope: str,
        model: str,
    ) -> str | None:
        """Retourne la prédiction cachée ou None si absente."""
        key = self._key(post_id, axis, prompt_hash, scope, model)
        result = self._cache.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def put(
        self,
        post_id: int,
        axis: str,
        prompt_hash: str,
        scope: str,
        model: str,
        prediction: str,
    ) -> None:
        """Enregistre une prédiction dans le cache."""
        key = self._key(post_id, axis, prompt_hash, scope, model)
        self._cache[key] = prediction

    def has(
        self,
        post_id: int,
        axis: str,
        prompt_hash: str,
        scope: str,
        model: str,
    ) -> bool:
        """Vérifie si une prédiction est dans le cache sans compter les stats."""
        return self._key(post_id, axis, prompt_hash, scope, model) in self._cache

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def size(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0


def prompt_hash(rendered_prompt: str) -> str:
    """Hash déterministe d'un prompt rendu pour le cache."""
    return hashlib.sha256(rendered_prompt.encode()).hexdigest()[:16]
