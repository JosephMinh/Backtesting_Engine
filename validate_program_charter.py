import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent
CHARTER_PATH = ROOT / "program_charter.json"


def _decode_json(text: str, label: str) -> Dict[str, Any]:
    try:
        return json.JSONDecoder().decode(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Unable to decode JSON for {label}") from exc


def load_charter(path: Path = CHARTER_PATH) -> Dict[str, Any]:
    try:
        return _decode_json(path.read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise ValueError(f"Unable to load charter JSON from {path}") from exc


def _decision(
    evaluation_id: str,
    surface: str,
    rule_id: str,
    reason_code: str,
    passed: bool,
    violation_type: str,
    message: str,
    actual: Any,
    expected: Any,
) -> Dict[str, Any]:
    return {
        "evaluation_id": evaluation_id,
        "surface": surface,
        "rule_id": rule_id,
        "status": "pass" if passed else "fail",
        "reason_code": reason_code if not passed else None,
        "violation_type": violation_type if not passed else None,
        "message": message,
        "actual": actual,
        "expected": expected,
    }


def evaluate_posture(
    candidate: Dict[str, Any], charter: Dict[str, Any], evaluation_id: str = "posture-eval"
) -> Dict[str, Any]:
    lane = charter["initial_live_lane"]
    checks: List[Dict[str, Any]] = []

    def require_equal(rule_id: str, field: str, expected: Any, reason_code: str) -> None:
        actual = candidate.get(field)
        passed = actual == expected
        checks.append(
            _decision(
                evaluation_id=evaluation_id,
                surface="posture",
                rule_id=rule_id,
                reason_code=reason_code,
                passed=passed,
                violation_type="unexpected_value",
                message=f"{field} must equal {expected!r}",
                actual=actual,
                expected=expected,
            )
        )

    def require_max(rule_id: str, field: str, maximum: int, reason_code: str) -> None:
        actual = candidate.get(field)
        passed = isinstance(actual, int) and actual <= maximum
        checks.append(
            _decision(
                evaluation_id=evaluation_id,
                surface="posture",
                rule_id=rule_id,
                reason_code=reason_code,
                passed=passed,
                violation_type="limit_exceeded",
                message=f"{field} must be <= {maximum}",
                actual=actual,
                expected={"max": maximum},
            )
        )

    def require_true(rule_id: str, field: str, reason_code: str) -> None:
        actual = candidate.get(field)
        passed = isinstance(actual, bool) and actual
        checks.append(
            _decision(
                evaluation_id=evaluation_id,
                surface="posture",
                rule_id=rule_id,
                reason_code=reason_code,
                passed=passed,
                violation_type="required_true",
                message=f"{field} must be true",
                actual=actual,
                expected=True,
            )
        )

    def require_false(rule_id: str, field: str, reason_code: str) -> None:
        actual = candidate.get(field)
        passed = isinstance(actual, bool) and not actual
        checks.append(
            _decision(
                evaluation_id=evaluation_id,
                surface="posture",
                rule_id=rule_id,
                reason_code=reason_code,
                passed=passed,
                violation_type="required_false",
                message=f"{field} must be false",
                actual=actual,
                expected=False,
            )
        )

    require_equal(
        "POSTURE-01",
        "research_symbol",
        lane["research_symbol"],
        "CHARTER_POSTURE_RESEARCH_SYMBOL_NOT_APPROVED",
    )
    require_equal(
        "POSTURE-02",
        "execution_symbol",
        lane["execution_symbol"],
        "CHARTER_POSTURE_EXECUTION_SYMBOL_NOT_APPROVED",
    )
    require_equal(
        "POSTURE-03",
        "broker",
        lane["broker"],
        "CHARTER_POSTURE_BROKER_NOT_APPROVED",
    )
    require_equal(
        "POSTURE-04",
        "approved_live_account_usd",
        lane["approved_live_account_usd"],
        "CHARTER_POSTURE_ACCOUNT_SIZE_NOT_APPROVED",
    )
    require_max(
        "POSTURE-05",
        "live_contract_count",
        lane["max_live_contracts"],
        "CHARTER_POSTURE_LIVE_CONTRACT_LIMIT_EXCEEDED",
    )
    require_max(
        "POSTURE-06",
        "active_live_bundles_per_account_product",
        lane["max_active_live_bundles_per_account_product"],
        "CHARTER_POSTURE_ACTIVE_BUNDLE_LIMIT_EXCEEDED",
    )
    require_equal(
        "POSTURE-07",
        "host_topology",
        lane["host_topology"],
        "CHARTER_POSTURE_HOST_TOPOLOGY_NOT_APPROVED",
    )
    require_true(
        "POSTURE-08",
        "bar_based",
        "CHARTER_POSTURE_BAR_BASED_REQUIRED",
    )

    actual_interval = candidate.get("decision_interval_seconds")
    checks.append(
        _decision(
            evaluation_id=evaluation_id,
            surface="posture",
            rule_id="POSTURE-09",
            reason_code="CHARTER_POSTURE_DECISION_INTERVAL_TOO_FAST",
            passed=isinstance(actual_interval, int)
            and actual_interval >= lane["minimum_decision_interval_seconds"],
            violation_type="minimum_not_met",
            message=(
                "decision_interval_seconds must be >= "
                f"{lane['minimum_decision_interval_seconds']}"
            ),
            actual=actual_interval,
            expected={"min": lane["minimum_decision_interval_seconds"]},
        )
    )

    require_false(
        "POSTURE-10",
        "uses_depth_signals",
        "CHARTER_POSTURE_DEPTH_DEPENDENT_STRATEGY_NOT_LIVE_ELIGIBLE",
    )
    require_false(
        "POSTURE-11",
        "uses_queue_signals",
        "CHARTER_POSTURE_QUEUE_DEPENDENT_STRATEGY_NOT_LIVE_ELIGIBLE",
    )
    require_false(
        "POSTURE-12",
        "uses_subminute_signals",
        "CHARTER_POSTURE_SUBMINUTE_STRATEGY_NOT_LIVE_ELIGIBLE",
    )

    overnight = candidate.get("overnight_holding")
    overnight_class = candidate.get("overnight_candidate_class")
    overnight_expected = lane["overnight_holding"]["requires_candidate_class"]
    overnight_is_true = isinstance(overnight, bool) and overnight
    overnight_is_false = isinstance(overnight, bool) and not overnight
    overnight_passed = overnight_is_false or (
        overnight_is_true and overnight_class == overnight_expected
    )
    checks.append(
        _decision(
            evaluation_id=evaluation_id,
            surface="posture",
            rule_id="POSTURE-13",
            reason_code="CHARTER_POSTURE_OVERNIGHT_CLASS_REQUIRED",
            passed=overnight_passed,
            violation_type="missing_candidate_class",
            message=(
                "overnight holding requires candidate class "
                f"{overnight_expected!r}"
            ),
            actual={
                "overnight_holding": overnight,
                "overnight_candidate_class": overnight_class,
            },
            expected={"overnight_candidate_class": overnight_expected},
        )
    )

    return {
        "evaluation_id": evaluation_id,
        "surface": "posture",
        "allowed": all(check["status"] == "pass" for check in checks),
        "checks": checks,
    }


def evaluate_principles(
    candidate: Dict[str, Any], charter: Dict[str, Any], evaluation_id: str = "principle-eval"
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    for principle in charter["non_negotiable_principles"]:
        rule_id = principle["id"]
        reason_code = principle["reason_code"]
        rule_type = principle["rule_type"]
        title = principle["title"]

        if rule_type == "require_equal":
            field = principle["field"]
            actual = candidate.get(field)
            expected = principle["expected"]
            passed = actual == expected
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="unexpected_value",
                    message=title,
                    actual=actual,
                    expected=expected,
                )
            )
        elif rule_type == "forbid_equal":
            field = principle["field"]
            actual = candidate.get(field)
            expected = principle["expected"]
            passed = actual != expected
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="forbidden_value",
                    message=title,
                    actual=actual,
                    expected={"forbidden": expected},
                )
            )
        elif rule_type == "require_true":
            field = principle["field"]
            actual = candidate.get(field)
            passed = isinstance(actual, bool) and actual
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="required_true",
                    message=title,
                    actual=actual,
                    expected=True,
                )
            )
        elif rule_type == "require_all_true":
            fields = principle["fields"]
            actual = {field: candidate.get(field) for field in fields}
            passed = all(isinstance(value, bool) and value for value in actual.values())
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="required_true",
                    message=title,
                    actual=actual,
                    expected={field: True for field in fields},
                )
            )
        elif rule_type == "baseline_stack":
            expected = principle["expected"]
            actual = {field: candidate.get(field) for field in expected}
            passed = actual == expected
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="unexpected_value",
                    message=title,
                    actual=actual,
                    expected=expected,
                )
            )
        elif rule_type == "conditional_gate":
            if_field = principle["if_field"]
            gate_field = principle["gate_field"]
            requested = candidate.get(if_field)
            gate_passed = candidate.get(gate_field)
            requested_is_true = isinstance(requested, bool) and requested
            gate_is_true = isinstance(gate_passed, bool) and gate_passed
            passed = (not requested_is_true) or gate_is_true
            checks.append(
                _decision(
                    evaluation_id=evaluation_id,
                    surface="principle",
                    rule_id=rule_id,
                    reason_code=reason_code,
                    passed=passed,
                    violation_type="gate_not_satisfied",
                    message=title,
                    actual={if_field: requested, gate_field: gate_passed},
                    expected={if_field: True, gate_field: True},
                )
            )
        else:
            raise ValueError(f"Unsupported rule_type: {rule_type}")

    return {
        "evaluation_id": evaluation_id,
        "surface": "principle",
        "allowed": all(check["status"] == "pass" for check in checks),
        "checks": checks,
    }


def evaluate_all(
    candidate: Dict[str, Any], charter: Dict[str, Any], evaluation_id: str = "charter-eval"
) -> Dict[str, Any]:
    posture = evaluate_posture(candidate, charter, evaluation_id=f"{evaluation_id}:posture")
    principles = evaluate_principles(
        candidate, charter, evaluation_id=f"{evaluation_id}:principles"
    )
    return {
        "evaluation_id": evaluation_id,
        "allowed": posture["allowed"] and principles["allowed"],
        "posture": posture,
        "principles": principles,
    }


def _load_candidate(path: Path) -> Dict[str, Any]:
    try:
        return _decode_json(path.read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise ValueError(f"Unable to load candidate JSON from {path}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--charter", type=Path, default=CHARTER_PATH)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=["posture", "principles", "all"],
        default="all",
    )
    parser.add_argument("--evaluation-id", default="cli-eval")
    args = parser.parse_args()

    charter = load_charter(args.charter)
    candidate = _load_candidate(args.input)

    if args.mode == "posture":
        result = evaluate_posture(candidate, charter, evaluation_id=args.evaluation_id)
    elif args.mode == "principles":
        result = evaluate_principles(candidate, charter, evaluation_id=args.evaluation_id)
    else:
        result = evaluate_all(candidate, charter, evaluation_id=args.evaluation_id)

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
