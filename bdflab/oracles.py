"""Oracles d'effet : vérifier qu'un scénario a produit un effet réel, pas seulement un code de succès.

Principe (mission §5, rapport « Risques ») : ne jamais conclure qu'un programme a réussi parce qu'il
démarre ou renvoie 0. On vérifie l'effet par un moyen indépendant du programme testé (lecture du
fichier produit, empreinte, relecture par un outil tiers). Un succès annoncé sans fichier présent et
correct est classé « faux succès ».
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class OracleResult:
    name: str
    passed: bool
    detail: str
    kind: str = "effect"         # "effect" | "startup" | "independent"
    false_success: bool = False  # succès annoncé par le programme mais effet absent/incorrect

    def to_dict(self) -> dict:
        return asdict(self)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def oracle_process_stable(exit_code: int | None, timed_out: bool, min_ok: bool = True) -> OracleResult:
    """Démarrage/fin stable : le programme s'est terminé sans être tué ni planter."""
    if timed_out:
        return OracleResult("process_stable", False, "délai dépassé, processus tué", kind="startup")
    if exit_code is None:
        return OracleResult("process_stable", False, "pas de code de sortie", kind="startup")
    ok = exit_code in (0, 2) if min_ok else exit_code == 0  # 2 = dégradation propre documentée
    return OracleResult("process_stable", ok, f"code de sortie {exit_code}", kind="startup")


def oracle_file_exists(path: Path) -> OracleResult:
    p = Path(path)
    return OracleResult("file_exists", p.is_file(), f"{p} {'présent' if p.is_file() else 'ABSENT'}")


def oracle_file_contains(path: Path, needle: str, announced_saved: bool = True) -> OracleResult:
    """Le fichier produit contient bien le texte attendu (effet de la modification + enregistrement)."""
    p = Path(path)
    if not p.is_file():
        return OracleResult("file_contains", False, f"{p} absent alors que l'enregistrement était annoncé={announced_saved}",
                            false_success=announced_saved)
    text = p.read_text(encoding="utf-8", errors="replace")
    ok = needle in text
    return OracleResult("file_contains", ok, f"motif {'présent' if ok else 'ABSENT'} : {needle!r}",
                        false_success=announced_saved and not ok)


def oracle_file_changed(path: Path, before_sha: str | None, announced_saved: bool = True) -> OracleResult:
    """Le contenu a réellement changé par rapport à l'état de référence."""
    p = Path(path)
    if not p.is_file():
        return OracleResult("file_changed", False, f"{p} absent", false_success=announced_saved)
    now = sha256(p)
    ok = (before_sha is None) or (now != before_sha)
    return OracleResult("file_changed", ok, f"sha256 {now[:16]} ({'modifié' if ok else 'INCHANGÉ'})",
                        false_success=announced_saved and not ok)


def oracle_reopen_consistent(path: Path, expected_needle: str) -> OracleResult:
    """Après fermeture/réouverture (relecture indépendante), le contenu attendu est présent."""
    p = Path(path)
    if not p.is_file():
        return OracleResult("reopen_consistent", False, f"{p} absent à la réouverture")
    text = p.read_text(encoding="utf-8", errors="replace")
    ok = expected_needle in text
    return OracleResult("reopen_consistent", ok, f"relecture : motif {'présent' if ok else 'ABSENT'}", kind="independent")


def oracle_pdf_text(path: Path, expected_needle: str) -> OracleResult:
    """Vérification par un outil INDÉPENDANT (pdftotext de poppler) que le PDF produit contient le texte.

    Un PDF écrit par le programme testé n'est « bon » que si un lecteur tiers y retrouve le contenu.
    """
    p = Path(path)
    if not p.is_file():
        return OracleResult("pdf_text", False, f"{p} absent", kind="independent", false_success=True)
    tool = shutil.which("pdftotext")
    if not tool:
        # repli : vérifier au moins la signature PDF et la présence du texte brut (flux non compressé)
        data = p.read_bytes()
        ok = data.startswith(b"%PDF-") and expected_needle.encode() in data
        return OracleResult("pdf_text", ok, f"pdftotext absent ; vérif. brute {'OK' if ok else 'échec'}", kind="independent")
    try:
        r = subprocess.run([tool, "-q", str(p), "-"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return OracleResult("pdf_text", False, "pdftotext: délai dépassé", kind="independent")
    ok = expected_needle in r.stdout
    return OracleResult("pdf_text", ok, f"pdftotext: {'texte retrouvé' if ok else 'texte ABSENT'} (extrait {r.stdout[:40]!r})",
                        kind="independent", false_success=not ok and p.stat().st_size > 0)


def oracle_timestamp_plausible(path: Path, announced_saved: bool = True) -> OracleResult:
    """Le pied de page « saved-at AAAA-MM-JJ hh:mm:ss » porte une date plausible (année 2020-2100, champs valides).

    Attrape une implémentation qui annonce le succès en laissant le tampon de sortie à zéro
    (horodatage « 0000-00-00 ») : effet annoncé mais contenu corrompu = faux succès.
    """
    import re
    p = Path(path)
    if not p.is_file():
        return OracleResult("timestamp_plausible", False, f"{p} absent", kind="independent", false_success=announced_saved)
    text = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"saved-at (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", text)
    if not m:
        return OracleResult("timestamp_plausible", False, "pied de page saved-at absent", kind="independent", false_success=announced_saved)
    y, mo, d, h, mi, se = (int(x) for x in m.groups())
    ok = 2020 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31 and h < 24 and mi < 60 and se < 60
    return OracleResult("timestamp_plausible", ok, f"saved-at {m.group(0)[9:]} ({'plausible' if ok else 'INVALIDE'})",
                        kind="independent", false_success=announced_saved and not ok)


@dataclass
class ScenarioOutcome:
    scenario: str
    oracles: list[OracleResult]
    app_announced_success: bool

    @property
    def passed(self) -> bool:
        return all(o.passed for o in self.oracles) and len(self.oracles) > 0

    @property
    def false_success(self) -> bool:
        """Le programme a annoncé un succès mais au moins un oracle d'effet le contredit."""
        return self.app_announced_success and any(o.false_success for o in self.oracles)

    def to_dict(self) -> dict:
        return {"scenario": self.scenario, "passed": self.passed, "false_success": self.false_success,
                "app_announced_success": self.app_announced_success, "oracles": [o.to_dict() for o in self.oracles]}
