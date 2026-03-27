from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    from shared.policy.deployment_packets import BundleReadinessRecord, DeploymentInstance
    from shared.policy.readiness_revocation import (
        DependencyPropagationRequest,
        EmergencyWithdrawalReviewRequest,
    )
    from shared.policy.release_certification import ReleaseCorrectionEvent

FIXTURE_PATH = (
    PROJECT_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "readiness_revocation_cases.json"
)


def load_fixture() -> dict[str, object]:
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


def build_readiness(overrides: dict[str, object] | None = None) -> BundleReadinessRecord:
    from shared.policy.deployment_packets import BundleReadinessRecord

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
    from shared.policy.deployment_packets import DeploymentInstance

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


def build_correction_event(
    overrides: dict[str, object] | None = None,
) -> ReleaseCorrectionEvent:
    from shared.policy.release_certification import ReleaseCorrectionEvent

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
                "reason_bundle": "default dependent update",
            }
        ],
        "justification": "default correction impact",
        "recorded_at_utc": "2026-03-27T00:00:00+00:00",
    }
    payload = deep_merge(payload, overrides or {})
    return ReleaseCorrectionEvent.from_dict(payload)


def build_dependency_request(case: dict[str, object]) -> DependencyPropagationRequest:
    from shared.policy.readiness_revocation import DependencyPropagationRequest

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
    from shared.policy.readiness_revocation import EmergencyWithdrawalReviewRequest

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


def dependency_reports(
    fixture: dict[str, object],
    case_id: str | None = None,
) -> list[dict[str, object]]:
    from shared.policy.readiness_revocation import evaluate_dependency_propagation

    cases = fixture["dependency_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        evaluate_dependency_propagation(build_dependency_request(case)).to_dict()
        for case in cases
    ]


def withdrawal_reports(
    fixture: dict[str, object],
    case_id: str | None = None,
) -> list[dict[str, object]]:
    from shared.policy.readiness_revocation import evaluate_emergency_withdrawal_review

    cases = fixture["withdrawal_review_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        evaluate_emergency_withdrawal_review(build_withdrawal_request(case)).to_dict()
        for case in cases
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.5 readiness revocation smoke harness."
    )
    parser.add_argument(
        "--flow",
        choices=("dependency", "withdrawal", "all"),
        default="all",
        help="Select which readiness-revocation scenario family to run.",
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of the full selected set.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional directory where one JSON report per case will be written.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    reports: list[dict[str, object]] = []
    if args.flow in {"dependency", "all"}:
        reports.extend(dependency_reports(fixture, args.case_id))
    if args.flow in {"withdrawal", "all"}:
        reports.extend(withdrawal_reports(fixture, args.case_id))

    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for report in reports:
            output_path = output_dir / f"{report['case_id']}.json"
            output_path.write_text(
                json.dumps(report, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
