"""Smoke runner for mandatory paper and shadow-live stage policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parents[1]
if TYPE_CHECKING:
    from shared.policy.paper_shadow_stage_policy import PaperShadowStagePolicyRequest

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "shared"
    / "fixtures"
    / "policy"
    / "paper_shadow_stage_policy_cases.json"
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


def apply_objective_mutations(
    payload: dict[str, object],
    mutations: dict[str, dict[str, dict[str, object]]],
) -> dict[str, object]:
    mutated = dict(payload)
    for field_name in ("paper_objectives", "shadow_live_objectives"):
        if field_name not in mutations:
            continue
        objective_mutations = mutations[field_name]
        records = []
        for record in mutated.get(field_name, []):
            updated = dict(record)
            record_mutation = objective_mutations.get(str(updated["objective_id"]))
            if record_mutation:
                updated.update(record_mutation)
            records.append(updated)
        mutated[field_name] = records
    return mutated


def _load_policy_api() -> tuple[type["PaperShadowStagePolicyRequest"], object]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from shared.policy.paper_shadow_stage_policy import (
        PaperShadowStagePolicyRequest,
        evaluate_paper_shadow_stage_policy,
    )

    return PaperShadowStagePolicyRequest, evaluate_paper_shadow_stage_policy


def build_request(
    fixture: dict[str, object], case_id: str
) -> "PaperShadowStagePolicyRequest":
    request_cls, _ = _load_policy_api()
    case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    payload["case_id"] = case_id
    payload = apply_objective_mutations(payload, dict(case.get("objective_mutations", {})))
    return request_cls.from_dict(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the paper and shadow-live stage policy smoke workflow."
    )
    parser.add_argument("--case-id", required=True, help="Fixture case id to evaluate")
    parser.add_argument("--output", type=Path, help="Optional path to write the full JSON report")
    args = parser.parse_args()

    fixture = load_fixture()
    request = build_request(fixture, args.case_id)
    _, evaluate = _load_policy_api()
    report = evaluate(request)
    payload = report.to_dict()

    if args.output:
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "case_id": args.case_id,
                "requested_lane": report.requested_lane,
                "status": report.status,
                "reason_code": report.reason_code,
                "requested_lane_permitted": report.requested_lane_permitted,
                "live_activation_permitted": report.live_activation_permitted,
                "paper_stage_complete": report.paper_stage_complete,
                "shadow_live_stage_complete": report.shadow_live_stage_complete,
                "overnight_evidence_complete": report.overnight_evidence_complete,
                "retained_artifact_ids": report.retained_artifact_ids,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
