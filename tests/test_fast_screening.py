from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.fast_screening import (
    REQUIRED_FULL_NAUTILUS_FOLLOW_ON,
    FastScreeningCheckID,
    FastScreeningReport,
    FastScreeningRequest,
    FastScreeningStatus,
    VALIDATION_ERRORS,
    evaluate_fast_screening_path,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "fast_screening_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"fast screening fixture failed to load: {exc}") from exc


class FastScreeningContractTests(unittest.TestCase):
    def test_request_round_trip_serialization_preserves_payload(self) -> None:
        request = FastScreeningRequest.from_dict(load_cases()["cases"][0]["request"])
        self.assertEqual(request, FastScreeningRequest.from_json(request.to_json()))

    def test_request_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = deepcopy(load_cases()["cases"][0]["request"])
        invalid_cases = (
            (
                "non_object_payload",
                [],
                "fast_screening_request: must be an object",
            ),
            (
                "equivalence_passed_truthy_string",
                lambda payload: payload["equivalence_evidence"].__setitem__("passed", "true"),
                "passed: must be boolean",
            ),
            (
                "coverage_seed_count_bool",
                lambda payload: payload["equivalence_evidence"].__setitem__("coverage_seed_count", True),
                "coverage_seed_count: must be an integer",
            ),
            (
                "other_allowed_actions_string",
                lambda payload: payload["governance"].__setitem__("other_allowed_actions", "continue"),
                "other_allowed_actions: must be a list of strings",
            ),
            (
                "schema_version_unsupported",
                lambda payload: payload.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
            (
                "schema_version_missing",
                lambda payload: payload.pop("schema_version"),
                "schema_version: missing required field",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                if case_id == "non_object_payload":
                    with self.assertRaisesRegex(ValueError, error):
                        FastScreeningRequest.from_dict(mutate)
                    continue
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FastScreeningRequest.from_dict(payload)

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = FastScreeningRequest.from_dict(case["request"])
                report = evaluate_fast_screening_path(request)
                failed_reason_codes = [
                    trace["reason_code"]
                    for trace in report.decision_trace
                    if not trace["passed"]
                ]

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected_fast_path_eligible"],
                    report.fast_path_eligible,
                )
                self.assertEqual(
                    case["expected_equivalence_certified"],
                    report.equivalence_certified,
                )
                self.assertEqual(
                    case["expected_promotion_blocked"],
                    report.promotion_blocked,
                )
                self.assertEqual(
                    case["expected_admissible_research_actions"],
                    report.admissible_research_actions,
                )
                self.assertEqual(
                    case["expected_failed_check_ids"],
                    report.failed_check_ids,
                )
                self.assertEqual(
                    case["expected_failed_reason_codes"],
                    failed_reason_codes,
                )

    def test_report_is_structured_and_operator_readable(self) -> None:
        request = FastScreeningRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_fast_screening_path(request)
        payload = report.to_dict()

        self.assertEqual(FastScreeningStatus.PASS.value, report.status)
        self.assertEqual(
            list(REQUIRED_FULL_NAUTILUS_FOLLOW_ON),
            report.required_follow_on_workflow,
        )
        self.assertTrue(
            {
                "case_id",
                "candidate_id",
                "strategy_class_id",
                "fast_path_engine",
                "status",
                "reason_code",
                "fast_path_eligible",
                "equivalence_certified",
                "promotion_blocked",
                "admissible_research_actions",
                "required_follow_on_workflow",
                "decision_trace",
                "failed_check_ids",
                "retained_run_log_ids",
                "retained_artifact_ids",
                "expected_vs_actual_diff_ids",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertTrue(report.retained_run_log_ids)
        self.assertTrue(report.retained_artifact_ids)
        self.assertTrue(report.expected_vs_actual_diff_ids)
        self.assertIn("Nautilus", report.explanation)

    def test_report_round_trip_preserves_emitted_shape(self) -> None:
        request = FastScreeningRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_fast_screening_path(request)
        self.assertEqual(
            report.to_dict(),
            FastScreeningReport.from_json(report.to_json()).to_dict(),
        )

    def test_report_loader_rejects_invalid_boundary_values(self) -> None:
        request = FastScreeningRequest.from_dict(load_cases()["cases"][0]["request"])
        base_payload = evaluate_fast_screening_path(request).to_dict()
        invalid_cases = (
            (
                "non_object_payload",
                "[]",
                "fast_screening_report: expected JSON object",
            ),
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ship"),
                "status: must be a valid fast-screening status",
            ),
            (
                "decision_trace_string",
                lambda payload: payload.__setitem__("decision_trace", "trace"),
                "decision_trace: must be a list of objects",
            ),
            (
                "timestamp_naive",
                lambda payload: payload.__setitem__("timestamp", "2026-03-28T00:00:00"),
                "timestamp: must be timezone-aware",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                if case_id == "non_object_payload":
                    with self.assertRaisesRegex(ValueError, error):
                        FastScreeningReport.from_json(mutate)
                    continue
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FastScreeningReport.from_dict(payload)

    def test_invalid_request_shape_returns_invalid_status(self) -> None:
        request = FastScreeningRequest.from_dict(load_cases()["cases"][0]["request"])
        invalid_request = FastScreeningRequest(
            case_id=request.case_id,
            candidate_id=request.candidate_id,
            strategy_class_id=request.strategy_class_id,
            fast_path_engine="",
            decision_basis=request.decision_basis,
            bar_interval_seconds=0,
            order_semantics=(),
            order_management_mode="",
            requires_passive_queue_dependence=request.requires_passive_queue_dependence,
            depends_on_portability_sensitive_microstructure=(
                request.depends_on_portability_sensitive_microstructure
            ),
            equivalence_evidence=request.equivalence_evidence,
            governance=request.governance,
            schema_version=request.schema_version,
        )

        report = evaluate_fast_screening_path(invalid_request)

        self.assertEqual(FastScreeningStatus.INVALID.value, report.status)
        self.assertEqual([FastScreeningCheckID.REQUEST_SHAPE.value], report.failed_check_ids)
        self.assertEqual([], report.admissible_research_actions)
        self.assertIn("invalid", report.reason_code.lower())

    def test_contract_validation_errors_are_empty(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


if __name__ == "__main__":
    unittest.main()
