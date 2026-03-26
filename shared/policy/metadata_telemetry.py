"""Canonical metadata versus dense telemetry contract.

This module encodes the plan-level rule that records of truth remain durable
and queryable even if dense telemetry retention, storage, or sampling evolves.
It also makes replay/promotion applicability explicit so future schema work can
assert that no required operational state lives only in telemetry series.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class StorageClass(str, Enum):
    CANONICAL_METADATA = "canonical_metadata"
    DENSE_TELEMETRY = "dense_telemetry"


class FieldClass(str, Enum):
    STATE_OF_TRUTH = "state_of_truth"
    CANONICAL_REFERENCE = "canonical_reference"
    TELEMETRY_ONLY = "telemetry_only"


class LifecycleNeed(str, Enum):
    REPLAY = "replay"
    PROMOTION = "promotion"


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    field_class: FieldClass
    description: str
    required_for: tuple[LifecycleNeed, ...] = ()


@dataclass(frozen=True)
class RecordDefinition:
    record_id: str
    title: str
    storage_class: StorageClass
    plan_section: str
    description: str
    queryable_when_telemetry_pruned: bool
    durable_when_telemetry_pruned: bool
    retention_independent: bool
    fields: tuple[FieldDefinition, ...]


@dataclass(frozen=True)
class ClassificationReport:
    record_id: str
    storage_class: str
    plan_section: str
    queryable_when_telemetry_pruned: bool
    durable_when_telemetry_pruned: bool
    retention_independent: bool
    field_classification: dict[str, str]
    replay_fields: tuple[str, ...]
    promotion_fields: tuple[str, ...]
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class DerivabilityReport:
    record_id: str
    storage_class: str
    replay_applicable: bool
    replay_state_derived_from_canonical: bool
    promotion_applicable: bool
    promotion_state_derived_from_canonical: bool
    offending_fields: tuple[str, ...]
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _field(
    name: str,
    field_class: FieldClass,
    description: str,
    *required_for: LifecycleNeed,
) -> FieldDefinition:
    return FieldDefinition(
        name=name,
        field_class=field_class,
        description=description,
        required_for=required_for,
    )


RECORD_DEFINITIONS: tuple[RecordDefinition, ...] = (
    RecordDefinition(
        record_id="research_run",
        title="Research run",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Canonical research execution context and release bindings.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("research_run_id", FieldClass.STATE_OF_TRUTH, "Stable research run identifier."),
            _field(
                "strategy_family_id",
                FieldClass.STATE_OF_TRUTH,
                "Strategy family under evaluation.",
                LifecycleNeed.REPLAY,
            ),
            _field(
                "data_profile_release_id",
                FieldClass.STATE_OF_TRUTH,
                "Frozen data profile release used by the run.",
                LifecycleNeed.REPLAY,
            ),
            _field(
                "signal_kernel_release_id",
                FieldClass.STATE_OF_TRUTH,
                "Canonical kernel release bound to the run.",
                LifecycleNeed.REPLAY,
            ),
            _field(
                "parameter_set_digest",
                FieldClass.STATE_OF_TRUTH,
                "Frozen parameter bundle digest.",
                LifecycleNeed.REPLAY,
            ),
            _field(
                "artifact_manifest_id",
                FieldClass.CANONICAL_REFERENCE,
                "Manifest tying the run to immutable artifacts.",
                LifecycleNeed.REPLAY,
            ),
        ),
    ),
    RecordDefinition(
        record_id="family_decision_record",
        title="Family decision record",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Governed decision on which strategy family advances or is rejected.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("decision_record_id", FieldClass.STATE_OF_TRUTH, "Stable family decision identifier."),
            _field("strategy_family_id", FieldClass.STATE_OF_TRUTH, "Family being decided."),
            _field("decision_outcome", FieldClass.STATE_OF_TRUTH, "Decision result and lane."),
            _field(
                "supporting_research_run_id",
                FieldClass.CANONICAL_REFERENCE,
                "Canonical run that produced the decision evidence.",
            ),
            _field("policy_id", FieldClass.CANONICAL_REFERENCE, "Policy snapshot governing the decision."),
        ),
    ),
    RecordDefinition(
        record_id="release_manifest",
        title="Release manifest",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Frozen manifest of immutable artifacts and compatibility inputs.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("release_id", FieldClass.STATE_OF_TRUTH, "Stable release identifier."),
            _field(
                "artifact_digest_set",
                FieldClass.STATE_OF_TRUTH,
                "Immutable artifact digests for reproducibility.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "compatibility_matrix_id",
                FieldClass.CANONICAL_REFERENCE,
                "Compatibility contract covering dependent surfaces.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "frozen_at_utc",
                FieldClass.STATE_OF_TRUTH,
                "UTC freeze timestamp for release immutability.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="release_certification",
        title="Release certification",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.11",
        description="Signed certification record that makes a release usable.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field(
                "certification_id",
                FieldClass.STATE_OF_TRUTH,
                "Stable certification identifier.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "release_id",
                FieldClass.STATE_OF_TRUTH,
                "Certified release identifier.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "release_kind",
                FieldClass.STATE_OF_TRUTH,
                "Canonical release kind for the certified object.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "deterministic_manifest_hash",
                FieldClass.CANONICAL_REFERENCE,
                "Hash of the deterministic build manifest used for certification.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "prior_release_semantic_diff_hash",
                FieldClass.CANONICAL_REFERENCE,
                "Hash of the semantic diff against the prior release.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "validation_summary_hash",
                FieldClass.CANONICAL_REFERENCE,
                "Hash of the release validation summary bundled with certification.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "signed_certification_report_hash",
                FieldClass.CANONICAL_REFERENCE,
                "Hash of the signed certification report.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="release_correction_event",
        title="Release correction event",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.11",
        description="Policy-classified correction or restatement event against a certified release.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field(
                "correction_event_id",
                FieldClass.STATE_OF_TRUTH,
                "Stable correction event identifier.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "release_id",
                FieldClass.STATE_OF_TRUTH,
                "Certified release affected by the correction event.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "certified_vendor_revision_watermark",
                FieldClass.STATE_OF_TRUTH,
                "Vendor watermark that was current when the release was certified.",
                LifecycleNeed.REPLAY,
            ),
            _field(
                "corrected_vendor_revision_watermark",
                FieldClass.STATE_OF_TRUTH,
                "Vendor watermark that triggered the correction event.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "semantic_impact_diff_hash",
                FieldClass.CANONICAL_REFERENCE,
                "Hash of the semantic impact diff for the correction.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "impact_class",
                FieldClass.STATE_OF_TRUTH,
                "Policy impact classification for the correction event.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "superseding_release_id",
                FieldClass.CANONICAL_REFERENCE,
                "Superseding release id when the correction results in explicit replacement.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="candidate_bundle",
        title="Candidate bundle",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Immutable deployment-grade candidate bundle and its frozen bindings.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("candidate_bundle_id", FieldClass.STATE_OF_TRUTH, "Stable candidate bundle identifier."),
            _field(
                "signal_kernel_digest",
                FieldClass.STATE_OF_TRUTH,
                "Digest of the approved signal kernel.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "resolved_context_bundle_id",
                FieldClass.CANONICAL_REFERENCE,
                "Frozen context bundle bound into the candidate.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "execution_profile_release_id",
                FieldClass.STATE_OF_TRUTH,
                "Execution-profile release approved for the candidate.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "compatibility_matrix_version",
                FieldClass.STATE_OF_TRUTH,
                "Compatibility matrix version frozen into the candidate bundle.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="bundle_readiness_record",
        title="Bundle readiness record",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Mutable readiness state for one candidate bundle in one account context.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field(
                "bundle_readiness_record_id",
                FieldClass.STATE_OF_TRUTH,
                "Stable bundle-readiness record identifier.",
            ),
            _field(
                "candidate_bundle_id",
                FieldClass.CANONICAL_REFERENCE,
                "Candidate bundle being qualified.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "target_account_binding_id",
                FieldClass.STATE_OF_TRUTH,
                "Concrete account binding owned by the readiness layer.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "approved_data_profile_release_id",
                FieldClass.STATE_OF_TRUTH,
                "Approved current data-profile binding for this readiness context.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "policy_bundle_hash",
                FieldClass.STATE_OF_TRUTH,
                "Policy bundle hash governing the readiness state.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "operator_signoff_id",
                FieldClass.CANONICAL_REFERENCE,
                "Operator review package or approval record.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="deployment_instance",
        title="Deployment instance",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Mutable activation record for one paper, shadow-live, or live deployment.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field(
                "deployment_instance_id",
                FieldClass.STATE_OF_TRUTH,
                "Stable deployment instance identifier.",
            ),
            _field(
                "candidate_bundle_id",
                FieldClass.CANONICAL_REFERENCE,
                "Candidate bundle loaded into the deployment.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "bundle_readiness_record_id",
                FieldClass.CANONICAL_REFERENCE,
                "Readiness record authorizing the deployment context.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "promotion_packet_id",
                FieldClass.CANONICAL_REFERENCE,
                "Promotion packet currently authorizing execution.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "deployment_state",
                FieldClass.STATE_OF_TRUTH,
                "Mutable lifecycle state of the deployment instance.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="promotion_packet",
        title="Promotion packet",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Operator-facing packet that promotes a candidate into an executable lane.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("promotion_packet_id", FieldClass.STATE_OF_TRUTH, "Stable promotion packet identifier."),
            _field(
                "candidate_bundle_id",
                FieldClass.CANONICAL_REFERENCE,
                "Candidate bundle being promoted.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "bundle_readiness_record_id",
                FieldClass.CANONICAL_REFERENCE,
                "Readiness review bound to the promotion.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "approved_account_profile_id",
                FieldClass.STATE_OF_TRUTH,
                "Approved account/risk posture for the promotion.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "signed_policy_digest",
                FieldClass.STATE_OF_TRUTH,
                "Signed digest of the governing promotion rules.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="session_readiness_packet",
        title="Session readiness packet",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Per-session green-light packet that gates a tradeable session.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("session_readiness_packet_id", FieldClass.STATE_OF_TRUTH, "Stable session-readiness identifier."),
            _field(
                "deployment_instance_id",
                FieldClass.CANONICAL_REFERENCE,
                "Deployment instance being cleared for the session.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "source_promotion_packet_id",
                FieldClass.CANONICAL_REFERENCE,
                "Promotion packet authorizing the session.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "session_context_digest",
                FieldClass.STATE_OF_TRUTH,
                "Resolved calendar, maintenance, and context bundle digest.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "contract_conformance_digest",
                FieldClass.STATE_OF_TRUTH,
                "Pre-open contract conformance digest.",
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "operator_attestation_id",
                FieldClass.CANONICAL_REFERENCE,
                "Human/operator attestation or review bundle.",
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="policy_record",
        title="Policy record",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Versioned policy object with governance weight.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("policy_id", FieldClass.STATE_OF_TRUTH, "Stable policy identifier."),
            _field("policy_family", FieldClass.STATE_OF_TRUTH, "Policy family and lane."),
            _field(
                "policy_digest",
                FieldClass.STATE_OF_TRUTH,
                "Immutable digest for the approved policy version.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
            _field(
                "effective_from_utc",
                FieldClass.STATE_OF_TRUTH,
                "UTC effectiveness boundary for governance replay.",
                LifecycleNeed.REPLAY,
                LifecycleNeed.PROMOTION,
            ),
        ),
    ),
    RecordDefinition(
        record_id="incident_record",
        title="Incident record",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Canonical incident and break-glass review trail.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("incident_id", FieldClass.STATE_OF_TRUTH, "Stable incident identifier."),
            _field("incident_type", FieldClass.STATE_OF_TRUTH, "Incident or break-glass classification."),
            _field("severity", FieldClass.STATE_OF_TRUTH, "Severity used for governance and response."),
            _field("opened_at_utc", FieldClass.STATE_OF_TRUTH, "UTC incident open timestamp."),
            _field("linked_policy_id", FieldClass.CANONICAL_REFERENCE, "Related governing policy."),
        ),
    ),
    RecordDefinition(
        record_id="ledger_close",
        title="Ledger close",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="Canonical daily or session ledger close for auditable accounting.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("ledger_close_id", FieldClass.STATE_OF_TRUTH, "Stable ledger close identifier."),
            _field("account_id", FieldClass.STATE_OF_TRUTH, "Account being closed."),
            _field("trading_day_utc", FieldClass.STATE_OF_TRUTH, "Trading day keyed in UTC."),
            _field("closing_equity", FieldClass.STATE_OF_TRUTH, "Auditable close equity."),
            _field("reconciliation_record_id", FieldClass.CANONICAL_REFERENCE, "Reconciliation bound to the close."),
        ),
    ),
    RecordDefinition(
        record_id="reconciliation_record",
        title="Reconciliation record",
        storage_class=StorageClass.CANONICAL_METADATA,
        plan_section="3.3",
        description="As-booked versus as-reconciled state transition record.",
        queryable_when_telemetry_pruned=True,
        durable_when_telemetry_pruned=True,
        retention_independent=True,
        fields=(
            _field("reconciliation_id", FieldClass.STATE_OF_TRUTH, "Stable reconciliation identifier."),
            _field("account_id", FieldClass.STATE_OF_TRUTH, "Reconciled account."),
            _field("broker_statement_digest", FieldClass.STATE_OF_TRUTH, "Digest of the broker-side evidence."),
            _field("internal_ledger_digest", FieldClass.STATE_OF_TRUTH, "Digest of the as-booked ledger state."),
            _field("reconciliation_outcome", FieldClass.STATE_OF_TRUTH, "Operator-readable reconciliation result."),
        ),
    ),
    RecordDefinition(
        record_id="run_metrics",
        title="Run metrics",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="High-volume metrics emitted during research runs.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("research_run_id", FieldClass.CANONICAL_REFERENCE, "Canonical run anchor."),
            _field("metric_name", FieldClass.TELEMETRY_ONLY, "Metric series name."),
            _field("metric_value", FieldClass.TELEMETRY_ONLY, "Metric series value."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
    RecordDefinition(
        record_id="parity_series",
        title="Parity series",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="Series-level parity observations used for diagnostics and dashboards.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("candidate_id", FieldClass.CANONICAL_REFERENCE, "Candidate anchor for parity telemetry."),
            _field("series_name", FieldClass.TELEMETRY_ONLY, "Parity telemetry series name."),
            _field("measured_value", FieldClass.TELEMETRY_ONLY, "Observed parity measure."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
    RecordDefinition(
        record_id="quality_events",
        title="Quality events",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="Quality-event stream for diagnostics, trend analysis, and alerting.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("source_record_id", FieldClass.CANONICAL_REFERENCE, "Canonical record anchored by the event."),
            _field("event_code", FieldClass.TELEMETRY_ONLY, "Telemetry event code."),
            _field("severity", FieldClass.TELEMETRY_ONLY, "Telemetry severity level."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
    RecordDefinition(
        record_id="latency_series",
        title="Latency series",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="Latency measurements for dashboards, alerts, and trend analysis.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("session_readiness_packet_id", FieldClass.CANONICAL_REFERENCE, "Session anchor for latency telemetry."),
            _field("stage_name", FieldClass.TELEMETRY_ONLY, "Measured latency stage."),
            _field("latency_ms", FieldClass.TELEMETRY_ONLY, "Observed latency value."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
    RecordDefinition(
        record_id="drift_metrics",
        title="Drift metrics",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="Drift indicators used for monitoring but not as records of truth.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("candidate_id", FieldClass.CANONICAL_REFERENCE, "Candidate anchor for drift telemetry."),
            _field("drift_dimension", FieldClass.TELEMETRY_ONLY, "Dimension being tracked."),
            _field("drift_value", FieldClass.TELEMETRY_ONLY, "Observed drift metric."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
    RecordDefinition(
        record_id="diagnostics",
        title="Diagnostics",
        storage_class=StorageClass.DENSE_TELEMETRY,
        plan_section="3.3",
        description="Verbose diagnostics and debug streams not permitted to redefine state.",
        queryable_when_telemetry_pruned=False,
        durable_when_telemetry_pruned=False,
        retention_independent=False,
        fields=(
            _field("source_record_id", FieldClass.CANONICAL_REFERENCE, "Canonical anchor for the diagnostic stream."),
            _field("subsystem", FieldClass.TELEMETRY_ONLY, "Subsystem emitting diagnostics."),
            _field("diagnostic_code", FieldClass.TELEMETRY_ONLY, "Verbose diagnostic code."),
            _field("captured_at_utc", FieldClass.TELEMETRY_ONLY, "Telemetry capture timestamp."),
        ),
    ),
)


def records_by_storage_class(storage_class: StorageClass) -> tuple[RecordDefinition, ...]:
    return tuple(
        record for record in RECORD_DEFINITIONS if record.storage_class == storage_class
    )


def _required_fields(
    record: RecordDefinition, lifecycle_need: LifecycleNeed
) -> tuple[FieldDefinition, ...]:
    return tuple(
        field_definition
        for field_definition in record.fields
        if lifecycle_need in field_definition.required_for
    )


def classification_reports() -> list[ClassificationReport]:
    reports: list[ClassificationReport] = []
    for record in RECORD_DEFINITIONS:
        field_classification = {
            field_definition.name: field_definition.field_class.value
            for field_definition in record.fields
        }
        replay_fields = tuple(
            field_definition.name
            for field_definition in _required_fields(record, LifecycleNeed.REPLAY)
        )
        promotion_fields = tuple(
            field_definition.name
            for field_definition in _required_fields(record, LifecycleNeed.PROMOTION)
        )
        reason_code = (
            f"METADATA_CLASSIFIED_{record.record_id.upper()}"
            if record.storage_class == StorageClass.CANONICAL_METADATA
            else f"TELEMETRY_CLASSIFIED_{record.record_id.upper()}"
        )
        explanation = (
            "Canonical metadata remains queryable and durable even if telemetry storage evolves."
            if record.storage_class == StorageClass.CANONICAL_METADATA
            else "Dense telemetry is anchored to canonical IDs but cannot redefine replay or promotion state."
        )
        reports.append(
            ClassificationReport(
                record_id=record.record_id,
                storage_class=record.storage_class.value,
                plan_section=record.plan_section,
                queryable_when_telemetry_pruned=record.queryable_when_telemetry_pruned,
                durable_when_telemetry_pruned=record.durable_when_telemetry_pruned,
                retention_independent=record.retention_independent,
                field_classification=field_classification,
                replay_fields=replay_fields,
                promotion_fields=promotion_fields,
                reason_code=reason_code,
                explanation=explanation,
            )
        )
    return reports


def derivability_reports() -> list[DerivabilityReport]:
    reports: list[DerivabilityReport] = []
    for record in RECORD_DEFINITIONS:
        replay_fields = _required_fields(record, LifecycleNeed.REPLAY)
        promotion_fields = _required_fields(record, LifecycleNeed.PROMOTION)
        replay_applicable = bool(replay_fields)
        promotion_applicable = bool(promotion_fields)

        offending_fields = tuple(
            field_definition.name
            for field_definition in (*replay_fields, *promotion_fields)
            if field_definition.field_class == FieldClass.TELEMETRY_ONLY
        )

        replay_state_derived_from_canonical = replay_applicable and not offending_fields
        promotion_state_derived_from_canonical = promotion_applicable and not offending_fields

        if record.storage_class == StorageClass.DENSE_TELEMETRY:
            reason_code = f"TELEMETRY_NOT_AUTHORITATIVE_{record.record_id.upper()}"
            explanation = (
                "This record is dense telemetry. It may reference canonical IDs but is never "
                "an authoritative replay or promotion source."
            )
            replay_state_derived_from_canonical = False
            promotion_state_derived_from_canonical = False
            replay_applicable = False
            promotion_applicable = False
        elif offending_fields:
            reason_code = f"DERIVABILITY_VIOLATION_{record.record_id.upper()}"
            explanation = (
                f"{record.record_id} marks telemetry-only fields as replay/promotion requirements: "
                f"{offending_fields}."
            )
        else:
            reason_code = f"DERIVABILITY_CANONICAL_{record.record_id.upper()}"
            explanation = (
                "All replay/promotion inputs for this record are stored in canonical metadata "
                "or canonical references."
            )

        reports.append(
            DerivabilityReport(
                record_id=record.record_id,
                storage_class=record.storage_class.value,
                replay_applicable=replay_applicable,
                replay_state_derived_from_canonical=replay_state_derived_from_canonical,
                promotion_applicable=promotion_applicable,
                promotion_state_derived_from_canonical=promotion_state_derived_from_canonical,
                offending_fields=offending_fields,
                reason_code=reason_code,
                explanation=explanation,
            )
        )
    return reports


def validate_metadata_contract() -> list[str]:
    errors: list[str] = []
    record_ids = [record.record_id for record in RECORD_DEFINITIONS]
    if len(record_ids) != len(set(record_ids)):
        errors.append("record identifiers must be unique")

    for record in RECORD_DEFINITIONS:
        field_names = [field_definition.name for field_definition in record.fields]
        if len(field_names) != len(set(field_names)):
            errors.append(f"{record.record_id}: field names must be unique")

        if record.storage_class == StorageClass.CANONICAL_METADATA:
            if not (
                record.queryable_when_telemetry_pruned
                and record.durable_when_telemetry_pruned
                and record.retention_independent
            ):
                errors.append(
                    f"{record.record_id}: canonical metadata must remain queryable/durable "
                    "independent of telemetry retention"
                )
            telemetry_only_fields = [
                field_definition.name
                for field_definition in record.fields
                if field_definition.field_class == FieldClass.TELEMETRY_ONLY
            ]
            if telemetry_only_fields:
                errors.append(
                    f"{record.record_id}: canonical records cannot contain telemetry-only fields "
                    f"{telemetry_only_fields}"
                )
        else:
            if (
                record.queryable_when_telemetry_pruned
                or record.durable_when_telemetry_pruned
                or record.retention_independent
            ):
                errors.append(
                    f"{record.record_id}: dense telemetry must not be marked telemetry-retention independent"
                )
            if any(field_definition.required_for for field_definition in record.fields):
                errors.append(
                    f"{record.record_id}: dense telemetry cannot define replay/promotion requirements"
                )
            if not any(
                field_definition.field_class == FieldClass.CANONICAL_REFERENCE
                for field_definition in record.fields
            ):
                errors.append(
                    f"{record.record_id}: dense telemetry must anchor to canonical metadata"
                )

        for field_definition in record.fields:
            if (
                field_definition.required_for
                and field_definition.field_class == FieldClass.TELEMETRY_ONLY
            ):
                errors.append(
                    f"{record.record_id}.{field_definition.name}: telemetry-only fields cannot be "
                    "required for replay or promotion"
                )

    return errors


VALIDATION_ERRORS = validate_metadata_contract()
