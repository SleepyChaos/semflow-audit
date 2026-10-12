"""Guard evaluator separation, scenario meaning and supplemental receipt selection."""

import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.benchmarks import supplemental_prepare as prep
from scripts.benchmarks.supplemental_repair_cases import cases
from scripts.benchmarks.supplemental_rule_cases import datasets
from scripts.test_archive.catalog import selected_files


class SupplementalDataTests(unittest.TestCase):
    def test_shape_ignores_identifiers_but_preserves_syntax_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for name, code in {
                "a.py": "def handler(value):\n return eval(value + 'one')\n",
                "b.py": "def renamed(payload):\n return eval(payload + 'two')\n",
                "safe.py": "def handler(value):\n return 'constant'\n",
            }.items():
                (source / name).write_text(code)
            with patch.object(prep, "SOURCE", source):
                self.assertEqual(
                    prep.shape({"file": "a.py"}), prep.shape({"file": "b.py"})
                )
                # This is syntax-shape screening, not a semantic duplicate proof.
                self.assertNotEqual(
                    prep.shape({"file": "a.py"}),
                    prep.shape({"file": "safe.py"}),
                )

    def test_model_batches_contain_paths_only_and_exclude_evaluator_answers(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            testcode = source / "testcode"
            testcode.mkdir(parents=True)
            selected = []
            for i in range(49):
                file = f"testcode/Case{i}.py"
                (source / file).write_text("value = 1\n")
                if i < 48:
                    selected.append(
                        {
                            "file": file,
                            "vulnerable": bool(i % 2),
                            "cwe": 79,
                            "category": "xss",
                        }
                    )
            output = Path(temporary) / "run"
            shapes = {r["file"]: "same" for r in selected}
            with patch.object(prep, "SOURCE", source):
                result = prep.make_sample(output, "fresh", selected, 1, shapes, set())
            model = json.loads(
                (output / "samples/fresh/model-batches.json").read_text()
            )
            self.assertEqual(len(model["batches"]), 12)
            self.assertTrue(
                all(set(r) == {"group_id", "case_paths"} for r in model["batches"])
            )
            self.assertNotIn("vulnerable", json.dumps(model))
            self.assertNotIn("cwe", json.dumps(model))
            self.assertEqual(result["case_count"], 48)
            self.assertFalse(
                (output / "samples/fresh/source/testcode/Case48.py").exists()
            )

    def test_repair_cases_have_distinct_business_and_security_oracles(self):
        rows = cases()
        self.assertEqual(len({r["id"] for r in rows}), 10)
        self.assertEqual(sum(r["language"] == "python" for r in rows), 5)
        for row in rows:
            self.assertNotEqual(row["normal"], row["security"])
            self.assertNotIn(row["security"], row["contract"])
            if row["language"] == "python":
                for key in ("normal", "security", "original", "reference"):
                    ast.parse(row[key])
        self.assertIn(
            "polluted", next(r for r in rows if r["id"] == "js-prototype")["security"]
        )

    def test_new_rule_flow_probes_have_exact_sink_locations_and_safe_negatives(self):
        rows = datasets()
        self.assertEqual(len(rows), 6)
        for row in rows.values():
            positive, negative = (
                row["fixtures"]["positive"],
                row["fixtures"]["negative"],
            )
            self.assertEqual(len(positive["expected"]), 2)
            self.assertEqual(negative["expected"], [])
            for expected in positive["expected"]:
                line = positive["files"][expected["file"]].splitlines()[
                    expected["line"] - 1
                ]
                self.assertIn("target", line)
            if row["language"] == "python":
                for group in (positive, negative):
                    for code in group["files"].values():
                        ast.parse(code)

    def test_archive_retains_failures_and_raw_logs_without_gui_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "artifacts/research/supplemental/20261009-v1/gui"
            directory.mkdir(parents=True)
            for name in (
                "report.json",
                "playwright.log",
                "junit.xml",
                "mobile.png",
                "input-source.tar.gz",
                "credentials.private.json",
            ):
                (directory / name).write_text("{}")
            selected = {p.name for p in selected_files(root)}
            self.assertEqual(
                selected,
                {
                    "report.json",
                    "playwright.log",
                    "junit.xml",
                    "mobile.png",
                    "input-source.tar.gz",
                },
            )


if __name__ == "__main__":
    unittest.main()
