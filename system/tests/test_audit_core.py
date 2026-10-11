import json
import stat
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

import pytest
from app.adapters.archive import extract_snapshot
from app.adapters.codeql.sarif import parse_sarif
from app.domain.audit import AuditError
from app.workflows.scanning import build_scan_graph


def archive(path, entries):
    with ZipFile(path, "w") as bundle:
        for name, content in entries:
            bundle.writestr(name, content)


@pytest.mark.parametrize(
    "name", ["../outside.py", "/outside.py", "dir\\outside.py", "C:/outside.py"]
)
def test_archive_rejects_escaping_paths(tmp_path, name):
    archive(tmp_path / "sample.zip", [(name, "print(1)")])
    with pytest.raises(AuditError):
        extract_snapshot(tmp_path / "sample.zip", tmp_path / "source", "python")
    assert not (tmp_path / "source").exists()


def test_archive_rejects_symlink(tmp_path):
    info = ZipInfo("app.py")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive(tmp_path / "sample.zip", [(info, "/etc/passwd")])
    with pytest.raises(AuditError):
        extract_snapshot(tmp_path / "sample.zip", tmp_path / "source", "python")


def test_snapshot_hash_and_coverage(tmp_path):
    archive(
        tmp_path / "sample.zip",
        [
            ("app.py", "print(1)"),
            ("app.js", "console.log(1)"),
            (".git/config", "ignored"),
        ],
    )
    first, coverage = extract_snapshot(
        tmp_path / "sample.zip", tmp_path / "source", "python"
    )
    second, _ = extract_snapshot(tmp_path / "sample.zip", tmp_path / "other", "python")
    assert first == second
    assert coverage["unscanned_languages"] == ["javascript"]
    assert not (tmp_path / "source/.git").exists()


def document(results):
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "rules": [
                            {
                                "id": "py/test",
                                "properties": {"security-severity": "8.0"},
                            }
                        ]
                    }
                },
                "results": results,
            }
        ],
    }


def result(file):
    return {
        "ruleId": "py/test",
        "message": {"text": "test"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": file},
                    "region": {"startLine": 3},
                }
            }
        ],
    }


def test_same_rule_has_distinct_finding_identities(tmp_path):
    p = tmp_path / "results.sarif"
    first = result("a.py")
    first["codeFlows"] = [
        {"threadFlows": [{"locations": [{"location": result("b.py")["locations"][0]}]}]}
    ]
    p.write_text(json.dumps(document([first, result("c.py")])))
    findings = parse_sarif(p, "snapshot")
    assert len({f["id"] for f in findings}) == 2
    assert findings[0]["code_flows"][0][0]["file"] == "b.py"
    assert findings[0]["security_severity"] == "8.0"


@pytest.mark.parametrize("content", ["broken", "{}", '{"version":"2.1.0","runs":[]}'])
def test_invalid_sarif_is_failure_not_empty_success(tmp_path, content):
    p = tmp_path / "bad.sarif"
    p.write_text(content)
    with pytest.raises(AuditError):
        parse_sarif(p, "snapshot")


def test_successful_zero_results_is_supported(tmp_path):
    p = tmp_path / "empty.sarif"
    p.write_text(json.dumps(document([])))
    assert parse_sarif(p, "snapshot") == []


class Service:
    def __init__(self, directory, fail=False):
        self.calls = []
        self.fail = fail
        self.artifacts = SimpleNamespace(directory=lambda _: directory)

    def create_database(self, run_id):
        self.calls.append(("database", run_id))

    def scan(self, run_id):
        self.calls.append(("scan", run_id))
        if self.fail:
            raise AuditError("scan failed")

    def save_findings(self, run_id):
        self.calls.append(("evidence", run_id))


def test_graph_executes_real_stage_order(tmp_path):
    service = Service(tmp_path)
    state = build_scan_graph(service).invoke({"run_id": "run"})
    assert service.calls == [("database", "run"), ("scan", "run"), ("evidence", "run")]
    assert state["findings_saved"]
    records = [
        json.loads(p.read_text()) for p in (tmp_path / "node-timings").glob("*.json")
    ]
    assert len(records) == 3 and all(r["status"] == "completed" for r in records)


def test_graph_failure_prevents_publishing_findings(tmp_path):
    service = Service(tmp_path, fail=True)
    with pytest.raises(AuditError):
        build_scan_graph(service).invoke({"run_id": "run"})
    assert [step for step, _ in service.calls] == ["database", "scan"]
    records = [
        json.loads(p.read_text()) for p in (tmp_path / "node-timings").glob("*.json")
    ]
    assert len(records) == 2 and any(r["status"] == "failed" for r in records)
