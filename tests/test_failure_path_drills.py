"""Contract tests for failure-path end-to-end drill scenarios."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.deployment_packets import PacketStatus
from shared.policy.failure_path_drills import (
    VALIDATION_ERRORS,
    FailurePathDrillRequest,
    FailurePathDrillReport,
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

    def test_request_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = deepcopy(load_cases()["drill_cases"][0]["payload"])
        invalid_cases = (
            (
                "non_object_payload",
                [],
                "failure_path_drill_request: must be an object",
            ),
            (
                "scenario_invalid",
                lambda payload: payload.__setitem__("scenario", "resume"),
                "scenario: must be a valid failure-path scenario",
            ),
            (
                "timeline_events_string",
                lambda payload: payload.__setitem__("timeline_events", "event"),
                "timeline_events: must be a list of objects",
            ),
            (
                "sequence_number_bool",
                lambda payload: payload["timeline_events"][0].__setitem__("sequence_number", True),
                "sequence_number: must be an integer",
            ),
            (
                "operator_reason_bundle_string",
                lambda payload: payload.__setitem__("operator_reason_bundle", "reason"),
                "operator_reason_bundle: must be a list of strings",
            ),
            (
                "schema_version_unsupported",
                lambda payload: payload.__setitem__("schema_version", 2),
                "schema_version: unsupported schema version 2; expected 1",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                if case_id == "non_object_payload":
                    with self.assertRaisesRegex(ValueError, error):
                        FailurePathDrillRequest.from_dict(mutate)
                    continue
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FailurePathDrillRequest.from_dict(payload)

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

    def test_report_round_trip_preserves_emitted_shape(self) -> None:
        case = load_cases()["drill_cases"][0]
        report = evaluate_failure_path_drill(
            case["case_id"],
            build_request(case["payload"]),
        )

        self.assertEqual(
            report.to_dict(),
            FailurePathDrillReport.from_json(report.to_json()).to_dict(),
        )

    def test_report_loader_rejects_invalid_boundary_values(self) -> None:
        case = load_cases()["drill_cases"][0]
        base_payload = evaluate_failure_path_drill(
            case["case_id"],
            build_request(case["payload"]),
        ).to_dict()
        invalid_cases = (
            (
                "non_object_payload",
                [],
                "failure_path_drill_report: payload must decode to a JSON object",
            ),
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ship"),
                "status: must be a valid packet status",
            ),
            (
                "observed_safe_outcome_invalid",
                lambda payload: payload.__setitem__("observed_safe_outcome", "resume"),
                "observed_safe_outcome: must be a valid safe outcome",
            ),
            (
                "timeline_events_string",
                lambda payload: payload.__setitem__("timeline_events", "event"),
                "timeline_events: must be a list of objects",
            ),
            (
                "observed_safe_outcome_missing",
                lambda payload: payload.pop("observed_safe_outcome"),
                "observed_safe_outcome: field is required",
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
                        FailurePathDrillReport.from_json("[]")
                    continue
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FailurePathDrillReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
