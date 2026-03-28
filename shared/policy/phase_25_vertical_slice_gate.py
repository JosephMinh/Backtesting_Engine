"""Phase 2.5 execution-lane vertical-slice gate contract."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

SUPPORTED_PHASE_25_VERTICAL_SLICE_SCHEMA_VERSION = 1
PHASE_25_CHECK_IDS = ("P2501", "P2502", "P2503", "P2504", "P2505")
REQUIRED_PHASE_25_SURFACES = (
    "live_data_entitlement_checks",
    "approved_ibkr_bar_construction_pipeline",
    "dummy_strategy_routing_through_opsd",
    "paper_route_smoke_workflow",
    "shadow_live_suppression_path",
    "statement_ingestion_skeleton",
    "reconciliation_skeleton",
    "contract_conformance_checks",
    "preliminary_1oz_tradability_diagnostics",
)
REQUIRED_VERTICAL_SLICE_SUMMARY_KEYS = (
    "script_reference",
    "manifest_path",
    "artifact_root",
    "run_id",
    "correlation_id",
    "decision_trace_id",
    "decision",
    "reason_code",
    "kernel",
    "runtime",
    "schedule",
    "live_bar",
    "readiness",
    "recovery_smoke",
    "recovery_runtime",
    "route_mode",
    "reconciliation",
    "evidence_archive",
    "retained_logs",
    "retained_artifact_ids",
)
REQUIRED_VERTICAL_SLICE_LOG_STEPS = (
    "kernel",
    "runtime",
    "schedule",
    "live_bar",
    "readiness",
    "recovery_smoke",
    "recovery_runtime",
    "route_mode",
    "reconciliation",
    "evidence_archive",
)
REQUIRED_RUNTIME_STARTUP_SCENARIOS = (
    "startup-handoff",
    "mailbox-backpressure",
    "broker-mutation-control",
)
REQUIRED_ROUTE_MODE_OUTCOMES = {
    "paper-route-reroutes-submit": (
        "routed_to_paper",
        "PAPER_ROUTE_EXECUTION_REHEARSAL",
    ),
    "shadow-live-suppresses-submit": (
        "suppressed",
        "SHADOW_LIVE_SUPPRESSION_REQUIRED",
    ),
}
REQUIRED_SEALED_EVIDENCE_IDS = (
    "paper_bundle_001",
    "shadow_bundle_001",
    "recovery_bundle_001",
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_present(payload: dict[str, Any], *, field_name: str) -> object:
    if field_name not in payload:
        raise ValueError(f"{field_name} field is required")
    return payload[field_name]


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of objects")
    return tuple(_require_mapping(item, field_name=f"{field_name}[]") for item in value)


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}: must be a non-empty string")
    return value


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[]") for item in value
    )


def _require_boolean(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be a boolean")
    return value


def _require_integer(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}: must be an integer")
    return value


def _require_timestamp(value: object, *, field_name: str) -> str:
    try:
        normalized = datetime.datetime.fromisoformat(
            _require_non_empty_string(value, field_name=field_name).replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be timezone-aware and ISO-8601 compatible") from exc
    if normalized.tzinfo is None:
        raise ValueError(f"{field_name}: must be timezone-aware and ISO-8601 compatible")
    return normalized.astimezone(datetime.timezone.utc).isoformat()


def _require_status(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid phase 2.5 status")
    try:
        return Phase25VerticalSliceStatus(value).value
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid phase 2.5 status") from exc


def _require_supported_schema_version(value: object, *, field_name: str) -> int:
    version = _require_integer(value, field_name=field_name)
    if version != SUPPORTED_PHASE_25_VERTICAL_SLICE_SCHEMA_VERSION:
        raise ValueError(f"{field_name}: unsupported schema_version")
    return version


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _unique_strings(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _as_string_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value) for value in values if str(value))


@unique
class Phase25VerticalSliceStatus(str, Enum):
    PASS = "pass"  # nosec B105 - verification status literal, not a credential
    PIVOT = "pivot"
    INVALID = "invalid"


@dataclass(frozen=True)
class Phase25CheckResult:
    check_id: str
    check_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25CheckResult":
        payload = _require_mapping(payload, field_name="phase_25_check_result")
        return cls(
            check_id=_require_non_empty_string(
                _require_present(payload, field_name="check_id"),
                field_name="check_id",
            ),
            check_name=_require_non_empty_string(
                _require_present(payload, field_name="check_name"),
                field_name="check_name",
            ),
            passed=_require_boolean(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            diagnostic=_require_non_empty_string(
                _require_present(payload, field_name="diagnostic"),
                field_name="diagnostic",
            ),
            evidence=_require_mapping(
                _require_present(payload, field_name="evidence"),
                field_name="evidence",
            ),
            remediation=_require_non_empty_string(
                _require_present(payload, field_name="remediation"),
                field_name="remediation",
            ),
        )


@dataclass(frozen=True)
class Phase25SurfaceEvidence:
    surface_id: str
    passed: bool
    reference_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25SurfaceEvidence":
        payload = _require_mapping(payload, field_name="phase_25_surface_evidence")
        return cls(
            surface_id=_require_non_empty_string(
                _require_present(payload, field_name="surface_id"),
                field_name="surface_id",
            ),
            passed=_require_boolean(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            reference_id=_require_non_empty_string(
                _require_present(payload, field_name="reference_id"),
                field_name="reference_id",
            ),
            detail=_require_non_empty_string(
                _require_present(payload, field_name="detail"),
                field_name="detail",
            ),
        )


@dataclass(frozen=True)
class Phase25RuntimeEvidence:
    broker_reconnect_observed: bool
    broker_reconnect_reference_id: str
    session_reset_observed: bool
    session_reset_reference_id: str
    state_ownership_verified: bool
    state_ownership_reference_id: str
    supervision_reference_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25RuntimeEvidence":
        payload = _require_mapping(payload, field_name="phase_25_runtime_evidence")
        return cls(
            broker_reconnect_observed=_require_boolean(
                _require_present(payload, field_name="broker_reconnect_observed"),
                field_name="broker_reconnect_observed",
            ),
            broker_reconnect_reference_id=_require_non_empty_string(
                _require_present(payload, field_name="broker_reconnect_reference_id"),
                field_name="broker_reconnect_reference_id",
            ),
            session_reset_observed=_require_boolean(
                _require_present(payload, field_name="session_reset_observed"),
                field_name="session_reset_observed",
            ),
            session_reset_reference_id=_require_non_empty_string(
                _require_present(payload, field_name="session_reset_reference_id"),
                field_name="session_reset_reference_id",
            ),
            state_ownership_verified=_require_boolean(
                _require_present(payload, field_name="state_ownership_verified"),
                field_name="state_ownership_verified",
            ),
            state_ownership_reference_id=_require_non_empty_string(
                _require_present(payload, field_name="state_ownership_reference_id"),
                field_name="state_ownership_reference_id",
            ),
            supervision_reference_id=_require_non_empty_string(
                _require_present(payload, field_name="supervision_reference_id"),
                field_name="supervision_reference_id",
            ),
        )


@dataclass(frozen=True)
class Phase25RetainedLogReference:
    step_id: str
    reference_id: str
    correlation_id: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25RetainedLogReference":
        payload = _require_mapping(payload, field_name="phase_25_retained_log_reference")
        return cls(
            step_id=_require_non_empty_string(
                _require_present(payload, field_name="step_id"),
                field_name="step_id",
            ),
            reference_id=_require_non_empty_string(
                _require_present(payload, field_name="reference_id"),
                field_name="reference_id",
            ),
            correlation_id=_require_non_empty_string(
                _require_present(payload, field_name="correlation_id"),
                field_name="correlation_id",
            ),
            detail=_require_non_empty_string(
                _require_present(payload, field_name="detail"),
                field_name="detail",
            ),
        )


@dataclass(frozen=True)
class Phase25VerticalSliceHarnessReport:
    schema_version: int
    case_id: str
    script_reference: str
    manifest_path: str
    artifact_root: str
    run_id: str
    correlation_id: str
    decision_trace_id: str
    decision: str
    reason_code: str
    retained_logs: tuple[Phase25RetainedLogReference, ...]
    retained_artifact_ids: tuple[str, ...]
    summary: dict[str, Any]
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "script_reference": self.script_reference,
            "manifest_path": self.manifest_path,
            "artifact_root": self.artifact_root,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "decision_trace_id": self.decision_trace_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "retained_logs": [item.to_dict() for item in self.retained_logs],
            "retained_artifact_ids": list(self.retained_artifact_ids),
            "summary": dict(self.summary),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25VerticalSliceHarnessReport":
        payload = _require_mapping(payload, field_name="phase_25_vertical_slice_harness_report")
        return cls(
            schema_version=_require_supported_schema_version(
                _require_present(payload, field_name="schema_version"),
                field_name="schema_version",
            ),
            case_id=_require_non_empty_string(
                _require_present(payload, field_name="case_id"),
                field_name="case_id",
            ),
            script_reference=_require_non_empty_string(
                _require_present(payload, field_name="script_reference"),
                field_name="script_reference",
            ),
            manifest_path=_require_non_empty_string(
                _require_present(payload, field_name="manifest_path"),
                field_name="manifest_path",
            ),
            artifact_root=_require_non_empty_string(
                _require_present(payload, field_name="artifact_root"),
                field_name="artifact_root",
            ),
            run_id=_require_non_empty_string(
                _require_present(payload, field_name="run_id"),
                field_name="run_id",
            ),
            correlation_id=_require_non_empty_string(
                _require_present(payload, field_name="correlation_id"),
                field_name="correlation_id",
            ),
            decision_trace_id=_require_non_empty_string(
                _require_present(payload, field_name="decision_trace_id"),
                field_name="decision_trace_id",
            ),
            decision=_require_non_empty_string(
                _require_present(payload, field_name="decision"),
                field_name="decision",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            retained_logs=tuple(
                Phase25RetainedLogReference.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="retained_logs"),
                    field_name="retained_logs",
                )
            ),
            retained_artifact_ids=_require_string_sequence(
                _require_present(payload, field_name="retained_artifact_ids"),
                field_name="retained_artifact_ids",
            ),
            summary=_require_mapping(
                _require_present(payload, field_name="summary"),
                field_name="summary",
            ),
            timestamp=_require_timestamp(
                _require_present(payload, field_name="timestamp"),
                field_name="timestamp",
            ),
        )


@dataclass(frozen=True)
class Phase25VerticalSliceGateRequest:
    case_id: str
    vertical_slice_report: Phase25VerticalSliceHarnessReport
    surface_evidence: tuple[Phase25SurfaceEvidence, ...]
    runtime_evidence: Phase25RuntimeEvidence
    drill_script_reference: str
    operator_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "vertical_slice_report": self.vertical_slice_report.to_dict(),
            "surface_evidence": [surface.to_dict() for surface in self.surface_evidence],
            "runtime_evidence": self.runtime_evidence.to_dict(),
            "drill_script_reference": self.drill_script_reference,
            "operator_notes": list(self.operator_notes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25VerticalSliceGateRequest":
        payload = _require_mapping(payload, field_name="phase_25_gate_request")
        return cls(
            case_id=_require_non_empty_string(
                _require_present(payload, field_name="case_id"),
                field_name="case_id",
            ),
            vertical_slice_report=Phase25VerticalSliceHarnessReport.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="vertical_slice_report"),
                    field_name="vertical_slice_report",
                )
            ),
            surface_evidence=tuple(
                Phase25SurfaceEvidence.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="surface_evidence"),
                    field_name="surface_evidence",
                )
            ),
            runtime_evidence=Phase25RuntimeEvidence.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="runtime_evidence"),
                    field_name="runtime_evidence",
                )
            ),
            drill_script_reference=_require_non_empty_string(
                _require_present(payload, field_name="drill_script_reference"),
                field_name="drill_script_reference",
            ),
            operator_notes=_require_string_sequence(
                payload.get("operator_notes", ()),
                field_name="operator_notes",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "Phase25VerticalSliceGateRequest":
        return cls.from_dict(_decode_json_object(payload, label="phase_25_gate_request"))


@dataclass(frozen=True)
class Phase25VerticalSliceGateReport:
    schema_version: int
    case_id: str
    phase_gate: str
    status: str
    reason_code: str
    scenario_decision: str
    scenario_reason_code: str
    correlation_id: str
    run_id: str
    decision_trace: list[dict[str, Any]]
    expected_vs_actual_diffs: list[dict[str, Any]]
    retained_artifact_ids: tuple[str, ...]
    operator_reason_bundle: dict[str, Any]
    context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["retained_artifact_ids"] = list(self.retained_artifact_ids)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Phase25VerticalSliceGateReport":
        payload = _require_mapping(payload, field_name="phase_25_gate_report")
        return cls(
            schema_version=_require_supported_schema_version(
                _require_present(payload, field_name="schema_version"),
                field_name="schema_version",
            ),
            case_id=_require_non_empty_string(
                _require_present(payload, field_name="case_id"),
                field_name="case_id",
            ),
            phase_gate=_require_non_empty_string(
                _require_present(payload, field_name="phase_gate"),
                field_name="phase_gate",
            ),
            status=_require_status(
                _require_present(payload, field_name="status"),
                field_name="status",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            scenario_decision=_require_non_empty_string(
                _require_present(payload, field_name="scenario_decision"),
                field_name="scenario_decision",
            ),
            scenario_reason_code=_require_non_empty_string(
                _require_present(payload, field_name="scenario_reason_code"),
                field_name="scenario_reason_code",
            ),
            correlation_id=_require_non_empty_string(
                _require_present(payload, field_name="correlation_id"),
                field_name="correlation_id",
            ),
            run_id=_require_non_empty_string(
                _require_present(payload, field_name="run_id"),
                field_name="run_id",
            ),
            decision_trace=list(
                _require_object_sequence(
                    _require_present(payload, field_name="decision_trace"),
                    field_name="decision_trace",
                )
            ),
            expected_vs_actual_diffs=list(
                _require_object_sequence(
                    _require_present(payload, field_name="expected_vs_actual_diffs"),
                    field_name="expected_vs_actual_diffs",
                )
            ),
            retained_artifact_ids=_require_string_sequence(
                _require_present(payload, field_name="retained_artifact_ids"),
                field_name="retained_artifact_ids",
            ),
            operator_reason_bundle=_require_mapping(
                _require_present(payload, field_name="operator_reason_bundle"),
                field_name="operator_reason_bundle",
            ),
            context=_require_mapping(
                _require_present(payload, field_name="context"),
                field_name="context",
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, field_name="explanation"),
                field_name="explanation",
            ),
            remediation=_require_non_empty_string(
                _require_present(payload, field_name="remediation"),
                field_name="remediation",
            ),
            timestamp=_require_timestamp(
                _require_present(payload, field_name="timestamp"),
                field_name="timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "Phase25VerticalSliceGateReport":
        return cls.from_dict(_decode_json_object(payload, label="phase_25_gate_report"))


def _check(
    *,
    check_id: str,
    check_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    evidence: dict[str, Any],
    remediation: str,
) -> Phase25CheckResult:
    return Phase25CheckResult(
        check_id=check_id,
        check_name=check_name,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence=evidence,
        remediation=remediation,
    )


def _append_diff(
    diffs: list[dict[str, Any]],
    *,
    subject: str,
    reason_code: str,
    expected: Any,
    actual: Any,
    diagnostic: str,
) -> None:
    diffs.append(
        {
            "subject": subject,
            "reason_code": reason_code,
            "expected": expected,
            "actual": actual,
            "diagnostic": diagnostic,
        }
    )


def evaluate_phase_25_vertical_slice_gate(
    request: Phase25VerticalSliceGateRequest,
) -> Phase25VerticalSliceGateReport:
    """Evaluate the explicit Phase 2.5 pass-or-pivot gate."""

    slice_report = request.vertical_slice_report
    summary = slice_report.summary
    runtime_summary = dict(summary.get("runtime") or {})
    schedule_summary = dict(summary.get("schedule") or {})
    live_bar_summary = dict(summary.get("live_bar") or {})
    readiness_summary = dict(summary.get("readiness") or {})
    recovery_smoke_summary = dict(summary.get("recovery_smoke") or {})
    recovery_runtime_summary = dict(summary.get("recovery_runtime") or {})
    route_mode_summary = dict(summary.get("route_mode") or {})
    reconciliation_summary = dict(summary.get("reconciliation") or {})
    evidence_archive_summary = dict(summary.get("evidence_archive") or {})

    retained_log_steps = {item.step_id for item in slice_report.retained_logs}
    retained_log_correlations = {item.correlation_id for item in slice_report.retained_logs}
    route_mode_selected = {
        str(item.get("scenario")): {
            "outcome": str(item.get("outcome")),
            "reason_code": str(item.get("reason_code")),
        }
        for item in route_mode_summary.get("selected", ())
        if isinstance(item, dict)
    }
    startup_scenarios = _as_string_tuple(runtime_summary.get("startup_scenarios"))
    sealed_evidence_ids = set(_as_string_tuple(evidence_archive_summary.get("sealed_evidence_ids")))
    required_summary_keys_present = all(
        key in summary for key in REQUIRED_VERTICAL_SLICE_SUMMARY_KEYS
    )
    route_mode_complete = all(
        route_mode_selected.get(scenario, {}) == {
            "outcome": expected_outcome,
            "reason_code": expected_reason_code,
        }
        for scenario, (expected_outcome, expected_reason_code) in REQUIRED_ROUTE_MODE_OUTCOMES.items()
    )
    vertical_slice_report_valid = (
        slice_report.schema_version == SUPPORTED_PHASE_25_VERTICAL_SLICE_SCHEMA_VERSION
        and slice_report.decision in {Phase25VerticalSliceStatus.PASS.value, Phase25VerticalSliceStatus.PIVOT.value}
        and bool(slice_report.reason_code)
        and bool(slice_report.script_reference)
        and bool(slice_report.manifest_path)
        and bool(slice_report.artifact_root)
        and bool(slice_report.correlation_id)
        and bool(slice_report.decision_trace_id)
        and bool(slice_report.run_id)
        and required_summary_keys_present
    )
    checks = [
        _check(
            check_id=PHASE_25_CHECK_IDS[0],
            check_name="vertical_slice_harness_contract",
            passed=vertical_slice_report_valid,
            reason_code=(
                "PHASE_25_VERTICAL_SLICE_REPORT_VALID"
                if vertical_slice_report_valid
                else "PHASE_25_VERTICAL_SLICE_REPORT_INVALID"
            ),
            diagnostic=(
                "The retained Phase 2.5 report is a vertical-slice harness run with explicit pass-or-pivot output."
                if vertical_slice_report_valid
                else "Phase 2.5 requires a retained opsd vertical-slice harness report with explicit decision output."
            ),
            evidence={
                "script_reference": slice_report.script_reference,
                "decision": slice_report.decision,
                "reason_code": slice_report.reason_code,
                "required_summary_keys_present": required_summary_keys_present,
            },
            remediation=(
                "Bind this milestone to a retained report from `scripts/opsd_vertical_slice_smoke.py` "
                "before clearing the gate."
            ),
        )
    ]

    retained_evidence_valid = (
        slice_report.script_reference == "scripts/opsd_vertical_slice_smoke.py"
        and slice_report.manifest_path in slice_report.retained_artifact_ids
        and bool(slice_report.retained_artifact_ids)
        and retained_log_steps.issuperset(REQUIRED_VERTICAL_SLICE_LOG_STEPS)
        and retained_log_correlations == {slice_report.correlation_id}
    )
    checks.append(
        _check(
            check_id=PHASE_25_CHECK_IDS[1],
            check_name="retained_logs_and_manifest",
            passed=retained_evidence_valid,
            reason_code=(
                "PHASE_25_RETAINED_EVIDENCE_VALID"
                if retained_evidence_valid
                else "PHASE_25_RETAINED_EVIDENCE_INVALID"
            ),
            diagnostic=(
                "The vertical-slice harness keeps the manifest, log bundle, and retained artifact ids together."
                if retained_evidence_valid
                else "The vertical-slice harness is missing retained logs, manifest linkage, or stable artifact references."
            ),
            evidence={
                "manifest_path": slice_report.manifest_path,
                "retained_log_steps": sorted(retained_log_steps),
                "retained_log_correlations": sorted(retained_log_correlations),
                "retained_artifact_count": len(slice_report.retained_artifact_ids),
            },
            remediation=(
                "Retain the vertical-slice manifest, all ten step stdout logs, and the bundle of artifact ids "
                "before evaluating Phase 2.5."
            ),
        )
    )

    surface_map = {surface.surface_id: surface for surface in request.surface_evidence}
    missing_surfaces = tuple(
        surface for surface in REQUIRED_PHASE_25_SURFACES if surface not in surface_map
    )
    failed_surfaces = tuple(
        surface
        for surface in REQUIRED_PHASE_25_SURFACES
        if surface in surface_map and not surface_map[surface].passed
    )
    unknown_surfaces = tuple(
        surface for surface in surface_map if surface not in REQUIRED_PHASE_25_SURFACES
    )
    surfaces_complete = not missing_surfaces and not failed_surfaces and not unknown_surfaces
    checks.append(
        _check(
            check_id=PHASE_25_CHECK_IDS[2],
            check_name="phase_25_surface_coverage",
            passed=surfaces_complete,
            reason_code=(
                "PHASE_25_BUILD_SURFACES_COMPLETE"
                if surfaces_complete
                else "PHASE_25_BUILD_SURFACES_INCOMPLETE"
            ),
            diagnostic=(
                "All required Phase 2.5 build surfaces are evidenced and passing."
                if surfaces_complete
                else "One or more required Phase 2.5 build surfaces are missing, failed, or unknown."
            ),
            evidence={
                "missing_surfaces": list(missing_surfaces),
                "failed_surfaces": list(failed_surfaces),
                "unknown_surfaces": list(unknown_surfaces),
            },
            remediation=(
                "Retain passing evidence for entitlements, approved IBKR bar construction, "
                "dummy strategy routing, paper/shadow behavior, statement ingestion, reconciliation, "
                "contract conformance, and preliminary 1OZ diagnostics."
            ),
        )
    )

    runtime_evidence_complete = (
        request.runtime_evidence.broker_reconnect_observed
        and bool(request.runtime_evidence.broker_reconnect_reference_id)
        and request.runtime_evidence.session_reset_observed
        and bool(request.runtime_evidence.session_reset_reference_id)
        and request.runtime_evidence.state_ownership_verified
        and bool(request.runtime_evidence.state_ownership_reference_id)
        and bool(request.runtime_evidence.supervision_reference_id)
        and bool(request.drill_script_reference)
        and set(startup_scenarios).issuperset(REQUIRED_RUNTIME_STARTUP_SCENARIOS)
        and runtime_summary.get("control_reason_code") == "WITHDRAW_LIVE_OPERATOR_REQUEST"
        and bool(schedule_summary.get("artifact_id"))
        and schedule_summary.get("reset_state") == "reset_boundary"
        and schedule_summary.get("post_reset_tradeable") == "true"
        and live_bar_summary.get("status") == "accepted"
        and live_bar_summary.get("reason_code") == "BAR_BUILDER_ACCEPTED"
        and readiness_summary.get("status") == "green"
        and readiness_summary.get("reason_code") == "READINESS_READY_TO_ACTIVATE"
        and recovery_smoke_summary.get("recovery_status") == "resume_tradeable"
        and recovery_smoke_summary.get("shutdown_status") == "restart_ready"
        and recovery_runtime_summary.get("scenario") == "recovery_fence"
        and recovery_runtime_summary.get("recovery_state") == "safe_resume"
        and recovery_runtime_summary.get("shutdown_restart_ready") == "true"
        and route_mode_complete
        and bool(reconciliation_summary.get("artifact_id"))
        and reconciliation_summary.get("next_session_eligibility") == "blocked"
        and sealed_evidence_ids.issuperset(REQUIRED_SEALED_EVIDENCE_IDS)
    )
    checks.append(
        _check(
            check_id=PHASE_25_CHECK_IDS[3],
            check_name="runtime_reset_route_and_supervision_evidence",
            passed=runtime_evidence_complete,
            reason_code=(
                "PHASE_25_RUNTIME_EVIDENCE_COMPLETE"
                if runtime_evidence_complete
                else "PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE"
            ),
            diagnostic=(
                "The real Rust runtime path retained reconnects, reset boundaries, route controls, recovery, reconciliation, and supervision evidence."
                if runtime_evidence_complete
                else "Phase 2.5 is missing reconnect, reset, route-mode, recovery, reconciliation, supervision, or drill-script evidence."
            ),
            evidence={
                "broker_reconnect_observed": request.runtime_evidence.broker_reconnect_observed,
                "broker_reconnect_reference_id": request.runtime_evidence.broker_reconnect_reference_id,
                "session_reset_observed": request.runtime_evidence.session_reset_observed,
                "session_reset_reference_id": request.runtime_evidence.session_reset_reference_id,
                "state_ownership_verified": request.runtime_evidence.state_ownership_verified,
                "state_ownership_reference_id": request.runtime_evidence.state_ownership_reference_id,
                "supervision_reference_id": request.runtime_evidence.supervision_reference_id,
                "drill_script_reference": request.drill_script_reference,
                "startup_scenarios": list(startup_scenarios),
                "route_mode_selected": route_mode_selected,
                "sealed_evidence_ids": sorted(sealed_evidence_ids),
            },
            remediation=(
                "Retain documented reconnect, reset, supervision, route-mode, recovery, and reconciliation evidence "
                "from the opsd vertical-slice run before clearing the milestone."
            ),
        )
    )

    gate_clear = slice_report.decision == Phase25VerticalSliceStatus.PASS.value
    checks.append(
        _check(
            check_id=PHASE_25_CHECK_IDS[4],
            check_name="explicit_phase_25_clear_or_pivot",
            passed=gate_clear,
            reason_code=(
                "PHASE_25_CLEAR_DECISION_RECORDED"
                if gate_clear
                else "PHASE_25_PIVOT_DECISION_RECORDED"
            ),
            diagnostic=(
                "The retained vertical-slice harness report clears the lane."
                if gate_clear
                else "The retained vertical-slice harness report preserves an explicit pivot decision."
            ),
            evidence={
                "scenario_decision": slice_report.decision,
                "scenario_reason_code": slice_report.reason_code,
            },
            remediation=(
                "Do not continue deeper live-lane work until this milestone either clears "
                "cleanly or records an explicit pivot decision with evidence."
            ),
        )
    )

    expected_vs_actual_diffs: list[dict[str, Any]] = []
    for surface_id in missing_surfaces:
        _append_diff(
            expected_vs_actual_diffs,
            subject=surface_id,
            reason_code="PHASE_25_BUILD_SURFACES_INCOMPLETE",
            expected="passing retained evidence",
            actual="missing",
            diagnostic=f"Required surface evidence missing for {surface_id}.",
        )
    for surface_id in failed_surfaces:
        surface = surface_map[surface_id]
        _append_diff(
            expected_vs_actual_diffs,
            subject=surface_id,
            reason_code="PHASE_25_BUILD_SURFACES_INCOMPLETE",
            expected="passing retained evidence",
            actual={"reference_id": surface.reference_id, "detail": surface.detail},
            diagnostic=surface.detail,
        )
    for surface_id in unknown_surfaces:
        _append_diff(
            expected_vs_actual_diffs,
            subject=surface_id,
            reason_code="PHASE_25_BUILD_SURFACES_INCOMPLETE",
            expected=list(REQUIRED_PHASE_25_SURFACES),
            actual=surface_id,
            diagnostic=f"Unknown surface evidence {surface_id} is not part of Phase 2.5.",
        )
    if not request.runtime_evidence.broker_reconnect_observed:
        _append_diff(
            expected_vs_actual_diffs,
            subject="broker_reconnect_observation",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected=True,
            actual=False,
            diagnostic="Phase 2.5 requires a documented broker reconnect observation.",
        )
    if not request.runtime_evidence.session_reset_observed:
        _append_diff(
            expected_vs_actual_diffs,
            subject="session_reset_observation",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected=True,
            actual=False,
            diagnostic="Phase 2.5 requires a documented session-reset observation.",
        )
    if not request.runtime_evidence.state_ownership_verified:
        _append_diff(
            expected_vs_actual_diffs,
            subject="runtime_state_ownership",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected=True,
            actual=False,
            diagnostic="Phase 2.5 requires explicit runtime state-ownership evidence.",
        )
    if not bool(request.runtime_evidence.supervision_reference_id):
        _append_diff(
            expected_vs_actual_diffs,
            subject="runtime_supervision",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="retained supervision reference",
            actual="missing",
            diagnostic="Phase 2.5 requires retained runtime supervision evidence.",
        )
    if not bool(request.drill_script_reference):
        _append_diff(
            expected_vs_actual_diffs,
            subject="phase_25_drill_script",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="scripts/opsd_vertical_slice_smoke.py",
            actual="missing",
            diagnostic="Phase 2.5 requires a retained user-runnable vertical-slice drill reference.",
        )
    if set(startup_scenarios) != set(REQUIRED_RUNTIME_STARTUP_SCENARIOS):
        _append_diff(
            expected_vs_actual_diffs,
            subject="runtime.startup_scenarios",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected=list(REQUIRED_RUNTIME_STARTUP_SCENARIOS),
            actual=list(startup_scenarios),
            diagnostic="The retained runtime slice must include startup handoff, mailbox backpressure, and broker control scenarios.",
        )
    if schedule_summary.get("reset_state") != "reset_boundary":
        _append_diff(
            expected_vs_actual_diffs,
            subject="schedule.reset_state",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="reset_boundary",
            actual=schedule_summary.get("reset_state"),
            diagnostic="Phase 2.5 requires compiled-session reset-boundary evidence.",
        )
    if live_bar_summary.get("status") != "accepted":
        _append_diff(
            expected_vs_actual_diffs,
            subject="live_bar.status",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="accepted",
            actual=live_bar_summary.get("status"),
            diagnostic="Phase 2.5 requires an accepted live-bar construction pass on the real path.",
        )
    if readiness_summary.get("status") != "green":
        _append_diff(
            expected_vs_actual_diffs,
            subject="readiness.status",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="green",
            actual=readiness_summary.get("status"),
            diagnostic="Phase 2.5 requires a green session-readiness packet on the rehearsal path.",
        )
    if recovery_runtime_summary.get("recovery_state") != "safe_resume":
        _append_diff(
            expected_vs_actual_diffs,
            subject="recovery_runtime.recovery_state",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="safe_resume",
            actual=recovery_runtime_summary.get("recovery_state"),
            diagnostic="Phase 2.5 requires retained recovery-fence evidence showing safe resume.",
        )
    if not route_mode_complete:
        _append_diff(
            expected_vs_actual_diffs,
            subject="route_mode.selected",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected={
                scenario: {
                    "outcome": expected_outcome,
                    "reason_code": expected_reason_code,
                }
                for scenario, (expected_outcome, expected_reason_code) in REQUIRED_ROUTE_MODE_OUTCOMES.items()
            },
            actual=route_mode_selected,
            diagnostic="Phase 2.5 requires both paper-route rerouting and shadow-live suppression evidence.",
        )
    if reconciliation_summary.get("next_session_eligibility") != "blocked":
        _append_diff(
            expected_vs_actual_diffs,
            subject="reconciliation.next_session_eligibility",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected="blocked",
            actual=reconciliation_summary.get("next_session_eligibility"),
            diagnostic="Phase 2.5 requires authoritative reconciliation to block next-session promotion by default.",
        )
    if not sealed_evidence_ids.issuperset(REQUIRED_SEALED_EVIDENCE_IDS):
        _append_diff(
            expected_vs_actual_diffs,
            subject="evidence_archive.sealed_evidence_ids",
            reason_code="PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE",
            expected=list(REQUIRED_SEALED_EVIDENCE_IDS),
            actual=sorted(sealed_evidence_ids),
            diagnostic="Phase 2.5 requires sealed paper, shadow, and recovery evidence bundles.",
        )
    if slice_report.decision != Phase25VerticalSliceStatus.PASS.value:
        _append_diff(
            expected_vs_actual_diffs,
            subject="vertical_slice_decision",
            reason_code="PHASE_25_VERTICAL_SLICE_PIVOT",
            expected="pass",
            actual={
                "decision": slice_report.decision,
                "reason_code": slice_report.reason_code,
            },
            diagnostic="The retained vertical-slice harness recorded an explicit pivot decision.",
        )

    failed_checks = [check for check in checks if not check.passed]
    structurally_invalid = not vertical_slice_report_valid or not retained_evidence_valid
    if structurally_invalid:
        status = Phase25VerticalSliceStatus.INVALID
        reason_code = (
            "PHASE_25_VERTICAL_SLICE_REPORT_INVALID"
            if not vertical_slice_report_valid
            else "PHASE_25_RETAINED_EVIDENCE_INVALID"
        )
        explanation = (
            "Phase 2.5 cannot be evaluated because the retained opsd vertical-slice report is malformed "
            "or its log and artifact bundle is incomplete."
        )
        remediation = failed_checks[0].remediation
    elif surfaces_complete and runtime_evidence_complete and gate_clear:
        status = Phase25VerticalSliceStatus.PASS
        reason_code = "PHASE_25_VERTICAL_SLICE_PASS"
        explanation = (
            "Phase 2.5 clears: the non-economic 1OZ/IBKR vertical slice now runs through the real Rust "
            "execution lane with retained logs, artifacts, and explicit operational evidence."
        )
        remediation = (
            "Retain this gate report and its linked artifacts as the approval record before "
            "moving deeper into live-lane calibration work."
        )
    else:
        status = Phase25VerticalSliceStatus.PIVOT
        if not surfaces_complete:
            reason_code = "PHASE_25_BUILD_SURFACES_INCOMPLETE"
        elif not runtime_evidence_complete:
            reason_code = "PHASE_25_RUNTIME_EVIDENCE_INCOMPLETE"
        else:
            reason_code = "PHASE_25_VERTICAL_SLICE_PIVOT"
        explanation = (
            "Phase 2.5 retains enough evidence to pivot or narrow the lane, but it does not "
            "clear as a clean end-to-end vertical-slice pass."
        )
        remediation = failed_checks[0].remediation if failed_checks else (
            "Preserve the current pivot decision and tighten the next follow-up on the failing lane."
        )

    retained_artifact_ids = _unique_strings(
        list(slice_report.retained_artifact_ids)
        + [item.reference_id for item in slice_report.retained_logs]
        + [surface.reference_id for surface in request.surface_evidence]
        + [
            slice_report.script_reference,
            slice_report.manifest_path,
            slice_report.artifact_root,
            request.runtime_evidence.broker_reconnect_reference_id,
            request.runtime_evidence.session_reset_reference_id,
            request.runtime_evidence.state_ownership_reference_id,
            request.runtime_evidence.supervision_reference_id,
            request.drill_script_reference,
        ]
    )
    operator_reason_bundle = {
        "summary": explanation,
        "gate_summary": {
            "phase_gate": "phase_2_5",
            "status": status.value,
            "reason_code": reason_code,
            "scenario_decision": slice_report.decision,
            "scenario_reason_code": slice_report.reason_code,
        },
        "rule_trace": [
            {
                "check_id": check.check_id,
                "reason_code": check.reason_code,
                "passed": check.passed,
            }
            for check in checks
        ],
        "remediation_hints": [
            check.remediation for check in checks if not check.passed
        ]
        or [remediation],
        "operator_notes": list(request.operator_notes),
    }
    context = {
        "scenario_case_id": slice_report.case_id,
        "artifact_root": slice_report.artifact_root,
        "manifest_path": slice_report.manifest_path,
        "missing_surfaces": list(missing_surfaces),
        "failed_surfaces": list(failed_surfaces),
        "unknown_surfaces": list(unknown_surfaces),
        "required_surfaces": list(REQUIRED_PHASE_25_SURFACES),
        "retained_log_steps": sorted(retained_log_steps),
        "broker_reconnect_observed": request.runtime_evidence.broker_reconnect_observed,
        "session_reset_observed": request.runtime_evidence.session_reset_observed,
        "state_ownership_verified": request.runtime_evidence.state_ownership_verified,
    }
    return Phase25VerticalSliceGateReport(
        schema_version=SUPPORTED_PHASE_25_VERTICAL_SLICE_SCHEMA_VERSION,
        case_id=request.case_id,
        phase_gate="phase_2_5",
        status=status.value,
        reason_code=reason_code,
        scenario_decision=slice_report.decision,
        scenario_reason_code=slice_report.reason_code,
        correlation_id=slice_report.correlation_id,
        run_id=slice_report.run_id,
        decision_trace=[check.to_dict() for check in checks],
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        retained_artifact_ids=retained_artifact_ids,
        operator_reason_bundle=operator_reason_bundle,
        context=context,
        explanation=explanation,
        remediation=remediation,
    )


def validate_phase_25_vertical_slice_gate_contract() -> list[str]:
    errors: list[str] = []
    if len(set(PHASE_25_CHECK_IDS)) != len(PHASE_25_CHECK_IDS):
        errors.append("Phase 2.5 gate check ids must be unique")
    if len(set(REQUIRED_PHASE_25_SURFACES)) != len(REQUIRED_PHASE_25_SURFACES):
        errors.append("Phase 2.5 required surfaces must be unique")
    if len(REQUIRED_PHASE_25_SURFACES) != 9:
        errors.append("Phase 2.5 gate must enumerate nine required build surfaces")
    if len(set(REQUIRED_VERTICAL_SLICE_LOG_STEPS)) != len(REQUIRED_VERTICAL_SLICE_LOG_STEPS):
        errors.append("Phase 2.5 retained log step ids must be unique")
    if len(REQUIRED_VERTICAL_SLICE_LOG_STEPS) != 10:
        errors.append("Phase 2.5 gate must retain all ten vertical-slice step logs")
    return errors


VALIDATION_ERRORS = validate_phase_25_vertical_slice_gate_contract()
