"""Storage tiers and point-in-time experiment binding contract."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp


class StorageTier(str, Enum):
    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"
    TIER_D = "tier_d"
    TIER_E = "tier_e"


class ContractStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@dataclass(frozen=True)
class StorageArtifactClass:
    artifact_type: str
    storage_tier: StorageTier
    plan_section: str
    description: str
    durability_role: str
    point_in_time_relevant: bool


@dataclass(frozen=True)
class TierAssignmentRequest:
    case_id: str
    artifact_type: str
    requested_tier: StorageTier


@dataclass(frozen=True)
class TierAssignmentReport:
    case_id: str
    artifact_type: str
    status: str
    reason_code: str
    requested_tier: str
    expected_tier: str | None
    durability_role: str | None
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
class PromotableExperimentBinding:
    case_id: str
    experiment_id: str
    dataset_release_id: str
    analytic_release_id: str | None
    data_profile_release_id: str
    observation_cutoff_utc: str
    resolved_context_bundle_id: str
    policy_bundle_hash: str
    compatibility_matrix_version: str
    mutable_reference_reads: tuple[str, ...] = ()
    binding_mutated_after_freeze: bool = False


@dataclass(frozen=True)
class ExperimentBindingReport:
    case_id: str
    experiment_id: str
    status: str
    reason_code: str
    required_artifact_set: dict[str, str | None]
    actual_artifact_set: dict[str, str | None]
    observation_cutoff_utc: str | None
    mutable_reference_reads: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


STORAGE_ARTIFACT_CLASSES: tuple[StorageArtifactClass, ...] = (
    StorageArtifactClass(
        artifact_type="raw_vendor_payload",
        storage_tier=StorageTier.TIER_A,
        plan_section="5.1",
        description="Raw vendor payload exactly as received.",
        durability_role="immutable_raw_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="vendor_request_metadata",
        storage_tier=StorageTier.TIER_A,
        plan_section="5.1",
        description="Request metadata bound to a raw vendor pull.",
        durability_role="immutable_raw_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="ingestion_log",
        storage_tier=StorageTier.TIER_A,
        plan_section="5.1",
        description="Ingestion logs and hashes for raw vendor archive pulls.",
        durability_role="immutable_raw_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="contract_definition",
        storage_tier=StorageTier.TIER_B,
        plan_section="5.1",
        description="Bitemporal contract-definition fact with effective and observation time.",
        durability_role="bitemporal_reference",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="calendar_definition",
        storage_tier=StorageTier.TIER_B,
        plan_section="5.1",
        description="Exchange or macro calendar reference fact with point-in-time semantics.",
        durability_role="bitemporal_reference",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="roll_input",
        storage_tier=StorageTier.TIER_B,
        plan_section="5.1",
        description="Roll-map and delivery-fence input used for point-in-time resolution.",
        durability_role="bitemporal_reference",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="resolved_context_bundle",
        storage_tier=StorageTier.TIER_B,
        plan_section="5.1-5.2",
        description="Content-addressed point-in-time bundle compiled from resolved reference state.",
        durability_role="dependency_pinned_reference_bundle",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="normalized_market_data_partition",
        storage_tier=StorageTier.TIER_C,
        plan_section="5.1",
        description="Cleaned, typed, partitioned historical market data for backtesting.",
        durability_role="normalized_research_catalog",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="dataset_release",
        storage_tier=StorageTier.TIER_C,
        plan_section="4.3-5.1",
        description="Certified point-in-time dataset release over normalized research data.",
        durability_role="normalized_research_catalog",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="data_profile_release",
        storage_tier=StorageTier.TIER_C,
        plan_section="4.3-5.1",
        description="Immutable market-data interpretation profile for promotable work.",
        durability_role="normalized_research_catalog",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="analytic_release",
        storage_tier=StorageTier.TIER_D,
        plan_section="4.3-5.1",
        description="Derived analytic release tied to exactly one dataset release.",
        durability_role="derived_analytics",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="feature_block_manifest",
        storage_tier=StorageTier.TIER_D,
        plan_section="5.1",
        description="Derived feature block manifest tied to one dataset release.",
        durability_role="derived_analytics",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="sidecar_mask",
        storage_tier=StorageTier.TIER_D,
        plan_section="5.1-5.3",
        description="Validation sidecar mask tied to normalized data and release certification.",
        durability_role="derived_analytics",
        point_in_time_relevant=True,
    ),
    StorageArtifactClass(
        artifact_type="paper_pass_evidence",
        storage_tier=StorageTier.TIER_E,
        plan_section="5.1",
        description="Immutable paper-trading evidence retained for readiness and promotion.",
        durability_role="operational_evidence_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="replay_artifact",
        storage_tier=StorageTier.TIER_E,
        plan_section="5.1",
        description="Immutable replay and recovery evidence artifact.",
        durability_role="operational_evidence_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="broker_session_recording",
        storage_tier=StorageTier.TIER_E,
        plan_section="5.1",
        description="Immutable broker-session recording retained for diagnostics and review.",
        durability_role="operational_evidence_archive",
        point_in_time_relevant=False,
    ),
    StorageArtifactClass(
        artifact_type="parity_report",
        storage_tier=StorageTier.TIER_E,
        plan_section="5.1",
        description="Immutable parity or drift report retained for operator review.",
        durability_role="operational_evidence_archive",
        point_in_time_relevant=False,
    ),
)


def artifact_classes_by_type() -> dict[str, StorageArtifactClass]:
    return {
        artifact_class.artifact_type: artifact_class
        for artifact_class in STORAGE_ARTIFACT_CLASSES
    }


def artifacts_by_tier(storage_tier: StorageTier) -> tuple[StorageArtifactClass, ...]:
    return tuple(
        artifact_class
        for artifact_class in STORAGE_ARTIFACT_CLASSES
        if artifact_class.storage_tier == storage_tier
    )


def validate_storage_catalog() -> list[str]:
    errors: list[str] = []
    artifact_types = [artifact_class.artifact_type for artifact_class in STORAGE_ARTIFACT_CLASSES]

    if len(artifact_types) != len(set(artifact_types)):
        errors.append("storage artifact types must be unique")

    for storage_tier in StorageTier:
        if not artifacts_by_tier(storage_tier):
            errors.append(f"{storage_tier.value}: at least one artifact class is required")

    if "resolved_context_bundle" not in artifact_classes_by_type():
        errors.append("resolved_context_bundle must be classified explicitly")
    if "dataset_release" not in artifact_classes_by_type():
        errors.append("dataset_release must be classified explicitly")
    if "data_profile_release" not in artifact_classes_by_type():
        errors.append("data_profile_release must be classified explicitly")

    return errors


def evaluate_tier_assignment(request: TierAssignmentRequest) -> TierAssignmentReport:
    artifact_class = artifact_classes_by_type().get(request.artifact_type)
    if artifact_class is None:
        return TierAssignmentReport(
            case_id=request.case_id,
            artifact_type=request.artifact_type,
            status=ContractStatus.INVALID.value,
            reason_code="STORAGE_TIER_UNKNOWN_ARTIFACT",
            requested_tier=request.requested_tier.value,
            expected_tier=None,
            durability_role=None,
            explanation="The requested artifact type is not classified in the canonical storage-tier catalog.",
            remediation="Classify the artifact type explicitly before assigning a storage tier.",
        )

    if request.requested_tier != artifact_class.storage_tier:
        return TierAssignmentReport(
            case_id=request.case_id,
            artifact_type=request.artifact_type,
            status=ContractStatus.VIOLATION.value,
            reason_code="STORAGE_TIER_MISPLACED_ARTIFACT",
            requested_tier=request.requested_tier.value,
            expected_tier=artifact_class.storage_tier.value,
            durability_role=artifact_class.durability_role,
            explanation=(
                f"{request.artifact_type} belongs in {artifact_class.storage_tier.value} because it "
                f"serves the '{artifact_class.durability_role}' role."
            ),
            remediation="Move the artifact to its canonical storage tier before using it in promotable workflows.",
        )

    return TierAssignmentReport(
        case_id=request.case_id,
        artifact_type=request.artifact_type,
        status=ContractStatus.PASS.value,
        reason_code="STORAGE_TIER_ASSIGNMENT_ALLOWED",
        requested_tier=request.requested_tier.value,
        expected_tier=artifact_class.storage_tier.value,
        durability_role=artifact_class.durability_role,
        explanation="The artifact is assigned to the canonical storage tier for its role.",
        remediation="No remediation required.",
    )


def _normalize_observation_cutoff(observation_cutoff_utc: str) -> str:
    cutoff = datetime.datetime.fromisoformat(observation_cutoff_utc)
    return canonicalize_persisted_timestamp(cutoff).isoformat()


def validate_promotable_experiment_binding(
    binding: PromotableExperimentBinding,
) -> ExperimentBindingReport:
    required_artifact_set = {
        "dataset_release_id": "required",
        "analytic_release_id": "optional",
        "data_profile_release_id": "required",
        "observation_cutoff_utc": "required",
        "resolved_context_bundle_id": "required",
        "policy_bundle_hash": "required",
        "compatibility_matrix_version": "required",
    }
    actual_artifact_set = {
        "dataset_release_id": binding.dataset_release_id or None,
        "analytic_release_id": binding.analytic_release_id,
        "data_profile_release_id": binding.data_profile_release_id or None,
        "observation_cutoff_utc": binding.observation_cutoff_utc or None,
        "resolved_context_bundle_id": binding.resolved_context_bundle_id or None,
        "policy_bundle_hash": binding.policy_bundle_hash or None,
        "compatibility_matrix_version": binding.compatibility_matrix_version or None,
    }

    missing_required = [
        field_name
        for field_name, requirement in required_artifact_set.items()
        if requirement == "required" and not actual_artifact_set[field_name]
    ]
    if missing_required:
        return ExperimentBindingReport(
            case_id=binding.case_id,
            experiment_id=binding.experiment_id,
            status=ContractStatus.INVALID.value,
            reason_code="PROMOTABLE_BINDING_MISSING_REQUIRED_ARTIFACTS",
            required_artifact_set=required_artifact_set,
            actual_artifact_set=actual_artifact_set,
            observation_cutoff_utc=actual_artifact_set["observation_cutoff_utc"],
            mutable_reference_reads=binding.mutable_reference_reads,
            explanation=(
                "A promotable experiment is missing one or more required point-in-time bindings: "
                f"{missing_required}."
            ),
            remediation="Bind every required release, cutoff, and policy artifact before promotable execution.",
        )

    try:
        normalized_cutoff = _normalize_observation_cutoff(binding.observation_cutoff_utc)
    except ValueError:
        return ExperimentBindingReport(
            case_id=binding.case_id,
            experiment_id=binding.experiment_id,
            status=ContractStatus.INVALID.value,
            reason_code="PROMOTABLE_BINDING_INVALID_OBSERVATION_CUTOFF",
            required_artifact_set=required_artifact_set,
            actual_artifact_set=actual_artifact_set,
            observation_cutoff_utc=binding.observation_cutoff_utc,
            mutable_reference_reads=binding.mutable_reference_reads,
            explanation="The observation cutoff must be a timezone-aware UTC-normalizable timestamp.",
            remediation="Record the observation cutoff as a timezone-aware timestamp before freeze.",
        )

    if binding.mutable_reference_reads:
        return ExperimentBindingReport(
            case_id=binding.case_id,
            experiment_id=binding.experiment_id,
            status=ContractStatus.VIOLATION.value,
            reason_code="PROMOTABLE_BINDING_MUTABLE_REFERENCE_READ",
            required_artifact_set=required_artifact_set,
            actual_artifact_set=actual_artifact_set,
            observation_cutoff_utc=normalized_cutoff,
            mutable_reference_reads=binding.mutable_reference_reads,
            explanation=(
                "Promotable execution attempted to read mutable reference inputs at runtime instead "
                f"of relying on a frozen resolved-context bundle: {binding.mutable_reference_reads}."
            ),
            remediation="Route promotable execution through resolved-context bundles and remove direct mutable reads.",
        )

    if binding.binding_mutated_after_freeze:
        return ExperimentBindingReport(
            case_id=binding.case_id,
            experiment_id=binding.experiment_id,
            status=ContractStatus.VIOLATION.value,
            reason_code="PROMOTABLE_BINDING_MUTATED_AFTER_FREEZE",
            required_artifact_set=required_artifact_set,
            actual_artifact_set=actual_artifact_set,
            observation_cutoff_utc=normalized_cutoff,
            mutable_reference_reads=binding.mutable_reference_reads,
            explanation=(
                "The experiment binding changed after freeze, so the observation cutoff and exact "
                "artifact set are no longer immutable."
            ),
            remediation="Freeze the artifact set once and require a new experiment id for any changed binding.",
        )

    actual_artifact_set["observation_cutoff_utc"] = normalized_cutoff
    return ExperimentBindingReport(
        case_id=binding.case_id,
        experiment_id=binding.experiment_id,
        status=ContractStatus.PASS.value,
        reason_code="PROMOTABLE_BINDING_FROZEN",
        required_artifact_set=required_artifact_set,
        actual_artifact_set=actual_artifact_set,
        observation_cutoff_utc=normalized_cutoff,
        mutable_reference_reads=binding.mutable_reference_reads,
        explanation=(
            "The promotable experiment binds exactly one dataset release, zero-or-one analytic "
            "release, one data-profile release, one observation cutoff, one resolved-context "
            "bundle, one policy bundle hash, and one compatibility matrix version."
        ),
        remediation="No remediation required.",
    )


VALIDATION_ERRORS = validate_storage_catalog()
