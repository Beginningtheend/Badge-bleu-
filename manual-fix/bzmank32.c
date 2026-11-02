/*
 * Correctif MANUEL de référence (config C de l'expérience) — écrit à la main.
 *
 * DLL de compatibilité pour KERNEL32.dll, destinée à être fournie à une COPIE de l'exécutable de
 * test dont l'import « KERNEL32.dll » est redirigé vers « bzmank32.dll » (même longueur de nom).
 * Elle renvoie vers la bibliothèque Wine toutes les fonctions réellement présentes et fournit les
 * trois fonctions absentes de Wine 11.0, en IMPLÉMENTANT réellement la plus utile.
 *
 * Différence avec le correctif AUTOMATIQUE (config B) :
 *   - config B : stratégie A (absence déclarée) pour SystemTimeToTzSpecificLocalTimeEx ; le
 *     programme emprunte son repli documenté (SystemTimeToTzSpecificLocalTime).
 *   - config C : implémentation COMPLÈTE de SystemTimeToTzSpecificLocalTimeEx (le programme obtient
 *     l'heure locale par le chemin nominal, method=ex), au prix d'un temps d'écriture humain.
 *
 * Ce fichier et bzmank32.def ont été rédigés à la main (liste des renvois incluse), ce qui
 * représente l'effort humain mesuré par la config C.
 */
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <timezoneapi.h>
#include <tlhelp32.h>

/* Implémentation réelle : la structure dynamique commence par les mêmes champs que
 * TIME_ZONE_INFORMATION ; on délègue à SystemTimeToTzSpecificLocalTime (présente dans Wine). */
BOOL WINAPI SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *dtzi,
                                              const SYSTEMTIME *utc, LPSYSTEMTIME local)
{
    TIME_ZONE_INFORMATION tzi;
    const TIME_ZONE_INFORMATION *p = NULL;
    if (dtzi) {
        memcpy(&tzi, dtzi, sizeof(tzi));   /* préfixe commun : Bias, Standard/Daylight Name/Date/Bias */
        p = &tzi;
    }
    return SystemTimeToTzSpecificLocalTime((TIME_ZONE_INFORMATION *)p, utc, local);
}

/* ToolHelp : implémentation de référence « honnête » = non prise en charge, échec propre.
 * (Une implémentation complète du parcours de tas dépasse le cadre d'un correctif de référence.) */
BOOL WINAPI Heap32First(LPHEAPENTRY32 lphe, DWORD pid, ULONG_PTR heapid)
{
    (void)lphe; (void)pid; (void)heapid;
    SetLastError(ERROR_CALL_NOT_IMPLEMENTED);
    return FALSE;
}

BOOL WINAPI Heap32Next(LPHEAPENTRY32 lphe)
{
    (void)lphe;
    SetLastError(ERROR_CALL_NOT_IMPLEMENTED);
    return FALSE;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) { (void)h;(void)reason;(void)r; return TRUE; }
