"""Readiness revocation propagation and emergency withdrawal review contracts."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.deployment_packets import (
    BundleReadinessRecord,
    DeploymentInstance,
    DeploymentState,
    PacketStatus,
    ReadinessState,
    transition_bundle_readiness_record,
)
from shared.policy.release_certification import (
    CorrectionImpactClass,
    DependentSurfaceKind,
    DependentUpdateAction,
    ReleaseCorrectionEvent,
)

STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []


def _utcnow() -> str:
    return canonicalize_persisted_timestamp(
        _dt.datetime.now(_dt.timezone.utc)
    ).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _parse_timestamp(value: str) -> _dt.datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    return _dt.datetime.fromisoformat(candidate)


def _sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@unique
class LiveDeploymentAction(str, Enum):
    NONE = "none"
    CONTINUE_WITH_REVIEWED_WAIVER = "continue_with_reviewed_waiver"
    WITHDRAW_REQUIRED = "withdraw_required"


@unique
class WithdrawalTriggerSource(str, Enum):
    OPSD = "opsd"
    KILL_SWITCH = "kill_switch"
    GUARDIAN = "guardian"


@dataclass(frozen=True)
class DependencyPropagationRequest:
    case_id: str
    readiness_record: BundleReadinessRecord
    dependency_surface_kind: str
    dependency_surface_id: str
    dependency_lifecycle_state: str | None = None
    correction_event: ReleaseCorrectionEvent | None = None
    active_deployment: DeploymentInstance | None = None
    reviewed_waiver_id: str | None = None
    operator_reason_bundle: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "readiness_record": self.readiness_record.to_dict(),
            "dependency_surface_kind": self.dependency_surface_kind,
            "dependency_surface_id": self.dependency_surface_id,
            "dependency_lifecycle_state": self.dependency_lifecycle_state,
            "correction_event": (
                self.correction_event.to_dict() if self.correction_event is not None else None
            ),
            "active_deployment": (
                self.active_deployment.to_dict()
                if self.active_deployment is not None
                else None
            ),
            "reviewed_waiver_id": self.reviewed_waiver_id,
            "operator_reason_bundle": list(self.operator_reason_bundle),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DependencyPropagationRequest":
        return cls(
            case_id=str(payload["case_id"]),
            readiness_record=BundleReadinessRecord.from_dict(
                dict(payload["readiness_record"])
            ),
            dependency_surface_kind=str(payload["dependency_surface_kind"]),
            dependency_surface_id=str(payload["dependency_surface_id"]),
            dependency_lifecycle_state=(
                str(payload["dependency_lifecycle_state"])
                if payload.get("dependency_lifecycle_state") is not None
                else None
            ),
            correction_event=(
                ReleaseCorrectionEvent.from_dict(dict(payload["correction_event"]))
                if payload.get("correction_event") is not None
                else None
            ),
            active_deployment=(
                DeploymentInstance.from_dict(dict(payload["active_deployment"]))
                if payload.get("active_deployment") is not None
                else None
            ),
            reviewed_waiver_id=(
                str(payload["reviewed_waiver_id"])
                if payload.get("reviewed_waiver_id") is not None
                else None
            ),
            operator_reason_bundle=tuple(
                str(item) for item in payload.get("operator_reason_bundle", ())
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DependencyPropagationRequest":
        return cls.from_dict(_decode_json_object(payload, label="dependency propagation"))


@dataclass(frozen=True)
class EmergencyWithdrawalReviewRequest:
    case_id: str
    readiness_record: BundleReadinessRecord
    deployment: DeploymentInstance
    trigger_source: WithdrawalTriggerSource
    operator_action_id: str
    incident_reference_id: str
    withdrawn_at_utc: str
    review_completed_at_utc: str | None = None
    review_decision_state: ReadinessState | None = None
    review_rationale: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "readiness_record": self.readiness_record.to_dict(),
            "deployment": self.deployment.to_dict(),
            "trigger_source": self.trigger_source.value,
            "operator_action_id": self.operator_action_id,
            "incident_reference_id": self.incident_reference_id,
            "withdrawn_at_utc": self.withdrawn_at_utc,
            "review_completed_at_utc": self.review_completed_at_utc,
            "review_decision_state": (
                self.review_decision_state.value
                if self.review_decision_state is not None
                else None
            ),
            "review_rationale": self.review_rationale,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EmergencyWithdrawalReviewRequest":
        return cls(
            case_id=str(payload["case_id"]),
            readiness_record=BundleReadinessRecord.from_dict(
                dict(payload["readiness_record"])
            ),
            deployment=DeploymentInstance.from_dict(dict(payload["deployment"])),
            trigger_source=WithdrawalTriggerSource(payload["trigger_source"]),
            operator_action_id=str(payload["operator_action_id"]),
            incident_reference_id=str(payload["incident_reference_id"]),
            withdrawn_at_utc=str(payload["withdrawn_at_utc"]),
            review_completed_at_utc=(
                str(payload["review_completed_at_utc"])
                if payload.get("review_completed_at_utc") is not None
                else None
            ),
            review_decision_state=(
                ReadinessState(payload["review_decision_state"])
                if payload.get("review_decision_state") is not None
                else None
            ),
            review_rationale=(
                str(payload["review_rationale"])
                if payload.get("review_rationale") is not None
                else None
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "EmergencyWithdrawalReviewRequest":
        return cls.from_dict(_decode_json_object(payload, label="withdrawal review"))


@dataclass(frozen=True)
class DependencyPropagationReport:
    case_id: str
    readiness_record_id: str
    dependency_surface_kind: str
    dependency_surface_id: str
    status: str
    reason_code: str
    propagation_reason_code: str
    resulting_readiness_state: str
    live_deployment_action: str
    reviewed_waiver_id: str | None
    transition_reason_code: str
    artifact_manifest: dict[str, Any]
    structured_logs: list[dict[str, Any]]
    operator_reason_bundle: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class EmergencyWithdrawalReviewReport:
    case_id: str
    readiness_record_id: str
    deployment_instance_id: str
    status: str
    reason_code: str
    resulting_readiness_state: str
    review_due_at_utc: str
    review_completed_at_utc: str | None
    reviewed_within_sla: bool
    transition_reason_code: str
    artifact_manifest: dict[str, Any]
    structured_logs: list[dict[str, Any]]
    operator_reason_bundle: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _artifact_record(
    run_id: str,
    case_id: str,
    role: str,
    payload: Any,
) -> dict[str, Any]:
    return {
        "artifact_id": f"{run_id}_{role}",
        "artifact_role": role,
        "relative_path": f"verification/readiness_revocation/{case_id}/{role}.json",
        "sha256": _sha256_payload(payload),
        "content_type": "application/json",
    }


def _build_artifact_manifest(
    run_id: str,
    case_id: str,
    payloads: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifest_id": f"artifact_manifest_{run_id}",
        "generated_at_utc": _utcnow(),
        "retention_class": "promotion_review_and_incident_investigation",
        "contains_secrets": False,
        "redaction_policy": "opaque_identifiers_only",
        "artifacts": [
            _artifact_record(run_id, case_id, role, payload)
            for role, payload in payloads.items()
        ],
    }


def _structured_log(
    *,
    event_id: str,
    event_type: str,
    correlation_id: str,
    decision_trace_id: str,
    reason_code: str,
    reason_summary: str,
    referenced_ids: list[str],
    artifact_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
        "event_type": event_type,
        "plane": "certification",
        "event_id": event_id,
        "recorded_at_utc": _utcnow(),
        "correlation_id": correlation_id,
        "decision_trace_id": decision_trace_id,
        "reason_code": reason_code,
        "reason_summary": reason_summary,
        "referenced_ids": referenced_ids,
        "redacted_fields": [],
        "omitted_fields": [],
        "artifact_manifest": artifact_manifest,
    }


def _matching_update(
    correction_event: ReleaseCorrectionEvent | None,
    readiness_record_id: str,
) -> tuple[DependentUpdateAction | None, str | None]:
    if correction_event is None:
        return None, None
    for update in correction_event.dependent_updates:
        if (
            update.surface_kind == DependentSurfaceKind.BUNDLE_READINESS_RECORD
            and update.surface_id == readiness_record_id
        ):
            return update.action, update.reason_bundle
    return None, None


def _resulting_state_for_dependency(
    request: DependencyPropagationRequest,
) -> tuple[ReadinessState, str, str, str]:
    update_action, update_reason = _matching_update(
        request.correction_event,
        request.readiness_record.bundle_readiness_record_id,
    )
    if update_action == DependentUpdateAction.RECERTIFY:
        return (
            ReadinessState.RECERT_REQUIRED,
            "READINESS_DEPENDENCY_PROPAGATED_RECERT_REQUIRED",
            "A dependent correction event requires recertification before this readiness record can be trusted again.",
            update_reason or "Recertify the readiness record against the corrected dependency.",
        )
    if update_action == DependentUpdateAction.QUARANTINE:
        return (
            ReadinessState.SUSPECT,
            "READINESS_DEPENDENCY_PROPAGATED_SUSPECT",
            "A dependent correction event quarantined this readiness record pending operator review.",
            update_reason or "Review the dependency correction and decide whether recertification or revocation is required.",
        )
    if update_action == DependentUpdateAction.SUPERSEDE:
        return (
            ReadinessState.REVOKED,
            "READINESS_DEPENDENCY_PROPAGATED_REVOKED",
            "A dependent correction event superseded the readiness record, so the old readiness may not remain active.",
            update_reason or "Promote a superseding readiness record before any further activation.",
        )
    if request.correction_event is not None:
        if request.correction_event.impact_class == CorrectionImpactClass.RECERT_REQUIRED:
            return (
                ReadinessState.RECERT_REQUIRED,
                "READINESS_DEPENDENCY_PROPAGATED_RECERT_REQUIRED",
                "The dependency correction carries a recertification impact that must propagate into readiness.",
                "Recertify the affected readiness record before paper or live continuation.",
            )
        if request.correction_event.impact_class == CorrectionImpactClass.SUSPECT:
            return (
                ReadinessState.SUSPECT,
                "READINESS_DEPENDENCY_PROPAGATED_SUSPECT",
                "The dependency correction makes the readiness record suspect until an operator reviews the material change.",
                "Review the corrected dependency and either restore confidence or revoke the readiness record.",
            )
    if request.dependency_lifecycle_state is not None:
        state_value = request.dependency_lifecycle_state.upper()
        if state_value == "QUARANTINED":
            return (
                ReadinessState.RECERT_REQUIRED,
                "READINESS_DEPENDENCY_PROPAGATED_RECERT_REQUIRED",
                "A quarantined dependency forces readiness back into recertification review.",
                "Recertify the readiness record against non-quarantined dependency inputs.",
            )
        if state_value == "REVOKED":
            return (
                ReadinessState.SUSPECT,
                "READINESS_DEPENDENCY_PROPAGATED_SUSPECT",
                "A revoked dependency marks the downstream readiness record suspect until the operator explicitly waives or replaces it.",
                "Withdraw or review-waive the live deployment and re-evaluate the readiness record.",
            )
    return (
        request.readiness_record.lifecycle_state,
        "READINESS_DEPENDENCY_CLEAR",
        "No dependency revocation or material correction impact requires a readiness state change.",
        "No remediation required.",
    )


def evaluate_dependency_propagation(
    request: DependencyPropagationRequest,
) -> DependencyPropagationReport:
    if request.correction_event is None and request.dependency_lifecycle_state is None:
        resulting_state = request.readiness_record.lifecycle_state
        propagation_reason_code = "READINESS_DEPENDENCY_TRIGGER_MISSING"
        explanation = (
            "Dependency propagation requires either a dependency lifecycle state or a release correction event."
        )
        remediation = "Attach the triggering dependency lifecycle state or correction event."
        transition_reason_code = "BUNDLE_READINESS_NO_STATE_CHANGE"
        live_action = LiveDeploymentAction.NONE
        status = PacketStatus.INVALID.value
        reason_code = propagation_reason_code
    else:
        resulting_state, propagation_reason_code, explanation, remediation = (
            _resulting_state_for_dependency(request)
        )
        transition = transition_bundle_readiness_record(
            request.case_id,
            request.readiness_record,
            resulting_state,
        )
        transition_reason_code = transition.reason_code
        live_action = LiveDeploymentAction.NONE
        status = PacketStatus.PASS.value
        reason_code = propagation_reason_code
        if (
            request.active_deployment is not None
            and request.active_deployment.lifecycle_state
            in {DeploymentState.LIVE_ACTIVE, DeploymentState.LIVE_CANARY}
            and resulting_state != request.readiness_record.lifecycle_state
        ):
            if request.reviewed_waiver_id:
                live_action = LiveDeploymentAction.CONTINUE_WITH_REVIEWED_WAIVER
                reason_code = "READINESS_DEPENDENCY_WAIVER_APPLIED"
                explanation = (
                    "The dependency propagation degraded readiness, but a reviewed waiver keeps the live deployment running under explicit operator accountability."
                )
                remediation = (
                    "Track the waiver in the promotion record and schedule the required recertification or replacement."
                )
            else:
                live_action = LiveDeploymentAction.WITHDRAW_REQUIRED
                status = PacketStatus.VIOLATION.value
                reason_code = "READINESS_DEPENDENCY_WITHDRAWAL_REQUIRED"
                explanation = (
                    "A live deployment may not continue through the degraded dependency state without an explicit reviewed waiver."
                )
                remediation = (
                    "Withdraw the live deployment immediately or attach a reviewed waiver before continuation."
                )

    operator_reason_bundle = {
        "summary": explanation,
        "gate_summary": (
            "Dependency propagation completed without forcing live withdrawal."
            if status == PacketStatus.PASS.value
            else "Dependency propagation forced an immediate operator action."
        ),
        "rule_trace": [
            "Quarantined, revoked, or materially corrected dependencies must push readiness into RECERT_REQUIRED, SUSPECT, or REVOKED according to policy.",
            "No live deployment may continue through a degraded dependency without an explicit reviewed waiver.",
        ],
        "remediation_hints": [
            remediation,
            "Retain the propagation report with the affected dependency ids and resulting readiness state.",
        ],
    }
    evidence_payload = {
        "readiness_record": request.readiness_record.to_dict(),
        "dependency_surface_kind": request.dependency_surface_kind,
        "dependency_surface_id": request.dependency_surface_id,
        "dependency_lifecycle_state": request.dependency_lifecycle_state,
        "correction_event": (
            request.correction_event.to_dict() if request.correction_event is not None else None
        ),
    }
    outcome_payload = {
        "resulting_readiness_state": resulting_state.value,
        "live_deployment_action": live_action.value,
        "reason_code": reason_code,
        "propagation_reason_code": propagation_reason_code,
        "reviewed_waiver_id": request.reviewed_waiver_id,
    }
    manifest = _build_artifact_manifest(
        request.readiness_record.bundle_readiness_record_id,
        request.case_id,
        {
            "dependency_evidence": evidence_payload,
            "propagation_outcome": outcome_payload,
            "operator_reason_bundle": operator_reason_bundle,
        },
    )
    referenced_ids = [
        request.readiness_record.bundle_readiness_record_id,
        request.dependency_surface_id,
    ]
    if request.active_deployment is not None:
        referenced_ids.append(request.active_deployment.deployment_instance_id)
    structured_logs = [
        _structured_log(
            event_id=f"{request.case_id}:propagation_started",
            event_type="dependency_propagation_started",
            correlation_id=request.readiness_record.bundle_readiness_record_id,
            decision_trace_id=request.case_id,
            reason_code="READINESS_DEPENDENCY_PROPAGATION_STARTED",
            reason_summary="Dependency revocation propagation started.",
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
        _structured_log(
            event_id=f"{request.case_id}:readiness_transition",
            event_type="dependency_propagation_transition_evaluated",
            correlation_id=request.readiness_record.bundle_readiness_record_id,
            decision_trace_id=request.case_id,
            reason_code=transition_reason_code,
            reason_summary="Readiness transition evaluated against the canonical lifecycle.",
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
        _structured_log(
            event_id=f"{request.case_id}:propagation_completed",
            event_type="dependency_propagation_completed",
            correlation_id=request.readiness_record.bundle_readiness_record_id,
            decision_trace_id=request.case_id,
            reason_code=reason_code,
            reason_summary=explanation,
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
    ]
    return DependencyPropagationReport(
        case_id=request.case_id,
        readiness_record_id=request.readiness_record.bundle_readiness_record_id,
        dependency_surface_kind=request.dependency_surface_kind,
        dependency_surface_id=request.dependency_surface_id,
        status=status,
        reason_code=reason_code,
        propagation_reason_code=propagation_reason_code,
        resulting_readiness_state=resulting_state.value,
        live_deployment_action=live_action.value,
        reviewed_waiver_id=request.reviewed_waiver_id,
        transition_reason_code=transition_reason_code,
        artifact_manifest=manifest,
        structured_logs=structured_logs,
        operator_reason_bundle=operator_reason_bundle,
        explanation=explanation,
        remediation=remediation,
    )


def evaluate_emergency_withdrawal_review(
    request: EmergencyWithdrawalReviewRequest,
) -> EmergencyWithdrawalReviewReport:
    review_due_at = _parse_timestamp(request.withdrawn_at_utc) + _dt.timedelta(hours=24)
    valid_review_states = {
        request.readiness_record.lifecycle_state,
        ReadinessState.RECERT_REQUIRED,
        ReadinessState.SUSPECT,
        ReadinessState.REVOKED,
    }

    if (
        request.deployment.lifecycle_state != DeploymentState.WITHDRAWN
        or request.deployment.withdrawal_event_id is None
    ):
        resulting_state = ReadinessState.SUSPECT
        status = PacketStatus.INVALID.value
        reason_code = "EMERGENCY_WITHDRAWAL_NOT_RECORDED"
        explanation = (
            "Emergency withdrawal review requires a deployment instance that is already marked WITHDRAWN and carries a withdrawal event id."
        )
        remediation = "Record the withdrawal event before starting the post-withdrawal review."
        reviewed_within_sla = False
    elif (
        request.review_completed_at_utc is None
        or request.review_decision_state is None
        or not request.review_rationale
    ):
        resulting_state = ReadinessState.SUSPECT
        status = PacketStatus.VIOLATION.value
        reason_code = "EMERGENCY_WITHDRAWAL_REVIEW_MISSING"
        explanation = (
            "A withdrawn live deployment must receive a post-withdrawal review within 24 hours with a recorded readiness decision and rationale."
        )
        remediation = (
            "Complete the post-withdrawal review and decide whether readiness remains valid, becomes RECERT_REQUIRED, becomes SUSPECT, or is REVOKED."
        )
        reviewed_within_sla = False
    elif request.review_decision_state not in valid_review_states:
        resulting_state = ReadinessState.SUSPECT
        status = PacketStatus.INVALID.value
        reason_code = "EMERGENCY_WITHDRAWAL_REVIEW_STATE_INVALID"
        explanation = (
            "The post-withdrawal review decision must either preserve the current readiness state or move it to RECERT_REQUIRED, SUSPECT, or REVOKED."
        )
        remediation = "Choose a valid readiness outcome for the withdrawal review."
        reviewed_within_sla = False
    else:
        review_completed_at = _parse_timestamp(request.review_completed_at_utc)
        resulting_state = request.review_decision_state
        reviewed_within_sla = review_completed_at <= review_due_at
        if reviewed_within_sla:
            status = PacketStatus.PASS.value
            reason_code = "EMERGENCY_WITHDRAWAL_REVIEW_COMPLETED"
            explanation = (
                "The emergency withdrawal received a timely review and the readiness decision is now auditable."
            )
            remediation = "No remediation required."
        else:
            status = PacketStatus.VIOLATION.value
            reason_code = "EMERGENCY_WITHDRAWAL_REVIEW_OVERDUE"
            explanation = (
                "The emergency withdrawal review was completed, but it missed the mandatory 24-hour review window."
            )
            remediation = (
                "Record the SLA miss and treat the readiness record as operator-sensitive until the late review outcome is explicitly accepted."
            )

    transition = transition_bundle_readiness_record(
        request.case_id,
        request.readiness_record,
        resulting_state,
    )
    operator_reason_bundle = {
        "summary": explanation,
        "gate_summary": (
            "Emergency withdrawal review satisfied the post-withdrawal governance rule."
            if status == PacketStatus.PASS.value
            else "Emergency withdrawal review violated the post-withdrawal governance rule."
        ),
        "rule_trace": [
            "An operator may withdraw through opsd, the kill-switch path, or guardian emergency control.",
            "Post-withdrawal review is mandatory within 24 hours and must choose the resulting readiness state.",
        ],
        "remediation_hints": [
            remediation,
            "Retain the withdrawal report with the operator action, incident reference, and resulting readiness decision.",
        ],
    }
    evidence_payload = {
        "deployment": request.deployment.to_dict(),
        "readiness_record": request.readiness_record.to_dict(),
        "trigger_source": request.trigger_source.value,
        "operator_action_id": request.operator_action_id,
        "incident_reference_id": request.incident_reference_id,
        "withdrawn_at_utc": request.withdrawn_at_utc,
        "review_completed_at_utc": request.review_completed_at_utc,
        "review_decision_state": (
            request.review_decision_state.value
            if request.review_decision_state is not None
            else None
        ),
        "review_rationale": request.review_rationale,
    }
    outcome_payload = {
        "resulting_readiness_state": resulting_state.value,
        "reason_code": reason_code,
        "review_due_at_utc": review_due_at.isoformat(),
        "reviewed_within_sla": reviewed_within_sla,
    }
    manifest = _build_artifact_manifest(
        request.deployment.deployment_instance_id,
        request.case_id,
        {
            "withdrawal_evidence": evidence_payload,
            "review_outcome": outcome_payload,
            "operator_reason_bundle": operator_reason_bundle,
        },
    )
    referenced_ids = [
        request.deployment.deployment_instance_id,
        request.readiness_record.bundle_readiness_record_id,
        request.operator_action_id,
        request.incident_reference_id,
    ]
    structured_logs = [
        _structured_log(
            event_id=f"{request.case_id}:withdrawal_recorded",
            event_type="emergency_withdrawal_recorded",
            correlation_id=request.deployment.deployment_instance_id,
            decision_trace_id=request.case_id,
            reason_code="EMERGENCY_WITHDRAWAL_RECORDED",
            reason_summary="Emergency withdrawal recorded.",
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
        _structured_log(
            event_id=f"{request.case_id}:review_transition",
            event_type="emergency_withdrawal_review_transition_evaluated",
            correlation_id=request.deployment.deployment_instance_id,
            decision_trace_id=request.case_id,
            reason_code=transition.reason_code,
            reason_summary="Withdrawal review decision checked against the readiness lifecycle.",
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
        _structured_log(
            event_id=f"{request.case_id}:review_completed",
            event_type="emergency_withdrawal_review_completed",
            correlation_id=request.deployment.deployment_instance_id,
            decision_trace_id=request.case_id,
            reason_code=reason_code,
            reason_summary=explanation,
            referenced_ids=referenced_ids,
            artifact_manifest=manifest,
        ),
    ]
    return EmergencyWithdrawalReviewReport(
        case_id=request.case_id,
        readiness_record_id=request.readiness_record.bundle_readiness_record_id,
        deployment_instance_id=request.deployment.deployment_instance_id,
        status=status,
        reason_code=reason_code,
        resulting_readiness_state=resulting_state.value,
        review_due_at_utc=review_due_at.isoformat(),
        review_completed_at_utc=request.review_completed_at_utc,
        reviewed_within_sla=reviewed_within_sla,
        transition_reason_code=transition.reason_code,
        artifact_manifest=manifest,
        structured_logs=structured_logs,
        operator_reason_bundle=operator_reason_bundle,
        explanation=explanation,
        remediation=remediation,
    )
