Extraits du rapport PolyRE (doc Claude https://claude.ai/artifact/2AmRmfLTw33LEWtyanaffZ), extraits le 2026-11-02 pour polyre-bdf-lab. Le reste du rapport n'est pas reproduit ici.

# PolyRE — Recherche d'une architecture d'exécution universelle

2026-10-15 · @Shadow

## Verdict : pas de faille universelle, un goulot identifié

Aucune des 20 pistes ne supprime l'incompatibilité par un mécanisme unique : le vrai goulot est la connaissance des comportements NT, pas le moyen de les exécuter.

- **Le CPU n'est pas en cause.** Windows et Linux exécutent le même x86-64. Ce qui diffère est l'ABI du système : syscalls NT, chargeur PE, objets et handles, SEH, registre, win32k, pilotes graphiques.
- **Nécessaire ou historique.** La sémantique des objets et de la synchronisation est nécessaire, car les applications en dépendent : c'est pourquoi le noyau Linux a reçu [ntsync](https://www.phoronix.com/news/Linux-6.14-Char-Misc-NTSYNC) et que [Wine 11.0 l'utilise](https://www.omgubuntu.co.uk/2026/01/wine-11-0-released/amp). Les numéros de syscalls et la disposition du PEB/TEB sont historiques, mais figés de fait par les applications.
- **Triangle de contraintes.** Fidélité maximale, aucun code Microsoft, aucune VM : on en tient deux, rarement trois. Wine choisit « sans code Microsoft, sans VM » et paie la longue traîne des comportements.
- **Où se trouve la rupture possible.** Dans l'automatisation de l'acquisition des contrats de comportement et dans une échelle d'isolation par application, pas dans un mécanisme matériel.

---

## Piste expérimentale n°6 : fidélité dirigée par le binaire

Hypothèse à tester, non démontrée : un runtime n'a besoin d'être fidèle que sur ce qu'un exécutable peut observer, et peut compléter le reste par des réponses optimistes confinées. L'expérience doit dire si cela réduit le temps de production des correctifs par application ; elle ne vise aucune compatibilité générale.

### Énoncé

1. **Surface d'observation.** L'ensemble des résultats d'API que l'exécutable peut distinguer : codes de retour comparés, champs de structure lus, branches d'erreur présentes dans son code.
2. **Réponse optimiste.** Pour un comportement observable mais non implémenté, le runtime choisit une réponse qui garde le programme sur son chemin nominal, la journalise et marque le profil « spéculatif ».
3. **Capsule.** Un fichier de contrats validés en laboratoire, indexé par l'identité du binaire et appliqué au lancement ; « glisser l'exe » revient à chercher sa capsule.

### Antériorité

Chaque pièce existe déjà quelque part ; le neuf serait leur assemblage dans un runtime de compatibilité, et la mesure en temps humain.

| Travail | Ce qu'il a montré | Ce qu'on en reprend | Ce qui manque |
|---|---|---|---|
| [Failure-oblivious computing](https://www.usenix.org/conference/osdi-04/enhancing-server-availability-and-security-through-failure-oblivious-computing) (Rinard et al., OSDI 2004) | Fabriquer des valeurs pour les lectures invalides et jeter les écritures invalides laisse des serveurs continuer ; cela marche parce que leur distance de propagation d'erreur est courte | Le principe de la valeur fabriquée et le critère de distance de propagation | Une application de bureau accumule un état dans ses documents : distance longue |
| [Recovery shepherding, RCV](https://people.csail.mit.edu/fanl/papers/rcv-pldi14.pdf) (Long, Sidiroglou-Douskos, Rinard, PLDI 2014) | Sur des binaires x86 nus, fabrique une valeur sur division par zéro ou déréférence nulle, suit l'influence de cette valeur et bloque les appels système influencés ; 17 erreurs sur 18 donnent une sortie acceptable | Le modèle de confinement : teinter les réponses optimistes et bloquer les effets persistants teintés | Vise des erreurs internes, pas des API absentes ; 18 cas |
| [Mining specifications](https://dblp.uni-trier.de/rec/conf/popl/AmmonsBL02.html) (Ammons, Bodík, Larus, POPL 2002) | Un programme débogué révèle dans ses traces le protocole d'API qu'il attend | L'hypothèse que le client encode le contrat | Traces d'exécution et protocoles temporels ; rien sur les valeurs de retour d'un binaire |
| [Mining API error-handling specifications](https://dblp.dagstuhl.de/rec/conf/fase/AcharyaX09.html) (Acharya, Xie, FASE 2009) | Extrait statiquement, depuis du code client C, les vérifications d'erreur attendues : 62 spécifications et 264 défauts sur 82 paquets | La lecture des chemins d'erreur du client comme spécification | Source C ; l'approximation statique est déjà imprécise avec le source |
| Wine, stubs des fichiers .spec | Une fonction déclarée `stub` lève EXCEPTION_WINE_STUB, non continuable ([stub.c](https://goma.googlesource.com/wine/+/master/dlls/winecrt0/stub.c)) ; les stubs restent nécessaires pour GetProcAddress ([wine-devel](https://www.winehq.org/pipermail/wine-devel/2017-February/116094.html)) | Le point d'interception du prototype | Les semi-stubs implémentés avec un FIXME ne lèvent rien |
| Wine, canal +relay | Journalise les appels d'API avec arguments et retours ([page de manuel](https://manpages.ubuntu.com/manpages/noble/man1/wine-stable.1.html)) | Le traçage dynamique sans instrumentation à écrire | Journaux de plusieurs Mo à Go, ralentissement |
| [umu-protonfixes](https://openwinecomponents.org/) | Correctifs par jeu en Python, indexés par identifiant, appliqués au lancement : winetricks, overrides de DLL, registre | Le modèle de distribution, et la référence du correctif écrit à la main | Pas d'identité par empreinte, pas de validation automatique |
| [imphash](https://cloud.google.com/blog/topics/threat-intelligence/tracking-malware-import-hashing) (Mandiant, 2014) | Deux fichiers de même imphash ont la même table d'imports | Une clé secondaire pour reconnaître une version voisine | Collisions possibles entre binaires différents |

### Limites de l'analyse statique et apports du traçage dynamique

Sur un x86 nu, l'analyse statique donne une surface d'observation partielle et bruitée : elle sert à prioriser, pas à décider. Acharya et Xie jugent l'approximation statique déjà imprécise avec le code source ; sans lui, la reconstruction du flot et l'analyse de pointeurs ne sont qu'approchées.

| Information | Analyse statique du binaire | Traçage dynamique (+relay, hooks) |
|---|---|---|
| Imports à l'édition de liens | Oui, table d'imports | Oui |
| Imports dynamiques (GetProcAddress, résolution par hash) | Non, sauf chaînes en clair | Oui, à l'appel |
| .NET, Java, Electron, tout code JIT | Non : le x86 n'existe qu'à l'exécution ; il faut un analyseur IL ou JS séparé | Oui, via les appels natifs finaux |
| Appels COM par table virtuelle | Faible, cible indirecte | Oui |
| Codes de retour comparés | Partiel : comparaisons proches de l'appel ; perdu si la valeur transite par la mémoire | Oui, sur les chemins exercés |
| Champs de structure lus | Partiel, décalages constants | Oui, avec des points d'arrêt mémoire coûteux |
| Chemins d'erreur (MessageBox, ExitProcess, journal) | Oui, par le graphe de flot | Seulement s'ils sont exercés |
| Ordre, délais, réentrance | Non | Partiel, et l'observation les perturbe |
| Effets attendus (fichier écrit, clé créée) | Non | Oui, par différence d'état après scénario |
| Code packé ou obfusqué | Non | Oui, sauf protection anti-analyse (classe D, exclue) |
| Couverture | Tous les chemins, y compris infaisables | Seuls les chemins des scénarios |

Conséquence : le statique fournit un ensemble candidat avec des faux positifs ; le dynamique le confirme sur les scénarios. L'écart entre les deux mesure ce que les scénarios ne couvrent pas. La phase 1 du protocole mesure la précision et le rappel du statique contre le dynamique avant d'en dépendre.

### Conditions de sûreté d'une réponse optimiste

Une réponse optimiste n'est sûre que si son influence ne peut pas atteindre un état persistant sans vérification : c'est le critère de confinement de RCV, transposé aux API. Deux stratégies sont distinguées.

- **A, absence déclarée.** La fonction répond « non pris en charge » par un code que le programme sait traiter (ERROR_CALL_NOT_IMPLEMENTED, E_NOTIMPL, NULL avec dernier code d'erreur). Le programme dégrade une fonctionnalité ; rien n'est fabriqué.
- **S, succès fabriqué.** La fonction répond comme si elle avait réussi. Le programme croit à un effet qui n'a pas eu lieu.

Conditions, toutes requises pour une réponse S :

1. **Requête sans donnée.** La fonction renvoie un statut ou un handle opaque, jamais un tampon que le programme relira ou enregistrera.
2. **Aucun effet persistant promis.** La fonction n'écrit ni fichier, ni registre, ni réseau, et ne modifie aucun état partagé entre processus.
3. **Hors sécurité.** Jamais pour jetons, ACL, cryptographie, signatures, licences, droits ou anti-triche (classe D).
4. **Cohérence observationnelle.** La valeur est compatible avec toutes les vérifications ultérieures visibles dans la trace ; une contradiction rejette la réponse.
5. **Confinement.** La réponse est teintée ; tout effet persistant influencé (écriture de fichier, de registre, envoi réseau) est bloqué ou mis en quarantaine jusqu'à validation.
6. **Réversibilité.** Réponse journalisée avec son site d'appel ; une ré-exécution avec la réponse alternative reste possible.
7. **Validation hors ligne.** En produit, une réponse S ne vient que d'une capsule validée ; la spéculation en direct chez l'utilisateur se limite à la stratégie A. Choix de conception à confirmer par l'expérience.

| Classe d'API | Stratégie A | Stratégie S |
|---|---|---|
| Requête d'état sans donnée (IsX, GetX renvoyant un statut) | Oui | Oui, sous les conditions 4 à 6 |
| Requête avec tampon de sortie (lecture, conversion, énumération) | Oui | Non : une donnée fabriquée est une corruption |
| Mutation locale au processus (propriété d'objet ou de fenêtre) | Oui | Oui, sous teinte |
| Mutation persistante (fichier, registre, réseau, presse-papiers) | Oui | Non, sauf en laboratoire sur données jetables |
| Sécurité, identité, licence | Non | Non |
| Synchronisation, temps, ordonnancement | Non | Non : classe C, escalade |

Pourquoi plus prudent que Rinard : ses serveurs traitaient des requêtes indépendantes, et une erreur n'affectait guère la suivante. Une application de bureau accumule un état dans un document et des réglages ; une valeur fabriquée peut y survivre des mois.

### Risques : corruption silencieuse, faux succès, régression

Les trois risques se détectent par la vérification de l'effet, jamais par le code de retour ; le protocole en fait des mesures.

| Risque | Mécanisme | Exemples | Détection | Parade |
|---|---|---|---|---|
| Corruption silencieuse | Une valeur fabriquée entre dans une donnée enregistrée | Attributs de fichier devinés, puis écrasement ; paramètres régionaux devinés, puis dates mal enregistrées ; taille de tampon fausse, puis écriture tronquée | Différence de l'état persistant après scénario contre l'attendu ; fichiers canaris | Teinte et blocage (condition 5) ; S interdit sur les tampons |
| Faux succès | La fonctionnalité semble réussir sans effet | « Enregistrer » répond OK sans écrire ; impression vers nulle part ; export vide | Oracle d'effet par scénario : fichier présent et lisible par un lecteur de référence | Tout succès sans oracle compte comme un échec |
| Régression | Un stub masque un échec qu'une version suivante aurait révélé ; capsule de la version N appliquée à N+1 ; deux stubs cohérents séparément, incohérents ensemble | Témoin qui passait et qui échoue | Corpus témoin rejoué à chaque changement ; revalidation des capsules à chaque version du runtime | Expiration des capsules ; identité stricte |
| Dette masquée | Les succès optimistes retirent la pression qui mène aux vraies implémentations | Stub « temporaire » toujours là deux ans après | Inventaire public des stubs par application | Chaque stub porte une date et un ticket |
| Sécurité | Réponse optimiste à une vérification de droits | Contrôle d'accès court-circuité | Lint de capsule (condition 3) | Refus catégorique |

### Format des capsules et critères de validité

Une capsule est un fichier déclaratif signé, sans aucun binaire tiers, qui lie une identité de binaire à des contrats et aux preuves qui les justifient.

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

Critères de validité, tous requis :

1. **Identité.** sha256 exact ; à défaut, imphash et version identiques, capsule marquée « dégradée » et limitée à la stratégie A.
2. **Scénarios.** Chaque scénario listé passe sur la version de runtime visée, oracle d'effet compris.
3. **Sûreté.** Aucun shim ne viole la table de sûreté ; un lint le vérifie à la construction.
4. **Reproduction.** Résultat reproduit sur au moins deux exécutions indépendantes, machines ou préfixes propres distincts.
5. **Signature.** Signée par le laboratoire ; une capsule non signée ne s'applique qu'en mode spéculatif, stratégie A.
6. **Aucun binaire tiers.** Seulement des références au catalogue de sources officielles, avec empreinte.
7. **Bornée.** Au-delà d'un nombre fixé de shims (proposé : 25), l'application est candidate à l'escalade, pas à une capsule.

Toute montée de version majeure du runtime invalide la validation ; la revalidation relance les scénarios automatiquement.

### Protocole expérimental

Quatre bras sur un même corpus pré-enregistré ; la mesure décisive est le temps humain pour faire passer une fonctionnalité complète, pas le démarrage de l'application.

[Schéma : prototype isolé · 6 étapes, une boucle de rejeu, import différé vers PolyRE]

Le prototype vit dans un dépôt séparé et ne produit que des capsules ; un échec aux oracles renvoie au résolveur avec la réponse alternative, et le moteur PolyRE n'importe rien tant que H1 n'a pas tenu deux fois.

**Les quatre bras**

| Bras | Configuration | Intervention humaine | Ce qu'il mesure |
|---|---|---|---|
| 1 | Wine 11.0 seul | Aucune | Ligne de base |
| 2 | Wine 11.0 + résolveur optimiste automatique | Aucune | Gain brut des stubs générés, faux succès, régressions |
| 3 | Wine 11.0 + correctifs écrits à la main (pratique actuelle : scripts façon protonfixes, réparations PolyRE) | Développeur, temps chronométré | Coût actuel d'un correctif |
| 4 | Bras 2, puis correctifs à la main sur ce qui reste | Développeur, temps chronométré | Réduction du temps humain : la question de la piste |

**Corpus et données**

- 30 applications choisies et publiées avant toute mesure : 20 qui échouent ou échouent partiellement sous Wine (AppDB Bronze ou Silver, ou tests PolyRE), 10 témoins qui marchent (Platinum) pour mesurer les régressions.
- Diversité imposée : Win32 natif, MFC, .NET, Qt, Delphi, Electron ; installateurs MSI et NSIS ; bureautique et utilitaires d'abord, aucun jeu au départ.
- Exclues : DRM, anti-triche, activation en ligne (classe D) ; applications dont la licence interdit l'analyse.
- Données : documents jetables générés par script, aucune donnée personnelle, préfixe Wine neuf à chaque exécution.

**Scénarios : cinq fonctionnalités complètes par application**

| Scénario | Oracle d'effet |
|---|---|
| Installer, puis lancer jusqu'à la fenêtre principale | Fenêtre détectée, aucune boîte d'erreur, processus stable 60 s |
| Ouvrir, modifier, enregistrer un document | Le fichier produit contient la modification, lu par un lecteur de référence indépendant |
| Exporter ou imprimer vers un fichier | Fichier valide (PDF ouvrable, image décodable) et contenu attendu |
| Changer un réglage, quitter, relancer | Le réglage a persisté |
| Fonction propre à l'application (plugin, réseau local, presse-papiers) | Effet vérifiable défini à l'avance |

**Métriques et seuils pré-enregistrés**

| Métrique | Définition | Seuil proposé |
|---|---|---|
| Réussite vérifiée | Scénarios dont l'oracle passe, sur 150 | Le bras 2 dépasse le bras 1 d'au moins 10 points |
| Faux succès | L'application signale un succès et l'oracle échoue | 2 % des scénarios du bras 2 au plus |
| Corruption | Sortie différente de l'attendu alors que la présence du fichier passe | 0 ; tout cas documenté |
| Régression | Scénario témoin qui passe au bras 1 et échoue au bras 2 | 0 |
| Temps humain | Minutes de développeur jusqu'au passage de l'oracle, bras 3 contre bras 4 | H1 : réduction d'au moins 30 % à réussite égale |
| Dette | Stubs optimistes encore présents après le correctif final | Rapportée, sans seuil |

Analyse : 150 points de scénario ; temps comparés par application, appariés (test de Wilcoxon des rangs signés), intervalles de confiance par bootstrap ; seuils fixés avant la première mesure. Biais principal : un développeur qui corrige une application au bras 3 la connaît déjà au bras 4. Parade : deux développeurs en chassé-croisé, chacun prenant la moitié des applications dans chaque bras, ordre tiré au sort ; l'effectif reste faible, un résultat positif appelle une réplication, pas une intégration.

**Phases et portes**

1. **Phase 0, outillage (environ 2 semaines).** Intercepter un stub Wine réel et y répondre, sur 3 applications pilotes. Porte : un stub réel intercepté et résolu de bout en bout.
2. **Phase 1, surface statique.** Analyseur sur le corpus ; précision et rappel contre les traces. Porte : rappel d'au moins 70 % sur les codes de retour comparés, sinon le statique n'est plus qu'une priorisation.
3. **Phase 2, bras 1 et 2.** 150 scénarios, deux exécutions complètes. Porte : réussite +10 points, faux succès 2 % au plus, régression 0 ; sinon arrêt et rapport.
4. **Phase 3, bras 3 et 4.** Étude de temps en chassé-croisé. Porte : H1 tient.
5. **Décision.** Intégration à PolyRE seulement si H1 tient sur deux exécutions indépendantes ; sinon la piste est archivée avec ses données.

**Règles d'isolement**

- Dépôt séparé ; aucune modification du moteur PolyRE pendant l'expérience ; seul point de contact, le format de capsule.
- Wine 11.0 figé pour toute la durée ; toute mise à jour relance la phase 2.
- Hôte jetable (conteneur ou VM) ; pas de réseau, sauf scénario qui l'exige.
- Scripts, corpus, journaux et capsules publiés avec le rapport.

**Ce qui réfuterait la piste**

- Rappel statique sous 50 %, et des scénarios dynamiques qui couvrent déjà le travail de correction : aucune économie.
- Faux succès au-dessus de 5 %, ou une corruption passée à travers les oracles.
- Temps humain non réduit, ou alourdi par le débogage de stubs faux.
- Blocages du corpus surtout de classe A, déjà couverte par PolyRE, ou de classe C, hors de portée des stubs. Les correctifs protonfixes actuels sont surtout des overrides, des verbes winetricks et des clés de registre, donc de classe A : ce scénario est plausible et l'expérience 1 doit le mesurer.

**Distance à « glisser l'exe »**

Elle se mesure : part du corpus qui passe ses cinq scénarios sans aucune étape humaine, capsule connue ou stratégie A suffisante. Elle sera rapportée telle quelle, sans extrapolation hors corpus.

---

## Architecture principale : l'échelle pilotée par contrats

La solution la plus générale trouvée n'est pas un mécanisme mais un routage : chaque échec est classé, puis confié au mécanisme le moins coûteux qui le résout.

[Schéma : architecture principale · laboratoire hors ligne et 4 niveaux d'exécution]

Le laboratoire tourne hors ligne ; sur le PC, une application démarre au niveau 0 et ne monte que lorsqu'un contrat échoue.

### Quatre classes de contrats

| Classe | Exemple | Où elle se résout | Automatisable |
|---|---|---|---|
| A, déclarative | Clé de registre, police, runtime, override de DLL | Profil PolyRE, niveau 0 | Oui ; PolyRE le fait déjà en partie |
| B, comportement simple | Valeur de retour, code d'erreur, drapeau | Shim généré, niveau 0 ou 1 | En partie |
| C, sémantique profonde | Ordonnancement, mémoire, service ou pilote noyau | Escalade au niveau 2 ou 3 | Non |
| D, hors périmètre | DRM, activation, anti-triche | Refus explicite | Non |

### Pourquoi c'est la piste la plus générale

- **L'usage des API est concentré, au moins sous Linux.** Une étude de toutes les applications d'Ubuntu 15.04 trouve quelques API très utilisées puis une chute brutale, et propose une métrique de complétude pondérée ([Tsai et al., EuroSys 2016](https://www.cs.unc.edu/~porter/pubs/syspop16.pdf)).
- **Un indice côté Windows, informel.** Un relevé des imports statiques a trouvé 22 961 fonctions utilisées sur environ 127 600 exportées, sur 6 615 fichiers ([OpenRCE](https://www.openrce.org/blog/print_view/1192/Some_Win32_API_usage_statistics)). Il ignore les appels résolus dynamiquement ; l'expérience 2 doit le refaire proprement.
- **Le principe différentiel est déjà prouvé.** Le TestBot de Wine exécute les tests de conformité sur des VM Windows avant intégration ([WineHQ](https://list.winehq.org/hyperkitty/list/wine-bugs@list.winehq.org/thread/DX2RUP4LWXNKXKX7LAPOMTLDWRA2M5ZF/)). La nouveauté serait de dériver les contrats des traces d'applications, et non de tests écrits à la main.
- **Limite.** OracleForge automatise la détection et la spécification d'un écart. L'implémentation reste manuelle pour la plupart des contrats B et pour tous les C.

### Rattachement proposé des axes PolyRE

D'après leurs seuls noms, sans leur contenu : OracleForge devient le laboratoire ; Contract Fusion et Hardware Contract Engine, la bibliothèque de contrats ; Janus et UEC, la personnalité du niveau 1 ; HARP et Dual-World, l'isolation du niveau 1 ; NT-Organ, le niveau 2 ; AutoPort et REA/Ghidra, les outils d'analyse du labo. Semantic Islands et Memory Ownership Core n'ont pas de place établie ici.

---

## Expériences à confier à Astra

Les expériences 1 et 2 passent en premier : elles disent pour un coût faible si la piste OracleForge vaut l'effort. Les seuils sont proposés, pas mesurés.

| # | Expérience | Ce qu'elle tranche | Critère de réussite proposé | Effort |
|---|---|---|---|---|
| 1 | Lancer au moins 100 applications dans PolyRE et classer chaque échec en A, B, C ou D | Quelle part des échecs est automatisable | Deux classements indépendants concordent sur 90 % des cas | Moyen |
| 2 | Mesurer la couverture d'API pondérée d'un corpus Windows avec la méthode de [Tsai et al.](https://www.cs.unc.edu/~porter/pubs/syspop16.pdf) : imports PE, puis traces | Si l'usage de Win32 est concentré, donc si un ensemble fini de contrats suffit | Une courbe « contrats implémentés → applications couvertes » qui s'aplatit | Faible en statique |
| 3 | Diff de traces sur 5 applications (Notepad++, KeePass, LibreOffice et 2 autres) entre un Windows de référence et PolyRE | Part des écarts convertible en contrats A ou B sans humain | 50 % des écarts convertis automatiquement | Élevé |
| 4 | Tester le pilote 3D expérimental [viogpu3d](https://github.com/virtio-win/kvm-guest-drivers-windows/pull/943) dans une VM Windows, puis sous ReactOS | Viabilité du GPU au niveau 2 | Un rendu D3D10 stable pendant 30 minutes | Moyen |
| 5 | Démarrer ReactOS en micro-VM avec virtio-fs ; lancer Notepad++ et KeePass | Viabilité du niveau 2 sur un PC de 8 Go | Moins de 1 Go de RAM et démarrage en moins de 10 s | Moyen |
| 6 | Mesurer l'aller-retour NT vers Linux : Syscall User Dispatch face à des mondes séparés par EPT | Utilité de Dual-World | Gain d'au moins 2× sur l'aller-retour | Élevé |
| 7 | Protocole à quatre bras de la piste 6 : prototype isolé, 30 applications, 150 scénarios à oracle d'effet, étude de temps en chassé-croisé | Si les réponses optimistes réduisent le temps humain des correctifs sans faux succès | H1 : temps humain réduit d'au moins 30 %, faux succès 2 % au plus, régression 0, reproduit deux fois | Élevé |
