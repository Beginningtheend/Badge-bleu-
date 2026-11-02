"""Pré-réponse par analyse des branches (idée n°3 du carnet d'idéation).

Un programme ne distingue que ce qu'il teste. En lisant le code JUSTE APRÈS un appel à une fonction
manquante, on peut deviner quelle valeur de retour garde le programme sur son chemin nominal : on repère
le test de la valeur de retour (``test eax,eax`` / ``cmp``) et le saut conditionnel qui suit, puis on
regarde laquelle des deux branches ressemble à une sortie d'erreur précoce (``mov eax, <code>`` ; ``ret``).

Le résultat n'est qu'un INDICE : il PRIORISE les candidats de :mod:`bdflab.speculate`. L'oracle d'effet
reste juge ; si l'indice se trompe, la recherche essaie quand même les autres réponses. L'analyse
désassemble avec Capstone ; elle est best-effort (x86-64, exécutables non liés/boundés).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

RET_REGS = {"eax", "rax", "al", "ax"}


@dataclass
class BranchHint:
    dll: str
    func: str
    call_sites: int
    tested: bool                      # la valeur de retour est-elle testée puis branchée ?
    predicted_nonzero_nominal: bool | None   # True : une valeur non nulle garde le chemin nominal ;
                                             # False : zéro le garde ; None : indéterminé
    confidence: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def preferred_strategy_first(self) -> str | None:
        """Quelle stratégie essayer en premier : 'S' si non-nul garde le nominal, 'A' si zéro le garde."""
        if self.predicted_nonzero_nominal is True:
            return "S"
        if self.predicted_nonzero_nominal is False:
            return "A"
        return None


def _looks_like_error_exit(insns, start, window=14) -> bool:
    """Heuristique : chemin d'ERREUR précoce = charge un PETIT CODE constant (1..255) dans un registre
    (eax, ou esi/edi/ebx… qui alimente un épilogue commun) puis quitte (jmp/ret), SANS y faire couler le
    résultat d'un appel (``mov reg, eax`` après un ``call``). Le chemin nominal, lui, poursuit un calcul
    (appel dont le résultat est conservé)."""
    small_imm = False
    result_flow = False
    seen_call = False
    for ins in insns[start:start + window]:
        if ins.mnemonic == "call":
            seen_call = True
            continue
        if ins.mnemonic == "mov" and ins.operands and len(ins.operands) == 2 and ins.operands[0].type == CS_OP_REG:
            if ins.operands[1].type == CS_OP_IMM and 1 <= ins.operands[1].imm <= 255:
                small_imm = True
            elif ins.operands[1].type == CS_OP_REG and ins.op_str.endswith(", eax") and seen_call:
                result_flow = True
        if ins.mnemonic in ("jmp", "ret"):
            return small_imm and not result_flow
    return small_imm and not result_flow


def analyze(exe_path, dll: str, func: str) -> BranchHint:
    pe = pefile.PE(str(exe_path))
    base = pe.OPTIONAL_HEADER.ImageBase
    dll_l = dll.lower() if dll.lower().endswith(".dll") else dll.lower() + ".dll"
    slot_rva = None
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            if (entry.dll or b"").decode().lower() != dll_l:
                continue
            for imp in entry.imports:
                if imp.name and imp.name.decode() == func:
                    slot_rva = imp.address - base
    if slot_rva is None:
        return BranchHint(dll, func, 0, False, None, "aucun (import introuvable)")

    text = next((s for s in pe.sections if b".text" in s.Name), None)
    if not text:
        return BranchHint(dll, func, 0, False, None, "aucun (.text absent)")
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    insns = list(md.disasm(text.get_data(), base + text.VirtualAddress))

    call_idx = []
    for i, ins in enumerate(insns):
        if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == CS_OP_MEM:
            m = ins.operands[0].mem
            # call qword ptr [rip + disp]
            if m.base != 0 and (ins.address + ins.size + m.disp) - base == slot_rva:
                call_idx.append(i)

    if not call_idx:
        return BranchHint(dll, func, 0, False, None, "aucun site d'appel direct trouvé (appel indirect ?)")

    evidence: list[str] = []
    predicted = None
    confidence = "basse"
    tested = False
    for ci in call_idx[:3]:
        # suivre le registre qui reçoit eax, jusqu'au premier test/cmp + jcc
        tracked = "eax"
        clobbered = False   # eax est écrasé par tout appel ultérieur : on ne re-suit plus après
        window = insns[ci + 1:ci + 24]
        for j, ins in enumerate(window):
            if ins.mnemonic == "call":
                clobbered = True
            if (not clobbered and ins.mnemonic == "mov" and ins.op_str.endswith(", eax")
                    and ins.op_str.split(",")[0].strip() not in RET_REGS):
                tracked = ins.op_str.split(",")[0].strip()
                continue
            if ins.mnemonic in ("test", "cmp") and tracked in ins.op_str:
                tested = True
                evidence.append(f"{ins.address:x}: {ins.mnemonic} {ins.op_str}")
                # le saut conditionnel suivant
                for k in range(j + 1, min(j + 4, len(window))):
                    ji = window[k]
                    if ji.mnemonic.startswith("j") and ji.mnemonic != "jmp" and ji.operands and ji.operands[0].type == CS_OP_IMM:
                        evidence.append(f"{ji.address:x}: {ji.mnemonic} {ji.op_str}")
                        tgt = ji.operands[0].imm
                        # index de la cible du saut dans insns
                        tgt_idx = next((x for x, a in enumerate(insns) if a.address == tgt), None)
                        fall_err = _looks_like_error_exit(window, k + 1)
                        jump_err = _looks_like_error_exit(insns, tgt_idx) if tgt_idx is not None else False
                        # jz/je : saut pris si ZÉRO. jnz/jne : saut pris si NON nul.
                        zero_takes_jump = ji.mnemonic in ("je", "jz")
                        if jump_err and not fall_err:
                            # la cible du saut est l'ERREUR : la valeur qui PREND le saut mène à l'erreur.
                            # je/jz : zéro saute -> zéro = erreur -> NON-NUL nominal (True) ;
                            # jne/jnz : non-nul saute -> non-nul = erreur -> zéro nominal (False).
                            predicted = zero_takes_jump
                            confidence = "moyenne"
                        elif fall_err and not jump_err:
                            # la suite (non-saut) est l'ERREUR : la valeur qui NE saute PAS mène à l'erreur.
                            predicted = (not zero_takes_jump)
                            confidence = "moyenne"
                        else:
                            # aucune branche ne ressemble à une sortie d'erreur : le programme gère les deux
                            # valeurs (repli documenté) -> pas de préférence ; la recherche gardera A d'abord.
                            predicted = None
                            confidence = "basse"
                            evidence.append("les deux branches semblent viables (repli géré) : pas de préférence")
                        break
                break
    return BranchHint(dll, func, len(call_idx), tested, predicted, confidence, evidence)
