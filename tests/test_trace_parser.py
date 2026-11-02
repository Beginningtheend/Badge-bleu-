"""Tests du parseur de traces Wine."""
from pathlib import Path
from bdflab.trace_parser import parse_wine_log, parse_app_stdout


def test_detect_unimplemented_and_seh(tmp_path):
    log = tmp_path / "w.log"
    log.write_text(
        "2716.1:002c:Call KERNEL32.GetSystemTime(7ffe) ret=140001\n"
        "2716.1:002c:Ret  KERNEL32.GetSystemTime() retval=0 ret=140001\n"
        "002c:trace:seh:dispatch_exception code=80000100 (EXCEPTION_WINE_STUB) flags=1 addr=6FFFFFC68218\n"
        "wine: Call from 006FFFFFC68218 to unimplemented function KERNEL32.dll.SystemTimeToTzSpecificLocalTimeEx, aborting\n")
    ts = parse_wine_log(log)
    assert ts.relay_calls == 1
    assert ts.fatal is True
    assert len(ts.stub_calls) == 1
    assert ts.stub_calls[0].func == "SystemTimeToTzSpecificLocalTimeEx"
    assert any(e["code"] == "80000100" for e in ts.exceptions)


def test_detect_missing_library_and_import_failure(tmp_path):
    log = tmp_path / "w.log"
    log.write_text(
        '002c:warn:module:import_dll Library mfc140u.dll (which is needed by L"Z:\\\\app.exe") not found\n'
        '002c:err:module:import_dll Importing dlls for L"Z:\\\\app.exe" failed, status c0000135\n')
    ts = parse_wine_log(log)
    assert ts.missing_libraries and ts.missing_libraries[0]["lib"] == "mfc140u.dll"
    assert ts.import_failures and ts.fatal is True


def test_detect_noimpl_import(tmp_path):
    log = tmp_path / "w.log"
    log.write_text('011c:warn:module:import_dll No implementation for KERNEL32.dll.Heap32First '
                   'imported from L"Z:\\\\app.exe", setting to 00007FFFFE460000\n')
    ts = parse_wine_log(log)
    assert ts.missing_impl_imports and ts.missing_impl_imports[0]["func"] == "Heap32First"


def test_parse_app_stdout():
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("BDFEDIT|OPENED|path=doc.txt|bytes=16\nBDFEDIT|SAVED|path=doc.txt|lines=4\nnoise\n")
        name = f.name
    ev = parse_app_stdout(name)
    os.unlink(name)
    assert [e["event"] for e in ev] == ["OPENED", "SAVED"]
    assert ev[0]["bytes"] == "16"
