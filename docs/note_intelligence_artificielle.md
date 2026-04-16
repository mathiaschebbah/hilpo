VERSION 2.0

# Note sur l'utilisation de l'Intelligence Artificielle

## 1. Outils utilisés

Ce projet a été construit en utilisant les agents de code Claude Code et Codex.
Ces agents ont contribué à l'architecture, la conception des pipelines et l'écriture du code.

### 1.1 Observations concernant la pertinence des agents

Qualitativement, durant le travail de création de la pipeline, j'ai observé les patterns suivants.

- Lorsque l'utilisateur est profane sur le sujet, l'agent (en particulier Claude Code) a tendance à surestimer les idées de ce dernier. On parle de "Claude's psychosis" ([voir l'exemple sur X/Twitter](https://x.com/banteg/status/2041446845721854401)). Ce phénomène est assez répandu et documenté sur X. En résumé : Claude encense les idées de l'utilisateur, en créant un univers autour d'une idée assez simple.
- Je suspecte ce projet d'être victime de ce phénomène. En effet, ce projet est né d'un besoin réel chez Views, et la problématique a été actée en décembre 2025. Pour autant, l'agent a inventé un nom (initialement Human In The Loop Prompt Optimization), affirmé que cette méthodologie était **complètement novatrice** (on a vu plus tard qu'un papier de 2023 introduisait le concept de SGD pour les prompts. J'ai décidé de garder cette filiation, et proposer de l'étendre aux données multimodales. On observe que DSPy est un concurrent sérieux de solution au problème que l'on tente de résoudre, et nous comparerons notre approche avec la leur).
- Lorsque qu'un projet se construit sans une planification avancée de la part de l'humain, l'intelligence artificielle a tendance a proposer une architecture **qui paraît correcte**, mais qui infine, . Le principal écueil est le manque de plannification humaine. Une plannification plus poussée de ma part aurait permis de construire le projet plus proprement, avec des contributions de l'agent plus utiles.
- Je constate toutefois que le modèle m'a permis d'obtenir des pistes dont je n'avais pas connaissance auparavant. Ce qui aurait pris des jours de recherche sur des moteurs de recherche classiques ont été générés en drastiquement moins de temps. À mon sens, ces agents sont le plus pertiennts lorsque l'on les utilise afin d'acquérir le glossaire technique d'une solution. Demander à de tels agents de produire une idée novatrice n'est, pas encore, pertinent, mais les utiliser comme réellement un moteur de langage, capable de nous familiariser avec le vocabulaire d'une solution technique est un levier très puissant. En cela, je suis convaincu qu'utiliser de tels modèles pour produire un rendu universitaire est utile, car infine il fait progresser l'étudiant, sous réserve que ce dernier soit capable de produire une réflexion critique sur ce que les tokens de sortie du modèle produisent sémantiquement.

## 1.2 Sur le contexte-engineering des agents

- Garder un CLAUDE.md propre, court, concis et qui est rempli par humain aide drastiquement l'agent à connaître le projet. De plus, j'ai construit un skill /setup, qui permet en début de session de générer le contexte favorable à ce que l'agent puisse être utile dans la production de ses messages. Il inclut les commandes bash à exécuter pour requêter la base de données locale, les commandes ls à exécuter pour connaître l'arborescence du projet, et comprendre la structure. Garder un versionnement du CLAUDE.md aide également l'agent à connaître les différentes étapes qui ont fait grandir le projet, et de ne pas reproduire certains écueils.

Je renderais plus tard à disposition les traces des agents au format .jsonl et fournirais une analyse plus détaillée, de mes sessions d'agents.