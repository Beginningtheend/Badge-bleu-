"""Communs de capsules adressé par CONTENU (idée n°6 du carnet d'idéation).

« Glisser l'exe » = chercher sa capsule par empreinte. Clé primaire : sha256 de l'exécutable (exact).
Clé secondaire : imphash (version voisine → capsule « dégradée », stratégie A uniquement, jamais S).
Différence avec protonfixes (indexé par ID de jeu Steam) : ici l'index est l'EMPREINTE du binaire, et
chaque capsule est typée par la table de sûreté et porte un statut. Rien n'est appliqué silencieusement :
une capsule `experimental` est signalée comme telle.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .capsule import load_capsule, lint_capsule


@dataclass
class Lookup:
    match: str              # "exact" | "degraded" | "none"
    capsule_path: str | None
    status: str | None      # experimental | validated | rejected
    note: str


class CapsuleCommons:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self.index = json.loads(self.index_path.read_text()) if self.index_path.exists() else {"by_sha256": {}, "by_imphash": {}}

    def _save(self) -> None:
        self.index_path.write_text(json.dumps(self.index, indent=1, ensure_ascii=False))

    def put(self, capsule_path: Path) -> str:
        obj = load_capsule(capsule_path)
        ident = obj.get("identity", {})
        sha = ident.get("sha256", "")
        imphash = ident.get("imphash", "")
        dest = self.root / Path(capsule_path).name
        if Path(capsule_path).resolve() != dest.resolve():
            shutil.copy2(capsule_path, dest)
        rel = dest.name
        if sha:
            self.index["by_sha256"][sha] = rel
        if imphash:
            self.index["by_imphash"].setdefault(imphash, [])
            if rel not in self.index["by_imphash"][imphash]:
                self.index["by_imphash"][imphash].append(rel)
        self._save()
        return str(dest)

    def get(self, sha256: str, imphash: str = "") -> Lookup:
        rel = self.index.get("by_sha256", {}).get(sha256)
        if rel and (self.root / rel).exists():
            obj = load_capsule(self.root / rel)
            return Lookup("exact", str(self.root / rel), obj.get("meta", {}).get("status"),
                          "capsule trouvée par sha256 (identité exacte)")
        if imphash:
            for rel in self.index.get("by_imphash", {}).get(imphash, []):
                if (self.root / rel).exists():
                    return Lookup("degraded", str(self.root / rel), load_capsule(self.root / rel).get("meta", {}).get("status"),
                                  "capsule d'une version voisine (imphash) : mode DÉGRADÉ, stratégie A uniquement")
        return Lookup("none", None, None, "aucune capsule connue pour cette empreinte")
