"""Tests du parseur de fichiers .spec de Wine et de la base de connaissances."""
import io
from pathlib import Path
import pytest
from bdflab.knowledge.build_wine_db import parse_spec, parse_arch_flags, scan_c_file


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p


def test_parse_spec_stub_and_stdcall(tmp_path):
    spec = write(tmp_path, "x.spec", """
@ stdcall FooImplemented(long ptr)
@ stub FooStub
123 stdcall -ordinal OrdFunc(long)
# @ stub FooCommented
@ stdcall -import FwdFunc(ptr) kernelbase.FwdFunc
""".strip())
    out = parse_spec(spec)
    assert out["FooImplemented"]["t"] == "stdcall"
    assert out["FooImplemented"]["a"] == ["long", "ptr"]
    assert out["FooStub"]["t"] == "stub"
    assert out["FooCommented"]["t"] == "absent"
    assert out["FwdFunc"].get("f") == "kernelbase.FwdFunc" or out["FwdFunc"].get("fl")


def test_parse_arch_flags():
    assert parse_arch_flags(["-i386"]) == {"i386"}
    assert parse_arch_flags(["-arch=win64"]) == {"x86_64", "arm64", "arm64ec"}
    r = parse_arch_flags(["-arch=!i386"])
    assert "i386" not in r and "x86_64" in r


def test_scan_c_semistub(tmp_path):
    c = write(tmp_path, "y.c", """
HANDLE WINAPI CreateFileTransactedW(LPCWSTR n, DWORD a)
{
    FIXME("(%s): semi-stub\\n", n);
    return CreateFileW(n, a);
}
BOOL WINAPI FullyDone(void)
{
    TRACE("ok\\n");
    return TRUE;
}
INT WINAPI NotImpl(void)
{
    FIXME("not implemented\\n");
    return 0;
}
""".strip())
    out = scan_c_file(c)
    assert out["CreateFileTransactedW"]["kind"] == "semi-stub"
    assert "FullyDone" not in out
    assert out["NotImpl"]["kind"] == "fixme-unimplemented"
