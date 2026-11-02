# Outils

- `fetch_corpus.sh` — télécharge un corpus de vrais exécutables Windows open source / redistribuables
  (SumatraPDF, suite Sysinternals, Python embarqué, 7-Zip) dans `_corpus/` pour le balayage statique
  (`python3 -m bdflab.sweep`). Le corpus lui-même n'est **pas** versionné (voir `.gitignore`) ; seul le
  résultat d'analyse `results/sweep.json` l'est.
