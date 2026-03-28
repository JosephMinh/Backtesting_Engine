"""Operational runtime module-boundary and deterministic state-ownership contract."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _normalize_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of objects")
    return tuple(_require_mapping(item, field_name=field_name) for item in value)


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
        raise ValueError(f"{field_name} must be a valid {description}")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid {description}") from exc


def _require_enum_sequence(
    value: object,
    *,
    field_name: str,
    enum_type: type[Enum],
    description: str,
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of {description} values")
    return tuple(
        _require_enum_value(
            item,
            field_name=field_name,
            enum_type=enum_type,
            description=description,
        )
        for item in value
    )


def _require_report_status(value: object, *, field_name: str) -> str:
    return _require_enum_value(
        value,
        field_name=field_name,
        enum_type=RuntimeReportStatus,
        description="runtime report status",
    )


@unique
class RuntimeProcess(str, Enum):
    OPSD = "opsd"
    GUARDIAN = "guardian"
    WATCHDOG = "watchdog"
    BROKER_GATEWAY = "broker_gateway"


@unique
class RuntimeModuleId(str, Enum):
    MARKET_DATA = "market_data"
    STRATEGY_RUNNER = "strategy_runner"
    RISK = "risk"
    BROKER = "broker"
    STATE_STORE = "state_store"
    RECONCILIATION = "reconciliation"
    OPS_HTTP = "ops_http"
    GUARDIAN = "guardian"
    WATCHDOG = "watchdog"
    BROKER_GATEWAY = "broker_gateway"


@unique
class RuntimeStateSurface(str, Enum):
    NORMALIZED_MARKET_STATE = "normalized_market_state"
    BUNDLE_DECISION_STATE = "bundle_decision_state"
    TRADING_ELIGIBILITY_STATE = "trading_eligibility_state"
    EXPOSURE_STATE = "exposure_state"
    ORDERS = "orders"
    POSITIONS = "positions"
    FILLS = "fills"
    ORDER_INTENT_MAPPINGS = "order_intent_mappings"
    BROKER_SESSION_STATE = "broker_session_state"
    READINESS_STATE = "readiness_state"
    RECONCILIATION_STATE = "reconciliation_state"
    SNAPSHOT_STORAGE = "snapshot_storage"
    APPEND_ONLY_JOURNAL = "append_only_journal"
    CONTROL_ACTION_EVIDENCE = "control_action_evidence"


@unique
class RuntimeControlAction(str, Enum):
    HALT_NEW_ORDERS = "halt_new_orders"
    ASSERT_KILL_SWITCH = "assert_kill_switch"
    CANCEL_OPEN_ORDERS = "cancel_open_orders"
    FLATTEN_POSITIONS = "flatten_positions"
    MARK_SESSION_NOT_READY = "mark_session_not_ready"
    PUBLISH_SESSION_READINESS_PACKET = "publish_session_readiness_packet"
    EMERGENCY_CANCEL_OPEN_ORDERS = "emergency_cancel_open_orders"
    EMERGENCY_FLATTEN_POSITIONS = "emergency_flatten_positions"
    RESTART_OPSD = "restart_opsd"
    RESTART_GUARDIAN = "restart_guardian"
    RESTART_BROKER_GATEWAY = "restart_broker_gateway"


@unique
class RuntimeReportStatus(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"
    INVALID = "invalid"


@dataclass(frozen=True)
class RuntimeModuleBoundary:
    module_id: RuntimeModuleId
    process: RuntimeProcess
    title: str
    responsibilities: tuple[str, ...]
    owned_state_surfaces: tuple[RuntimeStateSurface, ...]
    allowed_control_actions: tuple[RuntimeControlAction, ...]
    supervision_targets: tuple[RuntimeProcess, ...] = ()
    separate_process_required: bool = False
    emits_correlated_logs: bool = True
    plan_section: str = "10.7/10.8"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id.value,
            "process": self.process.value,
            "title": self.title,
            "responsibilities": list(self.responsibilities),
            "owned_state_surfaces": [surface.value for surface in self.owned_state_surfaces],
            "allowed_control_actions": [action.value for action in self.allowed_control_actions],
            "supervision_targets": [process.value for process in self.supervision_targets],
            "separate_process_required": self.separate_process_required,
            "emits_correlated_logs": self.emits_correlated_logs,
            "plan_section": self.plan_section,
        }


@dataclass(frozen=True)
class RuntimeStateOwnershipReport:
    case_id: str
    state_surface: str
    claimant_module: str
    owner_module: str
    status: str
    reason_code: str
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "state_surface": self.state_surface,
            "claimant_module": self.claimant_module,
            "owner_module": self.owner_module,
            "status": self.status,
            "reason_code": self.reason_code,
            "diagnostic_context": self.diagnostic_context,
            "explanation": self.explanation,
            "remediation": self.remediation,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeStateOwnershipReport":
        payload = _require_mapping(payload, field_name="runtime_state_ownership_report")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            state_surface=_require_enum_value(
                payload["state_surface"],
                field_name="state_surface",
                enum_type=RuntimeStateSurface,
                description="runtime state surface",
            ),
            claimant_module=_require_enum_value(
                payload["claimant_module"],
                field_name="claimant_module",
                enum_type=RuntimeModuleId,
                description="runtime module id",
            ),
            owner_module=_require_enum_value(
                payload["owner_module"],
                field_name="owner_module",
                enum_type=RuntimeModuleId,
                description="runtime module id",
            ),
            status=_require_report_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            diagnostic_context=_require_mapping(
                payload["diagnostic_context"],
                field_name="diagnostic_context",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_timestamp(payload.get("timestamp"), field_name="timestamp"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "RuntimeStateOwnershipReport":
        return cls.from_dict(_decode_json_object(payload, label="runtime_state_ownership_report"))


@dataclass(frozen=True)
class ControlActionRequest:
    case_id: str
    action: RuntimeControlAction
    requested_by: RuntimeModuleId
    authorization_token_present: bool = False
    independent_broker_connectivity_verified: bool = False
    high_priority_lane_available: bool = False
    target_deployment_instance_id: str | None = None
    target_order_intent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "action": self.action.value,
            "requested_by": self.requested_by.value,
            "authorization_token_present": self.authorization_token_present,
            "independent_broker_connectivity_verified": (
                self.independent_broker_connectivity_verified
            ),
            "high_priority_lane_available": self.high_priority_lane_available,
            "target_deployment_instance_id": self.target_deployment_instance_id,
            "target_order_intent_id": self.target_order_intent_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ControlActionRequest":
        payload = _require_mapping(payload, field_name="control_action_request")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            action=RuntimeControlAction(
                _require_enum_value(
                    payload["action"],
                    field_name="action",
                    enum_type=RuntimeControlAction,
                    description="runtime control action",
                )
            ),
            requested_by=RuntimeModuleId(
                _require_enum_value(
                    payload["requested_by"],
                    field_name="requested_by",
                    enum_type=RuntimeModuleId,
                    description="runtime module id",
                )
            ),
            authorization_token_present=_require_bool(
                payload.get("authorization_token_present", False),
                field_name="authorization_token_present",
            ),
            independent_broker_connectivity_verified=_require_bool(
                payload.get("independent_broker_connectivity_verified", False),
                field_name="independent_broker_connectivity_verified",
            ),
            high_priority_lane_available=_require_bool(
                payload.get("high_priority_lane_available", False),
                field_name="high_priority_lane_available",
            ),
            target_deployment_instance_id=_require_optional_non_empty_string(
                payload.get("target_deployment_instance_id"),
                field_name="target_deployment_instance_id",
            ),
            target_order_intent_id=_require_optional_non_empty_string(
                payload.get("target_order_intent_id"),
                field_name="target_order_intent_id",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ControlActionRequest":
        decoded = _decode_json_object(payload, label="control_action_request")
        return cls.from_dict(decoded)


@dataclass(frozen=True)
class ControlActionAuthorityReport:
    case_id: str
    action: str
    requested_by: str
    owner_module: str
    status: str
    reason_code: str
    allowed: bool
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "action": self.action,
            "requested_by": self.requested_by,
            "owner_module": self.owner_module,
            "status": self.status,
            "reason_code": self.reason_code,
            "allowed": self.allowed,
            "diagnostic_context": self.diagnostic_context,
            "explanation": self.explanation,
            "remediation": self.remediation,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ControlActionAuthorityReport":
        payload = _require_mapping(payload, field_name="control_action_authority_report")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            action=_require_enum_value(
                payload["action"],
                field_name="action",
                enum_type=RuntimeControlAction,
                description="runtime control action",
            ),
            requested_by=_require_enum_value(
                payload["requested_by"],
                field_name="requested_by",
                enum_type=RuntimeModuleId,
                description="runtime module id",
            ),
            owner_module=_require_enum_value(
                payload["owner_module"],
                field_name="owner_module",
                enum_type=RuntimeModuleId,
                description="runtime module id",
            ),
            status=_require_report_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            allowed=_require_bool(payload["allowed"], field_name="allowed"),
            diagnostic_context=_require_mapping(
                payload["diagnostic_context"],
                field_name="diagnostic_context",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_timestamp(payload.get("timestamp"), field_name="timestamp"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ControlActionAuthorityReport":
        return cls.from_dict(_decode_json_object(payload, label="control_action_authority_report"))


@dataclass(frozen=True)
class RuntimeTraceEvent:
    module_id: RuntimeModuleId
    event_type: str
    correlation_id: str
    decision_trace_id: str
    artifact_manifest_id: str
    high_priority_lane: bool
    sequence_number: int
    state_surface: RuntimeStateSurface | None = None
    control_action: RuntimeControlAction | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "module_id": self.module_id.value,
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "decision_trace_id": self.decision_trace_id,
            "artifact_manifest_id": self.artifact_manifest_id,
            "high_priority_lane": self.high_priority_lane,
            "sequence_number": self.sequence_number,
        }
        if self.state_surface is not None:
            payload["state_surface"] = self.state_surface.value
        if self.control_action is not None:
            payload["control_action"] = self.control_action.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeTraceEvent":
        payload = _require_mapping(payload, field_name="runtime_trace_event")
        return cls(
            module_id=RuntimeModuleId(
                _require_enum_value(
                    payload["module_id"],
                    field_name="module_id",
                    enum_type=RuntimeModuleId,
                    description="runtime module id",
                )
            ),
            event_type=_require_non_empty_string(payload["event_type"], field_name="event_type"),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            decision_trace_id=_require_non_empty_string(
                payload["decision_trace_id"],
                field_name="decision_trace_id",
            ),
            artifact_manifest_id=_require_non_empty_string(
                payload["artifact_manifest_id"],
                field_name="artifact_manifest_id",
            ),
            high_priority_lane=_require_bool(
                payload["high_priority_lane"],
                field_name="high_priority_lane",
            ),
            sequence_number=_require_int(
                payload["sequence_number"],
                field_name="sequence_number",
            ),
            state_surface=(
                RuntimeStateSurface(
                    _require_enum_value(
                        payload["state_surface"],
                        field_name="state_surface",
                        enum_type=RuntimeStateSurface,
                        description="runtime state surface",
                    )
                )
                if payload.get("state_surface") is not None
                else None
            ),
            control_action=(
                RuntimeControlAction(
                    _require_enum_value(
                        payload["control_action"],
                        field_name="control_action",
                        enum_type=RuntimeControlAction,
                        description="runtime control action",
                    )
                )
                if payload.get("control_action") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class SupervisionTraceBundle:
    path_kind: str
    required_processes: tuple[RuntimeProcess, ...]
    events: tuple[RuntimeTraceEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_kind": self.path_kind,
            "required_processes": [process.value for process in self.required_processes],
            "events": [event.to_dict() for event in self.events],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SupervisionTraceBundle":
        payload = _require_mapping(payload, field_name="supervision_trace_bundle")
        return cls(
            path_kind=_require_non_empty_string(payload["path_kind"], field_name="path_kind"),
            required_processes=tuple(
                RuntimeProcess(process)
                for process in _require_enum_sequence(
                    payload["required_processes"],
                    field_name="required_processes",
                    enum_type=RuntimeProcess,
                    description="runtime process",
                )
            ),
            events=tuple(
                RuntimeTraceEvent.from_dict(item)
                for item in _require_object_sequence(
                    payload["events"],
                    field_name="events",
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "SupervisionTraceBundle":
        decoded = _decode_json_object(payload, label="supervision_trace_bundle")
        return cls.from_dict(decoded)


@dataclass(frozen=True)
class SupervisionTraceReport:
    case_id: str
    path_kind: str
    status: str
    reason_code: str
    correlated: bool
    diagnostic_context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path_kind": self.path_kind,
            "status": self.status,
            "reason_code": self.reason_code,
            "correlated": self.correlated,
            "diagnostic_context": self.diagnostic_context,
            "explanation": self.explanation,
            "remediation": self.remediation,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SupervisionTraceReport":
        payload = _require_mapping(payload, field_name="supervision_trace_report")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            path_kind=_require_non_empty_string(payload["path_kind"], field_name="path_kind"),
            status=_require_report_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            correlated=_require_bool(payload["correlated"], field_name="correlated"),
            diagnostic_context=_require_mapping(
                payload["diagnostic_context"],
                field_name="diagnostic_context",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_timestamp(payload.get("timestamp"), field_name="timestamp"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "SupervisionTraceReport":
        return cls.from_dict(_decode_json_object(payload, label="supervision_trace_report"))


RUNTIME_MODULES: tuple[RuntimeModuleBoundary, ...] = (
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.MARKET_DATA,
        process=RuntimeProcess.OPSD,
        title="opsd.market_data",
        responsibilities=(
            "Own the latest normalized market state.",
            "Publish market-state updates to bounded internal mailboxes.",
        ),
        owned_state_surfaces=(RuntimeStateSurface.NORMALIZED_MARKET_STATE,),
        allowed_control_actions=(),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.STRATEGY_RUNNER,
        process=RuntimeProcess.OPSD,
        title="opsd.strategy_runner",
        responsibilities=(
            "Own per-bundle decision state.",
            "Translate approved bundle state into order intents without mutating broker state.",
        ),
        owned_state_surfaces=(RuntimeStateSurface.BUNDLE_DECISION_STATE,),
        allowed_control_actions=(),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.RISK,
        process=RuntimeProcess.OPSD,
        title="opsd.risk",
        responsibilities=(
            "Own trading eligibility and exposure state.",
            "Assert kill-switch and trade-halt decisions before trading becomes active.",
        ),
        owned_state_surfaces=(
            RuntimeStateSurface.TRADING_ELIGIBILITY_STATE,
            RuntimeStateSurface.EXPOSURE_STATE,
        ),
        allowed_control_actions=(
            RuntimeControlAction.HALT_NEW_ORDERS,
            RuntimeControlAction.ASSERT_KILL_SWITCH,
        ),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.BROKER,
        process=RuntimeProcess.OPSD,
        title="opsd.broker",
        responsibilities=(
            "Own order-intent to broker-order mappings and broker-session state.",
            "Own routine order, fill, and position state used by the live lane.",
        ),
        owned_state_surfaces=(
            RuntimeStateSurface.ORDERS,
            RuntimeStateSurface.POSITIONS,
            RuntimeStateSurface.FILLS,
            RuntimeStateSurface.ORDER_INTENT_MAPPINGS,
            RuntimeStateSurface.BROKER_SESSION_STATE,
        ),
        allowed_control_actions=(
            RuntimeControlAction.CANCEL_OPEN_ORDERS,
            RuntimeControlAction.FLATTEN_POSITIONS,
        ),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.STATE_STORE,
        process=RuntimeProcess.OPSD,
        title="opsd.state_store",
        responsibilities=(
            "Own snapshots and the append-only journal.",
            "Preserve runtime evidence for replay, recovery, and audit.",
        ),
        owned_state_surfaces=(
            RuntimeStateSurface.SNAPSHOT_STORAGE,
            RuntimeStateSurface.APPEND_ONLY_JOURNAL,
        ),
        allowed_control_actions=(),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.RECONCILIATION,
        process=RuntimeProcess.OPSD,
        title="opsd.reconciliation",
        responsibilities=(
            "Own mismatch assessments, ledger-close assembly, and readiness evidence.",
            "Coordinate session-readiness publication with risk and broker checks.",
        ),
        owned_state_surfaces=(
            RuntimeStateSurface.READINESS_STATE,
            RuntimeStateSurface.RECONCILIATION_STATE,
        ),
        allowed_control_actions=(
            RuntimeControlAction.MARK_SESSION_NOT_READY,
            RuntimeControlAction.PUBLISH_SESSION_READINESS_PACKET,
        ),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.OPS_HTTP,
        process=RuntimeProcess.OPSD,
        title="opsd.ops_http",
        responsibilities=(
            "Expose operator and automation ingress for opsd.",
            "Relay requests into authoritative internal modules without owning economic state.",
        ),
        owned_state_surfaces=(),
        allowed_control_actions=(),
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.GUARDIAN,
        process=RuntimeProcess.GUARDIAN,
        title="guardian",
        responsibilities=(
            "Independently verify broker connectivity.",
            "Execute authorized emergency cancel/flatten actions without owning strategy state.",
        ),
        owned_state_surfaces=(RuntimeStateSurface.CONTROL_ACTION_EVIDENCE,),
        allowed_control_actions=(
            RuntimeControlAction.EMERGENCY_CANCEL_OPEN_ORDERS,
            RuntimeControlAction.EMERGENCY_FLATTEN_POSITIONS,
        ),
        separate_process_required=True,
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.WATCHDOG,
        process=RuntimeProcess.WATCHDOG,
        title="watchdog",
        responsibilities=(
            "Supervise opsd, guardian, and the broker gateway process.",
            "Escalate restart actions without taking ownership of trading state.",
        ),
        owned_state_surfaces=(),
        allowed_control_actions=(
            RuntimeControlAction.RESTART_OPSD,
            RuntimeControlAction.RESTART_GUARDIAN,
            RuntimeControlAction.RESTART_BROKER_GATEWAY,
        ),
        supervision_targets=(
            RuntimeProcess.OPSD,
            RuntimeProcess.GUARDIAN,
            RuntimeProcess.BROKER_GATEWAY,
        ),
        separate_process_required=True,
    ),
    RuntimeModuleBoundary(
        module_id=RuntimeModuleId.BROKER_GATEWAY,
        process=RuntimeProcess.BROKER_GATEWAY,
        title="broker_gateway",
        responsibilities=(
            "Provide supervised broker connectivity.",
            "Remain separately supervised from opsd and guardian.",
        ),
        owned_state_surfaces=(),
        allowed_control_actions=(),
        separate_process_required=True,
    ),
)

_MODULE_INDEX: dict[RuntimeModuleId, RuntimeModuleBoundary] = {
    boundary.module_id: boundary for boundary in RUNTIME_MODULES
}

RUNTIME_STATE_OWNERSHIP: dict[RuntimeStateSurface, RuntimeModuleId] = {
    RuntimeStateSurface.NORMALIZED_MARKET_STATE: RuntimeModuleId.MARKET_DATA,
    RuntimeStateSurface.BUNDLE_DECISION_STATE: RuntimeModuleId.STRATEGY_RUNNER,
    RuntimeStateSurface.TRADING_ELIGIBILITY_STATE: RuntimeModuleId.RISK,
    RuntimeStateSurface.EXPOSURE_STATE: RuntimeModuleId.RISK,
    RuntimeStateSurface.ORDERS: RuntimeModuleId.BROKER,
    RuntimeStateSurface.POSITIONS: RuntimeModuleId.BROKER,
    RuntimeStateSurface.FILLS: RuntimeModuleId.BROKER,
    RuntimeStateSurface.ORDER_INTENT_MAPPINGS: RuntimeModuleId.BROKER,
    RuntimeStateSurface.BROKER_SESSION_STATE: RuntimeModuleId.BROKER,
    RuntimeStateSurface.READINESS_STATE: RuntimeModuleId.RECONCILIATION,
    RuntimeStateSurface.RECONCILIATION_STATE: RuntimeModuleId.RECONCILIATION,
    RuntimeStateSurface.SNAPSHOT_STORAGE: RuntimeModuleId.STATE_STORE,
    RuntimeStateSurface.APPEND_ONLY_JOURNAL: RuntimeModuleId.STATE_STORE,
    RuntimeStateSurface.CONTROL_ACTION_EVIDENCE: RuntimeModuleId.GUARDIAN,
}

ACTION_OWNER_MODULES: dict[RuntimeControlAction, RuntimeModuleId] = {
    RuntimeControlAction.HALT_NEW_ORDERS: RuntimeModuleId.RISK,
    RuntimeControlAction.ASSERT_KILL_SWITCH: RuntimeModuleId.RISK,
    RuntimeControlAction.CANCEL_OPEN_ORDERS: RuntimeModuleId.BROKER,
    RuntimeControlAction.FLATTEN_POSITIONS: RuntimeModuleId.BROKER,
    RuntimeControlAction.MARK_SESSION_NOT_READY: RuntimeModuleId.RECONCILIATION,
    RuntimeControlAction.PUBLISH_SESSION_READINESS_PACKET: RuntimeModuleId.RECONCILIATION,
    RuntimeControlAction.EMERGENCY_CANCEL_OPEN_ORDERS: RuntimeModuleId.GUARDIAN,
    RuntimeControlAction.EMERGENCY_FLATTEN_POSITIONS: RuntimeModuleId.GUARDIAN,
    RuntimeControlAction.RESTART_OPSD: RuntimeModuleId.WATCHDOG,
    RuntimeControlAction.RESTART_GUARDIAN: RuntimeModuleId.WATCHDOG,
    RuntimeControlAction.RESTART_BROKER_GATEWAY: RuntimeModuleId.WATCHDOG,
}

HIGH_PRIORITY_CONTROL_ACTIONS: frozenset[RuntimeControlAction] = frozenset(
    {
        RuntimeControlAction.CANCEL_OPEN_ORDERS,
        RuntimeControlAction.FLATTEN_POSITIONS,
        RuntimeControlAction.MARK_SESSION_NOT_READY,
        RuntimeControlAction.PUBLISH_SESSION_READINESS_PACKET,
        RuntimeControlAction.EMERGENCY_CANCEL_OPEN_ORDERS,
        RuntimeControlAction.EMERGENCY_FLATTEN_POSITIONS,
    }
)


def runtime_module_ids() -> list[str]:
    return [boundary.module_id.value for boundary in RUNTIME_MODULES]


def boundary_for_module(module_id: RuntimeModuleId) -> RuntimeModuleBoundary:
    return _MODULE_INDEX[module_id]


def owner_for_state_surface(surface: RuntimeStateSurface) -> RuntimeModuleId:
    return RUNTIME_STATE_OWNERSHIP[surface]


def evaluate_state_ownership(
    case_id: str,
    state_surface: RuntimeStateSurface,
    claimant_module: RuntimeModuleId,
) -> RuntimeStateOwnershipReport:
    owner_module = owner_for_state_surface(state_surface)
    context = {
        "state_surface": state_surface.value,
        "claimant_module": claimant_module.value,
        "owner_module": owner_module.value,
        "claimant_process": boundary_for_module(claimant_module).process.value,
        "owner_process": boundary_for_module(owner_module).process.value,
    }
    if claimant_module == owner_module:
        return RuntimeStateOwnershipReport(
            case_id=case_id,
            state_surface=state_surface.value,
            claimant_module=claimant_module.value,
            owner_module=owner_module.value,
            status="pass",
            reason_code="OPERATIONAL_RUNTIME_STATE_OWNER_CONFIRMED",
            diagnostic_context=context,
            explanation=(
                "The claimant matches the canonical single-writer owner for the requested "
                "runtime state surface."
            ),
            remediation="No remediation required.",
        )

    return RuntimeStateOwnershipReport(
        case_id=case_id,
        state_surface=state_surface.value,
        claimant_module=claimant_module.value,
        owner_module=owner_module.value,
        status="violation",
        reason_code="OPERATIONAL_RUNTIME_STATE_OWNER_MISMATCH",
        diagnostic_context=context,
        explanation=(
            "The claimant does not match the canonical single-writer owner for the requested "
            "runtime state surface."
        ),
        remediation="Route writes through the authoritative owner and consume every other view as read-only.",
    )


def evaluate_control_action_authority(
    request: ControlActionRequest,
) -> ControlActionAuthorityReport:
    owner_module = ACTION_OWNER_MODULES[request.action]
    context = {
        "action": request.action.value,
        "requested_by": request.requested_by.value,
        "owner_module": owner_module.value,
        "authorization_token_present": request.authorization_token_present,
        "independent_broker_connectivity_verified": (
            request.independent_broker_connectivity_verified
        ),
        "high_priority_lane_available": request.high_priority_lane_available,
        "target_deployment_instance_id": request.target_deployment_instance_id,
        "target_order_intent_id": request.target_order_intent_id,
    }

    if request.requested_by != owner_module:
        return ControlActionAuthorityReport(
            case_id=request.case_id,
            action=request.action.value,
            requested_by=request.requested_by.value,
            owner_module=owner_module.value,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_ACTION_OWNER_MISMATCH",
            allowed=False,
            diagnostic_context=context,
            explanation=(
                "The requested module is not the canonical owner for this control action."
            ),
            remediation="Send the action through the authoritative module instead of bypassing ownership boundaries.",
        )

    if request.action in {
        RuntimeControlAction.EMERGENCY_CANCEL_OPEN_ORDERS,
        RuntimeControlAction.EMERGENCY_FLATTEN_POSITIONS,
    } and not request.authorization_token_present:
        return ControlActionAuthorityReport(
            case_id=request.case_id,
            action=request.action.value,
            requested_by=request.requested_by.value,
            owner_module=owner_module.value,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_GUARDIAN_AUTH_REQUIRED",
            allowed=False,
            diagnostic_context=context,
            explanation=(
                "Guardian emergency actions require explicit independent authorization before "
                "they can bypass the primary control plane."
            ),
            remediation="Attach an explicit guardian authorization token before issuing emergency cancel/flatten.",
        )

    if request.action in {
        RuntimeControlAction.EMERGENCY_CANCEL_OPEN_ORDERS,
        RuntimeControlAction.EMERGENCY_FLATTEN_POSITIONS,
    } and not request.independent_broker_connectivity_verified:
        return ControlActionAuthorityReport(
            case_id=request.case_id,
            action=request.action.value,
            requested_by=request.requested_by.value,
            owner_module=owner_module.value,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_GUARDIAN_CONNECTIVITY_PROOF_REQUIRED",
            allowed=False,
            diagnostic_context=context,
            explanation=(
                "Guardian may only execute emergency actions after it independently verifies "
                "broker connectivity."
            ),
            remediation="Require guardian to prove broker connectivity before executing emergency cancel/flatten.",
        )

    if request.action in HIGH_PRIORITY_CONTROL_ACTIONS and not request.high_priority_lane_available:
        return ControlActionAuthorityReport(
            case_id=request.case_id,
            action=request.action.value,
            requested_by=request.requested_by.value,
            owner_module=owner_module.value,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_HIGH_PRIORITY_LANE_REQUIRED",
            allowed=False,
            diagnostic_context=context,
            explanation=(
                "Cancel, flatten, and reconciliation work must use the reserved high-priority lane."
            ),
            remediation="Route the action through the reserved high-priority lane before declaring it admissible.",
        )

    return ControlActionAuthorityReport(
        case_id=request.case_id,
        action=request.action.value,
        requested_by=request.requested_by.value,
        owner_module=owner_module.value,
        status="pass",
        reason_code="OPERATIONAL_RUNTIME_ACTION_AUTHORIZED",
        allowed=True,
        diagnostic_context=context,
        explanation="The request uses the authoritative owner and satisfies the required runtime controls.",
        remediation="No remediation required.",
    )


def validate_supervision_trace_bundle(
    case_id: str,
    bundle: SupervisionTraceBundle,
) -> SupervisionTraceReport:
    if not bundle.events:
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="invalid",
            reason_code="OPERATIONAL_RUNTIME_TRACE_BUNDLE_EMPTY",
            correlated=False,
            diagnostic_context={"required_processes": [p.value for p in bundle.required_processes]},
            explanation="A supervision trace bundle must contain at least one event.",
            remediation="Capture at least one correlated event before evaluating the supervision path.",
        )

    observed_processes = {
        boundary_for_module(event.module_id).process for event in bundle.events
    }
    missing_processes = set(bundle.required_processes).difference(observed_processes)
    context = {
        "required_processes": [process.value for process in bundle.required_processes],
        "observed_processes": sorted(process.value for process in observed_processes),
        "event_count": len(bundle.events),
    }

    if missing_processes:
        context["missing_processes"] = sorted(process.value for process in missing_processes)
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_TRACE_PROCESS_MISSING",
            correlated=False,
            diagnostic_context=context,
            explanation=(
                "The supervision path is missing one or more required runtime processes."
            ),
            remediation="Capture correlated events from every required process before trusting the supervision path.",
        )

    correlation_ids = {event.correlation_id for event in bundle.events}
    if len(correlation_ids) != 1:
        context["correlation_ids"] = sorted(correlation_ids)
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_TRACE_CORRELATION_MISMATCH",
            correlated=False,
            diagnostic_context=context,
            explanation="The supervision path emitted multiple correlation ids instead of one shared thread.",
            remediation="Thread opsd, guardian, and watchdog events through a single correlation id.",
        )

    decision_trace_ids = {event.decision_trace_id for event in bundle.events}
    if len(decision_trace_ids) != 1:
        context["decision_trace_ids"] = sorted(decision_trace_ids)
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_TRACE_DECISION_TRACE_MISMATCH",
            correlated=False,
            diagnostic_context=context,
            explanation="The supervision path emitted multiple decision traces instead of one reviewable story.",
            remediation="Keep the same decision trace id across opsd, guardian, and watchdog events.",
        )

    if any(not event.artifact_manifest_id for event in bundle.events):
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="invalid",
            reason_code="OPERATIONAL_RUNTIME_TRACE_ARTIFACT_MANIFEST_REQUIRED",
            correlated=False,
            diagnostic_context=context,
            explanation="Every supervision-path event must reference a retained artifact manifest.",
            remediation="Attach an artifact manifest id to every correlated supervision event.",
        )

    if any(
        event.control_action in HIGH_PRIORITY_CONTROL_ACTIONS and not event.high_priority_lane
        for event in bundle.events
    ):
        return SupervisionTraceReport(
            case_id=case_id,
            path_kind=bundle.path_kind,
            status="violation",
            reason_code="OPERATIONAL_RUNTIME_TRACE_HIGH_PRIORITY_LANE_REQUIRED",
            correlated=False,
            diagnostic_context=context,
            explanation=(
                "Cancel, flatten, and reconciliation events in the supervision path must remain "
                "on the reserved high-priority lane."
            ),
            remediation="Re-emit the supervision path with high-priority lanes for cancel, flatten, and reconciliation work.",
        )

    context["correlation_id"] = next(iter(correlation_ids))
    context["decision_trace_id"] = next(iter(decision_trace_ids))
    return SupervisionTraceReport(
        case_id=case_id,
        path_kind=bundle.path_kind,
        status="pass",
        reason_code="OPERATIONAL_RUNTIME_TRACE_BUNDLE_CORRELATED",
        correlated=True,
        diagnostic_context=context,
        explanation=(
            "The supervision path keeps opsd, watchdog, and guardian events on one correlated "
            "decision trace with retained artifacts."
        ),
        remediation="No remediation required.",
    )


def _validate_contract() -> list[str]:
    errors: list[str] = []

    if len(_MODULE_INDEX) != len(RUNTIME_MODULES):
        errors.append("runtime module ids must be unique")

    if set(RUNTIME_STATE_OWNERSHIP) != set(RuntimeStateSurface):
        missing = set(RuntimeStateSurface).difference(RUNTIME_STATE_OWNERSHIP)
        extra = set(RUNTIME_STATE_OWNERSHIP).difference(set(RuntimeStateSurface))
        if missing:
            errors.append(
                "runtime state ownership missing surfaces: "
                + ", ".join(sorted(surface.value for surface in missing))
            )
        if extra:
            errors.append(
                "runtime state ownership has unknown surfaces: "
                + ", ".join(sorted(surface.value for surface in extra))
            )

    for surface, owner in RUNTIME_STATE_OWNERSHIP.items():
        if surface not in _MODULE_INDEX[owner].owned_state_surfaces:
            errors.append(
                f"{owner.value} must list {surface.value} in its owned_state_surfaces"
            )

    for action, owner in ACTION_OWNER_MODULES.items():
        if action not in _MODULE_INDEX[owner].allowed_control_actions:
            errors.append(f"{owner.value} must list {action.value} in its allowed_control_actions")

    guardian = _MODULE_INDEX[RuntimeModuleId.GUARDIAN]
    if guardian.owned_state_surfaces != (RuntimeStateSurface.CONTROL_ACTION_EVIDENCE,):
        errors.append("guardian may only own emergency control-action evidence")
    if not guardian.separate_process_required:
        errors.append("guardian must remain a separate process from opsd")

    watchdog = _MODULE_INDEX[RuntimeModuleId.WATCHDOG]
    if watchdog.owned_state_surfaces:
        errors.append("watchdog must not own economically significant state")
    if set(watchdog.supervision_targets) != {
        RuntimeProcess.OPSD,
        RuntimeProcess.GUARDIAN,
        RuntimeProcess.BROKER_GATEWAY,
    }:
        errors.append("watchdog must supervise opsd, guardian, and broker_gateway")

    if _MODULE_INDEX[RuntimeModuleId.OPS_HTTP].owned_state_surfaces:
        errors.append("ops_http must not own authoritative runtime state")

    return errors


VALIDATION_ERRORS = _validate_contract()
