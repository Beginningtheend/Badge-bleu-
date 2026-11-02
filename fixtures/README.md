# Fixtures : réponses d'API distillées sur un Windows réel

Format ouvert consommé par `bdflab.speculate` (stratégie **F**, « fidèle ») : pour une fonction
déterministe sans état externe, la réponse exacte observée sur le Windows **de l'utilisateur**, distillée
**sur Windows** (ex. via WinDbg TTD + Replay SDK, API Monitor, Detours) puis exportée **sans aucun code ni
donnée Windows** — uniquement `(fonction, arguments pertinents) → (retour, dernier code d'erreur)`.
Voir `docs/RECHERCHE-graal-2026.md` §8 pour les limites (jamais de trace brute, jamais de tampon de sortie
en v0.1, sous-ensemble déterministe seulement).

```json
{
  "schema": "bdflab-fixtures/0.2",
  "source": "windows-11-23H2 (poste de l'utilisateur), distillé le AAAA-MM-JJ",
  "entries": {
    "shcore.IsAppCompatModeEnabled": {
      "returns": 1, "last_error": 0, "deterministic": true,
      "observations": [
        {"input": "document A, session 1", "returns": 1, "last_error": 0},
        {"input": "document B, session 2", "returns": 1, "last_error": 0}
      ]
    }
  }
}
```

**Règle du professeur (0.2, `RESULTATS.md` §8.10).** Une valeur enregistrée n'est admise comme règle (stratégie F)
que si elle a été observée **identique sous au moins deux entrées ou états distincts** (`observations`). Si les
sorties diffèrent, la valeur dépend de l'entrée : ce n'est pas une règle mais une récitation, aucun candidat F
n'est produit et la voie est la fonderie (transférer la *fonction*, pas la *valeur*). Sans `observations`
(format 0.1), la fixture est admise mais étiquetée « observation unique ». Le professeur (la VM Windows) a donc
pour produit le plus utile des **couples entrée → effet**, c'est-à-dire des tests, plus que des réponses.

Le fichier `example-illustratif.json` de ce dossier est **un exemple écrit à la main pour les tests**, pas une
distillation réelle (aucun Windows n'était disponible sur ce banc).
