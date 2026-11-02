#!/usr/bin/env bash
# Construit le correctif manuel de référence (config C). Nom de DLL de 12 caractères (= "KERNEL32.dll").
set -euo pipefail
cd "$(dirname "$0")"
x86_64-w64-mingw32-gcc -O1 -shared -o bzmank32.dll bzmank32.c bzmank32.def \
  -Wl,--no-insert-timestamp -static-libgcc -Wl,--enable-stdcall-fixup
x86_64-w64-mingw32-objdump -p bzmank32.dll | grep -A3 "Export" | head -6
echo "built bzmank32.dll ($(stat -c%s bzmank32.dll) octets)"
