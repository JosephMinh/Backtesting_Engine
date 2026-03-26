"""Resolved-context bundle and execution-profile release contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.artifact_classes import ArtifactClass, get_artifact_definition
from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.release_schemas import ReleaseLifecycleState, release_definitions_by_kind
from shared.policy.storage_tiers import (
    StorageTier,
    artifact_classes_by_type as storage_artifact_classes_by_type,
)

SUPPORTED_CONTEXT_SCHEMA_VERSION = 1

ALLOWED_CONTEXT_INVALIDATION_CAUSES = (
    "dependency_revocation",
    "compiler_protocol_incompatible",
    "reproducibility_failure",
)


@unique
class ContextContractStatus(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class ContextBindingSurface(str, Enum):
    CANDIDATE_BUNDLE = "candidate_bundle"
    PORTABILITY_ASSESSMENT = "portability_assessment"
    REPLAY_FIXTURE = "replay_fixture"


@dataclass(frozen=True)
class ResolvedContextBundle:
    bundle_id: str
    source_dataset_release_id: str
    observation_cutoff_utc: str
    compiled_session_schedule_ids: tuple[str, ...]
    compiled_session_anchor_ids: tuple[str, ...]
    resolved_reference_record_hashes: tuple[str, ...]
    quality_mask_ids: tuple[str, ...]
    protected_zone_mask_ids: tuple[str, ...]
    event_window_ids: tuple[str, ...]
    roll_map_id: str
    delivery_fence_ids: tuple[str, ...]
    dependency_pin_ids: tuple[str, ...]
    content_hash: str
    compiler_id: str
    compiler_protocol_version: str
    portability_policy_resolution_id: str | None = None
    schema_version: int = SUPPORTED_CONTEXT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResolvedContextBundle":
        return cls(
            bundle_id=str(payload["bundle_id"]),
            source_dataset_release_id=str(payload["source_dataset_release_id"]),
            observation_cutoff_utc=str(payload["observation_cutoff_utc"]),
            compiled_session_schedule_ids=tuple(
                str(item) for item in payload["compiled_session_schedule_ids"]
            ),
            compiled_session_anchor_ids=tuple(
                str(item) for item in payload["compiled_session_anchor_ids"]
            ),
            resolved_reference_record_hashes=tuple(
                str(item) for item in payload["resolved_reference_record_hashes"]
            ),
            quality_mask_ids=tuple(str(item) for item in payload["quality_mask_ids"]),
            protected_zone_mask_ids=tuple(
                str(item) for item in payload["protected_zone_mask_ids"]
            ),
            event_window_ids=tuple(str(item) for item in payload["event_window_ids"]),
            roll_map_id=str(payload["roll_map_id"]),
            delivery_fence_ids=tuple(str(item) for item in payload["delivery_fence_ids"]),
            dependency_pin_ids=tuple(str(item) for item in payload["dependency_pin_ids"]),
            content_hash=str(payload["content_hash"]),
            compiler_id=str(payload["compiler_id"]),
            compiler_protocol_version=str(payload["compiler_protocol_version"]),
            portability_policy_resolution_id=(
                str(payload["portability_policy_resolution_id"])
                if payload.get("portability_policy_resolution_id")
                else None
            ),
            schema_version=int(payload.get("schema_version", SUPPORTED_CONTEXT_SCHEMA_VERSION)),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ResolvedContextBundle":
        return cls.from_dict(_decode_context_json(payload, "resolved_context_bundle"))


@dataclass(frozen=True)
class ExecutionProfileRelease:
    release_id: str
    data_profile_release_id: str
    order_type_assumptions: tuple[str, ...]
    slippage_surface_ids: tuple[str, ...]
    fill_rules: tuple[str, ...]
    latency_assumptions: tuple[str, ...]
    adverse_selection_penalties: tuple[str, ...]
    quote_absence_policy: str
    spread_spike_policy: str
    degraded_bar_policy: str
    calibration_evidence_ids: tuple[str, ...]
    artifact_root_hash: str
    lifecycle_state: ReleaseLifecycleState
    schema_version: int = SUPPORTED_CONTEXT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lifecycle_state"] = self.lifecycle_state.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionProfileRelease":
        return cls(
            release_id=str(payload["release_id"]),
            data_profile_release_id=str(payload["data_profile_release_id"]),
            order_type_assumptions=tuple(str(item) for item in payload["order_type_assumptions"]),
            slippage_surface_ids=tuple(str(item) for item in payload["slippage_surface_ids"]),
            fill_rules=tuple(str(item) for item in payload["fill_rules"]),
            latency_assumptions=tuple(str(item) for item in payload["latency_assumptions"]),
            adverse_selection_penalties=tuple(
                str(item) for item in payload.get("adverse_selection_penalties", ())
            ),
            quote_absence_policy=str(payload["quote_absence_policy"]),
            spread_spike_policy=str(payload["spread_spike_policy"]),
            degraded_bar_policy=str(payload["degraded_bar_policy"]),
            calibration_evidence_ids=tuple(
                str(item) for item in payload["calibration_evidence_ids"]
            ),
            artifact_root_hash=str(payload["artifact_root_hash"]),
            lifecycle_state=ReleaseLifecycleState(payload["lifecycle_state"]),
            schema_version=int(payload.get("schema_version", SUPPORTED_CONTEXT_SCHEMA_VERSION)),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ExecutionProfileRelease":
        return cls.from_dict(_decode_context_json(payload, "execution_profile_release"))


@dataclass(frozen=True)
class ContextArtifactBindingRequest:
    case_id: str
    surface_name: ContextBindingSurface
    resolved_context_bundle_id: str
    resolved_context_content_hash: str
    execution_profile_release_id: str
    execution_profile_artifact_hash: str
    mutable_reference_reads: tuple[str, ...] = ()
    mutable_execution_overrides: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["surface_name"] = self.surface_name.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContextArtifactBindingRequest":
        return cls(
            case_id=str(payload["case_id"]),
            surface_name=ContextBindingSurface(payload["surface_name"]),
            resolved_context_bundle_id=str(payload["resolved_context_bundle_id"]),
            resolved_context_content_hash=str(payload["resolved_context_content_hash"]),
            execution_profile_release_id=str(payload["execution_profile_release_id"]),
            execution_profile_artifact_hash=str(payload["execution_profile_artifact_hash"]),
            mutable_reference_reads=tuple(
                str(item) for item in payload.get("mutable_reference_reads", ())
            ),
            mutable_execution_overrides=tuple(
                str(item) for item in payload.get("mutable_execution_overrides", ())
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ContextArtifactBindingRequest":
        return cls.from_dict(_decode_context_json(payload, "context_artifact_binding"))


@dataclass(frozen=True)
class ResolvedContextValidationReport:
    case_id: str
    bundle_id: str | None
    status: str
    reason_code: str
    normalized_observation_cutoff_utc: str | None
    missing_fields: tuple[str, ...]
    dependency_pin_ids: tuple[str, ...]
    content_hash: str | None
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
class ExecutionProfileValidationReport:
    case_id: str
    release_id: str | None
    status: str
    reason_code: str
    lifecycle_state: str | None
    data_profile_release_id: str | None
    artifact_root_hash: str | None
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
class ContextBindingReport:
    case_id: str
    surface_name: str
    status: str
    reason_code: str
    digest_bound: bool
    bound_artifact_set: dict[str, str]
    mutable_reference_reads: tuple[str, ...]
    mutable_execution_overrides: tuple[str, ...]
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
class ContextInvalidationReport:
    bundle_id: str
    invalidation_cause: str
    status: str
    allowed: bool
    reason_code: str
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _decode_context_json(payload: str, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: payload must decode to a JSON object")
    return decoded


def _normalize_observation_cutoff(observation_cutoff_utc: str) -> str:
    cutoff = datetime.datetime.fromisoformat(observation_cutoff_utc)
    return canonicalize_persisted_timestamp(cutoff).isoformat()


def _mentions_digest(identifier: str, digest: str) -> bool:
    return bool(identifier and digest and digest in identifier)


def _missing_bundle_fields(bundle: ResolvedContextBundle) -> tuple[str, ...]:
    missing: list[str] = []
    required_scalars = {
        "bundle_id": bundle.bundle_id,
        "source_dataset_release_id": bundle.source_dataset_release_id,
        "observation_cutoff_utc": bundle.observation_cutoff_utc,
        "roll_map_id": bundle.roll_map_id,
        "content_hash": bundle.content_hash,
        "compiler_id": bundle.compiler_id,
        "compiler_protocol_version": bundle.compiler_protocol_version,
    }
    for field_name, field_value in required_scalars.items():
        if not field_value:
            missing.append(field_name)
    required_sequences = {
        "compiled_session_schedule_ids": bundle.compiled_session_schedule_ids,
        "compiled_session_anchor_ids": bundle.compiled_session_anchor_ids,
        "resolved_reference_record_hashes": bundle.resolved_reference_record_hashes,
        "quality_mask_ids": bundle.quality_mask_ids,
        "protected_zone_mask_ids": bundle.protected_zone_mask_ids,
        "event_window_ids": bundle.event_window_ids,
        "delivery_fence_ids": bundle.delivery_fence_ids,
        "dependency_pin_ids": bundle.dependency_pin_ids,
    }
    for field_name, field_value in required_sequences.items():
        if not field_value:
            missing.append(field_name)
    return tuple(missing)


def _missing_execution_profile_fields(release: ExecutionProfileRelease) -> tuple[str, ...]:
    missing: list[str] = []
    required_scalars = {
        "release_id": release.release_id,
        "data_profile_release_id": release.data_profile_release_id,
        "quote_absence_policy": release.quote_absence_policy,
        "spread_spike_policy": release.spread_spike_policy,
        "degraded_bar_policy": release.degraded_bar_policy,
        "artifact_root_hash": release.artifact_root_hash,
    }
    for field_name, field_value in required_scalars.items():
        if not field_value:
            missing.append(field_name)
    required_sequences = {
        "order_type_assumptions": release.order_type_assumptions,
        "slippage_surface_ids": release.slippage_surface_ids,
        "fill_rules": release.fill_rules,
        "latency_assumptions": release.latency_assumptions,
        "calibration_evidence_ids": release.calibration_evidence_ids,
    }
    for field_name, field_value in required_sequences.items():
        if not field_value:
            missing.append(field_name)
    return tuple(missing)


def validate_resolved_context_bundle(
    case_id: str,
    bundle: ResolvedContextBundle,
) -> ResolvedContextValidationReport:
    if bundle.schema_version != SUPPORTED_CONTEXT_SCHEMA_VERSION:
        return ResolvedContextValidationReport(
            case_id=case_id,
            bundle_id=bundle.bundle_id or None,
            status=ContextContractStatus.INVALID.value,
            reason_code="CONTEXT_BUNDLE_SCHEMA_VERSION_UNSUPPORTED",
            normalized_observation_cutoff_utc=bundle.observation_cutoff_utc or None,
            missing_fields=(),
            dependency_pin_ids=bundle.dependency_pin_ids,
            content_hash=bundle.content_hash or None,
            explanation=(
                "The resolved-context bundle uses an unsupported schema version for the canonical "
                "contract."
            ),
            remediation="Rebuild the bundle with the supported canonical schema version.",
        )

    missing_fields = _missing_bundle_fields(bundle)
    if missing_fields:
        return ResolvedContextValidationReport(
            case_id=case_id,
            bundle_id=bundle.bundle_id or None,
            status=ContextContractStatus.INVALID.value,
            reason_code="CONTEXT_BUNDLE_MISSING_REQUIRED_FIELDS",
            normalized_observation_cutoff_utc=bundle.observation_cutoff_utc or None,
            missing_fields=missing_fields,
            dependency_pin_ids=bundle.dependency_pin_ids,
            content_hash=bundle.content_hash or None,
            explanation=(
                "The resolved-context bundle is missing one or more required frozen inputs: "
                f"{missing_fields}."
            ),
            remediation="Populate every required schedule, reference, mask, dependency, and hash field.",
        )

    try:
        normalized_cutoff = _normalize_observation_cutoff(bundle.observation_cutoff_utc)
    except ValueError:
        return ResolvedContextValidationReport(
            case_id=case_id,
            bundle_id=bundle.bundle_id,
            status=ContextContractStatus.INVALID.value,
            reason_code="CONTEXT_BUNDLE_INVALID_OBSERVATION_CUTOFF",
            normalized_observation_cutoff_utc=bundle.observation_cutoff_utc,
            missing_fields=(),
            dependency_pin_ids=bundle.dependency_pin_ids,
            content_hash=bundle.content_hash,
            explanation="The observation cutoff must be timezone-aware and canonicalizable to UTC.",
            remediation="Record the bundle cutoff as a timezone-aware timestamp before freeze.",
        )

    if not _mentions_digest(bundle.bundle_id, bundle.content_hash):
        return ResolvedContextValidationReport(
            case_id=case_id,
            bundle_id=bundle.bundle_id,
            status=ContextContractStatus.VIOLATION.value,
            reason_code="CONTEXT_BUNDLE_NOT_CONTENT_ADDRESSED",
            normalized_observation_cutoff_utc=normalized_cutoff,
            missing_fields=(),
            dependency_pin_ids=bundle.dependency_pin_ids,
            content_hash=bundle.content_hash,
            explanation=(
                "The resolved-context bundle identifier does not embed the content hash, so the "
                "bundle is not digest-addressable for replay or promotion."
            ),
            remediation="Regenerate the bundle identifier from the canonical content hash.",
        )

    return ResolvedContextValidationReport(
        case_id=case_id,
        bundle_id=bundle.bundle_id,
        status=ContextContractStatus.PASS.value,
        reason_code="CONTEXT_BUNDLE_FROZEN_AND_PINNED",
        normalized_observation_cutoff_utc=normalized_cutoff,
        missing_fields=(),
        dependency_pin_ids=bundle.dependency_pin_ids,
        content_hash=bundle.content_hash,
        explanation=(
            "The resolved-context bundle freezes the compiled schedules, reference state, masks, "
            "roll rules, and dependency pins behind a content-addressed identifier."
        ),
        remediation="No remediation required.",
    )


def evaluate_context_bundle_invalidation(
    bundle: ResolvedContextBundle,
    invalidation_cause: str,
) -> ContextInvalidationReport:
    if invalidation_cause not in ALLOWED_CONTEXT_INVALIDATION_CAUSES:
        return ContextInvalidationReport(
            bundle_id=bundle.bundle_id,
            invalidation_cause=invalidation_cause,
            status=ContextContractStatus.VIOLATION.value,
            allowed=False,
            reason_code="CONTEXT_BUNDLE_INVALIDATION_CAUSE_NOT_ALLOWED",
            explanation=(
                "Resolved-context bundles may be invalidated only by dependency revocation, "
                "compiler/protocol incompatibility, or reproducibility failure."
            ),
            remediation="Use a supported invalidation cause or leave the frozen bundle valid.",
        )

    return ContextInvalidationReport(
        bundle_id=bundle.bundle_id,
        invalidation_cause=invalidation_cause,
        status=ContextContractStatus.PASS.value,
        allowed=True,
        reason_code="CONTEXT_BUNDLE_INVALIDATION_CAUSE_ALLOWED",
        explanation="The invalidation cause is one of the canonical reasons allowed by the plan.",
        remediation="No remediation required.",
    )


def validate_execution_profile_release(
    case_id: str,
    release: ExecutionProfileRelease,
) -> ExecutionProfileValidationReport:
    if release.schema_version != SUPPORTED_CONTEXT_SCHEMA_VERSION:
        return ExecutionProfileValidationReport(
            case_id=case_id,
            release_id=release.release_id or None,
            status=ContextContractStatus.INVALID.value,
            reason_code="EXECUTION_PROFILE_RELEASE_SCHEMA_VERSION_UNSUPPORTED",
            lifecycle_state=release.lifecycle_state.value,
            data_profile_release_id=release.data_profile_release_id or None,
            artifact_root_hash=release.artifact_root_hash or None,
            missing_fields=(),
            explanation=(
                "The execution-profile release uses an unsupported schema version for the "
                "canonical contract."
            ),
            remediation="Publish the release using the supported canonical schema version.",
        )

    missing_fields = _missing_execution_profile_fields(release)
    if missing_fields:
        return ExecutionProfileValidationReport(
            case_id=case_id,
            release_id=release.release_id or None,
            status=ContextContractStatus.INVALID.value,
            reason_code="EXECUTION_PROFILE_RELEASE_MISSING_REQUIRED_FIELDS",
            lifecycle_state=release.lifecycle_state.value,
            data_profile_release_id=release.data_profile_release_id or None,
            artifact_root_hash=release.artifact_root_hash or None,
            missing_fields=missing_fields,
            explanation=(
                "The execution-profile release is missing one or more required assumption sets: "
                f"{missing_fields}."
            ),
            remediation=(
                "Populate the order, slippage, fill, latency, degraded-bar, calibration, and "
                "data-profile bindings before release."
            ),
        )

    if not _mentions_digest(release.release_id, release.artifact_root_hash):
        return ExecutionProfileValidationReport(
            case_id=case_id,
            release_id=release.release_id,
            status=ContextContractStatus.VIOLATION.value,
            reason_code="EXECUTION_PROFILE_RELEASE_NOT_DIGEST_BOUND",
            lifecycle_state=release.lifecycle_state.value,
            data_profile_release_id=release.data_profile_release_id,
            artifact_root_hash=release.artifact_root_hash,
            missing_fields=(),
            explanation=(
                "The execution-profile release identifier does not embed the artifact hash, so "
                "downstream surfaces cannot bind the assumptions by digest."
            ),
            remediation="Regenerate the release identifier from the canonical artifact hash.",
        )

    return ExecutionProfileValidationReport(
        case_id=case_id,
        release_id=release.release_id,
        status=ContextContractStatus.PASS.value,
        reason_code="EXECUTION_PROFILE_RELEASE_VERSIONED",
        lifecycle_state=release.lifecycle_state.value,
        data_profile_release_id=release.data_profile_release_id,
        artifact_root_hash=release.artifact_root_hash,
        missing_fields=(),
        explanation=(
            "The execution-profile release captures governed execution assumptions, calibration "
            "evidence, and the applicable data-profile release behind a digest-bound identifier."
        ),
        remediation="No remediation required.",
    )


def validate_context_artifact_binding(
    request: ContextArtifactBindingRequest,
) -> ContextBindingReport:
    bound_artifact_set = {
        "resolved_context_bundle_id": request.resolved_context_bundle_id or "",
        "resolved_context_content_hash": request.resolved_context_content_hash or "",
        "execution_profile_release_id": request.execution_profile_release_id or "",
        "execution_profile_artifact_hash": request.execution_profile_artifact_hash or "",
    }
    missing_fields = tuple(
        field_name for field_name, field_value in bound_artifact_set.items() if not field_value
    )
    if missing_fields:
        return ContextBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=ContextContractStatus.INVALID.value,
            reason_code="CONTEXT_BINDING_MISSING_REQUIRED_DIGESTS",
            digest_bound=False,
            bound_artifact_set=bound_artifact_set,
            mutable_reference_reads=request.mutable_reference_reads,
            mutable_execution_overrides=request.mutable_execution_overrides,
            explanation=(
                "The binding surface is missing one or more required digest-bound context "
                f"artifacts: {missing_fields}."
            ),
            remediation="Bind both the resolved-context bundle and execution-profile release by digest.",
        )

    if request.mutable_reference_reads:
        return ContextBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=ContextContractStatus.VIOLATION.value,
            reason_code="CONTEXT_BINDING_MUTABLE_REFERENCE_READ",
            digest_bound=False,
            bound_artifact_set=bound_artifact_set,
            mutable_reference_reads=request.mutable_reference_reads,
            mutable_execution_overrides=request.mutable_execution_overrides,
            explanation=(
                "The binding surface still depends on mutable reference reads instead of the "
                f"frozen resolved-context bundle: {request.mutable_reference_reads}."
            ),
            remediation="Remove runtime reference reads and rely on the frozen bundle only.",
        )

    if request.mutable_execution_overrides:
        return ContextBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=ContextContractStatus.VIOLATION.value,
            reason_code="CONTEXT_BINDING_MUTABLE_EXECUTION_OVERRIDE",
            digest_bound=False,
            bound_artifact_set=bound_artifact_set,
            mutable_reference_reads=request.mutable_reference_reads,
            mutable_execution_overrides=request.mutable_execution_overrides,
            explanation=(
                "The binding surface applies mutable execution overrides instead of using the "
                f"governed execution-profile release: {request.mutable_execution_overrides}."
            ),
            remediation="Remove mutable overrides and bind exactly one execution-profile release.",
        )

    digest_bound = _mentions_digest(
        request.resolved_context_bundle_id,
        request.resolved_context_content_hash,
    ) and _mentions_digest(
        request.execution_profile_release_id,
        request.execution_profile_artifact_hash,
    )
    if not digest_bound:
        return ContextBindingReport(
            case_id=request.case_id,
            surface_name=request.surface_name.value,
            status=ContextContractStatus.VIOLATION.value,
            reason_code="CONTEXT_BINDING_NOT_DIGEST_PINNED",
            digest_bound=False,
            bound_artifact_set=bound_artifact_set,
            mutable_reference_reads=request.mutable_reference_reads,
            mutable_execution_overrides=request.mutable_execution_overrides,
            explanation=(
                "The surface references context artifacts, but one or both identifiers do not "
                "embed the referenced digest."
            ),
            remediation="Regenerate the artifact identifiers from their canonical digests before binding.",
        )

    return ContextBindingReport(
        case_id=request.case_id,
        surface_name=request.surface_name.value,
        status=ContextContractStatus.PASS.value,
        reason_code="CONTEXT_BINDING_DIGEST_PINNED",
        digest_bound=True,
        bound_artifact_set=bound_artifact_set,
        mutable_reference_reads=request.mutable_reference_reads,
        mutable_execution_overrides=request.mutable_execution_overrides,
        explanation=(
            "The surface binds the frozen resolved-context bundle and execution-profile release "
            "directly by digest without mutable overrides."
        ),
        remediation="No remediation required.",
    )


def validate_resolved_context_contract() -> list[str]:
    errors: list[str] = []
    try:
        resolved_context_definition = get_artifact_definition("resolved_context_bundle")
    except KeyError:
        errors.append("resolved_context_bundle: missing from artifact-class registry")
    else:
        if resolved_context_definition.artifact_class != ArtifactClass.INTEGRITY_BOUND:
            errors.append("resolved_context_bundle: must remain integrity-bound")

    try:
        execution_profile_definition = get_artifact_definition("execution_profile_release")
    except KeyError:
        errors.append("execution_profile_release: missing from artifact-class registry")
    else:
        if execution_profile_definition.artifact_class != ArtifactClass.INTEGRITY_BOUND:
            errors.append("execution_profile_release: must remain integrity-bound")

    storage_index = storage_artifact_classes_by_type()
    resolved_context_storage = storage_index.get("resolved_context_bundle")
    if resolved_context_storage is None:
        errors.append("resolved_context_bundle: missing from storage-tier catalog")
    elif resolved_context_storage.storage_tier != StorageTier.TIER_B:
        errors.append("resolved_context_bundle: must remain in storage tier B")

    execution_profile_storage = storage_index.get("execution_profile_release")
    if execution_profile_storage is None:
        errors.append("execution_profile_release: missing from storage-tier catalog")
    elif execution_profile_storage.storage_tier != StorageTier.TIER_D:
        errors.append("execution_profile_release: must remain in storage tier D")

    if "data_profile_release" not in release_definitions_by_kind():
        errors.append("data_profile_release: execution-profile releases require the canonical release")

    return errors


VALIDATION_ERRORS = validate_resolved_context_contract()
