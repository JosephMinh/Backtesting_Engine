"""Signed release certification and correction-impact handling contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.metadata_telemetry import RECORD_DEFINITIONS, StorageClass
from shared.policy.release_schemas import (
    ReleaseLifecycleState,
    ReleaseStatus,
    release_definitions_by_kind,
)

SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION = 1


@unique
class CorrectionImpactClass(str, Enum):
    NONE = "none"
    DIAGNOSTIC_ONLY = "diagnostic_only"
    RECERT_REQUIRED = "recert_required"
    SUSPECT = "suspect"


@unique
class DependentSurfaceKind(str, Enum):
    ANALYTIC_RELEASE = "analytic_release"
    CANDIDATE_READINESS_RECORD = "candidate_readiness_record"
    DATA_PROFILE_RELEASE = "data_profile_release"
    PORTABILITY_STUDY = "portability_study"


@unique
class DependentUpdateAction(str, Enum):
    ANNOTATE = "annotate"
    QUARANTINE = "quarantine"
    RECERTIFY = "recertify"
    RETAIN = "retain"
    SUPERSEDE = "supersede"


@dataclass(frozen=True)
class DependentPolicyUpdate:
    surface_kind: DependentSurfaceKind
    surface_id: str
    action: DependentUpdateAction
    reason_bundle: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["surface_kind"] = self.surface_kind.value
        payload["action"] = self.action.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DependentPolicyUpdate":
        return cls(
            surface_kind=DependentSurfaceKind(payload["surface_kind"]),
            surface_id=str(payload["surface_id"]),
            action=DependentUpdateAction(payload["action"]),
            reason_bundle=str(payload["reason_bundle"]),
        )


@dataclass(frozen=True)
class ReleaseCertificationRecord:
    certification_id: str
    release_kind: str
    release_id: str
    deterministic_manifest_hash: str
    prior_release_semantic_diff_hash: str
    validation_summary_hash: str
    policy_evaluation_hash: str
    canary_or_parity_required: bool
    canary_or_parity_evidence_ids: tuple[str, ...]
    signed_certification_report_hash: str
    signer_ids: tuple[str, ...]
    certified_at_utc: str
    lifecycle_state: ReleaseLifecycleState
    schema_version: int = SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReleaseCertificationRecord":
        return cls(
            certification_id=str(payload["certification_id"]),
            release_kind=str(payload["release_kind"]),
            release_id=str(payload["release_id"]),
            deterministic_manifest_hash=str(payload["deterministic_manifest_hash"]),
            prior_release_semantic_diff_hash=str(payload["prior_release_semantic_diff_hash"]),
            validation_summary_hash=str(payload["validation_summary_hash"]),
            policy_evaluation_hash=str(payload["policy_evaluation_hash"]),
            canary_or_parity_required=bool(payload["canary_or_parity_required"]),
            canary_or_parity_evidence_ids=tuple(
                str(item) for item in payload["canary_or_parity_evidence_ids"]
            ),
            signed_certification_report_hash=str(payload["signed_certification_report_hash"]),
            signer_ids=tuple(str(item) for item in payload["signer_ids"]),
            certified_at_utc=str(payload["certified_at_utc"]),
            lifecycle_state=ReleaseLifecycleState(payload["lifecycle_state"]),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReleaseCertificationRecord":
        return cls.from_dict(_decode_payload(payload, "release_certification_record"))


@dataclass(frozen=True)
class ReleaseCorrectionEvent:
    correction_event_id: str
    release_kind: str
    release_id: str
    certified_vendor_revision_watermark: str
    corrected_vendor_revision_watermark: str
    semantic_impact_diff_hash: str
    impact_class: CorrectionImpactClass
    preserves_prior_reproducibility: bool
    superseding_release_id: str | None
    dependent_updates: tuple[DependentPolicyUpdate, ...]
    justification: str
    recorded_at_utc: str
    schema_version: int = SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["impact_class"] = self.impact_class.value
        payload["dependent_updates"] = [update.to_dict() for update in self.dependent_updates]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReleaseCorrectionEvent":
        return cls(
            correction_event_id=str(payload["correction_event_id"]),
            release_kind=str(payload["release_kind"]),
            release_id=str(payload["release_id"]),
            certified_vendor_revision_watermark=str(payload["certified_vendor_revision_watermark"]),
            corrected_vendor_revision_watermark=str(payload["corrected_vendor_revision_watermark"]),
            semantic_impact_diff_hash=str(payload["semantic_impact_diff_hash"]),
            impact_class=CorrectionImpactClass(payload["impact_class"]),
            preserves_prior_reproducibility=bool(payload["preserves_prior_reproducibility"]),
            superseding_release_id=(
                str(payload["superseding_release_id"])
                if payload.get("superseding_release_id")
                else None
            ),
            dependent_updates=tuple(
                DependentPolicyUpdate.from_dict(item) for item in payload["dependent_updates"]
            ),
            justification=str(payload["justification"]),
            recorded_at_utc=str(payload["recorded_at_utc"]),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReleaseCorrectionEvent":
        return cls.from_dict(_decode_payload(payload, "release_correction_event"))


@dataclass(frozen=True)
class ReleaseCertificationReport:
    certification_id: str | None
    release_kind: str | None
    release_id: str | None
    lifecycle_state: str | None
    status: str
    usable: bool
    reason_code: str
    missing_fields: tuple[str, ...]
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
class ReleaseCorrectionReport:
    correction_event_id: str | None
    release_id: str | None
    release_kind: str | None
    impact_class: str | None
    status: str
    reason_code: str
    superseding_release_id: str | None
    dependent_actions: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _decode_payload(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _allowed_actions(impact_class: CorrectionImpactClass) -> tuple[DependentUpdateAction, ...]:
    if impact_class == CorrectionImpactClass.NONE:
        return (DependentUpdateAction.RETAIN, DependentUpdateAction.ANNOTATE)
    if impact_class == CorrectionImpactClass.DIAGNOSTIC_ONLY:
        return (DependentUpdateAction.ANNOTATE, DependentUpdateAction.RETAIN)
    if impact_class == CorrectionImpactClass.RECERT_REQUIRED:
        return (DependentUpdateAction.RECERTIFY, DependentUpdateAction.SUPERSEDE)
    return (DependentUpdateAction.QUARANTINE, DependentUpdateAction.SUPERSEDE)


def policy_actions_for_impact_class(
    impact_class: CorrectionImpactClass,
) -> tuple[str, ...]:
    return tuple(action.value for action in _allowed_actions(impact_class))


def _missing_certification_fields(
    record: ReleaseCertificationRecord,
) -> tuple[str, ...]:
    missing: list[str] = []
    required_scalars = {
        "certification_id": record.certification_id,
        "release_kind": record.release_kind,
        "release_id": record.release_id,
        "deterministic_manifest_hash": record.deterministic_manifest_hash,
        "prior_release_semantic_diff_hash": record.prior_release_semantic_diff_hash,
        "validation_summary_hash": record.validation_summary_hash,
        "policy_evaluation_hash": record.policy_evaluation_hash,
        "signed_certification_report_hash": record.signed_certification_report_hash,
        "certified_at_utc": record.certified_at_utc,
    }
    for field_name, field_value in required_scalars.items():
        if not field_value:
            missing.append(field_name)
    required_sequences = {
        "signer_ids": record.signer_ids,
    }
    for field_name, field_value in required_sequences.items():
        if not field_value:
            missing.append(field_name)
    return tuple(missing)


def _missing_correction_fields(event: ReleaseCorrectionEvent) -> tuple[str, ...]:
    missing: list[str] = []
    required_scalars = {
        "correction_event_id": event.correction_event_id,
        "release_kind": event.release_kind,
        "release_id": event.release_id,
        "certified_vendor_revision_watermark": event.certified_vendor_revision_watermark,
        "corrected_vendor_revision_watermark": event.corrected_vendor_revision_watermark,
        "semantic_impact_diff_hash": event.semantic_impact_diff_hash,
        "justification": event.justification,
        "recorded_at_utc": event.recorded_at_utc,
    }
    for field_name, field_value in required_scalars.items():
        if not field_value:
            missing.append(field_name)
    if not event.dependent_updates:
        missing.append("dependent_updates")
    return tuple(missing)


def validate_release_certification(
    record: ReleaseCertificationRecord,
) -> ReleaseCertificationReport:
    if record.schema_version != SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION:
        return ReleaseCertificationReport(
            certification_id=record.certification_id or None,
            release_kind=record.release_kind or None,
            release_id=record.release_id or None,
            lifecycle_state=record.lifecycle_state.value,
            status=ReleaseStatus.INVALID.value,
            usable=False,
            reason_code="RELEASE_CERTIFICATION_SCHEMA_VERSION_UNSUPPORTED",
            missing_fields=(),
            explanation="The certification record uses an unsupported canonical schema version.",
            remediation="Regenerate the certification record with the supported schema version.",
        )

    if record.release_kind not in release_definitions_by_kind():
        return ReleaseCertificationReport(
            certification_id=record.certification_id or None,
            release_kind=record.release_kind or None,
            release_id=record.release_id or None,
            lifecycle_state=record.lifecycle_state.value,
            status=ReleaseStatus.INVALID.value,
            usable=False,
            reason_code="RELEASE_CERTIFICATION_UNKNOWN_RELEASE_KIND",
            missing_fields=(),
            explanation="The certification record references an unknown canonical release kind.",
            remediation="Bind the certification record to a defined release kind before use.",
        )

    missing_fields = _missing_certification_fields(record)
    if missing_fields:
        return ReleaseCertificationReport(
            certification_id=record.certification_id or None,
            release_kind=record.release_kind,
            release_id=record.release_id or None,
            lifecycle_state=record.lifecycle_state.value,
            status=ReleaseStatus.INVALID.value,
            usable=False,
            reason_code="RELEASE_CERTIFICATION_MISSING_REQUIRED_EVIDENCE",
            missing_fields=missing_fields,
            explanation=(
                "The certification record is missing required manifest, diff, summary, policy, "
                f"or signer evidence: {missing_fields}."
            ),
            remediation="Populate every required evidence hash and signer before certifying the release.",
        )

    if record.canary_or_parity_required and not record.canary_or_parity_evidence_ids:
        return ReleaseCertificationReport(
            certification_id=record.certification_id,
            release_kind=record.release_kind,
            release_id=record.release_id,
            lifecycle_state=record.lifecycle_state.value,
            status=ReleaseStatus.VIOLATION.value,
            usable=False,
            reason_code="RELEASE_CERTIFICATION_CANARY_EVIDENCE_REQUIRED",
            missing_fields=(),
            explanation=(
                "The release was marked as requiring canary or parity evidence, but no such "
                "evidence ids were recorded."
            ),
            remediation="Attach the relevant canary or parity evidence before marking the release usable.",
        )

    if record.lifecycle_state not in {
        ReleaseLifecycleState.CERTIFIED,
        ReleaseLifecycleState.APPROVED,
        ReleaseLifecycleState.PUBLISHED,
    }:
        return ReleaseCertificationReport(
            certification_id=record.certification_id,
            release_kind=record.release_kind,
            release_id=record.release_id,
            lifecycle_state=record.lifecycle_state.value,
            status=ReleaseStatus.VIOLATION.value,
            usable=False,
            reason_code="RELEASE_CERTIFICATION_RELEASE_NOT_USABLE_STATE",
            missing_fields=(),
            explanation=(
                "A release is usable only when its lifecycle state is certified, approved, or "
                "published in addition to carrying the certification evidence."
            ),
            remediation="Advance the release through certification or treat it as non-usable.",
        )

    return ReleaseCertificationReport(
        certification_id=record.certification_id,
        release_kind=record.release_kind,
        release_id=record.release_id,
        lifecycle_state=record.lifecycle_state.value,
        status=ReleaseStatus.PASS.value,
        usable=True,
        reason_code="RELEASE_CERTIFICATION_USABLE",
        missing_fields=(),
        explanation=(
            "The release carries deterministic manifests, semantic diff evidence, validation "
            "summary, policy evaluation, signatures, and any required canary evidence."
        ),
        remediation="No remediation required.",
    )


def evaluate_release_correction(
    event: ReleaseCorrectionEvent,
) -> ReleaseCorrectionReport:
    if event.schema_version != SUPPORTED_RELEASE_CERTIFICATION_SCHEMA_VERSION:
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id or None,
            release_id=event.release_id or None,
            release_kind=event.release_kind or None,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_CORRECTION_SCHEMA_VERSION_UNSUPPORTED",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=(),
            explanation="The correction event uses an unsupported canonical schema version.",
            remediation="Regenerate the correction event with the supported schema version.",
        )

    missing_fields = _missing_correction_fields(event)
    if missing_fields:
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id or None,
            release_id=event.release_id or None,
            release_kind=event.release_kind or None,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_CORRECTION_MISSING_REQUIRED_FIELDS",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=(),
            explanation=(
                "The correction event is missing required watermark, diff, justification, or "
                f"dependent update fields: {missing_fields}."
            ),
            remediation="Populate every required correction field before recording the event.",
        )

    if event.release_kind != "dataset_release":
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id,
            release_id=event.release_id,
            release_kind=event.release_kind,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_CORRECTION_UNSUPPORTED_RELEASE_KIND",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=(),
            explanation=(
                "Vendor correction events currently anchor on certified dataset releases because "
                "they are the root source of correction watermarks."
            ),
            remediation="Record the correction against the affected dataset release.",
        )

    if (
        event.certified_vendor_revision_watermark
        == event.corrected_vendor_revision_watermark
    ):
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id,
            release_id=event.release_id,
            release_kind=event.release_kind,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.INVALID.value,
            reason_code="RELEASE_CORRECTION_WATERMARK_UNCHANGED",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=(),
            explanation=(
                "A correction event must compare the certified watermark against a different "
                "corrected watermark."
            ),
            remediation="Record the upstream corrected watermark that triggered the event.",
        )

    if not event.preserves_prior_reproducibility:
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id,
            release_id=event.release_id,
            release_kind=event.release_kind,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.VIOLATION.value,
            reason_code="RELEASE_CORRECTION_REPRODUCIBILITY_NOT_PRESERVED",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=tuple(update.action.value for update in event.dependent_updates),
            explanation=(
                "Correction handling must preserve reproducibility of the originally certified "
                "release while making any superseding release explicit."
            ),
            remediation="Retain the original release and record the correction through supersession metadata.",
        )

    allowed_actions = _allowed_actions(event.impact_class)
    disallowed_updates = tuple(
        update.action.value
        for update in event.dependent_updates
        if update.action not in allowed_actions
    )
    if disallowed_updates:
        return ReleaseCorrectionReport(
            correction_event_id=event.correction_event_id,
            release_id=event.release_id,
            release_kind=event.release_kind,
            impact_class=event.impact_class.value,
            status=ReleaseStatus.VIOLATION.value,
            reason_code="RELEASE_CORRECTION_POLICY_ACTION_MISMATCH",
            superseding_release_id=event.superseding_release_id,
            dependent_actions=tuple(update.action.value for update in event.dependent_updates),
            explanation=(
                "One or more dependent updates do not match the canonical action set for impact "
                f"class '{event.impact_class.value}': {disallowed_updates}."
            ),
            remediation="Restrict dependent updates to the canonical policy actions for the impact class.",
        )

    if any(update.action == DependentUpdateAction.SUPERSEDE for update in event.dependent_updates):
        if not event.superseding_release_id:
            return ReleaseCorrectionReport(
                correction_event_id=event.correction_event_id,
                release_id=event.release_id,
                release_kind=event.release_kind,
                impact_class=event.impact_class.value,
                status=ReleaseStatus.INVALID.value,
                reason_code="RELEASE_CORRECTION_SUPERSESSION_REQUIRES_RELEASE_ID",
                superseding_release_id=event.superseding_release_id,
                dependent_actions=tuple(update.action.value for update in event.dependent_updates),
                explanation=(
                    "A correction event cannot request supersession actions without naming the "
                    "superseding release."
                ),
                remediation="Provide the superseding release id or remove supersession actions.",
            )

    return ReleaseCorrectionReport(
        correction_event_id=event.correction_event_id,
        release_id=event.release_id,
        release_kind=event.release_kind,
        impact_class=event.impact_class.value,
        status=ReleaseStatus.PASS.value,
        reason_code="RELEASE_CORRECTION_POLICY_CLASSIFIED",
        superseding_release_id=event.superseding_release_id,
        dependent_actions=tuple(update.action.value for update in event.dependent_updates),
        explanation=(
            "The correction event records a semantic impact diff, an explicit impact class, and "
            "policy-governed dependent updates while preserving the prior certified release."
        ),
        remediation="No remediation required.",
    )


def validate_release_certification_contract() -> list[str]:
    errors: list[str] = []

    dataset_release_definition = release_definitions_by_kind().get("dataset_release")
    if dataset_release_definition is None:
        errors.append("dataset_release: missing from release schema catalog")
    else:
        for required_field in (
            "vendor_revision_watermark",
            "correction_horizon",
            "certification_report_hash",
        ):
            if required_field not in dataset_release_definition.required_fields:
                errors.append(
                    f"dataset_release: required field '{required_field}' must remain in the schema"
                )

    metadata_index = {
        definition.record_id: definition
        for definition in RECORD_DEFINITIONS
    }
    for record_id in ("release_certification", "release_correction_event"):
        definition = metadata_index.get(record_id)
        if definition is None:
            errors.append(f"{record_id}: missing from canonical metadata registry")
            continue
        if definition.storage_class != StorageClass.CANONICAL_METADATA:
            errors.append(f"{record_id}: must remain canonical metadata")

    return errors


VALIDATION_ERRORS = validate_release_certification_contract()
