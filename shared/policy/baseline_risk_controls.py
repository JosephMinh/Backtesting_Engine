"""Baseline live-lane risk controls inherited from shared account and strategy contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.policy_engine import PolicyWaiver
from shared.policy.product_profiles import (
    OperatingPosture,
    account_risk_profiles_by_id,
    product_profiles_by_id,
)
from shared.policy.strategy_contract import StrategyContract


SUPPORTED_BASELINE_RISK_CONTROL_SCHEMA_VERSION = 1
BASELINE_RISK_WAIVER_CATEGORY = "baseline_risk_controls"
BASELINE_RISK_CONTROL_IDS = (
    "max_position_limit",
    "max_concurrent_order_intents",
    "degraded_data_entry_suppression",
    "daily_loss_lockout",
    "max_drawdown_flatten",
    "delivery_fence_forced_flat",
    "warmup_hold",
    "margin_pretrade_check",
    "overnight_approval",
)
_ACTION_SEVERITY = {
    "allow": 0,
    "allow_with_waiver": 0,
    "restrict": 1,
    "exit_only": 2,
    "flatten": 3,
    "halt": 4,
}


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
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
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
    if not parsed == parsed or parsed in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} must be finite")
    return parsed


@unique
class RiskControlStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class RiskControlAction(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WAIVER = "allow_with_waiver"
    RESTRICT = "restrict"
    EXIT_ONLY = "exit_only"
    FLATTEN = "flatten"
    HALT = "halt"


@dataclass(frozen=True)
class BaselineRiskDefaults:
    source_product_profile_id: str
    source_account_profile_id: str
    source_strategy_contract_id: str
    execution_symbol: str
    max_position_size: int
    max_concurrent_order_intents: int
    daily_loss_lockout_fraction: float
    max_drawdown_fraction: float
    max_initial_margin_fraction: float
    max_maintenance_margin_fraction: float
    overnight_gap_stress_fraction: float
    allowed_operating_postures: tuple[str, ...]
    default_operating_posture: str
    overnight_only_with_strict_class: bool
    delivery_fence_rule: str
    delivery_fence_review_required: bool
    warmup_min_history_bars: int
    warmup_min_history_minutes: int
    warmup_requires_state_seed: bool

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BaselineRiskDefaults":
        return cls(
            source_product_profile_id=str(payload["source_product_profile_id"]),
            source_account_profile_id=str(payload["source_account_profile_id"]),
            source_strategy_contract_id=str(payload["source_strategy_contract_id"]),
            execution_symbol=str(payload["execution_symbol"]),
            max_position_size=_require_int(
                payload["max_position_size"],
                field_name="max_position_size",
            ),
            max_concurrent_order_intents=_require_int(
                payload["max_concurrent_order_intents"],
                field_name="max_concurrent_order_intents",
            ),
            daily_loss_lockout_fraction=_require_finite_number(
                payload["daily_loss_lockout_fraction"],
                field_name="daily_loss_lockout_fraction",
            ),
            max_drawdown_fraction=_require_finite_number(
                payload["max_drawdown_fraction"],
                field_name="max_drawdown_fraction",
            ),
            max_initial_margin_fraction=_require_finite_number(
                payload["max_initial_margin_fraction"],
                field_name="max_initial_margin_fraction",
            ),
            max_maintenance_margin_fraction=_require_finite_number(
                payload["max_maintenance_margin_fraction"],
                field_name="max_maintenance_margin_fraction",
            ),
            overnight_gap_stress_fraction=_require_finite_number(
                payload["overnight_gap_stress_fraction"],
                field_name="overnight_gap_stress_fraction",
            ),
            allowed_operating_postures=tuple(
                str(item) for item in payload["allowed_operating_postures"]
            ),
            default_operating_posture=str(payload["default_operating_posture"]),
            overnight_only_with_strict_class=_require_bool(
                payload["overnight_only_with_strict_class"],
                field_name="overnight_only_with_strict_class",
            ),
            delivery_fence_rule=str(payload["delivery_fence_rule"]),
            delivery_fence_review_required=_require_bool(
                payload["delivery_fence_review_required"],
                field_name="delivery_fence_review_required",
            ),
            warmup_min_history_bars=_require_int(
                payload["warmup_min_history_bars"],
                field_name="warmup_min_history_bars",
            ),
            warmup_min_history_minutes=_require_int(
                payload["warmup_min_history_minutes"],
                field_name="warmup_min_history_minutes",
            ),
            warmup_requires_state_seed=_require_bool(
                payload["warmup_requires_state_seed"],
                field_name="warmup_requires_state_seed",
            ),
        )


@dataclass(frozen=True)
class BaselineRiskEvaluationRequest:
    case_id: str
    product_profile_id: str
    account_profile_id: str
    strategy_contract: StrategyContract
    current_position_size: int
    projected_position_size: int
    pending_order_intent_count: int
    data_quality_degraded: bool
    proposed_order_increases_risk: bool
    daily_loss_fraction: float
    drawdown_fraction: float
    delivery_window_active: bool
    warmup_bars_observed: int
    warmup_minutes_observed: int
    state_seed_loaded: bool
    requested_initial_margin_fraction: float
    requested_maintenance_margin_fraction: float
    requested_operating_posture: str
    overnight_requested: bool
    overnight_approval_granted: bool
    waivers: tuple[PolicyWaiver, ...] = ()
    evaluated_at_utc: str | None = None
    schema_version: int = SUPPORTED_BASELINE_RISK_CONTROL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["strategy_contract"] = self.strategy_contract.to_dict()
        payload["waivers"] = [waiver.to_dict() for waiver in self.waivers]
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BaselineRiskEvaluationRequest":
        return cls(
            case_id=str(payload["case_id"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_profile_id=str(payload["account_profile_id"]),
            strategy_contract=StrategyContract.from_dict(dict(payload["strategy_contract"])),
            current_position_size=_require_int(
                payload["current_position_size"],
                field_name="current_position_size",
            ),
            projected_position_size=_require_int(
                payload["projected_position_size"],
                field_name="projected_position_size",
            ),
            pending_order_intent_count=_require_int(
                payload["pending_order_intent_count"],
                field_name="pending_order_intent_count",
            ),
            data_quality_degraded=_require_bool(
                payload["data_quality_degraded"],
                field_name="data_quality_degraded",
            ),
            proposed_order_increases_risk=_require_bool(
                payload["proposed_order_increases_risk"],
                field_name="proposed_order_increases_risk",
            ),
            daily_loss_fraction=_require_finite_number(
                payload["daily_loss_fraction"],
                field_name="daily_loss_fraction",
            ),
            drawdown_fraction=_require_finite_number(
                payload["drawdown_fraction"],
                field_name="drawdown_fraction",
            ),
            delivery_window_active=_require_bool(
                payload["delivery_window_active"],
                field_name="delivery_window_active",
            ),
            warmup_bars_observed=_require_int(
                payload["warmup_bars_observed"],
                field_name="warmup_bars_observed",
            ),
            warmup_minutes_observed=_require_int(
                payload["warmup_minutes_observed"],
                field_name="warmup_minutes_observed",
            ),
            state_seed_loaded=_require_bool(
                payload["state_seed_loaded"],
                field_name="state_seed_loaded",
            ),
            requested_initial_margin_fraction=_require_finite_number(
                payload["requested_initial_margin_fraction"],
                field_name="requested_initial_margin_fraction",
            ),
            requested_maintenance_margin_fraction=_require_finite_number(
                payload["requested_maintenance_margin_fraction"],
                field_name="requested_maintenance_margin_fraction",
            ),
            requested_operating_posture=str(payload["requested_operating_posture"]),
            overnight_requested=_require_bool(
                payload["overnight_requested"],
                field_name="overnight_requested",
            ),
            overnight_approval_granted=_require_bool(
                payload["overnight_approval_granted"],
                field_name="overnight_approval_granted",
            ),
            waivers=tuple(
                PolicyWaiver.from_dict(dict(item)) for item in payload.get("waivers", ())
            ),
            evaluated_at_utc=(
                _normalize_timestamp(str(payload["evaluated_at_utc"]))
                if payload.get("evaluated_at_utc") not in (None, "")
                else None
            ),
            schema_version=_require_schema_version(
                payload.get("schema_version"),
                label="baseline_risk_evaluation_request",
            ),
        )


@dataclass(frozen=True)
class BaselineRiskControlResult:
    control_id: str
    control_name: str
    passed: bool
    waived: bool
    status: str
    action: str
    reason_code: str | None
    diagnostic: str
    context: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    waiver_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BaselineRiskControlResult":
        return cls(
            control_id=str(payload["control_id"]),
            control_name=str(payload["control_name"]),
            passed=_require_bool(payload["passed"], field_name="passed"),
            waived=_require_bool(payload["waived"], field_name="waived"),
            status=str(payload["status"]),
            action=str(payload["action"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            context=dict(payload.get("context", {})),
            remediation=(
                str(payload["remediation"])
                if payload.get("remediation") not in (None, "")
                else None
            ),
            waiver_references=tuple(str(item) for item in payload.get("waiver_references", ())),
        )


@dataclass(frozen=True)
class BaselineRiskEvaluationReport:
    case_id: str
    status: str
    reason_code: str
    action: str
    product_profile_id: str
    account_profile_id: str
    contract_id: str
    default_control_source_ids: tuple[str, ...]
    effective_defaults: BaselineRiskDefaults | None
    missing_fields: tuple[str, ...]
    triggered_control_ids: tuple[str, ...]
    waiver_references: tuple[str, ...]
    control_results: tuple[BaselineRiskControlResult, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["effective_defaults"] = (
            self.effective_defaults.to_dict() if self.effective_defaults is not None else None
        )
        payload["control_results"] = [result.to_dict() for result in self.control_results]
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BaselineRiskEvaluationReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            action=str(payload["action"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_profile_id=str(payload["account_profile_id"]),
            contract_id=str(payload["contract_id"]),
            default_control_source_ids=tuple(
                str(item) for item in payload["default_control_source_ids"]
            ),
            effective_defaults=(
                BaselineRiskDefaults.from_dict(dict(payload["effective_defaults"]))
                if payload.get("effective_defaults") is not None
                else None
            ),
            missing_fields=tuple(str(item) for item in payload.get("missing_fields", ())),
            triggered_control_ids=tuple(
                str(item) for item in payload.get("triggered_control_ids", ())
            ),
            waiver_references=tuple(str(item) for item in payload.get("waiver_references", ())),
            control_results=tuple(
                BaselineRiskControlResult.from_dict(dict(item))
                for item in payload.get("control_results", ())
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=_normalize_timestamp(str(payload.get("timestamp", _utcnow()))),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BaselineRiskEvaluationReport":
        return cls.from_dict(
            _decode_json_object(
                payload,
                label="baseline_risk_evaluation_report",
            )
        )


def inherited_baseline_risk_defaults(
    *,
    product_profile_id: str,
    account_profile_id: str,
    strategy_contract: StrategyContract,
) -> BaselineRiskDefaults:
    product = product_profiles_by_id()[product_profile_id]
    account = account_risk_profiles_by_id()[account_profile_id]
    execution_symbol = product.contract_specification.symbol
    max_position_size = account.max_position_size_by_symbol[execution_symbol]
    return BaselineRiskDefaults(
        source_product_profile_id=product.profile_id,
        source_account_profile_id=account.profile_id,
        source_strategy_contract_id=strategy_contract.contract_id,
        execution_symbol=execution_symbol,
        max_position_size=max_position_size,
        max_concurrent_order_intents=max(1, max_position_size),
        daily_loss_lockout_fraction=account.daily_loss_lockout_fraction,
        max_drawdown_fraction=account.max_drawdown_fraction,
        max_initial_margin_fraction=account.max_initial_margin_fraction,
        max_maintenance_margin_fraction=account.max_maintenance_margin_fraction,
        overnight_gap_stress_fraction=account.overnight_gap_stress_fraction,
        allowed_operating_postures=tuple(
            posture.value for posture in account.allowed_operating_postures
        ),
        default_operating_posture=account.default_operating_posture.value,
        overnight_only_with_strict_class=account.overnight_only_with_strict_class,
        delivery_fence_rule=product.delivery_fence.delivery_fence_rule,
        delivery_fence_review_required=product.delivery_fence.reviewed_roll_required,
        warmup_min_history_bars=strategy_contract.warmup.min_history_bars,
        warmup_min_history_minutes=strategy_contract.warmup.min_history_minutes,
        warmup_requires_state_seed=strategy_contract.warmup.requires_state_seed,
    )


def _matching_waiver_ids(
    *,
    waivers: tuple[PolicyWaiver, ...],
    control_id: str,
    reason_code: str,
    at_utc: str | None,
) -> tuple[str, ...]:
    matches: list[str] = []
    for waiver in waivers:
        if not waiver.is_active(at_utc):
            continue
        if waiver.categories and BASELINE_RISK_WAIVER_CATEGORY not in waiver.categories:
            continue
        if waiver.rule_ids and control_id not in waiver.rule_ids:
            continue
        if waiver.reason_codes and reason_code not in waiver.reason_codes:
            continue
        matches.append(waiver.waiver_id)
    return tuple(sorted(set(matches)))


def _control_result(
    *,
    control_id: str,
    control_name: str,
    triggered: bool,
    action: RiskControlAction,
    reason_code: str,
    diagnostic: str,
    remediation: str,
    context: dict[str, Any],
    waivers: tuple[PolicyWaiver, ...],
    evaluated_at_utc: str | None,
) -> BaselineRiskControlResult:
    if not triggered:
        return BaselineRiskControlResult(
            control_id=control_id,
            control_name=control_name,
            passed=True,
            waived=False,
            status=RiskControlStatus.PASS.value,
            action=RiskControlAction.ALLOW.value,
            reason_code=None,
            diagnostic=diagnostic,
            context=context,
            remediation="No remediation required.",
        )

    waiver_references = _matching_waiver_ids(
        waivers=waivers,
        control_id=control_id,
        reason_code=reason_code,
        at_utc=evaluated_at_utc,
    )
    return BaselineRiskControlResult(
        control_id=control_id,
        control_name=control_name,
        passed=False,
        waived=bool(waiver_references),
        status=RiskControlStatus.VIOLATION.value,
        action=action.value,
        reason_code=reason_code,
        diagnostic=diagnostic,
        context=context,
        remediation=remediation,
        waiver_references=waiver_references,
    )


def _invalid_report(
    request: BaselineRiskEvaluationRequest,
    *,
    missing_fields: tuple[str, ...],
    explanation: str,
) -> BaselineRiskEvaluationReport:
    return BaselineRiskEvaluationReport(
        case_id=request.case_id,
        status=RiskControlStatus.INVALID.value,
        reason_code="BASELINE_RISK_INVALID",
        action=RiskControlAction.HALT.value,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        contract_id=request.strategy_contract.contract_id,
        default_control_source_ids=(),
        effective_defaults=None,
        missing_fields=missing_fields,
        triggered_control_ids=(),
        waiver_references=(),
        control_results=(),
        explanation=explanation,
        remediation=(
            "Repair the canonical product/account binding or request payload before applying "
            "baseline live-lane controls."
        ),
    )


def evaluate_baseline_risk_controls(
    request: BaselineRiskEvaluationRequest,
) -> BaselineRiskEvaluationReport:
    missing_fields: list[str] = []
    products = product_profiles_by_id()
    accounts = account_risk_profiles_by_id()

    if request.schema_version != SUPPORTED_BASELINE_RISK_CONTROL_SCHEMA_VERSION:
        missing_fields.append("schema_version")
    if request.product_profile_id not in products:
        missing_fields.append("product_profile_id")
    if request.account_profile_id not in accounts:
        missing_fields.append("account_profile_id")
    if request.pending_order_intent_count < 0:
        missing_fields.append("pending_order_intent_count")
    if request.warmup_bars_observed < 0:
        missing_fields.append("warmup_bars_observed")
    if request.warmup_minutes_observed < 0:
        missing_fields.append("warmup_minutes_observed")
    if request.daily_loss_fraction < 0:
        missing_fields.append("daily_loss_fraction")
    if request.drawdown_fraction < 0:
        missing_fields.append("drawdown_fraction")
    if request.requested_initial_margin_fraction < 0:
        missing_fields.append("requested_initial_margin_fraction")
    if request.requested_maintenance_margin_fraction < 0:
        missing_fields.append("requested_maintenance_margin_fraction")
    if request.requested_operating_posture not in {
        posture.value for posture in OperatingPosture
    }:
        missing_fields.append("requested_operating_posture")

    if missing_fields:
        return _invalid_report(
            request,
            missing_fields=tuple(missing_fields),
            explanation=(
                "Baseline risk controls could not be evaluated because required request or "
                f"catalog fields were invalid: {missing_fields}."
            ),
        )

    defaults = inherited_baseline_risk_defaults(
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        strategy_contract=request.strategy_contract,
    )
    abs_current_position = abs(request.current_position_size)
    abs_projected_position = abs(request.projected_position_size)
    first_trade_pending = abs_current_position == 0 and abs_projected_position > 0

    control_results = (
        _control_result(
            control_id="max_position_limit",
            control_name="Maximum position limit",
            triggered=(
                abs_projected_position > defaults.max_position_size
                or abs_current_position > defaults.max_position_size
            ),
            action=(
                RiskControlAction.EXIT_ONLY
                if abs_current_position > defaults.max_position_size
                else RiskControlAction.RESTRICT
            ),
            reason_code="BASELINE_RISK_POSITION_LIMIT_EXCEEDED",
            diagnostic=(
                "Projected or active position size exceeds the inherited account maximum for "
                "the execution symbol."
            ),
            remediation="Reduce position size or obtain a signed waiver for the exception.",
            context={
                "current_position_size": request.current_position_size,
                "projected_position_size": request.projected_position_size,
                "max_position_size": defaults.max_position_size,
                "execution_symbol": defaults.execution_symbol,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="max_concurrent_order_intents",
            control_name="Concurrent order-intent limit",
            triggered=request.pending_order_intent_count > defaults.max_concurrent_order_intents,
            action=RiskControlAction.RESTRICT,
            reason_code="BASELINE_RISK_CONCURRENT_ORDER_INTENT_LIMIT_EXCEEDED",
            diagnostic=(
                "Concurrent order-intent count exceeds the inherited live-lane default and "
                "must be throttled before additional entry attempts."
            ),
            remediation=(
                "Drain outstanding intents or obtain an explicit waiver before increasing "
                "order concurrency."
            ),
            context={
                "pending_order_intent_count": request.pending_order_intent_count,
                "max_concurrent_order_intents": defaults.max_concurrent_order_intents,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="degraded_data_entry_suppression",
            control_name="Degraded-data entry suppression",
            triggered=request.data_quality_degraded and request.proposed_order_increases_risk,
            action=RiskControlAction.RESTRICT,
            reason_code="BASELINE_RISK_DATA_DEGRADED_ENTRY_SUPPRESSION",
            diagnostic=(
                "Data quality is degraded while the proposed action would increase risk, so "
                "the inherited baseline blocks fresh entry."
            ),
            remediation=(
                "Restore data quality or keep the strategy in non-expanding posture until "
                "market data is trustworthy again."
            ),
            context={
                "data_quality_degraded": request.data_quality_degraded,
                "proposed_order_increases_risk": request.proposed_order_increases_risk,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="daily_loss_lockout",
            control_name="Daily loss lockout",
            triggered=request.daily_loss_fraction >= defaults.daily_loss_lockout_fraction,
            action=RiskControlAction.EXIT_ONLY,
            reason_code="BASELINE_RISK_DAILY_LOSS_LOCKOUT",
            diagnostic=(
                "The strategy breached the inherited daily loss limit and may only reduce "
                "risk until the session is reset."
            ),
            remediation=(
                "Stop new entries, close exposure in an orderly way, and review the loss "
                "incident before continuation."
            ),
            context={
                "daily_loss_fraction": request.daily_loss_fraction,
                "daily_loss_lockout_fraction": defaults.daily_loss_lockout_fraction,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="max_drawdown_flatten",
            control_name="Max drawdown flatten",
            triggered=request.drawdown_fraction >= defaults.max_drawdown_fraction,
            action=RiskControlAction.FLATTEN,
            reason_code="BASELINE_RISK_MAX_DRAWDOWN",
            diagnostic=(
                "Cumulative drawdown breached the inherited hard limit, so the baseline "
                "policy requires immediate flattening."
            ),
            remediation=(
                "Flatten exposure, halt family continuation decisions, and review whether the "
                "candidate still belongs in the live lane."
            ),
            context={
                "drawdown_fraction": request.drawdown_fraction,
                "max_drawdown_fraction": defaults.max_drawdown_fraction,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="delivery_fence_forced_flat",
            control_name="Delivery-fence forced flat",
            triggered=request.delivery_window_active and abs_projected_position > 0,
            action=(
                RiskControlAction.FLATTEN
                if abs_current_position > 0
                else RiskControlAction.RESTRICT
            ),
            reason_code="BASELINE_RISK_DELIVERY_FENCE_FLATTEN",
            diagnostic=(
                "The product profile marked the delivery fence active, so the inherited "
                "baseline blocks or liquidates exposure around the fence."
            ),
            remediation=(
                "Flatten or refuse new exposure until the delivery fence clears and the "
                "reviewed roll path is complete."
            ),
            context={
                "delivery_window_active": request.delivery_window_active,
                "delivery_fence_rule": defaults.delivery_fence_rule,
                "delivery_fence_review_required": defaults.delivery_fence_review_required,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="warmup_hold",
            control_name="Warm-up hold",
            triggered=first_trade_pending
            and (
                request.warmup_bars_observed < defaults.warmup_min_history_bars
                or request.warmup_minutes_observed < defaults.warmup_min_history_minutes
                or (
                    defaults.warmup_requires_state_seed
                    and not request.state_seed_loaded
                )
            ),
            action=RiskControlAction.RESTRICT,
            reason_code="BASELINE_RISK_WARMUP_HOLD",
            diagnostic=(
                "The strategy has not yet satisfied the inherited warm-up requirements for "
                "its first live-lane trade."
            ),
            remediation=(
                "Wait for the required bars/minutes and load the required state seed before "
                "admitting the first trade."
            ),
            context={
                "warmup_bars_observed": request.warmup_bars_observed,
                "warmup_minutes_observed": request.warmup_minutes_observed,
                "state_seed_loaded": request.state_seed_loaded,
                "required_bars": defaults.warmup_min_history_bars,
                "required_minutes": defaults.warmup_min_history_minutes,
                "requires_state_seed": defaults.warmup_requires_state_seed,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="margin_pretrade_check",
            control_name="Margin-aware pre-trade check",
            triggered=(
                request.requested_initial_margin_fraction
                > defaults.max_initial_margin_fraction
                or request.requested_maintenance_margin_fraction
                > defaults.max_maintenance_margin_fraction
            ),
            action=RiskControlAction.HALT,
            reason_code="BASELINE_RISK_MARGIN_LIMIT",
            diagnostic=(
                "Requested margin usage exceeds the inherited account limits, so trading must "
                "halt until the capital posture is repaired."
            ),
            remediation=(
                "Reduce size, recapitalize, or lower margin usage before resuming any live-"
                "lane activity."
            ),
            context={
                "requested_initial_margin_fraction": request.requested_initial_margin_fraction,
                "requested_maintenance_margin_fraction": request.requested_maintenance_margin_fraction,
                "max_initial_margin_fraction": defaults.max_initial_margin_fraction,
                "max_maintenance_margin_fraction": defaults.max_maintenance_margin_fraction,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
        _control_result(
            control_id="overnight_approval",
            control_name="Overnight approval",
            triggered=request.overnight_requested
            and (
                not request.overnight_approval_granted
                or (
                    defaults.overnight_only_with_strict_class
                    and request.requested_operating_posture
                    != OperatingPosture.OVERNIGHT_STRICT.value
                )
            ),
            action=(
                RiskControlAction.EXIT_ONLY
                if abs_current_position > 0
                else RiskControlAction.RESTRICT
            ),
            reason_code=(
                "BASELINE_RISK_OVERNIGHT_STRICT_POSTURE_REQUIRED"
                if request.overnight_requested
                and defaults.overnight_only_with_strict_class
                and request.requested_operating_posture
                != OperatingPosture.OVERNIGHT_STRICT.value
                else "BASELINE_RISK_OVERNIGHT_APPROVAL_REQUIRED"
            ),
            diagnostic=(
                "Overnight carrying requires explicit approval and, for this account class, "
                "the strict overnight operating posture."
            ),
            remediation=(
                "Obtain overnight approval and switch to the strict overnight posture before "
                "carrying exposure across sessions."
            ),
            context={
                "overnight_requested": request.overnight_requested,
                "overnight_approval_granted": request.overnight_approval_granted,
                "requested_operating_posture": request.requested_operating_posture,
                "overnight_only_with_strict_class": defaults.overnight_only_with_strict_class,
            },
            waivers=request.waivers,
            evaluated_at_utc=request.evaluated_at_utc,
        ),
    )

    triggered_control_ids = tuple(
        result.control_id for result in control_results if not result.passed
    )
    waiver_references = tuple(
        sorted(
            {
                waiver_id
                for result in control_results
                for waiver_id in result.waiver_references
            }
        )
    )
    unwaived_violations = [
        result for result in control_results if not result.passed and not result.waived
    ]
    waived_violations = [
        result for result in control_results if not result.passed and result.waived
    ]

    if unwaived_violations:
        dominant = max(
            unwaived_violations,
            key=lambda result: _ACTION_SEVERITY[result.action],
        )
        return BaselineRiskEvaluationReport(
            case_id=request.case_id,
            status=RiskControlStatus.VIOLATION.value,
            reason_code=dominant.reason_code or "BASELINE_RISK_VIOLATION",
            action=dominant.action,
            product_profile_id=request.product_profile_id,
            account_profile_id=request.account_profile_id,
            contract_id=request.strategy_contract.contract_id,
            default_control_source_ids=(
                defaults.source_product_profile_id,
                defaults.source_account_profile_id,
                defaults.source_strategy_contract_id,
            ),
            effective_defaults=defaults,
            missing_fields=(),
            triggered_control_ids=triggered_control_ids,
            waiver_references=waiver_references,
            control_results=control_results,
            explanation=(
                "One or more inherited baseline risk controls fired without an active waiver. "
                f"Triggered controls: {triggered_control_ids}."
            ),
            remediation=(
                "Honor the emitted action, clear the violating condition, or record a signed "
                "waiver before overriding the inherited baseline."
            ),
        )

    if waived_violations:
        return BaselineRiskEvaluationReport(
            case_id=request.case_id,
            status=RiskControlStatus.PASS.value,
            reason_code="BASELINE_RISK_ALLOW_WITH_WAIVER",
            action=RiskControlAction.ALLOW_WITH_WAIVER.value,
            product_profile_id=request.product_profile_id,
            account_profile_id=request.account_profile_id,
            contract_id=request.strategy_contract.contract_id,
            default_control_source_ids=(
                defaults.source_product_profile_id,
                defaults.source_account_profile_id,
                defaults.source_strategy_contract_id,
            ),
            effective_defaults=defaults,
            missing_fields=(),
            triggered_control_ids=triggered_control_ids,
            waiver_references=waiver_references,
            control_results=control_results,
            explanation=(
                "Baseline controls fired, but each exception was covered by an active signed "
                f"waiver. Triggered controls: {triggered_control_ids}."
            ),
            remediation=(
                "Keep the waiver evidence attached to the operator decision and retire the "
                "exception once the root condition is resolved."
            ),
        )

    return BaselineRiskEvaluationReport(
        case_id=request.case_id,
        status=RiskControlStatus.PASS.value,
        reason_code="BASELINE_RISK_ALLOW",
        action=RiskControlAction.ALLOW.value,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        contract_id=request.strategy_contract.contract_id,
        default_control_source_ids=(
            defaults.source_product_profile_id,
            defaults.source_account_profile_id,
            defaults.source_strategy_contract_id,
        ),
        effective_defaults=defaults,
        missing_fields=(),
        triggered_control_ids=(),
        waiver_references=(),
        control_results=control_results,
        explanation=(
            "All inherited baseline risk controls passed, so the live-lane request remains in "
            "allow posture."
        ),
        remediation="No remediation required.",
    )


def validate_baseline_risk_catalog() -> list[str]:
    errors: list[str] = []
    if len(BASELINE_RISK_CONTROL_IDS) != len(set(BASELINE_RISK_CONTROL_IDS)):
        errors.append("baseline risk control identifiers must be unique")
    if not BASELINE_RISK_WAIVER_CATEGORY.strip():
        errors.append("baseline risk waiver category must be non-empty")
    if SUPPORTED_BASELINE_RISK_CONTROL_SCHEMA_VERSION < 1:
        errors.append("baseline risk schema version must stay positive")
    return errors


VALIDATION_ERRORS = validate_baseline_risk_catalog()
