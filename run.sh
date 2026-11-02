#!/usr/bin/env bash
# Script de lancement de polyre-bdf-lab (prototype v0.1).
#
# Étapes : vérifie les dépendances, (re)construit la base de connaissances Wine si besoin, compile le
# programme de test synthétique et les correctifs, puis lance l'expérience phase 0 (configs A/B/C).
#
# Variables : BDFLAB_WINE_BIN (défaut /opt/wine-stable/bin), BDFLAB_WORK (espace de travail jetable).
set -euo pipefail
cd "$(dirname "$0")"
export BDFLAB_WINE_BIN="${BDFLAB_WINE_BIN:-/opt/wine-stable/bin}"
WORK="${BDFLAB_WORK:-$PWD/_scratch/bdflab-work}"
WINE_SRC="${WINE_SRC:-}"
DATA="data/wine-11.0"

echo "== polyre-bdf-lab : lancement =="
command -v "$BDFLAB_WINE_BIN/wine" >/dev/null || { echo "Wine introuvable dans $BDFLAB_WINE_BIN (voir requirements-system.txt)"; exit 2; }
"$BDFLAB_WINE_BIN/wine" --version
command -v x86_64-w64-mingw32-gcc >/dev/null || { echo "mingw-w64 introuvable (voir requirements-system.txt)"; exit 2; }
python3 -c "import pefile, tomli_w, psutil" 2>/dev/null || { echo "Dépendances Python manquantes : pip install -r requirements.txt"; exit 2; }

# 1. base de connaissances Wine (si absente et si l'arbre source est fourni)
if [ ! -f "$DATA/meta.json" ]; then
  [ -n "$WINE_SRC" ] || { echo "Base $DATA absente : fournissez WINE_SRC=<arbre source Wine 11.0>"; exit 2; }
  echo "== construction de la base de connaissances Wine =="
  python3 -m bdflab.knowledge.build_wine_db --source "$WINE_SRC" --install "$(dirname "$BDFLAB_WINE_BIN")" --out "$DATA"
fi

# 2. programme de test synthétique + DLL optionnelle, et correctif manuel de référence
echo "== compilation du programme de test et des correctifs =="
( cd testapps/bdfedit && ./build.sh )
( cd manual-fix && ./build_manual.sh )
[ -f catalogue/bdfpdf.dll ] || cp testapps/bdfedit/bin/bdfpdf.dll catalogue/bdfpdf.dll

# 3. expérience phase 0 (A/B/C, 2 exécutions, préfixes propres)
echo "== expérience phase 0 =="
python3 -m bdflab.run_experiment \
  --exe testapps/bdfedit/bin/bdfedit.exe --data "$DATA" --work "$WORK" \
  --out results --catalogue catalogue --synthetic --runs 2 --configs A,B,C

echo "== terminé. Voir results/latest/results.json et RESULTATS.md =="
