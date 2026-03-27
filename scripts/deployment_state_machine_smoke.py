from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.deployment_packets import (
    BundleReadinessRecord,
    DeploymentInstance,
    DeploymentState,
    ReadinessState,
    transition_bundle_readiness_record,
    transition_deployment_instance,
    validate_bundle_readiness_record,
    validate_deployment_instance,
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


def build_readiness(payload: dict[str, object]) -> BundleReadinessRecord:
    return BundleReadinessRecord.from_dict(payload)


def build_deployment(payload: dict[str, object]) -> DeploymentInstance:
    return DeploymentInstance.from_dict(payload)


def readiness_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["readiness_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        validate_bundle_readiness_record(case["case_id"], build_readiness(case["payload"])).to_dict()
        for case in cases
    ]


def readiness_transition_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["readiness_transition_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        transition_bundle_readiness_record(
            case["case_id"],
            build_readiness(case["payload"]),
            ReadinessState(case["to_state"]),
        ).to_dict()
        for case in cases
    ]


def deployment_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["deployment_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        validate_deployment_instance(case["case_id"], build_deployment(case["payload"])).to_dict()
        for case in cases
    ]


def deployment_transition_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["deployment_transition_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        transition_deployment_instance(
            case["case_id"],
            build_deployment(case["payload"]),
            DeploymentState(case["to_state"]),
        ).to_dict()
        for case in cases
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 7.2 deployment state-machine smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named readiness or deployment case instead of the full fixture set.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    grouped_reports = {
        "readiness_reports": readiness_reports(fixture, args.case_id),
        "readiness_transition_reports": readiness_transition_reports(
            fixture, args.case_id
        ),
        "deployment_reports": deployment_reports(fixture, args.case_id),
        "deployment_transition_reports": deployment_transition_reports(
            fixture, args.case_id
        ),
    }
    if args.case_id is not None and not any(grouped_reports.values()):
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(grouped_reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
