"""Broker capability, conformance, idempotency, and fixture contracts."""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.product_profiles import (
    BrokerContractDescriptor,
    ProductLane,
    product_profiles_by_id,
)

SUPPORTED_BROKER_DESCRIPTOR_SCHEMA_VERSION = "1.0.0"
SUPPORTED_BROKER_FIXTURE_LIBRARY_SCHEMA_VERSION = "1.0.0"


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _parse_timestamp(value: str) -> _dt.datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        value = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return value


@unique
class BrokerOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    MARKET_ON_CLOSE = "market_on_close"


@unique
class BrokerTimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    OPG = "opg"


@unique
class BrokerMutationKind(str, Enum):
    SUBMIT = "submit"
    MODIFY = "modify"
    CANCEL = "cancel"
    FLATTEN = "flatten"


@unique
class MutationAckState(str, Enum):
    UNKNOWN = "unknown"
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"


@unique
class AmbiguousRecoveryPolicy(str, Enum):
    RECONCILE_FIRST_NO_RESEND = "reconcile_first_no_resend"
    HALT_OR_FLATTEN = "halt_or_flatten"
    RESEND_MUTATION = "resend_mutation"


@unique
class BrokerTimelineEventType(str, Enum):
    PERSIST_INTENT = "persist_intent"
    SUBMIT_ATTEMPT = "submit_attempt"
    MODIFY_ATTEMPT = "modify_attempt"
    CANCEL_ATTEMPT = "cancel_attempt"
    FLATTEN_ATTEMPT = "flatten_attempt"
    ACK_RECEIVED = "ack_received"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    REJECT = "reject"
    UNSOLICITED_CANCEL = "unsolicited_cancel"
    DUPLICATE_FILL_CALLBACK = "duplicate_fill_callback"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"
    DAILY_RESET = "daily_reset"
    POST_RESET_RESUME = "post_reset_resume"
    CONTRACT_DEFINITION_MISMATCH = "contract_definition_mismatch"
    TIMEOUT_WITH_NO_RESPONSE = "timeout_with_no_response"
    OPERATOR_RETRY = "operator_retry"


@unique
class BrokerSessionScenarioKind(str, Enum):
    CLEAN_FILL_FLOW = "clean_fill_flow"
    PARTIAL_FILLS = "partial_fills"
    UNSOLICITED_CANCEL = "unsolicited_cancel"
    REJECT_AFTER_ACKNOWLEDGEMENT = "reject_after_acknowledgement"
    DISCONNECT_RECONNECT_MID_ORDER = "disconnect_reconnect_mid_order"
    DAILY_RESET_AND_POST_RESET_RESUME = "daily_reset_and_post_reset_resume"
    CONTRACT_DEFINITION_MISMATCH_DETECTION = "contract_definition_mismatch_detection"
    TIMEOUT_WITH_NO_RESPONSE = "timeout_with_no_response"


REQUIRED_BROKER_SESSION_SCENARIOS: tuple[BrokerSessionScenarioKind, ...] = (
    BrokerSessionScenarioKind.CLEAN_FILL_FLOW,
    BrokerSessionScenarioKind.PARTIAL_FILLS,
    BrokerSessionScenarioKind.UNSOLICITED_CANCEL,
    BrokerSessionScenarioKind.REJECT_AFTER_ACKNOWLEDGEMENT,
    BrokerSessionScenarioKind.DISCONNECT_RECONNECT_MID_ORDER,
    BrokerSessionScenarioKind.DAILY_RESET_AND_POST_RESET_RESUME,
    BrokerSessionScenarioKind.CONTRACT_DEFINITION_MISMATCH_DETECTION,
    BrokerSessionScenarioKind.TIMEOUT_WITH_NO_RESPONSE,
)

TRADEABLE_LANES: frozenset[ProductLane] = frozenset(
    {ProductLane.PAPER, ProductLane.SHADOW_LIVE, ProductLane.LIVE}
)

_PRODUCT_PROFILE_INDEX = product_profiles_by_id()


@dataclass(frozen=True)
class BrokerCapabilityDescriptor:
    schema_version: str
    descriptor_id: str
    adapter_id: str
    broker: str
    supported_order_types: tuple[BrokerOrderType, ...]
    supported_time_in_force: tuple[BrokerTimeInForce, ...]
    modify_cancel_supported: bool
    flatten_supported: bool
    session_definition_supported: bool
    partial_fill_behavior: str
    reject_behavior: str
    maintenance_window_behavior: str
    message_rate_limit_per_second: int
    exchange_constraints: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "descriptor_id": self.descriptor_id,
            "adapter_id": self.adapter_id,
            "broker": self.broker,
            "supported_order_types": [item.value for item in self.supported_order_types],
            "supported_time_in_force": [item.value for item in self.supported_time_in_force],
            "modify_cancel_supported": self.modify_cancel_supported,
            "flatten_supported": self.flatten_supported,
            "session_definition_supported": self.session_definition_supported,
            "partial_fill_behavior": self.partial_fill_behavior,
            "reject_behavior": self.reject_behavior,
            "maintenance_window_behavior": self.maintenance_window_behavior,
            "message_rate_limit_per_second": self.message_rate_limit_per_second,
            "exchange_constraints": {
                key: list(values) for key, values in sorted(self.exchange_constraints.items())
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BrokerCapabilityDescriptor:
        return cls(
            schema_version=str(payload["schema_version"]),
            descriptor_id=str(payload["descriptor_id"]),
            adapter_id=str(payload["adapter_id"]),
            broker=str(payload["broker"]),
            supported_order_types=tuple(
                BrokerOrderType(item) for item in payload["supported_order_types"]
            ),
            supported_time_in_force=tuple(
                BrokerTimeInForce(item) for item in payload["supported_time_in_force"]
            ),
            modify_cancel_supported=bool(payload["modify_cancel_supported"]),
            flatten_supported=bool(payload["flatten_supported"]),
            session_definition_supported=bool(payload["session_definition_supported"]),
            partial_fill_behavior=str(payload["partial_fill_behavior"]),
            reject_behavior=str(payload["reject_behavior"]),
            maintenance_window_behavior=str(payload["maintenance_window_behavior"]),
            message_rate_limit_per_second=int(payload["message_rate_limit_per_second"]),
            exchange_constraints={
                str(key): tuple(str(value) for value in values)
                for key, values in dict(payload.get("exchange_constraints", {})).items()
            },
        )

    @classmethod
    def from_json(cls, payload: str) -> BrokerCapabilityDescriptor:
        return cls.from_dict(_decode_json_object(payload, label="broker capability descriptor"))


@dataclass(frozen=True)
class BrokerConformanceRequest:
    case_id: str
    product_profile_id: str
    lane: ProductLane
    descriptor: BrokerCapabilityDescriptor
    active_contract: BrokerContractDescriptor
    required_order_types: tuple[BrokerOrderType, ...]
    required_time_in_force: tuple[BrokerTimeInForce, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "product_profile_id": self.product_profile_id,
            "lane": self.lane.value,
            "descriptor": self.descriptor.to_dict(),
            "active_contract": {
                "symbol": self.active_contract.symbol,
                "exchange": self.active_contract.exchange,
                "currency": self.active_contract.currency,
                "contract_size_oz": self.active_contract.contract_size_oz,
                "minimum_price_fluctuation_usd_per_oz": (
                    self.active_contract.minimum_price_fluctuation_usd_per_oz
                ),
                "settlement_type": self.active_contract.settlement_type,
                "session_calendar_id": self.active_contract.session_calendar_id,
            },
            "required_order_types": [item.value for item in self.required_order_types],
            "required_time_in_force": [item.value for item in self.required_time_in_force],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BrokerConformanceRequest:
        contract = payload["active_contract"]
        return cls(
            case_id=str(payload["case_id"]),
            product_profile_id=str(payload["product_profile_id"]),
            lane=ProductLane(payload["lane"]),
            descriptor=BrokerCapabilityDescriptor.from_dict(dict(payload["descriptor"])),
            active_contract=BrokerContractDescriptor(
                symbol=str(contract["symbol"]),
                exchange=str(contract["exchange"]),
                currency=str(contract["currency"]),
                contract_size_oz=int(contract["contract_size_oz"]),
                minimum_price_fluctuation_usd_per_oz=float(
                    contract["minimum_price_fluctuation_usd_per_oz"]
                ),
                settlement_type=str(contract["settlement_type"]),
                session_calendar_id=str(contract["session_calendar_id"]),
            ),
            required_order_types=tuple(
                BrokerOrderType(item) for item in payload["required_order_types"]
            ),
            required_time_in_force=tuple(
                BrokerTimeInForce(item) for item in payload["required_time_in_force"]
            ),
        )


@dataclass(frozen=True)
class BrokerConformanceReport:
    case_id: str
    product_profile_id: str
    lane: str
    status: str
    reason_code: str
    conformance_required: bool
    allowed: bool
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)


@dataclass(frozen=True)
class OrderIntentIdentity:
    deployment_instance_id: str
    decision_sequence_number: int
    leg_id: str
    side: str
    intent_purpose: str

    def deterministic_id(self) -> str:
        return (
            f"{self.deployment_instance_id}:"
            f"{self.decision_sequence_number}:"
            f"{self.leg_id}:{self.side}:{self.intent_purpose}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_instance_id": self.deployment_instance_id,
            "decision_sequence_number": self.decision_sequence_number,
            "leg_id": self.leg_id,
            "side": self.side,
            "intent_purpose": self.intent_purpose,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OrderIntentIdentity:
        return cls(
            deployment_instance_id=str(payload["deployment_instance_id"]),
            decision_sequence_number=int(payload["decision_sequence_number"]),
            leg_id=str(payload["leg_id"]),
            side=str(payload["side"]),
            intent_purpose=str(payload["intent_purpose"]),
        )


@dataclass(frozen=True)
class BrokerMutationScenario:
    case_id: str
    mutation_kind: BrokerMutationKind
    order_intent_identity: OrderIntentIdentity
    observed_order_intent_id: str
    persisted_before_submit: bool
    persistence_atomic_with_submit: bool
    mapping_persisted: bool
    last_known_ack_state: MutationAckState
    broker_order_ids: tuple[str, ...]
    ambiguous_recovery: bool
    ambiguous_recovery_policy: AmbiguousRecoveryPolicy
    duplicate_callback_handled: bool
    operator_retry_reuses_order_intent_id: bool
    timeline_event_types: tuple[BrokerTimelineEventType, ...]
    correlation_id: str
    decision_trace_id: str
    expected_timeline_id: str
    actual_timeline_id: str
    artifact_manifest_id: str
    operator_reason_bundle_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "mutation_kind": self.mutation_kind.value,
            "order_intent_identity": self.order_intent_identity.to_dict(),
            "observed_order_intent_id": self.observed_order_intent_id,
            "persisted_before_submit": self.persisted_before_submit,
            "persistence_atomic_with_submit": self.persistence_atomic_with_submit,
            "mapping_persisted": self.mapping_persisted,
            "last_known_ack_state": self.last_known_ack_state.value,
            "broker_order_ids": list(self.broker_order_ids),
            "ambiguous_recovery": self.ambiguous_recovery,
            "ambiguous_recovery_policy": self.ambiguous_recovery_policy.value,
            "duplicate_callback_handled": self.duplicate_callback_handled,
            "operator_retry_reuses_order_intent_id": self.operator_retry_reuses_order_intent_id,
            "timeline_event_types": [item.value for item in self.timeline_event_types],
            "correlation_id": self.correlation_id,
            "decision_trace_id": self.decision_trace_id,
            "expected_timeline_id": self.expected_timeline_id,
            "actual_timeline_id": self.actual_timeline_id,
            "artifact_manifest_id": self.artifact_manifest_id,
            "operator_reason_bundle_id": self.operator_reason_bundle_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BrokerMutationScenario:
        return cls(
            case_id=str(payload["case_id"]),
            mutation_kind=BrokerMutationKind(payload["mutation_kind"]),
            order_intent_identity=OrderIntentIdentity.from_dict(
                dict(payload["order_intent_identity"])
            ),
            observed_order_intent_id=str(payload["observed_order_intent_id"]),
            persisted_before_submit=bool(payload["persisted_before_submit"]),
            persistence_atomic_with_submit=bool(payload["persistence_atomic_with_submit"]),
            mapping_persisted=bool(payload["mapping_persisted"]),
            last_known_ack_state=MutationAckState(payload["last_known_ack_state"]),
            broker_order_ids=tuple(str(item) for item in payload["broker_order_ids"]),
            ambiguous_recovery=bool(payload["ambiguous_recovery"]),
            ambiguous_recovery_policy=AmbiguousRecoveryPolicy(
                payload["ambiguous_recovery_policy"]
            ),
            duplicate_callback_handled=bool(payload["duplicate_callback_handled"]),
            operator_retry_reuses_order_intent_id=bool(
                payload["operator_retry_reuses_order_intent_id"]
            ),
            timeline_event_types=tuple(
                BrokerTimelineEventType(item) for item in payload["timeline_event_types"]
            ),
            correlation_id=str(payload["correlation_id"]),
            decision_trace_id=str(payload["decision_trace_id"]),
            expected_timeline_id=str(payload["expected_timeline_id"]),
            actual_timeline_id=str(payload["actual_timeline_id"]),
            artifact_manifest_id=str(payload["artifact_manifest_id"]),
            operator_reason_bundle_id=str(payload["operator_reason_bundle_id"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> BrokerMutationScenario:
        return cls.from_dict(_decode_json_object(payload, label="broker mutation scenario"))


@dataclass(frozen=True)
class BrokerIdempotencyReport:
    case_id: str
    mutation_kind: str
    order_intent_id: str
    status: str
    reason_code: str
    idempotent: bool
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)


@dataclass(frozen=True)
class BrokerSessionFixture:
    fixture_id: str
    scenario_kind: BrokerSessionScenarioKind
    broker: str
    adapter_id: str
    recorded_at_utc: str
    immutable_sha256: str
    interface_schema_id: str
    replay_seed: str
    expected_timeline_id: str
    correlation_log_id: str
    artifact_manifest_id: str
    event_types: tuple[BrokerTimelineEventType, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "scenario_kind": self.scenario_kind.value,
            "broker": self.broker,
            "adapter_id": self.adapter_id,
            "recorded_at_utc": self.recorded_at_utc,
            "immutable_sha256": self.immutable_sha256,
            "interface_schema_id": self.interface_schema_id,
            "replay_seed": self.replay_seed,
            "expected_timeline_id": self.expected_timeline_id,
            "correlation_log_id": self.correlation_log_id,
            "artifact_manifest_id": self.artifact_manifest_id,
            "event_types": [item.value for item in self.event_types],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BrokerSessionFixture:
        return cls(
            fixture_id=str(payload["fixture_id"]),
            scenario_kind=BrokerSessionScenarioKind(payload["scenario_kind"]),
            broker=str(payload["broker"]),
            adapter_id=str(payload["adapter_id"]),
            recorded_at_utc=str(payload["recorded_at_utc"]),
            immutable_sha256=str(payload["immutable_sha256"]),
            interface_schema_id=str(payload["interface_schema_id"]),
            replay_seed=str(payload["replay_seed"]),
            expected_timeline_id=str(payload["expected_timeline_id"]),
            correlation_log_id=str(payload["correlation_log_id"]),
            artifact_manifest_id=str(payload["artifact_manifest_id"]),
            event_types=tuple(BrokerTimelineEventType(item) for item in payload["event_types"]),
        )


@dataclass(frozen=True)
class BrokerSessionFixtureLibrary:
    schema_version: str
    library_id: str
    fixtures: tuple[BrokerSessionFixture, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "library_id": self.library_id,
            "fixtures": [fixture.to_dict() for fixture in self.fixtures],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BrokerSessionFixtureLibrary:
        return cls(
            schema_version=str(payload["schema_version"]),
            library_id=str(payload["library_id"]),
            fixtures=tuple(
                BrokerSessionFixture.from_dict(dict(item))
                for item in payload["fixtures"]
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> BrokerSessionFixtureLibrary:
        return cls.from_dict(_decode_json_object(payload, label="broker session fixture library"))


@dataclass(frozen=True)
class BrokerSessionFixtureReport:
    case_id: str
    library_id: str
    status: str
    reason_code: str
    deterministic_replay_ready: bool
    immutable_fixture_store: bool
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)


def required_broker_session_scenarios() -> tuple[str, ...]:
    return tuple(item.value for item in REQUIRED_BROKER_SESSION_SCENARIOS)


def evaluate_broker_conformance(request: BrokerConformanceRequest) -> BrokerConformanceReport:
    context: dict[str, Any] = {
        "product_profile_id": request.product_profile_id,
        "lane": request.lane.value,
        "descriptor_id": request.descriptor.descriptor_id,
        "adapter_id": request.descriptor.adapter_id,
        "required_order_types": [item.value for item in request.required_order_types],
        "required_time_in_force": [item.value for item in request.required_time_in_force],
    }

    if request.product_profile_id not in _PRODUCT_PROFILE_INDEX:
        context["known_product_profiles"] = sorted(_PRODUCT_PROFILE_INDEX)
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=request.product_profile_id,
            lane=request.lane.value,
            status="invalid",
            reason_code="BROKER_CONFORMANCE_UNKNOWN_PRODUCT_PROFILE",
            conformance_required=request.lane in TRADEABLE_LANES,
            allowed=False,
            diagnostic_context=context,
            explanation="The broker conformance request references an unknown product profile.",
            remediation="Bind the request to a canonical product profile before evaluating broker conformance.",
        )

    profile = _PRODUCT_PROFILE_INDEX[request.product_profile_id]
    context["supported_lanes"] = [lane.value for lane in profile.supported_lanes]
    if request.lane not in profile.supported_lanes:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_CONFORMANCE_LANE_UNSUPPORTED",
            conformance_required=request.lane in TRADEABLE_LANES,
            allowed=False,
            diagnostic_context=context,
            explanation="The product profile does not allow the requested execution lane.",
            remediation="Evaluate broker conformance only on a lane explicitly supported by the product profile.",
        )

    conformance_required = request.lane in TRADEABLE_LANES
    assumptions = profile.broker_capability_assumptions
    context["conformance_required"] = conformance_required
    if not conformance_required:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="pass",
            reason_code="BROKER_CONFORMANCE_NOT_REQUIRED_FOR_LANE",
            conformance_required=False,
            allowed=True,
            diagnostic_context=context,
            explanation="The requested lane is research-only, so tradeable broker conformance is advisory.",
            remediation="No remediation required.",
        )

    descriptor = request.descriptor
    if descriptor.schema_version != SUPPORTED_BROKER_DESCRIPTOR_SCHEMA_VERSION:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="invalid",
            reason_code="BROKER_DESCRIPTOR_SCHEMA_UNSUPPORTED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The broker capability descriptor uses an unsupported schema version.",
            remediation="Publish the descriptor using the supported broker descriptor schema version.",
        )

    if descriptor.message_rate_limit_per_second <= 0:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="invalid",
            reason_code="BROKER_DESCRIPTOR_RATE_LIMIT_REQUIRED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The active adapter descriptor is missing a positive message-rate limit.",
            remediation="Declare the adapter message-rate limit before allowing tradeable conformance.",
        )

    if descriptor.broker != assumptions.broker:
        context["expected_broker"] = assumptions.broker
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_DESCRIPTOR_BROKER_MISMATCH",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The active adapter broker does not match the product profile assumptions.",
            remediation="Run tradeable conformance against the approved broker adapter only.",
        )

    if assumptions.modify_cancel_supported and not descriptor.modify_cancel_supported:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_MODIFY_CANCEL_SUPPORT_REQUIRED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The live lane requires modify/cancel support but the adapter does not declare it.",
            remediation="Use an adapter descriptor that supports modify/cancel semantics or block trading.",
        )

    if assumptions.flatten_supported and not descriptor.flatten_supported:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_FLATTEN_SUPPORT_REQUIRED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The live lane requires flatten support before the session can become tradeable.",
            remediation="Block trading until the active adapter can flatten positions and open orders safely.",
        )

    if assumptions.session_definition_required and not descriptor.session_definition_supported:
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_SESSION_DEFINITION_REQUIRED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The product profile requires session-definition support from the adapter.",
            remediation="Publish a descriptor that proves the adapter can resolve and honor session definitions.",
        )

    unsupported_order_types = sorted(
        item.value
        for item in set(request.required_order_types).difference(descriptor.supported_order_types)
    )
    if unsupported_order_types:
        context["unsupported_order_types"] = unsupported_order_types
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_REQUIRED_ORDER_TYPE_UNSUPPORTED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The candidate bundle requests order types that the active adapter does not support.",
            remediation="Restrict the bundle to the active adapter order types or change the adapter.",
        )

    unsupported_tifs = sorted(
        item.value
        for item in set(request.required_time_in_force).difference(
            descriptor.supported_time_in_force
        )
    )
    if unsupported_tifs:
        context["unsupported_time_in_force"] = unsupported_tifs
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_REQUIRED_TIME_IN_FORCE_UNSUPPORTED",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation="The candidate bundle requires a time-in-force mode unavailable on the active adapter.",
            remediation="Use only supported TIF modes for the active adapter before enabling the session.",
        )

    descriptor_contract = request.active_contract
    invariants = profile.broker_contract_invariants
    differences: dict[str, dict[str, Any]] = {}
    if descriptor_contract.symbol != invariants.symbol:
        differences["symbol"] = {"actual": descriptor_contract.symbol, "expected": invariants.symbol}
    if descriptor_contract.exchange != invariants.exchange:
        differences["exchange"] = {
            "actual": descriptor_contract.exchange,
            "expected": invariants.exchange,
        }
    if descriptor_contract.currency != invariants.currency:
        differences["currency"] = {
            "actual": descriptor_contract.currency,
            "expected": invariants.currency,
        }
    if descriptor_contract.contract_size_oz != invariants.contract_size_oz:
        differences["contract_size_oz"] = {
            "actual": descriptor_contract.contract_size_oz,
            "expected": invariants.contract_size_oz,
        }
    if (
        descriptor_contract.minimum_price_fluctuation_usd_per_oz
        != invariants.minimum_price_fluctuation_usd_per_oz
    ):
        differences["minimum_price_fluctuation_usd_per_oz"] = {
            "actual": descriptor_contract.minimum_price_fluctuation_usd_per_oz,
            "expected": invariants.minimum_price_fluctuation_usd_per_oz,
        }
    if descriptor_contract.settlement_type != invariants.settlement_type:
        differences["settlement_type"] = {
            "actual": descriptor_contract.settlement_type,
            "expected": invariants.settlement_type,
        }
    if descriptor_contract.session_calendar_id != invariants.session_calendar_id:
        differences["session_calendar_id"] = {
            "actual": descriptor_contract.session_calendar_id,
            "expected": invariants.session_calendar_id,
        }

    if differences:
        context["contract_differences"] = differences
        return BrokerConformanceReport(
            case_id=request.case_id,
            product_profile_id=profile.profile_id,
            lane=request.lane.value,
            status="violation",
            reason_code="BROKER_CONTRACT_INVARIANT_MISMATCH",
            conformance_required=True,
            allowed=False,
            diagnostic_context=context,
            explanation=(
                "The active broker contract descriptor does not match the canonical product-profile "
                "contract invariants."
            ),
            remediation=(
                "Block trading until symbol, exchange, tick size, settlement, and session "
                "definition all match the product profile."
            ),
        )

    return BrokerConformanceReport(
        case_id=request.case_id,
        product_profile_id=profile.profile_id,
        lane=request.lane.value,
        status="pass",
        reason_code="BROKER_CONFORMANCE_CONFIRMED",
        conformance_required=True,
        allowed=True,
        diagnostic_context=context,
        explanation=(
            "The active adapter descriptor, contract descriptor, and required bundle capabilities "
            "match the product profile for the requested tradeable lane."
        ),
        remediation="No remediation required.",
    )


def evaluate_order_intent_idempotency(scenario: BrokerMutationScenario) -> BrokerIdempotencyReport:
    expected_order_intent_id = scenario.order_intent_identity.deterministic_id()
    context: dict[str, Any] = {
        "mutation_kind": scenario.mutation_kind.value,
        "observed_order_intent_id": scenario.observed_order_intent_id,
        "expected_order_intent_id": expected_order_intent_id,
        "last_known_ack_state": scenario.last_known_ack_state.value,
        "broker_order_ids": list(scenario.broker_order_ids),
        "ambiguous_recovery": scenario.ambiguous_recovery,
        "ambiguous_recovery_policy": scenario.ambiguous_recovery_policy.value,
        "timeline_event_types": [item.value for item in scenario.timeline_event_types],
        "correlation_id": scenario.correlation_id,
        "decision_trace_id": scenario.decision_trace_id,
        "expected_timeline_id": scenario.expected_timeline_id,
        "actual_timeline_id": scenario.actual_timeline_id,
        "artifact_manifest_id": scenario.artifact_manifest_id,
        "operator_reason_bundle_id": scenario.operator_reason_bundle_id,
    }

    if scenario.observed_order_intent_id != expected_order_intent_id:
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=scenario.observed_order_intent_id,
            status="violation",
            reason_code="BROKER_ORDER_INTENT_ID_NONDETERMINISTIC",
            idempotent=False,
            diagnostic_context=context,
            explanation="The broker mutation did not reuse the canonical deterministic order-intent id.",
            remediation="Derive order_intent_id only from deployment instance, decision sequence, leg, side, and intent purpose.",
        )

    if not (scenario.persisted_before_submit or scenario.persistence_atomic_with_submit):
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="violation",
            reason_code="BROKER_ORDER_INTENT_NOT_DURABLE_BEFORE_SUBMIT",
            idempotent=False,
            diagnostic_context=context,
            explanation="The mutation could reach the broker before the order-intent record becomes durable.",
            remediation="Persist the order-intent before submit or atomically with the first broker mutation.",
        )

    if not scenario.mapping_persisted:
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="violation",
            reason_code="BROKER_ORDER_INTENT_MAPPING_NOT_DURABLE",
            idempotent=False,
            diagnostic_context=context,
            explanation="The adapter is missing a durable mapping between order_intent_id and broker state.",
            remediation="Persist broker order ids, status versions, and acknowledgement state durably before proceeding.",
        )

    if not all(
        (
            scenario.correlation_id.strip(),
            scenario.decision_trace_id.strip(),
            scenario.expected_timeline_id.strip(),
            scenario.actual_timeline_id.strip(),
            scenario.artifact_manifest_id.strip(),
            scenario.operator_reason_bundle_id.strip(),
        )
    ):
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="invalid",
            reason_code="BROKER_MUTATION_EVIDENCE_INCOMPLETE",
            idempotent=False,
            diagnostic_context=context,
            explanation="Critical broker-mutation evidence fields are missing from the scenario.",
            remediation="Retain correlation ids, expected-vs-actual timelines, artifact manifests, and operator reason bundles for every critical mutation.",
        )

    if (
        BrokerTimelineEventType.DUPLICATE_FILL_CALLBACK in scenario.timeline_event_types
        and not scenario.duplicate_callback_handled
    ):
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="violation",
            reason_code="BROKER_DUPLICATE_CALLBACK_NOT_IDEMPOTENT",
            idempotent=False,
            diagnostic_context=context,
            explanation="The adapter does not treat duplicate fill callbacks as idempotent replays of known state.",
            remediation="Deduplicate duplicate callbacks against the durable order-intent mapping before mutating state.",
        )

    if not scenario.operator_retry_reuses_order_intent_id:
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="violation",
            reason_code="BROKER_OPERATOR_RETRY_BREAKS_IDEMPOTENCY",
            idempotent=False,
            diagnostic_context=context,
            explanation="Operator retry paths must reuse the original order-intent id instead of generating a new mutation identity.",
            remediation="Route operator retries through the existing order-intent record and durable mapping.",
        )

    if (
        scenario.ambiguous_recovery
        and scenario.ambiguous_recovery_policy
        == AmbiguousRecoveryPolicy.RESEND_MUTATION
    ):
        return BrokerIdempotencyReport(
            case_id=scenario.case_id,
            mutation_kind=scenario.mutation_kind.value,
            order_intent_id=expected_order_intent_id,
            status="violation",
            reason_code="BROKER_AMBIGUOUS_RECOVERY_REQUIRES_RECONCILIATION",
            idempotent=False,
            diagnostic_context=context,
            explanation="Ambiguous broker recovery cannot default to resending the mutation.",
            remediation="Reconcile broker state first and default to no-resend plus halt/flatten according to policy.",
        )

    return BrokerIdempotencyReport(
        case_id=scenario.case_id,
        mutation_kind=scenario.mutation_kind.value,
        order_intent_id=expected_order_intent_id,
        status="pass",
        reason_code="BROKER_IDEMPOTENCY_GUARDED",
        idempotent=True,
        diagnostic_context=context,
        explanation=(
            "The mutation uses a deterministic durable order-intent id, retains correlated broker "
            "evidence, and handles retry and recovery without creating duplicate economic actions."
        ),
        remediation="No remediation required.",
    )


def evaluate_broker_session_fixture_library(
    case_id: str,
    library: BrokerSessionFixtureLibrary,
) -> BrokerSessionFixtureReport:
    observed_fixture_ids = [fixture.fixture_id for fixture in library.fixtures]
    observed_scenarios = {fixture.scenario_kind for fixture in library.fixtures}
    missing_scenarios = sorted(
        scenario.value
        for scenario in set(REQUIRED_BROKER_SESSION_SCENARIOS).difference(observed_scenarios)
    )
    duplicate_fixture_ids = sorted(
        fixture_id
        for fixture_id in set(observed_fixture_ids)
        if observed_fixture_ids.count(fixture_id) > 1
    )
    context: dict[str, Any] = {
        "required_scenarios": required_broker_session_scenarios(),
        "observed_scenarios": sorted(item.value for item in observed_scenarios),
        "fixture_count": len(library.fixtures),
        "duplicate_fixture_ids": duplicate_fixture_ids,
    }

    if library.schema_version != SUPPORTED_BROKER_FIXTURE_LIBRARY_SCHEMA_VERSION:
        return BrokerSessionFixtureReport(
            case_id=case_id,
            library_id=library.library_id,
            status="invalid",
            reason_code="BROKER_SESSION_FIXTURE_LIBRARY_SCHEMA_UNSUPPORTED",
            deterministic_replay_ready=False,
            immutable_fixture_store=False,
            diagnostic_context=context,
            explanation="The broker session fixture library uses an unsupported schema version.",
            remediation="Rebuild the fixture library using the supported broker fixture schema version.",
        )

    if duplicate_fixture_ids:
        return BrokerSessionFixtureReport(
            case_id=case_id,
            library_id=library.library_id,
            status="invalid",
            reason_code="BROKER_SESSION_FIXTURE_DUPLICATE_ID",
            deterministic_replay_ready=False,
            immutable_fixture_store=False,
            diagnostic_context=context,
            explanation="The fixture library contains duplicate fixture identifiers.",
            remediation="Assign globally unique ids to every broker session fixture.",
        )

    if missing_scenarios:
        context["missing_scenarios"] = missing_scenarios
        return BrokerSessionFixtureReport(
            case_id=case_id,
            library_id=library.library_id,
            status="violation",
            reason_code="BROKER_SESSION_FIXTURE_SCENARIOS_MISSING",
            deterministic_replay_ready=False,
            immutable_fixture_store=False,
            diagnostic_context=context,
            explanation="The fixture library is missing one or more required broker edge-case scenarios.",
            remediation="Capture immutable fixtures for every required broker session scenario before relying on replay tests.",
        )

    for fixture in library.fixtures:
        if (
            not fixture.immutable_sha256.strip()
            or not fixture.replay_seed.strip()
            or not fixture.expected_timeline_id.strip()
            or not fixture.correlation_log_id.strip()
            or not fixture.artifact_manifest_id.strip()
            or not fixture.interface_schema_id.strip()
            or not fixture.event_types
            or _parse_timestamp(fixture.recorded_at_utc) is None
        ):
            context["invalid_fixture_id"] = fixture.fixture_id
            return BrokerSessionFixtureReport(
                case_id=case_id,
                library_id=library.library_id,
                status="invalid",
                reason_code="BROKER_SESSION_FIXTURE_METADATA_INCOMPLETE",
                deterministic_replay_ready=False,
                immutable_fixture_store=False,
                diagnostic_context=context,
                explanation="Every broker session fixture must retain immutable storage and replay metadata.",
                remediation="Store fixture digests, replay seeds, timeline ids, correlation logs, artifact manifests, and timestamps for every recorded scenario.",
            )

    return BrokerSessionFixtureReport(
        case_id=case_id,
        library_id=library.library_id,
        status="pass",
        reason_code="BROKER_SESSION_FIXTURE_LIBRARY_COMPLETE",
        deterministic_replay_ready=True,
        immutable_fixture_store=True,
        diagnostic_context=context,
        explanation=(
            "The fixture library covers every required broker scenario and retains immutable "
            "replay metadata for deterministic adapter tests."
        ),
        remediation="No remediation required.",
    )


def validate_broker_semantics_catalog() -> list[str]:
    errors: list[str] = []
    if len(REQUIRED_BROKER_SESSION_SCENARIOS) != len(set(REQUIRED_BROKER_SESSION_SCENARIOS)):
        errors.append("required broker session scenarios must be unique")
    if SUPPORTED_BROKER_DESCRIPTOR_SCHEMA_VERSION.count(".") != 2:
        errors.append("broker descriptor schema version must look like semantic versioning")
    if SUPPORTED_BROKER_FIXTURE_LIBRARY_SCHEMA_VERSION.count(".") != 2:
        errors.append("broker fixture library schema version must look like semantic versioning")
    if not TRADEABLE_LANES:
        errors.append("tradeable lanes must be explicit")
    return errors


VALIDATION_ERRORS = validate_broker_semantics_catalog()
