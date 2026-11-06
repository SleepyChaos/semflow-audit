"""Archive safety and Linux filesystem requirements of the optional installer."""

import importlib.util
import platform
import stat
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

spec = importlib.util.spec_from_file_location(
    "docker_tools", Path(__file__).resolve().parents[1] / "scripts/docker_tools.py"
)
assert spec is not None and spec.loader is not None
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def test_tool_archive_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "tools.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("codeql/../../escaped", "must not be written")
    destination = tmp_path / "runtime"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="Unsafe tool archive path"):
        tools.install_codeql(archive, destination)
    assert not (tmp_path / "escaped").exists()
    assert not (destination / ".semflow-version").exists()


def test_tool_archive_rejects_external_symlink(tmp_path):
    archive = tmp_path / "tools.zip"
    link = ZipInfo("codeql/external")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(archive, "w") as bundle:
        bundle.writestr(link, "../../outside")
    destination = tmp_path / "runtime"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="Unsafe tool archive link"):
        tools.install_codeql(archive, destination)
    assert not (destination / "external").is_symlink()


@pytest.mark.skipif(platform.system() != "Linux", reason="Installer targets Linux volumes")
def test_linux_volume_keeps_case_distinct_files_and_executable_mode(tmp_path):
    archive = tmp_path / "tools.zip"
    executable = ZipInfo("codeql/codeql")
    executable.external_attr = (stat.S_IFREG | 0o755) << 16
    with ZipFile(archive, "w") as bundle:
        bundle.writestr(executable, "#!/bin/sh\nexit 0\n")
        bundle.writestr("codeql/data/Name", "upper")
        bundle.writestr("codeql/data/name", "lower")
    destination = tmp_path / "runtime"
    destination.mkdir()
    tools.install_codeql(archive, destination)
    assert (destination / "data/Name").read_text() == "upper"
    assert (destination / "data/name").read_text() == "lower"
    assert (destination / "codeql").stat().st_mode & stat.S_IXUSR
    assert (destination / ".semflow-version").read_text() == tools.CODEQL_VERSION


def test_installer_rejects_native_windows_before_download(monkeypatch):
    monkeypatch.setattr(tools.platform, "system", lambda: "Windows")
    with pytest.raises(SystemExit, match="Linux amd64"):
        tools.main()
