# RESULTATS — polyre-bdf-lab v0.1

**Date** : 2026-11-02 · **Wine** : 11.0 stable (`wine-11.0`, WineHQ ; tarball source
sha256 `c07a6857933c1fc6…`) · **Hôte** : conteneur Linux x86-64, 4 cœurs, 16 Go RAM.
**Priorité de la mission** : un premier résultat expérimental vérifiable, pas une nouvelle théorie.

---

## Résumé exécutif

Le critère de réussite de la mission est **atteint sur un cas synthétique** :

> Un programme Windows échoue sous Wine 11.0 ; le laboratoire identifie le comportement
> problématique, propose un correctif sûr ; après application, le programme **réussit** le scénario,
> **sans faux succès ni régression constatée**, sur **deux exécutions** indépendantes en préfixes propres.

| Configuration | Scénarios réussis | Faux succès | Régressions | Reproductible |
|---|---|---|---|---|
| **A** — Wine 11.0 standard | **2 / 8** (seul le témoin de démarrage) | 0 | — | oui |
| **B** — Wine + correctif **généré** | **8 / 8** | **0** | **0** | oui |
| **C** — Wine + correctif **manuel** de référence | **8 / 8** | **0** | **0** | oui |

Trois scénarios passent de l'échec (A) au succès (B et C) : édition-enregistrement-réouverture,
diagnostic dégradé, export PDF. Ils couvrent **deux classes de problèmes** : classe A (déclaratif, DLL
absente) et classe B (comportement, fonction non implémentée par Wine).

**Ce que cela prouve** : le prototype fonctionne de bout en bout — analyse → diagnostic → correctif sûr
→ vérification d'effet. **Ce que cela ne prouve pas** : une efficacité sur des logiciels commerciaux
inconnus (le programme de test est synthétique, écrit pour le labo). Voir §5.

---

## 1. Dispositif expérimental

**Base de connaissances Wine 11.0** (générée depuis les sources, `data/wine-11.0/`) :

| Élément | Quantité |
|---|---|
| Fichiers `.spec` analysés | 699 |
| Exports recensés | 130 664 |
| Exports `@ stub` explicites | 26 310 |
| Fonctions semi-stub repérées par `FIXME` dans les `.c` | 3 131 |
| Prototypes extraits des en-têtes | 10 864 |
| api-sets résolus | 555 |
| DLL fournies par Wine (x86-64) | 763 |

**Programme de test** : `bdfedit` (`testapps/bdfedit/`, C/mingw-w64, x86-64, `synthetic = true`,
sha256 `25205f9b77d4…`, imphash `fe7a428bf8b2…`). Éditeur de documents en console, piloté par la ligne
de commande, qui appelle de **vraies** fonctions Windows insuffisamment prises en charge par Wine 11.0 et
se dégrade proprement quand elles échouent. Toutes les données sont jetables.

**Problèmes réellement présents dans ce binaire** (identifiés automatiquement) :

| Fonction / DLL | Statut Wine 11.0 | Classe | Classe d'API |
|---|---|---|---|
| `KERNEL32.SystemTimeToTzSpecificLocalTimeEx` | export absent (stub dans kernelbase) | B | tampon de sortie |
| `KERNEL32.Heap32First` | `@ stub` | B | tampon de sortie |
| `KERNEL32.Heap32Next` | `@ stub` | B | tampon de sortie |
| `bdfpdf.dll` (export PDF) | DLL absente | A | chargeur |

**Scénarios et oracles d'effet** (données jetables, vérification indépendante) :

| Scénario | Ce qu'il exerce | Oracles d'effet |
|---|---|---|
| `startup` | démarrage/fin stables (témoin) | code de sortie, événement de fin |
| `edit-save-reopen` | modifier + enregistrer + rouvrir ; dépend de `SystemTimeToTzSpecificLocalTimeEx` | fichier modifié (sha256 ≠ référence), contenu attendu présent, horodatage présent, relecture indépendante |
| `stats-degrade` | diagnostic mémoire ; dépend de `Heap32First` | survie du processus + dégradation propre signalée |
| `export-pdf` | export PDF ; dépend de `bdfpdf.dll` (classe A) | PDF présent + **texte retrouvé par `pdftotext`** (outil tiers) |

**Trois configurations**, chaque scénario joué **2 fois** dans un **préfixe Wine neuf** à chaque fois ;
ressources bornées (1 Wine à la fois, délai max puis `wineserver -k`, contrôle disque/mémoire avant toute
exécution).

## 2. Résultats détaillés

```
config | scénario           | r1   | r2   | faux succès | exit (A)
A      | startup            | PASS | PASS | non         | 0
A      | edit-save-reopen   | FAIL | FAIL | non         | 1  (plantage EXCEPTION_WINE_STUB)
A      | stats-degrade      | FAIL | FAIL | non         | 1  (plantage EXCEPTION_WINE_STUB)
A      | export-pdf         | FAIL | FAIL | non         | 2  (dégradation honnête : « indisponible »)
B/C    | startup            | PASS | PASS | non         | 0
B/C    | edit-save-reopen   | PASS | PASS | non         | 0
B/C    | stats-degrade      | PASS | PASS | non         | 0
B/C    | export-pdf         | PASS | PASS | non         | 0
```

**Preuve du problème (config A)** — trace Wine `+relay,+seh`, extrait conservé dans
`results/<horodatage>/runs/A-edit-save-reopen-r1/*.evidence.txt` :

```
## KERNEL32.dll.SystemTimeToTzSpecificLocalTimeEx @ 0x…C68218
code=80000100 (EXCEPTION_WINE_STUB) flags=1   → processus interrompu avant l'enregistrement
```

En config A, `edit-save-reopen` émet `OPENED, MODIFIED` puis **meurt** (pas d'événement `SAVED`, fichier
non modifié) : échec **franc**, pas un faux succès. `export-pdf` sort proprement en code 2 (« indisponible »)
sans produire de PDF : échec du scénario, mais **pas** un faux succès (le programme n'a rien annoncé de faux).

**Coût** (moyennes par exécution) : CPU ≈ 0,07–0,11 s, mémoire de pointe ≈ 88–95 Mo (arbre de processus
Wine complet), durée ≈ 1–4 s. Création d'un préfixe propre ≈ 0,4 s (copie par liens durs d'un gabarit).

**Correctif généré (config B)** — produit automatiquement en **2,9 s** :
- une DLL de compatibilité pour `KERNEL32` : 33 exports renvoyés vers Wine, **3 fonctions fournies**
  (`SystemTimeToTzSpecificLocalTimeEx`, `Heap32First`, `Heap32Next`), toutes en **stratégie A** (absence
  déclarée : retour 0 + `ERROR_CALL_NOT_IMPLEMENTED` = 120) ;
- un contrat déclaratif classe A : `bdfpdf.dll` fourni depuis le catalogue du labo (empreinte vérifiée) ;
- une **capsule TOML** (`capsules/bdfedit-25205f9b77d4.capsule.toml`), statut `experimental`,
  `synthetic = true`, version Wine exacte, preuves de trace par fonction, résultats de scénarios ;
  le **linter de sûreté** la valide (0 erreur).

## 3. Réponses aux questions de la mission

**A. Une API problématique a-t-elle été identifiée ?** **Oui**, automatiquement, avec preuve : trois
fonctions `KERNEL32` non implémentées par Wine 11.0 (`SystemTimeToTzSpecificLocalTimeEx` absente ;
`Heap32First`/`Heap32Next` en `@ stub`), confirmées à l'exécution par l'exception `EXCEPTION_WINE_STUB`
(0x80000100), plus une dépendance absente (`bdfpdf.dll`, classe A).

**B. Le prototype a-t-il généré un correctif ?** **Oui** : une DLL de compatibilité (stratégie A) + un
contrat déclaratif classe A, en 2,9 s, encapsulés dans une capsule signable conforme à la table de sûreté.

**C. Ce correctif a-t-il amélioré un scénario réel ?** **Oui, sur le programme de test synthétique** :
trois scénarios passent de l'échec au succès. « Réel » s'entend ici au sens d'**effets réels vérifiés**
(pas seulement un code de retour), **pas** au sens d'un logiciel commercial. Voir §5.

**D. Les effets attendus ont-ils été vérifiés ?** **Oui**, par des oracles indépendants du programme :
empreinte sha256 du fichier avant/après, présence du contenu attendu, relecture après réouverture, et
**lecture du PDF par `pdftotext`** (outil tiers). **0 faux succès** sur 24 exécutions : aucun scénario
n'est compté « réussi » sans effet constaté par un tiers.

**E. Le prototype réduit-il le travail manuel ?** **Oui, en effort humain** — c'est là que se situe le
gain, et il faut être précis sur la mesure :

- **Config B (automatique)** : **2,9 s de machine, 0 étape humaine**. Le labo lit la trace, identifie la
  fonction, lit son prototype, choisit la stratégie sûre, **génère** le code (implémentation + liste des
  33 renvois), compile et applique le correctif à une copie — sans intervention.
- **Config C (manuel de référence)** : la **compilation seule** prend 0,73 s (mesuré, 3 fois), mais elle
  est précédée d'un travail humain que le labo supprime entièrement : lire la trace relay pour trouver la
  fonction fautive, retrouver son prototype, écrire l'implémentation, **énumérer à la main les ~34 imports
  et écrire les renvois du `.def`**, puis tester. Ces fichiers (`manual-fix/`) ont été écrits à la main ;
  l'énumération des renvois est fastidieuse et sujette à erreur.

**Mesure honnête** : les temps **machine** sont comparables (les deux compilent une DLL, ~0,7 s). Le gain
mesurable et défendable est la **suppression totale des étapes humaines de diagnostic et d'écriture**. Nous
**ne** revendiquons **pas** un chiffre de « minutes humaines économisées » : il n'a pas été mesuré au
chronomètre sur un panel de développeurs (c'est l'objet de l'expérience à 4 bras du rapport, hors v0.1).

**F. Que reste-t-il à développer pour automatiser davantage ?**

1. **ABI x86 (`__stdcall`)** : décorer les exports `@N` selon le nombre d'octets d'arguments (la v0.1
   suppose l'ABI Win64 où l'appelant nettoie la pile). 79 des 182 binaires du corpus réel sont en i386.
2. **Stratégie S en pratique** : la v0.1 n'utilise que la stratégie A (absence déclarée). Les cases
   autorisées de la table (requête d'état sans donnée, mutation locale) restent à exercer, sous teinte.
3. **Validation sur logiciels tiers réels** : non faite ici (voir §4 et §5).
4. **Base d'API enrichie** : prototypes manquants pour certaines fonctions (ex. `ktmw32`), sémantique des
   semi-stubs, effets de bord attendus par fonction.
5. **Chaîne de signature et d'escalade** : signer les capsules validées ; marquer candidate à l'escalade
   au-delà de 25 shims ; distinguer capsule `experimental` / `validated` dans l'application.
6. **Applications graphiques** : oracles pour les effets visibles (le labo est aujourd'hui orienté console
   et fichiers).

## 4. Largeur : balayage statique d'un corpus réel (sans exécution)

Pour mesurer la **portée de l'analyseur** sur de vrais binaires, 182 fichiers PE de quatre logiciels réels
(SumatraPDF, suite Sysinternals, Python 3.12 embarqué, 7-Zip) ont été analysés **statiquement, sans les
exécuter** (`python3 -m bdflab.sweep`, `results/sweep.json`).

| Catégorie d'import | Sites |
|---|---|
| **Durs, corrigeables (classe B)** — l'appel échouerait (`@ stub` / export absent) | **63** (dans **25** applications) |
| Durs, refusés (classe D, sécurité) | 3 |
| Durs, à escalader (classe C) | 2 |
| Semi-stubs (implémentation partielle de Wine, fonctionne souvent) | 651 |
| DLL de runtime manquantes (classe A, catalogue) | 0 |
| DLL privées de l'application (présentes à l'exécution) — **exclues** | 2 273 |

Architectures : 103 binaires x86-64, 79 i386. Exemples de fonctions dures réelles trouvées :
`FindPackagesByPackageFamily` (Autoruns), `TdhGetEventInformation` (Sysmon, ETW),
`Heap32ListNext`/`EndTask` (Process Explorer), `GetOwnerModuleFromTcpEntry` (TCPView),
`PssCaptureSnapshot` (python312.dll). À l'inverse, **7zr.exe** ne présente **aucun** import dur : le labo
prédit correctement « rien à corriger » (vrai négatif — pas de correctif fabriqué inutilement).

**Honnêteté du balayage** : un import problématique en analyse **statique** n'est pas forcément **atteint**
à l'exécution. Ce balayage mesure l'étendue de l'analyseur, **pas** un taux de panne ni un taux de
réparation. Les DLL privées des applications ont été exclues pour ne pas gonfler les chiffres, et les
semi-stubs sont comptés à part (ils fonctionnent souvent). **Aucun de ces 182 binaires n'a été exécuté ni
corrigé** : l'exécution de binaires tiers téléchargés sort du périmètre sûr de ce banc.

## 5. Scénario 3 — verdict explicite

> Hypothèse (rapport) : « BDF résout **automatiquement plusieurs catégories** de problèmes sur des
> applications **inconnues**, avec des effets **vérifiés** et **sans corruption**. »

**Verdict : l'expérience NE CONFIRME PAS le Scénario 3. Elle ne l'infirme pas non plus ; elle ne permet
pas d'en juger.** Ce qui est établi, et ce qui ne l'est pas :

- **Établi** : sur un cas **synthétique**, le prototype résout automatiquement **plusieurs catégories**
  (A déclaratif + B comportement), avec **effets vérifiés** par des oracles indépendants et **sans
  corruption ni faux succès**, de façon reproductible. C'est une **preuve de fonctionnement du prototype**.
- **Non établi** : les applications étaient **connues** (écrites pour le labo), pas inconnues ni
  commerciales. Les vrais logiciels n'ont été analysés que **statiquement**. Les binaires réels qui
  présentent des stubs durs sont surtout des outils système (Sysinternals) nécessitant pilotes/services,
  difficiles à mettre en scénario sous Wine ; les applications « sages » du corpus (7-Zip, SumatraPDF) ne
  touchent pas de stub dur. **Aucune validation d'effet à l'exécution sur un logiciel tiers n'a été faite.**

Conformément à la consigne, le Scénario 3 **n'est pas présumé**. Un cas synthétique validé prouve le
mécanisme, pas l'efficacité sur des logiciels commerciaux.

## 6. Limites et honnêteté

- **Cas synthétique** : le programme de test a été écrit pour appeler des stubs réels de Wine et se
  dégrader proprement ; il est marqué `synthetic = true` partout et séparé des résultats réels.
- **Voie de compatibilité** : DLL de compatibilité + redirection d'import sur une copie jetable (le moteur
  Wine n'est pas modifié, l'original reste intact). Limite ABI x86 (voir §3.F).
- **Statique ≠ exécution** : §4.
- **Pas de falsification** : aucune réponse fabriquée sur licence, identité, sécurité, signature,
  activation (classe D refusée) ; stratégie S jamais utilisée en v0.1.
- **Durée** : expérience exécutée sur Wine 11.0 figé ; tout changement de version invalide les capsules.

## 7. Reproduire

```bash
./run.sh                 # tout : compile, lance A/B/C (2 exécutions), écrit results/ + capsule
python3 -m pytest tests/ -q
```

Preuves conservées : `results/<horodatage>/results.json` (verdicts, mesures), `runs/*/` (traces
compressées, extraits de preuve, fichiers produits), `capsules/*.toml`, `results/sweep.json`.

---

## 8. Extensions vérifiées après le premier jalon

Trois capacités ajoutées après l'expérience initiale, chacune mesurée, toujours sur cas synthétique
(sauf la portée statique, sur vrais binaires sans exécution). Voir aussi `docs/IDEATION-graal.md`
(carnet d'idéation : hypothèses de rupture, avec vérification d'antériorité — non démontrées).

**8.1 Durcissement de la sûreté.** La détection sécurité/identité couvre désormais LSA, jetons,
privilèges, ACL/SID, descripteurs de sécurité, comptes, credentials ; une règle « noyau/pilote/service »
route vers l'escalade (classe C). Ces fonctions ne sont **jamais** corrigées automatiquement. Vérifié par
+11 tests (37 au total) et sur une vraie application (voir 8.2) : `GetSecurityInfo`,
`LsaEnumerateAccountRights`, `LookupAccountNameW`, `CertGetNameStringW` sont **refusées** ; `NtLoadDriver`,
`NtUnloadDriver` **escaladées**.

**8.2 Portée : génération STATIQUE pour une vraie application** (`results/realapp-procexp64.json`).
Sur Process Explorer 64 bits (Sysinternals, vrai binaire, **sans l'exécuter**), le générateur produit en
~17 s un correctif **multi-DLL** cohérent : 10 DLL de compatibilité (kernel32 : 231 exports renvoyés,
7 fournis ; user32 : 190/3 ; advapi32 : 79/5 ; ntdll : 29/11 ; etc.) et une copie corrigée qui importe les
10 proxys. Toutes les DLL compilent et exportent correctement. **Honnêteté :** ceci prouve que le
générateur produit des artefacts valides et bien structurés pour un vrai binaire complexe, et qu'il refuse
les fonctions de sécurité et de pilote ; **ce n'est PAS** une preuve que Process Explorer fonctionne sous
Wine (il requiert un pilote noyau). Aucun binaire tiers n'a été exécuté.

**8.3 Découverte automatique de la réponse (stratégie S), vérifiée par oracle**
(`bdflab/speculate.py`, `tools/demo_speculate.py`, `results/speculate-demo.json`). Jusqu'ici seule la
stratégie A (absence déclarée) était exercée. Nouveau : le labo **découvre seul** la bonne réponse d'un
stub en essayant toutes les réponses sûres autorisées et en laissant l'oracle d'effet trancher. Sur
`shcore.IsAppCompatModeEnabled` (vrai stub Wine 11.0), scénario où l'enregistrement est conditionné à la
capacité :

| Réponse essayée | Résultat du scénario | Oracle d'effet | Faux succès |
|---|---|---|---|
| A — FALSE + ERROR_CALL_NOT_IMPLEMENTED | le programme renonce (exit 2), **aucun enregistrement** | échec | non |
| S — TRUE (succès fabriqué) | enregistrement effectué | **réussite** (fichier correct) | non |

Le labo retient **S**, avec la justification : « aucune réponse A ne passe ; S fait passer l'oracle, sans
faux succès, et la table de sûreté l'autorise pour une requête d'état sans tampon de sortie (teinté,
journalisé) ». Aucun humain n'a indiqué « renvoie TRUE » : la réponse est **découverte et prouvée par
l'effet**. C'est la moitié active de la Fidélité dirigée par le binaire, et elle reste strictement bornée
par la table de sûreté (la stratégie S demeure interdite sur tampon de sortie, mutation persistante,
sécurité, synchronisation).

Ces extensions renforcent le prototype ; elles **ne changent pas** le verdict §5 : efficacité sur logiciel
tiers réel toujours non démontrée à l'exécution.

**8.4 Pré-réponse par analyse des branches (idée n°3 du carnet), vérifiée par oracle**
(`bdflab/branch_hint.py`). Le labo lit le code **juste après** l'appel à la fonction manquante (Capstone) :
il repère le test de la valeur de retour et le saut conditionnel, puis reconnaît la branche d'erreur
précoce (petit code constant chargé puis sortie) de la branche nominale (résultat d'un appel conservé).
Il en déduit la réponse qui garde le programme sur son chemin nominal et **ordonne** les candidats de la
recherche (§8.3) — sans jamais ajouter de réponse que la table de sûreté interdit. Sur
`IsAppCompatModeEnabled`, l'indice statique prédit « non-nul → S d'abord » (confiance moyenne) ; la recherche
confirme que S est la seule réponse qui fait passer l'oracle : **prédiction statique et preuve dynamique
concordent**. Sur `SystemTimeToTzSpecificLocalTimeEx`, l'indice reconnaît le repli documenté ; la sûreté
n'autorise que A, qui passe. L'indice est un accélérateur et une explication, pas un juge : l'oracle reste
seul juge.

**8.5 Fonderie de shims : toute implémentation proposée est jugée par l'oracle (idée n°11)**
(`bdflab/foundry.py`, `tools/demo_foundry.py`, `results/foundry-demo.json`). Une implémentation d'une
fonction manquante peut être proposée par un humain ou par un modèle **hors ligne** ; la fonderie ne lui
fait aucune confiance : elle la compile dans la DLL de compatibilité, rejoue le scénario en préfixe propre
et n'accepte que si **tous** les oracles d'effet passent sans faux succès. À l'exécution, aucune IA ne
tourne : seul le code accepté est embarqué. Démonstration sur `SystemTimeToTzSpecificLocalTimeEx` :

| Proposition | Fichier enregistré avec la marque | Horodatage | Verdict |
|---|---|---|---|
| correcte (délègue au non-Ex) | oui | plausible, chemin **ex** réellement emprunté | **ACCEPTÉE** |
| fausse (renvoie TRUE sans remplir la sortie) | **oui** | `0000-00-00` (tampon laissé vide) | **REJETÉE : faux succès** |

Le point décisif : la proposition fausse **aurait trompé** une vérification naïve (« le fichier est-il
enregistré avec la marque ? » → oui). Seul l'oracle d'effet plus profond (plausibilité de l'horodatage) a
révélé la corruption. C'est le principe du rapport — détection par oracle d'effet, jamais par code de
retour — appliqué à la validation d'implémentations synthétisées. Cela répond à l'obstacle relevé par la
recherche sur la synthèse d'API par modèle (« l'oracle exige de connaître le comportement attendu ») : ici
l'oracle porte sur l'**effet observable** sur données jetables, pas sur une spécification formelle.
