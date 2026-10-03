"""Explicit test doubles only: deterministic responses do not measure model quality."""

from pathlib import Path
from app.contracts.stages import ReviewResponse, RepairResponse, RuleResponse


class ScriptedModel:
    model = "test-fixture-not-production"

    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.seen = []
        self.review_calls = 0

    def generate(self, purpose, payload, schema):
        self.usage["calls"] += 1
        self.seen.append((purpose, payload))
        if purpose == "review":
            self.review_calls += 1
            if self.review_calls == 1:
                result = {
                    "action": "tool",
                    "tool": {
                        "name": "read_source",
                        "arguments": {"file": "app.py", "start_line": 1, "end_line": 1},
                    },
                }
            elif self.review_calls == 2:
                result = {
                    "action": "tool",
                    "tool": {
                        "name": "knowledge",
                        "arguments": {"query": "Python eval CodeQL 动态执行"},
                    },
                }
            else:
                result = {
                    "action": "final",
                    "findings": [
                        {
                            "candidate_id": payload["targets"][0]["candidate_id"],
                            "title": "Untrusted dynamic execution",
                            "description": "Input can reach eval without a protection boundary.",
                            "assessment": "supported",
                            "evidence_ids": [
                                row["id"]
                                for row in payload["evidence"]
                                if row["kind"] == "code"
                            ],
                        }
                    ],
                    "summary": "Evidence supports manual review; no automatic confirmation.",
                }
            return schema.model_validate(result)
        if purpose == "repair":
            contents = "\n".join(payload["allowed_files"].values())
            old = (
                "eval(expression)"
                if "eval(expression)" in contents
                else "eval(input())"
            )
            new = "int(expression)" if old == "eval(expression)" else "int(input())"
            return schema.model_validate(
                {
                    "changes": [
                        {
                            "file": "app.py",
                            "old_text": old,
                            "new_text": new,
                            "reason": "Limit the intended numeric conversion and remove arbitrary evaluation.",
                        }
                    ],
                    "summary": "Replace dynamic execution with explicit integer conversion for the test sample.",
                }
            )
        if purpose == "rule":
            query = (
                (
                    Path(__file__).resolve().parents[1]
                    / "docs/knowledge/python-codeql.md"
                )
                .read_text()
                .split("```ql\n")[1]
                .split("```")[0]
            )
            return schema.model_validate(
                {
                    "title": "Dynamic eval review anchor",
                    "strategy": "new_query",
                    "coverage_analysis": "Baseline dataflow catches injection; this broad anchor query is for manual review and is not a precision claim.",
                    "query": query,
                    "knowledge_ids": [payload["knowledge"][0]["id"]],
                    "positive": {
                        "files": {"positive.py": "value = eval(input())\n"},
                        "expected": [{"file": "positive.py", "line": 1}],
                    },
                    "negative": {
                        "files": {"negative.py": "value = int(input())\n"},
                        "expected": [],
                    },
                }
            )
        raise AssertionError(purpose)
