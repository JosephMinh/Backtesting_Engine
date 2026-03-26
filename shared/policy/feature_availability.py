"""Feature-availability contracts and delivery-aware roll-policy gates."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.product_profiles import product_profiles_by_id

SUPPORTED_FEATURE_CONTRACT_SCHEMA_VERSION = 1


@unique
class PolicyGateStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"
    INCOMPATIBLE = "incompatible"


@unique
class DecisionLatencyClass(str, Enum):
    INTRA_BAR = "intra_bar"
    BAR_CLOSE = "bar_close"
    SESSION_CLOSE = "session_close"
    NEXT_SESSION = "next_session"


@unique
class FallbackBehavior(str, Enum):
    BLOCK_SURFACE = "block_surface"
    SKIP_FEATURE_BLOCK = "skip_feature_block"
    HOLD_LAST_VALUE = "hold_last_value"
    USE_SENTINEL = "use_sentinel"


@unique
class FeatureDecisionSurface(str, Enum):
    EXPERIMENT_BUILD = "experiment_build"
    REPLAY_CERTIFICATION = "replay_certification"
    PAPER_ACTIVATION = "paper_activation"
    SHADOW_LIVE_ACTIVATION = "shadow_live_activation"
    LIVE_ACTIVATION = "live_activation"


@unique
class RollPolicySurface(str, Enum):
    ANALYTICS = "analytics"
    BACKTEST = "backtest"
    REPLAY = "replay"
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"
    LIVE = "live"


@unique
class ContractSeriesMode(str, Enum):
    ACTUAL_SEGMENTS = "actual_segments"
    CONTINUOUS_SERIES = "continuous_series"


@unique
class ContinuousSeriesUsage(str, Enum):
    NONE = "none"
    ANALYTICS_ONLY = "analytics_only"
    VISUALIZATION_ONLY = "visualization_only"
    EXECUTION = "execution"


@unique
class BacktestEvaluationMode(str, Enum):
    SEGMENT_BASED = "segment_based"
    CONTINUOUS_SERIES = "continuous_series"


@unique
class RollTransitionAction(str, Enum):
    HOLD_CURRENT_SEGMENT = "hold_current_segment"
    ROLL_TO_NEXT_SEGMENT = "roll_to_next_segment"
    BLOCKED_BY_DELIVERY_FENCE = "blocked_by_delivery_fence"


LATENCY_ORDER = {
    DecisionLatencyClass.INTRA_BAR: 0,
    DecisionLatencyClass.BAR_CLOSE: 1,
    DecisionLatencyClass.SESSION_CLOSE: 2,
    DecisionLatencyClass.NEXT_SESSION: 3,
}


@dataclass(frozen=True)
class FeatureAvailabilityContract:
    feature_block_id: str
    source_artifact_ids: tuple[str, ...]
    source_fields: tuple[str, ...]
    value_timestamp_rule: str
    available_at_rule: str
    requires_bar_close: bool
    requires_session_close: bool
    decision_latency_class: DecisionLatencyClass
    fallback_behavior: FallbackBehavior
    compatible_data_profile_release_ids: tuple[str, ...]
    feature_contract_hash: str
    schema_version: int = SUPPORTED_FEATURE_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision_latency_class"] = self.decision_latency_class.value
        payload["fallback_behavior"] = self.fallback_behavior.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeatureAvailabilityContract":
        return cls(
            feature_block_id=str(payload["feature_block_id"]),
            source_artifact_ids=tuple(str(item) for item in payload["source_artifact_ids"]),
            source_fields=tuple(str(item) for item in payload["source_fields"]),
            value_timestamp_rule=str(payload["value_timestamp_rule"]),
            available_at_rule=str(payload["available_at_rule"]),
            requires_bar_close=bool(payload["requires_bar_close"]),
            requires_session_close=bool(payload["requires_session_close"]),
            decision_latency_class=DecisionLatencyClass(payload["decision_latency_class"]),
            fallback_behavior=FallbackBehavior(payload["fallback_behavior"]),
            compatible_data_profile_release_ids=tuple(
                str(item) for item in payload["compatible_data_profile_release_ids"]
            ),
            feature_contract_hash=str(payload["feature_contract_hash"]),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_FEATURE_CONTRACT_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FeatureAvailabilityContract":
        return cls.from_dict(_decode_json(payload, "feature_availability_contract"))


@dataclass(frozen=True)
class FeatureAvailabilityGateRequest:
    case_id: str
    surface_name: FeatureDecisionSurface
    decision_latency_class: DecisionLatencyClass
    bound_data_profile_release_id: str
    feature_contracts: tuple[FeatureAvailabilityContract, ...]


@dataclass(frozen=True)
class FeatureContractValidationReport:
    case_id: str
    feature_block_id: str | None
    status: str
    reason_code: str
    missing_fields: tuple[str, ...]
    decision_latency_class: str | None
    compatible_data_profile_release_ids: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class FeatureAvailabilityGateReport:
    case_id: str
    surface_name: str
    status: str
    reason_code: str
    decision_latency_class: str
    bound_data_profile_release_id: str | None
    accepted_feature_block_ids: tuple[str, ...]
    rejected_feature_block_ids: tuple[str, ...]
    decision_trace: dict[str, dict[str, Any]]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class RollPolicyRequest:
    case_id: str
    surface_name: RollPolicySurface
    product_profile_id: str
    resolved_context_bundle_id: str
    roll_map_id: str
    roll_calendar_source: str
    contract_series_mode: ContractSeriesMode
    continuous_series_usage: ContinuousSeriesUsage
    selected_contract_segment_id: str
    next_contract_segment_id: str | None = None
    active_contract_is_point_in_time: bool = True
    active_contract_is_delivery_aware: bool = True
    delivery_fence_enforced: bool = True
    delivery_window_active: bool = False
    reviewed_roll_approved: bool = True
    backtest_evaluation_mode: BacktestEvaluationMode = BacktestEvaluationMode.SEGMENT_BASED


@dataclass(frozen=True)
class RollPolicyReport:
    case_id: str
    surface_name: str
    product_profile_id: str
    status: str
    reason_code: str
    transition_action: str
    blocked_by_delivery_fence: bool
    selected_contract_segment_id: str | None
    next_contract_segment_id: str | None
    expected_roll_calendar_source: str | None
    actual_roll_calendar_source: str | None
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _decode_json(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _missing_feature_contract_fields(
    contract: FeatureAvailabilityContract,
) -> tuple[str, ...]:
    missing: list[str] = []
    required_scalars = {
        "feature_block_id": contract.feature_block_id,
        "value_timestamp_rule": contract.value_timestamp_rule,
        "available_at_rule": contract.available_at_rule,
        "feature_contract_hash": contract.feature_contract_hash,
    }
    for field_name, field_value in required_scalars.items():
        if not field_value:
            missing.append(field_name)

    required_sequences = {
        "source_artifact_ids": contract.source_artifact_ids,
        "source_fields": contract.source_fields,
        "compatible_data_profile_release_ids": contract.compatible_data_profile_release_ids,
    }
    for field_name, field_value in required_sequences.items():
        if not field_value:
            missing.append(field_name)

    return tuple(missing)


def _required_latency_rank(contract: FeatureAvailabilityContract) -> int:
    required = LATENCY_ORDER[contract.decision_latency_class]
    if contract.requires_bar_close:
        required = max(required, LATENCY_ORDER[DecisionLatencyClass.BAR_CLOSE])
    if contract.requires_session_close:
        required = max(required, LATENCY_ORDER[DecisionLatencyClass.SESSION_CLOSE])
    return required


def validate_feature_availability_contract(
    case_id: str,
    contract: FeatureAvailabilityContract,
) -> FeatureContractValidationReport:
    if contract.schema_version != SUPPORTED_FEATURE_CONTRACT_SCHEMA_VERSION:
        return FeatureContractValidationReport(
            case_id=case_id,
            feature_block_id=contract.feature_block_id or None,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_CONTRACT_SCHEMA_VERSION_UNSUPPORTED",
            missing_fields=(),
            decision_latency_class=contract.decision_latency_class.value,
            compatible_data_profile_release_ids=contract.compatible_data_profile_release_ids,
            explanation=(
                "The feature-availability contract uses an unsupported schema version."
            ),
            remediation="Rebuild the feature contract using the supported schema version.",
        )

    missing_fields = _missing_feature_contract_fields(contract)
    if missing_fields:
        return FeatureContractValidationReport(
            case_id=case_id,
            feature_block_id=contract.feature_block_id or None,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_CONTRACT_MISSING_REQUIRED_FIELDS",
            missing_fields=missing_fields,
            decision_latency_class=contract.decision_latency_class.value,
            compatible_data_profile_release_ids=contract.compatible_data_profile_release_ids,
            explanation=(
                "The feature-availability contract is missing one or more required fields: "
                f"{missing_fields}."
            ),
            remediation=(
                "Populate all required feature-block identifiers, source bindings, timing rules, "
                "data-profile bindings, and content hash fields."
            ),
        )

    if contract.requires_session_close and not contract.requires_bar_close:
        return FeatureContractValidationReport(
            case_id=case_id,
            feature_block_id=contract.feature_block_id,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_CONTRACT_SESSION_CLOSE_REQUIRES_BAR_CLOSE",
            missing_fields=(),
            decision_latency_class=contract.decision_latency_class.value,
            compatible_data_profile_release_ids=contract.compatible_data_profile_release_ids,
            explanation=(
                "Session-close features must also declare bar-close dependency because the final "
                "bar cannot be complete before the session closes."
            ),
            remediation="Mark session-close features as requiring both bar close and session close.",
        )

    declared_rank = LATENCY_ORDER[contract.decision_latency_class]
    required_rank = _required_latency_rank(contract)
    if declared_rank < required_rank:
        return FeatureContractValidationReport(
            case_id=case_id,
            feature_block_id=contract.feature_block_id,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_CONTRACT_DECISION_LATENCY_INCONSISTENT",
            missing_fields=(),
            decision_latency_class=contract.decision_latency_class.value,
            compatible_data_profile_release_ids=contract.compatible_data_profile_release_ids,
            explanation=(
                "The declared decision-latency class is earlier than the close dependency encoded "
                "by the feature contract."
            ),
            remediation=(
                "Align decision_latency_class with the required bar-close or session-close timing."
            ),
        )

    return FeatureContractValidationReport(
        case_id=case_id,
        feature_block_id=contract.feature_block_id,
        status=PolicyGateStatus.PASS.value,
        reason_code="FEATURE_CONTRACT_VALID",
        missing_fields=(),
        decision_latency_class=contract.decision_latency_class.value,
        compatible_data_profile_release_ids=contract.compatible_data_profile_release_ids,
        explanation=(
            "The feature-availability contract declares explicit source bindings, timing rules, "
            "close dependencies, fallback behavior, data-profile compatibility, and content hash."
        ),
        remediation="No remediation required.",
    )


def evaluate_feature_availability_gate(
    request: FeatureAvailabilityGateRequest,
) -> FeatureAvailabilityGateReport:
    if not request.feature_contracts:
        return FeatureAvailabilityGateReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_GATE_NO_CONTRACTS_BOUND",
            decision_latency_class=request.decision_latency_class.value,
            bound_data_profile_release_id=request.bound_data_profile_release_id or None,
            accepted_feature_block_ids=(),
            rejected_feature_block_ids=(),
            decision_trace={},
            explanation=(
                "The surface cannot evaluate feature timing without bound feature-availability "
                "contracts."
            ),
            remediation="Bind every required feature block to an explicit availability contract.",
        )

    accepted: list[str] = []
    rejected: list[str] = []
    decision_trace: dict[str, dict[str, Any]] = {}
    invalid_found = False
    timing_mismatch_found = False
    data_profile_mismatch_found = False

    request_rank = LATENCY_ORDER[request.decision_latency_class]
    for contract in request.feature_contracts:
        validation = validate_feature_availability_contract(request.case_id, contract)
        block_id = contract.feature_block_id or "<missing-feature-block-id>"
        if validation.status != PolicyGateStatus.PASS.value:
            invalid_found = True
            rejected.append(block_id)
            decision_trace[block_id] = {
                "status": validation.status,
                "reason_code": validation.reason_code,
                "fallback_behavior": contract.fallback_behavior.value,
            }
            continue

        required_rank = _required_latency_rank(contract)
        if request.bound_data_profile_release_id not in contract.compatible_data_profile_release_ids:
            data_profile_mismatch_found = True
            rejected.append(block_id)
            decision_trace[block_id] = {
                "status": PolicyGateStatus.INCOMPATIBLE.value,
                "reason_code": "FEATURE_GATE_DATA_PROFILE_INCOMPATIBLE",
                "fallback_behavior": contract.fallback_behavior.value,
            }
            continue

        if request_rank < required_rank:
            timing_mismatch_found = True
            rejected.append(block_id)
            decision_trace[block_id] = {
                "status": PolicyGateStatus.INCOMPATIBLE.value,
                "reason_code": "FEATURE_GATE_DECISION_TIMING_INCOMPATIBLE",
                "fallback_behavior": contract.fallback_behavior.value,
            }
            continue

        accepted.append(block_id)
        decision_trace[block_id] = {
            "status": PolicyGateStatus.PASS.value,
            "reason_code": "FEATURE_GATE_COMPATIBLE",
            "fallback_behavior": contract.fallback_behavior.value,
        }

    if invalid_found:
        return FeatureAvailabilityGateReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=PolicyGateStatus.INVALID.value,
            reason_code="FEATURE_GATE_INVALID_CONTRACTS_PRESENT",
            decision_latency_class=request.decision_latency_class.value,
            bound_data_profile_release_id=request.bound_data_profile_release_id or None,
            accepted_feature_block_ids=tuple(accepted),
            rejected_feature_block_ids=tuple(rejected),
            decision_trace=decision_trace,
            explanation=(
                "One or more feature blocks are bound to invalid availability contracts, so the "
                "surface cannot certify timing safety."
            ),
            remediation="Repair or replace the invalid feature contracts before build or activation.",
        )

    if timing_mismatch_found and not data_profile_mismatch_found:
        return FeatureAvailabilityGateReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=PolicyGateStatus.INCOMPATIBLE.value,
            reason_code="FEATURE_GATE_DECISION_TIMING_INCOMPATIBLE",
            decision_latency_class=request.decision_latency_class.value,
            bound_data_profile_release_id=request.bound_data_profile_release_id or None,
            accepted_feature_block_ids=tuple(accepted),
            rejected_feature_block_ids=tuple(rejected),
            decision_trace=decision_trace,
            explanation=(
                "At least one feature block becomes available later than the candidate's decision "
                "timing allows."
            ),
            remediation=(
                "Use slower decision timing or remove the rejected feature blocks from the surface."
            ),
        )

    if data_profile_mismatch_found and not timing_mismatch_found:
        return FeatureAvailabilityGateReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=PolicyGateStatus.INCOMPATIBLE.value,
            reason_code="FEATURE_GATE_DATA_PROFILE_INCOMPATIBLE",
            decision_latency_class=request.decision_latency_class.value,
            bound_data_profile_release_id=request.bound_data_profile_release_id or None,
            accepted_feature_block_ids=tuple(accepted),
            rejected_feature_block_ids=tuple(rejected),
            decision_trace=decision_trace,
            explanation=(
                "At least one feature block depends on data-profile semantics that do not match "
                "the bound promotable surface."
            ),
            remediation="Bind a compatible data_profile_release or remove the rejected feature blocks.",
        )

    if rejected:
        return FeatureAvailabilityGateReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=PolicyGateStatus.INCOMPATIBLE.value,
            reason_code="FEATURE_GATE_REJECTED_FEATURE_BLOCKS",
            decision_latency_class=request.decision_latency_class.value,
            bound_data_profile_release_id=request.bound_data_profile_release_id or None,
            accepted_feature_block_ids=tuple(accepted),
            rejected_feature_block_ids=tuple(rejected),
            decision_trace=decision_trace,
            explanation=(
                "The surface has rejected one or more feature blocks because their availability "
                "contracts are not jointly admissible."
            ),
            remediation="Resolve the rejected feature-block contract mismatches before proceeding.",
        )

    return FeatureAvailabilityGateReport(
        case_id=request.case_id,
        surface_name=request.surface_name.value,
        status=PolicyGateStatus.PASS.value,
        reason_code="FEATURE_GATE_ALL_CONTRACTS_COMPATIBLE",
        decision_latency_class=request.decision_latency_class.value,
        bound_data_profile_release_id=request.bound_data_profile_release_id,
        accepted_feature_block_ids=tuple(accepted),
        rejected_feature_block_ids=(),
        decision_trace=decision_trace,
        explanation=(
            "All bound feature blocks are available no later than the surface decision timing and "
            "are compatible with the bound data-profile release."
        ),
        remediation="No remediation required.",
    )


def evaluate_roll_policy(request: RollPolicyRequest) -> RollPolicyReport:
    products = product_profiles_by_id()
    product = products.get(request.product_profile_id)
    if product is None:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.INVALID.value,
            reason_code="ROLL_POLICY_UNKNOWN_PRODUCT_PROFILE",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id or None,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=None,
            actual_roll_calendar_source=request.roll_calendar_source or None,
            explanation="The referenced product profile does not exist in the canonical catalog.",
            remediation="Bind the roll-policy request to a known product profile identifier.",
        )

    required_scalars = {
        "resolved_context_bundle_id": request.resolved_context_bundle_id,
        "roll_map_id": request.roll_map_id,
        "roll_calendar_source": request.roll_calendar_source,
        "selected_contract_segment_id": request.selected_contract_segment_id,
    }
    missing_fields = tuple(
        field_name for field_name, field_value in required_scalars.items() if not field_value
    )
    if missing_fields:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.INVALID.value,
            reason_code="ROLL_POLICY_MISSING_REQUIRED_FIELDS",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id or None,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=product.roll_policy_inputs.roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source or None,
            explanation=(
                "The roll-policy request is missing one or more required resolved-context or "
                "contract-segment fields: "
                f"{missing_fields}."
            ),
            remediation="Bind the request to an explicit resolved-context bundle, roll map, and contract segment.",
        )

    expected_roll_calendar_source = product.roll_policy_inputs.roll_calendar_source
    if request.roll_calendar_source != expected_roll_calendar_source:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_UNBOUND_TO_RESOLVED_CONTEXT",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "The roll-policy request is not using the resolved-context bundle roll-window "
                "source required by the product profile."
            ),
            remediation="Compile roll windows into the resolved-context bundle and bind to that source.",
        )

    if request.continuous_series_usage == ContinuousSeriesUsage.EXECUTION:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_CONTINUOUS_SERIES_EXECUTION_FORBIDDEN",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Continuous series may support analytics or visualization, but never execution "
                "logic or active-contract selection."
            ),
            remediation="Route execution through actual contract segments instead of synthetic series.",
        )

    if (
        request.surface_name != RollPolicySurface.ANALYTICS
        and request.contract_series_mode == ContractSeriesMode.CONTINUOUS_SERIES
    ):
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_CONTINUOUS_SERIES_EXECUTION_FORBIDDEN",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Backtests, replay, paper, shadow-live, and live surfaces must use actual "
                "contract segments rather than synthetic continuous series."
            ),
            remediation="Switch the surface to actual contract segments and preserve continuous series for analytics only.",
        )

    if (
        request.surface_name == RollPolicySurface.ANALYTICS
        and request.contract_series_mode == ContractSeriesMode.CONTINUOUS_SERIES
        and request.continuous_series_usage
        not in (
            ContinuousSeriesUsage.ANALYTICS_ONLY,
            ContinuousSeriesUsage.VISUALIZATION_ONLY,
        )
    ):
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.INVALID.value,
            reason_code="ROLL_POLICY_ANALYTICS_USAGE_MUST_BE_EXPLICIT",
            transition_action=RollTransitionAction.HOLD_CURRENT_SEGMENT.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Analytics surfaces may use continuous series only when the usage is explicitly "
                "marked as analytics-only or visualization-only."
            ),
            remediation="Label continuous series usage explicitly or use actual contract segments.",
        )

    if not request.active_contract_is_point_in_time:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_ACTIVE_CONTRACT_NOT_POINT_IN_TIME",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Active-contract selection must be frozen point-in-time rather than inferred from "
                "current or hindsight state."
            ),
            remediation="Resolve the active contract from the bound context bundle at the decision timestamp.",
        )

    if not request.active_contract_is_delivery_aware:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_ACTIVE_CONTRACT_NOT_DELIVERY_AWARE",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Active-contract selection must account for delivery status and last-trade "
                "constraints from the product profile."
            ),
            remediation="Use delivery-aware contract selection derived from the resolved-context bundle.",
        )

    if not request.delivery_fence_enforced:
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_DELIVERY_FENCE_NOT_ENFORCED",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "The request does not enforce the hard delivery fence required by the product profile."
            ),
            remediation="Apply the product profile delivery-fence rule before the surface is used.",
        )

    if (
        request.surface_name == RollPolicySurface.BACKTEST
        and request.backtest_evaluation_mode != BacktestEvaluationMode.SEGMENT_BASED
    ):
        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.VIOLATION.value,
            reason_code="ROLL_POLICY_BACKTEST_REQUIRES_SEGMENT_EVALUATION",
            transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "Backtests must default to actual contract segments rather than continuous-series "
                "evaluation."
            ),
            remediation="Run the backtest with segment-based evaluation and explicit roll maps.",
        )

    if request.delivery_window_active and product.delivery_fence.reviewed_roll_required:
        if not request.reviewed_roll_approved:
            return RollPolicyReport(
                case_id=request.case_id,
                surface_name=request.surface_name.value,
                product_profile_id=request.product_profile_id,
                status=PolicyGateStatus.VIOLATION.value,
                reason_code="ROLL_POLICY_DELIVERY_FENCE_BLOCKED",
                transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
                blocked_by_delivery_fence=True,
                selected_contract_segment_id=request.selected_contract_segment_id,
                next_contract_segment_id=request.next_contract_segment_id,
                expected_roll_calendar_source=expected_roll_calendar_source,
                actual_roll_calendar_source=request.roll_calendar_source,
                explanation=(
                    "The delivery window is active and the product profile requires a reviewed "
                    "roll before trading or replay can continue."
                ),
                remediation="Approve the reviewed roll or stop before the delivery fence becomes active.",
            )

        if not request.next_contract_segment_id:
            return RollPolicyReport(
                case_id=request.case_id,
                surface_name=request.surface_name.value,
                product_profile_id=request.product_profile_id,
                status=PolicyGateStatus.INVALID.value,
                reason_code="ROLL_POLICY_NEXT_SEGMENT_REQUIRED",
                transition_action=RollTransitionAction.BLOCKED_BY_DELIVERY_FENCE.value,
                blocked_by_delivery_fence=True,
                selected_contract_segment_id=request.selected_contract_segment_id,
                next_contract_segment_id=request.next_contract_segment_id,
                expected_roll_calendar_source=expected_roll_calendar_source,
                actual_roll_calendar_source=request.roll_calendar_source,
                explanation=(
                    "The delivery window is active, but no explicit next contract segment was "
                    "bound for the reviewed roll transition."
                ),
                remediation="Bind the next admissible contract segment before entering the delivery window.",
            )

        return RollPolicyReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            product_profile_id=request.product_profile_id,
            status=PolicyGateStatus.PASS.value,
            reason_code="ROLL_POLICY_ALLOWED",
            transition_action=RollTransitionAction.ROLL_TO_NEXT_SEGMENT.value,
            blocked_by_delivery_fence=False,
            selected_contract_segment_id=request.selected_contract_segment_id,
            next_contract_segment_id=request.next_contract_segment_id,
            expected_roll_calendar_source=expected_roll_calendar_source,
            actual_roll_calendar_source=request.roll_calendar_source,
            explanation=(
                "The surface is using actual contract segments, the active contract selection is "
                "point-in-time and delivery-aware, and the reviewed roll moves to the next "
                "explicit contract segment."
            ),
            remediation="No remediation required.",
        )

    return RollPolicyReport(
        case_id=request.case_id,
        surface_name=request.surface_name.value,
        product_profile_id=request.product_profile_id,
        status=PolicyGateStatus.PASS.value,
        reason_code="ROLL_POLICY_ALLOWED",
        transition_action=RollTransitionAction.HOLD_CURRENT_SEGMENT.value,
        blocked_by_delivery_fence=False,
        selected_contract_segment_id=request.selected_contract_segment_id,
        next_contract_segment_id=request.next_contract_segment_id,
        expected_roll_calendar_source=expected_roll_calendar_source,
        actual_roll_calendar_source=request.roll_calendar_source,
        explanation=(
            "The surface uses actual contract segments with point-in-time, delivery-aware active "
            "contract selection and an enforced product-profile delivery fence."
        ),
        remediation="No remediation required.",
    )


def validate_feature_policy_contract() -> list[str]:
    errors: list[str] = []
    products = product_profiles_by_id()

    if not products:
        errors.append("at least one product profile is required for roll-policy validation")

    for profile_id, profile in products.items():
        if profile.roll_policy_inputs.roll_calendar_source != "resolved_context_bundle_roll_windows":
            errors.append(
                f"{profile_id}: roll policy must bind to resolved_context_bundle_roll_windows"
            )
        if not profile.delivery_fence.delivery_fence_rule:
            errors.append(f"{profile_id}: delivery_fence_rule must be explicit")
        if not profile.delivery_fence.reviewed_roll_required:
            errors.append(f"{profile_id}: reviewed_roll_required must be explicit and true")

    return errors


VALIDATION_ERRORS = validate_feature_policy_contract()
