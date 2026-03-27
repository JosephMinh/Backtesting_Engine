"""Contract tests for notebook quarantine and admissible evidence boundaries."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.notebook_quarantine import (
    VALIDATION_ERRORS,
    NotebookQuarantineReport,
    NotebookQuarantineRequest,
    admissible_gate_source_kinds,
    evaluate_notebook_quarantine,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "notebook_quarantine_cases.json"
)


class TestNotebookQuarantineContract(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_admissible_source_kinds_match_the_plan_boundary(self) -> None:
        self.assertEqual(
            (
                "reproducible_batch_run",
                "signed_manifest",
                "certified_release",
                "policy_evaluated_report",
                "sealed_operational_evidence_bundle",
            ),
            admissible_gate_source_kinds(),
        )

    def test_fixture_cases(self) -> None:
        try:
            payload = json.JSONDecoder().decode(FIXTURE_PATH.read_text())
        except json.JSONDecodeError as exc:
            self.fail(f"fixture JSON is invalid: {exc}")
        for case in payload["cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = NotebookQuarantineRequest.from_dict(case["request"])
                report = evaluate_notebook_quarantine(request)
                self.assertEqual(case["expected"]["status"], report.status.value)
                self.assertEqual(
                    case["expected"]["selection_admissible"],
                    report.selection_admissible,
                )
                self.assertEqual(
                    case["expected"]["promotion_admissible"],
                    report.promotion_admissible,
                )
                self.assertEqual(
                    tuple(case["expected"]["quarantined_source_ids"]),
                    report.quarantined_source_ids,
                )
                self.assertEqual(
                    tuple(case["expected"]["admissible_source_ids"]),
                    report.admissible_source_ids,
                )
                self.assertEqual(
                    tuple(case["expected"]["rejected_source_ids"]),
                    report.rejected_source_ids,
                )
                self.assertEqual(
                    tuple(case["expected"]["covered_decision_record_ids"]),
                    report.covered_decision_record_ids,
                )
                self.assertEqual(
                    tuple(case["expected"]["missing_decision_record_ids"]),
                    report.missing_decision_record_ids,
                )
                self.assertEqual(
                    tuple(case["expected"]["failing_reason_codes"]),
                    tuple(
                        result.reason_code
                        for result in report.check_results
                        if result.reason_code is not None
                    ),
                )

    def test_report_round_trip_preserves_check_results(self) -> None:
        request = NotebookQuarantineRequest.from_dict(
            {
                "evaluation_id": "nbq-roundtrip",
                "family_id": "gold_breakout",
                "required_decision_record_ids": ["decision-001"],
                "evidence_sources": [
                    {
                        "source_id": "decision-report",
                        "source_kind": "policy_evaluated_report",
                        "usage": "promotion",
                        "counts_toward_gate": True,
                        "canonical_reference_id": "decision-001",
                        "reference_artifact_id": "family_decision_record",
                        "family_decision_record_id": "decision-001",
                    }
                ],
            }
        )
        restored = NotebookQuarantineReport.from_dict(
            self._load_report_json(evaluate_notebook_quarantine(request).to_json())
        )

        self.assertEqual("pass", restored.status.value)
        self.assertTrue(restored.promotion_admissible)
        self.assertEqual(("decision-report",), restored.admissible_source_ids)
        self.assertEqual(6, len(restored.check_results))

    def _load_report_json(self, payload: str) -> dict[str, object]:
        try:
            return json.JSONDecoder().decode(payload)
        except json.JSONDecodeError as exc:
            self.fail(f"report JSON is invalid: {exc}")


if __name__ == "__main__":
    unittest.main()
