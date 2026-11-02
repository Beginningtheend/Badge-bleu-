"""Chargeur de fixtures (réponses d'API distillées sur le Windows de l'utilisateur), formats 0.1 et 0.2.

Format (fixtures/README.md) : {"schema": "bdflab-fixtures/0.2", "source": "...", "entries": {"<dll>.<Func>": {...}}}.
Chaque entrée : returns, last_error, deterministic, et (0.2) observations = [{input, returns, last_error}, ...].
Le chargeur normalise les clés (« KERNEL32.dll.Foo » -> « kernel32.Foo »), reporte ``source`` dans chaque
entrée (provenance exigée par le linter de capsule : ``fixture_source``) et vérifie la structure. Il ne décide
RIEN : c'est ``speculate.fixture_stability`` (règle du professeur : ≥ 2 entrées distinctes, même sortie) puis
l'oracle d'effet qui tranchent. Aucune trace brute, aucun code ni donnée Windows : uniquement des scalaires.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMAS = {"bdflab-fixtures/0.1", "bdflab-fixtures/0.2"}


def norm_key(key: str) -> str:
    """« KERNEL32.dll.Foo » / « kernel32.Foo » -> « kernel32.Foo » (DLL en minuscules, fonction intacte)."""
    dll, _, func = key.rpartition(".")
    if dll.lower().endswith(".dll"):
        dll = dll[:-4]
    if not dll or not func:
        raise ValueError(f"clé de fixture invalide : {key!r} (attendu « dll.Fonction »)")
    return f"{dll.lower()}.{func}"


def validate_entry(key: str, entry: dict) -> list[str]:
    """Problèmes de structure d'une entrée (liste vide = conforme)."""
    issues: list[str] = []
    if not isinstance(entry, dict):
        return [f"{key} : entrée non-objet"]
    if "returns" not in entry and not entry.get("observations"):
        issues.append(f"{key} : ni « returns » ni « observations »")
    for i, o in enumerate(entry.get("observations") or []):
        if not isinstance(o, dict) or "input" not in o or "returns" not in o:
            issues.append(f"{key} : observation {i} sans « input »/« returns »")
    for k in ("returns", "last_error"):
        v = entry.get(k)
        if v is not None and not isinstance(v, int):
            issues.append(f"{key} : « {k} » doit être un entier (scalaire), pas {type(v).__name__}")
    return issues


def load_fixtures(path: Path | str) -> dict[str, dict]:
    """Charge un fichier de fixtures et renvoie {« dll.Func » : entrée + source}. Lève ValueError si non conforme."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = obj.get("schema")
    if schema not in SCHEMAS:
        raise ValueError(f"schéma de fixtures inconnu : {schema!r} (attendu : {sorted(SCHEMAS)})")
    source = obj.get("source") or "windows-utilisateur (source non renseignée)"
    out: dict[str, dict] = {}
    problems: list[str] = []
    for key, entry in (obj.get("entries") or {}).items():
        problems += validate_entry(key, entry)
        e = dict(entry)
        e.setdefault("source", source)
        out[norm_key(key)] = e
    if problems:
        raise ValueError("fixtures non conformes : " + " ; ".join(problems))
    return out


def fixture_for(fixtures: dict[str, dict], dll: str, func: str) -> dict | None:
    """Entrée pour (dll, func), ou None."""
    return fixtures.get(norm_key(f"{dll}.{func}"))
