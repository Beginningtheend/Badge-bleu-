# Outils

- `fetch_corpus.sh` — télécharge un corpus de vrais exécutables Windows open source / redistribuables
  (SumatraPDF, suite Sysinternals, Python embarqué, 7-Zip) dans `_corpus/` pour le balayage statique
  (`python3 -m bdflab.sweep`). Le corpus lui-même n'est **pas** versionné (voir `.gitignore`) ; seul le
  résultat d'analyse `results/sweep.json` l'est.
- `capture_to_recipe.py` — capture (CSV Process Monitor depuis la VM, ou journal Wine) → `recipe.json` + `extract.ps1`
  (à exécuter dans la VM) ; sortie dans `_captures/<app>/` (ignoré par git : chemins et noms d'utilisateur Windows).
- `demo_speculate.py` — recherche de réponse par oracle (stratégie S découverte, pas présumée) ; résultat
  `results/speculate-demo.json`.
- `demo_foundry.py` — fonderie : une implémentation proposée correcte est acceptée, une fausse (succès annoncé sans
  sortie) est rejetée par l'oracle ; résultat `results/foundry-demo.json`.
- `demo_generalization.py` — la question décisive (« Windows professeur, Linux élève ») : un correctif dérivé
  d'actions enregistrées est jugé sur des actions **jamais enregistrées**, en trois bras (règle dans la table de
  sûreté / valeur enregistrée rejouée = contrôle négatif / règle synthétisée par la fonderie), avec oracle faible
  et oracle fort ; résultat `results/generalization-demo.json`, capsule émise avec section `[generalization]`.
