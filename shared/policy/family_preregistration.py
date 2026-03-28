"""Strategy-family preregistration and continuation-budget governance contracts."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.guardrails import check_guardrail
from shared.policy.principles import PrincipleID
from shared.policy.research_state import FamilyDecisionRecord, FamilyDecisionType

SUPPORTED_FAMILY_PREREGISTRATION_SCHEMA_VERSION = 1
REQUIRED_PREREGISTRATION_FIELDS = (
    "registration_id",
    "family_id",
    "subfamily_id",
    "economic_thesis",
    "target_session_class",
    "intended_execution_style",
    "intended_holding_period",
    "research_symbol",
    "expected_execution_symbol",
    "execution_symbol_tradability_hypothesis",
)
SUPPORTED_VIABILITY_GATE_TYPES = (
    "early_viability_gate",
    "execution_symbol_first_viability_screen",
)
PREREGISTRATION_CHECK_IDS = (
    "required_metadata",
    "parameter_ranges",
    "budget_limits",
)
CONTINUATION_CHECK_IDS = (
    "preregistration_valid",
    "canonical_decision_record_alignment",
    "structured_evidence_and_economics",
    "registered_budget_cap",
    "deep_budget_viability_guardrail",
)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_timestamp(value: str) -> str:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("timestamp fields must be timezone-aware UTC-normalizable strings") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp fields must be timezone-aware UTC-normalizable strings")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_schema_version(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label}: schema_version must be an integer")
    return value


def _require_finite_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be finite")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _require_positive_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


@unique
class FamilyGovernanceStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class FamilyBudgetDecision(str, Enum):
    REGISTER = "register"
    AUTHORIZE = "authorize"
    HOLD = "hold"
    TERMINATE = "terminate"
    REJECT = "reject"


@dataclass(frozen=True)
class ParameterRange:
    parameter_id: str
    lower_bound: float
    upper_bound: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ParameterRange":
        return cls(
            parameter_id=str(payload["parameter_id"]),
            lower_bound=_require_finite_number(
                payload["lower_bound"],
                field_name="lower_bound",
            ),
            upper_bound=_require_finite_number(
                payload["upper_bound"],
                field_name="upper_bound",
            ),
            rationale=str(payload["rationale"]),
        )


@dataclass(frozen=True)
class FamilyBudgetLimits:
    historical_data_spend_limit_usd: float
    compute_spend_limit_usd: float
    tuning_trial_limit: int
    operator_review_hours_limit: float
    exploratory_budget_limit_usd: float
    continuation_budget_limit_usd: float
    deep_budget_requires_viability: bool = True

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyBudgetLimits":
        return cls(
            historical_data_spend_limit_usd=_require_finite_number(
                payload["historical_data_spend_limit_usd"],
                field_name="historical_data_spend_limit_usd",
            ),
            compute_spend_limit_usd=_require_finite_number(
                payload["compute_spend_limit_usd"],
                field_name="compute_spend_limit_usd",
            ),
            tuning_trial_limit=_require_positive_int(
                payload["tuning_trial_limit"],
                field_name="tuning_trial_limit",
            ),
            operator_review_hours_limit=_require_finite_number(
                payload["operator_review_hours_limit"],
                field_name="operator_review_hours_limit",
            ),
            exploratory_budget_limit_usd=_require_finite_number(
                payload["exploratory_budget_limit_usd"],
                field_name="exploratory_budget_limit_usd",
            ),
            continuation_budget_limit_usd=_require_finite_number(
                payload["continuation_budget_limit_usd"],
                field_name="continuation_budget_limit_usd",
            ),
            deep_budget_requires_viability=_require_bool(
                payload.get("deep_budget_requires_viability", True)
                ,
                field_name="deep_budget_requires_viability",
            ),
        )


@dataclass(frozen=True)
class StrategyFamilyPreregistration:
    registration_id: str
    family_id: str
    subfamily_id: str
    economic_thesis: str
    lane_assumptions: tuple[str, ...]
    target_session_class: str
    intended_execution_style: str
    intended_holding_period: str
    research_symbol: str
    expected_execution_symbol: str
    execution_symbol_tradability_hypothesis: str
    failure_criteria: tuple[str, ...]
    preliminary_parameter_ranges: tuple[ParameterRange, ...]
    primary_evaluation_metrics: tuple[str, ...]
    budget_limits: FamilyBudgetLimits
    created_at_utc: str = field(default_factory=_utcnow)
    schema_version: int = SUPPORTED_FAMILY_PREREGISTRATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["preliminary_parameter_ranges"] = [
            item.to_dict() for item in self.preliminary_parameter_ranges
        ]
        payload["budget_limits"] = self.budget_limits.to_dict()
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyFamilyPreregistration":
        return cls(
            registration_id=str(payload["registration_id"]),
            family_id=str(payload["family_id"]),
            subfamily_id=str(payload["subfamily_id"]),
            economic_thesis=str(payload["economic_thesis"]),
            lane_assumptions=tuple(str(item) for item in payload["lane_assumptions"]),
            target_session_class=str(payload["target_session_class"]),
            intended_execution_style=str(payload["intended_execution_style"]),
            intended_holding_period=str(payload["intended_holding_period"]),
            research_symbol=str(payload["research_symbol"]),
            expected_execution_symbol=str(payload["expected_execution_symbol"]),
            execution_symbol_tradability_hypothesis=str(
                payload["execution_symbol_tradability_hypothesis"]
            ),
            failure_criteria=tuple(str(item) for item in payload["failure_criteria"]),
            preliminary_parameter_ranges=tuple(
                ParameterRange.from_dict(dict(item))
                for item in payload["preliminary_parameter_ranges"]
            ),
            primary_evaluation_metrics=tuple(
                str(item) for item in payload["primary_evaluation_metrics"]
            ),
            budget_limits=FamilyBudgetLimits.from_dict(dict(payload["budget_limits"])),
            created_at_utc=_normalize_timestamp(str(payload["created_at_utc"])),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                label="family_preregistration",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "StrategyFamilyPreregistration":
        return cls.from_dict(
            _decode_json_object(payload, label="family preregistration payload")
        )


@dataclass(frozen=True)
class ContinuationEvidenceSummary:
    evidence_reference_ids: tuple[str, ...]
    quality_findings: tuple[str, ...]
    economics_findings: tuple[str, ...]
    metric_references: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContinuationEvidenceSummary":
        return cls(
            evidence_reference_ids=tuple(
                str(item) for item in payload["evidence_reference_ids"]
            ),
            quality_findings=tuple(str(item) for item in payload["quality_findings"]),
            economics_findings=tuple(
                str(item) for item in payload["economics_findings"]
            ),
            metric_references=tuple(str(item) for item in payload["metric_references"]),
        )


@dataclass(frozen=True)
class ViabilityDecisionReference:
    gate_type: str
    report_id: str
    execution_symbol: str
    viability_passed: bool
    deep_promotable_budget_allowed: bool
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ViabilityDecisionReference":
        return cls(
            gate_type=str(payload["gate_type"]),
            report_id=str(payload["report_id"]),
            execution_symbol=str(payload["execution_symbol"]),
            viability_passed=_require_bool(
                payload["viability_passed"],
                field_name="viability_passed",
            ),
            deep_promotable_budget_allowed=_require_bool(
                payload["deep_promotable_budget_allowed"],
                field_name="deep_promotable_budget_allowed",
            ),
            reason_code=str(payload["reason_code"]),
        )


@dataclass(frozen=True)
class FamilyBudgetDecisionRequest:
    case_id: str
    preregistration: StrategyFamilyPreregistration
    decision_record: FamilyDecisionRecord
    evidence_summary: ContinuationEvidenceSummary
    viability_reference: ViabilityDecisionReference | None = None
    evaluated_at_utc: str | None = None
    schema_version: int = SUPPORTED_FAMILY_PREREGISTRATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "preregistration": self.preregistration.to_dict(),
            "decision_record": self.decision_record.to_dict(),
            "evidence_summary": self.evidence_summary.to_dict(),
            "viability_reference": (
                None if self.viability_reference is None else self.viability_reference.to_dict()
            ),
            "evaluated_at_utc": self.evaluated_at_utc,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyBudgetDecisionRequest":
        viability_payload = payload.get("viability_reference")
        return cls(
            case_id=str(payload["case_id"]),
            preregistration=StrategyFamilyPreregistration.from_dict(
                dict(payload["preregistration"])
            ),
            decision_record=FamilyDecisionRecord.from_dict(dict(payload["decision_record"])),
            evidence_summary=ContinuationEvidenceSummary.from_dict(
                dict(payload["evidence_summary"])
            ),
            viability_reference=(
                None
                if viability_payload is None
                else ViabilityDecisionReference.from_dict(dict(viability_payload))
            ),
            evaluated_at_utc=(
                None
                if payload.get("evaluated_at_utc") is None
                else _normalize_timestamp(str(payload["evaluated_at_utc"]))
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                label="family_budget_decision_request",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "FamilyBudgetDecisionRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="family budget decision payload")
        )


@dataclass(frozen=True)
class FamilyGovernanceCheckResult:
    check_id: str
    passed: bool
    reason_code: str
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyGovernanceCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            passed=_require_bool(payload["passed"], field_name="passed"),
            reason_code=str(payload["reason_code"]),
            diagnostic=str(payload["diagnostic"]),
        )


@dataclass(frozen=True)
class FamilyGovernanceLogEntry:
    stage: str
    reason_code: str
    message: str
    references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyGovernanceLogEntry":
        return cls(
            stage=str(payload["stage"]),
            reason_code=str(payload["reason_code"]),
            message=str(payload["message"]),
            references=tuple(str(item) for item in payload.get("references", ())),
        )


@dataclass(frozen=True)
class FamilyPreregistrationReport:
    registration_id: str
    family_id: str
    subfamily_id: str
    status: str
    decision: str
    reason_code: str
    deep_budget_threshold_usd: float
    triggered_check_ids: tuple[str, ...]
    check_results: tuple[FamilyGovernanceCheckResult, ...]
    decision_log: tuple[FamilyGovernanceLogEntry, ...]
    evaluated_at_utc: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "registration_id": self.registration_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "status": self.status,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "deep_budget_threshold_usd": self.deep_budget_threshold_usd,
            "triggered_check_ids": list(self.triggered_check_ids),
            "check_results": [item.to_dict() for item in self.check_results],
            "decision_log": [item.to_dict() for item in self.decision_log],
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyPreregistrationReport":
        return cls(
            registration_id=str(payload["registration_id"]),
            family_id=str(payload["family_id"]),
            subfamily_id=str(payload["subfamily_id"]),
            status=str(payload["status"]),
            decision=str(payload["decision"]),
            reason_code=str(payload["reason_code"]),
            deep_budget_threshold_usd=_require_finite_number(
                payload["deep_budget_threshold_usd"],
                field_name="deep_budget_threshold_usd",
            ),
            triggered_check_ids=tuple(
                str(item) for item in payload["triggered_check_ids"]
            ),
            check_results=tuple(
                FamilyGovernanceCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            decision_log=tuple(
                FamilyGovernanceLogEntry.from_dict(dict(item))
                for item in payload["decision_log"]
            ),
            evaluated_at_utc=_normalize_timestamp(str(payload["evaluated_at_utc"])),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "FamilyPreregistrationReport":
        return cls.from_dict(
            _decode_json_object(payload, label="family preregistration report payload")
        )


@dataclass(frozen=True)
class FamilyBudgetDecisionReport:
    case_id: str
    registration_id: str
    decision_record_id: str
    family_id: str
    status: str
    decision: str
    reason_code: str
    authorized_budget_usd: float
    deep_budget_requested: bool
    viability_gate_required: bool
    viability_gate_passed: bool
    triggered_check_ids: tuple[str, ...]
    check_results: tuple[FamilyGovernanceCheckResult, ...]
    decision_log: tuple[FamilyGovernanceLogEntry, ...]
    guardrail_trace: dict[str, Any] | None = None
    evaluated_at_utc: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "registration_id": self.registration_id,
            "decision_record_id": self.decision_record_id,
            "family_id": self.family_id,
            "status": self.status,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "authorized_budget_usd": self.authorized_budget_usd,
            "deep_budget_requested": self.deep_budget_requested,
            "viability_gate_required": self.viability_gate_required,
            "viability_gate_passed": self.viability_gate_passed,
            "triggered_check_ids": list(self.triggered_check_ids),
            "check_results": [item.to_dict() for item in self.check_results],
            "decision_log": [item.to_dict() for item in self.decision_log],
            "guardrail_trace": self.guardrail_trace,
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyBudgetDecisionReport":
        return cls(
            case_id=str(payload["case_id"]),
            registration_id=str(payload["registration_id"]),
            decision_record_id=str(payload["decision_record_id"]),
            family_id=str(payload["family_id"]),
            status=str(payload["status"]),
            decision=str(payload["decision"]),
            reason_code=str(payload["reason_code"]),
            authorized_budget_usd=_require_finite_number(
                payload["authorized_budget_usd"],
                field_name="authorized_budget_usd",
            ),
            deep_budget_requested=_require_bool(
                payload["deep_budget_requested"],
                field_name="deep_budget_requested",
            ),
            viability_gate_required=_require_bool(
                payload["viability_gate_required"],
                field_name="viability_gate_required",
            ),
            viability_gate_passed=_require_bool(
                payload["viability_gate_passed"],
                field_name="viability_gate_passed",
            ),
            triggered_check_ids=tuple(
                str(item) for item in payload["triggered_check_ids"]
            ),
            check_results=tuple(
                FamilyGovernanceCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            decision_log=tuple(
                FamilyGovernanceLogEntry.from_dict(dict(item))
                for item in payload["decision_log"]
            ),
            guardrail_trace=(
                None
                if payload.get("guardrail_trace") is None
                else dict(payload["guardrail_trace"])
            ),
            evaluated_at_utc=_normalize_timestamp(str(payload["evaluated_at_utc"])),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "FamilyBudgetDecisionReport":
        return cls.from_dict(
            _decode_json_object(payload, label="family budget decision report payload")
        )


def _check(
    check_id: str,
    *,
    passed: bool,
    reason_code: str,
    diagnostic: str,
) -> FamilyGovernanceCheckResult:
    return FamilyGovernanceCheckResult(
        check_id=check_id,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
    )


def _decision_log(
    stage: str,
    reason_code: str,
    message: str,
    references: tuple[str, ...] = (),
) -> FamilyGovernanceLogEntry:
    return FamilyGovernanceLogEntry(
        stage=stage,
        reason_code=reason_code,
        message=message,
        references=references,
    )


def validate_family_preregistration_contract() -> list[str]:
    errors: list[str] = []
    if len(PREREGISTRATION_CHECK_IDS) != len(set(PREREGISTRATION_CHECK_IDS)):
        errors.append("preregistration check ids must be unique")
    if len(CONTINUATION_CHECK_IDS) != len(set(CONTINUATION_CHECK_IDS)):
        errors.append("continuation check ids must be unique")
    if len(SUPPORTED_VIABILITY_GATE_TYPES) != len(set(SUPPORTED_VIABILITY_GATE_TYPES)):
        errors.append("supported viability gate types must be unique")
    return errors


VALIDATION_ERRORS = validate_family_preregistration_contract()


def validate_family_preregistration(
    preregistration: StrategyFamilyPreregistration,
) -> FamilyPreregistrationReport:
    checks: list[FamilyGovernanceCheckResult] = []

    metadata_complete = (
        preregistration.schema_version == SUPPORTED_FAMILY_PREREGISTRATION_SCHEMA_VERSION
        and all(
            bool(getattr(preregistration, field_name))
            for field_name in REQUIRED_PREREGISTRATION_FIELDS
        )
        and bool(preregistration.lane_assumptions)
        and bool(preregistration.failure_criteria)
        and bool(preregistration.primary_evaluation_metrics)
    )
    checks.append(
        _check(
            PREREGISTRATION_CHECK_IDS[0],
            passed=metadata_complete,
            reason_code=(
                "FAMILY_PREREGISTRATION_METADATA_COMPLETE"
                if metadata_complete
                else "FAMILY_PREREGISTRATION_MISSING_REQUIRED_FIELDS"
            ),
            diagnostic=(
                "Economic thesis, lane assumptions, symbols, failure criteria, and metrics are all declared."
                if metadata_complete
                else "Preregistration must declare thesis, lane assumptions, symbols, failure criteria, and primary metrics."
            ),
        )
    )

    parameter_ids = [
        parameter.parameter_id for parameter in preregistration.preliminary_parameter_ranges
    ]
    parameter_ranges_valid = (
        bool(preregistration.preliminary_parameter_ranges)
        and len(parameter_ids) == len(set(parameter_ids))
        and all(
            parameter.parameter_id
            and parameter.lower_bound < parameter.upper_bound
            and bool(parameter.rationale)
            for parameter in preregistration.preliminary_parameter_ranges
        )
    )
    checks.append(
        _check(
            PREREGISTRATION_CHECK_IDS[1],
            passed=parameter_ranges_valid,
            reason_code=(
                "FAMILY_PREREGISTRATION_PARAMETER_RANGES_VALID"
                if parameter_ranges_valid
                else "FAMILY_PREREGISTRATION_PARAMETER_RANGES_INVALID"
            ),
            diagnostic=(
                "Preliminary parameter ranges are unique, bounded, and justified."
                if parameter_ranges_valid
                else "Preregistration must include unique parameter ranges with lower<upper bounds and rationales."
            ),
        )
    )

    budgets = preregistration.budget_limits
    budget_profile_valid = (
        budgets.historical_data_spend_limit_usd >= 0
        and budgets.compute_spend_limit_usd >= 0
        and budgets.tuning_trial_limit > 0
        and budgets.operator_review_hours_limit > 0
        and budgets.exploratory_budget_limit_usd > 0
        and budgets.continuation_budget_limit_usd >= budgets.exploratory_budget_limit_usd
    )
    checks.append(
        _check(
            PREREGISTRATION_CHECK_IDS[2],
            passed=budget_profile_valid,
            reason_code=(
                "FAMILY_PREREGISTRATION_BUDGET_LIMITS_VALID"
                if budget_profile_valid
                else "FAMILY_PREREGISTRATION_BUDGET_LIMITS_INVALID"
            ),
            diagnostic=(
                "Budget caps are positive and continuation cap does not undercut exploratory cap."
                if budget_profile_valid
                else "Budget profile must declare non-negative spend caps, a positive trial/review budget, and continuation>=exploratory."
            ),
        )
    )

    triggered_check_ids = tuple(check.check_id for check in checks if not check.passed)
    passed = not triggered_check_ids
    return FamilyPreregistrationReport(
        registration_id=preregistration.registration_id,
        family_id=preregistration.family_id,
        subfamily_id=preregistration.subfamily_id,
        status=(
            FamilyGovernanceStatus.PASS.value
            if passed
            else FamilyGovernanceStatus.INVALID.value
        ),
        decision=(
            FamilyBudgetDecision.REGISTER.value
            if passed
            else FamilyBudgetDecision.REJECT.value
        ),
        reason_code=(
            "FAMILY_PREREGISTRATION_VALID"
            if passed
            else checks[next(index for index, check in enumerate(checks) if not check.passed)].reason_code
        ),
        deep_budget_threshold_usd=budgets.exploratory_budget_limit_usd,
        triggered_check_ids=triggered_check_ids,
        check_results=tuple(checks),
        decision_log=(
            _decision_log(
                stage="preregistration",
                reason_code=(
                    "FAMILY_PREREGISTRATION_VALID"
                    if passed
                    else "FAMILY_PREREGISTRATION_REJECTED"
                ),
                message=(
                    "Strategy family preregistration captured thesis, metrics, ranges, and explicit budgets."
                    if passed
                    else "Strategy family preregistration is incomplete and cannot anchor continuation decisions."
                ),
                references=(
                    preregistration.registration_id,
                    preregistration.family_id,
                    preregistration.expected_execution_symbol,
                ),
            ),
        ),
    )


def evaluate_family_budget_decision(
    request: FamilyBudgetDecisionRequest,
) -> FamilyBudgetDecisionReport:
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()
    preregistration_report = validate_family_preregistration(request.preregistration)
    checks: list[FamilyGovernanceCheckResult] = []
    decision_log: list[FamilyGovernanceLogEntry] = []

    preregistration_valid = preregistration_report.status == FamilyGovernanceStatus.PASS.value
    checks.append(
        _check(
            CONTINUATION_CHECK_IDS[0],
            passed=preregistration_valid,
            reason_code=(
                "FAMILY_CONTINUATION_PREREGISTRATION_VALID"
                if preregistration_valid
                else "FAMILY_CONTINUATION_PREREGISTRATION_INVALID"
            ),
            diagnostic=(
                "Preregistration is valid and can anchor a family_decision_record."
                if preregistration_valid
                else "Preregistration must validate before continuation budgets can be authorized."
            ),
        )
    )

    canonical_alignment = (
        request.decision_record.family_id == request.preregistration.family_id
        and request.evidence_summary.evidence_reference_ids
        == request.decision_record.evidence_references
        and bool(request.decision_record.reason_bundle)
        and (
            request.decision_record.decision_type == FamilyDecisionType.TERMINATE
            or request.decision_record.next_budget_authorized_usd > 0
        )
    )
    checks.append(
        _check(
            CONTINUATION_CHECK_IDS[1],
            passed=canonical_alignment,
            reason_code=(
                "FAMILY_CONTINUATION_DECISION_RECORD_ALIGNED"
                if canonical_alignment
                else "FAMILY_CONTINUATION_DECISION_RECORD_MISMATCH"
            ),
            diagnostic=(
                "family_decision_record family, evidence references, and budget semantics align with preregistration."
                if canonical_alignment
                else "family_decision_record must match preregistration family_id, evidence references, and non-terminal budget semantics."
            ),
        )
    )

    metric_alignment = set(request.evidence_summary.metric_references).issubset(
        set(request.preregistration.primary_evaluation_metrics)
    )
    structured_summary_present = (
        bool(request.evidence_summary.quality_findings)
        and bool(request.evidence_summary.economics_findings)
        and bool(request.evidence_summary.metric_references)
        and metric_alignment
    )
    checks.append(
        _check(
            CONTINUATION_CHECK_IDS[2],
            passed=structured_summary_present,
            reason_code=(
                "FAMILY_CONTINUATION_STRUCTURED_SUMMARY_VALID"
                if structured_summary_present
                else "FAMILY_CONTINUATION_STRUCTURED_SUMMARY_INVALID"
            ),
            diagnostic=(
                "Continuation summary retains research-quality findings, economics findings, and preregistered metrics."
                if structured_summary_present
                else "Continuation summary must include research-quality findings, economics findings, and preregistered metrics."
            ),
        )
    )

    budget_within_cap = (
        request.decision_record.budget_consumed_usd >= 0
        and request.decision_record.next_budget_authorized_usd
        <= request.preregistration.budget_limits.continuation_budget_limit_usd
    )
    checks.append(
        _check(
            CONTINUATION_CHECK_IDS[3],
            passed=budget_within_cap,
            reason_code=(
                "FAMILY_CONTINUATION_BUDGET_WITHIN_CAP"
                if budget_within_cap
                else "FAMILY_CONTINUATION_BUDGET_EXCEEDS_REGISTERED_CAP"
            ),
            diagnostic=(
                "Authorized continuation budget stays within the preregistered continuation cap."
                if budget_within_cap
                else "Continuation decision exceeds the preregistered continuation budget cap."
            ),
        )
    )

    deep_budget_requested = (
        request.decision_record.decision_type != FamilyDecisionType.TERMINATE
        and request.decision_record.next_budget_authorized_usd
        > request.preregistration.budget_limits.exploratory_budget_limit_usd
    )
    viability_gate_required = (
        request.preregistration.budget_limits.deep_budget_requires_viability
        and deep_budget_requested
    )
    viability_gate_passed = False
    if not viability_gate_required:
        viability_passed = True
        viability_reason_code = "FAMILY_CONTINUATION_DEEP_BUDGET_NOT_REQUIRED"
        viability_diagnostic = "Requested budget stays within exploratory limits or preregistration does not require a viability gate."
        guardrail_trace = None
    else:
        viability_reference = request.viability_reference
        viability_passed = bool(
            viability_reference is not None
            and viability_reference.gate_type in SUPPORTED_VIABILITY_GATE_TYPES
            and viability_reference.execution_symbol
            == request.preregistration.expected_execution_symbol
            and viability_reference.viability_passed
            and viability_reference.deep_promotable_budget_allowed
        )
        guardrail = check_guardrail(
            PrincipleID.P13_NO_DEEP_BUDGET_BEFORE_VIABILITY,
            condition_met=viability_passed,
            diagnostic=(
                "Deep continuation budget is backed by a passed viability gate on the intended execution lane."
                if viability_passed
                else "Deep continuation budget requires a passed viability gate on the intended execution lane."
            ),
            context={
                "registration_id": request.preregistration.registration_id,
                "decision_record_id": request.decision_record.decision_record_id,
                "expected_execution_symbol": request.preregistration.expected_execution_symbol,
                "viability_reference": (
                    None if viability_reference is None else viability_reference.to_dict()
                ),
            },
        )
        guardrail_trace = guardrail.to_dict()
        viability_reason_code = (
            "FAMILY_CONTINUATION_DEEP_BUDGET_VIABILITY_VALID"
            if viability_passed
            else "FAMILY_CONTINUATION_DEEP_BUDGET_VIABILITY_MISSING"
        )
        viability_diagnostic = (
            "Deep continuation budget is backed by a valid viability reference."
            if viability_passed
            else "Deep continuation budget is missing a passed viability reference for the intended execution symbol."
        )
    viability_gate_passed = viability_passed
    checks.append(
        _check(
            CONTINUATION_CHECK_IDS[4],
            passed=viability_passed,
            reason_code=viability_reason_code,
            diagnostic=viability_diagnostic,
        )
    )

    decision_log.append(
        _decision_log(
            stage="decision_record",
            reason_code="FAMILY_CONTINUATION_DECISION_LOGGED",
            message="Continuation decision references canonical family_decision_record evidence and budget fields.",
            references=(
                request.preregistration.registration_id,
                request.decision_record.decision_record_id,
                *request.decision_record.evidence_references,
            ),
        )
    )
    decision_log.append(
        _decision_log(
            stage="summary",
            reason_code="FAMILY_CONTINUATION_SUMMARY_CAPTURED",
            message=(
                f"Captured {len(request.evidence_summary.quality_findings)} quality findings and "
                f"{len(request.evidence_summary.economics_findings)} economics findings."
            ),
            references=request.evidence_summary.metric_references,
        )
    )
    if viability_gate_required:
        decision_log.append(
            _decision_log(
                stage="guardrail",
                reason_code=viability_reason_code,
                message=viability_diagnostic,
                references=(
                    ()
                    if request.viability_reference is None
                    else (request.viability_reference.report_id,)
                ),
            )
        )

    invalid_failure_ids = {
        CONTINUATION_CHECK_IDS[0],
        CONTINUATION_CHECK_IDS[1],
        CONTINUATION_CHECK_IDS[2],
    }
    triggered_check_ids = tuple(check.check_id for check in checks if not check.passed)
    invalid_triggered = tuple(
        check_id for check_id in triggered_check_ids if check_id in invalid_failure_ids
    )
    violation_triggered = tuple(
        check_id for check_id in triggered_check_ids if check_id not in invalid_failure_ids
    )

    if invalid_triggered:
        status = FamilyGovernanceStatus.INVALID.value
        decision = FamilyBudgetDecision.REJECT.value
        reason_code = next(
            check.reason_code for check in checks if check.check_id == invalid_triggered[0]
        )
    elif violation_triggered:
        status = FamilyGovernanceStatus.VIOLATION.value
        decision = FamilyBudgetDecision.REJECT.value
        reason_code = next(
            check.reason_code for check in checks if check.check_id == violation_triggered[0]
        )
    elif request.decision_record.decision_type == FamilyDecisionType.PAUSE:
        status = FamilyGovernanceStatus.PASS.value
        decision = FamilyBudgetDecision.HOLD.value
        reason_code = "FAMILY_CONTINUATION_PAUSED"
    elif request.decision_record.decision_type == FamilyDecisionType.TERMINATE:
        status = FamilyGovernanceStatus.PASS.value
        decision = FamilyBudgetDecision.TERMINATE.value
        reason_code = "FAMILY_CONTINUATION_TERMINATED"
    else:
        status = FamilyGovernanceStatus.PASS.value
        decision = FamilyBudgetDecision.AUTHORIZE.value
        reason_code = "FAMILY_CONTINUATION_AUTHORIZED"

    decision_log.append(
        _decision_log(
            stage="decision",
            reason_code=reason_code,
            message=(
                "Continuation budget decision is fully structured and queryable."
                if status == FamilyGovernanceStatus.PASS.value
                else "Continuation budget decision is rejected because required governance evidence is incomplete or blocked."
            ),
            references=(
                request.decision_record.decision_record_id,
                request.preregistration.registration_id,
            ),
        )
    )

    return FamilyBudgetDecisionReport(
        case_id=request.case_id,
        registration_id=request.preregistration.registration_id,
        decision_record_id=request.decision_record.decision_record_id,
        family_id=request.preregistration.family_id,
        status=status,
        decision=decision,
        reason_code=reason_code,
        authorized_budget_usd=request.decision_record.next_budget_authorized_usd,
        deep_budget_requested=deep_budget_requested,
        viability_gate_required=viability_gate_required,
        viability_gate_passed=viability_gate_passed,
        triggered_check_ids=triggered_check_ids,
        check_results=tuple(checks),
        decision_log=tuple(decision_log),
        guardrail_trace=guardrail_trace,
        evaluated_at_utc=evaluated_at_utc,
    )
