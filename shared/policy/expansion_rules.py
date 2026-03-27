"""Evidence-based post-v1 expansion rules for continuation review.

This surface keeps post-v1 growth conditional on measured evidence and explicit
continuation-review approval rather than letting deferred scope drift into the
default roadmap.
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

SUPPORTED_EXPANSION_RULES_SCHEMA_VERSION = 1
STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "policy"
    / "expansion_rules_cases.json"
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


@lru_cache(maxsize=1)
def _fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        decoded = json.load(fixture_file)
    if not isinstance(decoded, dict):  # pragma: no cover - defensive
        raise ValueError("expansion rules fixture must decode to an object")
    return decoded


@unique
class ExpansionRuleId(str, Enum):
    SECOND_BROKER = "second_broker"
    LIVE_PREMIUM_FEED = "live_premium_feed"
    KUBERNETES_ORCHESTRATION = "kubernetes_orchestration"
    DEPTH_DRIVEN_LIVE_ALPHA = "depth_driven_live_alpha"
    MULTIPLE_ACTIVE_LIVE_BUNDLES = "multiple_active_live_bundles"


@unique
class ExpansionEvidenceRequirement(str, Enum):
    BROKER_BOTTLENECK_PROVEN = "broker_bottleneck_proven"
    FEED_INSUFFICIENCY_PROVEN = "feed_insufficiency_proven"
    ONE_HOST_SLO_FAILURE_PROVEN = "one_host_slo_failure_proven"
    LIVE_STACK_REDESIGN_APPROVED = "live_stack_redesign_approved"
    SINGLE_BUNDLE_STABILITY_PROVEN = "single_bundle_stability_proven"
    ECONOMIC_JUSTIFICATION_PROVEN = "economic_justification_proven"


RULE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    ExpansionRuleId.SECOND_BROKER.value: (
        ExpansionEvidenceRequirement.BROKER_BOTTLENECK_PROVEN.value,
    ),
    ExpansionRuleId.LIVE_PREMIUM_FEED.value: (
        ExpansionEvidenceRequirement.FEED_INSUFFICIENCY_PROVEN.value,
    ),
    ExpansionRuleId.KUBERNETES_ORCHESTRATION.value: (
        ExpansionEvidenceRequirement.ONE_HOST_SLO_FAILURE_PROVEN.value,
    ),
    ExpansionRuleId.DEPTH_DRIVEN_LIVE_ALPHA.value: (
        ExpansionEvidenceRequirement.LIVE_STACK_REDESIGN_APPROVED.value,
    ),
    ExpansionRuleId.MULTIPLE_ACTIVE_LIVE_BUNDLES.value: (
        ExpansionEvidenceRequirement.SINGLE_BUNDLE_STABILITY_PROVEN.value,
        ExpansionEvidenceRequirement.ECONOMIC_JUSTIFICATION_PROVEN.value,
    ),
}
REQUIRED_RULE_IDS: tuple[str, ...] = tuple(item.value for item in ExpansionRuleId)


@dataclass(frozen=True)
class ExpansionRuleEvidence:
    rule_id: str
    evidence_ids: tuple[str, ...]
    satisfied_requirement_ids: tuple[str, ...]
    trigger_summary: str
    approval_scope: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExpansionRuleEvidence":
        return cls(
            rule_id=str(payload["rule_id"]),
            evidence_ids=_unique_strings([str(item) for item in payload["evidence_ids"]]),
            satisfied_requirement_ids=_unique_strings(
                [str(item) for item in payload["satisfied_requirement_ids"]]
            ),
            trigger_summary=str(payload["trigger_summary"]),
            approval_scope=str(payload["approval_scope"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExpansionRulesRequest:
    case_id: str
    continuation_review_id: str
    continuation_review_approved: bool
    residual_limitations_register_id: str
    residual_limitations_digest: str
    requested_rule_ids: tuple[str, ...]
    rule_evidence: tuple[ExpansionRuleEvidence, ...]
    review_artifact_id: str
    operator_notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExpansionRulesRequest":
        return cls(
            case_id=str(payload["case_id"]),
            continuation_review_id=str(payload["continuation_review_id"]),
            continuation_review_approved=bool(payload["continuation_review_approved"]),
            residual_limitations_register_id=str(payload["residual_limitations_register_id"]),
            residual_limitations_digest=str(payload["residual_limitations_digest"]),
            requested_rule_ids=_unique_strings(
                [str(item) for item in payload["requested_rule_ids"]]
            ),
            rule_evidence=tuple(
                ExpansionRuleEvidence.from_dict(item) for item in payload["rule_evidence"]
            ),
            review_artifact_id=str(payload["review_artifact_id"]),
            operator_notes=_unique_strings(
                [str(item) for item in payload.get("operator_notes", [])]
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rule_evidence"] = [item.to_dict() for item in self.rule_evidence]
        return payload


@dataclass(frozen=True)
class ExpansionRulesReport:
    case_id: str
    status: str
    reason_code: str
    continuation_review_id: str
    requested_rule_ids: tuple[str, ...]
    approved_rule_ids: tuple[str, ...]
    blocked_rule_ids: tuple[str, ...]
    missing_requirement_ids: dict[str, tuple[str, ...]]
    register_reference: dict[str, str]
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
        payload["missing_requirement_ids"] = {
            key: list(value) for key, value in self.missing_requirement_ids.items()
        }
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExpansionRulesReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            continuation_review_id=str(payload["continuation_review_id"]),
            requested_rule_ids=tuple(str(item) for item in payload["requested_rule_ids"]),
            approved_rule_ids=tuple(str(item) for item in payload["approved_rule_ids"]),
            blocked_rule_ids=tuple(str(item) for item in payload["blocked_rule_ids"]),
            missing_requirement_ids={
                str(key): tuple(str(item) for item in value)
                for key, value in payload["missing_requirement_ids"].items()
            },
            register_reference=dict(payload["register_reference"]),
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
    def from_json(cls, payload: str) -> "ExpansionRulesReport":
        return cls.from_dict(_decode_json_object(payload, label="expansion rules report"))


def _artifact_manifest(request: ExpansionRulesRequest) -> dict[str, Any]:
    artifacts = [
        {
            "artifact_id": request.review_artifact_id,
            "artifact_role": "continuation_review",
        }
    ]
    for item in request.rule_evidence:
        for evidence_id in item.evidence_ids:
            artifacts.append(
                {
                    "artifact_id": evidence_id,
                    "artifact_role": "expansion_evidence",
                    "rule_id": item.rule_id,
                }
            )
    return {
        "manifest_id": f"{request.continuation_review_id}:manifest",
        "generated_at_utc": _utc_now(),
        "retention_class": "continuation_governance",
        "contains_secrets": False,
        "redaction_policy": "none",
        "artifacts": artifacts,
    }


def _structured_logs(
    request: ExpansionRulesRequest,
    *,
    status: str,
    reason_code: str,
    approved_rule_ids: tuple[str, ...],
    blocked_rule_ids: tuple[str, ...],
    missing_requirement_ids: dict[str, tuple[str, ...]],
) -> tuple[dict[str, Any], ...]:
    return (
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "expansion_rules_evaluated",
            "plane": "governance",
            "event_id": f"{request.continuation_review_id}:evaluation",
            "recorded_at_utc": _utc_now(),
            "correlation_id": f"{request.continuation_review_id}:{reason_code.lower()}",
            "case_id": request.case_id,
            "status": status,
            "reason_code": reason_code,
            "approved_rule_ids": list(approved_rule_ids),
            "blocked_rule_ids": list(blocked_rule_ids),
            "missing_requirement_ids": {
                key: list(value) for key, value in missing_requirement_ids.items()
            },
            "residual_limitations_register_id": request.residual_limitations_register_id,
        },
    )


def _diffs(
    *,
    missing_requirement_ids: dict[str, tuple[str, ...]],
    blocked_rule_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    diffs: list[dict[str, Any]] = []
    for rule_id in blocked_rule_ids:
        diffs.append(
            {
                "field_name": "requested_rule_id",
                "expected": "approved_via_continuation_review",
                "actual": "blocked",
                "rule_id": rule_id,
                "missing_requirements": list(missing_requirement_ids.get(rule_id, ())),
            }
        )
    return tuple(diffs)


def evaluate_expansion_rules(request: ExpansionRulesRequest) -> ExpansionRulesReport:
    evidence_by_rule = {item.rule_id: item for item in request.rule_evidence}
    approved_rule_ids: list[str] = []
    blocked_rule_ids: list[str] = []
    missing_requirement_ids: dict[str, tuple[str, ...]] = {}

    for rule_id in request.requested_rule_ids:
        required = RULE_REQUIREMENTS.get(rule_id)
        evidence = evidence_by_rule.get(rule_id)
        if required is None:
            blocked_rule_ids.append(rule_id)
            missing_requirement_ids[rule_id] = ("unknown_rule_id",)
            continue
        if not request.continuation_review_approved:
            blocked_rule_ids.append(rule_id)
            missing_requirement_ids[rule_id] = ("continuation_review_approval",)
            continue
        if not request.residual_limitations_digest.strip():
            blocked_rule_ids.append(rule_id)
            missing_requirement_ids[rule_id] = ("residual_limitations_digest",)
            continue
        if evidence is None:
            blocked_rule_ids.append(rule_id)
            missing_requirement_ids[rule_id] = required
            continue
        missing = tuple(
            requirement
            for requirement in required
            if requirement not in evidence.satisfied_requirement_ids
        )
        if missing:
            blocked_rule_ids.append(rule_id)
            missing_requirement_ids[rule_id] = missing
        else:
            approved_rule_ids.append(rule_id)

    approved_rule_ids = list(_unique_strings(approved_rule_ids))
    blocked_rule_ids = list(_unique_strings(blocked_rule_ids))

    if blocked_rule_ids:
        status = "violation"
        reason_code = "EXPANSION_RULES_REQUIRE_MEASURED_EVIDENCE"
        explanation = (
            "Requested post-v1 scope growth is still blocked because continuation-review "
            "approval or the required measured evidence is missing."
        )
        remediation = (
            "Keep these items deferred until continuation review is approved and the "
            "required evidence is retained for each requested rule."
        )
    else:
        status = "pass"
        reason_code = "EXPANSION_RULES_APPROVED"
        explanation = (
            "Every requested expansion item is backed by measured evidence and explicit "
            "continuation-review approval."
        )
        remediation = (
            "Retain the continuation-review bundle and use the approved rule set as the "
            "only authorized path for post-v1 scope growth."
        )

    artifact_manifest = _artifact_manifest(request)
    structured_logs = _structured_logs(
        request,
        status=status,
        reason_code=reason_code,
        approved_rule_ids=tuple(approved_rule_ids),
        blocked_rule_ids=tuple(blocked_rule_ids),
        missing_requirement_ids=missing_requirement_ids,
    )
    operator_reason_bundle = {
        "summary": explanation,
        "requested_rule_ids": list(request.requested_rule_ids),
        "approved_rule_ids": approved_rule_ids,
        "blocked_rule_ids": blocked_rule_ids,
        "missing_requirement_ids": {
            key: list(value) for key, value in missing_requirement_ids.items()
        },
        "residual_limitations_register_id": request.residual_limitations_register_id,
        "residual_limitations_digest": request.residual_limitations_digest,
        "continuation_review_id": request.continuation_review_id,
    }

    return ExpansionRulesReport(
        case_id=request.case_id,
        status=status,
        reason_code=reason_code,
        continuation_review_id=request.continuation_review_id,
        requested_rule_ids=request.requested_rule_ids,
        approved_rule_ids=tuple(approved_rule_ids),
        blocked_rule_ids=tuple(blocked_rule_ids),
        missing_requirement_ids=missing_requirement_ids,
        register_reference={
            "register_id": request.residual_limitations_register_id,
            "register_digest": request.residual_limitations_digest,
        },
        artifact_manifest=artifact_manifest,
        structured_logs=structured_logs,
        operator_reason_bundle=operator_reason_bundle,
        expected_vs_actual_diffs=_diffs(
            missing_requirement_ids=missing_requirement_ids,
            blocked_rule_ids=tuple(blocked_rule_ids),
        ),
        explanation=explanation,
        remediation=remediation,
        timestamp=_utc_now(),
    )


def evaluate_expansion_rules_case(case_id: str) -> ExpansionRulesReport:
    fixture = _fixture()
    try:
        case = next(case for case in fixture["cases"] if case["case_id"] == case_id)
    except StopIteration as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown expansion rules case_id: {case_id}") from exc
    payload = dict(fixture["defaults"])
    payload.update(dict(case.get("payload_overrides", {})))
    payload["case_id"] = case_id

    if "evidence_mutations" in case:
        mutation_map = dict(case["evidence_mutations"])
        updated = []
        for evidence in payload["rule_evidence"]:
            record = dict(evidence)
            mutation = mutation_map.get(str(record["rule_id"]))
            if mutation:
                record.update(dict(mutation))
            updated.append(record)
        payload["rule_evidence"] = updated

    request = ExpansionRulesRequest.from_dict(payload)
    return evaluate_expansion_rules(request)
