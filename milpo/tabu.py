"""Liste tabou pour l'optimisation structurée MILPO.

Empêche de revisiter un état de règles déjà évalué pour un slot donné.
Invalidée entre les passes de coordinate ascent pour permettre la
ré-exploration après changement d'un autre slot.
"""

from __future__ import annotations

from collections import defaultdict


class TabuList:
    """Tracks visited RuleState hashes per slot to prevent cycles."""

    def __init__(self) -> None:
        self._visited: dict[str, set[str]] = defaultdict(set)

    def is_tabu(self, slot_key: str, state_hash: str) -> bool:
        """Vérifie si un état a déjà été visité pour ce slot."""
        return state_hash in self._visited[slot_key]

    def add(self, slot_key: str, state_hash: str) -> None:
        """Enregistre un état comme visité pour ce slot."""
        self._visited[slot_key].add(state_hash)

    def invalidate_all(self) -> None:
        """Vide toutes les listes tabou (entre passes coordinate ascent)."""
        self._visited.clear()

    def invalidate_slot(self, slot_key: str) -> None:
        """Vide la liste tabou d'un slot spécifique."""
        self._visited.pop(slot_key, None)

    def size(self, slot_key: str) -> int:
        """Nombre d'états visités pour un slot."""
        return len(self._visited.get(slot_key, set()))

    def total_size(self) -> int:
        """Nombre total d'états visités tous slots confondus."""
        return sum(len(v) for v in self._visited.values())
