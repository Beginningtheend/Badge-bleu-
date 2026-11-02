# Scénarios et oracles d'effet

Les scénarios sont définis dans `bdflab/experiment.py` (`SCENARIOS`) et vérifiés par les oracles de
`bdflab/oracles.py`. Chaque scénario est joué sous trois configurations (A Wine standard, B correctif
généré, C correctif manuel), au moins deux fois, dans des préfixes Wine propres et jetables.

| Scénario | Commande | API Windows exercée (statut Wine 11.0) | Oracles d'effet |
|---|---|---|---|
| `startup` | `bdfedit idle 2` | aucune (témoin de démarrage) | code de sortie 0 ; événement de fin émis |
| `edit-save-reopen` | `bdfedit edit doc.txt doc.txt <marque>` puis relecture | `SystemTimeToTzSpecificLocalTimeEx` (absente) | fichier modifié (sha256 ≠ référence) ; marque présente ; horodatage présent ; relecture indépendante cohérente |
| `stats-degrade` | `bdfedit stats` | `Heap32First` (`@ stub`) | processus survivant + fonctionnalité signalée (disponible ou dégradée proprement) |
| `export-pdf` | `bdfedit export-pdf doc.txt out.pdf` | `bdfpdf.dll` (DLL absente, classe A) | PDF présent + **texte retrouvé par `pdftotext`** (outil indépendant) |

## Règle d'or (anti-faux-succès)

Un scénario n'est « réussi » que si **un oracle indépendant du programme** confirme l'effet attendu.
Un programme qui annonce « enregistré » ou « exporté » alors que le fichier est absent ou incorrect est
classé **faux succès** (échec), jamais succès. Les oracles lisent les fichiers produits côté hôte,
calculent leur empreinte, et pour le PDF délèguent à `pdftotext`.

## Résultat attendu et obtenu

- Config A : seul `startup` réussit ; les trois autres échouent (plantage `EXCEPTION_WINE_STUB` pour
  `edit`/`stats`, dégradation « indisponible » pour `export-pdf`). Aucun faux succès.
- Configs B et C : les quatre scénarios réussissent, effets vérifiés, 0 faux succès, 0 régression.

Voir `RESULTATS.md` pour les mesures.

## Généralisation : actions jamais enregistrées

Les scénarios ci-dessus servent à **dériver** le correctif (exécutions de référence). Pour répondre à la
question « le correctif marche-t-il sur ce que la référence n'a jamais montré ? », `tools/demo_generalization.py`
rejoue le correctif sur des actions **tenues à l'écart** : autre document, texte Unicode, document vide, document
de 5000 lignes, et des familles de scénario jamais utilisées pour dériver le correctif (`stats`, `export-pdf`,
`startup`). Chaque action tourne dans un préfixe propre et est jugée par les mêmes oracles d'effet, plus un
oracle **fort** d'horodatage (`timestamp_fresh` : l'heure enregistrée doit être celle de l'exécution, pas une
valeur rejouée). Le verdict (`bdflab/generalize.py`) est `generalizes`, `does-not-generalize` ou `cannot-judge`
— jamais présumé. Résultats : `RESULTATS.md` §8.10.
