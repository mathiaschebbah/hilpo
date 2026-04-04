# Schema BDD

## Tables prevues

- `posts` : image_path, caption, metadata, split (dev/test)
- `templates` : 20 classes (lookup)
- `categories` : 15 classes (lookup)
- `annotations` : label humain + prediction modele, colonnes match auto-calculees
- `prompt_versions` : contenu, status (draft/active/retired), accuracy par axe
- `rewrite_logs` : prompt avant/apres, batch d'erreurs, raisonnement du rewriter
- `api_calls` : tokens, cout, latence, type d'appel — tracabilite complete

## Contraintes cles

- Un seul prompt actif a la fois (index unique partiel)
- Colonnes match auto-calculees (GENERATED ALWAYS)
- Vue SQL `prompt_metrics` pour le dashboard de convergence
