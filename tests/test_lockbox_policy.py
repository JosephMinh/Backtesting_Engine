"""Contract tests for lockbox access, finalist bounds, and contamination handling."""

from __future__ import annotations

import json
import unittest
from functools import cache
from pathlib import Path
from typing import Any

from shared.policy.evaluation_protocol import (
    EvaluationProtocolRequest,
    evaluate_evaluation_protocol,
)
from shared.policy.lockbox_policy import (
    LOCKBOX_POLICY_RULE_IDS,
    VALIDATION_ERRORS,
    LockboxDecision,
    LockboxPolicyReport,
    LockboxPolicyRequest,
    LockboxPolicyStatus,
    evaluate_lockbox_policy,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "lockbox_policy_cases.json"
)
EVALUATION_FIXTURE_PATH = (
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


@cache
def baseline_evaluation_protocol_report() -> dict[str, Any]:
    with EVALUATION_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        evaluation_fixture = json.load(fixture_file)
    request = EvaluationProtocolRequest.from_dict(
        dict(evaluation_fixture["shared_request_defaults"])
    )
    return evaluate_evaluation_protocol(request).to_dict()


def build_request(overrides: dict[str, Any] | None = None) -> LockboxPolicyRequest:
    fixture = load_cases()
    payload = dict(fixture["shared_request_defaults"])
    payload["evaluation_protocol_report"] = baseline_evaluation_protocol_report()
    payload = deep_merge(payload, overrides or {})
    return LockboxPolicyRequest.from_dict(payload)


class LockboxPolicyCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_rule_catalog_matches_plan(self) -> None:
        self.assertEqual(
            (
                "evaluation_protocol_lockbox_ready",
                "lockbox_run_recorded",
                "bounded_finalist_count",
                "policy_controlled_access",
                "no_ranking_surface_access",
                "contamination_incident_handling",
                "retained_lockbox_artifacts",
            ),
            LOCKBOX_POLICY_RULE_IDS,
        )


class LockboxPolicyFixtureTests(unittest.TestCase):
    def test_fixture_cases_match_expected_reports(self) -> None:
        fixture = load_cases()
        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_lockbox_policy(build_request(case["overrides"]))
                expected = case["expected"]

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["triggered_rule_ids"]),
                    report.triggered_rule_ids,
                )
                self.assertEqual(
                    tuple(expected["contamination_incident_ids"]),
                    report.contamination_incident_ids,
                )

    def test_contamination_restart_retains_reviewable_incident_ids(self) -> None:
        case = next(
            case
            for case in load_cases()["cases"]
            if case["case_id"] == "contamination_requires_restart"
        )
        report = evaluate_lockbox_policy(build_request(case["overrides"]))

        self.assertEqual(LockboxPolicyStatus.VIOLATION.value, report.status)
        self.assertEqual(LockboxDecision.RESTART_CYCLE.value, report.decision)
        self.assertEqual(("lockbox-incident-001",), report.contamination_incident_ids)
        self.assertIn("review-lockbox-incident-001", report.retained_artifact_ids)

    def test_ep08_failure_blocks_lockbox_entry(self) -> None:
        request = build_request()
        evaluation_payload = request.evaluation_protocol_report.to_dict()
        evaluation_payload["status"] = "violation"
        evaluation_payload["reason_code"] = "EVALUATION_PROTOCOL_LOCKBOX_CONTROLS_INCOMPLETE"
        evaluation_payload["triggered_check_ids"] = ["EP08"]
        evaluation_payload["candidate_freeze_ready"] = False
        for check in evaluation_payload["check_results"]:
            if check["check_id"] == "EP08":
                check["passed"] = False
                check["status"] = "violation"
                check["reason_code"] = "EVALUATION_PROTOCOL_LOCKBOX_CONTROLS_INCOMPLETE"
                check["diagnostic"] = "Lockbox readiness is incomplete."
                check["remediation"] = "Record bounded lockbox access before proceeding."
        payload = request.to_dict()
        payload["evaluation_protocol_report"] = evaluation_payload

        report = evaluate_lockbox_policy(LockboxPolicyRequest.from_dict(payload))

        self.assertEqual(LockboxPolicyStatus.VIOLATION.value, report.status)
        self.assertEqual(LockboxDecision.HOLD.value, report.decision)
        self.assertEqual("LOCKBOX_PROTOCOL_PREREQUISITE_MISSING", report.reason_code)
        self.assertEqual(("LP01",), report.triggered_rule_ids)

    def test_report_json_round_trip_is_lossless(self) -> None:
        report = evaluate_lockbox_policy(build_request())
        self.assertEqual(report, LockboxPolicyReport.from_json(report.to_json()))

    def test_invalid_json_payloads_raise_value_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "lockbox_policy_request: invalid JSON payload"
        ):
            LockboxPolicyRequest.from_json("not-json")

        with self.assertRaisesRegex(
            ValueError, "lockbox_policy_report: invalid JSON payload"
        ):
            LockboxPolicyReport.from_json("not-json")

    def test_invalid_request_returns_invalid_report(self) -> None:
        request = build_request({"selected_candidate_id": "candidate-not-in-finalists"})

        report = evaluate_lockbox_policy(request)

        self.assertEqual(LockboxPolicyStatus.INVALID.value, report.status)
        self.assertEqual(LockboxDecision.HOLD.value, report.decision)
        self.assertEqual("LOCKBOX_POLICY_REQUEST_INVALID", report.reason_code)
        self.assertEqual((), report.triggered_rule_ids)
        self.assertEqual((), report.check_results)


if __name__ == "__main__":
    unittest.main()
