"""Offline provenance, evidence-availability and replay-isolation regression tests."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_evidence_feedback import (
    accepted_matches,
    gap_status,
    named_paths,
    provider_hash,
    requests_for,
    stage_rows,
    verify_supplement,
)
from prepare_dvga_feedback_replay import add_pages, base_context


def page(identifier="p1", start=1, end=3):
    content = "source body"
    return {
        "id": identifier,
        "kind": "code",
        "content": content,
        "reference": {"file": "core/guard.py", "start_line": start, "end_line": end},
        "digest": hashlib.sha256(content.encode()).hexdigest(),
    }


def window(row, total=6):
    return {
        "evidence_id": row["id"],
        **row["reference"],
        "total_lines": total,
        "complete_file": False,
    }


class EvidenceAvailabilityTests(unittest.TestCase):
    def test_partial_page_does_not_imply_complete_control_chain(self):
        p = page()
        result = gap_status(
            "core/guard.py",
            {"evidence": [p], "source_windows": [window(p)]},
            [p],
            {"p1": 1},
            10,
        )
        self.assertEqual(result["availability"], "pages_in_current_request")
        self.assertFalse(result["complete_in_current_request"])
        self.assertEqual(
            result["next_action"], "inspect_supplied_pages_and_identify_unread_ranges"
        )

    def test_union_of_actual_pages_establishes_file_coverage_only(self):
        pages = [page(), page("p2", 4, 6)]
        ctx = {"evidence": pages, "source_windows": [window(p) for p in pages]}
        result = gap_status("core/guard.py", ctx, pages, {}, 10)
        self.assertTrue(result["complete_in_current_request"])
        self.assertIn("not proof", result["limit"])

    def test_earlier_stage_read_is_distinct_from_current_context(self):
        p = page()
        result = gap_status("core/guard.py", {"evidence": []}, [p], {"p1": 3}, 10)
        self.assertEqual(result["availability"], "pages_seen_in_earlier_stage_call")
        self.assertEqual(result["current_evidence_ids"], [])
        self.assertEqual(result["earlier_evidence_ids"], ["p1"])

    def test_future_read_never_becomes_historical_available_evidence(self):
        result = gap_status("core/guard.py", {"evidence": []}, [page()], {"p1": 11}, 10)
        self.assertEqual(
            result["availability"], "pages_retained_in_stage_time_unverified"
        )
        self.assertEqual(result["earlier_evidence_ids"], [])

    def test_missing_file_is_not_silent_empty_success(self):
        result = gap_status("missing.py", {"evidence": []}, [], {}, 10)
        self.assertEqual(result["availability"], "no_retained_pages")

    def test_paths_only_come_from_missing_premise_text(self):
        assessment = {
            "missing_premises": ["未读（core/middleware.py、core/view_override.py）"],
            "reason": "app.py was read",
            "premises": [{"status": "established", "reason": "config.py inspected"}],
        }
        self.assertEqual(
            named_paths(assessment), ["core/middleware.py", "core/view_override.py"]
        )

    def test_navigation_outside_snapshot_is_never_an_actionable_file(self):
        assessment = {
            "missing_premises": ["../private/key.py /etc/config.py core/valid.py"]
        }
        self.assertEqual(named_paths(assessment), ["core/valid.py"])

    def test_template_control_paths_are_retained_as_missing_facts(self):
        assessment = {
            "missing_premises": ["需读取 templates/paste.html 与 frontend/page.tsx"]
        }
        self.assertEqual(
            named_paths(assessment), ["frontend/page.tsx", "templates/paste.html"]
        )


class ProvenanceTests(unittest.TestCase):
    def test_citation_retention_matches_host_but_cannot_change_a_verdict(self):
        raw = {
            "assessment": "insufficient",
            "evidence_ids": [],
            "detail": {
                "evidence_ids": ["detail"],
                "exploitation": {"evidence_ids": ["example"]},
            },
            "premises": [{"evidence_ids": ["detail", "premise"]}],
        }
        accepted = {**raw, "evidence_ids": ["detail", "example", "premise"]}
        self.assertTrue(accepted_matches(raw, accepted))
        self.assertFalse(accepted_matches(raw, {**accepted, "assessment": "supported"}))
        self.assertFalse(
            accepted_matches(raw, {**accepted, "evidence_ids": ["invented"]})
        )

    def test_provider_identity_keeps_retries_for_one_saved_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "batches/b/call-0"
            path.mkdir(parents=True)
            payload = {"evidence": [], "text": "原始请求"}
            (path / "input.json").write_text(json.dumps({"payload": payload}))
            (path / "receipt.json").write_text(
                json.dumps({"output": {"action": "final"}})
            )
            stage = {
                "model_calls": [
                    {"input_hash": provider_hash(payload), "call_index": i}
                    for i in (7, 8)
                ]
            }
            self.assertEqual(
                next(iter(requests_for(root, stage).values()))["indices"], [7, 8]
            )
            with self.assertRaisesRegex(ValueError, "no provider call"):
                requests_for(root, {"model_calls": []})

    def test_manifest_detects_changed_actual_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source.json").write_bytes(b"source")
            manifest = [
                {
                    "path": "source.json",
                    "bytes": 6,
                    "sha256": hashlib.sha256(b"source").hexdigest(),
                }
            ]
            (root / "MANIFEST.json").write_text(json.dumps(manifest))
            self.assertEqual(verify_supplement(root), 1)
            (root / "source.json").write_bytes(b"forged")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_supplement(root)

    def test_cross_snapshot_evidence_fails_before_request_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "database-records/s1"
            db.mkdir(parents=True)
            (db / "stage.json").write_text(
                json.dumps({"result": {"snapshot_hash": "old"}})
            )
            evidence = {**page(), "snapshot_hash": "new", "stage_id": "s1"}
            (db / "evidence.json").write_text(json.dumps([evidence]))
            with self.assertRaisesRegex(ValueError, "Cross-snapshot"):
                stage_rows(root, root / "review-stages/s1")


class ReplayIsolationTests(unittest.TestCase):
    def test_pairing_removes_only_unselected_targets_and_preserves_source(self):
        original = {
            "targets": [{"candidate_id": "a"}, {"candidate_id": "b"}],
            "citation_contract": {"target_source_ids": {"a": ["p1"], "b": ["p2"]}},
            "evidence": [page()],
            "source_inventory": {"files": ["core/guard.py"]},
        }
        context = base_context(original, {"a"})
        self.assertEqual(context["targets"], [{"candidate_id": "a"}])
        self.assertEqual(
            context["citation_contract"]["target_source_ids"], {"a": ["p1"]}
        )
        self.assertEqual(context["evidence"], original["evidence"])
        self.assertEqual(len(original["targets"]), 2)
        self.assertTrue(context["finalize_required"])
        self.assertFalse(context["allow_supplementary_findings"])

    def test_retrieval_retains_ids_bodies_and_independent_contexts(self):
        p1, p2 = page(), page("p2", 4, 6)
        base = {
            "evidence": [p1],
            "source_windows": [window(p1)],
            "local_control_context": {"provided_complete_modules": []},
        }
        supplied = add_pages(base, [p1, p2], {p["id"]: window(p) for p in [p1, p2]})
        self.assertEqual(supplied["evidence"], [p1, p2])
        self.assertEqual(
            supplied["local_control_context"]["provided_complete_modules"],
            ["core/guard.py"],
        )
        self.assertEqual(base["evidence"], [p1])
        self.assertEqual(base["local_control_context"]["provided_complete_modules"], [])


if __name__ == "__main__":
    unittest.main()
