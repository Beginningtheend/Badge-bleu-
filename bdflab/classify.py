"""Classification des problèmes de compatibilité selon le rapport PolyRE.

Classes de contrat (rapport, « Quatre classes de contrats ») :
  A  déclaratif        clé de registre, police, runtime, override de DLL      → profil/catalogue
  B  comportement      valeur de retour, code d'erreur, drapeau               → shim généré
  C  sémantique        ordonnancement, mémoire, service ou pilote noyau       → escalade (hors v0.1)
  D  hors périmètre    DRM, activation, anti-triche, sécurité                 → refus explicite

Classe d'API (pour la table de sûreté, rapport « Table de sûreté ») :
  state-query          IsX / GetX renvoyant un statut, sans tampon de sortie
  output-buffer        lecture / conversion / énumération remplissant un tampon
  local-mutation       mutation locale au processus (propriété d'objet/fenêtre)
  persistent-mutation  fichier, registre, réseau, presse-papiers
  security             sécurité, identité, licence, signature, activation
  sync-time            synchronisation, temps, ordonnancement
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

# --- motifs de noms de fonctions ----------------------------------------------------------------

SECURITY_DLLS = {"crypt32", "bcrypt", "ncrypt", "wintrust", "secur32", "cryptui", "cryptnet", "softpub",
                 "mssign32", "wininet"}  # wininet surveillé (téléchargements)
SECURITY_NAME = re.compile(
    r"(licen[cs]|activat|genuine|wga|slmgr|sppsvc|authenticode|signtool|wintrust|certificat|\bcert[A-Z]|"
    r"crypt|bcrypt|ncrypt|protect(data|memory)|cng|drm|playready|widevine|anticheat|anti[_-]?tamper|"
    r"\bsign(ature|ed|hash)|verifytrust|winverifytrust|hwid|machineid|attestation|tpm|secure?boot)", re.I)
DRM_NAME = re.compile(r"(drm|playready|widevine|denuvo|vmprotect|themida|anticheat|easyanticheat|battleye|"
                      r"activation|licensing|licence|hasp|sentinel|rockey|dongle)", re.I)

SYNC_TIME_NAME = re.compile(
    r"^(WaitFor|SignalObjectAndWait|SleepConditionVariable|NtWaitFor|NtDelayExecution|QueryPerformance|"
    r"Sleep$|SleepEx|SwitchToThread|Yield|NtYield|SetWaitableTimer|CreateWaitableTimer|timeBeginPeriod|"
    r"timeSetEvent|QueueUserAPC|RtlRegisterWait|SetThreadpoolTimer|GetTickCount|GetSystemTimeAdjust)", re.I)

OUTPUT_BUFFER_NAME = re.compile(
    r"(Read[A-Z]|.*Read$|Enum[A-Z]|.*Enumerate|Query[A-Z].*(?:Info|Value|Data|Buffer|Name|String|Key)|"
    r"Get[A-Z].*(?:Info|Buffer|Data|Name|String|Text|List|Array|Names|Path|Directory|Content)|"
    r"Convert[A-Z]|Decode|Decompress|Unpack|Format[A-Z].*(?:Message|String)|.*ToString|Load[A-Z].*(?:String|Resource|Image)|"
    r"Find(First|Next)[A-Z]|RegGetValue|RegQueryValue|CryptDecrypt)", re.I)

STATE_QUERY_NAME = re.compile(
    r"^(Is[A-Z]|Has[A-Z]|Can[A-Z]|Are[A-Z]|Should[A-Z]|Supports[A-Z])|"
    r"^(Get[A-Z]\w*(?:Enabled|State|Status|Mode|Count|Level|Flags|Type|Version|Metrics|Capabilit|Present|Available|Supported))", re.I)

PERSISTENT_MUTATION_NAME = re.compile(
    r"(Write[A-Z]|.*Write$|Create(File|Directory|Key|Process|Service|Hard|Symbolic)|Delete(File|Key|Value|Service)|"
    r"Move(File|FileEx)|Copy(File|File2|FileEx)|RegSet(Value|KeyValue)|RegCreateKey|RegDeleteKey|RegDelete(Value|Tree)|"
    r"Set[A-Z].*(?:File|Registry|Key|Clipboard|Environment)|SetClipboard|EmptyClipboard|Save[A-Z]|"
    r"Flush[A-Z].*Buffers|WriteProcessMemory|RemoveDirectory|ReplaceFile|SetFileAttributes|SetEndOfFile|send$|sendto|connect$|WSASend)", re.I)

LOCAL_MUTATION_NAME = re.compile(
    r"(SetWindow|SetProp|SetParent|SetFocus|MoveWindow|SetCursor|SetLayeredWindow|SetWindowTheme|DwmSetWindowAttribute|"
    r"SetThreadDescription|SetThreadDpiAwareness|SetProcessDpiAwareness|SetProcessDefaultLayout|RegisterClass|"
    r"SetLastError|SetHandleInformation|SetConsole[A-Z]|SetThreadExecutionState)", re.I)

# contrats A : la panne est en réalité un composant déclaratif manquant, pas une fonction stub
A_DLL_MISSING = {"msvcp140", "msvcp120", "msvcp110", "msvcp100", "vcruntime140", "vcruntime140_1", "mfc140", "mfc140u",
                 "mfc120", "mfc120u", "mfcm140", "concrt140", "msvcr120", "msvcr110", "msvcr100", "msvcr90",
                 "d3dx9_43", "d3dx9_42", "d3dx10_43", "d3dx11_43", "d3dcompiler_47", "d3dcompiler_43", "xinput1_3",
                 "xaudio2_7", "mono", "mscoree", "gdiplus", "msvcp140_1", "msvcp140_2", "api-ms-win-crt-runtime-l1-1-0"}

RUNTIME_HINTS = {
    "msvcp": "vcrun (Visual C++ Redistributable)", "vcruntime": "vcrun (Visual C++ Redistributable)",
    "mfc": "vcrun (Visual C++ Redistributable)", "concrt": "vcrun (Visual C++ Redistributable)",
    "msvcr": "vcrun (Visual C++ Redistributable, version ancienne)", "d3dx9": "d3dx9 (DirectX End-User Runtime)",
    "d3dx10": "d3dx10 (DirectX End-User Runtime)", "d3dx11": "d3dx11 (DirectX End-User Runtime)",
    "d3dcompiler": "d3dcompiler (DirectX)", "xinput": "xinput (DirectX)", "xaudio2": "xact/xaudio (DirectX)",
    "mscoree": ".NET / Mono", "mono": "Mono", "gdiplus": "gdiplus",
}


@dataclass
class Problem:
    dll: str
    func: str
    wine_status: str           # export-absent | stub | dll-missing | semi-stub | forward-broken | runtime-exception
    contract_class: str        # A | B | C | D | unknown
    api_class: str             # state-query | output-buffer | local-mutation | persistent-mutation | security | sync-time | unknown
    evidence: list[str] = field(default_factory=list)
    prototype: dict | None = None
    rationale: str = ""
    confidence: str = "moyenne"  # haute | moyenne | basse
    fixable_v01: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def classify_api(func: str, dll: str, prototype: dict | None) -> tuple[str, str, str]:
    """Retourne (api_class, confidence, note) d'après le nom, la DLL et le prototype."""
    ret = (prototype or {}).get("ret", "") if prototype else ""
    params = (prototype or {}).get("params", []) if prototype else []
    notes = []
    dlll = dll.lower().removesuffix(".dll")

    if dlll in SECURITY_DLLS or SECURITY_NAME.search(func) or DRM_NAME.search(func):
        return "security", "haute", "nom/DLL liés à sécurité, identité, licence ou signature"

    if SYNC_TIME_NAME.search(func):
        return "sync-time", "haute", "synchronisation / temps / ordonnancement"

    # tampon de sortie : un paramètre pointeur non const (convention Windows LP*/P*, ou *) en plus du
    # nom évocateur. Les pointeurs const et les HANDLE/HWND/HKEY (valeurs opaques) ne comptent pas.
    def _is_out_ptr(t: str) -> bool:
        tl = t.lower()
        if "const" in tl:
            return False
        bare = t.strip().rstrip("*").strip()
        if "*" in t:
            return True
        # typedefs pointeur Windows : LPxxx, Pxxx (hors PBYTE d'entrée improbable ici), sauf handles opaques
        if bare in {"HANDLE", "HWND", "HKEY", "HMODULE", "HINSTANCE", "HDC", "HMENU", "HGLOBAL", "HLOCAL",
                    "HRSRC", "HBITMAP", "HICON", "HCURSOR", "HBRUSH", "HFONT", "HPEN", "HRGN", "HGDIOBJ",
                    "SC_HANDLE", "LPCWSTR", "LPCSTR", "PCWSTR", "PCSTR", "LPCVOID", "REFIID", "REFCLSID", "REFGUID"}:
            return False
        return bool(re.match(r"^(LP|P)[A-Z]", bare))
    has_out_ptr = any(_is_out_ptr(p[0]) for p in params)
    if OUTPUT_BUFFER_NAME.search(func):
        return "output-buffer", "haute" if has_out_ptr else "moyenne", "lecture/énumération/conversion remplissant un tampon"

    if PERSISTENT_MUTATION_NAME.search(func):
        return "persistent-mutation", "haute", "mutation persistante (fichier, registre, réseau, presse-papiers)"

    if LOCAL_MUTATION_NAME.search(func):
        return "local-mutation", "moyenne", "mutation locale au processus"

    if STATE_QUERY_NAME.search(func):
        # requête d'état seulement si pas de tampon de sortie évident
        if has_out_ptr and ret.upper() in {"BOOL", "WINBOOL", "HRESULT", "LSTATUS", "LONG", "NTSTATUS"} and len(params) >= 2:
            return "state-query", "moyenne", "Get* avec tampon : statut + sortie, prudence (traité comme requête d'état seulement si sortie ignorable)"
        return "state-query", "haute", "requête d'état renvoyant un statut"

    # défaut : si le retour est un simple statut et peu/pas de pointeur de sortie → state-query basse confiance
    if ret.upper() in {"BOOL", "WINBOOL", "HRESULT", "LSTATUS", "NTSTATUS", "DWORD", "INT", "LONG"} and not has_out_ptr:
        return "state-query", "basse", "heuristique : statut sans tampon de sortie apparent"
    if has_out_ptr:
        return "output-buffer", "basse", "heuristique : présence d'un pointeur de sortie"
    return "unknown", "basse", "non classé par heuristique de nom/prototype"


def classify_problem(dll: str, func: str, wine_status: str, prototype: dict | None, evidence: list[str],
                     semistub: dict | None = None, resolution_notes: list[str] | None = None) -> Problem:
    dlll = dll.lower().removesuffix(".dll")
    api_class, conf, api_note = classify_api(func, dll, prototype)
    ev = list(evidence)
    if api_note:
        ev.append("api: " + api_note)
    for note in (resolution_notes or []):
        ev.append("res: " + note)

    # D — hors périmètre : sécurité/identité/licence quelle que soit la panne
    if api_class == "security" or DRM_NAME.search(func):
        return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="D", api_class=api_class or "security",
                       evidence=ev, prototype=prototype, confidence="haute", fixable_v01=False,
                       rationale="hors périmètre : sécurité, identité, licence, signature ou activation ; refus explicite (rapport, classe D)")

    # C — sémantique profonde : synchronisation/temps/ordonnancement
    if api_class == "sync-time":
        return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="C", api_class=api_class,
                       evidence=ev, prototype=prototype, confidence=conf, fixable_v01=False,
                       rationale="sémantique profonde (synchronisation/temps/ordonnancement) : escalade niveau 2/3, hors v0.1")

    # A — déclaratif : DLL de runtime manquante
    if wine_status == "dll-missing":
        hint = next((v for k, v in RUNTIME_HINTS.items() if dlll.startswith(k)), None)
        if hint or dlll in A_DLL_MISSING:
            return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="A", api_class=api_class,
                           evidence=ev + ([f"composant attendu : {hint}"] if hint else []), prototype=prototype,
                           confidence="haute", fixable_v01=True,
                           rationale=f"déclaratif : DLL « {dlll} » absente, à fournir par le catalogue{(' (' + hint + ')') if hint else ''} + empreinte, override natif")
        # DLL inconnue sans correspondance catalogue : A possible mais incertain
        return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="A", api_class=api_class,
                       evidence=ev, prototype=prototype, confidence="basse", fixable_v01=False,
                       rationale=f"déclaratif probable : DLL « {dlll} » absente, mais hors catalogue connu ; à vérifier manuellement")

    # B — comportement : fonction stub / absente / semi-stub appelée, résoluble par un shim
    if wine_status in {"stub", "export-absent", "forward-broken", "semi-stub", "runtime-exception"}:
        # output-buffer et persistent-mutation : shim possible en stratégie A (absence déclarée) seulement
        fixable = api_class in {"state-query", "local-mutation", "output-buffer", "persistent-mutation", "unknown"}
        return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="B", api_class=api_class,
                       evidence=ev, prototype=prototype, confidence=conf, fixable_v01=fixable,
                       rationale="comportement : fonction non implémentée par Wine, candidate à un shim (stratégie à déterminer par la table de sûreté)")

    return Problem(dll=dlll, func=func, wine_status=wine_status, contract_class="unknown", api_class=api_class,
                   evidence=ev, prototype=prototype, confidence="basse", fixable_v01=False,
                   rationale="non classé")
