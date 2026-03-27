"""Smoke runner for operational-evidence admissibility and promotion exit gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parents[1]
if TYPE_CHECKING:
    from shared.policy.operational_evidence_gate import OperationalEvidenceGateRequest

FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "operational_evidence_gate_cases.json"
)
STAGE_FIXTURE_PATH = (
    REPO_ROOT / "shared" / "fixtures" / "policy" / "paper_shadow_stage_policy_cases.json"
)


def _load_gate_api():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from shared.policy.operational_evidence_gate import (
        OperationalEvidenceGateRequest,
        evaluate_operational_evidence_gate,
    )
    from shared.policy.paper_shadow_stage_policy import (
        PaperShadowStagePolicyRequest,
        evaluate_paper_shadow_stage_policy,
    )

    return (
        OperationalEvidenceGateRequest,
        evaluate_operational_evidence_gate,
        PaperShadowStagePolicyRequest,
        evaluate_paper_shadow_stage_policy,
    )


def load_fixture(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def deep_merge(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def apply_stage_objective_mutations(
    payload: dict[str, object],
    mutations: dict[str, dict[str, dict[str, object]]],
) -> dict[str, object]:
    mutated = dict(payload)
    for field_name in ("paper_objectives", "shadow_live_objectives"):
        if field_name not in mutations:
            continue
        objective_mutations = mutations[field_name]
        updated_records = []
        for record in mutated.get(field_name, []):
            updated = dict(record)
            record_mutation = objective_mutations.get(str(updated["objective_id"]))
            if record_mutation:
                updated.update(record_mutation)
            updated_records.append(updated)
        mutated[field_name] = updated_records
    return mutated


def build_stage_policy_report(case_id: str):
    (
        _gate_request_cls,
        _evaluate_gate,
        stage_request_cls,
        evaluate_stage_policy,
    ) = _load_gate_api()
    fixture = load_fixture(STAGE_FIXTURE_PATH)
    case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    payload["case_id"] = case_id
    payload = apply_stage_objective_mutations(payload, dict(case.get("objective_mutations", {})))
    request = stage_request_cls.from_dict(payload)
    return evaluate_stage_policy(request)


def build_request(
    fixture: dict[str, object], case_id: str
) -> "OperationalEvidenceGateRequest":
    request_cls, _evaluate_gate, _stage_request_cls, _evaluate_stage = _load_gate_api()
    case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    payload = deep_merge(dict(fixture["defaults"]), dict(case.get("payload_overrides", {})))
    stage_report = build_stage_policy_report(str(payload.pop("stage_policy_case_id")))
    payload["case_id"] = case_id
    payload["stage_policy_report"] = stage_report.to_dict()
    return request_cls.from_dict(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the operational-evidence gate smoke workflow."
    )
    parser.add_argument("--case-id", required=True, help="Fixture case id to evaluate")
    parser.add_argument("--output", type=Path, help="Optional path to write the full JSON report")
    args = parser.parse_args()

    fixture = load_fixture(FIXTURE_PATH)
    request = build_request(fixture, args.case_id)
    _, evaluate_gate, _, _ = _load_gate_api()
    report = evaluate_gate(request)
    payload = report.to_dict()

    if args.output:
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "case_id": args.case_id,
                "requested_transition": report.requested_transition,
                "status": report.status,
                "reason_code": report.reason_code,
                "promotion_allowed": report.promotion_allowed,
                "approved_target_state": report.approved_target_state,
                "promotion_admissible_evidence_ids": report.promotion_admissible_evidence_ids,
                "blocked_evidence_ids": report.blocked_evidence_ids,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
