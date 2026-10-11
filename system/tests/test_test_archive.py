"""Provenance regressions; run with unittest without loading DB fixtures."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.test_archive.catalog import build_catalog, normalize_reference
from scripts.test_archive.identity import configuration, evidence
from scripts.test_archive.improvements import classify
from scripts.test_archive.relocation import file_map, resolve
from scripts.test_archive.store import freeze, verify


class TestResultArchive(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path

    def prepare_results(self):
        self.write(
            "docs/research/example-results.md",
            "# Result\n`artifacts/research/test/run-a/`\n",
        )
        self.write(
            "artifacts/research/test/run-a/config.json",
            {"review_version": "8", "implementation_hashes": {"app.py": "a" * 64}},
        )
        self.write("artifacts/research/test/run-a/summary.json", {"passed": 3})
        self.write(
            "artifacts/research/test/run-b/config.json",
            {"review_version": "9", "implementation_hashes": {"app.py": "b" * 64}},
        )
        self.write("artifacts/research/test/run-c/summary.json", {"passed": 1})

    def test_same_run_receipt_never_borrows_sibling_or_current_version(self):
        self.prepare_results()
        rows = {r["path"]: r for r in build_catalog(self.root)}
        a = rows["artifacts/research/test/run-a/summary.json"]
        b = rows["artifacts/research/test/run-b/config.json"]
        c = rows["artifacts/research/test/run-c/summary.json"]
        self.assertEqual(
            a["version_receipt_ids"],
            [rows["artifacts/research/test/run-a/config.json"]["result_id"]],
        )
        self.assertNotIn(b["test_version_ids"][0], a["test_version_ids"])
        self.assertEqual(c["version_status"], "unresolved")
        self.assertEqual(c["test_version_ids"], [])

    def test_changed_result_keeps_locator_but_changes_content_hash(self):
        self.prepare_results()
        first = build_catalog(self.root)
        path = "artifacts/research/test/run-a/summary.json"
        self.write(path, {"passed": 4})
        before = next(r for r in first if r["path"] == path)
        after = next(r for r in build_catalog(self.root) if r["path"] == path)
        self.assertEqual(before["result_id"], after["result_id"])
        self.assertNotEqual(before["sha256"], after["sha256"])

    def test_invalid_json_and_missing_references_remain_visible(self):
        self.write("artifacts/research/failure/config.json", "{invalid")
        self.write(
            "docs/research/failure-results.md",
            "`artifacts/research/missing/report.json`",
        )
        rows = build_catalog(self.root)
        broken = next(r for r in rows if r["path"].endswith("config.json"))
        report = next(r for r in rows if r["role"] == "report")
        self.assertTrue(broken["parse_status"].startswith("failed:"))
        self.assertEqual(broken["version_status"], "unresolved")
        self.assertEqual(
            report["missing_references"], ["artifacts/research/missing/report.json"]
        )

    def test_secret_fields_and_secret_symlinks_are_not_catalogued(self):
        self.write(
            "artifacts/research/a/config.json",
            {
                "model": "test-model",
                "api_key": "secret",
                "request": {"authorization": "secret"},
            },
        )
        secret = self.write(".env", "AI_API_KEY=secret\nAI_MODEL=test-model\n")
        (self.root / "artifacts/research/a/identity.json").symlink_to(secret)
        rows = build_catalog(self.root)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("secret", json.dumps(rows))
        self.assertEqual(
            evidence({"prompt_versions": {"review": "9"}})["declared"],
            {"prompt_versions.review": "9"},
        )

    def test_configuration_selects_only_allowlisted_values(self):
        self.write(
            "system/backend/app/core/audit_config.py",
            "class Settings:\n    AI_MODEL: str = 'default'\n",
        )
        self.write(
            ".env", "AI_API_KEY=secret\nPOSTGRES_PASSWORD=secret\nAI_MODEL=test-model\n"
        )
        with patch.dict("os.environ", {}, clear=True):
            result = configuration(self.root)
        self.assertEqual(result["values"], {"AI_MODEL": "test-model"})
        self.assertNotIn("secret", json.dumps(result))

    def test_old_absolute_paths_rebase_but_traversal_is_rejected(self):
        self.assertEqual(
            normalize_reference("/old/ai-code-audit/artifacts/a/report.json"),
            "artifacts/a/report.json",
        )
        self.assertIsNone(normalize_reference("artifacts/../../.env"))

    def test_archive_checks_originals_and_copies_and_refuses_overwrite(self):
        self.prepare_results()
        self.write(
            "system/scripts/test_archive/improvement-versions.json",
            {"improvements": []},
        )
        self.write("system/backend/app/main.py", "value = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Archive Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            cwd=self.root,
            check=True,
        )
        with patch(
            "scripts.test_archive.store.environment",
            return_value={"secret_content_archived": False},
        ):
            result = freeze(self.root, "fixture-v1")
            self.assertEqual(result["verification"], "passed")
            with self.assertRaises(FileExistsError):
                freeze(self.root, "fixture-v1")
        original = "artifacts/research/test/run-a/summary.json"
        self.write(original, {"passed": 0})
        self.assertIn(
            "original_result_missing_or_changed:" + original,
            verify(self.root, "fixture-v1"),
        )
        self.assertEqual(verify(self.root, "fixture-v1", originals=False), [])
        # Old registries and copied receipts stay byte-for-byte identical when
        # their original reports move to the new five-directory layout.
        old = "docs/research/example-results.md"
        new = "benchmarks/reports/example-results.md"
        destination = self.root / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        (self.root / old).rename(destination)
        self.write(
            "design/repository-file-map.json",
            {"files": [{"old_path": old, "path": new}]},
        )
        self.assertEqual(resolve(self.root, old, file_map(self.root)), destination)
        self.assertNotIn(
            "original_result_missing_or_changed:" + old,
            verify(self.root, "fixture-v1"),
        )
        self.assertEqual(verify(self.root, "fixture-v1", originals=False), [])
        copy = ".local-workspace/test-archives/fixture-v1/receipts/" + original
        self.write(copy, {"passed": 99})
        self.assertIn(
            "archived_file_missing_or_changed:" + copy,
            verify(self.root, "fixture-v1", originals=False),
        )

    def test_relocated_receipt_rejects_traversal_in_both_locations(self):
        for relative, mapping in (
            ("../outside", {}),
            ("/outside", {}),
            ("old", {"old": "../outside"}),
            ("old", {"old": "/outside"}),
        ):
            with (
                self.subTest(relative=relative, mapping=mapping),
                self.assertRaises(ValueError),
            ):
                resolve(self.root, relative, mapping)

    def test_improvement_grouping_uses_specific_version_not_date(self):
        groups = {
            "improvements": [
                {"id": "CURRENT", "path_prefixes": ["runs/"]},
                {"id": "EXPERIMENT", "path_prefixes": ["runs/revision-02/"]},
            ]
        }
        rows = [
            {"path": "runs/revision-02/summary.json"},
            {"path": "20261008-old/report.json"},
        ]
        classify(rows, groups)
        self.assertEqual(rows[0]["improvement_archive_group"], "EXPERIMENT")
        self.assertEqual(rows[1]["improvement_archive_group"], "UNMAPPED")

    def test_ambiguous_improvement_mapping_is_rejected(self):
        groups = {
            "improvements": [
                {"id": "A", "path_prefixes": ["runs/"]},
                {"id": "B", "path_prefixes": ["runs/"]},
            ]
        }
        with self.assertRaises(ValueError):
            classify([{"path": "runs/summary.json"}], groups)


if __name__ == "__main__":
    unittest.main()
