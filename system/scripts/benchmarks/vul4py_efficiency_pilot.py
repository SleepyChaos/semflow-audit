"""Fixed small development experiment, with cached v3 baseline, never full replay."""

import argparse
import json
import time
from pathlib import Path

from scripts.benchmarks.mechanical_pipeline import exclusive, save

PROJECTS = ["case-001", "case-004"]
REPAIRS = ["CVE-2023-6681", "CVE-2024-6866", "CVE-2025-59420"]


def summarize(origin, root):
    projects, repairs = [], []
    for identity in PROJECTS:
        entry = {"project_id": identity}
        for label, directory in (("v3", origin), ("v4", root)):
            folder = directory / "e2e/system" / identity
            if not (folder / "result.json").exists():
                continue
            result = json.loads((folder / "result.json").read_text())
            scout = json.loads((folder / "scout.json").read_text())
            stage = scout["stage"]
            coverage = stage["result"]["coverage"]
            entry[label] = {
                "status": result["status"],
                "joint_pass": result["joint_pass"],
                "confirmed": result["confirmed_candidates"],
                "unresolved": result["unresolved_candidates"],
                "scout_seconds": scout["wall_seconds"],
                "usage": stage["usage"],
                "planned_windows": coverage["planned_windows"],
                "inspected_windows": coverage["inspected_windows"],
                "coverage_status": coverage["status"],
            }
        projects.append(entry)
    for identity in REPAIRS:
        entry = {"vuln_id": identity}
        for label, directory in (("v3", origin), ("v4", root)):
            path = directory / "runs" / identity / "result.json"
            if path.exists():
                row = json.loads(path.read_text())
                entry[label] = {
                    k: row.get(k)
                    for k in (
                        "status",
                        "reason",
                        "stage_id",
                        "usage",
                        "joint_pass",
                        "functional_pass",
                        "security_pass",
                    )
                }
        repairs.append(entry)
    summary = {
        "regime": "small development efficiency comparison; v3 historical baseline; no significance or full generalization claim",
        "projects": projects,
        "repairs": repairs,
    }
    save(root / "pilot-summary.json", summary)
    return summary


def run(origin, root, mode="all"):
    from scripts.benchmarks.realvuln_run import verify_implementation
    from scripts.benchmarks.vul4py_e2e import run_project
    from scripts.benchmarks.vul4py_repair import run as run_repair

    with exclusive(root / "pilot.lock"):
        verify_implementation(root)
        protocol = json.loads((root / "pilot-protocol.json").read_text())
        projects = PROJECTS if mode == "all" else []
        if protocol["projects"] != projects or protocol["repairs"] != REPAIRS:
            raise RuntimeError("Pilot selection changed")
        config = json.loads((root / "repair-config.json").read_text())
        for identity in REPAIRS:
            run_repair(identity, root, config["policy"], config["image_id"])
            summarize(origin, root)
            verify_implementation(root)
        config = json.loads((root / "e2e/config.json").read_text())
        mapping = {
            r["project_id"]: r["vuln_id"]
            for r in json.loads((root / "e2e/evaluator-only-mapping.json").read_text())[
                "records"
            ]
        }
        inputs = json.loads((root / "e2e/inputs.json").read_text())["records"]
        for identity in projects:
            row = next(r for r in inputs if r["id"] == identity)
            result = run_project(row, mapping[identity], config, root)
            summarize(origin, root)
            if result.get("provider_interrupted"):
                raise RuntimeError("Provider interrupted; do not replay paid work")
        save(
            root / "pilot-finished.json",
            {
                "status": "completed",
                "finished_unix": time.time(),
                "projects": len(projects),
                "repairs": 3,
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["all", "repairs"], default="all")
    args = parser.parse_args()
    run(args.origin.resolve(), args.output.resolve(), args.mode)


if __name__ == "__main__":
    main()
