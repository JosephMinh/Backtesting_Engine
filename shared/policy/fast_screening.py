"""Fast-screening governance contracts for non-promotable candidate triage."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

SUPPORTED_FAST_SCREENING_SCHEMA_VERSION = 1
FAST_SCREENING_ALLOWED_DECISION_BASES = ("bar_close", "one_bar_late")
FAST_SCREENING_SIMPLE_ORDER_SEMANTICS = (
    "market",
    "limit",
    "stop",
    "basic_bracket",
)
FAST_SCREENING_ALLOWED_ORDER_MANAGEMENT_MODES = (
    "single_shot",
    "basic_bracket",
)
REQUIRED_EQUIVALENCE_DIMENSIONS = (
    "signal_parity",
    "trade_count",
    "fill_rate",
    "pnl_path",
)
REQUIRED_FULL_NAUTILUS_FOLLOW_ON = (
    "full_nautilus_screening",
    "full_validation",
    "full_stress",
    "null_comparison",
)
_ELIGIBILITY_REASON_CODES = {
    "decision_basis": "FAST_SCREENING_ELIGIBILITY_DECISION_BASIS",
    "order_semantics": "FAST_SCREENING_ELIGIBILITY_ORDER_SEMANTICS",
    "order_management_mode": "FAST_SCREENING_ELIGIBILITY_ORDER_MANAGEMENT",
    "passive_queue_dependence": "FAST_SCREENING_ELIGIBILITY_PASSIVE_QUEUE",
    "microstructure_dependence": "FAST_SCREENING_ELIGIBILITY_MICROSTRUCTURE",
}
_EQUIVALENCE_REASON_CODES = {
    "comparison_engine": "FAST_SCREENING_EQUIVALENCE_ENGINE_MISMATCH",
    "study_failed": "FAST_SCREENING_EQUIVALENCE_STUDY_FAILED",
    "dimensions": "FAST_SCREENING_EQUIVALENCE_DIMENSIONS_INCOMPLETE",
    "signal_mismatch": "FAST_SCREENING_EQUIVALENCE_SIGNAL_DRIFT",
    "fill_rate_delta": "FAST_SCREENING_EQUIVALENCE_FILL_DRIFT",
    "pnl_drift_bps": "FAST_SCREENING_EQUIVALENCE_PNL_DRIFT",
    "run_logs": "FAST_SCREENING_EQUIVALENCE_RUN_LOGS_INCOMPLETE",
    "artifact_ids": "FAST_SCREENING_EQUIVALENCE_ARTIFACTS_MISSING",
    "diff_ids": "FAST_SCREENING_EQUIVALENCE_DIFFS_MISSING",
}
_CONTROL_REASON_CODES = {
    "promotion_blocked": "FAST_SCREENING_CONTROL_PROMOTION_NOT_BLOCKED",
    "other_allowed_actions": "FAST_SCREENING_CONTROL_ACTION_SCOPE_TOO_BROAD",
}
_FOLLOW_ON_REASON_CODES = {
    "full_nautilus_screening": "FAST_SCREENING_FOLLOW_ON_NAUTILUS_REQUIRED",
    "full_validation": "FAST_SCREENING_FOLLOW_ON_VALIDATION_REQUIRED",
    "full_stress": "FAST_SCREENING_FOLLOW_ON_STRESS_REQUIRED",
    "null_comparison": "FAST_SCREENING_FOLLOW_ON_NULL_COMPARISON_REQUIRED",
}


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name}: must be timezone-aware")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_present(payload: dict[str, Any], *, field_name: str) -> object:
    if field_name not in payload:
        raise ValueError(f"{field_name}: missing required field")
    return payload[field_name]


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a non-empty string")
    parsed = value.strip()
    if not parsed:
        raise ValueError(f"{field_name}: must be a non-empty string")
    return parsed


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be boolean")
    return value


def _require_int(
    value: object,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}: must be an integer")
    if minimum is not None and value < minimum:
        qualifier = "positive" if minimum == 1 else f">= {minimum}"
        raise ValueError(f"{field_name}: must be {qualifier}")
    return value


def _require_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}: must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name}: must be finite")
    return parsed


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of strings")
    return tuple(_require_non_empty_string(item, field_name=field_name) for item in value)


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of objects")
    return tuple(_require_mapping(item, field_name=field_name) for item in value)


def _require_schema_version(value: object, *, field_name: str) -> int:
    parsed = _require_int(value, field_name=field_name, minimum=1)
    if parsed != SUPPORTED_FAST_SCREENING_SCHEMA_VERSION:
        raise ValueError(
            f"{field_name}: unsupported schema version {parsed}; "
            f"expected {SUPPORTED_FAST_SCREENING_SCHEMA_VERSION}"
        )
    return parsed


def _require_enum_value(
    value: object,
    *,
    field_name: str,
    enum_type: type[Enum],
    description: str,
) -> str:
    if isinstance(value, enum_type):
        return value.value
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid {description}")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid {description}") from exc


@unique
class FastScreeningStatus(str, Enum):
    PASS = "pass"
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class FastScreeningCheckID(str, Enum):
    REQUEST_SHAPE = "FS00"
    ELIGIBILITY = "FS01"
    NAUTILUS_EQUIVALENCE = "FS02"
    NON_PROMOTABLE_CONTROLS = "FS03"
    FOLLOW_ON_WORKFLOW = "FS04"


@dataclass(frozen=True)
class FastScreeningEquivalenceEvidence:
    study_id: str
    compared_engine: str
    passed: bool
    checked_dimensions: tuple[str, ...]
    coverage_seed_count: int
    retained_run_log_ids: tuple[str, ...]
    retained_artifact_ids: tuple[str, ...]
    expected_vs_actual_diff_ids: tuple[str, ...]
    max_signal_mismatch_rate: float
    allowed_signal_mismatch_rate: float
    max_fill_rate_delta: float
    allowed_fill_rate_delta: float
    max_pnl_drift_bps: float
    allowed_pnl_drift_bps: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FastScreeningEquivalenceEvidence":
        payload = _require_mapping(payload, field_name="fast_screening_equivalence")
        return cls(
            study_id=_require_non_empty_string(
                _require_present(payload, field_name="study_id"),
                field_name="study_id",
            ),
            compared_engine=_require_non_empty_string(
                _require_present(payload, field_name="compared_engine"),
                field_name="compared_engine",
            ),
            passed=_require_bool(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            checked_dimensions=_require_string_sequence(
                _require_present(payload, field_name="checked_dimensions"),
                field_name="checked_dimensions",
            ),
            coverage_seed_count=_require_int(
                _require_present(payload, field_name="coverage_seed_count"),
                field_name="coverage_seed_count",
                minimum=1,
            ),
            retained_run_log_ids=_require_string_sequence(
                _require_present(payload, field_name="retained_run_log_ids"),
                field_name="retained_run_log_ids",
            ),
            retained_artifact_ids=_require_string_sequence(
                _require_present(payload, field_name="retained_artifact_ids"),
                field_name="retained_artifact_ids",
            ),
            expected_vs_actual_diff_ids=_require_string_sequence(
                _require_present(payload, field_name="expected_vs_actual_diff_ids"),
                field_name="expected_vs_actual_diff_ids",
            ),
            max_signal_mismatch_rate=_require_finite_float(
                _require_present(payload, field_name="max_signal_mismatch_rate"),
                field_name="max_signal_mismatch_rate",
            ),
            allowed_signal_mismatch_rate=_require_finite_float(
                _require_present(payload, field_name="allowed_signal_mismatch_rate"),
                field_name="allowed_signal_mismatch_rate",
            ),
            max_fill_rate_delta=_require_finite_float(
                _require_present(payload, field_name="max_fill_rate_delta"),
                field_name="max_fill_rate_delta",
            ),
            allowed_fill_rate_delta=_require_finite_float(
                _require_present(payload, field_name="allowed_fill_rate_delta"),
                field_name="allowed_fill_rate_delta",
            ),
            max_pnl_drift_bps=_require_finite_float(
                _require_present(payload, field_name="max_pnl_drift_bps"),
                field_name="max_pnl_drift_bps",
            ),
            allowed_pnl_drift_bps=_require_finite_float(
                _require_present(payload, field_name="allowed_pnl_drift_bps"),
                field_name="allowed_pnl_drift_bps",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FastScreeningEquivalenceEvidence":
        return cls.from_dict(_decode_json_object(payload, label="fast_screening_equivalence"))


@dataclass(frozen=True)
class FastScreeningGovernance:
    may_inform_continuation: bool
    may_inform_abandonment: bool
    promotion_blocked: bool
    requires_full_nautilus_screening: bool
    requires_full_validation: bool
    requires_full_stress: bool
    requires_null_comparison: bool
    other_allowed_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FastScreeningGovernance":
        payload = _require_mapping(payload, field_name="fast_screening_governance")
        return cls(
            may_inform_continuation=_require_bool(
                _require_present(payload, field_name="may_inform_continuation"),
                field_name="may_inform_continuation",
            ),
            may_inform_abandonment=_require_bool(
                _require_present(payload, field_name="may_inform_abandonment"),
                field_name="may_inform_abandonment",
            ),
            promotion_blocked=_require_bool(
                _require_present(payload, field_name="promotion_blocked"),
                field_name="promotion_blocked",
            ),
            requires_full_nautilus_screening=_require_bool(
                _require_present(payload, field_name="requires_full_nautilus_screening"),
                field_name="requires_full_nautilus_screening",
            ),
            requires_full_validation=_require_bool(
                _require_present(payload, field_name="requires_full_validation"),
                field_name="requires_full_validation",
            ),
            requires_full_stress=_require_bool(
                _require_present(payload, field_name="requires_full_stress"),
                field_name="requires_full_stress",
            ),
            requires_null_comparison=_require_bool(
                _require_present(payload, field_name="requires_null_comparison"),
                field_name="requires_null_comparison",
            ),
            other_allowed_actions=_require_string_sequence(
                _require_present(payload, field_name="other_allowed_actions"),
                field_name="other_allowed_actions",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FastScreeningGovernance":
        return cls.from_dict(_decode_json_object(payload, label="fast_screening_governance"))


@dataclass(frozen=True)
class FastScreeningRequest:
    case_id: str
    candidate_id: str
    strategy_class_id: str
    fast_path_engine: str
    decision_basis: str
    bar_interval_seconds: int
    order_semantics: tuple[str, ...]
    order_management_mode: str
    requires_passive_queue_dependence: bool
    depends_on_portability_sensitive_microstructure: bool
    equivalence_evidence: FastScreeningEquivalenceEvidence
    governance: FastScreeningGovernance
    schema_version: int = SUPPORTED_FAST_SCREENING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["equivalence_evidence"] = self.equivalence_evidence.to_dict()
        payload["governance"] = self.governance.to_dict()
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FastScreeningRequest":
        payload = _require_mapping(payload, field_name="fast_screening_request")
        if "schema_version" not in payload:
            raise ValueError("schema_version: missing required field")
        return cls(
            case_id=_require_non_empty_string(
                _require_present(payload, field_name="case_id"),
                field_name="case_id",
            ),
            candidate_id=_require_non_empty_string(
                _require_present(payload, field_name="candidate_id"),
                field_name="candidate_id",
            ),
            strategy_class_id=_require_non_empty_string(
                _require_present(payload, field_name="strategy_class_id"),
                field_name="strategy_class_id",
            ),
            fast_path_engine=_require_non_empty_string(
                _require_present(payload, field_name="fast_path_engine"),
                field_name="fast_path_engine",
            ),
            decision_basis=_require_non_empty_string(
                _require_present(payload, field_name="decision_basis"),
                field_name="decision_basis",
            ),
            bar_interval_seconds=_require_int(
                _require_present(payload, field_name="bar_interval_seconds"),
                field_name="bar_interval_seconds",
                minimum=1,
            ),
            order_semantics=_require_string_sequence(
                _require_present(payload, field_name="order_semantics"),
                field_name="order_semantics",
            ),
            order_management_mode=_require_non_empty_string(
                _require_present(payload, field_name="order_management_mode"),
                field_name="order_management_mode",
            ),
            requires_passive_queue_dependence=_require_bool(
                _require_present(payload, field_name="requires_passive_queue_dependence"),
                field_name="requires_passive_queue_dependence",
            ),
            depends_on_portability_sensitive_microstructure=_require_bool(
                _require_present(
                    payload,
                    field_name="depends_on_portability_sensitive_microstructure",
                ),
                field_name="depends_on_portability_sensitive_microstructure",
            ),
            equivalence_evidence=FastScreeningEquivalenceEvidence.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="equivalence_evidence"),
                    field_name="equivalence_evidence",
                )
            ),
            governance=FastScreeningGovernance.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="governance"),
                    field_name="governance",
                )
            ),
            schema_version=_require_schema_version(
                payload["schema_version"],
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FastScreeningRequest":
        return cls.from_dict(_decode_json_object(payload, label="fast_screening_request"))


@dataclass(frozen=True)
class FastScreeningCheckResult:
    check_id: str
    check_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FastScreeningCheckResult":
        payload = _require_mapping(payload, field_name="fast_screening_check_result")
        evidence = _require_mapping(
            _require_present(payload, field_name="evidence"),
            field_name="evidence",
        )
        return cls(
            check_id=_require_enum_value(
                _require_present(payload, field_name="check_id"),
                field_name="check_id",
                enum_type=FastScreeningCheckID,
                description="fast-screening check id",
            ),
            check_name=_require_non_empty_string(
                _require_present(payload, field_name="check_name"),
                field_name="check_name",
            ),
            passed=_require_bool(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            diagnostic=_require_non_empty_string(
                _require_present(payload, field_name="diagnostic"),
                field_name="diagnostic",
            ),
            evidence=dict(evidence),
            timestamp=_normalize_utc_timestamp(
                _require_present(payload, field_name="timestamp"),
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FastScreeningCheckResult":
        return cls.from_dict(_decode_json_object(payload, label="fast_screening_check_result"))


@dataclass(frozen=True)
class FastScreeningReport:
    case_id: str
    candidate_id: str
    strategy_class_id: str
    fast_path_engine: str
    status: str
    reason_code: str
    fast_path_eligible: bool
    equivalence_certified: bool
    promotion_blocked: bool
    admissible_research_actions: list[str]
    required_follow_on_workflow: list[str]
    decision_trace: list[dict[str, Any]]
    failed_check_ids: list[str]
    retained_run_log_ids: list[str]
    retained_artifact_ids: list[str]
    expected_vs_actual_diff_ids: list[str]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FastScreeningReport":
        payload = _require_mapping(payload, field_name="fast_screening_report")
        return cls(
            case_id=_require_non_empty_string(
                _require_present(payload, field_name="case_id"),
                field_name="case_id",
            ),
            candidate_id=_require_non_empty_string(
                _require_present(payload, field_name="candidate_id"),
                field_name="candidate_id",
            ),
            strategy_class_id=_require_non_empty_string(
                _require_present(payload, field_name="strategy_class_id"),
                field_name="strategy_class_id",
            ),
            fast_path_engine=_require_non_empty_string(
                _require_present(payload, field_name="fast_path_engine"),
                field_name="fast_path_engine",
            ),
            status=_require_enum_value(
                _require_present(payload, field_name="status"),
                field_name="status",
                enum_type=FastScreeningStatus,
                description="fast-screening status",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            fast_path_eligible=_require_bool(
                _require_present(payload, field_name="fast_path_eligible"),
                field_name="fast_path_eligible",
            ),
            equivalence_certified=_require_bool(
                _require_present(payload, field_name="equivalence_certified"),
                field_name="equivalence_certified",
            ),
            promotion_blocked=_require_bool(
                _require_present(payload, field_name="promotion_blocked"),
                field_name="promotion_blocked",
            ),
            admissible_research_actions=list(
                _require_string_sequence(
                    _require_present(payload, field_name="admissible_research_actions"),
                    field_name="admissible_research_actions",
                )
            ),
            required_follow_on_workflow=list(
                _require_string_sequence(
                    _require_present(payload, field_name="required_follow_on_workflow"),
                    field_name="required_follow_on_workflow",
                )
            ),
            decision_trace=[
                FastScreeningCheckResult.from_dict(item).to_dict()
                for item in _require_object_sequence(
                    _require_present(payload, field_name="decision_trace"),
                    field_name="decision_trace",
                )
            ],
            failed_check_ids=list(
                _require_string_sequence(
                    _require_present(payload, field_name="failed_check_ids"),
                    field_name="failed_check_ids",
                )
            ),
            retained_run_log_ids=list(
                _require_string_sequence(
                    _require_present(payload, field_name="retained_run_log_ids"),
                    field_name="retained_run_log_ids",
                )
            ),
            retained_artifact_ids=list(
                _require_string_sequence(
                    _require_present(payload, field_name="retained_artifact_ids"),
                    field_name="retained_artifact_ids",
                )
            ),
            expected_vs_actual_diff_ids=list(
                _require_string_sequence(
                    _require_present(payload, field_name="expected_vs_actual_diff_ids"),
                    field_name="expected_vs_actual_diff_ids",
                )
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, field_name="explanation"),
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                _require_present(payload, field_name="remediation"),
                field_name="remediation",
            ),
            timestamp=_normalize_utc_timestamp(
                _require_present(payload, field_name="timestamp"),
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FastScreeningReport":
        return cls.from_dict(_decode_json_object(payload, label="fast_screening_report"))


def _admissible_actions(governance: FastScreeningGovernance) -> list[str]:
    actions: list[str] = []
    if governance.may_inform_continuation:
        actions.append("continuation")
    if governance.may_inform_abandonment:
        actions.append("abandonment")
    actions.extend(governance.other_allowed_actions)
    return actions


def _validate_request(request: FastScreeningRequest) -> list[str]:
    errors: list[str] = []

    if not request.case_id:
        errors.append("case_id must be non-empty")
    if not request.candidate_id:
        errors.append("candidate_id must be non-empty")
    if not request.strategy_class_id:
        errors.append("strategy_class_id must be non-empty")
    if not request.fast_path_engine:
        errors.append("fast_path_engine must be non-empty")
    if not request.decision_basis:
        errors.append("decision_basis must be non-empty")
    if request.bar_interval_seconds <= 0:
        errors.append("bar_interval_seconds must be positive")
    if not request.order_semantics:
        errors.append("order_semantics must be non-empty")
    if not request.order_management_mode:
        errors.append("order_management_mode must be non-empty")
    if not request.equivalence_evidence.study_id:
        errors.append("equivalence_evidence.study_id must be non-empty")
    if request.equivalence_evidence.coverage_seed_count <= 0:
        errors.append("equivalence_evidence.coverage_seed_count must be positive")
    if request.equivalence_evidence.allowed_signal_mismatch_rate < 0:
        errors.append("equivalence_evidence.allowed_signal_mismatch_rate must be non-negative")
    if request.equivalence_evidence.allowed_fill_rate_delta < 0:
        errors.append("equivalence_evidence.allowed_fill_rate_delta must be non-negative")
    if request.equivalence_evidence.allowed_pnl_drift_bps < 0:
        errors.append("equivalence_evidence.allowed_pnl_drift_bps must be non-negative")

    return errors


def check_fast_path_eligibility(request: FastScreeningRequest) -> FastScreeningCheckResult:
    failures: list[str] = []
    unsupported_order_semantics = [
        semantic
        for semantic in request.order_semantics
        if semantic not in FAST_SCREENING_SIMPLE_ORDER_SEMANTICS
    ]

    if request.decision_basis not in FAST_SCREENING_ALLOWED_DECISION_BASES:
        failures.append("decision_basis")
    if unsupported_order_semantics:
        failures.append("order_semantics")
    if request.order_management_mode not in FAST_SCREENING_ALLOWED_ORDER_MANAGEMENT_MODES:
        failures.append("order_management_mode")
    if request.requires_passive_queue_dependence:
        failures.append("passive_queue_dependence")
    if request.depends_on_portability_sensitive_microstructure:
        failures.append("microstructure_dependence")

    passed = not failures
    reason_code = (
        "FAST_SCREENING_FS01_ELIGIBLE"
        if passed
        else (
            _ELIGIBILITY_REASON_CODES[failures[0]]
            if len(failures) == 1
            else "FAST_SCREENING_ELIGIBILITY_MULTIPLE"
        )
    )
    diagnostic = (
        "The candidate stays inside the simple fast-screening envelope."
        if passed
        else (
            "The candidate exceeds the optional fast-screening envelope because "
            f"{failures} are outside the approved simple-class rules."
        )
    )

    return FastScreeningCheckResult(
        check_id=FastScreeningCheckID.ELIGIBILITY.value,
        check_name="fast_path_eligibility",
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "decision_basis": request.decision_basis,
            "bar_interval_seconds": request.bar_interval_seconds,
            "order_semantics": list(request.order_semantics),
            "unsupported_order_semantics": unsupported_order_semantics,
            "order_management_mode": request.order_management_mode,
            "requires_passive_queue_dependence": request.requires_passive_queue_dependence,
            "depends_on_portability_sensitive_microstructure": (
                request.depends_on_portability_sensitive_microstructure
            ),
            "failed_constraints": failures,
        },
    )


def check_nautilus_equivalence(request: FastScreeningRequest) -> FastScreeningCheckResult:
    evidence = request.equivalence_evidence
    failures: list[str] = []
    missing_dimensions = [
        dimension
        for dimension in REQUIRED_EQUIVALENCE_DIMENSIONS
        if dimension not in evidence.checked_dimensions
    ]

    if evidence.compared_engine != "nautilus_high_level":
        failures.append("comparison_engine")
    if not evidence.passed:
        failures.append("study_failed")
    if missing_dimensions:
        failures.append("dimensions")
    if evidence.max_signal_mismatch_rate > evidence.allowed_signal_mismatch_rate:
        failures.append("signal_mismatch")
    if evidence.max_fill_rate_delta > evidence.allowed_fill_rate_delta:
        failures.append("fill_rate_delta")
    if evidence.max_pnl_drift_bps > evidence.allowed_pnl_drift_bps:
        failures.append("pnl_drift_bps")
    if len(evidence.retained_run_log_ids) < evidence.coverage_seed_count:
        failures.append("run_logs")
    if not evidence.retained_artifact_ids:
        failures.append("artifact_ids")
    if not evidence.expected_vs_actual_diff_ids:
        failures.append("diff_ids")

    passed = not failures
    reason_code = (
        "FAST_SCREENING_FS02_NAUTILUS_EQUIVALENT"
        if passed
        else (
            _EQUIVALENCE_REASON_CODES[failures[0]]
            if len(failures) == 1
            else "FAST_SCREENING_EQUIVALENCE_MULTIPLE"
        )
    )
    diagnostic = (
        "The fast path is backed by retained equivalence evidence against the full Nautilus path."
        if passed
        else (
            "The fast path lacks sufficient equivalence evidence against the full Nautilus path "
            f"because {failures} failed."
        )
    )

    return FastScreeningCheckResult(
        check_id=FastScreeningCheckID.NAUTILUS_EQUIVALENCE.value,
        check_name="nautilus_equivalence",
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "study_id": evidence.study_id,
            "compared_engine": evidence.compared_engine,
            "coverage_seed_count": evidence.coverage_seed_count,
            "checked_dimensions": list(evidence.checked_dimensions),
            "missing_dimensions": missing_dimensions,
            "retained_run_log_ids": list(evidence.retained_run_log_ids),
            "retained_artifact_ids": list(evidence.retained_artifact_ids),
            "expected_vs_actual_diff_ids": list(evidence.expected_vs_actual_diff_ids),
            "max_signal_mismatch_rate": evidence.max_signal_mismatch_rate,
            "allowed_signal_mismatch_rate": evidence.allowed_signal_mismatch_rate,
            "max_fill_rate_delta": evidence.max_fill_rate_delta,
            "allowed_fill_rate_delta": evidence.allowed_fill_rate_delta,
            "max_pnl_drift_bps": evidence.max_pnl_drift_bps,
            "allowed_pnl_drift_bps": evidence.allowed_pnl_drift_bps,
            "failed_constraints": failures,
        },
    )


def check_non_promotable_controls(request: FastScreeningRequest) -> FastScreeningCheckResult:
    governance = request.governance
    failures: list[str] = []

    if not governance.promotion_blocked:
        failures.append("promotion_blocked")
    if governance.other_allowed_actions:
        failures.append("other_allowed_actions")

    passed = not failures
    reason_code = (
        "FAST_SCREENING_FS03_NON_PROMOTABLE"
        if passed
        else (
            _CONTROL_REASON_CODES[failures[0]]
            if len(failures) == 1
            else "FAST_SCREENING_CONTROL_MULTIPLE"
        )
    )
    diagnostic = (
        "The fast path remains explicitly non-promotable and scoped to research triage only."
        if passed
        else (
            "The fast path governance is too permissive because "
            f"{failures} violate the non-promotable rule."
        )
    )

    return FastScreeningCheckResult(
        check_id=FastScreeningCheckID.NON_PROMOTABLE_CONTROLS.value,
        check_name="non_promotable_controls",
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "admissible_research_actions": _admissible_actions(governance),
            "promotion_blocked": governance.promotion_blocked,
            "failed_constraints": failures,
        },
    )


def check_full_nautilus_follow_on(request: FastScreeningRequest) -> FastScreeningCheckResult:
    governance = request.governance
    requirements = {
        "full_nautilus_screening": governance.requires_full_nautilus_screening,
        "full_validation": governance.requires_full_validation,
        "full_stress": governance.requires_full_stress,
        "null_comparison": governance.requires_null_comparison,
    }
    failures = [name for name, enabled in requirements.items() if not enabled]
    passed = not failures
    reason_code = (
        "FAST_SCREENING_FS04_FULL_PATH_REQUIRED"
        if passed
        else (
            _FOLLOW_ON_REASON_CODES[failures[0]]
            if len(failures) == 1
            else "FAST_SCREENING_FOLLOW_ON_MULTIPLE"
        )
    )
    diagnostic = (
        "Any surviving candidate is still forced through the full Nautilus workflow."
        if passed
        else (
            "The survivor workflow is incomplete because the fast path is not forcing "
            f"{failures} before promotion-grade decisions."
        )
    )

    return FastScreeningCheckResult(
        check_id=FastScreeningCheckID.FOLLOW_ON_WORKFLOW.value,
        check_name="full_nautilus_follow_on",
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "required_follow_on_workflow": list(REQUIRED_FULL_NAUTILUS_FOLLOW_ON),
            "enabled_follow_on_workflow": [
                name for name, enabled in requirements.items() if enabled
            ],
            "failed_constraints": failures,
        },
    )


def _build_explanation(
    *,
    status: FastScreeningStatus,
    failed_checks: list[FastScreeningCheckResult],
) -> str:
    if status == FastScreeningStatus.PASS:
        return (
            "The candidate stays inside the simple fast-screening envelope, retains "
            "equivalence evidence against the full Nautilus path, remains non-promotable, "
            "and still forces survivors through the full Nautilus screening workflow."
        )

    failed_ids = {check.check_id for check in failed_checks}
    segments: list[str] = []
    if FastScreeningCheckID.ELIGIBILITY.value in failed_ids:
        segments.append("The candidate is outside the approved simple-class fast-screening scope.")
    if FastScreeningCheckID.NAUTILUS_EQUIVALENCE.value in failed_ids:
        segments.append("Equivalence to the full Nautilus path is missing or has drifted.")
    if FastScreeningCheckID.NON_PROMOTABLE_CONTROLS.value in failed_ids:
        segments.append("Governance would let the fast path act like a second promotion lane.")
    if FastScreeningCheckID.FOLLOW_ON_WORKFLOW.value in failed_ids:
        segments.append(
            "The survivor workflow does not force full Nautilus screening, validation, stress, "
            "and null comparison."
        )
    return " ".join(segments) or "The fast-screening request is invalid."


def _build_remediation(failed_checks: list[FastScreeningCheckResult]) -> str:
    failed_ids = {check.check_id for check in failed_checks}
    steps: list[str] = []
    if FastScreeningCheckID.REQUEST_SHAPE.value in failed_ids:
        steps.append("Repair the malformed request and re-run the contract.")
    if FastScreeningCheckID.ELIGIBILITY.value in failed_ids:
        steps.append(
            "Restrict the candidate to bar-close or one-bar-late logic with simple orders only."
        )
    if FastScreeningCheckID.NAUTILUS_EQUIVALENCE.value in failed_ids:
        steps.append(
            "Retain seeded Nautilus equivalence evidence with run logs, manifests, and expected-vs-actual diffs."
        )
    if FastScreeningCheckID.NON_PROMOTABLE_CONTROLS.value in failed_ids:
        steps.append(
            "Block promotion from the fast path and remove any actions beyond continuation or abandonment."
        )
    if FastScreeningCheckID.FOLLOW_ON_WORKFLOW.value in failed_ids:
        steps.append(
            "Require full Nautilus screening, validation, stress, and null comparison for every survivor."
        )
    return " ".join(steps) or "No remediation required."


def evaluate_fast_screening_path(request: FastScreeningRequest) -> FastScreeningReport:
    """Evaluate the optional fast path against the non-promotable screening contract."""

    if request.schema_version != SUPPORTED_FAST_SCREENING_SCHEMA_VERSION:
        invalid_check = FastScreeningCheckResult(
            check_id=FastScreeningCheckID.REQUEST_SHAPE.value,
            check_name="request_shape",
            passed=False,
            reason_code="FAST_SCREENING_SCHEMA_VERSION_UNSUPPORTED",
            diagnostic="The fast-screening request uses an unsupported schema version.",
            evidence={
                "schema_version": request.schema_version,
                "supported_schema_version": SUPPORTED_FAST_SCREENING_SCHEMA_VERSION,
            },
        )
        return FastScreeningReport(
            case_id=request.case_id,
            candidate_id=request.candidate_id,
            strategy_class_id=request.strategy_class_id,
            fast_path_engine=request.fast_path_engine,
            status=FastScreeningStatus.INVALID.value,
            reason_code="FAST_SCREENING_INVALID_REQUEST",
            fast_path_eligible=False,
            equivalence_certified=False,
            promotion_blocked=bool(request.governance.promotion_blocked),
            admissible_research_actions=[],
            required_follow_on_workflow=list(REQUIRED_FULL_NAUTILUS_FOLLOW_ON),
            decision_trace=[invalid_check.to_dict()],
            failed_check_ids=[invalid_check.check_id],
            retained_run_log_ids=list(request.equivalence_evidence.retained_run_log_ids),
            retained_artifact_ids=list(request.equivalence_evidence.retained_artifact_ids),
            expected_vs_actual_diff_ids=list(
                request.equivalence_evidence.expected_vs_actual_diff_ids
            ),
            explanation="The request must use the supported fast-screening schema version.",
            remediation="Regenerate the request with the canonical schema version.",
        )

    validation_errors = _validate_request(request)
    if validation_errors:
        invalid_check = FastScreeningCheckResult(
            check_id=FastScreeningCheckID.REQUEST_SHAPE.value,
            check_name="request_shape",
            passed=False,
            reason_code="FAST_SCREENING_INVALID_REQUEST",
            diagnostic="The fast-screening request is missing required fields or thresholds.",
            evidence={"validation_errors": validation_errors},
        )
        return FastScreeningReport(
            case_id=request.case_id,
            candidate_id=request.candidate_id,
            strategy_class_id=request.strategy_class_id,
            fast_path_engine=request.fast_path_engine,
            status=FastScreeningStatus.INVALID.value,
            reason_code="FAST_SCREENING_INVALID_REQUEST",
            fast_path_eligible=False,
            equivalence_certified=False,
            promotion_blocked=bool(request.governance.promotion_blocked),
            admissible_research_actions=[],
            required_follow_on_workflow=list(REQUIRED_FULL_NAUTILUS_FOLLOW_ON),
            decision_trace=[invalid_check.to_dict()],
            failed_check_ids=[invalid_check.check_id],
            retained_run_log_ids=list(request.equivalence_evidence.retained_run_log_ids),
            retained_artifact_ids=list(request.equivalence_evidence.retained_artifact_ids),
            expected_vs_actual_diff_ids=list(
                request.equivalence_evidence.expected_vs_actual_diff_ids
            ),
            explanation="The fast-screening request is structurally invalid.",
            remediation="Repair required fields, thresholds, or identifiers and retry.",
        )

    decision_trace = [
        check_fast_path_eligibility(request),
        check_nautilus_equivalence(request),
        check_non_promotable_controls(request),
        check_full_nautilus_follow_on(request),
    ]
    failed_checks = [check for check in decision_trace if not check.passed]
    status = (
        FastScreeningStatus.PASS if not failed_checks else FastScreeningStatus.VIOLATION
    )

    return FastScreeningReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        strategy_class_id=request.strategy_class_id,
        fast_path_engine=request.fast_path_engine,
        status=status.value,
        reason_code=(
            "FAST_SCREENING_APPROVED"
            if status == FastScreeningStatus.PASS
            else "FAST_SCREENING_BLOCKED"
        ),
        fast_path_eligible=decision_trace[0].passed,
        equivalence_certified=decision_trace[1].passed,
        promotion_blocked=decision_trace[2].passed,
        admissible_research_actions=(
            _admissible_actions(request.governance) if status == FastScreeningStatus.PASS else []
        ),
        required_follow_on_workflow=list(REQUIRED_FULL_NAUTILUS_FOLLOW_ON),
        decision_trace=[check.to_dict() for check in decision_trace],
        failed_check_ids=[check.check_id for check in failed_checks],
        retained_run_log_ids=list(request.equivalence_evidence.retained_run_log_ids),
        retained_artifact_ids=list(request.equivalence_evidence.retained_artifact_ids),
        expected_vs_actual_diff_ids=list(request.equivalence_evidence.expected_vs_actual_diff_ids),
        explanation=_build_explanation(status=status, failed_checks=failed_checks),
        remediation=_build_remediation(failed_checks),
    )


def validate_fast_screening_contract() -> list[str]:
    errors: list[str] = []

    if len(FAST_SCREENING_ALLOWED_DECISION_BASES) != len(
        set(FAST_SCREENING_ALLOWED_DECISION_BASES)
    ):
        errors.append("fast_screening: decision bases must be unique")
    if len(FAST_SCREENING_SIMPLE_ORDER_SEMANTICS) != len(
        set(FAST_SCREENING_SIMPLE_ORDER_SEMANTICS)
    ):
        errors.append("fast_screening: simple order semantics must be unique")
    if len(FAST_SCREENING_ALLOWED_ORDER_MANAGEMENT_MODES) != len(
        set(FAST_SCREENING_ALLOWED_ORDER_MANAGEMENT_MODES)
    ):
        errors.append("fast_screening: order management modes must be unique")
    if len(REQUIRED_EQUIVALENCE_DIMENSIONS) != len(set(REQUIRED_EQUIVALENCE_DIMENSIONS)):
        errors.append("fast_screening: equivalence dimensions must be unique")
    if len(REQUIRED_FULL_NAUTILUS_FOLLOW_ON) != len(set(REQUIRED_FULL_NAUTILUS_FOLLOW_ON)):
        errors.append("fast_screening: follow-on workflow entries must be unique")

    return errors


VALIDATION_ERRORS = validate_fast_screening_contract()
