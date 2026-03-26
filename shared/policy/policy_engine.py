"""Shared policy-engine orchestration and machine-readable decision traces."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum, unique
from typing import Any

from shared.policy.artifact_classes import evaluate_gate_admissibility
from shared.policy.deployment_packets import (
    BundleReadinessRecord,
    PromotionPacket,
    SessionReadinessPacket,
    validate_bundle_readiness_record,
    validate_promotion_packet,
    validate_session_readiness_packet,
)
from shared.policy.release_validation import (
    ReleaseLifecycleTransitionRequest,
    evaluate_release_lifecycle_transition,
)
from shared.policy.research_state import (
    ResearchStateStore,
    validate_decision_evidence_chain,
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_timestamp(value: str) -> str:
    return (
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(datetime.timezone.utc)
        .isoformat()
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@unique
class PolicyDecisionCategory(str, Enum):
    LIFECYCLE_TRANSITION = "lifecycle_transition"
    FRESHNESS_CHECK = "freshness_check"
    SESSION_READINESS = "session_readiness"
    PROMOTION_DECISION = "promotion_decision"


@unique
class PolicyDecisionOutcome(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WAIVER = "allow_with_waiver"
    BLOCK = "block"


@dataclass(frozen=True)
class PolicyWaiver:
    waiver_id: str
    categories: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    approved_by: str = ""
    justification: str = ""
    expires_at_utc: str | None = None
    related_incident_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "waiver_id": self.waiver_id,
            "categories": list(self.categories),
            "rule_ids": list(self.rule_ids),
            "reason_codes": list(self.reason_codes),
            "approved_by": self.approved_by,
            "justification": self.justification,
            "expires_at_utc": self.expires_at_utc,
            "related_incident_id": self.related_incident_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyWaiver":
        return cls(
            waiver_id=str(payload["waiver_id"]),
            categories=tuple(str(item) for item in payload.get("categories", ())),
            rule_ids=tuple(str(item) for item in payload.get("rule_ids", ())),
            reason_codes=tuple(str(item) for item in payload.get("reason_codes", ())),
            approved_by=str(payload.get("approved_by", "")),
            justification=str(payload.get("justification", "")),
            expires_at_utc=(
                str(payload["expires_at_utc"])
                if payload.get("expires_at_utc") is not None
                else None
            ),
            related_incident_id=(
                str(payload["related_incident_id"])
                if payload.get("related_incident_id") is not None
                else None
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "PolicyWaiver":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("policy_waiver: invalid JSON payload") from exc
        return cls.from_dict(data)

    def is_active(self, at_utc: str | None = None) -> bool:
        if self.expires_at_utc is None:
            return True
        comparison_time = _normalize_timestamp(at_utc or _utc_now())
        return _normalize_timestamp(self.expires_at_utc) >= comparison_time

    def matches(
        self,
        *,
        category: PolicyDecisionCategory,
        rule_id: str,
        reason_code: str | None,
        at_utc: str | None = None,
    ) -> bool:
        if not self.is_active(at_utc):
            return False
        if self.categories and category.value not in self.categories:
            return False
        if self.rule_ids and rule_id not in self.rule_ids:
            return False
        if self.reason_codes and reason_code not in self.reason_codes:
            return False
        return True


@dataclass(frozen=True)
class PolicyRuleEvaluation:
    rule_id: str
    rule_name: str
    passed: bool
    status: str
    reason_code: str | None
    diagnostic: str
    context: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    waived: bool = False
    waiver_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "passed": self.passed,
            "status": self.status,
            "reason_code": self.reason_code,
            "diagnostic": self.diagnostic,
            "context": _jsonable(self.context),
            "remediation": self.remediation,
            "waived": self.waived,
            "waiver_references": list(self.waiver_references),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyRuleEvaluation":
        return cls(
            rule_id=str(payload["rule_id"]),
            rule_name=str(payload["rule_name"]),
            passed=bool(payload["passed"]),
            status=str(payload["status"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") is not None
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            context=dict(payload.get("context", {})),
            remediation=(
                str(payload["remediation"])
                if payload.get("remediation") is not None
                else None
            ),
            waived=bool(payload.get("waived", False)),
            waiver_references=tuple(
                str(item) for item in payload.get("waiver_references", ())
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "PolicyRuleEvaluation":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("policy_rule_evaluation: invalid JSON payload") from exc
        return cls.from_dict(data)


@dataclass(frozen=True)
class PolicyDecisionTrace:
    decision_id: str
    category: str
    policy_bundle_hash: str
    inputs: dict[str, Any]
    evaluated_rules: tuple[PolicyRuleEvaluation, ...]
    waiver_references: tuple[str, ...]
    decision: str
    decision_reason_code: str
    decision_diagnostic: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "category": self.category,
            "policy_bundle_hash": self.policy_bundle_hash,
            "inputs": _jsonable(self.inputs),
            "evaluated_rules": [item.to_dict() for item in self.evaluated_rules],
            "waiver_references": list(self.waiver_references),
            "decision": self.decision,
            "decision_reason_code": self.decision_reason_code,
            "decision_diagnostic": self.decision_diagnostic,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PolicyDecisionTrace":
        return cls(
            decision_id=str(payload["decision_id"]),
            category=str(payload["category"]),
            policy_bundle_hash=str(payload["policy_bundle_hash"]),
            inputs=dict(payload["inputs"]),
            evaluated_rules=tuple(
                PolicyRuleEvaluation.from_dict(dict(item))
                for item in payload["evaluated_rules"]
            ),
            waiver_references=tuple(
                str(item) for item in payload.get("waiver_references", ())
            ),
            decision=str(payload["decision"]),
            decision_reason_code=str(payload["decision_reason_code"]),
            decision_diagnostic=str(payload["decision_diagnostic"]),
            timestamp=str(payload["timestamp"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "PolicyDecisionTrace":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("policy_decision_trace: invalid JSON payload") from exc
        return cls.from_dict(data)


@dataclass(frozen=True)
class PolicyEngine:
    policy_bundle_hash: str
    waivers: tuple[PolicyWaiver, ...] = ()
    evaluated_at_utc: str | None = None

    def evaluate_lifecycle_transition(
        self,
        request: ReleaseLifecycleTransitionRequest,
    ) -> PolicyDecisionTrace:
        report = evaluate_release_lifecycle_transition(request)
        rules = (
            self._lifecycle_rule(report),
        )
        return self._finalize_trace(
            category=PolicyDecisionCategory.LIFECYCLE_TRANSITION,
            decision_id=f"{PolicyDecisionCategory.LIFECYCLE_TRANSITION.value}:{request.case_id}",
            inputs={"request": _jsonable(request)},
            rules=rules,
        )

    def evaluate_freshness_gate(
        self,
        *,
        gate_name: str,
        integrity_artifacts: list[dict[str, str]],
        freshness_evidence: list[dict[str, str]],
    ) -> PolicyDecisionTrace:
        gate_report = evaluate_gate_admissibility(
            gate_name=gate_name,
            integrity_artifacts=integrity_artifacts,
            freshness_evidence=freshness_evidence,
        )
        rules = tuple(
            self._artifact_rule(gate_name, payload)
            for payload in gate_report["diagnostics"]
        )
        return self._finalize_trace(
            category=PolicyDecisionCategory.FRESHNESS_CHECK,
            decision_id=f"{PolicyDecisionCategory.FRESHNESS_CHECK.value}:{gate_name}",
            inputs={
                "gate_name": gate_name,
                "integrity_artifacts": integrity_artifacts,
                "freshness_evidence": freshness_evidence,
                "gate_summary": {
                    key: value
                    for key, value in gate_report.items()
                    if key != "diagnostics"
                },
            },
            rules=rules,
        )

    def evaluate_session_readiness(
        self,
        *,
        case_id: str,
        readiness_record: BundleReadinessRecord,
        session_packet: SessionReadinessPacket,
    ) -> PolicyDecisionTrace:
        readiness_report = validate_bundle_readiness_record(case_id, readiness_record)
        session_report = validate_session_readiness_packet(case_id, session_packet)
        rules = (
            self._policy_bundle_alignment_rule(
                PolicyDecisionCategory.SESSION_READINESS,
                input_policy_bundle_hash=readiness_record.policy_bundle_hash,
            ),
            self._packet_rule(
                rule_id="bundle_readiness_record",
                rule_name="bundle_readiness_record validation",
                report=readiness_report,
            ),
            self._packet_rule(
                rule_id="session_readiness_packet",
                rule_name="session_readiness_packet validation",
                report=session_report,
            ),
        )
        return self._finalize_trace(
            category=PolicyDecisionCategory.SESSION_READINESS,
            decision_id=f"{PolicyDecisionCategory.SESSION_READINESS.value}:{case_id}",
            inputs={
                "case_id": case_id,
                "readiness_record": _jsonable(readiness_record),
                "session_packet": _jsonable(session_packet),
            },
            rules=rules,
        )

    def evaluate_promotion_decision(
        self,
        *,
        case_id: str,
        promotion_packet: PromotionPacket,
        store: ResearchStateStore | None = None,
        decision_record_id: str | None = None,
    ) -> PolicyDecisionTrace:
        promotion_report = validate_promotion_packet(case_id, promotion_packet)
        rules = [
            self._policy_bundle_alignment_rule(
                PolicyDecisionCategory.PROMOTION_DECISION,
                input_policy_bundle_hash=promotion_packet.policy_bundle_hash,
            ),
            self._packet_rule(
                rule_id="promotion_packet",
                rule_name="promotion_packet validation",
                report=promotion_report,
            ),
        ]
        if store is not None and decision_record_id is not None:
            rules.append(
                self._evidence_chain_rule(
                    validate_decision_evidence_chain(store, decision_record_id)
                )
            )
        return self._finalize_trace(
            category=PolicyDecisionCategory.PROMOTION_DECISION,
            decision_id=f"{PolicyDecisionCategory.PROMOTION_DECISION.value}:{case_id}",
            inputs={
                "case_id": case_id,
                "promotion_packet": _jsonable(promotion_packet),
                "decision_record_id": decision_record_id,
            },
            rules=tuple(rules),
            declared_waiver_references=promotion_packet.active_waiver_ids,
        )

    def _evaluation_timestamp(self) -> str:
        if self.evaluated_at_utc is not None:
            return _normalize_timestamp(self.evaluated_at_utc)
        return _utc_now()

    def _matching_waiver_ids(
        self,
        *,
        category: PolicyDecisionCategory,
        rule_id: str,
        reason_code: str | None,
    ) -> tuple[str, ...]:
        return tuple(
            waiver.waiver_id
            for waiver in self.waivers
            if waiver.matches(
                category=category,
                rule_id=rule_id,
                reason_code=reason_code,
                at_utc=self.evaluated_at_utc,
            )
        )

    def _decorate_rule(
        self,
        *,
        category: PolicyDecisionCategory,
        rule: PolicyRuleEvaluation,
    ) -> PolicyRuleEvaluation:
        if rule.passed:
            return rule
        waiver_ids = self._matching_waiver_ids(
            category=category,
            rule_id=rule.rule_id,
            reason_code=rule.reason_code,
        )
        if not waiver_ids:
            return rule
        return PolicyRuleEvaluation(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            passed=rule.passed,
            status=rule.status,
            reason_code=rule.reason_code,
            diagnostic=rule.diagnostic,
            context=rule.context,
            remediation=rule.remediation,
            waived=True,
            waiver_references=waiver_ids,
        )

    def _finalize_trace(
        self,
        *,
        category: PolicyDecisionCategory,
        decision_id: str,
        inputs: dict[str, Any],
        rules: tuple[PolicyRuleEvaluation, ...],
        declared_waiver_references: tuple[str, ...] = (),
    ) -> PolicyDecisionTrace:
        decorated_rules = tuple(
            self._decorate_rule(category=category, rule=rule) for rule in rules
        )
        matched_waiver_ids = {
            waiver_id
            for rule in decorated_rules
            for waiver_id in rule.waiver_references
        }
        waiver_references = tuple(
            sorted(set(declared_waiver_references).union(matched_waiver_ids))
        )
        failing_unwaived = [
            rule for rule in decorated_rules if not rule.passed and not rule.waived
        ]
        failing_waived = [rule for rule in decorated_rules if not rule.passed and rule.waived]

        if failing_unwaived:
            decision = PolicyDecisionOutcome.BLOCK.value
            decision_reason_code = "POLICY_DECISION_BLOCKED"
            decision_diagnostic = (
                f"Policy engine blocked {category.value} because "
                + ", ".join(rule.reason_code or rule.rule_id for rule in failing_unwaived)
                + " remained unresolved."
            )
        elif failing_waived:
            decision = PolicyDecisionOutcome.ALLOW_WITH_WAIVER.value
            decision_reason_code = "POLICY_DECISION_ALLOWED_WITH_WAIVER"
            decision_diagnostic = (
                f"Policy engine allowed {category.value} under active waiver references: "
                + ", ".join(waiver_references)
                + "."
            )
        else:
            decision = PolicyDecisionOutcome.ALLOW.value
            decision_reason_code = "POLICY_DECISION_ALLOWED"
            decision_diagnostic = (
                f"Policy engine allowed {category.value}; all evaluated rules passed."
            )

        return PolicyDecisionTrace(
            decision_id=decision_id,
            category=category.value,
            policy_bundle_hash=self.policy_bundle_hash,
            inputs=_jsonable(inputs),
            evaluated_rules=decorated_rules,
            waiver_references=waiver_references,
            decision=decision,
            decision_reason_code=decision_reason_code,
            decision_diagnostic=decision_diagnostic,
            timestamp=self._evaluation_timestamp(),
        )

    def _policy_bundle_alignment_rule(
        self,
        category: PolicyDecisionCategory,
        *,
        input_policy_bundle_hash: str,
    ) -> PolicyRuleEvaluation:
        passed = input_policy_bundle_hash == self.policy_bundle_hash
        return PolicyRuleEvaluation(
            rule_id="policy_bundle_alignment",
            rule_name="policy bundle alignment",
            passed=passed,
            status="pass" if passed else "violation",
            reason_code=None if passed else "POLICY_ENGINE_BUNDLE_HASH_MISMATCH",
            diagnostic=(
                "Input policy bundle hash matches the shared policy engine bundle."
                if passed
                else "Input policy bundle hash does not match the shared policy engine bundle."
            ),
            context={
                "category": category.value,
                "engine_policy_bundle_hash": self.policy_bundle_hash,
                "input_policy_bundle_hash": input_policy_bundle_hash,
            },
            remediation=(
                None
                if passed
                else "Rebuild the input under the same policy bundle hash or evaluate it with the correct engine bundle."
            ),
        )

    @staticmethod
    def _artifact_rule(
        gate_name: str,
        payload: dict[str, Any],
    ) -> PolicyRuleEvaluation:
        return PolicyRuleEvaluation(
            rule_id=str(payload["artifact_id"]),
            rule_name=str(payload["title"]),
            passed=bool(payload["admissible"]),
            status=str(payload["status"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") is not None
                else None
            ),
            diagnostic=str(payload["explanation"]),
            context={
                "gate_name": gate_name,
                "artifact_class": payload["artifact_class"],
                "dependency_state": payload["dependency_state"],
                "freshness_state": payload["freshness_state"],
                "invalidation_channel": payload["invalidation_channel"],
            },
        )

    @staticmethod
    def _lifecycle_rule(report: Any) -> PolicyRuleEvaluation:
        return PolicyRuleEvaluation(
            rule_id="release_lifecycle_transition",
            rule_name="release lifecycle transition",
            passed=report.status == "pass",
            status=report.status,
            reason_code=report.reason_code,
            diagnostic=report.explanation,
            context={
                "release_id": report.release_id,
                "release_kind": report.release_kind,
                "from_state": report.from_state,
                "to_state": report.to_state,
                "new_work_posture": report.new_work_posture,
                "dependency_action": report.dependency_action,
            },
            remediation=report.remediation,
        )

    @staticmethod
    def _packet_rule(
        *,
        rule_id: str,
        rule_name: str,
        report: Any,
    ) -> PolicyRuleEvaluation:
        return PolicyRuleEvaluation(
            rule_id=rule_id,
            rule_name=rule_name,
            passed=report.status == "pass",
            status=report.status,
            reason_code=report.reason_code,
            diagnostic=report.explanation,
            context=_jsonable(report.context),
            remediation=report.remediation,
        )

    @staticmethod
    def _evidence_chain_rule(report: Any) -> PolicyRuleEvaluation:
        return PolicyRuleEvaluation(
            rule_id="family_decision_evidence_chain",
            rule_name="family_decision evidence chain",
            passed=report.status == "pass",
            status=report.status,
            reason_code=report.reason_code,
            diagnostic=report.explanation,
            context={
                "decision_record_id": report.decision_record_id,
                "family_id": report.family_id,
                "referenced_run_ids": report.referenced_run_ids,
                "missing_run_ids": report.missing_run_ids,
                "foreign_family_run_ids": report.foreign_family_run_ids,
                "duplicate_references": report.duplicate_references,
            },
        )


def evaluate_lifecycle_transition_policy(
    *,
    policy_bundle_hash: str,
    request: ReleaseLifecycleTransitionRequest,
    waivers: tuple[PolicyWaiver, ...] = (),
    evaluated_at_utc: str | None = None,
) -> PolicyDecisionTrace:
    return PolicyEngine(
        policy_bundle_hash=policy_bundle_hash,
        waivers=waivers,
        evaluated_at_utc=evaluated_at_utc,
    ).evaluate_lifecycle_transition(request)


def evaluate_freshness_policy(
    *,
    policy_bundle_hash: str,
    gate_name: str,
    integrity_artifacts: list[dict[str, str]],
    freshness_evidence: list[dict[str, str]],
    waivers: tuple[PolicyWaiver, ...] = (),
    evaluated_at_utc: str | None = None,
) -> PolicyDecisionTrace:
    return PolicyEngine(
        policy_bundle_hash=policy_bundle_hash,
        waivers=waivers,
        evaluated_at_utc=evaluated_at_utc,
    ).evaluate_freshness_gate(
        gate_name=gate_name,
        integrity_artifacts=integrity_artifacts,
        freshness_evidence=freshness_evidence,
    )


def evaluate_session_readiness_policy(
    *,
    policy_bundle_hash: str,
    case_id: str,
    readiness_record: BundleReadinessRecord,
    session_packet: SessionReadinessPacket,
    waivers: tuple[PolicyWaiver, ...] = (),
    evaluated_at_utc: str | None = None,
) -> PolicyDecisionTrace:
    return PolicyEngine(
        policy_bundle_hash=policy_bundle_hash,
        waivers=waivers,
        evaluated_at_utc=evaluated_at_utc,
    ).evaluate_session_readiness(
        case_id=case_id,
        readiness_record=readiness_record,
        session_packet=session_packet,
    )


def evaluate_promotion_policy(
    *,
    policy_bundle_hash: str,
    case_id: str,
    promotion_packet: PromotionPacket,
    store: ResearchStateStore | None = None,
    decision_record_id: str | None = None,
    waivers: tuple[PolicyWaiver, ...] = (),
    evaluated_at_utc: str | None = None,
) -> PolicyDecisionTrace:
    return PolicyEngine(
        policy_bundle_hash=policy_bundle_hash,
        waivers=waivers,
        evaluated_at_utc=evaluated_at_utc,
    ).evaluate_promotion_decision(
        case_id=case_id,
        promotion_packet=promotion_packet,
        store=store,
        decision_record_id=decision_record_id,
    )


def validate_policy_engine_contract() -> list[str]:
    errors: list[str] = []
    if {item.value for item in PolicyDecisionCategory} != {
        "lifecycle_transition",
        "freshness_check",
        "session_readiness",
        "promotion_decision",
    }:
        errors.append("policy engine categories must cover lifecycle, freshness, readiness, and promotion")
    if {item.value for item in PolicyDecisionOutcome} != {
        "allow",
        "allow_with_waiver",
        "block",
    }:
        errors.append("policy engine outcomes must remain allow/allow_with_waiver/block")
    return errors


VALIDATION_ERRORS = validate_policy_engine_contract()

