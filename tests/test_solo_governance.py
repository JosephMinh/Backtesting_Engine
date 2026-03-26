from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.policy_engine import PolicyDecisionCategory
from shared.policy.solo_governance import (
    VALIDATION_ERRORS,
    GovernanceWaiverRecord,
    SoloGovernanceReport,
    SoloGovernanceRequest,
    SoloGovernanceStatus,
    evaluate_solo_governance,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "solo_governance_cases.json"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"solo governance fixture failed to load: {exc}") from exc


def failed_reason_codes(report: SoloGovernanceReport) -> list[str]:
    return [
        check.reason_code
        for check in report.decision_trace
        if not check.passed
    ]


class SoloGovernanceContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_request_round_trip_preserves_payload(self) -> None:
        request = SoloGovernanceRequest.from_dict(load_cases()["cases"][0]["request"])
        self.assertEqual(request, SoloGovernanceRequest.from_json(request.to_json()))

    def test_report_round_trip_preserves_payload(self) -> None:
        request = SoloGovernanceRequest.from_dict(load_cases()["cases"][0]["request"])
        report = evaluate_solo_governance(request)
        self.assertEqual(report, SoloGovernanceReport.from_json(report.to_json()))

    def test_fixture_cases_emit_expected_reports(self) -> None:
        for payload in load_cases()["cases"]:
            with self.subTest(case_id=payload["case_id"]):
                request = SoloGovernanceRequest.from_dict(payload["request"])
                report = evaluate_solo_governance(request)

                self.assertEqual(payload["expected_status"], report.status)
                self.assertEqual(payload["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    payload["expected_governance_path"],
                    report.governance_path,
                )
                self.assertEqual(
                    payload["expected_failed_reason_codes"],
                    failed_reason_codes(report),
                )

    def test_waiver_record_converts_to_policy_waiver(self) -> None:
        request = SoloGovernanceRequest.from_dict(load_cases()["cases"][0]["request"])
        self.assertIsNotNone(request.waiver)
        waiver = GovernanceWaiverRecord.from_dict(request.waiver.to_dict())
        policy_waiver = waiver.to_policy_waiver()

        self.assertEqual(waiver.waiver_id, policy_waiver.waiver_id)
        self.assertEqual(waiver.approved_by, policy_waiver.approved_by)
        self.assertEqual(waiver.expires_at_utc, policy_waiver.expires_at_utc)
        self.assertTrue(policy_waiver.is_active("2026-03-26T18:00:00+00:00"))
        self.assertTrue(
            policy_waiver.matches(
                category=PolicyDecisionCategory.SESSION_READINESS,
                rule_id="bundle_readiness_record",
                reason_code="BUNDLE_READINESS_FRESHNESS_EVIDENCE_REQUIRED",
                at_utc="2026-03-26T18:00:00+00:00",
            )
        )

    def test_report_is_structured_and_operator_readable(self) -> None:
        request = SoloGovernanceRequest.from_dict(load_cases()["cases"][3]["request"])
        report = evaluate_solo_governance(request)
        payload = report.to_dict()

        self.assertTrue(
            {
                "case_id",
                "status",
                "reason_code",
                "governance_path",
                "operator_id",
                "policy_bundle_hash",
                "cooling_off_satisfied",
                "cooling_off_minutes_observed",
                "waiver_active",
                "incident_closed",
                "attestation_step_ids",
                "checklist_artifact_ids",
                "audit_record_ids",
                "decision_trace",
                "explanation",
                "remediation",
                "timestamp",
            }.issubset(payload.keys())
        )
        self.assertEqual(SoloGovernanceStatus.PASS.value, report.status)
        self.assertIn("corrective-action", report.explanation)
        self.assertEqual(6, len(report.decision_trace))
        self.assertIn("incident_restore_review_001", report.audit_record_ids)


if __name__ == "__main__":
    unittest.main()
