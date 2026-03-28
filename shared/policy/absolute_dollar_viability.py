"""Absolute-dollar viability gate and benchmark comparisons."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.account_fit_gate import AccountFitStatus

SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION = 1
ABSOLUTE_DOLLAR_CHECK_IDS = (
    "de_minimis_monthly_net",
    "passive_gold_benchmark_excess",
    "cash_benchmark_excess",
    "low_turnover_downside",
    "lower_touch_alternative_dominance",
)
BENCHMARK_IDS = (
    "passive_gold",
    "cash_or_short_duration_treasury",
)
SENSITIVITY_SCENARIO_IDS = (
    "conservative_baseline",
    "low_turnover_downside",
)


def validate_absolute_dollar_viability_contract() -> list[str]:
    errors: list[str] = []
    if len(ABSOLUTE_DOLLAR_CHECK_IDS) != len(set(ABSOLUTE_DOLLAR_CHECK_IDS)):
        errors.append("absolute-dollar viability check identifiers must be unique")
    if len(BENCHMARK_IDS) != len(set(BENCHMARK_IDS)):
        errors.append("absolute-dollar benchmark identifiers must be unique")
    if len(SENSITIVITY_SCENARIO_IDS) != len(set(SENSITIVITY_SCENARIO_IDS)):
        errors.append("sensitivity scenario identifiers must be unique")
    if SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    return errors


VALIDATION_ERRORS = validate_absolute_dollar_viability_contract()


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_field(payload: dict[str, Any], key: str, *, field_name: str) -> object:
    if key not in payload:
        raise ValueError(f"{field_name}: field is required")
    return payload[key]


def _as_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}: must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name}: must be numeric")
    return parsed


def _as_non_negative_float(value: object, *, field_name: str) -> float:
    parsed = _as_float(value, field_name=field_name)
    if parsed < 0.0:
        raise ValueError(f"{field_name}: must be non-negative")
    return parsed


def _as_positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name}: must be positive")
    parsed = value
    if parsed < 1:
        raise ValueError(f"{field_name}: must be positive")
    return parsed


def _as_optional_non_negative_float(
    value: object | None,
    *,
    field_name: str,
) -> float | None:
    if value in (None, ""):
        return None
    return _as_non_negative_float(value, field_name=field_name)


def _require_boolean(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be boolean")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}: must be a non-empty string")
    return value


def _require_optional_non_empty_string(
    value: object, *, field_name: str
) -> str | None:
    if value in (None, ""):
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[]") for item in value
    )


def _require_object_sequence(
    value: object, *, field_name: str
) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of objects")
    return tuple(_require_mapping(item, field_name=f"{field_name}[]") for item in value)


def _require_schema_version(value: object, *, field_name: str) -> int:
    parsed = _as_positive_int(value, field_name=field_name)
    if parsed != SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION:
        raise ValueError(
            f"{field_name}: unsupported schema_version {parsed}; expected "
            f"{SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION}"
        )
    return parsed


def _normalize_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name}: must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name}: must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@unique
class AbsoluteDollarViabilityStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    FAIL = "fail"
    INVALID = "invalid"


@unique
class AbsoluteDollarDecision(str, Enum):
    KEEP = "keep"
    PIVOT = "pivot"
    REJECT = "reject"


@dataclass(frozen=True)
class AbsoluteDollarThresholds:
    de_minimis_monthly_net_usd: float
    minimum_passive_gold_excess_usd: float
    minimum_cash_excess_usd: float
    minimum_low_turnover_monthly_net_usd: float

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AbsoluteDollarThresholds":
        payload = _require_mapping(payload, field_name="thresholds")
        return cls(
            de_minimis_monthly_net_usd=_as_non_negative_float(
                payload["de_minimis_monthly_net_usd"],
                field_name="de_minimis_monthly_net_usd",
            ),
            minimum_passive_gold_excess_usd=_as_non_negative_float(
                payload["minimum_passive_gold_excess_usd"],
                field_name="minimum_passive_gold_excess_usd",
            ),
            minimum_cash_excess_usd=_as_non_negative_float(
                payload["minimum_cash_excess_usd"],
                field_name="minimum_cash_excess_usd",
            ),
            minimum_low_turnover_monthly_net_usd=_as_float(
                payload["minimum_low_turnover_monthly_net_usd"],
                field_name="minimum_low_turnover_monthly_net_usd",
            ),
        )


@dataclass(frozen=True)
class AbsoluteDollarViabilityRequest:
    case_id: str
    evaluation_id: str
    candidate_id: str
    strategy_family_id: str
    product_profile_id: str
    account_profile_id: str
    execution_symbol: str
    source_account_fit_case_id: str
    source_fully_loaded_economics_evaluation_id: str
    account_fit_status: str
    approved_starting_equity_usd: int
    committed_margin_usd: float
    conservative_monthly_net_usd: float
    passive_gold_benchmark_monthly_usd: float
    cash_benchmark_monthly_usd: float
    downside_low_turnover_monthly_net_usd: float
    worst_session_loss_usd: float
    thresholds: AbsoluteDollarThresholds
    operator_maintenance_hours_per_month: float | None = None
    lower_touch_alternative_monthly_net_usd: float | None = None
    lower_touch_alternative_operator_hours_per_month: float | None = None
    schema_version: int = SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"] = self.thresholds.to_dict()
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AbsoluteDollarViabilityRequest":
        payload = _require_mapping(payload, field_name="absolute_dollar_viability_request")
        lower_touch_alternative_monthly_net_usd = _as_optional_non_negative_float(
            payload.get("lower_touch_alternative_monthly_net_usd"),
            field_name="lower_touch_alternative_monthly_net_usd",
        )
        lower_touch_alternative_operator_hours_per_month = _as_optional_non_negative_float(
            payload.get("lower_touch_alternative_operator_hours_per_month"),
            field_name="lower_touch_alternative_operator_hours_per_month",
        )
        if (
            lower_touch_alternative_operator_hours_per_month is not None
            and lower_touch_alternative_monthly_net_usd is None
        ):
            raise ValueError(
                "lower_touch_alternative_monthly_net_usd: required when lower-touch hours are set"
            )
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            evaluation_id=_require_non_empty_string(
                payload["evaluation_id"],
                field_name="evaluation_id",
            ),
            candidate_id=_require_non_empty_string(
                payload["candidate_id"],
                field_name="candidate_id",
            ),
            strategy_family_id=_require_non_empty_string(
                payload["strategy_family_id"],
                field_name="strategy_family_id",
            ),
            product_profile_id=_require_non_empty_string(
                payload["product_profile_id"],
                field_name="product_profile_id",
            ),
            account_profile_id=_require_non_empty_string(
                payload["account_profile_id"],
                field_name="account_profile_id",
            ),
            execution_symbol=_require_non_empty_string(
                payload["execution_symbol"],
                field_name="execution_symbol",
            ),
            source_account_fit_case_id=_require_non_empty_string(
                payload["source_account_fit_case_id"],
                field_name="source_account_fit_case_id",
            ),
            source_fully_loaded_economics_evaluation_id=_require_non_empty_string(
                payload["source_fully_loaded_economics_evaluation_id"],
                field_name="source_fully_loaded_economics_evaluation_id",
            ),
            account_fit_status=AccountFitStatus(
                _require_non_empty_string(
                    payload["account_fit_status"],
                    field_name="account_fit_status",
                )
            ).value,
            approved_starting_equity_usd=_as_positive_int(
                payload["approved_starting_equity_usd"],
                field_name="approved_starting_equity_usd",
            ),
            committed_margin_usd=_as_non_negative_float(
                payload["committed_margin_usd"],
                field_name="committed_margin_usd",
            ),
            conservative_monthly_net_usd=_as_float(
                payload["conservative_monthly_net_usd"],
                field_name="conservative_monthly_net_usd",
            ),
            passive_gold_benchmark_monthly_usd=_as_non_negative_float(
                payload["passive_gold_benchmark_monthly_usd"],
                field_name="passive_gold_benchmark_monthly_usd",
            ),
            cash_benchmark_monthly_usd=_as_non_negative_float(
                payload["cash_benchmark_monthly_usd"],
                field_name="cash_benchmark_monthly_usd",
            ),
            downside_low_turnover_monthly_net_usd=_as_float(
                payload["downside_low_turnover_monthly_net_usd"],
                field_name="downside_low_turnover_monthly_net_usd",
            ),
            worst_session_loss_usd=_as_non_negative_float(
                payload["worst_session_loss_usd"],
                field_name="worst_session_loss_usd",
            ),
            thresholds=AbsoluteDollarThresholds.from_dict(
                _require_mapping(payload["thresholds"], field_name="thresholds")
            ),
            operator_maintenance_hours_per_month=_as_optional_non_negative_float(
                payload.get("operator_maintenance_hours_per_month"),
                field_name="operator_maintenance_hours_per_month",
            ),
            lower_touch_alternative_monthly_net_usd=lower_touch_alternative_monthly_net_usd,
            lower_touch_alternative_operator_hours_per_month=(
                lower_touch_alternative_operator_hours_per_month
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AbsoluteDollarViabilityRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="absolute_dollar_viability_request")
        )


@dataclass(frozen=True)
class BenchmarkComparison:
    benchmark_id: str
    title: str
    benchmark_monthly_usd: float
    candidate_monthly_net_usd: float
    excess_usd: float
    passed: bool
    reason_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BenchmarkComparison":
        payload = _require_mapping(payload, field_name="benchmark_comparison")
        return cls(
            benchmark_id=_require_non_empty_string(
                payload["benchmark_id"],
                field_name="benchmark_id",
            ),
            title=_require_non_empty_string(payload["title"], field_name="title"),
            benchmark_monthly_usd=_as_float(
                payload["benchmark_monthly_usd"],
                field_name="benchmark_monthly_usd",
            ),
            candidate_monthly_net_usd=_as_float(
                payload["candidate_monthly_net_usd"],
                field_name="candidate_monthly_net_usd",
            ),
            excess_usd=_as_float(payload["excess_usd"], field_name="excess_usd"),
            passed=_require_boolean(payload["passed"], field_name="passed"),
            reason_code=_require_optional_non_empty_string(
                payload.get("reason_code"),
                field_name="reason_code",
            ),
        )


@dataclass(frozen=True)
class SensitivityScenario:
    scenario_id: str
    title: str
    monthly_net_usd: float
    delta_vs_baseline_usd: float
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SensitivityScenario":
        payload = _require_mapping(payload, field_name="sensitivity_scenario")
        return cls(
            scenario_id=_require_non_empty_string(
                payload["scenario_id"],
                field_name="scenario_id",
            ),
            title=_require_non_empty_string(payload["title"], field_name="title"),
            monthly_net_usd=_as_float(
                payload["monthly_net_usd"],
                field_name="monthly_net_usd",
            ),
            delta_vs_baseline_usd=_as_float(
                payload["delta_vs_baseline_usd"],
                field_name="delta_vs_baseline_usd",
            ),
            narrative=_require_non_empty_string(
                payload["narrative"],
                field_name="narrative",
            ),
        )


@dataclass(frozen=True)
class AbsoluteDollarCheckResult:
    check_id: str
    title: str
    passed: bool
    reason_code: str | None
    diagnostic: str
    actual_usd: float | None
    threshold_usd: float | None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AbsoluteDollarCheckResult":
        payload = _require_mapping(payload, field_name="check_result")
        return cls(
            check_id=_require_non_empty_string(payload["check_id"], field_name="check_id"),
            title=_require_non_empty_string(payload["title"], field_name="title"),
            passed=_require_boolean(payload["passed"], field_name="passed"),
            reason_code=_require_optional_non_empty_string(
                payload.get("reason_code"),
                field_name="reason_code",
            ),
            diagnostic=_require_non_empty_string(
                payload["diagnostic"],
                field_name="diagnostic",
            ),
            actual_usd=(
                _as_float(payload["actual_usd"], field_name="actual_usd")
                if payload.get("actual_usd") is not None
                else None
            ),
            threshold_usd=(
                _as_float(payload["threshold_usd"], field_name="threshold_usd")
                if payload.get("threshold_usd") is not None
                else None
            ),
            context=_require_mapping(payload.get("context", {}), field_name="context"),
        )


@dataclass(frozen=True)
class AbsoluteDollarViabilityReport:
    case_id: str
    evaluation_id: str
    candidate_id: str
    strategy_family_id: str
    status: str
    decision: str
    reason_code: str
    product_profile_id: str
    account_profile_id: str
    execution_symbol: str
    source_ids: tuple[str, ...]
    thresholds: AbsoluteDollarThresholds | None
    approved_starting_equity_usd: int
    committed_margin_usd: float
    free_cash_usd: float
    conservative_monthly_net_usd: float
    passive_gold_benchmark_monthly_usd: float
    cash_benchmark_monthly_usd: float
    monthly_excess_vs_passive_gold_usd: float
    monthly_excess_vs_cash_usd: float
    downside_low_turnover_monthly_net_usd: float
    operator_maintenance_hours_per_month: float | None
    net_per_operator_maintenance_hour_usd: float | None
    lower_touch_alternative_monthly_net_usd: float | None
    lower_touch_alternative_operator_hours_per_month: float | None
    lower_touch_alternative_net_per_hour_usd: float | None
    lower_touch_dominates: bool
    conservative_return_on_committed_margin: float | None
    worst_session_loss_usd: float
    worst_session_loss_fraction_of_free_cash: float | None
    benchmark_comparisons: tuple[BenchmarkComparison, ...]
    sensitivity_scenarios: tuple[SensitivityScenario, ...]
    failed_check_ids: tuple[str, ...]
    check_results: tuple[AbsoluteDollarCheckResult, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"] = self.thresholds.to_dict() if self.thresholds is not None else None
        payload["benchmark_comparisons"] = [
            item.to_dict() for item in self.benchmark_comparisons
        ]
        payload["sensitivity_scenarios"] = [
            item.to_dict() for item in self.sensitivity_scenarios
        ]
        payload["check_results"] = [item.to_dict() for item in self.check_results]
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AbsoluteDollarViabilityReport":
        payload = _require_mapping(payload, field_name="absolute_dollar_viability_report")
        thresholds_payload = _require_field(payload, "thresholds", field_name="thresholds")
        operator_maintenance_hours = _require_field(
            payload,
            "operator_maintenance_hours_per_month",
            field_name="operator_maintenance_hours_per_month",
        )
        net_per_operator_hour = _require_field(
            payload,
            "net_per_operator_maintenance_hour_usd",
            field_name="net_per_operator_maintenance_hour_usd",
        )
        lower_touch_monthly_net = _require_field(
            payload,
            "lower_touch_alternative_monthly_net_usd",
            field_name="lower_touch_alternative_monthly_net_usd",
        )
        lower_touch_operator_hours = _require_field(
            payload,
            "lower_touch_alternative_operator_hours_per_month",
            field_name="lower_touch_alternative_operator_hours_per_month",
        )
        lower_touch_net_per_hour = _require_field(
            payload,
            "lower_touch_alternative_net_per_hour_usd",
            field_name="lower_touch_alternative_net_per_hour_usd",
        )
        conservative_return = _require_field(
            payload,
            "conservative_return_on_committed_margin",
            field_name="conservative_return_on_committed_margin",
        )
        worst_loss_fraction = _require_field(
            payload,
            "worst_session_loss_fraction_of_free_cash",
            field_name="worst_session_loss_fraction_of_free_cash",
        )
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            evaluation_id=_require_non_empty_string(
                payload["evaluation_id"],
                field_name="evaluation_id",
            ),
            candidate_id=_require_non_empty_string(
                payload["candidate_id"],
                field_name="candidate_id",
            ),
            strategy_family_id=_require_non_empty_string(
                payload["strategy_family_id"],
                field_name="strategy_family_id",
            ),
            status=AbsoluteDollarViabilityStatus(
                _require_non_empty_string(payload["status"], field_name="status")
            ).value,
            decision=AbsoluteDollarDecision(
                _require_non_empty_string(payload["decision"], field_name="decision")
            ).value,
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            product_profile_id=_require_non_empty_string(
                payload["product_profile_id"],
                field_name="product_profile_id",
            ),
            account_profile_id=_require_non_empty_string(
                payload["account_profile_id"],
                field_name="account_profile_id",
            ),
            execution_symbol=_require_non_empty_string(
                payload["execution_symbol"],
                field_name="execution_symbol",
            ),
            source_ids=_require_string_sequence(payload["source_ids"], field_name="source_ids"),
            thresholds=(
                AbsoluteDollarThresholds.from_dict(
                    _require_mapping(thresholds_payload, field_name="thresholds")
                )
                if thresholds_payload is not None
                else None
            ),
            approved_starting_equity_usd=_as_positive_int(
                payload["approved_starting_equity_usd"],
                field_name="approved_starting_equity_usd",
            ),
            committed_margin_usd=_as_float(
                payload["committed_margin_usd"],
                field_name="committed_margin_usd",
            ),
            free_cash_usd=_as_float(payload["free_cash_usd"], field_name="free_cash_usd"),
            conservative_monthly_net_usd=_as_float(
                payload["conservative_monthly_net_usd"],
                field_name="conservative_monthly_net_usd",
            ),
            passive_gold_benchmark_monthly_usd=_as_float(
                payload["passive_gold_benchmark_monthly_usd"],
                field_name="passive_gold_benchmark_monthly_usd",
            ),
            cash_benchmark_monthly_usd=_as_float(
                payload["cash_benchmark_monthly_usd"],
                field_name="cash_benchmark_monthly_usd",
            ),
            monthly_excess_vs_passive_gold_usd=_as_float(
                payload["monthly_excess_vs_passive_gold_usd"],
                field_name="monthly_excess_vs_passive_gold_usd",
            ),
            monthly_excess_vs_cash_usd=_as_float(
                payload["monthly_excess_vs_cash_usd"],
                field_name="monthly_excess_vs_cash_usd",
            ),
            downside_low_turnover_monthly_net_usd=_as_float(
                payload["downside_low_turnover_monthly_net_usd"],
                field_name="downside_low_turnover_monthly_net_usd",
            ),
            operator_maintenance_hours_per_month=(
                _as_float(
                    operator_maintenance_hours,
                    field_name="operator_maintenance_hours_per_month",
                )
                if operator_maintenance_hours is not None
                else None
            ),
            net_per_operator_maintenance_hour_usd=(
                _as_float(
                    net_per_operator_hour,
                    field_name="net_per_operator_maintenance_hour_usd",
                )
                if net_per_operator_hour is not None
                else None
            ),
            lower_touch_alternative_monthly_net_usd=(
                _as_float(
                    lower_touch_monthly_net,
                    field_name="lower_touch_alternative_monthly_net_usd",
                )
                if lower_touch_monthly_net is not None
                else None
            ),
            lower_touch_alternative_operator_hours_per_month=(
                _as_float(
                    lower_touch_operator_hours,
                    field_name="lower_touch_alternative_operator_hours_per_month",
                )
                if lower_touch_operator_hours is not None
                else None
            ),
            lower_touch_alternative_net_per_hour_usd=(
                _as_float(
                    lower_touch_net_per_hour,
                    field_name="lower_touch_alternative_net_per_hour_usd",
                )
                if lower_touch_net_per_hour is not None
                else None
            ),
            lower_touch_dominates=_require_boolean(
                payload["lower_touch_dominates"],
                field_name="lower_touch_dominates",
            ),
            conservative_return_on_committed_margin=(
                _as_float(
                    conservative_return,
                    field_name="conservative_return_on_committed_margin",
                )
                if conservative_return is not None
                else None
            ),
            worst_session_loss_usd=_as_float(
                payload["worst_session_loss_usd"],
                field_name="worst_session_loss_usd",
            ),
            worst_session_loss_fraction_of_free_cash=(
                _as_float(
                    worst_loss_fraction,
                    field_name="worst_session_loss_fraction_of_free_cash",
                )
                if worst_loss_fraction is not None
                else None
            ),
            benchmark_comparisons=tuple(
                BenchmarkComparison.from_dict(item)
                for item in _require_object_sequence(
                    payload.get("benchmark_comparisons"),
                    field_name="benchmark_comparisons",
                )
            ),
            sensitivity_scenarios=tuple(
                SensitivityScenario.from_dict(item)
                for item in _require_object_sequence(
                    payload.get("sensitivity_scenarios"),
                    field_name="sensitivity_scenarios",
                )
            ),
            failed_check_ids=_require_string_sequence(
                payload.get("failed_check_ids"),
                field_name="failed_check_ids",
            ),
            check_results=tuple(
                AbsoluteDollarCheckResult.from_dict(item)
                for item in _require_object_sequence(
                    payload.get("check_results"),
                    field_name="check_results",
                )
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_timestamp(
                payload.get("timestamp"),
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AbsoluteDollarViabilityReport":
        return cls.from_dict(
            _decode_json_object(payload, label="absolute_dollar_viability_report")
        )


def _invalid_report(
    request: AbsoluteDollarViabilityRequest,
    *,
    reason_code: str,
    explanation: str,
    remediation: str,
) -> AbsoluteDollarViabilityReport:
    return AbsoluteDollarViabilityReport(
        case_id=request.case_id,
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        strategy_family_id=request.strategy_family_id,
        status=AbsoluteDollarViabilityStatus.INVALID.value,
        decision=AbsoluteDollarDecision.REJECT.value,
        reason_code=reason_code,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        execution_symbol=request.execution_symbol,
        source_ids=(
            request.source_account_fit_case_id,
            request.source_fully_loaded_economics_evaluation_id,
        ),
        thresholds=request.thresholds,
        approved_starting_equity_usd=request.approved_starting_equity_usd,
        committed_margin_usd=request.committed_margin_usd,
        free_cash_usd=max(
            float(request.approved_starting_equity_usd) - request.committed_margin_usd,
            0.0,
        ),
        conservative_monthly_net_usd=request.conservative_monthly_net_usd,
        passive_gold_benchmark_monthly_usd=request.passive_gold_benchmark_monthly_usd,
        cash_benchmark_monthly_usd=request.cash_benchmark_monthly_usd,
        monthly_excess_vs_passive_gold_usd=(
            request.conservative_monthly_net_usd - request.passive_gold_benchmark_monthly_usd
        ),
        monthly_excess_vs_cash_usd=(
            request.conservative_monthly_net_usd - request.cash_benchmark_monthly_usd
        ),
        downside_low_turnover_monthly_net_usd=request.downside_low_turnover_monthly_net_usd,
        operator_maintenance_hours_per_month=request.operator_maintenance_hours_per_month,
        net_per_operator_maintenance_hour_usd=None,
        lower_touch_alternative_monthly_net_usd=request.lower_touch_alternative_monthly_net_usd,
        lower_touch_alternative_operator_hours_per_month=(
            request.lower_touch_alternative_operator_hours_per_month
        ),
        lower_touch_alternative_net_per_hour_usd=None,
        lower_touch_dominates=False,
        conservative_return_on_committed_margin=None,
        worst_session_loss_usd=request.worst_session_loss_usd,
        worst_session_loss_fraction_of_free_cash=None,
        benchmark_comparisons=(),
        sensitivity_scenarios=(),
        failed_check_ids=(),
        check_results=(),
        explanation=explanation,
        remediation=remediation,
    )


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0.0:
        return None
    return numerator / denominator


def _lower_touch_dominates(
    *,
    candidate_monthly_net_usd: float,
    candidate_operator_hours: float | None,
    lower_touch_monthly_net_usd: float | None,
    lower_touch_operator_hours: float | None,
) -> tuple[bool, float | None, float | None]:
    candidate_net_per_hour = (
        _safe_ratio(candidate_monthly_net_usd, candidate_operator_hours)
        if candidate_operator_hours is not None
        else None
    )
    lower_touch_net_per_hour = (
        _safe_ratio(lower_touch_monthly_net_usd, lower_touch_operator_hours)
        if lower_touch_monthly_net_usd is not None and lower_touch_operator_hours is not None
        else None
    )
    if lower_touch_monthly_net_usd is None:
        return False, candidate_net_per_hour, lower_touch_net_per_hour
    if candidate_operator_hours is None or lower_touch_operator_hours is None:
        return (
            lower_touch_monthly_net_usd >= candidate_monthly_net_usd,
            candidate_net_per_hour,
            lower_touch_net_per_hour,
        )
    if lower_touch_operator_hours > candidate_operator_hours:
        return False, candidate_net_per_hour, lower_touch_net_per_hour
    return (
        lower_touch_monthly_net_usd >= candidate_monthly_net_usd
        or (
            lower_touch_net_per_hour is not None
            and candidate_net_per_hour is not None
            and lower_touch_net_per_hour >= candidate_net_per_hour
        ),
        candidate_net_per_hour,
        lower_touch_net_per_hour,
    )


def evaluate_absolute_dollar_viability(
    request: AbsoluteDollarViabilityRequest,
) -> AbsoluteDollarViabilityReport:
    if request.schema_version != SUPPORTED_ABSOLUTE_DOLLAR_VIABILITY_SCHEMA_VERSION:
        return _invalid_report(
            request,
            reason_code="ABSOLUTE_DOLLAR_VIABILITY_INVALID",
            explanation="Absolute-dollar viability request used an unsupported schema version.",
            remediation="Update the request to the supported schema version before re-running the gate.",
        )
    if request.account_fit_status != "pass":
        return _invalid_report(
            request,
            reason_code="ABSOLUTE_DOLLAR_ACCOUNT_FIT_PREREQUISITE_MISSING",
            explanation=(
                "Absolute-dollar viability requires a passed account-fit result so the approved "
                "live size, committed margin, and execution contract are already pinned."
            ),
            remediation="Pass account-fit on the actual execution contract before evaluating this gate.",
        )
    if request.committed_margin_usd <= 0.0:
        return _invalid_report(
            request,
            reason_code="ABSOLUTE_DOLLAR_COMMITTED_MARGIN_INVALID",
            explanation="Committed margin must be positive for small-account futures viability.",
            remediation="Bind the gate to the actual committed margin on the approved live contract.",
        )

    free_cash_usd = float(request.approved_starting_equity_usd) - request.committed_margin_usd
    if free_cash_usd <= 0.0:
        return _invalid_report(
            request,
            reason_code="ABSOLUTE_DOLLAR_FREE_CASH_INVALID",
            explanation=(
                "Committed margin consumes all approved starting equity, so free-cash loss "
                "severity cannot be evaluated honestly."
            ),
            remediation="Reduce committed margin or raise approved starting equity before promotion.",
        )

    passive_gold_excess_usd = (
        request.conservative_monthly_net_usd - request.passive_gold_benchmark_monthly_usd
    )
    cash_excess_usd = request.conservative_monthly_net_usd - request.cash_benchmark_monthly_usd
    lower_touch_dominates, net_per_operator_hour_usd, lower_touch_net_per_hour_usd = (
        _lower_touch_dominates(
            candidate_monthly_net_usd=request.conservative_monthly_net_usd,
            candidate_operator_hours=request.operator_maintenance_hours_per_month,
            lower_touch_monthly_net_usd=request.lower_touch_alternative_monthly_net_usd,
            lower_touch_operator_hours=request.lower_touch_alternative_operator_hours_per_month,
        )
    )
    conservative_return_on_committed_margin = _safe_ratio(
        request.conservative_monthly_net_usd,
        request.committed_margin_usd,
    )
    worst_session_loss_fraction_of_free_cash = _safe_ratio(
        request.worst_session_loss_usd,
        free_cash_usd,
    )

    check_results = (
        AbsoluteDollarCheckResult(
            check_id="de_minimis_monthly_net",
            title="Conservative monthly net dollars",
            passed=(
                request.conservative_monthly_net_usd
                >= request.thresholds.de_minimis_monthly_net_usd
            ),
            reason_code=(
                None
                if request.conservative_monthly_net_usd
                >= request.thresholds.de_minimis_monthly_net_usd
                else "ABSOLUTE_DOLLAR_DE_MINIMIS"
            ),
            diagnostic=(
                "Conservative monthly net dollars clear the de-minimis threshold."
                if request.conservative_monthly_net_usd
                >= request.thresholds.de_minimis_monthly_net_usd
                else (
                    "Conservative monthly net dollars remain de minimis at the approved "
                    "live size."
                )
            ),
            actual_usd=request.conservative_monthly_net_usd,
            threshold_usd=request.thresholds.de_minimis_monthly_net_usd,
            context={"approved_live_size_symbol": request.execution_symbol},
        ),
        AbsoluteDollarCheckResult(
            check_id="passive_gold_benchmark_excess",
            title="Passive-gold benchmark excess",
            passed=(
                passive_gold_excess_usd
                >= request.thresholds.minimum_passive_gold_excess_usd
            ),
            reason_code=(
                None
                if passive_gold_excess_usd
                >= request.thresholds.minimum_passive_gold_excess_usd
                else "ABSOLUTE_DOLLAR_PASSIVE_GOLD_BENCHMARK_NOT_BEATEN"
            ),
            diagnostic=(
                "Conservative monthly net dollars exceed the passive-gold benchmark."
                if passive_gold_excess_usd
                >= request.thresholds.minimum_passive_gold_excess_usd
                else "Passive-gold benchmark outperforms the candidate on a conservative monthly basis."
            ),
            actual_usd=passive_gold_excess_usd,
            threshold_usd=request.thresholds.minimum_passive_gold_excess_usd,
            context={
                "candidate_monthly_net_usd": request.conservative_monthly_net_usd,
                "benchmark_monthly_usd": request.passive_gold_benchmark_monthly_usd,
            },
        ),
        AbsoluteDollarCheckResult(
            check_id="cash_benchmark_excess",
            title="Cash or Treasury benchmark excess",
            passed=cash_excess_usd >= request.thresholds.minimum_cash_excess_usd,
            reason_code=(
                None
                if cash_excess_usd >= request.thresholds.minimum_cash_excess_usd
                else "ABSOLUTE_DOLLAR_CASH_BENCHMARK_NOT_BEATEN"
            ),
            diagnostic=(
                "Conservative monthly net dollars exceed the idle-capital cash benchmark."
                if cash_excess_usd >= request.thresholds.minimum_cash_excess_usd
                else "Idle-capital cash or short-duration Treasury benchmark outperforms the candidate."
            ),
            actual_usd=cash_excess_usd,
            threshold_usd=request.thresholds.minimum_cash_excess_usd,
            context={
                "candidate_monthly_net_usd": request.conservative_monthly_net_usd,
                "benchmark_monthly_usd": request.cash_benchmark_monthly_usd,
            },
        ),
        AbsoluteDollarCheckResult(
            check_id="low_turnover_downside",
            title="Low-turnover downside monthly net",
            passed=(
                request.downside_low_turnover_monthly_net_usd
                >= request.thresholds.minimum_low_turnover_monthly_net_usd
            ),
            reason_code=(
                None
                if request.downside_low_turnover_monthly_net_usd
                >= request.thresholds.minimum_low_turnover_monthly_net_usd
                else "ABSOLUTE_DOLLAR_LOW_TURNOVER_DOWNSIDE_TOO_WEAK"
            ),
            diagnostic=(
                "Low-turnover downside remains within the approved monthly net floor."
                if request.downside_low_turnover_monthly_net_usd
                >= request.thresholds.minimum_low_turnover_monthly_net_usd
                else "Low-turnover downside is too weak to support a keep decision."
            ),
            actual_usd=request.downside_low_turnover_monthly_net_usd,
            threshold_usd=request.thresholds.minimum_low_turnover_monthly_net_usd,
            context={
                "baseline_monthly_net_usd": request.conservative_monthly_net_usd,
            },
        ),
        AbsoluteDollarCheckResult(
            check_id="lower_touch_alternative_dominance",
            title="Lower-touch alternative dominance",
            passed=not lower_touch_dominates,
            reason_code=(
                None
                if not lower_touch_dominates
                else "ABSOLUTE_DOLLAR_LOWER_TOUCH_ALTERNATIVE_DOMINATES"
            ),
            diagnostic=(
                "No lower-touch alternative dominates after operator time is considered."
                if not lower_touch_dominates
                else "A lower-touch alternative dominates after operator time is considered."
            ),
            actual_usd=request.lower_touch_alternative_monthly_net_usd,
            threshold_usd=request.conservative_monthly_net_usd,
            context={
                "candidate_net_per_operator_hour_usd": net_per_operator_hour_usd,
                "lower_touch_net_per_operator_hour_usd": lower_touch_net_per_hour_usd,
                "candidate_operator_hours_per_month": request.operator_maintenance_hours_per_month,
                "lower_touch_operator_hours_per_month": (
                    request.lower_touch_alternative_operator_hours_per_month
                ),
                "lower_touch_dominates": lower_touch_dominates,
            },
        ),
    )

    failed_check_ids = tuple(
        result.check_id for result in check_results if not result.passed
    )
    benchmark_comparisons = (
        BenchmarkComparison(
            benchmark_id="passive_gold",
            title="Passive-gold benchmark",
            benchmark_monthly_usd=request.passive_gold_benchmark_monthly_usd,
            candidate_monthly_net_usd=request.conservative_monthly_net_usd,
            excess_usd=passive_gold_excess_usd,
            passed=(
                passive_gold_excess_usd
                >= request.thresholds.minimum_passive_gold_excess_usd
            ),
            reason_code=(
                None
                if passive_gold_excess_usd
                >= request.thresholds.minimum_passive_gold_excess_usd
                else "ABSOLUTE_DOLLAR_PASSIVE_GOLD_BENCHMARK_NOT_BEATEN"
            ),
        ),
        BenchmarkComparison(
            benchmark_id="cash_or_short_duration_treasury",
            title="Cash or short-duration Treasury benchmark",
            benchmark_monthly_usd=request.cash_benchmark_monthly_usd,
            candidate_monthly_net_usd=request.conservative_monthly_net_usd,
            excess_usd=cash_excess_usd,
            passed=cash_excess_usd >= request.thresholds.minimum_cash_excess_usd,
            reason_code=(
                None
                if cash_excess_usd >= request.thresholds.minimum_cash_excess_usd
                else "ABSOLUTE_DOLLAR_CASH_BENCHMARK_NOT_BEATEN"
            ),
        ),
    )
    sensitivity_scenarios = (
        SensitivityScenario(
            scenario_id="conservative_baseline",
            title="Conservative monthly baseline",
            monthly_net_usd=request.conservative_monthly_net_usd,
            delta_vs_baseline_usd=0.0,
            narrative="Baseline conservative monthly net dollars at the approved live size.",
        ),
        SensitivityScenario(
            scenario_id="low_turnover_downside",
            title="Low-turnover downside",
            monthly_net_usd=request.downside_low_turnover_monthly_net_usd,
            delta_vs_baseline_usd=(
                request.downside_low_turnover_monthly_net_usd
                - request.conservative_monthly_net_usd
            ),
            narrative=(
                "Downside monthly net under a low-turnover assumption for the same live size."
            ),
        ),
    )

    reject_reason_codes = {
        "ABSOLUTE_DOLLAR_DE_MINIMIS",
        "ABSOLUTE_DOLLAR_PASSIVE_GOLD_BENCHMARK_NOT_BEATEN",
        "ABSOLUTE_DOLLAR_CASH_BENCHMARK_NOT_BEATEN",
    }
    pivot_reason_codes = {
        "ABSOLUTE_DOLLAR_LOW_TURNOVER_DOWNSIDE_TOO_WEAK",
        "ABSOLUTE_DOLLAR_LOWER_TOUCH_ALTERNATIVE_DOMINATES",
    }
    failed_reason_codes = {
        result.reason_code
        for result in check_results
        if not result.passed and result.reason_code is not None
    }
    reject_failures = sorted(failed_reason_codes & reject_reason_codes)
    pivot_failures = sorted(failed_reason_codes & pivot_reason_codes)

    if not failed_check_ids:
        status = AbsoluteDollarViabilityStatus.PASS.value
        decision = AbsoluteDollarDecision.KEEP.value
        reason_code = "ABSOLUTE_DOLLAR_VIABILITY_PASSED"
        explanation = (
            "Conservative monthly net dollars are not de minimis, exceed the passive-gold "
            "and cash benchmarks, preserve downside above the configured floor, and are not "
            "dominated by a lower-touch alternative."
        )
        remediation = "No remediation required."
    elif reject_failures:
        status = AbsoluteDollarViabilityStatus.FAIL.value
        decision = AbsoluteDollarDecision.REJECT.value
        reason_code = (
            reject_failures[0]
            if len(reject_failures) == 1 and not pivot_failures
            else "ABSOLUTE_DOLLAR_VIABILITY_REJECTED"
        )
        explanation = (
            "The candidate is economically unconvincing at the approved live size because "
            "either the monthly net remains de minimis or a required benchmark still "
            "outperforms it."
        )
        remediation = (
            "Reject the current promotion path, or materially improve the live-size economics "
            "before revisiting this gate."
        )
    else:
        status = AbsoluteDollarViabilityStatus.FAIL.value
        decision = AbsoluteDollarDecision.PIVOT.value
        reason_code = (
            pivot_failures[0]
            if len(pivot_failures) == 1
            else "ABSOLUTE_DOLLAR_VIABILITY_PIVOT_REQUIRED"
        )
        explanation = (
            "The candidate clears the basic benchmark floor but the downside or operator-time "
            "trade-off argues for a pivot instead of a direct keep decision."
        )
        remediation = (
            "Pivot to a lower-touch alternative or a narrower operating posture before any "
            "promotion memo proceeds."
        )

    return AbsoluteDollarViabilityReport(
        case_id=request.case_id,
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        strategy_family_id=request.strategy_family_id,
        status=status,
        decision=decision,
        reason_code=reason_code,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        execution_symbol=request.execution_symbol,
        source_ids=(
            request.source_account_fit_case_id,
            request.source_fully_loaded_economics_evaluation_id,
        ),
        thresholds=request.thresholds,
        approved_starting_equity_usd=request.approved_starting_equity_usd,
        committed_margin_usd=request.committed_margin_usd,
        free_cash_usd=free_cash_usd,
        conservative_monthly_net_usd=request.conservative_monthly_net_usd,
        passive_gold_benchmark_monthly_usd=request.passive_gold_benchmark_monthly_usd,
        cash_benchmark_monthly_usd=request.cash_benchmark_monthly_usd,
        monthly_excess_vs_passive_gold_usd=passive_gold_excess_usd,
        monthly_excess_vs_cash_usd=cash_excess_usd,
        downside_low_turnover_monthly_net_usd=request.downside_low_turnover_monthly_net_usd,
        operator_maintenance_hours_per_month=request.operator_maintenance_hours_per_month,
        net_per_operator_maintenance_hour_usd=net_per_operator_hour_usd,
        lower_touch_alternative_monthly_net_usd=request.lower_touch_alternative_monthly_net_usd,
        lower_touch_alternative_operator_hours_per_month=(
            request.lower_touch_alternative_operator_hours_per_month
        ),
        lower_touch_alternative_net_per_hour_usd=lower_touch_net_per_hour_usd,
        lower_touch_dominates=lower_touch_dominates,
        conservative_return_on_committed_margin=conservative_return_on_committed_margin,
        worst_session_loss_usd=request.worst_session_loss_usd,
        worst_session_loss_fraction_of_free_cash=worst_session_loss_fraction_of_free_cash,
        benchmark_comparisons=benchmark_comparisons,
        sensitivity_scenarios=sensitivity_scenarios,
        failed_check_ids=failed_check_ids,
        check_results=check_results,
        explanation=explanation,
        remediation=remediation,
    )
