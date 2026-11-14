"""Explicit CodeQL project-query substitute shared by CLI/Web boundary gates."""

import json

from semflow_research.adapters.codeql.sarif import parse_sarif


def install_replay(monkeypatch, phases):
    def run_query(database, pack, output, log, snapshot_hash, *, _kernel):
        phases.append("project_replay")
        assert (database / "src.zip").is_file()
        assert (
            _kernel.source_root.joinpath("app.py").read_text()
            == "value = eval(input())\n"
        )
        query = (pack / "generated.ql").read_text()
        import re

        identifier = re.search(r"@id\s+(\S+)", query)[1]
        output.write_text(
            json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [
                        {
                            "tool": {
                                "driver": {
                                    "rules": [
                                        {
                                            "id": identifier,
                                            "properties": {
                                                "tags": ["external/cwe/cwe-095"]
                                            },
                                        }
                                    ]
                                }
                            },
                            "invocations": [{"executionSuccessful": True}],
                            "results": [
                                {
                                    "ruleId": identifier,
                                    "message": {
                                        "text": "Explicit project replay substitute"
                                    },
                                    "locations": [
                                        {
                                            "physicalLocation": {
                                                "artifactLocation": {"uri": "app.py"},
                                                "region": {"startLine": 1},
                                            }
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            )
        )
        log.write_text(
            "Explicit CodeQL project query substitute; source and database metadata are real fixture bytes"
        )
        return parse_sarif(output, snapshot_hash)

    monkeypatch.setattr(
        "semflow_research.rules.rule_project_validation.run_query", run_query
    )
