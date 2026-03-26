"""Integrity-bound artifacts and freshness-bound evidence contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique


@unique
class ArtifactClass(str, Enum):
    INTEGRITY_BOUND = "integrity_bound"
    FRESHNESS_BOUND = "freshness_bound"


@unique
class DependencyState(str, Enum):
    VALID = "valid"
    SUSPECT = "suspect"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"
    RECERT_REQUIRED = "recert_required"


@unique
class FreshnessState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    FRESH = "fresh"
    EXPIRED = "expired"
    SUPERSEDED_COMPATIBLE = "superseded_compatible"
    SUPERSEDED_INCOMPATIBLE = "superseded_incompatible"


@unique
class InvalidationChannel(str, Enum):
    NONE = "none"
    DEPENDENCY = "dependency"
    FRESHNESS = "freshness"


@dataclass(frozen=True)
class ArtifactDefinition:
    artifact_id: str
    title: str
    artifact_class: ArtifactClass
    plan_section: str
    description: str
    expected_control: str
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactAdmissibilityDiagnostic:
    artifact_id: str
    title: str
    artifact_class: str
    status: str
    admissible: bool
    reason_code: str | None
    dependency_state: str
    freshness_state: str
    invalidation_channel: str
    expected_control: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


ARTIFACT_DEFINITIONS: tuple[ArtifactDefinition, ...] = (
    ArtifactDefinition(
        artifact_id="research_run",
        title="Research run",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Canonical research execution record and immutable bindings.",
        expected_control=(
            "Research runs stay valid until an integrity failure or dependency invalidation occurs."
        ),
        used_by=("replay", "promotion"),
    ),
    ArtifactDefinition(
        artifact_id="family_decision_record",
        title="Family decision record",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Governed decision on which strategy family advances or is rejected.",
        expected_control=(
            "Family decision records remain integrity-bound and are not freshness-gated."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="dataset_release",
        title="Dataset release",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Certified dataset release used by downstream replay and promotion.",
        expected_control=(
            "Dataset releases remain valid until quarantined, revoked, or otherwise invalidated."
        ),
        used_by=("replay", "promotion"),
    ),
    ArtifactDefinition(
        artifact_id="analytic_release",
        title="Analytic release",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Immutable analytic release bound into downstream artifacts.",
        expected_control=(
            "Analytic releases stay integrity-bound rather than expiring by age."
        ),
        used_by=("replay", "promotion"),
    ),
    ArtifactDefinition(
        artifact_id="data_profile_release",
        title="Data-profile release",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Approved data-profile release referenced by digest.",
        expected_control=(
            "Data-profile releases remain valid until dependency invalidation or integrity failure."
        ),
        used_by=("replay", "promotion"),
    ),
    ArtifactDefinition(
        artifact_id="resolved_context_bundle",
        title="Resolved-context bundle",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Content-addressed context bundle with dependency-pinned calendars and mappings.",
        expected_control=(
            "Resolved-context bundles are integrity-bound and do not expire merely because time passes."
        ),
        used_by=("replay", "promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="execution_profile_release",
        title="Execution-profile release",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Versioned execution-assumption release pinned by artifact hash.",
        expected_control=(
            "Execution-profile releases remain integrity-bound until dependency invalidation or "
            "release revocation is found."
        ),
        used_by=("replay", "promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="candidate_bundle",
        title="Candidate bundle",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Frozen candidate bundle for replay, paper, shadow-live, and live qualification.",
        expected_control=(
            "Candidate bundles remain integrity-bound once frozen and dependency-pinned."
        ),
        used_by=("replay", "promotion"),
    ),
    ArtifactDefinition(
        artifact_id="replay_fixture",
        title="Replay fixture",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Immutable replay fixture retained for certification and recertification.",
        expected_control=(
            "Replay fixtures remain valid until integrity or dependency failure is found."
        ),
        used_by=("replay",),
    ),
    ArtifactDefinition(
        artifact_id="state_snapshot",
        title="State snapshot",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Immutable state snapshot or barrier used for restoration and recovery.",
        expected_control=(
            "State snapshots are integrity-bound and not freshness-gated."
        ),
        used_by=("replay", "recovery"),
    ),
    ArtifactDefinition(
        artifact_id="broker_session_fixture",
        title="Broker-session fixture",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Immutable broker-session capture retained for certification.",
        expected_control=(
            "Broker-session fixtures remain valid until dependency invalidation or integrity failure."
        ),
        used_by=("replay", "certification"),
    ),
    ArtifactDefinition(
        artifact_id="signed_manifest",
        title="Signed manifest",
        artifact_class=ArtifactClass.INTEGRITY_BOUND,
        plan_section="3.2",
        description="Signed manifest tying immutable artifacts to a governed release surface.",
        expected_control=(
            "Signed manifests remain integrity-bound and are not freshness-expired."
        ),
        used_by=("promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="execution_profile_calibration",
        title="Execution-profile calibration",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Calibration evidence whose admissibility depends on recency.",
        expected_control=(
            "Execution-profile calibration evidence must remain fresh and not be superseded incompatibly."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="portability_study",
        title="Portability study",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Portability study admitted only while sufficiently recent.",
        expected_control=(
            "Portability studies are immutable but freshness-bound for promotion decisions."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="native_execution_symbol_validation_study",
        title="Native execution-symbol validation study",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Validation study for native execution symbol behavior.",
        expected_control=(
            "Native execution-symbol validation studies require recency checks before use."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="execution_symbol_tradability_study",
        title="Execution-symbol tradability study",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Tradability study admitted only while still fresh.",
        expected_control=(
            "Execution-symbol tradability studies are freshness-bound evidence."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="databento_ibkr_bar_parity_study",
        title="Databento-to-IBKR bar-parity study",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Parity study that must be recent enough for current promotion or activation.",
        expected_control=(
            "Bar-parity studies fail admissibility when expired or superseded incompatibly."
        ),
        used_by=("promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="paper_pass_evidence",
        title="Paper-pass evidence",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Paper-pass evidence used for promotion and readiness.",
        expected_control=(
            "Paper-pass evidence remains immutable but requires recency checks."
        ),
        used_by=("promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="shadow_pass_evidence",
        title="Shadow-pass evidence",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Shadow-pass evidence used for promotion and readiness.",
        expected_control=(
            "Shadow-pass evidence remains immutable but requires recency checks."
        ),
        used_by=("promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="session_readiness_packet",
        title="Session-readiness packet",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Readiness artifact that must be fresh for each tradeable session.",
        expected_control=(
            "Session-readiness packets are freshness-bound evidence and must be renewed when stale or superseded."
        ),
        used_by=("readiness", "activation"),
    ),
    ArtifactDefinition(
        artifact_id="fee_schedule_snapshot",
        title="Fee schedule snapshot",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Fee schedule evidence admitted only while sufficiently recent.",
        expected_control=(
            "Fee schedule snapshots are freshness-bound and expire for promotion or activation."
        ),
        used_by=("promotion",),
    ),
    ArtifactDefinition(
        artifact_id="broker_margin_snapshot",
        title="Broker margin snapshot",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Broker margin evidence admitted only while sufficiently recent.",
        expected_control=(
            "Broker margin snapshots are freshness-bound and expire for promotion or activation."
        ),
        used_by=("promotion", "readiness"),
    ),
    ArtifactDefinition(
        artifact_id="operating_envelope_recalibration_evidence",
        title="Operating-envelope recalibration evidence",
        artifact_class=ArtifactClass.FRESHNESS_BOUND,
        plan_section="3.2",
        description="Operational recalibration evidence with explicit recency bounds.",
        expected_control=(
            "Operating-envelope recalibration evidence is immutable but freshness-bound."
        ),
        used_by=("promotion", "readiness"),
    ),
)

_ARTIFACT_INDEX: dict[str, ArtifactDefinition] = {
    definition.artifact_id: definition for definition in ARTIFACT_DEFINITIONS
}


def artifact_ids() -> list[str]:
    return [definition.artifact_id for definition in ARTIFACT_DEFINITIONS]


def integrity_bound_artifact_ids() -> list[str]:
    return [
        definition.artifact_id
        for definition in ARTIFACT_DEFINITIONS
        if definition.artifact_class == ArtifactClass.INTEGRITY_BOUND
    ]


def freshness_bound_evidence_ids() -> list[str]:
    return [
        definition.artifact_id
        for definition in ARTIFACT_DEFINITIONS
        if definition.artifact_class == ArtifactClass.FRESHNESS_BOUND
    ]


def get_artifact_definition(artifact_id: str) -> ArtifactDefinition:
    return _ARTIFACT_INDEX[artifact_id]


def evaluate_artifact_admissibility(
    artifact_id: str,
    *,
    dependency_state: DependencyState = DependencyState.VALID,
    freshness_state: FreshnessState = FreshnessState.NOT_APPLICABLE,
) -> ArtifactAdmissibilityDiagnostic:
    definition = get_artifact_definition(artifact_id)
    if dependency_state != DependencyState.VALID:
        reason_code = {
            DependencyState.SUSPECT: "ARTIFACT_DEPENDENCY_SUSPECT",
            DependencyState.QUARANTINED: "ARTIFACT_DEPENDENCY_QUARANTINED",
            DependencyState.REVOKED: "ARTIFACT_DEPENDENCY_REVOKED",
            DependencyState.RECERT_REQUIRED: "ARTIFACT_DEPENDENCY_RECERT_REQUIRED",
        }[dependency_state]
        return ArtifactAdmissibilityDiagnostic(
            artifact_id=definition.artifact_id,
            title=definition.title,
            artifact_class=definition.artifact_class.value,
            status="violation",
            admissible=False,
            reason_code=reason_code,
            dependency_state=dependency_state.value,
            freshness_state=freshness_state.value,
            invalidation_channel=InvalidationChannel.DEPENDENCY.value,
            expected_control=definition.expected_control,
            explanation=(
                f"{definition.title} is blocked because a dependency entered "
                f"{dependency_state.value} state."
            ),
        )

    if definition.artifact_class == ArtifactClass.INTEGRITY_BOUND:
        return ArtifactAdmissibilityDiagnostic(
            artifact_id=definition.artifact_id,
            title=definition.title,
            artifact_class=definition.artifact_class.value,
            status="pass",
            admissible=True,
            reason_code=None,
            dependency_state=dependency_state.value,
            freshness_state=freshness_state.value,
            invalidation_channel=InvalidationChannel.NONE.value,
            expected_control=definition.expected_control,
            explanation=(
                f"{definition.title} remains admissible because it is integrity-bound "
                "and does not expire merely because time passes."
            ),
        )

    if freshness_state == FreshnessState.NOT_APPLICABLE:
        return ArtifactAdmissibilityDiagnostic(
            artifact_id=definition.artifact_id,
            title=definition.title,
            artifact_class=definition.artifact_class.value,
            status="violation",
            admissible=False,
            reason_code="ARTIFACT_FRESHNESS_STATE_MISSING",
            dependency_state=dependency_state.value,
            freshness_state=freshness_state.value,
            invalidation_channel=InvalidationChannel.FRESHNESS.value,
            expected_control=definition.expected_control,
            explanation=(
                f"{definition.title} requires an explicit freshness classification before it can be admitted."
            ),
        )

    if freshness_state == FreshnessState.EXPIRED:
        return ArtifactAdmissibilityDiagnostic(
            artifact_id=definition.artifact_id,
            title=definition.title,
            artifact_class=definition.artifact_class.value,
            status="violation",
            admissible=False,
            reason_code="ARTIFACT_FRESHNESS_EXPIRED",
            dependency_state=dependency_state.value,
            freshness_state=freshness_state.value,
            invalidation_channel=InvalidationChannel.FRESHNESS.value,
            expected_control=definition.expected_control,
            explanation=(
                f"{definition.title} is freshness-bound and has expired."
            ),
        )

    if freshness_state == FreshnessState.SUPERSEDED_INCOMPATIBLE:
        return ArtifactAdmissibilityDiagnostic(
            artifact_id=definition.artifact_id,
            title=definition.title,
            artifact_class=definition.artifact_class.value,
            status="violation",
            admissible=False,
            reason_code="ARTIFACT_FRESHNESS_SUPERSEDED_INCOMPATIBLY",
            dependency_state=dependency_state.value,
            freshness_state=freshness_state.value,
            invalidation_channel=InvalidationChannel.FRESHNESS.value,
            expected_control=definition.expected_control,
            explanation=(
                f"{definition.title} was superseded incompatibly and must be regenerated before promotion or activation."
            ),
        )

    explanation = (
        f"{definition.title} remains admissible because it is freshness-bound and "
        "still fresh."
    )
    if freshness_state == FreshnessState.SUPERSEDED_COMPATIBLE:
        explanation = (
            f"{definition.title} remains admissible because supersession was compatible "
            "and did not invalidate the evidence."
        )
    return ArtifactAdmissibilityDiagnostic(
        artifact_id=definition.artifact_id,
        title=definition.title,
        artifact_class=definition.artifact_class.value,
        status="pass",
        admissible=True,
        reason_code=None,
        dependency_state=dependency_state.value,
        freshness_state=freshness_state.value,
        invalidation_channel=InvalidationChannel.NONE.value,
        expected_control=definition.expected_control,
        explanation=explanation,
    )


def evaluate_gate_admissibility(
    *,
    gate_name: str,
    integrity_artifacts: list[dict[str, str]],
    freshness_evidence: list[dict[str, str]],
) -> dict[str, object]:
    diagnostics: list[ArtifactAdmissibilityDiagnostic] = []

    for item in integrity_artifacts:
        diagnostics.append(
            evaluate_artifact_admissibility(
                item["artifact_id"],
                dependency_state=DependencyState(item.get("dependency_state", "valid")),
                freshness_state=FreshnessState(
                    item.get("freshness_state", "not_applicable")
                ),
            )
        )

    for item in freshness_evidence:
        diagnostics.append(
            evaluate_artifact_admissibility(
                item["artifact_id"],
                dependency_state=DependencyState(item.get("dependency_state", "valid")),
                freshness_state=FreshnessState(item.get("freshness_state", "fresh")),
            )
        )

    dependency_invalidations = [
        diagnostic.to_dict()
        for diagnostic in diagnostics
        if diagnostic.invalidation_channel == InvalidationChannel.DEPENDENCY.value
    ]
    freshness_failures = [
        diagnostic.to_dict()
        for diagnostic in diagnostics
        if diagnostic.invalidation_channel == InvalidationChannel.FRESHNESS.value
    ]
    integrity_ready = not any(
        diagnostic.artifact_class == ArtifactClass.INTEGRITY_BOUND.value
        and not diagnostic.admissible
        for diagnostic in diagnostics
    )
    freshness_ready = not any(
        diagnostic.artifact_class == ArtifactClass.FRESHNESS_BOUND.value
        and not diagnostic.admissible
        for diagnostic in diagnostics
    )

    return {
        "gate_name": gate_name,
        "integrity_ready": integrity_ready,
        "freshness_ready": freshness_ready,
        "allowed": integrity_ready and freshness_ready,
        "requires_dependency_review": bool(dependency_invalidations),
        "requires_new_freshness_evidence": bool(freshness_failures),
        "dependency_invalidations": dependency_invalidations,
        "freshness_failures": freshness_failures,
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def validate_artifact_class_contract() -> list[str]:
    errors: list[str] = []
    identifiers = artifact_ids()
    if len(identifiers) != len(set(identifiers)):
        errors.append("artifact identifiers must be unique")
    if "resolved_context_bundle" not in integrity_bound_artifact_ids():
        errors.append("resolved_context_bundle must remain integrity-bound")
    if "execution_profile_release" not in integrity_bound_artifact_ids():
        errors.append("execution_profile_release must remain integrity-bound")
    if "session_readiness_packet" not in freshness_bound_evidence_ids():
        errors.append("session_readiness_packet must remain freshness-bound")
    for definition in ARTIFACT_DEFINITIONS:
        if definition.plan_section != "3.2":
            errors.append(
                f"{definition.artifact_id}: artifact classification must remain bound to plan section 3.2"
            )
    return errors


VALIDATION_ERRORS = validate_artifact_class_contract()
