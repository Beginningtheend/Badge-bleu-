#!/usr/bin/env bash
# Construit le programme de test synthétique bdfedit.exe et la DLL optionnelle bdfpdf.dll (x86-64).
# Dépendances : gcc-mingw-w64-x86-64 (x86_64-w64-mingw32-gcc, x86_64-w64-mingw32-windres).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin
CC=x86_64-w64-mingw32-gcc
WINDRES=x86_64-w64-mingw32-windres
CFLAGS="-O1 -Wall -Wextra -municode -D_WIN32_WINNT=0x0601"
# --no-insert-timestamp : en-tête PE reproductible (sha256 stable entre deux constructions identiques)
LDFLAGS="-Wl,--no-insert-timestamp -static-libgcc"
$WINDRES bdfedit.rc -O coff -o bin/bdfedit.res
$CC $CFLAGS -o bin/bdfedit.exe bdfedit.c bin/bdfedit.res $LDFLAGS -lversion
$CC -O1 -Wall -shared -o bin/bdfpdf.dll bdfpdf/bdfpdf.c -Wl,--no-insert-timestamp -static-libgcc
rm -f bin/bdfedit.res
( cd bin && sha256sum bdfedit.exe bdfpdf.dll > SHA256SUMS )
cat bin/SHA256SUMS
