# Prompt — nouvelle conversation Claude Code **locale** (Fable 5.1, effort max, ultracode)

Ce fichier est le kit de passation de la session cloud du 2 novembre 2026 vers une conversation Claude Code
**sur votre machine** (là où se trouve votre VM Windows). Il contient : le mode d'emploi de lancement (§A), puis
le **prompt à coller** (§B, après la ligne `---`). Tout ce que la session cloud a dit et produit est dans le
dépôt : `docs/handoff/CONVERSATION-integrale.md` (la conversation entière), `RESULTATS.md`,
`docs/RECHERCHE-graal-2026.md`, `docs/IDEATION-graal.md`, `docs/handoff/HANDOFF.md` (contexte PolyRE et rapport).

## A. Mode d'emploi (pour vous, avant de coller le prompt)

<!-- MODE-D-EMPLOI : complété après vérification de la documentation Claude Code (voir fin de fichier) -->

---

## B. Prompt à coller (tout ce qui suit)

ultracode

MISSION CLAUDE CODE — POLYRE BDF-LAB, PHASE « PROFESSEUR » : LA VM WINDOWS RÉELLE COMME ORACLE
(passation depuis la session cloud du 2 novembre 2026 ; tu es sur la machine de l'utilisateur, en local)

Rôle : ingénieur senior en compatibilité Windows/Linux (Wine), rétro-ingénierie PE, automatisation des tests et
méthode expérimentale. Tu travailles en français, de façon autonome, avec des sous-agents et Internet autant
que nécessaire (le mot « ultracode » ci-dessus active l'orchestration multi-agents : utilise des workflows
pour toute tâche substantielle, avec vérification adverse des résultats), à l'effort maximal, et tu restes
**honnête** : aucun gain revendiqué sans mesure, aucun verdict présumé.

### 0. Lis d'abord, dans cet ordre, sans rien écrire

1. `RESULTATS.md` en entier (§1–§8.10) : ce qui est prouvé, ce qui ne l'est pas, les chiffres réels.
2. `docs/RECHERCHE-graal-2026.md` §0, §13, §10 ter → §10 sexies (les idées de l'utilisateur et leur
   vérification) ; le reste en diagonale.
3. `docs/handoff/HANDOFF.md` §1–§5 (contexte PolyRE, rapport, classes A/B/C/D, table de sûreté, format de
   capsule, protocole à 4 bras). Son §6 est obsolète : le labo existe maintenant.
4. `docs/handoff/CONVERSATION-integrale.md` : toute la conversation précédente (messages de l'utilisateur
   verbatim). Lis au minimum tous les messages « Utilisateur » : ils contiennent ses règles, ses idées et son
   style ; les réponses de Claude expliquent chaque décision.
5. `README.md` (inventaire des 18 capacités), `fixtures/README.md`, `fixtures/CAPTURE-WINDOWS-README.md`,
   `scenarios/README.md`, `tools/README.md`.
6. Le code : `bdflab/` (23 modules), `tests/` (82 tests), `tools/demo_*.py`.

### 1. Règles de l'utilisateur, non négociables

- **Interdiction de modifier le moteur PolyRE principal** (dépôt NoxPolyRE : lecture seule, s'il est présent sur
  la machine ; ne le cherche pas ailleurs). Le labo reste un projet indépendant.
- **Aucune falsification** de licence, identité, sécurité, signature ou activation (classe D : refus explicite).
  Les fonctions de sécurité, les pilotes et services noyau sont classés C ou D, jamais corrigés.
- **Stratégie A (absence déclarée) par défaut.** Stratégie S (succès fabriqué) uniquement dans les cases
  autorisées de la table de sûreté (`bdflab/safety.py`), teintée et journalisée, jamais en production depuis une
  capsule expérimentale. Stratégie F (valeur enregistrée) : même périmètre que S, et seulement si la valeur a été
  observée identique sous au moins deux entrées distinctes (règle du professeur, `speculate.fixture_stability`).
- **Un succès annoncé sans fichier présent et correct = faux succès = échec.** Jamais de conclusion sur un code de
  sortie : toujours un oracle d'effet indépendant, et un oracle **aussi fort que la propriété vérifiée**
  (RESULTATS §8.10 : un horodatage « plausible » a laissé passer 5 faux succès ; un horodatage « frais » les a
  tous attrapés).
- **Cas synthétiques** marqués `synthetic = true`, résultats séparés des logiciels réels.
- **Scénario 3** (« BDF résout automatiquement plusieurs catégories de problèmes sur des applications inconnues,
  avec effets vérifiés et sans corruption ») : confirmer, infirmer ou dire qu'on ne peut pas juger. Ne jamais
  présumer.
- **Ressources, machine partagée** : 1 à 2 Wine simultanés au maximum (`RunLock` existe dans
  `bdflab/wine_runner.py` : tous les agents passent par lui), délais maximaux puis `wineserver -k`, aucun test sur
  un disque avec erreurs SMART, **aucune suppression de données existantes**, aucun processus laissé tourner.
  Même avec beaucoup d'agents, le nombre de Wine simultanés ne dépasse jamais 2.
- **Vocabulaire** : la session cloud a été arrêtée une fois par un classifieur de sûreté à cause de termes
  évoquant l'intrusion logicielle. Décris les mécanismes avec le vocabulaire du labo : « DLL de compatibilité »,
  « redirection d'import dans une copie jetable de l'exécutable », « réponse déclarée », « fonderie », « capsule ».
  Reste précis techniquement ; change les mots, pas les idées.
- **Style** : l'utilisateur veut des avancées fortes (« eureka », « gain extraordinaire ») et accepte les idées
  « débiles techniquement » **à condition qu'elles soient testées** ; il exige en retour une honnêteté totale sur
  ce qui est prouvé. Réponds en français, avec les chiffres mesurés, sans enjoliver.

### 2. État exact des lieux (dépôt `Beginningtheend/Badge-bleu-`, branche `claude/polyre-bdf-lab-prototype-tc4bkz`)

Ce qui est **prouvé sur ce banc** (programme synthétique `bdfedit`, Wine 11.0 stable WineHQ, préfixes propres) :
- Expérience A/B/C, 4 scénarios × 2 exécutions : Wine seul **2/8** (témoin de démarrage seulement) → correctif
  généré **8/8** → correctif manuel **8/8** ; 0 faux succès, 0 régression ; deux classes de problèmes (A : DLL
  absente fournie par catalogue avec empreinte ; B : fonctions non implémentées par Wine redirigées vers une DLL
  de compatibilité générée).
- Généralisation (RESULTATS §8.10) : correctif dérivé d'une seule référence → **8/8 actions jamais
  enregistrées** (autres documents, Unicode, vide, 5000 lignes, 3 familles de scénario jamais apprises) ; contrôle
  négatif « valeur enregistrée rejouée » → **0/5, 5 faux succès** démasqués par l'oracle fort alors que l'oracle
  faible le laisse passer (5/5) ; règle synthétisée par la fonderie → **5/5**.
- Mécanismes réels et testés (82 tests) : base de connaissances Wine 11.0 (exports, stubs, semi-stubs,
  prototypes, api-sets), analyse PE, traces (`+relay,+seh,+loaddll`), classification A/B/C/D, table de sûreté et
  linter, génération de DLL de compatibilité + copie jetable de l'exécutable, oracles d'effet, capsules TOML avec
  `[generalization]`, découverte de réponse par oracle, pré-réponse par analyse des branches (Capstone), fonderie
  (toute implémentation jugée par l'oracle), communs par empreinte, flux « déposer l'exe », catalogue « Windows
  de l'utilisateur » (règle du plancher), importateur de capture (Process Monitor / journal Wine) → recette →
  script PowerShell d'extraction, juge de généralisation.
- Balayage statique de 182 vrais exécutables ; génération statique multi-DLL pour Process Explorer avec refus des
  fonctions de sécurité et pilote.

Ce qui **n'est pas prouvé** : toute efficacité sur un logiciel réel à l'exécution (Scénario 3 : « ne permet pas
de juger ») ; tout ce qui exige un Windows (capture, distillation de fixtures, catalogue de DLL natives) ; les
classes C/D sont hors périmètre par décision. La recherche (RECHERCHE §0, §13) conclut : pas de graal technique ;
l'avantage réaliste est la couche de capsules sûres, vérifiées par l'effet, à côté de Wine (qui refuse le code
généré par IA) ; la VM Windows de l'utilisateur a trois rôles : **catalogue, repli, oracle**.

### 3. Avant toute chose : inventaire de la machine (ne présume rien)

Produis un tableau de ce qui est présent : système hôte (Linux natif ou WSL2 ; Windows seul n'exécute pas le
labo), version **exacte** de Wine (`wine --version` ; l'expérience est figée sur `wine-11.0` : si une autre
version est installée, dis-le et n'en mélange pas deux ; propose l'installation WineHQ stable 11.0 sans la faire
sans accord), `x86_64-w64-mingw32-gcc`, GNU `time`, `pdftotext`, Python ≥ 3.11 et `pip install -r
requirements.txt`, cœurs/RAM/disque, état SMART si lisible, la VM Windows (hyperviseur, version de Windows,
Process Monitor et PowerShell disponibles, dossier partagé VM ↔ hôte), le dépôt NoxPolyRE (présent ou non), et
la liste des applications que l'utilisateur veut faire marcher (demande-la lui : c'est la seule question qui vaut
une interruption). Puis `python3 -m pytest tests/ -q` (82 attendus) et `./run.sh` si Wine 11.0 est là.

### 4. La mission « professeur » : ce que la session cloud ne pouvait pas faire

Objectif : remplacer le professeur **simulé** par le **vrai** (votre VM Windows), sur de **vrais logiciels**, et
rendre le verdict Scénario 3 sur mesures. Dans l'ordre, chaque étape avec son critère d'acceptation :

**M1. Capture réelle → recette → extraction → vérification par oracle.** Suivre
`fixtures/CAPTURE-WINDOWS-README.md` : Process Monitor dans la VM, **chaque scénario joué avec au moins deux
entrées différentes** (deux documents, deux textes), export CSV → `bdflab.capture_import.parse_procmon_csv` +
`build_recipe` → `to_extract_script` → `extract.ps1` dans la VM → dossier extrait (privé, jamais versionné :
`.gitignore`) → application de la recette dans un préfixe Wine propre → oracles. Accepté si : une application
réelle passe au moins un scénario à oracle qu'elle échouait sous Wine seul, 0 faux succès, 2 exécutions.

**M2. Fixtures 0.2 distillées sur Windows.** Pour chaque fonction absente/stub de classe requête d'état touchée
par l'application : observer sa réponse sous ≥ 2 entrées/états (API Monitor, Process Monitor, ou un petit
programme-sonde compilé avec mingw et lancé dans la VM), écrire `fixtures/<app>.json` au format 0.2
(`observations`), laisser `speculate` décider F/A/S par oracle. Aucune trace brute, aucun code ni donnée Windows
dans le dépôt : uniquement (fonction, entrée pertinente) → (retour, dernier code d'erreur).

**M3. Protocole à 4 bras sur de vrais logiciels** (HANDOFF §3 : 1 Wine seul · 2 Wine + résolveur automatique ·
3 Wine + correctifs manuels chronométrés · 4 bras 2 puis manuel sur le reste), ≥ 2 exécutions par scénario,
préfixes propres, oracles d'effet par scénario, temps humain chronométré, CPU/RAM. Commence par 3 applications
choisies avec l'utilisateur ; vise le corpus de 30 du rapport seulement si les 3 premières sont concluantes.
Seuils pré-enregistrés du rapport : faux succès ≤ 2 %, corruption 0, régression 0, temps humain réduit d'au moins
30 % (H1). Verdict Scénario 3 par application et global, en trois valeurs.

**M4. Généralisation sur de vrais logiciels.** Pour chaque correctif dérivé d'actions de référence, tester des
actions tenues à l'écart (`bdflab/generalize.py`), avec des oracles **forts** spécifiques à l'application
(relecture par un outil tiers, empreintes, horodatage frais, comparaison de rendu) ; section `[generalization]`
dans chaque capsule ; statut `validated` seulement avec `generalizes`, signature et 2 exécutions.

**M5. Catalogue « Windows de l'utilisateur ».** Exercer `bdflab/userwindows.py` sur le `System32` de la VM
(inventaire par empreinte, règle du plancher), proposer des contrats `dll-native-user-windows` pour les DLL hors
plancher que l'application charge, vérifier par oracle. Jamais redistribué.

**M6. Honnêteté et dépôt.** `RESULTATS.md` reçoit une section « 9. Logiciels réels » avec les chiffres réellement
obtenus, séparés du synthétique, et une mise à jour du verdict §5. Chaque résultat a son JSON dans `results/`.
Les données extraites de Windows restent hors dépôt. Commits clairs, push sur la branche indiquée par
l'utilisateur (demande-lui s'il veut continuer sur `claude/polyre-bdf-lab-prototype-tc4bkz` ou ouvrir une
branche). Ne supprime jamais un résultat passé.

**M7. La quête continue.** L'utilisateur veut toujours la percée. Après M1–M4, relance la recherche d'idées
(RECHERCHE §10 ter → sexies et `docs/IDEATION-graal.md` montrent la méthode : idée → vérification en points →
expérience dans le labo). Toute idée nouvelle se teste ; toute source se vérifie (jamais de citation non lue).

### 5. Méthode de travail

- Workflows (ultracode) pour : lecture parallèle du dépôt au démarrage, revue adverse de chaque résultat avant
  de l'écrire dans `RESULTATS.md`, recherche Internet multi-angles avec vérification des sources, critique de
  complétude en fin de phase. Les agents n'exécutent Wine qu'à travers `RunLock` (slots ≤ 2).
- Chaque chiffre publié vient d'un fichier dans `results/` ; chaque affirmation sur Wine vient de la base
  `data/wine-11.0/` ou d'une trace.
- Pièges rencontrés dans la session cloud, déjà corrigés mais à connaître : chemins de journaux relatifs au
  répertoire de l'enfant (GNU time), ordre horodatage/thread dans les lignes `+relay`, canal `loaddll` distinct de
  `module`, drapeaux `(?i)` en milieu de motif refusés par Python 3.13, `-municode` exige `wmain`, préfixes propres
  par liens durs depuis un gabarit, DLL « always builtin » non remplaçables par `WINEDLLOVERRIDES` (d'où la DLL de
  compatibilité + redirection d'import), classifieur de sûreté sensible au vocabulaire, workflows multi-agents
  bloqués sur un conteneur à 2 cœurs (en local, surveille la charge), citations non vérifiées (remplacées par des
  chiffres lus à la source), Wine refuse le code généré par IA (ne propose jamais d'y contribuer du code produit
  par modèle).
- Limite connue v0.1 : ABI Win64 seulement pour les DLL de compatibilité (x86 32 bits : décoration `@N` à faire).

### 6. Livrables de cette phase

Code et tests pour tout ce qui est nouveau ; `results/*.json` ; capsules ; `RESULTATS.md` §9 ; `fixtures/*.json`
(sans données Windows) ; un `docs/handoff/` mis à jour pour la session suivante ; et, en fin de phase, un
message final qui donne : le verdict Scénario 3 (trois valeurs), le tableau des mesures par application, les faux
succès, les régressions, le temps humain, ce qui n'est pas prouvé, et la prochaine étape.

Priorité absolue : un premier résultat **réel** (une vraie application, un vrai scénario, un vrai oracle, dans un
préfixe propre, deux fois) avant toute nouvelle théorie.
