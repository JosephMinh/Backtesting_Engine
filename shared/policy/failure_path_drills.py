"""Failure-path end-to-end drill contracts for safety-critical runtime scenarios."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.deployment_packets import PacketStatus
from shared.policy.readiness_revocation import (
    DependencyPropagationRequest,
    EmergencyWithdrawalReviewRequest,
    evaluate_dependency_propagation,
    evaluate_emergency_withdrawal_review,
)
from shared.policy.runtime_recovery import (
    DegradationAssessment,
    GracefulShutdownRecord,
    LedgerCloseArtifact,
    RecoveryFenceRequest,
    RestoreDrillArtifact,
    validate_degradation_assessment,
    validate_graceful_shutdown,
    validate_ledger_close,
    validate_recovery_fence,
    validate_restore_drill,
)


SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION = 1


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


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of strings")
    return tuple(_require_non_empty_string(item, field_name=field_name) for item in value)


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of objects")
    return tuple(_require_mapping(item, field_name=field_name) for item in value)


def _require_schema_version(value: object, *, field_name: str) -> int:
    parsed = _require_int(value, field_name=field_name, minimum=1)
    if parsed != SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION:
        raise ValueError(
            f"{field_name}: unsupported schema version {parsed}; "
            f"expected {SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION}"
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
class FailurePathScenario(str, Enum):
    RECONNECT_BEFORE_ACK = "reconnect_before_ack"
    DEGRADED_DATA = "degraded_data"
    DEPENDENCY_REVOCATION = "dependency_revocation"
    RECONCILIATION_FAILURE = "reconciliation_failure"
    RESTORE_AFTER_HOST_LOSS = "restore_after_host_loss"
    SAFE_STOP = "safe_stop"


@unique
class SafeOutcome(str, Enum):
    HALT_BEFORE_MUTATION = "halt_before_mutation"
    EXIT_ONLY = "exit_only"
    WITHDRAW_AND_REVIEW = "withdraw_and_review"
    NEXT_SESSION_BLOCKED = "next_session_blocked"
    REMAIN_HALTED_UNTIL_REVIEW = "remain_halted_until_review"
    RESTART_ARTIFACTS_PERSISTED = "restart_artifacts_persisted"


@dataclass(frozen=True)
class DrillTimelineEvent:
    sequence_number: int
    event_id: str
    event_type: str
    correlation_id: str
    referenced_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    reason_code: str
    declared_safe_outcome: SafeOutcome | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["declared_safe_outcome"] = (
            self.declared_safe_outcome.value
            if self.declared_safe_outcome is not None
            else None
        )
        return _jsonable(payload)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DrillTimelineEvent":
        payload = _require_mapping(payload, field_name="drill_timeline_event")
        return cls(
            sequence_number=_require_int(
                payload["sequence_number"],
                field_name="sequence_number",
                minimum=1,
            ),
            event_id=_require_non_empty_string(payload["event_id"], field_name="event_id"),
            event_type=_require_non_empty_string(payload["event_type"], field_name="event_type"),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            referenced_ids=_require_string_sequence(
                payload["referenced_ids"],
                field_name="referenced_ids",
            ),
            artifact_ids=_require_string_sequence(
                payload["artifact_ids"],
                field_name="artifact_ids",
            ),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            declared_safe_outcome=(
                SafeOutcome(
                    _require_enum_value(
                        payload["declared_safe_outcome"],
                        field_name="declared_safe_outcome",
                        enum_type=SafeOutcome,
                        description="safe outcome",
                    )
                )
                if payload.get("declared_safe_outcome") is not None
                else None
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DrillTimelineEvent":
        return cls.from_dict(_decode_json(payload, "drill_timeline_event"))


@dataclass(frozen=True)
class FailurePathDrillRequest:
    drill_id: str
    scenario: FailurePathScenario
    target_deployment_instance_id: str
    correlation_id: str
    decision_trace_id: str
    expected_safe_outcome: SafeOutcome
    timeline_events: tuple[DrillTimelineEvent, ...]
    recovery_request: RecoveryFenceRequest | None = None
    degradation_assessment: DegradationAssessment | None = None
    dependency_request: DependencyPropagationRequest | None = None
    withdrawal_review_request: EmergencyWithdrawalReviewRequest | None = None
    ledger_close_artifact: LedgerCloseArtifact | None = None
    restore_drill_artifact: RestoreDrillArtifact | None = None
    shutdown_record: GracefulShutdownRecord | None = None
    operator_reason_bundle: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "scenario": self.scenario.value,
            "target_deployment_instance_id": self.target_deployment_instance_id,
            "correlation_id": self.correlation_id,
            "decision_trace_id": self.decision_trace_id,
            "expected_safe_outcome": self.expected_safe_outcome.value,
            "timeline_events": [event.to_dict() for event in self.timeline_events],
            "recovery_request": (
                self.recovery_request.to_dict()
                if self.recovery_request is not None
                else None
            ),
            "degradation_assessment": (
                self.degradation_assessment.to_dict()
                if self.degradation_assessment is not None
                else None
            ),
            "dependency_request": (
                self.dependency_request.to_dict()
                if self.dependency_request is not None
                else None
            ),
            "withdrawal_review_request": (
                self.withdrawal_review_request.to_dict()
                if self.withdrawal_review_request is not None
                else None
            ),
            "ledger_close_artifact": (
                self.ledger_close_artifact.to_dict()
                if self.ledger_close_artifact is not None
                else None
            ),
            "restore_drill_artifact": (
                self.restore_drill_artifact.to_dict()
                if self.restore_drill_artifact is not None
                else None
            ),
            "shutdown_record": (
                self.shutdown_record.to_dict()
                if self.shutdown_record is not None
                else None
            ),
            "operator_reason_bundle": list(self.operator_reason_bundle),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailurePathDrillRequest":
        payload = _require_mapping(payload, field_name="failure_path_drill_request")
        return cls(
            drill_id=_require_non_empty_string(payload["drill_id"], field_name="drill_id"),
            scenario=FailurePathScenario(
                _require_enum_value(
                    payload["scenario"],
                    field_name="scenario",
                    enum_type=FailurePathScenario,
                    description="failure-path scenario",
                )
            ),
            target_deployment_instance_id=_require_non_empty_string(
                payload["target_deployment_instance_id"],
                field_name="target_deployment_instance_id",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            decision_trace_id=_require_non_empty_string(
                payload["decision_trace_id"],
                field_name="decision_trace_id",
            ),
            expected_safe_outcome=SafeOutcome(
                _require_enum_value(
                    payload["expected_safe_outcome"],
                    field_name="expected_safe_outcome",
                    enum_type=SafeOutcome,
                    description="safe outcome",
                )
            ),
            timeline_events=tuple(
                DrillTimelineEvent.from_dict(item)
                for item in _require_object_sequence(
                    payload["timeline_events"],
                    field_name="timeline_events",
                )
            ),
            recovery_request=(
                RecoveryFenceRequest.from_dict(
                    _require_mapping(
                        payload["recovery_request"],
                        field_name="recovery_request",
                    )
                )
                if payload.get("recovery_request") is not None
                else None
            ),
            degradation_assessment=(
                DegradationAssessment.from_dict(
                    _require_mapping(
                        payload["degradation_assessment"],
                        field_name="degradation_assessment",
                    )
                )
                if payload.get("degradation_assessment") is not None
                else None
            ),
            dependency_request=(
                DependencyPropagationRequest.from_dict(
                    _require_mapping(
                        payload["dependency_request"],
                        field_name="dependency_request",
                    )
                )
                if payload.get("dependency_request") is not None
                else None
            ),
            withdrawal_review_request=(
                EmergencyWithdrawalReviewRequest.from_dict(
                    _require_mapping(
                        payload["withdrawal_review_request"],
                        field_name="withdrawal_review_request",
                    )
                )
                if payload.get("withdrawal_review_request") is not None
                else None
            ),
            ledger_close_artifact=(
                LedgerCloseArtifact.from_dict(
                    _require_mapping(
                        payload["ledger_close_artifact"],
                        field_name="ledger_close_artifact",
                    )
                )
                if payload.get("ledger_close_artifact") is not None
                else None
            ),
            restore_drill_artifact=(
                RestoreDrillArtifact.from_dict(
                    _require_mapping(
                        payload["restore_drill_artifact"],
                        field_name="restore_drill_artifact",
                    )
                )
                if payload.get("restore_drill_artifact") is not None
                else None
            ),
            shutdown_record=(
                GracefulShutdownRecord.from_dict(
                    _require_mapping(
                        payload["shutdown_record"],
                        field_name="shutdown_record",
                    )
                )
                if payload.get("shutdown_record") is not None
                else None
            ),
            operator_reason_bundle=_require_string_sequence(
                payload.get("operator_reason_bundle", ()),
                field_name="operator_reason_bundle",
            ),
            schema_version=_require_schema_version(
                payload.get(
                    "schema_version",
                    SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION,
                ),
                field_name="schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FailurePathDrillRequest":
        return cls.from_dict(_decode_json(payload, "failure_path_drill_request"))


@dataclass(frozen=True)
class FailurePathDrillReport:
    case_id: str
    drill_id: str
    scenario: str
    status: str
    reason_code: str
    expected_safe_outcome: str
    observed_safe_outcome: str | None
    correlation_id: str
    retained_artifact_ids: tuple[str, ...]
    subreport_reason_codes: tuple[str, ...]
    timeline_events: tuple[dict[str, Any], ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailurePathDrillReport":
        payload = _require_mapping(payload, field_name="failure_path_drill_report")
        if "observed_safe_outcome" not in payload:
            raise ValueError("observed_safe_outcome: field is required")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            drill_id=_require_non_empty_string(payload["drill_id"], field_name="drill_id"),
            scenario=_require_enum_value(
                payload["scenario"],
                field_name="scenario",
                enum_type=FailurePathScenario,
                description="failure-path scenario",
            ),
            status=_require_enum_value(
                payload["status"],
                field_name="status",
                enum_type=PacketStatus,
                description="packet status",
            ),
            reason_code=_require_non_empty_string(payload["reason_code"], field_name="reason_code"),
            expected_safe_outcome=_require_enum_value(
                payload["expected_safe_outcome"],
                field_name="expected_safe_outcome",
                enum_type=SafeOutcome,
                description="safe outcome",
            ),
            observed_safe_outcome=(
                _require_enum_value(
                    payload["observed_safe_outcome"],
                    field_name="observed_safe_outcome",
                    enum_type=SafeOutcome,
                    description="safe outcome",
                )
                if payload.get("observed_safe_outcome") is not None
                else None
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            retained_artifact_ids=_require_string_sequence(
                payload["retained_artifact_ids"],
                field_name="retained_artifact_ids",
            ),
            subreport_reason_codes=_require_string_sequence(
                payload["subreport_reason_codes"],
                field_name="subreport_reason_codes",
            ),
            timeline_events=tuple(
                DrillTimelineEvent.from_dict(item).to_dict()
                for item in _require_object_sequence(
                    payload["timeline_events"],
                    field_name="timeline_events",
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
            timestamp=_normalize_utc_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FailurePathDrillReport":
        return cls.from_dict(_decode_json(payload, "failure_path_drill_report"))


def _timeline_validation_error(request: FailurePathDrillRequest) -> tuple[str, str] | None:
    if len(request.timeline_events) < 3:
        return (
            "FAILURE_DRILL_TIMELINE_TOO_SHORT",
            "Failure-path drills must retain a start, decision, and safe-outcome timeline.",
        )

    seen_sequences: set[int] = set()
    previous_sequence = 0
    for event in request.timeline_events:
        if event.sequence_number in seen_sequences or event.sequence_number <= previous_sequence:
            return (
                "FAILURE_DRILL_TIMELINE_SEQUENCE_INVALID",
                "Failure-path drill timeline events must have strictly increasing unique sequence numbers.",
            )
        if event.correlation_id != request.correlation_id:
            return (
                "FAILURE_DRILL_TIMELINE_CORRELATION_MISMATCH",
                "Every event in a failure-path drill must retain the same correlation id as the drill envelope.",
            )
        if not event.referenced_ids or not event.artifact_ids:
            return (
                "FAILURE_DRILL_TIMELINE_REFERENCES_REQUIRED",
                "Each timeline event must retain referenced ids and artifact ids for reconstruction.",
            )
        previous_sequence = event.sequence_number
        seen_sequences.add(event.sequence_number)

    final_event = request.timeline_events[-1]
    if final_event.declared_safe_outcome != request.expected_safe_outcome:
        return (
            "FAILURE_DRILL_FINAL_OUTCOME_MISMATCH",
            "The final timeline event must declare the expected safe outcome for the drill.",
        )

    if not any(
        request.target_deployment_instance_id in event.referenced_ids
        for event in request.timeline_events
    ):
        return (
            "FAILURE_DRILL_DEPLOYMENT_REFERENCE_REQUIRED",
            "The target deployment instance id must appear in the retained timeline references.",
        )

    return None


def _retained_artifact_ids(request: FailurePathDrillRequest) -> tuple[str, ...]:
    artifact_ids: list[str] = []
    for event in request.timeline_events:
        artifact_ids.extend(event.artifact_ids)

    if request.recovery_request is not None:
        artifact_ids.extend(
            [
                request.recovery_request.snapshot_artifact_id,
                request.recovery_request.journal_replay_artifact_id,
                request.recovery_request.journal_digest_frontier_id,
                request.recovery_request.warmup_artifact_id,
            ]
        )
    if request.ledger_close_artifact is not None:
        artifact_ids.append(request.ledger_close_artifact.authoritative_statement_set_id)
        artifact_ids.extend(request.ledger_close_artifact.discrepancy_summary_ids)
        if request.ledger_close_artifact.review_or_waiver_id is not None:
            artifact_ids.append(request.ledger_close_artifact.review_or_waiver_id)
    if request.restore_drill_artifact is not None:
        artifact_ids.extend(
            [
                request.restore_drill_artifact.backup_artifact_id,
                request.restore_drill_artifact.snapshot_artifact_id,
                request.restore_drill_artifact.journal_barrier_id,
                request.restore_drill_artifact.journal_digest_frontier_id,
            ]
        )
        if request.restore_drill_artifact.reviewed_waiver_id is not None:
            artifact_ids.append(request.restore_drill_artifact.reviewed_waiver_id)
    if request.shutdown_record is not None:
        artifact_ids.extend(
            [
                request.shutdown_record.final_snapshot_artifact_id,
                request.shutdown_record.journal_barrier_id,
                request.shutdown_record.journal_digest_frontier_id,
            ]
        )
    if request.dependency_request is not None and request.dependency_request.reviewed_waiver_id:
        artifact_ids.append(request.dependency_request.reviewed_waiver_id)
    if request.withdrawal_review_request is not None:
        artifact_ids.append(request.withdrawal_review_request.incident_reference_id)
        artifact_ids.append(request.withdrawal_review_request.operator_action_id)

    return tuple(dict.fromkeys(artifact_ids))


def _report(
    *,
    case_id: str,
    request: FailurePathDrillRequest,
    status: str,
    reason_code: str,
    observed_safe_outcome: SafeOutcome | None,
    subreport_reason_codes: list[str],
    explanation: str,
    remediation: str,
) -> FailurePathDrillReport:
    return FailurePathDrillReport(
        case_id=case_id,
        drill_id=request.drill_id,
        scenario=request.scenario.value,
        status=status,
        reason_code=reason_code,
        expected_safe_outcome=request.expected_safe_outcome.value,
        observed_safe_outcome=(
            observed_safe_outcome.value if observed_safe_outcome is not None else None
        ),
        correlation_id=request.correlation_id,
        retained_artifact_ids=_retained_artifact_ids(request),
        subreport_reason_codes=tuple(subreport_reason_codes),
        timeline_events=tuple(event.to_dict() for event in request.timeline_events),
        explanation=explanation,
        remediation=remediation,
    )


def evaluate_failure_path_drill(
    case_id: str,
    request: FailurePathDrillRequest,
) -> FailurePathDrillReport:
    if request.schema_version != SUPPORTED_FAILURE_PATH_DRILL_SCHEMA_VERSION:
        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.INVALID.value,
            reason_code="FAILURE_DRILL_SCHEMA_VERSION_UNSUPPORTED",
            observed_safe_outcome=None,
            subreport_reason_codes=[],
            explanation="The failure-path drill uses an unsupported schema version.",
            remediation="Rebuild the drill artifact with the supported schema version.",
        )

    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "drill_id": request.drill_id,
            "target_deployment_instance_id": request.target_deployment_instance_id,
            "correlation_id": request.correlation_id,
            "decision_trace_id": request.decision_trace_id,
            "timeline_events": request.timeline_events,
            "operator_reason_bundle": request.operator_reason_bundle,
        }.items()
        if not field_value
    )
    if missing_fields:
        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.INVALID.value,
            reason_code="FAILURE_DRILL_MISSING_REQUIRED_FIELDS",
            observed_safe_outcome=None,
            subreport_reason_codes=list(missing_fields),
            explanation="Failure-path drills require explicit identities, correlation, timeline, and operator reason metadata.",
            remediation="Populate the missing drill-envelope fields before evaluating the scenario.",
        )

    timeline_error = _timeline_validation_error(request)
    if timeline_error is not None:
        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code=timeline_error[0],
            observed_safe_outcome=None,
            subreport_reason_codes=[],
            explanation=timeline_error[1],
            remediation="Repair the retained timeline so the drill can be reconstructed deterministically.",
        )

    subreport_reason_codes: list[str] = []

    if request.scenario == FailurePathScenario.RECONNECT_BEFORE_ACK:
        if request.recovery_request is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_RECOVERY_REQUEST_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Reconnect-before-ack drills require a recovery-fence request.",
                remediation="Attach the recovery-fence request for this drill.",
            )
        recovery_report = validate_recovery_fence(case_id, request.recovery_request)
        subreport_reason_codes.append(recovery_report.reason_code)
        if (
            recovery_report.status == PacketStatus.PASS.value
            and request.recovery_request.ambiguity_detected
            and request.recovery_request.ambiguity_disposition.value == "halt"
            and request.expected_safe_outcome == SafeOutcome.HALT_BEFORE_MUTATION
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.HALT_BEFORE_MUTATION,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The reconnect-before-ack drill kept the system in RECOVERING and halted broker mutation until ambiguity was safely resolved.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The reconnect-before-ack drill did not retain the expected halt-before-mutation outcome.",
            remediation="Ensure ambiguous reconnect recovery halts mutation before any resume attempt.",
        )

    if request.scenario == FailurePathScenario.DEGRADED_DATA:
        if request.degradation_assessment is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_DEGRADATION_ASSESSMENT_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Degraded-data drills require a degradation assessment.",
                remediation="Attach the degradation assessment for this drill.",
            )
        degradation_report = validate_degradation_assessment(
            case_id,
            request.degradation_assessment,
        )
        subreport_reason_codes.append(degradation_report.reason_code)
        if (
            degradation_report.status == PacketStatus.PASS.value
            and request.degradation_assessment.proposed_action.value == "exit_only"
            and request.expected_safe_outcome == SafeOutcome.EXIT_ONLY
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.EXIT_ONLY,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The degraded-data drill escalated into exit-only mode and retained the evidence needed to explain the safe posture.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The degraded-data drill did not retain the expected exit-only safe outcome.",
            remediation="Escalate severe data or health degradation into an exit-only or stronger posture.",
        )

    if request.scenario == FailurePathScenario.DEPENDENCY_REVOCATION:
        if request.dependency_request is None or request.withdrawal_review_request is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_REVOCATION_AND_REVIEW_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Dependency-revocation drills require both propagation and withdrawal-review requests.",
                remediation="Attach the dependency-propagation and emergency-withdrawal review requests.",
            )
        propagation_report = evaluate_dependency_propagation(request.dependency_request)
        review_report = evaluate_emergency_withdrawal_review(
            request.withdrawal_review_request
        )
        subreport_reason_codes.extend(
            [propagation_report.reason_code, review_report.reason_code]
        )
        if (
            propagation_report.reason_code == "READINESS_DEPENDENCY_WITHDRAWAL_REQUIRED"
            and propagation_report.live_deployment_action == "withdraw_required"
            and review_report.status == PacketStatus.PASS.value
            and request.expected_safe_outcome == SafeOutcome.WITHDRAW_AND_REVIEW
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.WITHDRAW_AND_REVIEW,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The dependency-revocation drill forced withdrawal and completed the post-withdrawal review within the governed path.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The dependency-revocation drill did not retain both the forced-withdrawal and reviewed follow-up outcome.",
            remediation="Ensure revoked dependencies force withdrawal and produce a recorded review outcome.",
        )

    if request.scenario == FailurePathScenario.RECONCILIATION_FAILURE:
        if request.ledger_close_artifact is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_LEDGER_CLOSE_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Reconciliation-failure drills require a ledger-close artifact.",
                remediation="Attach the authoritative ledger-close artifact for this drill.",
            )
        ledger_report = validate_ledger_close(case_id, request.ledger_close_artifact)
        subreport_reason_codes.append(ledger_report.reason_code)
        if (
            ledger_report.status == PacketStatus.PASS.value
            and request.ledger_close_artifact.next_session_eligibility.value == "blocked"
            and request.expected_safe_outcome == SafeOutcome.NEXT_SESSION_BLOCKED
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.NEXT_SESSION_BLOCKED,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The reconciliation-failure drill blocked the next session instead of silently carrying forward unresolved statement differences.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The reconciliation-failure drill did not retain the expected next-session block.",
            remediation="Keep next-session eligibility blocked or review-required until reconciliation is governed.",
        )

    if request.scenario == FailurePathScenario.RESTORE_AFTER_HOST_LOSS:
        if request.restore_drill_artifact is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_RESTORE_ARTIFACT_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Restore-after-host-loss drills require a restore-drill artifact.",
                remediation="Attach the restore-drill artifact for this drill.",
            )
        restore_report = validate_restore_drill(case_id, request.restore_drill_artifact)
        subreport_reason_codes.append(restore_report.reason_code)
        if (
            restore_report.reason_code == "RESTORE_DRILL_RECONCILIATION_REVIEW_REQUIRED"
            and request.expected_safe_outcome == SafeOutcome.REMAIN_HALTED_UNTIL_REVIEW
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.REMAIN_HALTED_UNTIL_REVIEW,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The host-loss restore drill remained halted until dirty reconciliation could be reviewed, rather than resuming unsafely.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The host-loss restore drill did not retain the expected remain-halted-until-review outcome.",
            remediation="Do not allow restored runtime to resume after dirty reconciliation without review or waiver.",
        )

    if request.scenario == FailurePathScenario.SAFE_STOP:
        if request.shutdown_record is None:
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.INVALID.value,
                reason_code="FAILURE_DRILL_SHUTDOWN_RECORD_REQUIRED",
                observed_safe_outcome=None,
                subreport_reason_codes=[],
                explanation="Safe-stop drills require a graceful-shutdown record.",
                remediation="Attach the graceful-shutdown record for this drill.",
            )
        shutdown_report = validate_graceful_shutdown(case_id, request.shutdown_record)
        subreport_reason_codes.append(shutdown_report.reason_code)
        if (
            shutdown_report.status == PacketStatus.PASS.value
            and request.shutdown_record.restart_ready
            and request.expected_safe_outcome
            == SafeOutcome.RESTART_ARTIFACTS_PERSISTED
        ):
            return _report(
                case_id=case_id,
                request=request,
                status=PacketStatus.PASS.value,
                reason_code="FAILURE_DRILL_SAFE_OUTCOME_OBSERVED",
                observed_safe_outcome=SafeOutcome.RESTART_ARTIFACTS_PERSISTED,
                subreport_reason_codes=subreport_reason_codes,
                explanation="The safe-stop drill fenced entries and persisted restart artifacts instead of leaving shutdown state ambiguous.",
                remediation="No remediation required.",
            )

        return _report(
            case_id=case_id,
            request=request,
            status=PacketStatus.VIOLATION.value,
            reason_code="FAILURE_DRILL_SAFE_OUTCOME_NOT_OBSERVED",
            observed_safe_outcome=None,
            subreport_reason_codes=subreport_reason_codes,
            explanation="The safe-stop drill did not retain the expected restart-artifact outcome.",
            remediation="Persist verified restart artifacts before claiming graceful shutdown success.",
        )

    return _report(
        case_id=case_id,
        request=request,
        status=PacketStatus.INVALID.value,
        reason_code="FAILURE_DRILL_SCENARIO_UNSUPPORTED",
        observed_safe_outcome=None,
        subreport_reason_codes=[],
        explanation="The failure-path drill scenario is not supported.",
        remediation="Use a supported failure-path scenario.",
    )


def validate_failure_path_drill_contract() -> list[str]:
    errors: list[str] = []
    if len(FailurePathScenario) != len(set(FailurePathScenario)):
        errors.append("failure-path scenarios must remain unique")
    if len(SafeOutcome) != len(set(SafeOutcome)):
        errors.append("failure-path safe outcomes must remain unique")
    return errors


VALIDATION_ERRORS = validate_failure_path_drill_contract()
