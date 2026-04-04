# Protocole experimental

## Metriques de classification

Par axe (template, categorie, brand) et global (3 axes corrects simultanement) :
- Accuracy
- F1 macro (insensible au desequilibre des classes)
- F1 micro
- Matrice de confusion
- Cohen's kappa (accord modele/humain)

Tous rapportes en moyenne ± ecart-type sur 5 splits.

## Significativite statistique

- Test de McNemar (paire par paire) entre chaque methode sur chaque split
- p-values rapportees, seuil alpha = 0.05 avec correction de Bonferroni

## Convergence

- Courbe accuracy vs nombre d'annotations (dev et test separement)
- Plateau defini comme : variation < 2% sur les 3 dernieres iterations

## Fiabilite de l'annotation

- Kappa intra-annotateur (test-retest a 1 semaine, 50+ posts)
- Kappa inter-annotateur (collaborateur Views, 500+ posts)

## Ablations

| ID | Variante | Variable testee |
|----|----------|-----------------|
| A0 | Prompt v0 statique | Baseline sans optimisation |
| A1 | HILPO batch=1 | Taille du batch |
| A2 | HILPO batch=10 | Taille du batch |
| A3 | HILPO batch=30 (defaut) | Configuration principale |
| A4 | HILPO batch=50 | Taille du batch |
| A5 | HILPO sans rollback | Effet du mecanisme de rollback |
| A6 | HILPO rewrite humain | LLM rewriter vs humain expert |

## Baselines

| ID | Methode | Type | Donnees necessaires |
|----|---------|------|---------------------|
| B0 | Zero-shot + prompt v0 | Zero-shot | 0 |
| B1 | Zero-shot CLIP | Zero-shot | 0 |
| B2 | Few-shot 5 exemples/classe | Few-shot | ~150 |
| B3 | Few-shot 10 exemples/classe | Few-shot | ~300 |
| B4 | CLIP embeddings + Logistic Regression | Supervise | 1600 |
| B5 | CLIP embeddings + SVM | Supervise | 1600 |
| B6 | Fine-tuning LoRA (si faisable) | Supervise | 1600 |
