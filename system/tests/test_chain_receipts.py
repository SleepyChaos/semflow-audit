"""Failed attempts and private material must survive with honest archive boundaries."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.benchmarks.chain_summary import summarize
from scripts.test_archive.catalog import selected_files
from scripts.test_archive.identity import environment


class ChainReceiptsTests(unittest.TestCase):
    def test_offline_environment_does_not_contact_docker_or_inherit_image_ids(self):
        calls = []

        def observe(args, root):
            calls.append(args)
            return {"status": "unavailable", "value": None}

        with patch("scripts.test_archive.identity.command", side_effect=observe):
            snapshot = environment(
                Path(__file__).resolve().parents[2], inspect_images=False
            )
        self.assertFalse(
            any(args[:3] == ["docker", "image", "inspect"] for args in calls)
        )
        self.assertTrue(snapshot["service_image_identities"])
        self.assertEqual(snapshot["stage_defaults_from_source"]["report"], "2")
        self.assertTrue(
            all(
                row["status"] == "not_observed" and row["value"] is None
                for row in snapshot["service_image_identities"].values()
            )
        )

    def test_reused_stage_is_counted_once_and_failure_is_never_completed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for version in (1, 2):
                output = base / f"20261009-v{version}"
                output.mkdir()
                (output / "report.json").write_text(
                    json.dumps(
                        {
                            "steps": [
                                {
                                    "language": "python",
                                    "name": "confirmation",
                                    "status": "failed",
                                }
                            ],
                            "scope": "test",
                        }
                    )
                )
                (output / "same-completed-stage-receipt.json").write_text(
                    json.dumps(
                        {
                            "id": "same",
                            "audit_id": "audit",
                            "kind": "scout",
                            "status": "completed",
                            "prompt_version": "7",
                            "usage": {},
                            "model_calls": [
                                {
                                    "input_tokens": 10,
                                    "output_tokens": 2,
                                    "response_model": "actual",
                                }
                            ],
                        }
                    )
                )
            regression = base / "20261009-v1/regression"
            regression.mkdir()
            (regression / "junit.xml").write_text(
                '<testsuites><testsuite><testcase name="a"/><testcase name="b"><skipped/></testcase></testsuite></testsuites>'
            )
            result = summarize(base)
            self.assertEqual(result["usage"]["calls"], 1)
            self.assertEqual(result["usage"]["input_tokens"], 10)
            self.assertEqual(result["regression"]["skipped"], 1)
            self.assertFalse(result["all_product_chains_completed"])
            self.assertEqual(
                [a["counts"] for a in result["attempts"]],
                [{"failed": 1}, {"failed": 1}],
            )
            self.assertFalse(result["independent_human_review"])

    def test_selected_chain_archive_excludes_credentials_and_database_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "artifacts/research/chain-completion/20261009-v1"
            run.mkdir(parents=True)
            for name in (
                "report.json",
                "credentials.private.json",
                "browser.log",
                "regression.xml",
                "failure.png",
                "input-source.tar.gz",
                "runner-source.tar.gz",
                "accepted.diff",
                "published.ql",
                "baseline.sarif",
            ):
                (run / name).write_text("{}")
            database = run / "runtime/task/database"
            database.mkdir(parents=True)
            (database / "report.json").write_text("{}")
            payload = run / "runtime/task/model-response.json"
            payload.write_text("{}")
            selected = selected_files(root)
            names = {p.name for p in selected}
            self.assertNotIn("credentials.private.json", names)
            self.assertNotIn(payload, selected)
            self.assertNotIn(database / "report.json", selected)
            self.assertEqual(len(selected), 9)
            self.assertIn("baseline.sarif", names)


if __name__ == "__main__":
    unittest.main()
