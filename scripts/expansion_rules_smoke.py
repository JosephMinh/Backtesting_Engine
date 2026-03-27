"""Smoke runner for the post-v1 expansion rules contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from shared.policy.expansion_rules import evaluate_expansion_rules_case

    parser = argparse.ArgumentParser(
        description="Run the post-v1 expansion rules smoke workflow."
    )
    parser.add_argument("--case-id", required=True, help="Fixture case id to evaluate")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory where the full JSON report should be written.",
    )
    args = parser.parse_args()

    report = evaluate_expansion_rules_case(args.case_id)
    payload = report.to_dict()

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{args.case_id}.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "case_id": report.case_id,
                "status": report.status,
                "reason_code": report.reason_code,
                "approved_rule_ids": report.approved_rule_ids,
                "blocked_rule_ids": report.blocked_rule_ids,
                "missing_requirement_ids": report.missing_requirement_ids,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
