from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.deployment_packets import (
    CandidateBundle,
    CandidateBundleFreezeRegistration,
    CandidateBundleReplayContext,
    build_candidate_bundle_freeze_registration,
    validate_candidate_bundle,
    validate_candidate_bundle_freeze_registration,
    validate_candidate_bundle_load,
    validate_candidate_bundle_replay_readiness,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "deployment_packets.json"
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


def candidate_payload_by_case(
    fixture: dict[str, object], case_id: str
) -> dict[str, object]:
    candidate_case = next(
        case for case in fixture["candidate_cases"] if case["case_id"] == case_id
    )
    return dict(candidate_case["payload"])


def build_candidate(payload: dict[str, object]) -> CandidateBundle:
    return CandidateBundle.from_dict(payload)


def build_freeze_registration(
    candidate: CandidateBundle, overrides: dict[str, object] | None = None
) -> CandidateBundleFreezeRegistration:
    registration = build_candidate_bundle_freeze_registration(
        candidate,
        registration_log_id="candidate_bundle_freeze_log_default",
        registration_artifact_id="signed_manifest_candidate_bundle_default",
        correlation_id="corr-candidate-freeze-default",
        operator_reason_bundle=("candidate bundle freeze recorded",),
    )
    payload = deep_merge(registration.to_dict(), overrides or {})
    return CandidateBundleFreezeRegistration.from_dict(payload)


def build_replay_context(
    registration: CandidateBundleFreezeRegistration,
    overrides: dict[str, object] | None = None,
) -> CandidateBundleReplayContext:
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


def candidate_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["candidate_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        validate_candidate_bundle(case["case_id"], build_candidate(case["payload"])).to_dict()
        for case in cases
    ]


def candidate_freeze_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["candidate_freeze_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    reports = []
    for case in cases:
        candidate = build_candidate(candidate_payload_by_case(fixture, case["candidate_case_id"]))
        registration = build_freeze_registration(candidate, case.get("registration_overrides"))
        reports.append(
            validate_candidate_bundle_freeze_registration(
                case["case_id"],
                candidate,
                registration,
            ).to_dict()
        )
    return reports


def candidate_load_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["candidate_load_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    reports = []
    for case in cases:
        baseline_candidate = build_candidate(
            candidate_payload_by_case(fixture, case["candidate_case_id"])
        )
        registration = build_freeze_registration(
            baseline_candidate,
            case.get("registration_overrides"),
        )
        candidate = build_candidate(
            deep_merge(
                candidate_payload_by_case(fixture, case["candidate_case_id"]),
                case.get("bundle_overrides", {}),
            )
        )
        reports.append(
            validate_candidate_bundle_load(
                case["case_id"],
                candidate,
                registration,
            ).to_dict()
        )
    return reports


def candidate_replay_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["candidate_replay_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    reports = []
    for case in cases:
        candidate = build_candidate(candidate_payload_by_case(fixture, case["candidate_case_id"]))
        registration = build_freeze_registration(
            candidate,
            case.get("registration_overrides"),
        )
        replay_context = build_replay_context(
            registration,
            case.get("replay_context_overrides"),
        )
        reports.append(
            validate_candidate_bundle_replay_readiness(
                case["case_id"],
                candidate,
                registration,
                replay_context,
            ).to_dict()
        )
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.1 candidate bundle smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of all candidate freeze/load/replay cases.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    grouped_reports = {
        "candidate_reports": candidate_reports(fixture, args.case_id),
        "candidate_freeze_reports": candidate_freeze_reports(fixture, args.case_id),
        "candidate_load_reports": candidate_load_reports(fixture, args.case_id),
        "candidate_replay_reports": candidate_replay_reports(fixture, args.case_id),
    }
    if args.case_id is not None and not any(grouped_reports.values()):
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(grouped_reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
