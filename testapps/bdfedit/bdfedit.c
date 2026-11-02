/*
 * bdfedit — programme de test SYNTHÉTIQUE pour polyre-bdf-lab (synthetic = true).
 *
 * Éditeur de documents texte minimal, en mode console, piloté par la ligne de commande,
 * écrit uniquement avec l'API Win32. Il reproduit le motif d'un logiciel Windows 7+ qui :
 *   - affiche sa version via version.dll (import statique : GetFileVersionInfo*) ;
 *   - horodate ses enregistrements avec SystemTimeToTzSpecificLocalTimeEx (API publique
 *     Windows 7+, timezoneapi.h) en se repliant sur SystemTimeToTzSpecificLocalTime si l'appel
 *     échoue (comportement documenté : la fonction retourne FALSE et positionne GetLastError) ;
 *   - exporte en PDF via une DLL optionnelle (bdfpdf.dll) chargée dynamiquement, et dégrade
 *     proprement si elle est absente.
 *
 * Sous Wine 11.0, kernel32 n'exporte pas SystemTimeToTzSpecificLocalTimeEx (kernelbase ne l'a
 * qu'en « @ stub ») : l'appel lève EXCEPTION_WINE_STUB et le processus meurt avant d'écrire.
 * C'est l'incompatibilité que le laboratoire doit détecter, classer et corriger.
 *
 * Protocole de sortie (stdout, non tamponné) : lignes « BDFEDIT|EVENT|cle=valeur|... ».
 * Codes de retour : 0 succès ; 2 fonctionnalité indisponible (dégradation propre) ; 3 erreur E/S ;
 * 4 usage.
 *
 * Toutes les données manipulées sont jetables (fichiers de test créés par le harnais).
 */
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <timezoneapi.h>
#ifndef BDFEDIT_HAVE_TZ_EX_PROTO
/* Déclaré explicitement : certaines versions des en-têtes mingw-w64 ne l'exposent pas. */
WINBASEAPI BOOL WINAPI SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *, const SYSTEMTIME *, LPSYSTEMTIME);
#endif
#include <tlhelp32.h>
/* Fonction de capacité, importée statiquement (lib d'import générée) : shcore.IsAppCompatModeEnabled.
 * C'est un VRAI stub de Wine 11.0 ; l'appeler sous Wine standard lève EXCEPTION_WINE_STUB.
 * Le programme ne poursuit l'enregistrement QUE si la capacité est signalée disponible (retour TRUE). */
__declspec(dllimport) BOOL WINAPI IsAppCompatModeEnabled(void);
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define BDFEDIT_VERSION "0.1.0"

static void out(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
    fflush(stdout);
}

/* ------------------------------------------------------------------ E/S */

static char *read_file(const wchar_t *path, DWORD *size_out)
{
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        out("BDFEDIT|ERROR|op=open|path=%ls|err=%lu", path, GetLastError());
        return NULL;
    }
    LARGE_INTEGER sz;
    if (!GetFileSizeEx(h, &sz) || sz.QuadPart > 64 * 1024 * 1024) {
        out("BDFEDIT|ERROR|op=size|path=%ls|err=%lu", path, GetLastError());
        CloseHandle(h);
        return NULL;
    }
    char *buf = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)sz.QuadPart + 1);
    DWORD got = 0, total = 0;
    while (total < (DWORD)sz.QuadPart) {
        if (!ReadFile(h, buf + total, (DWORD)sz.QuadPart - total, &got, NULL) || got == 0) {
            out("BDFEDIT|ERROR|op=read|path=%ls|err=%lu", path, GetLastError());
            CloseHandle(h);
            HeapFree(GetProcessHeap(), 0, buf);
            return NULL;
        }
        total += got;
    }
    buf[total] = 0;
    CloseHandle(h);
    *size_out = total;
    return buf;
}

static int count_lines(const char *s)
{
    int n = 0;
    for (; *s; s++) if (*s == '\n') n++;
    return n;
}

/* Écriture atomique : fichier temporaire + MoveFileEx(REPLACE_EXISTING). */
static int write_file_atomic(const wchar_t *path, const char *data, DWORD size)
{
    wchar_t tmp[MAX_PATH + 8];
    _snwprintf(tmp, MAX_PATH + 8, L"%ls.tmp", path);
    HANDLE h = CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        out("BDFEDIT|ERROR|op=create-tmp|path=%ls|err=%lu", tmp, GetLastError());
        return 0;
    }
    DWORD written = 0;
    if (!WriteFile(h, data, size, &written, NULL) || written != size) {
        out("BDFEDIT|ERROR|op=write|path=%ls|err=%lu", tmp, GetLastError());
        CloseHandle(h);
        return 0;
    }
    FlushFileBuffers(h);
    CloseHandle(h);
    if (!MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        out("BDFEDIT|ERROR|op=replace|path=%ls|err=%lu", path, GetLastError());
        return 0;
    }
    return 1;
}

/* ------------------------------------------------------------ horodatage */

/*
 * Calcule l'heure locale d'enregistrement. Chemin nominal : fuseau dynamique
 * (GetDynamicTimeZoneInformation + SystemTimeToTzSpecificLocalTimeEx, Windows 7+).
 * Repli documenté : SystemTimeToTzSpecificLocalTime si la variante Ex échoue.
 */
static void local_timestamp(char *buf, size_t len, const char **method, DWORD *err)
{
    SYSTEMTIME utc, local;
    DYNAMIC_TIME_ZONE_INFORMATION dtzi;
    GetSystemTime(&utc);
    memset(&local, 0, sizeof(local));
    memset(&dtzi, 0, sizeof(dtzi));
    GetDynamicTimeZoneInformation(&dtzi);
    *err = 0;
    SetLastError(0);
    if (SystemTimeToTzSpecificLocalTimeEx(&dtzi, &utc, &local)) {
        *method = "ex";
    } else {
        *err = GetLastError();
        *method = "fallback";
        memset(&local, 0, sizeof(local));
        SystemTimeToTzSpecificLocalTime(NULL, &utc, &local);
    }
    _snprintf(buf, len, "%04u-%02u-%02u %02u:%02u:%02u", local.wYear, local.wMonth, local.wDay,
              local.wHour, local.wMinute, local.wSecond);
}

/* --------------------------------------------------------------- version */

typedef DWORD (WINAPI *pGetFileVersionInfoSizeW)(LPCWSTR, LPDWORD);

static void print_version(void)
{
    wchar_t self[MAX_PATH];
    DWORD handle = 0, size;
    GetModuleFileNameW(NULL, self, MAX_PATH);
    size = GetFileVersionInfoSizeW(self, &handle);
    if (size) {
        void *block = HeapAlloc(GetProcessHeap(), 0, size);
        if (GetFileVersionInfoW(self, handle, size, block)) {
            VS_FIXEDFILEINFO *ffi = NULL;
            UINT ffi_len = 0;
            if (VerQueryValueW(block, L"\\", (LPVOID *)&ffi, &ffi_len) && ffi) {
                out("BDFEDIT|VERSION|product=bdfedit|version=%u.%u.%u.%u|synthetic=true",
                    HIWORD(ffi->dwProductVersionMS), LOWORD(ffi->dwProductVersionMS),
                    HIWORD(ffi->dwProductVersionLS), LOWORD(ffi->dwProductVersionLS));
                HeapFree(GetProcessHeap(), 0, block);
                return;
            }
        }
        HeapFree(GetProcessHeap(), 0, block);
    }
    out("BDFEDIT|VERSION|product=bdfedit|version=%s|synthetic=true|source=compiled-in", BDFEDIT_VERSION);
}

/* -------------------------------------------------------------- commandes */

static int cmd_idle(int seconds)
{
    OSVERSIONINFOEXW osv;
    memset(&osv, 0, sizeof(osv));
    osv.dwOSVersionInfoSize = sizeof(osv);
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
    GetVersionExW((OSVERSIONINFOW *)&osv);
#pragma GCC diagnostic pop
    print_version();
    out("BDFEDIT|START|pid=%lu|os=%lu.%lu.%lu|idle=%d", GetCurrentProcessId(), osv.dwMajorVersion,
        osv.dwMinorVersion, osv.dwBuildNumber, seconds);
    /* travail d'initialisation plausible : tas, chemin, répertoire courant, variables */
    void *scratch = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, 1 << 20);
    wchar_t cwd[MAX_PATH];
    GetCurrentDirectoryW(MAX_PATH, cwd);
    for (int i = 0; i < seconds; i++) {
        Sleep(1000);
        if ((i + 1) % 10 == 0) out("BDFEDIT|HEARTBEAT|t=%d", i + 1);
    }
    HeapFree(GetProcessHeap(), 0, scratch);
    out("BDFEDIT|EXIT|code=0");
    return 0;
}

static int cmd_edit(const wchar_t *in, const wchar_t *outpath, const char *text)
{
    DWORD size = 0;
    char *doc = read_file(in, &size);
    if (!doc) return 3;
    out("BDFEDIT|OPENED|path=%ls|bytes=%lu|lines=%d", in, size, count_lines(doc));

    /* modification : ajout d'une ligne */
    size_t tlen = strlen(text);
    size_t newsize = size + tlen + 1;
    char *newdoc = (char *)HeapAlloc(GetProcessHeap(), 0, newsize + 128);
    memcpy(newdoc, doc, size);
    size_t pos = size;
    if (size > 0 && doc[size - 1] != '\n') newdoc[pos++] = '\n';
    memcpy(newdoc + pos, text, tlen);
    pos += tlen;
    newdoc[pos++] = '\n';
    out("BDFEDIT|MODIFIED|appended_bytes=%lu", (unsigned long)(tlen + 1));

    /* pied de page horodaté (c'est ici que l'API Windows 7+ est appelée) */
    char stamp[64];
    const char *method = "?";
    DWORD err = 0;
    local_timestamp(stamp, sizeof(stamp), &method, &err);
    out("BDFEDIT|TZ|method=%s|err=%lu|stamp=%s", method, err, stamp);
    pos += _snprintf(newdoc + pos, 120, "# saved-at %s\n", stamp);

    if (!write_file_atomic(outpath, newdoc, (DWORD)pos)) {
        out("BDFEDIT|SAVE-FAILED|path=%ls", outpath);
        return 3;
    }
    out("BDFEDIT|SAVED|path=%ls|bytes=%lu|lines=%d", outpath, (unsigned long)pos, count_lines(newdoc));
    HeapFree(GetProcessHeap(), 0, doc);
    HeapFree(GetProcessHeap(), 0, newdoc);
    return 0;
}

static int cmd_show(const wchar_t *path)
{
    DWORD size = 0;
    char *doc = read_file(path, &size);
    if (!doc) return 3;
    out("BDFEDIT|REOPENED|path=%ls|bytes=%lu|lines=%d", path, size, count_lines(doc));
    out("BDFEDIT|CONTENT-BEGIN");
    fwrite(doc, 1, size, stdout);
    if (size == 0 || doc[size - 1] != '\n') printf("\n");
    out("BDFEDIT|CONTENT-END");
    HeapFree(GetProcessHeap(), 0, doc);
    return 0;
}

typedef int (__cdecl *pBdfPdfWriteText)(const char *utf8_text, const wchar_t *out_path, unsigned long *bytes_written);

static int cmd_export_pdf(const wchar_t *in, const wchar_t *outpath)
{
    DWORD size = 0;
    char *doc = read_file(in, &size);
    if (!doc) return 3;
    out("BDFEDIT|OPENED|path=%ls|bytes=%lu|lines=%d", in, size, count_lines(doc));
    HMODULE lib = LoadLibraryW(L"bdfpdf.dll");
    if (!lib) {
        out("BDFEDIT|EXPORT|status=unavailable|reason=bdfpdf.dll|err=%lu", GetLastError());
        return 2;
    }
    pBdfPdfWriteText fn = (pBdfPdfWriteText)(void (*)(void))GetProcAddress(lib, "BdfPdfWriteText");
    if (!fn) {
        out("BDFEDIT|EXPORT|status=unavailable|reason=BdfPdfWriteText|err=%lu", GetLastError());
        return 2;
    }
    unsigned long bytes = 0;
    int rc = fn(doc, outpath, &bytes);
    if (rc != 0) {
        out("BDFEDIT|EXPORT|status=failed|rc=%d", rc);
        return 3;
    }
    out("BDFEDIT|EXPORTED|path=%ls|bytes=%lu", outpath, bytes);
    return 0;
}

/*
 * Fonctionnalité « statistiques » : diagnostic mémoire via l'API ToolHelp (Heap32First).
 * Sous Wine 11.0, kernel32.Heap32First est un stub (@ stub) : l'appeler interrompt le processus.
 * Chemin de dégradation documenté : si Heap32First échoue, la fonctionnalité est signalée
 * indisponible et le programme continue (il n'en dépend pas pour son fonctionnement nominal).
 */
static int cmd_stats(void)
{
    print_version();
    out("BDFEDIT|START|pid=%lu|feature=stats", GetCurrentProcessId());
    HEAPENTRY32 he;
    memset(&he, 0, sizeof(he));
    he.dwSize = sizeof(he);
    unsigned long blocks = 0;
    SetLastError(0);
    BOOL ok = Heap32First(&he, GetCurrentProcessId(), 0);
    DWORD err = ok ? 0 : GetLastError();
    if (ok) {
        do { blocks++; } while (blocks < 100000 && Heap32Next(&he));
    }
    out("BDFEDIT|STATS|heap_walk=%s|err=%lu|blocks=%lu|feature=%s",
        ok ? "ok" : "failed", err, blocks, ok ? "available" : "unavailable-degraded");
    out("BDFEDIT|EXIT|code=0");
    return 0;
}

/*
 * Scénario « capability » : l'enregistrement est conditionné à une capacité optionnelle signalée par
 * IsAppCompatModeEnabled() (stub Wine). Chemin nominal Windows : la capacité répond, le programme
 * enregistre. Sous Wine nu : plantage (stub). Avec une réponse « absence déclarée » (FALSE), le
 * programme renonce proprement (exit 2) SANS enregistrer : la bonne réponse, ici, est un SUCCÈS
 * fabriqué (TRUE), que le laboratoire doit DÉCOUVRIR par recherche + oracle, et seulement si la
 * table de sûreté l'autorise (requête d'état sans tampon de sortie).
 */
static int cmd_capability(const wchar_t *in, const wchar_t *outpath, const char *text)
{
    SetLastError(0);
    BOOL enabled = IsAppCompatModeEnabled();
    out("BDFEDIT|CAP|enabled=%d|err=%lu", enabled, GetLastError());
    if (!enabled) {
        out("BDFEDIT|CAP-UNAVAILABLE|feature=save-gated");
        return 2;  /* renoncement propre : AUCUN enregistrement */
    }
    return cmd_edit(in, outpath, text);
}

static int usage(void)
{
    out("BDFEDIT|USAGE|cmds=--version;idle <s>;edit <in> <out> <text>;show <file>;stats;capability <in> <out> <text>;export-pdf <in> <out.pdf>");
    return 4;
}

int wmain(int argc, wchar_t **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 2) return usage();
    if (!wcscmp(argv[1], L"--version")) { print_version(); return 0; }
    if (!wcscmp(argv[1], L"idle")) return cmd_idle(argc > 2 ? _wtoi(argv[2]) : 5);
    if (!wcscmp(argv[1], L"edit") && argc >= 5) {
        char text[1024];
        WideCharToMultiByte(CP_UTF8, 0, argv[4], -1, text, sizeof(text), NULL, NULL);
        return cmd_edit(argv[2], argv[3], text);
    }
    if (!wcscmp(argv[1], L"stats")) return cmd_stats();
    if (!wcscmp(argv[1], L"capability") && argc >= 5) {
        char ctext[1024];
        WideCharToMultiByte(CP_UTF8, 0, argv[4], -1, ctext, sizeof(ctext), NULL, NULL);
        return cmd_capability(argv[2], argv[3], ctext);
    }
    if (!wcscmp(argv[1], L"show") && argc >= 3) return cmd_show(argv[2]);
    if (!wcscmp(argv[1], L"export-pdf") && argc >= 4) return cmd_export_pdf(argv[2], argv[3]);
    return usage();
}
