"""Tests du catalogue « Windows de l'utilisateur » (sans vraies DLL Windows : fichiers de substitution)."""
from pathlib import Path
from bdflab import userwindows as uw


def test_floor_rule():
    for d in ("ntdll.dll", "win32u", "kernelbase.dll", "user32", "gdi32.dll", "ntoskrnl.exe", "something.sys"):
        assert uw.is_floor(d), d
    for d in ("propsys.dll", "dwmapi", "msxml6.dll", "d3dx9_43.dll"):
        assert not uw.is_floor(d), d


def test_inventory_and_proposal(tmp_path):
    s32 = tmp_path / "System32"; s32.mkdir()
    # substituts : n'importe quel binaire (on hache seulement)
    src = Path(__file__).resolve().parent.parent / "testapps/bdfedit/bin/bdfpdf.dll"
    (s32 / "propsys.dll").write_bytes(src.read_bytes())
    (s32 / "ntdll.dll").write_bytes(b"MZ-fake")
    m = uw.inventory(s32, tmp_path / "manifest.json", source_label="test")
    assert "propsys.dll" in m["entries"] and not m["entries"]["propsys.dll"]["floor"]
    assert m["entries"]["ntdll.dll"]["floor"] is True
    assert "INTERDITE" in m["redistribution"]
    # proposition : propsys acceptable, ntdll refusée (plancher), inconnue -> None
    p = uw.propose_native_override("propsys", m)
    assert p and p["kind"] == "dll-native-user-windows" and p["sha256"] == m["entries"]["propsys.dll"]["sha256"]
    r = uw.propose_native_override("ntdll", m)
    assert r and r.get("refused") is True
    assert uw.propose_native_override("nonexistent", m) is None
