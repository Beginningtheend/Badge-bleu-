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
fait à la main.

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

## 8. Trace « dorée » par application (WinDbg TTD) — *(éclaireur en cours, à compléter)*

Hypothèse : enregistrer une fois, sur le Windows licencié de l'utilisateur, les résultats exacts des API
(TTD / ETW / Detours), et s'en servir comme oracle ou comme réponses rejouées pour le sous-ensemble
déterministe. Prior art connu : record-replay Linux (rr, Transplay) ; rien de grand public pour un binaire
Windows rejoué sur Linux. Verdict détaillé à venir.

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

## 10. Personnalité NT sur Linux (WSL1 à l'envers, Longene, ReactOS) — *(éclaireur en cours, à compléter)*

Faits déjà acquis : `lxcore.sys` fermé (§1), glu noyau refusée par Linux (§4). Reste à évaluer : principes
transférables de WSL1/Drawbridge, pourquoi Longene est mort, et si des composants ReactOS sont réutilisables
en bibliothèque. Verdict détaillé à venir.

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

## 13. Verdict et stratégie

1. **Pas de graal technique.** Les voies « noyau », « micro-VM Windows » et « code NT ouvert » sont fermées
   en 2026 par des décisions externes (Linux, Microsoft, Hyperlight). La compatibilité reste Wine-style +
   traduction — **Apple l'a confirmé** en bâtissant GPTK sur CrossOver/Wine.
2. **La rupture réaliste est organisationnelle et outillée** : des agents réparent déjà de vraies
   applications (Alderson), mais Wine refuse ce code. Le vide à occuper = **la couche de correctifs
   assistés, sûre, vérifiée par l'effet, reproductible et partagée par empreinte**, hors Wine. Aucun acteur
   identifié ne l'occupe (umu = par jeu, Wine = par API, Alderson = artisanal).
3. **Ce que PolyRE peut être** : l'usine Alderson. Entrée : un exe. Sortie : une capsule signée, vérifiée
   par oracles, refusant sécurité/noyau, indexée par empreinte, partagée. Le labo en est le prototype
   (analyse → indice → recherche → fonderie → oracle → capsule → communs).
4. **Ce qui n'est pas prouvé** : l'efficacité à l'échelle sur des applications tierces inconnues (notre preuve
   est synthétique ; celle d'Alderson est un cas unique, faiblement vérifié). C'est l'objet du protocole à
   4 bras du rapport, inchangé.

## 14. Sources

Voir les liens en ligne dans chaque section. Sources primaires lues intégralement : Alderson (2026-03-17),
mixed-news sur la règle Wine (oct.), documentation noyau SUD, Steamworks Proton. Secondaires : Phoronix,
GamingOnLinux, BleepingComputer/The Register (WSL), devclass/Phoronix (Hyperlight), umu-launcher README,
wiki de conformité Wine, arXiv 2602.02690.
