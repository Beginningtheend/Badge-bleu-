"""Tests de l'importateur de capture (Procmon CSV et journal Wine) vers recette de capsule."""
from pathlib import Path
from bdflab.capture_import import parse_procmon_csv, parse_wine_log, build_recipe

REPO = Path(__file__).resolve().parent.parent


def test_procmon_csv_recipe_floor_and_candidates():
    cap = parse_procmon_csv(REPO / "fixtures/procmon-exemple.csv")
    r = build_recipe(cap, r"C:\Apps\bdfedit", ["s1"], "procmon-csv")
    names = {x["dll"] for x in r.native_dll_candidates}
    assert "propsys" in names and "version" in names
    assert {x["dll"] for x in r.floor_refused} >= {"ntdll", "kernel32", "kernelbase"}
    assert any("TimeZoneInformation" in k for k in r.registry_keys)
    assert any(f.lower().endswith("segoeui.ttf") for f in r.fonts)
    assert any(f.lower().endswith("doc.txt") for f in r.app_files)


def test_wine_log_recipe(tmp_path):
    log = tmp_path / "w.log"
    log.write_text(
        '0024:trace:loaddll:build_module Loaded L"C:\\\\windows\\\\system32\\\\ntdll.dll" at 00006FFFFFC00000: builtin\n'
        '0024:trace:loaddll:build_module Loaded L"C:\\\\windows\\\\system32\\\\propsys.dll" at 00006FFFFF000000: builtin\n'
        '0024:trace:loaddll:build_module Loaded L"C:\\\\bdf\\\\bdfedit.exe" at 0000000140000000: native\n'
        '0024:Call ADVAPI32.RegOpenKeyExW(80000002,7ffe L"Software\\\\Test\\\\Key",00000000,00020019,7ffe) ret=140001\n')
    cap = parse_wine_log(log)
    r = build_recipe(cap, r"C:\bdf", ["s1"], "wine-log")
    assert {x["dll"] for x in r.native_dll_candidates} == {"propsys"}
    assert {x["dll"] for x in r.floor_refused} == {"ntdll"}
    assert any(k.endswith("Key") for k in r.registry_keys)
    assert r.stats["native_candidates"] == 1 and r.stats["floor_seen"] == 1


def test_priority_absent_then_stubby(tmp_path):
    # une DLL absente de Wine doit passer avant une DLL à stubs, elle-même avant une DLL sans stub
    class FakeDB:
        def dll_known(self, d): return d != "mfc140u"
        def stubs_of(self, d): return ["X"] * 5 if d == "propsys" else []
    cap = {"dll_paths": {r"C:\Windows\System32\version.dll": 1, r"C:\Windows\System32\propsys.dll": 1,
                         r"C:\Windows\System32\mfc140u.dll": 1}, "reg_keys": {}, "file_paths": {}}
    r = build_recipe(cap, r"C:\App", [], "test", FakeDB())
    assert [x["dll"] for x in r.native_dll_candidates] == ["mfc140u", "propsys", "version"]
