"""Paper and shadow-live mandatory stage policy contract."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.deployment_packets import PromotionLane
from shared.policy.overnight_candidate import (
    REQUIRED_GLOBAL_SCENARIO_TYPES,
    REQUIRED_LANE_SCENARIO_TYPES,
    OvernightCandidateClass,
    OvernightEvidenceLane,
    OvernightEvidenceRecord,
)

SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION = 1
STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []

PAPER_OBJECTIVE_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "live_market_data_behavior",
        "runtime",
        "Validate live market-data behavior on the paper lane.",
    ),
    (
        "live_bar_construction",
        "runtime",
        "Validate live bar construction before promotion beyond paper.",
    ),
    (
        "operational_timing",
        "runtime",
        "Measure operational timing under live-like conditions.",
    ),
    (
        "broker_api_behavior",
        "broker",
        "Confirm the broker API behaves coherently on the paper route.",
    ),
    (
        "real_reconciliation_flow",
        "broker",
        "Exercise the real reconciliation flow during paper trading.",
    ),
    (
        "execution_profile_realism",
        "evidence",
        "Capture execution-profile realism evidence under paper conditions.",
    ),
    (
        "databento_ibkr_bar_parity",
        "evidence",
        "Retain Databento-to-IBKR bar-parity evidence for the paper stage.",
    ),
    (
        "strategy_health_drift",
        "readiness",
        "Measure strategy-health drift before live-lane entry.",
    ),
    (
        "data_quality_behavior",
        "readiness",
        "Evaluate data-quality behavior on the paper route.",
    ),
    (
        "operating_envelope_realism",
        "readiness",
        "Demonstrate operating-envelope realism during paper trading.",
    ),
    (
        "account_fit_live_like_conditions",
        "readiness",
        "Confirm account fit under live-like paper conditions.",
    ),
)

SHADOW_LIVE_OBJECTIVE_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "production_account_entitlements",
        "broker",
        "Confirm production market-data entitlements and permissions.",
    ),
    (
        "contract_conformance_live_lane",
        "broker",
        "Validate contract conformance on the actual live connectivity lane.",
    ),
    (
        "session_reset_and_reconnect_behavior",
        "runtime",
        "Exercise session reset and reconnect behavior on the shadow-live lane.",
    ),
    (
        "real_operator_controls",
        "readiness",
        "Validate operator controls on the shadow-live lane.",
    ),
    (
        "suppressed_order_mutation_sink",
        "broker",
        "Validate suppressed or diverted order-mutation flow without economics.",
    ),
    (
        "clean_reconciliation_and_intent_logging",
        "evidence",
        "Retain clean reconciliation and intent logging without economic mutation.",
    ),
)


def _utcnow() -> str:
    return canonicalize_persisted_timestamp(
        _dt.datetime.now(_dt.timezone.utc)
    ).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
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


def _require_supported_schema_version(value: Any, *, label: str) -> int:
    parsed = _require_int(value, label=label)
    if parsed != SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION:
        raise ValueError(f"{label}: unsupported schema_version")
    return parsed


def _require_string_sequence(value: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected list")
    return tuple(_require_non_empty_string(item, label=label) for item in value)


def _require_mapping_sequence(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected list")
    return [
        _require_mapping(item, label=f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _require_timestamp(value: Any, *, label: str) -> str:
    timestamp = _require_non_empty_string(value, label=label)
    try:
        parsed = _dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}: expected ISO-8601 timestamp") from exc
    return canonicalize_persisted_timestamp(parsed).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique_strings(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _spec_index(
    specs: tuple[tuple[str, str, str], ...],
) -> dict[str, tuple[str, str]]:
    return {
        objective_id: (objective_group, objective_question)
        for objective_id, objective_group, objective_question in specs
    }


def _objective_evidence_index(
    objective_evidence: tuple["StageObjectiveEvidence", ...],
) -> dict[str, "StageObjectiveEvidence"]:
    indexed: dict[str, StageObjectiveEvidence] = {}
    for evidence in objective_evidence:
        indexed[evidence.objective_id] = evidence
    return indexed


def _artifact_record(
    run_id: str,
    case_id: str,
    role: str,
    payload: Any,
) -> dict[str, Any]:
    return {
        "artifact_id": f"{run_id}_{role}",
        "artifact_role": role,
        "relative_path": f"verification/paper_shadow_stage_policy/{case_id}/{role}.json",
        "sha256": _sha256_payload(payload),
        "content_type": "application/json",
    }


def _reference_artifact_record(
    run_id: str,
    case_id: str,
    role: str,
    reference_id: str,
) -> dict[str, Any]:
    payload = {"reference_id": reference_id, "role": role}
    return {
        "artifact_id": f"{run_id}_{role}_{reference_id}",
        "artifact_role": role,
        "relative_path": f"verification/paper_shadow_stage_policy/{case_id}/references/{role}_{reference_id}.json",
        "sha256": _sha256_payload(payload),
        "content_type": "application/vnd.backtesting_engine.reference+json",
    }


@unique
class PaperShadowStageStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    BLOCKED = "blocked"
    INVALID = "invalid"


@dataclass(frozen=True)
class StageObjectiveEvidence:
    objective_id: str
    objective_group: str
    satisfied: bool
    reference_id: str
    detail: str
    artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageObjectiveEvidence":
        objective_payload = _require_mapping(payload, label="stage_objective_evidence")
        return cls(
            objective_id=_require_non_empty_string(
                _require_present(
                    objective_payload, "objective_id", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.objective_id",
            ),
            objective_group=_require_non_empty_string(
                _require_present(
                    objective_payload, "objective_group", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.objective_group",
            ),
            satisfied=_require_bool(
                _require_present(
                    objective_payload, "satisfied", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.satisfied",
            ),
            reference_id=_require_non_empty_string(
                _require_present(
                    objective_payload, "reference_id", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.reference_id",
            ),
            detail=_require_non_empty_string(
                _require_present(
                    objective_payload, "detail", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.detail",
            ),
            artifact_ids=_require_string_sequence(
                _require_present(
                    objective_payload, "artifact_ids", label="stage_objective_evidence"
                ),
                label="stage_objective_evidence.artifact_ids",
            ),
        )


@dataclass(frozen=True)
class StageObjectiveCheck:
    check_id: str
    stage_id: str
    objective_id: str
    objective_group: str
    passed: bool
    reason_code: str
    diagnostic: str
    expected_question: str
    reference_id: str | None
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class PaperShadowStagePolicyRequest:
    case_id: str
    candidate_bundle_id: str
    requested_lane: str
    paper_pass_evidence_id: str | None
    shadow_pass_evidence_id: str | None
    market_data_entitlement_check_id: str | None
    paper_objectives: tuple[StageObjectiveEvidence, ...]
    shadow_live_objectives: tuple[StageObjectiveEvidence, ...] = ()
    overnight_candidate_class: str = OvernightCandidateClass.NONE.value
    overnight_evidence_records: tuple[OvernightEvidenceRecord, ...] = ()
    correlation_id: str = ""
    operator_reason_bundle: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "candidate_bundle_id": self.candidate_bundle_id,
            "requested_lane": self.requested_lane,
            "paper_pass_evidence_id": self.paper_pass_evidence_id,
            "shadow_pass_evidence_id": self.shadow_pass_evidence_id,
            "market_data_entitlement_check_id": self.market_data_entitlement_check_id,
            "paper_objectives": [objective.to_dict() for objective in self.paper_objectives],
            "shadow_live_objectives": [
                objective.to_dict() for objective in self.shadow_live_objectives
            ],
            "overnight_candidate_class": self.overnight_candidate_class,
            "overnight_evidence_records": [
                record.to_dict() for record in self.overnight_evidence_records
            ],
            "correlation_id": self.correlation_id,
            "operator_reason_bundle": list(self.operator_reason_bundle),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PaperShadowStagePolicyRequest":
        request_payload = _require_mapping(
            payload, label="paper_shadow_stage_policy_request"
        )
        return cls(
            case_id=_require_non_empty_string(
                _require_present(
                    request_payload, "case_id", label="paper_shadow_stage_policy_request"
                ),
                label="paper_shadow_stage_policy_request.case_id",
            ),
            candidate_bundle_id=_require_non_empty_string(
                _require_present(
                    request_payload,
                    "candidate_bundle_id",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.candidate_bundle_id",
            ),
            requested_lane=_require_non_empty_string(
                _require_present(
                    request_payload,
                    "requested_lane",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.requested_lane",
            ),
            paper_pass_evidence_id=_require_optional_string(
                _require_present(
                    request_payload,
                    "paper_pass_evidence_id",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.paper_pass_evidence_id",
            ),
            shadow_pass_evidence_id=_require_optional_string(
                _require_present(
                    request_payload,
                    "shadow_pass_evidence_id",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.shadow_pass_evidence_id",
            ),
            market_data_entitlement_check_id=_require_optional_string(
                _require_present(
                    request_payload,
                    "market_data_entitlement_check_id",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.market_data_entitlement_check_id",
            ),
            paper_objectives=tuple(
                StageObjectiveEvidence.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "paper_objectives",
                        label="paper_shadow_stage_policy_request",
                    ),
                    label="paper_shadow_stage_policy_request.paper_objectives",
                )
            ),
            shadow_live_objectives=tuple(
                StageObjectiveEvidence.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "shadow_live_objectives",
                        label="paper_shadow_stage_policy_request",
                    ),
                    label="paper_shadow_stage_policy_request.shadow_live_objectives",
                )
            ),
            overnight_candidate_class=_require_non_empty_string(
                _require_present(
                    request_payload,
                    "overnight_candidate_class",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.overnight_candidate_class",
            ),
            overnight_evidence_records=tuple(
                OvernightEvidenceRecord.from_dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        request_payload,
                        "overnight_evidence_records",
                        label="paper_shadow_stage_policy_request",
                    ),
                    label="paper_shadow_stage_policy_request.overnight_evidence_records",
                )
            ),
            correlation_id=_require_non_empty_string(
                _require_present(
                    request_payload,
                    "correlation_id",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.correlation_id",
            ),
            operator_reason_bundle=_require_string_sequence(
                _require_present(
                    request_payload,
                    "operator_reason_bundle",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.operator_reason_bundle",
            ),
            schema_version=_require_supported_schema_version(
                _require_present(
                    request_payload,
                    "schema_version",
                    label="paper_shadow_stage_policy_request",
                ),
                label="paper_shadow_stage_policy_request.schema_version",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "PaperShadowStagePolicyRequest":
        return cls.from_dict(_decode_json_object(payload, label="paper_shadow_stage_policy_request"))


@dataclass(frozen=True)
class PaperShadowStagePolicyReport:
    schema_version: int
    case_id: str
    candidate_bundle_id: str
    requested_lane: str
    status: str
    reason_code: str
    paper_stage_complete: bool
    shadow_live_stage_complete: bool
    overnight_evidence_complete: bool
    requested_lane_permitted: bool
    live_activation_permitted: bool
    decision_trace: list[dict[str, Any]]
    expected_vs_actual_diffs: list[dict[str, Any]]
    retained_artifact_ids: tuple[str, ...]
    operator_reason_bundle: dict[str, Any]
    artifact_manifest: dict[str, Any]
    structured_logs: list[dict[str, Any]]
    context: dict[str, Any]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PaperShadowStagePolicyReport":
        report_payload = _require_mapping(payload, label="paper_shadow_stage_policy_report")
        return cls(
            schema_version=_require_supported_schema_version(
                _require_present(
                    report_payload,
                    "schema_version",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.schema_version",
            ),
            case_id=_require_non_empty_string(
                _require_present(
                    report_payload, "case_id", label="paper_shadow_stage_policy_report"
                ),
                label="paper_shadow_stage_policy_report.case_id",
            ),
            candidate_bundle_id=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "candidate_bundle_id",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.candidate_bundle_id",
            ),
            requested_lane=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "requested_lane",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.requested_lane",
            ),
            status=PaperShadowStageStatus(
                _require_non_empty_string(
                    _require_present(
                        report_payload,
                        "status",
                        label="paper_shadow_stage_policy_report",
                    ),
                    label="paper_shadow_stage_policy_report.status",
                )
            ).value,
            reason_code=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "reason_code",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.reason_code",
            ),
            paper_stage_complete=_require_bool(
                _require_present(
                    report_payload,
                    "paper_stage_complete",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.paper_stage_complete",
            ),
            shadow_live_stage_complete=_require_bool(
                _require_present(
                    report_payload,
                    "shadow_live_stage_complete",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.shadow_live_stage_complete",
            ),
            overnight_evidence_complete=_require_bool(
                _require_present(
                    report_payload,
                    "overnight_evidence_complete",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.overnight_evidence_complete",
            ),
            requested_lane_permitted=_require_bool(
                _require_present(
                    report_payload,
                    "requested_lane_permitted",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.requested_lane_permitted",
            ),
            live_activation_permitted=_require_bool(
                _require_present(
                    report_payload,
                    "live_activation_permitted",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.live_activation_permitted",
            ),
            decision_trace=_require_mapping_sequence(
                _require_present(
                    report_payload,
                    "decision_trace",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.decision_trace",
            ),
            expected_vs_actual_diffs=[
                dict(item)
                for item in _require_mapping_sequence(
                    _require_present(
                        report_payload,
                        "expected_vs_actual_diffs",
                        label="paper_shadow_stage_policy_report",
                    ),
                    label="paper_shadow_stage_policy_report.expected_vs_actual_diffs",
                )
            ],
            retained_artifact_ids=_require_string_sequence(
                _require_present(
                    report_payload,
                    "retained_artifact_ids",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.retained_artifact_ids",
            ),
            operator_reason_bundle=_require_mapping(
                _require_present(
                    report_payload,
                    "operator_reason_bundle",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.operator_reason_bundle",
            ),
            artifact_manifest=_require_mapping(
                _require_present(
                    report_payload,
                    "artifact_manifest",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.artifact_manifest",
            ),
            structured_logs=_require_mapping_sequence(
                _require_present(
                    report_payload,
                    "structured_logs",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.structured_logs",
            ),
            context=_require_mapping(
                _require_present(
                    report_payload,
                    "context",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.context",
            ),
            explanation=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "explanation",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.explanation",
            ),
            remediation=_require_non_empty_string(
                _require_present(
                    report_payload,
                    "remediation",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.remediation",
            ),
            timestamp=_require_timestamp(
                _require_present(
                    report_payload,
                    "timestamp",
                    label="paper_shadow_stage_policy_report",
                ),
                label="paper_shadow_stage_policy_report.timestamp",
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "PaperShadowStagePolicyReport":
        return cls.from_dict(_decode_json_object(payload, label="paper_shadow_stage_policy_report"))


def _evaluate_stage(
    *,
    stage_id: str,
    evidence_records: tuple[StageObjectiveEvidence, ...],
    specs: tuple[tuple[str, str, str], ...],
) -> tuple[list[StageObjectiveCheck], list[dict[str, Any]], list[str], list[str], dict[str, int]]:
    indexed = _objective_evidence_index(evidence_records)
    checks: list[StageObjectiveCheck] = []
    diffs: list[dict[str, Any]] = []
    missing_objectives: list[str] = []
    failed_objectives: list[str] = []
    group_totals: dict[str, int] = {}
    group_passed: dict[str, int] = {}

    for index, (objective_id, objective_group, objective_question) in enumerate(specs, start=1):
        group_totals[objective_group] = group_totals.get(objective_group, 0) + 1
        evidence = indexed.get(objective_id)
        if evidence is None:
            missing_objectives.append(objective_id)
            checks.append(
                StageObjectiveCheck(
                    check_id=f"{stage_id.upper()}_{index:02d}",
                    stage_id=stage_id,
                    objective_id=objective_id,
                    objective_group=objective_group,
                    passed=False,
                    reason_code=f"{stage_id.upper()}_OBJECTIVE_MISSING",
                    diagnostic=f"{stage_id} objective {objective_id} is missing",
                    expected_question=objective_question,
                    reference_id=None,
                    remediation=f"Record sealed evidence for {objective_id} before promotion.",
                )
            )
            diffs.append(
                {
                    "subject": f"{stage_id}.{objective_id}",
                    "expected": "sealed passing objective evidence",
                    "actual": "missing",
                    "objective_group": objective_group,
                    "expected_question": objective_question,
                }
            )
            continue
        if not evidence.satisfied:
            failed_objectives.append(objective_id)
            checks.append(
                StageObjectiveCheck(
                    check_id=f"{stage_id.upper()}_{index:02d}",
                    stage_id=stage_id,
                    objective_id=objective_id,
                    objective_group=objective_group,
                    passed=False,
                    reason_code=f"{stage_id.upper()}_OBJECTIVE_FAILED",
                    diagnostic=evidence.detail,
                    expected_question=objective_question,
                    reference_id=evidence.reference_id,
                    remediation=f"Remediate {objective_id} and rerun the {stage_id} stage.",
                )
            )
            diffs.append(
                {
                    "subject": f"{stage_id}.{objective_id}",
                    "expected": "passed",
                    "actual": "failed",
                    "objective_group": objective_group,
                    "expected_question": objective_question,
                    "reference_id": evidence.reference_id,
                    "diagnostic": evidence.detail,
                }
            )
            continue

        group_passed[objective_group] = group_passed.get(objective_group, 0) + 1
        checks.append(
            StageObjectiveCheck(
                check_id=f"{stage_id.upper()}_{index:02d}",
                stage_id=stage_id,
                objective_id=objective_id,
                objective_group=objective_group,
                passed=True,
                reason_code=f"{stage_id.upper()}_OBJECTIVE_SATISFIED",
                diagnostic=evidence.detail,
                expected_question=objective_question,
                reference_id=evidence.reference_id,
                remediation="No action required.",
            )
        )

    group_summary = {
        group: group_passed.get(group, 0) for group in sorted(group_totals)
    }
    for group, total in group_totals.items():
        group_summary[f"{group}_required"] = total
    return checks, diffs, missing_objectives, failed_objectives, group_summary


def _evaluate_overnight_evidence(
    overnight_candidate_class: str,
    evidence_records: tuple[OvernightEvidenceRecord, ...],
) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    if overnight_candidate_class == OvernightCandidateClass.NONE.value:
        return True, [], {"required": False, "missing_lanes": [], "missing_scenarios": []}

    passed_records = [
        record
        for record in evidence_records
        if record.passed
    ]
    passed_keys = {
        (record.lane, record.scenario_type)
        for record in passed_records
    }
    missing_pairs: list[dict[str, str]] = []
    for lane in (OvernightEvidenceLane.PAPER.value, OvernightEvidenceLane.SHADOW_LIVE.value):
        for scenario_type in REQUIRED_LANE_SCENARIO_TYPES:
            if (lane, scenario_type) not in passed_keys:
                missing_pairs.append({"lane": lane, "scenario_type": scenario_type})

    passed_scenarios = {record.scenario_type for record in passed_records}
    missing_global = [
        scenario_type
        for scenario_type in REQUIRED_GLOBAL_SCENARIO_TYPES
        if scenario_type not in passed_scenarios
    ]

    diffs: list[dict[str, Any]] = []
    for missing_pair in missing_pairs:
        diffs.append(
            {
                "subject": "overnight_evidence",
                "expected": "passed evidence record",
                "actual": "missing",
                "lane": missing_pair["lane"],
                "scenario_type": missing_pair["scenario_type"],
            }
        )
    for scenario_type in missing_global:
        diffs.append(
            {
                "subject": "overnight_global_scenario",
                "expected": "passed global scenario evidence",
                "actual": "missing",
                "scenario_type": scenario_type,
            }
        )

    return (
        not missing_pairs and not missing_global,
        diffs,
        {
            "required": True,
            "overnight_candidate_class": overnight_candidate_class,
            "missing_lanes": missing_pairs,
            "missing_scenarios": missing_global,
        },
    )


def evaluate_paper_shadow_stage_policy(
    request: PaperShadowStagePolicyRequest,
) -> PaperShadowStagePolicyReport:
    """Evaluate mandatory paper and shadow-live stages before live activation."""

    run_id = f"{request.case_id}_{_sha256_payload(request.to_dict())[:12]}"
    validation_diffs: list[dict[str, Any]] = []

    if request.schema_version != SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION:
        validation_diffs.append(
            {
                "subject": "schema_version",
                "expected": SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION,
                "actual": request.schema_version,
            }
        )

    try:
        requested_lane = PromotionLane(request.requested_lane)
    except ValueError:
        validation_diffs.append(
            {
                "subject": "requested_lane",
                "expected": [lane.value for lane in PromotionLane],
                "actual": request.requested_lane,
            }
        )
        requested_lane = None

    try:
        overnight_class = OvernightCandidateClass(request.overnight_candidate_class)
    except ValueError:
        validation_diffs.append(
            {
                "subject": "overnight_candidate_class",
                "expected": [value.value for value in OvernightCandidateClass],
                "actual": request.overnight_candidate_class,
            }
        )
        overnight_class = OvernightCandidateClass.NONE

    if validation_diffs:
        VALIDATION_ERRORS[:] = [diff["subject"] for diff in validation_diffs]
        manifest = {
            "manifest_id": f"artifact_manifest_{run_id}",
            "generated_at_utc": _utcnow(),
            "retention_class": "promotion_stage_validation",
            "contains_secrets": False,
            "redaction_policy": "opaque_identifiers_only",
            "artifacts": [
                _artifact_record(run_id, request.case_id, "stage_policy_request", request.to_dict()),
                _artifact_record(
                    run_id,
                    request.case_id,
                    "expected_vs_actual_diffs",
                    validation_diffs,
                ),
            ],
        }
        return PaperShadowStagePolicyReport(
            schema_version=SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_bundle_id=request.candidate_bundle_id,
            requested_lane=request.requested_lane,
            status=PaperShadowStageStatus.INVALID.value,
            reason_code="PAPER_SHADOW_STAGE_POLICY_REQUEST_INVALID",
            paper_stage_complete=False,
            shadow_live_stage_complete=False,
            overnight_evidence_complete=False,
            requested_lane_permitted=False,
            live_activation_permitted=False,
            decision_trace=[],
            expected_vs_actual_diffs=validation_diffs,
            retained_artifact_ids=_unique_strings(
                [artifact["artifact_id"] for artifact in manifest["artifacts"]]
            ),
            operator_reason_bundle={
                "gate_summary": {
                    "status": PaperShadowStageStatus.INVALID.value,
                    "reason_code": "PAPER_SHADOW_STAGE_POLICY_REQUEST_INVALID",
                },
                "operator_notes": list(request.operator_reason_bundle),
            },
            artifact_manifest=manifest,
            structured_logs=[
                {
                    "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
                    "event_type": "paper_shadow_stage_policy.invalid",
                    "correlation_id": request.correlation_id,
                    "run_id": run_id,
                    "case_id": request.case_id,
                    "candidate_bundle_id": request.candidate_bundle_id,
                    "reason_code": "PAPER_SHADOW_STAGE_POLICY_REQUEST_INVALID",
                    "details": validation_diffs,
                    "timestamp": _utcnow(),
                }
            ],
            context={"validation_diffs": validation_diffs},
            explanation="The stage-policy request is malformed and cannot be evaluated.",
            remediation="Correct the invalid request fields and rerun the stage-policy check.",
        )

    paper_checks, paper_diffs, paper_missing, paper_failed, paper_group_summary = _evaluate_stage(
        stage_id=PromotionLane.PAPER.value,
        evidence_records=request.paper_objectives,
        specs=PAPER_OBJECTIVE_SPECS,
    )
    if requested_lane is PromotionLane.LIVE or request.shadow_live_objectives:
        (
            shadow_checks,
            shadow_diffs,
            shadow_missing,
            shadow_failed,
            shadow_group_summary,
        ) = _evaluate_stage(
            stage_id=PromotionLane.SHADOW_LIVE.value,
            evidence_records=request.shadow_live_objectives,
            specs=SHADOW_LIVE_OBJECTIVE_SPECS,
        )
    else:
        shadow_checks = []
        shadow_diffs = []
        shadow_missing = []
        shadow_failed = []
        shadow_group_summary = {}
    overnight_complete, overnight_diffs, overnight_summary = _evaluate_overnight_evidence(
        overnight_class.value,
        request.overnight_evidence_records,
    )

    paper_stage_complete = not paper_missing and not paper_failed
    shadow_live_stage_complete = (
        requested_lane is PromotionLane.LIVE or bool(request.shadow_live_objectives)
    ) and not shadow_missing and not shadow_failed

    expected_vs_actual_diffs = [*paper_diffs, *shadow_diffs]

    if requested_lane in (PromotionLane.SHADOW_LIVE, PromotionLane.LIVE) and not request.paper_pass_evidence_id:
        expected_vs_actual_diffs.append(
            {
                "subject": "paper_pass_evidence_id",
                "expected": "sealed paper-pass evidence identifier",
                "actual": "missing",
            }
        )
        paper_stage_complete = False

    if requested_lane is PromotionLane.LIVE and not request.shadow_pass_evidence_id:
        expected_vs_actual_diffs.append(
            {
                "subject": "shadow_pass_evidence_id",
                "expected": "sealed shadow-live pass evidence identifier",
                "actual": "missing",
            }
        )
        shadow_live_stage_complete = False

    if requested_lane is PromotionLane.LIVE and not request.market_data_entitlement_check_id:
        expected_vs_actual_diffs.append(
            {
                "subject": "market_data_entitlement_check_id",
                "expected": "production entitlement check identifier",
                "actual": "missing",
            }
        )
        shadow_live_stage_complete = False

    if requested_lane is PromotionLane.LIVE and overnight_class is not OvernightCandidateClass.NONE:
        expected_vs_actual_diffs.extend(overnight_diffs)

    requested_lane_permitted = requested_lane is PromotionLane.PAPER
    if requested_lane is PromotionLane.SHADOW_LIVE:
        requested_lane_permitted = paper_stage_complete
    elif requested_lane is PromotionLane.LIVE:
        requested_lane_permitted = (
            paper_stage_complete
            and shadow_live_stage_complete
            and (overnight_complete or overnight_class is OvernightCandidateClass.NONE)
        )

    live_activation_permitted = (
        requested_lane is PromotionLane.LIVE and requested_lane_permitted
    )

    status = PaperShadowStageStatus.PASS
    reason_code = "PAPER_AND_SHADOW_STAGE_REQUIREMENTS_SATISFIED"
    explanation = (
        "Paper and shadow-live stage evidence is complete for the requested promotion lane."
    )
    remediation = "No action required."

    if requested_lane is PromotionLane.SHADOW_LIVE and not requested_lane_permitted:
        status = PaperShadowStageStatus.BLOCKED
        reason_code = "PAPER_STAGE_OBJECTIVES_INCOMPLETE"
        explanation = "Paper-stage objectives are incomplete, so shadow-live entry is blocked."
        remediation = "Complete the missing or failed paper-stage objectives and rerun the gate."
    elif requested_lane is PromotionLane.SHADOW_LIVE:
        reason_code = "PAPER_STAGE_COMPLETED_FOR_SHADOW_LIVE"
        explanation = "Paper-stage evidence is complete, so the candidate may enter shadow-live."
    elif requested_lane is PromotionLane.LIVE and not paper_stage_complete:
        status = PaperShadowStageStatus.BLOCKED
        reason_code = "PAPER_STAGE_OBJECTIVES_INCOMPLETE"
        explanation = "Live activation is blocked because paper-stage objectives are incomplete."
        remediation = "Complete the paper-stage evidence set and rerun the gate."
    elif requested_lane is PromotionLane.LIVE and not shadow_live_stage_complete:
        status = PaperShadowStageStatus.BLOCKED
        reason_code = "SHADOW_LIVE_STAGE_OBJECTIVES_INCOMPLETE"
        explanation = "Live activation is blocked because shadow-live objectives are incomplete."
        remediation = "Complete the shadow-live evidence set and rerun the gate."
    elif (
        requested_lane is PromotionLane.LIVE
        and overnight_class is not OvernightCandidateClass.NONE
        and not overnight_complete
    ):
        status = PaperShadowStageStatus.BLOCKED
        reason_code = "OVERNIGHT_EVIDENCE_INCOMPLETE"
        explanation = (
            "Live activation is blocked because the overnight candidate lacks required overnight evidence."
        )
        remediation = "Collect the missing overnight evidence classes on paper and shadow-live lanes."

    decision_trace = [check.to_dict() for check in [*paper_checks, *shadow_checks]]

    structured_logs = [
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "paper_shadow_stage_policy.stage_evaluated",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "candidate_bundle_id": request.candidate_bundle_id,
            "stage_id": PromotionLane.PAPER.value,
            "complete": paper_stage_complete,
            "missing_objectives": paper_missing,
            "failed_objectives": paper_failed,
            "objective_group_summary": paper_group_summary,
            "timestamp": _utcnow(),
        },
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "paper_shadow_stage_policy.stage_evaluated",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "candidate_bundle_id": request.candidate_bundle_id,
            "stage_id": PromotionLane.SHADOW_LIVE.value,
            "complete": shadow_live_stage_complete,
            "missing_objectives": shadow_missing,
            "failed_objectives": shadow_failed,
            "objective_group_summary": shadow_group_summary,
            "timestamp": _utcnow(),
        },
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "paper_shadow_stage_policy.decision",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "candidate_bundle_id": request.candidate_bundle_id,
            "requested_lane": requested_lane.value,
            "status": status.value,
            "reason_code": reason_code,
            "requested_lane_permitted": requested_lane_permitted,
            "live_activation_permitted": live_activation_permitted,
            "timestamp": _utcnow(),
        },
    ]

    operator_reason_bundle = {
        "gate_summary": {
            "status": status.value,
            "reason_code": reason_code,
            "requested_lane": requested_lane.value,
            "requested_lane_permitted": requested_lane_permitted,
            "live_activation_permitted": live_activation_permitted,
        },
        "paper_stage": {
            "complete": paper_stage_complete,
            "missing_objectives": paper_missing,
            "failed_objectives": paper_failed,
            "objective_group_summary": paper_group_summary,
            "pass_evidence_id": request.paper_pass_evidence_id,
        },
        "shadow_live_stage": {
            "complete": shadow_live_stage_complete,
            "missing_objectives": shadow_missing,
            "failed_objectives": shadow_failed,
            "objective_group_summary": shadow_group_summary,
            "pass_evidence_id": request.shadow_pass_evidence_id,
            "market_data_entitlement_check_id": request.market_data_entitlement_check_id,
        },
        "overnight": overnight_summary,
        "operator_notes": list(request.operator_reason_bundle),
    }

    artifacts = [
        _artifact_record(run_id, request.case_id, "stage_policy_request", request.to_dict()),
        _artifact_record(run_id, request.case_id, "decision_trace", decision_trace),
        _artifact_record(
            run_id, request.case_id, "expected_vs_actual_diffs", expected_vs_actual_diffs
        ),
        _artifact_record(
            run_id, request.case_id, "operator_reason_bundle", operator_reason_bundle
        ),
        _artifact_record(run_id, request.case_id, "structured_logs", structured_logs),
    ]
    if request.paper_pass_evidence_id:
        artifacts.append(
            _reference_artifact_record(
                run_id,
                request.case_id,
                "paper_pass_evidence",
                request.paper_pass_evidence_id,
            )
        )
    if request.shadow_pass_evidence_id:
        artifacts.append(
            _reference_artifact_record(
                run_id,
                request.case_id,
                "shadow_pass_evidence",
                request.shadow_pass_evidence_id,
            )
        )
    if request.market_data_entitlement_check_id:
        artifacts.append(
            _reference_artifact_record(
                run_id,
                request.case_id,
                "market_data_entitlement_check",
                request.market_data_entitlement_check_id,
            )
        )

    artifact_manifest = {
        "manifest_id": f"artifact_manifest_{run_id}",
        "generated_at_utc": _utcnow(),
        "retention_class": "promotion_stage_reviews",
        "contains_secrets": False,
        "redaction_policy": "opaque_identifiers_only",
        "artifacts": artifacts,
    }
    retained_artifact_ids = _unique_strings(
        [artifact["artifact_id"] for artifact in artifacts]
        + [
            request.paper_pass_evidence_id or "",
            request.shadow_pass_evidence_id or "",
            request.market_data_entitlement_check_id or "",
        ]
        + [
            artifact_id
            for evidence in [*request.paper_objectives, *request.shadow_live_objectives]
            for artifact_id in evidence.artifact_ids
        ]
        + [
            artifact_id
            for evidence in request.overnight_evidence_records
            for artifact_id in evidence.artifact_ids
        ]
    )

    context = {
        "paper_required_objectives": [objective_id for objective_id, _, _ in PAPER_OBJECTIVE_SPECS],
        "shadow_live_required_objectives": [
            objective_id for objective_id, _, _ in SHADOW_LIVE_OBJECTIVE_SPECS
        ],
        "paper_missing_objectives": paper_missing,
        "paper_failed_objectives": paper_failed,
        "shadow_live_missing_objectives": shadow_missing,
        "shadow_live_failed_objectives": shadow_failed,
        "overnight_summary": overnight_summary,
    }

    return PaperShadowStagePolicyReport(
        schema_version=SUPPORTED_PAPER_SHADOW_STAGE_POLICY_SCHEMA_VERSION,
        case_id=request.case_id,
        candidate_bundle_id=request.candidate_bundle_id,
        requested_lane=requested_lane.value,
        status=status.value,
        reason_code=reason_code,
        paper_stage_complete=paper_stage_complete,
        shadow_live_stage_complete=shadow_live_stage_complete,
        overnight_evidence_complete=(
            overnight_complete or overnight_class is OvernightCandidateClass.NONE
        ),
        requested_lane_permitted=requested_lane_permitted,
        live_activation_permitted=live_activation_permitted,
        decision_trace=decision_trace,
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        retained_artifact_ids=retained_artifact_ids,
        operator_reason_bundle=operator_reason_bundle,
        artifact_manifest=artifact_manifest,
        structured_logs=structured_logs,
        context=context,
        explanation=explanation,
        remediation=remediation,
    )
