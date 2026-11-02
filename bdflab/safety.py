"""Table de sûreté et linter (rapport PolyRE « Table de sûreté » + HANDOFF §2, §3, §5).

Deux stratégies de réponse optimiste :
  A  absence déclarée  — répondre « non pris en charge » par un code que le programme sait traiter
                         (ERROR_CALL_NOT_IMPLEMENTED=120, E_NOTIMPL=0x80004001, NULL + last error).
                         Rien n'est fabriqué. C'est le DÉFAUT.
  S  succès fabriqué    — répondre comme si l'appel avait réussi. Réservé, et seulement en laboratoire
                         sur données jetables, aux classes autorisées, sous teinte et journal.

Table de sûreté (A autorisé / S autorisé) :
  state-query          A oui · S oui (conditions 4-6 ; et seulement si « sans donnée » : pas de tampon de sortie)
  output-buffer        A oui · S NON (donnée fabriquée = corruption)
  local-mutation       A oui · S oui (sous teinte)
  persistent-mutation  A oui · S NON (sauf labo, données jetables, jamais en production)
  security             A NON · S NON  (classe D)
  sync-time            A NON · S NON  (classe C : escalade)

Sept conditions de sûreté pour S (toutes requises) : (1) requête sans donnée ; (2) aucun effet
persistant promis ; (3) hors sécurité ; (4) cohérence observationnelle ; (5) confinement (teinte,
blocage des écritures influencées) ; (6) réversibilité (journal + ré-exécution) ; (7) validation
hors ligne — en production S ne vient que d'une capsule validée ; la spéculation en direct se limite à A.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

# api_class -> (A autorisé, S autorisé en labo sur données jetables)
SAFETY_TABLE: dict[str, tuple[bool, bool]] = {
    "state-query": (True, True),
    "output-buffer": (True, False),
    "local-mutation": (True, True),
    "persistent-mutation": (True, False),
    "security": (False, False),
    "sync-time": (False, False),
    "unknown": (True, False),
}

# codes de retour « absence déclarée » admissibles
ERROR_CALL_NOT_IMPLEMENTED = 120     # ERROR_CALL_NOT_IMPLEMENTED
E_NOTIMPL = 0x80004001
S_OK = 0
ERROR_NOT_SUPPORTED = 50


@dataclass
class SafetyVerdict:
    strategy_default: str              # "A" | "S" | "none"
    a_allowed: bool
    s_allowed_lab: bool
    s_allowed_production: bool         # toujours False pour une capsule expérimentale
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(contract_class: str, api_class: str, has_output_pointer: bool, synthetic: bool,
             persistent_disposable: bool = False) -> SafetyVerdict:
    """Décide des stratégies autorisées pour un problème donné."""
    reasons: list[str] = []
    if contract_class == "D":
        return SafetyVerdict("none", False, False, False,
                             ["classe D (sécurité/identité/licence/activation) : aucun correctif, refus explicite"])
    if contract_class == "C" or api_class == "sync-time":
        return SafetyVerdict("none", False, False, False,
                             ["classe C (sémantique profonde) : escalade niveau 2/3, hors périmètre v0.1"])

    a_tab, s_tab = SAFETY_TABLE.get(api_class, (True, False))
    a_allowed = a_tab
    s_lab = s_tab

    # condition 1 : S exige « sans donnée » — un tampon de sortie l'interdit même pour une state-query
    if s_lab and has_output_pointer:
        s_lab = False
        reasons.append("S refusé : la fonction remplit un tampon de sortie (condition 1 « sans donnée » non remplie)")

    # mutation persistante : S seulement en labo sur données jetables, jamais sinon
    if api_class == "persistent-mutation":
        if persistent_disposable and synthetic:
            s_lab = True
            reasons.append("S toléré en laboratoire : mutation persistante sur données jetables, synthétique, sous journal")
        else:
            s_lab = False
            reasons.append("S refusé : mutation persistante hors cadre labo/jetable")

    s_production = False  # une capsule expérimentale n'autorise jamais S en production (condition 7)

    default = "A" if a_allowed else ("S" if s_lab else "none")
    if a_allowed:
        reasons.append("A (absence déclarée) autorisé : réponse « non implémenté » sans rien fabriquer — stratégie par défaut")
    if s_lab:
        reasons.append("S (succès fabriqué) autorisé en laboratoire sous teinte et journal (conditions 2,4,5,6)")
    elif not s_lab and api_class not in {"persistent-mutation"}:
        reasons.append(f"S non autorisé pour la classe d'API « {api_class} » (table de sûreté)")
    return SafetyVerdict(default, a_allowed, s_lab, s_production, reasons)


@dataclass
class LintIssue:
    level: str   # "error" | "warning"
    code: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def lint_shim(contract_class: str, api_class: str, strategy: str, has_output_pointer: bool, synthetic: bool,
              returns, last_error, status: str, persistent_disposable: bool = False) -> list[LintIssue]:
    """Vérifie qu'un shim proposé respecte la table de sûreté. Renvoie la liste des problèmes."""
    issues: list[LintIssue] = []
    v = evaluate(contract_class, api_class, has_output_pointer, synthetic, persistent_disposable)

    if contract_class == "D":
        issues.append(LintIssue("error", "class-D-forbidden",
                                "classe D : aucun correctif autorisé (sécurité/identité/licence/activation)"))
        return issues
    if contract_class == "C":
        issues.append(LintIssue("error", "class-C-escalation",
                                "classe C : escalade requise, aucun shim en v0.1"))
        return issues

    if strategy not in {"A", "S"}:
        issues.append(LintIssue("error", "bad-strategy", f"stratégie « {strategy} » inconnue (A ou S)"))
        return issues

    if strategy == "A" and not v.a_allowed:
        issues.append(LintIssue("error", "A-forbidden", f"stratégie A interdite pour « {api_class} »"))
    if strategy == "S":
        if not v.s_allowed_lab:
            issues.append(LintIssue("error", "S-forbidden",
                                    f"stratégie S interdite pour « {api_class} »" +
                                    (" (tampon de sortie)" if has_output_pointer else "")))
        if not synthetic and api_class == "persistent-mutation":
            issues.append(LintIssue("error", "S-persistent-nonsynthetic",
                                    "stratégie S sur mutation persistante hors cas synthétique jetable"))
        # S exige une teinte : signalé comme avertissement si la capsule ne le mentionne pas (vérifié ailleurs)

    # cohérence du code de retour avec la stratégie A
    if strategy == "A":
        ok_codes = {ERROR_CALL_NOT_IMPLEMENTED, E_NOTIMPL, ERROR_NOT_SUPPORTED, 0, None}
        if returns not in (0, None) and returns not in ok_codes and (last_error not in ok_codes):
            issues.append(LintIssue("warning", "A-return-check",
                                    f"stratégie A : vérifier que retour={returns}/last_error={last_error} est bien un échec propre"))
    return issues
