# Carnet d'idéation — pistes de rupture Windows → Linux

> **Statut : HYPOTHÈSES, non démontrées.** Ce carnet est un travail d'invention dirigé, pas un résultat.
> Le rapport PolyRE a déjà conclu qu'il n'existe pas de « faille » universelle connue et que la
> compatibilité se *mesure*. Rien ici ne contredit cela. Chaque idée porte un verdict de nouveauté
> (vérifié par recherche web, sources en bas) et une note de testabilité au labo. Une seule de ces
> idées a été **rendue réelle** aujourd'hui (la n°1), et uniquement sur un cas synthétique.
> État de l'art 2026 vérifié et verdict stratégique : voir `RECHERCHE-graal-2026.md`.

Objet : « déposer l'exe et ça marche », sans Windows, sans IA à l'exécution. Les idées sont rangées par
« lentille » (angle d'attaque imposé). Pour chacune : **mécanisme concret**, **nouveauté**, **test labo**.

---

## A. La seule déjà prouvée aujourd'hui (synthétique)

### 1. Découverte de la réponse par oracle (« OracleForge au niveau réponse ») — *réalisée*
**Mécanisme.** Pour une fonction que Wine n'implémente pas, ne pas *deviner* la valeur à renvoyer :
**essayer toutes les réponses sûres** autorisées par la table de sûreté (A = absence déclarée ;
S = succès fabriqué, là où c'est permis), **rejouer le scénario** pour chacune dans un préfixe propre,
et **laisser l'oracle d'effet choisir** celle qui produit le bon résultat, sans faux succès.
**Nouveauté : partielle→réelle.** Le plus proche est *recovery shepherding / RCV* (Long, Sidiroglou-Douskos,
Rinard, PLDI 2014) : valeurs fabriquées pour des crashs (div par zéro, déréférencement nul) sur binaires
nus, avec suivi de propagation. Mais RCV ne fait pas de *sélection vérifiée par oracle d'effet* parmi des
candidats, n'est pas *typé par la table de sûreté d'une API OS*, et n'est pas indexé par identité de binaire
en capsule réutilisable. La combinaison est, à ma connaissance, inédite dans un contexte de compatibilité.
**Test labo : FAIT.** `bdflab/speculate.py` + `tools/demo_speculate.py`. Sur `shcore.IsAppCompatModeEnabled`
(vrai stub Wine 11.0), le labo découvre seul que la réponse A (FALSE) échoue (le programme renonce,
aucun enregistrement) et que S (TRUE) réussit (fichier enregistré, vérifié), puis retient S — parce que
la table de sûreté l'autorise pour une requête d'état sans tampon. Résultat : `results/speculate-demo.json`.

---

## B. Surface d'observation (optimiste)

### 2. Grille ABI par force brute, choisie par l'oracle — *réalisée (version bornée)*
**Mécanisme.** Généraliser la n°1 : pour un stub de signature inconnue, essayer une petite **grille**
(valeur de retour × dernier code d'erreur × « remplir/ne pas remplir le tampon ») et garder la case qui
passe l'oracle d'effet. « Débile » assumé : on ne comprend pas la fonction, on la *mesure*.
**Nouveauté : partielle** (extension de RCV + de la n°1 à un espace de réponses). **Test labo : FAIT**
(version bornée) : quand le type de retour est INCONNU — le cas de la plupart des `@ stub` sans prototype
public — `speculate.py` essaie les deux conventions (BOOL : 0+erreur / TRUE ; HRESULT : E_NOTIMPL / S_OK)
et laisse l'oracle trancher, car « 0 » serait un *succès* pour un HRESULT. Toujours borné par la sûreté.

### 3. Pré-réponse par « ce que le programme teste ensuite » — *réalisée*
**Mécanisme.** Analyser statiquement les **branches** qui suivent l'appel (le programme compare le retour à
quoi ?) pour proposer en priorité la réponse qui garde le programme sur son chemin nominal, puis vérifier.
**Nouveauté : novel** (personne ne relie l'analyse de branches post-appel au choix de réponse optimiste
dans un compat layer). **Test labo : FAIT** (`bdflab/branch_hint.py`, Capstone) : sur `IsAppCompatModeEnabled`
l'indice prédit « non-nul → S » et l'oracle le confirme ; voir `RESULTATS.md` §8.4.

## C. Inversion : Linux *se fait passer* pour Windows

### 4. Personnalité par binaire pilotée par capsule (au-dessus de SUD)
**Mécanisme.** *Syscall User Dispatch* permet déjà de router les syscalls d'une région du processus vers un
émulateur en espace utilisateur ; **Wine 11.5 (mars 2026) l'utilise déjà**. Twist : piloter la personnalité
**par capsule, par binaire** (chaque exe obtient le profil NT minimal que sa capsule décrit), plutôt qu'un
profil générique. **Nouveauté : le mécanisme de base est désormais courant** (noyau ≥ 5.11, Wine 11.5) ;
seule la *personnalité par capsule* resterait à inventer. **Test labo : partiel** (mesurer ce que la capsule
doit contenir ; l'intégration SUD est lourde pour la v0.1).

## D. Capture-rejeu

### 5. « Enregistre une fois sur ton Windows, rejoue pour toujours »
**Mécanisme.** Sur SON PROPRE Windows licencié, l'utilisateur enregistre une fois les **traces d'effet
dorées** (golden traces) d'un scénario ; on rejoue de façon déterministe sous Linux, sans Windows, en
servant ces effets. **Nouveauté : novel comme produit.** `rr` et *Transplay* font du record-replay mais pour
des programmes **Linux** ; aucun outil grand public ne rejoue un binaire **Windows** sur Linux sans Windows.
**Reformulée après enquête** (`RECHERCHE-graal-2026.md` §8) : rejouer une trace TTD sous Linux est **infaisable**
(format fermé, licence Windows-only, non-déterminisme) ; la version réaliste est **distiller sur Windows** les
résultats des API déterministes en fixtures ouvertes qui **amorcent la recherche de réponse** (n°1).
**Test labo : partiel** — l'amorçage par fixtures est implémentable ; la distillation exige un Windows.

## E. Communs

### 6. Communs de comportements adressé par CONTENU (pas par ID de jeu)
**Mécanisme.** Une capsule par **empreinte de binaire** (sha256 + imphash + version) ; « glisser l'exe »
= chercher sa capsule par hash. Chaque bizarrerie est résolue **une fois** par quelqu'un, signée, puis
partagée mondialement ; les versions voisines retombent sur l'imphash en mode dégradé.
**Nouveauté : novel sur le point clé.** `protonfixes` indexe par **ID Steam du jeu**, pas par hash du binaire,
et n'est pas *typé sûreté* ni signé. L'adressage par contenu + la typologie A/B/C/D + la signature sont le
delta original. **Test labo : oui** — c'est déjà le format de capsule du labo ; reste l'index partagé.

## F. Lifting ahead-of-time

### 7. Lifting guidé par le comportement (seulement le chemin observé)
**Mécanisme.** Au lieu de lifter tout le PE (fragile), ne recompiler en natif que les **chemins chauds
réellement observés** par les traces, et **BDF-stubber** le reste. **Nouveauté : novel comme combinaison.**
McSema/rev.ng liftent statiquement (le PE x64 reste fragile) ; personne ne *restreint* le lifting aux
chemins mesurés en bouchant le reste par réponses optimistes. **Test labo : partiel** (le lifting x64 PE est
réputé cassant ; mesurable sur un binaire jouet).

## G. Délibérément bête mais malin

### 8. Le téléphone comme coprocesseur de compatibilité
**Mécanisme.** Pour les 1 % d'appels vraiment durs, **déporter** l'exécution de la DLL concernée vers un
appareil qui a Windows/Android (le téléphone de l'utilisateur, un vieux PC), via USB/LAN, et streamer l'état.
**Nouveauté : novel dans ce cadre** (existe en jeux cloud, pas pour quelques DLL d'une app de bureau).
**Test labo : non en v0.1** (transfert d'état complexe) ; mais un pico-service local qui ne sert qu'une
fonction est esquissable.

### 9. Canaris partout + annulation
**Mécanisme.** Écrire des **fichiers/valeurs canaris** avant toute réponse spéculative ; si un canari est
lu/propagé de façon incohérente, **annuler** la spéculation et rejouer en absence déclarée. « Bête » : on
salit volontairement pour détecter la corruption. **Nouveauté : partielle** (teinte/confinement connus ;
l'usage systématique de canaris pour arbitrer A vs S est original). **Test labo : oui**, extension des oracles.

## H. Déterminisme

### 10. Double-monde spéculatif, on garde le survivant
**Mécanisme.** Au point d'un stub, **dupliquer** l'état (CRIU/fork), exécuter les DEUX réponses en parallèle
dans des clones jetables, **garder** le clone dont l'oracle passe, tuer l'autre. La n°1 en est la version
sage et séquentielle. **Nouveauté : partielle** (fork spéculatif connu ; appliqué au choix de réponse OS +
oracle d'effet, original). **Test labo : oui** (séquentiel déjà fait ; le vrai fork d'état est un plus).

## I. IA au moment de la construction (jamais à l'exécution)

### 11. Fonderie de shims hors ligne, prouvés par oracle avant signature — *réalisée*
**Mécanisme.** Un modèle, **hors ligne**, propose une implémentation de shim à partir des en-têtes/doc ;
elle n'est acceptée que si les **oracles d'effet** la valident sur données jetables ; une fois signée, elle
tourne **sans aucune IA** à l'exécution (contrainte PolyRE respectée). **Nouveauté : partielle.** La synthèse
d'API par LLM validée par tests existe (surtout en Java) ; l'obstacle noté par la recherche est justement
« l'oracle exige de connaître le comportement attendu ». Le labo y répond par des **oracles d'effet sur
données jetables** et la **séparation stricte build-time / runtime**. **Test labo : FAIT** (`bdflab/foundry.py`) : une proposition correcte est acceptée, une proposition « succès
sans sortie » est rejetée comme faux succès par l'oracle d'horodatage ; voir `RESULTATS.md` §8.5.

## J. Compatibilité « par le but »

### 12. Satisfaire le RÉSULTAT, pas l'API
**Mécanisme.** Pour les cas durs, ne pas exécuter le code : **détecter l'intention** de l'utilisateur
(ouvrir/éditer/enregistrer un `.docx`, exporter un PDF) et la satisfaire avec un **gestionnaire natif**
Linux, en ne gardant du binaire Windows que l'UI. « Débile » : on contourne le programme pour servir son but.
**Nouveauté : novel dans ce cadrage** (proche des associations de fichiers, mais poussé au niveau
« remplacer l'action, pas l'API »). **Test labo : partiel** (démontrable sur un format simple).

---

## Court-liste « eurêka » (nouveauté × testabilité)

1. **n°1 Découverte par oracle** — *déjà réelle*, extensible (n°2 grille ABI).
2. **n°6 Communs adressé par contenu** — nouveauté nette vs protonfixes ; format déjà en place.
3. **n°5 Enregistre-une-fois-rejoue** — reformulée en « distiller des fixtures » (le rejeu intégral est infaisable).
4. **n°3 Pré-réponse par analyse de branches** — *déjà réelle*, prédiction confirmée par l'oracle.
5. **n°11 Fonderie de shims hors ligne** — *déjà réelle* ; la proposition fausse est bien rejetée.

## Ce que la réalité impose (honnêteté)

- **Pas de faille universelle** (verdict du rapport) : ces idées réduisent le travail *par application*,
  elles ne « détruisent » pas l'incompatibilité.
- **SUD est déjà courant** (noyau ≥ 5.11, Wine 11.5) : l'inversion « Linux se fait passer pour Windows » au
  niveau syscall n'est plus neuve en soi.
- **Le lifting x64 PE reste fragile** (McSema).
- **La stratégie S fabrique un effet** : jamais sur tampon de sortie, mutation persistante, sécurité ; jamais
  en production hors capsule validée. La n°1 respecte déjà cette table.

## Sources (antériorité vérifiée le 2026-11-02)

- Failure-oblivious computing (contexte) — [arXiv 1806.09026](https://arxiv.org/pdf/1806.09026) ; stubs Wine — [WineHQ Developer Hints](https://wiki.winehq.org/Developer_Hints).
- Recovery shepherding / RCV — [MIT DSpace 1721.1/125189](https://dspace.mit.edu/handle/1721.1/125189), [PLDI 2014](https://bibtex.github.io/PLDI-2014-LongSR.html).
- Record-replay — [rr](https://rr-project.org/), [Transplay (Columbia)](https://academiccommons.columbia.edu/doi/10.7916/D8JH3T24/download), [Callahan et al., USENIX ATC'17](https://www.usenix.org/system/files/conference/atc17/atc17-o_callahan.pdf).
- protonfixes / ProtonDB — [protonfixes (PyPI)](https://www.pypi.org/project/protonfixes/1.0.2/), [Proton (Wikipedia)](https://en.wikipedia.org/wiki/Proton_(software)).
- Lifting PE — [McSema](https://blog.trailofbits.com/2017/03/14/mcsema-im-liftin-it/).
- Syscall User Dispatch — [kernel.org doc](https://docs.kernel.org/admin-guide/syscall-user-dispatch.html), [Phoronix](https://www.phoronix.com/news/Linux-Syscall-User-Dispatch), [Wine 11.5 (GamingOnLinux)](https://www.gamingonlinux.com/2026/03/wine-11-5-released-with-support-for-syscall-user-dispatch-on-linux/).
- Synthèse d'API par LLM / oracles depuis la doc — [API synthesis review](https://themoonlight.io/review/an-approach-for-api-synthesis-using-large-language-models), [arXiv 2411.01789](https://arxiv.org/html/2411.01789v1), [arXiv 2502.15246](https://arxiv.org/html/2502.15246v1).
