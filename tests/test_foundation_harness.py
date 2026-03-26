from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.foundation_harness import (
    VALIDATION_ERRORS,
    FoundationHarnessReport,
    FoundationHarnessRequest,
    evaluate_foundation_harness,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "foundation_harness_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"foundation harness fixture failed to load: {exc}") from exc


def failed_reason_codes(report: FoundationHarnessReport) -> list[str]:
    return [check.reason_code for check in report.check_results if not check.passed]


class FoundationHarnessContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_payload(self) -> None:
        request = FoundationHarnessRequest.from_dict(load_cases()["cases"][0]["request"])
        self.assertEqual(request, FoundationHarnessRequest.from_json(request.to_json()))

    def test_report_round_trip_preserves_payload(self) -> None:
        request = FoundationHarnessRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_foundation_harness(request)
        self.assertEqual(report, FoundationHarnessReport.from_json(report.to_json()))

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["cases"]:
            with self.subTest(case_id=payload["case_id"]):
                request = FoundationHarnessRequest.from_dict(payload["request"])
                report = evaluate_foundation_harness(request)

                self.assertEqual(payload["expected"]["status"], report.status)
                self.assertEqual(payload["expected"]["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(payload["expected"]["failure_classes"]),
                    report.failure_classes,
                )

    def test_report_is_structured_and_operator_readable(self) -> None:
        request = FoundationHarnessRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_foundation_harness(request)
        payload = report.to_dict()

        self.assertTrue(
            {
                "case_id",
                "phase_gate",
                "status",
                "reason_code",
                "passed_count",
                "failed_count",
                "failure_classes",
                "check_results",
                "correlation_id",
                "retained_artifact_ids",
                "operator_reason_bundle",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertEqual("phase_0", report.phase_gate)
        self.assertIn("reproducible", report.explanation.lower())
        self.assertGreaterEqual(len(report.retained_artifact_ids), 6)

    def test_invariant_failure_case_records_multiple_failed_reasons(self) -> None:
        request = FoundationHarnessRequest.from_dict(load_cases()["cases"][3]["request"])
        report = evaluate_foundation_harness(request)

        self.assertEqual(("invariant_failure",), report.failure_classes)
        self.assertEqual(
            [
                "FOUNDATION_JOURNAL_DIGEST_FAILED",
                "FOUNDATION_PROPERTY_HARNESS_FAILED",
            ],
            failed_reason_codes(report),
        )


if __name__ == "__main__":
    unittest.main()
