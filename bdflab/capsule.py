"""Générateur et linter de capsules (format TOML du rapport PolyRE, HANDOFF §3).

Une capsule est un fichier déclaratif indexé par l'identité du binaire (sha256 + imphash + version),
contenant les contrats (classe A déclaratifs, classe B « shim »), les preuves (traces), les résultats
de scénarios et un statut. Le linter refuse toute capsule violant la table de sûreté ; une capsule
expérimentale n'est jamais appliquée silencieusement à un logiciel de production.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib
import tomli_w

from .safety import lint_shim, evaluate

SCHEMA_VERSION = "0.1"
VALID_STATUS = {"experimental", "validated", "rejected"}


@dataclass
class Capsule:
    identity: dict
    runtime: dict
    contracts: list[dict]      # classe A déclaratifs
    shims: list[dict]          # classe B
    validation: dict
    provenance: dict
    status: str = "experimental"
    synthetic: bool = False
    rejected: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_toml_obj(self) -> dict:
        obj = {
            "meta": {"schema": SCHEMA_VERSION, "status": self.status, "synthetic": self.synthetic},
            "identity": self.identity,
            "runtime": self.runtime,
        }
        if self.contracts:
            obj["contract"] = self.contracts
        if self.shims:
            obj["shim"] = self.shims
        obj["validation"] = self.validation
        obj["provenance"] = self.provenance
        if self.rejected:
            obj["rejected"] = self.rejected
        if self.notes:
            obj["notes"] = {"lines": self.notes}
        return obj

    def dumps(self) -> str:
        header = (
            "# Capsule PolyRE BDF-Lab — générée automatiquement.\n"
            "# Une capsule « experimental » ne doit JAMAIS être appliquée silencieusement à un\n"
            "# logiciel de production (rapport, condition 7 ; HANDOFF §4). Statut, synthétique et\n"
            "# version Wine EXACTE sont obligatoires. Les preuves (traces) justifient chaque shim.\n\n"
        )
        return header + tomli_w.dumps(self.to_toml_obj())

    def dump(self, path: Path) -> None:
        Path(path).write_text(self.dumps(), encoding="utf-8")


def build_capsule(identity: dict, wine_version: str, polyre_range: str, contracts: list[dict], shims: list[dict],
                  scenarios: list[str], results: dict, runs: int, machines: int, status: str, synthetic: bool,
                  evidence_by_func: dict | None = None, rejected: list[dict] | None = None,
                  generated_by: str = "bdf-lab 0.1", today: str | None = None) -> Capsule:
    today = today or _dt.date.today().isoformat()
    evidence_by_func = evidence_by_func or {}
    norm_shims = []
    for sh in shims:
        entry = {
            "dll": sh["dll"] if str(sh["dll"]).endswith(".dll") else sh["dll"] + ".dll",
            "function": sh["func"],
            "strategy": sh["strategy"],
            "api_class": sh.get("api_class", ""),
            "returns": sh["returns"] if sh.get("returns") is not None else 0,
        }
        if sh.get("last_error") is not None:
            entry["last_error"] = sh["last_error"]
        if sh.get("tainted"):
            entry["tainted"] = True
        if sh.get("fixture_source"):
            entry["fixture_source"] = sh["fixture_source"]
        ev = evidence_by_func.get(sh["func"]) or evidence_by_func.get(f"{sh['dll']}.{sh['func']}")
        if ev:
            entry["evidence"] = ev
        if sh.get("note"):
            entry["note"] = sh["note"]
        if sh.get("hint"):
            # indice statique (analyse des branches) : explicabilité ; n'autorise rien, l'oracle reste juge
            entry["branch_hint"] = {k: v for k, v in sh["hint"].items() if v is not None}
        norm_shims.append(entry)
    return Capsule(
        identity=identity,
        runtime={"polyre": polyre_range, "wine": wine_version},
        contracts=contracts,
        shims=norm_shims,
        validation={"scenarios": scenarios, "results": results, "runs": runs, "machines": machines,
                    "date": today, "expires_on": "changement de runtime (Wine ou PolyRE)"},
        provenance={"generated_by": generated_by, "reviewed_by": "", "signature": ""},
        status=status, synthetic=synthetic, rejected=rejected or [],
    )


def load_capsule(path: Path) -> dict:
    with Path(path).open("rb") as fh:
        return tomllib.load(fh)


# ---------------------------------------------------------------------------
# linter de sûreté de la capsule
# ---------------------------------------------------------------------------

@dataclass
class CapsuleLint:
    ok: bool
    errors: list[str]
    warnings: list[str]


def lint_capsule(obj: dict) -> CapsuleLint:
    """Vérifie la conformité d'une capsule (structure + table de sûreté). obj = TOML chargé."""
    errors: list[str] = []
    warnings: list[str] = []

    meta = obj.get("meta", {})
    status = meta.get("status")
    if status not in VALID_STATUS:
        errors.append(f"statut invalide : {status!r} (attendu : {sorted(VALID_STATUS)})")
    synthetic = bool(meta.get("synthetic", False))

    ident = obj.get("identity", {})
    if not ident.get("sha256"):
        errors.append("identity.sha256 manquant (clé d'identité exacte obligatoire)")
    if not ident.get("imphash"):
        warnings.append("identity.imphash manquant (clé secondaire recommandée)")

    runtime = obj.get("runtime", {})
    if not runtime.get("wine"):
        errors.append("runtime.wine manquant (version Wine EXACTE obligatoire — rapport, écart §3)")

    # shims : re-vérifier chaque shim contre la table de sûreté
    for sh in obj.get("shim", []):
        fn = sh.get("function", "?")
        api = sh.get("api_class", "unknown")
        strat = sh.get("strategy", "?")
        has_out = api == "output-buffer"
        # on reconstitue la classe de contrat : un shim implique une classe B (A/C/D ne produisent pas de shim)
        issues = lint_shim("B", api, strat, has_out, synthetic, sh.get("returns"), sh.get("last_error"),
                           status, persistent_disposable=synthetic)
        for i in issues:
            msg = f"shim {fn} ({api}, stratégie {strat}) : {i.message}"
            (errors if i.level == "error" else warnings).append(msg)
        if strat == "F" and not sh.get("fixture_source"):
            errors.append(f"shim {fn} : stratégie F sans « fixture_source » (provenance de la réponse enregistrée requise)")
        if strat in ("S", "F"):
            if status != "validated" and not synthetic:
                errors.append(f"shim {fn} : stratégie S interdite hors capsule validée (condition 7) "
                              f"sauf cas synthétique de laboratoire")
            if not sh.get("tainted"):
                warnings.append(f"shim {fn} : stratégie S sans marque « tainted » (teinte/journal requis)")

    # contrats déclaratifs (classe A) : exiger une empreinte pour toute DLL fournie
    for c in obj.get("contract", []):
        if c.get("kind") in {"dll-provide", "dll-override"} and not c.get("sha256"):
            warnings.append(f"contrat {c.get('dll')} : empreinte sha256 absente (catalogue + empreinte requis)")

    # validation : résultats présents, au moins 2 exécutions
    val = obj.get("validation", {})
    if val.get("runs", 0) < 2:
        warnings.append("validation.runs < 2 (rapport : reproduire sur 2 exécutions indépendantes)")
    if not val.get("results"):
        warnings.append("validation.results vide (aucun oracle d'effet enregistré)")

    # une capsule « validated » exige une signature et 0 faux succès / 0 régression consignés
    if status == "validated":
        if not obj.get("provenance", {}).get("signature"):
            errors.append("capsule « validated » sans signature du labo (sinon : experimental, stratégie A seulement)")

    # nombre de shims borné (candidate à l'escalade au-delà de 25)
    n_shims = len(obj.get("shim", []))
    if n_shims > 25:
        warnings.append(f"{n_shims} shims (> 25) : application candidate à l'escalade (rapport, critère borné)")

    return CapsuleLint(ok=not errors, errors=errors, warnings=warnings)
