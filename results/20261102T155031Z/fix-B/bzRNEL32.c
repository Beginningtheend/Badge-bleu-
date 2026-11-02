/* DLL proxy générée par bdflab.shimgen — NE PAS ÉDITER À LA MAIN. */
/* Forwarders vers KERNEL32 ; implémentations réelles pour les fonctions corrigées. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

static void bdf_log(const char *fn, const char *strat, const char *detail) {
    const char *path = getenv("BDFLAB_SHIM_LOG");
    if (!path) return;
    FILE *f = fopen(path, "a");
    if (!f) return;
    fprintf(f, "shim|dll=%s|fn=%s|strategy=%s|%s\n", "kernel32.dll", fn, strat, detail ? detail : "");
    fclose(f);
}

/* Heap32First: classe API output-buffer, stratégie A (A-declared-absence); comportement : fonction non implémentée par Wine, candidate à un shim (stratégie à déterminer par la table de sûreté) */
int bdf_impl_Heap32First(void) {
    bdf_log("Heap32First", "A", "ret=0");
    SetLastError(120);
    return 0;
}

/* Heap32Next: classe API output-buffer, stratégie A (A-declared-absence); comportement : fonction non implémentée par Wine, candidate à un shim (stratégie à déterminer par la table de sûreté) */
int bdf_impl_Heap32Next(void) {
    bdf_log("Heap32Next", "A", "ret=0");
    SetLastError(120);
    return 0;
}

/* SystemTimeToTzSpecificLocalTimeEx: classe API output-buffer, stratégie A (A-declared-absence); repli documenté du programme vers SystemTimeToTzSpecificLocalTime quand la variante Ex échoue */
int bdf_impl_SystemTimeToTzSpecificLocalTimeEx(void) {
    bdf_log("SystemTimeToTzSpecificLocalTimeEx", "A", "ret=0");
    SetLastError(120);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) { (void)h;(void)r;(void)reason; return TRUE; }
