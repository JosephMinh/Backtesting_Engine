from __future__ import annotations

import json
import unittest
from copy import deepcopy
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

    def test_request_loader_rejects_truthy_bool_and_bad_shapes(self) -> None:
        base_payload = deepcopy(load_cases()["cases"][0]["request"])
        invalid_cases = (
            (
                "schema_loaded_truthy_string",
                lambda payload: payload["schema_surfaces"][0].__setitem__("loaded", "true"),
                "loaded must be a boolean",
            ),
            (
                "property_seed_bool",
                lambda payload: payload["property_harness"].__setitem__("seed", True),
                "seed must be an integer",
            ),
            (
                "operator_reason_bundle_string",
                lambda payload: payload.__setitem__("operator_reason_bundle", "boot"),
                "operator_reason_bundle must be a sequence of non-empty strings",
            ),
            (
                "deterministic_clock_naive",
                lambda payload: payload.__setitem__(
                    "deterministic_clock_utc",
                    "2026-03-28T00:00:00",
                ),
                "deterministic_clock_utc must be a timezone-aware ISO-8601 timestamp",
            ),
            (
                "clock_probe_not_object",
                lambda payload: payload.__setitem__("clock_probe", []),
                "clock_probe must be an object",
            ),
            (
                "schema_surface_error_detail_missing",
                lambda payload: payload["schema_surfaces"][0].pop("error_detail"),
                "error_detail missing required field",
            ),
            (
                "startup_mismatch_details_missing",
                lambda payload: payload["startup_compatibility"].pop("mismatch_details"),
                "mismatch_details missing required field",
            ),
            (
                "round_trip_expected_diff_missing",
                lambda payload: payload["round_trip_smoke"].pop("expected_vs_actual_diff_id"),
                "expected_vs_actual_diff_id missing required field",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FoundationHarnessRequest.from_dict(payload)

    def test_report_loader_rejects_invalid_status_and_bad_sequences(self) -> None:
        report_payload = evaluate_foundation_harness(
            FoundationHarnessRequest.from_dict(load_cases()["cases"][0]["request"])
        ).to_dict()
        invalid_cases = (
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ready"),
                "status must be a valid foundation harness status",
            ),
            (
                "failure_classes_invalid",
                lambda payload: payload.__setitem__("failure_classes", ["bad_class"]),
                "bad_class",
            ),
            (
                "check_results_string",
                lambda payload: payload.__setitem__("check_results", "FH01"),
                "check_results must be a sequence of objects",
            ),
            (
                "timestamp_missing",
                lambda payload: payload.pop("timestamp"),
                "timestamp missing required field",
            ),
            (
                "check_failure_class_missing",
                lambda payload: payload["check_results"][0].pop("failure_class"),
                "failure_class missing required field",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(report_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FoundationHarnessReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
