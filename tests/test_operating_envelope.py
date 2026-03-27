from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.operating_envelope import (
    REQUIRED_SESSION_CLASSES,
    VALIDATION_ERRORS,
    OperatingEnvelopeEvaluationReport,
    OperatingEnvelopeEvaluationRequest,
    OperatingEnvelopeStatus,
    SessionConditionedRiskProfile,
    evaluate_operating_envelope,
    validate_operating_envelope_profile,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "operating_envelope_cases.json"
)


def load_cases() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_request(overrides: dict[str, object] | None = None) -> OperatingEnvelopeEvaluationRequest:
    fixture = load_cases()
    payload = deep_merge(
        dict(fixture["shared_request_defaults"]),
        overrides or {},
    )
    return OperatingEnvelopeEvaluationRequest.from_dict(payload)


class OperatingEnvelopeCatalogTests(unittest.TestCase):
    def test_operating_envelope_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


class OperatingEnvelopeFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = build_request(case["overrides"])
                report = evaluate_operating_envelope(request)
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_dimension_ids"]),
                    report.triggered_dimension_ids,
                )
                self.assertEqual(
                    tuple(expected["triggered_actions"]),
                    report.triggered_actions,
                )
                self.assertEqual(
                    expected["effective_size_multiplier"],
                    report.effective_size_multiplier,
                )
                self.assertEqual(
                    expected["effective_max_trade_count_multiplier"],
                    report.effective_max_trade_count_multiplier,
                )
                self.assertEqual(
                    expected["resulting_entry_mode"],
                    report.resulting_entry_mode,
                )
                self.assertEqual(
                    expected["required_operating_posture"],
                    report.required_operating_posture,
                )
                self.assertEqual(
                    expected["overnight_carry_allowed"],
                    report.overnight_carry_allowed,
                )
                self.assertIsNotNone(report.session_overlay)
                self.assertEqual(expected["session_band"], report.session_overlay.band)

    def test_report_traces_every_dimension_in_profile_order(self) -> None:
        request = build_request()
        report = evaluate_operating_envelope(request)

        self.assertEqual(
            len(request.operating_envelope_profile.dimensions),
            len(report.dimension_results),
        )
        self.assertEqual(
            tuple(
                dimension.dimension_id
                for dimension in request.operating_envelope_profile.dimensions
            ),
            tuple(result.dimension_id for result in report.dimension_results),
        )

    def test_report_round_trip_preserves_dimension_and_session_overlay_results(self) -> None:
        fixture = load_cases()
        case = next(
            case
            for case in fixture["evaluation_cases"]
            if case["case_id"] == "macro_event_profile_becomes_passive_only"
        )
        report = evaluate_operating_envelope(build_request(case["overrides"]))
        reparsed = OperatingEnvelopeEvaluationReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)


class OperatingEnvelopeEdgeCaseTests(unittest.TestCase):
    def test_missing_signal_score_drift_is_invalid_when_profile_marks_it_relevant(self) -> None:
        request = build_request()
        payload = request.to_dict()
        payload["observed_values"].pop("signal_score_drift")

        report = evaluate_operating_envelope(
            OperatingEnvelopeEvaluationRequest.from_dict(payload)
        )

        self.assertEqual(OperatingEnvelopeStatus.INVALID.value, report.status)
        self.assertEqual(
            "OPERATING_ENVELOPE_OBSERVED_VALUES_MISSING",
            report.reason_code,
        )

    def test_signal_score_drift_may_be_omitted_when_profile_marks_it_irrelevant(self) -> None:
        request = build_request()
        payload = request.to_dict()
        profile = dict(payload["operating_envelope_profile"])
        profile["signal_score_drift_relevant"] = False
        profile["dimensions"] = [
            dimension
            for dimension in profile["dimensions"]
            if dimension["dimension_id"] != "signal_score_drift"
        ]
        payload["operating_envelope_profile"] = profile
        payload["observed_values"].pop("signal_score_drift")

        report = evaluate_operating_envelope(
            OperatingEnvelopeEvaluationRequest.from_dict(payload)
        )

        self.assertEqual(OperatingEnvelopeStatus.GREEN.value, report.status)
        self.assertEqual("OPERATING_ENVELOPE_GREEN", report.reason_code)

    def test_session_profile_must_cover_all_required_session_classes(self) -> None:
        request = build_request()
        session_profile = request.session_conditioned_risk_profile
        self.assertIsNotNone(session_profile)
        if session_profile is None:
            self.fail("fixture request must carry a session-conditioned risk profile")
        truncated = session_profile.to_dict()
        truncated["rules"] = [
            rule
            for rule in truncated["rules"]
            if rule["session_class"] != REQUIRED_SESSION_CLASSES[-1]
        ]
        errors = validate_operating_envelope_profile(
            request.operating_envelope_profile,
            SessionConditionedRiskProfile.from_dict(truncated),
        )

        self.assertTrue(errors)
        self.assertIn(
            "session-conditioned risk profile: missing required classes: degraded_data",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
