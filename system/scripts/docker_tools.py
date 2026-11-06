"""Install verified Linux scan tools into case-sensitive Docker volumes."""

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

CODEQL_VERSION = "2.23.5"
ASSETS = {
    "codeql-linux64.zip": (
        f"https://github.com/github/codeql-cli-binaries/releases/download/v{CODEQL_VERSION}/codeql-linux64.zip",
        "43d94a2ad35523d0c41623fe9c5396242a8b842d7bd2a00044d153d9be3bfa58",
    ),
    "python311.tar.gz": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/20251209/"
        "cpython-3.11.14%2B20251209-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
        "b2c6b82b870994664fab6edfc0a3d0c5a1f39af1a9808db2b2d0ffbd97d47382",
    ),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verified_asset(name: str) -> Path:
    url, expected = ASSETS[name]
    path = Path("/downloads") / name
    if path.is_file() and digest(path) == expected:
        return path
    temporary = path.with_suffix(path.suffix + ".part")
    for attempt in range(3):
        try:
            print(f"Downloading official {name} (attempt {attempt + 1})", flush=True)
            with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output, 1024 * 1024)
            if digest(temporary) != expected:
                raise RuntimeError(f"SHA-256 mismatch for {name}")
            temporary.replace(path)
            return path
        except (OSError, RuntimeError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Download did not complete")


def install_codeql(archive: Path, destination: Path) -> None:
    receipt = destination / ".semflow-version"
    if receipt.is_file() and receipt.read_text() == CODEQL_VERSION:
        return
    with ZipFile(archive) as bundle:
        for item in bundle.infolist():
            relative = Path(item.filename).relative_to("codeql")
            target = destination / relative
            if not target.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe tool archive path")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                link = bundle.read(item).decode()
                if not (target.parent / link).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe tool archive link")
                if not target.is_symlink():
                    target.symlink_to(link)
            else:
                with bundle.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod((mode & 0o777) or 0o644)
    receipt.write_text(CODEQL_VERSION)


def install_python(archive: Path, destination: Path) -> None:
    receipt = destination / ".semflow-version"
    if receipt.is_file() and receipt.read_text() == "3.11.14":
        return
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(archive) as bundle:
            bundle.extractall(temporary, filter="data")
        # Both paths are Linux filesystems; do not copy these names onto NTFS.
        shutil.copytree(Path(temporary) / "python", destination, dirs_exist_ok=True, symlinks=True)
    receipt.write_text("3.11.14")


def main() -> None:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise SystemExit("This optional tool installer requires Linux amd64 containers")
    Path("/downloads").mkdir(parents=True, exist_ok=True)
    install_codeql(verified_asset("codeql-linux64.zip"), Path("/opt/codeql"))
    install_python(verified_asset("python311.tar.gz"), Path("/opt/python311"))
    environment = {
        key: value for key, value in os.environ.items()
        if key in {"PATH", "HOME", "LANG", "TMPDIR"}
    }
    environment["PATH"] = "/opt/codeql:" + environment.get("PATH", "")
    for command in (
        ["/opt/codeql/codeql", "version", "--format=json"],
        ["/opt/python311/bin/python3.11", "--version"],
        ["/opt/codeql/codeql", "pack", "download", "--dir", "/app/artifacts/packs",
         "codeql/python-queries@1.6.0", "codeql/javascript-queries@1.4.0"],
        ["python", "/app/system/scripts/install_query_sources.py"],
    ):
        subprocess.run(command, env=environment, check=True)
    print("Linux scan tools and fixed query packs are ready.", flush=True)


if __name__ == "__main__":
    main()
