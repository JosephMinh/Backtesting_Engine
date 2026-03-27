"""Lockbox access, finalist bounds, and contamination-handling policy contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.evaluation_protocol import (
    EvaluationArtifactBundle,
    EvaluationProtocolCheckResult,
    EvaluationProtocolReport,
)
from shared.policy.research_state import (
    ResearchAdmissibilityClass,
    ResearchRunPurpose,
    ResearchRunRecord,
    ReviewerAttestation,
)

SUPPORTED_LOCKBOX_POLICY_SCHEMA_VERSION = 1

LOCKBOX_POLICY_RULE_IDS = (
    "evaluation_protocol_lockbox_ready",
    "lockbox_run_recorded",
    "bounded_finalist_count",
    "policy_controlled_access",
    "no_ranking_surface_access",
    "contamination_incident_handling",
    "retained_lockbox_artifacts",
)


def validate_lockbox_policy_contract() -> list[str]:
    errors: list[str] = []
    if SUPPORTED_LOCKBOX_POLICY_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    if len(LOCKBOX_POLICY_RULE_IDS) != len(set(LOCKBOX_POLICY_RULE_IDS)):
        errors.append("lockbox policy rule identifiers must be unique")
    if ResearchRunPurpose.LOCKBOX.value != "lockbox":
        errors.append("lockbox policy expects the canonical research_run purpose")
    return errors


VALIDATION_ERRORS = validate_lockbox_policy_contract()


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _sorted_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _artifact_bundle_complete(bundle: EvaluationArtifactBundle) -> bool:
    return bool(
        bundle.artifact_manifest_id
        and bundle.retained_log_ids
        and bundle.correlation_ids
        and bundle.expected_actual_diff_ids
        and bundle.operator_reason_bundle
    )


def _protocol_check(
    report: EvaluationProtocolReport, check_id: str
) -> EvaluationProtocolCheckResult | None:
    for result in report.check_results:
        if result.check_id == check_id:
            return result
    return None


@unique
class LockboxPolicyStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class LockboxDecision(str, Enum):
    FREEZE_CANDIDATE = "freeze_candidate"
    HOLD = "hold"
    REJECT_CANDIDATE = "reject_candidate"
    RESTART_CYCLE = "restart_cycle"


@unique
class LockboxAccessPurpose(str, Enum):
    ADMIT_FINALISTS = "admit_finalists"
    FINAL_REVIEW = "final_review"
    INCIDENT_REVIEW = "incident_review"
    FREEZE_APPROVAL = "freeze_approval"


@unique
class LockboxContaminationDisposition(str, Enum):
    PENDING_REVIEW = "pending_review"
    REJECT_CANDIDATE = "reject_candidate"
    RESTART_CYCLE = "restart_cycle"


@dataclass(frozen=True)
class LockboxAccessEvent:
    access_event_id: str
    actor_id: str
    access_purpose: LockboxAccessPurpose
    finalist_candidate_ids: tuple[str, ...]
    approved_control_ids: tuple[str, ...]
    access_log_id: str
    ranking_surface_accessed: bool = False
    approval_reference_id: str | None = None
    accessed_at_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "access_event_id": self.access_event_id,
            "actor_id": self.actor_id,
            "access_purpose": self.access_purpose.value,
            "finalist_candidate_ids": list(self.finalist_candidate_ids),
            "approved_control_ids": list(self.approved_control_ids),
            "access_log_id": self.access_log_id,
            "ranking_surface_accessed": self.ranking_surface_accessed,
            "approval_reference_id": self.approval_reference_id,
            "accessed_at_utc": self.accessed_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LockboxAccessEvent":
        return cls(
            access_event_id=str(payload["access_event_id"]),
            actor_id=str(payload["actor_id"]),
            access_purpose=LockboxAccessPurpose(str(payload["access_purpose"])),
            finalist_candidate_ids=tuple(
                str(item) for item in payload["finalist_candidate_ids"]
            ),
            approved_control_ids=tuple(
                str(item) for item in payload["approved_control_ids"]
            ),
            access_log_id=str(payload["access_log_id"]),
            ranking_surface_accessed=bool(payload.get("ranking_surface_accessed", False)),
            approval_reference_id=(
                None
                if payload.get("approval_reference_id") in (None, "")
                else str(payload["approval_reference_id"])
            ),
            accessed_at_utc=str(payload.get("accessed_at_utc", _utc_now())),
        )


@dataclass(frozen=True)
class LockboxIncidentRecord:
    incident_record_id: str
    candidate_id: str
    reason_code: str
    incident_log_ids: tuple[str, ...]
    review_reference_ids: tuple[str, ...]
    reviewer_self_attestations: tuple[ReviewerAttestation, ...]
    disposition: LockboxContaminationDisposition
    explanation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "incident_record_id": self.incident_record_id,
            "candidate_id": self.candidate_id,
            "reason_code": self.reason_code,
            "incident_log_ids": list(self.incident_log_ids),
            "review_reference_ids": list(self.review_reference_ids),
            "reviewer_self_attestations": [
                item.to_dict() for item in self.reviewer_self_attestations
            ],
            "disposition": self.disposition.value,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LockboxIncidentRecord":
        return cls(
            incident_record_id=str(payload["incident_record_id"]),
            candidate_id=str(payload["candidate_id"]),
            reason_code=str(payload["reason_code"]),
            incident_log_ids=tuple(str(item) for item in payload["incident_log_ids"]),
            review_reference_ids=tuple(
                str(item) for item in payload["review_reference_ids"]
            ),
            reviewer_self_attestations=tuple(
                ReviewerAttestation.from_dict(dict(item))
                for item in payload["reviewer_self_attestations"]
            ),
            disposition=LockboxContaminationDisposition(str(payload["disposition"])),
            explanation=str(payload["explanation"]),
            timestamp=str(payload.get("timestamp", _utc_now())),
        )


@dataclass(frozen=True)
class LockboxPolicyCheckResult:
    check_id: str
    check_name: str
    passed: bool
    status: str
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LockboxPolicyCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            check_name=str(payload["check_name"]),
            passed=bool(payload["passed"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            diagnostic=str(payload["diagnostic"]),
            evidence=dict(payload["evidence"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class LockboxPolicyRequest:
    case_id: str
    family_id: str
    selected_candidate_id: str
    finalist_candidate_ids: tuple[str, ...]
    finalist_cap: int
    evaluation_protocol_report: EvaluationProtocolReport
    lockbox_run_record: ResearchRunRecord
    access_events: tuple[LockboxAccessEvent, ...]
    contamination_incidents: tuple[LockboxIncidentRecord, ...]
    artifact_bundle: EvaluationArtifactBundle
    schema_version: int = SUPPORTED_LOCKBOX_POLICY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "family_id": self.family_id,
            "selected_candidate_id": self.selected_candidate_id,
            "finalist_candidate_ids": list(self.finalist_candidate_ids),
            "finalist_cap": self.finalist_cap,
            "evaluation_protocol_report": self.evaluation_protocol_report.to_dict(),
            "lockbox_run_record": self.lockbox_run_record.to_dict(),
            "access_events": [item.to_dict() for item in self.access_events],
            "contamination_incidents": [
                item.to_dict() for item in self.contamination_incidents
            ],
            "artifact_bundle": self.artifact_bundle.to_dict(),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LockboxPolicyRequest":
        return cls(
            case_id=str(payload["case_id"]),
            family_id=str(payload["family_id"]),
            selected_candidate_id=str(payload["selected_candidate_id"]),
            finalist_candidate_ids=tuple(
                str(item) for item in payload["finalist_candidate_ids"]
            ),
            finalist_cap=int(payload["finalist_cap"]),
            evaluation_protocol_report=EvaluationProtocolReport.from_dict(
                dict(payload["evaluation_protocol_report"])
            ),
            lockbox_run_record=ResearchRunRecord.from_dict(
                dict(payload["lockbox_run_record"])
            ),
            access_events=tuple(
                LockboxAccessEvent.from_dict(dict(item))
                for item in payload["access_events"]
            ),
            contamination_incidents=tuple(
                LockboxIncidentRecord.from_dict(dict(item))
                for item in payload["contamination_incidents"]
            ),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
            schema_version=int(
                payload.get(
                    "schema_version", SUPPORTED_LOCKBOX_POLICY_SCHEMA_VERSION
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "LockboxPolicyRequest":
        return cls.from_dict(_decode_json_object(payload, label="lockbox_policy_request"))


@dataclass(frozen=True)
class LockboxPolicyReport:
    case_id: str
    status: str
    decision: str
    reason_code: str
    passed_count: int
    failed_count: int
    triggered_rule_ids: tuple[str, ...]
    selected_candidate_id: str
    finalist_candidate_ids: tuple[str, ...]
    finalist_cap: int
    contamination_incident_ids: tuple[str, ...]
    access_log_ids: tuple[str, ...]
    retained_artifact_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]
    check_results: tuple[LockboxPolicyCheckResult, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = _jsonable(asdict(self))
        payload["check_results"] = [item.to_dict() for item in self.check_results]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LockboxPolicyReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            decision=str(payload["decision"]),
            reason_code=str(payload["reason_code"]),
            passed_count=int(payload["passed_count"]),
            failed_count=int(payload["failed_count"]),
            triggered_rule_ids=tuple(str(item) for item in payload["triggered_rule_ids"]),
            selected_candidate_id=str(payload["selected_candidate_id"]),
            finalist_candidate_ids=tuple(
                str(item) for item in payload["finalist_candidate_ids"]
            ),
            finalist_cap=int(payload["finalist_cap"]),
            contamination_incident_ids=tuple(
                str(item) for item in payload["contamination_incident_ids"]
            ),
            access_log_ids=tuple(str(item) for item in payload["access_log_ids"]),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            check_results=tuple(
                LockboxPolicyCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utc_now())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "LockboxPolicyReport":
        return cls.from_dict(_decode_json_object(payload, label="lockbox_policy_report"))


def _check(
    *,
    check_id: str,
    check_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    evidence: dict[str, Any],
    remediation: str,
) -> LockboxPolicyCheckResult:
    return LockboxPolicyCheckResult(
        check_id=check_id,
        check_name=check_name,
        passed=passed,
        status=(
            LockboxPolicyStatus.PASS.value
            if passed
            else LockboxPolicyStatus.VIOLATION.value
        ),
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence=evidence,
        remediation=remediation,
    )


def _invalid_report(
    request: LockboxPolicyRequest, errors: list[str]
) -> LockboxPolicyReport:
    reason_bundle = tuple(errors) or ("lockbox request is invalid",)
    return LockboxPolicyReport(
        case_id=request.case_id,
        status=LockboxPolicyStatus.INVALID.value,
        decision=LockboxDecision.HOLD.value,
        reason_code="LOCKBOX_POLICY_REQUEST_INVALID",
        passed_count=0,
        failed_count=0,
        triggered_rule_ids=(),
        selected_candidate_id=request.selected_candidate_id,
        finalist_candidate_ids=request.finalist_candidate_ids,
        finalist_cap=request.finalist_cap,
        contamination_incident_ids=tuple(
            incident.incident_record_id for incident in request.contamination_incidents
        ),
        access_log_ids=tuple(event.access_log_id for event in request.access_events),
        retained_artifact_ids=(),
        correlation_ids=(),
        operator_reason_bundle=reason_bundle,
        check_results=(),
        explanation="Lockbox policy request is malformed and cannot be evaluated safely.",
        remediation="Repair the request shape before using the lockbox policy workflow.",
    )


def _validate_request(request: LockboxPolicyRequest) -> list[str]:
    errors: list[str] = []
    if request.schema_version != SUPPORTED_LOCKBOX_POLICY_SCHEMA_VERSION:
        errors.append("schema_version must match the supported lockbox policy version")
    if not request.case_id:
        errors.append("case_id is required")
    if not request.family_id:
        errors.append("family_id is required")
    if not request.selected_candidate_id:
        errors.append("selected_candidate_id is required")
    if not request.finalist_candidate_ids:
        errors.append("finalist_candidate_ids must not be empty")
    if len(set(request.finalist_candidate_ids)) != len(request.finalist_candidate_ids):
        errors.append("finalist_candidate_ids must be unique")
    if request.finalist_cap <= 0:
        errors.append("finalist_cap must be positive")
    if request.selected_candidate_id not in request.finalist_candidate_ids:
        errors.append("selected_candidate_id must be present in finalist_candidate_ids")
    if request.lockbox_run_record.family_id != request.family_id:
        errors.append("lockbox_run_record family_id must match the request family")
    if request.lockbox_run_record.run_purpose != ResearchRunPurpose.LOCKBOX:
        errors.append("lockbox_run_record must use the canonical lockbox run purpose")
    if not request.access_events:
        errors.append("lockbox access requires at least one recorded access event")
    if not _artifact_bundle_complete(request.artifact_bundle):
        errors.append("lockbox artifact_bundle must be complete")
    finalists = set(request.finalist_candidate_ids)
    for event in request.access_events:
        if not set(event.finalist_candidate_ids).issubset(finalists):
            errors.append(
                f"access event {event.access_event_id} references finalists outside the lockbox set"
            )
    for incident in request.contamination_incidents:
        if incident.candidate_id not in finalists:
            errors.append(
                f"incident {incident.incident_record_id} references a candidate outside the lockbox set"
            )
    return errors


def _evaluation_protocol_ready_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    lockbox_check = _protocol_check(request.evaluation_protocol_report, "EP08")
    passed = bool(lockbox_check and lockbox_check.passed)
    return _check(
        check_id="LP01",
        check_name="evaluation_protocol_lockbox_ready",
        passed=passed,
        reason_code=(
            "LOCKBOX_PROTOCOL_READY"
            if passed
            else "LOCKBOX_PROTOCOL_PREREQUISITE_MISSING"
        ),
        diagnostic=(
            "The upstream evaluation protocol retained a passing lockbox-readiness check."
            if passed
            else "Lockbox policy cannot proceed until the evaluation protocol records a passing EP08 lockbox-readiness check."
        ),
        evidence={
            "evaluation_status": request.evaluation_protocol_report.status,
            "evaluation_reason_code": request.evaluation_protocol_report.reason_code,
            "triggered_check_ids": list(
                request.evaluation_protocol_report.triggered_check_ids
            ),
            "lockbox_check_present": lockbox_check is not None,
            "lockbox_check_reason_code": (
                None if lockbox_check is None else lockbox_check.reason_code
            ),
        },
        remediation="Repair the evaluation protocol until lockbox readiness passes before final holdout access.",
    )


def _lockbox_run_recorded_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    record = request.lockbox_run_record
    passed = bool(
        record.run_purpose == ResearchRunPurpose.LOCKBOX
        and record.family_id == request.family_id
        and record.admissibility_class == ResearchAdmissibilityClass.RISK_POLICY_ADMISSIBLE
        and record.output_artifact_digests
    )
    return _check(
        check_id="LP02",
        check_name="lockbox_run_recorded",
        passed=passed,
        reason_code=(
            "LOCKBOX_RUN_RECORDED"
            if passed
            else "LOCKBOX_RUN_RECORD_INVALID"
        ),
        diagnostic=(
            "The lockbox access lane is anchored to a canonical lockbox research_run."
            if passed
            else "Lockbox access must reference a promotable lockbox research_run with retained output artifacts."
        ),
        evidence={
            "research_run_id": record.research_run_id,
            "run_purpose": record.run_purpose.value,
            "admissibility_class": record.admissibility_class.value,
            "family_id": record.family_id,
            "output_artifact_digests": list(record.output_artifact_digests),
        },
        remediation="Record the lockbox activity as a canonical lockbox research_run before freeze decisions are made.",
    )


def _bounded_finalist_check(request: LockboxPolicyRequest) -> LockboxPolicyCheckResult:
    finalists = request.finalist_candidate_ids
    passed = (
        0 < len(finalists) <= request.finalist_cap
        and request.selected_candidate_id in finalists
    )
    return _check(
        check_id="LP03",
        check_name="bounded_finalist_count",
        passed=passed,
        reason_code=(
            "LOCKBOX_FINALISTS_BOUNDED"
            if passed
            else "LOCKBOX_FINALIST_CAP_EXCEEDED"
        ),
        diagnostic=(
            "Lockbox entry keeps the finalist set within the bounded final-holdout limit."
            if passed
            else "Lockbox finalists must stay bounded and the selected candidate must already be inside that bounded set."
        ),
        evidence={
            "finalist_candidate_ids": list(finalists),
            "finalist_count": len(finalists),
            "finalist_cap": request.finalist_cap,
            "selected_candidate_id": request.selected_candidate_id,
        },
        remediation="Reduce the finalist set before lockbox entry and keep the chosen candidate inside the bounded cohort.",
    )


def _policy_controlled_access_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    finalists = set(request.finalist_candidate_ids)
    passed = bool(request.access_events) and all(
        event.access_log_id
        and event.approved_control_ids
        and set(event.finalist_candidate_ids).issubset(finalists)
        and (
            request.selected_candidate_id in event.finalist_candidate_ids
            or event.access_purpose == LockboxAccessPurpose.ADMIT_FINALISTS
            or event.access_purpose == LockboxAccessPurpose.INCIDENT_REVIEW
        )
        for event in request.access_events
    )
    return _check(
        check_id="LP04",
        check_name="policy_controlled_access",
        passed=passed,
        reason_code=(
            "LOCKBOX_ACCESS_LOGGED_AND_CONTROLLED"
            if passed
            else "LOCKBOX_ACCESS_CONTROL_MISSING"
        ),
        diagnostic=(
            "Every lockbox access event is logged and tied to explicit policy controls."
            if passed
            else "Lockbox access must be logged, policy-approved, and scoped to the finalist set."
        ),
        evidence={
            "access_events": [event.to_dict() for event in request.access_events],
            "selected_candidate_id": request.selected_candidate_id,
        },
        remediation="Record access logs and approval controls for each lockbox touch before reviewing or freezing a candidate.",
    )


def _no_ranking_surface_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    ranking_surface_event_ids = tuple(
        event.access_event_id
        for event in request.access_events
        if event.ranking_surface_accessed
    )
    passed = not ranking_surface_event_ids
    return _check(
        check_id="LP05",
        check_name="no_ranking_surface_access",
        passed=passed,
        reason_code=(
            "LOCKBOX_NOT_USED_FOR_RANKING"
            if passed
            else "LOCKBOX_RANKING_SURFACE_ACCESSED"
        ),
        diagnostic=(
            "The lockbox remained a promotion-grade holdout instead of another ranking loop."
            if passed
            else "A lockbox access event recorded ranking-surface usage, which contaminates the holdout."
        ),
        evidence={
            "ranking_surface_event_ids": list(ranking_surface_event_ids),
            "access_event_ids": [event.access_event_id for event in request.access_events],
        },
        remediation="Treat any ranking-style lockbox access as contamination and route the case through explicit incident review.",
    )


def _contamination_incident_handling_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    incidents = request.contamination_incidents
    documented = all(
        incident.incident_log_ids
        and incident.review_reference_ids
        and incident.reviewer_self_attestations
        and incident.disposition != LockboxContaminationDisposition.PENDING_REVIEW
        for incident in incidents
    )
    passed = not incidents or documented
    return _check(
        check_id="LP06",
        check_name="contamination_incident_handling",
        passed=passed,
        reason_code=(
            "LOCKBOX_CONTAMINATION_CLEAR"
            if not incidents
            else (
                "LOCKBOX_CONTAMINATION_HANDLED"
                if documented
                else "LOCKBOX_CONTAMINATION_REVIEW_MISSING"
            )
        ),
        diagnostic=(
            "No lockbox contamination incidents were recorded."
            if not incidents
            else (
                "Lockbox contamination incidents were escalated with review references and explicit reject-or-restart dispositions."
                if documented
                else "Lockbox contamination requires review references, reviewer attestations, and an explicit reject-or-restart disposition."
            )
        ),
        evidence={
            "incident_record_ids": [
                incident.incident_record_id for incident in request.contamination_incidents
            ],
            "incident_dispositions": [
                incident.disposition.value for incident in request.contamination_incidents
            ],
        },
        remediation="Document contamination with review references and explicit reject-or-restart handling before the lockbox lane can proceed.",
    )


def _retained_artifacts_check(
    request: LockboxPolicyRequest,
) -> LockboxPolicyCheckResult:
    passed = _artifact_bundle_complete(request.artifact_bundle)
    return _check(
        check_id="LP07",
        check_name="retained_lockbox_artifacts",
        passed=passed,
        reason_code=(
            "LOCKBOX_ARTIFACT_BUNDLE_COMPLETE"
            if passed
            else "LOCKBOX_ARTIFACT_BUNDLE_INCOMPLETE"
        ),
        diagnostic=(
            "The lockbox lane retained artifact manifests, logs, correlation ids, diffs, and operator reasons."
            if passed
            else "Lockbox policy requires a complete retained artifact bundle for later review."
        ),
        evidence=request.artifact_bundle.to_dict(),
        remediation="Retain the artifact manifest, logs, correlation ids, expected-versus-actual diffs, and operator reason bundle for the lockbox workflow.",
    )


def evaluate_lockbox_policy(request: LockboxPolicyRequest) -> LockboxPolicyReport:
    validation_errors = _validate_request(request)
    if validation_errors:
        return _invalid_report(request, validation_errors)

    checks = (
        _evaluation_protocol_ready_check(request),
        _lockbox_run_recorded_check(request),
        _bounded_finalist_check(request),
        _policy_controlled_access_check(request),
        _no_ranking_surface_check(request),
        _contamination_incident_handling_check(request),
        _retained_artifacts_check(request),
    )
    failed_checks = tuple(check for check in checks if not check.passed)
    passed_count = len(checks) - len(failed_checks)
    contamination_incidents = request.contamination_incidents
    incident_ids = tuple(
        incident.incident_record_id for incident in contamination_incidents
    )
    access_log_ids = _sorted_unique(
        [event.access_log_id for event in request.access_events]
    )
    retained_artifact_ids = _sorted_unique(
        list(request.evaluation_protocol_report.retained_artifact_ids)
        + list(request.lockbox_run_record.output_artifact_digests)
        + [request.artifact_bundle.artifact_manifest_id]
        + list(access_log_ids)
        + [
            item
            for incident in contamination_incidents
            for item in (
                *incident.incident_log_ids,
                *incident.review_reference_ids,
            )
        ]
    )
    correlation_ids = _sorted_unique(
        list(request.evaluation_protocol_report.correlation_ids)
        + list(request.artifact_bundle.correlation_ids)
    )
    operator_reason_bundle = _sorted_unique(
        list(request.evaluation_protocol_report.operator_reason_bundle)
        + list(request.artifact_bundle.operator_reason_bundle)
        + [incident.explanation for incident in contamination_incidents]
    )

    if failed_checks:
        first_failure = failed_checks[0]
        explanation = " ".join(check.diagnostic for check in failed_checks)
        remediation = " ".join(check.remediation for check in failed_checks)
        return LockboxPolicyReport(
            case_id=request.case_id,
            status=LockboxPolicyStatus.VIOLATION.value,
            decision=LockboxDecision.HOLD.value,
            reason_code=first_failure.reason_code,
            passed_count=passed_count,
            failed_count=len(failed_checks),
            triggered_rule_ids=tuple(check.check_id for check in failed_checks),
            selected_candidate_id=request.selected_candidate_id,
            finalist_candidate_ids=request.finalist_candidate_ids,
            finalist_cap=request.finalist_cap,
            contamination_incident_ids=incident_ids,
            access_log_ids=access_log_ids,
            retained_artifact_ids=retained_artifact_ids,
            correlation_ids=correlation_ids,
            operator_reason_bundle=operator_reason_bundle,
            check_results=checks,
            explanation=explanation,
            remediation=remediation,
        )

    if contamination_incidents:
        if any(
            incident.disposition == LockboxContaminationDisposition.RESTART_CYCLE
            for incident in contamination_incidents
        ):
            decision = LockboxDecision.RESTART_CYCLE
            reason_code = "LOCKBOX_CONTAMINATION_RESTART_REQUIRED"
            explanation = (
                "Lockbox contamination was documented and requires restarting the candidate cycle."
            )
            remediation = (
                "Restart the affected candidate cycle and keep the contaminated lockbox evidence out of promotion decisions."
            )
        else:
            decision = LockboxDecision.REJECT_CANDIDATE
            reason_code = "LOCKBOX_CONTAMINATION_REJECT_CANDIDATE"
            explanation = (
                "Lockbox contamination was documented and requires rejecting the affected candidate."
            )
            remediation = (
                "Reject the contaminated candidate and reopen selection only with uncontaminated finalists."
            )
        return LockboxPolicyReport(
            case_id=request.case_id,
            status=LockboxPolicyStatus.VIOLATION.value,
            decision=decision.value,
            reason_code=reason_code,
            passed_count=passed_count,
            failed_count=0,
            triggered_rule_ids=("LP06",),
            selected_candidate_id=request.selected_candidate_id,
            finalist_candidate_ids=request.finalist_candidate_ids,
            finalist_cap=request.finalist_cap,
            contamination_incident_ids=incident_ids,
            access_log_ids=access_log_ids,
            retained_artifact_ids=retained_artifact_ids,
            correlation_ids=correlation_ids,
            operator_reason_bundle=operator_reason_bundle,
            check_results=checks,
            explanation=explanation,
            remediation=remediation,
        )

    return LockboxPolicyReport(
        case_id=request.case_id,
        status=LockboxPolicyStatus.PASS.value,
        decision=LockboxDecision.FREEZE_CANDIDATE.value,
        reason_code="LOCKBOX_POLICY_CONTROLS_SATISFIED",
        passed_count=passed_count,
        failed_count=0,
        triggered_rule_ids=(),
        selected_candidate_id=request.selected_candidate_id,
        finalist_candidate_ids=request.finalist_candidate_ids,
        finalist_cap=request.finalist_cap,
        contamination_incident_ids=(),
        access_log_ids=access_log_ids,
        retained_artifact_ids=retained_artifact_ids,
        correlation_ids=correlation_ids,
        operator_reason_bundle=operator_reason_bundle,
        check_results=checks,
        explanation=(
            "The lockbox remained bounded, logged, and policy-controlled, so the finalist can proceed to candidate freeze."
        ),
        remediation="No remediation required.",
    )
