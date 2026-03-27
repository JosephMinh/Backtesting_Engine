"""Contract tests for readiness revocation propagation and withdrawal review."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shared.policy.deployment_packets import BundleReadinessRecord, DeploymentInstance
from shared.policy.readiness_revocation import (
    VALIDATION_ERRORS,
    DependencyPropagationRequest,
    EmergencyWithdrawalReviewRequest,
    evaluate_dependency_propagation,
    evaluate_emergency_withdrawal_review,
)
from shared.policy.release_certification import ReleaseCorrectionEvent

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "readiness_revocation_cases.json"
)
SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "readiness_revocation_smoke.py"
)


def load_cases() -> dict[str, object]:
    try:
        with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
        raise AssertionError(f"readiness revocation fixture failed to load: {exc}") from exc


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def build_readiness(overrides: dict[str, object] | None = None) -> BundleReadinessRecord:
    payload = {
        "bundle_readiness_record_id": "bundle_readiness_record_gold_001",
        "candidate_bundle_id": "candidate_bundle_gold_core_candidate_bundle_sha256_001",
        "target_account_binding_id": "account_binding_live_gold_001",
        "policy_bundle_hash": "policy_bundle_hash_gold_001",
        "account_risk_profile_id": "account_risk_profile_gold_001",
        "broker_capability_descriptor_id": "broker_capability_descriptor_gold_001",
        "approved_data_profile_release_id": "data_profile_release_gold_2026q1_v1",
        "current_fee_schedule_snapshot_id": "fee_schedule_snapshot_gold_001",
        "current_margin_snapshot_id": "margin_snapshot_gold_001",
        "freshness_evidence_ids": ["freshness_evidence_001"],
        "lifecycle_state": "LIVE_ELIGIBLE",
        "approval_history_ids": ["approval_history_001"],
    }
    payload = deep_merge(payload, overrides or {})
    return BundleReadinessRecord.from_dict(payload)


def build_deployment(
    readiness: BundleReadinessRecord,
    overrides: dict[str, object] | None = None,
) -> DeploymentInstance:
    payload = {
        "deployment_instance_id": "deployment_live_gold_default",
        "lane": "live",
        "target_account_binding_id": readiness.target_account_binding_id,
        "candidate_bundle_id": readiness.candidate_bundle_id,
        "bundle_readiness_record_id": readiness.bundle_readiness_record_id,
        "active_promotion_packet_id": "promotion_packet_gold_live_v1",
        "session_readiness_packet_ids": ["session_readiness_gold_001"],
        "runtime_sequence_number": 42,
        "operator_action_ids": ["operator_action_default"],
        "start_event_id": "deployment_start_event_001",
        "stop_event_id": None,
        "withdrawal_event_id": "withdrawal_event_default",
        "recovery_event_ids": [],
        "lifecycle_state": "WITHDRAWN",
    }
    payload = deep_merge(payload, overrides or {})
    return DeploymentInstance.from_dict(payload)


def build_correction_event(overrides: dict[str, object] | None = None) -> ReleaseCorrectionEvent:
    payload = {
        "correction_event_id": "correction_event_default",
        "release_kind": "dataset_release",
        "release_id": "dataset_release_gold_2026q1_v1",
        "certified_vendor_revision_watermark": "vendor_revision_2026-03-20",
        "corrected_vendor_revision_watermark": "vendor_revision_2026-03-25",
        "semantic_impact_diff_hash": "semantic_diff_hash_gold_001",
        "impact_class": "recert_required",
        "preserves_prior_reproducibility": False,
        "superseding_release_id": "dataset_release_gold_2026q1_v2",
        "dependent_updates": [
            {
                "surface_kind": "bundle_readiness_record",
                "surface_id": "bundle_readiness_record_gold_001",
                "action": "recertify",
                "reason_bundle": "default dependent update"
            }
        ],
        "justification": "default correction impact",
        "recorded_at_utc": "2026-03-27T00:00:00+00:00"
    }
    payload = deep_merge(payload, overrides or {})
    return ReleaseCorrectionEvent.from_dict(payload)


def build_dependency_request(case: dict[str, object]) -> DependencyPropagationRequest:
    readiness = build_readiness(dict(case.get("readiness_overrides", {})))
    active_deployment = None
    if "active_deployment_overrides" in case:
        active_deployment = build_deployment(
            readiness,
            dict(case.get("active_deployment_overrides", {})),
        )
    correction_event = None
    if "correction_event_overrides" in case:
        correction_event = build_correction_event(
            dict(case.get("correction_event_overrides", {}))
        )
    payload = {
        "case_id": case["case_id"],
        "readiness_record": readiness.to_dict(),
        "dependency_surface_kind": case["dependency_surface_kind"],
        "dependency_surface_id": case["dependency_surface_id"],
        "dependency_lifecycle_state": case.get("dependency_lifecycle_state"),
        "correction_event": (
            correction_event.to_dict() if correction_event is not None else None
        ),
        "active_deployment": (
            active_deployment.to_dict() if active_deployment is not None else None
        ),
        "reviewed_waiver_id": case.get("reviewed_waiver_id"),
        "operator_reason_bundle": case.get("operator_reason_bundle", []),
    }
    return DependencyPropagationRequest.from_dict(payload)


def build_withdrawal_request(case: dict[str, object]) -> EmergencyWithdrawalReviewRequest:
    readiness = build_readiness(dict(case.get("readiness_overrides", {})))
    deployment = build_deployment(
        readiness,
        dict(case.get("deployment_overrides", {})),
    )
    payload = {
        "case_id": case["case_id"],
        "readiness_record": readiness.to_dict(),
        "deployment": deployment.to_dict(),
        "trigger_source": case["trigger_source"],
        "operator_action_id": case["operator_action_id"],
        "incident_reference_id": case["incident_reference_id"],
        "withdrawn_at_utc": case["withdrawn_at_utc"],
        "review_completed_at_utc": case.get("review_completed_at_utc"),
        "review_decision_state": case.get("review_decision_state"),
        "review_rationale": case.get("review_rationale"),
    }
    return EmergencyWithdrawalReviewRequest.from_dict(payload)


def decode_json_object(payload: str, *, label: str) -> dict[str, object]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise AssertionError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{label} must decode to a JSON object")
    return decoded


class ReadinessRevocationContractTest(unittest.TestCase):
    def test_validation_contract_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)

    def test_dependency_request_round_trip_preserves_correction_event(self) -> None:
        case = load_cases()["dependency_cases"][0]
        request = build_dependency_request(case)
        reparsed = DependencyPropagationRequest.from_json(request.to_json())

        self.assertEqual(request.case_id, reparsed.case_id)
        self.assertEqual(
            request.readiness_record.bundle_readiness_record_id,
            reparsed.readiness_record.bundle_readiness_record_id,
        )
        self.assertIsNotNone(reparsed.correction_event)

    def test_withdrawal_request_round_trip_preserves_review_decision(self) -> None:
        case = load_cases()["withdrawal_review_cases"][0]
        request = build_withdrawal_request(case)
        reparsed = EmergencyWithdrawalReviewRequest.from_json(request.to_json())

        self.assertEqual(request.case_id, reparsed.case_id)
        self.assertEqual(
            request.deployment.deployment_instance_id,
            reparsed.deployment.deployment_instance_id,
        )
        self.assertEqual(request.review_decision_state, reparsed.review_decision_state)

    def test_dependency_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["dependency_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_dependency_propagation(build_dependency_request(case))

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected_propagation_reason_code"],
                    report.propagation_reason_code,
                )
                self.assertEqual(
                    case["expected_resulting_readiness_state"],
                    report.resulting_readiness_state,
                )
                self.assertEqual(
                    case["expected_live_deployment_action"],
                    report.live_deployment_action,
                )

    def test_withdrawal_fixture_cases_emit_expected_reports(self) -> None:
        for case in load_cases()["withdrawal_review_cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate_emergency_withdrawal_review(
                    build_withdrawal_request(case)
                )

                self.assertEqual(case["expected_status"], report.status)
                self.assertEqual(case["expected_reason_code"], report.reason_code)
                self.assertEqual(
                    case["expected_resulting_readiness_state"],
                    report.resulting_readiness_state,
                )
                self.assertEqual(
                    case["expected_reviewed_within_sla"],
                    report.reviewed_within_sla,
                )

    def test_reports_include_manifest_logs_and_reason_bundle(self) -> None:
        dep_case = next(
            case
            for case in load_cases()["dependency_cases"]
            if case["case_id"] == "revoked_dependency_without_waiver_forces_live_withdrawal"
        )
        dep_report = evaluate_dependency_propagation(
            build_dependency_request(dep_case)
        ).to_dict()
        manifest = dep_report["artifact_manifest"]
        self.assertTrue(
            {
                "manifest_id",
                "generated_at_utc",
                "retention_class",
                "contains_secrets",
                "redaction_policy",
                "artifacts",
            }.issubset(manifest.keys())
        )
        self.assertGreaterEqual(len(manifest["artifacts"]), 3)
        self.assertGreaterEqual(len(dep_report["structured_logs"]), 3)
        self.assertTrue(
            {
                "summary",
                "gate_summary",
                "rule_trace",
                "remediation_hints",
            }.issubset(dep_report["operator_reason_bundle"].keys())
        )

        withdrawal_case = next(
            case
            for case in load_cases()["withdrawal_review_cases"]
            if case["case_id"] == "guardian_withdrawal_review_can_revoke_readiness"
        )
        withdrawal_report = evaluate_emergency_withdrawal_review(
            build_withdrawal_request(withdrawal_case)
        ).to_dict()
        self.assertGreaterEqual(len(withdrawal_report["structured_logs"]), 3)
        for record in withdrawal_report["structured_logs"]:
            self.assertTrue(
                {
                    "schema_version",
                    "event_type",
                    "plane",
                    "event_id",
                    "recorded_at_utc",
                    "correlation_id",
                    "decision_trace_id",
                    "reason_code",
                    "reason_summary",
                    "referenced_ids",
                    "redacted_fields",
                    "omitted_fields",
                    "artifact_manifest",
                }.issubset(record.keys())
            )

    def test_smoke_script_emits_selected_dependency_case_and_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            result = subprocess.run(  # nosec B603 - trusted test harness invocation
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--flow",
                    "dependency",
                    "--case-id",
                    "revoked_dependency_with_reviewed_waiver_can_continue",
                    "--output-dir",
                    output_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed = decode_json_object(result.stdout, label="readiness revocation smoke")
            self.assertEqual(1, len(parsed["reports"]))
            self.assertEqual(
                "READINESS_DEPENDENCY_WAIVER_APPLIED",
                parsed["reports"][0]["reason_code"],
            )
            written = (
                Path(output_dir)
                / "revoked_dependency_with_reviewed_waiver_can_continue.json"
            )
            self.assertTrue(written.exists())


if __name__ == "__main__":
    unittest.main()
