from __future__ import annotations

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
        surface_id="execution_lane_vertical_slice",
        title="Execution-lane viability and vertical slice",
        related_beads=(
            "backtesting_engine-ltc.1.5",
            "backtesting_engine-ltc.4.3",
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
        surface_id="simulation_and_execution_profiles",
        title="Simulation semantics and execution calibration",
        related_beads=(
            "backtesting_engine-ltc.4.1",
            "backtesting_engine-ltc.4.5",
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
        surface_id="research_governance_and_selection",
        title="Research governance, budgets, and selection gates",
        related_beads=(
            "backtesting_engine-ltc.6.1",
            "backtesting_engine-ltc.6.2",
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
