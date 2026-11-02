# polyre-bdf-lab — v0.1

Prototype indépendant de la piste expérimentale n°6 du rapport PolyRE, « Fidélité dirigée par le
binaire » (BDF). Objectif : vérifier, par du code qui s'exécute et des mesures, qu'un laboratoire
peut **repérer automatiquement un comportement Windows mal pris en charge par Wine, proposer un
correctif sûr, puis constater que le programme réussit son scénario après application — sans faux
succès ni régression**.

Ce projet **ne modifie pas** le moteur PolyRE (NoxPolyRE). Il est autonome et ne sera intégré que si
ses résultats sont convaincants. Les résultats réellement obtenus sont dans [`RESULTATS.md`](RESULTATS.md).

> État : prototype de recherche. La victoire obtenue est **synthétique** (programme de test écrit pour
> le labo). Elle prouve que le prototype fonctionne, **pas** une efficacité sur des logiciels
> commerciaux. Voir `RESULTATS.md` §5 (« Scénario 3 »).

---

## Ce que fait le labo

1. **Analyse statique d'un PE** (`bdflab/pe_surface.py`, via `pefile`) : identité (sha256, imphash,
   VERSIONINFO), architecture, imports et imports différés, DLL chargées dynamiquement.
2. **Base de connaissances Wine** (`bdflab/knowledge/build_wine_db.py`) : extraite des sources de
   Wine 11.0 — exports des `.spec`, fonctions `@ stub`, semi-stubs repérés par les `FIXME("…stub")`
   dans les `.c`, prototypes des en-têtes, DLL fournies, table des « api-sets ».
3. **Croisement** (`bdflab/wine_db.py`) : chaque import est résolu vers un statut dans Wine 11.0 —
   `implemented`, `semi-stub`, `stub`, `export-absent`, `dll-missing`, `forward-broken` (en suivant
   les redirections d'export et les api-sets).
4. **Collecte de traces Wine** (`bdflab/wine_runner.py`, `bdflab/trace_parser.py`) : exécution dans un
   préfixe jetable avec `WINEDEBUG=+relay,+tid,+timestamp,+seh,warn+module,+loaddll` ; repérage des
   appels à des fonctions non implémentées (`EXCEPTION_WINE_STUB` = 0x80000100), des imports sans
   implémentation, des DLL introuvables et des exceptions.
5. **Classification A/B/C/D** (`bdflab/classify.py`) : classe de contrat (A déclaratif, B comportement,
   C sémantique profonde, D hors périmètre) et classe d'API (requête d'état, tampon de sortie, mutation
   locale, mutation persistante, sécurité, synchronisation/temps).
6. **Décision de sûreté** (`bdflab/safety.py`) : table de sûreté du rapport. Stratégie **A** (absence
   déclarée) par défaut ; stratégie **S** (succès fabriqué) seulement dans les cases autorisées, en
   laboratoire, sur données jetables, sous teinte et journal ; jamais sur tampon de sortie, mutation
   persistante, sécurité, synchronisation ; jamais en production depuis une capsule expérimentale.
7. **Génération du correctif** (`bdflab/fixgen.py`, `bdflab/shimgen.py`) : voir « Voie de compatibilité »
   ci-dessous.
8. **Capsule** (`bdflab/capsule.py`) : fichier TOML signable indexé par l'identité du binaire, avec
   contrats, preuves (traces), résultats de scénarios et statut (`experimental` / `validated` /
   `rejected`) ; un linter refuse toute capsule violant la table de sûreté.
9. **Vérification des effets** (`bdflab/oracles.py`) : un programme n'« a réussi » que si un oracle
   indépendant le confirme (contenu du fichier, empreinte, réouverture, lecture PDF par `pdftotext`).
   Un succès annoncé sans fichier correct = **faux succès** (échec).
10. **Expérience comparative** (`bdflab/experiment.py`, `bdflab/run_experiment.py`) : 3 configurations
    (A Wine standard, B correctif généré, C correctif manuel de référence), chaque scénario au moins
    deux fois, dans des préfixes propres, avec mesures.
11. **Balayage de portée** (`bdflab/sweep.py`) : analyse statique d'un corpus de vrais exécutables
    (sans exécution) pour mesurer l'étendue de l'analyseur.

## Voie de compatibilité retenue (v0.1)

Le rapport (HANDOFF §5) laisse le choix entre (a) une DLL de remplacement chargée par
`WINEDLLOVERRIDES`, (b) une redirection au niveau de la table d'import, (c) un patch de Wine. La v0.1
retient une **combinaison de (a) et (b)**, documentée ici :

> Pour chaque DLL d'origine contenant une fonction absente de Wine, le labo **génère une DLL de
> compatibilité** qui **renvoie** (`forwarders` du `.def` : `Func = KERNEL32.Func`) tous les exports
> réellement présents vers la bibliothèque Wine, et **fournit** les fonctions manquantes. Dans une
> **copie jetable** de l'exécutable, le nom de la DLL d'origine est remplacé, sur place et à longueur
> égale, par celui de la DLL de compatibilité. La DLL est déposée à côté de la copie, dans le préfixe
> isolé.

Intérêt : cela fonctionne même pour une DLL « always builtin » (kernel32, kernelbase, ntdll…) que
`WINEDLLOVERRIDES` ne peut pas remplacer globalement — une seule fonction est fournie, le reste est
renvoyé à Wine. **Le moteur Wine n'est pas modifié ; l'exécutable d'origine reste intact ; la
correction est confinée au préfixe jetable.**

Limite connue : la signature de remplacement suppose l'ABI Win64 (x86-64), où l'appelant nettoie la
pile — une implémentation sans paramètre est sûre. Sur x86 (`__stdcall`), il faudrait décorer les
exports `@N` selon le nombre d'octets d'arguments (consigné dans `RESULTATS.md` §3.F).

## Installation

Dépendances système : voir `requirements-system.txt` (Wine 11.0 stable de WineHQ, `gcc-mingw-w64-x86-64`,
GNU `time`, et `poppler-utils` pour la vérification PDF — facultatif). Dépendances Python :

```bash
pip install -r requirements.txt
```

La base de connaissances Wine (`data/wine-11.0/`) est fournie dans le dépôt. Pour la reconstruire,
fournir l'arbre source de Wine 11.0 :

```bash
python3 -m bdflab.knowledge.build_wine_db --source <wine-11.0-src> --install /opt/wine-stable --out data/wine-11.0
```

## Utilisation

```bash
./run.sh                      # compile le test + les correctifs, lance l'expérience A/B/C
# ou, étape par étape :
python3 -m bdflab.run_experiment --exe testapps/bdfedit/bin/bdfedit.exe --synthetic --runs 2 --configs A,B,C
python3 -m bdflab.sweep --dir <dossier-d-exes> --out results/sweep.json   # balayage statique
python3 -m pytest tests/ -q                                               # tests automatisés
```

## Arborescence

```
bdflab/            code du laboratoire (analyse, base Wine, runner, classification, sûreté, génération, capsules, oracles, expérience, balayage)
testapps/bdfedit/  programme de test synthétique (C/mingw) + DLL d'export optionnelle + build.sh
manual-fix/        correctif manuel de référence (config C), écrit à la main
catalogue/         composants redistribuables par nous, avec empreintes (manifest.json)
data/wine-11.0/    base de connaissances Wine (générée)
capsules/          capsules TOML générées
results/           journaux, traces (preuves), fichiers produits, results.json, sweep.json
tests/             tests automatisés (pytest)
docs/              extraits du rapport + dossier de passation
scenarios/         description des scénarios et de leurs oracles
tools/             scripts utilitaires (récupération du corpus)
```

## Sûreté et limites (résumé)

- Aucune falsification de licence, identité, sécurité, signature ou activation (classe D : refus).
- Données **jetables** uniquement ; aucune suppression de données existantes.
- Une capsule `experimental` ne s'applique jamais silencieusement à un logiciel de production.
- Ressources bornées : 1–2 Wine simultanés, délais maximaux puis `wineserver -k`, contrôle disque/mémoire.
- La victoire est **synthétique**. Détails, mesures et honnêteté dans `RESULTATS.md`.
