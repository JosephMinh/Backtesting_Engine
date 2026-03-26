"""Solo-governance workflow contract for waivers and incidents."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.metadata_telemetry import RECORD_DEFINITIONS
from shared.policy.policy_engine import PolicyWaiver


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        datetime.timezone.utc
    )


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


def _metadata_record_fields(record_id: str) -> set[str]:
    for record in RECORD_DEFINITIONS:
        if record.record_id == record_id:
            return {field.name for field in record.fields}
    return set()


VALIDATION_ERRORS: list[str] = []
if not any(record.record_id == "incident_record" for record in RECORD_DEFINITIONS):
    VALIDATION_ERRORS.append("solo_governance: incident_record metadata definition missing")
else:
    missing_incident_fields = {
        "incident_id",
        "incident_type",
        "severity",
        "opened_at_utc",
        "linked_policy_id",
    } - _metadata_record_fields("incident_record")
    if missing_incident_fields:
        VALIDATION_ERRORS.append(
            "solo_governance: incident_record metadata missing fields "
            f"{tuple(sorted(missing_incident_fields))}"
        )

if not any(
    field.name == "operator_attestation_id"
    for record in RECORD_DEFINITIONS
    for field in record.fields
):
    VALIDATION_ERRORS.append(
        "solo_governance: metadata contract must retain operator_attestation_id references"
    )

policy_waiver_fields = set(PolicyWaiver.__dataclass_fields__)
for required_field in ("waiver_id", "approved_by", "justification", "expires_at_utc"):
    if required_field not in policy_waiver_fields:
        VALIDATION_ERRORS.append(
            f"solo_governance: policy waiver contract missing field {required_field}"
        )


@unique
class SoloGovernanceStatus(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"
    INVALID = "invalid"


@unique
class SoloGovernancePath(str, Enum):
    NONE = "none"
    WAIVER = "waiver"
    INCIDENT = "incident"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class SelfAttestationStep:
    step_id: str
    attested_by: str
    signed_at_utc: str
    checklist_artifact_id: str
    checklist_digest: str
    signature_ref: str
    attested_controls: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["attested_controls"] = list(self.attested_controls)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SelfAttestationStep":
        return cls(
            step_id=str(payload["step_id"]),
            attested_by=str(payload["attested_by"]),
            signed_at_utc=str(payload["signed_at_utc"]),
            checklist_artifact_id=str(payload["checklist_artifact_id"]),
            checklist_digest=str(payload["checklist_digest"]),
            signature_ref=str(payload["signature_ref"]),
            attested_controls=tuple(str(item) for item in payload["attested_controls"]),
            rationale=str(payload["rationale"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "SelfAttestationStep":
        return cls.from_dict(_decode_json_object(payload, label="self_attestation_step"))


@dataclass(frozen=True)
class GovernanceWaiverRecord:
    waiver_id: str
    scope: str
    approved_by: str
    justification: str
    issued_at_utc: str
    expires_at_utc: str
    approval_artifact_id: str
    categories: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    related_incident_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["categories"] = list(self.categories)
        payload["rule_ids"] = list(self.rule_ids)
        payload["reason_codes"] = list(self.reason_codes)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GovernanceWaiverRecord":
        return cls(
            waiver_id=str(payload["waiver_id"]),
            scope=str(payload["scope"]),
            approved_by=str(payload["approved_by"]),
            justification=str(payload["justification"]),
            issued_at_utc=str(payload["issued_at_utc"]),
            expires_at_utc=str(payload["expires_at_utc"]),
            approval_artifact_id=str(payload["approval_artifact_id"]),
            categories=tuple(str(item) for item in payload.get("categories", ())),
            rule_ids=tuple(str(item) for item in payload.get("rule_ids", ())),
            reason_codes=tuple(str(item) for item in payload.get("reason_codes", ())),
            related_incident_id=(
                str(payload["related_incident_id"])
                if payload.get("related_incident_id") is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "GovernanceWaiverRecord":
        return cls.from_dict(_decode_json_object(payload, label="governance_waiver_record"))

    def to_policy_waiver(self) -> PolicyWaiver:
        return PolicyWaiver(
            waiver_id=self.waiver_id,
            categories=self.categories,
            rule_ids=self.rule_ids,
            reason_codes=self.reason_codes,
            approved_by=self.approved_by,
            justification=self.justification,
            expires_at_utc=self.expires_at_utc,
            related_incident_id=self.related_incident_id,
        )


@dataclass(frozen=True)
class GovernanceIncidentRecord:
    incident_id: str
    incident_type: str
    severity: str
    opened_at_utc: str
    linked_policy_id: str
    incident_summary: str
    corrective_action_owner: str
    corrective_action_due_at_utc: str
    corrective_action_summary: str
    review_artifact_id: str
    closed_at_utc: str | None = None
    closure_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GovernanceIncidentRecord":
        return cls(
            incident_id=str(payload["incident_id"]),
            incident_type=str(payload["incident_type"]),
            severity=str(payload["severity"]),
            opened_at_utc=str(payload["opened_at_utc"]),
            linked_policy_id=str(payload["linked_policy_id"]),
            incident_summary=str(payload["incident_summary"]),
            corrective_action_owner=str(payload["corrective_action_owner"]),
            corrective_action_due_at_utc=str(payload["corrective_action_due_at_utc"]),
            corrective_action_summary=str(payload["corrective_action_summary"]),
            review_artifact_id=str(payload["review_artifact_id"]),
            closed_at_utc=(
                str(payload["closed_at_utc"])
                if payload.get("closed_at_utc") is not None
                else None
            ),
            closure_summary=(
                str(payload["closure_summary"])
                if payload.get("closure_summary") is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "GovernanceIncidentRecord":
        return cls.from_dict(
            _decode_json_object(payload, label="governance_incident_record")
        )


@dataclass(frozen=True)
class SoloGovernanceCheckResult:
    check_id: str
    check_name: str
    passed: bool
    status: str
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoloGovernanceCheckResult":
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
class SoloGovernanceRequest:
    case_id: str
    operator_id: str
    policy_bundle_hash: str
    live_impacting_exception: bool
    evaluation_time_utc: str
    minimum_cooling_off_minutes: int
    attestation_steps: tuple[SelfAttestationStep, ...]
    waiver: GovernanceWaiverRecord | None = None
    incident: GovernanceIncidentRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["attestation_steps"] = [step.to_dict() for step in self.attestation_steps]
        payload["waiver"] = self.waiver.to_dict() if self.waiver is not None else None
        payload["incident"] = (
            self.incident.to_dict() if self.incident is not None else None
        )
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoloGovernanceRequest":
        return cls(
            case_id=str(payload["case_id"]),
            operator_id=str(payload["operator_id"]),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            live_impacting_exception=bool(payload["live_impacting_exception"]),
            evaluation_time_utc=str(payload["evaluation_time_utc"]),
            minimum_cooling_off_minutes=int(payload["minimum_cooling_off_minutes"]),
            attestation_steps=tuple(
                SelfAttestationStep.from_dict(step_payload)
                for step_payload in payload["attestation_steps"]
            ),
            waiver=(
                GovernanceWaiverRecord.from_dict(dict(payload["waiver"]))
                if payload.get("waiver") is not None
                else None
            ),
            incident=(
                GovernanceIncidentRecord.from_dict(dict(payload["incident"]))
                if payload.get("incident") is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "SoloGovernanceRequest":
        return cls.from_dict(_decode_json_object(payload, label="solo_governance_request"))


@dataclass(frozen=True)
class SoloGovernanceReport:
    case_id: str
    status: str
    reason_code: str
    governance_path: str
    operator_id: str
    policy_bundle_hash: str
    cooling_off_satisfied: bool
    cooling_off_minutes_observed: float
    waiver_active: bool | None
    incident_closed: bool | None
    attestation_step_ids: tuple[str, ...]
    checklist_artifact_ids: tuple[str, ...]
    audit_record_ids: tuple[str, ...]
    decision_trace: tuple[SoloGovernanceCheckResult, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision_trace"] = [item.to_dict() for item in self.decision_trace]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SoloGovernanceReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            governance_path=str(payload["governance_path"]),
            operator_id=str(payload["operator_id"]),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            cooling_off_satisfied=bool(payload["cooling_off_satisfied"]),
            cooling_off_minutes_observed=float(payload["cooling_off_minutes_observed"]),
            waiver_active=payload.get("waiver_active"),
            incident_closed=payload.get("incident_closed"),
            attestation_step_ids=tuple(
                str(item) for item in payload["attestation_step_ids"]
            ),
            checklist_artifact_ids=tuple(
                str(item) for item in payload["checklist_artifact_ids"]
            ),
            audit_record_ids=tuple(str(item) for item in payload["audit_record_ids"]),
            decision_trace=tuple(
                SoloGovernanceCheckResult.from_dict(dict(item))
                for item in payload["decision_trace"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utc_now())),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "SoloGovernanceReport":
        return cls.from_dict(_decode_json_object(payload, label="solo_governance_report"))


def _governance_path(request: SoloGovernanceRequest) -> SoloGovernancePath:
    if request.waiver is not None and request.incident is not None:
        return SoloGovernancePath.CONFLICT
    if request.waiver is not None:
        return SoloGovernancePath.WAIVER
    if request.incident is not None:
        return SoloGovernancePath.INCIDENT
    return SoloGovernancePath.NONE


def _check_attestation_steps(request: SoloGovernanceRequest) -> SoloGovernanceCheckResult:
    step_ids = [step.step_id for step in request.attestation_steps]
    duplicate_step_ids = tuple(
        sorted(step_id for step_id in set(step_ids) if step_ids.count(step_id) > 1)
    )
    mismatched_attestors = tuple(
        sorted(
            step.step_id
            for step in request.attestation_steps
            if step.attested_by != request.operator_id
        )
    )
    passed = (
        len(request.attestation_steps) >= 2
        and not duplicate_step_ids
        and not mismatched_attestors
    )
    status = (
        SoloGovernanceStatus.PASS.value
        if passed
        else SoloGovernanceStatus.INVALID.value
    )
    reason_code = (
        "SOLO_GOVERNANCE_ATTESTATION_STEPS_VALID"
        if passed
        else "SOLO_GOVERNANCE_ATTESTATION_STEPS_INVALID"
    )
    diagnostic = (
        "Solo governance retained time-separated self-attestation steps for the operator."
        if passed
        else (
            "Solo governance requires at least two unique self-attestation steps by the "
            f"same operator. duplicate_step_ids={duplicate_step_ids}, "
            f"mismatched_attestors={mismatched_attestors}."
        )
    )
    return SoloGovernanceCheckResult(
        check_id="SG01",
        check_name="two_step_self_attestation",
        passed=passed,
        status=status,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "operator_id": request.operator_id,
            "attestation_step_ids": step_ids,
            "duplicate_step_ids": list(duplicate_step_ids),
            "mismatched_attestors": list(mismatched_attestors),
        },
        remediation="Record two unique self-attestation steps signed by the solo operator.",
    )


def _cooling_off_minutes_observed(
    request: SoloGovernanceRequest,
) -> float:
    if len(request.attestation_steps) < 2:
        return 0.0
    ordered_steps = sorted(request.attestation_steps, key=lambda step: step.signed_at_utc)
    return (
        _parse_utc(ordered_steps[-1].signed_at_utc)
        - _parse_utc(ordered_steps[0].signed_at_utc)
    ).total_seconds() / 60.0


def _check_cooling_off(request: SoloGovernanceRequest) -> SoloGovernanceCheckResult:
    observed_minutes = _cooling_off_minutes_observed(request)
    passed = observed_minutes >= request.minimum_cooling_off_minutes
    status = (
        SoloGovernanceStatus.PASS.value
        if passed
        else SoloGovernanceStatus.VIOLATION.value
    )
    reason_code = (
        "SOLO_GOVERNANCE_COOLING_OFF_SATISFIED"
        if passed
        else "SOLO_GOVERNANCE_COOLING_OFF_UNSATISFIED"
    )
    diagnostic = (
        "Attestation steps are separated by the required cooling-off interval."
        if passed
        else (
            "Attestation steps are too close together for solo governance: "
            f"{observed_minutes:.1f}m < {request.minimum_cooling_off_minutes}m."
        )
    )
    return SoloGovernanceCheckResult(
        check_id="SG02",
        check_name="cooling_off_interval",
        passed=passed,
        status=status,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "minimum_cooling_off_minutes": request.minimum_cooling_off_minutes,
            "cooling_off_minutes_observed": observed_minutes,
        },
        remediation="Wait through the cooling-off interval before signing the final attestation.",
    )


def _check_signed_checklists(
    request: SoloGovernanceRequest,
) -> SoloGovernanceCheckResult:
    incomplete_steps = tuple(
        sorted(
            step.step_id
            for step in request.attestation_steps
            if not (
                step.checklist_artifact_id
                and step.checklist_digest
                and step.signature_ref
                and step.attested_controls
                and step.rationale
            )
        )
    )
    passed = not incomplete_steps
    status = (
        SoloGovernanceStatus.PASS.value
        if passed
        else SoloGovernanceStatus.INVALID.value
    )
    reason_code = (
        "SOLO_GOVERNANCE_SIGNED_CHECKLISTS_PRESENT"
        if passed
        else "SOLO_GOVERNANCE_SIGNED_CHECKLISTS_MISSING"
    )
    diagnostic = (
        "Each attestation retains a signed checklist artifact and rationale."
        if passed
        else f"Attestation steps missing signed checklist evidence: {incomplete_steps}."
    )
    return SoloGovernanceCheckResult(
        check_id="SG03",
        check_name="signed_checklist_artifacts",
        passed=passed,
        status=status,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "checklist_artifact_ids": [
                step.checklist_artifact_id for step in request.attestation_steps
            ],
            "incomplete_step_ids": list(incomplete_steps),
        },
        remediation="Attach signed checklist artifacts, digests, and rationale to every attestation step.",
    )


def _check_exception_capture(
    request: SoloGovernanceRequest,
) -> SoloGovernanceCheckResult:
    path = _governance_path(request)
    passed = (
        not request.live_impacting_exception
        or path in {SoloGovernancePath.WAIVER, SoloGovernancePath.INCIDENT}
    ) and path != SoloGovernancePath.CONFLICT
    status = (
        SoloGovernanceStatus.PASS.value
        if passed
        else SoloGovernanceStatus.VIOLATION.value
    )
    if path == SoloGovernancePath.CONFLICT:
        reason_code = "SOLO_GOVERNANCE_EXCEPTION_PATH_CONFLICT"
        diagnostic = (
            "Live-impacting exceptions must use exactly one workflow path, not both waiver and incident."
        )
    elif not request.live_impacting_exception:
        reason_code = "SOLO_GOVERNANCE_NO_EXCEPTION_PATH_REQUIRED"
        diagnostic = "No live-impacting exception was declared, so no waiver or incident path is required."
    elif path == SoloGovernancePath.NONE:
        reason_code = "SOLO_GOVERNANCE_LIVE_EXCEPTION_UNTRACKED"
        diagnostic = (
            "Live-impacting exception has no explicit waiver or incident record; operator judgment is untracked."
        )
    else:
        reason_code = "SOLO_GOVERNANCE_EXCEPTION_CAPTURED"
        diagnostic = f"Live-impacting exception is captured through the {path.value} workflow."
    return SoloGovernanceCheckResult(
        check_id="SG04",
        check_name="explicit_exception_capture",
        passed=passed,
        status=status,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "live_impacting_exception": request.live_impacting_exception,
            "governance_path": path.value,
        },
        remediation="Record exactly one explicit waiver or incident for every live-impacting exception.",
    )


def _check_waiver_details(
    request: SoloGovernanceRequest,
) -> SoloGovernanceCheckResult:
    if request.waiver is None:
        return SoloGovernanceCheckResult(
            check_id="SG05",
            check_name="waiver_expiry_and_scope",
            passed=True,
            status=SoloGovernanceStatus.PASS.value,
            reason_code="SOLO_GOVERNANCE_WAIVER_NOT_USED",
            diagnostic="No waiver record was used for this governance path.",
            evidence={"governance_path": _governance_path(request).value},
            remediation="No remediation required.",
        )

    waiver = request.waiver
    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "waiver_id": waiver.waiver_id,
            "scope": waiver.scope,
            "approved_by": waiver.approved_by,
            "justification": waiver.justification,
            "issued_at_utc": waiver.issued_at_utc,
            "expires_at_utc": waiver.expires_at_utc,
            "approval_artifact_id": waiver.approval_artifact_id,
        }.items()
        if not field_value
    )
    if missing_fields:
        return SoloGovernanceCheckResult(
            check_id="SG05",
            check_name="waiver_expiry_and_scope",
            passed=False,
            status=SoloGovernanceStatus.INVALID.value,
            reason_code="SOLO_GOVERNANCE_WAIVER_FIELDS_MISSING",
            diagnostic=f"Waiver record is missing required fields: {missing_fields}.",
            evidence={"missing_fields": list(missing_fields)},
            remediation="Populate waiver scope, approval artifact, justification, and expiry fields.",
        )

    issued_at = _parse_utc(waiver.issued_at_utc)
    expires_at = _parse_utc(waiver.expires_at_utc)
    evaluation_time = _parse_utc(request.evaluation_time_utc)
    if expires_at <= issued_at:
        return SoloGovernanceCheckResult(
            check_id="SG05",
            check_name="waiver_expiry_and_scope",
            passed=False,
            status=SoloGovernanceStatus.INVALID.value,
            reason_code="SOLO_GOVERNANCE_WAIVER_EXPIRY_INVALID",
            diagnostic="Waiver expiry must be later than its issuance time.",
            evidence={
                "issued_at_utc": waiver.issued_at_utc,
                "expires_at_utc": waiver.expires_at_utc,
            },
            remediation="Issue waivers with a forward expiry boundary.",
        )

    if evaluation_time > expires_at:
        return SoloGovernanceCheckResult(
            check_id="SG05",
            check_name="waiver_expiry_and_scope",
            passed=False,
            status=SoloGovernanceStatus.VIOLATION.value,
            reason_code="SOLO_GOVERNANCE_WAIVER_EXPIRED",
            diagnostic="Waiver has expired and can no longer justify live-impacting behavior.",
            evidence={
                "waiver_id": waiver.waiver_id,
                "scope": waiver.scope,
                "expires_at_utc": waiver.expires_at_utc,
                "approval_artifact_id": waiver.approval_artifact_id,
            },
            remediation="Renew the waiver through a fresh review or remove the exception path.",
        )

    return SoloGovernanceCheckResult(
        check_id="SG05",
        check_name="waiver_expiry_and_scope",
        passed=True,
        status=SoloGovernanceStatus.PASS.value,
        reason_code="SOLO_GOVERNANCE_WAIVER_ACTIVE",
        diagnostic="Waiver remains active, scoped, and time-bounded.",
        evidence={
            "waiver_id": waiver.waiver_id,
            "scope": waiver.scope,
            "expires_at_utc": waiver.expires_at_utc,
            "approval_artifact_id": waiver.approval_artifact_id,
        },
        remediation="No remediation required.",
    )


def _check_incident_closure(
    request: SoloGovernanceRequest,
) -> SoloGovernanceCheckResult:
    if request.incident is None:
        return SoloGovernanceCheckResult(
            check_id="SG06",
            check_name="incident_corrective_action_closure",
            passed=True,
            status=SoloGovernanceStatus.PASS.value,
            reason_code="SOLO_GOVERNANCE_INCIDENT_NOT_USED",
            diagnostic="No incident record was used for this governance path.",
            evidence={"governance_path": _governance_path(request).value},
            remediation="No remediation required.",
        )

    incident = request.incident
    missing_fields = tuple(
        field_name
        for field_name, field_value in {
            "incident_id": incident.incident_id,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "opened_at_utc": incident.opened_at_utc,
            "linked_policy_id": incident.linked_policy_id,
            "incident_summary": incident.incident_summary,
            "corrective_action_owner": incident.corrective_action_owner,
            "corrective_action_due_at_utc": incident.corrective_action_due_at_utc,
            "corrective_action_summary": incident.corrective_action_summary,
            "review_artifact_id": incident.review_artifact_id,
        }.items()
        if not field_value
    )
    if missing_fields:
        return SoloGovernanceCheckResult(
            check_id="SG06",
            check_name="incident_corrective_action_closure",
            passed=False,
            status=SoloGovernanceStatus.INVALID.value,
            reason_code="SOLO_GOVERNANCE_INCIDENT_FIELDS_MISSING",
            diagnostic=f"Incident record is missing required fields: {missing_fields}.",
            evidence={"missing_fields": list(missing_fields)},
            remediation="Populate the incident record with corrective-action ownership and review evidence.",
        )

    opened_at = _parse_utc(incident.opened_at_utc)
    corrective_action_due_at = _parse_utc(incident.corrective_action_due_at_utc)
    if corrective_action_due_at < opened_at:
        return SoloGovernanceCheckResult(
            check_id="SG06",
            check_name="incident_corrective_action_closure",
            passed=False,
            status=SoloGovernanceStatus.INVALID.value,
            reason_code="SOLO_GOVERNANCE_INCIDENT_DUE_AT_INVALID",
            diagnostic="Corrective-action due time must not precede incident open time.",
            evidence={
                "opened_at_utc": incident.opened_at_utc,
                "corrective_action_due_at_utc": incident.corrective_action_due_at_utc,
            },
            remediation="Set the corrective-action due time after the incident opens.",
        )

    if not incident.closed_at_utc or not incident.closure_summary:
        return SoloGovernanceCheckResult(
            check_id="SG06",
            check_name="incident_corrective_action_closure",
            passed=False,
            status=SoloGovernanceStatus.VIOLATION.value,
            reason_code="SOLO_GOVERNANCE_INCIDENT_REQUIRES_CLOSURE",
            diagnostic=(
                "Incident record has corrective-action tracking but lacks explicit closure evidence."
            ),
            evidence={
                "incident_id": incident.incident_id,
                "corrective_action_owner": incident.corrective_action_owner,
                "corrective_action_due_at_utc": incident.corrective_action_due_at_utc,
                "review_artifact_id": incident.review_artifact_id,
            },
            remediation="Close the incident with a corrective-action summary before relying on it as governance evidence.",
        )

    closed_at = _parse_utc(incident.closed_at_utc)
    if closed_at < opened_at:
        return SoloGovernanceCheckResult(
            check_id="SG06",
            check_name="incident_corrective_action_closure",
            passed=False,
            status=SoloGovernanceStatus.INVALID.value,
            reason_code="SOLO_GOVERNANCE_INCIDENT_CLOSURE_INVALID",
            diagnostic="Incident closure time must not precede incident open time.",
            evidence={
                "opened_at_utc": incident.opened_at_utc,
                "closed_at_utc": incident.closed_at_utc,
            },
            remediation="Record incident closure after the incident opens.",
        )

    return SoloGovernanceCheckResult(
        check_id="SG06",
        check_name="incident_corrective_action_closure",
        passed=True,
        status=SoloGovernanceStatus.PASS.value,
        reason_code="SOLO_GOVERNANCE_INCIDENT_CLOSED",
        diagnostic="Incident record retains corrective-action ownership and explicit closure.",
        evidence={
            "incident_id": incident.incident_id,
            "closed_at_utc": incident.closed_at_utc,
            "review_artifact_id": incident.review_artifact_id,
        },
        remediation="No remediation required.",
    )


def evaluate_solo_governance(request: SoloGovernanceRequest) -> SoloGovernanceReport:
    decision_trace = (
        _check_attestation_steps(request),
        _check_cooling_off(request),
        _check_signed_checklists(request),
        _check_exception_capture(request),
        _check_waiver_details(request),
        _check_incident_closure(request),
    )
    invalid_failures = [
        item for item in decision_trace if not item.passed and item.status == "invalid"
    ]
    violation_failures = [
        item for item in decision_trace if not item.passed and item.status == "violation"
    ]
    if invalid_failures:
        status = SoloGovernanceStatus.INVALID.value
        reason_code = invalid_failures[0].reason_code
        explanation = invalid_failures[0].diagnostic
        remediation = invalid_failures[0].remediation
    elif violation_failures:
        status = SoloGovernanceStatus.VIOLATION.value
        reason_code = violation_failures[0].reason_code
        explanation = violation_failures[0].diagnostic
        remediation = violation_failures[0].remediation
    else:
        path = _governance_path(request)
        if path == SoloGovernancePath.WAIVER:
            reason_code = "SOLO_GOVERNANCE_WAIVER_ACTIVE"
            explanation = (
                "Solo governance passed with time-separated attestations, signed checklists, "
                "and an active reviewed waiver."
            )
        elif path == SoloGovernancePath.INCIDENT:
            reason_code = "SOLO_GOVERNANCE_INCIDENT_CLOSED"
            explanation = (
                "Solo governance passed with time-separated attestations and a closed incident "
                "that retains corrective-action closure."
            )
        else:
            reason_code = "SOLO_GOVERNANCE_NO_EXCEPTION_PATH_REQUIRED"
            explanation = (
                "Solo governance passed because no live-impacting exception required waiver or incident handling."
            )
        status = SoloGovernanceStatus.PASS.value
        remediation = "No remediation required."

    path = _governance_path(request)
    cooling_off_report = next(item for item in decision_trace if item.check_id == "SG02")
    waiver_report = next(item for item in decision_trace if item.check_id == "SG05")
    incident_report = next(item for item in decision_trace if item.check_id == "SG06")
    return SoloGovernanceReport(
        case_id=request.case_id,
        status=status,
        reason_code=reason_code,
        governance_path=path.value,
        operator_id=request.operator_id,
        policy_bundle_hash=request.policy_bundle_hash,
        cooling_off_satisfied=cooling_off_report.passed,
        cooling_off_minutes_observed=float(
            cooling_off_report.evidence["cooling_off_minutes_observed"]
        ),
        waiver_active=waiver_report.passed if request.waiver is not None else None,
        incident_closed=incident_report.passed if request.incident is not None else None,
        attestation_step_ids=tuple(step.step_id for step in request.attestation_steps),
        checklist_artifact_ids=tuple(
            step.checklist_artifact_id for step in request.attestation_steps
        ),
        audit_record_ids=tuple(
            [step.step_id for step in request.attestation_steps]
            + ([request.waiver.waiver_id] if request.waiver is not None else [])
            + ([request.incident.incident_id] if request.incident is not None else [])
        ),
        decision_trace=decision_trace,
        explanation=explanation,
        remediation=remediation,
    )
