"""Operational-evidence admissibility and promotion exit gate contract."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.clock_discipline import canonicalize_persisted_timestamp
from shared.policy.deployment_packets import DeploymentState
from shared.policy.paper_shadow_stage_policy import PaperShadowStagePolicyReport

SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION = 1
STRUCTURED_LOG_SCHEMA_VERSION = "1.0.0"
VALIDATION_ERRORS: list[str] = []

EXECUTION_CALIBRATION_DOMAINS = (
    "execution_assumptions",
    "data_quality_expectations",
    "operating_envelope_thresholds",
)
RISK_POLICY_DOMAINS = (*EXECUTION_CALIBRATION_DOMAINS, "risk_policy_controls")

PAPER_TO_SHADOW_REQUIRED_CRITERIA = (
    "replay_certification_holds",
    "portability_certification_holds_when_required",
    "native_1oz_validation_holds_when_required",
    "paper_sample_quality_sufficient",
    "no_blocking_reconciliation_discrepancy",
    "operating_envelope_behavior_acceptable",
    "strategy_health_drift_within_bounds",
    "signed_promotion_packet_to_shadow_live",
)
SHADOW_TO_CANARY_REQUIRED_CRITERIA = (
    "exact_live_data_and_broker_lane_exercised_cleanly",
    "shadow_reconciliation_and_intent_logging_clean",
    "no_permission_or_entitlement_issue",
    "no_contract_conformance_issue",
    "no_session_reset_issue",
    "signed_promotion_packet_to_live_canary",
    "shadow_review_completed",
)
CANARY_TO_ACTIVE_REQUIRED_CRITERIA = (
    "conservative_canary_constraints_respected",
    "canary_sample_quality_sufficient",
    "no_unresolved_canary_incident",
    "canary_review_completed",
    "signed_promotion_packet_to_live_active",
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


def _artifact_record(run_id: str, case_id: str, role: str, payload: Any) -> dict[str, Any]:
    return {
        "artifact_id": f"{run_id}_{role}",
        "artifact_role": role,
        "relative_path": f"verification/operational_evidence_gate/{case_id}/{role}.json",
        "sha256": _sha256_payload(payload),
        "content_type": "application/json",
    }


@unique
class OperationalEvidenceGateStatus(str, Enum):
    PASS = "pass"  # nosec B105 - gate status literal, not a credential
    BLOCKED = "blocked"
    INVALID = "invalid"


@unique
class OperationalEvidenceClass(str, Enum):
    DIAGNOSTIC_ONLY = "diagnostic_only"
    EXECUTION_CALIBRATION_ADMISSIBLE = "execution_calibration_admissible"
    RISK_POLICY_ADMISSIBLE = "risk_policy_admissible"
    INCIDENT_REVIEW_ONLY = "incident_review_only"


@unique
class PromotionTransition(str, Enum):
    PAPER_TO_SHADOW_LIVE = "paper_to_shadow_live"
    SHADOW_LIVE_TO_LIVE_CANARY = "shadow_live_to_live_canary"
    LIVE_CANARY_TO_LIVE_ACTIVE = "live_canary_to_live_active"


@dataclass(frozen=True)
class OperationalEvidenceRecord:
    evidence_id: str
    evidence_class: str
    sealed: bool
    reconciled: bool
    minimum_sample_check_passed: bool
    policy_approved: bool
    allowed_update_domains: tuple[str, ...]
    detail: str
    artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperationalEvidenceRecord":
        return cls(
            evidence_id=str(payload["evidence_id"]),
            evidence_class=str(payload["evidence_class"]),
            sealed=bool(payload["sealed"]),
            reconciled=bool(payload["reconciled"]),
            minimum_sample_check_passed=bool(payload["minimum_sample_check_passed"]),
            policy_approved=bool(payload["policy_approved"]),
            allowed_update_domains=tuple(
                str(item) for item in payload.get("allowed_update_domains", ())
            ),
            detail=str(payload["detail"]),
            artifact_ids=tuple(str(item) for item in payload.get("artifact_ids", ())),
        )


@dataclass(frozen=True)
class ExitCriterionRecord:
    criterion_id: str
    satisfied: bool
    reference_id: str
    detail: str
    supporting_evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExitCriterionRecord":
        return cls(
            criterion_id=str(payload["criterion_id"]),
            satisfied=bool(payload["satisfied"]),
            reference_id=str(payload["reference_id"]),
            detail=str(payload["detail"]),
            supporting_evidence_ids=tuple(
                str(item) for item in payload.get("supporting_evidence_ids", ())
            ),
        )


@dataclass(frozen=True)
class OperationalEvidenceGateRequest:
    case_id: str
    stage_policy_report: PaperShadowStagePolicyReport
    requested_transition: str
    current_deployment_state: str
    operational_evidence: tuple[OperationalEvidenceRecord, ...]
    exit_criteria: tuple[ExitCriterionRecord, ...]
    correlation_id: str
    operator_reason_bundle: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "stage_policy_report": self.stage_policy_report.to_dict(),
            "requested_transition": self.requested_transition,
            "current_deployment_state": self.current_deployment_state,
            "operational_evidence": [record.to_dict() for record in self.operational_evidence],
            "exit_criteria": [record.to_dict() for record in self.exit_criteria],
            "correlation_id": self.correlation_id,
            "operator_reason_bundle": list(self.operator_reason_bundle),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OperationalEvidenceGateRequest":
        return cls(
            case_id=str(payload["case_id"]),
            stage_policy_report=PaperShadowStagePolicyReport.from_dict(
                dict(payload["stage_policy_report"])
            ),
            requested_transition=str(payload["requested_transition"]),
            current_deployment_state=str(payload["current_deployment_state"]),
            operational_evidence=tuple(
                OperationalEvidenceRecord.from_dict(dict(item))
                for item in payload["operational_evidence"]
            ),
            exit_criteria=tuple(
                ExitCriterionRecord.from_dict(dict(item))
                for item in payload["exit_criteria"]
            ),
            correlation_id=str(payload["correlation_id"]),
            operator_reason_bundle=tuple(
                str(item) for item in payload.get("operator_reason_bundle", ())
            ),
            schema_version=int(
                payload.get(
                    "schema_version", SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OperationalEvidenceGateRequest":
        return cls.from_dict(_decode_json_object(payload, label="operational_evidence_gate_request"))


@dataclass(frozen=True)
class OperationalEvidenceGateReport:
    schema_version: int
    case_id: str
    requested_transition: str
    current_deployment_state: str
    approved_target_state: str | None
    status: str
    reason_code: str
    promotion_allowed: bool
    promotion_admissible_evidence_ids: tuple[str, ...]
    blocked_evidence_ids: tuple[str, ...]
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
    def from_dict(cls, payload: dict[str, Any]) -> "OperationalEvidenceGateReport":
        return cls(
            schema_version=int(payload["schema_version"]),
            case_id=str(payload["case_id"]),
            requested_transition=str(payload["requested_transition"]),
            current_deployment_state=str(payload["current_deployment_state"]),
            approved_target_state=(
                str(payload["approved_target_state"])
                if payload.get("approved_target_state") is not None
                else None
            ),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            promotion_allowed=bool(payload["promotion_allowed"]),
            promotion_admissible_evidence_ids=tuple(
                str(item) for item in payload["promotion_admissible_evidence_ids"]
            ),
            blocked_evidence_ids=tuple(str(item) for item in payload["blocked_evidence_ids"]),
            decision_trace=[dict(item) for item in payload["decision_trace"]],
            expected_vs_actual_diffs=[
                dict(item) for item in payload["expected_vs_actual_diffs"]
            ],
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            operator_reason_bundle=dict(payload["operator_reason_bundle"]),
            artifact_manifest=dict(payload["artifact_manifest"]),
            structured_logs=[dict(item) for item in payload["structured_logs"]],
            context=dict(payload["context"]),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OperationalEvidenceGateReport":
        return cls.from_dict(_decode_json_object(payload, label="operational_evidence_gate_report"))


def _required_criteria(transition: PromotionTransition) -> tuple[str, ...]:
    if transition is PromotionTransition.PAPER_TO_SHADOW_LIVE:
        return PAPER_TO_SHADOW_REQUIRED_CRITERIA
    if transition is PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY:
        return SHADOW_TO_CANARY_REQUIRED_CRITERIA
    return CANARY_TO_ACTIVE_REQUIRED_CRITERIA


def _target_state(transition: PromotionTransition) -> DeploymentState:
    if transition is PromotionTransition.PAPER_TO_SHADOW_LIVE:
        return DeploymentState.SHADOW_RUNNING
    if transition is PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY:
        return DeploymentState.LIVE_CANARY
    return DeploymentState.LIVE_ACTIVE


def _stage_policy_ready(
    transition: PromotionTransition, report: PaperShadowStagePolicyReport
) -> tuple[bool, str]:
    if transition is PromotionTransition.PAPER_TO_SHADOW_LIVE:
        return report.paper_stage_complete, "paper_stage_complete"
    if transition is PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY:
        return report.live_activation_permitted, "live_activation_permitted"
    return report.live_activation_permitted, "live_activation_permitted"


def _classify_operational_evidence(
    record: OperationalEvidenceRecord,
) -> tuple[bool, str, list[str]]:
    try:
        evidence_class = OperationalEvidenceClass(record.evidence_class)
    except ValueError:
        return False, "OPERATIONAL_EVIDENCE_CLASS_INVALID", list(record.allowed_update_domains)

    if evidence_class in (
        OperationalEvidenceClass.DIAGNOSTIC_ONLY,
        OperationalEvidenceClass.INCIDENT_REVIEW_ONLY,
    ):
        return False, "OPERATIONAL_EVIDENCE_CLASS_NOT_PROMOTION_ADMISSIBLE", list(
            record.allowed_update_domains
        )

    if not (
        record.sealed
        and record.reconciled
        and record.minimum_sample_check_passed
        and record.policy_approved
    ):
        return False, "OPERATIONAL_EVIDENCE_PROVENANCE_INCOMPLETE", []

    allowed_domains = (
        EXECUTION_CALIBRATION_DOMAINS
        if evidence_class is OperationalEvidenceClass.EXECUTION_CALIBRATION_ADMISSIBLE
        else RISK_POLICY_DOMAINS
    )
    disallowed = [domain for domain in record.allowed_update_domains if domain not in allowed_domains]
    if disallowed:
        return False, "OPERATIONAL_EVIDENCE_DISALLOWED_UPDATE_DOMAIN", disallowed
    return True, "OPERATIONAL_EVIDENCE_PROMOTION_ADMISSIBLE", []


def evaluate_operational_evidence_gate(
    request: OperationalEvidenceGateRequest,
) -> OperationalEvidenceGateReport:
    """Evaluate promotion-exit criteria backed by admissible operational evidence."""

    run_id = f"{request.case_id}_{_sha256_payload(request.to_dict())[:12]}"
    validation_diffs: list[dict[str, Any]] = []

    if request.schema_version != SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION:
        validation_diffs.append(
            {
                "subject": "schema_version",
                "expected": SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION,
                "actual": request.schema_version,
            }
        )
    try:
        transition = PromotionTransition(request.requested_transition)
    except ValueError:
        validation_diffs.append(
            {
                "subject": "requested_transition",
                "expected": [item.value for item in PromotionTransition],
                "actual": request.requested_transition,
            }
        )
        transition = None

    try:
        current_state = DeploymentState(request.current_deployment_state)
    except ValueError:
        validation_diffs.append(
            {
                "subject": "current_deployment_state",
                "expected": [item.value for item in DeploymentState],
                "actual": request.current_deployment_state,
            }
        )
        current_state = None

    if validation_diffs:
        VALIDATION_ERRORS[:] = [diff["subject"] for diff in validation_diffs]
        artifacts = [
            _artifact_record(run_id, request.case_id, "gate_request", request.to_dict()),
            _artifact_record(run_id, request.case_id, "expected_vs_actual_diffs", validation_diffs),
        ]
        manifest = {
            "manifest_id": f"artifact_manifest_{run_id}",
            "generated_at_utc": _utcnow(),
            "retention_class": "promotion_gate_validation",
            "contains_secrets": False,
            "redaction_policy": "opaque_identifiers_only",
            "artifacts": artifacts,
        }
        return OperationalEvidenceGateReport(
            schema_version=SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION,
            case_id=request.case_id,
            requested_transition=request.requested_transition,
            current_deployment_state=request.current_deployment_state,
            approved_target_state=None,
            status=OperationalEvidenceGateStatus.INVALID.value,
            reason_code="OPERATIONAL_EVIDENCE_GATE_REQUEST_INVALID",
            promotion_allowed=False,
            promotion_admissible_evidence_ids=(),
            blocked_evidence_ids=(),
            decision_trace=[],
            expected_vs_actual_diffs=validation_diffs,
            retained_artifact_ids=_unique_strings(
                [artifact["artifact_id"] for artifact in artifacts]
            ),
            operator_reason_bundle={
                "gate_summary": {
                    "status": OperationalEvidenceGateStatus.INVALID.value,
                    "reason_code": "OPERATIONAL_EVIDENCE_GATE_REQUEST_INVALID",
                },
                "operator_notes": list(request.operator_reason_bundle),
            },
            artifact_manifest=manifest,
            structured_logs=[
                {
                    "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
                    "event_type": "operational_evidence_gate.invalid",
                    "correlation_id": request.correlation_id,
                    "run_id": run_id,
                    "case_id": request.case_id,
                    "details": validation_diffs,
                    "timestamp": _utcnow(),
                }
            ],
            context={"validation_diffs": validation_diffs},
            explanation="The operational-evidence gate request is malformed.",
            remediation="Correct the invalid request fields and rerun the gate.",
        )

    admissible_evidence_ids: list[str] = []
    blocked_evidence_ids: list[str] = []
    evidence_trace: list[dict[str, Any]] = []
    expected_vs_actual_diffs: list[dict[str, Any]] = []
    evidence_by_id = {record.evidence_id: record for record in request.operational_evidence}

    for record in request.operational_evidence:
        admissible, reason_code, disallowed_domains = _classify_operational_evidence(record)
        evidence_trace.append(
            {
                "subject": f"operational_evidence.{record.evidence_id}",
                "evidence_class": record.evidence_class,
                "passed": admissible,
                "reason_code": reason_code,
                "detail": record.detail,
                "disallowed_domains": disallowed_domains,
            }
        )
        if admissible:
            admissible_evidence_ids.append(record.evidence_id)
        else:
            blocked_evidence_ids.append(record.evidence_id)
            expected_vs_actual_diffs.append(
                {
                    "subject": f"operational_evidence.{record.evidence_id}",
                    "expected": "promotion-admissible evidence",
                    "actual": reason_code,
                    "disallowed_domains": disallowed_domains,
                }
            )

    stage_ready, stage_field = _stage_policy_ready(transition, request.stage_policy_report)
    if not stage_ready:
        expected_vs_actual_diffs.append(
            {
                "subject": "stage_policy_report",
                "expected": f"{stage_field}=true",
                "actual": stage_field,
            }
        )

    target_state = _target_state(transition)
    if transition is PromotionTransition.PAPER_TO_SHADOW_LIVE and current_state not in (
        DeploymentState.PAPER_PENDING,
        DeploymentState.PAPER_RUNNING,
    ):
        expected_vs_actual_diffs.append(
            {
                "subject": "current_deployment_state",
                "expected": [
                    DeploymentState.PAPER_PENDING.value,
                    DeploymentState.PAPER_RUNNING.value,
                ],
                "actual": current_state.value,
            }
        )
    elif transition is PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY and current_state is not DeploymentState.SHADOW_RUNNING:
        expected_vs_actual_diffs.append(
            {
                "subject": "current_deployment_state",
                "expected": DeploymentState.SHADOW_RUNNING.value,
                "actual": current_state.value,
            }
        )
    elif transition is PromotionTransition.LIVE_CANARY_TO_LIVE_ACTIVE and current_state is not DeploymentState.LIVE_CANARY:
        expected_vs_actual_diffs.append(
            {
                "subject": "current_deployment_state",
                "expected": DeploymentState.LIVE_CANARY.value,
                "actual": current_state.value,
            }
        )

    criteria_by_id = {criterion.criterion_id: criterion for criterion in request.exit_criteria}
    criteria_trace: list[dict[str, Any]] = []
    missing_criteria: list[str] = []
    failed_criteria: list[str] = []
    criteria_supported_by_admissible_evidence = False

    for criterion_id in _required_criteria(transition):
        criterion = criteria_by_id.get(criterion_id)
        if criterion is None:
            missing_criteria.append(criterion_id)
            expected_vs_actual_diffs.append(
                {
                    "subject": f"criterion.{criterion_id}",
                    "expected": "satisfied exit criterion",
                    "actual": "missing",
                }
            )
            criteria_trace.append(
                {
                    "criterion_id": criterion_id,
                    "passed": False,
                    "reason_code": "EXIT_CRITERION_MISSING",
                    "detail": "Required exit criterion is missing.",
                }
            )
            continue

        criterion_passed = criterion.satisfied
        reason_code = "EXIT_CRITERION_SATISFIED"
        if not criterion.satisfied:
            failed_criteria.append(criterion_id)
            criterion_passed = False
            reason_code = "EXIT_CRITERION_FAILED"
            expected_vs_actual_diffs.append(
                {
                    "subject": f"criterion.{criterion_id}",
                    "expected": "satisfied",
                    "actual": "failed",
                    "reference_id": criterion.reference_id,
                    "diagnostic": criterion.detail,
                }
            )

        for evidence_id in criterion.supporting_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                criterion_passed = False
                reason_code = "EXIT_CRITERION_SUPPORTING_EVIDENCE_MISSING"
                expected_vs_actual_diffs.append(
                    {
                        "subject": f"criterion.{criterion_id}.supporting_evidence",
                        "expected": evidence_id,
                        "actual": "missing",
                    }
                )
                continue
            if evidence_id not in admissible_evidence_ids:
                criterion_passed = False
                reason_code = "EXIT_CRITERION_SUPPORTING_EVIDENCE_NOT_ADMISSIBLE"
                expected_vs_actual_diffs.append(
                    {
                        "subject": f"criterion.{criterion_id}.supporting_evidence",
                        "expected": "promotion-admissible evidence",
                        "actual": evidence_id,
                    }
                )
            else:
                criteria_supported_by_admissible_evidence = True

        if not criterion_passed and criterion_id not in failed_criteria and criterion.satisfied:
            failed_criteria.append(criterion_id)

        criteria_trace.append(
            {
                "criterion_id": criterion_id,
                "passed": criterion_passed,
                "reason_code": reason_code,
                "reference_id": criterion.reference_id,
                "detail": criterion.detail,
                "supporting_evidence_ids": list(criterion.supporting_evidence_ids),
            }
        )

    if not criteria_supported_by_admissible_evidence:
        expected_vs_actual_diffs.append(
            {
                "subject": "transition_supporting_evidence",
                "expected": "at least one promotion-admissible evidence record",
                "actual": "none",
            }
        )

    decision_trace = [*evidence_trace, *criteria_trace]
    promotion_allowed = (
        stage_ready
        and not missing_criteria
        and not failed_criteria
        and not blocked_evidence_ids
        and criteria_supported_by_admissible_evidence
        and not any(diff["subject"] == "current_deployment_state" for diff in expected_vs_actual_diffs)
    )

    status = OperationalEvidenceGateStatus.PASS if promotion_allowed else OperationalEvidenceGateStatus.BLOCKED
    reason_code = "OPERATIONAL_EVIDENCE_GATE_PASSED"
    explanation = "Operational evidence and exit criteria support the requested promotion."
    remediation = "No action required."
    if not stage_ready:
        reason_code = "STAGE_POLICY_NOT_READY"
        explanation = "The upstream paper/shadow stage policy does not yet authorize this promotion path."
        remediation = "Complete the stage-policy prerequisites before requesting this transition."
    elif blocked_evidence_ids:
        reason_code = "OPERATIONAL_EVIDENCE_NOT_PROMOTION_ADMISSIBLE"
        explanation = "One or more operational evidence records are not admissible for promotion."
        remediation = "Seal, reconcile, sample-check, and policy-approve the evidence or change its class."
    elif missing_criteria or failed_criteria:
        if transition is PromotionTransition.PAPER_TO_SHADOW_LIVE:
            reason_code = "PAPER_EXIT_CRITERIA_INCOMPLETE"
        elif transition is PromotionTransition.SHADOW_LIVE_TO_LIVE_CANARY:
            reason_code = "SHADOW_EXIT_CRITERIA_INCOMPLETE"
        else:
            reason_code = "LIVE_CANARY_EXIT_CRITERIA_INCOMPLETE"
        explanation = "The requested promotion is blocked by missing or failed exit criteria."
        remediation = "Resolve the missing or failed criteria and rerun the gate."
    elif not criteria_supported_by_admissible_evidence:
        reason_code = "OPERATIONAL_EVIDENCE_NOT_PROMOTION_ADMISSIBLE"
        explanation = "No transition criterion is backed by admissible operational evidence."
        remediation = "Attach at least one admissible operational evidence record to the transition criteria."
    elif any(diff["subject"] == "current_deployment_state" for diff in expected_vs_actual_diffs):
        reason_code = "CURRENT_DEPLOYMENT_STATE_INVALID"
        explanation = "The current deployment state does not match the requested promotion transition."
        remediation = "Request the correct transition for the current deployment state."

    structured_logs = [
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "operational_evidence_gate.evidence_classified",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "admissible_evidence_ids": admissible_evidence_ids,
            "blocked_evidence_ids": blocked_evidence_ids,
            "timestamp": _utcnow(),
        },
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "operational_evidence_gate.criteria_evaluated",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "requested_transition": transition.value,
            "missing_criteria": missing_criteria,
            "failed_criteria": failed_criteria,
            "timestamp": _utcnow(),
        },
        {
            "schema_version": STRUCTURED_LOG_SCHEMA_VERSION,
            "event_type": "operational_evidence_gate.decision",
            "correlation_id": request.correlation_id,
            "run_id": run_id,
            "case_id": request.case_id,
            "requested_transition": transition.value,
            "current_deployment_state": current_state.value,
            "approved_target_state": target_state.value if promotion_allowed else None,
            "status": status.value,
            "reason_code": reason_code,
            "promotion_allowed": promotion_allowed,
            "timestamp": _utcnow(),
        },
    ]

    operator_reason_bundle = {
        "gate_summary": {
            "status": status.value,
            "reason_code": reason_code,
            "requested_transition": transition.value,
            "promotion_allowed": promotion_allowed,
            "approved_target_state": target_state.value if promotion_allowed else None,
        },
        "stage_policy": {
            "reason_code": request.stage_policy_report.reason_code,
            "paper_stage_complete": request.stage_policy_report.paper_stage_complete,
            "shadow_live_stage_complete": request.stage_policy_report.shadow_live_stage_complete,
            "live_activation_permitted": request.stage_policy_report.live_activation_permitted,
        },
        "operational_evidence": {
            "promotion_admissible_evidence_ids": admissible_evidence_ids,
            "blocked_evidence_ids": blocked_evidence_ids,
        },
        "criteria": {
            "missing": missing_criteria,
            "failed": failed_criteria,
        },
        "operator_notes": list(request.operator_reason_bundle),
    }

    artifacts = [
        _artifact_record(run_id, request.case_id, "gate_request", request.to_dict()),
        _artifact_record(run_id, request.case_id, "decision_trace", decision_trace),
        _artifact_record(run_id, request.case_id, "expected_vs_actual_diffs", expected_vs_actual_diffs),
        _artifact_record(run_id, request.case_id, "operator_reason_bundle", operator_reason_bundle),
        _artifact_record(run_id, request.case_id, "structured_logs", structured_logs),
    ]
    artifact_manifest = {
        "manifest_id": f"artifact_manifest_{run_id}",
        "generated_at_utc": _utcnow(),
        "retention_class": "promotion_gate_reviews",
        "contains_secrets": False,
        "redaction_policy": "opaque_identifiers_only",
        "artifacts": artifacts,
    }
    retained_artifact_ids = _unique_strings(
        [artifact["artifact_id"] for artifact in artifacts]
        + [record.evidence_id for record in request.operational_evidence]
        + [
            artifact_id
            for record in request.operational_evidence
            for artifact_id in record.artifact_ids
        ]
        + [criterion.reference_id for criterion in request.exit_criteria]
    )

    context = {
        "required_criteria": list(_required_criteria(transition)),
        "missing_criteria": missing_criteria,
        "failed_criteria": failed_criteria,
        "stage_ready": stage_ready,
        "stage_field": stage_field,
        "promotion_admissible_evidence_ids": admissible_evidence_ids,
        "blocked_evidence_ids": blocked_evidence_ids,
    }

    return OperationalEvidenceGateReport(
        schema_version=SUPPORTED_OPERATIONAL_EVIDENCE_GATE_SCHEMA_VERSION,
        case_id=request.case_id,
        requested_transition=transition.value,
        current_deployment_state=current_state.value,
        approved_target_state=target_state.value if promotion_allowed else None,
        status=status.value,
        reason_code=reason_code,
        promotion_allowed=promotion_allowed,
        promotion_admissible_evidence_ids=tuple(admissible_evidence_ids),
        blocked_evidence_ids=tuple(blocked_evidence_ids),
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
