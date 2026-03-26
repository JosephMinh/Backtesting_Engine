"""Evaluate the non-negotiable program guardrails against a context bundle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE_PATH = REPO_ROOT / "shared" / "policy" / "non_negotiable_principles.json"


def load_non_negotiable_principles_bundle(path: Path | None = None) -> dict[str, Any]:
    bundle_path = path or DEFAULT_BUNDLE_PATH
    try:
        with bundle_path.open("r", encoding="utf-8") as bundle_file:
            return json.load(bundle_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load guardrail bundle from {bundle_path}") from exc


def _evaluate_condition(condition: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    field = condition["field"]
    operator = condition["op"]
    actual = context.get(field)

    if operator == "eq":
        expected = condition["expected"]
        passed = actual == expected
    elif operator == "truthy":
        expected = True
        passed = bool(actual)
    elif operator == "falsy":
        expected = False
        passed = not bool(actual)
    else:
        raise ValueError(f"Unsupported operator: {operator}")

    return {
        "field": field,
        "op": operator,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def evaluate_guardrails(
    context: Mapping[str, Any], bundle: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return one structured decision trace per non-negotiable principle."""

    guardrail_bundle = bundle or load_non_negotiable_principles_bundle()
    decisions: list[dict[str, Any]] = []

    for principle in guardrail_bundle["principles"]:
        condition_results = [_evaluate_condition(condition, context) for condition in principle["conditions"]]
        failures = [result for result in condition_results if not result["passed"]]
        diagnostic_context = {result["field"]: result["actual"] for result in condition_results}

        decisions.append(
            {
                "principle_id": principle["principle_id"],
                "slug": principle["slug"],
                "status": "pass" if not failures else "violation",
                "reason_code": None if not failures else principle["reason_code"],
                "violation_type": None if not failures else principle["violation_type"],
                "diagnostic_context": diagnostic_context,
                "failed_conditions": failures,
            }
        )

    return decisions


def violation_traces(
    context: Mapping[str, Any], bundle: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return only blocking guardrail decisions."""

    return [decision for decision in evaluate_guardrails(context, bundle) if decision["status"] == "violation"]
