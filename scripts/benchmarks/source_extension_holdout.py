"""Evaluator-only alias/propagation and safe counterexamples; no model feedback."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.adapters.artifacts import ArtifactStore
from app.adapters.codeql.custom import validate_fixtures
from app.core.db import engine
from app.persistence.knowledge_models import RuleVersion
from app.services.context_materials import digest, save_json
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/benchmarks/v7-source-extension-additional-20261004"
DATA = {
    "positive": {
        "files": {
            "alias.py": "import events_api as external\ndef forward(value):\n    return value\ndef consume():\n    return eval(forward(external.fetch_event()))\n",
            "direct.py": "from events_api import fetch_event as read_event\ndef consume():\n    raw = read_event()\n    return eval(raw)\n",
        },
        "expected": [{"file": "alias.py", "line": 5}, {"file": "direct.py", "line": 4}],
    },
    "negative": {
        "files": {
            "numeric.py": "import events_api\ndef consume():\n    return eval(str(int(events_api.fetch_event())))\n",
            "constant.py": "import events_api\ndef consume():\n    unused = events_api.fetch_event()\n    return eval('1+2')\n",
            "trusted.py": "import events_api\ndef consume():\n    return eval(events_api.trusted_config())\n",
            "shadowed.py": "import events_api\nclass Local:\n    def fetch_event(self):\n        return '1+2'\ndef consume():\n    events_api = Local()\n    return eval(events_api.fetch_event())\n",
        },
        "expected": [],
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prior",
        type=Path,
        default=ROOT
        / "artifacts/benchmarks/v7-external-source-fixed-20261004/report.json",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    prior = json.loads(args.prior.read_text())
    rows = [r for r in prior["rows"] if r["status"] == "draft"]
    if len(rows) != 3 or output.exists():
        raise RuntimeError("Requires three completed rules and a new evaluation output")
    save_json(
        output / "dataset.json",
        {
            "hash": digest(DATA),
            "fixtures": DATA,
            "meaning": "Hand-authored evaluator cases, not a public benchmark. All three rules were completed before this evaluator run; results never enter generation.",
        },
    )
    results = []
    for row in rows:
        with Session(engine) as db:
            rule = db.get(RuleVersion, UUID(row["rule_id"]))
        pack = (
            ArtifactStore().directory(str(rule.stage_id))
            / f"draft-{rule.validation['attempts'] - 1}"
        )
        outcome = validate_fixtures(output / str(rule.id), pack, "python", DATA)
        results.append(
            {"rule_id": str(rule.id), "query_hash": rule.query_hash, "result": outcome}
        )
        save_json(
            output / "report.json", {"dataset_hash": digest(DATA), "records": results}
        )
        print(
            json.dumps(
                {
                    "rule_id": str(rule.id),
                    "status": outcome["status"],
                    "tests": {k: v["actual"] for k, v in outcome["tests"].items()},
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
