# HILPO — Human-In-the-Loop Prompt Optimization

Dépôt associé au mémoire de Mathias CHEBBAH, Master 1 MIAGE, Université Paris Dauphine.

## Contexte

Dans le cadre d'une alternance chez Views, ce projet répond au besoin de classifier automatiquement des publications Instagram multimodales (image + légende) selon trois axes : le template visuel, la catégorie éditoriale et le type de contenu (brand ou organique).

**Problématique** : Comment concevoir et évaluer une méthode de classification multimodale pour catégoriser des publications sur les réseaux sociaux ?

## Méthode

Nous proposons HILPO, une méthode d'optimisation itérative de prompts par boucle humain-dans-la-boucle. Un annotateur humain classe d'abord les publications via une interface de swipe, puis un script rejoue les annotations dans l'ordre de présentation et simule la boucle d'optimisation (protocole prequential). Lorsque le modèle se trompe, un agent rewriter analyse les erreurs accumulées et propose une nouvelle version du prompt, stockée et versionnée en base de données.

L'hypothèse est que cette boucle d'optimisation permet d'atteindre une performance de classification satisfaisante sans recourir au fine-tuning, avec un volume d'annotations réduit et un artefact interprétable : le prompt optimisé.

## Collaboration Agent-Humain

Ce projet est également une expérimentation de collaboration entre un agent IA (Claude Code) et un humain pour un travail de recherche. L'intégralité du développement — de la conception architecturale à l'implémentation — est réalisée en binôme agent-humain, avec des mécanismes d'interaction structurés (hooks, validations humaines, versionnement de la documentation). La progression est traçable dans l'historique git.

Les mécanismes d'interaction sont définis dans [`.claude/hooks/`](.claude/hooks/) et documentés dans [`docs/conventions.md`](docs/conventions.md).

## Reproduction

Voir [`REPRODUCE.md`](REPRODUCE.md) pour le guide de reproduction de l'état actuel des résultats et du protocole expérimental visé.

## Licence

Ce dépôt est publié à des fins académiques.
