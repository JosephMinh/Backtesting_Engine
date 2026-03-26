from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.fidelity_calibration import (
    EXPLICITLY_EXCLUDED_STRATEGY_CLASSES,
    FidelityCalibrationRequest,
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


if __name__ == "__main__":
    unittest.main()
