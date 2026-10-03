"""Run an explicitly separated, corrected JS negative control, preserving baseline."""

import json
from uuid import UUID

import live_model as bench


def main():
    reports = sorted(
        (bench.ROOT / "artifacts/benchmarks").glob("live-model-*/report.json")
    )
    if len(reports) != 1:
        raise SystemExit("Select a single baseline before running follow-up")
    path = reports[0]
    bench.OUTPUT = path.parent
    bench.REPORT = json.loads(path.read_text())
    if len(bench.REPORT["stages"]) != 27:
        raise SystemExit("Baseline must finish exactly 27 stages first")
    bench.OWNER = UUID(bench.REPORT["owner"])
    source = bench.OUTPUT / "corrected-js-negative"
    source.mkdir()
    (source / "shadowed_json.js").write_text(
        'const express=require("express");const app=express();function eval(value){return value;}app.get("/",(req,res)=>res.json({value:eval(req.query.value)}));\n'
    )
    audit_id, seconds = bench.new_audit(
        bench.OWNER, source, "corrected-js-negative", "javascript"
    )
    bench.REPORT["audits"].append(
        {
            "id": str(audit_id),
            "language": "javascript",
            "static_seconds": seconds,
            "phase": "corrected-negative-followup",
        }
    )
    bench.save()
    for number in range(1, 4):
        bench.run_stage(
            audit_id,
            "review",
            {
                "paths": ["shadowed_json.js"],
                "discover": True,
                "max_steps": 8,
                "max_context_chars": 60000,
            },
            {
                "case": "shadowed_json.js",
                "round": number,
                "expected_vulnerable": False,
                "phase": "corrected-negative-followup",
            },
        )


if __name__ == "__main__":
    main()
