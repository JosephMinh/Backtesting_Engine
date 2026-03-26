from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.policy.foundation_harness import (
    FoundationHarnessRequest,
    evaluate_foundation_harness,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "foundation_harness_cases.json"
)


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["cases"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the phase-0 foundation smoke harness over seeded fixture cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of all fixture cases.",
    )
    args = parser.parse_args()

    cases = load_cases()
    if args.case_id is not None:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        if not cases:
            raise SystemExit(f"unknown case id: {args.case_id}")

    reports = []
    for payload in cases:
        request = FoundationHarnessRequest.from_dict(payload["request"])
        reports.append(evaluate_foundation_harness(request).to_dict())

    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
