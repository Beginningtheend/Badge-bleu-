# Script d'extraction généré par polyre-bdf-lab (capture_import.to_extract_script).
# À exécuter DANS la VM Windows de l'utilisateur (PowerShell, droits lecture suffisants).
# Il copie ce que l'application a chargé — HORS plancher — dans un dossier local.
# Les fichiers copiés sont ceux de votre licence Windows : ils ne doivent PAS être redistribués.
$out = Join-Path (Get-Location) 'extrait-capsule'
New-Item -ItemType Directory -Force -Path (Join-Path $out 'dlls') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out 'app') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out 'fonts') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out 'registry') | Out-Null

# --- DLL natives hors plancher (priorisées par le statut Wine) ---
Copy-Item -LiteralPath 'C:\windows\system32\coml2.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (12 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\cryptbase.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (3 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\dnsapi.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (94 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\iphlpapi.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (61 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\mpr.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (14 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\nsi.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (15 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\ole32.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (32 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\setupapi.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (257 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\shell32.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (69 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\shlwapi.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (124 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\wininet.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (42 stubs)
Copy-Item -LiteralPath 'C:\windows\system32\userenv.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (0 stub)
Copy-Item -LiteralPath 'C:\windows\system32\VERSION.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (0 stub)
Copy-Item -LiteralPath 'C:\windows\system32\wevtsvc.dll' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # fournie par Wine (0 stub)

# --- plancher : volontairement NON copié (Wine le fournit) ---
# [plancher] advapi32
# [plancher] combase
# [plancher] gdi32
# [plancher] imm32
# [plancher] kernel32
# [plancher] kernelbase
# [plancher] msvcrt
# [plancher] ntdll
# [plancher] rpcrt4
# [plancher] sechost
# [plancher] shcore
# [plancher] ucrtbase
# [plancher] user32
# [plancher] win32u
# [plancher] ws2_32

# --- fichiers de l'application ---
Copy-Item -LiteralPath 'C:\bdf\bdfedit.exe' -Destination (Join-Path $out 'app') -ErrorAction SilentlyContinue

# --- polices ---

# --- registre : export des clés lues (format .reg, importable dans le préfixe Wine) ---

# --- manifeste d'empreintes (seul élément destiné à circuler) ---
Get-ChildItem -Recurse -File $out | Get-FileHash -Algorithm SHA256 | Select-Object Hash, Path | Export-Csv (Join-Path $out 'MANIFEST-sha256.csv') -NoTypeInformation
Write-Host "Extraction terminée dans $out — copiez le dossier sur la machine Linux (il reste privé)."
