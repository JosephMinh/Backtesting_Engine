"""Canonical product and account profile schemas for the first live lane."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from shared.policy.clock_discipline import DEFAULT_TIME_DISCIPLINE_POLICY
from shared.policy.posture import APPROVED_POSTURE


class ProductLane(str, Enum):
    RESEARCH = "research"
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"
    LIVE = "live"


class BindingStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    STALE = "stale"
    INCOMPATIBLE = "incompatible"


class OperatingPosture(str, Enum):
    INTRADAY_FLAT_DEFAULT = "intraday_flat_default"
    OVERNIGHT_STRICT = "overnight_strict"


@dataclass(frozen=True)
class ContractSpecification:
    symbol: str
    exchange: str
    contract_size_oz: int
    minimum_price_fluctuation_usd_per_oz: float
    currency: str
    settlement_type: str
    last_trade_rule: str

    @property
    def tick_value_usd(self) -> float:
        return self.contract_size_oz * self.minimum_price_fluctuation_usd_per_oz


@dataclass(frozen=True)
class SessionPolicy:
    calendar_id: str
    exchange_timezone: str
    exchange_calendar_source: str
    maintenance_windows: tuple[str, ...]
    event_window_source: str


@dataclass(frozen=True)
class DeliveryFence:
    delivery_type: str
    last_trade_constraint: str
    delivery_fence_rule: str
    reviewed_roll_required: bool


@dataclass(frozen=True)
class RollPolicyInputs:
    roll_calendar_source: str
    liquidity_inputs: tuple[str, ...]
    last_trade_fence_input: str
    delivery_fence_input: str


@dataclass(frozen=True)
class BrokerCapabilityAssumptions:
    broker: str
    market_data_source: str
    contract_conformance_required: bool
    flatten_supported: bool
    modify_cancel_supported: bool
    session_definition_required: bool


@dataclass(frozen=True)
class BrokerContractInvariant:
    symbol: str
    exchange: str
    currency: str
    contract_size_oz: int
    minimum_price_fluctuation_usd_per_oz: float
    settlement_type: str
    session_calendar_id: str


@dataclass(frozen=True)
class ProductProfile:
    profile_id: str
    title: str
    plan_section: str
    supported_lanes: tuple[ProductLane, ...]
    contract_specification: ContractSpecification
    session_policy: SessionPolicy
    delivery_fence: DeliveryFence
    roll_policy_inputs: RollPolicyInputs
    approved_data_profile_releases: tuple[str, ...]
    stale_data_profile_releases: tuple[str, ...]
    broker_capability_assumptions: BrokerCapabilityAssumptions
    broker_contract_invariants: BrokerContractInvariant


@dataclass(frozen=True)
class AccountRiskProfile:
    profile_id: str
    title: str
    plan_section: str
    broker: str
    approved_starting_equity_usd: int
    approved_symbols: tuple[str, ...]
    approved_starting_size_by_symbol: dict[str, int]
    max_position_size_by_symbol: dict[str, int]
    max_initial_margin_fraction: float
    max_maintenance_margin_fraction: float
    daily_loss_lockout_fraction: float
    max_drawdown_fraction: float
    overnight_gap_stress_fraction: float
    allowed_operating_postures: tuple[OperatingPosture, ...]
    default_operating_posture: OperatingPosture
    overnight_only_with_strict_class: bool


@dataclass(frozen=True)
class BrokerContractDescriptor:
    symbol: str
    exchange: str
    currency: str
    contract_size_oz: int
    minimum_price_fluctuation_usd_per_oz: float
    settlement_type: str
    session_calendar_id: str


@dataclass(frozen=True)
class ProfileBindingRequest:
    case_id: str
    product_profile_id: str
    account_profile_id: str
    requested_lane: ProductLane
    requested_symbol: str
    requested_broker: str
    requested_data_profile_release_id: str
    requested_contract_count: int
    requested_initial_margin_fraction: float
    requested_maintenance_margin_fraction: float
    requested_operating_posture: OperatingPosture
    overnight_requested: bool
    broker_contract_descriptor: BrokerContractDescriptor


@dataclass(frozen=True)
class ProfileBindingReport:
    case_id: str
    status: str
    reason_code: str
    product_profile_id: str
    account_profile_id: str
    differences: dict[str, dict[str, Any]]
    remediation: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


_SESSION_POLICY = SessionPolicy(
    calendar_id="comex_metals_globex_v1",
    exchange_timezone="America/Chicago",
    exchange_calendar_source=DEFAULT_TIME_DISCIPLINE_POLICY.exchange_calendar_source,
    maintenance_windows=("daily_16:00_to_17:00_ct",),
    event_window_source=DEFAULT_TIME_DISCIPLINE_POLICY.session_boundary_source,
)


PRODUCT_PROFILES: tuple[ProductProfile, ...] = (
    ProductProfile(
        profile_id="mgc_comex_v1",
        title="MGC COMEX micro gold profile",
        plan_section="4.1",
        supported_lanes=(ProductLane.RESEARCH,),
        contract_specification=ContractSpecification(
            symbol="MGC",
            exchange="COMEX",
            contract_size_oz=10,
            minimum_price_fluctuation_usd_per_oz=0.10,
            currency="USD",
            settlement_type="deliverable",
            last_trade_rule="third_last_business_day_of_delivery_month",
        ),
        session_policy=_SESSION_POLICY,
        delivery_fence=DeliveryFence(
            delivery_type="deliverable",
            last_trade_constraint="terminate_before_delivery_month_last_trade_boundary",
            delivery_fence_rule="block_tradeability_when_delivery_window_is_active",
            reviewed_roll_required=True,
        ),
        roll_policy_inputs=RollPolicyInputs(
            roll_calendar_source="resolved_context_bundle_roll_windows",
            liquidity_inputs=(
                "front_vs_next_volume",
                "front_vs_next_open_interest",
                "delivery_window_distance",
            ),
            last_trade_fence_input="days_to_last_trade",
            delivery_fence_input="delivery_window_status",
        ),
        approved_data_profile_releases=("databento_mgc_comex_trades_1m_v1",),
        stale_data_profile_releases=("databento_mgc_comex_trades_1m_v0",),
        broker_capability_assumptions=BrokerCapabilityAssumptions(
            broker=APPROVED_POSTURE.broker,
            market_data_source="databento_historical_and_ibkr_runtime",
            contract_conformance_required=True,
            flatten_supported=True,
            modify_cancel_supported=True,
            session_definition_required=True,
        ),
        broker_contract_invariants=BrokerContractInvariant(
            symbol="MGC",
            exchange="COMEX",
            currency="USD",
            contract_size_oz=10,
            minimum_price_fluctuation_usd_per_oz=0.10,
            settlement_type="deliverable",
            session_calendar_id=_SESSION_POLICY.calendar_id,
        ),
    ),
    ProductProfile(
        profile_id="oneoz_comex_v1",
        title="1OZ COMEX one-ounce gold profile",
        plan_section="4.1",
        supported_lanes=(
            ProductLane.RESEARCH,
            ProductLane.PAPER,
            ProductLane.SHADOW_LIVE,
            ProductLane.LIVE,
        ),
        contract_specification=ContractSpecification(
            symbol=APPROVED_POSTURE.execution_symbol,
            exchange="COMEX",
            contract_size_oz=1,
            minimum_price_fluctuation_usd_per_oz=0.25,
            currency="USD",
            settlement_type="cash_settled",
            last_trade_rule="third_last_business_day_of_month_prior_to_contract_month",
        ),
        session_policy=_SESSION_POLICY,
        delivery_fence=DeliveryFence(
            delivery_type="cash_settled",
            last_trade_constraint="terminate_before_cash_settlement_last_trade_boundary",
            delivery_fence_rule="block_tradeability_when_resolved_context_marks_expiring_contract",
            reviewed_roll_required=True,
        ),
        roll_policy_inputs=RollPolicyInputs(
            roll_calendar_source="resolved_context_bundle_roll_windows",
            liquidity_inputs=(
                "front_vs_next_volume",
                "front_vs_next_open_interest",
                "cash_settlement_month_boundary",
            ),
            last_trade_fence_input="days_to_last_trade",
            delivery_fence_input="contract_month_roll_state",
        ),
        approved_data_profile_releases=("ibkr_1oz_comex_bars_1m_v1",),
        stale_data_profile_releases=("ibkr_1oz_comex_bars_1m_v0",),
        broker_capability_assumptions=BrokerCapabilityAssumptions(
            broker=APPROVED_POSTURE.broker,
            market_data_source="ibkr_runtime",
            contract_conformance_required=True,
            flatten_supported=True,
            modify_cancel_supported=True,
            session_definition_required=True,
        ),
        broker_contract_invariants=BrokerContractInvariant(
            symbol=APPROVED_POSTURE.execution_symbol,
            exchange="COMEX",
            currency="USD",
            contract_size_oz=1,
            minimum_price_fluctuation_usd_per_oz=0.25,
            settlement_type="cash_settled",
            session_calendar_id=_SESSION_POLICY.calendar_id,
        ),
    ),
)


ACCOUNT_RISK_PROFILES: tuple[AccountRiskProfile, ...] = (
    AccountRiskProfile(
        profile_id="solo_small_gold_ibkr_5000_v1",
        title="Solo small-account gold profile on IBKR",
        plan_section="4.1",
        broker=APPROVED_POSTURE.broker,
        approved_starting_equity_usd=APPROVED_POSTURE.max_account_value_usd,
        approved_symbols=(APPROVED_POSTURE.execution_symbol,),
        approved_starting_size_by_symbol={APPROVED_POSTURE.execution_symbol: 1},
        max_position_size_by_symbol={APPROVED_POSTURE.execution_symbol: 1},
        max_initial_margin_fraction=0.25,
        max_maintenance_margin_fraction=0.35,
        daily_loss_lockout_fraction=0.025,
        max_drawdown_fraction=0.15,
        overnight_gap_stress_fraction=0.05,
        allowed_operating_postures=(
            OperatingPosture.INTRADAY_FLAT_DEFAULT,
            OperatingPosture.OVERNIGHT_STRICT,
        ),
        default_operating_posture=OperatingPosture.INTRADAY_FLAT_DEFAULT,
        overnight_only_with_strict_class=True,
    ),
)


def product_profiles_by_id() -> dict[str, ProductProfile]:
    return {profile.profile_id: profile for profile in PRODUCT_PROFILES}


def account_risk_profiles_by_id() -> dict[str, AccountRiskProfile]:
    return {profile.profile_id: profile for profile in ACCOUNT_RISK_PROFILES}


def validate_profile_catalogs() -> list[str]:
    errors: list[str] = []

    product_ids = [profile.profile_id for profile in PRODUCT_PROFILES]
    account_ids = [profile.profile_id for profile in ACCOUNT_RISK_PROFILES]
    if len(product_ids) != len(set(product_ids)):
        errors.append("product profile identifiers must be unique")
    if len(account_ids) != len(set(account_ids)):
        errors.append("account risk profile identifiers must be unique")

    for profile in PRODUCT_PROFILES:
        if not profile.supported_lanes:
            errors.append(f"{profile.profile_id}: supported_lanes must be explicit")
        if not profile.approved_data_profile_releases:
            errors.append(f"{profile.profile_id}: approved_data_profile_releases are required")
        if set(profile.approved_data_profile_releases) & set(profile.stale_data_profile_releases):
            errors.append(
                f"{profile.profile_id}: approved and stale data-profile release ids must not overlap"
            )
        if profile.session_policy.exchange_calendar_source != "compiled_exchange_calendars":
            errors.append(
                f"{profile.profile_id}: exchange-local times must come from compiled calendars"
            )
        if profile.contract_specification.tick_value_usd <= 0:
            errors.append(f"{profile.profile_id}: tick economics must be positive")

    for profile in ACCOUNT_RISK_PROFILES:
        if profile.approved_starting_equity_usd <= 0:
            errors.append(f"{profile.profile_id}: approved_starting_equity_usd must be positive")
        if not profile.approved_symbols:
            errors.append(f"{profile.profile_id}: approved_symbols must not be empty")
        if profile.max_initial_margin_fraction <= 0 or profile.max_initial_margin_fraction >= 1:
            errors.append(f"{profile.profile_id}: max_initial_margin_fraction must be within (0, 1)")
        if (
            profile.max_maintenance_margin_fraction <= profile.max_initial_margin_fraction
            or profile.max_maintenance_margin_fraction >= 1
        ):
            errors.append(
                f"{profile.profile_id}: max_maintenance_margin_fraction must exceed initial and stay below 1"
            )
        if profile.daily_loss_lockout_fraction <= 0 or profile.daily_loss_lockout_fraction >= 1:
            errors.append(f"{profile.profile_id}: daily_loss_lockout_fraction must be within (0, 1)")
        if profile.max_drawdown_fraction <= 0 or profile.max_drawdown_fraction >= 1:
            errors.append(f"{profile.profile_id}: max_drawdown_fraction must be within (0, 1)")
        if profile.overnight_gap_stress_fraction <= 0 or profile.overnight_gap_stress_fraction >= 1:
            errors.append(f"{profile.profile_id}: overnight_gap_stress_fraction must be within (0, 1)")
        if profile.default_operating_posture not in profile.allowed_operating_postures:
            errors.append(
                f"{profile.profile_id}: default_operating_posture must be an allowed_operating_posture"
            )

    product_symbol_set = {profile.contract_specification.symbol for profile in PRODUCT_PROFILES}
    for profile in ACCOUNT_RISK_PROFILES:
        unknown_symbols = set(profile.approved_symbols) - product_symbol_set
        if unknown_symbols:
            errors.append(
                f"{profile.profile_id}: approved_symbols reference unknown product symbols {sorted(unknown_symbols)}"
            )

    initial_account = account_risk_profiles_by_id().get("solo_small_gold_ibkr_5000_v1")
    if initial_account is not None:
        if initial_account.broker != APPROVED_POSTURE.broker:
            errors.append("solo_small_gold_ibkr_5000_v1: broker must match approved posture")
        if initial_account.approved_starting_equity_usd != APPROVED_POSTURE.max_account_value_usd:
            errors.append(
                "solo_small_gold_ibkr_5000_v1: approved_starting_equity_usd must match approved posture"
            )
        if initial_account.max_position_size_by_symbol.get(APPROVED_POSTURE.execution_symbol) != APPROVED_POSTURE.max_live_contracts:
            errors.append(
                "solo_small_gold_ibkr_5000_v1: max position size must match one-contract posture"
            )

    return errors


def validate_profile_binding(request: ProfileBindingRequest) -> ProfileBindingReport:
    products = product_profiles_by_id()
    accounts = account_risk_profiles_by_id()

    if request.product_profile_id not in products:
        return ProfileBindingReport(
            case_id=request.case_id,
            status=BindingStatus.INVALID.value,
            reason_code="PROFILE_BINDING_UNKNOWN_PRODUCT_PROFILE",
            product_profile_id=request.product_profile_id,
            account_profile_id=request.account_profile_id,
            differences={"product_profile_id": {"actual": request.product_profile_id, "expected": sorted(products)}},
            remediation="Bind the request to a known product_profile identifier.",
            explanation="The requested product profile does not exist in the canonical catalog.",
        )

    if request.account_profile_id not in accounts:
        return ProfileBindingReport(
            case_id=request.case_id,
            status=BindingStatus.INVALID.value,
            reason_code="PROFILE_BINDING_UNKNOWN_ACCOUNT_PROFILE",
            product_profile_id=request.product_profile_id,
            account_profile_id=request.account_profile_id,
            differences={"account_profile_id": {"actual": request.account_profile_id, "expected": sorted(accounts)}},
            remediation="Bind the request to a known account_risk_profile identifier.",
            explanation="The requested account profile does not exist in the canonical catalog.",
        )

    product = products[request.product_profile_id]
    account = accounts[request.account_profile_id]

    if request.requested_data_profile_release_id in product.stale_data_profile_releases:
        return ProfileBindingReport(
            case_id=request.case_id,
            status=BindingStatus.STALE.value,
            reason_code="PROFILE_BINDING_STALE_DATA_PROFILE_RELEASE",
            product_profile_id=product.profile_id,
            account_profile_id=account.profile_id,
            differences={
                "requested_data_profile_release_id": {
                    "actual": request.requested_data_profile_release_id,
                    "expected": product.approved_data_profile_releases,
                }
            },
            remediation="Use an approved current data_profile_release before promotion or readiness.",
            explanation="The binding references a stale data-profile release that is no longer admissible.",
        )

    differences: dict[str, dict[str, Any]] = {}

    if request.requested_data_profile_release_id not in product.approved_data_profile_releases:
        differences["requested_data_profile_release_id"] = {
            "actual": request.requested_data_profile_release_id,
            "expected": product.approved_data_profile_releases,
        }

    if request.requested_lane not in product.supported_lanes:
        differences["requested_lane"] = {
            "actual": request.requested_lane.value,
            "expected": tuple(lane.value for lane in product.supported_lanes),
        }

    if request.requested_symbol != product.contract_specification.symbol:
        differences["requested_symbol"] = {
            "actual": request.requested_symbol,
            "expected": product.contract_specification.symbol,
        }

    if request.requested_broker != product.broker_capability_assumptions.broker:
        differences["requested_broker"] = {
            "actual": request.requested_broker,
            "expected": product.broker_capability_assumptions.broker,
        }

    if request.requested_symbol not in account.approved_symbols:
        differences["approved_symbols"] = {
            "actual": request.requested_symbol,
            "expected": account.approved_symbols,
        }

    approved_starting_size = account.approved_starting_size_by_symbol.get(request.requested_symbol)
    max_position_size = account.max_position_size_by_symbol.get(request.requested_symbol)
    if approved_starting_size is None or max_position_size is None:
        differences["position_sizing"] = {
            "actual": request.requested_symbol,
            "expected": sorted(account.max_position_size_by_symbol),
        }
    elif request.requested_contract_count > max_position_size or request.requested_contract_count < 1:
        differences["requested_contract_count"] = {
            "actual": request.requested_contract_count,
            "expected": {"minimum": 1, "approved_starting_size": approved_starting_size, "maximum": max_position_size},
        }

    if (
        request.requested_initial_margin_fraction <= 0
        or request.requested_initial_margin_fraction >= 1
    ):
        differences["requested_initial_margin_fraction"] = {
            "actual": request.requested_initial_margin_fraction,
            "expected": {"minimum_exclusive": 0, "maximum_exclusive": 1},
        }
    elif request.requested_initial_margin_fraction > account.max_initial_margin_fraction:
        differences["requested_initial_margin_fraction"] = {
            "actual": request.requested_initial_margin_fraction,
            "expected": account.max_initial_margin_fraction,
        }

    if (
        request.requested_maintenance_margin_fraction <= 0
        or request.requested_maintenance_margin_fraction >= 1
    ):
        differences["requested_maintenance_margin_fraction"] = {
            "actual": request.requested_maintenance_margin_fraction,
            "expected": {"minimum_exclusive": 0, "maximum_exclusive": 1},
        }
    elif request.requested_maintenance_margin_fraction > account.max_maintenance_margin_fraction:
        differences["requested_maintenance_margin_fraction"] = {
            "actual": request.requested_maintenance_margin_fraction,
            "expected": account.max_maintenance_margin_fraction,
        }
    elif (
        request.requested_maintenance_margin_fraction
        <= request.requested_initial_margin_fraction
    ):
        differences["requested_maintenance_margin_fraction"] = {
            "actual": request.requested_maintenance_margin_fraction,
            "expected": {
                "greater_than": request.requested_initial_margin_fraction,
                "maximum": account.max_maintenance_margin_fraction,
            },
        }

    if request.requested_operating_posture not in account.allowed_operating_postures:
        differences["requested_operating_posture"] = {
            "actual": request.requested_operating_posture.value,
            "expected": tuple(posture.value for posture in account.allowed_operating_postures),
        }

    if (
        request.overnight_requested
        and account.overnight_only_with_strict_class
        and request.requested_operating_posture != OperatingPosture.OVERNIGHT_STRICT
    ):
        differences["overnight_requested"] = {
            "actual": request.requested_operating_posture.value,
            "expected": OperatingPosture.OVERNIGHT_STRICT.value,
        }

    descriptor = request.broker_contract_descriptor
    invariants = product.broker_contract_invariants
    if descriptor.symbol != invariants.symbol:
        differences["broker_contract.symbol"] = {"actual": descriptor.symbol, "expected": invariants.symbol}
    if descriptor.exchange != invariants.exchange:
        differences["broker_contract.exchange"] = {"actual": descriptor.exchange, "expected": invariants.exchange}
    if descriptor.currency != invariants.currency:
        differences["broker_contract.currency"] = {"actual": descriptor.currency, "expected": invariants.currency}
    if descriptor.contract_size_oz != invariants.contract_size_oz:
        differences["broker_contract.contract_size_oz"] = {
            "actual": descriptor.contract_size_oz,
            "expected": invariants.contract_size_oz,
        }
    if (
        descriptor.minimum_price_fluctuation_usd_per_oz
        != invariants.minimum_price_fluctuation_usd_per_oz
    ):
        differences["broker_contract.minimum_price_fluctuation_usd_per_oz"] = {
            "actual": descriptor.minimum_price_fluctuation_usd_per_oz,
            "expected": invariants.minimum_price_fluctuation_usd_per_oz,
        }
    if descriptor.settlement_type != invariants.settlement_type:
        differences["broker_contract.settlement_type"] = {
            "actual": descriptor.settlement_type,
            "expected": invariants.settlement_type,
        }
    if descriptor.session_calendar_id != invariants.session_calendar_id:
        differences["broker_contract.session_calendar_id"] = {
            "actual": descriptor.session_calendar_id,
            "expected": invariants.session_calendar_id,
        }

    if differences:
        return ProfileBindingReport(
            case_id=request.case_id,
            status=BindingStatus.INCOMPATIBLE.value,
            reason_code="PROFILE_BINDING_INCOMPATIBLE",
            product_profile_id=product.profile_id,
            account_profile_id=account.profile_id,
            differences=differences,
            remediation="Align symbol, account posture, broker descriptor, and data-profile binding with the canonical profiles.",
            explanation="The binding is outside policy because one or more canonical product/account assumptions do not match.",
        )

    return ProfileBindingReport(
        case_id=request.case_id,
        status=BindingStatus.PASS.value,
        reason_code="PROFILE_BINDING_ALLOWED",
        product_profile_id=product.profile_id,
        account_profile_id=account.profile_id,
        differences={},
        remediation="No remediation required.",
        explanation="The product profile, account profile, broker contract descriptor, and data-profile binding are all admissible.",
    )


VALIDATION_ERRORS = validate_profile_catalogs()
