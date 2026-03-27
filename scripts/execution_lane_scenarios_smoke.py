from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURE_PATH = (
    REPO_ROOT
    / "shared"
    / "fixtures"
    / "policy"
    / "execution_lane_scenarios_cases.json"
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


def main() -> int:
    from shared.policy.execution_lane_scenarios import (
        ExecutionLaneScenarioRequest,
        evaluate_execution_lane_scenario,
    )

    parser = argparse.ArgumentParser(
        description="Run the 11.9 execution-lane scenario suite over seeded cases."
    )
    parser.add_argument(
        "--case-id",
        help="Run only the named case id instead of all fixture cases.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional directory for writing one JSON report per executed case.",
    )
    args = parser.parse_args()

    fixture = load_fixture()
    cases = list(fixture["cases"])
    if args.case_id is not None:
        cases = [case for case in cases if case["case_id"] == args.case_id]
        if not cases:
            raise SystemExit(f"unknown case id: {args.case_id}")

    reports = []
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    for case in cases:
        payload = deep_merge(dict(fixture["shared_request_defaults"]), dict(case["overrides"]))
        payload["case_id"] = case["case_id"]
        request = ExecutionLaneScenarioRequest.from_dict(payload)
        report = evaluate_execution_lane_scenario(request).to_dict()
        reports.append(report)
        if output_dir is not None:
            (output_dir / f"{case['case_id']}.json").write_text(
                json.dumps(report, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
