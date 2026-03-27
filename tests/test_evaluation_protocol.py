from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from shared.policy.evaluation_protocol import (
    EVALUATION_PROTOCOL_CHECK_IDS,
    REQUIRED_EVALUATION_STAGE_ORDER,
    REQUIRED_OMISSION_DIMENSIONS,
    VALIDATION_ERRORS,
    EvaluationProtocolDecision,
    EvaluationProtocolReport,
    EvaluationProtocolRequest,
    EvaluationProtocolStatus,
    evaluate_evaluation_protocol,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "evaluation_protocol_cases.json"
)


def load_cases() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_request(overrides: dict[str, Any] | None = None) -> EvaluationProtocolRequest:
    fixture = load_cases()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), overrides or {})
    return EvaluationProtocolRequest.from_dict(payload)


class EvaluationProtocolCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_required_stage_order_matches_plan(self) -> None:
        self.assertEqual(
            (
                "screening",
                "validation",
                "stress",
                "omission",
                "lockbox",
                "candidate_freeze",
            ),
            REQUIRED_EVALUATION_STAGE_ORDER,
        )

    def test_required_omission_dimensions_match_plan(self) -> None:
        self.assertEqual(
            ("regime", "segment", "anchor", "event_cluster"),
            REQUIRED_OMISSION_DIMENSIONS,
        )


class EvaluationProtocolFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_evaluation_protocol(build_request(case["overrides"]))
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_check_ids"]),
                    report.triggered_check_ids,
                )
                self.assertEqual(
                    expected["deep_tuning_allowed"],
                    report.deep_tuning_allowed,
                )
                self.assertEqual(
                    expected["candidate_freeze_ready"],
                    report.candidate_freeze_ready,
                )
                self.assertEqual(
                    tuple(expected["omission_dimensions_covered"]),
                    report.omission_dimensions_covered,
                )

    def test_report_traces_every_check_in_catalog_order(self) -> None:
        report = evaluate_evaluation_protocol(build_request())

        self.assertEqual(len(EVALUATION_PROTOCOL_CHECK_IDS), len(report.check_results))
        self.assertEqual(
            EVALUATION_PROTOCOL_CHECK_IDS,
            tuple(result.check_id for result in report.check_results),
        )

    def test_success_report_retains_artifacts_and_correlations(self) -> None:
        report = evaluate_evaluation_protocol(build_request())

        self.assertEqual(EvaluationProtocolStatus.PASS.value, report.status)
        self.assertEqual(EvaluationProtocolDecision.FREEZE_CANDIDATE.value, report.decision)
        self.assertTrue(report.retained_artifact_ids)
        self.assertTrue(report.correlation_ids)
        self.assertIn("candidate-freeze-001", report.retained_artifact_ids)
        self.assertIn("corr-freeze-001", report.correlation_ids)

    def test_invalid_request_returns_invalid_report(self) -> None:
        request = build_request(
            {
                "case_id": "invalid-bootstrap",
                "bootstrap_intervals": [
                    {
                        "metric_id": "net_edge_bps",
                        "block_length_bars": 0,
                        "resample_count": 0,
                        "confidence_level": 1.5,
                        "lower_bound": 12.0,
                        "upper_bound": 8.0,
                        "minimum_acceptable_edge": 8.0,
                        "passed": False,
                        "artifact_bundle": {
                            "artifact_manifest_id": "manifest-invalid-bootstrap-001",
                            "retained_log_ids": ["log-invalid-bootstrap-001"],
                            "correlation_ids": ["corr-invalid-bootstrap-001"],
                            "expected_actual_diff_ids": ["diff-invalid-bootstrap-001"],
                            "operator_reason_bundle": ["bootstrap interval is malformed"]
                        }
                    }
                ]
            }
        )

        report = evaluate_evaluation_protocol(request)

        self.assertEqual(EvaluationProtocolStatus.INVALID.value, report.status)
        self.assertEqual(EvaluationProtocolDecision.REPAIR_PROTOCOL.value, report.decision)
        self.assertEqual("EVALUATION_PROTOCOL_REQUEST_INVALID", report.reason_code)
        self.assertEqual((), report.triggered_check_ids)
        self.assertEqual((), report.check_results)

    def test_report_json_round_trip_is_lossless(self) -> None:
        report = evaluate_evaluation_protocol(build_request())

        self.assertEqual(report, EvaluationProtocolReport.from_json(report.to_json()))


if __name__ == "__main__":
    unittest.main()
