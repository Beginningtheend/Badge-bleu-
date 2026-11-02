# Recherche fondamentale 2026 — existe-t-il un « graal » Windows → Linux ?

> Synthèse d'une recherche menée le 2026-11-02 : recherches web (état de l'art 2025-2026), lecture de
> sources primaires, et trois éclaireurs (sous-agents) sur des angles distincts — recompilation statique,
> traces « dorées » (WinDbg TTD), personnalité NT sur Linux. **Tout ce qui suit est sourcé ou marqué
> incertain.** Les sections des éclaireurs sont marquées *(à compléter)* tant que leur rapport n'est pas
> rendu. Ce document ne contredit pas le verdict du rapport PolyRE (« pas de faille universelle ») ; il le
> **précise** avec les faits de 2026 et dégage ce qui est réellement nouveau.

---

## 0. Réponse courte

**Non, il n'y a pas de graal technique** — et 2026 le confirme de trois façons : (1) Linux a *refusé* de
mettre une personnalité NT dans le noyau et a choisi un mécanisme d'espace utilisateur (Syscall User
Dispatch) que Wine 11.5 utilise désormais ; (2) les micro-VM à la Hyperlight ne peuvent pas héberger
Windows ; (3) le code noyau NT reste fermé (WSL est open source, mais son pilote noyau `lxcore.sys` ne
l'est pas, et ni Prism ni le noyau NT n'ont été ouverts).

**Mais une rupture non technique est apparue en 2026**, et elle est exploitable : des agents de code
réparent déjà de vraies applications « irrécupérables » sous Wine (preuve terrain : Alderson, mars 2026), et
**Wine refuse structurellement ce code** (règle « clean room » : pas de code généré par modèle). Les
correctifs assistés ne peuvent donc vivre **qu'à côté de Wine**, dans une couche de capsules. Personne
n'a encore industrialisé cette couche avec **sûreté, oracles d'effet, reproductibilité et partage par
empreinte**. C'est exactement ce que fait le labo, et c'est là que se trouve l'avantage réaliste.

---

## 1. État de l'art 2026 (vérifié)

- **Wine 11.0** (janv. 2026) : ntsync et nouveau WoW64 achevés. **Wine 11.5** (mars 2026) : prise en charge de
  **Syscall User Dispatch**. **Wine 11.6** : relance du pilote Android. Des gains « 678 % » circulent : à
  prendre avec prudence (source secondaire enthousiaste). [Phoronix](https://www.phoronix.com/linux/WINE),
  [GamingOnLinux](https://www.gamingonlinux.com/2026/03/wine-11-5-released-with-support-for-syscall-user-dispatch-on-linux/)
- **ARM** : Hangover = Wine + FEX/Box64 ; builds ARM64EC. Dépendance à des émulateurs tiers, intégration non
  stabilisée en amont. [GameNative builds](https://github.com/GameNative/proton-wine/releases)
- **Apple Game Porting Toolkit** : GPTK 2 sorti de bêta (janv. 2025), positionné comme **outil de
  diagnostic** pour développeurs ; GPTK 4 (WWDC, juin 2026) ajoute la prise en charge du **codage par
  agents** (compétences d'agent et exemples open source), toujours en bêta. **Confirmé par CodeWeavers**
  (juin 2023) : « Apple chose to use CrossOver's source code as their emulation solution for the Game Porting
  Toolkit. We did not work with Apple on this tool. » — GPTK est donc du **Wine (CrossOver)** sous une couche
  graphique propriétaire (D3DMetal). Un acteur majeur a choisi la traduction Wine-style, pas une nouvelle
  architecture, et y ajoute des agents en 2026.
  [CodeWeavers](https://codeweavers.com/blog/mjohnson/2023/6/6/wine-comes-to-macos-apple-s-game-porting-toolkit-powered-by-crossover-source-code),
  [OSNews](https://www.osnews.com/story/136223/apples-game-porting-toolkit-is-wine/),
  [developer-tech](https://www.developer-tech.com/news/game-porting-toolkit-2-exits-beta-mac-gaming-drive/),
  [AppleInsider](https://appleinsider.com/articles/26/06/08/game-porting-toolkit-4-ushers-in-support-for-agentic-coding)
- **Microsoft** : WSL open source (mai 2025, MIT) — **mais** `lxcore.sys` (le pilote noyau de WSL1, lignée
  Drawbridge/pico-process) **reste fermé**, de même que `p9rdr.sys`. Aucune ouverture de Prism ni du noyau NT.
  [BleepingComputer](https://www.bleepingcomputer.com/news/microsoft/microsoft-open-sources-windows-subsystem-for-linux-at-build-2025/),
  [The Register](https://www.theregister.com/2025/05/19/microsoft_wsl_open_source/)

## 2. Le fait structurant : Wine refuse le code généré par IA

La FAQ développeur de Wine répond **« Non »** au code généré par modèle : « The copyright and licensing
status of LLM-generated code is not well-defined […] we can't assume that we are allowed to distribute that
code under the Wine license » (motif : **provenance et licence**, pas qualité). *Libellé cité via deux
sources secondaires (mixed-news ; un ticket GitHub citant les Clean Room Guidelines : « Don't use an LLM tool
to generate code ») — la page primaire du wiki WineHQ n'était pas accessible depuis ce banc (protection
anti-robot).* Cas réel : un correctif de
plantage de *Space Marine 2* sous ntsync, prototypé par modèle, a dû être déposé **en prose** (bug Wine
60397, 27 sept.) ; le mainteneur Proton a renvoyé vers l'amont (« any changes that can go to upstream wine,
should go upstream first »), sans fusion. Valve n'a pas de politique propre et s'aligne sur Wine.
[mixed-news](https://mixed-news.com/en/valve-proton-maintainer-wine-llm-code-rule-space-marine-2-fix/),
[Wine (Wikipedia)](https://en.wikipedia.org/wiki/Wine_(software))

**Conséquence architecturale (décisive pour PolyRE)** : tout correctif assisté par modèle est **expulsé** de
Wine et de Proton. Son seul foyer possible est une **couche externe** — DLL de compatibilité + capsules —
qui ne modifie pas Wine. C'est le choix du labo (`shimgen`, `foundry`, `capsule`), désormais imposé par
la politique du projet amont lui-même, pas seulement par prudence.

## 3. La preuve terrain : un agent répare une vraie application « garbage »

Martin Alderson (17 mars 2026) : *Airflow* (streaming AirPlay/Chromecast), classée **« garbage »** sur
l'AppDB WineHQ. Un agent de code l'a rendue « presque entièrement fonctionnelle » en **~2 heures** : il a
**construit un stub `powrprof.dll` avec mingw** (le mécanisme même de nos DLL de compatibilité), diagnostiqué
chaque plantage en décompilant les DLL, puis **patché en binaire** (code caves, sauts conditionnels,
constantes de sockets). Citation : « I wasn't even aware you could compile Windows DLLs on Linux like that. »
[Alderson](https://martinalderson.com/posts/using-agents-and-wine-to-move-off-windows/)

**Ce qui manque à ce précédent — et que le labo apporte :**

| Faiblesse observée chez Alderson | Réponse du labo |
|---|---|
| Vérification = une capture d'écran ; AirPlay non testé ; « presque » fonctionnel | **Oracles d'effet** indépendants ; faux succès = échec |
| Patchs binaires ad hoc, y compris du gestionnaire d'exceptions | **Table de sûreté** A/B/C/D ; sécurité et noyau refusés |
| Reproductible sur sa machine seulement (un gist) | **Préfixes propres, 2 exécutions, capsule** indexée par empreinte |
| Résultat perdu pour les autres utilisateurs | **Communs** adressé par contenu |
| « Extrêmement impliqué pour 99,99 % des humains » | Flux **« déposer l'exe »** |

Autrement dit : la direction marche sur du **réel** (ce n'est plus seulement notre cas synthétique), et la
valeur ajoutée réaliste n'est pas un nouveau moteur, c'est **l'industrialisation sûre** de ce que l'agent
fait à la main. *Honnêteté : au 2026-11-02, c'est le **seul** rapport public directement comparable que j'aie
trouvé (aucun équivalent avec un autre agent) — un précédent, pas encore une tendance mesurée.*

## 4. Ce que Linux a refusé : la personnalité NT en noyau

Le débat de 2020 (patchs Krisman, LWN) visait à aider Wine à émuler les syscalls Windows ; la communauté a
rejeté la « glu » en noyau (sécurité, encombrement) et retenu un **trampoline en espace utilisateur** —
devenu Syscall User Dispatch (5.11+), aujourd'hui utilisé par Wine 11.5. L'idée eBPF a été évoquée, jamais
construite. **Toute personnalité NT sera donc en espace utilisateur (voie Wine) ou en VM** ; une voie
« noyau Linux + NT » à la Longene n'a pas d'avenir amont.
[LWN](https://lwn.net/Articles/826313/), [exposé OSS EU 2020](https://static.sched.com/hosted_files/osseu2020/5c/Gabriel_Krisman_Bertazi-Efficient-syscall-emulation-for-gaming-on-linuxsyscall-emulation-dark.pdf),
[doc noyau SUD](https://docs.kernel.org/admin-guide/syscall-user-dispatch.html)

## 5. Micro-VM : Hyperlight n'héberge pas Windows

Hyperlight (Microsoft, Rust, mars-avril 2025) démarre un invité en 1-2 ms mais n'offre « qu'une plage
mémoire et un CPU » : pas d'OS, invités Wasm/no_std. **Il ne peut pas héberger Windows.** Un « NT-Organ » en
micro-VM suppose donc d'**écrire soi-même** l'OS-bibliothèque NT — d'où la question ReactOS (§9).
[Phoronix](https://www.phoronix.com/news/Microsoft-Hyperlight-Wasm), [devclass](https://www.devclass.com/development/2025/03/27/microsoft-releases-experimental-hyperlight-wasm-micro-vms-that-run-wasm-apps/1623450)

## 6. Communs : la lacune « adressé par contenu » est confirmée

umu-launcher / UMU-Database / UMU-Protonfixes (partagés par Bottles, Heroic…) indexent les correctifs par
**magasin + identifiant de jeu**, pas par empreinte de binaire ; rien sur une clé sha256/imphash, rien sur
un typage de sûreté ou une signature. L'adressage par contenu (notre `commons.py`) reste inédit dans cet
écosystème. [umu-launcher](https://github.com/Open-Wine-Components/umu-launcher), [OWC](https://ulwgl.openwinecomponents.org/)

## 7. Oracles : Wine utilise déjà « Windows comme oracle » — par API, pas par application

Les tests de conformité Wine doivent **d'abord passer sur un vrai Windows** (WineTest quotidien) ; c'est un
oracle **par API**, écrit à la main. Le complément manquant est un oracle **par application** (effet d'un
scénario) — ce que font nos oracles d'effet, et ce que pourrait apporter une trace « dorée » par application
(§8). [Wiki conformance](https://forge.fsky.io/brunodev85/wine/wiki/Conformance-Tests)

## 8. Trace « dorée » par application (WinDbg TTD) — *éclaireur rendu*

**Ce que TTD est vraiment.** Time Travel Debugging (lignée Nirvana/iDNA, MSR, VEE 2006) traduit en binaire
tout le flux d'**instructions** en espace utilisateur : état initial des registres, valeurs lues en mémoire
(seulement si elles diffèrent d'un cache de prédiction), événements de séquencement (syscalls, exceptions,
threads, modules) ; les écritures ne sont pas journalisées ; ≈ 0,5 bit à 1 octet par instruction, 5-50 Mo/s,
ralentissement 5-20×, espace utilisateur seulement. **La trace ne contient pas « des appels d'API »** : ils
sont reconstruits par `TTD.Calls()` et exigent des symboles (avec les PDB publics : 4 paramètres `uint64`
par défaut, aucune sémantique des tampons de sortie). Le format `.run` est **propriétaire, non documenté,
sans parseur indépendant** (2024-2026 ; format changé en 1.11.592, 2025) ; relecture uniquement via
`TTDReplay.dll` **sur Windows** ; un SDK « TTD Replay API » expérimental existe (mi-2025, en-têtes et exemples
MIT), mais les DLL d'exécution sont téléchargées chez Microsoft, jamais redistribuées. Licence WinDbg
(maj 25/09/2026) : « solely for use on Windows », interdiction de rétro-ingénierie et de redistribution ;
une trace **embarque du code Windows** et des données personnelles ⇒ **partage délicat**.

**Antériorité « trace comme oracle ».** Sur wine-devel, l'idée revient en 2003, 2005 (diff d'un logger
contre `+relay`) et 2018 ; réponses : API Monitor/`+relay` suffisent, comparer à grande échelle est « peu
utile », **une différence n'est pas forcément un bogue** — aucun outil maintenu n'en est sorti. L'oracle
officiel de Wine reste la suite de **tests de conformité** (binaires mingw exécutés par le TestBot sur de
vraies VM Windows ; `todo_wine` = échec connu, `broken()` = bizarrerie Windows tolérée). Précédents réels :
**R2** (OSDI 2008) : record/replay à l'interface Win32 avec **1 301 fonctions annotées** (in/out, tailles,
callbacks), journaux énormes ; **Replay.io** (2021) : shims sur des centaines de fonctions système Windows,
relecture sous Linux — explicitement « rejouer les résultats d'UNE exécution figée », pas un compat layer ;
**apitrace** : capture D3D sur Windows, relecture sous Wine/DXVK — précédent concret, limité au graphique.

**Verdict.** Une trace Windows peut faire foi pour le **sous-ensemble déterministe sans état externe** :
NLS/locale (`CompareString`, `LCMapString`), `FormatMessage`/`LoadString` et ressources, `GetVersion` et
drapeaux de fonctionnalités, `GetSystemInfo`/métriques, registre et chemins shell si instantanés, le
`GetLastError` **attendu** pour un appel donné, fonctions `Rtl*`/Shlwapi pures, dispositions de structures,
résolution SxS/COM. **Non remplaçable** : temps, handles/adresses (ASLR, tas), ordonnancement, GUI/messages,
réseau, E/S asynchrones, GPU, SID — toute divergence d'entrée désynchronise (leçon R2/Replay.io). Pipeline
réaliste : enregistrer sur le Windows **de l'utilisateur** (`ttd.exe -accepteula -noUI -module <dll>`), **distiller
sur Windows** via le Replay SDK vers un format ouvert (JSON appels/paramètres/retours, **sans code Windows**),
puis sous Linux **générer** des tests de conformité ou des **fixtures pour les stubs** — **jamais relire le `.run`
sous Wine**. Trois blocages : (1) verrou technico-juridique (format fermé, DLL Windows sous licence
restrictive, traces porteuses de code Windows ⇒ distiller sur Windows, ne pas partager les traces) ; (2) fossé
sémantique (instructions, pas API ; dépendance aux symboles ; tampons de sortie à annoter) ; (3)
non-déterminisme (sans normalisation lourde, le diff est du bruit). **Réaliste : un générateur de fixtures et
de tests, pas un oracle d'exécution.**

**Lien avec le labo (nouveau).** Les fixtures distillées (« sur Windows, cet appel déterministe renvoie X ») sont
exactement ce qui manque à la **recherche de réponse par oracle** (idée n°1) : au lieu de deviner ou d'essayer
une grille, le labo disposerait, pour le sous-ensemble déterministe, de **la vraie réponse Windows** comme
premier candidat — l'oracle d'effet restant juge. L'idée n°5 passe donc de « enregistre-et-rejoue pour
toujours » (infaisable) à « **distille des fixtures ouvertes qui amorcent la recherche** » (faisable, légal si l'on
ne partage que des résultats d'API, pas des traces).
Sources : [TTD trace file (Microsoft)](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/time-travel-debugging-trace-file-information),
[TTD release notes](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/time-travel-debugging-release-notes),
[WinDbg license terms](https://learn.microsoft.com/en-us/legal/windows-sdk/windbg-preview---software-license-terms),
[Nirvana/iDNA (VEE 2006)](https://www.usenix.org/legacy/event/vee06/full_papers/p154-bhansali.pdf),
[R2 (OSDI 2008)](https://static.usenix.org/events/osdi08/tech/full_papers/guo/guo_html/index.html).
*(Le wiki GitLab de Wine et le TestBot étaient inaccessibles depuis le banc ; ces points reposent sur des
sources secondaires.)*

## 9. Recompilation statique « à la N64Recomp » + Wine pour l'API — *éclaireur rendu*

**Ce qui existe.** *N64Recomp / Zelda 64: Recompiled* (mai 2024) : ROM → C fonction par fonction, appels
indirects via table d'adresses, sauts via `switch` ; **exige un ELF avec symboles** issus des projets de
décompilation communautaires, plus un runtime maison (threads, audio, manettes) et RT64 pour le rendu.
*XenonRecomp / Unleashed Recompiled* (début 2025) : PowerPC → C++, bornes de fonctions depuis `.pdata`, tables
de saut « réglées pour Sonic Unleashed », exceptions non supportées, TOML manuel. Côté **x86/PE** :
*xboxrecomp* (v0.16, oct. 2026) redirige 371 ordinaux noyau Xbox vers Win32, appels indirects = « la partie
la plus dure », « premier lancement = crash attendu » ; *SR* (M-HT) : **2 jeux Windows en ~10 ans**, API
remplacée par du code spécifique (SDL), pas Wine ; *McSema* archivé (août 2022), « fait comme si les
exceptions n'existaient pas », pas de code packé ni auto-modifiant ; *LeanBin* (2024) montre McSema et rev.ng
échouant à lifter+recompiler SPEC CPU2006. Recherche 2026 (UC Irvine, *Elevator* arXiv 2605.08419, *No Bit
Left Behind* 2609.16423) : x86-64→AArch64 statique par force brute, ELF seulement, perf « comparable ou
meilleure que QEMU user-mode » (pas FEX), code auto-modifiant/JIT « fondamentalement incompatible ».
LLM : *LLM4Decompile* 45-53 % de ré-exécutabilité **au niveau fonction** (C/GCC/x86 Linux), rien de
programme entier, rien pour PE. **Recompilation + Wine : aucun projet trouvé.** La couture réelle est
**dynamique** : *Hangover* 11.0 (13 janv. 2026) = Wine + FEX/Box64 branchés sur l'interface CPU WoW64
(`wowbox64.dll`, `libwow64fex.dll`) et ARM64EC (`libarm64ecfex.dll`).

**Pourquoi la console marche et pas Windows.** Matériel figé, binaire unique et autonome (l'« OS » libultra
est lié dans la ROM, donc recompilé avec), ISA à longueur fixe (découverte de code aisée), pas de chargement
dynamique, symboles issus d'années de décomp, aucune protection, **et une équipe d'experts par titre pendant
des mois**. Windows : x86 à longueur variable (séparer code et données est indécidable en général), pas de
symboles, optimisations MSVC (tables de saut, appels terminaux, vtables), surface API immense et **dynamique**
(LoadLibrary/GetProcAddress, COM, callbacks, SEH, TLS), 32 vs 64 bits, packers/DRM fréquents.

**Verdict.** Idée cohérente avec des analogues (xboxrecomp → Win32, SR → SDL, Hangover occupe déjà la
couture), mais **non démontrée**, et viable seulement comme **port artisanal par titre** (vieux jeux 32 bits
non protégés) — pas comme voie générale « n'importe quelle appli ». Ce qu'elle apporterait : supprimer le
JIT x86 sur ARM, autoriser des mods natifs, sortie déterministe. Ce qu'elle **ne résout pas** : l'écart
sémantique (D3D, audio, entrée, threads) reste **100 % celui de Wine**. Trois risques majeurs : (1) récupération
du contrôle (appels indirects/vtables sans symboles → corrections manuelles ; binaires packés/virtualisés =
blocage net, non contourné ; code auto-modifiant impossible) ; (2) frontière ABI avec Wine (callbacks rappelés
par Wine aux adresses d'origine → trampolines et bascule de contexte, cf. corruption McSema #785 ; SEH/C++ EH
à travers les cadres Wine ; thunks 32→64 ; x87) ; (3) gain incertain et intégration lourde (émettre du
ARM64EC conforme est spéculatif, personne ne l'a fait ; aucun avantage prouvé sur FEX/Box64).
Sources : [N64Recomp](https://github.com/N64Recomp/N64Recomp), [XenonRecomp](https://github.com/hedge-dev/XenonRecomp),
[xboxrecomp](https://github.com/sp00nznet/xboxrecomp), [SR](https://github.com/M-HT/SR),
[Hangover 11.0](https://www.phoronix.com/news/Hangover-11.0-Released), [McSema limits](https://github.com/lifting-bits/mcsema/blob/master/docs/Limitations.md),
[Elevator](https://arxiv.org/abs/2605.08419), [LLM4Decompile](https://arxiv.org/html/2403.05286v3).

## 10. Personnalité NT sur Linux (WSL1 à l'envers, Longene, ReactOS) — *éclaireur rendu*

**Principes transférables de Drawbridge / WSL1.** *Drawbridge* (MSR, ASPLOS 2011) : Windows 7 refactorisé en
**OS-bibliothèque** (ntdll et win32k en espace utilisateur, ~150 syscalls NT émulés, surtout des stubs) au-dessus
d'une **ABI hôte de 36 appels** (threads, mémoire virtuelle, flux d'E/S). Le papier désigne la partie la plus
dure : le **modèle d'E/S NT** (sync/async, handles attendables, ports de complétion, APC) ; le registre fut
réimplémenté in-process en 1,3 KLoC (contre 61 KLoC) ; tout accès inter-processus échoue. Une variante
remplaçait la table de syscalls par processus — **ancêtre conceptuel de Syscall User Dispatch** ; une autre
(hvdkpal, ring 0 dans une partition Hyper-V) **préfigure l'option micro-VM**. *WSL1* (2016) : « processus
minimal » (espace d'adressage vide) + *pico provider* (`lxcore.sys`) recevant syscalls et exceptions ; ~235
syscalls ; a exigé des **retouches du noyau NT** (fork, pages 4 Ko, casse) ; règle : traduire vers l'appel natif
si la sémantique colle, réimplémenter sinon. Transfert vers Linux : (1) capturer l'ABI étrangère d'un processus
« vide » = **le rôle de SUD** ; (2) ABI hôte minimale ; (3) traduire/implémenter cas par cas ; (4) accepter des
**ajouts noyau ciblés** — ntsync est à Wine ce que le « fork amélioré » fut à WSL1.

**Longene : ce qu'il fit, pourquoi il mourut.** *Linux Unified Kernel* (Insigma, Chine, 2005-2014, GPLv2) :
modules noyau, **deux tables de syscalls** (`int 0x2e` Windows / `int 0x80` Linux), gestionnaire d'objets,
jetons, registre et fichiers **portés de Wine dans le noyau**, puis des fonctions de wineserver (0.3, 2010).
Jamais faits : WDM, DPC, exports DDK ; dépendait de DLL Wine **modifiées**. Dernière version 1.0-rc2 (janv.
2014, Wine 1.7.10). Aucune source primaire n'explique l'arrêt ; hypothèses convergentes : suivre les internals
de Wine depuis un module hors-arbre, **aucun chemin vers le noyau mainline**, gains jamais mesurés
publiquement, petite équipe. Précédents dans le même sens : *ndiswrapper* (ABI ntoskrnl partielle en module) ne
compile plus (2023) ; `personality(2)` n'a jamais commuté de table de syscalls ; l'eBPF « sur transitions de
privilège » (LKML 2020) n'a pas été fusionné — **c'est SUD qui l'a été**. Revival 2026 : *LSW* (chargeur PE
espace utilisateur, 1 235 stubs Win32, module noyau optionnel), auto-déclaré, **archivé juillet 2026**.

**Carte de faisabilité 2026.** *En espace utilisateur, faible surcoût, prouvé* : syscalls NT bruts émis par du
code PE → **Syscall User Dispatch** (Linux 5.11), amont dans Wine 11.5 (20 mars 2026), coût : un SIGSYS par
syscall émulé ; sémaphores/mutex/événements et attentes atomiques any/all → **ntsync** (6.14), Wine 11.0 ;
threads, SEH par signaux, mémoire (sections via memfd), registre in-process → voie Wine/Drawbridge. *Exige
encore noyau, serveur central ou VM* : espace de noms d'objets **inter-processus** et attentes sur handles
processus/thread/fichier (ntsync couvre 3 types ; ni timers, ni keyed events, ni IOCP, ni APC) ; **APC et attentes
alertables** → wineserver + signaux, pas de primitive noyau ; **E/S asynchrone / IOCP** → io_uring plausible
(analyse de l'éclaireur, aucune implémentation Wine trouvée) ; inter-processus (ReadProcessMemory,
CreateRemoteThread, débogage) → ptrace, partiel ; **pilotes noyau** (anti-triche, DRM, matériel) → ntoskrnl en
espace utilisateur de Wine (**Wine 11.18, 18 sept. 2026** : ~380 commits, extension de `ntoskrnl.exe` pour charger des pilotes
en mode noyau — PnP, identifiants de conteneur — **couverte par des tests**, mais toujours en espace utilisateur :
pas de ring 0, donc l'anti-triche noyau reste hors de portée) ou **micro-VM KVM** ; Hyperlight vise des invités sans
noyau, donc inadapté tel quel.

**ReactOS.** 0.4.15 (21 mars 2025) ; **0.4.16 (29 août 2026)** : installeur graphique, nouveau pilote ATA,
import du KMDF Microsoft, correctif PTE du gestionnaire mémoire, synchronisation Wine 10 ; premier syscall NT6
(juillet 2026, encore no-op) ; **toujours alpha**. Aucun projet « ntoskrnl en bibliothèque sur Linux ».
Verdict : réutilisable comme **référence sémantique** (Ob/Ke/Cm) ou comme **noyau complet dans une micro-VM**
pour les pilotes ; **pas** comme bibliothèque drop-in en espace utilisateur (couplage HAL/Mm/Ke ; GPLv2 vs LGPL
de Wine ; refus historique d'une base Linux par ses développeurs).

**Conclusion §10.** La personnalité NT « sous » Linux a été essayée et abandonnée ; la version moderne et
viable est **celle que Wine a déjà absorbée** (SUD + ntsync, espace utilisateur). Le niveau 2 du rapport
(NT-Organ en micro-VM) reste un **projet lourd et séparé**, justifié seulement pour la classe C (pilotes), pas
un raccourci vers la compatibilité générale.
Sources : [pico-process (Microsoft)](https://learn.microsoft.com/en-us/archive/blogs/wsl/pico-process-overview),
[Drawbridge (ASPLOS 2011)](https://www.cs.unc.edu/~porter/pubs/p291-porter.pdf), [Longene](https://en.wikipedia.org/wiki/Longene),
[ntsync (doc noyau)](https://docs.kernel.org/userspace-api/ntsync.html), [SUD dans Wine 11.5 (bug 48291)](https://bugs.winehq.org/show_bug.cgi?id=48291).

## 10 bis. Retourner le problème : il n'y a pas UN univers Windows, il y en a plusieurs

« Faire tourner les applis Windows » traite un ensemble hétérogène comme un seul problème. En le
**segmentant par runtime**, plusieurs sous-univers ont déjà une voie **sans Wine** — c'est là que le mot
« graal » a un sens partiel et honnête :

| Sous-univers | Voie 2026 | Ce qui reste dur |
|---|---|---|
| **.NET / WPF** | *Avalonia XPF* : applications WPF existantes « with little to no changes required » sur Linux ; 429 contrôles testés, ~90 % fonctionnels (base de compatibilité éditeur) ; XPF 2.0 annoncé (Avalonia 12, Wayland). **Commercial**, licence par appli et par plateforme ; Avalonia lui-même est MIT. | contrôles tiers (ex. Telerik) à réécrire ; P/Invoke vers Win32 |
| **.NET / WinForms** | migration (guides Avalonia), pas exécution telle quelle | tout l'existant WinForms non porté |
| **Electron / Chromium, Java, Qt** | le vendeur livre souvent Linux ; sinon le build Windows tourne généralement bien sous Wine | rien de structurel |
| **Win32 natif (C/C++, MFC, Delphi)** | **Wine** — c'est ici que vivent les stubs, et donc le labo | l'écart sémantique de l'API |
| **Pilotes / anti-triche noyau / DRM** | aucune voie (§11) | décision d'éditeur, pas technique |

**Implication pour PolyRE** : le **routeur** d'entrée devrait d'abord **classer le binaire par runtime**
(PE natif vs assembly .NET vs Electron…) et n'envoyer vers Wine + capsules que le sous-univers Win32 natif.
Pour .NET, l'option « runtime .NET natif Linux + XPF » peut battre Wine en fidélité, au prix d'une licence.
(Vérifications : ce sont des **affirmations d'éditeur**, pas des tests indépendants.)
[Avalonia XPF](https://avaloniaui.net/blog/wpf-modernization-in-2026), [comparatif](https://avaloniaui.net/wpf-compare), [Avalonia](https://github.com/AvaloniaUI/Avalonia)

**L'extrême « partout » reste Wine.** *Boxedwine* fait tourner un Wine 32 bits **non modifié** dans un Linux
émulé, compilé en WebAssembly (navigateur, Linux, macOS, Windows) — environ 25 % de la vitesse hôte selon
son auteur, jouable pour des applications légères, pas pour des jeux exigeants ; activité 2025-2026 non
confirmée par des notes de version officielles. Cela confirme la thèse : même en allant jusqu'au navigateur,
on **transporte Wine**, on ne le remplace pas.
[XDA](https://www.xda-developers.com/boxedwine-emulate-windows-applications-web-browsers/), [Boxedwine wiki](https://github.com/danoon2/Boxedwine/wiki)

## 10 ter. Idée de l'utilisateur : « prendre une vraie copie de Windows et l'adapter à Linux »

L'idée recouvre **trois variantes** au sort très différent.

**(1) Les DLL réelles de Windows (partie utilisateur) sur Wine — oui, en partie : un vrai levier.** Wine charge
depuis toujours une DLL Windows **native** à la place de la sienne (`WINEDLLOVERRIDES`, pratique de winetricks).
La limite est un **plancher** : `ntdll`, `win32u`, `kernelbase`, `kernel32`, `user32`, `gdi32`… parlent au noyau
NT par syscalls que Linux n'a pas — celles-là doivent rester celles de Wine. Au-dessus du plancher, une DLL peut
venir de la **copie licenciée de l'utilisateur** (jamais redistribuée par PolyRE). Syscall User Dispatch
(Wine 11.5) attrape désormais les syscalls bruts émis par du code natif, ce qui élargit ce qui tient. Limites :
dépendances natives en cascade, sémantiques noyau absentes — **l'effet doit être vérifié par oracle** comme
tout correctif. **Implémenté dans le labo** : `bdflab/userwindows.py` (inventaire par empreinte d'un `System32`
fourni par l'utilisateur, règle du plancher, contrat de classe A `dll-native-user-windows`) ; 60 tests ;
**non exercé sur de vraies DLL Windows** (aucun Windows sur ce banc).

**(2) Le vrai noyau NT comme bibliothèque dans un processus Linux — non.** Ring 0, instructions privilégiées,
tables de pages, HAL/ACPI, pilotes de boot : hors VM, il faudrait un émulateur CPU logiciel (lent) ou **modifier le
binaire du noyau Microsoft** (licence : pas de rétro-ingénierie ni de modification ; non redistribuable). Même
Microsoft, **avec le code source**, a dû *refactoriser* Windows 7 pour en faire Drawbridge (§10) ; de l'extérieur,
en binaire, cela ne « s'adapte » pas.

**(3) Le vrai noyau NT dans une micro-VM — cela existe et fonctionne.** C'est le **niveau 3** du rapport.
*WinApps* et **WinBoat** (sept. 2025, pré-1.0 : Docker + KVM + FreeRDP RemoteApp, interface Electron) font tourner
un **vrai Windows caché dans une VM** et affichent chaque application dans sa propre fenêtre sur le bureau Linux.
Fidélité **100 %** (c'est Windows), légal avec la licence de l'utilisateur ; coûts : RAM, démarrage, licence,
GPU difficile, anti-triche souvent bloqué en VM ; et cela contredit l'idéal « sans Windows » — que le rapport
avait, à juste titre, gardé comme **dernier recours**. [The Register](https://www.theregister.com/2026/02/14/winapps_and_winboat/),
[WinBoat](https://github.com/winboat-org/winboat), [GamingOnLinux](https://gamingonlinux.com/2025/09/winboat-is-a-new-linux-app-to-run-windows-apps-with-seamless-integration)

**(3 bis) La VM dormante : « la prendre sans la faire tourner ».** Variante du niveau 3 qui répond à son coût :
on démarre Windows **une fois**, on **gèle** la VM sur disque (mémoire + état : snapshot), et au repos elle ne
consomme **ni CPU ni RAM**. Au lancement d'une appli, on la **restaure** à la demande — ou mieux, on **clone** le
snapshot en copie-sur-écriture pour chaque appli (modèle « serverless » : une image pré-chauffée, un clone par
requête, jeté ensuite) — et on affiche la fenêtre via RemoteApp. Faits : Firecracker (microVM Linux) restaure
un snapshot en quelques millisecondes **avec chargement paresseux de la mémoire** (userfaultfd ; chiffre de
3-5 ms issu d'un billet non vérifié), mais **plusieurs centaines de ms pour 4 Gio sans paresse** (doc d'un
outil tiers), et l'étude académique vHive mesure des fonctions **~95 % plus lentes** après restauration à cause
des défauts de page (la mémoire se recharge à la demande) — d'où un « préchauffage » après réveil. Pour un
invité **Windows** sous QEMU/KVM (`savevm`/`loadvm`), aucune mesure publique trouvée ici ; en pratique, une image
mémoire de plusieurs Gio se recharge en **secondes**, pas en millisecondes, et Windows doit resynchroniser son
horloge au réveil. Ce qui reste vrai même ainsi : licence **par instance en cours** (un clone = une instance),
pas de GPU, anti-triche souvent bloqué en VM. **Verdict : réaliste et utile** — c'est ce qui rend le niveau 3
acceptable comme repli (« ne coûte rien tant qu'on ne s'en sert pas »), mais c'est toujours Windows qui
s'exécute, par intermittence. Lecture passive de la même idée : **ne jamais démarrer** la VM et n'exploiter que son
**image disque** montée en lecture seule (DLL, polices, ruches de registre) — c'est la variante 1, déjà couverte
par `userwindows.py`.
[Firecracker snapshots (billet)](https://mohakchugh.is-a.dev/blog/firecracker-microvm-snapshot-restore-serverless-cold-start),
[vHive (étude)](https://core.ac.uk/download/425539178.pdf)

**Synthèse débloquée par l'idée.** La copie de Windows de l'utilisateur peut jouer **trois rôles** : (a) **catalogue**
de DLL natives pour Wine (variante 1, classe A) ; (b) **repli** de fidélité maximale (variante 3, niveau 3) ;
(c) **oracle** — on y distille les vraies réponses d'API pour amorcer la recherche du labo (§8, stratégie F).
Recommandation pour la question ouverte n°7 du rapport : **garder le niveau 3**, non comme concurrent de Wine
mais comme plafond de fidélité et comme source d'oracle.

## 10 quater. Idée de l'utilisateur, étape suivante : « extraire une fois dans la VM, relancer sans VM »

**L'idée.** Lancer l'application **une fois** dans la VM Windows de l'utilisateur, **capturer tout ce qu'elle
touche** (DLL chargées, clés de registre lues, fichiers, polices, résultats d'API), mettre le nécessaire dans
un **dossier**, puis relancer **sans VM** : Wine fournit le socle, le dossier fournit le reste. La VM n'est qu'un
**four d'extraction** à usage unique. C'est la forme la plus aboutie de la capsule : elle naît d'une **observation
réelle** de l'application sur un vrai Windows, pas seulement d'une analyse statique.

**Précédents (côté Windows).** C'est le principe de la *virtualisation d'application par capture* : le
séquenceur **App-V** « surveille et enregistre tous les processus d'installation et de configuration » pour
produire un paquet diffusé aux clients sans toucher au système cible ; **ThinApp** prend un instantané du système,
laisse installer l'application, enregistre les changements et produit un `.exe`/`.msi` portable. Bonne pratique
documentée : capturer dans une **VM remise à neuf** à chaque fois pour éviter les « faux positifs » d'autres
processus — exactement la discipline des préfixes propres du labo. Aucun de ces outils ne vise Linux : la cible
du paquet, ici, devient un **préfixe Wine**.
[App-V sequencer (Microsoft)](https://technet.microsoft.com/en-us/library/cc817179),
[ThinApp (Computerwoche)](https://www.computerwoche.de/article/2708926/thinapp-macht-anwendungsvirtualisierung-einfach.html),
[séquençage en VM (Advanced Installer)](https://www.advancedinstaller.com/user-guide/sequence-mozilla-firefox-appv.html)

**Implémenté dans le labo (côté Linux).** `bdflab/capture_import.py` lit une capture — export CSV de **Process
Monitor** (depuis la VM Windows) ou **journal Wine** (`+loaddll`, `+relay`) — et produit une **recette** : DLL
natives candidates **hors plancher**, chacune annotée du statut Wine (« absente », « N stubs », « 0 stub ») pour
**prioriser** ce qui vaut la peine d'être extrait ; fichiers de l'appli ; clés de registre à exporter en `.reg` ;
polices ; et la liste des DLL du plancher vues, **jamais remplacées**. Démonstration sur une vraie trace de
l'expérience (`bdfedit`, une exécution) : 46 DLL distinctes chargées, 202 clés de registre lues, **14 DLL
extractibles** au-dessus du plancher (`shell32`, `ole32`, `shlwapi`, `setupapi`, `iphlpapi`…), 15 du plancher.
Sur l'exemple Process Monitor : `propsys` (140 stubs dans Wine) classée avant `version` (0 stub).
`results/recipe-demo-*.json`. Ce qui n'est **pas** fait ici : la capture elle-même sur Windows (aucun Windows sur
ce banc) et la vérification par oracle d'une recette appliquée.

**Limites structurelles (honnêtes).** (1) **Le plancher** : rien sous `ntdll`/`win32u`/`kernelbase`/`kernel32`/
`user32`/`gdi32` ni le noyau n'est extractible — si le problème de l'application est **là**, la qualité de Wine
reste le plafond ; la liste du plancher est volontairement **conservatrice** et pourrait être **affinée
empiriquement** par le labo (remplacer → l'oracle casse ? → plancher). (2) **Couverture** : une capture ne voit
que les chemins exercés — capturer **chaque scénario d'oracle**. (3) **Services vivants** : COM distants, WMI,
Windows Search ne tiennent pas dans un dossier (Wine en fournit certains, partiel). (4) **Licence** : les DLL
extraites restent **chez l'utilisateur** ; seule la **recette** (noms, empreintes, clés, fixtures) circule dans le
communs — un autre utilisateur ré-extrait depuis **son** Windows. (5) Pilotes, anti-triche, DRM : non.

**Pourquoi c'est la bonne forme.** Elle réunit toutes les briques du labo en un seul flux : capture →
recette (classe A : DLL natives, registre, polices) + fixtures distillées (stratégie F) → correctifs générés
pour les stubs restants (classe B) → oracles d'effet → capsule par empreinte → communs. La VM Windows de
l'utilisateur en est le **four**, utilisé une fois par application, puis éteint.

## 10 quinquies. Idée de l'utilisateur, dernier cran : « observer jusqu'au processeur, adapter, reprendre »

L'idée : faire tourner le logiciel dans une VM, **observer tout ce qu'il fait jusqu'au niveau du processeur**,
en déduire l'adaptation, puis **reprendre** l'exécution sans la VM. Vérification en quatre points.

**1. Observer jusqu'au processeur — OUI, outillé et mature.** *PANDA* (MIT Lincoln Lab / NYU, sur QEMU) fait de
l'**enregistrement-rejeu déterministe de tout le système** (i386, x86_64, arm) : il capture les entrées
non déterministes (paquets réseau, lectures disque, souris/clavier) et rejoue l'exécution à l'identique ;
les journaux se compressent et se partagent ; invités Windows pris en charge (vérifier la version courante).
QEMU possède aussi son propre mode `icount` d'enregistrement-rejeu. Côté processus, WinDbg **TTD** (§8). Donc
voir **chaque instruction, chaque syscall, chaque accès** d'une application dans une VM : **réel**.
[PANDA record/replay](https://github.com/chyyuu/panda/blob/master/docs/record_replay.md),
[PANDA (NYU)](https://cyber.nyu.edu/2015/12/08/repeatable-reverse-engineering-panda/),
[PANDA (MIT LL)](https://www.ll.mit.edu/r-d/publications/repeatable-reverse-engineering-greater-good-panda)

**2. Adapter à partir de l'observation — OUI, c'est le labo, en mieux.** Une trace complète donne la carte
**exacte** des dépendances et comportements réellement exercés (API appelées, résultats, fichiers, registre,
syscalls) : la recette d'extraction (§10 quater), les fixtures distillées (§8, stratégie F) et l'identification
des stubs qui comptent deviennent **dynamiques et précises**, là où l'analyse statique ne faisait que prioriser
(« statique ≠ exécution », §4 des résultats). C'est la « surface d'observation » du rapport, rendue exacte.

**3. Reprendre l'exécution depuis l'état du processeur, sans la VM — NON (pour une application vivante).**
Instantané du processus (registres, mémoire) puis continuation sous Wine : ce que contient la mémoire est
l'application **et** les DLL Windows chargées, plancher compris, qui émettent des syscalls NT ; mais surtout
**l'état côté noyau** — handles ouverts (fichiers, sockets, événements), fenêtres et messages, sections, APC,
jetons — **n'existe pas** dans l'instantané et ne se reconstruit pas sous un autre noyau. Précédent : *Transplay*
(Columbia) ne faisait que du **rejeu partiel** pour le débogage, pas une continuation interactive ; CRIU ne migre
pas entre noyaux/ABI différents. Une reprise mi-vol est donc un **rejeu** (ré-exécuter la trace, pour analyser),
pas une application utilisable.

**4. Reprendre « depuis le début » sous Wine avec tout ce qu'on a appris — OUI.** C'est la forme correcte de
l'idée : observer dans la VM, **adapter** (recette + fixtures + correctifs), puis **relancer** l'application
depuis zéro sous Wine + dossier, l'oracle jugeant. Pas universel — l'utilisateur l'admet et c'est exact —, mais
chaque application observée devient un cas **résolu et reproductible**.

**Le cran que l'idée débloque vraiment : la VM comme oracle du NOYAU.** Une trace système complète (PANDA)
montre aussi ce que **le noyau NT a fait** pour l'application (résultats des syscalls, sémantique des objets).
C'est l'oracle qui manque pour le **plancher** : on peut comparer, syscall par syscall, le comportement de
`ntdll`/`win32u` de Wine à celui observé sur le vrai Windows pour **cette** application — un test différentiel
ciblé, là où la suite de conformité de Wine (§7) est générique et écrite à la main. Cela ne corrige pas le
plancher automatiquement (le code reste à écrire, et sans IA pour l'amont, §2), mais cela **désigne précisément**
l'écart. Limites : coût d'une trace système (volumineuse, lente), licence (la trace embarque du code Windows :
distiller, ne pas partager), et non-déterminisme (§8).

**Verdict.** Observer : oui. Adapter : oui, et c'est le cœur du labo. Reprendre mi-vol sans VM : non. Relancer
sous Wine avec ce qu'on a appris : oui. Universel : non — mais **application par application, c'est la voie
la plus complète décrite dans ce document**, et le labo en possède déjà la moitié Linux.

## 10 sexies. Idée de l'utilisateur, synthèse : « Windows comme professeur, Linux comme élève » — la question décisive, mesurée

L'utilisateur résume l'architecture ainsi : la VM Windows **capture** appels, arguments, retours et effets ;
BDF-Lab **compare** aux traces Wine ; PolyRE **génère** un correctif ou identifie ce qu'il faut réimplémenter ;
Linux **teste de nouveaux scénarios sans VM**. Puis il pose la seule question qui compte : *peut-on générer
automatiquement un correctif qui fonctionne sur des actions que la VM n'a jamais enregistrées ?*

**Précédents cités, vérifiés.** Replay (billet de Brian Hackett, 16 novembre 2021) remplace les fonctions des
bibliothèques système Windows par des shims qui « record the inputs and outputs to those functions when they
are called », et rejoue **sur Linux** toute capture, quel que soit l'OS d'origine ; la conversion d'ABI « adds a
fair amount of complexity ». Mais c'est le rejeu *de la même exécution* (débogage de leur propre navigateur, en
bêta), pas un usage libre. apitrace trace OpenGL, Direct3D et DirectDraw et rejoue « on any machine and, for
OpenGL, on any operating system » — le rejeu Direct3D hors Windows n'est pas revendiqué. Les deux confirment la
distinction de l'utilisateur : **rejouer un enregistrement est facile, rendre l'application librement utilisable
ne l'est pas.** Aucun des deux ne répond à la question décisive.

**La réponse, mesurée (RESULTATS §8.10).** Le labo a dérivé un correctif d'une seule exécution de référence, puis
l'a jugé sur des actions tenues à l'écart (autres documents, Unicode, vide, 5000 lignes, trois familles de
scénario jamais apprises), avec un verdict en trois valeurs jamais présumé :

| Ce qui est transféré | Généralise ? | Mesure |
|---|---|---|
| une **règle** (absence déclarée A ; propriété stable S) | **oui, par construction** : rien n'est rejoué, la règle est dans le repli du programme ou dans une propriété stable | 8/8, 0 faux succès |
| une **valeur** enregistrée par le professeur (heure locale) | **non** : rejouée telle quelle, elle est plausible mais périmée | 0/5, 5 faux succès ; l'oracle faible, lui, est trompé (5/5) |
| une **fonction** synthétisée (fonderie) | **oui**, si elle est juste — et seuls les oracles sur plusieurs actions le disent | 5/5, 0 faux succès |

**Trois conclusions.**
1. **Oui pour A et S, non pour les valeurs, oui pour les fonctions.** Pour tout ce qui est « non implémenté → le
   programme se replie » ou « capacité présente », le correctif généralise par nature. Pour une sortie qui dépend
   de l'entrée, aucune valeur enregistrée ne généralise ; il faut la fonction (fonderie, §8.4), jugée sur
   plusieurs entrées.
2. **Le professeur ne transmet pas des réponses, il transmet des tests.** Le produit le plus utile de la VM n'est
   pas la valeur enregistrée mais les **couples entrée → effet**, qui deviennent des oracles côté Linux. Et un
   oracle doit être **aussi fort que la propriété généralisée** : un horodatage plausible a laissé passer cinq
   faux succès, un horodatage « frais » les a tous attrapés. Règle désormais implémentée (`speculate.fixture_stability`,
   fixtures 0.2) : une valeur enregistrée n'est admise comme règle que si la VM l'a vue **identique sous au moins
   deux entrées distinctes** ; sinon c'est une valeur, pas une règle, et la voie est la fonderie. C'est la forme
   exécutable de la remarque de l'utilisateur : « capturer plusieurs entrées et états différents pour distinguer
   les véritables règles de fonctionnement des simples valeurs enregistrées ».
3. **Ce qui reste hors de portée** est inchangé : interface interactive, état persistant entre actions,
   non-déterminisme (autre que le temps), pilotes, protections (classe C/D). Et la preuve est synthétique :
   aucune VM Windows n'a tourné, le professeur a été simulé par la valeur qu'il aurait enregistrée.

**Ce que PolyRE gagne.** Une boucle complète et honnête : VM (professeur) → fixtures multi-entrées → règle ou
fonction → oracle fort sur actions jamais vues → capsule avec section `[generalization]` (le linter exige
`generalizes` pour le statut `validated`). L'avancée « réellement intéressante » annoncée par l'utilisateur
existe donc pour le sous-ensemble A / S / fonction scalaire ; au-delà, elle reste à mesurer sur de vrais
logiciels, avec le protocole à 4 bras du rapport.

## 11. La frontière : anti-triche noyau et DRM (classe D)

Position officielle Steamworks : EAC et BattlEye fonctionnent sous Proton **si l'éditeur active** la prise
en charge Linux (opt-in par titre) ; les solutions **en espace noyau ne sont pas prises en charge**. Vanguard,
Ricochet, FACEIT : pas de chemin Linux. **Ce n'est pas un problème technique à contourner : c'est une
décision d'éditeur**, et le labo refuse explicitement la classe D.
[Steamworks](https://partner.steamgames.com/doc/steamhardware/proton)

## 12. Le danger documenté : « supprimer le crash » n'est pas réparer

Live-kBench (arXiv 2602.02690, fév. 2026, révisé juin 2026 ; Huang, Mathai, Yu, Nogikh, Maniatis, Ivančić,
Wu, Kaffes, Yang, Ray) mesure des agents sur 534 bogues du noyau Linux : ils « resolve **74 %** of crashes on
the first attempt (**plausible patches**) ; however only **~20 %** of generated patches closely match developer
fixes ». L'écart entre « le crash disparaît » (plausible) et « c'est la bonne correction » est l'exact
analogue du **faux succès** : un correctif qui fait passer le symptôme sans rétablir le comportement. *(Une
formulation « supprimer le crash silencieusement », reprise d'un résumé de recherche, ne figure pas dans le
résumé de l'article ; je ne la cite donc pas comme verbatim.)* Toute industrialisation d'agents correcteurs
exige des **oracles d'effet**, pas des codes de retour — ce que le labo impose (sa fonderie a rejeté une
implémentation « succès sans sortie » qu'une vérification naïve aurait acceptée). [arXiv 2602.02690](https://arxiv.org/abs/2602.02690)

---

## 13. Verdict et stratégie (après les trois éclaireurs)

1. **Pas de graal technique — confirmé sur les trois voies « profondes ».** Recompilation statique (§9) :
   artisanale par titre, aucun projet avec Wine, l'écart sémantique reste celui de Wine. Personnalité NT sous
   Linux (§10) : tentée (Longene) et morte ; sa version viable est **déjà dans Wine** (SUD 11.5, ntsync 11.0) ;
   le reste (IOCP/APC/inter-processus/pilotes) exige serveur, noyau ou VM, et ReactOS n'est pas une
   bibliothèque. Trace dorée (§8) : pas un oracle d'exécution, mais un **générateur de fixtures** pour le
   sous-ensemble déterministe. Les voies « noyau », « micro-VM Windows » et « code NT ouvert » sont fermées par
   des décisions externes (Linux, Microsoft, Hyperlight). Apple l'a **confirmé** en bâtissant GPTK sur
   CrossOver/Wine.
2. **La rupture réaliste est organisationnelle et outillée.** Des agents réparent déjà de vraies applications
   (Alderson — un précédent documenté, pas encore une tendance), mais **Wine refuse ce code**. Le vide à occuper
   = **la couche de correctifs assistés, sûre, vérifiée par l'effet, reproductible et partagée par empreinte**,
   hors Wine. Aucun acteur identifié ne l'occupe (umu = par ID de jeu, Wine = oracle par API, Alderson =
   artisanal).
3. **Ce que PolyRE peut être : l'usine Alderson.** Entrée : un exe, **routé par runtime** (§10 bis — le .NET/WPF
   a sa propre voie). Pour le Win32 natif : analyse → indice statique → recherche de réponse (amorcée, pour le
   déterministe, par des **fixtures distillées** sur le Windows de l'utilisateur) → fonderie (toute
   implémentation jugée par l'oracle) → capsule signée, refusant sécurité et noyau → communs par empreinte. Le
   labo en est le prototype fonctionnel.
4. **Ce qui n'est pas prouvé.** L'efficacité à l'échelle sur des applications tierces inconnues : notre preuve
   est synthétique, celle d'Alderson est un cas unique faiblement vérifié. C'est l'objet du protocole à 4 bras
   du rapport, inchangé. Et le plafond demeure : **la classe D (anti-triche noyau, DRM) est une décision
   d'éditeur**, pas un problème à résoudre.
5. **La question décisive est tranchée pour le périmètre mesuré** (§10 sexies) : un correctif dérivé d'une seule
   référence généralise à des actions jamais enregistrées quand il transfère une **règle** (A, S : 8/8) ou une
   **fonction** (fonderie : 5/5), jamais quand il rejoue une **valeur** (0/5, cinq faux succès, invisibles pour un
   oracle faible). Le professeur doit fournir des tests multi-entrées, pas des réponses.

## 14. Sources

Voir les liens en ligne dans chaque section. Sources primaires lues intégralement : Alderson (2026-03-17),
mixed-news sur la règle Wine (oct.), documentation noyau SUD, Steamworks Proton. Secondaires : Phoronix,
GamingOnLinux, BleepingComputer/The Register (WSL), devclass/Phoronix (Hyperlight), umu-launcher README,
wiki de conformité Wine, arXiv 2602.02690, Replay (billet du 2021-11-16), apitrace.github.io.
