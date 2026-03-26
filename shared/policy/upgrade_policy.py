"""Upgrade and migration policy with startup compatibility checks."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique

from shared.policy.lifecycle_compatibility import (
    CompatibilityCheckRequest,
    CompatibilityDomain,
    CompatibilityVector,
    LifecycleMachine,
    LifecycleSpecStatus,
    evaluate_compatibility,
)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@unique
class StartupSurface(str, Enum):
    BINARY_VERSION = "binary_version"
    DATABASE_SCHEMA_VERSION = "database_schema_version"
    SNAPSHOT_JOURNAL_FORMAT = "snapshot_journal_format"
    POLICY_BUNDLE_HASH = "policy_bundle_hash"
    ARTIFACT_COMPATIBILITY_MATRIX = "artifact_compatibility_matrix"


REQUIRED_STARTUP_SURFACES = tuple(surface.value for surface in StartupSurface)

REPO_STRUCTURE_RULES = (
    ("python/research/", "python_research"),
    ("python/bindings/", "python_bindings"),
    ("rust/kernels/", "rust_kernels"),
    ("rust/opsd/", "rust_opsd"),
    ("rust/guardian/", "rust_guardian"),
    ("rust/watchdog/", "rust_watchdog"),
    ("shared/", "shared_contracts"),
    ("sql/", "sql_migrations"),
    ("infra/", "infra_support"),
    ("docs/", "documentation"),
    ("tests/", "tests"),
)

RETAINED_MIGRATION_ARTIFACTS = (
    "migration_manifest",
    "startup_compatibility_report",
    "rollback_or_restore_path",
    "operator_reason_bundle",
)


@dataclass(frozen=True)
class MigrationDeclaration:
    migration_id: str
    description: str
    affected_domains: tuple[str, ...]
    startup_surfaces: tuple[str, ...]
    replay_required: bool
    recertification_required: bool
    new_promotion_packet_required: bool
    forward_only: bool
    recoverability_evidence_id: str | None
    rollback_or_restore_path: str | None
    repo_paths: tuple[str, ...]
    incident_override: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StartupSnapshot:
    binary_version: str
    database_schema_version: str
    snapshot_journal_format: str
    policy_bundle_hash: str
    artifact_compatibility_matrix: str
    compatibility_vector: CompatibilityVector

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["compatibility_vector"] = self.compatibility_vector.to_dict()
        return payload


@dataclass(frozen=True)
class RepoPathAssessment:
    path: str
    plane: str | None
    aligned: bool
    explanation: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RepoStructureReport:
    aligned: bool
    invalid_paths: tuple[str, ...]
    assessments: tuple[RepoPathAssessment, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["assessments"] = [item.to_dict() for item in self.assessments]
        return payload


@dataclass(frozen=True)
class StartupCompatibilityRequest:
    case_id: str
    subject_id: str
    machine_id: str
    migration: MigrationDeclaration
    baseline: StartupSnapshot
    candidate: StartupSnapshot
    active_session: bool = False


@dataclass(frozen=True)
class StartupCompatibilityReport:
    case_id: str
    subject_id: str
    machine_id: str
    status: str
    reason_code: str
    changed_startup_surfaces: tuple[str, ...]
    blocking_startup_surfaces: tuple[str, ...]
    replay_required: bool
    recertification_required: bool
    new_promotion_packet_required: bool
    retained_artifacts: tuple[str, ...]
    repo_structure_report: RepoStructureReport
    compatibility_report: dict[str, object]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["repo_structure_report"] = self.repo_structure_report.to_dict()
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def classify_repo_path(path: str) -> RepoPathAssessment:
    for prefix, plane in REPO_STRUCTURE_RULES:
        if path.startswith(prefix):
            return RepoPathAssessment(
                path=path,
                plane=plane,
                aligned=True,
                explanation=f"{path} stays inside the declared {plane} plane boundary.",
            )
    return RepoPathAssessment(
        path=path,
        plane=None,
        aligned=False,
        explanation=(
            f"{path} does not live under one of the declared plane roots and risks "
            "mixing research, runtime, kernel, or shared-contract concerns."
        ),
    )


def evaluate_repo_structure(paths: tuple[str, ...]) -> RepoStructureReport:
    assessments = tuple(classify_repo_path(path) for path in paths)
    invalid_paths = tuple(item.path for item in assessments if not item.aligned)
    return RepoStructureReport(
        aligned=not invalid_paths,
        invalid_paths=invalid_paths,
        assessments=assessments,
    )


def _normalize_machine_id(machine_id: str) -> str:
    try:
        return LifecycleMachine(machine_id).value
    except ValueError:
        return machine_id


def _normalize_domains(domains: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for domain in domains:
        value = CompatibilityDomain(domain).value
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _normalize_startup_surfaces(startup_surfaces: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for surface in startup_surfaces:
        value = StartupSurface(surface).value
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _changed_startup_surfaces(
    baseline: StartupSnapshot, candidate: StartupSnapshot
) -> tuple[str, ...]:
    changed: list[str] = []
    for surface in StartupSurface:
        if getattr(baseline, surface.value) != getattr(candidate, surface.value):
            changed.append(surface.value)
    return tuple(changed)


def evaluate_startup_compatibility(
    request: StartupCompatibilityRequest,
) -> StartupCompatibilityReport:
    machine_id = _normalize_machine_id(request.machine_id)
    migration = request.migration
    try:
        affected_domains = _normalize_domains(migration.affected_domains)
        declared_surfaces = _normalize_startup_surfaces(migration.startup_surfaces)
    except ValueError as exc:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code="UNKNOWN_MIGRATION_DECLARATION_VALUE",
            changed_startup_surfaces=(),
            blocking_startup_surfaces=(),
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=evaluate_repo_structure(migration.repo_paths),
            compatibility_report={},
            explanation=(
                "Migration declarations must use canonical compatibility-domain and "
                "startup-surface names."
            ),
            remediation=str(exc),
        )

    repo_structure = evaluate_repo_structure(migration.repo_paths)
    changed_surfaces = _changed_startup_surfaces(request.baseline, request.candidate)
    compatibility_report = evaluate_compatibility(
        CompatibilityCheckRequest(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            baseline=request.baseline.compatibility_vector,
            candidate=request.candidate.compatibility_vector,
            declared_affected_domains=affected_domains,
            active_session=request.active_session and not migration.incident_override,
        )
    )
    compatibility_payload = compatibility_report.to_dict()

    if not set(changed_surfaces).issubset(declared_surfaces):
        undeclared_surfaces = tuple(
            surface for surface in changed_surfaces if surface not in declared_surfaces
        )
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="UNDECLARED_STARTUP_SURFACE_CHANGE",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=undeclared_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "Startup surface drift was detected without declaring the changed "
                "surfaces in the migration manifest."
            ),
            remediation="List every changed startup surface in the migration declaration.",
        )

    if request.active_session and changed_surfaces and not migration.incident_override:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="ACTIVE_SESSION_UPGRADE_BLOCKED",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "Live-capable upgrades may not be applied during an active session "
                "outside incident procedure."
            ),
            remediation="Wait for session end or declare an incident override explicitly.",
        )

    if migration.forward_only and not migration.recoverability_evidence_id:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="FORWARD_ONLY_MISSING_RECOVERABILITY_EVIDENCE",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "Forward-only migrations require backup/restore evidence before they "
                "can be treated as safe."
            ),
            remediation="Attach a recoverability evidence identifier from a restore rehearsal.",
        )

    if not migration.rollback_or_restore_path:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="ROLLBACK_OR_RESTORE_PATH_REQUIRED",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "Every live-capable upgrade must name a rollback or restore path that "
                "operators can follow."
            ),
            remediation="Record a rollback or restore path in the migration manifest.",
        )

    if not repo_structure.aligned:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="REPO_STRUCTURE_BOUNDARY_VIOLATION",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "The migration touches paths outside the declared plane boundaries for "
                "research, kernels, runtime, shared contracts, docs, or tests."
            ),
            remediation="Move the files under the declared plane roots before proceeding.",
        )

    if compatibility_report.status == LifecycleSpecStatus.INVALID.value:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.INVALID.value,
            reason_code=compatibility_report.reason_code,
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=compatibility_report.explanation,
            remediation=compatibility_report.remediation,
        )

    if compatibility_report.status == LifecycleSpecStatus.VIOLATION.value:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code=compatibility_report.reason_code,
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=compatibility_report.explanation,
            remediation=compatibility_report.remediation,
        )

    replay_domains = {
        CompatibilityDomain.DATA_PROTOCOL.value,
        CompatibilityDomain.STRATEGY_PROTOCOL.value,
        CompatibilityDomain.OPS_PROTOCOL.value,
    }
    recertification_needed = bool(compatibility_report.recertification_domains)
    replay_needed = bool(
        replay_domains.intersection(compatibility_report.recertification_domains)
    )

    if recertification_needed and not migration.recertification_required:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="RECERTIFICATION_CONSEQUENCE_MISSING",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "The migration changed a compatibility domain that requires "
                "recertification, but the migration manifest did not declare it."
            ),
            remediation="Mark recertification as required in the migration declaration.",
        )

    if replay_needed and not migration.replay_required:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.VIOLATION.value,
            reason_code="REPLAY_CONSEQUENCE_MISSING",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS,
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "The migration changed data, strategy, or ops semantics without "
                "declaring deterministic replay consequences."
            ),
            remediation="Mark replay as required in the migration declaration.",
        )

    if compatibility_report.status == LifecycleSpecStatus.INCOMPATIBLE.value:
        return StartupCompatibilityReport(
            case_id=request.case_id,
            subject_id=request.subject_id,
            machine_id=machine_id,
            status=LifecycleSpecStatus.INCOMPATIBLE.value,
            reason_code="STARTUP_COMPATIBILITY_REQUIRES_RECERTIFICATION",
            changed_startup_surfaces=changed_surfaces,
            blocking_startup_surfaces=changed_surfaces,
            replay_required=migration.replay_required,
            recertification_required=migration.recertification_required,
            new_promotion_packet_required=migration.new_promotion_packet_required,
            retained_artifacts=RETAINED_MIGRATION_ARTIFACTS
            + (("recoverability_evidence",) if migration.recoverability_evidence_id else ()),
            repo_structure_report=repo_structure,
            compatibility_report=compatibility_payload,
            explanation=(
                "The startup surfaces are governed, but compatibility drift still "
                "creates a new certification boundary before activation."
            ),
            remediation=(
                "Run the required replay/recertification workflow and bind the new "
                "startup versions to a fresh promotion path."
            ),
        )

    return StartupCompatibilityReport(
        case_id=request.case_id,
        subject_id=request.subject_id,
        machine_id=machine_id,
        status=LifecycleSpecStatus.PASS.value,
        reason_code="STARTUP_COMPATIBILITY_CONFIRMED",
        changed_startup_surfaces=changed_surfaces,
        blocking_startup_surfaces=(),
        replay_required=migration.replay_required,
        recertification_required=migration.recertification_required,
        new_promotion_packet_required=migration.new_promotion_packet_required,
        retained_artifacts=RETAINED_MIGRATION_ARTIFACTS
        + (("recoverability_evidence",) if migration.recoverability_evidence_id else ()),
        repo_structure_report=repo_structure,
        compatibility_report=compatibility_payload,
        explanation=(
            "The migration declaration matches the startup surface drift, plane "
            "boundaries stay intact, and all compatibility domains remain compatible."
        ),
        remediation="Startup may proceed with the recorded migration artifacts.",
    )


def validate_contract() -> list[str]:
    errors: list[str] = []

    if REQUIRED_STARTUP_SURFACES != tuple(surface.value for surface in StartupSurface):
        errors.append("startup surfaces must cover the canonical startup contract")

    if not RETAINED_MIGRATION_ARTIFACTS:
        errors.append("migration policy must declare retained artifacts")

    for prefix, plane in REPO_STRUCTURE_RULES:
        if not prefix.endswith("/"):
            errors.append(f"repo structure prefix {prefix!r} for {plane} must end with /")

    return errors


VALIDATION_ERRORS = validate_contract()
