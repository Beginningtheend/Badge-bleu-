"""Orchestrateur : du diagnostic d'un exécutable à une proposition de correctif de compatibilité.

Enchaîne : analyse statique (:mod:`pe_surface`) → classification A/B/C/D (:mod:`classify`) →
décision de sûreté (:mod:`safety`) → génération d'une DLL de compatibilité (:mod:`shimgen`) ou d'un
contrat déclaratif (classe A). Ne touche jamais l'exécutable d'origine : toute correction porte sur
une copie, dans un préfixe Wine isolé et jetable.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .wine_db import WineDB
from .pe_surface import PESurface, analyze, identity_of
from .classify import Problem, classify_problem, RUNTIME_HINTS, A_DLL_MISSING
from .safety import evaluate, lint_shim
from .shimgen import (ShimSpec, GeneratedShimDLL, PatchResult, generate_shim_dll, patch_exe_imports,
                      default_response, _proxy_name)


@dataclass
class DeclarativeContract:
    """Classe A : composant déclaratif à fournir (DLL de runtime manquante, override, clé de registre)."""
    kind: str                 # "dll-provide" | "dll-override" | "registry"
    dll: str
    catalogue_source: str     # entrée du catalogue du labo, ou "" si inconnue
    sha256: str = ""
    mode: str = "native"      # override builtin/native
    evidence: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FixPlan:
    identity: dict
    problems: list[dict]
    declarative: list[DeclarativeContract]
    shims: list[ShimSpec]
    rejected: list[dict]           # problèmes non corrigeables (C/D) avec motif
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def fixable(self) -> bool:
        return bool(self.declarative or self.shims)


def diagnose(surface: PESurface, db: WineDB, catalogue: dict[str, str] | None = None) -> list[Problem]:
    """Classe chaque import non implémenté et chaque DLL dynamique manquante."""
    catalogue = catalogue or {}
    problems: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for imp in surface.imports:
        res = imp.resolution
        if res["status"] == "implemented":
            continue
        key = (res["dll"], imp.func)
        if key in seen:
            continue
        seen.add(key)
        p = classify_problem(res["dll"], imp.func, res["status"], res.get("prototype"),
                             evidence=[f"import statique{' (différé)' if imp.delay else ''} depuis {Path(surface.path).name}"],
                             semistub=res.get("semistub"), resolution_notes=res.get("notes"))
        problems.append(p)
    # DLL chargées dynamiquement et absentes de Wine (candidates classe A)
    for dll in surface.dynamic_dll_candidates:
        d = dll.lower().removesuffix(".dll")
        if db.dll_known(d):
            continue
        key = (d, "<load>")
        if key in seen:
            continue
        seen.add(key)
        in_cat = d in {c.lower().removesuffix(".dll") for c in catalogue}
        hint = next((v for k, v in RUNTIME_HINTS.items() if d.startswith(k)), None)
        problems.append(Problem(dll=d, func="<load dynamique>", wine_status="dll-missing", contract_class="A",
                                api_class="loader", evidence=[f"chaîne « {dll} » repérée dans {Path(surface.path).name}",
                                "chargement dynamique présumé (LoadLibrary / délai)"] + ([f"catalogue: {d}"] if in_cat else [])
                                + ([f"composant: {hint}"] if hint else []),
                                confidence="haute" if (in_cat or hint) else "basse",
                                fixable_v01=in_cat or bool(hint),
                                rationale="déclaratif : DLL chargée dynamiquement, absente de Wine ; à fournir par le catalogue du labo"))
    return problems


def plan_fixes(surface: PESurface, problems: list[Problem], db: WineDB, catalogue: dict[str, str] | None = None,
               synthetic: bool = False, allow_persistent_lab: bool = False) -> FixPlan:
    """Transforme les problèmes classés en contrats déclaratifs (A) et DLL de compatibilité (B)."""
    catalogue = catalogue or {}
    cat_norm: dict[str, tuple[str, str]] = {}
    for _name, _sha in catalogue.items():
        cat_norm[_name.lower().removesuffix(".dll")] = (_name, _sha)
    declarative: list[DeclarativeContract] = []
    shims: list[ShimSpec] = []
    rejected: list[dict] = []
    notes: list[str] = []

    for p in problems:
        if p.contract_class == "A":
            d = p.dll
            cat = cat_norm.get(d)
            if cat:
                declarative.append(DeclarativeContract(kind="dll-provide", dll=d, catalogue_source=f"catalogue:{cat[0]}",
                                                        sha256=cat[1], mode="native",
                                                        evidence=p.evidence, note=p.rationale))
            else:
                # hors catalogue : contrat déclaratif « à fournir », non applicable en l'état
                rejected.append({**p.to_dict(), "reject_reason": "DLL de runtime absente du catalogue du labo ; "
                                 "à ajouter manuellement (source officielle + empreinte) avant application"})
            continue
        if p.contract_class in {"C", "D"}:
            rejected.append({**p.to_dict(), "reject_reason": p.rationale})
            continue
        if p.contract_class == "B":
            proto = p.prototype or {}
            has_out = p.api_class in {"output-buffer"} or any(
                ("*" in (pp[0] if isinstance(pp, (list, tuple)) else "")) for pp in proto.get("params", []))
            verdict = evaluate(p.contract_class, p.api_class, has_out, synthetic,
                               persistent_disposable=allow_persistent_lab)
            if verdict.strategy_default == "none":
                rejected.append({**p.to_dict(), "reject_reason": "; ".join(verdict.reasons)})
                continue
            strategy = verdict.strategy_default
            ret, le = default_response(p.api_class, proto.get("ret", ""), strategy)
            issues = lint_shim(p.contract_class, p.api_class, strategy, has_out, synthetic, ret, le, p.wine_status,
                               persistent_disposable=allow_persistent_lab)
            errors = [i for i in issues if i.level == "error"]
            if errors:
                rejected.append({**p.to_dict(), "reject_reason": "lint: " + "; ".join(i.message for i in errors)})
                continue
            note = p.rationale
            if p.func == "SystemTimeToTzSpecificLocalTimeEx":
                note = "repli documenté du programme vers SystemTimeToTzSpecificLocalTime quand la variante Ex échoue"
            shims.append(ShimSpec(dll=p.dll, func=p.func, strategy=strategy, api_class=p.api_class,
                                  ret_type=proto.get("ret", ""), returns=ret, last_error=le,
                                  tainted=(strategy == "S"), note=note))

    return FixPlan(identity=identity_of(surface), problems=[p.to_dict() for p in problems],
                   declarative=declarative, shims=shims, rejected=rejected, notes=notes)


@dataclass
class BuiltFix:
    patched_exe: str | None
    generated_dlls: list[dict]
    catalogue_dlls: list[dict]           # [{name, source, dest}]
    rename_map: dict
    shim_log_env: str
    actions: list[str]
    gen_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def build_fix(plan: FixPlan, exe: Path, out_dir: Path, surface: PESurface, catalogue_dir: Path | None = None,
              cc: str = "x86_64-w64-mingw32-gcc") -> BuiltFix:
    """Construit les artefacts du correctif : DLL de compatibilité + copie corrigée de l'exécutable.

    - classe B : une DLL de compatibilité par DLL d'origine concernée, qui renvoie les exports réels
      vers la bibliothèque Wine et fournit les fonctions manquantes ; le nom de la DLL d'origine est
      redirigé, sur place, vers celui de la DLL de compatibilité dans une COPIE de l'exécutable ;
    - classe A : la DLL du catalogue est déposée à côté de la copie.
    """
    import time
    out_dir.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    generated: list[dict] = []
    catalogue_dlls: list[dict] = []
    rename_map: dict[str, str] = {}
    t0 = time.time()

    # regrouper les shims par DLL d'origine
    by_dll: dict[str, list[ShimSpec]] = {}
    for s in plan.shims:
        by_dll.setdefault(s.dll, []).append(s)

    taken: set[str] = set()
    for dll, specs in by_dll.items():
        # toutes les fonctions importées de cette DLL par la cible (pour les renvoyer)
        imported = [i.func for i in surface.imports if i.dll.lower().removesuffix(".dll") == dll]
        orig = dll if dll.endswith(".dll") else dll + ".dll"
        # retrouver le nom exact tel qu'importé (casse d'origine) pour la redirection
        orig_exact = next((i.dll for i in surface.imports if i.dll.lower().removesuffix(".dll") == dll), orig)
        pname = _proxy_name(orig_exact, taken)
        taken.add(pname.lower())
        g = generate_shim_dll(dll, imported, specs, out_dir, proxy_name=pname, cc=cc)
        generated.append(g.to_dict())
        rename_map[orig_exact] = pname
        actions.append(f"classe B : DLL de compatibilité {pname} pour {orig_exact} "
                       f"({g.forwarded} exports renvoyés vers Wine, {len(g.implemented)} fournis : {', '.join(g.implemented)})")

    patched = None
    if rename_map:
        patched_path = out_dir / exe.name
        pr = patch_exe_imports(exe, patched_path, rename_map)
        patched = pr.patched_exe
        for r in pr.renamed:
            actions.append(f"copie corrigée : import « {r['from']} » redirigé vers « {r['to']} » (original intact)")
        for note in pr.notes:
            actions.append("avertissement: " + note)
    else:
        # pas de shim : on copie quand même l'exe pour un préfixe isolé homogène
        patched_path = out_dir / exe.name
        shutil.copy2(exe, patched_path)
        patched = str(patched_path)

    # classe A : déposer les DLL du catalogue
    for c in plan.declarative:
        if c.kind != "dll-provide":
            continue
        src = None
        if catalogue_dir:
            cand = catalogue_dir / (c.dll + ".dll")
            if cand.exists():
                src = cand
        if src:
            dest = out_dir / (c.dll + ".dll")
            shutil.copy2(src, dest)
            catalogue_dlls.append({"name": c.dll + ".dll", "source": str(src), "dest": str(dest)})
            actions.append(f"classe A : {c.dll}.dll fourni depuis le catalogue du labo ({c.catalogue_source})")
        else:
            actions.append(f"classe A : {c.dll}.dll référencé mais absent du catalogue local (non déposé)")

    return BuiltFix(patched_exe=patched, generated_dlls=generated, catalogue_dlls=catalogue_dlls,
                    rename_map=rename_map, shim_log_env="BDFLAB_SHIM_LOG", actions=actions,
                    gen_seconds=round(time.time() - t0, 3))
