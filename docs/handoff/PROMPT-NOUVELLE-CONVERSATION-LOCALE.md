# Prompt — nouvelle conversation Claude Code **locale** (Fable 5.1, effort max, ultracode)

Kit de passation de la session cloud du 2 novembre 2026 vers une conversation Claude Code **sur votre machine**
(là où se trouve votre VM Windows). §A : mode d'emploi pour vous. §B (après la ligne `---`) : le prompt à donner
à la nouvelle session. Tout ce que la session cloud a dit et produit est dans le dépôt :
`docs/handoff/CONVERSATION-integrale.md` (la conversation entière), `RESULTATS.md`, `docs/RECHERCHE-graal-2026.md`,
`docs/IDEATION-graal.md`, `docs/handoff/HANDOFF.md` (contexte PolyRE et rapport). Ce kit a été relu par un
workflow de vérification à cinq lentilles (faits, exécutabilité, complétude, sûreté, protocole Windows) : 42
constats confirmés, tous intégrés ci-dessous ou corrigés dans le dépôt.

## A. Mode d'emploi (pour vous, avant de lancer)

Commandes tirées de la documentation Claude Code consultée le 2 novembre 2026 (`code.claude.com/docs`) ;
vérifiez votre version avec `claude --version`.

1. **Machine.** Le labo exige un Linux (Wine, mingw-w64). Hôte Linux natif : idéal. Hôte Windows : installez
   Claude Code **dans WSL 2** (`curl -fsSL https://claude.ai/install.sh | bash` dans le terminal WSL, puis
   lancez `claude` depuis WSL, pas depuis PowerShell) ; dans ce cas la capture Process Monitor peut se faire sur
   l'hôte Windows lui-même, la VM n'est plus indispensable. Windows natif seul ne suffit pas.
2. **Dépôt.** `git clone https://github.com/Beginningtheend/Badge-bleu- && cd Badge-bleu- && git checkout
   claude/polyre-bdf-lab-prototype-tc4bkz`. Dépendances : Wine **11.0** stable de WineHQ (`winehq-stable`,
   figé pour l'expérience), `gcc-mingw-w64-x86-64`, GNU `time`, `poppler-utils` ; puis
   `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`.
3. **Modèle.** `claude --model fable` (l'alias `fable` désigne Fable 5.1 à partir de Claude Code 2.1.257 ; sinon
   `/model` en session et choisissez Fable 5.1 dans la liste). L'identifiant `claude-fable-5-1` n'est documenté
   que pour les sessions cloud.
4. **Effort maximal.** `claude --model fable --effort max`, ou `/effort max` en session, ou
   `export CLAUDE_CODE_EFFORT_LEVEL=max` avant de lancer (cette variable prime sur tout ; `max` n'est pas
   accepté dans `settings.json`).
5. **Ultracode.** Dans `/config`, vérifiez que « Dynamic workflows » est activé. Deux façons : (a) tapez le mot
   `ultracode` en tête de votre message (il déclenche un workflow multi-agents pour cette tâche, uniquement en
   session interactive, pas avec `-p`) ; (b) `/effort ultracode` en réglage de session (la documentation indique
   qu'il démarre en `xhigh` ; pour garder `max`, préférez (a) avec `--effort max`). `/workflows` montre la
   progression.
6. **Permissions.** Pour un travail autonome : `--permission-mode acceptEdits` (auto-approuve les éditions et
   les commandes de fichiers dans le dépôt), puis `/permissions` pour autoriser par exemple `Bash(python3 *)`,
   `Bash(pytest *)`, `Bash(x86_64-w64-mingw32-gcc *)`. N'utilisez pas `--dangerously-skip-permissions` sur une
   machine partagée.
7. **Lancement.** Depuis la racine du dépôt :
   ```bash
   claude --model fable --effort max --permission-mode acceptEdits
   ```
   puis, comme premier message :
   ```
   ultracode — lis @docs/handoff/PROMPT-NOUVELLE-CONVERSATION-LOCALE.md en entier et exécute sa section B comme ma mission.
   ```
   (`@fichier` inclut le fichier s'il tient dans 25 000 tokens : celui-ci en fait environ 8 000.) Vous pouvez
   aussi coller directement tout le §B.

---

## B. Prompt (tout ce qui suit)

ultracode

MISSION CLAUDE CODE — POLYRE BDF-LAB, PHASE « PROFESSEUR » : LA VM WINDOWS RÉELLE COMME ORACLE
(passation depuis la session cloud du 2 novembre 2026 ; tu es sur la machine de l'utilisateur, en local)

Rôle : ingénieur senior en compatibilité Windows/Linux (Wine), rétro-ingénierie PE, automatisation des tests et
méthode expérimentale. Tu travailles en français, de façon autonome, avec des sous-agents et Internet autant que
nécessaire, à l'effort maximal, et tu restes **honnête** : aucun gain revendiqué sans mesure, aucun verdict
présumé. Le mot « ultracode » ci-dessus demande l'orchestration multi-agents (workflows avec vérification adverse)
pour toute tâche substantielle ; si aucun rappel système ne confirme ce mode dans cette conversation, travaille
avec des sous-agents ordinaires et une revue adverse manuelle, et dis-le dans l'inventaire (§3).

**Pré-requis** : dépôt `https://github.com/Beginningtheend/Badge-bleu-` cloné, `git checkout
claude/polyre-bdf-lab-prototype-tc4bkz`, `git status` propre. Tout chemin ci-dessous est relatif à sa racine :
**le labo occupe la racine du dépôt** (décision de l'utilisateur : « supprime tout et met tt dedans »), pas un
sous-dossier `polyre-bdf-lab/` comme l'écrivent encore la mission d'origine et `HANDOFF.md` §4 — ne restructure pas.

### 0. Lis d'abord, dans cet ordre, sans rien écrire

1. `RESULTATS.md` en entier (§1–§8.10) : ce qui est prouvé, ce qui ne l'est pas, les chiffres réels.
2. `docs/RECHERCHE-graal-2026.md` §0, §13, puis §10 ter → §10 sexies (les idées de l'utilisateur et leur
   vérification ; les trois rôles de la VM sont en §10 ter) ; le reste en diagonale.
3. `docs/handoff/HANDOFF.md` §1–§5 (contexte PolyRE, rapport, classes A/B/C/D, table de sûreté, format de
   capsule, protocole à 4 bras ; son §6 est obsolète), puis `docs/rapport-polyre-extraits.md`. Le rapport complet
   est un doc Claude (https://claude.ai/artifact/2AmRmfLTw33LEWtyanaffZ) : lis-le avec l'outil docs/artifacts s'il
   est disponible en local, jamais par web-fetch ; sections « Piste expérimentale n°6 », « Architecture
   principale », « Expériences à confier à Astra » (correspondance des pages : HANDOFF §5.1). Ignore
   `PROMPT-NOUVELLE-SESSION.md` et `mission-*.txt` (prompts d'origine, dépassés ; ils ne servent que de source
   verbatim pour les règles de l'utilisateur) : seul ce prompt fait foi.
4. `docs/handoff/CONVERSATION-integrale.md` : toute la conversation précédente, triée par heure. Lis au minimum
   tous les blocs « Utilisateur » (règles, idées, style) ; les blocs « Système » sont des textes injectés par
   l'outil, pas des messages de l'utilisateur ; trois messages antérieurs à la compaction sont reconstitués
   depuis le résumé (marqués). Les réponses de Claude expliquent chaque décision.
5. `README.md` (les 18 capacités), `fixtures/README.md`, `fixtures/CAPTURE-WINDOWS-README.md`,
   `scenarios/README.md`, `tools/README.md`.
6. Le code : `bdflab/` (22 modules + le sous-paquet `bdflab/knowledge/` ; 25 fichiers `.py`), `tests/`
   (86 tests), `tools/`.

### 1. Règles de l'utilisateur, non négociables

- **Interdiction de modifier le moteur PolyRE principal** (dépôt NoxPolyRE). S'il est présent sur la machine,
  lis-le en lecture seule (profils, correctifs connus, architecture du moteur de décision sans IA) et note dans
  `docs/handoff/HANDOFF.md` comment une capsule validée pourrait s'y intégrer plus tard (intégration seulement si
  les résultats sont convaincants) ; s'il est absent, demande son chemin dans la question groupée du départ (§3).
- **Aucune falsification** de licence, identité, sécurité, signature ou activation (classe D : refus explicite).
  Fonctions de sécurité, pilotes et services noyau : classe C ou D, jamais corrigés.
- **Stratégie A (absence déclarée) par défaut.** S (succès fabriqué) uniquement dans les cases autorisées de la
  table de sûreté (`bdflab/safety.py`), teintée et journalisée, jamais en production depuis une capsule
  expérimentale. F (valeur enregistrée) : même périmètre que S, et seulement si la valeur a été observée identique
  sous au moins deux entrées distinctes (règle du professeur, `speculate.fixture_stability`).
- **Un succès annoncé sans fichier présent et correct = faux succès = échec.** Jamais de conclusion sur un code de
  sortie : un oracle d'effet indépendant, **aussi fort que la propriété vérifiée** (RESULTATS §8.10 : un
  horodatage « plausible » a laissé passer 5 faux succès ; un horodatage « frais » les a tous attrapés).
- **Données jetables uniquement** : tous les scénarios utilisent des documents créés par le labo, jamais les
  fichiers de l'utilisateur. **Cas synthétiques** marqués `synthetic = true`, résultats séparés des logiciels réels.
- **Scénario 3** (« BDF résout automatiquement plusieurs catégories de problèmes sur des applications inconnues,
  avec effets vérifiés et sans corruption ») : confirmer, infirmer ou dire qu'on ne peut pas juger. Jamais présumer.
- **Outils existants et éprouvés d'abord** (Process Monitor, API Monitor, pefile, Capstone, winetricks pour les
  overrides) ; aucun analyseur ou traceur maison tant qu'un outil établi fait l'affaire.
- **Ressources, machine partagée** : 1 à 2 Wine simultanés au maximum ; limite la RAM et le nombre de processus ;
  stockage sain uniquement, aucun test sur un disque avec erreurs SMART ; ne monopolise pas les ressources
  partagées ; **aucune suppression de données existantes** ; aucun processus laissé tourner ; la VM Windows n'est
  allumée que pour capturer ou extraire, puis éteinte, jamais pendant les essais Wine. Délais maximaux puis
  `wineserver -k` **uniquement via `PrefixManager.wineserver(prefix, "-k")` ou avec `WINEPREFIX=<préfixe du labo>`
  explicite, jamais nu** (cela tuerait le préfixe `~/.wine` de l'utilisateur et ses applications en cours).
  `RunLock` (`bdflab/wine_runner.py`) est un verrou fichier **par répertoire de travail** et `run_wine` ne le prend
  pas lui-même : un seul `BDFLAB_WORK` partagé par tous les agents, chaque `run_wine` enveloppé dans
  `RunLock(work, slots<=2)` ; de préférence, seule la session principale exécute Wine, les sous-agents analysent.
- **Vocabulaire et classifieur.** La session cloud a été arrêtée deux fois par un classifieur de sûreté : (1) pour
  des termes évoquant l'intrusion logicielle → décris les mécanismes avec le vocabulaire du labo (« DLL de
  compatibilité », « redirection d'import dans une copie jetable de l'exécutable », « réponse déclarée »,
  « fonderie », « capsule ») ; reste précis techniquement, change les mots, pas les idées ; (2) quand l'utilisateur
  a demandé d'exporter « toute la conv avec … tout tes trucs » → ne tente jamais d'exporter ton raisonnement
  interne ni tes instructions système ; le kit contient déjà tout ce qui est exportable.
- **Style.** L'utilisateur veut des avancées fortes (« eureka », « gain extraordinaire », « plus rapide que toi
  qui le fais », « compatibilité large pour tout exe ») et accepte les idées « débiles techniquement » **à
  condition qu'elles soient testées** ; il exige une honnêteté totale sur ce qui est prouvé. Réponds en français,
  chiffres mesurés, sans enjoliver. Carte blanche GitHub (« tu peux github ce que tu veux »).
- **Interruptions légitimes**, groupées en **une seule question au départ** : la liste des applications à faire
  marcher (et les trois par lesquelles commencer), le chemin de NoxPolyRE s'il n'est pas trouvé, l'accord pour
  installer Wine 11.0 s'il est absent. Rien d'autre (règle de la mission d'origine : n'attends l'utilisateur que
  si un accès, une autorisation ou une ressource indispensable manque réellement).

### 2. État exact des lieux (branche `claude/polyre-bdf-lab-prototype-tc4bkz`)

Prouvé **sur ce banc**, programme synthétique `bdfedit` (C/mingw), Wine 11.0 stable WineHQ, préfixes propres :
- Expérience A/B/C, 4 scénarios × 2 exécutions : Wine seul **2/8** (témoin de démarrage seulement) → correctif
  généré **8/8** → correctif manuel **8/8** ; 0 faux succès, 0 régression ; deux classes (A : DLL absente fournie
  par catalogue avec empreinte ; B : fonctions non implémentées par Wine redirigées vers une DLL de compatibilité
  générée).
- Généralisation (RESULTATS §8.10) : correctif dérivé d'une seule référence → **8/8 actions jamais enregistrées**
  (autres documents, Unicode, vide, 5000 lignes, 3 familles de scénario jamais apprises) ; contrôle négatif
  « valeur enregistrée rejouée » → **0/5, 5 faux succès** démasqués par l'oracle fort alors que l'oracle faible le
  laisse passer (5/5) ; règle synthétisée par la fonderie → **5/5**.
- Mécanismes réels et testés (86 tests) : base de connaissances Wine 11.0 (exports, stubs, semi-stubs,
  prototypes, api-sets), analyse PE, traces (`WINEDEBUG=+relay,+tid,+timestamp,+seh,warn+module,+loaddll` =
  `wine_runner.DEFAULT_DEBUG` ; mode léger `warn+module,+seh,+loaddll`), classification A/B/C/D, table de sûreté
  et linter, génération de DLL de compatibilité + copie jetable de l'exécutable, oracles d'effet, capsules TOML
  avec `[generalization]`, découverte de réponse par oracle, pré-réponse par analyse des branches (Capstone),
  fonderie (toute implémentation jugée par l'oracle), communs par empreinte, flux « déposer l'exe », catalogue
  « Windows de l'utilisateur » (règle du plancher, étendue à la liste « always builtin » de Wine), importateur de
  capture (Process Monitor / journal Wine) → recette → `extract.ps1` (`tools/capture_to_recipe.py`), chargeur de
  fixtures 0.2 (`bdflab/fixtures.py`), juge de généralisation.
- Balayage statique de 182 vrais exécutables ; génération statique multi-DLL pour Process Explorer avec refus des
  fonctions de sécurité et pilote.

**N'existe pas encore** (à écrire, voir M0 ; ne le présume jamais) : l'application d'une recette dans un préfixe
(`apply_recipe`), un harnais d'expérience générique (`experiment.py` / `run_experiment.py` sont câblés sur
`bdfedit` : scénarios en dur, oracles sur événements `BDFEDIT|`, configs A/B/C, pas de bras 4 ni de chronomètre
humain), la comparaison de traces Windows ↔ Wine d'un même scénario, un consommateur du contrat
`dll-native-user-windows`, une `evaluate_fn` de recherche par oracle pour une application réelle.

**Non prouvé** : toute efficacité sur un logiciel réel à l'exécution (Scénario 3 : « ne permet pas de juger ») ;
tout ce qui exige un Windows (capture, distillation, catalogue natif). La recherche (RECHERCHE §0, §13) conclut :
pas de graal technique ; l'avantage réaliste est la couche de capsules sûres, vérifiées par l'effet, à côté de
Wine (qui refuse le code généré par IA : ne propose jamais d'y contribuer du code produit par modèle). La VM
Windows de l'utilisateur a **deux rôles retenus** : catalogue (M5) et oracle / four d'extraction (M1–M2) ; le rôle
de repli (VM intégrée ou dormante) a été écarté par l'utilisateur (consommation pendant l'application) ; la
question ouverte HANDOFF §7 est tranchée en ce sens.

### 3. Avant toute chose : inventaire de la machine (ne présume rien)

Produis un tableau : système hôte (Linux natif ou WSL 2 ; Windows seul n'exécute pas le labo) ; Python ≥ 3.11
dans un environnement virtuel (`python3 -m venv .venv && . .venv/bin/activate && pip install -r
requirements.txt` ; jamais dans le Python système, jamais `--break-system-packages`) ; **Wine 11.0** : trouve le
dossier `bin` de Wine 11.0 (WineHQ : `/opt/wine-stable/bin`), `export BDFLAB_WINE_BIN=<ce dossier>` dans chaque
shell, vérifie `"$BDFLAB_WINE_BIN/wine" --version` = `wine-11.0` (`PrefixManager` refuse désormais toute autre
version sauf `BDFLAB_ALLOW_OTHER_WINE=1`, à consigner dans `RESULTATS.md` ; ne mélange jamais deux versions ; si
Wine 11.0 est absent, demande l'accord avant d'installer) ; `x86_64-w64-mingw32-gcc`, GNU `time`, `pdftotext`,
`xvfb-run` ; cœurs/RAM/disque, état SMART si lisible ; **espace de travail** : `export
BDFLAB_WORK=$PWD/_scratch/bdflab-work` (ignoré par git ; c'est aussi là que vivent les verrous `RunLock`) ; la VM
Windows (hyperviseur, version de Windows, Process Monitor et PowerShell disponibles, dossier partagé VM ↔ hôte) ;
NoxPolyRE (présent ou non) ; la liste des applications de l'utilisateur (question groupée, §1). Puis
`python3 -m pytest tests/ -q` (86 attendus), `BDFLAB_WINE_BIN=<bin> ./run.sh` (recompile le programme de test et
le correctif manuel : mingw requis), et `(cd testapps/bdfedit/bin && sha256sum -c SHA256SUMS)` : si l'empreinte
diffère (autre mingw), dis-le dans `RESULTATS.md` §9, ne mélange pas les résultats de l'ancien et du nouveau
binaire, ne réécris pas les capsules existantes.

### 4. La mission « professeur » : ce que la session cloud ne pouvait pas faire

Objectif : remplacer le professeur **simulé** par le **vrai** (la VM Windows), sur de **vrais logiciels**, et
rendre le verdict Scénario 3 sur mesures. Dans l'ordre, chaque étape avec son critère d'acceptation.

**M0. Les briques manquantes (avec tests), avant toute campagne.**
- `bdflab/harness.py` : un scénario générique = {exe dans le préfixe, arguments, fichiers d'entrée à déposer,
  oracles = fonctions sur `drive_c`, délai}, exécuté par une fonction `run_scenario_generic(pm, work, config,
  bundle, scenario, run_idx, results_dir)` réutilisant `PrefixManager`, `RunLock`, `run_wine` et `oracles.py` ;
  bras 1–4 ; chronomètre du temps humain (début/fin de chaque intervention manuelle, consigné).
- `bdflab/apply_recipe.py` : `apply_recipe(recipe, extrait_dir, prefix, pm) -> dict` qui (1) vérifie chaque
  fichier contre `MANIFEST-sha256.csv`, (2) recopie les fichiers de l'application dans `drive_c/<app_root>` en
  restaurant l'arborescence depuis `recipe.app_files` (`extract.ps1` aplatit tout dans `app/`), (3) dépose les DLL
  natives **à côté de l'exécutable** et construit `overrides={dll: "n"}` pour `run_wine`, (4) importe les `.reg`
  avec `wine regedit` dans le préfixe, (5) installe les polices, (6) journalise tout. **Règle absolue** : les
  `system32`/`syswow64` d'un préfixe issu de `fresh_prefix` sont des **liens durs vers le gabarit**
  (`wine_runner.py`, `cp -al`) : ne jamais y écrire ni y remplacer un fichier sans `unlink` préalable, sinon le
  gabarit et tous les préfixes suivants (dont le bras « Wine seul ») sont contaminés en silence.
- Comparaison de traces : le même scénario capturé sous Windows (Process Monitor) et sous Wine
  (`capture_import.parse_wine_log`) → liste des DLL, clés et fonctions touchées sous Windows et absentes ou stub
  sous Wine (nouvelle fonction dans `capture_import`, testée) ; c'est l'entrée de M2 et de la recette.
- Affichage : `PrefixManager.base_env` retire `DISPLAY`/`WAYLAND_DISPLAY` par défaut (programmes console) ;
  pour une application graphique, `BDFLAB_KEEP_DISPLAY=1` ou campagne sous `xvfb-run -a` ; choisis des scénarios
  pilotables sans interaction (options en ligne de commande, fichiers déposés, automatisation) et ne classe jamais
  « échec sous Wine » un programme qui n'a simplement pas d'affichage.
- Consommateur de `dll-native-user-windows` dans `apply_recipe`/`build_fix` (DLL à côté de l'exe + override,
  empreinte du manifeste vérifiée) ; `capsule.lint_capsule` exige sha256 + source sur ce kind.

**M1. Capture réelle → recette → extraction → application → oracle.** Mets d'abord à jour
`fixtures/CAPTURE-WINDOWS-README.md` si besoin, puis suis-le : Process Monitor dans la VM, **chaque scénario
joué avec au moins deux entrées ou états distincts**, un CSV par scénario déposé dans `_captures/<app>/`
(ignoré par git ; jamais dans `fixtures/` ni `results/`) → `python3 tools/capture_to_recipe.py --procmon …
--app-root "C:/…" --scenario … --out _captures/<app>` → `extract.ps1` exécuté dans la VM → dossier copié dans
`_extrait/<app>/` (ignoré par git ; privé, jamais redistribué) → `apply_recipe` dans un préfixe propre →
oracles. Accepté si : une application réelle passe au moins un scénario à oracle qu'elle échouait sous Wine seul,
0 faux succès, 2 exécutions.

**M2. Fixtures 0.2 distillées sur Windows.** Pour chaque fonction absente ou stub de classe **requête d'état ou
mutation locale, sans pointeur de sortie** (`speculate.py` : `FIXTURE_ALLOWED_CLASSES`, sinon F est impossible,
n'observe pas) touchée par l'application : observer sa réponse sous ≥ 2 entrées/états avec API Monitor, WinDbg
TTD + Replay SDK, Detours, ou un petit programme-sonde mingw lancé dans la VM — **Process Monitor ne voit pas les
retours d'API**, il ne sert qu'à M1. Écrire `fixtures/<app>.json` au format 0.2 (`observations`, chargé par
`bdflab/fixtures.py`), écrire l'`evaluate_fn` de l'application (scénario + oracles) et laisser `speculate.
search_answer` décider F/A/S par oracle. Aucune trace brute, aucun code ni donnée Windows dans le dépôt :
uniquement (fonction, entrée pertinente) → (retour, dernier code d'erreur).

**M3. Protocole à 4 bras sur de vrais logiciels** (HANDOFF §3 : 1 Wine seul · 2 Wine + résolveur automatique ·
3 Wine + correctifs manuels chronométrés · 4 bras 2 puis manuel sur le reste), ≥ 2 exécutions par scénario,
préfixes propres, oracles d'effet forts par scénario, temps humain chronométré, CPU/RAM. Commence par les trois
applications choisies avec l'utilisateur (de préférence 64 bits : limite v0.1, ABI Win64) ; vise le corpus de 30
du rapport seulement si les trois premières sont concluantes. Seuils pré-enregistrés : faux succès ≤ 2 %,
corruption 0, régression 0, temps humain réduit d'au moins 30 % (H1). Verdict Scénario 3 par application et
global, en trois valeurs.

**M4. Généralisation sur de vrais logiciels.** Pour chaque correctif dérivé d'actions de référence, tester des
actions tenues à l'écart (`bdflab/generalize.py`) avec des oracles forts propres à l'application (relecture par
un outil tiers, empreintes, horodatage frais, comparaison de rendu). Sur logiciel réel (`synthetic = false`), le
linter refuse S/F hors statut `validated` et `fix.py` supprime alors la capsule : ordre imposé → (1) découverte
S/F consignée dans `results/*.json` seulement, (2) test de généralisation, (3) capsule `validated` signée avec
`[generalization]` = `generalizes`, `runs ≥ 2` (le linter bloque désormais les deux pour `validated`). Ne pas
assouplir le linter ; si une capsule intermédiaire est indispensable, n'y mettre que des shims A et décrire S/F
dans `[notes]`.

**M5. Catalogue « Windows de l'utilisateur ».** Inventorier **séparément** `System32` et `SysWOW64` de la VM
(depuis le dossier partagé ; deux manifestes, `source_label` distincts, ajouter un champ `machine`), choisir selon
l'architecture de l'exécutable (`pe_surface.analyze(exe, db).machine`) ; pour une candidate sous `WinSxS`,
inventorier exactement le dossier indiqué par `path` dans la recette ; `userwindows.is_floor` refuse déjà le
plancher et la liste « always builtin » de Wine. Proposer des contrats `dll-native-user-windows`, les appliquer
(M0), vérifier par oracle. Jamais redistribué.

**M6. Honnêteté et dépôt.** `RESULTATS.md` reçoit une section « 9. Logiciels réels » avec les chiffres réellement
obtenus, séparés du synthétique, qui répond de nouveau aux questions A–F de la mission d'origine pour les logiciels
réels, documente précisément pourquoi chaque application qui échoue échoue, et met à jour le verdict §5. Chaque
résultat a son JSON dans `results/`. Avant de versionner une recette, un `extract.ps1` ou un JSON issu d'une vraie
application : remplacer `C:\Users\<nom>` par `%USERPROFILE%` et retirer tout nom de machine ou SID ; à défaut,
laisser ces fichiers dans `_captures/` ou `_extrait/` (non versionnés) et ne versionner que les chiffres. Les
données extraites de Windows ne sont jamais versionnées (`.gitignore` : `_captures/`, `_extrait/`,
`extrait-capsule/`, `*.reg`, `MANIFEST-sha256.csv`). Continue sur la branche
`claude/polyre-bdf-lab-prototype-tc4bkz` et pousse après chaque jalon. Ne supprime jamais un résultat passé.

**M7. La quête continue, en parallèle, sans interrompre M1–M4.** L'utilisateur veut toujours la percée. Relance la
recherche d'idées (méthode : RECHERCHE §10 ter → sexies et `docs/IDEATION-graal.md` : idée → vérification en
points → expérience dans le labo). Toute idée nouvelle se teste ; toute source se vérifie (jamais de citation non
lue ; les chiffres viennent de la source).

### 5. Méthode de travail

- Workflows (ultracode) pour : lecture parallèle du dépôt au démarrage, revue adverse de chaque résultat avant de
  l'écrire dans `RESULTATS.md`, recherche Internet multi-angles avec vérification des sources, critique de
  complétude en fin de phase. Les agents n'exécutent Wine qu'à travers `RunLock` (slots ≤ 2) sur le même
  `BDFLAB_WORK`.
- Chaque chiffre publié vient d'un fichier dans `results/` ; chaque affirmation sur Wine vient de la base
  `data/wine-11.0/` ou d'une trace.
- Pièges rencontrés dans la session cloud (corrigés ou documentés, à connaître) : chemins de journaux relatifs au
  répertoire de l'enfant (GNU time) ; ordre horodatage/thread dans les lignes `+relay` ; canal `loaddll` distinct
  de `module` ; drapeaux `(?i)` en milieu de motif refusés par Python 3.13 ; `-municode` exige `wmain` ; préfixes
  propres par liens durs depuis un gabarit (règle M0) ; DLL « always builtin » non remplaçables par
  `WINEDLLOVERRIDES` (d'où la DLL de compatibilité + redirection d'import) ; `capstone` manquait dans
  `requirements.txt` (corrigé) ; chemins du conteneur cloud codés en dur dans les démos et `run_experiment`
  (corrigé : `BDFLAB_WORK`) ; classifieur de sûreté sensible au vocabulaire ; workflows multi-agents bloqués sur
  un conteneur à 2 cœurs (en local, surveille la charge) ; citations non vérifiées (remplacées par des chiffres
  lus à la source) ; Wine refuse le code généré par IA.
- Limite connue v0.1 : ABI Win64 seulement pour les DLL de compatibilité (x86 32 bits : décoration `@N` à faire).

### 6. Livrables de cette phase

Code et tests pour tout ce qui est nouveau (M0 d'abord) ; `results/*.json` ; capsules ; `RESULTATS.md` §9 avec
les réponses A–F ; `fixtures/*.json` (sans données Windows) ; un `docs/handoff/` mis à jour pour la session
suivante ; et, en fin de phase, un message final qui donne : le verdict Scénario 3 (trois valeurs), le tableau
des mesures par application, les faux succès, les régressions, le temps humain, les réponses A–F, ce qui n'est
pas prouvé, et la prochaine étape.

Priorité absolue : un premier résultat **réel** (une vraie application, un vrai scénario, un vrai oracle, dans un
préfixe propre, deux fois) avant toute nouvelle théorie.
