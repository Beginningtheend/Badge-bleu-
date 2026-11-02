# Fixtures : réponses d'API distillées sur un Windows réel

Format ouvert consommé par `bdflab.speculate` (stratégie **F**, « fidèle ») : pour une fonction
déterministe sans état externe, la réponse exacte observée sur le Windows **de l'utilisateur**, distillée
**sur Windows** (ex. via WinDbg TTD + Replay SDK, API Monitor, Detours) puis exportée **sans aucun code ni
donnée Windows** — uniquement `(fonction, arguments pertinents) → (retour, dernier code d'erreur)`.
Voir `docs/RECHERCHE-graal-2026.md` §8 pour les limites (jamais de trace brute, jamais de tampon de sortie
en v0.1, sous-ensemble déterministe seulement).

```json
{
  "schema": "bdflab-fixtures/0.1",
  "source": "windows-11-23H2 (poste de l'utilisateur), distillé le AAAA-MM-JJ",
  "entries": {
    "shcore.IsAppCompatModeEnabled": { "returns": 1, "last_error": 0, "deterministic": true }
  }
}
```

Le fichier `example-illustratif.json` de ce dossier est **un exemple écrit à la main pour les tests**, pas une
distillation réelle (aucun Windows n'était disponible sur ce banc).
