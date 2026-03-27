from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_program_closure_helpers():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from shared.policy.program_closure import (
        evaluate_program_closure_case,
        load_program_closure_fixture,
    )

    return evaluate_program_closure_case, load_program_closure_fixture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic program-closure decision walkthroughs."
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Specific case id to run. May be repeated.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory to write each report as JSON.",
    )
    return parser.parse_args()


def selected_case_ids(args: argparse.Namespace) -> list[str]:
    if args.case_ids:
        return list(args.case_ids)
    _, load_program_closure_fixture = _load_program_closure_helpers()
    return [case["case_id"] for case in load_program_closure_fixture()["cases"]]


def main() -> None:
    args = parse_args()
    evaluate_program_closure_case, _ = _load_program_closure_helpers()
    reports = [
        evaluate_program_closure_case(case_id).to_dict()
        for case_id in selected_case_ids(args)
    ]
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for report in reports:
            output_path = args.output_dir / f"{report['case_id']}.json"
            output_path.write_text(
                json.dumps(report, indent=2, sort_keys=True),
                encoding="utf-8",
            )
    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
