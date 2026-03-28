"""Recovery, degradation, reconciliation, and restore-drill policy contracts."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.deployment_packets import (
    PacketStatus,
    SessionReadinessPacket,
    SessionReadinessStatus,
    validate_session_readiness_packet,
)


SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be an ISO-8601 timestamp string") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name}: must be timezone-aware")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a non-empty string")
    parsed = value.strip()
    if not parsed:
        raise ValueError(f"{field_name}: must be a non-empty string")
    return parsed


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be boolean")
    return value


def _require_int(
    value: object,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}: must be an integer")
    if minimum is not None and value < minimum:
        qualifier = "positive" if minimum == 1 else f">= {minimum}"
        raise ValueError(f"{field_name}: must be {qualifier}")
    return value


def _require_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name}: must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field_name}: must be finite")
    return parsed


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of strings")
    return tuple(_require_non_empty_string(item, field_name=field_name) for item in value)


def _require_schema_version(value: object, *, field_name: str) -> int:
    parsed = _require_int(value, field_name=field_name, minimum=1)
    if parsed != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        raise ValueError(
            f"{field_name}: unsupported schema version {parsed}; "
            f"expected {SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION}"
        )
    return parsed


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
        raise ValueError(f"{field_name}: must be a valid {description}")
    try:
        return enum_type(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid {description}") from exc


@unique
class RecoveryDisposition(str, Enum):
    NONE = "none"
    HALT = "halt"
    FLATTEN = "flatten"


@unique
class WarmupSource(str, Enum):
    OPERATIONAL_EVIDENCE = "operational_evidence"
    DATASET_RELEASE = "dataset_release"


@unique
class GracefulDrainPolicy(str, Enum):
    DRAIN = "drain"
    CANCEL = "cancel"
    HALT = "halt"


@unique
class DegradationAction(str, Enum):
    ALLOW = "allow"
    RESTRICT = "restrict"
    NO_NEW_OVERNIGHT_CARRY = "no_new_overnight_carry"
    EXIT_ONLY = "exit_only"
    FLATTEN_AND_WITHDRAW = "flatten_and_withdraw"


@unique
class NextSessionEligibility(str, Enum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class RecoveryFenceRequest:
    recovery_run_id: str
    deployment_instance_id: str
    trigger_event_id: str
    entered_recovering_state: bool
    no_new_entries_asserted: bool
    broker_mutations_blocked: bool
    broker_positions_reconciled: bool
    open_orders_reconciled: bool
    order_intent_mappings_repaired: bool
    ambiguity_detected: bool
    ambiguity_disposition: RecoveryDisposition
    snapshot_artifact_id: str
    journal_replay_artifact_id: str
    journal_digest_frontier_id: str
    warmup_source: WarmupSource
    warmup_artifact_id: str
    session_reset_or_material_reconnect: bool
    fresh_session_packet: SessionReadinessPacket | None
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    signed_recovery_hash: str
    schema_version: int = SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ambiguity_disposition"] = self.ambiguity_disposition.value
        payload["warmup_source"] = self.warmup_source.value
        payload["fresh_session_packet"] = (
            self.fresh_session_packet.to_dict()
            if self.fresh_session_packet is not None
            else None
        )
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RecoveryFenceRequest":
        payload = _require_mapping(payload, field_name="recovery_fence_request")
        session_payload = payload.get("fresh_session_packet")
        return cls(
            recovery_run_id=_require_non_empty_string(
                payload["recovery_run_id"],
                field_name="recovery_run_id",
            ),
            deployment_instance_id=_require_non_empty_string(
                payload["deployment_instance_id"],
                field_name="deployment_instance_id",
            ),
            trigger_event_id=_require_non_empty_string(
                payload["trigger_event_id"],
                field_name="trigger_event_id",
            ),
            entered_recovering_state=_require_bool(
                payload["entered_recovering_state"],
                field_name="entered_recovering_state",
            ),
            no_new_entries_asserted=_require_bool(
                payload["no_new_entries_asserted"],
                field_name="no_new_entries_asserted",
            ),
            broker_mutations_blocked=_require_bool(
                payload["broker_mutations_blocked"],
                field_name="broker_mutations_blocked",
            ),
            broker_positions_reconciled=_require_bool(
                payload["broker_positions_reconciled"],
                field_name="broker_positions_reconciled",
            ),
            open_orders_reconciled=_require_bool(
                payload["open_orders_reconciled"],
                field_name="open_orders_reconciled",
            ),
            order_intent_mappings_repaired=_require_bool(
                payload["order_intent_mappings_repaired"],
                field_name="order_intent_mappings_repaired",
            ),
            ambiguity_detected=_require_bool(
                payload["ambiguity_detected"],
                field_name="ambiguity_detected",
            ),
            ambiguity_disposition=RecoveryDisposition(
                _require_enum_value(
                    payload["ambiguity_disposition"],
                    field_name="ambiguity_disposition",
                    enum_type=RecoveryDisposition,
                    description="recovery disposition",
                )
            ),
            snapshot_artifact_id=_require_non_empty_string(
                payload["snapshot_artifact_id"],
                field_name="snapshot_artifact_id",
            ),
            journal_replay_artifact_id=_require_non_empty_string(
                payload["journal_replay_artifact_id"],
                field_name="journal_replay_artifact_id",
            ),
            journal_digest_frontier_id=_require_non_empty_string(
                payload["journal_digest_frontier_id"],
                field_name="journal_digest_frontier_id",
            ),
            warmup_source=WarmupSource(
                _require_enum_value(
                    payload["warmup_source"],
                    field_name="warmup_source",
                    enum_type=WarmupSource,
                    description="warmup source",
                )
            ),
            warmup_artifact_id=_require_non_empty_string(
                payload["warmup_artifact_id"],
                field_name="warmup_artifact_id",
            ),
            session_reset_or_material_reconnect=_require_bool(
                payload["session_reset_or_material_reconnect"]
                ,
                field_name="session_reset_or_material_reconnect",
            ),
            fresh_session_packet=(
                SessionReadinessPacket.from_dict(
                    _require_mapping(
                        session_payload,
                        field_name="fresh_session_packet",
                    )
                )
                if session_payload is not None
                else None
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            signed_recovery_hash=_require_non_empty_string(
                payload["signed_recovery_hash"],
                field_name="signed_recovery_hash",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "RecoveryFenceRequest":
        return cls.from_dict(_decode_json(payload, "recovery_fence_request"))


@dataclass(frozen=True)
class GracefulShutdownRecord:
    shutdown_record_id: str
    deployment_instance_id: str
    stop_new_entries_asserted: bool
    drain_policy: GracefulDrainPolicy
    final_snapshot_artifact_id: str
    journal_barrier_id: str
    journal_digest_frontier_id: str
    shutdown_reason: str
    restart_ready: bool
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    signed_shutdown_hash: str
    schema_version: int = SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["drain_policy"] = self.drain_policy.value
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GracefulShutdownRecord":
        payload = _require_mapping(payload, field_name="graceful_shutdown_record")
        return cls(
            shutdown_record_id=_require_non_empty_string(
                payload["shutdown_record_id"],
                field_name="shutdown_record_id",
            ),
            deployment_instance_id=_require_non_empty_string(
                payload["deployment_instance_id"],
                field_name="deployment_instance_id",
            ),
            stop_new_entries_asserted=_require_bool(
                payload["stop_new_entries_asserted"],
                field_name="stop_new_entries_asserted",
            ),
            drain_policy=GracefulDrainPolicy(
                _require_enum_value(
                    payload["drain_policy"],
                    field_name="drain_policy",
                    enum_type=GracefulDrainPolicy,
                    description="graceful drain policy",
                )
            ),
            final_snapshot_artifact_id=_require_non_empty_string(
                payload["final_snapshot_artifact_id"],
                field_name="final_snapshot_artifact_id",
            ),
            journal_barrier_id=_require_non_empty_string(
                payload["journal_barrier_id"],
                field_name="journal_barrier_id",
            ),
            journal_digest_frontier_id=_require_non_empty_string(
                payload["journal_digest_frontier_id"],
                field_name="journal_digest_frontier_id",
            ),
            shutdown_reason=_require_non_empty_string(
                payload["shutdown_reason"],
                field_name="shutdown_reason",
            ),
            restart_ready=_require_bool(payload["restart_ready"], field_name="restart_ready"),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            signed_shutdown_hash=_require_non_empty_string(
                payload["signed_shutdown_hash"],
                field_name="signed_shutdown_hash",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "GracefulShutdownRecord":
        return cls.from_dict(_decode_json(payload, "graceful_shutdown_record"))


@dataclass(frozen=True)
class DegradationAssessment:
    assessment_id: str
    deployment_instance_id: str
    session_id: str
    market_data_fresh: bool
    stale_quote_rate_bps: int
    bar_parity_healthy: bool
    connection_healthy: bool
    clock_synced: bool
    broker_latency_ms: int
    policy_engine_healthy: bool
    intraday_mismatch_above_tolerance: bool
    proposed_action: DegradationAction
    new_entries_blocked: bool
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    signed_assessment_hash: str
    schema_version: int = SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proposed_action"] = self.proposed_action.value
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DegradationAssessment":
        payload = _require_mapping(payload, field_name="degradation_assessment")
        return cls(
            assessment_id=_require_non_empty_string(
                payload["assessment_id"],
                field_name="assessment_id",
            ),
            deployment_instance_id=_require_non_empty_string(
                payload["deployment_instance_id"],
                field_name="deployment_instance_id",
            ),
            session_id=_require_non_empty_string(payload["session_id"], field_name="session_id"),
            market_data_fresh=_require_bool(
                payload["market_data_fresh"],
                field_name="market_data_fresh",
            ),
            stale_quote_rate_bps=_require_int(
                payload["stale_quote_rate_bps"],
                field_name="stale_quote_rate_bps",
                minimum=0,
            ),
            bar_parity_healthy=_require_bool(
                payload["bar_parity_healthy"],
                field_name="bar_parity_healthy",
            ),
            connection_healthy=_require_bool(
                payload["connection_healthy"],
                field_name="connection_healthy",
            ),
            clock_synced=_require_bool(payload["clock_synced"], field_name="clock_synced"),
            broker_latency_ms=_require_int(
                payload["broker_latency_ms"],
                field_name="broker_latency_ms",
                minimum=0,
            ),
            policy_engine_healthy=_require_bool(
                payload["policy_engine_healthy"],
                field_name="policy_engine_healthy",
            ),
            intraday_mismatch_above_tolerance=_require_bool(
                payload["intraday_mismatch_above_tolerance"]
                ,
                field_name="intraday_mismatch_above_tolerance",
            ),
            proposed_action=DegradationAction(
                _require_enum_value(
                    payload["proposed_action"],
                    field_name="proposed_action",
                    enum_type=DegradationAction,
                    description="degradation action",
                )
            ),
            new_entries_blocked=_require_bool(
                payload["new_entries_blocked"],
                field_name="new_entries_blocked",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            signed_assessment_hash=_require_non_empty_string(
                payload["signed_assessment_hash"],
                field_name="signed_assessment_hash",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DegradationAssessment":
        return cls.from_dict(_decode_json(payload, "degradation_assessment"))


@dataclass(frozen=True)
class LedgerCloseArtifact:
    ledger_close_id: str
    deployment_instance_id: str
    ledger_close_date: str
    authoritative_statement_set_id: str
    as_booked_pnl: float
    as_reconciled_pnl: float
    discrepancy_summary_ids: tuple[str, ...]
    discrepancy_above_tolerance: bool
    reviewed_or_waived: bool
    review_or_waiver_id: str | None
    next_session_eligibility: NextSessionEligibility
    cash_movements_reconciled: bool
    commissions_reconciled: bool
    margin_reconciled: bool
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    signed_ledger_hash: str
    schema_version: int = SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["next_session_eligibility"] = self.next_session_eligibility.value
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LedgerCloseArtifact":
        payload = _require_mapping(payload, field_name="ledger_close_artifact")
        return cls(
            ledger_close_id=_require_non_empty_string(
                payload["ledger_close_id"],
                field_name="ledger_close_id",
            ),
            deployment_instance_id=_require_non_empty_string(
                payload["deployment_instance_id"],
                field_name="deployment_instance_id",
            ),
            ledger_close_date=_require_non_empty_string(
                payload["ledger_close_date"],
                field_name="ledger_close_date",
            ),
            authoritative_statement_set_id=_require_non_empty_string(
                payload["authoritative_statement_set_id"],
                field_name="authoritative_statement_set_id",
            ),
            as_booked_pnl=_require_finite_float(
                payload["as_booked_pnl"],
                field_name="as_booked_pnl",
            ),
            as_reconciled_pnl=_require_finite_float(
                payload["as_reconciled_pnl"],
                field_name="as_reconciled_pnl",
            ),
            discrepancy_summary_ids=_require_string_sequence(
                payload["discrepancy_summary_ids"],
                field_name="discrepancy_summary_ids",
            ),
            discrepancy_above_tolerance=_require_bool(
                payload["discrepancy_above_tolerance"],
                field_name="discrepancy_above_tolerance",
            ),
            reviewed_or_waived=_require_bool(
                payload["reviewed_or_waived"],
                field_name="reviewed_or_waived",
            ),
            review_or_waiver_id=_require_optional_non_empty_string(
                payload.get("review_or_waiver_id"),
                field_name="review_or_waiver_id",
            ),
            next_session_eligibility=NextSessionEligibility(
                _require_enum_value(
                    payload["next_session_eligibility"],
                    field_name="next_session_eligibility",
                    enum_type=NextSessionEligibility,
                    description="next-session eligibility",
                )
            ),
            cash_movements_reconciled=_require_bool(
                payload["cash_movements_reconciled"],
                field_name="cash_movements_reconciled",
            ),
            commissions_reconciled=_require_bool(
                payload["commissions_reconciled"],
                field_name="commissions_reconciled",
            ),
            margin_reconciled=_require_bool(
                payload["margin_reconciled"],
                field_name="margin_reconciled",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            signed_ledger_hash=_require_non_empty_string(
                payload["signed_ledger_hash"],
                field_name="signed_ledger_hash",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "LedgerCloseArtifact":
        return cls.from_dict(_decode_json(payload, "ledger_close_artifact"))


@dataclass(frozen=True)
class RestoreDrillArtifact:
    restore_drill_id: str
    deployment_instance_id: str
    backup_artifact_id: str
    snapshot_artifact_id: str
    journal_barrier_id: str
    journal_digest_frontier_id: str
    off_host_recoverable: bool
    digest_chain_verified: bool
    restored_to_clean_host: bool
    entered_recovering_state: bool
    broker_reconciliation_clean: bool
    reviewed_waiver_id: str | None
    rpo_target_minutes: int
    achieved_rpo_minutes: int
    rto_target_minutes: int
    achieved_rto_minutes: int
    dashboard_visible: bool
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    signed_restore_hash: str
    schema_version: int = SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RestoreDrillArtifact":
        payload = _require_mapping(payload, field_name="restore_drill_artifact")
        return cls(
            restore_drill_id=_require_non_empty_string(
                payload["restore_drill_id"],
                field_name="restore_drill_id",
            ),
            deployment_instance_id=_require_non_empty_string(
                payload["deployment_instance_id"],
                field_name="deployment_instance_id",
            ),
            backup_artifact_id=_require_non_empty_string(
                payload["backup_artifact_id"],
                field_name="backup_artifact_id",
            ),
            snapshot_artifact_id=_require_non_empty_string(
                payload["snapshot_artifact_id"],
                field_name="snapshot_artifact_id",
            ),
            journal_barrier_id=_require_non_empty_string(
                payload["journal_barrier_id"],
                field_name="journal_barrier_id",
            ),
            journal_digest_frontier_id=_require_non_empty_string(
                payload["journal_digest_frontier_id"],
                field_name="journal_digest_frontier_id",
            ),
            off_host_recoverable=_require_bool(
                payload["off_host_recoverable"],
                field_name="off_host_recoverable",
            ),
            digest_chain_verified=_require_bool(
                payload["digest_chain_verified"],
                field_name="digest_chain_verified",
            ),
            restored_to_clean_host=_require_bool(
                payload["restored_to_clean_host"],
                field_name="restored_to_clean_host",
            ),
            entered_recovering_state=_require_bool(
                payload["entered_recovering_state"],
                field_name="entered_recovering_state",
            ),
            broker_reconciliation_clean=_require_bool(
                payload["broker_reconciliation_clean"],
                field_name="broker_reconciliation_clean",
            ),
            reviewed_waiver_id=_require_optional_non_empty_string(
                payload.get("reviewed_waiver_id"),
                field_name="reviewed_waiver_id",
            ),
            rpo_target_minutes=_require_int(
                payload["rpo_target_minutes"],
                field_name="rpo_target_minutes",
                minimum=0,
            ),
            achieved_rpo_minutes=_require_int(
                payload["achieved_rpo_minutes"],
                field_name="achieved_rpo_minutes",
                minimum=0,
            ),
            rto_target_minutes=_require_int(
                payload["rto_target_minutes"],
                field_name="rto_target_minutes",
                minimum=0,
            ),
            achieved_rto_minutes=_require_int(
                payload["achieved_rto_minutes"],
                field_name="achieved_rto_minutes",
                minimum=0,
            ),
            dashboard_visible=_require_bool(
                payload["dashboard_visible"],
                field_name="dashboard_visible",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            signed_restore_hash=_require_non_empty_string(
                payload["signed_restore_hash"],
                field_name="signed_restore_hash",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "RestoreDrillArtifact":
        return cls.from_dict(_decode_json(payload, "restore_drill_artifact"))


@dataclass(frozen=True)
class RecoveryValidationReport:
    case_id: str
    artifact_kind: str
    artifact_id: str | None
    status: str
    reason_code: str
    context: dict[str, Any]
    missing_fields: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RecoveryValidationReport":
        payload = _require_mapping(payload, field_name="recovery_validation_report")
        if "artifact_id" not in payload:
            raise ValueError("artifact_id: field is required")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            artifact_kind=_require_non_empty_string(
                payload["artifact_kind"],
                field_name="artifact_kind",
            ),
            artifact_id=_require_optional_non_empty_string(
                payload.get("artifact_id"),
                field_name="artifact_id",
            ),
            status=_require_enum_value(
                payload["status"],
                field_name="status",
                enum_type=PacketStatus,
                description="packet status",
            ),
            reason_code=_require_non_empty_string(payload["reason_code"], field_name="reason_code"),
            context=_require_mapping(payload["context"], field_name="context"),
            missing_fields=_require_string_sequence(
                payload["missing_fields"],
                field_name="missing_fields",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "RecoveryValidationReport":
        return cls.from_dict(_decode_json(payload, "recovery_validation_report"))


def _recovery_context(request: RecoveryFenceRequest) -> dict[str, Any]:
    context = {
        "deployment_instance_id": request.deployment_instance_id,
        "trigger_event_id": request.trigger_event_id,
        "ambiguity_disposition": request.ambiguity_disposition.value,
        "warmup_source": request.warmup_source.value,
        "correlation_id": request.correlation_id,
    }
    if request.fresh_session_packet is not None:
        context["fresh_session_readiness_packet_id"] = (
            request.fresh_session_packet.session_readiness_packet_id
        )
    return context


def _shutdown_context(record: GracefulShutdownRecord) -> dict[str, Any]:
    return {
        "deployment_instance_id": record.deployment_instance_id,
        "drain_policy": record.drain_policy.value,
        "journal_barrier_id": record.journal_barrier_id,
        "correlation_id": record.correlation_id,
    }


def _degradation_context(assessment: DegradationAssessment) -> dict[str, Any]:
    return {
        "deployment_instance_id": assessment.deployment_instance_id,
        "session_id": assessment.session_id,
        "proposed_action": assessment.proposed_action.value,
        "new_entries_blocked": assessment.new_entries_blocked,
        "correlation_id": assessment.correlation_id,
    }


def _ledger_close_context(artifact: LedgerCloseArtifact) -> dict[str, Any]:
    return {
        "deployment_instance_id": artifact.deployment_instance_id,
        "ledger_close_date": artifact.ledger_close_date,
        "next_session_eligibility": artifact.next_session_eligibility.value,
        "correlation_id": artifact.correlation_id,
    }


def _restore_context(artifact: RestoreDrillArtifact) -> dict[str, Any]:
    return {
        "deployment_instance_id": artifact.deployment_instance_id,
        "backup_artifact_id": artifact.backup_artifact_id,
        "rpo_target_minutes": artifact.rpo_target_minutes,
        "achieved_rpo_minutes": artifact.achieved_rpo_minutes,
        "rto_target_minutes": artifact.rto_target_minutes,
        "achieved_rto_minutes": artifact.achieved_rto_minutes,
        "correlation_id": artifact.correlation_id,
    }


def validate_recovery_fence(
    case_id: str,
    request: RecoveryFenceRequest,
) -> RecoveryValidationReport:
    if request.schema_version != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="RECOVERY_FENCE_SCHEMA_VERSION_UNSUPPORTED",
            context=_recovery_context(request),
            missing_fields=(),
            explanation="The recovery-fence request uses an unsupported schema version.",
            remediation="Rebuild the recovery-fence artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "recovery_run_id": request.recovery_run_id,
            "deployment_instance_id": request.deployment_instance_id,
            "trigger_event_id": request.trigger_event_id,
            "snapshot_artifact_id": request.snapshot_artifact_id,
            "journal_replay_artifact_id": request.journal_replay_artifact_id,
            "journal_digest_frontier_id": request.journal_digest_frontier_id,
            "warmup_artifact_id": request.warmup_artifact_id,
            "correlation_id": request.correlation_id,
            "operator_reason_bundle": request.operator_reason_bundle,
            "signed_recovery_hash": request.signed_recovery_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="RECOVERY_FENCE_MISSING_REQUIRED_FIELDS",
            context=_recovery_context(request),
            missing_fields=missing_fields,
            explanation=(
                "Recovery requires explicit snapshot, journal, warm-up, correlation, and signed-artifact references."
            ),
            remediation="Populate the missing recovery-fence fields before allowing the workflow to continue.",
        )

    if not request.entered_recovering_state:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_RECOVERING_STATE_REQUIRED",
            context=_recovery_context(request),
            missing_fields=(),
            explanation="Restart and reconnect handling must enter RECOVERING before runtime may evaluate resume safety.",
            remediation="Enter RECOVERING first, then rerun the recovery fence checks.",
        )

    if not request.no_new_entries_asserted:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_NO_NEW_ENTRIES_REQUIRED",
            context=_recovery_context(request),
            missing_fields=(),
            explanation="RECOVERING must block new entries until broker, state, and readiness checks are coherent again.",
            remediation="Assert the no-new-entries fence before attempting restart or reconnect recovery.",
        )

    if not request.broker_mutations_blocked:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_BROKER_MUTATION_FENCE_REQUIRED",
            context=_recovery_context(request),
            missing_fields=(),
            explanation="Broker mutations must stay fenced until reconciliation and state repair finish.",
            remediation="Keep submit/modify/cancel/flatten paths fenced while recovery is in progress.",
        )

    if not (
        request.broker_positions_reconciled
        and request.open_orders_reconciled
        and request.order_intent_mappings_repaired
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_RECONCILIATION_REQUIRED",
            context=_recovery_context(request),
            missing_fields=(),
            explanation=(
                "Recovery must reconcile broker positions and open orders and repair durable order-intent mappings before resume."
            ),
            remediation="Finish reconciliation and durable mapping repair before resuming runtime activity.",
        )

    if (
        request.ambiguity_detected
        and request.ambiguity_disposition
        not in (RecoveryDisposition.HALT, RecoveryDisposition.FLATTEN)
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_AMBIGUOUS_STATE_REQUIRES_SAFE_DISPOSITION",
            context=_recovery_context(request),
            missing_fields=("ambiguity_disposition",),
            explanation="Ambiguous recovery paths must escalate to halt or flatten rather than silent resume.",
            remediation="Record a halt or flatten disposition for the ambiguous recovery state.",
        )

    if request.session_reset_or_material_reconnect and request.fresh_session_packet is None:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="recovery_fence",
            artifact_id=request.recovery_run_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RECOVERY_FENCE_SESSION_PACKET_REQUIRED_AFTER_RESET",
            context=_recovery_context(request),
            missing_fields=("fresh_session_packet",),
            explanation=(
                "A broker daily reset or material reconnect requires a fresh green session-readiness packet before entries may resume."
            ),
            remediation="Issue and attach a fresh session-readiness packet for the active session.",
        )

    if request.fresh_session_packet is not None:
        packet_report = validate_session_readiness_packet(
            case_id,
            request.fresh_session_packet,
        )
        if packet_report.status != PacketStatus.PASS.value:
            return RecoveryValidationReport(
                case_id=case_id,
                artifact_kind="recovery_fence",
                artifact_id=request.recovery_run_id,
                status=PacketStatus.VIOLATION.value,
                reason_code="RECOVERY_FENCE_RESUME_REQUIRES_GREEN_SESSION_PACKET",
                context=_recovery_context(request),
                missing_fields=packet_report.missing_fields,
                explanation="Recovery cannot resume entries with an invalid or blocked session-readiness packet.",
                remediation="Repair the session packet and attach a fresh green session artifact.",
            )
        if request.fresh_session_packet.session_status != SessionReadinessStatus.GREEN:
            return RecoveryValidationReport(
                case_id=case_id,
                artifact_kind="recovery_fence",
                artifact_id=request.recovery_run_id,
                status=PacketStatus.VIOLATION.value,
                reason_code="RECOVERY_FENCE_RESUME_REQUIRES_GREEN_SESSION_PACKET",
                context=_recovery_context(request),
                missing_fields=("fresh_session_packet.session_status",),
                explanation="Recovery resume requires a green session-readiness packet, not a blocked or suspect one.",
                remediation="Attach a fresh green session packet before resuming entries.",
            )
        if request.fresh_session_packet.deployment_instance_id != request.deployment_instance_id:
            return RecoveryValidationReport(
                case_id=case_id,
                artifact_kind="recovery_fence",
                artifact_id=request.recovery_run_id,
                status=PacketStatus.VIOLATION.value,
                reason_code="RECOVERY_FENCE_SESSION_BINDING_MISMATCH",
                context=_recovery_context(request),
                missing_fields=("fresh_session_packet.deployment_instance_id",),
                explanation="The attached session packet must bind to the same deployment instance being recovered.",
                remediation="Reissue the session packet against the active deployment instance.",
            )

    return RecoveryValidationReport(
        case_id=case_id,
        artifact_kind="recovery_fence",
        artifact_id=request.recovery_run_id,
        status=PacketStatus.PASS.value,
        reason_code="RECOVERY_FENCE_RECOVERING_AND_GOVERNED",
        context=_recovery_context(request),
        missing_fields=(),
        explanation=(
            "Recovery entered RECOVERING, fenced new risk and broker mutations, reconciled state, repaired order-intent mappings, and attached fresh session evidence when required."
        ),
        remediation="No remediation required.",
    )


def validate_graceful_shutdown(
    case_id: str,
    record: GracefulShutdownRecord,
) -> RecoveryValidationReport:
    if record.schema_version != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="graceful_shutdown",
            artifact_id=record.shutdown_record_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="GRACEFUL_SHUTDOWN_SCHEMA_VERSION_UNSUPPORTED",
            context=_shutdown_context(record),
            missing_fields=(),
            explanation="The graceful-shutdown record uses an unsupported schema version.",
            remediation="Rebuild the shutdown artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "shutdown_record_id": record.shutdown_record_id,
            "deployment_instance_id": record.deployment_instance_id,
            "final_snapshot_artifact_id": record.final_snapshot_artifact_id,
            "journal_barrier_id": record.journal_barrier_id,
            "journal_digest_frontier_id": record.journal_digest_frontier_id,
            "shutdown_reason": record.shutdown_reason,
            "correlation_id": record.correlation_id,
            "operator_reason_bundle": record.operator_reason_bundle,
            "signed_shutdown_hash": record.signed_shutdown_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="graceful_shutdown",
            artifact_id=record.shutdown_record_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="GRACEFUL_SHUTDOWN_MISSING_REQUIRED_FIELDS",
            context=_shutdown_context(record),
            missing_fields=missing_fields,
            explanation="Graceful shutdown requires final snapshot, journal barrier, digest frontier, and signed reason metadata.",
            remediation="Populate the missing shutdown fields before claiming restart readiness.",
        )

    if not record.stop_new_entries_asserted:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="graceful_shutdown",
            artifact_id=record.shutdown_record_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="GRACEFUL_SHUTDOWN_ENTRY_FENCE_REQUIRED",
            context=_shutdown_context(record),
            missing_fields=(),
            explanation="Graceful shutdown must stop new entries before draining or cancelling outstanding intents.",
            remediation="Assert the new-entry fence before beginning shutdown.",
        )

    if not record.restart_ready:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="graceful_shutdown",
            artifact_id=record.shutdown_record_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="GRACEFUL_SHUTDOWN_RESTART_ARTIFACTS_REQUIRED",
            context=_shutdown_context(record),
            missing_fields=(),
            explanation="Shutdown is not restart-safe until the final snapshot, barrier, and digest frontier are persisted and verified.",
            remediation="Persist and verify the final restart artifacts before marking shutdown complete.",
        )

    return RecoveryValidationReport(
        case_id=case_id,
        artifact_kind="graceful_shutdown",
        artifact_id=record.shutdown_record_id,
        status=PacketStatus.PASS.value,
        reason_code="GRACEFUL_SHUTDOWN_PERSISTED_FOR_RESTART",
        context=_shutdown_context(record),
        missing_fields=(),
        explanation="Graceful shutdown fenced entries, recorded the final snapshot and journal barrier, and preserved restart-safe artifacts.",
        remediation="No remediation required.",
    )


def validate_degradation_assessment(
    case_id: str,
    assessment: DegradationAssessment,
) -> RecoveryValidationReport:
    if assessment.schema_version != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="DEGRADATION_SCHEMA_VERSION_UNSUPPORTED",
            context=_degradation_context(assessment),
            missing_fields=(),
            explanation="The degradation assessment uses an unsupported schema version.",
            remediation="Rebuild the degradation artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "assessment_id": assessment.assessment_id,
            "deployment_instance_id": assessment.deployment_instance_id,
            "session_id": assessment.session_id,
            "correlation_id": assessment.correlation_id,
            "operator_reason_bundle": assessment.operator_reason_bundle,
            "signed_assessment_hash": assessment.signed_assessment_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="DEGRADATION_MISSING_REQUIRED_FIELDS",
            context=_degradation_context(assessment),
            missing_fields=missing_fields,
            explanation="Degradation actions require explicit correlation, reason bundles, and signed decision artifacts.",
            remediation="Populate the missing degradation-assessment fields.",
        )

    if (
        assessment.proposed_action
        in (DegradationAction.EXIT_ONLY, DegradationAction.FLATTEN_AND_WITHDRAW)
        and not assessment.new_entries_blocked
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEGRADATION_ENTRY_BLOCK_REQUIRED",
            context=_degradation_context(assessment),
            missing_fields=(),
            explanation="Exit-only and flatten-and-withdraw postures must block new entries immediately.",
            remediation="Assert the new-entry block when selecting an exit-only or flatten posture.",
        )

    if assessment.intraday_mismatch_above_tolerance and assessment.proposed_action not in (
        DegradationAction.EXIT_ONLY,
        DegradationAction.FLATTEN_AND_WITHDRAW,
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEGRADATION_MISMATCH_REQUIRES_STRONG_ACTION",
            context=_degradation_context(assessment),
            missing_fields=(),
            explanation="An unexplained broker-state mismatch above tolerance must block new risk and escalate beyond simple restriction.",
            remediation="Use exit-only or flatten-and-withdraw until reconciliation is reviewed or resolved.",
        )

    severe_signals = (
        not assessment.connection_healthy
        or not assessment.clock_synced
        or not assessment.policy_engine_healthy
    )
    if severe_signals and assessment.proposed_action not in (
        DegradationAction.EXIT_ONLY,
        DegradationAction.FLATTEN_AND_WITHDRAW,
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEGRADATION_SEVERE_SIGNAL_REQUIRES_STRONG_ACTION",
            context=_degradation_context(assessment),
            missing_fields=(),
            explanation="Connection, clock, and policy-engine failures require an exit-only or flatten posture.",
            remediation="Escalate the degradation action to exit-only or flatten-and-withdraw.",
        )

    moderate_signals = (
        (not assessment.market_data_fresh)
        or assessment.stale_quote_rate_bps > 50
        or (not assessment.bar_parity_healthy)
        or assessment.broker_latency_ms > 1000
    )
    if moderate_signals and assessment.proposed_action == DegradationAction.ALLOW:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="degradation_assessment",
            artifact_id=assessment.assessment_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="DEGRADATION_MODERATE_SIGNAL_REQUIRES_RESTRICTION",
            context=_degradation_context(assessment),
            missing_fields=(),
            explanation="Moderate freshness, latency, or parity drift cannot remain in an unrestricted allow posture.",
            remediation="Raise the posture to restrict, no-new-overnight-carry, exit-only, or flatten-and-withdraw.",
        )

    return RecoveryValidationReport(
        case_id=case_id,
        artifact_kind="degradation_assessment",
        artifact_id=assessment.assessment_id,
        status=PacketStatus.PASS.value,
        reason_code="DEGRADATION_ACTION_MATCHES_SIGNAL_SEVERITY",
        context=_degradation_context(assessment),
        missing_fields=(),
        explanation="The proposed degradation posture matches the observed freshness, parity, latency, connectivity, and reconciliation signals.",
        remediation="No remediation required.",
    )


def validate_ledger_close(
    case_id: str,
    artifact: LedgerCloseArtifact,
) -> RecoveryValidationReport:
    if artifact.schema_version != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="ledger_close",
            artifact_id=artifact.ledger_close_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="LEDGER_CLOSE_SCHEMA_VERSION_UNSUPPORTED",
            context=_ledger_close_context(artifact),
            missing_fields=(),
            explanation="The ledger-close artifact uses an unsupported schema version.",
            remediation="Rebuild the ledger-close artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "ledger_close_id": artifact.ledger_close_id,
            "deployment_instance_id": artifact.deployment_instance_id,
            "ledger_close_date": artifact.ledger_close_date,
            "authoritative_statement_set_id": artifact.authoritative_statement_set_id,
            "correlation_id": artifact.correlation_id,
            "operator_reason_bundle": artifact.operator_reason_bundle,
            "signed_ledger_hash": artifact.signed_ledger_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="ledger_close",
            artifact_id=artifact.ledger_close_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="LEDGER_CLOSE_MISSING_REQUIRED_FIELDS",
            context=_ledger_close_context(artifact),
            missing_fields=missing_fields,
            explanation="Ledger close requires the authoritative statement set, correlation metadata, and a signed summary artifact.",
            remediation="Populate the missing ledger-close fields before finalizing next-session eligibility.",
        )

    if artifact.reviewed_or_waived and not artifact.review_or_waiver_id:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="ledger_close",
            artifact_id=artifact.ledger_close_id,
            status=PacketStatus.INVALID.value,
            reason_code="LEDGER_CLOSE_REVIEW_REFERENCE_REQUIRED",
            context=_ledger_close_context(artifact),
            missing_fields=("review_or_waiver_id",),
            explanation="A reviewed or waived ledger discrepancy must retain the corresponding review or waiver identifier.",
            remediation="Attach the review or waiver reference before marking the discrepancy governed.",
        )

    if not (
        artifact.cash_movements_reconciled
        and artifact.commissions_reconciled
        and artifact.margin_reconciled
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="ledger_close",
            artifact_id=artifact.ledger_close_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="LEDGER_CLOSE_AUTHORITATIVE_RECONCILIATION_REQUIRED",
            context=_ledger_close_context(artifact),
            missing_fields=(),
            explanation="End-of-day close is incomplete until cash, fees, and margin reconcile to the broker statement set.",
            remediation="Complete authoritative statement reconciliation before issuing next-session eligibility.",
        )

    if (
        artifact.discrepancy_above_tolerance
        and not artifact.reviewed_or_waived
        and artifact.next_session_eligibility == NextSessionEligibility.ELIGIBLE
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="ledger_close",
            artifact_id=artifact.ledger_close_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="LEDGER_CLOSE_REVIEW_OR_WAIVER_REQUIRED",
            context=_ledger_close_context(artifact),
            missing_fields=("review_or_waiver_id",),
            explanation="A discrepancy above tolerance must block or remain under review until a documented review or waiver exists.",
            remediation="Keep next-session eligibility blocked or review-required until the discrepancy is reviewed or waived.",
        )

    return RecoveryValidationReport(
        case_id=case_id,
        artifact_kind="ledger_close",
        artifact_id=artifact.ledger_close_id,
        status=PacketStatus.PASS.value,
        reason_code="LEDGER_CLOSE_ELIGIBILITY_GOVERNED",
        context=_ledger_close_context(artifact),
        missing_fields=(),
        explanation="Ledger close reconciled the authoritative broker statement set and issued a governed next-session eligibility decision.",
        remediation="No remediation required.",
    )


def validate_restore_drill(
    case_id: str,
    artifact: RestoreDrillArtifact,
) -> RecoveryValidationReport:
    if artifact.schema_version != SUPPORTED_RUNTIME_RECOVERY_SCHEMA_VERSION:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="RESTORE_DRILL_SCHEMA_VERSION_UNSUPPORTED",
            context=_restore_context(artifact),
            missing_fields=(),
            explanation="The restore-drill artifact uses an unsupported schema version.",
            remediation="Rebuild the restore-drill artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "restore_drill_id": artifact.restore_drill_id,
            "deployment_instance_id": artifact.deployment_instance_id,
            "backup_artifact_id": artifact.backup_artifact_id,
            "snapshot_artifact_id": artifact.snapshot_artifact_id,
            "journal_barrier_id": artifact.journal_barrier_id,
            "journal_digest_frontier_id": artifact.journal_digest_frontier_id,
            "correlation_id": artifact.correlation_id,
            "operator_reason_bundle": artifact.operator_reason_bundle,
            "signed_restore_hash": artifact.signed_restore_hash,
        }.items()
        if not field_value
    )
    if missing_fields:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id or None,
            status=PacketStatus.INVALID.value,
            reason_code="RESTORE_DRILL_MISSING_REQUIRED_FIELDS",
            context=_restore_context(artifact),
            missing_fields=missing_fields,
            explanation="Restore drills require backup, snapshot, digest, correlation, and signed artifact references.",
            remediation="Populate the missing restore-drill fields before certifying recoverability.",
        )

    if not artifact.off_host_recoverable:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RESTORE_DRILL_OFF_HOST_RECOVERY_REQUIRED",
            context=_restore_context(artifact),
            missing_fields=(),
            explanation="Live-capable backup evidence must be independently recoverable off-host.",
            remediation="Use an off-host recoverable backup or checkpoint source for the restore drill.",
        )

    if not artifact.digest_chain_verified:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RESTORE_DRILL_DIGEST_CHAIN_REQUIRED",
            context=_restore_context(artifact),
            missing_fields=(),
            explanation="Restore drills must verify the snapshot and journal digest chain before re-entering RECOVERING.",
            remediation="Verify the hash chain and digest frontier before accepting the restore result.",
        )

    if not (artifact.restored_to_clean_host and artifact.entered_recovering_state):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RESTORE_DRILL_RECOVERY_ENTRY_REQUIRED",
            context=_restore_context(artifact),
            missing_fields=(),
            explanation="A valid restore drill must rebuild to a clean host and re-enter RECOVERING.",
            remediation="Repeat the restore drill on a clean host and record the RECOVERING transition.",
        )

    if not artifact.broker_reconciliation_clean and not artifact.reviewed_waiver_id:
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RESTORE_DRILL_RECONCILIATION_REVIEW_REQUIRED",
            context=_restore_context(artifact),
            missing_fields=("reviewed_waiver_id",),
            explanation="A restore drill cannot claim safe resume after a dirty broker reconciliation without a reviewed waiver.",
            remediation="Review the reconciliation failure or attach the explicit waiver before certifying the drill.",
        )

    if (
        artifact.achieved_rpo_minutes > artifact.rpo_target_minutes
        or artifact.achieved_rto_minutes > artifact.rto_target_minutes
        or not artifact.dashboard_visible
    ):
        return RecoveryValidationReport(
            case_id=case_id,
            artifact_kind="restore_drill",
            artifact_id=artifact.restore_drill_id,
            status=PacketStatus.VIOLATION.value,
            reason_code="RESTORE_DRILL_RPO_RTO_VISIBILITY_REQUIRED",
            context=_restore_context(artifact),
            missing_fields=(),
            explanation="Restore drills must meet RPO/RTO targets and expose the latest results on the operator dashboard.",
            remediation="Bring the drill within target and publish the result to the operator-facing visibility surface.",
        )

    return RecoveryValidationReport(
        case_id=case_id,
        artifact_kind="restore_drill",
        artifact_id=artifact.restore_drill_id,
        status=PacketStatus.PASS.value,
        reason_code="RESTORE_DRILL_RECOVERABLE_AND_GOVERNED",
        context=_restore_context(artifact),
        missing_fields=(),
        explanation="The restore drill used off-host evidence, verified digest integrity, re-entered RECOVERING, and governed resume safety with reconciliation and RPO/RTO evidence.",
        remediation="No remediation required.",
    )


def validate_runtime_recovery_contract() -> list[str]:
    errors: list[str] = []

    if GracefulDrainPolicy.HALT.value == DegradationAction.FLATTEN_AND_WITHDRAW.value:
        errors.append("graceful shutdown and degradation actions must remain distinct")

    if NextSessionEligibility.ELIGIBLE.value == NextSessionEligibility.BLOCKED.value:
        errors.append("next-session eligibility states must be unique")

    return errors


VALIDATION_ERRORS = validate_runtime_recovery_contract()
