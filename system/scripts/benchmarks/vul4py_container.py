"""Invoke frozen official Vul4Py tools inside an isolated evaluator container."""

import argparse
import json
import sys
from pathlib import Path

from scripts.benchmarks.vul4py_prepare import load_module, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--mode", choices=["setup", "tests"], required=True)
    parser.add_argument("--targets", nargs="+", default=["vulnerable", "fixed"])
    parser.add_argument(
        "--test-dependencies", choices=["project-declared", "project-compatible"]
    )
    args = parser.parse_args()
    official = load_module(Path("/official/scripts/vul4py.py"), "official_oracle")
    original_python = official.ensure_python_interpreter

    def interpreter(tools, version):
        # Exact minor-version match only; other versions retain official provisioning.
        if version == f"{sys.version_info.major}.{sys.version_info.minor}":
            return Path(sys.executable)
        return original_python(tools, version)

    official.ensure_python_interpreter = interpreter
    case = args.case
    meta = official.load_meta(case)
    tools, logs = Path("/tools"), case / "logs"
    logs.mkdir(exist_ok=True)
    results = {}
    if args.test_dependencies == "project-compatible":
        from scripts.benchmarks.vul4py_compatibility import constraints

        profile = json.loads(Path("/environment-profile.json").read_text())
        constraints(case, profile)
    for target in args.targets:
        source = case / target
        if args.mode == "setup":
            if args.test_dependencies == "project-compatible" and profile.get(
                "projects", {}
            ).get(case.name, {}).get("restore_git_history"):
                from scripts.benchmarks.vul4py_git_fixture import restore

                restore(
                    case,
                    source,
                    target,
                    meta,
                    logs,
                    restore_submodules=profile["projects"][case.name].get(
                        "restore_submodules", False
                    ),
                )
            official.create_and_install(tools, source, meta, logs)
            if args.test_dependencies:
                from scripts.benchmarks.vul4py_dependencies import install

                install(official, tools, source, logs)
            results[target] = {"setup": "succeeded"}
        else:
            effective_meta = meta
            if args.test_dependencies == "project-compatible":
                from scripts.benchmarks.vul4py_compatibility import collection_meta

                effective_meta = collection_meta(source, meta, logs)
            results[target] = {
                "functional_rc": official.run_functional(
                    tools, source, effective_meta, logs, timeout=300
                ),
                "exploit_rc": official.run_exploit_for_target(
                    tools, case / "fixed", source, target, meta, logs, timeout=300
                ),
            }
    save(case / f"{args.mode}-result.json", results)


if __name__ == "__main__":
    main()
