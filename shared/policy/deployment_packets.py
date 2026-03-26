"""Candidate, readiness, deployment, promotion, and session packet contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.artifact_classes import ArtifactClass, get_artifact_definition
from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.metadata_telemetry import RECORD_DEFINITIONS, StorageClass

SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION = 1


@unique
class PacketStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"
    INCOMPATIBLE = "incompatible"


@unique
class PromotionLane(str, Enum):
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"
    LIVE = "live"


@unique
class ReadinessState(str, Enum):
    FROZEN = "FROZEN"
    PORTABILITY_PENDING = "PORTABILITY_PENDING"
    PORTABILITY_PASSED = "PORTABILITY_PASSED"
    REPLAY_PENDING = "REPLAY_PENDING"
    REPLAY_PASSED = "REPLAY_PASSED"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"
    PAPER_PASSED = "PAPER_PASSED"
    SHADOW_ELIGIBLE = "SHADOW_ELIGIBLE"
    SHADOW_PASSED = "SHADOW_PASSED"
    LIVE_ELIGIBLE = "LIVE_ELIGIBLE"
    RECERT_REQUIRED = "RECERT_REQUIRED"
    SUSPECT = "SUSPECT"
    REVOKED = "REVOKED"


@unique
class DeploymentState(str, Enum):
    PAPER_PENDING = "PAPER_PENDING"
    PAPER_RUNNING = "PAPER_RUNNING"
    SHADOW_PENDING = "SHADOW_PENDING"
    SHADOW_RUNNING = "SHADOW_RUNNING"
    LIVE_CANARY = "LIVE_CANARY"
    LIVE_ACTIVE = "LIVE_ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    CLOSED = "CLOSED"


@unique
class SessionReadinessStatus(str, Enum):
    GREEN = "green"
    BLOCKED = "blocked"
    SUSPECT = "suspect"


@unique
class DiscrepancyStatus(str, Enum):
    CLEAR = "clear"
    BLOCKING = "blocking"


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class CandidateBundle:
    bundle_id: str
    content_hash: str
    strategy_family_id: str
    strategy_subfamily_id: str
    signal_kernel_digest: str
    kernel_abi_version: str
    state_serialization_version: str
    adapter_compatibility_hashes: tuple[str, ...]
    parameterization_digest: str
    product_profile_id: str
    research_symbol: str
    execution_symbol: str
    dataset_release_id: str
    analytic_release_id: str | None
    data_profile_release_id: str
    resolved_context_bundle_id: str
    execution_profile_release_id: str
    dependency_dag_hash: str
    feature_contract_hashes: tuple[str, ...]
    operating_envelope_profile_id: str
    session_conditioned_risk_envelope_id: str | None
    strategy_hard_risk_bounds_digest: str
    eligible_account_class_constraints: tuple[str, ...]
    minimum_capital_usd: int
    minimum_margin_fraction: float
    required_broker_capability_profile_id: str
    portability_policy_declaration: str
    required_evidence_ids: tuple[str, ...]
    compatibility_matrix_version: str
    signature_ids: tuple[str, ...]
    concrete_account_binding_id: str | None = None
    live_data_entitlement_id: str | None = None
    current_fee_schedule_snapshot_id: str | None = None
    current_margin_snapshot_id: str | None = None
    schema_version: int = SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateBundle":
        return cls(
            bundle_id=str(payload["bundle_id"]),
            content_hash=str(payload["content_hash"]),
            strategy_family_id=str(payload["strategy_family_id"]),
            strategy_subfamily_id=str(payload["strategy_subfamily_id"]),
            signal_kernel_digest=str(payload["signal_kernel_digest"]),
            kernel_abi_version=str(payload["kernel_abi_version"]),
            state_serialization_version=str(payload["state_serialization_version"]),
            adapter_compatibility_hashes=tuple(
                str(item) for item in payload["adapter_compatibility_hashes"]
            ),
            parameterization_digest=str(payload["parameterization_digest"]),
            product_profile_id=str(payload["product_profile_id"]),
            research_symbol=str(payload["research_symbol"]),
            execution_symbol=str(payload["execution_symbol"]),
            dataset_release_id=str(payload["dataset_release_id"]),
            analytic_release_id=(
                str(payload["analytic_release_id"])
                if payload.get("analytic_release_id")
                else None
            ),
            data_profile_release_id=str(payload["data_profile_release_id"]),
            resolved_context_bundle_id=str(payload["resolved_context_bundle_id"]),
            execution_profile_release_id=str(payload["execution_profile_release_id"]),
            dependency_dag_hash=str(payload["dependency_dag_hash"]),
            feature_contract_hashes=tuple(str(item) for item in payload["feature_contract_hashes"]),
            operating_envelope_profile_id=str(payload["operating_envelope_profile_id"]),
            session_conditioned_risk_envelope_id=(
                str(payload["session_conditioned_risk_envelope_id"])
                if payload.get("session_conditioned_risk_envelope_id")
                else None
            ),
            strategy_hard_risk_bounds_digest=str(payload["strategy_hard_risk_bounds_digest"]),
            eligible_account_class_constraints=tuple(
                str(item) for item in payload["eligible_account_class_constraints"]
            ),
            minimum_capital_usd=int(payload["minimum_capital_usd"]),
            minimum_margin_fraction=float(payload["minimum_margin_fraction"]),
            required_broker_capability_profile_id=str(
                payload["required_broker_capability_profile_id"]
            ),
            portability_policy_declaration=str(payload["portability_policy_declaration"]),
            required_evidence_ids=tuple(str(item) for item in payload["required_evidence_ids"]),
            compatibility_matrix_version=str(payload["compatibility_matrix_version"]),
            signature_ids=tuple(str(item) for item in payload["signature_ids"]),
            concrete_account_binding_id=(
                str(payload["concrete_account_binding_id"])
                if payload.get("concrete_account_binding_id")
                else None
            ),
            live_data_entitlement_id=(
                str(payload["live_data_entitlement_id"])
                if payload.get("live_data_entitlement_id")
                else None
            ),
            current_fee_schedule_snapshot_id=(
                str(payload["current_fee_schedule_snapshot_id"])
                if payload.get("current_fee_schedule_snapshot_id")
                else None
            ),
            current_margin_snapshot_id=(
                str(payload["current_margin_snapshot_id"])
                if payload.get("current_margin_snapshot_id")
                else None
            ),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "CandidateBundle":
        return cls.from_dict(_decode_json(payload, "candidate_bundle"))


@dataclass(frozen=True)
class BundleReadinessRecord:
    bundle_readiness_record_id: str
    candidate_bundle_id: str
    target_account_binding_id: str
    policy_bundle_hash: str
    account_risk_profile_id: str
    broker_capability_descriptor_id: str
    approved_data_profile_release_id: str
    current_fee_schedule_snapshot_id: str
    current_margin_snapshot_id: str
    freshness_evidence_ids: tuple[str, ...]
    lifecycle_state: ReadinessState
    approval_history_ids: tuple[str, ...]
    schema_version: int = SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BundleReadinessRecord":
        return cls(
            bundle_readiness_record_id=str(payload["bundle_readiness_record_id"]),
            candidate_bundle_id=str(payload["candidate_bundle_id"]),
            target_account_binding_id=str(payload["target_account_binding_id"]),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            account_risk_profile_id=str(payload["account_risk_profile_id"]),
            broker_capability_descriptor_id=str(payload["broker_capability_descriptor_id"]),
            approved_data_profile_release_id=str(payload["approved_data_profile_release_id"]),
            current_fee_schedule_snapshot_id=str(payload["current_fee_schedule_snapshot_id"]),
            current_margin_snapshot_id=str(payload["current_margin_snapshot_id"]),
            freshness_evidence_ids=tuple(str(item) for item in payload["freshness_evidence_ids"]),
            lifecycle_state=ReadinessState(payload["lifecycle_state"]),
            approval_history_ids=tuple(str(item) for item in payload["approval_history_ids"]),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BundleReadinessRecord":
        return cls.from_dict(_decode_json(payload, "bundle_readiness_record"))


@dataclass(frozen=True)
class DeploymentInstance:
    deployment_instance_id: str
    lane: PromotionLane
    target_account_binding_id: str
    candidate_bundle_id: str
    bundle_readiness_record_id: str
    active_promotion_packet_id: str
    session_readiness_packet_ids: tuple[str, ...]
    runtime_sequence_number: int
    operator_action_ids: tuple[str, ...]
    start_event_id: str
    stop_event_id: str | None
    withdrawal_event_id: str | None
    recovery_event_ids: tuple[str, ...]
    lifecycle_state: DeploymentState
    schema_version: int = SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeploymentInstance":
        return cls(
            deployment_instance_id=str(payload["deployment_instance_id"]),
            lane=PromotionLane(payload["lane"]),
            target_account_binding_id=str(payload["target_account_binding_id"]),
            candidate_bundle_id=str(payload["candidate_bundle_id"]),
            bundle_readiness_record_id=str(payload["bundle_readiness_record_id"]),
            active_promotion_packet_id=str(payload["active_promotion_packet_id"]),
            session_readiness_packet_ids=tuple(
                str(item) for item in payload["session_readiness_packet_ids"]
            ),
            runtime_sequence_number=int(payload["runtime_sequence_number"]),
            operator_action_ids=tuple(str(item) for item in payload["operator_action_ids"]),
            start_event_id=str(payload["start_event_id"]),
            stop_event_id=str(payload["stop_event_id"]) if payload.get("stop_event_id") else None,
            withdrawal_event_id=(
                str(payload["withdrawal_event_id"])
                if payload.get("withdrawal_event_id")
                else None
            ),
            recovery_event_ids=tuple(str(item) for item in payload["recovery_event_ids"]),
            lifecycle_state=DeploymentState(payload["lifecycle_state"]),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DeploymentInstance":
        return cls.from_dict(_decode_json(payload, "deployment_instance"))


@dataclass(frozen=True)
class PromotionPacket:
    promotion_packet_id: str
    lane: PromotionLane
    candidate_bundle_id: str
    target_account_binding_id: str
    account_risk_profile_hash: str
    bundle_readiness_record_id: str
    replay_certification_id: str
    portability_certification_id: str
    native_validation_id: str | None
    execution_symbol_tradability_study_id: str
    paper_pass_evidence_id: str | None
    shadow_pass_evidence_id: str | None
    fee_schedule_snapshot_id: str
    margin_snapshot_id: str
    market_data_entitlement_check_id: str
    active_waiver_ids: tuple[str, ...]
    incident_reference_ids: tuple[str, ...]
    policy_bundle_hash: str
    compatibility_matrix_version: str
    signoff_ids: tuple[str, ...]
    evidence_expiry_timestamps_utc: tuple[str, ...]
    signed_packet_hash: str
    schema_version: int = SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PromotionPacket":
        return cls(
            promotion_packet_id=str(payload["promotion_packet_id"]),
            lane=PromotionLane(payload["lane"]),
            candidate_bundle_id=str(payload["candidate_bundle_id"]),
            target_account_binding_id=str(payload["target_account_binding_id"]),
            account_risk_profile_hash=str(payload["account_risk_profile_hash"]),
            bundle_readiness_record_id=str(payload["bundle_readiness_record_id"]),
            replay_certification_id=str(payload["replay_certification_id"]),
            portability_certification_id=str(payload["portability_certification_id"]),
            native_validation_id=(
                str(payload["native_validation_id"])
                if payload.get("native_validation_id")
                else None
            ),
            execution_symbol_tradability_study_id=str(
                payload["execution_symbol_tradability_study_id"]
            ),
            paper_pass_evidence_id=(
                str(payload["paper_pass_evidence_id"])
                if payload.get("paper_pass_evidence_id")
                else None
            ),
            shadow_pass_evidence_id=(
                str(payload["shadow_pass_evidence_id"])
                if payload.get("shadow_pass_evidence_id")
                else None
            ),
            fee_schedule_snapshot_id=str(payload["fee_schedule_snapshot_id"]),
            margin_snapshot_id=str(payload["margin_snapshot_id"]),
            market_data_entitlement_check_id=str(payload["market_data_entitlement_check_id"]),
            active_waiver_ids=tuple(str(item) for item in payload["active_waiver_ids"]),
            incident_reference_ids=tuple(
                str(item) for item in payload["incident_reference_ids"]
            ),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            compatibility_matrix_version=str(payload["compatibility_matrix_version"]),
            signoff_ids=tuple(str(item) for item in payload["signoff_ids"]),
            evidence_expiry_timestamps_utc=tuple(
                str(item) for item in payload["evidence_expiry_timestamps_utc"]
            ),
            signed_packet_hash=str(payload["signed_packet_hash"]),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "PromotionPacket":
        return cls.from_dict(_decode_json(payload, "promotion_packet"))


@dataclass(frozen=True)
class SessionReadinessPacket:
    session_readiness_packet_id: str
    deployment_instance_id: str
    session_id: str
    valid_from_utc: str
    valid_to_utc: str
    source_promotion_packet_id: str
    fee_check_id: str
    margin_check_id: str
    entitlement_check_id: str
    contract_conformance_check_id: str
    backup_freshness_check_id: str
    restore_drill_check_id: str
    clock_health_check_id: str
    secret_health_check_id: str
    unresolved_discrepancy_status: DiscrepancyStatus
    operating_envelope_check_id: str
    session_eligibility_check_id: str
    session_status: SessionReadinessStatus
    blocked_check_ids: tuple[str, ...]
    decision_trace_hash: str
    schema_version: int = SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unresolved_discrepancy_status"] = self.unresolved_discrepancy_status.value
        payload["session_status"] = self.session_status.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionReadinessPacket":
        return cls(
            session_readiness_packet_id=str(payload["session_readiness_packet_id"]),
            deployment_instance_id=str(payload["deployment_instance_id"]),
            session_id=str(payload["session_id"]),
            valid_from_utc=str(payload["valid_from_utc"]),
            valid_to_utc=str(payload["valid_to_utc"]),
            source_promotion_packet_id=str(payload["source_promotion_packet_id"]),
            fee_check_id=str(payload["fee_check_id"]),
            margin_check_id=str(payload["margin_check_id"]),
            entitlement_check_id=str(payload["entitlement_check_id"]),
            contract_conformance_check_id=str(payload["contract_conformance_check_id"]),
            backup_freshness_check_id=str(payload["backup_freshness_check_id"]),
            restore_drill_check_id=str(payload["restore_drill_check_id"]),
            clock_health_check_id=str(payload["clock_health_check_id"]),
            secret_health_check_id=str(payload["secret_health_check_id"]),
            unresolved_discrepancy_status=DiscrepancyStatus(
                payload["unresolved_discrepancy_status"]
            ),
            operating_envelope_check_id=str(payload["operating_envelope_check_id"]),
            session_eligibility_check_id=str(payload["session_eligibility_check_id"]),
            session_status=SessionReadinessStatus(payload["session_status"]),
            blocked_check_ids=tuple(str(item) for item in payload["blocked_check_ids"]),
            decision_trace_hash=str(payload["decision_trace_hash"]),
            schema_version=int(
                payload.get("schema_version", SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION)
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "SessionReadinessPacket":
        return cls.from_dict(_decode_json(payload, "session_readiness_packet"))


@dataclass(frozen=True)
class PacketValidationReport:
    case_id: str
    packet_kind: str
    packet_id: str | None
    status: str
    reason_code: str
    context: dict[str, str | None]
    missing_fields: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class PacketTransitionReport:
    case_id: str
    packet_kind: str
    packet_id: str
    from_state: str
    to_state: str
    status: str
    reason_code: str
    allowed: bool
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


READINESS_ALLOWED_TRANSITIONS: dict[ReadinessState, frozenset[ReadinessState]] = {
    ReadinessState.FROZEN: frozenset(
        {
            ReadinessState.PORTABILITY_PENDING,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.PORTABILITY_PENDING: frozenset(
        {
            ReadinessState.PORTABILITY_PASSED,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.PORTABILITY_PASSED: frozenset(
        {
            ReadinessState.REPLAY_PENDING,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.REPLAY_PENDING: frozenset(
        {
            ReadinessState.REPLAY_PASSED,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.REPLAY_PASSED: frozenset(
        {
            ReadinessState.PAPER_ELIGIBLE,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.PAPER_ELIGIBLE: frozenset(
        {
            ReadinessState.PAPER_PASSED,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.PAPER_PASSED: frozenset(
        {
            ReadinessState.SHADOW_ELIGIBLE,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.SHADOW_ELIGIBLE: frozenset(
        {
            ReadinessState.SHADOW_PASSED,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.SHADOW_PASSED: frozenset(
        {
            ReadinessState.LIVE_ELIGIBLE,
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.LIVE_ELIGIBLE: frozenset(
        {
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.RECERT_REQUIRED: frozenset(
        {
            ReadinessState.PORTABILITY_PENDING,
            ReadinessState.REPLAY_PENDING,
            ReadinessState.SUSPECT,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.SUSPECT: frozenset(
        {
            ReadinessState.RECERT_REQUIRED,
            ReadinessState.REVOKED,
        }
    ),
    ReadinessState.REVOKED: frozenset(),
}

DEPLOYMENT_ALLOWED_TRANSITIONS: dict[DeploymentState, frozenset[DeploymentState]] = {
    DeploymentState.PAPER_PENDING: frozenset(
        {DeploymentState.PAPER_RUNNING, DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.PAPER_RUNNING: frozenset(
        {DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.SHADOW_PENDING: frozenset(
        {DeploymentState.SHADOW_RUNNING, DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.SHADOW_RUNNING: frozenset(
        {DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.LIVE_CANARY: frozenset(
        {DeploymentState.LIVE_ACTIVE, DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.LIVE_ACTIVE: frozenset(
        {DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ),
    DeploymentState.WITHDRAWN: frozenset({DeploymentState.CLOSED}),
    DeploymentState.CLOSED: frozenset(),
}

READINESS_STATES_REQUIRING_APPROVAL = frozenset(
    {
        ReadinessState.PORTABILITY_PASSED,
        ReadinessState.REPLAY_PASSED,
        ReadinessState.PAPER_ELIGIBLE,
        ReadinessState.PAPER_PASSED,
        ReadinessState.SHADOW_ELIGIBLE,
        ReadinessState.SHADOW_PASSED,
        ReadinessState.LIVE_ELIGIBLE,
    }
)

READINESS_STATES_REQUIRING_FRESHNESS = frozenset(
    {
        ReadinessState.PAPER_ELIGIBLE,
        ReadinessState.PAPER_PASSED,
        ReadinessState.SHADOW_ELIGIBLE,
        ReadinessState.SHADOW_PASSED,
        ReadinessState.LIVE_ELIGIBLE,
    }
)

RUNNING_DEPLOYMENT_STATES = frozenset(
    {
        DeploymentState.PAPER_RUNNING,
        DeploymentState.SHADOW_RUNNING,
        DeploymentState.LIVE_CANARY,
        DeploymentState.LIVE_ACTIVE,
    }
)


def _decode_json(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _mentions_digest(identifier: str, digest: str) -> bool:
    return bool(identifier and digest and digest in identifier)


def _normalize_timestamp(value: str) -> str:
    return canonicalize_persisted_timestamp(datetime.datetime.fromisoformat(value)).isoformat()


def _candidate_context(bundle: CandidateBundle) -> dict[str, str | None]:
    return {
        "product_profile_id": bundle.product_profile_id,
        "resolved_context_bundle_id": bundle.resolved_context_bundle_id,
        "execution_profile_release_id": bundle.execution_profile_release_id,
        "compatibility_matrix_version": bundle.compatibility_matrix_version,
    }


def _readiness_context(record: BundleReadinessRecord) -> dict[str, str | None]:
    return {
        "candidate_bundle_id": record.candidate_bundle_id,
        "target_account_binding_id": record.target_account_binding_id,
        "account_risk_profile_id": record.account_risk_profile_id,
        "approved_data_profile_release_id": record.approved_data_profile_release_id,
        "lifecycle_state": record.lifecycle_state.value,
    }


def _deployment_context(instance: DeploymentInstance) -> dict[str, str | None]:
    return {
        "lane": instance.lane.value,
        "candidate_bundle_id": instance.candidate_bundle_id,
        "bundle_readiness_record_id": instance.bundle_readiness_record_id,
        "lifecycle_state": instance.lifecycle_state.value,
    }


def _promotion_context(packet: PromotionPacket) -> dict[str, str | None]:
    return {
        "lane": packet.lane.value,
        "candidate_bundle_id": packet.candidate_bundle_id,
        "bundle_readiness_record_id": packet.bundle_readiness_record_id,
        "target_account_binding_id": packet.target_account_binding_id,
        "compatibility_matrix_version": packet.compatibility_matrix_version,
    }


def _session_context(packet: SessionReadinessPacket) -> dict[str, str | None]:
    return {
        "deployment_instance_id": packet.deployment_instance_id,
        "source_promotion_packet_id": packet.source_promotion_packet_id,
        "session_id": packet.session_id,
        "session_status": packet.session_status.value,
    }


def validate_candidate_bundle(
    case_id: str,
    bundle: CandidateBundle,
) -> PacketValidationReport:
    if bundle.schema_version != SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="CANDIDATE_BUNDLE_SCHEMA_VERSION_UNSUPPORTED",
            context=_candidate_context(bundle),
            missing_fields=(),
            explanation="The candidate bundle uses an unsupported schema version.",
            remediation="Rebuild the candidate bundle with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "bundle_id": bundle.bundle_id,
            "content_hash": bundle.content_hash,
            "strategy_family_id": bundle.strategy_family_id,
            "strategy_subfamily_id": bundle.strategy_subfamily_id,
            "signal_kernel_digest": bundle.signal_kernel_digest,
            "kernel_abi_version": bundle.kernel_abi_version,
            "state_serialization_version": bundle.state_serialization_version,
            "adapter_compatibility_hashes": bundle.adapter_compatibility_hashes,
            "parameterization_digest": bundle.parameterization_digest,
            "product_profile_id": bundle.product_profile_id,
            "research_symbol": bundle.research_symbol,
            "execution_symbol": bundle.execution_symbol,
            "dataset_release_id": bundle.dataset_release_id,
            "data_profile_release_id": bundle.data_profile_release_id,
            "resolved_context_bundle_id": bundle.resolved_context_bundle_id,
            "execution_profile_release_id": bundle.execution_profile_release_id,
            "dependency_dag_hash": bundle.dependency_dag_hash,
            "feature_contract_hashes": bundle.feature_contract_hashes,
            "operating_envelope_profile_id": bundle.operating_envelope_profile_id,
            "strategy_hard_risk_bounds_digest": bundle.strategy_hard_risk_bounds_digest,
            "eligible_account_class_constraints": bundle.eligible_account_class_constraints,
            "required_broker_capability_profile_id": bundle.required_broker_capability_profile_id,
            "portability_policy_declaration": bundle.portability_policy_declaration,
            "required_evidence_ids": bundle.required_evidence_ids,
            "compatibility_matrix_version": bundle.compatibility_matrix_version,
            "signature_ids": bundle.signature_ids,
        }.items()
        if not field_value
    )
    if missing_fields:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="CANDIDATE_BUNDLE_MISSING_REQUIRED_FIELDS",
            context=_candidate_context(bundle),
            missing_fields=missing_fields,
            explanation=(
                "The candidate bundle is missing one or more required frozen strategy, context, "
                f"or signature bindings: {missing_fields}."
            ),
            remediation="Populate every required candidate bundle field before freeze.",
        )

    if not _mentions_digest(bundle.bundle_id, bundle.content_hash):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="CANDIDATE_BUNDLE_NOT_CONTENT_ADDRESSED",
            context=_candidate_context(bundle),
            missing_fields=(),
            explanation=(
                "The candidate bundle identifier does not embed the content hash, so the frozen "
                "bundle is not content-addressed."
            ),
            remediation="Regenerate the bundle identifier from the canonical content hash.",
        )

    if bundle.concrete_account_binding_id:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="CANDIDATE_BUNDLE_CONCRETE_ACCOUNT_BINDING_FORBIDDEN",
            context=_candidate_context(bundle),
            missing_fields=(),
            explanation=(
                "The candidate bundle encodes a concrete account binding, which belongs in the "
                "mutable readiness or promotion layer."
            ),
            remediation="Remove the concrete account binding from the candidate bundle.",
        )

    if any(
        (
            bundle.live_data_entitlement_id,
            bundle.current_fee_schedule_snapshot_id,
            bundle.current_margin_snapshot_id,
        )
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="CANDIDATE_BUNDLE_FRESHNESS_CONTEXT_FORBIDDEN",
            context=_candidate_context(bundle),
            missing_fields=(),
            explanation=(
                "The candidate bundle encodes freshness-sensitive operational context that must "
                "live in readiness, promotion, or session packets instead."
            ),
            remediation=(
                "Remove fee, margin, and entitlement bindings from the candidate bundle."
            ),
        )

    if bundle.minimum_capital_usd <= 0 or not 0 < bundle.minimum_margin_fraction < 1:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="candidate_bundle",
            packet_id=bundle.bundle_id,
            status=PacketStatus.INVALID.value,
            reason_code="CANDIDATE_BUNDLE_ACCOUNT_CONSTRAINTS_INVALID",
            context=_candidate_context(bundle),
            missing_fields=(),
            explanation=(
                "Minimum eligible account capital and margin assumptions must be explicit, "
                "positive, and within a sensible fractional range."
            ),
            remediation="Record positive minimum capital and a margin fraction within (0, 1).",
        )

    return PacketValidationReport(
        case_id=case_id,
        packet_kind="candidate_bundle",
        packet_id=bundle.bundle_id,
        status=PacketStatus.PASS.value,
        reason_code="CANDIDATE_BUNDLE_FROZEN",
        context=_candidate_context(bundle),
        missing_fields=(),
        explanation=(
            "The candidate bundle is immutable, content-addressed, and free of concrete account "
            "or freshness-sensitive operational bindings."
        ),
        remediation="No remediation required.",
    )


def validate_bundle_readiness_record(
    case_id: str,
    record: BundleReadinessRecord,
) -> PacketValidationReport:
    if record.schema_version != SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="bundle_readiness_record",
            packet_id=record.bundle_readiness_record_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="BUNDLE_READINESS_SCHEMA_VERSION_UNSUPPORTED",
            context=_readiness_context(record),
            missing_fields=(),
            explanation="The bundle-readiness record uses an unsupported schema version.",
            remediation="Rebuild the readiness record with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "bundle_readiness_record_id": record.bundle_readiness_record_id,
            "candidate_bundle_id": record.candidate_bundle_id,
            "target_account_binding_id": record.target_account_binding_id,
            "policy_bundle_hash": record.policy_bundle_hash,
            "account_risk_profile_id": record.account_risk_profile_id,
            "broker_capability_descriptor_id": record.broker_capability_descriptor_id,
            "approved_data_profile_release_id": record.approved_data_profile_release_id,
            "current_fee_schedule_snapshot_id": record.current_fee_schedule_snapshot_id,
            "current_margin_snapshot_id": record.current_margin_snapshot_id,
        }.items()
        if not field_value
    )
    if missing_fields:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="bundle_readiness_record",
            packet_id=record.bundle_readiness_record_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="BUNDLE_READINESS_MISSING_REQUIRED_FIELDS",
            context=_readiness_context(record),
            missing_fields=missing_fields,
            explanation=(
                "The bundle-readiness record is missing one or more required mutable admission "
                f"bindings: {missing_fields}."
            ),
            remediation="Populate every required readiness binding before promotion or activation.",
        )

    if (
        record.lifecycle_state in READINESS_STATES_REQUIRING_APPROVAL
        and not record.approval_history_ids
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="bundle_readiness_record",
            packet_id=record.bundle_readiness_record_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="BUNDLE_READINESS_APPROVAL_HISTORY_REQUIRED",
            context=_readiness_context(record),
            missing_fields=(),
            explanation=(
                "Readiness states that declare passed or eligible status must retain explicit "
                "approval history."
            ),
            remediation="Attach approval history before marking the readiness record eligible or passed.",
        )

    if (
        record.lifecycle_state in READINESS_STATES_REQUIRING_FRESHNESS
        and not record.freshness_evidence_ids
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="bundle_readiness_record",
            packet_id=record.bundle_readiness_record_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="BUNDLE_READINESS_FRESHNESS_EVIDENCE_REQUIRED",
            context=_readiness_context(record),
            missing_fields=(),
            explanation=(
                "Promotion-eligible readiness states must bind current freshness-sensitive "
                "evidence explicitly."
            ),
            remediation="Attach the required freshness-bound evidence references before promotion.",
        )

    return PacketValidationReport(
        case_id=case_id,
        packet_kind="bundle_readiness_record",
        packet_id=record.bundle_readiness_record_id,
        status=PacketStatus.PASS.value,
        reason_code="BUNDLE_READINESS_BOUND",
        context=_readiness_context(record),
        missing_fields=(),
        explanation=(
            "The readiness record owns the mutable account, broker, fee, margin, and freshness "
            "bindings that are intentionally absent from the candidate bundle."
        ),
        remediation="No remediation required.",
    )


def transition_bundle_readiness_record(
    case_id: str,
    record: BundleReadinessRecord,
    to_state: ReadinessState,
) -> PacketTransitionReport:
    allowed = to_state in READINESS_ALLOWED_TRANSITIONS[record.lifecycle_state]
    if not allowed:
        return PacketTransitionReport(
            case_id=case_id,
            packet_kind="bundle_readiness_record",
            packet_id=record.bundle_readiness_record_id,
            from_state=record.lifecycle_state.value,
            to_state=to_state.value,
            status=PacketStatus.VIOLATION.value,
            reason_code="BUNDLE_READINESS_INVALID_TRANSITION",
            allowed=False,
            explanation="The requested readiness transition is not part of the canonical state machine.",
            remediation="Advance the readiness record only through the plan-defined transitions.",
        )

    return PacketTransitionReport(
        case_id=case_id,
        packet_kind="bundle_readiness_record",
        packet_id=record.bundle_readiness_record_id,
        from_state=record.lifecycle_state.value,
        to_state=to_state.value,
        status=PacketStatus.PASS.value,
        reason_code="BUNDLE_READINESS_TRANSITION_ALLOWED",
        allowed=True,
        explanation="The readiness transition is allowed by the canonical state machine.",
        remediation="No remediation required.",
    )


def validate_deployment_instance(
    case_id: str,
    instance: DeploymentInstance,
) -> PacketValidationReport:
    if instance.schema_version != SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="DEPLOYMENT_INSTANCE_SCHEMA_VERSION_UNSUPPORTED",
            context=_deployment_context(instance),
            missing_fields=(),
            explanation="The deployment instance uses an unsupported schema version.",
            remediation="Rebuild the deployment instance with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "deployment_instance_id": instance.deployment_instance_id,
            "target_account_binding_id": instance.target_account_binding_id,
            "candidate_bundle_id": instance.candidate_bundle_id,
            "bundle_readiness_record_id": instance.bundle_readiness_record_id,
            "active_promotion_packet_id": instance.active_promotion_packet_id,
            "start_event_id": instance.start_event_id,
        }.items()
        if not field_value
    )
    if missing_fields:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="DEPLOYMENT_INSTANCE_MISSING_REQUIRED_FIELDS",
            context=_deployment_context(instance),
            missing_fields=missing_fields,
            explanation=(
                "The deployment instance is missing one or more required activation bindings: "
                f"{missing_fields}."
            ),
            remediation="Populate every required deployment binding before activation.",
        )

    if instance.runtime_sequence_number < 0:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id,
            status=PacketStatus.INVALID.value,
            reason_code="DEPLOYMENT_INSTANCE_SEQUENCE_NEGATIVE",
            context=_deployment_context(instance),
            missing_fields=(),
            explanation="Runtime sequence numbers must be explicit non-negative integers.",
            remediation="Initialize runtime sequence numbers at zero or higher.",
        )

    lane_allowed_states = {
        PromotionLane.PAPER: frozenset(
            {DeploymentState.PAPER_PENDING, DeploymentState.PAPER_RUNNING}
        ),
        PromotionLane.SHADOW_LIVE: frozenset(
            {DeploymentState.SHADOW_PENDING, DeploymentState.SHADOW_RUNNING}
        ),
        PromotionLane.LIVE: frozenset({DeploymentState.LIVE_CANARY, DeploymentState.LIVE_ACTIVE}),
    }
    if (
        instance.lifecycle_state not in lane_allowed_states[instance.lane]
        and instance.lifecycle_state not in {DeploymentState.WITHDRAWN, DeploymentState.CLOSED}
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id,
            status=PacketStatus.INCOMPATIBLE.value,
            reason_code="DEPLOYMENT_INSTANCE_STATE_LANE_MISMATCH",
            context=_deployment_context(instance),
            missing_fields=(),
            explanation=(
                "The deployment lifecycle state does not match the configured paper, shadow-live, "
                "or live lane."
            ),
            remediation="Use a lifecycle state that belongs to the deployment lane.",
        )

    if (
        instance.lifecycle_state in RUNNING_DEPLOYMENT_STATES
        and not instance.session_readiness_packet_ids
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEPLOYMENT_INSTANCE_SESSION_HISTORY_REQUIRED",
            context=_deployment_context(instance),
            missing_fields=(),
            explanation=(
                "Running or live deployment states must retain session-readiness packet history."
            ),
            remediation="Bind at least one session-readiness packet before marking the deployment active.",
        )

    return PacketValidationReport(
        case_id=case_id,
        packet_kind="deployment_instance",
        packet_id=instance.deployment_instance_id,
        status=PacketStatus.PASS.value,
        reason_code="DEPLOYMENT_INSTANCE_VALID",
        context=_deployment_context(instance),
        missing_fields=(),
        explanation=(
            "The deployment instance keeps mutable activation, operator, and runtime state "
            "separate from the immutable candidate bundle."
        ),
        remediation="No remediation required.",
    )


def transition_deployment_instance(
    case_id: str,
    instance: DeploymentInstance,
    to_state: DeploymentState,
) -> PacketTransitionReport:
    allowed = to_state in DEPLOYMENT_ALLOWED_TRANSITIONS[instance.lifecycle_state]
    if not allowed:
        return PacketTransitionReport(
            case_id=case_id,
            packet_kind="deployment_instance",
            packet_id=instance.deployment_instance_id,
            from_state=instance.lifecycle_state.value,
            to_state=to_state.value,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEPLOYMENT_INSTANCE_INVALID_TRANSITION",
            allowed=False,
            explanation="The requested deployment transition is not part of the canonical state machine.",
            remediation="Advance the deployment only through the plan-defined lifecycle transitions.",
        )

    return PacketTransitionReport(
        case_id=case_id,
        packet_kind="deployment_instance",
        packet_id=instance.deployment_instance_id,
        from_state=instance.lifecycle_state.value,
        to_state=to_state.value,
        status=PacketStatus.PASS.value,
        reason_code="DEPLOYMENT_INSTANCE_TRANSITION_ALLOWED",
        allowed=True,
        explanation="The deployment transition is allowed by the canonical state machine.",
        remediation="No remediation required.",
    )


def validate_promotion_packet(
    case_id: str,
    packet: PromotionPacket,
) -> PacketValidationReport:
    if packet.schema_version != SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="promotion_packet",
            packet_id=packet.promotion_packet_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="PROMOTION_PACKET_SCHEMA_VERSION_UNSUPPORTED",
            context=_promotion_context(packet),
            missing_fields=(),
            explanation="The promotion packet uses an unsupported schema version.",
            remediation="Rebuild the promotion packet with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "promotion_packet_id": packet.promotion_packet_id,
            "candidate_bundle_id": packet.candidate_bundle_id,
            "target_account_binding_id": packet.target_account_binding_id,
            "account_risk_profile_hash": packet.account_risk_profile_hash,
            "bundle_readiness_record_id": packet.bundle_readiness_record_id,
            "replay_certification_id": packet.replay_certification_id,
            "portability_certification_id": packet.portability_certification_id,
            "execution_symbol_tradability_study_id": packet.execution_symbol_tradability_study_id,
            "fee_schedule_snapshot_id": packet.fee_schedule_snapshot_id,
            "margin_snapshot_id": packet.margin_snapshot_id,
            "market_data_entitlement_check_id": packet.market_data_entitlement_check_id,
            "policy_bundle_hash": packet.policy_bundle_hash,
            "compatibility_matrix_version": packet.compatibility_matrix_version,
            "signoff_ids": packet.signoff_ids,
            "signed_packet_hash": packet.signed_packet_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="promotion_packet",
            packet_id=packet.promotion_packet_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="PROMOTION_PACKET_MISSING_REQUIRED_FIELDS",
            context=_promotion_context(packet),
            missing_fields=missing_fields,
            explanation=(
                "The promotion packet is missing one or more required approval bindings: "
                f"{missing_fields}."
            ),
            remediation="Populate every required promotion field before activation preflight.",
        )

    for timestamp in packet.evidence_expiry_timestamps_utc:
        try:
            _normalize_timestamp(timestamp)
        except ValueError:
            return PacketValidationReport(
                case_id=case_id,
                packet_kind="promotion_packet",
                packet_id=packet.promotion_packet_id,
                status=PacketStatus.INVALID.value,
                reason_code="PROMOTION_PACKET_EVIDENCE_EXPIRY_INVALID",
                context=_promotion_context(packet),
                missing_fields=(),
                explanation="Evidence expiry timestamps must be timezone-aware and UTC-normalizable.",
                remediation="Record evidence expiry timestamps as timezone-aware values.",
            )

    if packet.lane == PromotionLane.SHADOW_LIVE and not packet.paper_pass_evidence_id:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="promotion_packet",
            packet_id=packet.promotion_packet_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="PROMOTION_PACKET_PAPER_EVIDENCE_REQUIRED",
            context=_promotion_context(packet),
            missing_fields=(),
            explanation=(
                "Shadow-live promotion requires explicit paper-pass evidence."
            ),
            remediation="Bind paper-pass evidence before promoting into shadow-live.",
        )

    if packet.lane == PromotionLane.LIVE and (
        not packet.paper_pass_evidence_id or not packet.shadow_pass_evidence_id
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="promotion_packet",
            packet_id=packet.promotion_packet_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="PROMOTION_PACKET_LIVE_EVIDENCE_REQUIRED",
            context=_promotion_context(packet),
            missing_fields=(),
            explanation=(
                "Live promotion requires both paper-pass and shadow-pass evidence."
            ),
            remediation="Bind the required paper and shadow evidence before live activation.",
        )

    return PacketValidationReport(
        case_id=case_id,
        packet_kind="promotion_packet",
        packet_id=packet.promotion_packet_id,
        status=PacketStatus.PASS.value,
        reason_code="PROMOTION_PACKET_SIGNED_AND_BOUND",
        context=_promotion_context(packet),
        missing_fields=(),
        explanation=(
            "The promotion packet freezes the exact approval evidence, freshness checks, "
            "account context, and policy bundle required for activation."
        ),
        remediation="No remediation required.",
    )


def validate_session_readiness_packet(
    case_id: str,
    packet: SessionReadinessPacket,
) -> PacketValidationReport:
    if packet.schema_version != SUPPORTED_DEPLOYMENT_PACKET_SCHEMA_VERSION:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="SESSION_PACKET_SCHEMA_VERSION_UNSUPPORTED",
            context=_session_context(packet),
            missing_fields=(),
            explanation="The session-readiness packet uses an unsupported schema version.",
            remediation="Rebuild the session packet with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "session_readiness_packet_id": packet.session_readiness_packet_id,
            "deployment_instance_id": packet.deployment_instance_id,
            "session_id": packet.session_id,
            "valid_from_utc": packet.valid_from_utc,
            "valid_to_utc": packet.valid_to_utc,
            "source_promotion_packet_id": packet.source_promotion_packet_id,
            "fee_check_id": packet.fee_check_id,
            "margin_check_id": packet.margin_check_id,
            "entitlement_check_id": packet.entitlement_check_id,
            "contract_conformance_check_id": packet.contract_conformance_check_id,
            "backup_freshness_check_id": packet.backup_freshness_check_id,
            "restore_drill_check_id": packet.restore_drill_check_id,
            "clock_health_check_id": packet.clock_health_check_id,
            "secret_health_check_id": packet.secret_health_check_id,
            "operating_envelope_check_id": packet.operating_envelope_check_id,
            "session_eligibility_check_id": packet.session_eligibility_check_id,
            "decision_trace_hash": packet.decision_trace_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="SESSION_PACKET_MISSING_REQUIRED_FIELDS",
            context=_session_context(packet),
            missing_fields=missing_fields,
            explanation=(
                "The session-readiness packet is missing one or more required pre-session "
                f"checks or bindings: {missing_fields}."
            ),
            remediation="Populate every required session check and binding field.",
        )

    try:
        valid_from = _normalize_timestamp(packet.valid_from_utc)
        valid_to = _normalize_timestamp(packet.valid_to_utc)
    except ValueError:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id,
            status=PacketStatus.INVALID.value,
            reason_code="SESSION_PACKET_INVALID_VALIDITY_WINDOW",
            context=_session_context(packet),
            missing_fields=(),
            explanation="The session packet validity window must use timezone-aware timestamps.",
            remediation="Record the validity window with timezone-aware UTC-normalizable timestamps.",
        )

    if valid_from >= valid_to:
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id,
            status=PacketStatus.INVALID.value,
            reason_code="SESSION_PACKET_VALIDITY_WINDOW_INVERTED",
            context=_session_context(packet),
            missing_fields=(),
            explanation="The session packet validity window must end after it begins.",
            remediation="Set valid_to_utc later than valid_from_utc.",
        )

    if (
        packet.session_status == SessionReadinessStatus.GREEN
        and packet.unresolved_discrepancy_status != DiscrepancyStatus.CLEAR
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="SESSION_PACKET_GREEN_REQUIRES_CLEAR_DISCREPANCIES",
            context=_session_context(packet),
            missing_fields=(),
            explanation=(
                "A green session-readiness packet cannot coexist with unresolved blocking "
                "reconciliation discrepancies."
            ),
            remediation="Resolve the discrepancy or block the session.",
        )

    if (
        packet.session_status == SessionReadinessStatus.GREEN
        and packet.blocked_check_ids
    ):
        return PacketValidationReport(
            case_id=case_id,
            packet_kind="session_readiness_packet",
            packet_id=packet.session_readiness_packet_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="SESSION_PACKET_GREEN_REQUIRES_ALL_CHECKS_PASSING",
            context=_session_context(packet),
            missing_fields=(),
            explanation=(
                "A green session-readiness packet cannot list blocked checks."
            ),
            remediation="Clear the blocked checks or emit a blocked/suspect session status.",
        )

    return PacketValidationReport(
        case_id=case_id,
        packet_kind="session_readiness_packet",
        packet_id=packet.session_readiness_packet_id,
        status=PacketStatus.PASS.value,
        reason_code="SESSION_PACKET_VALID",
        context=_session_context(packet),
        missing_fields=(),
        explanation=(
            "The session-readiness packet binds one deployment instance to one session window, "
            "one promotion packet, and explicit per-session safety checks."
        ),
        remediation="No remediation required.",
    )


def validate_deployment_packet_contract() -> list[str]:
    errors: list[str] = []

    metadata_index = {definition.record_id: definition for definition in RECORD_DEFINITIONS}
    for record_id in (
        "candidate_bundle",
        "bundle_readiness_record",
        "deployment_instance",
        "promotion_packet",
        "session_readiness_packet",
    ):
        definition = metadata_index.get(record_id)
        if definition is None:
            errors.append(f"{record_id}: missing from canonical metadata registry")
            continue
        if definition.storage_class != StorageClass.CANONICAL_METADATA:
            errors.append(f"{record_id}: must remain canonical metadata")

    candidate_definition = get_artifact_definition("candidate_bundle")
    if candidate_definition.artifact_class != ArtifactClass.INTEGRITY_BOUND:
        errors.append("candidate_bundle: must remain integrity-bound")

    session_definition = get_artifact_definition("session_readiness_packet")
    if session_definition.artifact_class != ArtifactClass.FRESHNESS_BOUND:
        errors.append("session_readiness_packet: must remain freshness-bound")

    return errors


VALIDATION_ERRORS = validate_deployment_packet_contract()
