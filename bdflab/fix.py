#!/usr/bin/env python3
"""« Déposer l'exe » — flux en une commande (vision produit, prototype synthétique).

  python3 -m bdflab.fix --exe <PE> [--commons commons] [--data data/wine-11.0] [--apply DIR]

Étapes : empreinte → recherche dans le communs de capsules (sha256 exact, sinon imphash dégradé) →
si trouvée, on l'annonce (jamais appliquée silencieusement si experimental) ; sinon on diagnostique,
on génère un correctif, on émet une capsule et on l'ajoute au communs. Avec --apply, on matérialise
le bundle (copie corrigée + DLL de compatibilité) dans DIR. Aucune exécution de binaire tiers ici.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .wine_db import WineDB
from . import pe_surface, fixgen
from .commons import CapsuleCommons
from .capsule import build_capsule, lint_capsule, load_capsule
from .wine_runner import wine_info
from . import branch_hint


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--data", type=Path, default=Path("data/wine-11.0"))
    ap.add_argument("--commons", type=Path, default=Path("commons"))
    ap.add_argument("--catalogue", type=Path, default=Path("catalogue"))
    ap.add_argument("--apply", type=Path, default=None, help="matérialiser le bundle corrigé dans ce dossier")
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args(argv)

    db = WineDB(args.data)
    commons = CapsuleCommons(args.commons)
    s = pe_surface.analyze(args.exe, db)
    ident = pe_surface.identity_of(s)
    print(f"[fix] {args.exe.name}  sha256={s.sha256[:16]}  imphash={s.imphash}  ({s.machine})")

    look = commons.get(s.sha256, s.imphash)
    if look.match != "none":
        print(f"[fix] capsule {look.match.upper()} : {look.note} — statut={look.status}")
        if look.status == "experimental":
            print("[fix] capsule EXPERIMENTAL : ne pas appliquer silencieusement en production (choix explicite requis).")
        print(f"[fix] capsule : {look.capsule_path}")
        return 0

    print("[fix] aucune capsule connue → diagnostic et génération")
    catalogue = {}
    if args.catalogue.is_dir():
        import hashlib
        for p in sorted(args.catalogue.glob("*.dll")):
            catalogue[p.stem] = hashlib.sha256(p.read_bytes()).hexdigest()
    problems = fixgen.diagnose(s, db, catalogue)
    plan = fixgen.plan_fixes(s, problems, db, catalogue, synthetic=args.synthetic)
    wi = wine_info() if _wine_ok() else None
    wine_ver = wi.version if wi else "11.0"
    print(f"[fix] problèmes : {len(problems)} | shims générables : {len(plan.shims)} | contrats A : {len(plan.declarative)} | refusés : {len(plan.rejected)}")
    for r in plan.rejected:
        print(f"       refusé {r['dll']}.{r['func']} ({r.get('contract_class')}) : {r['reject_reason'][:70]}")

    if args.apply:
        bf = fixgen.build_fix(plan, args.exe, args.apply, s, catalogue_dir=(args.catalogue if args.catalogue.is_dir() else None))
        print(f"[fix] bundle matérialisé dans {args.apply} ({len(bf.generated_dlls)} DLL de compatibilité)")

    # indices statiques : lire le code après chaque appel pour prédire la réponse attendue (explicabilité)
    hints = {}
    for x in plan.shims:
        try:
            h = branch_hint.analyze(args.exe, x.dll, x.func)
            hints[(x.dll, x.func)] = {"tested": h.tested, "predicted_nonzero_nominal": h.predicted_nonzero_nominal,
                                     "confidence": h.confidence, "suggested_first_strategy": h.preferred_strategy_first(),
                                     "call_sites": h.call_sites}
            if h.tested:
                print(f"[indice] {x.dll}.{x.func} : testée={h.tested} non-nul-nominal={h.predicted_nonzero_nominal} "
                      f"confiance={h.confidence} -> essayer d'abord {h.preferred_strategy_first() or 'A (défaut)'}")
        except Exception as exc:  # l'indice est facultatif
            hints[(x.dll, x.func)] = {"error": f"{type(exc).__name__}"}
    cap = build_capsule(
        identity=ident, wine_version=wine_ver, polyre_range=">=0.4, <0.5",
        contracts=[{"kind": c.kind, "dll": c.dll, "source": c.catalogue_source, "sha256": c.sha256, "mode": c.mode} for c in plan.declarative],
        shims=[{"dll": x.dll, "func": x.func, "strategy": x.strategy, "api_class": x.api_class, "returns": x.returns,
                "last_error": x.last_error, "tainted": x.tainted, "note": x.note, "hint": hints.get((x.dll, x.func))} for x in plan.shims],
        scenarios=[], results={}, runs=0, machines=1,
        status="experimental", synthetic=args.synthetic)
    caps_name = f"{ident['product'].split()[0].lower()}-{s.sha256[:12]}.capsule.toml"
    tmp = Path(args.commons) / caps_name
    cap.dump(tmp)
    lr = lint_capsule(load_capsule(tmp))
    if not lr.ok:
        print("[fix] capsule REFUSÉE par le linter de sûreté :", lr.errors)
        tmp.unlink(missing_ok=True)
        return 1
    stored = commons.put(tmp)
    print(f"[fix] capsule émise (experimental, non vérifiée à l'exécution) et ajoutée au communs : {stored}")
    print("[fix] note : capsule non validée — à passer par l'expérience A/B/C (run_experiment) avant tout usage.")
    return 0


def _wine_ok() -> bool:
    try:
        from .wine_runner import find_wine
        find_wine()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
