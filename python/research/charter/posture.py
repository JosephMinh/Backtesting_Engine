from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return repo_root
    return Path(__file__).resolve().parents[3]


def _load_json_file(path: Path, *, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {label}: {path}") from exc
    return payload


def load_initial_live_lane_policy(repo_root: Path | None = None) -> dict[str, Any]:
    policy_path = (
        _repo_root(repo_root) / "shared" / "policy" / "charter" / "initial_live_lane.json"
    )
    return _load_json_file(policy_path, label="policy bundle")


def load_fixture_cases(repo_root: Path | None = None) -> dict[str, Any]:
    fixture_path = (
        _repo_root(repo_root)
        / "shared"
        / "fixtures"
        / "charter"
        / "initial_live_lane_cases.json"
    )
    return _load_json_file(fixture_path, label="fixture bundle")


def _evaluate_rule(candidate: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    operator = rule["operator"]
    field = rule["field"]
    actual = candidate.get(field)
    expected = rule.get("expected")
    condition_active = True

    if operator == "conditional_equals":
        when = rule["when"]
        condition_active = candidate.get(when["field"]) == when["expected"]
        if not condition_active:
            passed = True
        else:
            passed = actual == expected
    elif operator == "equals":
        passed = actual == expected
    elif operator == "less_than_or_equal":
        passed = actual is not None and actual <= expected
    elif operator == "greater_than_or_equal":
        passed = actual is not None and actual >= expected
    elif operator == "one_of":
        expected = rule["allowed_values"]
        passed = actual in expected
    else:
        raise ValueError(f"Unsupported operator: {operator}")

    return {
        "rule_id": rule["id"],
        "rule_code": rule["rule_code"],
        "description": rule["description"],
        "field": field,
        "operator": operator,
        "actual": actual,
        "expected": expected,
        "passed": passed,
        "condition_active": condition_active,
        "failure_reason_code": None if passed else rule["failure_reason_code"],
    }


def evaluate_initial_live_lane(
    candidate: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    bundle = policy or load_initial_live_lane_policy()
    traces = [_evaluate_rule(candidate, rule) for rule in bundle["constraints"]]
    return {
        "bundle_id": bundle["bundle_id"],
        "trace_id": trace_id or candidate.get("candidate_id", "initial-live-lane-eval"),
        "approved": all(trace["passed"] for trace in traces),
        "decision_traces": traces,
    }
