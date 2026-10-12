import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.domain.audit import AuditError


def location_data(location: dict, artifacts: list[dict]) -> dict:
    physical = location.get("physicalLocation", {})
    artifact = physical.get("artifactLocation", {})
    if "uri" not in artifact and isinstance(artifact.get("index"), int):
        index = artifact["index"]
        if 0 <= index < len(artifacts):
            artifact = artifacts[index].get("location", {})
    uri = unquote(artifact.get("uri", ""))
    if uri.startswith("file:"):
        uri = urlparse(uri).path
    region = physical.get("region", {})
    return {
        "file": uri,
        "line": region.get("startLine", 0),
        "column": region.get("startColumn", 0),
        "end_line": region.get("endLine", region.get("startLine", 0)),
    }


def parse_sarif(path: Path, snapshot_hash: str) -> list[dict]:
    try:
        document = json.loads(path.read_text())
        if (
            document.get("version") != "2.1.0"
            or not isinstance(document.get("runs"), list)
            or not document["runs"]
        ):
            raise ValueError("Invalid SARIF structure")
        findings = []
        for run_index, run in enumerate(document["runs"]):
            for invocation in run.get("invocations", []):
                if invocation.get("executionSuccessful") is False:
                    raise ValueError("SARIF reports unsuccessful execution")
            results = run.get("results", [])
            if not isinstance(results, list):
                raise ValueError("Invalid SARIF results")
            artifacts = run.get("artifacts", [])
            rules = {
                rule["id"]: rule
                for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
            }
            for index, result in enumerate(results):
                if (
                    not isinstance(result, dict)
                    or not result.get("ruleId")
                    or not result.get("locations")
                ):
                    raise ValueError("SARIF result has no rule or code location")
                locations = [
                    location_data(item, artifacts) for item in result["locations"]
                ]
                rule = rules.get(result["ruleId"], {})
                properties = rule.get("properties", {})
                identity = json.dumps(
                    [snapshot_hash, run_index, index, result["ruleId"], locations],
                    sort_keys=True,
                )
                flows = []
                for flow in result.get("codeFlows", []):
                    for thread in flow.get("threadFlows", []):
                        flows.append(
                            [
                                location_data(step.get("location", {}), artifacts)
                                for step in thread.get("locations", [])
                            ]
                        )
                findings.append(
                    {
                        "id": hashlib.sha256(identity.encode()).hexdigest(),
                        "rule": result["ruleId"],
                        "message": result.get("message", {}).get("text", ""),
                        "level": result.get("level", "warning"),
                        "security_severity": properties.get("security-severity"),
                        "tags": properties.get("tags", []),
                        "locations": locations,
                        "code_flows": flows,
                        "assessment": "unreviewed",
                        "rule_version": run.get("properties", {}).get(
                            "audit_rule_version"
                        ),
                        "origin": "custom_rule"
                        if run.get("properties", {}).get("audit_rule_version")
                        else "baseline",
                    }
                )
        return findings
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise AuditError("SARIF 解析失败；原始产物保留，不输出零漏洞结论") from exc
