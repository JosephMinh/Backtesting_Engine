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


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_present(
    payload: dict[str, Any],
    key: str,
    *,
    field_name: str,
) -> object:
    if key not in payload:
        raise ValueError(f"{field_name} missing required field")
    return payload[key]


def _require_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of non-empty strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _require_mapping_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of objects")
    return tuple(
        _require_mapping(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _normalize_utc_timestamp(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a timezone-aware ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(datetime.timezone.utc).isoformat()


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


def _require_harness_status(value: object, *, field_name: str) -> str:
    normalized = _require_non_empty_string(value, field_name=field_name)
    try:
        return FoundationHarnessStatus(normalized).value
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid foundation harness status") from exc


def _optional_failure_class(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    normalized = _require_non_empty_string(value, field_name=field_name)
    try:
        return FoundationFailureClass(normalized).value
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid foundation failure class") from exc


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
        payload = _require_mapping(payload, field_name="foundation_check_result")
        return cls(
            check_id=_require_non_empty_string(payload["check_id"], field_name="check_id"),
            check_name=_require_non_empty_string(
                payload["check_name"],
                field_name="check_name",
            ),
            passed=_require_bool(payload["passed"], field_name="passed"),
            status=_require_harness_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            failure_class=_optional_failure_class(
                _require_present(payload, "failure_class", field_name="failure_class"),
                field_name="failure_class",
            ),
            diagnostic=_require_non_empty_string(
                payload["diagnostic"],
                field_name="diagnostic",
            ),
            evidence=_require_mapping(payload["evidence"], field_name="evidence"),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
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
        payload = _require_mapping(payload, field_name="schema_load_surface")
        return cls(
            surface_id=_require_non_empty_string(payload["surface_id"], field_name="surface_id"),
            loaded=_require_bool(payload["loaded"], field_name="loaded"),
            schema_version=_require_non_empty_string(
                payload["schema_version"],
                field_name="schema_version",
            ),
            error_detail=_optional_non_empty_string(
                _require_present(payload, "error_detail", field_name="error_detail"),
                field_name="error_detail",
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
        payload = _require_mapping(payload, field_name="startup_compatibility")
        return cls(
            compatible=_require_bool(payload["compatible"], field_name="compatible"),
            binary_version=_require_non_empty_string(
                payload["binary_version"],
                field_name="binary_version",
            ),
            database_schema_version=_require_non_empty_string(
                payload["database_schema_version"],
                field_name="database_schema_version",
            ),
            snapshot_journal_format=_require_non_empty_string(
                payload["snapshot_journal_format"],
                field_name="snapshot_journal_format",
            ),
            policy_bundle_hash=_require_non_empty_string(
                payload["policy_bundle_hash"],
                field_name="policy_bundle_hash",
            ),
            compatibility_matrix_version=_require_non_empty_string(
                payload["compatibility_matrix_version"],
                field_name="compatibility_matrix_version",
            ),
            mismatch_details=_require_string_sequence(
                _require_present(payload, "mismatch_details", field_name="mismatch_details"),
                field_name="mismatch_details",
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
        payload = _require_mapping(payload, field_name="probe_evidence")
        return cls(
            status=_require_non_empty_string(payload["status"], field_name="status"),
            evidence_id=_require_non_empty_string(
                payload["evidence_id"],
                field_name="evidence_id",
            ),
            detail=_require_non_empty_string(payload["detail"], field_name="detail"),
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
        payload = _require_mapping(payload, field_name="property_harness")
        return cls(
            passed=_require_bool(payload["passed"], field_name="passed"),
            seed=_require_int(payload["seed"], field_name="seed"),
            case_count=_require_int(payload["case_count"], field_name="case_count"),
            failure_example_id=_optional_non_empty_string(
                _require_present(
                    payload,
                    "failure_example_id",
                    field_name="failure_example_id",
                ),
                field_name="failure_example_id",
            ),
            report_artifact_id=_require_non_empty_string(
                payload["report_artifact_id"],
                field_name="report_artifact_id",
            ),
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
        payload = _require_mapping(payload, field_name="round_trip_smoke")
        return cls(
            boot_succeeded=_require_bool(
                payload["boot_succeeded"],
                field_name="boot_succeeded",
            ),
            round_trip_completed=_require_bool(
                payload["round_trip_completed"],
                field_name="round_trip_completed",
            ),
            smoke_log_artifact_id=_require_non_empty_string(
                payload["smoke_log_artifact_id"],
                field_name="smoke_log_artifact_id",
            ),
            smoke_trace_id=_require_non_empty_string(
                payload["smoke_trace_id"],
                field_name="smoke_trace_id",
            ),
            expected_vs_actual_diff_id=_optional_non_empty_string(
                _require_present(
                    payload,
                    "expected_vs_actual_diff_id",
                    field_name="expected_vs_actual_diff_id",
                ),
                field_name="expected_vs_actual_diff_id",
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
        payload = _require_mapping(payload, field_name="foundation_harness_request")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            environment_lock_id=_require_non_empty_string(
                payload["environment_lock_id"],
                field_name="environment_lock_id",
            ),
            deterministic_clock_utc=_normalize_utc_timestamp(
                payload["deterministic_clock_utc"],
                field_name="deterministic_clock_utc",
            ),
            artifact_manifest_id=_require_non_empty_string(
                payload["artifact_manifest_id"],
                field_name="artifact_manifest_id",
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            schema_surfaces=tuple(
                SchemaLoadSurface.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["schema_surfaces"],
                    field_name="schema_surfaces",
                )
            ),
            startup_compatibility=StartupCompatibilityEvidence.from_dict(
                _require_mapping(
                    payload["startup_compatibility"],
                    field_name="startup_compatibility",
                )
            ),
            clock_probe=ProbeEvidence.from_dict(
                _require_mapping(payload["clock_probe"], field_name="clock_probe")
            ),
            secret_probe=ProbeEvidence.from_dict(
                _require_mapping(payload["secret_probe"], field_name="secret_probe")
            ),
            journal_digest_probe=ProbeEvidence.from_dict(
                _require_mapping(
                    payload["journal_digest_probe"],
                    field_name="journal_digest_probe",
                )
            ),
            property_harness=PropertyHarnessEvidence.from_dict(
                _require_mapping(
                    payload["property_harness"],
                    field_name="property_harness",
                )
            ),
            round_trip_smoke=RoundTripSmokeEvidence.from_dict(
                _require_mapping(
                    payload["round_trip_smoke"],
                    field_name="round_trip_smoke",
                )
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
        payload = _require_mapping(payload, field_name="foundation_harness_report")
        return cls(
            case_id=_require_non_empty_string(payload["case_id"], field_name="case_id"),
            phase_gate=_require_non_empty_string(payload["phase_gate"], field_name="phase_gate"),
            status=_require_harness_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(
                payload["reason_code"],
                field_name="reason_code",
            ),
            passed_count=_require_int(payload["passed_count"], field_name="passed_count"),
            failed_count=_require_int(payload["failed_count"], field_name="failed_count"),
            failure_classes=tuple(
                FoundationFailureClass(
                    _require_non_empty_string(item, field_name=f"failure_classes[{index}]")
                ).value
                for index, item in enumerate(
                    _require_string_sequence(
                        payload["failure_classes"],
                        field_name="failure_classes",
                    )
                )
            ),
            check_results=tuple(
                FoundationCheckResult.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["check_results"],
                    field_name="check_results",
                )
            ),
            correlation_id=_require_non_empty_string(
                payload["correlation_id"],
                field_name="correlation_id",
            ),
            retained_artifact_ids=_require_string_sequence(
                payload["retained_artifact_ids"],
                field_name="retained_artifact_ids",
            ),
            operator_reason_bundle=_require_string_sequence(
                payload["operator_reason_bundle"],
                field_name="operator_reason_bundle",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                payload["remediation"],
                field_name="remediation",
            ),
            timestamp=_normalize_utc_timestamp(
                _require_present(payload, "timestamp", field_name="timestamp"),
                field_name="timestamp",
            ),
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
