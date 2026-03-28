"""Null-suite and discovery-accounting contracts for promotable research."""

from __future__ import annotations

import datetime
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.family_preregistration import StrategyFamilyPreregistration
from shared.policy.guardrails import check_guardrail
from shared.policy.principles import PrincipleID
from shared.policy.research_state import FamilyDecisionRecord, FamilyDecisionType

SUPPORTED_DISCOVERY_ACCOUNTING_SCHEMA_VERSION = 1
REQUIRED_NULL_MODEL_IDS = (
    "random_entry",
    "time_shifted_anchor",
    "side_flipped_or_ablated",
    "permutation",
    "regime_conditional",
)
DISCOVERY_ACCOUNTING_CHECK_IDS = (
    "null_suite_coverage",
    "family_discovery_accounting",
    "program_discovery_ledger",
    "continuation_gate",
)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
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
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object payload")
    return loaded


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_schema_version(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label}: schema_version must be an integer")
    if value != SUPPORTED_DISCOVERY_ACCOUNTING_SCHEMA_VERSION:
        raise ValueError(
            f"{label}: unsupported schema version {value}; "
            f"expected {SUPPORTED_DISCOVERY_ACCOUNTING_SCHEMA_VERSION}"
        )
    return value


def _require_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name} must be numeric")
    return parsed


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must be a sequence of strings")
        items.append(item)
    return tuple(items)


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return dict(value)


def _require_mapping_sequence(
    value: object,
    *,
    field_name: str,
) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence of mappings")
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} must be a sequence of mappings")
        items.append(dict(item))
    return tuple(items)


@unique
class DiscoveryAccountingStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class DiscoveryAccountingDecision(str, Enum):
    ALLOW_EXPLORATORY = "allow_exploratory"
    ALLOW_WITH_CONTINUATION = "allow_with_continuation"
    BLOCK = "block"


@dataclass(frozen=True)
class NullComparisonDelta:
    metric_id: str
    baseline_value: float
    observed_value: float
    delta_value: float
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NullComparisonDelta":
        return cls(
            metric_id=_require_non_empty_string(
                payload["metric_id"],
                field_name="null_comparison_delta.metric_id",
            ),
            baseline_value=_require_float(
                payload["baseline_value"],
                field_name="null_comparison_delta.baseline_value",
            ),
            observed_value=_require_float(
                payload["observed_value"],
                field_name="null_comparison_delta.observed_value",
            ),
            delta_value=_require_float(
                payload["delta_value"],
                field_name="null_comparison_delta.delta_value",
            ),
            interpretation=_require_string(
                payload["interpretation"],
                field_name="null_comparison_delta.interpretation",
            ),
        )


@dataclass(frozen=True)
class NullSuiteEntry:
    null_model_id: str
    study_id: str
    completed: bool
    sample_count: int
    retained_artifact_ids: tuple[str, ...]
    retained_log_ids: tuple[str, ...]
    diagnostic_deltas: tuple[NullComparisonDelta, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["diagnostic_deltas"] = [item.to_dict() for item in self.diagnostic_deltas]
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NullSuiteEntry":
        return cls(
            null_model_id=_require_non_empty_string(
                payload["null_model_id"],
                field_name="null_suite_entry.null_model_id",
            ),
            study_id=_require_non_empty_string(
                payload["study_id"],
                field_name="null_suite_entry.study_id",
            ),
            completed=_require_bool(payload["completed"], field_name="completed"),
            sample_count=_require_int(payload["sample_count"], field_name="sample_count"),
            retained_artifact_ids=_require_string_sequence(
                payload["retained_artifact_ids"],
                field_name="null_suite_entry.retained_artifact_ids",
            ),
            retained_log_ids=_require_string_sequence(
                payload["retained_log_ids"],
                field_name="null_suite_entry.retained_log_ids",
            ),
            diagnostic_deltas=tuple(
                NullComparisonDelta.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["diagnostic_deltas"],
                    field_name="null_suite_entry.diagnostic_deltas",
                )
            ),
        )


@dataclass(frozen=True)
class FamilyDiscoveryLedgerEntry:
    family_id: str
    subfamily_id: str
    research_run_ids: tuple[str, ...]
    promotable_trial_count: int
    null_comparison_count: int
    historical_data_spend_usd: float
    compute_spend_usd: float
    operator_review_hours: float
    requested_next_budget_usd: float
    retained_log_ids: tuple[str, ...]
    correlation_id: str
    diagnostic_delta_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FamilyDiscoveryLedgerEntry":
        return cls(
            family_id=_require_non_empty_string(
                payload["family_id"],
                field_name="family_discovery_ledger_entry.family_id",
            ),
            subfamily_id=_require_non_empty_string(
                payload["subfamily_id"],
                field_name="family_discovery_ledger_entry.subfamily_id",
            ),
            research_run_ids=_require_string_sequence(
                payload["research_run_ids"],
                field_name="family_discovery_ledger_entry.research_run_ids",
            ),
            promotable_trial_count=_require_int(
                payload["promotable_trial_count"],
                field_name="promotable_trial_count",
            ),
            null_comparison_count=_require_int(
                payload["null_comparison_count"],
                field_name="null_comparison_count",
            ),
            historical_data_spend_usd=_require_float(
                payload["historical_data_spend_usd"],
                field_name="family_discovery_ledger_entry.historical_data_spend_usd",
            ),
            compute_spend_usd=_require_float(
                payload["compute_spend_usd"],
                field_name="family_discovery_ledger_entry.compute_spend_usd",
            ),
            operator_review_hours=_require_float(
                payload["operator_review_hours"],
                field_name="family_discovery_ledger_entry.operator_review_hours",
            ),
            requested_next_budget_usd=_require_float(
                payload["requested_next_budget_usd"],
                field_name="family_discovery_ledger_entry.requested_next_budget_usd",
            ),
            retained_log_ids=_require_string_sequence(
                payload["retained_log_ids"],
                field_name="family_discovery_ledger_entry.retained_log_ids",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="family_discovery_ledger_entry.correlation_id",
            ),
            diagnostic_delta_ids=_require_string_sequence(
                payload["diagnostic_delta_ids"],
                field_name="family_discovery_ledger_entry.diagnostic_delta_ids",
            ),
        )


@dataclass(frozen=True)
class ProgramDiscoveryLedger:
    ledger_id: str
    family_entries: tuple[FamilyDiscoveryLedgerEntry, ...]
    cumulative_promotable_trial_count: int
    cumulative_null_comparison_count: int
    cumulative_data_spend_usd: float
    cumulative_compute_spend_usd: float
    cumulative_operator_review_hours: float
    continuation_decision_record_ids: tuple[str, ...]
    recorded_at_utc: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["family_entries"] = [entry.to_dict() for entry in self.family_entries]
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProgramDiscoveryLedger":
        return cls(
            ledger_id=_require_non_empty_string(
                payload["ledger_id"],
                field_name="program_discovery_ledger.ledger_id",
            ),
            family_entries=tuple(
                FamilyDiscoveryLedgerEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["family_entries"],
                    field_name="program_discovery_ledger.family_entries",
                )
            ),
            cumulative_promotable_trial_count=_require_int(
                payload["cumulative_promotable_trial_count"],
                field_name="cumulative_promotable_trial_count",
            ),
            cumulative_null_comparison_count=_require_int(
                payload["cumulative_null_comparison_count"],
                field_name="cumulative_null_comparison_count",
            ),
            cumulative_data_spend_usd=_require_float(
                payload["cumulative_data_spend_usd"],
                field_name="program_discovery_ledger.cumulative_data_spend_usd",
            ),
            cumulative_compute_spend_usd=_require_float(
                payload["cumulative_compute_spend_usd"],
                field_name="program_discovery_ledger.cumulative_compute_spend_usd",
            ),
            cumulative_operator_review_hours=_require_float(
                payload["cumulative_operator_review_hours"],
                field_name="program_discovery_ledger.cumulative_operator_review_hours",
            ),
            continuation_decision_record_ids=_require_string_sequence(
                payload["continuation_decision_record_ids"],
                field_name="program_discovery_ledger.continuation_decision_record_ids",
            ),
            recorded_at_utc=_normalize_timestamp(
                payload["recorded_at_utc"],
                field_name="program_discovery_ledger.recorded_at_utc",
            ),
        )


@dataclass(frozen=True)
class DiscoveryAccountingRequest:
    case_id: str
    preregistration: StrategyFamilyPreregistration
    family_ledger: FamilyDiscoveryLedgerEntry
    null_suite_entries: tuple[NullSuiteEntry, ...]
    program_ledger: ProgramDiscoveryLedger
    continuation_decision: FamilyDecisionRecord | None = None
    evaluated_at_utc: str | None = None
    schema_version: int = SUPPORTED_DISCOVERY_ACCOUNTING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "preregistration": self.preregistration.to_dict(),
            "family_ledger": self.family_ledger.to_dict(),
            "null_suite_entries": [entry.to_dict() for entry in self.null_suite_entries],
            "program_ledger": self.program_ledger.to_dict(),
            "continuation_decision": (
                None if self.continuation_decision is None else self.continuation_decision.to_dict()
            ),
            "evaluated_at_utc": self.evaluated_at_utc,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiscoveryAccountingRequest":
        continuation_payload = payload.get("continuation_decision")
        return cls(
            case_id=_require_non_empty_string(
                payload["case_id"],
                field_name="discovery_accounting_request.case_id",
            ),
            preregistration=StrategyFamilyPreregistration.from_dict(
                _require_mapping(
                    payload["preregistration"],
                    field_name="discovery_accounting_request.preregistration",
                )
            ),
            family_ledger=FamilyDiscoveryLedgerEntry.from_dict(
                _require_mapping(
                    payload["family_ledger"],
                    field_name="discovery_accounting_request.family_ledger",
                )
            ),
            null_suite_entries=tuple(
                NullSuiteEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["null_suite_entries"],
                    field_name="discovery_accounting_request.null_suite_entries",
                )
            ),
            program_ledger=ProgramDiscoveryLedger.from_dict(
                _require_mapping(
                    payload["program_ledger"],
                    field_name="discovery_accounting_request.program_ledger",
                )
            ),
            continuation_decision=(
                None
                if continuation_payload is None
                else FamilyDecisionRecord.from_dict(
                    _require_mapping(
                        continuation_payload,
                        field_name="discovery_accounting_request.continuation_decision",
                    )
                )
            ),
            evaluated_at_utc=(
                None
                if payload.get("evaluated_at_utc") is None
                else _normalize_timestamp(
                    payload["evaluated_at_utc"],
                    field_name="discovery_accounting_request.evaluated_at_utc",
                )
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                label="discovery_accounting_request",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "DiscoveryAccountingRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="discovery_accounting_request")
        )


@dataclass(frozen=True)
class DiscoveryAccountingCheckResult:
    check_id: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiscoveryAccountingCheckResult":
        return cls(
            check_id=_require_non_empty_string(
                payload["check_id"],
                field_name="discovery_accounting_check_result.check_id",
            ),
            passed=_require_bool(payload["passed"], field_name="passed"),
            reason_code=_require_string(
                payload["reason_code"],
                field_name="discovery_accounting_check_result.reason_code",
            ),
            diagnostic=_require_string(
                payload["diagnostic"],
                field_name="discovery_accounting_check_result.diagnostic",
            ),
            evidence=_require_mapping(
                payload.get("evidence", {}),
                field_name="discovery_accounting_check_result.evidence",
            ),
        )


@dataclass(frozen=True)
class DiscoveryAccountingLogEntry:
    stage: str
    reason_code: str
    message: str
    references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiscoveryAccountingLogEntry":
        return cls(
            stage=_require_string(
                payload["stage"],
                field_name="discovery_accounting_log_entry.stage",
            ),
            reason_code=_require_string(
                payload["reason_code"],
                field_name="discovery_accounting_log_entry.reason_code",
            ),
            message=_require_string(
                payload["message"],
                field_name="discovery_accounting_log_entry.message",
            ),
            references=_require_string_sequence(
                payload.get("references", ()),
                field_name="discovery_accounting_log_entry.references",
            ),
        )


@dataclass(frozen=True)
class DiscoveryAccountingReport:
    case_id: str
    family_id: str
    subfamily_id: str
    status: str
    decision: str
    reason_code: str
    exploratory_budget_limit_usd: float
    continuation_budget_limit_usd: float
    family_total_spend_usd: float
    family_promotable_trial_count: int
    program_total_spend_usd: float
    program_promotable_trial_count: int
    remaining_exploratory_budget_usd: float
    completed_null_model_ids: tuple[str, ...]
    triggered_check_ids: tuple[str, ...]
    check_results: tuple[DiscoveryAccountingCheckResult, ...]
    decision_log: tuple[DiscoveryAccountingLogEntry, ...]
    continuation_decision_record_id: str | None = None
    guardrail_trace: dict[str, Any] | None = None
    evaluated_at_utc: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "status": self.status,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "exploratory_budget_limit_usd": self.exploratory_budget_limit_usd,
            "continuation_budget_limit_usd": self.continuation_budget_limit_usd,
            "family_total_spend_usd": self.family_total_spend_usd,
            "family_promotable_trial_count": self.family_promotable_trial_count,
            "program_total_spend_usd": self.program_total_spend_usd,
            "program_promotable_trial_count": self.program_promotable_trial_count,
            "remaining_exploratory_budget_usd": self.remaining_exploratory_budget_usd,
            "completed_null_model_ids": list(self.completed_null_model_ids),
            "triggered_check_ids": list(self.triggered_check_ids),
            "check_results": [item.to_dict() for item in self.check_results],
            "decision_log": [item.to_dict() for item in self.decision_log],
            "continuation_decision_record_id": self.continuation_decision_record_id,
            "guardrail_trace": self.guardrail_trace,
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DiscoveryAccountingReport":
        return cls(
            case_id=_require_non_empty_string(
                payload["case_id"],
                field_name="discovery_accounting_report.case_id",
            ),
            family_id=_require_non_empty_string(
                payload["family_id"],
                field_name="discovery_accounting_report.family_id",
            ),
            subfamily_id=_require_non_empty_string(
                payload["subfamily_id"],
                field_name="discovery_accounting_report.subfamily_id",
            ),
            status=DiscoveryAccountingStatus(
                _require_string(
                    payload["status"],
                    field_name="discovery_accounting_report.status",
                )
            ).value,
            decision=DiscoveryAccountingDecision(
                _require_string(
                    payload["decision"],
                    field_name="discovery_accounting_report.decision",
                )
            ).value,
            reason_code=_require_string(
                payload["reason_code"],
                field_name="discovery_accounting_report.reason_code",
            ),
            exploratory_budget_limit_usd=_require_float(
                payload["exploratory_budget_limit_usd"],
                field_name="discovery_accounting_report.exploratory_budget_limit_usd",
            ),
            continuation_budget_limit_usd=_require_float(
                payload["continuation_budget_limit_usd"],
                field_name="discovery_accounting_report.continuation_budget_limit_usd",
            ),
            family_total_spend_usd=_require_float(
                payload["family_total_spend_usd"],
                field_name="discovery_accounting_report.family_total_spend_usd",
            ),
            family_promotable_trial_count=_require_int(
                payload["family_promotable_trial_count"],
                field_name="family_promotable_trial_count",
            ),
            program_total_spend_usd=_require_float(
                payload["program_total_spend_usd"],
                field_name="discovery_accounting_report.program_total_spend_usd",
            ),
            program_promotable_trial_count=_require_int(
                payload["program_promotable_trial_count"],
                field_name="program_promotable_trial_count",
            ),
            remaining_exploratory_budget_usd=_require_float(
                payload["remaining_exploratory_budget_usd"],
                field_name="discovery_accounting_report.remaining_exploratory_budget_usd",
            ),
            completed_null_model_ids=_require_string_sequence(
                payload["completed_null_model_ids"],
                field_name="discovery_accounting_report.completed_null_model_ids",
            ),
            triggered_check_ids=_require_string_sequence(
                payload["triggered_check_ids"],
                field_name="discovery_accounting_report.triggered_check_ids",
            ),
            check_results=tuple(
                DiscoveryAccountingCheckResult.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["check_results"],
                    field_name="discovery_accounting_report.check_results",
                )
            ),
            decision_log=tuple(
                DiscoveryAccountingLogEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["decision_log"],
                    field_name="discovery_accounting_report.decision_log",
                )
            ),
            continuation_decision_record_id=_require_optional_string(
                payload.get("continuation_decision_record_id"),
                field_name="discovery_accounting_report.continuation_decision_record_id",
            ),
            guardrail_trace=(
                None
                if payload.get("guardrail_trace") is None
                else _require_mapping(
                    payload["guardrail_trace"],
                    field_name="discovery_accounting_report.guardrail_trace",
                )
            ),
            evaluated_at_utc=_normalize_timestamp(
                payload["evaluated_at_utc"],
                field_name="discovery_accounting_report.evaluated_at_utc",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "DiscoveryAccountingReport":
        return cls.from_dict(
            _decode_json_object(payload, label="discovery_accounting_report")
        )


def _check(
    check_id: str,
    *,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    evidence: dict[str, Any] | None = None,
) -> DiscoveryAccountingCheckResult:
    return DiscoveryAccountingCheckResult(
        check_id=check_id,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence=_jsonable(evidence or {}),
    )


def _log(
    stage: str,
    reason_code: str,
    message: str,
    references: tuple[str, ...] = (),
) -> DiscoveryAccountingLogEntry:
    return DiscoveryAccountingLogEntry(
        stage=stage,
        reason_code=reason_code,
        message=message,
        references=references,
    )


def validate_discovery_accounting_contract() -> list[str]:
    errors: list[str] = []
    if len(REQUIRED_NULL_MODEL_IDS) != len(set(REQUIRED_NULL_MODEL_IDS)):
        errors.append("required null model ids must be unique")
    if len(DISCOVERY_ACCOUNTING_CHECK_IDS) != len(set(DISCOVERY_ACCOUNTING_CHECK_IDS)):
        errors.append("discovery accounting check ids must be unique")
    return errors


VALIDATION_ERRORS = validate_discovery_accounting_contract()


def evaluate_discovery_accounting(
    request: DiscoveryAccountingRequest,
) -> DiscoveryAccountingReport:
    preregistration = request.preregistration
    family_ledger = request.family_ledger
    program_ledger = request.program_ledger
    continuation = request.continuation_decision

    family_total_spend_usd = (
        family_ledger.historical_data_spend_usd + family_ledger.compute_spend_usd
    )
    program_total_spend_usd = (
        program_ledger.cumulative_data_spend_usd
        + program_ledger.cumulative_compute_spend_usd
    )
    completed_null_model_ids = tuple(
        entry.null_model_id for entry in request.null_suite_entries if entry.completed
    )

    checks: list[DiscoveryAccountingCheckResult] = []
    decision_log: list[DiscoveryAccountingLogEntry] = []

    null_entries_by_id = {entry.null_model_id: entry for entry in request.null_suite_entries}
    missing_null_models = tuple(
        model_id for model_id in REQUIRED_NULL_MODEL_IDS if model_id not in null_entries_by_id
    )
    duplicate_null_models = tuple(
        model_id
        for model_id in {
            entry.null_model_id for entry in request.null_suite_entries
        }
        if sum(1 for entry in request.null_suite_entries if entry.null_model_id == model_id) > 1
    )
    incomplete_null_models = tuple(
        entry.null_model_id
        for entry in request.null_suite_entries
        if not entry.completed
        or entry.sample_count <= 0
        or not entry.retained_artifact_ids
        or not entry.retained_log_ids
        or not entry.diagnostic_deltas
    )
    null_suite_valid = not missing_null_models and not duplicate_null_models and not incomplete_null_models
    checks.append(
        _check(
            DISCOVERY_ACCOUNTING_CHECK_IDS[0],
            passed=null_suite_valid,
            reason_code=(
                "DISCOVERY_ACCOUNTING_NULL_SUITE_COMPLETE"
                if null_suite_valid
                else "DISCOVERY_ACCOUNTING_NULL_SUITE_INCOMPLETE"
            ),
            diagnostic=(
                "Required null families are present with retained artifacts, logs, and diagnostic deltas."
                if null_suite_valid
                else "Null suite must cover required families with retained artifacts, logs, and diagnostic deltas."
            ),
            evidence={
                "missing_null_models": missing_null_models,
                "duplicate_null_models": duplicate_null_models,
                "incomplete_null_models": incomplete_null_models,
            },
        )
    )

    family_accounting_valid = (
        request.schema_version == SUPPORTED_DISCOVERY_ACCOUNTING_SCHEMA_VERSION
        and family_ledger.family_id == preregistration.family_id
        and family_ledger.subfamily_id == preregistration.subfamily_id
        and bool(family_ledger.research_run_ids)
        and bool(family_ledger.retained_log_ids)
        and bool(family_ledger.correlation_id)
        and family_ledger.promotable_trial_count >= len(family_ledger.research_run_ids)
        and family_ledger.null_comparison_count >= len(request.null_suite_entries)
        and family_ledger.historical_data_spend_usd >= 0
        and family_ledger.compute_spend_usd >= 0
        and family_ledger.operator_review_hours >= 0
        and family_ledger.requested_next_budget_usd >= 0
        and all(
            diagnostic_delta_id
            for diagnostic_delta_id in family_ledger.diagnostic_delta_ids
        )
    )
    checks.append(
        _check(
            DISCOVERY_ACCOUNTING_CHECK_IDS[1],
            passed=family_accounting_valid,
            reason_code=(
                "DISCOVERY_ACCOUNTING_FAMILY_LEDGER_VALID"
                if family_accounting_valid
                else "DISCOVERY_ACCOUNTING_FAMILY_LEDGER_INVALID"
            ),
            diagnostic=(
                "Family ledger is queryable and aligned with preregistration."
                if family_accounting_valid
                else "Family ledger must align with preregistration and retain run ids, logs, counts, and diagnostic deltas."
            ),
            evidence={
                "family_id": family_ledger.family_id,
                "subfamily_id": family_ledger.subfamily_id,
                "research_run_count": len(family_ledger.research_run_ids),
                "diagnostic_delta_count": len(family_ledger.diagnostic_delta_ids),
            },
        )
    )

    aggregated_trial_count = sum(
        entry.promotable_trial_count for entry in program_ledger.family_entries
    )
    aggregated_null_count = sum(
        entry.null_comparison_count for entry in program_ledger.family_entries
    )
    aggregated_data_spend = sum(
        entry.historical_data_spend_usd for entry in program_ledger.family_entries
    )
    aggregated_compute_spend = sum(
        entry.compute_spend_usd for entry in program_ledger.family_entries
    )
    aggregated_review_hours = sum(
        entry.operator_review_hours for entry in program_ledger.family_entries
    )
    current_family_entries = tuple(
        entry
        for entry in program_ledger.family_entries
        if entry.family_id == family_ledger.family_id
        and entry.subfamily_id == family_ledger.subfamily_id
    )
    program_ledger_valid = (
        bool(program_ledger.ledger_id)
        and bool(program_ledger.family_entries)
        and len(current_family_entries) == 1
        and program_ledger.cumulative_promotable_trial_count == aggregated_trial_count
        and program_ledger.cumulative_null_comparison_count == aggregated_null_count
        and program_ledger.cumulative_data_spend_usd == aggregated_data_spend
        and program_ledger.cumulative_compute_spend_usd == aggregated_compute_spend
        and program_ledger.cumulative_operator_review_hours == aggregated_review_hours
    )
    checks.append(
        _check(
            DISCOVERY_ACCOUNTING_CHECK_IDS[2],
            passed=program_ledger_valid,
            reason_code=(
                "DISCOVERY_ACCOUNTING_PROGRAM_LEDGER_VALID"
                if program_ledger_valid
                else "DISCOVERY_ACCOUNTING_PROGRAM_LEDGER_MISMATCH"
            ),
            diagnostic=(
                "Program ledger preserves cumulative discovery counts and budget movements across families."
                if program_ledger_valid
                else "Program ledger must aggregate family discovery counts and budget movements exactly."
            ),
            evidence={
                "family_entry_count": len(program_ledger.family_entries),
                "aggregated_trial_count": aggregated_trial_count,
                "recorded_trial_count": program_ledger.cumulative_promotable_trial_count,
            },
        )
    )

    exceeds_exploratory = (
        family_ledger.promotable_trial_count > preregistration.budget_limits.tuning_trial_limit
        or family_ledger.historical_data_spend_usd
        > preregistration.budget_limits.historical_data_spend_limit_usd
        or family_ledger.compute_spend_usd
        > preregistration.budget_limits.compute_spend_limit_usd
        or family_ledger.operator_review_hours
        > preregistration.budget_limits.operator_review_hours_limit
        or family_total_spend_usd + family_ledger.requested_next_budget_usd
        > preregistration.budget_limits.exploratory_budget_limit_usd
    )
    continuation_valid = True
    if exceeds_exploratory:
        continuation_valid = bool(
            continuation is not None
            and continuation.family_id == preregistration.family_id
            and continuation.decision_type
            in (FamilyDecisionType.CONTINUE, FamilyDecisionType.PIVOT)
            and continuation.next_budget_authorized_usd
            >= family_ledger.requested_next_budget_usd
        )
    checks.append(
        _check(
            DISCOVERY_ACCOUNTING_CHECK_IDS[3],
            passed=continuation_valid,
            reason_code=(
                "DISCOVERY_ACCOUNTING_CONTINUATION_APPROVED"
                if continuation_valid
                else "DISCOVERY_ACCOUNTING_CONTINUATION_REQUIRED"
            ),
            diagnostic=(
                "Exploratory search remains within preregistered limits or has an explicit continuation decision."
                if continuation_valid
                else "Further promotable search is blocked until an explicit continuation decision authorizes it."
            ),
            evidence={
                "exceeds_exploratory": exceeds_exploratory,
                "decision_record_id": (
                    None if continuation is None else continuation.decision_record_id
                ),
            },
        )
    )

    guardrail_ok = null_suite_valid and program_ledger_valid and continuation_valid
    guardrail_trace = _jsonable(
        check_guardrail(
            PrincipleID.P08_NO_HIDDEN_OPTIMIZATION,
            condition_met=guardrail_ok,
            diagnostic=(
                "Null suite and discovery accounting remain explicit and queryable."
                if guardrail_ok
                else "Null suite coverage or discovery accounting is incomplete, creating a hidden optimization surface."
            ),
            context={
                "case_id": request.case_id,
                "family_id": preregistration.family_id,
                "completed_null_model_ids": completed_null_model_ids,
                "exceeds_exploratory": exceeds_exploratory,
            },
        ).to_dict()
    )

    decision_log.append(
        _log(
            stage="null_suite",
            reason_code=checks[0].reason_code,
            message=checks[0].diagnostic,
            references=tuple(entry.study_id for entry in request.null_suite_entries),
        )
    )
    decision_log.append(
        _log(
            stage="family_discovery",
            reason_code=checks[1].reason_code,
            message=checks[1].diagnostic,
            references=family_ledger.research_run_ids,
        )
    )
    decision_log.append(
        _log(
            stage="program_discovery",
            reason_code=checks[2].reason_code,
            message=checks[2].diagnostic,
            references=(program_ledger.ledger_id,),
        )
    )
    decision_log.append(
        _log(
            stage="continuation_gate",
            reason_code=checks[3].reason_code,
            message=checks[3].diagnostic,
            references=(
                ()
                if continuation is None
                else (continuation.decision_record_id,)
            ),
        )
    )

    triggered_check_ids = tuple(check.check_id for check in checks if not check.passed)
    if any(
        check_id in triggered_check_ids
        for check_id in (
            DISCOVERY_ACCOUNTING_CHECK_IDS[1],
            DISCOVERY_ACCOUNTING_CHECK_IDS[2],
        )
    ):
        status = DiscoveryAccountingStatus.INVALID.value
        decision = DiscoveryAccountingDecision.BLOCK.value
        reason_code = next(check.reason_code for check in checks if not check.passed)
    elif any(
        check_id in triggered_check_ids
        for check_id in (
            DISCOVERY_ACCOUNTING_CHECK_IDS[0],
            DISCOVERY_ACCOUNTING_CHECK_IDS[3],
        )
    ):
        status = DiscoveryAccountingStatus.VIOLATION.value
        decision = DiscoveryAccountingDecision.BLOCK.value
        reason_code = next(check.reason_code for check in checks if not check.passed)
    elif exceeds_exploratory:
        status = DiscoveryAccountingStatus.PASS.value
        decision = DiscoveryAccountingDecision.ALLOW_WITH_CONTINUATION.value
        reason_code = "DISCOVERY_ACCOUNTING_CONTINUED_WITH_APPROVAL"
    else:
        status = DiscoveryAccountingStatus.PASS.value
        decision = DiscoveryAccountingDecision.ALLOW_EXPLORATORY.value
        reason_code = "DISCOVERY_ACCOUNTING_EXPLORATORY_ALLOWED"

    decision_log.append(
        _log(
            stage="decision",
            reason_code=reason_code,
            message=(
                "Discovery accounting remains bounded and queryable."
                if status == DiscoveryAccountingStatus.PASS.value
                else "Discovery accounting blocks promotable search until missing governance evidence is fixed."
            ),
            references=(
                preregistration.registration_id,
                program_ledger.ledger_id,
            ),
        )
    )

    return DiscoveryAccountingReport(
        case_id=request.case_id,
        family_id=preregistration.family_id,
        subfamily_id=preregistration.subfamily_id,
        status=status,
        decision=decision,
        reason_code=reason_code,
        exploratory_budget_limit_usd=preregistration.budget_limits.exploratory_budget_limit_usd,
        continuation_budget_limit_usd=preregistration.budget_limits.continuation_budget_limit_usd,
        family_total_spend_usd=family_total_spend_usd,
        family_promotable_trial_count=family_ledger.promotable_trial_count,
        program_total_spend_usd=program_total_spend_usd,
        program_promotable_trial_count=program_ledger.cumulative_promotable_trial_count,
        remaining_exploratory_budget_usd=(
            preregistration.budget_limits.exploratory_budget_limit_usd
            - family_total_spend_usd
        ),
        completed_null_model_ids=completed_null_model_ids,
        triggered_check_ids=triggered_check_ids,
        check_results=tuple(checks),
        decision_log=tuple(decision_log),
        continuation_decision_record_id=(
            None if continuation is None else continuation.decision_record_id
        ),
        guardrail_trace=guardrail_trace,
        evaluated_at_utc=request.evaluated_at_utc or _utcnow(),
    )
