"""Contract tests for failure-path end-to-end drill scenarios."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.deployment_packets import PacketStatus
from shared.policy.failure_path_drills import (
    VALIDATION_ERRORS,
    FailurePathDrillRequest,
    evaluate_failure_path_drill,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "failure_path_drills_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"failure-path drill fixture failed to load: {exc}") from exc


def build_request(payload: dict[str, object]) -> FailurePathDrillRequest:
    return FailurePathDrillRequest.from_dict(payload)


class FailurePathDrillContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_scenario_and_timeline(self) -> None:
        request = build_request(load_cases()["drill_cases"][0]["payload"])
        reparsed = FailurePathDrillRequest.from_json(request.to_json())

        self.assertEqual(request.drill_id, reparsed.drill_id)
        self.assertEqual(request.scenario, reparsed.scenario)
        self.assertEqual(request.expected_safe_outcome, reparsed.expected_safe_outcome)
        self.assertEqual(request.timeline_events, reparsed.timeline_events)

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["drill_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_failure_path_drill(
                    case["case_id"],
                    build_request(case["payload"]),
                )
                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)

    def test_report_is_structured_and_retains_safe_outcome_artifacts(self) -> None:
        case = next(
            case
            for case in load_cases()["drill_cases"]
            if case["case_id"] == "allow_restore_host_loss_remains_halted_until_review"
        )
        report = evaluate_failure_path_drill(
            case["case_id"],
            build_request(case["payload"]),
        )
        payload = report.to_dict()

        self.assertEqual(PacketStatus.PASS.value, report.status)
        self.assertEqual("remain_halted_until_review", report.observed_safe_outcome)
        self.assertIn("restore", report.explanation.lower())
        self.assertIn("backup_checkpoint_live_20260327_401", report.retained_artifact_ids)
        self.assertTrue(
            {
                "case_id",
                "drill_id",
                "scenario",
                "status",
                "reason_code",
                "expected_safe_outcome",
                "observed_safe_outcome",
                "correlation_id",
                "retained_artifact_ids",
                "subreport_reason_codes",
                "timeline_events",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )


if __name__ == "__main__":
    unittest.main()
