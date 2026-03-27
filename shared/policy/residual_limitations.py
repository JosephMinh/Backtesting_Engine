"""Residual-limitations register for the first live stack.

This module encodes the explicit limitations that remain acceptable for the
initial live posture only because the first objective is honest validation and
safe operation, not maximum sophistication or maximum throughput.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum, unique
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_RESIDUAL_LIMITATIONS_SCHEMA_VERSION = 1
STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "policy"
    / "residual_limitations_cases.json"
)


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must decode from valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _unique_strings(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_initial_objective(value: str) -> bool:
    normalized = " ".join(value.lower().replace("-", " ").replace("_", " ").split())
    return "honest validation" in normalized and "safe operation" in normalized


@lru_cache(maxsize=1)
def _fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        decoded = json.load(fixture_file)
    if not isinstance(decoded, dict):  # pragma: no cover - defensive
        raise ValueError("residual limitations fixture must decode to an object")
    return decoded


@unique
class ResidualLimitationId(str, Enum):
    IBKR_MARKET_DATA_DEPENDENCY = "ibkr_market_data_dependency"
    ONE_OZ_LIQUIDITY_HETEROGENEITY = "one_oz_liquidity_heterogeneity"
    BAR_BASED_MICROSTRUCTURE_GAP = "bar_based_microstructure_gap"
    LIVE_CAPITAL_POSTURE_LIMIT = "live_capital_posture_limit"
    OVERNIGHT_OPERATIONAL_RISK = "overnight_operational_risk"
    SINGLE_HOST_INFRASTRUCTURE_CONCENTRATION = (
        "single_host_infrastructure_concentration"
    )


@unique
class DecisionSurface(str, Enum):
    PROMOTION_REVIEW = "promotion_review"
    CONTINUATION_REVIEW = "continuation_review"
    EXPANSION_REVIEW = "expansion_review"


REQUIRED_LIMITATION_IDS: tuple[str, ...] = tuple(item.value for item in ResidualLimitationId)
REQUIRED_DECISION_SURFACES: tuple[str, ...] = tuple(
    item.value for item in DecisionSurface
)


@dataclass(frozen=True)
class ResidualLimitationEntry:
    limitation_id: str
    title: str
    summary: str
    accepted_only_for_initial_objective: bool
    objective_rationale: str
    decision_surface_ids: tuple[str, ...]
    expansion_guardrail: str
    evidence_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResidualLimitationEntry":
        return cls(
            limitation_id=str(payload["limitation_id"]),
            title=str(payload["title"]),
            summary=str(payload["summary"]),
            accepted_only_for_initial_objective=bool(
                payload["accepted_only_for_initial_objective"]
            ),
            objective_rationale=str(payload["objective_rationale"]),
            decision_surface_ids=_unique_strings(
                [str(item) for item in payload["decision_surface_ids"]]
            ),
            expansion_guardrail=str(payload["expansion_guardrail"]),
            evidence_ids=_unique_strings([str(item) for item in payload.get("evidence_ids", [])]),
            notes=_unique_strings([str(item) for item in payload.get("notes", [])]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResidualLimitationsRegisterRequest:
    case_id: str
    register_id: str
    stack_id: str
    initial_objective: str
    limitations: tuple[ResidualLimitationEntry, ...]
    register_artifact_id: str
    recorded_at_utc: str
    operator_notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResidualLimitationsRegisterRequest":
        return cls(
            case_id=str(payload["case_id"]),
            register_id=str(payload["register_id"]),
            stack_id=str(payload["stack_id"]),
            initial_objective=str(payload["initial_objective"]),
            limitations=tuple(
                ResidualLimitationEntry.from_dict(item)
                for item in payload["limitations"]
            ),
            register_artifact_id=str(payload["register_artifact_id"]),
            recorded_at_utc=str(payload["recorded_at_utc"]),
            operator_notes=_unique_strings(
                [str(item) for item in payload.get("operator_notes", [])]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["limitations"] = [entry.to_dict() for entry in self.limitations]
        return payload


@dataclass(frozen=True)
class ResidualLimitationsRegisterReport:
    case_id: str
    status: str
    reason_code: str
    register_id: str
    stack_id: str
    initial_objective: str
    covered_limitation_ids: tuple[str, ...]
    missing_limitation_ids: tuple[str, ...]
    decision_surface_gaps: dict[str, tuple[str, ...]]
    nonobjective_limitation_ids: tuple[str, ...]
    missing_guardrail_ids: tuple[str, ...]
    register_digest: str
    artifact_manifest: dict[str, Any]
    structured_logs: tuple[dict[str, Any], ...]
    operator_reason_bundle: dict[str, Any]
    expected_vs_actual_diffs: tuple[dict[str, Any], ...]
    explanation: str
    remediation: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["structured_logs"] = [dict(item) for item in self.structured_logs]
        payload["expected_vs_actual_diffs"] = [
            dict(item) for item in self.expected_vs_actual_diffs
        ]
        payload["decision_surface_gaps"] = {
            key: list(value) for key, value in self.decision_surface_gaps.items()
        }
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResidualLimitationsRegisterReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            register_id=str(payload["register_id"]),
            stack_id=str(payload["stack_id"]),
            initial_objective=str(payload["initial_objective"]),
            covered_limitation_ids=tuple(
                str(item) for item in payload["covered_limitation_ids"]
            ),
            missing_limitation_ids=tuple(
                str(item) for item in payload["missing_limitation_ids"]
            ),
            decision_surface_gaps={
                str(key): tuple(str(item) for item in value)
                for key, value in payload["decision_surface_gaps"].items()
            },
            nonobjective_limitation_ids=tuple(
                str(item) for item in payload["nonobjective_limitation_ids"]
            ),
            missing_guardrail_ids=tuple(
                str(item) for item in payload["missing_guardrail_ids"]
            ),
            register_digest=str(payload["register_digest"]),
            artifact_manifest=dict(payload["artifact_manifest"]),
            structured_logs=tuple(
                dict(item) for item in payload["structured_logs"]
            ),
            operator_reason_bundle=dict(payload["operator_reason_bundle"]),
            expected_vs_actual_diffs=tuple(
                dict(item) for item in payload["expected_vs_actual_diffs"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload["timestamp"]),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ResidualLimitationsRegisterReport":
        return cls.from_dict(_decode_json_object(payload, label="residual limitations report"))


def _artifact_manifest(request: ResidualLimitationsRegisterRequest) -> dict[str, Any]:
    limitation_artifacts = []
    for entry in request.limitations:
        for evidence_id in entry.evidence_ids:
            limitation_artifacts.append(
                {
                    "artifact_id": evidence_id,
                    "artifact_role": "supporting_evidence",
                    "limitation_id": entry.limitation_id,
                }
            )
    return {
        "manifest_id": f"{request.register_id}:manifest",
        "generated_at_utc": _utc_now(),
        "retention_class": "governance_register",
        "contains_secrets": False,
        "redaction_policy": "none",
        "artifacts": [
            {
                "artifact_id": request.register_artifact_id,
                "artifact_role": "residual_limitations_register",
                "stack_id": request.stack_id,
            },
            *limitation_artifacts,
        ],
    }


def _structured_logs(
    request: ResidualLimitationsRegisterRequest,
    *,
    status: str,
    reason_code: str,
    missing_limitation_ids: tuple[str, ...],
    decision_surface_gaps: dict[str, tuple[str, ...]],
    nonobjective_limitation_ids: tuple[str, ...],
    missing_guardrail_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    correlation_id = f"{request.register_id}:{reason_code.lower()}"
    return (
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "residual_limitations_evaluated",
            "plane": "governance",
            "event_id": f"{request.register_id}:evaluation",
            "recorded_at_utc": _utc_now(),
            "correlation_id": correlation_id,
            "case_id": request.case_id,
            "stack_id": request.stack_id,
            "status": status,
            "reason_code": reason_code,
            "missing_limitation_ids": list(missing_limitation_ids),
            "decision_surface_gaps": {
                key: list(value) for key, value in decision_surface_gaps.items()
            },
            "nonobjective_limitation_ids": list(nonobjective_limitation_ids),
            "missing_guardrail_ids": list(missing_guardrail_ids),
        },
    )


def _diffs(
    *,
    missing_limitation_ids: tuple[str, ...],
    decision_surface_gaps: dict[str, tuple[str, ...]],
    nonobjective_limitation_ids: tuple[str, ...],
    missing_guardrail_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    diffs: list[dict[str, Any]] = []
    for limitation_id in missing_limitation_ids:
        diffs.append(
            {
                "field_name": "limitation_id",
                "expected": "present",
                "actual": "missing",
                "limitation_id": limitation_id,
            }
        )
    for limitation_id, missing_surfaces in decision_surface_gaps.items():
        diffs.append(
            {
                "field_name": "decision_surface_ids",
                "expected": list(REQUIRED_DECISION_SURFACES),
                "actual": list(missing_surfaces),
                "limitation_id": limitation_id,
            }
        )
    for limitation_id in nonobjective_limitation_ids:
        diffs.append(
            {
                "field_name": "accepted_only_for_initial_objective",
                "expected": True,
                "actual": False,
                "limitation_id": limitation_id,
            }
        )
    for limitation_id in missing_guardrail_ids:
        diffs.append(
            {
                "field_name": "expansion_guardrail",
                "expected": "non-empty",
                "actual": "missing",
                "limitation_id": limitation_id,
            }
        )
    return tuple(diffs)


def evaluate_residual_limitations_register(
    request: ResidualLimitationsRegisterRequest,
) -> ResidualLimitationsRegisterReport:
    limitation_map = {entry.limitation_id: entry for entry in request.limitations}
    covered_limitation_ids = tuple(sorted(limitation_map.keys()))
    missing_limitation_ids = tuple(
        limitation_id
        for limitation_id in REQUIRED_LIMITATION_IDS
        if limitation_id not in limitation_map
    )

    decision_surface_gaps: dict[str, tuple[str, ...]] = {}
    nonobjective_limitation_ids: list[str] = []
    missing_guardrail_ids: list[str] = []

    for limitation_id, entry in limitation_map.items():
        missing_surfaces = tuple(
            surface_id
            for surface_id in REQUIRED_DECISION_SURFACES
            if surface_id not in entry.decision_surface_ids
        )
        if missing_surfaces:
            decision_surface_gaps[limitation_id] = missing_surfaces
        if not entry.accepted_only_for_initial_objective or not entry.objective_rationale.strip():
            nonobjective_limitation_ids.append(limitation_id)
        if not entry.expansion_guardrail.strip():
            missing_guardrail_ids.append(limitation_id)

    if not _is_initial_objective(request.initial_objective):
        nonobjective_limitation_ids.extend(
            limitation_id
            for limitation_id in limitation_map
            if limitation_id not in nonobjective_limitation_ids
        )

    nonobjective_limitation_ids = list(_unique_strings(nonobjective_limitation_ids))
    missing_guardrail_ids = list(_unique_strings(missing_guardrail_ids))

    if missing_limitation_ids:
        status = "violation"
        reason_code = "RESIDUAL_LIMITATIONS_MISSING_REQUIRED_LIMITATION"
        explanation = "The residual limitations register omits one or more plan-required limitations."
        remediation = "Add every Phase 14.1 limitation explicitly before using the register downstream."
    elif decision_surface_gaps:
        status = "violation"
        reason_code = "RESIDUAL_LIMITATIONS_MISSING_DECISION_SURFACE"
        explanation = "One or more limitations is not available to promotion, continuation, and expansion decisions."
        remediation = "Attach each limitation explicitly to promotion, continuation review, and expansion review."
    elif nonobjective_limitation_ids:
        status = "violation"
        reason_code = "RESIDUAL_LIMITATIONS_NOT_OBJECTIVE_BOUND"
        explanation = "At least one limitation is being treated as acceptable without tying it to the initial objective."
        remediation = "Mark each limitation as acceptable only for honest validation and safe operation, with rationale."
    elif missing_guardrail_ids:
        status = "violation"
        reason_code = "RESIDUAL_LIMITATIONS_MISSING_GUARDRAIL"
        explanation = "At least one limitation lacks an explicit continuation or expansion guardrail."
        remediation = "Add a non-empty guardrail describing what later review or evidence would justify change."
    else:
        status = "pass"
        reason_code = "RESIDUAL_LIMITATIONS_REGISTER_COMPLETE"
        explanation = "The residual limitations register is explicit, decision-bound, and objective-bounded."
        remediation = "Continue using this register in promotion, continuation review, and expansion controls."

    artifact_manifest = _artifact_manifest(request)
    expected_vs_actual_diffs = _diffs(
        missing_limitation_ids=missing_limitation_ids,
        decision_surface_gaps=decision_surface_gaps,
        nonobjective_limitation_ids=tuple(nonobjective_limitation_ids),
        missing_guardrail_ids=tuple(missing_guardrail_ids),
    )
    structured_logs = _structured_logs(
        request,
        status=status,
        reason_code=reason_code,
        missing_limitation_ids=missing_limitation_ids,
        decision_surface_gaps=decision_surface_gaps,
        nonobjective_limitation_ids=tuple(nonobjective_limitation_ids),
        missing_guardrail_ids=tuple(missing_guardrail_ids),
    )
    operator_reason_bundle = {
        "summary": explanation,
        "initial_objective": request.initial_objective,
        "covered_limitation_ids": list(covered_limitation_ids),
        "missing_limitation_ids": list(missing_limitation_ids),
        "decision_surface_gaps": {
            key: list(value) for key, value in decision_surface_gaps.items()
        },
        "nonobjective_limitation_ids": list(nonobjective_limitation_ids),
        "missing_guardrail_ids": list(missing_guardrail_ids),
        "decision_surfaces_required": list(REQUIRED_DECISION_SURFACES),
    }

    return ResidualLimitationsRegisterReport(
        case_id=request.case_id,
        status=status,
        reason_code=reason_code,
        register_id=request.register_id,
        stack_id=request.stack_id,
        initial_objective=request.initial_objective,
        covered_limitation_ids=covered_limitation_ids,
        missing_limitation_ids=missing_limitation_ids,
        decision_surface_gaps={
            key: tuple(value) for key, value in decision_surface_gaps.items()
        },
        nonobjective_limitation_ids=tuple(nonobjective_limitation_ids),
        missing_guardrail_ids=tuple(missing_guardrail_ids),
        register_digest=_hash_payload(request.to_dict()),
        artifact_manifest=artifact_manifest,
        structured_logs=structured_logs,
        operator_reason_bundle=operator_reason_bundle,
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        explanation=explanation,
        remediation=remediation,
        timestamp=_utc_now(),
    )


def evaluate_residual_limitations_case(case_id: str) -> ResidualLimitationsRegisterReport:
    fixture = _fixture()
    cases = fixture["cases"]
    try:
        case = next(case for case in cases if case["case_id"] == case_id)
    except StopIteration as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown residual limitations case_id: {case_id}") from exc

    payload = dict(fixture["defaults"])
    overrides = dict(case.get("payload_overrides", {}))
    payload.update(overrides)
    payload["case_id"] = case_id

    if "limitation_mutations" in case:
        mutation_map = dict(case["limitation_mutations"])
        updated_limitations = []
        for limitation in payload["limitations"]:
            updated = dict(limitation)
            mutation = mutation_map.get(str(updated["limitation_id"]))
            if mutation:
                updated.update(dict(mutation))
            updated_limitations.append(updated)
        payload["limitations"] = updated_limitations

    if "drop_limitation_ids" in case:
        drop_ids = {str(item) for item in case["drop_limitation_ids"]}
        payload["limitations"] = [
            limitation
            for limitation in payload["limitations"]
            if str(limitation["limitation_id"]) not in drop_ids
        ]

    request = ResidualLimitationsRegisterRequest.from_dict(payload)
    return evaluate_residual_limitations_register(request)
