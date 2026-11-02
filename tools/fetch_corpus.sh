#!/usr/bin/env bash
# Télécharge quelques vrais exécutables Windows open source / redistribuables pour le balayage statique.
set -uo pipefail
C=$(dirname "$0")/../_corpus
mkdir -p "$C"/_dl
cd "$C"/_dl
fetch(){ echo "[dl] $2"; curl -sSL --max-time 120 -o "$1" "$2" 2>&1 | tail -1 || echo "  (échec $2)"; }
# SumatraPDF (open source, GPLv3) — archive zip 64-bit
fetch sumatra.zip "https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2-64.zip"
# Sysinternals (redistribuables Microsoft) — suite zip
fetch sysinternals.zip "https://download.sysinternals.com/files/SysinternalsSuite.zip"
# Python embeddable (PSF) — contient python.exe et DLLs
fetch pyembed.zip "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
# 7-Zip console (LGPL) via archive
fetch 7zr.exe "https://www.7-zip.org/a/7zr.exe"
ls -la
