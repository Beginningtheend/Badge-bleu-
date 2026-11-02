# Passation — PolyRE BDF-Lab v0.1

> **Mise à jour du 2 novembre 2026 (soir).** Ce dossier date du début de la session cloud. Depuis, le laboratoire
> **existe** (branche `claude/polyre-bdf-lab-prototype-tc4bkz`, 23 modules, 82 tests, expérience A/B/C 2/8 → 8/8,
> généralisation mesurée, recherche 2026). Le §6 ci-dessous est obsolète. Pour reprendre le travail en local avec
> votre VM Windows, utilisez `PROMPT-NOUVELLE-CONVERSATION-LOCALE.md` ; la conversation entière est dans
> `CONVERSATION-integrale.md` ; les résultats dans `../../RESULTATS.md`.

Dossier de passation pour une nouvelle session Claude Code. Il contient tout ce qui a été dit et produit dans
la conversation de recherche (15 octobre → 2 novembre 2026), le contexte PolyRE, et les écarts à corriger
dans la mission BDF-Lab avant de l'exécuter.

Fichiers du dossier :

- `HANDOFF.md` — ce fichier (contexte, décisions, écarts, conseils).
- `mission-recherche-graal.txt` — le prompt original de la mission de recherche fondamentale (15 oct.).
- `mission-bdf-lab-v0.1.txt` — le prompt original de la mission Claude Code BDF-Lab v0.1 (2 nov.).
- `PROMPT-NOUVELLE-SESSION.md` — le prompt prêt à coller dans la nouvelle session.

Le rapport scientifique complet est un doc Claude :
**https://claude.ai/artifact/2AmRmfLTw33LEWtyanaffZ** (« PolyRE — Recherche d'une architecture
d'exécution universelle »). Il faut le lire avec l'outil Artifact / Claude Docs (action `read`), pas par
web-fetch. Il peut aussi être exporté en Markdown ou PDF depuis le doc pour être déposé dans le dépôt du labo.

---

## 1. Contexte PolyRE (tel que décrit par l'utilisateur)

- PolyRE automatise la préparation et le lancement d'une application Windows sous Linux, avec Wine comme
  moteur de compatibilité ; le moteur de décision fonctionne **sans IA**.
- Parcours : analyse de l'EXE/MSI (architecture, type d'installateur, indices de dépendances) → choix d'une
  configuration → environnement séparé par application → téléchargement de composants depuis un **catalogue
  de sources officielles avec vérification d'empreinte** → lancement → profil conservé sur disque.
- Dispose de diagnostics, de résultats conservés localement et de réparations connues et limitées ;
  ne sait pas encore inventer une correction pour n'importe quelle API Windows.
- Tests déjà faits : Notepad++ réussi (≈ 29 s au premier lancement, 5,8 s au second, téléchargement exclu) ;
  KeePass : recherche de Mono déclenchée mais téléchargement échoué (piste : DNS absent du banc) ;
  LibreOffice en cours.
- Axes de recherche existants (noms seulement, contenu non fourni) : UEC, Janus ABI/Runtime, Contract Fusion,
  Semantic Islands, Memory Ownership Core, OracleForge, NT-Organ, AutoPort, HARP, Dual-World Execution,
  Hardware Contract Engine, REA/Ghidra.
- Le dépôt du moteur s'appelle **NoxPolyRE** (mentionné dans la mission). Il n'a pas été inspecté dans
  cette conversation : la nouvelle session doit le trouver et le lire en lecture seule.
- Projet frère : NoxOS (noxos.eu). Objectif long terme : lancer un maximum de logiciels Windows depuis NoxOS.

## 2. Ce que la recherche a conclu (résumé du rapport)

**Verdict.** Il n'y a pas de « faille » universelle. Le CPU n'est pas en cause (même x86-64) ; ce qui
sépare Windows de Linux est la longue traîne sémantique (syscalls NT, chargeur PE, objets/handles, SEH,
registre, win32k, pilotes graphiques). Une compatibilité à 100 % ne se prouve pas sans code Microsoft :
un test révèle un écart, jamais l'absence d'écart. Elle se **mesure** sur un corpus figé.

**Architecture principale retenue : une échelle d'escalade pilotée par contrats.**
- Laboratoire hors ligne (OracleForge) : même scénario sur un Windows de référence et sur PolyRE, diff des
  traces, re-test automatique, contrats versionnés et signés, sans IA à l'exécution.
- Sur le PC : analyse EXE/MSI + routeur → **niveau 0** Wine/Proton + contrats A et B → **niveau 1**
  personnalité NT isolée (picoprocess, Syscall User Dispatch, ntsync, shims générés) → **niveau 2** NT-Organ
  (noyau NT-compatible libre en micro-VM ; GPU non résolu) → **niveau 3** VM Windows complète (dernier
  recours, licence de l'utilisateur ; question ouverte : la garder ou l'exclure du produit).
- Une application ne monte un niveau que si un contrat échoue.

**Quatre classes de contrats** (utilisées partout, y compris dans BDF-Lab) :
| Classe | Exemple | Où ça se résout | Automatisable |
|---|---|---|---|
| A, déclarative | clé de registre, police, runtime, override de DLL | profil PolyRE, niveau 0 | oui ; PolyRE le fait déjà en partie |
| B, comportement simple | valeur de retour, code d'erreur, drapeau | shim généré, niveau 0 ou 1 | en partie |
| C, sémantique profonde | ordonnancement, mémoire, service ou pilote noyau | escalade niveau 2 ou 3 | non |
| D, hors périmètre | DRM, activation, anti-triche | refus explicite | non |

**Sources vérifiées qui comptent pour le labo :**
- Syscall User Dispatch (kernel.org) — interception des syscalls d'une région du process, sans ptrace.
- ntsync : version complète dans Linux 6.14 ; utilisé par Wine 10.15-dev puis **Wine 11.0 stable (13 janv. 2026)**.
- Wine 11.0 : nouveau WoW64 pleinement supporté, Wayland, Vulkan 1.4, H.264 via Vulkan Video.
- Drawbridge (MSR, ASPLOS 2011) — library OS NT en picoprocess, code Microsoft non distribuable.
- virtio-gpu native context — >99 % du natif sur msm, AMDGPU dans Mesa 25.0 ; **invités Linux seulement**.
  Pour un invité Windows, seul un pilote 3D expérimental (viogpu3d, via virgl) existe, instable selon son auteur.
- ReactOS 0.4.15 (21 mars 2025) ; cible déclarée Windows Server 2003 (source secondaire).
- Hyperlight (Microsoft, open source, Rust) — micro-VM sans noyau en 1–2 ms, KVM ou mshv.
- Tsai et al., EuroSys 2016 — méthode de « complétude pondérée » d'un système de compatibilité (sur Linux) ;
  à transposer à Windows (expérience 2 du rapport).

## 3. La piste n°6 « Fidélité dirigée par le binaire » (BDF) — ce qu'il faut savoir

Hypothèse **originale, non démontrée**, à tester, qui ne vise aucune compatibilité générale :

1. **Surface d'observation.** Un programme ne peut distinguer que ce qu'il teste : codes de retour comparés,
   champs de structure lus, branches d'erreur présentes dans son code. Tout ce qu'il ne regarde jamais n'a
   pas besoin d'être fidèle.
2. **Réponse optimiste.** Pour un comportement observable mais non implémenté, le runtime choisit une
   réponse qui garde le programme sur son chemin nominal, la journalise et marque le profil « spéculatif ».
3. **Capsule.** Fichier déclaratif signé, indexé par identité du binaire (sha256, imphash, version),
   contenant contrats + preuves + résultats de scénarios ; « glisser l'exe » = chercher sa capsule.

**Antériorité trouvée** (à citer dans le labo) :
- Rinard et al., *Failure-oblivious computing*, OSDI 2004 — valeurs fabriquées pour les lectures invalides ;
  marche sur des serveurs car la distance de propagation d'erreur est courte.
- Long, Sidiroglou-Douskos, Rinard, *RCV / recovery shepherding*, PLDI 2014 — sur binaires x86 nus, valeur
  par défaut + suivi d'influence + blocage des appels système influencés ; 17/18 cas acceptables.
- Ammons, Bodík, Larus, *Mining specifications*, POPL 2002 ; Acharya & Xie, FASE 2009 — le client encode le contrat.
- Wine : les stubs `.spec` lèvent `EXCEPTION_WINE_STUB` (0x80000100), non continuable, dans
  `dlls/winecrt0/stub.c` ; restent nécessaires pour `GetProcAddress`. Le canal `WINEDEBUG=+relay` journalise
  appels et retours (`+relay,+tid,+timestamp` ; `RelayExclude` dans le registre pour alléger).
- umu-protonfixes — correctifs par jeu en Python, indexés par ID, appliqués au lancement (surtout overrides,
  winetricks, registre = classe A).
- imphash (Mandiant 2014) — clé secondaire d'identité de binaire.

**Deux stratégies de réponse optimiste :**
- **A, absence déclarée** : répondre « non pris en charge » par un code que le programme sait traiter
  (`ERROR_CALL_NOT_IMPLEMENTED` = 120, `E_NOTIMPL`, `NULL` + last error). Rien n'est fabriqué.
- **S, succès fabriqué** : répondre comme si ça avait réussi. Le programme croit à un effet qui n'a pas eu lieu.

**Sept conditions de sûreté pour S** (toutes requises) : requête sans donnée ; aucun effet persistant promis ;
hors sécurité ; cohérence observationnelle ; confinement (teinte, blocage des écritures influencées) ;
réversibilité (journal + ré-exécution) ; **validation hors ligne** (en produit, S ne vient que d'une capsule
validée ; la spéculation en direct se limite à A).

**Table de sûreté :**
| Classe d'API | A | S |
|---|---|---|
| Requête d'état sans donnée (IsX, GetX → statut) | oui | oui, sous conditions 4–6 |
| Requête avec tampon de sortie (lecture, conversion, énumération) | oui | **non** : donnée fabriquée = corruption |
| Mutation locale au processus (propriété d'objet/fenêtre) | oui | oui, sous teinte |
| Mutation persistante (fichier, registre, réseau, presse-papiers) | oui | **non**, sauf labo sur données jetables |
| Sécurité, identité, licence | **non** | **non** |
| Synchronisation, temps, ordonnancement | non | non : classe C, escalade |

**Risques nommés** : corruption silencieuse, faux succès (« Enregistrer » répond OK sans écrire), régression,
dette masquée (stubs « temporaires » éternels), sécurité. Détection par **oracles d'effet**, jamais par code
de retour.

**Format de capsule proposé (TOML)** — à reprendre tel quel dans le générateur :
```toml
[identity]
sha256 = "…"                 # exécutable principal : clé exacte
imphash = "…"                # clé secondaire : version voisine, mode dégradé
product = "Exemple"          # VERSIONINFO
version = "3.2.1"
publisher = "…"              # signature Authenticode, si présente

[runtime]
polyre = ">=0.4, <0.5"
wine = "11.0"

[[contract]]                 # classe A, déclaratif
kind = "dll-override"
dll = "msvcp140"
mode = "native"
source = "catalogue:vcrun2022"
sha256 = "…"

[[shim]]                     # classe B, comportement
dll = "exemple.dll"
function = "ExempleQueryFeature"
strategy = "A"               # A = absence déclarée, S = succès fabriqué
when = "arg0 == 7"           # prédicat optionnel sur les arguments
returns = 0
last_error = 120             # ERROR_CALL_NOT_IMPLEMENTED
evidence = ["trace:2026-11-02T10:14/call-8812"]

[validation]
scenarios = ["ouvrir-modifier-enregistrer", "exporter-pdf"]
results = { "ouvrir-modifier-enregistrer" = "pass", "exporter-pdf" = "pass" }
runs = 2
machines = 2
date = 2026-11-02
expires_on = "changement de runtime"

[provenance]
generated_by = "bdf-lab 0.1"
reviewed_by = ""
signature = "…"
```
Sept critères de validité : identité exacte (sinon « dégradée », A seulement) ; scénarios passés avec oracle ;
lint de sûreté ; reproduction sur 2 exécutions indépendantes ; signature du labo (sinon spéculatif, A) ;
aucun binaire tiers (catalogue + empreinte seulement) ; bornée (> 25 shims ⇒ candidate à l'escalade).

**Protocole expérimental du rapport (à 4 bras)** : 1 Wine 11.0 seul · 2 Wine + résolveur optimiste automatique ·
3 Wine + correctifs manuels (temps chronométré) · 4 bras 2 puis manuel sur le reste (temps chronométré).
Corpus 30 applications pré-enregistrées (20 qui échouent, 10 témoins), 5 scénarios à oracle d'effet par
application = 150 points. Seuils pré-enregistrés : réussite +10 points, faux succès ≤ 2 %, corruption 0,
régression 0, **H1 = temps humain réduit d'au moins 30 %**. Wilcoxon apparié + bootstrap ; chassé-croisé de
deux développeurs. Phases : 0 outillage (un stub Wine réel intercepté et résolu) → 1 surface statique
(rappel ≥ 70 % sinon le statique n'est qu'une priorisation) → 2 bras 1-2 → 3 bras 3-4 → décision.
La mission BDF-Lab v0.1 est une version réduite à 3 bras (A/B/C) et 1 application : c'est cohérent
avec la **phase 0** du rapport.

## 4. Décisions et règles posées par l'utilisateur (à respecter telles quelles)

- Interdiction de modifier le moteur PolyRE principal tant qu'un bénéfice reproductible n'est pas démontré.
- Prototype isolé, dans un projet indépendant `polyre-bdf-lab/`, applications de test et données jetables.
- Mesurer sur des fonctionnalités complètes (ouvrir, modifier, enregistrer, rouvrir, vérifier par un outil
  indépendant), pas sur le seul démarrage.
- Un succès annoncé sans fichier présent et correct = **échec** (faux succès).
- Aucune falsification de licence, identité, sécurité, signature, activation.
- Une capsule expérimentale ne s'applique jamais silencieusement à un logiciel de production.
- Objectif : déterminer si la méthode réduit le temps de développement des correctifs par application,
  pas revendiquer une compatibilité universelle. Vision long terme : « déposer l'exe et ça marche ».
- Scénario attendu par l'utilisateur, non démontré : « Scénario 3 — véritable percée : BDF résout
  automatiquement plusieurs catégories de problèmes sur des applications inconnues, avec des effets vérifiés
  et sans corruption. » Le labo doit pouvoir le confirmer **ou l'infirmer**, pas le présumer.

## 5. Écarts à corriger dans `mission-bdf-lab-v0.1.txt` avant exécution

1. **« pages 7 à 15 »** — le rapport est un doc Claude sans pagination. Lire les sections :
   « Les cinq meilleures pistes » → « Piste expérimentale n°6 » (énoncé, antériorité, limites
   statique/dynamique, conditions de sûreté, risques, format des capsules, protocole), puis
   « Architecture principale » (classes A/B/C/D) et « Expériences à confier à Astra » (expérience 7).
2. **« Une réponse optimiste ne peut être expérimentée que sur les catégories autorisées »** — précision :
   la condition 7 du rapport réserve la **stratégie S** aux capsules validées hors ligne. Dans le labo
   (données jetables), S est autorisée uniquement sur les classes « requête d'état sans donnée » et
   « mutation locale au processus », sous teinte et journal ; **jamais** sur tampon de sortie, mutation
   persistante, sécurité, synchronisation. La stratégie **A** est le défaut.
3. **Wine 11.0** — figé pour toute l'expérience ; noter la version exacte dans chaque capsule et dans
   `RESULTATS.md`. Si seul Wine 10.x ou 11.x est disponible via la distribution, le dire et ne pas mélanger.
4. **Cas synthétique** — il est autorisé mais doit être marqué `synthetic = true` dans la capsule et
   séparé des résultats sur logiciels réels dans `RESULTATS.md` (critère 9 de la mission).
5. **Interception des stubs** — point d'entrée réaliste pour la phase 0 : `EXCEPTION_WINE_STUB`
   (0x80000100) levée par `__wine_spec_unimplemented_stub`. Trois voies, par ordre de simplicité :
   (a) une DLL de remplacement (override `native`/`builtin` via `WINEDLLOVERRIDES`) qui exporte la
   fonction et répond A ou S ; (b) un hook `GetProcAddress`/IAT dans un injecteur ; (c) un patch Wine local
   (plus lourd, à éviter en v0.1). Le rapport ne tranche pas ; la phase 0 doit choisir et documenter.
6. **Imphash** — calculable avec `pefile` (`pe.get_imphash()`), déjà installable par pip.
7. **Ressources** — le PC est partagé par plusieurs agents : limiter à 1–2 Wine simultanés, timeouts
   (`timeout` + `wineserver -k` propre), aucun test sur disque avec erreurs SMART, aucune suppression.

## 6. État de l'environnement de la session précédente (cloud, ne pas confondre avec le PC)

- Conteneur cloud Linux, 2 cœurs, 7,8 Go RAM, ~30 Go libres ; **ni Wine ni mingw installés** ; gcc/clang
  présents ; `apt-get` et `pip` joignables ; `pefile` installé par pip.
- Aucun code du labo n'a été écrit dans cette session (interrompue avant). Le dépôt `polyre-bdf-lab/`
  reste à créer entièrement.
- Le dépôt NoxPolyRE n'était pas accessible ici ; la nouvelle session doit le localiser (ou le cloner) et
  le lire sans le modifier.

## 7. Question ouverte laissée dans le rapport (commentaire dans le doc)

Garde-t-on le **niveau 3** (VM Windows complète, licence de l'utilisateur) dans le produit, ou l'exclut-on ?
Sans réponse, le labo n'a pas besoin d'en tenir compte : il ne travaille qu'au niveau 0.
