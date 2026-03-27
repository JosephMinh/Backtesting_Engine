"""Deterministic contract for the final definition-of-done gate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "policy"
    / "definition_of_done_cases.json"
)
STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []
REQUIRED_PHASE_GATES: tuple[str, ...] = (
    "phase_0",
    "phase_1",
    "phase_2",
    "phase_2_5",
    "phase_3",
    "phase_4",
    "phase_5",
    "phase_6",
    "phase_7",
    "phase_8",
    "phase_9",
)
REQUIRED_EVIDENCE_CLASSES: tuple[str, ...] = (
    "local_check_artifact_ids",
    "golden_path_artifact_ids",
    "failure_path_artifact_ids",
    "structured_log_ids",
    "artifact_bundle_ids",
)
ALLOWED_FINAL_OUTCOMES: tuple[str, ...] = (
    "rejected",
    "live_canary_approved",
)
REQUIRED_DONE_ITEM_IDS: tuple[str, ...] = (
    "certified_release_publication",
    "point_in_time_enforcement",
    "research_funnel_auditability",
    "execution_lane_viability_decision",
    "family_protocol_without_adhoc_evidence",
    "frozen_candidate_immutability_and_binding",
    "portability_and_tradability_certified",
    "native_1oz_validation_requirement",
    "research_live_parity_certified",
    "paper_and_shadow_live_end_to_end",
    "green_session_readiness_and_conformance",
    "intraday_controls_and_emergency_workflows",
    "end_of_day_statement_next_session_gate",
    "order_idempotency_and_safe_ambiguity",
    "backup_restore_and_migration_success",
    "operational_controls_observable",
    "candidate_rejected_or_live_canary",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to a JSON object")
    return decoded


def _unique_strings(items: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        candidate = str(item).strip()
        if candidate and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return tuple(ordered)


def _fixture() -> dict[str, Any]:
    try:
        return _decode_json_object(
            FIXTURE_PATH.read_text(encoding="utf-8"),
            label="definition_of_done fixture",
        )
    except OSError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"unable to load definition_of_done fixture: {exc}") from exc


@dataclass(frozen=True)
class DefinitionOfDoneEvidence:
    item_id: str
    summary: str
    local_check_artifact_ids: tuple[str, ...]
    golden_path_artifact_ids: tuple[str, ...]
    failure_path_artifact_ids: tuple[str, ...]
    structured_log_ids: tuple[str, ...]
    artifact_bundle_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DefinitionOfDoneEvidence":
        return cls(
            item_id=str(payload["item_id"]),
            summary=str(payload["summary"]),
            local_check_artifact_ids=_unique_strings(
                [str(item) for item in payload["local_check_artifact_ids"]]
            ),
            golden_path_artifact_ids=_unique_strings(
                [str(item) for item in payload["golden_path_artifact_ids"]]
            ),
            failure_path_artifact_ids=_unique_strings(
                [str(item) for item in payload["failure_path_artifact_ids"]]
            ),
            structured_log_ids=_unique_strings(
                [str(item) for item in payload["structured_log_ids"]]
            ),
            artifact_bundle_ids=_unique_strings(
                [str(item) for item in payload["artifact_bundle_ids"]]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DefinitionOfDoneRequest:
    case_id: str
    satisfied_phase_gates: tuple[str, ...]
    downstream_of_phase_and_resilience_graph: bool
    final_candidate_outcome: str
    checklist_evidence: tuple[DefinitionOfDoneEvidence, ...]
    review_artifact_id: str
    operator_notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DefinitionOfDoneRequest":
        return cls(
            case_id=str(payload["case_id"]),
            satisfied_phase_gates=_unique_strings(
                [str(item) for item in payload["satisfied_phase_gates"]]
            ),
            downstream_of_phase_and_resilience_graph=bool(
                payload["downstream_of_phase_and_resilience_graph"]
            ),
            final_candidate_outcome=str(payload["final_candidate_outcome"]),
            checklist_evidence=tuple(
                DefinitionOfDoneEvidence.from_dict(item)
                for item in payload["checklist_evidence"]
            ),
            review_artifact_id=str(payload["review_artifact_id"]),
            operator_notes=_unique_strings(
                [str(item) for item in payload.get("operator_notes", [])]
            ),
        )


@dataclass(frozen=True)
class DefinitionOfDoneReport:
    case_id: str
    status: str
    reason_code: str
    final_candidate_outcome: str
    satisfied_item_ids: tuple[str, ...]
    missing_item_ids: tuple[str, ...]
    missing_phase_gates: tuple[str, ...]
    evidence_class_gaps: dict[str, tuple[str, ...]]
    invalid_final_outcome: bool
    artifact_manifest: dict[str, Any]
    structured_logs: tuple[dict[str, Any], ...]
    operator_reason_bundle: dict[str, Any]
    expected_vs_actual_diffs: tuple[dict[str, Any], ...]
    explanation: str
    remediation: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_class_gaps"] = {
            key: list(value) for key, value in self.evidence_class_gaps.items()
        }
        payload["structured_logs"] = [dict(item) for item in self.structured_logs]
        payload["expected_vs_actual_diffs"] = [
            dict(item) for item in self.expected_vs_actual_diffs
        ]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DefinitionOfDoneReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            final_candidate_outcome=str(payload["final_candidate_outcome"]),
            satisfied_item_ids=tuple(str(item) for item in payload["satisfied_item_ids"]),
            missing_item_ids=tuple(str(item) for item in payload["missing_item_ids"]),
            missing_phase_gates=tuple(str(item) for item in payload["missing_phase_gates"]),
            evidence_class_gaps={
                str(key): tuple(str(item) for item in value)
                for key, value in payload["evidence_class_gaps"].items()
            },
            invalid_final_outcome=bool(payload["invalid_final_outcome"]),
            artifact_manifest=dict(payload["artifact_manifest"]),
            structured_logs=tuple(dict(item) for item in payload["structured_logs"]),
            operator_reason_bundle=dict(payload["operator_reason_bundle"]),
            expected_vs_actual_diffs=tuple(
                dict(item) for item in payload["expected_vs_actual_diffs"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload["timestamp"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DefinitionOfDoneReport":
        return cls.from_dict(_decode_json_object(payload, label="definition_of_done report"))


def _artifact_manifest(request: DefinitionOfDoneRequest) -> dict[str, Any]:
    artifacts = [
        {
            "artifact_id": request.review_artifact_id,
            "artifact_role": "definition_of_done_review",
        }
    ]
    for evidence in request.checklist_evidence:
        for artifact_id in (
            evidence.local_check_artifact_ids
            + evidence.golden_path_artifact_ids
            + evidence.failure_path_artifact_ids
            + evidence.structured_log_ids
            + evidence.artifact_bundle_ids
        ):
            artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_role": "definition_of_done_evidence",
                    "item_id": evidence.item_id,
                }
            )
    return {
        "manifest_id": f"{request.case_id}:definition_of_done_manifest",
        "generated_at_utc": _utc_now(),
        "retention_class": "final_gate",
        "contains_secrets": False,
        "redaction_policy": "none",
        "artifacts": artifacts,
    }


def _structured_logs(
    request: DefinitionOfDoneRequest,
    *,
    status: str,
    reason_code: str,
    missing_item_ids: tuple[str, ...],
    missing_phase_gates: tuple[str, ...],
    evidence_class_gaps: dict[str, tuple[str, ...]],
    invalid_final_outcome: bool,
) -> tuple[dict[str, Any], ...]:
    return (
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "definition_of_done_evaluated",
            "plane": "governance",
            "event_id": f"{request.case_id}:definition_of_done",
            "recorded_at_utc": _utc_now(),
            "correlation_id": f"{request.case_id}:{reason_code.lower()}",
            "status": status,
            "reason_code": reason_code,
            "missing_item_ids": list(missing_item_ids),
            "missing_phase_gates": list(missing_phase_gates),
            "evidence_class_gaps": {
                key: list(value) for key, value in evidence_class_gaps.items()
            },
            "invalid_final_outcome": invalid_final_outcome,
            "final_candidate_outcome": request.final_candidate_outcome,
        },
    )


def _diffs(
    *,
    missing_item_ids: tuple[str, ...],
    missing_phase_gates: tuple[str, ...],
    evidence_class_gaps: dict[str, tuple[str, ...]],
    invalid_final_outcome: bool,
    actual_final_outcome: str,
) -> tuple[dict[str, Any], ...]:
    diffs: list[dict[str, Any]] = []
    for item_id in missing_item_ids:
        diffs.append(
            {
                "field_name": "checklist_item",
                "expected": "present",
                "actual": "missing",
                "item_id": item_id,
            }
        )
    for gate in missing_phase_gates:
        diffs.append(
            {
                "field_name": "phase_gate",
                "expected": "satisfied",
                "actual": "missing",
                "phase_gate": gate,
            }
        )
    for item_id, missing_classes in evidence_class_gaps.items():
        diffs.append(
            {
                "field_name": "evidence_class",
                "expected": list(REQUIRED_EVIDENCE_CLASSES),
                "actual": list(missing_classes),
                "item_id": item_id,
            }
        )
    if invalid_final_outcome:
        diffs.append(
            {
                "field_name": "final_candidate_outcome",
                "expected": list(ALLOWED_FINAL_OUTCOMES),
                "actual": actual_final_outcome,
            }
        )
    return tuple(diffs)


def evaluate_definition_of_done(request: DefinitionOfDoneRequest) -> DefinitionOfDoneReport:
    evidence_by_item = {item.item_id: item for item in request.checklist_evidence}
    satisfied_item_ids = tuple(
        item_id for item_id in REQUIRED_DONE_ITEM_IDS if item_id in evidence_by_item
    )
    missing_item_ids = tuple(
        item_id for item_id in REQUIRED_DONE_ITEM_IDS if item_id not in evidence_by_item
    )
    missing_phase_gates = tuple(
        gate for gate in REQUIRED_PHASE_GATES if gate not in request.satisfied_phase_gates
    )
    evidence_class_gaps: dict[str, tuple[str, ...]] = {}
    for item_id, evidence in evidence_by_item.items():
        missing_classes: list[str] = []
        if not evidence.local_check_artifact_ids:
            missing_classes.append("local_check_artifact_ids")
        if not evidence.golden_path_artifact_ids:
            missing_classes.append("golden_path_artifact_ids")
        if not evidence.failure_path_artifact_ids:
            missing_classes.append("failure_path_artifact_ids")
        if not evidence.structured_log_ids:
            missing_classes.append("structured_log_ids")
        if not evidence.artifact_bundle_ids:
            missing_classes.append("artifact_bundle_ids")
        if missing_classes:
            evidence_class_gaps[item_id] = tuple(missing_classes)

    invalid_final_outcome = request.final_candidate_outcome not in ALLOWED_FINAL_OUTCOMES
    if (
        missing_item_ids
        or missing_phase_gates
        or evidence_class_gaps
        or invalid_final_outcome
        or not request.downstream_of_phase_and_resilience_graph
    ):
        status = "violation"
        reason_code = "DEFINITION_OF_DONE_NOT_SATISFIED"
        explanation = (
            "The final done gate is still blocked because checklist coverage, phase-gate "
            "evidence, verification evidence, or the terminal candidate outcome is incomplete."
        )
        remediation = (
            "Keep the program open until every Section 13 item has retained local, golden-path, "
            "failure-path, structured-log, and artifact-bundle evidence, every phase gate "
            "through phase_9 is satisfied, and the terminal outcome is either a defensible "
            "rejection or a controlled LIVE_CANARY approval."
        )
    else:
        status = "pass"
        reason_code = "DEFINITION_OF_DONE_SATISFIED"
        explanation = (
            "All Section 13 done conditions are backed by retained evidence and the final "
            "outcome remains within the plan's honest termination or LIVE_CANARY options."
        )
        remediation = (
            "Retain the definition-of-done review bundle as the final closure artifact for "
            "the first protocol cycle."
        )

    artifact_manifest = _artifact_manifest(request)
    structured_logs = _structured_logs(
        request,
        status=status,
        reason_code=reason_code,
        missing_item_ids=missing_item_ids,
        missing_phase_gates=missing_phase_gates,
        evidence_class_gaps=evidence_class_gaps,
        invalid_final_outcome=invalid_final_outcome,
    )
    operator_reason_bundle = {
        "summary": explanation,
        "required_done_item_ids": list(REQUIRED_DONE_ITEM_IDS),
        "satisfied_item_ids": list(satisfied_item_ids),
        "missing_item_ids": list(missing_item_ids),
        "required_phase_gates": list(REQUIRED_PHASE_GATES),
        "missing_phase_gates": list(missing_phase_gates),
        "evidence_class_gaps": {
            key: list(value) for key, value in evidence_class_gaps.items()
        },
        "downstream_of_phase_and_resilience_graph": request.downstream_of_phase_and_resilience_graph,
        "final_candidate_outcome": request.final_candidate_outcome,
    }

    return DefinitionOfDoneReport(
        case_id=request.case_id,
        status=status,
        reason_code=reason_code,
        final_candidate_outcome=request.final_candidate_outcome,
        satisfied_item_ids=satisfied_item_ids,
        missing_item_ids=missing_item_ids,
        missing_phase_gates=missing_phase_gates,
        evidence_class_gaps=evidence_class_gaps,
        invalid_final_outcome=invalid_final_outcome,
        artifact_manifest=artifact_manifest,
        structured_logs=structured_logs,
        operator_reason_bundle=operator_reason_bundle,
        expected_vs_actual_diffs=_diffs(
            missing_item_ids=missing_item_ids,
            missing_phase_gates=missing_phase_gates,
            evidence_class_gaps=evidence_class_gaps,
            invalid_final_outcome=invalid_final_outcome,
            actual_final_outcome=request.final_candidate_outcome,
        ),
        explanation=explanation,
        remediation=remediation,
        timestamp=_utc_now(),
    )


def evaluate_definition_of_done_case(case_id: str) -> DefinitionOfDoneReport:
    fixture = _fixture()
    try:
        case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    except StopIteration as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown definition_of_done case_id: {case_id}") from exc

    payload = dict(fixture["defaults"])
    payload.update(dict(case.get("payload_overrides", {})))
    payload["case_id"] = case_id

    evidence = [dict(item) for item in payload["checklist_evidence"]]
    if "evidence_mutations" in case:
        mutations = dict(case["evidence_mutations"])
        for item in evidence:
            mutation = mutations.get(str(item["item_id"]))
            if mutation:
                item.update(dict(mutation))
    payload["checklist_evidence"] = evidence
    request = DefinitionOfDoneRequest.from_dict(payload)
    return evaluate_definition_of_done(request)
