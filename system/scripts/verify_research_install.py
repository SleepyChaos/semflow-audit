"""Verify independent wheels offline using RECORD-verified locked dependencies.

This deliberately does not claim a fresh package-index download. The complete
runtime dependency closure is copied into an otherwise empty venv after checking
installed versions against uv.lock and bytes against each wheel's RECORD.
"""

import argparse
import base64
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib
from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PACKAGES = ("semflow_contracts", "semflow_research", "semflow_research_cli")


def command(arguments, **kwargs):
    return subprocess.run(
        arguments, check=True, capture_output=True, text=True, **kwargs
    ).stdout.strip()


def locked_versions(lock: Path):
    """Select the running interpreter's fork; never collapse distinct lock versions."""
    versions = {}
    for row in tomllib.loads(lock.read_text())["package"]:
        markers = row.get("resolution-markers", ())
        if markers and not any(Marker(value).evaluate() for value in markers):
            continue
        name = canonicalize_name(row["name"])
        if name in versions and versions[name] != row["version"]:
            raise ValueError(f"Ambiguous lock versions for current interpreter: {name}")
        versions[name] = row["version"]
    return versions


def locked_distributions(lock: Path, dependency_sources=()):
    versions = locked_versions(lock)
    cache = Path.home() / ".cache/uv/archive-v0"
    paths = (
        [str(path) for path in cache.iterdir() if path.is_dir()]
        if cache.is_dir()
        else []
    )
    candidates = tuple(
        importlib.metadata.distributions(path=[*paths, *map(str, dependency_sources)])
    )

    def resolve(name):
        try:
            installed = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed is not None and installed.version == versions[name]:
            return installed
        for distribution in candidates:
            if (
                canonicalize_name(distribution.metadata["Name"]) == name
                and distribution.version == versions[name]
            ):
                return distribution
        raise ValueError(
            f"Locked dependency not available in installed RECORDs or local wheel cache: {name}=={versions[name]}"
        )

    return resolve


def runtime_dependencies(system: Path, resolve):
    workspace = {canonicalize_name(name) for name in PACKAGES}
    pending = []
    for package in ("contracts", "research", "research_cli"):
        project = tomllib.loads((system / package / "pyproject.toml").read_text())[
            "project"
        ]
        pending.extend(Requirement(value) for value in project["dependencies"])
    resolved, processed = set(), set()
    while pending:
        dependency = pending.pop()
        name = canonicalize_name(dependency.name)
        if (
            name in workspace
            or (name, frozenset(dependency.extras)) in processed
            or (dependency.marker and not dependency.marker.evaluate({"extra": ""}))
        ):
            continue
        distribution = resolve(name)
        if dependency.specifier and distribution.version not in dependency.specifier:
            raise ValueError(f"Installed dependency fails declared requirement: {name}")
        resolved.add(name)
        processed.add((name, frozenset(dependency.extras)))
        for value in distribution.requires or ():
            requirement = Requirement(value)
            if requirement.marker is None or any(
                requirement.marker.evaluate({"extra": extra})
                for extra in {"", *dependency.extras}
            ):
                requirement.marker = None
                pending.append(requirement)
    return sorted(resolved)


def copy_locked_dependencies(target: Path, lock: Path, dependency_sources=()) -> dict:
    versions = locked_versions(lock)
    copied = {}
    resolve = locked_distributions(lock, dependency_sources)
    for name in runtime_dependencies(lock.parent, resolve):
        distribution = resolve(name)
        if distribution.version != versions[name]:
            raise ValueError(f"Installed dependency differs from lock: {name}")
        for entry in distribution.files or ():
            if entry.suffix == ".pyc":
                continue
            destination = target / entry
            if not destination.resolve().is_relative_to(target.resolve()):
                # Third-party console scripts are not invoked by this check.
                # Do not copy shebangs pointing back into the original venv.
                if destination.resolve().parent == target.parents[2] / "bin":
                    continue
                raise ValueError(
                    f"Distribution path escaped the isolated environment: {name}"
                )
            source = distribution.locate_file(entry)
            data = source.read_bytes()
            if entry.hash:
                actual = (
                    base64.urlsafe_b64encode(
                        hashlib.new(entry.hash.mode, data).digest()
                    )
                    .rstrip(b"=")
                    .decode()
                )
                if actual != entry.hash.value:
                    raise ValueError(
                        f"Installed RECORD digest mismatch: {name}/{entry}"
                    )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        copied[name] = distribution.version
    return copied


def verify(
    system: Path, wheels: Path, environment: Path, dependency_sources=()
) -> dict:
    if environment.exists():
        raise ValueError("Use a new, empty verification environment")
    command([sys.executable, "-m", "venv", "--without-pip", str(environment)])
    python = environment / "bin/python"
    target = Path(
        command(
            [
                str(python),
                "-I",
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ]
        )
    )
    dependencies = copy_locked_dependencies(
        target, system / "uv.lock", dependency_sources
    )
    wheel_paths = [str(wheels / f"{name}-0.1.0-py3-none-any.whl") for name in PACKAGES]
    command(
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(python),
            *wheel_paths,
        ]
    )
    command(["uv", "pip", "check", "--python", str(python)])
    script = """
import importlib.metadata as m, importlib.util, json, os, pkgutil
os.environ['HAYSTACK_TELEMETRY_ENABLED'] = 'false'
for name in ['app', 'fastapi', 'celery', 'sqlmodel', 'pydantic_settings']:
    assert importlib.util.find_spec(name) is None, name
from semflow_research.public import discovery, repair, rules
import semflow_research
for module in pkgutil.walk_packages(semflow_research.__path__, 'semflow_research.'):
    __import__(module.name)
from semflow_cli.main import main
assert main(['schema', '--kind', 'run']) == 0
"""
    command([str(python), "-I", "-c", script], cwd=environment)
    capabilities = json.loads(
        command(
            [str(environment / "bin/semflow-research"), "capabilities"], cwd=environment
        )
    )
    return {
        "scope": "three_local_wheels_and_record_verified_locked_dependencies",
        "platform_packages_present": False,
        "dependencies": dependencies,
        "wheel_sha256": {
            Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in wheel_paths
        },
        "capabilities": capabilities,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheels", required=True, type=Path)
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument(
        "--dependency-source",
        action="append",
        type=Path,
        default=[],
        help="Read-only installed distribution metadata location; only exact locked versions with verified RECORD bytes are copied",
    )
    args = parser.parse_args()
    report = verify(
        Path(__file__).resolve().parents[1],
        args.wheels.resolve(),
        args.environment.resolve(),
        tuple(path.resolve() for path in args.dependency_source),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
