"""Charter-scoped facade over the canonical non-negotiable guardrail bundle."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from python.research.policy.guardrails import (
    evaluate_guardrails as evaluate_canonical_guardrails,
    load_non_negotiable_principles_bundle,
)

CHARTER_INDEX_PATH = Path("shared/policy/charter/non_negotiable_principles.json")
FIXTURE_CASES_PATH = Path("shared/fixtures/charter/non_negotiable_principle_cases.json")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(relative_path: Path) -> dict[str, Any]:
    with (_repo_root() / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_policy_bundle() -> dict[str, Any]:
    return load_non_negotiable_principles_bundle()


def load_charter_index() -> dict[str, Any]:
    return _load_json(CHARTER_INDEX_PATH)


def load_fixture_cases() -> dict[str, Any]:
    return _load_json(FIXTURE_CASES_PATH)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _value_at_path(context: dict[str, Any], dotted_path: str) -> Any:
    current: Any = context
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def build_fixture_context(case_name: str) -> dict[str, Any]:
    fixtures = load_fixture_cases()
    baseline = fixtures["valid_case"]["context"]
    if case_name == fixtures["valid_case"]["name"]:
        return copy.deepcopy(baseline)

    for case in fixtures["violation_cases"]:
        if case["name"] == case_name:
            return _deep_merge(baseline, case["context_overrides"])

    raise KeyError(f"Unknown fixture case: {case_name}")


def evaluate_guardrails(
    context: dict[str, Any], policy_bundle: dict[str, Any] | None = None
) -> dict[str, Any]:
    bundle = policy_bundle or load_policy_bundle()
    decisions = evaluate_canonical_guardrails(context, bundle)
    return {
        "bundle_id": bundle["bundle_id"],
        "bundle_version": bundle["version"],
        "passed": not any(decision["status"] == "violation" for decision in decisions),
        "failed_reason_codes": [
            decision["reason_code"]
            for decision in decisions
            if decision["status"] == "violation"
        ],
        "checks": [
            {
                "principle_id": decision["principle_id"],
                "reason_code": decision["reason_code"],
                "passed": decision["status"] == "pass",
                "violation_type": decision["violation_type"],
                "diagnostic_context": decision["diagnostic_context"],
                "failures": decision["failed_conditions"],
            }
            for decision in decisions
        ],
    }
