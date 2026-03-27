from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.account_fit_gate import AccountFitRequest, evaluate_account_fit
from shared.policy.overnight_candidate import (
    VALIDATION_ERRORS,
    OvernightCandidateReport,
    OvernightCandidateRequest,
    OvernightCandidateStatus,
    evaluate_overnight_candidate,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "overnight_candidate_cases.json"
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


def build_request(overrides: dict[str, object] | None = None) -> OvernightCandidateRequest:
    fixture = load_cases()
    payload = deep_merge(dict(fixture["shared_request_defaults"]), overrides or {})
    account_fit_request = AccountFitRequest.from_dict(dict(payload.pop("account_fit_request")))
    payload["account_fit_report"] = evaluate_account_fit(account_fit_request).to_dict()
    return OvernightCandidateRequest.from_dict(payload)


class OvernightCandidateCatalogTests(unittest.TestCase):
    def test_contract_has_no_internal_validation_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)


class OvernightCandidateFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["evaluation_cases"]:
            with self.subTest(case_id=case["case_id"]):
                request = build_request(case["overrides"])
                report = evaluate_overnight_candidate(request)
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["failed_check_ids"]),
                    report.failed_check_ids,
                )

                expected_boundary_passes = expected.get("boundary_passes")
                if expected_boundary_passes is not None:
                    self.assertEqual(
                        expected_boundary_passes,
                        {
                            result.boundary: result.passed
                            for result in report.boundary_results
                        },
                    )

    def test_boundary_results_follow_request_order(self) -> None:
        request = build_request()
        report = evaluate_overnight_candidate(request)

        self.assertEqual(
            tuple(check.boundary for check in request.session_boundary_margin_checks),
            tuple(result.boundary for result in report.boundary_results),
        )

    def test_report_round_trip_preserves_check_and_boundary_results(self) -> None:
        report = evaluate_overnight_candidate(build_request())
        reparsed = OvernightCandidateReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)


class OvernightCandidateEdgeCaseTests(unittest.TestCase):
    def test_invalid_carry_action_is_reported_cleanly(self) -> None:
        request = build_request(
            {
                "carry_restriction_rules": [
                    {
                        "trigger_id": "maintenance_window",
                        "action": "totally_invalid_action",
                        "blocks_new_carry": True,
                        "diagnostic": "Broken test action.",
                        "remediation": "Repair the action."
                    }
                ]
            }
        )
        report = evaluate_overnight_candidate(request)

        self.assertEqual(OvernightCandidateStatus.INVALID.value, report.status)
        self.assertEqual("OVERNIGHT_CANDIDATE_REQUEST_INVALID", report.reason_code)

    def test_account_fit_candidate_mismatch_is_invalid(self) -> None:
        request = build_request()
        payload = request.to_dict()
        account_fit_report = dict(payload["account_fit_report"])
        account_fit_report["candidate_id"] = "other_candidate"
        payload["account_fit_report"] = account_fit_report

        report = evaluate_overnight_candidate(OvernightCandidateRequest.from_dict(payload))

        self.assertEqual(OvernightCandidateStatus.INVALID.value, report.status)
        self.assertEqual("OVERNIGHT_CANDIDATE_REQUEST_INVALID", report.reason_code)


if __name__ == "__main__":
    unittest.main()
