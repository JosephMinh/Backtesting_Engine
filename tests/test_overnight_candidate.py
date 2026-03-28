from __future__ import annotations

import json
import unittest
from copy import deepcopy
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

    def test_request_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = build_request().to_dict()
        invalid_cases = (
            (
                "allow_overnight_truthy_string",
                lambda payload: payload.__setitem__("allow_overnight", "true"),
                "allow_overnight must be a boolean",
            ),
            (
                "schema_version_bool",
                lambda payload: payload.__setitem__("schema_version", True),
                "overnight_candidate_request: schema_version must be an integer",
            ),
            (
                "evaluated_at_naive_timestamp",
                lambda payload: payload.__setitem__(
                    "evaluated_at_utc",
                    "2026-03-27T16:00:00",
                ),
                "evaluated_at_utc must be timezone-aware",
            ),
            (
                "overnight_candidate_class_invalid",
                lambda payload: payload.__setitem__(
                    "overnight_candidate_class",
                    "unsupported",
                ),
                "overnight_candidate_class must be a valid overnight candidate class",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    OvernightCandidateRequest.from_dict(payload)

    def test_nested_request_loader_rejects_invalid_record_values(self) -> None:
        base_payload = build_request().to_dict()
        invalid_cases = (
            (
                "evidence_record_passed_truthy_string",
                lambda payload: payload["evidence_records"][0].__setitem__("passed", "true"),
                "passed must be a boolean",
            ),
            (
                "carry_rule_blocks_new_carry_numeric_truthy",
                lambda payload: payload["carry_restriction_rules"][0].__setitem__(
                    "blocks_new_carry",
                    1,
                ),
                "blocks_new_carry must be a boolean",
            ),
            (
                "margin_check_required_margin_bool",
                lambda payload: payload["session_boundary_margin_checks"][0].__setitem__(
                    "required_margin_usd",
                    True,
                ),
                "required_margin_usd: must be non-negative",
            ),
            (
                "margin_check_boundary_invalid",
                lambda payload: payload["session_boundary_margin_checks"][0].__setitem__(
                    "boundary",
                    "post_close",
                ),
                "boundary must be a valid session boundary",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    OvernightCandidateRequest.from_dict(payload)

    def test_identifier_loaders_reject_non_string_values(self) -> None:
        request_payload = build_request().to_dict()
        invalid_request_cases = (
            (
                "candidate_id_bool",
                lambda payload: payload.__setitem__("candidate_id", False),
                "candidate_id must be a non-empty string",
            ),
            (
                "nested_evidence_artifact_bool",
                lambda payload: payload["evidence_records"][0].__setitem__(
                    "artifact_ids",
                    [False],
                ),
                "artifact_ids\\[\\] must be a non-empty string",
            ),
            (
                "nested_margin_artifact_bool",
                lambda payload: payload["session_boundary_margin_checks"][0].__setitem__(
                    "artifact_id",
                    False,
                ),
                "artifact_id must be a non-empty string",
            ),
        )

        for case_id, mutate, error in invalid_request_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(request_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    OvernightCandidateRequest.from_dict(payload)

    def test_report_loader_rejects_invalid_boundary_values(self) -> None:
        base_payload = evaluate_overnight_candidate(build_request()).to_dict()
        invalid_cases = (
            (
                "status_invalid",
                lambda payload: payload.__setitem__("status", "ready"),
                "status must be a valid overnight candidate status",
            ),
            (
                "allow_overnight_truthy_string",
                lambda payload: payload.__setitem__("allow_overnight", "true"),
                "allow_overnight must be a boolean",
            ),
            (
                "account_fit_status_invalid",
                lambda payload: payload.__setitem__("account_fit_status", "ready"),
                "account_fit_status must be a valid account-fit status",
            ),
            (
                "missing_timestamp",
                lambda payload: payload.pop("timestamp"),
                "timestamp must be an ISO-8601 timestamp string",
            ),
            (
                "naive_evaluated_at_timestamp",
                lambda payload: payload.__setitem__(
                    "evaluated_at_utc",
                    "2026-03-27T16:00:00",
                ),
                "evaluated_at_utc must be timezone-aware",
            ),
            (
                "boundary_result_passed_truthy_string",
                lambda payload: payload["boundary_results"][0].__setitem__("passed", "true"),
                "passed must be a boolean",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(base_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    OvernightCandidateReport.from_dict(payload)

    def test_report_identifier_loaders_reject_non_string_values(self) -> None:
        report_payload = evaluate_overnight_candidate(build_request()).to_dict()
        invalid_cases = (
            (
                "account_fit_case_id_bool",
                lambda payload: payload.__setitem__("account_fit_case_id", False),
                "account_fit_case_id must be a non-empty string",
            ),
            (
                "retained_artifact_bool",
                lambda payload: payload.__setitem__("retained_artifact_ids", [False]),
                "retained_artifact_ids\\[\\] must be a non-empty string",
            ),
            (
                "failed_check_id_bool",
                lambda payload: payload.__setitem__("failed_check_ids", [False]),
                "failed_check_ids\\[\\] must be a non-empty string",
            ),
            (
                "nested_check_artifact_bool",
                lambda payload: payload["check_results"][0].__setitem__("artifact_ids", [False]),
                "artifact_ids\\[\\] must be a non-empty string",
            ),
            (
                "boundary_artifact_bool",
                lambda payload: payload["boundary_results"][0].__setitem__("artifact_id", False),
                "artifact_id must be a non-empty string",
            ),
        )

        for case_id, mutate, error in invalid_cases:
            with self.subTest(case_id=case_id):
                payload = deepcopy(report_payload)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, error):
                    OvernightCandidateReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
