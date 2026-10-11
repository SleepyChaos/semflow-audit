"""Additional opaque-framework test: grounded model extension vs official baseline."""

import hashlib
import json
import logging
import time
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session
from app.adapters.ai.policy import policy_snapshot
from app.adapters.codeql.custom import compile_query, fixed_dependencies, prepare_query
from app.adapters.codeql.rule_spec import detector_template
from app.adapters.retrieval.knowledge import import_knowledge
from app.core.db import engine
from app.jobs.stages import execute_stage
from app.persistence.stage_models import StageRun
from app.persistence.knowledge_models import RuleVersion
from sqlmodel import select
from scripts.benchmarks.rule_ablation import initialize
from scripts.benchmarks.rule_ablation_oracles import build_databases, evaluate

ROOT = Path(__file__).resolve().parents[3]
ARMS = {
    "H_free_grounded": {
        "routing": True,
        "full_feedback": True,
        "framework_knowledge": True,
    },
    "I_spec_grounded": {
        "routing": True,
        "full_feedback": True,
        "framework_knowledge": True,
        "framework_spec": True,
    },
    "J_spec_no_domain": {
        "routing": True,
        "full_feedback": True,
        "framework_spec": True,
    },
}


def fixture(index):
    module = f"auditbridge{index}"
    member = ["evaluate", "run_code", "execute"][index]
    argument = index
    prefix = (
        "from flask import Flask, request\nimport "
        + module
        + '\napp = Flask(__name__)\n@app.get("/")\ndef endpoint():\n'
    )

    def call(values):
        return f"    return str({module}.{member}(" + ",".join(values) + ")) # target\n"

    positive = call(['"metadata"'] * argument + ['request.args["payload"]'])
    constant = call(['"metadata"'] * argument + ['"1+1"'])
    wrong = call(
        (['request.args["payload"]'] + ['"metadata"'] * (argument - 1) + ['"1+1"'])
        if argument
        else ['str(int(request.args["payload"]))']
    )
    data = {
        "id": f"opaque-python-exec-{index}",
        "language": "python",
        "operation": "eval",
        "purpose": "vulnerability_detector",
        "fixtures": {
            "positive": {
                "files": {"case.py": prefix + positive},
                "expected": [
                    {"file": "case.py", "line": len((prefix + positive).splitlines())}
                ],
            },
            "negative": {
                "files": {
                    "constant.py": prefix + constant,
                    "wrong_argument.py": prefix + wrong,
                },
                "expected": [],
            },
        },
    }
    # Text of APIs enters the private KB, code/examples/labels stay evaluator-only.
    doc = f"Python opaque execution API {module}.{member}. Calls imported module {module}, member {member}. Argument index {argument} (zero-based) is evaluated as Python source code by the external service. All preceding arguments are harmless metadata, not executable. Extend CodeInjection Sink using ApiGraphs. Constants at the executable argument are safe; user data in metadata alone is not code injection. Implementation is external and unavailable to static analysis."
    data["hash"] = hashlib.sha256(
        json.dumps(data["fixtures"], sort_keys=True).encode()
    ).hexdigest()
    return data, doc


def main():
    logging.basicConfig(level=logging.CRITICAL)
    output = ROOT / "artifacts/benchmarks" / ("framework-ablation-" + str(uuid4()))
    output.mkdir()
    audits, corpus_hash = initialize(output)
    with Session(engine) as db:
        from app.persistence.audit_models import AuditRun

        owner = db.get(AuditRun, UUID(audits["python"])).owner_id
    cases = []
    for index in range(3):
        data, doc = fixture(index)
        cases.append(data)
        import_knowledge(
            owner,
            f"Python eval auditbridge{index} API",
            f"framework-api:auditbridge{index}",
            "python",
            doc,
            {
                "api_version": fixed_dependencies("python")["codeql/python-all"][
                    "version"
                ],
                "trust": "synthetic_framework_documentation",
                "license": "CC0",
            },
        )
    policy = policy_snapshot()
    policy["thinking_mode"] = "disabled"
    policy["budgets"]["rule"] = 6000
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "arms": ARMS,
                "policy": policy,
                "prompt_version": "4",
                "cases": [
                    {k: v for k, v in case.items() if k != "fixtures"} for case in cases
                ],
                "corpus_hash": corpus_hash,
                "scope": "3 synthetic imported APIs with opaque implementation and different sink argument positions; not real CVE discovery",
            },
            indent=2,
        )
    )
    print("OUTPUT=" + str(output), flush=True)
    records = []
    for number in range(1, 4):
        for case in cases:
            for arm, flags in ARMS.items():
                requirement = f"Generate a Python eval/code-injection detector for opaque framework auditbridge{cases.index(case)} using its retrieved API documentation. The baseline cannot model this external API. Only the argument documented as executable is a sink; constants and data solely in metadata are safe. Explain coverage gap and add small draft regression fixtures."
                with Session(engine) as db:
                    stage = StageRun(
                        audit_id=UUID(audits["python"]),
                        kind="rule",
                        inputs={
                            "requirement": requirement,
                            "purpose": "vulnerability_detector",
                            "strategy": "new_query",
                        },
                        prompt_version="4",
                        model_config_snapshot={**policy, "rule_experiment": flags},
                    )
                    db.add(stage)
                    db.commit()
                    db.refresh(stage)
                    identifier = stage.id
                start = time.perf_counter()
                execute_stage.run(str(identifier))
                with Session(engine) as db:
                    stage = db.get(StageRun, identifier)
                    rules = db.exec(
                        select(RuleVersion).where(RuleVersion.stage_id == identifier)
                    ).all()
                    records.append(
                        {
                            "arm": arm,
                            "case": case["id"],
                            "round": number,
                            "generation_seconds": time.perf_counter() - start,
                            "stage": stage.model_dump(mode="json"),
                            "rules": [r.model_dump(mode="json") for r in rules],
                        }
                    )
                (output / "report.json").write_text(
                    json.dumps({"records": records}, ensure_ascii=False, indent=2)
                )
                print(arm, case["id"], number, stage.status, flush=True)
    baseline = []
    for case in cases:
        directory = output / "holdouts" / case["id"]
        directory.mkdir(parents=True)
        (directory / "dataset.json").write_text(json.dumps(case, indent=2))
        build_databases(directory, case)
        pack = directory / "baseline"
        query, provenance = detector_template("python", "eval")
        prepare_query(pack, "python", query, {}, fixed_dependencies("python"))
        compile_query(pack, pack / "compile.log")
        baseline.append(
            {
                "case": case["id"],
                "oracle": evaluate(directory, pack, case, pack / "oracle"),
                "provenance": provenance,
            }
        )
        for row in records:
            if row["case"] != case["id"]:
                continue
            if not row["rules"]:
                row["oracle"] = {"status": "not_generated"}
                continue
            rule = row["rules"][0]
            pack = output / "evaluation" / row["stage"]["id"]
            prepare_query(
                pack, "python", rule["query"], rule["modules"], rule["dependencies"]
            )
            try:
                row["oracle"] = evaluate(directory, pack, case, pack / "oracle")
            except Exception as exc:
                row["oracle_error"] = {"message": str(exc), "type": type(exc).__name__}
            print(
                "ORACLE",
                row["arm"],
                row["case"],
                row.get("oracle", {}).get("status", "error"),
                flush=True,
            )
        (output / "report.json").write_text(
            json.dumps(
                {"records": records, "baseline": baseline}, ensure_ascii=False, indent=2
            )
        )
    print("REPORT=" + str(output / "report.json"), flush=True)


if __name__ == "__main__":
    main()
