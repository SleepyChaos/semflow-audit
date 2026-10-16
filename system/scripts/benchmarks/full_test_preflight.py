"""Validate installed packs before extracting any full-source test project."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from app.core.audit_config import audit_settings
    from scripts.benchmarks.realvuln_run import verify_implementation

    root = args.output.resolve()
    verify_implementation(root)
    if not shutil.which(audit_settings.CODEQL_BIN):
        raise RuntimeError("CodeQL executable unavailable")
    config = json.loads((root / "e2e/config.json").read_text())
    for language, pack in config["packs"].items():
        name, version = pack["pack"].split("@")
        suite = audit_settings.CODEQL_PACK_PATH / name / version / pack["suite"]
        if not suite.is_file():
            raise RuntimeError(f"Frozen {language} query suite unavailable: {suite}")
    print(
        "Preflight passed: frozen implementation and query suite installed", flush=True
    )


if __name__ == "__main__":
    main()
