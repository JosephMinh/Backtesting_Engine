from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.failure_path_drills import (
    FailurePathDrillRequest,
    evaluate_failure_path_drill,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "failure_path_drills_cases.json"
)


def load_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def build_request(payload: dict[str, object]) -> FailurePathDrillRequest:
    return FailurePathDrillRequest.from_dict(payload)


def drill_reports(
    fixture: dict[str, object], case_id: str | None = None
) -> list[dict[str, object]]:
    cases = fixture["drill_cases"]
    if case_id is not None:
        cases = [case for case in cases if case["case_id"] == case_id]
    return [
        evaluate_failure_path_drill(
            case["case_id"],
            build_request(case["payload"]),
        ).to_dict()
        for case in cases
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the 11.5 failure-path drill smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named drill case instead of the full fixture set.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    reports = {"failure_path_drill_reports": drill_reports(fixture, args.case_id)}
    if args.case_id is not None and not reports["failure_path_drill_reports"]:
        raise SystemExit(f"unknown case id: {args.case_id}")

    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
