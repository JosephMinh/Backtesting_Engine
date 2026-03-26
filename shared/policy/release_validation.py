"""Validation classifications, sidecar masks, and release lifecycle contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp


class ValidationStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    REVIEW = "review"
    VIOLATION = "violation"
    INVALID = "invalid"


class ValidationFindingClass(str, Enum):
    STRUCTURAL_SCHEMA_FAILURE = "structural_schema_failure"
    SESSION_MISALIGNMENT = "session_misalignment"
    GAPS = "gaps"
    PRICE_ANOMALY = "price_anomaly"
    DUPLICATE_OR_OUT_OF_ORDER = "duplicate_or_out_of_order"
    SUSPICIOUS_ZERO_OR_LOCKED = "suspicious_zero_or_locked"
    EVENT_WINDOW_SENSITIVITY = "event_window_sensitivity"


class QualityTier(str, Enum):
    REFERENCE = "reference"
    SENSITIVE = "sensitive"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"


class ReleaseCertificationStatus(str, Enum):
    CERTIFIABLE = "certifiable"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"
    SUSPECT = "suspect"


class ReleaseKind(str, Enum):
    DATASET = "dataset"
    ANALYTIC = "analytic"
    DATA_PROFILE = "data_profile"


class LifecycleStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


class NewWorkPosture(str, Enum):
    NOT_PROMOTABLE = "not_promotable"
    PROMOTABLE = "promotable"
    REPRODUCIBLE_ONLY = "reproducible_only"
    BLOCKED = "blocked"
    SUSPECT = "suspect"


class DependencyAction(str, Enum):
    NONE = "none"
    FREEZE_EXISTING_REFERENCES = "freeze_existing_references"
    BLOCK_NEW_EXPERIMENTS = "block_new_experiments"
    MARK_DEPENDENTS_SUSPECT = "mark_dependents_suspect"


class DatasetLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    STAGING = "STAGING"
    CERTIFIED = "CERTIFIED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


class DerivedLifecycleState(str, Enum):
    DRAFT = "DRAFT"
    CERTIFIED = "CERTIFIED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class SidecarMask:
    mask_id: str
    finding_class: str
    affected_record_count: int
    preserves_source_truth: bool
    preserves_failing_records: bool
    severity: str
    reason_code: str
    explanation: str


@dataclass(frozen=True)
class ReleaseValidationRequest:
    case_id: str
    release_id: str
    release_kind: ReleaseKind
    structural_schema_failures: int = 0
    session_misalignment_events: int = 0
    gap_events: int = 0
    price_anomaly_events: int = 0
    duplicate_or_out_of_order_events: int = 0
    suspicious_zero_or_locked_events: int = 0
    event_window_sensitive_events: int = 0
    failing_records_preserved: bool = True
    source_truth_preserved: bool = True
    destructive_rewrite_attempted: bool = False


@dataclass(frozen=True)
class ReleaseValidationReport:
    case_id: str
    release_id: str
    release_kind: str
    status: str
    reason_code: str
    quality_tier: str
    certification_status: str
    finding_counts: dict[str, int]
    sidecar_masks: tuple[SidecarMask, ...]
    failing_records_preserved: bool
    source_truth_preserved: bool
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: canonicalize_persisted_timestamp(
            datetime.datetime.now(datetime.timezone.utc)
        ).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class LifecycleSemantics:
    release_kind: str
    lifecycle_state: str
    new_work_posture: str
    dependency_action: str
    reproducible: bool
    blocks_new_experiments: bool
    marks_dependents_suspect: bool
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class ReleaseLifecycleTransitionRequest:
    case_id: str
    release_id: str
    release_kind: ReleaseKind
    from_state: str
    to_state: str
    dependent_artifact_ids: tuple[str, ...] = ()
    reproducibility_stamp_present: bool = True


@dataclass(frozen=True)
class ReleaseLifecycleTransitionReport:
    case_id: str
    release_id: str
    release_kind: str
    status: str
    reason_code: str
    from_state: str
    to_state: str
    new_work_posture: str
    dependency_action: str
    reproducibility_preserved: bool
    dependent_artifact_ids: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: canonicalize_persisted_timestamp(
            datetime.datetime.now(datetime.timezone.utc)
        ).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


FINDING_RULES: dict[ValidationFindingClass, dict[str, str]] = {
    ValidationFindingClass.STRUCTURAL_SCHEMA_FAILURE: {
        "count_field": "structural_schema_failures",
        "severity": "quarantine_required",
        "reason_code": "VALIDATION_MASK_STRUCTURAL_SCHEMA_FAILURE",
        "explanation": (
            "Schema-level violations must be preserved in sidecar masks rather than corrected "
            "in place because the source truth cannot be rewritten."
        ),
    },
    ValidationFindingClass.SESSION_MISALIGNMENT: {
        "count_field": "session_misalignment_events",
        "severity": "quarantine_required",
        "reason_code": "VALIDATION_MASK_SESSION_MISALIGNMENT",
        "explanation": (
            "Session-misaligned records indicate the exchange calendar or event joins need "
            "review before release certification."
        ),
    },
    ValidationFindingClass.GAPS: {
        "count_field": "gap_events",
        "severity": "blocked_pending_remediation",
        "reason_code": "VALIDATION_MASK_GAPS",
        "explanation": (
            "Coverage gaps remain visible in sidecar masks so downstream research can "
            "deterministically decide whether the release is still admissible."
        ),
    },
    ValidationFindingClass.PRICE_ANOMALY: {
        "count_field": "price_anomaly_events",
        "severity": "blocked_pending_remediation",
        "reason_code": "VALIDATION_MASK_PRICE_ANOMALY",
        "explanation": (
            "Price anomalies require operator review and may downgrade the quality tier "
            "without destroying the raw source records."
        ),
    },
    ValidationFindingClass.DUPLICATE_OR_OUT_OF_ORDER: {
        "count_field": "duplicate_or_out_of_order_events",
        "severity": "quarantine_required",
        "reason_code": "VALIDATION_MASK_DUPLICATE_OR_OUT_OF_ORDER",
        "explanation": (
            "Duplicate or out-of-order events break deterministic replay assumptions and must "
            "quarantine the release until the lineage is corrected."
        ),
    },
    ValidationFindingClass.SUSPICIOUS_ZERO_OR_LOCKED: {
        "count_field": "suspicious_zero_or_locked_events",
        "severity": "blocked_pending_remediation",
        "reason_code": "VALIDATION_MASK_SUSPICIOUS_ZERO_OR_LOCKED",
        "explanation": (
            "Suspicious zero or locked values stay visible through masks so downstream "
            "analytics can exclude or study them explicitly."
        ),
    },
    ValidationFindingClass.EVENT_WINDOW_SENSITIVITY: {
        "count_field": "event_window_sensitive_events",
        "severity": "conditional",
        "reason_code": "VALIDATION_MASK_EVENT_WINDOW_SENSITIVITY",
        "explanation": (
            "Event-window-sensitive records remain promotable only with explicit conditioning "
            "because they are sensitive to macro-event masking choices."
        ),
    },
}

HARD_BLOCK_FINDINGS = frozenset(
    {
        ValidationFindingClass.STRUCTURAL_SCHEMA_FAILURE,
        ValidationFindingClass.SESSION_MISALIGNMENT,
        ValidationFindingClass.DUPLICATE_OR_OUT_OF_ORDER,
    }
)

DEGRADED_FINDINGS = frozenset(
    {
        ValidationFindingClass.GAPS,
        ValidationFindingClass.PRICE_ANOMALY,
        ValidationFindingClass.SUSPICIOUS_ZERO_OR_LOCKED,
    }
)


DATASET_ALLOWED_TRANSITIONS: dict[DatasetLifecycleState, frozenset[DatasetLifecycleState]] = {
    DatasetLifecycleState.DRAFT: frozenset(
        {
            DatasetLifecycleState.STAGING,
            DatasetLifecycleState.CERTIFIED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.STAGING: frozenset(
        {
            DatasetLifecycleState.CERTIFIED,
            DatasetLifecycleState.QUARANTINED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.CERTIFIED: frozenset(
        {
            DatasetLifecycleState.APPROVED,
            DatasetLifecycleState.QUARANTINED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.APPROVED: frozenset(
        {
            DatasetLifecycleState.ACTIVE,
            DatasetLifecycleState.QUARANTINED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.ACTIVE: frozenset(
        {
            DatasetLifecycleState.SUPERSEDED,
            DatasetLifecycleState.QUARANTINED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.SUPERSEDED: frozenset(
        {
            DatasetLifecycleState.QUARANTINED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.QUARANTINED: frozenset(
        {
            DatasetLifecycleState.APPROVED,
            DatasetLifecycleState.ACTIVE,
            DatasetLifecycleState.SUPERSEDED,
            DatasetLifecycleState.REVOKED,
        }
    ),
    DatasetLifecycleState.REVOKED: frozenset(),
}

DERIVED_ALLOWED_TRANSITIONS: dict[DerivedLifecycleState, frozenset[DerivedLifecycleState]] = {
    DerivedLifecycleState.DRAFT: frozenset(
        {
            DerivedLifecycleState.CERTIFIED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.CERTIFIED: frozenset(
        {
            DerivedLifecycleState.APPROVED,
            DerivedLifecycleState.QUARANTINED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.APPROVED: frozenset(
        {
            DerivedLifecycleState.ACTIVE,
            DerivedLifecycleState.QUARANTINED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.ACTIVE: frozenset(
        {
            DerivedLifecycleState.SUPERSEDED,
            DerivedLifecycleState.QUARANTINED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.SUPERSEDED: frozenset(
        {
            DerivedLifecycleState.QUARANTINED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.QUARANTINED: frozenset(
        {
            DerivedLifecycleState.APPROVED,
            DerivedLifecycleState.ACTIVE,
            DerivedLifecycleState.SUPERSEDED,
            DerivedLifecycleState.REVOKED,
        }
    ),
    DerivedLifecycleState.REVOKED: frozenset(),
}


def _finding_counts(request: ReleaseValidationRequest) -> dict[ValidationFindingClass, int]:
    return {
        finding_class: int(getattr(request, rule["count_field"]))
        for finding_class, rule in FINDING_RULES.items()
    }


def _build_sidecar_masks(
    release_id: str,
    counts: dict[ValidationFindingClass, int],
    *,
    source_truth_preserved: bool,
    failing_records_preserved: bool,
) -> tuple[SidecarMask, ...]:
    masks: list[SidecarMask] = []
    for finding_class, count in counts.items():
        if count <= 0:
            continue
        rule = FINDING_RULES[finding_class]
        masks.append(
            SidecarMask(
                mask_id=f"{release_id}:{finding_class.value}",
                finding_class=finding_class.value,
                affected_record_count=count,
                preserves_source_truth=source_truth_preserved,
                preserves_failing_records=failing_records_preserved,
                severity=rule["severity"],
                reason_code=rule["reason_code"],
                explanation=rule["explanation"],
            )
        )
    return tuple(masks)


def evaluate_release_validation(request: ReleaseValidationRequest) -> ReleaseValidationReport:
    counts = _finding_counts(request)
    rendered_counts = {finding_class.value: count for finding_class, count in counts.items()}

    if any(count < 0 for count in counts.values()):
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.INVALID.value,
            reason_code="RELEASE_VALIDATION_NEGATIVE_FINDING_COUNT",
            quality_tier=QualityTier.QUARANTINED.value,
            certification_status=ReleaseCertificationStatus.SUSPECT.value,
            finding_counts=rendered_counts,
            sidecar_masks=(),
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "Validation counts must be explicit non-negative integers so downstream "
                "quality tiers are deterministic."
            ),
            remediation="Fix the upstream validation summary before certifying or promoting this release.",
        )

    if request.destructive_rewrite_attempted or not request.source_truth_preserved:
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.VIOLATION.value,
            reason_code="RELEASE_VALIDATION_SOURCE_TRUTH_MUTATED",
            quality_tier=QualityTier.QUARANTINED.value,
            certification_status=ReleaseCertificationStatus.SUSPECT.value,
            finding_counts=rendered_counts,
            sidecar_masks=(),
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "Validation must preserve source truth and express quality judgments through "
                "sidecar masks rather than destructive rewrites."
            ),
            remediation="Rebuild the release from immutable inputs and persist the findings in sidecar masks.",
        )

    masks = _build_sidecar_masks(
        request.release_id,
        counts,
        source_truth_preserved=request.source_truth_preserved,
        failing_records_preserved=request.failing_records_preserved,
    )
    findings_present = {finding_class for finding_class, count in counts.items() if count > 0}

    if findings_present and not request.failing_records_preserved:
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.VIOLATION.value,
            reason_code="RELEASE_VALIDATION_FAILED_RECORDS_NOT_PRESERVED",
            quality_tier=QualityTier.QUARANTINED.value,
            certification_status=ReleaseCertificationStatus.SUSPECT.value,
            finding_counts=rendered_counts,
            sidecar_masks=masks,
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "Validation diagnostics must preserve failing records so certification, replay, "
                "and operator review can inspect the exact rejected population."
            ),
            remediation="Retain failing-record references in the sidecar mask bundle before re-running certification.",
        )

    if not findings_present:
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.PASS.value,
            reason_code="RELEASE_VALIDATION_CLEAN",
            quality_tier=QualityTier.REFERENCE.value,
            certification_status=ReleaseCertificationStatus.CERTIFIABLE.value,
            finding_counts=rendered_counts,
            sidecar_masks=(),
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "The release has no classified validation failures and can advance with a "
                "reference-grade quality tier."
            ),
            remediation="Freeze the release manifest and carry the validation digest into certification.",
        )

    if findings_present.intersection(HARD_BLOCK_FINDINGS):
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.VIOLATION.value,
            reason_code="RELEASE_VALIDATION_QUARANTINE_REQUIRED",
            quality_tier=QualityTier.QUARANTINED.value,
            certification_status=ReleaseCertificationStatus.SUSPECT.value,
            finding_counts=rendered_counts,
            sidecar_masks=masks,
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "Structural, session, or ordering failures make the release unsafe for new "
                "promotable work and require quarantine."
            ),
            remediation="Quarantine the release, rebuild the offending inputs, and issue a corrected successor release.",
        )

    if findings_present.intersection(DEGRADED_FINDINGS):
        return ReleaseValidationReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=ValidationStatus.REVIEW.value,
            reason_code="RELEASE_VALIDATION_BLOCKED_PENDING_REMEDIATION",
            quality_tier=QualityTier.DEGRADED.value,
            certification_status=ReleaseCertificationStatus.BLOCKED.value,
            finding_counts=rendered_counts,
            sidecar_masks=masks,
            failing_records_preserved=request.failing_records_preserved,
            source_truth_preserved=request.source_truth_preserved,
            explanation=(
                "The release is preserved with explicit sidecar masks, but quality degradation "
                "blocks certification until the anomalies are addressed or explicitly waived."
            ),
            remediation="Review the masked findings, repair the lineage, or document an approved waiver before promotion.",
        )

    return ReleaseValidationReport(
        case_id=request.case_id,
        release_id=request.release_id,
        release_kind=request.release_kind.value,
        status=ValidationStatus.REVIEW.value,
        reason_code="RELEASE_VALIDATION_CONDITIONAL_EVENT_WINDOW_SENSITIVITY",
        quality_tier=QualityTier.SENSITIVE.value,
        certification_status=ReleaseCertificationStatus.CONDITIONAL.value,
        finding_counts=rendered_counts,
        sidecar_masks=masks,
        failing_records_preserved=request.failing_records_preserved,
        source_truth_preserved=request.source_truth_preserved,
        explanation=(
            "The release is usable only with explicit event-window conditioning because the "
            "underlying records are sensitive to masking policy."
        ),
        remediation="Carry the event-window policy reference and approved mask set into downstream certification.",
    )


def _parse_lifecycle_state(release_kind: ReleaseKind, state_value: str) -> DatasetLifecycleState | DerivedLifecycleState:
    if release_kind == ReleaseKind.DATASET:
        return DatasetLifecycleState(state_value)
    return DerivedLifecycleState(state_value)


def describe_release_lifecycle_state(
    release_kind: ReleaseKind, state_value: str
) -> LifecycleSemantics:
    state = _parse_lifecycle_state(release_kind, state_value)

    if state_value == "ACTIVE":
        return LifecycleSemantics(
            release_kind=release_kind.value,
            lifecycle_state=state.value,
            new_work_posture=NewWorkPosture.PROMOTABLE.value,
            dependency_action=DependencyAction.NONE.value,
            reproducible=True,
            blocks_new_experiments=False,
            marks_dependents_suspect=False,
            explanation="Only ACTIVE releases seed new promotable work by default.",
        )

    if state_value == "SUPERSEDED":
        return LifecycleSemantics(
            release_kind=release_kind.value,
            lifecycle_state=state.value,
            new_work_posture=NewWorkPosture.REPRODUCIBLE_ONLY.value,
            dependency_action=DependencyAction.FREEZE_EXISTING_REFERENCES.value,
            reproducible=True,
            blocks_new_experiments=False,
            marks_dependents_suspect=False,
            explanation=(
                "Superseded releases remain reproducible for audit and replay, but new "
                "promotable work should bind to the successor release."
            ),
        )

    if state_value == "QUARANTINED":
        return LifecycleSemantics(
            release_kind=release_kind.value,
            lifecycle_state=state.value,
            new_work_posture=NewWorkPosture.BLOCKED.value,
            dependency_action=DependencyAction.BLOCK_NEW_EXPERIMENTS.value,
            reproducible=True,
            blocks_new_experiments=True,
            marks_dependents_suspect=False,
            explanation=(
                "Quarantined releases remain inspectable but block new experiments until an "
                "operator explicitly restores or replaces them."
            ),
        )

    if state_value == "REVOKED":
        return LifecycleSemantics(
            release_kind=release_kind.value,
            lifecycle_state=state.value,
            new_work_posture=NewWorkPosture.SUSPECT.value,
            dependency_action=DependencyAction.MARK_DEPENDENTS_SUSPECT.value,
            reproducible=True,
            blocks_new_experiments=True,
            marks_dependents_suspect=True,
            explanation=(
                "Revoked releases remain historically traceable, but every dependent artifact "
                "must be treated as suspect until re-certified."
            ),
        )

    reproducible = state_value in {"STAGING", "CERTIFIED", "APPROVED"}
    return LifecycleSemantics(
        release_kind=release_kind.value,
        lifecycle_state=state.value,
        new_work_posture=NewWorkPosture.NOT_PROMOTABLE.value,
        dependency_action=DependencyAction.NONE.value,
        reproducible=reproducible,
        blocks_new_experiments=False,
        marks_dependents_suspect=False,
        explanation=(
            "Pre-active lifecycle states are explicit checkpoints, but they do not seed new "
            "promotable work."
        ),
    )


def evaluate_release_lifecycle_transition(
    request: ReleaseLifecycleTransitionRequest,
) -> ReleaseLifecycleTransitionReport:
    try:
        from_state = _parse_lifecycle_state(request.release_kind, request.from_state)
        to_state = _parse_lifecycle_state(request.release_kind, request.to_state)
    except ValueError:
        return ReleaseLifecycleTransitionReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=LifecycleStatus.INVALID.value,
            reason_code="RELEASE_LIFECYCLE_UNKNOWN_STATE",
            from_state=request.from_state,
            to_state=request.to_state,
            new_work_posture=NewWorkPosture.SUSPECT.value,
            dependency_action=DependencyAction.MARK_DEPENDENTS_SUSPECT.value,
            reproducibility_preserved=False,
            dependent_artifact_ids=request.dependent_artifact_ids,
            explanation="The requested lifecycle transition references an unknown state.",
            remediation="Use the canonical lifecycle state set for the release kind being transitioned.",
        )

    if from_state == to_state:
        semantics = describe_release_lifecycle_state(request.release_kind, to_state.value)
        return ReleaseLifecycleTransitionReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=LifecycleStatus.INVALID.value,
            reason_code="RELEASE_LIFECYCLE_NO_STATE_CHANGE",
            from_state=from_state.value,
            to_state=to_state.value,
            new_work_posture=semantics.new_work_posture,
            dependency_action=semantics.dependency_action,
            reproducibility_preserved=semantics.reproducible,
            dependent_artifact_ids=request.dependent_artifact_ids,
            explanation="Lifecycle transitions must change state so downstream gates can react deterministically.",
            remediation="Submit an actual state transition or leave the release unchanged.",
        )

    allowed_transitions: dict[Any, frozenset[Any]]
    if request.release_kind == ReleaseKind.DATASET:
        allowed_transitions = DATASET_ALLOWED_TRANSITIONS
    else:
        allowed_transitions = DERIVED_ALLOWED_TRANSITIONS

    if to_state not in allowed_transitions[from_state]:
        semantics = describe_release_lifecycle_state(request.release_kind, to_state.value)
        return ReleaseLifecycleTransitionReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=LifecycleStatus.INVALID.value,
            reason_code="RELEASE_LIFECYCLE_TRANSITION_NOT_ALLOWED",
            from_state=from_state.value,
            to_state=to_state.value,
            new_work_posture=semantics.new_work_posture,
            dependency_action=semantics.dependency_action,
            reproducibility_preserved=semantics.reproducible,
            dependent_artifact_ids=request.dependent_artifact_ids,
            explanation=(
                "The requested transition skips required review checkpoints or violates the "
                "canonical lifecycle order."
            ),
            remediation="Move through the declared lifecycle checkpoints or issue a corrected successor release.",
        )

    if to_state.value == "SUPERSEDED" and not request.reproducibility_stamp_present:
        semantics = describe_release_lifecycle_state(request.release_kind, to_state.value)
        return ReleaseLifecycleTransitionReport(
            case_id=request.case_id,
            release_id=request.release_id,
            release_kind=request.release_kind.value,
            status=LifecycleStatus.VIOLATION.value,
            reason_code="RELEASE_LIFECYCLE_SUPERSEDED_REQUIRES_REPRODUCIBILITY",
            from_state=from_state.value,
            to_state=to_state.value,
            new_work_posture=semantics.new_work_posture,
            dependency_action=semantics.dependency_action,
            reproducibility_preserved=False,
            dependent_artifact_ids=request.dependent_artifact_ids,
            explanation=(
                "A superseded release must retain reproducibility evidence so historical "
                "experiments and audits can replay the exact prior artifact set."
            ),
            remediation="Persist reproducibility stamps before marking the release superseded.",
        )

    semantics = describe_release_lifecycle_state(request.release_kind, to_state.value)
    return ReleaseLifecycleTransitionReport(
        case_id=request.case_id,
        release_id=request.release_id,
        release_kind=request.release_kind.value,
        status=LifecycleStatus.PASS.value,
        reason_code="RELEASE_LIFECYCLE_TRANSITION_ALLOWED",
        from_state=from_state.value,
        to_state=to_state.value,
        new_work_posture=semantics.new_work_posture,
        dependency_action=semantics.dependency_action,
        reproducibility_preserved=semantics.reproducible,
        dependent_artifact_ids=request.dependent_artifact_ids,
        explanation=semantics.explanation,
        remediation="Propagate the resulting lifecycle posture into dependent release and readiness checks.",
    )


def validate_contract() -> list[str]:
    errors: list[str] = []

    if set(FINDING_RULES) != set(ValidationFindingClass):
        errors.append("validation finding rules must cover every canonical finding class")

    dataset_states = {state.value for state in DatasetLifecycleState}
    derived_states = {state.value for state in DerivedLifecycleState}
    if "STAGING" not in dataset_states:
        errors.append("dataset lifecycle must include STAGING")
    if "STAGING" in derived_states:
        errors.append("analytic and data-profile lifecycles may not include STAGING")

    if set(DATASET_ALLOWED_TRANSITIONS) != set(DatasetLifecycleState):
        errors.append("dataset lifecycle transitions must cover every dataset state")
    if set(DERIVED_ALLOWED_TRANSITIONS) != set(DerivedLifecycleState):
        errors.append("derived lifecycle transitions must cover every derived state")

    for release_kind in ReleaseKind:
        active = describe_release_lifecycle_state(release_kind, "ACTIVE")
        superseded = describe_release_lifecycle_state(release_kind, "SUPERSEDED")
        quarantined = describe_release_lifecycle_state(release_kind, "QUARANTINED")
        revoked = describe_release_lifecycle_state(release_kind, "REVOKED")

        if active.new_work_posture != NewWorkPosture.PROMOTABLE.value:
            errors.append(f"{release_kind.value}: ACTIVE must be promotable")
        if superseded.new_work_posture != NewWorkPosture.REPRODUCIBLE_ONLY.value:
            errors.append(f"{release_kind.value}: SUPERSEDED must remain reproducible-only")
        if not superseded.reproducible:
            errors.append(f"{release_kind.value}: SUPERSEDED must preserve reproducibility")
        if quarantined.dependency_action != DependencyAction.BLOCK_NEW_EXPERIMENTS.value:
            errors.append(f"{release_kind.value}: QUARANTINED must block new experiments")
        if revoked.dependency_action != DependencyAction.MARK_DEPENDENTS_SUSPECT.value:
            errors.append(f"{release_kind.value}: REVOKED must mark dependents suspect")

    return errors


VALIDATION_ERRORS = validate_contract()
