"""Phase-0 foundation and QA harness contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


@unique
class FoundationFailureClass(str, Enum):
    SETUP_ERROR = "setup_error"
    SCHEMA_ERROR = "schema_error"
    COMPATIBILITY_ERROR = "compatibility_error"
    INVARIANT_FAILURE = "invariant_failure"


@unique
class FoundationHarnessStatus(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"
    INVALID = "invalid"


@dataclass(frozen=True)
class FoundationCheckResult:
    check_id: str
    check_name: str
    passed: bool
    status: str
    reason_code: str
    failure_class: str | None
    diagnostic: str
    evidence: dict[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FoundationCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            check_name=str(payload["check_name"]),
            passed=bool(payload["passed"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            failure_class=(
                str(payload["failure_class"])
                if payload.get("failure_class") is not None
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            evidence=dict(payload["evidence"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class SchemaLoadSurface:
    surface_id: str
    loaded: bool
    schema_version: str
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SchemaLoadSurface":
        return cls(
            surface_id=str(payload["surface_id"]),
            loaded=bool(payload["loaded"]),
            schema_version=str(payload["schema_version"]),
            error_detail=(
                str(payload["error_detail"])
                if payload.get("error_detail") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class StartupCompatibilityEvidence:
    compatible: bool
    binary_version: str
    database_schema_version: str
    snapshot_journal_format: str
    policy_bundle_hash: str
    compatibility_matrix_version: str
    mismatch_details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mismatch_details"] = list(self.mismatch_details)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StartupCompatibilityEvidence":
        return cls(
            compatible=bool(payload["compatible"]),
            binary_version=str(payload["binary_version"]),
            database_schema_version=str(payload["database_schema_version"]),
            snapshot_journal_format=str(payload["snapshot_journal_format"]),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            compatibility_matrix_version=str(payload["compatibility_matrix_version"]),
            mismatch_details=tuple(
                str(item) for item in payload.get("mismatch_details", ())
            ),
        )


@dataclass(frozen=True)
class ProbeEvidence:
    status: str
    evidence_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProbeEvidence":
        return cls(
            status=str(payload["status"]),
            evidence_id=str(payload["evidence_id"]),
            detail=str(payload["detail"]),
        )


@dataclass(frozen=True)
class PropertyHarnessEvidence:
    passed: bool
    seed: int
    case_count: int
    failure_example_id: str | None = None
    report_artifact_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PropertyHarnessEvidence":
        return cls(
            passed=bool(payload["passed"]),
            seed=int(payload["seed"]),
            case_count=int(payload["case_count"]),
            failure_example_id=(
                str(payload["failure_example_id"])
                if payload.get("failure_example_id") is not None
                else None
            ),
            report_artifact_id=str(payload["report_artifact_id"]),
        )


@dataclass(frozen=True)
class RoundTripSmokeEvidence:
    boot_succeeded: bool
    round_trip_completed: bool
    smoke_log_artifact_id: str
    smoke_trace_id: str
    expected_vs_actual_diff_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoundTripSmokeEvidence":
        return cls(
            boot_succeeded=bool(payload["boot_succeeded"]),
            round_trip_completed=bool(payload["round_trip_completed"]),
            smoke_log_artifact_id=str(payload["smoke_log_artifact_id"]),
            smoke_trace_id=str(payload["smoke_trace_id"]),
            expected_vs_actual_diff_id=(
                str(payload["expected_vs_actual_diff_id"])
                if payload.get("expected_vs_actual_diff_id") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class FoundationHarnessRequest:
    case_id: str
    environment_lock_id: str
    deterministic_clock_utc: str
    artifact_manifest_id: str
    correlation_id: str
    operator_reason_bundle: tuple[str, ...]
    schema_surfaces: tuple[SchemaLoadSurface, ...]
    startup_compatibility: StartupCompatibilityEvidence
    clock_probe: ProbeEvidence
    secret_probe: ProbeEvidence
    journal_digest_probe: ProbeEvidence
    property_harness: PropertyHarnessEvidence
    round_trip_smoke: RoundTripSmokeEvidence

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operator_reason_bundle"] = list(self.operator_reason_bundle)
        payload["schema_surfaces"] = [item.to_dict() for item in self.schema_surfaces]
        payload["startup_compatibility"] = self.startup_compatibility.to_dict()
        payload["clock_probe"] = self.clock_probe.to_dict()
        payload["secret_probe"] = self.secret_probe.to_dict()
        payload["journal_digest_probe"] = self.journal_digest_probe.to_dict()
        payload["property_harness"] = self.property_harness.to_dict()
        payload["round_trip_smoke"] = self.round_trip_smoke.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FoundationHarnessRequest":
        return cls(
            case_id=str(payload["case_id"]),
            environment_lock_id=str(payload["environment_lock_id"]),
            deterministic_clock_utc=str(payload["deterministic_clock_utc"]),
            artifact_manifest_id=str(payload["artifact_manifest_id"]),
            correlation_id=str(payload["correlation_id"]),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            schema_surfaces=tuple(
                SchemaLoadSurface.from_dict(item)
                for item in payload["schema_surfaces"]
            ),
            startup_compatibility=StartupCompatibilityEvidence.from_dict(
                dict(payload["startup_compatibility"])
            ),
            clock_probe=ProbeEvidence.from_dict(dict(payload["clock_probe"])),
            secret_probe=ProbeEvidence.from_dict(dict(payload["secret_probe"])),
            journal_digest_probe=ProbeEvidence.from_dict(
                dict(payload["journal_digest_probe"])
            ),
            property_harness=PropertyHarnessEvidence.from_dict(
                dict(payload["property_harness"])
            ),
            round_trip_smoke=RoundTripSmokeEvidence.from_dict(
                dict(payload["round_trip_smoke"])
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "FoundationHarnessRequest":
        return cls.from_dict(_decode_json_object(payload, label="foundation_harness_request"))


@dataclass(frozen=True)
class FoundationHarnessReport:
    case_id: str
    phase_gate: str
    status: str
    reason_code: str
    passed_count: int
    failed_count: int
    failure_classes: tuple[str, ...]
    check_results: tuple[FoundationCheckResult, ...]
    correlation_id: str
    retained_artifact_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_results"] = [item.to_dict() for item in self.check_results]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FoundationHarnessReport":
        return cls(
            case_id=str(payload["case_id"]),
            phase_gate=str(payload["phase_gate"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            passed_count=int(payload["passed_count"]),
            failed_count=int(payload["failed_count"]),
            failure_classes=tuple(str(item) for item in payload["failure_classes"]),
            check_results=tuple(
                FoundationCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            correlation_id=str(payload["correlation_id"]),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utc_now())),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "FoundationHarnessReport":
        return cls.from_dict(_decode_json_object(payload, label="foundation_harness_report"))


VALIDATION_ERRORS: list[str] = []


def _make_check(
    *,
    check_id: str,
    check_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    failure_class: FoundationFailureClass | None,
    evidence: dict[str, Any],
    remediation: str,
) -> FoundationCheckResult:
    return FoundationCheckResult(
        check_id=check_id,
        check_name=check_name,
        passed=passed,
        status=(
            FoundationHarnessStatus.PASS.value
            if passed
            else FoundationHarnessStatus.VIOLATION.value
        ),
        reason_code=reason_code,
        failure_class=failure_class.value if failure_class is not None else None,
        diagnostic=diagnostic,
        evidence=evidence,
        remediation=remediation,
    )


def _environment_lock_check(request: FoundationHarnessRequest) -> FoundationCheckResult:
    passed = bool(request.environment_lock_id and request.deterministic_clock_utc)
    return _make_check(
        check_id="FH01",
        check_name="environment_lock_and_deterministic_clock",
        passed=passed,
        reason_code=(
            "FOUNDATION_ENVIRONMENT_LOCK_READY"
            if passed
            else "FOUNDATION_ENVIRONMENT_LOCK_MISSING"
        ),
        diagnostic=(
            "Environment lock and deterministic clock are retained for reproducible foundation runs."
            if passed
            else "Foundation harness requires both an environment lock id and deterministic clock."
        ),
        failure_class=None if passed else FoundationFailureClass.SETUP_ERROR,
        evidence={
            "environment_lock_id": request.environment_lock_id,
            "deterministic_clock_utc": request.deterministic_clock_utc,
        },
        remediation="Record the environment lock and deterministic clock before running the harness.",
    )


def _schema_scaffold_check(request: FoundationHarnessRequest) -> FoundationCheckResult:
    failing_surfaces = tuple(
        surface.surface_id
        for surface in request.schema_surfaces
        if not surface.loaded
    )
    passed = bool(request.schema_surfaces) and not failing_surfaces
    return _make_check(
        check_id="FH02",
        check_name="schema_scaffold_loading",
        passed=passed,
        reason_code=(
            "FOUNDATION_SCHEMA_SCAFFOLD_READY"
            if passed
            else "FOUNDATION_SCHEMA_SCAFFOLD_FAILED"
        ),
        diagnostic=(
            "Schema scaffold surfaces loaded successfully."
            if passed
            else f"Schema scaffold failed to load: {failing_surfaces}."
        ),
        failure_class=None if passed else FoundationFailureClass.SCHEMA_ERROR,
        evidence={
            "schema_surfaces": [surface.to_dict() for surface in request.schema_surfaces],
            "failing_surfaces": list(failing_surfaces),
        },
        remediation="Repair schema loading failures and keep the scaffold reproducible.",
    )


def _compatibility_check(request: FoundationHarnessRequest) -> FoundationCheckResult:
    evidence = request.startup_compatibility
    passed = evidence.compatible
    return _make_check(
        check_id="FH03",
        check_name="startup_compatibility",
        passed=passed,
        reason_code=(
            "FOUNDATION_STARTUP_COMPATIBILITY_READY"
            if passed
            else "FOUNDATION_STARTUP_COMPATIBILITY_BLOCKED"
        ),
        diagnostic=(
            "Startup compatibility checks are satisfied across binary, schema, journal, and policy surfaces."
            if passed
            else (
                "Startup compatibility checks failed: "
                + ", ".join(evidence.mismatch_details)
            )
        ),
        failure_class=None if passed else FoundationFailureClass.COMPATIBILITY_ERROR,
        evidence=evidence.to_dict(),
        remediation="Resolve compatibility mismatches before treating Phase 0 as bootable.",
    )


def _probe_check(
    *,
    check_id: str,
    check_name: str,
    reason_prefix: str,
    probe: ProbeEvidence,
    failure_class: FoundationFailureClass,
    remediation: str,
) -> FoundationCheckResult:
    passed = probe.status == "healthy"
    return _make_check(
        check_id=check_id,
        check_name=check_name,
        passed=passed,
        reason_code=(
            f"{reason_prefix}_READY" if passed else f"{reason_prefix}_FAILED"
        ),
        diagnostic=(
            f"{check_name.replace('_', ' ')} probe is healthy."
            if passed
            else probe.detail
        ),
        failure_class=None if passed else failure_class,
        evidence=probe.to_dict(),
        remediation=remediation,
    )


def _property_harness_check(request: FoundationHarnessRequest) -> FoundationCheckResult:
    evidence = request.property_harness
    passed = evidence.passed and evidence.case_count > 0 and evidence.report_artifact_id != ""
    return _make_check(
        check_id="FH07",
        check_name="property_invariant_harness",
        passed=passed,
        reason_code=(
            "FOUNDATION_PROPERTY_HARNESS_READY"
            if passed
            else "FOUNDATION_PROPERTY_HARNESS_FAILED"
        ),
        diagnostic=(
            "Property-based invariant harness ran with deterministic seed coverage."
            if passed
            else "Property harness must pass with at least one deterministic case and a retained report."
        ),
        failure_class=None if passed else FoundationFailureClass.INVARIANT_FAILURE,
        evidence=evidence.to_dict(),
        remediation="Run the property harness with a retained seed, case count, and artifact id.",
    )


def _round_trip_check(request: FoundationHarnessRequest) -> FoundationCheckResult:
    evidence = request.round_trip_smoke
    passed = (
        evidence.boot_succeeded
        and evidence.round_trip_completed
        and evidence.smoke_log_artifact_id != ""
        and evidence.smoke_trace_id != ""
    )
    return _make_check(
        check_id="FH08",
        check_name="end_to_end_round_trip_smoke",
        passed=passed,
        reason_code=(
            "FOUNDATION_ROUND_TRIP_SMOKE_READY"
            if passed
            else "FOUNDATION_ROUND_TRIP_SMOKE_FAILED"
        ),
        diagnostic=(
            "Local stack booted and completed the round-trip smoke path."
            if passed
            else "Local stack must boot and complete the round-trip smoke path with retained logs."
        ),
        failure_class=None if passed else FoundationFailureClass.SETUP_ERROR,
        evidence=evidence.to_dict(),
        remediation="Repair bootstrap or smoke-path failures and retain the resulting smoke trace.",
    )


def evaluate_foundation_harness(
    request: FoundationHarnessRequest,
) -> FoundationHarnessReport:
    checks = (
        _environment_lock_check(request),
        _schema_scaffold_check(request),
        _compatibility_check(request),
        _probe_check(
            check_id="FH04",
            check_name="clock_health_probe",
            reason_prefix="FOUNDATION_CLOCK_PROBE",
            probe=request.clock_probe,
            failure_class=FoundationFailureClass.SETUP_ERROR,
            remediation="Repair clock health and retain the probe evidence.",
        ),
        _probe_check(
            check_id="FH05",
            check_name="secret_health_probe",
            reason_prefix="FOUNDATION_SECRET_PROBE",
            probe=request.secret_probe,
            failure_class=FoundationFailureClass.SETUP_ERROR,
            remediation="Repair secret delivery or baseline checks before Phase 0 signoff.",
        ),
        _probe_check(
            check_id="FH06",
            check_name="journal_digest_probe",
            reason_prefix="FOUNDATION_JOURNAL_DIGEST",
            probe=request.journal_digest_probe,
            failure_class=FoundationFailureClass.INVARIANT_FAILURE,
            remediation="Repair journal-digest verification and keep the digest evidence retained.",
        ),
        _property_harness_check(request),
        _round_trip_check(request),
    )
    failing_checks = tuple(check for check in checks if not check.passed)
    passed_count = sum(1 for check in checks if check.passed)
    failed_count = len(checks) - passed_count
    failure_classes = tuple(
        sorted(
            {
                check.failure_class
                for check in failing_checks
                if check.failure_class is not None
            }
        )
    )
    retained_artifact_ids = tuple(
        filter(
            None,
            (
                request.artifact_manifest_id,
                request.clock_probe.evidence_id,
                request.secret_probe.evidence_id,
                request.journal_digest_probe.evidence_id,
                request.property_harness.report_artifact_id,
                request.round_trip_smoke.smoke_log_artifact_id,
                request.round_trip_smoke.smoke_trace_id,
                request.round_trip_smoke.expected_vs_actual_diff_id,
            ),
        )
    )

    if not request.operator_reason_bundle or not request.correlation_id:
        status = FoundationHarnessStatus.INVALID.value
        reason_code = "FOUNDATION_ARTIFACT_CONTEXT_MISSING"
        explanation = "Foundation harness requires a correlation id and operator reason bundle."
        remediation = "Populate retained artifact context before evaluating the harness."
    elif failing_checks:
        status = FoundationHarnessStatus.VIOLATION.value
        reason_code = failing_checks[0].reason_code
        explanation = failing_checks[0].diagnostic
        remediation = failing_checks[0].remediation
    else:
        status = FoundationHarnessStatus.PASS.value
        reason_code = "FOUNDATION_PHASE0_READY"
        explanation = (
            "Phase 0 foundation checks passed with reproducible locks, compatibility evidence, "
            "health probes, property coverage, and round-trip smoke artifacts."
        )
        remediation = "No remediation required."

    return FoundationHarnessReport(
        case_id=request.case_id,
        phase_gate="phase_0",
        status=status,
        reason_code=reason_code,
        passed_count=passed_count,
        failed_count=failed_count,
        failure_classes=failure_classes,
        check_results=checks,
        correlation_id=request.correlation_id,
        retained_artifact_ids=retained_artifact_ids,
        operator_reason_bundle=request.operator_reason_bundle,
        explanation=explanation,
        remediation=remediation,
    )
