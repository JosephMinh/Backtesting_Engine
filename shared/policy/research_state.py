"""Canonical research-state contracts for promotable batch runs and decisions."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum, unique

from shared.policy.artifact_classes import ArtifactClass, get_artifact_definition
from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.lifecycle_specs import (
    FAMILY_DECISION_MACHINE_ID,
    RESEARCH_RUN_MACHINE_ID,
    build_tuple_transition_map,
)
from shared.policy.metadata_telemetry import RECORD_DEFINITIONS, StorageClass


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_persisted_timestamp(value: str, *, field_name: str) -> str:
    try:
        normalized = canonicalize_persisted_timestamp(
            datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be timezone-aware and UTC-normalizable"
        ) from exc
    return normalized.isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of non-empty strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _require_mapping_sequence(value: object, *, field_name: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a sequence of objects")
    return tuple(
        _require_mapping(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )


def _require_enum_value(
    value: object,
    *,
    field_name: str,
    enum_type: type[Enum],
    description: str,
):
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a valid {description}")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid {description}") from exc


def _require_report_status(value: object, *, field_name: str) -> str:
    return _require_enum_value(
        value,
        field_name=field_name,
        enum_type=ResearchStateReportStatus,
        description="research-state report status",
    ).value


def _coerce_budget_value(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be finite and non-negative")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be finite and non-negative") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return parsed


def _coerce_seed_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("seed values must be explicit integers")
    return value


@unique
class ResearchRunPurpose(str, Enum):
    SCREENING = "screening"
    VALIDATION = "validation"
    STRESS = "stress"
    OMISSION = "omission"
    PORTABILITY = "portability"
    NATIVE_VALIDATION = "native_validation"
    TRADABILITY = "tradability"
    LOCKBOX = "lockbox"


@unique
class ResearchAdmissibilityClass(str, Enum):
    DIAGNOSTIC_ONLY = "diagnostic_only"
    EXECUTION_CALIBRATION_ADMISSIBLE = "execution_calibration_admissible"
    RISK_POLICY_ADMISSIBLE = "risk_policy_admissible"
    INCIDENT_REVIEW_ONLY = "incident_review_only"


@unique
class ResearchRunLifecycle(str, Enum):
    RECORDED = "recorded"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    REVOKED = "revoked"


@unique
class FamilyDecisionType(str, Enum):
    CONTINUE = "continue"
    PAUSE = "pause"
    PIVOT = "pivot"
    TERMINATE = "terminate"


@unique
class FamilyDecisionLifecycle(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


@unique
class ResearchStateReportStatus(str, Enum):
    PASS = "pass"
    INVALID = "invalid"
    VIOLATION = "violation"


@dataclass(frozen=True)
class ReviewerAttestation:
    reviewer_id: str
    attested_controls: tuple[str, ...]
    signed_at_utc: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "signed_at_utc",
            _normalize_persisted_timestamp(
                self.signed_at_utc,
                field_name="signed_at_utc",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "reviewer_id": self.reviewer_id,
            "attested_controls": list(self.attested_controls),
            "signed_at_utc": self.signed_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ReviewerAttestation:
        payload = _require_mapping(payload, field_name="reviewer_attestation")
        return cls(
            reviewer_id=_require_non_empty_string(payload["reviewer_id"], field_name="reviewer_id"),
            attested_controls=_require_string_sequence(
                payload["attested_controls"],
                field_name="attested_controls",
            ),
            signed_at_utc=_require_non_empty_string(
                payload["signed_at_utc"],
                field_name="signed_at_utc",
            ),
        )


@dataclass(frozen=True)
class ResearchRunRecord:
    research_run_id: str
    family_id: str
    subfamily_id: str
    run_purpose: ResearchRunPurpose
    code_digests: tuple[str, ...]
    environment_lock_id: str
    dataset_release_id: str
    analytic_release_id: str
    data_profile_release_id: str
    execution_profile_id: str
    parameter_reference_id: str
    seeds: tuple[int, ...]
    policy_bundle_hash: str
    compatibility_matrix_version: str
    output_artifact_digests: tuple[str, ...]
    admissibility_class: ResearchAdmissibilityClass
    parent_run_ids: tuple[str, ...] = ()
    lifecycle_state: ResearchRunLifecycle = ResearchRunLifecycle.RECORDED
    created_at_utc: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "created_at_utc",
            _normalize_persisted_timestamp(
                self.created_at_utc,
                field_name="created_at_utc",
            ),
        )
        object.__setattr__(
            self,
            "seeds",
            tuple(_coerce_seed_value(seed) for seed in self.seeds),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "research_run_id": self.research_run_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "run_purpose": self.run_purpose.value,
            "code_digests": list(self.code_digests),
            "environment_lock_id": self.environment_lock_id,
            "dataset_release_id": self.dataset_release_id,
            "analytic_release_id": self.analytic_release_id,
            "data_profile_release_id": self.data_profile_release_id,
            "execution_profile_id": self.execution_profile_id,
            "parameter_reference_id": self.parameter_reference_id,
            "seeds": list(self.seeds),
            "policy_bundle_hash": self.policy_bundle_hash,
            "compatibility_matrix_version": self.compatibility_matrix_version,
            "output_artifact_digests": list(self.output_artifact_digests),
            "admissibility_class": self.admissibility_class.value,
            "parent_run_ids": list(self.parent_run_ids),
            "lifecycle_state": self.lifecycle_state.value,
            "created_at_utc": self.created_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ResearchRunRecord:
        payload = _require_mapping(payload, field_name="research_run_record")
        return cls(
            research_run_id=_require_non_empty_string(
                payload["research_run_id"],
                field_name="research_run_id",
            ),
            family_id=_require_non_empty_string(payload["family_id"], field_name="family_id"),
            subfamily_id=_require_non_empty_string(
                payload["subfamily_id"],
                field_name="subfamily_id",
            ),
            run_purpose=_require_enum_value(
                payload["run_purpose"],
                field_name="run_purpose",
                enum_type=ResearchRunPurpose,
                description="research run purpose",
            ),
            code_digests=_require_string_sequence(
                payload["code_digests"],
                field_name="code_digests",
            ),
            environment_lock_id=_require_non_empty_string(
                payload["environment_lock_id"],
                field_name="environment_lock_id",
            ),
            dataset_release_id=_require_non_empty_string(
                payload["dataset_release_id"],
                field_name="dataset_release_id",
            ),
            analytic_release_id=_require_non_empty_string(
                payload["analytic_release_id"],
                field_name="analytic_release_id",
            ),
            data_profile_release_id=_require_non_empty_string(
                payload["data_profile_release_id"],
                field_name="data_profile_release_id",
            ),
            execution_profile_id=_require_non_empty_string(
                payload["execution_profile_id"],
                field_name="execution_profile_id",
            ),
            parameter_reference_id=_require_non_empty_string(
                payload["parameter_reference_id"],
                field_name="parameter_reference_id",
            ),
            seeds=tuple(_coerce_seed_value(item) for item in payload["seeds"]),
            policy_bundle_hash=_require_non_empty_string(
                payload["policy_bundle_hash"],
                field_name="policy_bundle_hash",
            ),
            compatibility_matrix_version=_require_non_empty_string(
                payload["compatibility_matrix_version"],
                field_name="compatibility_matrix_version",
            ),
            output_artifact_digests=_require_string_sequence(
                payload["output_artifact_digests"],
                field_name="output_artifact_digests",
            ),
            admissibility_class=_require_enum_value(
                payload["admissibility_class"],
                field_name="admissibility_class",
                enum_type=ResearchAdmissibilityClass,
                description="research admissibility class",
            ),
            parent_run_ids=_require_string_sequence(
                payload["parent_run_ids"],
                field_name="parent_run_ids",
            ),
            lifecycle_state=_require_enum_value(
                payload["lifecycle_state"],
                field_name="lifecycle_state",
                enum_type=ResearchRunLifecycle,
                description="research run lifecycle",
            ),
            created_at_utc=_require_non_empty_string(
                payload["created_at_utc"],
                field_name="created_at_utc",
            ),
        )


@dataclass(frozen=True)
class FamilyDecisionRecord:
    decision_record_id: str
    family_id: str
    decision_timestamp_utc: str
    decision_type: FamilyDecisionType
    evidence_references: tuple[str, ...]
    budget_consumed_usd: float
    next_budget_authorized_usd: float
    reviewer_self_attestations: tuple[ReviewerAttestation, ...]
    reason_bundle: tuple[str, ...]
    revisit_at_utc: str | None = None
    lifecycle_state: FamilyDecisionLifecycle = FamilyDecisionLifecycle.ACTIVE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "decision_timestamp_utc",
            _normalize_persisted_timestamp(
                self.decision_timestamp_utc,
                field_name="decision_timestamp_utc",
            ),
        )
        if self.revisit_at_utc is not None:
            object.__setattr__(
                self,
                "revisit_at_utc",
                _normalize_persisted_timestamp(
                    self.revisit_at_utc,
                    field_name="revisit_at_utc",
                ),
            )
        for field_name in ("budget_consumed_usd", "next_budget_authorized_usd"):
            object.__setattr__(
                self,
                field_name,
                _coerce_budget_value(getattr(self, field_name), field_name=field_name),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_record_id": self.decision_record_id,
            "family_id": self.family_id,
            "decision_timestamp_utc": self.decision_timestamp_utc,
            "decision_type": self.decision_type.value,
            "evidence_references": list(self.evidence_references),
            "budget_consumed_usd": self.budget_consumed_usd,
            "next_budget_authorized_usd": self.next_budget_authorized_usd,
            "reviewer_self_attestations": [
                item.to_dict() for item in self.reviewer_self_attestations
            ],
            "reason_bundle": list(self.reason_bundle),
            "revisit_at_utc": self.revisit_at_utc,
            "lifecycle_state": self.lifecycle_state.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FamilyDecisionRecord:
        payload = _require_mapping(payload, field_name="family_decision_record")
        return cls(
            decision_record_id=_require_non_empty_string(
                payload["decision_record_id"],
                field_name="decision_record_id",
            ),
            family_id=_require_non_empty_string(payload["family_id"], field_name="family_id"),
            decision_timestamp_utc=_require_non_empty_string(
                payload["decision_timestamp_utc"],
                field_name="decision_timestamp_utc",
            ),
            decision_type=_require_enum_value(
                payload["decision_type"],
                field_name="decision_type",
                enum_type=FamilyDecisionType,
                description="family decision type",
            ),
            evidence_references=_require_string_sequence(
                payload["evidence_references"],
                field_name="evidence_references",
            ),
            budget_consumed_usd=_coerce_budget_value(
                payload["budget_consumed_usd"],
                field_name="budget_consumed_usd",
            ),
            next_budget_authorized_usd=_coerce_budget_value(
                payload["next_budget_authorized_usd"],
                field_name="next_budget_authorized_usd",
            ),
            reviewer_self_attestations=tuple(
                ReviewerAttestation.from_dict(item)
                for item in _require_mapping_sequence(
                    payload["reviewer_self_attestations"],
                    field_name="reviewer_self_attestations",
                )
            ),
            reason_bundle=_require_string_sequence(
                payload["reason_bundle"],
                field_name="reason_bundle",
            ),
            revisit_at_utc=_require_optional_non_empty_string(
                payload["revisit_at_utc"],
                field_name="revisit_at_utc",
            ),
            lifecycle_state=_require_enum_value(
                payload["lifecycle_state"],
                field_name="lifecycle_state",
                enum_type=FamilyDecisionLifecycle,
                description="family decision lifecycle",
            ),
        )


@dataclass(frozen=True)
class ResearchStateMutationReport:
    record_type: str
    record_id: str
    operation: str
    status: str
    reason_code: str
    previous_state: str | None
    next_state: str | None
    explanation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "record_type": self.record_type,
            "record_id": self.record_id,
            "operation": self.operation,
            "status": self.status,
            "reason_code": self.reason_code,
            "previous_state": self.previous_state,
            "next_state": self.next_state,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ResearchStateMutationReport:
        payload = _require_mapping(payload, field_name="research_state_mutation_report")
        return cls(
            record_type=_require_non_empty_string(payload["record_type"], field_name="record_type"),
            record_id=_require_non_empty_string(payload["record_id"], field_name="record_id"),
            operation=_require_non_empty_string(payload["operation"], field_name="operation"),
            status=_require_report_status(payload["status"], field_name="status"),
            reason_code=_require_non_empty_string(payload["reason_code"], field_name="reason_code"),
            previous_state=_require_optional_non_empty_string(
                payload["previous_state"],
                field_name="previous_state",
            ),
            next_state=_require_optional_non_empty_string(
                payload["next_state"],
                field_name="next_state",
            ),
            explanation=_require_non_empty_string(
                payload["explanation"],
                field_name="explanation",
            ),
            timestamp=_normalize_persisted_timestamp(
                payload["timestamp"],
                field_name="timestamp",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class EvidenceChainReport:
    decision_record_id: str
    status: str
    reason_code: str
    family_id: str
    referenced_run_ids: tuple[str, ...]
    missing_run_ids: tuple[str, ...]
    foreign_family_run_ids: tuple[str, ...]
    duplicate_references: tuple[str, ...]
    explanation: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_record_id": self.decision_record_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "family_id": self.family_id,
            "referenced_run_ids": list(self.referenced_run_ids),
            "missing_run_ids": list(self.missing_run_ids),
            "foreign_family_run_ids": list(self.foreign_family_run_ids),
            "duplicate_references": list(self.duplicate_references),
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class ResearchStateStore:
    research_runs: dict[str, ResearchRunRecord] = field(default_factory=dict)
    family_decision_records: dict[str, FamilyDecisionRecord] = field(default_factory=dict)
    audit_log: list[ResearchStateMutationReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "research_runs": {
                run_id: record.to_dict()
                for run_id, record in self.research_runs.items()
            },
            "family_decision_records": {
                record_id: record.to_dict()
                for record_id, record in self.family_decision_records.items()
            },
            "audit_log": [event.to_dict() for event in self.audit_log],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ResearchStateStore:
        payload = _require_mapping(payload, field_name="research_state_store")
        store = cls()
        store.research_runs = {
            _require_non_empty_string(run_id, field_name="research_runs key"): ResearchRunRecord.from_dict(
                _require_mapping(record, field_name=f"research_runs[{run_id}]")
            )
            for run_id, record in _require_mapping(
                payload["research_runs"],
                field_name="research_runs",
            ).items()
        }
        store.family_decision_records = {
            _require_non_empty_string(
                record_id,
                field_name="family_decision_records key",
            ): FamilyDecisionRecord.from_dict(
                _require_mapping(record, field_name=f"family_decision_records[{record_id}]")
            )
            for record_id, record in _require_mapping(
                payload["family_decision_records"],
                field_name="family_decision_records",
            ).items()
        }
        store.audit_log = [
            ResearchStateMutationReport.from_dict(item)
            for item in _require_mapping_sequence(
                payload["audit_log"],
                field_name="audit_log",
            )
        ]
        return store

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


_ALLOWED_RUN_TRANSITIONS: dict[ResearchRunLifecycle, tuple[ResearchRunLifecycle, ...]] = (
    build_tuple_transition_map(RESEARCH_RUN_MACHINE_ID, ResearchRunLifecycle)
)

_ALLOWED_DECISION_TRANSITIONS: dict[
    FamilyDecisionLifecycle, tuple[FamilyDecisionLifecycle, ...]
] = build_tuple_transition_map(FAMILY_DECISION_MACHINE_ID, FamilyDecisionLifecycle)


def _record_audit(
    store: ResearchStateStore, report: ResearchStateMutationReport
) -> ResearchStateMutationReport:
    store.audit_log.append(report)
    return report


def research_runs_for_family(
    store: ResearchStateStore, family_id: str
) -> tuple[ResearchRunRecord, ...]:
    return tuple(
        sorted(
            (
                record
                for record in store.research_runs.values()
                if record.family_id == family_id
            ),
            key=lambda record: (record.created_at_utc, record.research_run_id),
        )
    )


def family_decisions_for_family(
    store: ResearchStateStore, family_id: str
) -> tuple[FamilyDecisionRecord, ...]:
    return tuple(
        sorted(
            (
                record
                for record in store.family_decision_records.values()
                if record.family_id == family_id
            ),
            key=lambda record: (record.decision_timestamp_utc, record.decision_record_id),
        )
    )


def audit_events_for_record(
    store: ResearchStateStore, record_type: str, record_id: str
) -> tuple[ResearchStateMutationReport, ...]:
    return tuple(
        event
        for event in store.audit_log
        if event.record_type == record_type and event.record_id == record_id
    )


def child_run_ids(store: ResearchStateStore, research_run_id: str) -> tuple[str, ...]:
    return tuple(
        record.research_run_id
        for record in sorted(
            (
                record
                for record in store.research_runs.values()
                if research_run_id in record.parent_run_ids
            ),
            key=lambda record: (record.created_at_utc, record.research_run_id),
        )
    )


def _validate_parent_runs(
    store: ResearchStateStore, record: ResearchRunRecord
) -> ResearchStateMutationReport | None:
    if not record.seeds:
        return ResearchStateMutationReport(
            record_type="research_run",
            record_id=record.research_run_id,
            operation="create",
            status="invalid",
            reason_code="RESEARCH_RUN_MISSING_SEEDS",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="research_run must declare at least one deterministic seed.",
        )
    if not record.output_artifact_digests:
        return ResearchStateMutationReport(
            record_type="research_run",
            record_id=record.research_run_id,
            operation="create",
            status="invalid",
            reason_code="RESEARCH_RUN_MISSING_OUTPUT_ARTIFACTS",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="research_run must retain output artifact digests for promotable batch outputs.",
        )
    if not record.code_digests:
        return ResearchStateMutationReport(
            record_type="research_run",
            record_id=record.research_run_id,
            operation="create",
            status="invalid",
            reason_code="RESEARCH_RUN_MISSING_CODE_DIGESTS",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="research_run must capture code digests for reproducibility.",
        )
    for parent_run_id in record.parent_run_ids:
        parent = store.research_runs.get(parent_run_id)
        if parent is None:
            return ResearchStateMutationReport(
                record_type="research_run",
                record_id=record.research_run_id,
                operation="create",
                status="invalid",
                reason_code="RESEARCH_RUN_PARENT_MISSING",
                previous_state=None,
                next_state=record.lifecycle_state.value,
                explanation=(
                    f"research_run lineage references missing parent run {parent_run_id}."
                ),
            )
        if parent.family_id != record.family_id:
            return ResearchStateMutationReport(
                record_type="research_run",
                record_id=record.research_run_id,
                operation="create",
                status="invalid",
                reason_code="RESEARCH_RUN_PARENT_FOREIGN_FAMILY",
                previous_state=None,
                next_state=record.lifecycle_state.value,
                explanation=(
                    f"research_run lineage references parent {parent_run_id} from another family."
                ),
            )
    return None


def record_research_run(
    store: ResearchStateStore, record: ResearchRunRecord
) -> ResearchStateMutationReport:
    if record.research_run_id in store.research_runs:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="research_run",
                record_id=record.research_run_id,
                operation="create",
                status="invalid",
                reason_code="RESEARCH_RUN_DUPLICATE_ID",
                previous_state=None,
                next_state=record.lifecycle_state.value,
                explanation="research_run identifiers must be unique.",
            ),
        )

    validation = _validate_parent_runs(store, record)
    if validation is not None:
        return _record_audit(store, validation)

    store.research_runs[record.research_run_id] = record
    return _record_audit(
        store,
        ResearchStateMutationReport(
            record_type="research_run",
            record_id=record.research_run_id,
            operation="create",
            status="pass",
            reason_code="RESEARCH_RUN_RECORDED",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation=(
                "research_run recorded with promotable execution context, dependencies, seeds, and outputs."
            ),
        ),
    )


def transition_research_run(
    store: ResearchStateStore,
    research_run_id: str,
    next_state: ResearchRunLifecycle,
) -> ResearchStateMutationReport:
    record = store.research_runs.get(research_run_id)
    if record is None:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="research_run",
                record_id=research_run_id,
                operation="transition",
                status="invalid",
                reason_code="RESEARCH_RUN_NOT_FOUND",
                previous_state=None,
                next_state=next_state.value,
                explanation="research_run must exist before lifecycle transitions can be applied.",
            ),
        )

    if next_state not in _ALLOWED_RUN_TRANSITIONS[record.lifecycle_state]:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="research_run",
                record_id=research_run_id,
                operation="transition",
                status="invalid",
                reason_code="RESEARCH_RUN_INVALID_TRANSITION",
                previous_state=record.lifecycle_state.value,
                next_state=next_state.value,
                explanation=(
                    f"research_run cannot transition from {record.lifecycle_state.value} to {next_state.value}."
                ),
            ),
        )

    store.research_runs[research_run_id] = replace(record, lifecycle_state=next_state)
    return _record_audit(
        store,
        ResearchStateMutationReport(
            record_type="research_run",
            record_id=research_run_id,
            operation="transition",
            status="pass",
            reason_code="RESEARCH_RUN_TRANSITION_APPLIED",
            previous_state=record.lifecycle_state.value,
            next_state=next_state.value,
            explanation="research_run lifecycle transition recorded.",
        ),
    )


def _evidence_chain_report(
    store: ResearchStateStore,
    *,
    decision_record_id: str,
    family_id: str,
    evidence_references: tuple[str, ...],
) -> EvidenceChainReport:
    missing_run_ids: list[str] = []
    foreign_family_run_ids: list[str] = []
    duplicate_references = sorted(
        {
            run_id
            for run_id in evidence_references
            if evidence_references.count(run_id) > 1
        }
    )

    for run_id in evidence_references:
        run = store.research_runs.get(run_id)
        if run is None:
            missing_run_ids.append(run_id)
        elif run.family_id != family_id:
            foreign_family_run_ids.append(run_id)

    if missing_run_ids:
        return EvidenceChainReport(
            decision_record_id=decision_record_id,
            status="violation",
            reason_code="FAMILY_DECISION_EVIDENCE_RUN_MISSING",
            family_id=family_id,
            referenced_run_ids=evidence_references,
            missing_run_ids=tuple(missing_run_ids),
            foreign_family_run_ids=tuple(foreign_family_run_ids),
            duplicate_references=tuple(duplicate_references),
            explanation="family_decision_record references missing research_run artifacts.",
        )
    if foreign_family_run_ids:
        return EvidenceChainReport(
            decision_record_id=decision_record_id,
            status="violation",
            reason_code="FAMILY_DECISION_EVIDENCE_FOREIGN_FAMILY",
            family_id=family_id,
            referenced_run_ids=evidence_references,
            missing_run_ids=tuple(missing_run_ids),
            foreign_family_run_ids=tuple(foreign_family_run_ids),
            duplicate_references=tuple(duplicate_references),
            explanation="family_decision_record references research_run artifacts from another family.",
        )
    if duplicate_references:
        return EvidenceChainReport(
            decision_record_id=decision_record_id,
            status="violation",
            reason_code="FAMILY_DECISION_EVIDENCE_DUPLICATE_REFERENCE",
            family_id=family_id,
            referenced_run_ids=evidence_references,
            missing_run_ids=tuple(missing_run_ids),
            foreign_family_run_ids=tuple(foreign_family_run_ids),
            duplicate_references=tuple(duplicate_references),
            explanation="family_decision_record contains duplicate evidence references.",
        )

    return EvidenceChainReport(
        decision_record_id=decision_record_id,
        status="pass",
        reason_code="FAMILY_DECISION_EVIDENCE_CHAIN_VALID",
        family_id=family_id,
        referenced_run_ids=evidence_references,
        missing_run_ids=(),
        foreign_family_run_ids=(),
        duplicate_references=(),
        explanation="family_decision_record references exactly the research_run artifacts it evaluated.",
    )


def validate_decision_evidence_chain(
    store: ResearchStateStore, decision_record_id: str
) -> EvidenceChainReport:
    decision = store.family_decision_records[decision_record_id]
    return _evidence_chain_report(
        store,
        decision_record_id=decision.decision_record_id,
        family_id=decision.family_id,
        evidence_references=decision.evidence_references,
    )


def _validate_decision_policy(
    store: ResearchStateStore, record: FamilyDecisionRecord
) -> ResearchStateMutationReport | None:
    if not record.evidence_references:
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code="FAMILY_DECISION_MISSING_EVIDENCE",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="family_decision_record must reference at least one research_run.",
        )
    if not record.reviewer_self_attestations:
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code="FAMILY_DECISION_MISSING_ATTESTATION",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="family_decision_record must retain reviewer self-attestations.",
        )
    if not record.reason_bundle:
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code="FAMILY_DECISION_MISSING_REASON_BUNDLE",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="family_decision_record must retain queryable reasons for the decision.",
        )
    if record.decision_type == FamilyDecisionType.TERMINATE:
        if record.next_budget_authorized_usd != 0:
            return ResearchStateMutationReport(
                record_type="family_decision_record",
                record_id=record.decision_record_id,
                operation="create",
                status="invalid",
                reason_code="FAMILY_DECISION_TERMINATE_REQUIRES_ZERO_BUDGET",
                previous_state=None,
                next_state=record.lifecycle_state.value,
                explanation="terminate decisions must authorize zero additional budget.",
            )
    elif record.next_budget_authorized_usd <= 0:
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code="FAMILY_DECISION_NON_TERMINAL_REQUIRES_BUDGET",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="continue, pause, or pivot decisions must authorize a positive next budget.",
        )
    if record.decision_type == FamilyDecisionType.PAUSE and record.revisit_at_utc is None:
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code="FAMILY_DECISION_PAUSE_REQUIRES_REVISIT",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation="pause decisions must declare a revisit timestamp.",
        )
    chain_report = _evidence_chain_report(
        store,
        decision_record_id=record.decision_record_id,
        family_id=record.family_id,
        evidence_references=record.evidence_references,
    )
    if chain_report.status != "pass":
        return ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="invalid",
            reason_code=chain_report.reason_code,
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation=chain_report.explanation,
        )
    return None


def record_family_decision(
    store: ResearchStateStore, record: FamilyDecisionRecord
) -> ResearchStateMutationReport:
    if record.decision_record_id in store.family_decision_records:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="family_decision_record",
                record_id=record.decision_record_id,
                operation="create",
                status="invalid",
                reason_code="FAMILY_DECISION_DUPLICATE_ID",
                previous_state=None,
                next_state=record.lifecycle_state.value,
                explanation="family_decision_record identifiers must be unique.",
            ),
        )

    validation = _validate_decision_policy(store, record)
    if validation is not None:
        return _record_audit(store, validation)

    store.family_decision_records[record.decision_record_id] = record
    return _record_audit(
        store,
        ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=record.decision_record_id,
            operation="create",
            status="pass",
            reason_code="FAMILY_DECISION_RECORDED",
            previous_state=None,
            next_state=record.lifecycle_state.value,
            explanation=(
                "family_decision_record recorded with evidence references, budget context, and reviewer attestations."
            ),
        ),
    )


def transition_family_decision(
    store: ResearchStateStore,
    decision_record_id: str,
    next_state: FamilyDecisionLifecycle,
) -> ResearchStateMutationReport:
    record = store.family_decision_records.get(decision_record_id)
    if record is None:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="family_decision_record",
                record_id=decision_record_id,
                operation="transition",
                status="invalid",
                reason_code="FAMILY_DECISION_NOT_FOUND",
                previous_state=None,
                next_state=next_state.value,
                explanation="family_decision_record must exist before lifecycle transitions can be applied.",
            ),
        )

    if next_state not in _ALLOWED_DECISION_TRANSITIONS[record.lifecycle_state]:
        return _record_audit(
            store,
            ResearchStateMutationReport(
                record_type="family_decision_record",
                record_id=decision_record_id,
                operation="transition",
                status="invalid",
                reason_code="FAMILY_DECISION_INVALID_TRANSITION",
                previous_state=record.lifecycle_state.value,
                next_state=next_state.value,
                explanation=(
                    f"family_decision_record cannot transition from {record.lifecycle_state.value} to {next_state.value}."
                ),
            ),
        )

    store.family_decision_records[decision_record_id] = replace(
        record, lifecycle_state=next_state
    )
    return _record_audit(
        store,
        ResearchStateMutationReport(
            record_type="family_decision_record",
            record_id=decision_record_id,
            operation="transition",
            status="pass",
            reason_code="FAMILY_DECISION_TRANSITION_APPLIED",
            previous_state=record.lifecycle_state.value,
            next_state=next_state.value,
            explanation="family_decision_record lifecycle transition recorded.",
        ),
    )


def validate_research_state_contract() -> list[str]:
    errors: list[str] = []

    metadata_index = {definition.record_id: definition for definition in RECORD_DEFINITIONS}
    for record_id in ("research_run", "family_decision_record"):
        metadata_record = metadata_index.get(record_id)
        if metadata_record is None:
            errors.append(f"{record_id}: missing from canonical metadata registry")
            continue
        if metadata_record.storage_class != StorageClass.CANONICAL_METADATA:
            errors.append(f"{record_id}: must remain canonical metadata")
        artifact_definition = get_artifact_definition(record_id)
        if artifact_definition.artifact_class != ArtifactClass.INTEGRITY_BOUND:
            errors.append(f"{record_id}: must remain integrity-bound")

    return errors


VALIDATION_ERRORS = validate_research_state_contract()
