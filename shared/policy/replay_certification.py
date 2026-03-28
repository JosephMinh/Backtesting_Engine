"""Deterministic replay certification contracts before paper trading."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.deployment_packets import (
    CandidateBundle,
    CandidateBundleFreezeRegistration,
    CandidateBundleReplayContext,
    PacketStatus,
    validate_candidate_bundle_replay_readiness,
)

STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []


def _utcnow() -> str:
    return canonicalize_persisted_timestamp(
        _dt.datetime.now(_dt.timezone.utc)
    ).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _require_present(
    payload: dict[str, Any], field_name: str, *, label: str
) -> Any:
    if field_name not in payload:
        raise ValueError(f"{label}: missing {field_name}")
    return payload[field_name]


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected object")
    return value


def _require_non_empty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label}: expected string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label}: expected non-empty string")
    return normalized


def _require_optional_string(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, label=label)


def _require_bool(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{label}: expected boolean")


def _require_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label}: expected integer")
    return value


def _require_float(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: expected finite number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{label}: expected finite number")
    return result


def _require_mapping_sequence(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected list")
    return [
        _require_mapping(item, label=f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _require_string_sequence(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected list")
    return [
        _require_non_empty_string(item, label=f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _require_timestamp(value: Any, *, label: str) -> str:
    raw = _require_non_empty_string(value, label=label)
    try:
        parsed = _dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}: expected ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label}: expected timezone-aware timestamp")
    return canonicalize_persisted_timestamp(parsed).isoformat()


def _sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@unique
class ReplayCertificationMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


@unique
class DependencyChangeScope(str, Enum):
    NONE = "none"
    NARROW = "narrow"
    BROAD = "broad"


@unique
class ReplayCertificationStatus(str, Enum):
    PASS = "pass"  # nosec B105 - certification status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@dataclass(frozen=True)
class SignalTraceEntry:
    signal_name: str
    signal_value: float
    timestamp_utc: str
    decision_sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SignalTraceEntry":
        entry_payload = _require_mapping(payload, label="signal_trace_entry")
        return cls(
            signal_name=_require_non_empty_string(
                _require_present(entry_payload, "signal_name", label="signal_trace_entry"),
                label="signal_trace_entry.signal_name",
            ),
            signal_value=_require_float(
                _require_present(entry_payload, "signal_value", label="signal_trace_entry"),
                label="signal_trace_entry.signal_value",
            ),
            timestamp_utc=_require_timestamp(
                _require_present(entry_payload, "timestamp_utc", label="signal_trace_entry"),
                label="signal_trace_entry.timestamp_utc",
            ),
            decision_sequence_number=_require_int(
                _require_present(
                    entry_payload, "decision_sequence_number", label="signal_trace_entry"
                ),
                label="signal_trace_entry.decision_sequence_number",
            ),
        )

    def reference_id(self) -> str:
        return f"{self.signal_name}@{self.timestamp_utc}"


@dataclass(frozen=True)
class OrderIntentTraceEntry:
    order_intent_id: str
    submitted_at_utc: str
    action: str
    symbol: str
    side: str
    quantity: float
    decision_sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OrderIntentTraceEntry":
        entry_payload = _require_mapping(payload, label="order_intent_trace_entry")
        return cls(
            order_intent_id=_require_non_empty_string(
                _require_present(
                    entry_payload, "order_intent_id", label="order_intent_trace_entry"
                ),
                label="order_intent_trace_entry.order_intent_id",
            ),
            submitted_at_utc=_require_timestamp(
                _require_present(
                    entry_payload, "submitted_at_utc", label="order_intent_trace_entry"
                ),
                label="order_intent_trace_entry.submitted_at_utc",
            ),
            action=_require_non_empty_string(
                _require_present(entry_payload, "action", label="order_intent_trace_entry"),
                label="order_intent_trace_entry.action",
            ),
            symbol=_require_non_empty_string(
                _require_present(entry_payload, "symbol", label="order_intent_trace_entry"),
                label="order_intent_trace_entry.symbol",
            ),
            side=_require_non_empty_string(
                _require_present(entry_payload, "side", label="order_intent_trace_entry"),
                label="order_intent_trace_entry.side",
            ),
            quantity=_require_float(
                _require_present(entry_payload, "quantity", label="order_intent_trace_entry"),
                label="order_intent_trace_entry.quantity",
            ),
            decision_sequence_number=_require_int(
                _require_present(
                    entry_payload,
                    "decision_sequence_number",
                    label="order_intent_trace_entry",
                ),
                label="order_intent_trace_entry.decision_sequence_number",
            ),
        )

    def reference_id(self) -> str:
        return self.order_intent_id


@dataclass(frozen=True)
class RiskActionTraceEntry:
    risk_action_id: str
    triggered_at_utc: str
    action: str
    policy_source: str
    decision_sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RiskActionTraceEntry":
        entry_payload = _require_mapping(payload, label="risk_action_trace_entry")
        return cls(
            risk_action_id=_require_non_empty_string(
                _require_present(
                    entry_payload, "risk_action_id", label="risk_action_trace_entry"
                ),
                label="risk_action_trace_entry.risk_action_id",
            ),
            triggered_at_utc=_require_timestamp(
                _require_present(
                    entry_payload, "triggered_at_utc", label="risk_action_trace_entry"
                ),
                label="risk_action_trace_entry.triggered_at_utc",
            ),
            action=_require_non_empty_string(
                _require_present(entry_payload, "action", label="risk_action_trace_entry"),
                label="risk_action_trace_entry.action",
            ),
            policy_source=_require_non_empty_string(
                _require_present(
                    entry_payload, "policy_source", label="risk_action_trace_entry"
                ),
                label="risk_action_trace_entry.policy_source",
            ),
            decision_sequence_number=_require_int(
                _require_present(
                    entry_payload,
                    "decision_sequence_number",
                    label="risk_action_trace_entry",
                ),
                label="risk_action_trace_entry.decision_sequence_number",
            ),
        )

    def reference_id(self) -> str:
        return self.risk_action_id


@dataclass(frozen=True)
class ContractStateDecisionEntry:
    decision_id: str
    decided_at_utc: str
    contract_state: str
    reason_code: str
    decision_sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContractStateDecisionEntry":
        entry_payload = _require_mapping(payload, label="contract_state_decision_entry")
        return cls(
            decision_id=_require_non_empty_string(
                _require_present(
                    entry_payload, "decision_id", label="contract_state_decision_entry"
                ),
                label="contract_state_decision_entry.decision_id",
            ),
            decided_at_utc=_require_timestamp(
                _require_present(
                    entry_payload, "decided_at_utc", label="contract_state_decision_entry"
                ),
                label="contract_state_decision_entry.decided_at_utc",
            ),
            contract_state=_require_non_empty_string(
                _require_present(
                    entry_payload, "contract_state", label="contract_state_decision_entry"
                ),
                label="contract_state_decision_entry.contract_state",
            ),
            reason_code=_require_non_empty_string(
                _require_present(
                    entry_payload, "reason_code", label="contract_state_decision_entry"
                ),
                label="contract_state_decision_entry.reason_code",
            ),
            decision_sequence_number=_require_int(
                _require_present(
                    entry_payload,
                    "decision_sequence_number",
                    label="contract_state_decision_entry",
                ),
                label="contract_state_decision_entry.decision_sequence_number",
            ),
        )

    def reference_id(self) -> str:
        return self.decision_id


@dataclass(frozen=True)
class FreshnessWatermarkEntry:
    data_source: str
    watermark_timestamp_utc: str
    handling_decision: str
    observed_at_utc: str
    decision_sequence_number: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FreshnessWatermarkEntry":
        entry_payload = _require_mapping(payload, label="freshness_watermark_entry")
        return cls(
            data_source=_require_non_empty_string(
                _require_present(
                    entry_payload, "data_source", label="freshness_watermark_entry"
                ),
                label="freshness_watermark_entry.data_source",
            ),
            watermark_timestamp_utc=_require_timestamp(
                _require_present(
                    entry_payload,
                    "watermark_timestamp_utc",
                    label="freshness_watermark_entry",
                ),
                label="freshness_watermark_entry.watermark_timestamp_utc",
            ),
            handling_decision=_require_non_empty_string(
                _require_present(
                    entry_payload,
                    "handling_decision",
                    label="freshness_watermark_entry",
                ),
                label="freshness_watermark_entry.handling_decision",
            ),
            observed_at_utc=_require_timestamp(
                _require_present(
                    entry_payload, "observed_at_utc", label="freshness_watermark_entry"
                ),
                label="freshness_watermark_entry.observed_at_utc",
            ),
            decision_sequence_number=_require_int(
                _require_present(
                    entry_payload,
                    "decision_sequence_number",
                    label="freshness_watermark_entry",
                ),
                label="freshness_watermark_entry.decision_sequence_number",
            ),
        )

    def reference_id(self) -> str:
        return f"{self.data_source}@{self.watermark_timestamp_utc}"


@dataclass(frozen=True)
class ReplayExpectedActualDiff:
    stream_name: str
    index: int
    field_name: str
    expected: Any
    actual: Any
    expected_reference: str | None
    actual_reference: str | None
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplayExpectedActualDiff":
        diff_payload = _require_mapping(payload, label="replay expected actual diff")
        return cls(
            stream_name=_require_non_empty_string(
                _require_present(
                    diff_payload, "stream_name", label="replay expected actual diff"
                ),
                label="replay expected actual diff.stream_name",
            ),
            index=_require_int(
                _require_present(
                    diff_payload, "index", label="replay expected actual diff"
                ),
                label="replay expected actual diff.index",
            ),
            field_name=_require_non_empty_string(
                _require_present(
                    diff_payload, "field_name", label="replay expected actual diff"
                ),
                label="replay expected actual diff.field_name",
            ),
            expected=diff_payload.get("expected"),
            actual=diff_payload.get("actual"),
            expected_reference=_require_optional_string(
                _require_present(
                    diff_payload,
                    "expected_reference",
                    label="replay expected actual diff",
                ),
                label="replay expected actual diff.expected_reference",
            ),
            actual_reference=_require_optional_string(
                _require_present(
                    diff_payload,
                    "actual_reference",
                    label="replay expected actual diff",
                ),
                label="replay expected actual diff.actual_reference",
            ),
            diagnostic=_require_non_empty_string(
                _require_present(
                    diff_payload, "diagnostic", label="replay expected actual diff"
                ),
                label="replay expected actual diff.diagnostic",
            ),
        )


@dataclass(frozen=True)
class StepwiseTraceEntry:
    stream_name: str
    index: int
    matched: bool
    expected_reference: str | None
    actual_reference: str | None
    expected_sequence_number: int | None
    actual_sequence_number: int | None
    divergence_fields: tuple[str, ...]
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StepwiseTraceEntry":
        trace_payload = _require_mapping(payload, label="replay stepwise trace entry")
        expected_sequence = _require_present(
            trace_payload,
            "expected_sequence_number",
            label="replay stepwise trace entry",
        )
        actual_sequence = _require_present(
            trace_payload,
            "actual_sequence_number",
            label="replay stepwise trace entry",
        )
        return cls(
            stream_name=_require_non_empty_string(
                _require_present(
                    trace_payload, "stream_name", label="replay stepwise trace entry"
                ),
                label="replay stepwise trace entry.stream_name",
            ),
            index=_require_int(
                _require_present(
                    trace_payload, "index", label="replay stepwise trace entry"
                ),
                label="replay stepwise trace entry.index",
            ),
            matched=_require_bool(
                _require_present(
                    trace_payload, "matched", label="replay stepwise trace entry"
                ),
                label="replay stepwise trace entry.matched",
            ),
            expected_reference=_require_optional_string(
                _require_present(
                    trace_payload,
                    "expected_reference",
                    label="replay stepwise trace entry",
                ),
                label="replay stepwise trace entry.expected_reference",
            ),
            actual_reference=_require_optional_string(
                _require_present(
                    trace_payload,
                    "actual_reference",
                    label="replay stepwise trace entry",
                ),
                label="replay stepwise trace entry.actual_reference",
            ),
            expected_sequence_number=(
                None
                if expected_sequence is None
                else _require_int(
                    expected_sequence,
                    label="replay stepwise trace entry.expected_sequence_number",
                )
            ),
            actual_sequence_number=(
                None
                if actual_sequence is None
                else _require_int(
                    actual_sequence,
                    label="replay stepwise trace entry.actual_sequence_number",
                )
            ),
            divergence_fields=tuple(
                _require_string_sequence(
                    _require_present(
                        trace_payload,
                        "divergence_fields",
                        label="replay stepwise trace entry",
                    ),
                    label="replay stepwise trace entry.divergence_fields",
                )
            ),
            diagnostic=_require_non_empty_string(
                _require_present(
                    trace_payload, "diagnostic", label="replay stepwise trace entry"
                ),
                label="replay stepwise trace entry.diagnostic",
            ),
        )


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    artifact_role: str
    relative_path: str
    sha256: str
    content_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactRecord":
        record_payload = _require_mapping(payload, label="replay artifact record")
        return cls(
            artifact_id=_require_non_empty_string(
                _require_present(
                    record_payload, "artifact_id", label="replay artifact record"
                ),
                label="replay artifact record.artifact_id",
            ),
            artifact_role=_require_non_empty_string(
                _require_present(
                    record_payload, "artifact_role", label="replay artifact record"
                ),
                label="replay artifact record.artifact_role",
            ),
            relative_path=_require_non_empty_string(
                _require_present(
                    record_payload, "relative_path", label="replay artifact record"
                ),
                label="replay artifact record.relative_path",
            ),
            sha256=_require_non_empty_string(
                _require_present(record_payload, "sha256", label="replay artifact record"),
                label="replay artifact record.sha256",
            ),
            content_type=_require_non_empty_string(
                _require_present(
                    record_payload, "content_type", label="replay artifact record"
                ),
                label="replay artifact record.content_type",
            ),
        )


@dataclass(frozen=True)
class ArtifactManifest:
    manifest_id: str
    generated_at_utc: str
    retention_class: str
    contains_secrets: bool
    redaction_policy: str
    artifacts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactManifest":
        manifest_payload = _require_mapping(payload, label="replay artifact manifest")
        return cls(
            manifest_id=_require_non_empty_string(
                _require_present(
                    manifest_payload, "manifest_id", label="replay artifact manifest"
                ),
                label="replay artifact manifest.manifest_id",
            ),
            generated_at_utc=_require_timestamp(
                _require_present(
                    manifest_payload, "generated_at_utc", label="replay artifact manifest"
                ),
                label="replay artifact manifest.generated_at_utc",
            ),
            retention_class=_require_non_empty_string(
                _require_present(
                    manifest_payload,
                    "retention_class",
                    label="replay artifact manifest",
                ),
                label="replay artifact manifest.retention_class",
            ),
            contains_secrets=_require_bool(
                _require_present(
                    manifest_payload,
                    "contains_secrets",
                    label="replay artifact manifest",
                ),
                label="replay artifact manifest.contains_secrets",
            ),
            redaction_policy=_require_non_empty_string(
                _require_present(
                    manifest_payload,
                    "redaction_policy",
                    label="replay artifact manifest",
                ),
                label="replay artifact manifest.redaction_policy",
            ),
            artifacts=[
                ArtifactRecord.from_dict(item).to_dict()
                for item in _require_mapping_sequence(
                    _require_present(
                        manifest_payload, "artifacts", label="replay artifact manifest"
                    ),
                    label="replay artifact manifest.artifacts",
                )
            ],
        )


@dataclass(frozen=True)
class StructuredLogRecord:
    schema_version: str
    event_type: str
    plane: str
    event_id: str
    recorded_at_utc: str
    correlation_id: str
    decision_trace_id: str
    reason_code: str
    reason_summary: str
    referenced_ids: list[str]
    redacted_fields: list[str]
    omitted_fields: list[str]
    artifact_manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredLogRecord":
        record_payload = _require_mapping(payload, label="replay structured log record")
        schema_version = _require_non_empty_string(
            _require_present(
                record_payload, "schema_version", label="replay structured log record"
            ),
            label="replay structured log record.schema_version",
        )
        if schema_version != STRUCTURED_LOG_SCHEMA_VERSION:
            raise ValueError(
                "replay structured log record.schema_version: unsupported schema version"
            )
        return cls(
            schema_version=schema_version,
            event_type=_require_non_empty_string(
                _require_present(
                    record_payload, "event_type", label="replay structured log record"
                ),
                label="replay structured log record.event_type",
            ),
            plane=_require_non_empty_string(
                _require_present(record_payload, "plane", label="replay structured log record"),
                label="replay structured log record.plane",
            ),
            event_id=_require_non_empty_string(
                _require_present(
                    record_payload, "event_id", label="replay structured log record"
                ),
                label="replay structured log record.event_id",
            ),
            recorded_at_utc=_require_timestamp(
                _require_present(
                    record_payload,
                    "recorded_at_utc",
                    label="replay structured log record",
                ),
                label="replay structured log record.recorded_at_utc",
            ),
            correlation_id=_require_non_empty_string(
                _require_present(
                    record_payload,
                    "correlation_id",
                    label="replay structured log record",
                ),
                label="replay structured log record.correlation_id",
            ),
            decision_trace_id=_require_non_empty_string(
                _require_present(
                    record_payload,
                    "decision_trace_id",
                    label="replay structured log record",
                ),
                label="replay structured log record.decision_trace_id",
            ),
            reason_code=_require_non_empty_string(
                _require_present(
                    record_payload, "reason_code", label="replay structured log record"
                ),
                label="replay structured log record.reason_code",
            ),
            reason_summary=_require_non_empty_string(
                _require_present(
                    record_payload,
                    "reason_summary",
                    label="replay structured log record",
                ),
                label="replay structured log record.reason_summary",
            ),
            referenced_ids=_require_string_sequence(
                _require_present(
                    record_payload,
                    "referenced_ids",
                    label="replay structured log record",
                ),
                label="replay structured log record.referenced_ids",
            ),
            redacted_fields=_require_string_sequence(
                _require_present(
                    record_payload,
                    "redacted_fields",
                    label="replay structured log record",
                ),
                label="replay structured log record.redacted_fields",
            ),
            omitted_fields=_require_string_sequence(
                _require_present(
                    record_payload,
                    "omitted_fields",
                    label="replay structured log record",
                ),
                label="replay structured log record.omitted_fields",
            ),
            artifact_manifest=ArtifactManifest.from_dict(
                _require_mapping(
                    _require_present(
                        record_payload,
                        "artifact_manifest",
                        label="replay structured log record",
                    ),
                    label="replay structured log record.artifact_manifest",
                )
            ).to_dict(),
        )


@dataclass(frozen=True)
class OperatorReasonBundle:
    summary: str
    gate_summary: str
    rule_trace: list[str]
    remediation_hints: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperatorReasonBundle":
        bundle_payload = _require_mapping(payload, label="replay operator reason bundle")
        return cls(
            summary=_require_non_empty_string(
                _require_present(
                    bundle_payload, "summary", label="replay operator reason bundle"
                ),
                label="replay operator reason bundle.summary",
            ),
            gate_summary=_require_non_empty_string(
                _require_present(
                    bundle_payload, "gate_summary", label="replay operator reason bundle"
                ),
                label="replay operator reason bundle.gate_summary",
            ),
            rule_trace=_require_string_sequence(
                _require_present(
                    bundle_payload, "rule_trace", label="replay operator reason bundle"
                ),
                label="replay operator reason bundle.rule_trace",
            ),
            remediation_hints=_require_string_sequence(
                _require_present(
                    bundle_payload,
                    "remediation_hints",
                    label="replay operator reason bundle",
                ),
                label="replay operator reason bundle.remediation_hints",
            ),
        )


@dataclass(frozen=True)
class ReplayCertificationRequest:
    case_id: str
    certification_id: str
    bundle: CandidateBundle
    registration: CandidateBundleFreezeRegistration
    replay_context: CandidateBundleReplayContext
    decision_trace_id: str
    expected_signal_trace: tuple[SignalTraceEntry, ...] = ()
    actual_signal_trace: tuple[SignalTraceEntry, ...] = ()
    expected_order_intent_trace: tuple[OrderIntentTraceEntry, ...] = ()
    actual_order_intent_trace: tuple[OrderIntentTraceEntry, ...] = ()
    expected_risk_action_trace: tuple[RiskActionTraceEntry, ...] = ()
    actual_risk_action_trace: tuple[RiskActionTraceEntry, ...] = ()
    expected_contract_state_trace: tuple[ContractStateDecisionEntry, ...] = ()
    actual_contract_state_trace: tuple[ContractStateDecisionEntry, ...] = ()
    expected_freshness_watermark_trace: tuple[FreshnessWatermarkEntry, ...] = ()
    actual_freshness_watermark_trace: tuple[FreshnessWatermarkEntry, ...] = ()
    certification_mode: ReplayCertificationMode = ReplayCertificationMode.FULL
    dependency_change_scope: DependencyChangeScope = DependencyChangeScope.NONE
    prior_certification_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "certification_id": self.certification_id,
            "bundle": self.bundle.to_dict(),
            "registration": self.registration.to_dict(),
            "replay_context": self.replay_context.to_dict(),
            "decision_trace_id": self.decision_trace_id,
            "expected_signal_trace": [
                item.to_dict() for item in self.expected_signal_trace
            ],
            "actual_signal_trace": [item.to_dict() for item in self.actual_signal_trace],
            "expected_order_intent_trace": [
                item.to_dict() for item in self.expected_order_intent_trace
            ],
            "actual_order_intent_trace": [
                item.to_dict() for item in self.actual_order_intent_trace
            ],
            "expected_risk_action_trace": [
                item.to_dict() for item in self.expected_risk_action_trace
            ],
            "actual_risk_action_trace": [
                item.to_dict() for item in self.actual_risk_action_trace
            ],
            "expected_contract_state_trace": [
                item.to_dict() for item in self.expected_contract_state_trace
            ],
            "actual_contract_state_trace": [
                item.to_dict() for item in self.actual_contract_state_trace
            ],
            "expected_freshness_watermark_trace": [
                item.to_dict() for item in self.expected_freshness_watermark_trace
            ],
            "actual_freshness_watermark_trace": [
                item.to_dict() for item in self.actual_freshness_watermark_trace
            ],
            "certification_mode": self.certification_mode.value,
            "dependency_change_scope": self.dependency_change_scope.value,
            "prior_certification_id": self.prior_certification_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplayCertificationRequest":
        request_payload = _require_mapping(payload, label="replay request")
        return cls(
            case_id=_require_non_empty_string(
                _require_present(request_payload, "case_id", label="replay request"),
                label="replay request.case_id",
            ),
            certification_id=_require_non_empty_string(
                _require_present(request_payload, "certification_id", label="replay request"),
                label="replay request.certification_id",
            ),
            bundle=CandidateBundle.from_dict(
                _require_mapping(
                    _require_present(request_payload, "bundle", label="replay request"),
                    label="replay request.bundle",
                )
            ),
            registration=CandidateBundleFreezeRegistration.from_dict(
                _require_mapping(
                    _require_present(request_payload, "registration", label="replay request"),
                    label="replay request.registration",
                )
            ),
            replay_context=CandidateBundleReplayContext.from_dict(
                _require_mapping(
                    _require_present(request_payload, "replay_context", label="replay request"),
                    label="replay request.replay_context",
                )
            ),
            decision_trace_id=_require_non_empty_string(
                _require_present(
                    request_payload, "decision_trace_id", label="replay request"
                ),
                label="replay request.decision_trace_id",
            ),
            expected_signal_trace=tuple(
                SignalTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload, "expected_signal_trace", label="replay request"
                    ),
                    label="replay request.expected_signal_trace",
                )
            ),
            actual_signal_trace=tuple(
                SignalTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload, "actual_signal_trace", label="replay request"
                    ),
                    label="replay request.actual_signal_trace",
                )
            ),
            expected_order_intent_trace=tuple(
                OrderIntentTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "expected_order_intent_trace",
                        label="replay request",
                    ),
                    label="replay request.expected_order_intent_trace",
                )
            ),
            actual_order_intent_trace=tuple(
                OrderIntentTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "actual_order_intent_trace",
                        label="replay request",
                    ),
                    label="replay request.actual_order_intent_trace",
                )
            ),
            expected_risk_action_trace=tuple(
                RiskActionTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload, "expected_risk_action_trace", label="replay request"
                    ),
                    label="replay request.expected_risk_action_trace",
                )
            ),
            actual_risk_action_trace=tuple(
                RiskActionTraceEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload, "actual_risk_action_trace", label="replay request"
                    ),
                    label="replay request.actual_risk_action_trace",
                )
            ),
            expected_contract_state_trace=tuple(
                ContractStateDecisionEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "expected_contract_state_trace",
                        label="replay request",
                    ),
                    label="replay request.expected_contract_state_trace",
                )
            ),
            actual_contract_state_trace=tuple(
                ContractStateDecisionEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "actual_contract_state_trace",
                        label="replay request",
                    ),
                    label="replay request.actual_contract_state_trace",
                )
            ),
            expected_freshness_watermark_trace=tuple(
                FreshnessWatermarkEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "expected_freshness_watermark_trace",
                        label="replay request",
                    ),
                    label="replay request.expected_freshness_watermark_trace",
                )
            ),
            actual_freshness_watermark_trace=tuple(
                FreshnessWatermarkEntry.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "actual_freshness_watermark_trace",
                        label="replay request",
                    ),
                    label="replay request.actual_freshness_watermark_trace",
                )
            ),
            certification_mode=ReplayCertificationMode(
                _require_non_empty_string(
                    _require_present(
                        request_payload, "certification_mode", label="replay request"
                    ),
                    label="replay request.certification_mode",
                )
            ),
            dependency_change_scope=DependencyChangeScope(
                _require_non_empty_string(
                    _require_present(
                        request_payload,
                        "dependency_change_scope",
                        label="replay request",
                    ),
                    label="replay request.dependency_change_scope",
                )
            ),
            prior_certification_id=_require_optional_string(
                _require_present(
                    request_payload, "prior_certification_id", label="replay request"
                ),
                label="replay request.prior_certification_id",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReplayCertificationRequest":
        return cls.from_dict(_decode_json_object(payload, label="replay request"))


@dataclass(frozen=True)
class ReplayCertificationReport:
    case_id: str
    certification_id: str
    bundle_id: str
    replay_context_id: str
    correlation_id: str
    status: str
    reason_code: str
    certification_mode: str
    dependency_change_scope: str
    replay_readiness_reason_code: str
    paper_entry_permitted: bool
    incremental_recertification_allowed: bool
    expected_vs_actual_diffs: list[dict[str, Any]]
    first_divergence: dict[str, Any] | None
    stepwise_trace: list[dict[str, Any]]
    artifact_manifest: dict[str, Any]
    structured_logs: list[dict[str, Any]]
    operator_reason_bundle: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplayCertificationReport":
        report_payload = _require_mapping(payload, label="replay certification report")
        return cls(
            case_id=_require_non_empty_string(
                _require_present(
                    report_payload, "case_id", label="replay certification report"
                ),
                label="replay certification report.case_id",
            ),
            certification_id=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "certification_id",
                    label="replay certification report",
                ),
                label="replay certification report.certification_id",
            ),
            bundle_id=_require_non_empty_string(
                _require_present(
                    report_payload, "bundle_id", label="replay certification report"
                ),
                label="replay certification report.bundle_id",
            ),
            replay_context_id=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "replay_context_id",
                    label="replay certification report",
                ),
                label="replay certification report.replay_context_id",
            ),
            correlation_id=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "correlation_id",
                    label="replay certification report",
                ),
                label="replay certification report.correlation_id",
            ),
            status=ReplayCertificationStatus(
                _require_non_empty_string(
                    _require_present(
                        report_payload, "status", label="replay certification report"
                    ),
                    label="replay certification report.status",
                )
            ).value,
            reason_code=_require_non_empty_string(
                _require_present(
                    report_payload, "reason_code", label="replay certification report"
                ),
                label="replay certification report.reason_code",
            ),
            certification_mode=ReplayCertificationMode(
                _require_non_empty_string(
                    _require_present(
                        report_payload,
                        "certification_mode",
                        label="replay certification report",
                    ),
                    label="replay certification report.certification_mode",
                )
            ).value,
            dependency_change_scope=DependencyChangeScope(
                _require_non_empty_string(
                    _require_present(
                        report_payload,
                        "dependency_change_scope",
                        label="replay certification report",
                    ),
                    label="replay certification report.dependency_change_scope",
                )
            ).value,
            replay_readiness_reason_code=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "replay_readiness_reason_code",
                    label="replay certification report",
                ),
                label="replay certification report.replay_readiness_reason_code",
            ),
            paper_entry_permitted=_require_bool(
                _require_present(
                    report_payload,
                    "paper_entry_permitted",
                    label="replay certification report",
                ),
                label="replay certification report.paper_entry_permitted",
            ),
            incremental_recertification_allowed=_require_bool(
                _require_present(
                    report_payload,
                    "incremental_recertification_allowed",
                    label="replay certification report",
                ),
                label="replay certification report.incremental_recertification_allowed",
            ),
            expected_vs_actual_diffs=[
                ReplayExpectedActualDiff.from_dict(item).to_dict()
                for item in _require_mapping_sequence(
                    _require_present(
                        report_payload,
                        "expected_vs_actual_diffs",
                        label="replay certification report",
                    ),
                    label="replay certification report.expected_vs_actual_diffs",
                )
            ],
            first_divergence=(
                ReplayExpectedActualDiff.from_dict(
                    _require_mapping(
                        _require_present(
                            report_payload,
                            "first_divergence",
                            label="replay certification report",
                        ),
                        label="replay certification report.first_divergence",
                    )
                ).to_dict()
                if _require_present(
                    report_payload, "first_divergence", label="replay certification report"
                )
                is not None
                else None
            ),
            stepwise_trace=[
                StepwiseTraceEntry.from_dict(item).to_dict()
                for item in _require_mapping_sequence(
                    _require_present(
                        report_payload,
                        "stepwise_trace",
                        label="replay certification report",
                    ),
                    label="replay certification report.stepwise_trace",
                )
            ],
            artifact_manifest=ArtifactManifest.from_dict(
                _require_present(
                    report_payload,
                    "artifact_manifest",
                    label="replay certification report",
                )
            ).to_dict(),
            structured_logs=[
                StructuredLogRecord.from_dict(item).to_dict()
                for item in _require_mapping_sequence(
                    _require_present(
                        report_payload,
                        "structured_logs",
                        label="replay certification report",
                    ),
                    label="replay certification report.structured_logs",
                )
            ],
            operator_reason_bundle=OperatorReasonBundle.from_dict(
                _require_present(
                    report_payload,
                    "operator_reason_bundle",
                    label="replay certification report",
                )
            ).to_dict(),
            explanation=_require_non_empty_string(
                _require_present(
                    report_payload, "explanation", label="replay certification report"
                ),
                label="replay certification report.explanation",
            ),
            remediation=_require_non_empty_string(
                _require_present(
                    report_payload, "remediation", label="replay certification report"
                ),
                label="replay certification report.remediation",
            ),
            timestamp=_require_timestamp(
                _require_present(
                    report_payload, "timestamp", label="replay certification report"
                ),
                label="replay certification report.timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReplayCertificationReport":
        return cls.from_dict(
            _decode_json_object(payload, label="replay certification report")
        )


def _sequence_number(record: Any | None) -> int | None:
    if record is None:
        return None
    return int(getattr(record, "decision_sequence_number", 0))


def _reference_id(record: Any | None) -> str | None:
    if record is None:
        return None
    return str(record.reference_id())


def _compare_stream(
    stream_name: str,
    expected_records: tuple[Any, ...],
    actual_records: tuple[Any, ...],
) -> tuple[list[StepwiseTraceEntry], list[ReplayExpectedActualDiff]]:
    stepwise: list[StepwiseTraceEntry] = []
    diffs: list[ReplayExpectedActualDiff] = []
    for index in range(max(len(expected_records), len(actual_records))):
        expected = expected_records[index] if index < len(expected_records) else None
        actual = actual_records[index] if index < len(actual_records) else None
        if expected is None or actual is None:
            diagnostic = "Stream length diverged before replay certification could finish."
            stepwise.append(
                StepwiseTraceEntry(
                    stream_name=stream_name,
                    index=index,
                    matched=False,
                    expected_reference=_reference_id(expected),
                    actual_reference=_reference_id(actual),
                    expected_sequence_number=_sequence_number(expected),
                    actual_sequence_number=_sequence_number(actual),
                    divergence_fields=("entry_presence",),
                    diagnostic=diagnostic,
                )
            )
            diffs.append(
                ReplayExpectedActualDiff(
                    stream_name=stream_name,
                    index=index,
                    field_name="entry_presence",
                    expected=(expected.to_dict() if expected is not None else None),
                    actual=(actual.to_dict() if actual is not None else None),
                    expected_reference=_reference_id(expected),
                    actual_reference=_reference_id(actual),
                    diagnostic=diagnostic,
                )
            )
            continue

        expected_payload = expected.to_dict()
        actual_payload = actual.to_dict()
        divergence_fields = tuple(
            sorted(
                field_name
                for field_name in set(expected_payload) | set(actual_payload)
                if expected_payload.get(field_name) != actual_payload.get(field_name)
            )
        )
        stepwise.append(
            StepwiseTraceEntry(
                stream_name=stream_name,
                index=index,
                matched=not divergence_fields,
                expected_reference=_reference_id(expected),
                actual_reference=_reference_id(actual),
                expected_sequence_number=_sequence_number(expected),
                actual_sequence_number=_sequence_number(actual),
                divergence_fields=divergence_fields,
                diagnostic=(
                    "Replay matched expected semantics for this step."
                    if not divergence_fields
                    else "Replay diverged from the expected semantics for this step."
                ),
            )
        )
        for field_name in divergence_fields:
            diffs.append(
                ReplayExpectedActualDiff(
                    stream_name=stream_name,
                    index=index,
                    field_name=field_name,
                    expected=expected_payload.get(field_name),
                    actual=actual_payload.get(field_name),
                    expected_reference=_reference_id(expected),
                    actual_reference=_reference_id(actual),
                    diagnostic=(
                        f"{stream_name} diverged at index {index} on {field_name}."
                    ),
                )
            )
    return stepwise, diffs


def _artifact_record(
    certification_id: str,
    case_id: str,
    role: str,
    payload: Any,
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=f"{certification_id}_{role}",
        artifact_role=role,
        relative_path=f"verification/replay_certification/{case_id}/{role}.json",
        sha256=_sha256_payload(payload),
        content_type="application/json",
    )


def _build_artifact_manifest(
    request: ReplayCertificationRequest,
    diff_payload: dict[str, Any],
    stepwise_payload: dict[str, Any],
    reason_payload: dict[str, Any],
) -> ArtifactManifest:
    expected_trace_payload = {
        "signal_trace": [item.to_dict() for item in request.expected_signal_trace],
        "order_intent_trace": [
            item.to_dict() for item in request.expected_order_intent_trace
        ],
        "risk_action_trace": [
            item.to_dict() for item in request.expected_risk_action_trace
        ],
        "contract_state_trace": [
            item.to_dict() for item in request.expected_contract_state_trace
        ],
        "freshness_watermark_trace": [
            item.to_dict() for item in request.expected_freshness_watermark_trace
        ],
    }
    actual_trace_payload = {
        "signal_trace": [item.to_dict() for item in request.actual_signal_trace],
        "order_intent_trace": [
            item.to_dict() for item in request.actual_order_intent_trace
        ],
        "risk_action_trace": [item.to_dict() for item in request.actual_risk_action_trace],
        "contract_state_trace": [
            item.to_dict() for item in request.actual_contract_state_trace
        ],
        "freshness_watermark_trace": [
            item.to_dict() for item in request.actual_freshness_watermark_trace
        ],
    }
    artifacts = [
        _artifact_record(
            request.certification_id,
            request.case_id,
            "expected_trace",
            expected_trace_payload,
        ).to_dict(),
        _artifact_record(
            request.certification_id,
            request.case_id,
            "actual_trace",
            actual_trace_payload,
        ).to_dict(),
        _artifact_record(
            request.certification_id,
            request.case_id,
            "stepwise_trace",
            stepwise_payload,
        ).to_dict(),
        _artifact_record(
            request.certification_id,
            request.case_id,
            "divergence_report",
            diff_payload,
        ).to_dict(),
        _artifact_record(
            request.certification_id,
            request.case_id,
            "operator_reason_bundle",
            reason_payload,
        ).to_dict(),
    ]
    return ArtifactManifest(
        manifest_id=f"artifact_manifest_{request.certification_id}",
        generated_at_utc=_utcnow(),
        retention_class="promotion_review_and_incident_investigation",
        contains_secrets=False,
        redaction_policy="opaque_identifiers_only",
        artifacts=artifacts,
    )


def _build_structured_logs(
    request: ReplayCertificationRequest,
    manifest: ArtifactManifest,
    final_reason_code: str,
    final_explanation: str,
    readiness_reason_code: str,
    readiness_explanation: str,
) -> list[dict[str, Any]]:
    referenced_ids = [
        request.bundle.bundle_id,
        request.registration.registration_log_id,
        request.replay_context.replay_context_id,
        request.certification_id,
    ]
    if request.prior_certification_id is not None:
        referenced_ids.append(request.prior_certification_id)
    records = [
        StructuredLogRecord(
            schema_version=STRUCTURED_LOG_SCHEMA_VERSION,
            event_type="replay_certification_started",
            plane="certification",
            event_id=f"{request.certification_id}:started",
            recorded_at_utc=_utcnow(),
            correlation_id=request.replay_context.correlation_id,
            decision_trace_id=request.decision_trace_id,
            reason_code="REPLAY_CERTIFICATION_STARTED",
            reason_summary="Deterministic replay certification started.",
            referenced_ids=referenced_ids,
            redacted_fields=[],
            omitted_fields=[],
            artifact_manifest=manifest.to_dict(),
        ),
        StructuredLogRecord(
            schema_version=STRUCTURED_LOG_SCHEMA_VERSION,
            event_type="replay_certification_readiness_checked",
            plane="certification",
            event_id=f"{request.certification_id}:readiness",
            recorded_at_utc=_utcnow(),
            correlation_id=request.replay_context.correlation_id,
            decision_trace_id=request.decision_trace_id,
            reason_code=readiness_reason_code,
            reason_summary=readiness_explanation,
            referenced_ids=referenced_ids,
            redacted_fields=[],
            omitted_fields=[],
            artifact_manifest=manifest.to_dict(),
        ),
        StructuredLogRecord(
            schema_version=STRUCTURED_LOG_SCHEMA_VERSION,
            event_type="replay_certification_completed",
            plane="certification",
            event_id=f"{request.certification_id}:completed",
            recorded_at_utc=_utcnow(),
            correlation_id=request.replay_context.correlation_id,
            decision_trace_id=request.decision_trace_id,
            reason_code=final_reason_code,
            reason_summary=final_explanation,
            referenced_ids=referenced_ids,
            redacted_fields=[],
            omitted_fields=[],
            artifact_manifest=manifest.to_dict(),
        ),
    ]
    return [record.to_dict() for record in records]


def evaluate_replay_certification(
    request: ReplayCertificationRequest,
) -> ReplayCertificationReport:
    readiness_report = validate_candidate_bundle_replay_readiness(
        request.case_id,
        request.bundle,
        request.registration,
        request.replay_context,
    )
    rule_trace = [
        "Replay readiness must pass before deterministic replay certification begins.",
        "Signal values, timestamps, order-intent sequences, risk actions, contract-state decisions, decision sequence numbers, and freshness-watermark handling must match exactly.",
        "Incremental recertification is allowed only when dependency change scope is narrow enough to preserve certification intent.",
    ]

    stepwise_trace: list[StepwiseTraceEntry] = []
    diffs: list[ReplayExpectedActualDiff] = []
    status = ReplayCertificationStatus.PASS
    reason_code = "REPLAY_CERTIFICATION_PASSED"
    explanation = (
        "Replay reproduced the frozen candidate's expected behavior across all required streams."
    )
    remediation = "No remediation required."

    if readiness_report.status != PacketStatus.PASS.value:
        status = ReplayCertificationStatus(readiness_report.status)
        reason_code = "REPLAY_CERTIFICATION_REPLAY_NOT_READY"
        explanation = (
            "Replay certification cannot begin until replay readiness is closed for the frozen candidate bundle."
        )
        remediation = readiness_report.remediation
    elif (
        request.certification_mode == ReplayCertificationMode.INCREMENTAL
        and request.prior_certification_id is None
    ):
        status = ReplayCertificationStatus.INVALID
        reason_code = "REPLAY_CERTIFICATION_INCREMENTAL_BASELINE_MISSING"
        explanation = (
            "Incremental replay recertification requires the prior certification id so the narrow change can be audited."
        )
        remediation = (
            "Attach the superseded replay certification id or rerun as a full certification."
        )
    elif (
        request.certification_mode == ReplayCertificationMode.INCREMENTAL
        and request.dependency_change_scope is not DependencyChangeScope.NARROW
    ):
        status = ReplayCertificationStatus.VIOLATION
        reason_code = "REPLAY_CERTIFICATION_INCREMENTAL_SCOPE_TOO_BROAD"
        explanation = (
            "Incremental replay recertification is only allowed for narrow dependency changes."
        )
        remediation = (
            "Promote this replay run to a full certification or reduce the dependency change scope."
        )
    else:
        stream_specs = (
            ("signal_trace", request.expected_signal_trace, request.actual_signal_trace),
            (
                "order_intent_trace",
                request.expected_order_intent_trace,
                request.actual_order_intent_trace,
            ),
            (
                "risk_action_trace",
                request.expected_risk_action_trace,
                request.actual_risk_action_trace,
            ),
            (
                "contract_state_trace",
                request.expected_contract_state_trace,
                request.actual_contract_state_trace,
            ),
            (
                "freshness_watermark_trace",
                request.expected_freshness_watermark_trace,
                request.actual_freshness_watermark_trace,
            ),
        )
        for stream_name, expected, actual in stream_specs:
            stream_stepwise, stream_diffs = _compare_stream(stream_name, expected, actual)
            stepwise_trace.extend(stream_stepwise)
            diffs.extend(stream_diffs)

        if diffs:
            first = diffs[0]
            status = ReplayCertificationStatus.VIOLATION
            reason_code = "REPLAY_CERTIFICATION_DIVERGENCE_DETECTED"
            explanation = (
                f"Replay diverged on {first.stream_name} field {first.field_name} at step {first.index}."
            )
            remediation = (
                "Inspect the retained divergence report, stepwise trace, and referenced artifacts before allowing paper promotion."
            )

    diff_payload = {
        "certification_id": request.certification_id,
        "case_id": request.case_id,
        "expected_vs_actual_diffs": [diff.to_dict() for diff in diffs],
    }
    stepwise_payload = {
        "certification_id": request.certification_id,
        "case_id": request.case_id,
        "stepwise_trace": [entry.to_dict() for entry in stepwise_trace],
    }
    operator_reason_bundle = OperatorReasonBundle(
        summary=explanation,
        gate_summary=(
            "Replay certification satisfied the mandatory paper-trading gate."
            if status is ReplayCertificationStatus.PASS
            else "Replay certification blocked the candidate from entering paper trading."
        ),
        rule_trace=rule_trace,
        remediation_hints=[
            remediation,
            "Attach this certification report to promotion review and incident investigation records.",
        ],
    )
    reason_payload = operator_reason_bundle.to_dict()
    manifest = _build_artifact_manifest(
        request,
        diff_payload=diff_payload,
        stepwise_payload=stepwise_payload,
        reason_payload=reason_payload,
    )
    structured_logs = _build_structured_logs(
        request,
        manifest,
        final_reason_code=reason_code,
        final_explanation=explanation,
        readiness_reason_code=readiness_report.reason_code,
        readiness_explanation=readiness_report.explanation,
    )
    diff_dicts = [diff.to_dict() for diff in diffs]

    return ReplayCertificationReport(
        case_id=request.case_id,
        certification_id=request.certification_id,
        bundle_id=request.bundle.bundle_id,
        replay_context_id=request.replay_context.replay_context_id,
        correlation_id=request.replay_context.correlation_id,
        status=status.value,
        reason_code=reason_code,
        certification_mode=request.certification_mode.value,
        dependency_change_scope=request.dependency_change_scope.value,
        replay_readiness_reason_code=readiness_report.reason_code,
        paper_entry_permitted=status is ReplayCertificationStatus.PASS,
        incremental_recertification_allowed=(
            request.certification_mode == ReplayCertificationMode.INCREMENTAL
            and request.dependency_change_scope is DependencyChangeScope.NARROW
        ),
        expected_vs_actual_diffs=diff_dicts,
        first_divergence=diff_dicts[0] if diff_dicts else None,
        stepwise_trace=[entry.to_dict() for entry in stepwise_trace],
        artifact_manifest=manifest.to_dict(),
        structured_logs=structured_logs,
        operator_reason_bundle=reason_payload,
        explanation=explanation,
        remediation=remediation,
    )
