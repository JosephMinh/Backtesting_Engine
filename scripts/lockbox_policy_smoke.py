from __future__ import annotations

import argparse
import json
from functools import cache
from pathlib import Path

from shared.policy.evaluation_protocol import (
    EvaluationProtocolRequest,
    evaluate_evaluation_protocol,
)
from shared.policy.lockbox_policy import LockboxPolicyRequest, evaluate_lockbox_policy

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


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


@cache
def baseline_evaluation_protocol_report() -> dict[str, object]:
    with EVALUATION_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        evaluation_fixture = json.load(fixture_file)
    request = EvaluationProtocolRequest.from_dict(
        dict(evaluation_fixture["shared_request_defaults"])
    )
    return evaluate_evaluation_protocol(request).to_dict()


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 6.4 lockbox-policy smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of all fixture cases.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    cases = fixture["cases"]
    if args.case_id is not None:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        if not cases:
            raise SystemExit(f"unknown case id: {args.case_id}")

    reports = []
    for case in cases:
        payload = dict(fixture["shared_request_defaults"])
        payload["evaluation_protocol_report"] = baseline_evaluation_protocol_report()
        payload = deep_merge(payload, case["overrides"])
        request = LockboxPolicyRequest.from_dict(payload)
        reports.append(evaluate_lockbox_policy(request).to_dict())

    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
