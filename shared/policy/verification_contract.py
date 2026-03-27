from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class VerificationClass(str, Enum):
    UNIT = "unit"
    CONTRACT = "contract"
    PROPERTY = "property"
    GOLDEN_PATH = "golden_path"
    FAILURE_PATH = "failure_path"
    PARITY_CERTIFICATION = "parity_certification"
    REPLAY_CERTIFICATION = "replay_certification"
    OPERATIONAL_REHEARSAL = "operational_rehearsal"


class ArtifactRequirement(str, Enum):
    STRUCTURED_LOGS = "structured_logs"
    CORRELATION_IDS = "correlation_ids"
    EXPECTED_VS_ACTUAL_DIFFS = "expected_vs_actual_diffs"
    ARTIFACT_MANIFESTS = "artifact_manifests"
    OPERATOR_REASON_BUNDLES = "operator_reason_bundles"
    DECISION_TRACES = "decision_traces"
    FIXTURE_MANIFESTS = "fixture_manifests"
    REPRODUCIBILITY_STAMPS = "reproducibility_stamps"


class ExplainabilityRequirement(str, Enum):
    RULE_TRACE = "rule_trace"
    REJECTION_REASON_CODES = "rejection_reason_codes"
    REMEDIATION_HINTS = "remediation_hints"
    GATE_SUMMARIES = "gate_summaries"


class FixtureSource(str, Enum):
    CERTIFIED_RELEASE = "certified_release"
    GOLDEN_SESSION = "golden_session"
    BROKER_SESSION_RECORDING = "broker_session_recording"
    SYNTHETIC_FAILURE_CASE = "synthetic_failure_case"
    PLAN_SEEDED_FIXTURE = "plan_seeded_fixture"


class TracePlane(str, Enum):
    RESEARCH = "research"
    RELEASE = "release"
    POLICY = "policy"
    CERTIFICATION = "certification"
    RUNTIME = "runtime"
    RECOVERY = "recovery"


LOCAL_CHECKS = (
    VerificationClass.UNIT,
    VerificationClass.CONTRACT,
    VerificationClass.PROPERTY,
)

GATE_DECISION_ARTIFACTS = (
    ArtifactRequirement.STRUCTURED_LOGS,
    ArtifactRequirement.CORRELATION_IDS,
    ArtifactRequirement.EXPECTED_VS_ACTUAL_DIFFS,
    ArtifactRequirement.ARTIFACT_MANIFESTS,
    ArtifactRequirement.OPERATOR_REASON_BUNDLES,
    ArtifactRequirement.DECISION_TRACES,
)

CORE_EXPLAINABILITY = (
    ExplainabilityRequirement.RULE_TRACE,
    ExplainabilityRequirement.REJECTION_REASON_CODES,
    ExplainabilityRequirement.REMEDIATION_HINTS,
    ExplainabilityRequirement.GATE_SUMMARIES,
)


@dataclass(frozen=True)
class FixtureContract:
    sources: tuple[FixtureSource, ...]
    deterministic_seed_required: bool
    deterministic_clock_required: bool
    provenance_required: bool


@dataclass(frozen=True)
class VerificationProfile:
    surface_id: str
    title: str
    related_beads: tuple[str, ...]
    phase_gates: tuple[str, ...]
    local_checks: tuple[VerificationClass, ...]
    golden_path: tuple[VerificationClass, ...]
    failure_path: tuple[VerificationClass, ...]
    retained_artifacts: tuple[ArtifactRequirement, ...]
    explainability: tuple[ExplainabilityRequirement, ...]
    fixture_contract: FixtureContract


@dataclass(frozen=True)
class PlaneTraceContract:
    plane: TracePlane
    required_identifiers: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactManifestContract:
    required_fields: tuple[str, ...]
    required_artifact_fields: tuple[str, ...]
    secret_boundary_fields: tuple[str, ...]


@dataclass(frozen=True)
class StructuredLoggingContract:
    schema_version: int
    required_envelope_fields: tuple[str, ...]
    plane_contracts: tuple[PlaneTraceContract, ...]
    artifact_manifest: ArtifactManifestContract


REQUIRED_CROSS_PLANE_IDENTIFIERS = (
    "dataset_release_id",
    "analytic_release_id",
    "data_profile_release_id",
    "resolved_context_bundle_id",
    "research_run_id",
    "family_decision_record_id",
    "candidate_bundle_id",
    "promotion_packet_id",
    "session_readiness_packet_id",
    "deployment_instance_id",
    "order_intent_id",
)

LOG_ENVELOPE_REQUIRED_FIELDS = (
    "schema_version",
    "event_type",
    "plane",
    "event_id",
    "recorded_at_utc",
    "correlation_id",
    "decision_trace_id",
    "reason_code",
    "reason_summary",
    "referenced_ids",
    "redacted_fields",
    "omitted_fields",
    "artifact_manifest",
)

ARTIFACT_MANIFEST_REQUIRED_FIELDS = (
    "manifest_id",
    "generated_at_utc",
    "retention_class",
    "contains_secrets",
    "redaction_policy",
    "artifacts",
)

ARTIFACT_ENTRY_REQUIRED_FIELDS = (
    "artifact_id",
    "artifact_role",
    "relative_path",
    "sha256",
    "content_type",
)

REQUIRED_REDACTION_FIELDS = (
    "broker_account_id",
    "credential_ref",
    "api_token",
    "session_cookie",
)

EXPECTED_CROSS_PLANE_IDENTIFIER_COVERAGE: dict[str, tuple[TracePlane, ...]] = {
    "dataset_release_id": (TracePlane.RESEARCH, TracePlane.RELEASE),
    "analytic_release_id": (TracePlane.RESEARCH, TracePlane.RELEASE),
    "data_profile_release_id": (TracePlane.RESEARCH, TracePlane.RELEASE),
    "resolved_context_bundle_id": (
        TracePlane.RESEARCH,
        TracePlane.RELEASE,
        TracePlane.POLICY,
    ),
    "research_run_id": (TracePlane.RESEARCH, TracePlane.POLICY),
    "family_decision_record_id": (TracePlane.POLICY, TracePlane.CERTIFICATION),
    "candidate_bundle_id": (
        TracePlane.RELEASE,
        TracePlane.POLICY,
        TracePlane.CERTIFICATION,
        TracePlane.RUNTIME,
    ),
    "promotion_packet_id": (
        TracePlane.CERTIFICATION,
        TracePlane.RUNTIME,
        TracePlane.RECOVERY,
    ),
    "session_readiness_packet_id": (
        TracePlane.CERTIFICATION,
        TracePlane.RUNTIME,
        TracePlane.RECOVERY,
    ),
    "deployment_instance_id": (TracePlane.RUNTIME, TracePlane.RECOVERY),
    "order_intent_id": (TracePlane.RUNTIME, TracePlane.RECOVERY),
}

PLANE_TRACE_CONTRACTS = (
    PlaneTraceContract(
        plane=TracePlane.RESEARCH,
        required_identifiers=(
            "research_run_id",
            "dataset_release_id",
            "analytic_release_id",
            "data_profile_release_id",
            "resolved_context_bundle_id",
        ),
    ),
    PlaneTraceContract(
        plane=TracePlane.RELEASE,
        required_identifiers=(
            "dataset_release_id",
            "analytic_release_id",
            "data_profile_release_id",
            "resolved_context_bundle_id",
            "candidate_bundle_id",
        ),
    ),
    PlaneTraceContract(
        plane=TracePlane.POLICY,
        required_identifiers=(
            "research_run_id",
            "resolved_context_bundle_id",
            "family_decision_record_id",
            "candidate_bundle_id",
        ),
    ),
    PlaneTraceContract(
        plane=TracePlane.CERTIFICATION,
        required_identifiers=(
            "family_decision_record_id",
            "candidate_bundle_id",
            "promotion_packet_id",
            "session_readiness_packet_id",
        ),
    ),
    PlaneTraceContract(
        plane=TracePlane.RUNTIME,
        required_identifiers=(
            "candidate_bundle_id",
            "promotion_packet_id",
            "session_readiness_packet_id",
            "deployment_instance_id",
            "order_intent_id",
        ),
    ),
    PlaneTraceContract(
        plane=TracePlane.RECOVERY,
        required_identifiers=(
            "promotion_packet_id",
            "session_readiness_packet_id",
            "deployment_instance_id",
            "order_intent_id",
        ),
    ),
)

STRUCTURED_LOGGING_CONTRACT = StructuredLoggingContract(
    schema_version=1,
    required_envelope_fields=LOG_ENVELOPE_REQUIRED_FIELDS,
    plane_contracts=PLANE_TRACE_CONTRACTS,
    artifact_manifest=ArtifactManifestContract(
        required_fields=ARTIFACT_MANIFEST_REQUIRED_FIELDS,
        required_artifact_fields=ARTIFACT_ENTRY_REQUIRED_FIELDS,
        secret_boundary_fields=("contains_secrets", "redaction_policy"),
    ),
)

GOLDEN_LOG_FIXTURES: dict[TracePlane, dict[str, object]] = {
    TracePlane.RESEARCH: {
        "schema_version": 1,
        "event_type": "research_run.completed",
        "plane": TracePlane.RESEARCH.value,
        "event_id": "research_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:00:00Z",
        "correlation_id": "corr_research_20260326_001",
        "decision_trace_id": "decision_trace_research_001",
        "reason_code": "RESEARCH_RUN_COMPLETED",
        "reason_summary": "Research run completed with reproducible release bindings.",
        "redacted_fields": ("broker_account_id",),
        "omitted_fields": ("api_token",),
        "referenced_ids": {
            "research_run_id": "research_run_gold_20260326_001",
            "dataset_release_id": "dataset_release_gold_2026q1_v1",
            "analytic_release_id": "analytic_release_gold_2026q1_v1",
            "data_profile_release_id": "data_profile_release_gold_2026q1_v1",
            "resolved_context_bundle_id": "resolved_context_bundle_gold_2026q1_ctx_sha256_001",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_research_001",
            "generated_at_utc": "2026-03-26T18:00:01Z",
            "retention_class": "gate_decision",
            "contains_secrets": False,
            "redaction_policy": "no_credentials",
            "artifacts": (
                {
                    "artifact_id": "research_summary_json",
                    "artifact_role": "research_summary",
                    "relative_path": "research/runs/research_run_gold_20260326_001/summary.json",
                    "sha256": "sha256:research-summary",
                    "content_type": "application/json",
                },
            ),
        },
    },
    TracePlane.RELEASE: {
        "schema_version": 1,
        "event_type": "release_manifest.frozen",
        "plane": TracePlane.RELEASE.value,
        "event_id": "release_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:05:00Z",
        "correlation_id": "corr_release_20260326_001",
        "decision_trace_id": "decision_trace_release_001",
        "reason_code": "RELEASE_MANIFEST_FROZEN",
        "reason_summary": "Immutable release manifest frozen for downstream certification.",
        "redacted_fields": ("credential_ref",),
        "omitted_fields": (),
        "referenced_ids": {
            "dataset_release_id": "dataset_release_gold_2026q1_v1",
            "analytic_release_id": "analytic_release_gold_2026q1_v1",
            "data_profile_release_id": "data_profile_release_gold_2026q1_v1",
            "resolved_context_bundle_id": "resolved_context_bundle_gold_2026q1_ctx_sha256_001",
            "candidate_bundle_id": "candidate_bundle_gold_core_candidate_bundle_sha256_001",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_release_001",
            "generated_at_utc": "2026-03-26T18:05:01Z",
            "retention_class": "gate_decision",
            "contains_secrets": False,
            "redaction_policy": "release_metadata_only",
            "artifacts": (
                {
                    "artifact_id": "release_manifest_json",
                    "artifact_role": "release_manifest",
                    "relative_path": "release/manifests/candidate_bundle_gold_core_candidate_bundle_sha256_001.json",
                    "sha256": "sha256:release-manifest",
                    "content_type": "application/json",
                },
            ),
        },
    },
    TracePlane.POLICY: {
        "schema_version": 1,
        "event_type": "policy.family_decision_recorded",
        "plane": TracePlane.POLICY.value,
        "event_id": "policy_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:10:00Z",
        "correlation_id": "corr_policy_20260326_001",
        "decision_trace_id": "decision_trace_policy_001",
        "reason_code": "FAMILY_APPROVED",
        "reason_summary": "Policy selected a promotable candidate family.",
        "redacted_fields": (),
        "omitted_fields": (),
        "referenced_ids": {
            "research_run_id": "research_run_gold_20260326_001",
            "resolved_context_bundle_id": "resolved_context_bundle_gold_2026q1_ctx_sha256_001",
            "family_decision_record_id": "family_decision_record_gold_20260326_001",
            "candidate_bundle_id": "candidate_bundle_gold_core_candidate_bundle_sha256_001",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_policy_001",
            "generated_at_utc": "2026-03-26T18:10:01Z",
            "retention_class": "gate_decision",
            "contains_secrets": False,
            "redaction_policy": "reason_bundle_only",
            "artifacts": (
                {
                    "artifact_id": "family_decision_bundle_json",
                    "artifact_role": "operator_reason_bundle",
                    "relative_path": "policy/family_decisions/family_decision_record_gold_20260326_001.json",
                    "sha256": "sha256:family-decision",
                    "content_type": "application/json",
                },
            ),
        },
    },
    TracePlane.CERTIFICATION: {
        "schema_version": 1,
        "event_type": "certification.promotion_packet_approved",
        "plane": TracePlane.CERTIFICATION.value,
        "event_id": "cert_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:15:00Z",
        "correlation_id": "corr_certification_20260326_001",
        "decision_trace_id": "decision_trace_certification_001",
        "reason_code": "PROMOTION_PACKET_APPROVED",
        "reason_summary": "Certification approved the packet for runtime activation.",
        "redacted_fields": ("credential_ref",),
        "omitted_fields": (),
        "referenced_ids": {
            "family_decision_record_id": "family_decision_record_gold_20260326_001",
            "candidate_bundle_id": "candidate_bundle_gold_core_candidate_bundle_sha256_001",
            "promotion_packet_id": "promotion_packet_gold_live_v1",
            "session_readiness_packet_id": "session_packet_gold_live_20260326",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_certification_001",
            "generated_at_utc": "2026-03-26T18:15:01Z",
            "retention_class": "gate_decision",
            "contains_secrets": False,
            "redaction_policy": "certification_bundle_only",
            "artifacts": (
                {
                    "artifact_id": "promotion_packet_json",
                    "artifact_role": "promotion_packet",
                    "relative_path": "certification/promotion_packets/promotion_packet_gold_live_v1.json",
                    "sha256": "sha256:promotion-packet",
                    "content_type": "application/json",
                },
            ),
        },
    },
    TracePlane.RUNTIME: {
        "schema_version": 1,
        "event_type": "runtime.order_intent_emitted",
        "plane": TracePlane.RUNTIME.value,
        "event_id": "runtime_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:20:00Z",
        "correlation_id": "corr_runtime_20260326_001",
        "decision_trace_id": "decision_trace_runtime_001",
        "reason_code": "ORDER_INTENT_EMITTED",
        "reason_summary": "Runtime emitted an order intent under an active deployment instance.",
        "redacted_fields": ("broker_account_id",),
        "omitted_fields": ("session_cookie",),
        "referenced_ids": {
            "candidate_bundle_id": "candidate_bundle_gold_core_candidate_bundle_sha256_001",
            "promotion_packet_id": "promotion_packet_gold_live_v1",
            "session_readiness_packet_id": "session_packet_gold_live_20260326",
            "deployment_instance_id": "deployment_gold_live_v1",
            "order_intent_id": "order_intent_gold_live_001",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_runtime_001",
            "generated_at_utc": "2026-03-26T18:20:01Z",
            "retention_class": "runtime_evidence",
            "contains_secrets": True,
            "redaction_policy": "credentials_redacted",
            "artifacts": (
                {
                    "artifact_id": "runtime_intent_json",
                    "artifact_role": "order_intent",
                    "relative_path": "runtime/order_intents/order_intent_gold_live_001.json",
                    "sha256": "sha256:order-intent",
                    "content_type": "application/json",
                },
            ),
        },
    },
    TracePlane.RECOVERY: {
        "schema_version": 1,
        "event_type": "recovery.restore_drill_completed",
        "plane": TracePlane.RECOVERY.value,
        "event_id": "recovery_event_20260326_001",
        "recorded_at_utc": "2026-03-26T18:25:00Z",
        "correlation_id": "corr_recovery_20260326_001",
        "decision_trace_id": "decision_trace_recovery_001",
        "reason_code": "RESTORE_DRILL_COMPLETED",
        "reason_summary": "Recovery drill reconstructed runtime state and verified retained evidence.",
        "redacted_fields": (),
        "omitted_fields": (),
        "referenced_ids": {
            "promotion_packet_id": "promotion_packet_gold_live_v1",
            "session_readiness_packet_id": "session_packet_gold_live_20260326",
            "deployment_instance_id": "deployment_gold_live_v1",
            "order_intent_id": "order_intent_gold_live_001",
        },
        "artifact_manifest": {
            "manifest_id": "artifact_manifest_recovery_001",
            "generated_at_utc": "2026-03-26T18:25:01Z",
            "retention_class": "recovery_evidence",
            "contains_secrets": False,
            "redaction_policy": "restore_summary_only",
            "artifacts": (
                {
                    "artifact_id": "restore_drill_report_json",
                    "artifact_role": "recovery_report",
                    "relative_path": "recovery/drills/restore_drill_20260326/report.json",
                    "sha256": "sha256:restore-drill",
                    "content_type": "application/json",
                },
            ),
        },
    },
}


def plane_trace_contracts() -> dict[TracePlane, PlaneTraceContract]:
    return {contract.plane: contract for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts}


def validate_log_fixture(plane: TracePlane, payload: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    contract = plane_trace_contracts()[plane]

    for field_name in STRUCTURED_LOGGING_CONTRACT.required_envelope_fields:
        if field_name not in payload:
            errors.append(f"{plane.value}: missing envelope field {field_name}")

    if payload.get("schema_version") != STRUCTURED_LOGGING_CONTRACT.schema_version:
        errors.append(
            f"{plane.value}: schema_version must be {STRUCTURED_LOGGING_CONTRACT.schema_version}"
        )
    if payload.get("plane") != plane.value:
        errors.append(f"{plane.value}: plane marker must equal {plane.value}")

    for field_name in ("redacted_fields", "omitted_fields"):
        value = payload.get(field_name)
        if not isinstance(value, (list, tuple)):
            errors.append(f"{plane.value}: {field_name} must be a sequence")

    referenced_ids = payload.get("referenced_ids")
    if not isinstance(referenced_ids, Mapping):
        errors.append(f"{plane.value}: referenced_ids must be a mapping")
    else:
        for identifier in contract.required_identifiers:
            value = referenced_ids.get(identifier)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{plane.value}: missing referenced_ids.{identifier}")

    manifest = payload.get("artifact_manifest")
    if not isinstance(manifest, Mapping):
        errors.append(f"{plane.value}: artifact_manifest must be a mapping")
        return errors

    for field_name in STRUCTURED_LOGGING_CONTRACT.artifact_manifest.required_fields:
        if field_name not in manifest:
            errors.append(f"{plane.value}: missing artifact_manifest.{field_name}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, (list, tuple)) or not artifacts:
        errors.append(f"{plane.value}: artifact_manifest.artifacts must be a non-empty sequence")
        return errors

    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            errors.append(f"{plane.value}: artifact_manifest.artifacts[{index}] must be a mapping")
            continue
        for field_name in STRUCTURED_LOGGING_CONTRACT.artifact_manifest.required_artifact_fields:
            if field_name not in artifact:
                errors.append(
                    f"{plane.value}: missing artifact_manifest.artifacts[{index}].{field_name}"
                )

    return errors


def cross_plane_identifier_coverage() -> dict[str, tuple[TracePlane, ...]]:
    coverage: dict[str, list[TracePlane]] = {
        identifier: [] for identifier in REQUIRED_CROSS_PLANE_IDENTIFIERS
    }
    for plane, payload in GOLDEN_LOG_FIXTURES.items():
        referenced_ids = payload.get("referenced_ids")
        if not isinstance(referenced_ids, Mapping):
            continue
        for identifier, value in referenced_ids.items():
            if identifier in coverage and isinstance(value, str) and value.strip():
                coverage[identifier].append(plane)
    return {
        identifier: tuple(planes)
        for identifier, planes in coverage.items()
    }


def validate_cross_plane_story() -> list[str]:
    errors: list[str] = []

    if set(GOLDEN_LOG_FIXTURES) != set(plane_trace_contracts()):
        errors.append("golden log fixtures must cover every declared trace plane")

    for identifier, expected_planes in EXPECTED_CROSS_PLANE_IDENTIFIER_COVERAGE.items():
        actual_planes = cross_plane_identifier_coverage().get(identifier, ())
        if actual_planes != expected_planes:
            errors.append(
                f"{identifier}: expected planes {expected_planes} but found {actual_planes}"
            )

    observed_redactions = {
        field_name
        for payload in GOLDEN_LOG_FIXTURES.values()
        for collection_name in ("redacted_fields", "omitted_fields")
        for field_name in payload.get(collection_name, ())
        if isinstance(field_name, str)
    }
    missing_redactions = set(REQUIRED_REDACTION_FIELDS).difference(observed_redactions)
    if missing_redactions:
        names = ", ".join(sorted(missing_redactions))
        errors.append(f"golden log fixtures missing secret-boundary coverage for: {names}")

    runtime_payload = GOLDEN_LOG_FIXTURES[TracePlane.RUNTIME]
    runtime_manifest = runtime_payload.get("artifact_manifest", {})
    if isinstance(runtime_manifest, Mapping):
        if runtime_manifest.get("contains_secrets") is not True:
            errors.append("runtime fixture must declare that secrets were present before redaction")
        if runtime_manifest.get("redaction_policy") != "credentials_redacted":
            errors.append("runtime fixture must record the credentials_redacted policy")

    recovery_payload = GOLDEN_LOG_FIXTURES[TracePlane.RECOVERY]
    recovery_references = recovery_payload.get("referenced_ids", {})
    runtime_references = runtime_payload.get("referenced_ids", {})
    if isinstance(recovery_references, Mapping) and isinstance(runtime_references, Mapping):
        for identifier in ("promotion_packet_id", "session_readiness_packet_id", "deployment_instance_id", "order_intent_id"):
            if recovery_references.get(identifier) != runtime_references.get(identifier):
                errors.append(
                    f"recovery fixture must retain runtime identifier {identifier}"
                )

    return errors


def validate_logging_contract() -> list[str]:
    errors: list[str] = []
    plane_ids = [contract.plane for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts]
    if len(plane_ids) != len(set(plane_ids)):
        errors.append("structured logging contract planes must be unique")

    covered_identifiers = {
        identifier
        for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts
        for identifier in contract.required_identifiers
    }
    missing_identifiers = set(REQUIRED_CROSS_PLANE_IDENTIFIERS).difference(covered_identifiers)
    if missing_identifiers:
        names = ", ".join(sorted(missing_identifiers))
        errors.append(f"structured logging contract missing identifiers: {names}")

    for contract in STRUCTURED_LOGGING_CONTRACT.plane_contracts:
        if not contract.required_identifiers:
            errors.append(f"{contract.plane.value}: trace contract must declare identifiers")

    for plane, payload in GOLDEN_LOG_FIXTURES.items():
        errors.extend(validate_log_fixture(plane, payload))

    errors.extend(validate_cross_plane_story())

    return errors


def _gate_profile(
    *,
    surface_id: str,
    title: str,
    related_beads: tuple[str, ...],
    phase_gates: tuple[str, ...],
    fixture_sources: tuple[FixtureSource, ...],
    golden_path: tuple[VerificationClass, ...],
    failure_path: tuple[VerificationClass, ...],
) -> VerificationProfile:
    return VerificationProfile(
        surface_id=surface_id,
        title=title,
        related_beads=related_beads,
        phase_gates=phase_gates,
        local_checks=LOCAL_CHECKS,
        golden_path=golden_path,
        failure_path=failure_path,
        retained_artifacts=GATE_DECISION_ARTIFACTS
        + (
            ArtifactRequirement.FIXTURE_MANIFESTS,
            ArtifactRequirement.REPRODUCIBILITY_STAMPS,
        ),
        explainability=CORE_EXPLAINABILITY,
        fixture_contract=FixtureContract(
            sources=fixture_sources,
            deterministic_seed_required=True,
            deterministic_clock_required=True,
            provenance_required=True,
        ),
    )


VERIFICATION_PROFILES: tuple[VerificationProfile, ...] = (
    _gate_profile(
        surface_id="mission_and_live_lane_posture",
        title="Mission and live-lane posture",
        related_beads=("backtesting_engine-ltc.1.1",),
        phase_gates=("phase_0",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="program_guardrails",
        title="Program guardrails and hard prohibitions",
        related_beads=("backtesting_engine-ltc.1.2",),
        phase_gates=("phase_0",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
    ),
    _gate_profile(
        surface_id="phase_0_foundation_and_qa_gate",
        title="Phase 0 foundation and QA gate",
        related_beads=("backtesting_engine-ltc.9.1",),
        phase_gates=("phase_0",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="plane_boundaries_and_shared_contracts",
        title="Plane separation and shared contract boundaries",
        related_beads=("backtesting_engine-ltc.2.1",),
        phase_gates=("phase_0",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.GOLDEN_SESSION,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="canonical_metadata_and_dense_telemetry",
        title="Canonical metadata versus dense telemetry",
        related_beads=("backtesting_engine-ltc.2.3",),
        phase_gates=("phase_1",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="phase_1_raw_archive_and_reference_gate",
        title="Phase 1 raw archive and bitemporal reference gate",
        related_beads=("backtesting_engine-ltc.9.2",),
        phase_gates=("phase_1",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="phase_2_validation_and_release_pipeline_gate",
        title="Phase 2 validation and release-pipeline gate",
        related_beads=("backtesting_engine-ltc.9.3",),
        phase_gates=("phase_2",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="time_discipline_and_session_clocks",
        title="Time discipline, session clocks, and skew policy",
        related_beads=("backtesting_engine-ltc.2.5",),
        phase_gates=("phase_0",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.REPLAY_CERTIFICATION,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="data_reference_and_release_pipeline",
        title="Data/reference objects and release pipeline",
        related_beads=(
            "backtesting_engine-ltc.3.1",
            "backtesting_engine-ltc.3.4",
            "backtesting_engine-ltc.3.8",
            "backtesting_engine-ltc.3.9",
            "backtesting_engine-ltc.3.10",
            "backtesting_engine-ltc.3.11",
        ),
        phase_gates=("phase_1", "phase_2"),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="lifecycle_state_machines_and_compatibility_domains",
        title="Lifecycle state machines and compatibility domains",
        related_beads=("backtesting_engine-ltc.8.2",),
        phase_gates=("phase_0", "phase_2", "phase_6", "phase_7", "phase_8"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(
            VerificationClass.FAILURE_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
    ),
    _gate_profile(
        surface_id="execution_lane_vertical_slice",
        title="Execution-lane viability and vertical slice",
        related_beads=(
            "backtesting_engine-ltc.1.5",
            "backtesting_engine-ltc.4.3",
            "backtesting_engine-ltc.11.9",
        ),
        phase_gates=("phase_2_5",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="operational_runtime_supervision_and_state_ownership",
        title="Operational runtime supervision and deterministic state ownership",
        related_beads=("backtesting_engine-ltc.7.9",),
        phase_gates=("phase_2_5", "phase_7"),
        fixture_sources=(
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="simulation_and_execution_profiles",
        title="Simulation semantics, fidelity calibration, and execution calibration",
        related_beads=(
            "backtesting_engine-ltc.4.1",
            "backtesting_engine-ltc.4.2",
            "backtesting_engine-ltc.4.4",
            "backtesting_engine-ltc.4.5",
            "backtesting_engine-ltc.11.9",
        ),
        phase_gates=("phase_3",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="fast_screening_governance",
        title="Fast-screening eligibility, equivalence, and non-promotable controls",
        related_beads=("backtesting_engine-ltc.4.6",),
        phase_gates=("phase_3",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="strategy_contracts_and_canonical_signal_kernel",
        title="Strategy contracts and canonical signal kernels",
        related_beads=("backtesting_engine-ltc.5.1",),
        phase_gates=("phase_5", "phase_6"),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.PARITY_CERTIFICATION),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="baseline_risk_controls_and_waiver_defaults",
        title="Baseline risk controls and waiver defaults",
        related_beads=("backtesting_engine-ltc.5.2",),
        phase_gates=("phase_5", "phase_7"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="operating_envelope_and_session_conditioned_risk_profiles",
        title="Operating-envelope and session-conditioned risk profiles",
        related_beads=("backtesting_engine-ltc.5.3",),
        phase_gates=("phase_5", "phase_7"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="actual_execution_contract_account_fit",
        title="Account-fit gate on the actual execution contract",
        related_beads=("backtesting_engine-ltc.5.4",),
        phase_gates=("phase_5", "phase_7"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="fully_loaded_economics",
        title="Fully loaded economics and recurring cost model",
        related_beads=("backtesting_engine-ltc.5.5",),
        phase_gates=("phase_5",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="absolute_dollar_viability_and_benchmark_gate",
        title="Absolute-dollar viability and benchmark gate",
        related_beads=("backtesting_engine-ltc.5.6",),
        phase_gates=("phase_5",),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="strict_overnight_candidate_class",
        title="Strict overnight candidate class",
        related_beads=("backtesting_engine-ltc.5.7",),
        phase_gates=("phase_5", "phase_7"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="structured_logging_and_artifact_capture",
        title="Structured logs, trace correlation, and artifact capture",
        related_beads=("backtesting_engine-ltc.11.6",),
        phase_gates=("phase_1", "phase_3", "phase_4", "phase_6", "phase_7", "phase_8"),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.REPLAY_CERTIFICATION,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="domain_semantics_contract_suites",
        title="Domain contract suites for policy, schemas, execution profiles, and broker semantics",
        related_beads=("backtesting_engine-ltc.11.3",),
        phase_gates=("phase_0", "phase_2", "phase_3", "phase_5", "phase_7", "phase_8"),
        fixture_sources=(
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(
            VerificationClass.FAILURE_PATH,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
    ),
    _gate_profile(
        surface_id="research_governance_and_selection",
        title="Research governance, budgets, and selection gates",
        related_beads=(
            "backtesting_engine-ltc.6.3",
            "backtesting_engine-ltc.6.1",
            "backtesting_engine-ltc.6.2",
            "backtesting_engine-ltc.6.4",
            "backtesting_engine-ltc.6.5",
            "backtesting_engine-ltc.6.6",
            "backtesting_engine-ltc.6.7",
        ),
        phase_gates=("phase_4", "phase_5"),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.PLAN_SEEDED_FIXTURE,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH,),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="candidate_and_activation_packets",
        title="Candidate bundles, readiness records, and activation packets",
        related_beads=("backtesting_engine-ltc.3.6",),
        phase_gates=("phase_6", "phase_7"),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.REPLAY_CERTIFICATION,
            VerificationClass.OPERATIONAL_REHEARSAL,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="candidate_freeze_and_certification",
        title="Candidate freeze, replay, and certification",
        related_beads=(
            "backtesting_engine-ltc.7.1",
            "backtesting_engine-ltc.7.3",
            "backtesting_engine-ltc.7.6",
        ),
        phase_gates=("phase_6",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(
            VerificationClass.GOLDEN_PATH,
            VerificationClass.REPLAY_CERTIFICATION,
            VerificationClass.PARITY_CERTIFICATION,
        ),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="paper_runtime_and_operational_evidence",
        title="Paper runtime, operational evidence, and reconciliation",
        related_beads=(
            "backtesting_engine-ltc.7.7",
            "backtesting_engine-ltc.7.8",
            "backtesting_engine-ltc.7.10",
            "backtesting_engine-tox",
        ),
        phase_gates=("phase_7",),
        fixture_sources=(
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH, VerificationClass.REPLAY_CERTIFICATION),
    ),
    _gate_profile(
        surface_id="operator_observability_and_response_targets",
        title="Operator observability, alert classes, and response targets",
        related_beads=("backtesting_engine-ltc.8.4",),
        phase_gates=("phase_7", "phase_8"),
        fixture_sources=(
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
    _gate_profile(
        surface_id="live_readiness_and_resilience",
        title="Live-readiness, resilience, and emergency controls",
        related_beads=(
            "backtesting_engine-ltc.8.1",
            "backtesting_engine-ltc.8.3",
            "backtesting_engine-ltc.8.5",
            "backtesting_engine-w81",
        ),
        phase_gates=("phase_8",),
        fixture_sources=(
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.GOLDEN_SESSION,
            FixtureSource.SYNTHETIC_FAILURE_CASE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH, VerificationClass.REPLAY_CERTIFICATION),
    ),
    _gate_profile(
        surface_id="program_closure_and_continuation",
        title="Definition-of-done closure and continuation review",
        related_beads=(
            "backtesting_engine-ltc.10.1",
            "backtesting_engine-ltc.10.4",
        ),
        phase_gates=("phase_9",),
        fixture_sources=(
            FixtureSource.CERTIFIED_RELEASE,
            FixtureSource.BROKER_SESSION_RECORDING,
            FixtureSource.PLAN_SEEDED_FIXTURE,
        ),
        golden_path=(VerificationClass.GOLDEN_PATH, VerificationClass.OPERATIONAL_REHEARSAL),
        failure_path=(VerificationClass.FAILURE_PATH,),
    ),
)


PHASE_GATES: dict[str, str] = {
    "phase_0": "Foundation and QA",
    "phase_1": "Raw archive and bitemporal reference",
    "phase_2": "Validation and release pipeline",
    "phase_2_5": "Execution-lane vertical slice",
    "phase_3": "Simulation semantics and execution calibration",
    "phase_4": "Research governance and baselines",
    "phase_5": "First promotable strategy family",
    "phase_6": "Candidate freezing and certification",
    "phase_7": "Paper runtime and operational evidence",
    "phase_8": "Live-readiness and resilience",
    "phase_9": "Continuation review",
}


def profiles_by_phase() -> dict[str, tuple[VerificationProfile, ...]]:
    grouped: dict[str, list[VerificationProfile]] = {phase_id: [] for phase_id in PHASE_GATES}
    for profile in VERIFICATION_PROFILES:
        for phase_id in profile.phase_gates:
            grouped[phase_id].append(profile)
    return {phase_id: tuple(grouped[phase_id]) for phase_id in PHASE_GATES}


def validate_contract() -> list[str]:
    errors: list[str] = []
    grouped = profiles_by_phase()

    for phase_id, phase_name in PHASE_GATES.items():
        if not grouped[phase_id]:
            errors.append(f"{phase_id}: {phase_name} has no verification coverage")

    for profile in VERIFICATION_PROFILES:
        if not set(profile.local_checks).intersection(LOCAL_CHECKS):
            errors.append(f"{profile.surface_id}: missing local unit/contract/property coverage")
        if not profile.golden_path:
            errors.append(f"{profile.surface_id}: missing golden-path coverage")
        if not profile.failure_path:
            errors.append(f"{profile.surface_id}: missing failure-path coverage")
        missing_artifacts = set(GATE_DECISION_ARTIFACTS).difference(profile.retained_artifacts)
        if missing_artifacts:
            names = ", ".join(sorted(item.value for item in missing_artifacts))
            errors.append(f"{profile.surface_id}: missing retained artifacts: {names}")
        missing_explain = set(CORE_EXPLAINABILITY).difference(profile.explainability)
        if missing_explain:
            names = ", ".join(sorted(item.value for item in missing_explain))
            errors.append(f"{profile.surface_id}: missing explainability surfaces: {names}")
        if not profile.fixture_contract.provenance_required:
            errors.append(f"{profile.surface_id}: fixture provenance must be required")
        if not profile.fixture_contract.deterministic_seed_required:
            errors.append(f"{profile.surface_id}: deterministic seeds must be required")
        if not profile.fixture_contract.deterministic_clock_required:
            errors.append(f"{profile.surface_id}: deterministic clocks must be required")
        if not profile.fixture_contract.sources:
            errors.append(f"{profile.surface_id}: fixture sources must be declared")

    return errors


VALIDATION_ERRORS = validate_contract()
VALIDATION_ERRORS += validate_logging_contract()
