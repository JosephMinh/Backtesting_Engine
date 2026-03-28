from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from shared.policy.fidelity_calibration import (
    EXPLICITLY_EXCLUDED_STRATEGY_CLASSES,
    FidelityCalibrationRequest,
    FidelityCalibrationReport,
    SessionCalibrationEvidence,
    FidelityCalibrationStatus,
    evaluate_fidelity_calibration,
    list_explicitly_excluded_strategy_classes,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "fidelity_calibration_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"fidelity calibration fixture failed to load: {exc}") from exc


class FidelityCalibrationContractTests(unittest.TestCase):
    def test_request_round_trip_serialization_preserves_payload(self) -> None:
        request = FidelityCalibrationRequest.from_dict(load_cases()["cases"][0]["request"])
        self.assertEqual(request, FidelityCalibrationRequest.from_json(request.to_json()))

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = FidelityCalibrationRequest.from_dict(case["request"])
                report = evaluate_fidelity_calibration(request)
                failed_reason_codes = [
                    trace["reason_code"]
                    for trace in report.decision_trace
                    if not trace["passed"]
                ]

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_live_lane_eligible"], report.live_lane_eligible)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(case["expected_failed_reason_codes"], failed_reason_codes)

    def test_report_is_structured_and_explainable(self) -> None:
        request = FidelityCalibrationRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_fidelity_calibration(request)
        payload = report.to_dict()

        self.assertEqual(FidelityCalibrationStatus.APPROVED.value, report.status)
        self.assertTrue(
            {
                "case_id",
                "candidate_id",
                "strategy_class_id",
                "status",
                "live_lane_eligible",
                "reason_code",
                "decision_trace",
                "failed_check_ids",
                "known_excluded_strategy_class_ids",
                "matched_excluded_strategy_class_ids",
                "session_classes",
                "supporting_data_refs",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertIn("session-conditioned", report.explanation.lower())
        self.assertEqual(["regular", "overnight"], report.session_classes)
        self.assertEqual(report, FidelityCalibrationReport.from_json(report.to_json()))

    def test_excluded_strategy_classes_are_recorded_explicitly(self) -> None:
        exclusions = list_explicitly_excluded_strategy_classes()
        self.assertEqual(EXPLICITLY_EXCLUDED_STRATEGY_CLASSES, exclusions)
        self.assertEqual(6, len(exclusions))

        exclusion_ids = {exclusion.strategy_class_id for exclusion in exclusions}
        self.assertTrue(
            {
                "sub_minute_reactive_scalping",
                "tick_reactive_intrabar",
                "order_book_imbalance_reversion",
                "queue_position_capture",
                "sub_minute_market_making",
                "premium_depth_microstructure",
            }.issubset(exclusion_ids)
        )

    def test_explicit_exclusion_is_reported_when_strategy_matches_registry(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "order_book_dependency_rejected"
        )
        request = FidelityCalibrationRequest.from_dict(case["request"])
        report = evaluate_fidelity_calibration(request)

        self.assertEqual(
            ["order_book_imbalance_reversion"],
            report.matched_excluded_strategy_class_ids,
        )
        self.assertIn(
            "order_book_imbalance_reversion",
            report.known_excluded_strategy_class_ids,
        )

    def test_request_loader_rejects_truthy_bool_and_bad_session_shapes(self) -> None:
        base_payload = deepcopy(load_cases()["cases"][0]["request"])
        invalid_cases = (
            (
                "passive_fill_truthy_string",
                lambda payload: payload.__setitem__(
                    "requires_passive_fill_assumption",
                    "false",
                ),
                "requires_passive_fill_assumption must be a boolean",
            ),
            (
                "decision_interval_bool",
                lambda payload: payload.__setitem__("decision_interval_seconds", True),
                "decision_interval_seconds must be an integer",
            ),
            (
                "session_calibrations_string",
                lambda payload: payload.__setitem__("session_calibrations", "regular"),
                "session_calibrations must be a sequence of objects",
            ),
            (
                "candidate_id_bool",
                lambda payload: payload.__setitem__("candidate_id", False),
                "candidate_id must be a non-empty string",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FidelityCalibrationRequest.from_dict(payload)

    def test_session_evidence_loader_rejects_bool_nonfinite_and_string_sequences(self) -> None:
        base_payload = deepcopy(load_cases()["cases"][0]["request"]["session_calibrations"][0])
        invalid_cases = (
            (
                "bar_sufficiency_truthy_string",
                lambda payload: payload.__setitem__("bar_sufficiency_passed", "true"),
                "bar_sufficiency_passed must be a boolean",
            ),
            (
                "slippage_nan",
                lambda payload: payload.__setitem__("realistic_slippage_bps", "nan"),
                "realistic_slippage_bps must be a finite number",
            ),
            (
                "bar_interval_bool",
                lambda payload: payload.__setitem__("bar_interval_seconds", True),
                "bar_interval_seconds must be an integer",
            ),
            (
                "supporting_refs_string",
                lambda payload: payload.__setitem__(
                    "supporting_data_refs",
                    "studies/fidelity/bad.json",
                ),
                "supporting_data_refs must be a sequence of strings",
            ),
            (
                "session_class_empty",
                lambda payload: payload.__setitem__("session_class", ""),
                "session_class must be a non-empty string",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    SessionCalibrationEvidence.from_dict(payload)

    def test_report_loader_rejects_invalid_boundary_values(self) -> None:
        report_payload = evaluate_fidelity_calibration(
            FidelityCalibrationRequest.from_dict(load_cases()["cases"][0]["request"])
        ).to_dict()
        invalid_cases = (
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ready"),
                "ready",
            ),
            (
                "live_lane_truthy_string",
                lambda payload: payload.__setitem__("live_lane_eligible", "true"),
                "live_lane_eligible must be a boolean",
            ),
            (
                "decision_trace_string",
                lambda payload: payload.__setitem__("decision_trace", "trace"),
                "decision_trace must be a sequence of objects",
            ),
            (
                "decision_trace_bad_timestamp",
                lambda payload: payload["decision_trace"][0].__setitem__(
                    "timestamp",
                    "2026-03-28T01:30:00",
                ),
                "timestamp must be timezone-aware",
            ),
            (
                "failed_check_ids_bool",
                lambda payload: payload.__setitem__("failed_check_ids", [False]),
                "failed_check_ids must be a sequence of strings",
            ),
            (
                "timestamp_missing",
                lambda payload: payload.pop("timestamp"),
                "timestamp",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(report_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    FidelityCalibrationReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
