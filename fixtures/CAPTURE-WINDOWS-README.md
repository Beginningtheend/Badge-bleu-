# Capturer une application dans votre VM Windows (four d'extraction)

Objectif : enregistrer **tout ce que l'application charge** pendant les scénarios, pour que le labo en fasse une
recette, puis un dossier réutilisable **sans VM** (Wine + dossier).

1. Dans la VM Windows (votre licence), installez l'application normalement.
2. Lancez **Process Monitor** (Sysinternals). Filtre : `Process Name` **is** `<votre-appli>.exe` → Include.
   Gardez les opérations : *Load Image*, *RegOpenKey*, *RegQueryValue*, *CreateFile*, *QueryOpen*.
3. Jouez **chaque scénario** que vous voulez couvrir (démarrer, ouvrir, modifier, enregistrer, rouvrir,
   exporter…). Une capture ne voit que ce qui a été exercé.
4. `File → Save…` → format **CSV**, « Events displayed using current filter » → `capture.csv`.
5. Sur Linux : `python3 -c "from bdflab.capture_import import *; ..."` (ou la commande du labo) produit la
   **recette** et le script `extract.ps1`.
6. De retour dans la VM : exécutez `extract.ps1` → dossier `extrait-capsule/` (DLL hors plancher, fichiers de
   l'appli, polices, `.reg`, manifeste d'empreintes). Copiez-le sur Linux. **Il reste privé** (votre licence).
7. Le labo applique la recette dans un préfixe Wine propre et **vérifie par oracle** avant d'émettre la capsule.

Ce qui ne s'extrait pas : le plancher (`ntdll`, `win32u`, `kernelbase`, `kernel32`, `user32`, `gdi32`, noyau),
les services Windows vivants, les pilotes. Wine fournit le socle ; la recette fournit le reste.

Note : un journal Wine (`+loaddll`, `+relay`) peut aussi alimenter la recette côté Linux, mais pour le **registre**
il n'est que partiel (seules les clés ouvertes depuis une ruche prédéfinie sont lisibles) — Process Monitor fait foi.
