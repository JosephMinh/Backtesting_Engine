"""Account-fit gating on the actual execution contract."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.product_profiles import (
    OperatingPosture,
    account_risk_profiles_by_id,
    product_profiles_by_id,
)

SUPPORTED_ACCOUNT_FIT_GATE_SCHEMA_VERSION = 1
ACCOUNT_FIT_CHECK_IDS = (
    "approved_execution_symbol",
    "initial_margin_fraction",
    "maintenance_margin_fraction",
    "daily_loss_lockout_fraction",
    "max_drawdown_fraction",
    "overnight_gap_stress_fraction",
)


def validate_account_fit_gate_contract() -> list[str]:
    errors: list[str] = []
    if len(ACCOUNT_FIT_CHECK_IDS) != len(set(ACCOUNT_FIT_CHECK_IDS)):
        errors.append("account-fit check identifiers must be unique")
    if SUPPORTED_ACCOUNT_FIT_GATE_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    return errors


VALIDATION_ERRORS = validate_account_fit_gate_contract()


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        datetime.timezone.utc
    )


def _normalize_timestamp(value: str) -> str:
    return _parse_utc(value).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _as_non_negative_float(value: object, *, field_name: str) -> float:
    parsed = float(value)
    if parsed < 0.0:
        raise ValueError(f"{field_name}: must be non-negative")
    return parsed


def _as_positive_int(value: object, *, field_name: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"{field_name}: must be positive")
    return parsed


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@unique
class AccountFitStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    FAIL = "fail"
    INVALID = "invalid"
    STALE = "stale"


@unique
class PromotionTarget(str, Enum):
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"
    LIVE = "live"


@dataclass(frozen=True)
class BrokerMarginSnapshot:
    snapshot_id: str
    broker: str
    symbol: str
    initial_margin_requirement_usd: float
    maintenance_margin_requirement_usd: float
    captured_at_utc: str
    valid_to_utc: str

    def total_initial_margin_usd(self, contract_count: int) -> float:
        return self.initial_margin_requirement_usd * contract_count

    def total_maintenance_margin_usd(self, contract_count: int) -> float:
        return self.maintenance_margin_requirement_usd * contract_count

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrokerMarginSnapshot":
        captured_at_utc = _normalize_timestamp(str(payload["captured_at_utc"]))
        valid_to_utc = _normalize_timestamp(str(payload["valid_to_utc"]))
        if _parse_utc(captured_at_utc) > _parse_utc(valid_to_utc):
            raise ValueError("margin_snapshot.valid_to_utc: must not precede captured_at_utc")
        return cls(
            snapshot_id=str(payload["snapshot_id"]),
            broker=str(payload["broker"]),
            symbol=str(payload["symbol"]),
            initial_margin_requirement_usd=_as_non_negative_float(
                payload["initial_margin_requirement_usd"],
                field_name="initial_margin_requirement_usd",
            ),
            maintenance_margin_requirement_usd=_as_non_negative_float(
                payload["maintenance_margin_requirement_usd"],
                field_name="maintenance_margin_requirement_usd",
            ),
            captured_at_utc=captured_at_utc,
            valid_to_utc=valid_to_utc,
        )


@dataclass(frozen=True)
class FeeScheduleArtifact:
    snapshot_id: str
    broker: str
    symbol: str
    commission_per_contract_side_usd: float
    exchange_and_regulatory_per_contract_side_usd: float
    captured_at_utc: str
    valid_from_utc: str
    valid_to_utc: str

    def round_turn_total_usd(self, contract_count: int) -> float:
        per_side = (
            self.commission_per_contract_side_usd
            + self.exchange_and_regulatory_per_contract_side_usd
        )
        return contract_count * 2.0 * per_side

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeeScheduleArtifact":
        captured_at_utc = _normalize_timestamp(str(payload["captured_at_utc"]))
        valid_from_utc = _normalize_timestamp(str(payload["valid_from_utc"]))
        valid_to_utc = _normalize_timestamp(str(payload["valid_to_utc"]))
        if _parse_utc(valid_from_utc) > _parse_utc(valid_to_utc):
            raise ValueError("fee_schedule.valid_to_utc: must not precede valid_from_utc")
        if _parse_utc(captured_at_utc) > _parse_utc(valid_to_utc):
            raise ValueError("fee_schedule.valid_to_utc: must not precede captured_at_utc")
        return cls(
            snapshot_id=str(payload["snapshot_id"]),
            broker=str(payload["broker"]),
            symbol=str(payload["symbol"]),
            commission_per_contract_side_usd=_as_non_negative_float(
                payload["commission_per_contract_side_usd"],
                field_name="commission_per_contract_side_usd",
            ),
            exchange_and_regulatory_per_contract_side_usd=_as_non_negative_float(
                payload["exchange_and_regulatory_per_contract_side_usd"],
                field_name="exchange_and_regulatory_per_contract_side_usd",
            ),
            captured_at_utc=captured_at_utc,
            valid_from_utc=valid_from_utc,
            valid_to_utc=valid_to_utc,
        )


@dataclass(frozen=True)
class AccountFitThresholds:
    source_product_profile_id: str
    source_account_profile_id: str
    execution_symbol: str
    approved_starting_equity_usd: int
    approved_symbols: tuple[str, ...]
    max_position_size: int | None
    max_initial_margin_fraction: float
    max_maintenance_margin_fraction: float
    daily_loss_lockout_fraction: float
    max_drawdown_fraction: float
    overnight_gap_stress_fraction: float

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountFitThresholds":
        return cls(
            source_product_profile_id=str(payload["source_product_profile_id"]),
            source_account_profile_id=str(payload["source_account_profile_id"]),
            execution_symbol=str(payload["execution_symbol"]),
            approved_starting_equity_usd=int(payload["approved_starting_equity_usd"]),
            approved_symbols=tuple(str(item) for item in payload["approved_symbols"]),
            max_position_size=(
                int(payload["max_position_size"])
                if payload.get("max_position_size") is not None
                else None
            ),
            max_initial_margin_fraction=float(payload["max_initial_margin_fraction"]),
            max_maintenance_margin_fraction=float(
                payload["max_maintenance_margin_fraction"]
            ),
            daily_loss_lockout_fraction=float(payload["daily_loss_lockout_fraction"]),
            max_drawdown_fraction=float(payload["max_drawdown_fraction"]),
            overnight_gap_stress_fraction=float(payload["overnight_gap_stress_fraction"]),
        )


@dataclass(frozen=True)
class AccountFitRequest:
    case_id: str
    candidate_id: str
    promotion_target: str
    product_profile_id: str
    account_profile_id: str
    requested_contract_count: int
    requested_operating_posture: str
    overnight_requested: bool
    expected_daily_loss_usd: float
    expected_max_drawdown_usd: float
    expected_overnight_gap_stress_usd: float
    margin_snapshot: BrokerMarginSnapshot
    fee_schedule: FeeScheduleArtifact
    evaluated_at_utc: str | None = None
    schema_version: int = SUPPORTED_ACCOUNT_FIT_GATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["margin_snapshot"] = self.margin_snapshot.to_dict()
        payload["fee_schedule"] = self.fee_schedule.to_dict()
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountFitRequest":
        return cls(
            case_id=str(payload["case_id"]),
            candidate_id=str(payload["candidate_id"]),
            promotion_target=str(payload["promotion_target"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_profile_id=str(payload["account_profile_id"]),
            requested_contract_count=_as_positive_int(
                payload["requested_contract_count"],
                field_name="requested_contract_count",
            ),
            requested_operating_posture=str(payload["requested_operating_posture"]),
            overnight_requested=bool(payload["overnight_requested"]),
            expected_daily_loss_usd=_as_non_negative_float(
                payload["expected_daily_loss_usd"],
                field_name="expected_daily_loss_usd",
            ),
            expected_max_drawdown_usd=_as_non_negative_float(
                payload["expected_max_drawdown_usd"],
                field_name="expected_max_drawdown_usd",
            ),
            expected_overnight_gap_stress_usd=_as_non_negative_float(
                payload["expected_overnight_gap_stress_usd"],
                field_name="expected_overnight_gap_stress_usd",
            ),
            margin_snapshot=BrokerMarginSnapshot.from_dict(
                dict(payload["margin_snapshot"])
            ),
            fee_schedule=FeeScheduleArtifact.from_dict(dict(payload["fee_schedule"])),
            evaluated_at_utc=(
                _normalize_timestamp(str(payload["evaluated_at_utc"]))
                if payload.get("evaluated_at_utc") not in (None, "")
                else None
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_ACCOUNT_FIT_GATE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AccountFitRequest":
        return cls.from_dict(_decode_json_object(payload, label="account_fit_request"))


@dataclass(frozen=True)
class AccountFitCheckResult:
    check_id: str
    title: str
    applied: bool
    passed: bool
    reason_code: str | None
    actual_fraction: float | None
    threshold_fraction: float | None
    actual_usd: float | None
    threshold_usd: float | None
    diagnostic: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountFitCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            title=str(payload["title"]),
            applied=bool(payload["applied"]),
            passed=bool(payload["passed"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            actual_fraction=(
                float(payload["actual_fraction"])
                if payload.get("actual_fraction") is not None
                else None
            ),
            threshold_fraction=(
                float(payload["threshold_fraction"])
                if payload.get("threshold_fraction") is not None
                else None
            ),
            actual_usd=(
                float(payload["actual_usd"])
                if payload.get("actual_usd") is not None
                else None
            ),
            threshold_usd=(
                float(payload["threshold_usd"])
                if payload.get("threshold_usd") is not None
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            context=dict(payload.get("context", {})),
        )


@dataclass(frozen=True)
class AccountFitReport:
    case_id: str
    candidate_id: str
    status: str
    reason_code: str
    promotion_target: str
    product_profile_id: str
    account_profile_id: str
    execution_symbol: str
    requested_contract_count: int
    requested_operating_posture: str
    overnight_requested: bool
    threshold_source_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    thresholds: AccountFitThresholds | None
    margin_snapshot: BrokerMarginSnapshot | None
    fee_schedule: FeeScheduleArtifact | None
    round_turn_fees_usd: float
    expected_daily_loss_usd: float
    expected_max_drawdown_usd: float
    expected_overnight_gap_stress_usd: float
    failed_check_ids: tuple[str, ...]
    check_results: tuple[AccountFitCheckResult, ...]
    allowed_execution_symbol: str | None
    explanation: str
    remediation: str
    evaluated_at_utc: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"] = self.thresholds.to_dict() if self.thresholds is not None else None
        payload["margin_snapshot"] = (
            self.margin_snapshot.to_dict() if self.margin_snapshot is not None else None
        )
        payload["fee_schedule"] = (
            self.fee_schedule.to_dict() if self.fee_schedule is not None else None
        )
        payload["check_results"] = [result.to_dict() for result in self.check_results]
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountFitReport":
        return cls(
            case_id=str(payload["case_id"]),
            candidate_id=str(payload["candidate_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            promotion_target=str(payload["promotion_target"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_profile_id=str(payload["account_profile_id"]),
            execution_symbol=str(payload["execution_symbol"]),
            requested_contract_count=int(payload["requested_contract_count"]),
            requested_operating_posture=str(payload["requested_operating_posture"]),
            overnight_requested=bool(payload["overnight_requested"]),
            threshold_source_ids=tuple(str(item) for item in payload["threshold_source_ids"]),
            artifact_ids=tuple(str(item) for item in payload["artifact_ids"]),
            thresholds=(
                AccountFitThresholds.from_dict(dict(payload["thresholds"]))
                if payload.get("thresholds") is not None
                else None
            ),
            margin_snapshot=(
                BrokerMarginSnapshot.from_dict(dict(payload["margin_snapshot"]))
                if payload.get("margin_snapshot") is not None
                else None
            ),
            fee_schedule=(
                FeeScheduleArtifact.from_dict(dict(payload["fee_schedule"]))
                if payload.get("fee_schedule") is not None
                else None
            ),
            round_turn_fees_usd=float(payload["round_turn_fees_usd"]),
            expected_daily_loss_usd=float(payload["expected_daily_loss_usd"]),
            expected_max_drawdown_usd=float(payload["expected_max_drawdown_usd"]),
            expected_overnight_gap_stress_usd=float(
                payload["expected_overnight_gap_stress_usd"]
            ),
            failed_check_ids=tuple(str(item) for item in payload["failed_check_ids"]),
            check_results=tuple(
                AccountFitCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            allowed_execution_symbol=(
                str(payload["allowed_execution_symbol"])
                if payload.get("allowed_execution_symbol") not in (None, "")
                else None
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            evaluated_at_utc=str(payload["evaluated_at_utc"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AccountFitReport":
        return cls.from_dict(_decode_json_object(payload, label="account_fit_report"))


@dataclass(frozen=True)
class AccountFitExecutionDecision:
    candidate_id: str
    status: str
    reason_code: str
    allowed_execution_symbols: tuple[str, ...]
    selected_execution_symbol: str | None
    source_case_ids: tuple[str, ...]
    report_status_by_symbol: dict[str, str]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountFitExecutionDecision":
        return cls(
            candidate_id=str(payload["candidate_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            allowed_execution_symbols=tuple(
                str(item) for item in payload["allowed_execution_symbols"]
            ),
            selected_execution_symbol=(
                str(payload["selected_execution_symbol"])
                if payload.get("selected_execution_symbol") not in (None, "")
                else None
            ),
            source_case_ids=tuple(str(item) for item in payload["source_case_ids"]),
            report_status_by_symbol={
                str(key): str(value)
                for key, value in dict(payload["report_status_by_symbol"]).items()
            },
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "AccountFitExecutionDecision":
        return cls.from_dict(
            _decode_json_object(payload, label="account_fit_execution_decision")
        )


def derive_account_fit_thresholds(
    *,
    product_profile_id: str,
    account_profile_id: str,
) -> AccountFitThresholds:
    product = product_profiles_by_id()[product_profile_id]
    account = account_risk_profiles_by_id()[account_profile_id]
    execution_symbol = product.contract_specification.symbol
    return AccountFitThresholds(
        source_product_profile_id=product.profile_id,
        source_account_profile_id=account.profile_id,
        execution_symbol=execution_symbol,
        approved_starting_equity_usd=account.approved_starting_equity_usd,
        approved_symbols=tuple(account.approved_symbols),
        max_position_size=account.max_position_size_by_symbol.get(execution_symbol),
        max_initial_margin_fraction=account.max_initial_margin_fraction,
        max_maintenance_margin_fraction=account.max_maintenance_margin_fraction,
        daily_loss_lockout_fraction=account.daily_loss_lockout_fraction,
        max_drawdown_fraction=account.max_drawdown_fraction,
        overnight_gap_stress_fraction=account.overnight_gap_stress_fraction,
    )


def _invalid_report(
    request: AccountFitRequest,
    *,
    execution_symbol: str,
    explanation: str,
    remediation: str,
) -> AccountFitReport:
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()
    return AccountFitReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=AccountFitStatus.INVALID.value,
        reason_code="ACCOUNT_FIT_INVALID",
        promotion_target=request.promotion_target,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        execution_symbol=execution_symbol,
        requested_contract_count=request.requested_contract_count,
        requested_operating_posture=request.requested_operating_posture,
        overnight_requested=request.overnight_requested,
        threshold_source_ids=(),
        artifact_ids=(
            request.margin_snapshot.snapshot_id,
            request.fee_schedule.snapshot_id,
        ),
        thresholds=None,
        margin_snapshot=request.margin_snapshot,
        fee_schedule=request.fee_schedule,
        round_turn_fees_usd=0.0,
        expected_daily_loss_usd=request.expected_daily_loss_usd,
        expected_max_drawdown_usd=request.expected_max_drawdown_usd,
        expected_overnight_gap_stress_usd=request.expected_overnight_gap_stress_usd,
        failed_check_ids=(),
        check_results=(),
        allowed_execution_symbol=None,
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )


def _stale_report(
    request: AccountFitRequest,
    *,
    thresholds: AccountFitThresholds,
    reason_code: str,
    explanation: str,
    remediation: str,
    evaluated_at_utc: str,
) -> AccountFitReport:
    return AccountFitReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=AccountFitStatus.STALE.value,
        reason_code=reason_code,
        promotion_target=request.promotion_target,
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
        execution_symbol=thresholds.execution_symbol,
        requested_contract_count=request.requested_contract_count,
        requested_operating_posture=request.requested_operating_posture,
        overnight_requested=request.overnight_requested,
        threshold_source_ids=(
            thresholds.source_product_profile_id,
            thresholds.source_account_profile_id,
        ),
        artifact_ids=(
            request.margin_snapshot.snapshot_id,
            request.fee_schedule.snapshot_id,
        ),
        thresholds=thresholds,
        margin_snapshot=request.margin_snapshot,
        fee_schedule=request.fee_schedule,
        round_turn_fees_usd=request.fee_schedule.round_turn_total_usd(
            request.requested_contract_count
        ),
        expected_daily_loss_usd=request.expected_daily_loss_usd,
        expected_max_drawdown_usd=request.expected_max_drawdown_usd,
        expected_overnight_gap_stress_usd=request.expected_overnight_gap_stress_usd,
        failed_check_ids=(),
        check_results=(),
        allowed_execution_symbol=None,
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )


def _approval_check(
    *,
    request: AccountFitRequest,
    thresholds: AccountFitThresholds,
) -> AccountFitCheckResult:
    symbol_approved = thresholds.execution_symbol in thresholds.approved_symbols
    size_approved = (
        thresholds.max_position_size is not None
        and request.requested_contract_count <= thresholds.max_position_size
    )
    passed = symbol_approved and size_approved
    if passed:
        diagnostic = (
            f"{thresholds.execution_symbol} is approved for the account posture at "
            f"{request.requested_contract_count} contract(s)."
        )
        reason_code = None
    else:
        diagnostic = (
            f"{thresholds.execution_symbol} is not approved for the account posture at "
            f"{request.requested_contract_count} contract(s)."
        )
        reason_code = "ACCOUNT_FIT_EXECUTION_SYMBOL_NOT_APPROVED"
    return AccountFitCheckResult(
        check_id="approved_execution_symbol",
        title="Approved execution symbol",
        applied=True,
        passed=passed,
        reason_code=reason_code,
        actual_fraction=None,
        threshold_fraction=None,
        actual_usd=None,
        threshold_usd=None,
        diagnostic=diagnostic,
        context={
            "execution_symbol": thresholds.execution_symbol,
            "approved_symbols": list(thresholds.approved_symbols),
            "requested_contract_count": request.requested_contract_count,
            "max_position_size": thresholds.max_position_size,
        },
    )


def _fraction_check(
    *,
    check_id: str,
    title: str,
    actual_usd: float,
    threshold_fraction: float,
    equity_usd: int,
    applied: bool,
    skipped_message: str | None = None,
) -> AccountFitCheckResult:
    actual_fraction = actual_usd / float(equity_usd)
    threshold_usd = threshold_fraction * float(equity_usd)
    passed = (actual_fraction <= threshold_fraction) if applied else True
    if not applied:
        diagnostic = skipped_message or f"{title} was not applied."
        reason_code = None
    elif passed:
        diagnostic = (
            f"{title} used {actual_fraction:.4f} of approved equity against a "
            f"{threshold_fraction:.4f} limit."
        )
        reason_code = None
    else:
        diagnostic = (
            f"{title} used {actual_fraction:.4f} of approved equity and exceeds the "
            f"{threshold_fraction:.4f} limit."
        )
        reason_code = {
            "initial_margin_fraction": "ACCOUNT_FIT_INITIAL_MARGIN_EXCEEDED",
            "maintenance_margin_fraction": "ACCOUNT_FIT_MAINTENANCE_MARGIN_EXCEEDED",
            "daily_loss_lockout_fraction": "ACCOUNT_FIT_DAILY_LOSS_LOCKOUT_EXCEEDED",
            "max_drawdown_fraction": "ACCOUNT_FIT_MAX_DRAWDOWN_EXCEEDED",
            "overnight_gap_stress_fraction": "ACCOUNT_FIT_OVERNIGHT_GAP_STRESS_EXCEEDED",
        }[check_id]
    return AccountFitCheckResult(
        check_id=check_id,
        title=title,
        applied=applied,
        passed=passed,
        reason_code=reason_code,
        actual_fraction=actual_fraction,
        threshold_fraction=threshold_fraction,
        actual_usd=actual_usd,
        threshold_usd=threshold_usd,
        diagnostic=diagnostic,
        context={
            "approved_starting_equity_usd": equity_usd,
        },
    )


def evaluate_account_fit(request: AccountFitRequest) -> AccountFitReport:
    products = product_profiles_by_id()
    accounts = account_risk_profiles_by_id()
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()

    missing_fields: list[str] = []
    if request.schema_version != SUPPORTED_ACCOUNT_FIT_GATE_SCHEMA_VERSION:
        missing_fields.append("schema_version")
    if request.product_profile_id not in products:
        missing_fields.append("product_profile_id")
    if request.account_profile_id not in accounts:
        missing_fields.append("account_profile_id")
    if request.promotion_target not in {target.value for target in PromotionTarget}:
        missing_fields.append("promotion_target")
    if request.requested_operating_posture not in {
        posture.value for posture in OperatingPosture
    }:
        missing_fields.append("requested_operating_posture")
    if request.requested_contract_count < 1:
        missing_fields.append("requested_contract_count")
    if request.expected_daily_loss_usd < 0:
        missing_fields.append("expected_daily_loss_usd")
    if request.expected_max_drawdown_usd < 0:
        missing_fields.append("expected_max_drawdown_usd")
    if request.expected_overnight_gap_stress_usd < 0:
        missing_fields.append("expected_overnight_gap_stress_usd")

    execution_symbol = request.margin_snapshot.symbol
    if request.product_profile_id in products:
        execution_symbol = products[request.product_profile_id].contract_specification.symbol

    if missing_fields:
        return _invalid_report(
            request,
            execution_symbol=execution_symbol,
            explanation=(
                "Account-fit could not be evaluated because required request or catalog fields "
                f"were invalid: {missing_fields}."
            ),
            remediation=(
                "Repair the canonical product/account binding and request payload before "
                "re-running account-fit."
            ),
        )

    thresholds = derive_account_fit_thresholds(
        product_profile_id=request.product_profile_id,
        account_profile_id=request.account_profile_id,
    )
    product = products[request.product_profile_id]
    account = accounts[request.account_profile_id]
    execution_symbol = thresholds.execution_symbol

    alignment_errors: list[str] = []
    if request.margin_snapshot.broker != account.broker:
        alignment_errors.append("margin_snapshot.broker")
    if request.fee_schedule.broker != account.broker:
        alignment_errors.append("fee_schedule.broker")
    if request.margin_snapshot.symbol != execution_symbol:
        alignment_errors.append("margin_snapshot.symbol")
    if request.fee_schedule.symbol != execution_symbol:
        alignment_errors.append("fee_schedule.symbol")
    if alignment_errors:
        return _invalid_report(
            request,
            execution_symbol=execution_symbol,
            explanation=(
                "Account-fit artifacts did not match the canonical execution contract or broker "
                f"binding: {alignment_errors}."
            ),
            remediation=(
                "Refresh the margin and fee artifacts so they match the actual execution "
                "contract and approved broker binding."
            ),
        )

    margin_is_fresh = (
        _parse_utc(request.margin_snapshot.captured_at_utc)
        <= _parse_utc(evaluated_at_utc)
        <= _parse_utc(request.margin_snapshot.valid_to_utc)
    )
    fee_is_current = (
        _parse_utc(request.fee_schedule.valid_from_utc)
        <= _parse_utc(evaluated_at_utc)
        <= _parse_utc(request.fee_schedule.valid_to_utc)
    )
    if not margin_is_fresh or not fee_is_current:
        if not margin_is_fresh and not fee_is_current:
            reason_code = "ACCOUNT_FIT_MARGIN_AND_FEE_ARTIFACTS_STALE"
            explanation = (
                "Account-fit stopped because both the broker margin snapshot and fee schedule "
                "artifact were outside their freshness windows."
            )
        elif not margin_is_fresh:
            reason_code = "ACCOUNT_FIT_MARGIN_SNAPSHOT_STALE"
            explanation = (
                "Account-fit stopped because the broker margin snapshot was outside its "
                "freshness window."
            )
        else:
            reason_code = "ACCOUNT_FIT_FEE_SCHEDULE_STALE"
            explanation = (
                "Account-fit stopped because the fee schedule artifact was outside its "
                "current validity window."
            )
        return _stale_report(
            request,
            thresholds=thresholds,
            reason_code=reason_code,
            explanation=explanation,
            remediation=(
                "Refresh the stale margin or fee artifact and re-run account-fit before "
                "promotion."
            ),
            evaluated_at_utc=evaluated_at_utc,
        )

    round_turn_fees_usd = request.fee_schedule.round_turn_total_usd(
        request.requested_contract_count
    )
    equity_usd = thresholds.approved_starting_equity_usd

    check_results = (
        _approval_check(request=request, thresholds=thresholds),
        _fraction_check(
            check_id="initial_margin_fraction",
            title="Initial margin usage",
            actual_usd=(
                request.margin_snapshot.total_initial_margin_usd(
                    request.requested_contract_count
                )
                + round_turn_fees_usd
            ),
            threshold_fraction=thresholds.max_initial_margin_fraction,
            equity_usd=equity_usd,
            applied=True,
        ),
        _fraction_check(
            check_id="maintenance_margin_fraction",
            title="Maintenance margin usage",
            actual_usd=(
                request.margin_snapshot.total_maintenance_margin_usd(
                    request.requested_contract_count
                )
                + round_turn_fees_usd
            ),
            threshold_fraction=thresholds.max_maintenance_margin_fraction,
            equity_usd=equity_usd,
            applied=True,
        ),
        _fraction_check(
            check_id="daily_loss_lockout_fraction",
            title="Daily loss lockout budget",
            actual_usd=request.expected_daily_loss_usd + round_turn_fees_usd,
            threshold_fraction=thresholds.daily_loss_lockout_fraction,
            equity_usd=equity_usd,
            applied=True,
        ),
        _fraction_check(
            check_id="max_drawdown_fraction",
            title="Max drawdown budget",
            actual_usd=request.expected_max_drawdown_usd + round_turn_fees_usd,
            threshold_fraction=thresholds.max_drawdown_fraction,
            equity_usd=equity_usd,
            applied=True,
        ),
        _fraction_check(
            check_id="overnight_gap_stress_fraction",
            title="Overnight gap stress budget",
            actual_usd=request.expected_overnight_gap_stress_usd + round_turn_fees_usd,
            threshold_fraction=thresholds.overnight_gap_stress_fraction,
            equity_usd=equity_usd,
            applied=request.overnight_requested,
            skipped_message=(
                "Overnight gap stress was not enforced because the request is not asking for "
                "overnight exposure."
            ),
        ),
    )

    failed_check_ids = tuple(
        result.check_id
        for result in check_results
        if result.applied and not result.passed
    )
    if not failed_check_ids:
        status = AccountFitStatus.PASS.value
        reason_code = "ACCOUNT_FIT_PASSED"
        explanation = (
            f"Account-fit passed on the actual execution contract {execution_symbol} using "
            "fresh broker margin and current fee artifacts."
        )
        remediation = "No remediation required."
        allowed_execution_symbol = execution_symbol
    else:
        status = AccountFitStatus.FAIL.value
        if len(failed_check_ids) == 1:
            failed_result = next(
                result for result in check_results if result.check_id == failed_check_ids[0]
            )
            reason_code = str(failed_result.reason_code)
        else:
            reason_code = "ACCOUNT_FIT_MULTIPLE_CONSTRAINTS_EXCEEDED"
        explanation = (
            f"Account-fit failed for {execution_symbol}. Failing checks: "
            f"{', '.join(failed_check_ids)}."
        )
        remediation = (
            "Reduce the actual-contract margin or risk envelope, or proceed only with an "
            "approved smaller execution symbol before promotion."
        )
        allowed_execution_symbol = None

    return AccountFitReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=status,
        reason_code=reason_code,
        promotion_target=request.promotion_target,
        product_profile_id=product.profile_id,
        account_profile_id=account.profile_id,
        execution_symbol=execution_symbol,
        requested_contract_count=request.requested_contract_count,
        requested_operating_posture=request.requested_operating_posture,
        overnight_requested=request.overnight_requested,
        threshold_source_ids=(product.profile_id, account.profile_id),
        artifact_ids=(
            request.margin_snapshot.snapshot_id,
            request.fee_schedule.snapshot_id,
        ),
        thresholds=thresholds,
        margin_snapshot=request.margin_snapshot,
        fee_schedule=request.fee_schedule,
        round_turn_fees_usd=round_turn_fees_usd,
        expected_daily_loss_usd=request.expected_daily_loss_usd,
        expected_max_drawdown_usd=request.expected_max_drawdown_usd,
        expected_overnight_gap_stress_usd=request.expected_overnight_gap_stress_usd,
        failed_check_ids=failed_check_ids,
        check_results=check_results,
        allowed_execution_symbol=allowed_execution_symbol,
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )


def select_account_fit_execution_symbol(
    reports: tuple[AccountFitReport, ...],
) -> AccountFitExecutionDecision:
    if not reports:
        return AccountFitExecutionDecision(
            candidate_id="",
            status=AccountFitStatus.INVALID.value,
            reason_code="ACCOUNT_FIT_EXECUTION_SYMBOL_SELECTION_INVALID",
            allowed_execution_symbols=(),
            selected_execution_symbol=None,
            source_case_ids=(),
            report_status_by_symbol={},
            explanation="No account-fit reports were supplied for execution-symbol selection.",
            remediation="Generate at least one account-fit report before selecting a symbol.",
        )

    candidate_id = reports[0].candidate_id
    statuses = {report.execution_symbol: report.status for report in reports}
    source_case_ids = tuple(report.case_id for report in reports)
    passing_symbols = tuple(
        sorted(report.execution_symbol for report in reports if report.status == "pass")
    )

    if passing_symbols:
        if len(passing_symbols) == 1:
            selected_execution_symbol = passing_symbols[0]
            if (
                selected_execution_symbol == "1OZ"
                and any(
                    report.execution_symbol != "1OZ" and report.status != "pass"
                    for report in reports
                )
            ):
                reason_code = "ACCOUNT_FIT_EXECUTION_SYMBOL_RESTRICTED_TO_1OZ"
                explanation = (
                    "Only 1OZ passed account-fit, so promotion may proceed only with "
                    "execution_symbol=1OZ."
                )
            else:
                reason_code = "ACCOUNT_FIT_EXECUTION_SYMBOL_ALLOWED"
                explanation = (
                    f"{selected_execution_symbol} passed account-fit and is promotable on the "
                    "actual execution contract."
                )
            remediation = "Carry the selected execution symbol into the promotion packet."
            return AccountFitExecutionDecision(
                candidate_id=candidate_id,
                status=AccountFitStatus.PASS.value,
                reason_code=reason_code,
                allowed_execution_symbols=passing_symbols,
                selected_execution_symbol=selected_execution_symbol,
                source_case_ids=source_case_ids,
                report_status_by_symbol=statuses,
                explanation=explanation,
                remediation=remediation,
            )

        return AccountFitExecutionDecision(
            candidate_id=candidate_id,
            status=AccountFitStatus.PASS.value,
            reason_code="ACCOUNT_FIT_MULTIPLE_EXECUTION_SYMBOLS_ALLOWED",
            allowed_execution_symbols=passing_symbols,
            selected_execution_symbol=None,
            source_case_ids=source_case_ids,
            report_status_by_symbol=statuses,
            explanation=(
                "More than one execution symbol passed account-fit, so the promotion path must "
                "pin a single actual execution contract before activation."
            ),
            remediation="Choose one execution symbol before promotion.",
        )

    if any(report.status == AccountFitStatus.STALE.value for report in reports):
        status = AccountFitStatus.STALE.value
        reason_code = "ACCOUNT_FIT_EXECUTION_SYMBOL_SELECTION_STALE"
        explanation = (
            "No execution symbol could be selected because one or more account-fit reports "
            "were stale."
        )
        remediation = "Refresh stale artifacts and regenerate account-fit reports."
    elif any(report.status == AccountFitStatus.INVALID.value for report in reports):
        status = AccountFitStatus.INVALID.value
        reason_code = "ACCOUNT_FIT_EXECUTION_SYMBOL_SELECTION_INVALID"
        explanation = (
            "No execution symbol could be selected because one or more account-fit reports "
            "were invalid."
        )
        remediation = "Repair the invalid account-fit request inputs and rerun the gate."
    else:
        status = AccountFitStatus.FAIL.value
        reason_code = "ACCOUNT_FIT_NO_EXECUTION_SYMBOL_FITS"
        explanation = (
            "No candidate execution symbol passed account-fit on the actual execution contract."
        )
        remediation = (
            "Reduce the contract-level margin or risk envelope, or move to a smaller approved "
            "execution symbol."
        )

    return AccountFitExecutionDecision(
        candidate_id=candidate_id,
        status=status,
        reason_code=reason_code,
        allowed_execution_symbols=(),
        selected_execution_symbol=None,
        source_case_ids=source_case_ids,
        report_status_by_symbol=statuses,
        explanation=explanation,
        remediation=remediation,
    )
