# Capturer une application dans votre VM Windows (four d'extraction)

Objectif : enregistrer **tout ce que l'application charge** pendant les scénarios, pour que le labo en fasse une
recette, puis un dossier réutilisable **sans VM** (Wine + dossier).

1. Dans la VM Windows (votre licence), installez l'application normalement.
2. Lancez **Process Monitor** (Sysinternals). Filtre : `Process Name` **is** `<votre-appli>.exe` → Include.
   Gardez les opérations : *Load Image*, *RegOpenKey*, *RegQueryValue*, *CreateFile*, *QueryOpen*.
3. Jouez **chaque scénario** que vous voulez couvrir (démarrer, ouvrir, modifier, enregistrer, rouvrir,
   exporter…), **chacun avec au moins deux entrées ou états différents** (deux documents, deux textes) : c'est ce
   qui permet ensuite de distinguer une règle d'une simple valeur enregistrée (`RESULTATS.md` §8.10). Une capture
   ne voit que ce qui a été exercé.
4. `File → Save…` → format **CSV**, « Events displayed using current filter » → un fichier par scénario.
5. Sur Linux, déposez les CSV dans `_captures/<app>/` (dossier **ignoré par git** : une capture contient des chemins
   et des noms d'utilisateur Windows), puis :
   ```bash
   python3 tools/capture_to_recipe.py --procmon _captures/<app>/s1.csv --procmon _captures/<app>/s2.csv \
       --app-root "C:/Program Files/<App>" --scenario s1 --scenario s2 --out _captures/<app>
   ```
   produit `recipe.json` (la **recette**) et `extract.ps1`. Avant de versionner une recette ou un script, remplacez
   `C:\Users\<nom>` par `%USERPROFILE%` et retirez tout nom de machine ; sinon laissez-les dans `_captures/`.
6. De retour dans la VM : exécutez `extract.ps1` → dossier `extrait-capsule/` (DLL hors plancher, fichiers de
   l'appli, polices, `.reg`, manifeste d'empreintes). Copiez-le sur Linux dans `_extrait/<app>/` (ignoré par git).
   **Il reste privé** (votre licence) : jamais versionné, jamais redistribué.
7. Le labo applique la recette dans un préfixe Wine propre et **vérifie par oracle** avant d'émettre la capsule.
   État : l'étape d'application (`apply_recipe`) **n'existe pas encore** dans le code (RESULTATS §8.9, « non fait
   ici ») ; elle est la première tâche de la phase locale (`docs/handoff/PROMPT-NOUVELLE-CONVERSATION-LOCALE.md`, M0).

Ce qui ne s'extrait pas : le plancher (`ntdll`, `win32u`, `kernelbase`, `kernel32`, `user32`, `gdi32`, noyau),
les services Windows vivants, les pilotes. Wine fournit le socle ; la recette fournit le reste.

Note : un journal Wine (`+loaddll`, `+relay`) peut aussi alimenter la recette côté Linux, mais pour le **registre**
il n'est que partiel (seules les clés ouvertes depuis une ruche prédéfinie sont lisibles) — Process Monitor fait foi.
