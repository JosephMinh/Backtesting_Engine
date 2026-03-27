from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.evaluation_protocol import (
    EvaluationProtocolRequest,
    evaluate_evaluation_protocol,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "evaluation_protocol_cases.json"
)


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["cases"]


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 6.3 evaluation-protocol smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of all fixture cases.",
    )
    args = parser.parse_args()

    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        fixture = json.load(fixture_file)
    cases = fixture["cases"]
    if args.case_id is not None:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        if not cases:
            raise SystemExit(f"unknown case id: {args.case_id}")

    reports = []
    for case in cases:
        payload = deep_merge(dict(fixture["shared_request_defaults"]), case["overrides"])
        request = EvaluationProtocolRequest.from_dict(payload)
        reports.append(evaluate_evaluation_protocol(request).to_dict())

    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
