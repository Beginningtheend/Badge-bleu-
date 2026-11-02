# Prompt à coller dans la nouvelle session Claude Code

> Copie tout ce qui suit la ligne, après avoir déposé les fichiers du dossier `polyre-bdf-lab-handoff/`
> dans le répertoire de travail (ou en les attachant). Adapte le chemin du dépôt NoxPolyRE.

---

MISSION CLAUDE CODE — POLYRE BDF-LAB V0.1 (passation depuis la session de recherche)

Rôle : ingénieur senior en compatibilité Windows/Linux, Wine, rétro-ingénierie PE et automatisation des tests.

Objectif : transformer la piste n°6 « Fidélité dirigée par le binaire » du rapport PolyRE en un prototype
réel, exécutable et vérifiable. Je ne veux plus un rapport de faisabilité : du code qui fonctionne, des
expériences exécutées, des résultats vérifiables.

0. Lis d'abord, dans cet ordre, sans rien écrire :
   - `HANDOFF.md` (contexte, décisions, table de sûreté, format de capsule, écarts à corriger).
   - `mission-bdf-lab-v0.1.txt` (la mission d'origine ; `HANDOFF.md` §5 la précise sur 7 points).
   - Le rapport scientifique, doc Claude : https://claude.ai/artifact/2AmRmfLTw33LEWtyanaffZ
     (lis-le avec l'outil de lecture de docs/artifacts, pas par web-fetch). Sections à lire :
     « Piste expérimentale n°6 » en entier, « Architecture principale » (classes A/B/C/D),
     « Expériences à confier à Astra » (expérience 7).
   - Le moteur PolyRE actuel, dépôt NoxPolyRE : <CHEMIN_OU_URL_DU_DEPOT>, en lecture seule, pour
     comprendre ses profils, ses correctifs et son architecture. Interdiction absolue de le modifier.

1. Crée un projet indépendant `polyre-bdf-lab/` (Python ; C/C++ seulement pour la DLL de shim et le
   programme de test). Il ne sera intégré au moteur principal que si ses résultats sont convaincants.

2. Laboratoire — capacités à livrer :
   1. Analyser les imports d'un exécutable PE (utilise `pefile` ; imphash via `pe.get_imphash()`).
   2. Identifier les fonctions Windows potentiellement problématiques (croisement avec les stubs des
      fichiers `.spec` de Wine et les FIXME ; EXCEPTION_WINE_STUB = 0x80000100).
   3. Collecter les traces Wine (`WINEDEBUG=+relay,+tid,+timestamp,+seh`, préfixe jetable, `RelayExclude`
      pour alléger).
   4. Repérer les appels associés aux échecs et aux comportements non implémentés.
   5. Classer chaque problème en A (déclaratif), B (comportement simple), C (sémantique profonde),
      D (hors périmètre : DRM, activation, anti-triche, sécurité) — définitions dans `HANDOFF.md` §2.
   6. Générer une proposition de correctif déclaratif (A) ou de shim (B) quand c'est possible, avec la
      stratégie A (absence déclarée) par défaut ; la stratégie S (succès fabriqué) uniquement dans les cases
      autorisées de la table de sûreté (`HANDOFF.md` §3), teintée et journalisée.
   7. Produire un rapport avec preuves, incertitudes et limites de chaque proposition.
   Utilise des outils existants (pefile, Wine, éventuellement Ghidra headless) plutôt qu'un analyseur PE maison.

3. Première expérience réelle — phase 0 du protocole :
   - Choisis un exécutable Windows de test au comportement connu dont une API est insuffisamment traitée par
     Wine. Si aucun cas réel n'est disponible, écris un programme de test minimal (mingw-w64) qui appelle une
     fonction stub de Wine et dégrade proprement ; marque-le `synthetic = true` partout et sépare ses résultats.
   - Exécute sous Wine 11.0 standard (note la version exacte ; si la distribution ne fournit que 10.x ou
     une autre 11.x, dis-le et n'en mélange pas deux) ; capture traces et état de référence ; identifie le
     comportement problématique ; génère la proposition ; applique-la dans un préfixe Wine isolé seulement ;
     relance exactement le même scénario ; compare avant/après.
   - Voie d'interception recommandée pour v0.1 : DLL de remplacement exportant la fonction, chargée par
     `WINEDLLOVERRIDES` ; documente le choix.
   - Aucune falsification de licence, identité, sécurité, signature ou activation.

4. Générateur de capsules — format TOML de `HANDOFF.md` §3, avec en plus : `status = "experimental" |
   "validated" | "rejected"`, `synthetic = true|false`, version Wine exacte, traces justificatives, résultats
   de scénarios. Un linter refuse toute capsule violant la table de sûreté. Une capsule expérimentale ne
   s'applique jamais silencieusement à un logiciel de production.

5. Vérification obligatoire des effets (données jetables uniquement) : démarrage stable 60 s ;
   modification d'un document de test ; enregistrement effectif ; fermeture et réouverture ; vérification du
   contenu par un outil indépendant (hash, lecteur de référence). Un succès annoncé sans fichier présent et
   correct = échec classé « faux succès ».

6. Comparaison — trois configurations : A Wine standard ; B Wine + correctif généré ; C Wine + correctif
   manuel de référence si disponible. Mesure : scénarios réussis, faux succès, régressions, temps de génération,
   temps humain, CPU/RAM, reproductibilité. Chaque scénario au moins deux fois dans des préfixes propres.
   Aucun gain revendiqué sans mesure.

7. Ressources : PC partagé par plusieurs agents. Limite RAM et processus (1–2 Wine simultanés), délais
   maximaux (`timeout`, puis `wineserver -k` propre), aucun test sur disque avec erreurs SMART, stockage sain
   uniquement, aucune suppression de données existantes, aucun processus bloqué laissé tourner.

8. Livrables dans `polyre-bdf-lab/` : code source complet ; script de lancement ; dépendances documentées ;
   exécutables de test si redistribuables (sinon script de construction) ; capsules générées ; traces et
   journaux ; tests automatisés ; `RESULTATS.md` avec les résultats réellement obtenus, qui répond à :
   A. Une API problématique a-t-elle été identifiée ?
   B. Le prototype a-t-il généré un correctif ?
   C. Ce correctif a-t-il amélioré un scénario réel ?
   D. Les effets attendus ont-ils été vérifiés ?
   E. Le prototype réduit-il effectivement le travail manuel ?
   F. Que reste-t-il à développer pour automatiser davantage ?
   Et une section « Scénario 3 » : dire explicitement si l'expérience confirme, infirme ou ne permet pas de
   juger l'hypothèse « BDF résout automatiquement plusieurs catégories de problèmes sur des applications
   inconnues, avec effets vérifiés et sans corruption ». Ne la présume pas.

9. Critère de réussite : un programme Windows échoue sous Wine, le laboratoire identifie un comportement
   problématique, propose un correctif sûr, et le programme réussit le scénario après application, sans faux
   succès ni régression constatée. Un cas synthétique validé prouve le fonctionnement du prototype, pas son
   efficacité sur des logiciels commerciaux. Si l'expérience échoue, documente précisément pourquoi.

10. Exécution autonome : écris le code, compile, exécute, analyse, corrige les bugs du labo, relance.
    N'attends mon intervention que si un accès, une autorisation ou une ressource indispensable manque
    réellement (par exemple : Wine absent et non installable, dépôt NoxPolyRE introuvable).

Priorité absolue : un premier résultat expérimental vérifiable, pas une nouvelle théorie.
