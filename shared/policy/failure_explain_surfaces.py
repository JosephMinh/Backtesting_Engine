"""Operator and developer explain surfaces for blocking policy and runtime failures."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.bar_parity import BarParityCertificationReport, BarParityStatus
from shared.policy.deployment_packets import PacketStatus, PacketValidationReport
from shared.policy.replay_certification import ReplayCertificationReport
from shared.policy.runtime_recovery import RecoveryValidationReport

SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION = 1
FAILURE_EXPLAIN_STAGE_IDS = (
    "summary",
    "violated_rule",
    "evidence_navigation",
    "next_action",
)
FAILURE_EXPLAIN_WALKTHROUGH_STEP_IDS = (
    "operator_summary",
    "developer_trace",
    "artifact_navigation",
    "next_action",
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must decode from valid JSON") from exc
    if not isinstance(decoded, dict):  # pragma: no cover - defensive
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _unique_strings(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _reference_strings_from_mapping(mapping: dict[str, Any]) -> tuple[str, ...]:
    references: list[str] = []
    for key, value in mapping.items():
        if value in (None, "", [], ()):
            continue
        if key.endswith("_id") and not isinstance(value, (list, tuple, dict)):
            references.append(str(value))
            continue
        if key.endswith("_ids") and isinstance(value, (list, tuple)):
            references.extend(str(item) for item in value if item not in (None, ""))
            continue
        if key == "artifact_manifest" and isinstance(value, dict):
            artifacts = value.get("artifacts", [])
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if isinstance(artifact, dict) and artifact.get("artifact_id"):
                        references.append(str(artifact["artifact_id"]))
    return _unique_strings(references)


def _packet_report_from_dict(payload: dict[str, Any]) -> PacketValidationReport:
    return PacketValidationReport(
        case_id=str(payload["case_id"]),
        packet_kind=str(payload["packet_kind"]),
        packet_id=(
            str(payload["packet_id"]) if payload.get("packet_id") is not None else None
        ),
        status=str(payload["status"]),
        reason_code=str(payload["reason_code"]),
        context=dict(payload["context"]),
        missing_fields=tuple(str(item) for item in payload["missing_fields"]),
        explanation=str(payload["explanation"]),
        remediation=str(payload["remediation"]),
        timestamp=str(payload["timestamp"]),
    )


def _recovery_report_from_dict(payload: dict[str, Any]) -> RecoveryValidationReport:
    return RecoveryValidationReport(
        case_id=str(payload["case_id"]),
        artifact_kind=str(payload["artifact_kind"]),
        artifact_id=(
            str(payload["artifact_id"])
            if payload.get("artifact_id") is not None
            else None
        ),
        status=str(payload["status"]),
        reason_code=str(payload["reason_code"]),
        context=dict(payload["context"]),
        missing_fields=tuple(str(item) for item in payload["missing_fields"]),
        explanation=str(payload["explanation"]),
        remediation=str(payload["remediation"]),
        timestamp=str(payload["timestamp"]),
    )


def _replay_report_from_dict(payload: dict[str, Any]) -> ReplayCertificationReport:
    return ReplayCertificationReport(
        case_id=str(payload["case_id"]),
        certification_id=str(payload["certification_id"]),
        bundle_id=str(payload["bundle_id"]),
        replay_context_id=str(payload["replay_context_id"]),
        correlation_id=str(payload["correlation_id"]),
        status=str(payload["status"]),
        reason_code=str(payload["reason_code"]),
        certification_mode=str(payload["certification_mode"]),
        dependency_change_scope=str(payload["dependency_change_scope"]),
        replay_readiness_reason_code=str(payload["replay_readiness_reason_code"]),
        paper_entry_permitted=bool(payload["paper_entry_permitted"]),
        incremental_recertification_allowed=bool(
            payload["incremental_recertification_allowed"]
        ),
        expected_vs_actual_diffs=[
            dict(item) for item in payload["expected_vs_actual_diffs"]
        ],
        first_divergence=(
            dict(payload["first_divergence"])
            if payload.get("first_divergence") is not None
            else None
        ),
        stepwise_trace=[dict(item) for item in payload["stepwise_trace"]],
        artifact_manifest=dict(payload["artifact_manifest"]),
        structured_logs=[dict(item) for item in payload["structured_logs"]],
        operator_reason_bundle=dict(payload["operator_reason_bundle"]),
        explanation=str(payload["explanation"]),
        remediation=str(payload["remediation"]),
        timestamp=str(payload["timestamp"]),
    )


def _build_rule_trace(
    *,
    source_kind: str,
    reason_code: str,
    explanation: str,
    context: dict[str, Any] | None,
    details: list[str],
) -> list[str]:
    trace = [
        f"source_kind={source_kind}",
        f"reason_code={reason_code}",
        explanation,
    ]
    if context:
        trace.append(f"context_keys={sorted(context.keys())}")
    trace.extend(details)
    return trace


def _diff_identifier(diff: dict[str, Any], fallback_prefix: str, index: int) -> str:
    if diff.get("stream_name") is not None and diff.get("field_name") is not None:
        return (
            f"{diff['stream_name']}:{diff.get('index', index)}:{diff['field_name']}"
        )
    if diff.get("dimension_id") is not None:
        return f"{diff['dimension_id']}:{index}"
    if diff.get("field_name") is not None:
        return f"{fallback_prefix}:{diff['field_name']}:{index}"
    return f"{fallback_prefix}:diff:{index}"


def _packet_correlation_ids(
    report: PacketValidationReport, request: "FailureExplainRequest"
) -> tuple[str, ...]:
    correlation_ids = list(request.correlation_ids)
    context_correlation = report.context.get("correlation_id")
    if context_correlation:
        correlation_ids.append(str(context_correlation))
    return _unique_strings(correlation_ids)


def _recovery_correlation_ids(
    report: RecoveryValidationReport, request: "FailureExplainRequest"
) -> tuple[str, ...]:
    correlation_ids = list(request.correlation_ids)
    context_correlation = report.context.get("correlation_id")
    if context_correlation:
        correlation_ids.append(str(context_correlation))
    return _unique_strings(correlation_ids)


def _replay_correlation_ids(
    report: ReplayCertificationReport, request: "FailureExplainRequest"
) -> tuple[str, ...]:
    return _unique_strings([*request.correlation_ids, report.correlation_id])


def _packet_diffs(report: PacketValidationReport) -> list[dict[str, Any]]:
    if report.reason_code == "SESSION_TRADEABILITY_REQUIRES_GREEN_PACKET":
        actual_status = report.missing_fields[0] if report.missing_fields else "unknown"
        return [
            {
                "field_name": "session_status",
                "expected": "green",
                "actual": actual_status,
                "diagnostic": report.explanation,
            }
        ]
    if report.reason_code == "SESSION_TRADEABILITY_OUTSIDE_VALIDITY_WINDOW":
        return [
            {
                "field_name": "evaluation_window",
                "expected": {
                    "valid_from_utc": report.context.get("session_valid_from_utc"),
                    "valid_to_utc": report.context.get("session_valid_to_utc"),
                },
                "actual": {"evaluated_at_utc": report.context.get("evaluated_at_utc")},
                "diagnostic": report.explanation,
            }
        ]
    if report.reason_code == "SESSION_TRADEABILITY_BINDING_MISMATCH":
        return [
            {
                "field_name": field_name,
                "expected": "match active deployment, promotion packet, and session",
                "actual": "binding mismatch",
                "diagnostic": report.explanation,
            }
            for field_name in report.missing_fields
        ]
    if report.reason_code in {
        "SESSION_TRADEABILITY_FRESHNESS_CHECK_FAILED",
        "SESSION_TRADEABILITY_INFRASTRUCTURE_CHECK_FAILED",
        "PROMOTION_PREFLIGHT_EVIDENCE_STALE",
        "PROMOTION_PREFLIGHT_COMPATIBILITY_INCOMPLETE",
        "PROMOTION_PREFLIGHT_INFRASTRUCTURE_CHECK_FAILED",
    }:
        return [
            {
                "field_name": field_name,
                "expected": "clear",
                "actual": "blocking",
                "diagnostic": report.explanation,
            }
            for field_name in report.missing_fields
        ]
    return [
        {
            "field_name": field_name,
            "expected": "present and policy-valid",
            "actual": "missing or invalid",
            "diagnostic": report.explanation,
        }
        for field_name in report.missing_fields
    ]


def _recovery_diffs(report: RecoveryValidationReport) -> list[dict[str, Any]]:
    if report.missing_fields:
        return [
            {
                "field_name": field_name,
                "expected": "present and governed",
                "actual": "missing or unsafe",
                "diagnostic": report.explanation,
            }
            for field_name in report.missing_fields
        ]
    return []


def _parity_diffs(report: BarParityCertificationReport) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for dimension in report.compared_dimensions:
        if dimension.get("passed", True):
            continue
        diffs.append(
            {
                "dimension_id": dimension.get("dimension_id"),
                "field_name": dimension.get("dimension_name"),
                "expected": dimension.get("research_value"),
                "actual": dimension.get("live_value"),
                "diagnostic": dimension.get("diagnostic"),
            }
        )
    return diffs


def _replay_diff_ids(report: ReplayCertificationReport) -> tuple[str, ...]:
    return tuple(
        _diff_identifier(diff, "replay", index)
        for index, diff in enumerate(report.expected_vs_actual_diffs)
    )


def _stage_cards(
    *,
    source_kind: "FailureExplainSourceKind",
    reason_code: str,
    operator_summary: str,
    developer_summary: str,
    evidence_links: tuple[str, ...],
    next_actions: tuple[str, ...],
) -> tuple["FailureExplainStageCard", ...]:
    return (
        FailureExplainStageCard(
            stage_id="summary",
            stage_label="Summary",
            status="blocked",
            reason_code=reason_code,
            why_it_happened=operator_summary,
            evidence_links=evidence_links,
            next_action=next_actions[0] if next_actions else "Inspect the retained evidence.",
            blocking=True,
        ),
        FailureExplainStageCard(
            stage_id="violated_rule",
            stage_label="Violated Rule",
            status="blocked",
            reason_code=reason_code,
            why_it_happened=developer_summary,
            evidence_links=evidence_links,
            next_action=next_actions[0] if next_actions else "Repair the violated rule.",
            blocking=True,
        ),
        FailureExplainStageCard(
            stage_id="evidence_navigation",
            stage_label="Evidence Navigation",
            status="blocked",
            reason_code=f"{source_kind.value.upper()}_EVIDENCE_NAVIGATION",
            why_it_happened="The explain surface preserves trace links and retained artifacts instead of replacing them.",
            evidence_links=evidence_links,
            next_action=next_actions[1] if len(next_actions) > 1 else next_actions[0],
            blocking=False,
        ),
        FailureExplainStageCard(
            stage_id="next_action",
            stage_label="Next Action",
            status="blocked",
            reason_code=f"{source_kind.value.upper()}_NEXT_ACTION",
            why_it_happened="The failure remains actionable only if the remediation path stays attached to the retained evidence.",
            evidence_links=evidence_links,
            next_action=next_actions[0] if next_actions else "Review the runbook and repair the blocker.",
            blocking=False,
        ),
    )


def _walkthrough_steps(
    *,
    operator_summary: str,
    developer_summary: str,
    evidence_links: tuple[str, ...],
    correlation_ids: tuple[str, ...],
    expected_actual_diff_ids: tuple[str, ...],
    next_actions: tuple[str, ...],
) -> tuple["FailureExplainWalkthroughStep", ...]:
    next_action = next_actions[0] if next_actions else "Inspect the retained evidence."
    return (
        FailureExplainWalkthroughStep(
            step_id="operator_summary",
            title="Operator Summary",
            summary=operator_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_action=next_action,
        ),
        FailureExplainWalkthroughStep(
            step_id="developer_trace",
            title="Developer Trace",
            summary=developer_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_action=next_action,
        ),
        FailureExplainWalkthroughStep(
            step_id="artifact_navigation",
            title="Artifact Navigation",
            summary="Follow the retained artifact and trace links before retrying or escalating.",
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_action=next_actions[1] if len(next_actions) > 1 else next_action,
        ),
        FailureExplainWalkthroughStep(
            step_id="next_action",
            title="Next Action",
            summary=next_action,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_action=next_action,
        ),
    )


@unique
class FailureExplainSourceKind(str, Enum):
    POLICY_FAILURE = "policy_failure"
    READINESS_REJECTION = "readiness_rejection"
    PARITY_DRIFT = "parity_drift"
    REPLAY_DIVERGENCE = "replay_divergence"
    RECOVERY_BLOCK = "recovery_block"


@unique
class FailureExplainOutcome(str, Enum):
    BLOCKED = "blocked"
    INVALID = "invalid"


@unique
class FailureExplainRemediationClass(str, Enum):
    REPAIR_POLICY_BINDINGS = "repair_policy_bindings"
    CLEAR_RUNTIME_BLOCKERS = "clear_runtime_blockers"
    REPAIR_PARITY_SEMANTICS = "repair_parity_semantics"
    RECERTIFY_REPLAY = "recertify_replay"
    HALT_AND_REVIEW = "halt_and_review"
    REPAIR_EXPLAIN_REQUEST = "repair_explain_request"


@dataclass(frozen=True)
class FailureExplainStageCard:
    stage_id: str
    stage_label: str
    status: str
    reason_code: str
    why_it_happened: str
    evidence_links: tuple[str, ...]
    next_action: str
    blocking: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "stage_label": self.stage_label,
            "status": self.status,
            "reason_code": self.reason_code,
            "why_it_happened": self.why_it_happened,
            "evidence_links": list(self.evidence_links),
            "next_action": self.next_action,
            "blocking": self.blocking,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FailureExplainStageCard":
        return cls(
            stage_id=str(payload["stage_id"]),
            stage_label=str(payload["stage_label"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            why_it_happened=str(payload["why_it_happened"]),
            evidence_links=tuple(str(item) for item in payload["evidence_links"]),
            next_action=str(payload["next_action"]),
            blocking=bool(payload.get("blocking", False)),
        )


@dataclass(frozen=True)
class FailureExplainWalkthroughStep:
    step_id: str
    title: str
    summary: str
    evidence_links: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    expected_actual_diff_ids: tuple[str, ...]
    next_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "summary": self.summary,
            "evidence_links": list(self.evidence_links),
            "correlation_ids": list(self.correlation_ids),
            "expected_actual_diff_ids": list(self.expected_actual_diff_ids),
            "next_action": self.next_action,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FailureExplainWalkthroughStep":
        return cls(
            step_id=str(payload["step_id"]),
            title=str(payload["title"]),
            summary=str(payload["summary"]),
            evidence_links=tuple(str(item) for item in payload["evidence_links"]),
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            expected_actual_diff_ids=tuple(
                str(item) for item in payload["expected_actual_diff_ids"]
            ),
            next_action=str(payload["next_action"]),
        )


@dataclass(frozen=True)
class FailureExplainRequest:
    case_id: str
    explain_surface_id: str
    source_kind: FailureExplainSourceKind
    packet_report: PacketValidationReport | None = None
    parity_report: BarParityCertificationReport | None = None
    replay_report: ReplayCertificationReport | None = None
    recovery_report: RecoveryValidationReport | None = None
    runbook_references: tuple[str, ...] = ()
    retained_log_ids: tuple[str, ...] = ()
    correlation_ids: tuple[str, ...] = ()
    operator_notes: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "explain_surface_id": self.explain_surface_id,
            "source_kind": self.source_kind.value,
            "packet_report": (
                self.packet_report.to_dict() if self.packet_report is not None else None
            ),
            "parity_report": (
                self.parity_report.to_dict() if self.parity_report is not None else None
            ),
            "replay_report": (
                self.replay_report.to_dict() if self.replay_report is not None else None
            ),
            "recovery_report": (
                self.recovery_report.to_dict()
                if self.recovery_report is not None
                else None
            ),
            "runbook_references": list(self.runbook_references),
            "retained_log_ids": list(self.retained_log_ids),
            "correlation_ids": list(self.correlation_ids),
            "operator_notes": list(self.operator_notes),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FailureExplainRequest":
        packet_payload = payload.get("packet_report")
        parity_payload = payload.get("parity_report")
        replay_payload = payload.get("replay_report")
        recovery_payload = payload.get("recovery_report")
        return cls(
            case_id=str(payload["case_id"]),
            explain_surface_id=str(payload["explain_surface_id"]),
            source_kind=FailureExplainSourceKind(str(payload["source_kind"])),
            packet_report=(
                _packet_report_from_dict(dict(packet_payload))
                if packet_payload is not None
                else None
            ),
            parity_report=(
                BarParityCertificationReport.from_dict(dict(parity_payload))
                if parity_payload is not None
                else None
            ),
            replay_report=(
                _replay_report_from_dict(dict(replay_payload))
                if replay_payload is not None
                else None
            ),
            recovery_report=(
                _recovery_report_from_dict(dict(recovery_payload))
                if recovery_payload is not None
                else None
            ),
            runbook_references=tuple(
                str(item) for item in payload.get("runbook_references", ())
            ),
            retained_log_ids=tuple(
                str(item) for item in payload.get("retained_log_ids", ())
            ),
            correlation_ids=tuple(
                str(item) for item in payload.get("correlation_ids", ())
            ),
            operator_notes=tuple(str(item) for item in payload.get("operator_notes", ())),
            schema_version=int(
                payload.get(
                    "schema_version", SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FailureExplainRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="failure_explain_request")
        )


@dataclass(frozen=True)
class FailureExplainReport:
    schema_version: int
    case_id: str
    explain_surface_id: str
    source_kind: FailureExplainSourceKind
    outcome: FailureExplainOutcome
    reason_code: str
    blocking_reason_code: str | None
    stage_cards: tuple[FailureExplainStageCard, ...]
    walkthrough_steps: tuple[FailureExplainWalkthroughStep, ...]
    evidence_navigation: dict[str, Any]
    expected_vs_actual_diffs: list[dict[str, Any]]
    correlation_ids: tuple[str, ...]
    expected_actual_diff_ids: tuple[str, ...]
    retained_artifact_ids: tuple[str, ...]
    retained_log_ids: tuple[str, ...]
    operator_reason_bundle: dict[str, Any]
    operator_summary: str
    developer_summary: str
    remediation_classification: FailureExplainRemediationClass
    remediation: str
    next_actions: tuple[str, ...]
    generated_at_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "explain_surface_id": self.explain_surface_id,
            "source_kind": self.source_kind.value,
            "outcome": self.outcome.value,
            "reason_code": self.reason_code,
            "blocking_reason_code": self.blocking_reason_code,
            "stage_cards": [card.to_dict() for card in self.stage_cards],
            "walkthrough_steps": [step.to_dict() for step in self.walkthrough_steps],
            "evidence_navigation": _jsonable(self.evidence_navigation),
            "expected_vs_actual_diffs": _jsonable(self.expected_vs_actual_diffs),
            "correlation_ids": list(self.correlation_ids),
            "expected_actual_diff_ids": list(self.expected_actual_diff_ids),
            "retained_artifact_ids": list(self.retained_artifact_ids),
            "retained_log_ids": list(self.retained_log_ids),
            "operator_reason_bundle": _jsonable(self.operator_reason_bundle),
            "operator_summary": self.operator_summary,
            "developer_summary": self.developer_summary,
            "remediation_classification": self.remediation_classification.value,
            "remediation": self.remediation,
            "next_actions": list(self.next_actions),
            "generated_at_utc": self.generated_at_utc,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailureExplainReport":
        return cls(
            schema_version=int(payload["schema_version"]),
            case_id=str(payload["case_id"]),
            explain_surface_id=str(payload["explain_surface_id"]),
            source_kind=FailureExplainSourceKind(str(payload["source_kind"])),
            outcome=FailureExplainOutcome(str(payload["outcome"])),
            reason_code=str(payload["reason_code"]),
            blocking_reason_code=(
                str(payload["blocking_reason_code"])
                if payload.get("blocking_reason_code") is not None
                else None
            ),
            stage_cards=tuple(
                FailureExplainStageCard.from_dict(dict(item))
                for item in payload["stage_cards"]
            ),
            walkthrough_steps=tuple(
                FailureExplainWalkthroughStep.from_dict(dict(item))
                for item in payload["walkthrough_steps"]
            ),
            evidence_navigation=dict(payload["evidence_navigation"]),
            expected_vs_actual_diffs=[
                dict(item) for item in payload["expected_vs_actual_diffs"]
            ],
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            expected_actual_diff_ids=tuple(
                str(item) for item in payload["expected_actual_diff_ids"]
            ),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            retained_log_ids=tuple(str(item) for item in payload["retained_log_ids"]),
            operator_reason_bundle=dict(payload["operator_reason_bundle"]),
            operator_summary=str(payload["operator_summary"]),
            developer_summary=str(payload["developer_summary"]),
            remediation_classification=FailureExplainRemediationClass(
                str(payload["remediation_classification"])
            ),
            remediation=str(payload["remediation"]),
            next_actions=tuple(str(item) for item in payload["next_actions"]),
            generated_at_utc=str(payload["generated_at_utc"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FailureExplainReport":
        return cls.from_dict(
            _decode_json_object(payload, label="failure_explain_report")
        )


def _invalid_report(
    request: FailureExplainRequest,
    *,
    reason_code: str,
    explanation: str,
    remediation: str,
) -> FailureExplainReport:
    next_actions = (remediation,)
    evidence_links = _unique_strings(
        [*request.runbook_references, *request.retained_log_ids, *request.correlation_ids]
    )
    return FailureExplainReport(
        schema_version=SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION,
        case_id=request.case_id,
        explain_surface_id=request.explain_surface_id,
        source_kind=request.source_kind,
        outcome=FailureExplainOutcome.INVALID,
        reason_code=reason_code,
        blocking_reason_code=reason_code,
        stage_cards=_stage_cards(
            source_kind=request.source_kind,
            reason_code=reason_code,
            operator_summary=explanation,
            developer_summary=explanation,
            evidence_links=evidence_links,
            next_actions=next_actions,
        ),
        walkthrough_steps=_walkthrough_steps(
            operator_summary=explanation,
            developer_summary=explanation,
            evidence_links=evidence_links,
            correlation_ids=_unique_strings(list(request.correlation_ids)),
            expected_actual_diff_ids=(),
            next_actions=next_actions,
        ),
        evidence_navigation={
            "runbook_references": list(request.runbook_references),
            "retained_log_ids": list(request.retained_log_ids),
            "correlation_ids": list(request.correlation_ids),
            "operator_notes": list(request.operator_notes),
        },
        expected_vs_actual_diffs=[],
        correlation_ids=_unique_strings(list(request.correlation_ids)),
        expected_actual_diff_ids=(),
        retained_artifact_ids=(),
        retained_log_ids=_unique_strings(list(request.retained_log_ids)),
        operator_reason_bundle={
            "summary": explanation,
            "gate_summary": "The explain request was invalid.",
            "rule_trace": [f"reason_code={reason_code}", explanation],
            "remediation_hints": [remediation],
        },
        operator_summary=explanation,
        developer_summary=explanation,
        remediation_classification=FailureExplainRemediationClass.REPAIR_EXPLAIN_REQUEST,
        remediation=remediation,
        next_actions=next_actions,
    )


def _request_validation_errors(request: FailureExplainRequest) -> list[str]:
    errors: list[str] = []
    if request.schema_version != SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION:
        errors.append("unsupported schema version")
    report_count = sum(
        report is not None
        for report in (
            request.packet_report,
            request.parity_report,
            request.replay_report,
            request.recovery_report,
        )
    )
    if report_count != 1:
        errors.append("exactly one source report must be attached")
    if request.source_kind in {
        FailureExplainSourceKind.POLICY_FAILURE,
        FailureExplainSourceKind.READINESS_REJECTION,
    } and request.packet_report is None:
        errors.append("packet_report is required for policy or readiness explain surfaces")
    if (
        request.source_kind == FailureExplainSourceKind.PARITY_DRIFT
        and request.parity_report is None
    ):
        errors.append("parity_report is required for parity-drift explain surfaces")
    if (
        request.source_kind == FailureExplainSourceKind.REPLAY_DIVERGENCE
        and request.replay_report is None
    ):
        errors.append("replay_report is required for replay-divergence explain surfaces")
    if (
        request.source_kind == FailureExplainSourceKind.RECOVERY_BLOCK
        and request.recovery_report is None
    ):
        errors.append("recovery_report is required for recovery-block explain surfaces")
    if not request.explain_surface_id:
        errors.append("explain_surface_id is required")
    if not request.runbook_references:
        errors.append("at least one runbook reference is required")
    return errors


def _build_packet_report(
    request: FailureExplainRequest,
) -> FailureExplainReport:
    report = request.packet_report
    if report is None:  # pragma: no cover - guarded by request validation
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_REQUEST_INVALID",
            explanation="The packet-backed explain request did not include a packet report.",
            remediation="Attach a blocking packet report for policy or readiness explanation.",
        )
    if report.status == PacketStatus.PASS.value:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_SOURCE_MUST_BE_BLOCKING",
            explanation="The attached packet report passed, so there is no blocking failure to explain.",
            remediation="Attach a blocking packet report for policy or readiness explanation.",
        )

    correlation_ids = _packet_correlation_ids(report, request)
    if not correlation_ids:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_CORRELATION_ID_REQUIRED",
            explanation="Blocking packet failures need at least one correlation identifier.",
            remediation="Attach a correlation_id directly or through the source packet context.",
        )

    retained_artifact_ids = _unique_strings(
        list(_reference_strings_from_mapping(report.context))
    )
    expected_vs_actual_diffs = _packet_diffs(report)
    expected_actual_diff_ids = tuple(
        _diff_identifier(diff, "packet", index)
        for index, diff in enumerate(expected_vs_actual_diffs)
    )
    source_label = (
        "Readiness rejection"
        if request.source_kind == FailureExplainSourceKind.READINESS_REJECTION
        else "Policy gate failure"
    )
    operator_summary = report.explanation
    developer_summary = (
        f"{source_label} `{report.packet_kind}` emitted `{report.reason_code}` with "
        f"status `{report.status}` and blocking fields {list(report.missing_fields)}."
    )
    next_actions = _unique_strings(
        [
            report.remediation,
            f"Review {request.runbook_references[0]}.",
        ]
    )
    evidence_links = _unique_strings(
        [
            *retained_artifact_ids,
            *request.retained_log_ids,
            *correlation_ids,
            *request.runbook_references,
        ]
    )
    rule_trace = _build_rule_trace(
        source_kind=request.source_kind.value,
        reason_code=report.reason_code,
        explanation=report.explanation,
        context=report.context,
        details=[f"packet_kind={report.packet_kind}", f"missing_fields={list(report.missing_fields)}"],
    )
    remediation_classification = (
        FailureExplainRemediationClass.CLEAR_RUNTIME_BLOCKERS
        if request.source_kind == FailureExplainSourceKind.READINESS_REJECTION
        else FailureExplainRemediationClass.REPAIR_POLICY_BINDINGS
    )
    operator_reason_bundle = {
        "summary": operator_summary,
        "gate_summary": developer_summary,
        "rule_trace": rule_trace,
        "remediation_hints": list(next_actions),
    }
    return FailureExplainReport(
        schema_version=SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION,
        case_id=request.case_id,
        explain_surface_id=request.explain_surface_id,
        source_kind=request.source_kind,
        outcome=FailureExplainOutcome.BLOCKED,
        reason_code=report.reason_code,
        blocking_reason_code=report.reason_code,
        stage_cards=_stage_cards(
            source_kind=request.source_kind,
            reason_code=report.reason_code,
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            next_actions=next_actions,
        ),
        walkthrough_steps=_walkthrough_steps(
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_actions=next_actions,
        ),
        evidence_navigation={
            "packet_kind": report.packet_kind,
            "packet_id": report.packet_id,
            "context": _jsonable(report.context),
            "runbook_references": list(request.runbook_references),
            "operator_notes": list(request.operator_notes),
        },
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        correlation_ids=correlation_ids,
        expected_actual_diff_ids=expected_actual_diff_ids,
        retained_artifact_ids=retained_artifact_ids,
        retained_log_ids=_unique_strings(list(request.retained_log_ids)),
        operator_reason_bundle=operator_reason_bundle,
        operator_summary=operator_summary,
        developer_summary=developer_summary,
        remediation_classification=remediation_classification,
        remediation=report.remediation,
        next_actions=next_actions,
    )


def _build_parity_report(
    request: FailureExplainRequest,
) -> FailureExplainReport:
    report = request.parity_report
    if report is None:  # pragma: no cover - guarded by request validation
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_REQUEST_INVALID",
            explanation="The parity explain request did not include a parity report.",
            remediation="Attach a failed parity certification report before rendering a parity explain surface.",
        )
    if (
        report.parity_passed
        or report.status == BarParityStatus.PASS.value
        or not report.drifted_dimensions
    ):
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_SOURCE_MUST_BE_BLOCKING",
            explanation="The attached parity report did not retain a blocking parity drift.",
            remediation="Attach a failed parity certification report before rendering a parity explain surface.",
        )

    correlation_ids = _unique_strings(list(request.correlation_ids))
    if not correlation_ids:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_CORRELATION_ID_REQUIRED",
            explanation="Parity-drift explain surfaces need an explicit correlation identifier because the parity contract itself does not carry one.",
            remediation="Provide a correlation_ids value when building the parity explain request.",
        )
    retained_artifact_ids = _unique_strings(
        [
            report.artifact_id,
            *report.mismatch_histogram_artifact_ids,
            *report.sampled_drilldown_artifact_ids,
        ]
    )
    expected_vs_actual_diffs = _parity_diffs(report)
    expected_actual_diff_ids = tuple(
        _diff_identifier(diff, "parity", index)
        for index, diff in enumerate(expected_vs_actual_diffs)
    )
    operator_summary = report.explanation
    developer_summary = (
        f"Bar parity drifted on dimensions {list(report.drifted_dimensions)} under "
        f"`{report.reason_code}`. Review the mismatch histogram and drilldown artifacts "
        "before trusting research/live bar equivalence again."
    )
    next_actions = _unique_strings(
        [report.remediation, f"Review {request.runbook_references[0]}."]
    )
    evidence_links = _unique_strings(
        [
            *retained_artifact_ids,
            *request.retained_log_ids,
            *correlation_ids,
            *request.runbook_references,
        ]
    )
    operator_reason_bundle = {
        "summary": operator_summary,
        "gate_summary": developer_summary,
        "rule_trace": _build_rule_trace(
            source_kind=request.source_kind.value,
            reason_code=report.reason_code,
            explanation=report.explanation,
            context={"drifted_dimensions": list(report.drifted_dimensions)},
            details=[f"artifact_id={report.artifact_id}"],
        ),
        "remediation_hints": list(next_actions),
    }
    return FailureExplainReport(
        schema_version=SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION,
        case_id=request.case_id,
        explain_surface_id=request.explain_surface_id,
        source_kind=request.source_kind,
        outcome=FailureExplainOutcome.BLOCKED,
        reason_code=report.reason_code,
        blocking_reason_code=report.reason_code,
        stage_cards=_stage_cards(
            source_kind=request.source_kind,
            reason_code=report.reason_code,
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            next_actions=next_actions,
        ),
        walkthrough_steps=_walkthrough_steps(
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_actions=next_actions,
        ),
        evidence_navigation={
            "artifact_id": report.artifact_id,
            "drifted_dimensions": list(report.drifted_dimensions),
            "mismatch_histogram_artifact_ids": list(report.mismatch_histogram_artifact_ids),
            "sampled_drilldown_artifact_ids": list(
                report.sampled_drilldown_artifact_ids
            ),
            "runbook_references": list(request.runbook_references),
            "operator_notes": list(request.operator_notes),
        },
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        correlation_ids=correlation_ids,
        expected_actual_diff_ids=expected_actual_diff_ids,
        retained_artifact_ids=retained_artifact_ids,
        retained_log_ids=_unique_strings(list(request.retained_log_ids)),
        operator_reason_bundle=operator_reason_bundle,
        operator_summary=operator_summary,
        developer_summary=developer_summary,
        remediation_classification=FailureExplainRemediationClass.REPAIR_PARITY_SEMANTICS,
        remediation=report.remediation,
        next_actions=next_actions,
    )


def _build_replay_report(
    request: FailureExplainRequest,
) -> FailureExplainReport:
    report = request.replay_report
    if report is None:  # pragma: no cover - guarded by request validation
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_REQUEST_INVALID",
            explanation="The replay explain request did not include a replay certification report.",
            remediation="Attach a failed replay certification report before rendering a replay explain surface.",
        )
    if report.status == PacketStatus.PASS.value:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_SOURCE_MUST_BE_BLOCKING",
            explanation="The attached replay certification report passed, so there is no divergence to explain.",
            remediation="Attach a failed replay certification report before rendering a replay explain surface.",
        )

    structured_log_ids = [
        str(item.get("event_id"))
        for item in report.structured_logs
        if item.get("event_id") is not None
    ]
    retained_artifact_ids = list(
        _reference_strings_from_mapping(report.artifact_manifest)
    )
    retained_artifact_ids.extend([report.bundle_id, report.replay_context_id])
    correlation_ids = _replay_correlation_ids(report, request)
    expected_actual_diff_ids = _replay_diff_ids(report)
    first_divergence = report.first_divergence or {}
    operator_summary = report.explanation
    developer_summary = (
        f"Replay certification blocked under `{report.reason_code}`; "
        f"readiness reason `{report.replay_readiness_reason_code}`; first divergence "
        f"{first_divergence or 'not recorded'}."
    )
    next_actions = _unique_strings(
        [report.remediation, f"Review {request.runbook_references[0]}."]
    )
    evidence_links = _unique_strings(
        [
            *retained_artifact_ids,
            *structured_log_ids,
            *request.retained_log_ids,
            *correlation_ids,
            *request.runbook_references,
        ]
    )
    operator_reason_bundle = (
        dict(report.operator_reason_bundle)
        if isinstance(report.operator_reason_bundle, dict)
        else {
            "summary": operator_summary,
            "gate_summary": developer_summary,
            "rule_trace": [],
            "remediation_hints": list(next_actions),
        }
    )
    operator_reason_bundle.setdefault("summary", operator_summary)
    operator_reason_bundle.setdefault("gate_summary", developer_summary)
    operator_reason_bundle.setdefault("rule_trace", [])
    operator_reason_bundle.setdefault("remediation_hints", list(next_actions))
    return FailureExplainReport(
        schema_version=SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION,
        case_id=request.case_id,
        explain_surface_id=request.explain_surface_id,
        source_kind=request.source_kind,
        outcome=FailureExplainOutcome.BLOCKED,
        reason_code=report.reason_code,
        blocking_reason_code=report.reason_code,
        stage_cards=_stage_cards(
            source_kind=request.source_kind,
            reason_code=report.reason_code,
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            next_actions=next_actions,
        ),
        walkthrough_steps=_walkthrough_steps(
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_actions=next_actions,
        ),
        evidence_navigation={
            "bundle_id": report.bundle_id,
            "replay_context_id": report.replay_context_id,
            "first_divergence": _jsonable(report.first_divergence),
            "artifact_manifest": _jsonable(report.artifact_manifest),
            "runbook_references": list(request.runbook_references),
            "operator_notes": list(request.operator_notes),
        },
        expected_vs_actual_diffs=[dict(item) for item in report.expected_vs_actual_diffs],
        correlation_ids=correlation_ids,
        expected_actual_diff_ids=expected_actual_diff_ids,
        retained_artifact_ids=_unique_strings(retained_artifact_ids),
        retained_log_ids=_unique_strings([*structured_log_ids, *request.retained_log_ids]),
        operator_reason_bundle=operator_reason_bundle,
        operator_summary=operator_summary,
        developer_summary=developer_summary,
        remediation_classification=FailureExplainRemediationClass.RECERTIFY_REPLAY,
        remediation=report.remediation,
        next_actions=next_actions,
    )


def _build_recovery_report(
    request: FailureExplainRequest,
) -> FailureExplainReport:
    report = request.recovery_report
    if report is None:  # pragma: no cover - guarded by request validation
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_REQUEST_INVALID",
            explanation="The recovery explain request did not include a recovery validation report.",
            remediation="Attach a blocking recovery validation report before rendering a recovery explain surface.",
        )
    if report.status == PacketStatus.PASS.value:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_SOURCE_MUST_BE_BLOCKING",
            explanation="The attached recovery report passed, so there is no major recovery block to explain.",
            remediation="Attach a blocking recovery validation report before rendering a recovery explain surface.",
        )

    correlation_ids = _recovery_correlation_ids(report, request)
    if not correlation_ids:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_CORRELATION_ID_REQUIRED",
            explanation="Recovery explain surfaces require a correlation identifier from the recovery context or request.",
            remediation="Attach a correlation_id directly or through the recovery validation report context.",
        )
    retained_artifact_ids = _unique_strings(
        list(_reference_strings_from_mapping(report.context))
    )
    expected_vs_actual_diffs = _recovery_diffs(report)
    expected_actual_diff_ids = tuple(
        _diff_identifier(diff, "recovery", index)
        for index, diff in enumerate(expected_vs_actual_diffs)
    )
    operator_summary = report.explanation
    developer_summary = (
        f"Recovery artifact `{report.artifact_kind}` blocked under `{report.reason_code}` "
        f"with missing fields {list(report.missing_fields)}."
    )
    next_actions = _unique_strings(
        [report.remediation, f"Review {request.runbook_references[0]}."]
    )
    evidence_links = _unique_strings(
        [
            *retained_artifact_ids,
            *request.retained_log_ids,
            *correlation_ids,
            *request.runbook_references,
        ]
    )
    operator_reason_bundle = {
        "summary": operator_summary,
        "gate_summary": developer_summary,
        "rule_trace": _build_rule_trace(
            source_kind=request.source_kind.value,
            reason_code=report.reason_code,
            explanation=report.explanation,
            context=report.context,
            details=[
                f"artifact_kind={report.artifact_kind}",
                f"missing_fields={list(report.missing_fields)}",
            ],
        ),
        "remediation_hints": list(next_actions),
    }
    return FailureExplainReport(
        schema_version=SUPPORTED_FAILURE_EXPLAIN_SCHEMA_VERSION,
        case_id=request.case_id,
        explain_surface_id=request.explain_surface_id,
        source_kind=request.source_kind,
        outcome=FailureExplainOutcome.BLOCKED,
        reason_code=report.reason_code,
        blocking_reason_code=report.reason_code,
        stage_cards=_stage_cards(
            source_kind=request.source_kind,
            reason_code=report.reason_code,
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            next_actions=next_actions,
        ),
        walkthrough_steps=_walkthrough_steps(
            operator_summary=operator_summary,
            developer_summary=developer_summary,
            evidence_links=evidence_links,
            correlation_ids=correlation_ids,
            expected_actual_diff_ids=expected_actual_diff_ids,
            next_actions=next_actions,
        ),
        evidence_navigation={
            "artifact_kind": report.artifact_kind,
            "artifact_id": report.artifact_id,
            "context": _jsonable(report.context),
            "runbook_references": list(request.runbook_references),
            "operator_notes": list(request.operator_notes),
        },
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        correlation_ids=correlation_ids,
        expected_actual_diff_ids=expected_actual_diff_ids,
        retained_artifact_ids=retained_artifact_ids,
        retained_log_ids=_unique_strings(list(request.retained_log_ids)),
        operator_reason_bundle=operator_reason_bundle,
        operator_summary=operator_summary,
        developer_summary=developer_summary,
        remediation_classification=FailureExplainRemediationClass.HALT_AND_REVIEW,
        remediation=report.remediation,
        next_actions=next_actions,
    )


def evaluate_failure_explain_surface(
    request: FailureExplainRequest,
) -> FailureExplainReport:
    errors = _request_validation_errors(request)
    if errors:
        return _invalid_report(
            request,
            reason_code="FAILURE_EXPLAIN_REQUEST_INVALID",
            explanation="The failure explain request was invalid.",
            remediation="; ".join(errors),
        )
    if request.source_kind in {
        FailureExplainSourceKind.POLICY_FAILURE,
        FailureExplainSourceKind.READINESS_REJECTION,
    }:
        return _build_packet_report(request)
    if request.source_kind == FailureExplainSourceKind.PARITY_DRIFT:
        return _build_parity_report(request)
    if request.source_kind == FailureExplainSourceKind.REPLAY_DIVERGENCE:
        return _build_replay_report(request)
    return _build_recovery_report(request)


def validate_failure_explain_contract() -> list[str]:
    errors: list[str] = []
    if len(set(FAILURE_EXPLAIN_STAGE_IDS)) != len(FAILURE_EXPLAIN_STAGE_IDS):
        errors.append("failure explain stage ids must be unique")
    if len(set(FAILURE_EXPLAIN_WALKTHROUGH_STEP_IDS)) != len(
        FAILURE_EXPLAIN_WALKTHROUGH_STEP_IDS
    ):
        errors.append("failure explain walkthrough step ids must be unique")
    return errors


VALIDATION_ERRORS = validate_failure_explain_contract()
