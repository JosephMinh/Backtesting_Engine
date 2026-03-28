from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.policy.deployment_packets import (
        CandidateBundle,
        CandidateBundleFreezeRegistration,
        CandidateBundleReplayContext,
    )
    from shared.policy.replay_certification import ReplayCertificationRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_PATH = (
    PROJECT_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "replay_certification_cases.json"
)
DEPLOYMENT_FIXTURE_PATH = (
    PROJECT_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
)


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def load_deployment_fixture() -> dict[str, object]:
    with DEPLOYMENT_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def candidate_payload_by_case(
    deployment_fixture: dict[str, object], case_id: str
) -> dict[str, object]:
    candidate_case = next(
        case for case in deployment_fixture["candidate_cases"] if case["case_id"] == case_id
    )
    return dict(candidate_case["payload"])


def build_candidate(payload: dict[str, object]) -> CandidateBundle:
    from shared.policy.deployment_packets import CandidateBundle

    return CandidateBundle.from_dict(payload)


def build_freeze_registration(
    candidate: CandidateBundle,
    overrides: dict[str, object] | None = None,
) -> CandidateBundleFreezeRegistration:
    from shared.policy.deployment_packets import (
        CandidateBundleFreezeRegistration,
        build_candidate_bundle_freeze_registration,
    )

    registration = build_candidate_bundle_freeze_registration(
        candidate,
        registration_log_id="candidate_bundle_freeze_log_default",
        registration_artifact_id="signed_manifest_candidate_bundle_default",
        correlation_id="corr-replay-certification-default",
        operator_reason_bundle=("candidate bundle freeze recorded",),
    )
    payload = deep_merge(registration.to_dict(), overrides or {})
    return CandidateBundleFreezeRegistration.from_dict(payload)


def build_replay_context(
    registration: CandidateBundleFreezeRegistration,
    overrides: dict[str, object] | None = None,
) -> CandidateBundleReplayContext:
    from shared.policy.deployment_packets import CandidateBundleReplayContext

    payload: dict[str, object] = {
        "replay_context_id": "candidate_bundle_replay_context_default",
        "registration_log_id": registration.registration_log_id,
        "replay_fixture_id": "replay_fixture_candidate_bundle_default",
        "signed_manifest_id": registration.registration_artifact_id,
        "available_artifact_ids": [
            "replay_fixture_candidate_bundle_default",
            registration.registration_artifact_id,
        ],
        "available_feature_contract_hashes": list(registration.feature_contract_hashes),
        "available_signature_ids": list(registration.signature_ids),
        "dependency_manifest_hashes": [registration.dependency_dag_hash],
        "correlation_id": registration.correlation_id,
        "operator_reason_bundle": ["candidate bundle replay context retained"],
    }
    payload = deep_merge(payload, overrides or {})
    return CandidateBundleReplayContext.from_dict(payload)


def build_request(
    case: dict[str, object],
    deployment_fixture: dict[str, object],
) -> ReplayCertificationRequest:
    from shared.policy.replay_certification import ReplayCertificationRequest

    candidate = build_candidate(
        candidate_payload_by_case(deployment_fixture, str(case["candidate_case_id"]))
    )
    registration = build_freeze_registration(
        candidate,
        dict(case.get("registration_overrides", {})),
    )
    replay_context = build_replay_context(
        registration,
        dict(case.get("replay_context_overrides", {})),
    )
    payload = {
        "case_id": case["case_id"],
        "certification_id": case["certification_id"],
        "bundle": candidate.to_dict(),
        "registration": registration.to_dict(),
        "replay_context": replay_context.to_dict(),
        "decision_trace_id": case["decision_trace_id"],
        "expected_signal_trace": case["expected_signal_trace"],
        "actual_signal_trace": case["actual_signal_trace"],
        "expected_order_intent_trace": case["expected_order_intent_trace"],
        "actual_order_intent_trace": case["actual_order_intent_trace"],
        "expected_risk_action_trace": case["expected_risk_action_trace"],
        "actual_risk_action_trace": case["actual_risk_action_trace"],
        "expected_contract_state_trace": case["expected_contract_state_trace"],
        "actual_contract_state_trace": case["actual_contract_state_trace"],
        "expected_freshness_watermark_trace": case[
            "expected_freshness_watermark_trace"
        ],
        "actual_freshness_watermark_trace": case["actual_freshness_watermark_trace"],
        "certification_mode": case.get("certification_mode", "full"),
        "dependency_change_scope": case.get("dependency_change_scope", "none"),
        "prior_certification_id": case.get("prior_certification_id"),
    }
    return ReplayCertificationRequest.from_dict(payload)


def certification_reports(
    fixture: dict[str, object],
    deployment_fixture: dict[str, object],
    case_id: str | None = None,
) -> list[dict[str, object]]:
    from shared.policy.replay_certification import evaluate_replay_certification

    cases = fixture["cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        evaluate_replay_certification(build_request(case, deployment_fixture)).to_dict()
        for case in cases
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.6 deterministic replay certification smoke harness."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named replay-certification case id instead of the full set.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional directory where one JSON report per case will be written.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    deployment_fixture = load_deployment_fixture()
    reports = certification_reports(fixture, deployment_fixture, args.case_id)

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
