"""Notebook quarantine and admissible evidence boundary contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.artifact_classes import (
    DependencyState,
    FreshnessState,
    evaluate_artifact_admissibility,
)
from shared.policy.research_state import ResearchAdmissibilityClass

SUPPORTED_NOTEBOOK_QUARANTINE_SCHEMA_VERSION = 1


def _require_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_present(payload: dict[str, object], *, field_name: str) -> object:
    if field_name not in payload:
        raise ValueError(f"{field_name} field is required")
    return payload[field_name]


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}: must be a non-empty string")
    return value


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[]") for item in value
    )


def _require_object_sequence(value: object, *, field_name: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of objects")
    return tuple(
        _require_mapping(item, field_name=f"{field_name}[]") for item in value
    )


def _require_boolean(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be a boolean")
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


def _require_evidence_source_kind(value: object, *, field_name: str) -> EvidenceSourceKind:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid evidence source kind")
    try:
        return EvidenceSourceKind(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid evidence source kind") from exc


def _require_evidence_usage(value: object, *, field_name: str) -> EvidenceUsage:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid evidence usage")
    try:
        return EvidenceUsage(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid evidence usage") from exc


def _require_dependency_state(value: object, *, field_name: str) -> DependencyState:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid dependency state")
    try:
        return DependencyState(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid dependency state") from exc


def _require_freshness_state(value: object, *, field_name: str) -> FreshnessState:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid freshness state")
    try:
        return FreshnessState(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid freshness state") from exc


def _require_research_admissibility(
    value: object,
    *,
    field_name: str,
) -> ResearchAdmissibilityClass:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid research admissibility class")
    try:
        return ResearchAdmissibilityClass(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid research admissibility class") from exc


def _require_status(value: object, *, field_name: str) -> NotebookQuarantineStatus:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid notebook quarantine status")
    try:
        return NotebookQuarantineStatus(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid notebook quarantine status") from exc


@unique
class EvidenceSourceKind(str, Enum):
    NOTEBOOK_OUTPUT = "notebook_output"
    REPRODUCIBLE_BATCH_RUN = "reproducible_batch_run"
    SIGNED_MANIFEST = "signed_manifest"
    CERTIFIED_RELEASE = "certified_release"
    POLICY_EVALUATED_REPORT = "policy_evaluated_report"
    SEALED_OPERATIONAL_EVIDENCE_BUNDLE = "sealed_operational_evidence_bundle"


@unique
class EvidenceUsage(str, Enum):
    EXPLORATION = "exploration"
    EXPLANATION = "explanation"
    SELECTION = "selection"
    PROMOTION = "promotion"


@unique
class NotebookQuarantineStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    VIOLATION = "violation"
    INVALID = "invalid"


ALLOWED_GATE_EVIDENCE_SOURCE_KINDS = (
    EvidenceSourceKind.REPRODUCIBLE_BATCH_RUN,
    EvidenceSourceKind.SIGNED_MANIFEST,
    EvidenceSourceKind.CERTIFIED_RELEASE,
    EvidenceSourceKind.POLICY_EVALUATED_REPORT,
    EvidenceSourceKind.SEALED_OPERATIONAL_EVIDENCE_BUNDLE,
)

GATE_USAGES = (EvidenceUsage.SELECTION, EvidenceUsage.PROMOTION)
GATE_ADMISSIBLE_RESEARCH_CLASSES = (
    ResearchAdmissibilityClass.EXECUTION_CALIBRATION_ADMISSIBLE,
    ResearchAdmissibilityClass.RISK_POLICY_ADMISSIBLE,
)

NOTEBOOK_QUARANTINE_CHECK_IDS = (
    "gate_sources_require_non_notebook_admissible_evidence",
    "gate_sources_use_allowed_origins",
    "notebook_derived_sources_cannot_count_toward_gate",
    "batch_runs_require_gate_admissible_research_state",
    "policy_reports_require_family_decision_records",
    "required_decision_records_are_covered",
)


def validate_notebook_quarantine_contract() -> list[str]:
    errors: list[str] = []
    if SUPPORTED_NOTEBOOK_QUARANTINE_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    if len(NOTEBOOK_QUARANTINE_CHECK_IDS) != len(set(NOTEBOOK_QUARANTINE_CHECK_IDS)):
        errors.append("notebook-quarantine check identifiers must be unique")
    if EvidenceSourceKind.NOTEBOOK_OUTPUT in ALLOWED_GATE_EVIDENCE_SOURCE_KINDS:
        errors.append("notebook outputs must never count as gate-admissible evidence")
    if len(ALLOWED_GATE_EVIDENCE_SOURCE_KINDS) != len(set(ALLOWED_GATE_EVIDENCE_SOURCE_KINDS)):
        errors.append("gate-admissible evidence source kinds must be unique")
    return errors


VALIDATION_ERRORS = validate_notebook_quarantine_contract()


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class EvidenceSourceRecord:
    source_id: str
    source_kind: EvidenceSourceKind
    usage: EvidenceUsage
    counts_toward_gate: bool = False
    canonical_reference_id: str | None = None
    reference_artifact_id: str | None = None
    research_run_id: str | None = None
    family_decision_record_id: str | None = None
    research_admissibility_class: ResearchAdmissibilityClass | None = None
    dependency_state: DependencyState = DependencyState.VALID
    freshness_state: FreshnessState = FreshnessState.NOT_APPLICABLE
    produced_by_notebook: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind.value,
            "usage": self.usage.value,
            "counts_toward_gate": self.counts_toward_gate,
            "canonical_reference_id": self.canonical_reference_id,
            "reference_artifact_id": self.reference_artifact_id,
            "research_run_id": self.research_run_id,
            "family_decision_record_id": self.family_decision_record_id,
            "research_admissibility_class": (
                None
                if self.research_admissibility_class is None
                else self.research_admissibility_class.value
            ),
            "dependency_state": self.dependency_state.value,
            "freshness_state": self.freshness_state.value,
            "produced_by_notebook": self.produced_by_notebook,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> EvidenceSourceRecord:
        payload = _require_mapping(payload, field_name="evidence_source_record")
        admissibility = payload.get("research_admissibility_class")
        return cls(
            source_id=_require_non_empty_string(
                _require_present(payload, field_name="source_id"),
                field_name="source_id",
            ),
            source_kind=_require_evidence_source_kind(
                _require_present(payload, field_name="source_kind"),
                field_name="source_kind",
            ),
            usage=_require_evidence_usage(
                _require_present(payload, field_name="usage"),
                field_name="usage",
            ),
            counts_toward_gate=(
                False
                if payload.get("counts_toward_gate") is None
                else _require_boolean(payload["counts_toward_gate"], field_name="counts_toward_gate")
            ),
            canonical_reference_id=(
                None
                if payload.get("canonical_reference_id") is None
                else _require_non_empty_string(
                    payload["canonical_reference_id"],
                    field_name="canonical_reference_id",
                )
            ),
            reference_artifact_id=(
                None
                if payload.get("reference_artifact_id") is None
                else _require_non_empty_string(
                    payload["reference_artifact_id"],
                    field_name="reference_artifact_id",
                )
            ),
            research_run_id=(
                None
                if payload.get("research_run_id") is None
                else _require_non_empty_string(
                    payload["research_run_id"],
                    field_name="research_run_id",
                )
            ),
            family_decision_record_id=(
                None
                if payload.get("family_decision_record_id") is None
                else _require_non_empty_string(
                    payload["family_decision_record_id"],
                    field_name="family_decision_record_id",
                )
            ),
            research_admissibility_class=(
                None
                if admissibility is None
                else _require_research_admissibility(
                    admissibility,
                    field_name="research_admissibility_class",
                )
            ),
            dependency_state=(
                DependencyState.VALID
                if payload.get("dependency_state") is None
                else _require_dependency_state(
                    payload["dependency_state"],
                    field_name="dependency_state",
                )
            ),
            freshness_state=(
                FreshnessState.NOT_APPLICABLE
                if payload.get("freshness_state") is None
                else _require_freshness_state(
                    payload["freshness_state"],
                    field_name="freshness_state",
                )
            ),
            produced_by_notebook=(
                False
                if payload.get("produced_by_notebook") is None
                else _require_boolean(
                    payload["produced_by_notebook"],
                    field_name="produced_by_notebook",
                )
            ),
        )


@dataclass(frozen=True)
class NotebookQuarantineRequest:
    evaluation_id: str
    family_id: str
    evidence_sources: tuple[EvidenceSourceRecord, ...]
    required_decision_record_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "family_id": self.family_id,
            "evidence_sources": [source.to_dict() for source in self.evidence_sources],
            "required_decision_record_ids": list(self.required_decision_record_ids),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> NotebookQuarantineRequest:
        payload = _require_mapping(payload, field_name="notebook_quarantine_request")
        return cls(
            evaluation_id=_require_non_empty_string(
                _require_present(payload, field_name="evaluation_id"),
                field_name="evaluation_id",
            ),
            family_id=_require_non_empty_string(
                _require_present(payload, field_name="family_id"),
                field_name="family_id",
            ),
            evidence_sources=tuple(
                EvidenceSourceRecord.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="evidence_sources"),
                    field_name="evidence_sources",
                )
            ),
            required_decision_record_ids=tuple(
                _require_string_sequence(
                    payload.get("required_decision_record_ids", []),
                    field_name="required_decision_record_ids",
                )
            ),
        )


@dataclass(frozen=True)
class NotebookQuarantineCheckResult:
    check_id: str
    passed: bool
    reason_code: str | None
    explanation: str
    affected_source_ids: tuple[str, ...] = ()
    context: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "affected_source_ids": list(self.affected_source_ids),
            "context": _jsonable(self.context),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> NotebookQuarantineCheckResult:
        payload = _require_mapping(payload, field_name="notebook_quarantine_check_result")
        return cls(
            check_id=_require_non_empty_string(
                _require_present(payload, field_name="check_id"),
                field_name="check_id",
            ),
            passed=_require_boolean(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            reason_code=(
                None
                if _require_present(payload, field_name="reason_code") is None
                else _require_non_empty_string(payload["reason_code"], field_name="reason_code")
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, field_name="explanation"),
                field_name="explanation",
            ),
            affected_source_ids=_require_string_sequence(
                _require_present(payload, field_name="affected_source_ids"),
                field_name="affected_source_ids",
            ),
            context=_require_mapping(
                _require_present(payload, field_name="context"),
                field_name="context",
            ),
        )


@dataclass(frozen=True)
class NotebookQuarantineReport:
    evaluation_id: str
    family_id: str
    status: NotebookQuarantineStatus
    selection_admissible: bool
    promotion_admissible: bool
    quarantined_source_ids: tuple[str, ...]
    admissible_source_ids: tuple[str, ...]
    rejected_source_ids: tuple[str, ...]
    covered_decision_record_ids: tuple[str, ...]
    missing_decision_record_ids: tuple[str, ...]
    check_results: tuple[NotebookQuarantineCheckResult, ...]
    generated_at_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "family_id": self.family_id,
            "status": self.status.value,
            "selection_admissible": self.selection_admissible,
            "promotion_admissible": self.promotion_admissible,
            "quarantined_source_ids": list(self.quarantined_source_ids),
            "admissible_source_ids": list(self.admissible_source_ids),
            "rejected_source_ids": list(self.rejected_source_ids),
            "covered_decision_record_ids": list(self.covered_decision_record_ids),
            "missing_decision_record_ids": list(self.missing_decision_record_ids),
            "check_results": [result.to_dict() for result in self.check_results],
            "generated_at_utc": self.generated_at_utc,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> NotebookQuarantineReport:
        payload = _require_mapping(payload, field_name="notebook_quarantine_report")
        return cls(
            evaluation_id=_require_non_empty_string(
                _require_present(payload, field_name="evaluation_id"),
                field_name="evaluation_id",
            ),
            family_id=_require_non_empty_string(
                _require_present(payload, field_name="family_id"),
                field_name="family_id",
            ),
            status=_require_status(
                _require_present(payload, field_name="status"),
                field_name="status",
            ),
            selection_admissible=_require_boolean(
                _require_present(payload, field_name="selection_admissible"),
                field_name="selection_admissible",
            ),
            promotion_admissible=_require_boolean(
                _require_present(payload, field_name="promotion_admissible"),
                field_name="promotion_admissible",
            ),
            quarantined_source_ids=_require_string_sequence(
                _require_present(payload, field_name="quarantined_source_ids"),
                field_name="quarantined_source_ids",
            ),
            admissible_source_ids=_require_string_sequence(
                _require_present(payload, field_name="admissible_source_ids"),
                field_name="admissible_source_ids",
            ),
            rejected_source_ids=_require_string_sequence(
                _require_present(payload, field_name="rejected_source_ids"),
                field_name="rejected_source_ids",
            ),
            covered_decision_record_ids=_require_string_sequence(
                _require_present(payload, field_name="covered_decision_record_ids"),
                field_name="covered_decision_record_ids",
            ),
            missing_decision_record_ids=_require_string_sequence(
                _require_present(payload, field_name="missing_decision_record_ids"),
                field_name="missing_decision_record_ids",
            ),
            check_results=tuple(
                NotebookQuarantineCheckResult.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="check_results"),
                    field_name="check_results",
                )
            ),
            generated_at_utc=_require_timestamp(
                _require_present(payload, field_name="generated_at_utc"),
                field_name="generated_at_utc",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> NotebookQuarantineReport:
        decoder = json.JSONDecoder()
        try:
            decoded = decoder.decode(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"notebook_quarantine_report: invalid JSON payload: {exc.msg}") from exc
        return cls.from_dict(_require_mapping(decoded, field_name="notebook_quarantine_report"))


def admissible_gate_source_kinds() -> tuple[str, ...]:
    return tuple(kind.value for kind in ALLOWED_GATE_EVIDENCE_SOURCE_KINDS)


def _check_result(
    *,
    check_id: str,
    passed: bool,
    reason_code: str | None,
    explanation: str,
    affected_source_ids: list[str],
    context: dict[str, object],
) -> NotebookQuarantineCheckResult:
    return NotebookQuarantineCheckResult(
        check_id=check_id,
        passed=passed,
        reason_code=reason_code,
        explanation=explanation,
        affected_source_ids=tuple(affected_source_ids),
        context=context,
    )


def _artifact_is_admissible(source: EvidenceSourceRecord) -> tuple[bool, str | None]:
    if source.source_kind == EvidenceSourceKind.REPRODUCIBLE_BATCH_RUN:
        diagnostic = evaluate_artifact_admissibility(
            "research_run",
            dependency_state=source.dependency_state,
            freshness_state=source.freshness_state,
        )
        return diagnostic.admissible, diagnostic.reason_code

    if source.source_kind == EvidenceSourceKind.POLICY_EVALUATED_REPORT:
        diagnostic = evaluate_artifact_admissibility(
            "family_decision_record",
            dependency_state=source.dependency_state,
            freshness_state=source.freshness_state,
        )
        return diagnostic.admissible, diagnostic.reason_code

    if source.reference_artifact_id in {"dataset_release", "analytic_release"}:
        diagnostic = evaluate_artifact_admissibility(
            source.reference_artifact_id,
            dependency_state=source.dependency_state,
            freshness_state=source.freshness_state,
        )
        return diagnostic.admissible, diagnostic.reason_code

    return True, None


def evaluate_notebook_quarantine(
    request: NotebookQuarantineRequest,
) -> NotebookQuarantineReport:
    validation_errors = list(VALIDATION_ERRORS)
    seen_source_ids: set[str] = set()
    for source in request.evidence_sources:
        if source.source_id in seen_source_ids:
            validation_errors.append(
                f"duplicate evidence source id {source.source_id!r} is not allowed"
            )
        seen_source_ids.add(source.source_id)

    if validation_errors:
        return NotebookQuarantineReport(
            evaluation_id=request.evaluation_id,
            family_id=request.family_id,
            status=NotebookQuarantineStatus.INVALID,
            selection_admissible=False,
            promotion_admissible=False,
            quarantined_source_ids=(),
            admissible_source_ids=(),
            rejected_source_ids=(),
            covered_decision_record_ids=(),
            missing_decision_record_ids=(),
            check_results=(
                _check_result(
                    check_id="contract_validation",
                    passed=False,
                    reason_code="NOTEBOOK_QUARANTINE_CONTRACT_INVALID",
                    explanation="Notebook-quarantine contract validation failed.",
                    affected_source_ids=[],
                    context={"errors": tuple(validation_errors)},
                ),
            ),
        )

    quarantined_source_ids: set[str] = set()
    admissible_source_ids: set[str] = set()
    rejected_source_ids: set[str] = set()
    covered_decision_record_ids: set[str] = set()
    counted_gate_sources = [
        source
        for source in request.evidence_sources
        if source.usage in GATE_USAGES and source.counts_toward_gate
    ]

    disallowed_gate_sources: list[str] = []
    notebook_derived_gate_sources: list[str] = []
    invalid_batch_run_sources: list[str] = []
    invalid_policy_report_sources: list[str] = []

    for source in request.evidence_sources:
        if (
            source.source_kind == EvidenceSourceKind.NOTEBOOK_OUTPUT
            or source.produced_by_notebook
        ):
            quarantined_source_ids.add(source.source_id)

        if source.family_decision_record_id and source.counts_toward_gate:
            covered_decision_record_ids.add(source.family_decision_record_id)

        if source.usage not in GATE_USAGES or not source.counts_toward_gate:
            continue

        if source.source_kind not in ALLOWED_GATE_EVIDENCE_SOURCE_KINDS:
            disallowed_gate_sources.append(source.source_id)
            rejected_source_ids.add(source.source_id)
            continue

        if source.produced_by_notebook:
            notebook_derived_gate_sources.append(source.source_id)
            rejected_source_ids.add(source.source_id)
            continue

        if not source.canonical_reference_id:
            disallowed_gate_sources.append(source.source_id)
            rejected_source_ids.add(source.source_id)
            continue

        if source.source_kind == EvidenceSourceKind.REPRODUCIBLE_BATCH_RUN:
            if (
                source.reference_artifact_id != "research_run"
                or not source.research_run_id
                or source.research_admissibility_class not in GATE_ADMISSIBLE_RESEARCH_CLASSES
            ):
                invalid_batch_run_sources.append(source.source_id)
                rejected_source_ids.add(source.source_id)
                continue
            artifact_ok, _ = _artifact_is_admissible(source)
            if not artifact_ok:
                invalid_batch_run_sources.append(source.source_id)
                rejected_source_ids.add(source.source_id)
                continue

        if source.source_kind == EvidenceSourceKind.POLICY_EVALUATED_REPORT:
            if (
                source.reference_artifact_id != "family_decision_record"
                or not source.family_decision_record_id
            ):
                invalid_policy_report_sources.append(source.source_id)
                rejected_source_ids.add(source.source_id)
                continue
            artifact_ok, _ = _artifact_is_admissible(source)
            if not artifact_ok:
                invalid_policy_report_sources.append(source.source_id)
                rejected_source_ids.add(source.source_id)
                continue

        if source.source_kind == EvidenceSourceKind.CERTIFIED_RELEASE and source.reference_artifact_id:
            artifact_ok, _ = _artifact_is_admissible(source)
            if not artifact_ok:
                disallowed_gate_sources.append(source.source_id)
                rejected_source_ids.add(source.source_id)
                continue

        admissible_source_ids.add(source.source_id)

    selection_sources_present = any(
        source.usage == EvidenceUsage.SELECTION for source in request.evidence_sources
    )
    promotion_sources_present = any(
        source.usage == EvidenceUsage.PROMOTION for source in request.evidence_sources
    )
    selection_admissible = any(
        source.source_id in admissible_source_ids and source.usage == EvidenceUsage.SELECTION
        for source in request.evidence_sources
    )
    promotion_admissible = any(
        source.source_id in admissible_source_ids and source.usage == EvidenceUsage.PROMOTION
        for source in request.evidence_sources
    )

    gate_evidence_failures: list[str] = []
    if selection_sources_present and not selection_admissible:
        gate_evidence_failures.extend(
            [
                source.source_id
                for source in request.evidence_sources
                if source.usage == EvidenceUsage.SELECTION
            ]
        )
    if promotion_sources_present and not promotion_admissible:
        gate_evidence_failures.extend(
            [
                source.source_id
                for source in request.evidence_sources
                if source.usage == EvidenceUsage.PROMOTION
            ]
        )

    missing_decision_record_ids = sorted(
        set(request.required_decision_record_ids) - covered_decision_record_ids
    )

    check_results = (
        _check_result(
            check_id="gate_sources_require_non_notebook_admissible_evidence",
            passed=not gate_evidence_failures,
            reason_code=(
                None
                if not gate_evidence_failures
                else "NOTEBOOK_QUARANTINE_MISSING_ADMISSIBLE_GATE_EVIDENCE"
            ),
            explanation=(
                "Every selection or promotion context has at least one admissible non-notebook "
                "source counting toward the gate."
                if not gate_evidence_failures
                else "Selection or promotion context is missing admissible non-notebook gate evidence."
            ),
            affected_source_ids=sorted(set(gate_evidence_failures)),
            context={
                "selection_admissible": selection_admissible,
                "promotion_admissible": promotion_admissible,
                "counted_gate_source_ids": tuple(source.source_id for source in counted_gate_sources),
            },
        ),
        _check_result(
            check_id="gate_sources_use_allowed_origins",
            passed=not disallowed_gate_sources,
            reason_code=(
                None
                if not disallowed_gate_sources
                else "NOTEBOOK_QUARANTINE_DISALLOWED_GATE_SOURCE"
            ),
            explanation=(
                "All counted gate sources use allowed admissible origins."
                if not disallowed_gate_sources
                else "One or more counted gate sources use notebook outputs or otherwise "
                "disallowed origins."
            ),
            affected_source_ids=sorted(disallowed_gate_sources),
            context={"allowed_source_kinds": admissible_gate_source_kinds()},
        ),
        _check_result(
            check_id="notebook_derived_sources_cannot_count_toward_gate",
            passed=not notebook_derived_gate_sources,
            reason_code=(
                None
                if not notebook_derived_gate_sources
                else "NOTEBOOK_QUARANTINE_NOTEBOOK_DERIVATION_FORBIDDEN"
            ),
            explanation=(
                "No counted gate source is derived from notebook output."
                if not notebook_derived_gate_sources
                else "Notebook-derived artifacts may support explanation, but they cannot count "
                "as admissible gate evidence."
            ),
            affected_source_ids=sorted(notebook_derived_gate_sources),
            context={},
        ),
        _check_result(
            check_id="batch_runs_require_gate_admissible_research_state",
            passed=not invalid_batch_run_sources,
            reason_code=(
                None
                if not invalid_batch_run_sources
                else "NOTEBOOK_QUARANTINE_BATCH_RUN_NOT_GATE_ADMISSIBLE"
            ),
            explanation=(
                "All counted batch runs point to admissible research-run records."
                if not invalid_batch_run_sources
                else "Counted batch runs must reference a canonical research_run with a gate-"
                "admissible research class."
            ),
            affected_source_ids=sorted(invalid_batch_run_sources),
            context={
                "allowed_research_classes": tuple(
                    item.value for item in GATE_ADMISSIBLE_RESEARCH_CLASSES
                )
            },
        ),
        _check_result(
            check_id="policy_reports_require_family_decision_records",
            passed=not invalid_policy_report_sources,
            reason_code=(
                None
                if not invalid_policy_report_sources
                else "NOTEBOOK_QUARANTINE_POLICY_REPORT_MISSING_DECISION_RECORD"
            ),
            explanation=(
                "All counted policy-evaluated reports bind to canonical family_decision_record "
                "artifacts."
                if not invalid_policy_report_sources
                else "Counted policy-evaluated reports must bind to a canonical "
                "family_decision_record."
            ),
            affected_source_ids=sorted(invalid_policy_report_sources),
            context={},
        ),
        _check_result(
            check_id="required_decision_records_are_covered",
            passed=not missing_decision_record_ids,
            reason_code=(
                None
                if not missing_decision_record_ids
                else "NOTEBOOK_QUARANTINE_MISSING_REQUIRED_DECISION_RECORD"
            ),
            explanation=(
                "All required decision records are covered by counted admissible evidence."
                if not missing_decision_record_ids
                else "One or more required family decision records are not covered by counted "
                "admissible evidence."
            ),
            affected_source_ids=[],
            context={"missing_decision_record_ids": tuple(missing_decision_record_ids)},
        ),
    )

    status = (
        NotebookQuarantineStatus.PASS
        if all(result.passed for result in check_results)
        else NotebookQuarantineStatus.VIOLATION
    )
    return NotebookQuarantineReport(
        evaluation_id=request.evaluation_id,
        family_id=request.family_id,
        status=status,
        selection_admissible=selection_admissible,
        promotion_admissible=promotion_admissible,
        quarantined_source_ids=tuple(sorted(quarantined_source_ids)),
        admissible_source_ids=tuple(sorted(admissible_source_ids)),
        rejected_source_ids=tuple(sorted(rejected_source_ids)),
        covered_decision_record_ids=tuple(sorted(covered_decision_record_ids)),
        missing_decision_record_ids=tuple(missing_decision_record_ids),
        check_results=check_results,
    )
