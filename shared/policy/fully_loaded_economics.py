"""Fully loaded economics contract with recurring cost allocation."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from enum import Enum, unique
from typing import Any

SUPPORTED_FULLY_LOADED_ECONOMICS_SCHEMA_VERSION = 1
DIRECT_COST_COMPONENTS = (
    "broker_commissions_and_fees_usd",
    "exchange_and_regulatory_fees_usd",
    "slippage_usd",
)
RECURRING_COST_COMPONENTS = (
    "live_market_data_usd",
    "historical_data_amortized_usd",
    "always_on_infrastructure_usd",
    "operator_time_usd",
)


def validate_fully_loaded_economics_contract() -> list[str]:
    errors: list[str] = []
    if len(DIRECT_COST_COMPONENTS) != len(set(DIRECT_COST_COMPONENTS)):
        errors.append("direct cost component keys must be unique")
    if len(RECURRING_COST_COMPONENTS) != len(set(RECURRING_COST_COMPONENTS)):
        errors.append("recurring cost component keys must be unique")
    if SUPPORTED_FULLY_LOADED_ECONOMICS_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    return errors


VALIDATION_ERRORS = validate_fully_loaded_economics_contract()


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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


def _as_non_negative_int(value: object, *, field_name: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field_name}: must be non-negative")
    return parsed


@unique
class FullyLoadedEconomicsStatus(str, Enum):
    PASS = "pass"
    INVALID = "invalid"


@unique
class EconomicsLayer(str, Enum):
    GROSS = "gross"
    NET_DIRECT = "net_direct"
    NET_FULLY_LOADED = "net_fully_loaded"


@dataclass(frozen=True)
class DirectCostBreakdown:
    broker_commissions_and_fees_usd: float
    exchange_and_regulatory_fees_usd: float
    slippage_usd: float

    def total_usd(self) -> float:
        return (
            self.broker_commissions_and_fees_usd
            + self.exchange_and_regulatory_fees_usd
            + self.slippage_usd
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DirectCostBreakdown":
        return cls(
            broker_commissions_and_fees_usd=_as_non_negative_float(
                payload["broker_commissions_and_fees_usd"],
                field_name="broker_commissions_and_fees_usd",
            ),
            exchange_and_regulatory_fees_usd=_as_non_negative_float(
                payload["exchange_and_regulatory_fees_usd"],
                field_name="exchange_and_regulatory_fees_usd",
            ),
            slippage_usd=_as_non_negative_float(
                payload["slippage_usd"],
                field_name="slippage_usd",
            ),
        )


@dataclass(frozen=True)
class ExecutionProfileEconomics:
    profile_id: str
    session_bucket_id: str
    gross_pnl_usd: float
    direct_costs: DirectCostBreakdown
    trade_count: int
    active_session_ids: tuple[str, ...] = ()

    def net_direct_pnl_usd(self) -> float:
        return self.gross_pnl_usd - self.direct_costs.total_usd()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["direct_costs"] = self.direct_costs.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionProfileEconomics":
        return cls(
            profile_id=str(payload["profile_id"]),
            session_bucket_id=str(payload["session_bucket_id"]),
            gross_pnl_usd=float(payload["gross_pnl_usd"]),
            direct_costs=DirectCostBreakdown.from_dict(
                dict(payload.get("direct_costs", {}))
            ),
            trade_count=_as_non_negative_int(payload["trade_count"], field_name="trade_count"),
            active_session_ids=tuple(
                str(item) for item in payload.get("active_session_ids", ())
            ),
        )


@dataclass(frozen=True)
class RecurringCostAllocation:
    allocation_basis: str
    allocation_window_days: int
    live_market_data_usd: float
    historical_data_amortized_usd: float
    always_on_infrastructure_usd: float
    operator_time_hours: float
    operator_hourly_rate_usd: float

    def operator_time_usd(self) -> float:
        return self.operator_time_hours * self.operator_hourly_rate_usd

    def component_breakdown(self) -> dict[str, float]:
        return {
            "live_market_data_usd": self.live_market_data_usd,
            "historical_data_amortized_usd": self.historical_data_amortized_usd,
            "always_on_infrastructure_usd": self.always_on_infrastructure_usd,
            "operator_time_usd": self.operator_time_usd(),
        }

    def total_usd(self) -> float:
        return sum(self.component_breakdown().values())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RecurringCostAllocation":
        return cls(
            allocation_basis=str(payload["allocation_basis"]),
            allocation_window_days=_as_non_negative_int(
                payload["allocation_window_days"],
                field_name="allocation_window_days",
            ),
            live_market_data_usd=_as_non_negative_float(
                payload["live_market_data_usd"],
                field_name="live_market_data_usd",
            ),
            historical_data_amortized_usd=_as_non_negative_float(
                payload["historical_data_amortized_usd"],
                field_name="historical_data_amortized_usd",
            ),
            always_on_infrastructure_usd=_as_non_negative_float(
                payload["always_on_infrastructure_usd"],
                field_name="always_on_infrastructure_usd",
            ),
            operator_time_hours=_as_non_negative_float(
                payload["operator_time_hours"],
                field_name="operator_time_hours",
            ),
            operator_hourly_rate_usd=_as_non_negative_float(
                payload["operator_hourly_rate_usd"],
                field_name="operator_hourly_rate_usd",
            ),
        )


@dataclass(frozen=True)
class FullyLoadedEconomicsRequest:
    evaluation_id: str
    candidate_id: str
    strategy_family_id: str
    liquidity_materially_heterogeneous: bool
    execution_profiles: tuple[ExecutionProfileEconomics, ...]
    recurring_cost_allocation: RecurringCostAllocation
    schema_version: int = SUPPORTED_FULLY_LOADED_ECONOMICS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_profiles"] = [profile.to_dict() for profile in self.execution_profiles]
        payload["recurring_cost_allocation"] = self.recurring_cost_allocation.to_dict()
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FullyLoadedEconomicsRequest":
        return cls(
            evaluation_id=str(payload["evaluation_id"]),
            candidate_id=str(payload["candidate_id"]),
            strategy_family_id=str(payload["strategy_family_id"]),
            liquidity_materially_heterogeneous=bool(
                payload["liquidity_materially_heterogeneous"]
            ),
            execution_profiles=tuple(
                ExecutionProfileEconomics.from_dict(dict(item))
                for item in payload.get("execution_profiles", ())
            ),
            recurring_cost_allocation=RecurringCostAllocation.from_dict(
                dict(payload["recurring_cost_allocation"])
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_FULLY_LOADED_ECONOMICS_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FullyLoadedEconomicsRequest":
        return cls.from_dict(_decode_json_object(payload, label="fully_loaded_economics"))


@dataclass(frozen=True)
class EconomicsLayerSummary:
    layer: str
    pnl_usd: float
    total_cost_usd: float
    cost_components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EconomicsLayerSummary":
        return cls(
            layer=str(payload["layer"]),
            pnl_usd=float(payload["pnl_usd"]),
            total_cost_usd=float(payload["total_cost_usd"]),
            cost_components={
                str(key): float(value)
                for key, value in dict(payload.get("cost_components", {})).items()
            },
        )


@dataclass(frozen=True)
class FullyLoadedEconomicsReport:
    evaluation_id: str
    candidate_id: str
    strategy_family_id: str
    status: str
    reason_code: str | None
    generated_at_utc: str
    liquidity_conditioning_used: bool
    gross_pnl_usd: float
    net_direct_pnl_usd: float
    net_fully_loaded_pnl_usd: float
    direct_cost_breakdown: dict[str, float]
    recurring_cost_breakdown: dict[str, float]
    layer_summaries: tuple[EconomicsLayerSummary, ...]
    execution_profile_breakdowns: tuple[dict[str, Any], ...]
    diagnostic: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["layer_summaries"] = [summary.to_dict() for summary in self.layer_summaries]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FullyLoadedEconomicsReport":
        return cls(
            evaluation_id=str(payload["evaluation_id"]),
            candidate_id=str(payload["candidate_id"]),
            strategy_family_id=str(payload["strategy_family_id"]),
            status=str(payload["status"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            generated_at_utc=str(payload["generated_at_utc"]),
            liquidity_conditioning_used=bool(payload["liquidity_conditioning_used"]),
            gross_pnl_usd=float(payload["gross_pnl_usd"]),
            net_direct_pnl_usd=float(payload["net_direct_pnl_usd"]),
            net_fully_loaded_pnl_usd=float(payload["net_fully_loaded_pnl_usd"]),
            direct_cost_breakdown={
                str(key): float(value)
                for key, value in dict(payload.get("direct_cost_breakdown", {})).items()
            },
            recurring_cost_breakdown={
                str(key): float(value)
                for key, value in dict(payload.get("recurring_cost_breakdown", {})).items()
            },
            layer_summaries=tuple(
                EconomicsLayerSummary.from_dict(dict(item))
                for item in payload.get("layer_summaries", ())
            ),
            execution_profile_breakdowns=tuple(
                dict(item) for item in payload.get("execution_profile_breakdowns", ())
            ),
            diagnostic=dict(payload.get("diagnostic", {})),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FullyLoadedEconomicsReport":
        return cls.from_dict(
            _decode_json_object(payload, label="fully_loaded_economics_report")
        )


def _invalid_report(
    request: FullyLoadedEconomicsRequest,
    *,
    reason_code: str,
    diagnostic: dict[str, Any],
) -> FullyLoadedEconomicsReport:
    return FullyLoadedEconomicsReport(
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        strategy_family_id=request.strategy_family_id,
        status=FullyLoadedEconomicsStatus.INVALID.value,
        reason_code=reason_code,
        generated_at_utc=_utc_now_iso(),
        liquidity_conditioning_used=False,
        gross_pnl_usd=0.0,
        net_direct_pnl_usd=0.0,
        net_fully_loaded_pnl_usd=0.0,
        direct_cost_breakdown={component: 0.0 for component in DIRECT_COST_COMPONENTS},
        recurring_cost_breakdown={component: 0.0 for component in RECURRING_COST_COMPONENTS},
        layer_summaries=(),
        execution_profile_breakdowns=(),
        diagnostic=diagnostic,
    )


def evaluate_fully_loaded_economics(
    request: FullyLoadedEconomicsRequest,
) -> FullyLoadedEconomicsReport:
    if request.schema_version != SUPPORTED_FULLY_LOADED_ECONOMICS_SCHEMA_VERSION:
        return _invalid_report(
            request,
            reason_code="UNSUPPORTED_SCHEMA_VERSION",
            diagnostic={"schema_version": request.schema_version},
        )

    if not request.execution_profiles:
        return _invalid_report(
            request,
            reason_code="EXECUTION_PROFILE_REQUIRED",
            diagnostic={"execution_profile_count": 0},
        )

    profile_ids = tuple(profile.profile_id for profile in request.execution_profiles)
    if len(profile_ids) != len(set(profile_ids)):
        return _invalid_report(
            request,
            reason_code="DUPLICATE_EXECUTION_PROFILE_ID",
            diagnostic={"execution_profile_ids": profile_ids},
        )

    session_bucket_ids = {profile.session_bucket_id for profile in request.execution_profiles}
    liquidity_conditioning_used = len(session_bucket_ids) > 1
    if request.liquidity_materially_heterogeneous and len(session_bucket_ids) < 2:
        return _invalid_report(
            request,
            reason_code="EXECUTION_PROFILE_CONDITIONING_REQUIRED",
            diagnostic={
                "execution_profile_ids": profile_ids,
                "session_bucket_ids": tuple(sorted(session_bucket_ids)),
            },
        )

    gross_pnl_usd = sum(profile.gross_pnl_usd for profile in request.execution_profiles)
    direct_cost_breakdown = {
        "broker_commissions_and_fees_usd": sum(
            profile.direct_costs.broker_commissions_and_fees_usd
            for profile in request.execution_profiles
        ),
        "exchange_and_regulatory_fees_usd": sum(
            profile.direct_costs.exchange_and_regulatory_fees_usd
            for profile in request.execution_profiles
        ),
        "slippage_usd": sum(
            profile.direct_costs.slippage_usd for profile in request.execution_profiles
        ),
    }
    net_direct_pnl_usd = gross_pnl_usd - sum(direct_cost_breakdown.values())
    recurring_cost_breakdown = request.recurring_cost_allocation.component_breakdown()
    net_fully_loaded_pnl_usd = net_direct_pnl_usd - sum(recurring_cost_breakdown.values())

    layer_summaries = (
        EconomicsLayerSummary(
            layer=EconomicsLayer.GROSS.value,
            pnl_usd=gross_pnl_usd,
            total_cost_usd=0.0,
            cost_components={},
        ),
        EconomicsLayerSummary(
            layer=EconomicsLayer.NET_DIRECT.value,
            pnl_usd=net_direct_pnl_usd,
            total_cost_usd=sum(direct_cost_breakdown.values()),
            cost_components=direct_cost_breakdown,
        ),
        EconomicsLayerSummary(
            layer=EconomicsLayer.NET_FULLY_LOADED.value,
            pnl_usd=net_fully_loaded_pnl_usd,
            total_cost_usd=sum(direct_cost_breakdown.values())
            + sum(recurring_cost_breakdown.values()),
            cost_components={**direct_cost_breakdown, **recurring_cost_breakdown},
        ),
    )
    execution_profile_breakdowns = tuple(
        {
            "profile_id": profile.profile_id,
            "session_bucket_id": profile.session_bucket_id,
            "active_session_ids": list(profile.active_session_ids),
            "trade_count": profile.trade_count,
            "gross_pnl_usd": profile.gross_pnl_usd,
            "net_direct_pnl_usd": profile.net_direct_pnl_usd(),
            "direct_cost_breakdown": profile.direct_costs.to_dict(),
        }
        for profile in request.execution_profiles
    )
    diagnostic = {
        "execution_profile_ids": list(profile_ids),
        "session_bucket_ids": sorted(session_bucket_ids),
        "execution_profile_count": len(request.execution_profiles),
        "liquidity_materially_heterogeneous": request.liquidity_materially_heterogeneous,
        "liquidity_conditioning_used": liquidity_conditioning_used,
        "allocation_basis": request.recurring_cost_allocation.allocation_basis,
        "allocation_window_days": request.recurring_cost_allocation.allocation_window_days,
        "operator_time_hours": request.recurring_cost_allocation.operator_time_hours,
        "operator_hourly_rate_usd": request.recurring_cost_allocation.operator_hourly_rate_usd,
    }
    return FullyLoadedEconomicsReport(
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        strategy_family_id=request.strategy_family_id,
        status=FullyLoadedEconomicsStatus.PASS.value,
        reason_code=None,
        generated_at_utc=_utc_now_iso(),
        liquidity_conditioning_used=liquidity_conditioning_used,
        gross_pnl_usd=gross_pnl_usd,
        net_direct_pnl_usd=net_direct_pnl_usd,
        net_fully_loaded_pnl_usd=net_fully_loaded_pnl_usd,
        direct_cost_breakdown=direct_cost_breakdown,
        recurring_cost_breakdown=recurring_cost_breakdown,
        layer_summaries=layer_summaries,
        execution_profile_breakdowns=execution_profile_breakdowns,
        diagnostic=diagnostic,
    )
