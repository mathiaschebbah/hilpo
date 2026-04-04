# Projet

Mémoire de fin d'études de Mathias Chebbah (Master 1 MIAGE, Université Paris Dauphine), en alternance chez Views (média gen-z).
Système d'annotation agentique pour classifier des posts Instagram via une boucle humain-dans-la-boucle qui optimise itérativement le prompt du classificateur. Le système remplace une heuristique de classification v0 (imprécise) par une pipeline performante, applicable en production chez Views.

## Problématique

"Comment concevoir et évaluer une méthode de classification multimodale pour catégoriser des publications sur les réseaux sociaux ?"

## Hypothèse de recherche

L'optimisation itérative d'un prompt par confrontation avec un annotateur humain permet d'atteindre une performance de classification multimodale satisfaisante, sans fine-tuning, avec un coût computationnel et un volume de données réduits.

## Contraintes

- **Deadline** : 18 avril 2026
- **Livrable** : rapport de mémoire + code fonctionnel
- **Budget API** : financé par Views
- **État au 4 avril 2026** : infrastructure complète (backend FastAPI, frontend React, PostgreSQL, GCS, splits, échantillon 2000 posts). Prêt à annoter.
