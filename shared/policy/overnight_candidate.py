"""Overnight candidate-class qualification contract."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.account_fit_gate import AccountFitReport, AccountFitStatus
from shared.policy.operating_envelope import OPERATING_ENVELOPE_ACTIONS, SessionConditionedRiskProfile
from shared.policy.product_profiles import OperatingPosture

SUPPORTED_OVERNIGHT_CANDIDATE_SCHEMA_VERSION = 1
REQUIRED_OVERNIGHT_EVIDENCE_LANES = ("paper", "shadow_live")
REQUIRED_LANE_SCENARIO_TYPES = (
    "overnight_hold",
    "overnight_exit",
    "restart_while_holding",
)
REQUIRED_GLOBAL_SCENARIO_TYPES = ("broker_disconnect", "data_degradation")
REQUIRED_CARRY_RESTRICTION_TRIGGERS = (
    "maintenance_window",
    "severe_data_degradation",
    "reconciliation_uncertainty",
    "broker_disconnect",
)
REQUIRED_MARGIN_BOUNDARIES = (
    "session_close",
    "maintenance_window",
    "next_session_open",
)
STRICT_CARRY_ACTIONS = (
    "no_new_overnight_carry",
    "entry_suppression",
    "exit_only",
    "forced_flatten",
)
STRICT_DEGRADATION_ACTIONS = ("entry_suppression", "exit_only", "forced_flatten")
STRICT_BROKER_ACTIONS = ("exit_only", "forced_flatten")
REQUIRED_SESSION_RULES = (
    "overnight",
    "maintenance_adjacent",
    "degraded_data",
)


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _as_non_negative_float(value: object, *, field_name: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{field_name}: must be non-negative")
    return parsed


@unique
class OvernightCandidateStatus(str, Enum):
    QUALIFIED = "qualified"
    BLOCKED = "blocked"
    INVALID = "invalid"
    STALE = "stale"


@unique
class OvernightCandidateClass(str, Enum):
    NONE = "none"
    STANDARD = "standard"
    STRICT = "strict"


@unique
class OvernightEvidenceLane(str, Enum):
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"


@unique
class OvernightScenarioType(str, Enum):
    OVERNIGHT_HOLD = "overnight_hold"
    OVERNIGHT_EXIT = "overnight_exit"
    RESTART_WHILE_HOLDING = "restart_while_holding"
    BROKER_DISCONNECT = "broker_disconnect"
    DATA_DEGRADATION = "data_degradation"


@unique
class OvernightCarryRestrictionTrigger(str, Enum):
    MAINTENANCE_WINDOW = "maintenance_window"
    SEVERE_DATA_DEGRADATION = "severe_data_degradation"
    RECONCILIATION_UNCERTAINTY = "reconciliation_uncertainty"
    BROKER_DISCONNECT = "broker_disconnect"


@unique
class MarginThresholdBasis(str, Enum):
    INITIAL_MARGIN = "initial_margin_fraction"
    MAINTENANCE_MARGIN = "maintenance_margin_fraction"


@unique
class SessionBoundary(str, Enum):
    SESSION_CLOSE = "session_close"
    MAINTENANCE_WINDOW = "maintenance_window"
    NEXT_SESSION_OPEN = "next_session_open"


@dataclass(frozen=True)
class OvernightEvidenceRecord:
    lane: str
    scenario_type: str
    passed: bool
    artifact_ids: tuple[str, ...]
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OvernightEvidenceRecord":
        return cls(
            lane=str(payload["lane"]),
            scenario_type=str(payload["scenario_type"]),
            passed=bool(payload["passed"]),
            artifact_ids=tuple(str(item) for item in payload.get("artifact_ids", ())),
            diagnostic=str(payload["diagnostic"]),
        )


@dataclass(frozen=True)
class OvernightCarryRestrictionRule:
    trigger_id: str
    action: str
    blocks_new_carry: bool
    diagnostic: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OvernightCarryRestrictionRule":
        return cls(
            trigger_id=str(payload["trigger_id"]),
            action=str(payload["action"]),
            blocks_new_carry=bool(payload["blocks_new_carry"]),
            diagnostic=str(payload["diagnostic"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class SessionBoundaryMarginCheck:
    boundary: str
    threshold_basis: str
    required_margin_usd: float
    buffer_usd: float | None = None
    artifact_id: str | None = None
    diagnostic: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return _jsonable(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionBoundaryMarginCheck":
        return cls(
            boundary=str(payload["boundary"]),
            threshold_basis=str(payload["threshold_basis"]),
            required_margin_usd=_as_non_negative_float(
                payload["required_margin_usd"],
                field_name="required_margin_usd",
            ),
            buffer_usd=(
                _as_non_negative_float(payload["buffer_usd"], field_name="buffer_usd")
                if payload.get("buffer_usd") is not None
                else None
            ),
            artifact_id=(
                str(payload["artifact_id"])
                if payload.get("artifact_id") not in (None, "")
                else None
            ),
            diagnostic=str(payload.get("diagnostic", "")),
        )


@dataclass(frozen=True)
class OvernightCandidateRequest:
    case_id: str
    candidate_id: str
    allow_overnight: bool
    overnight_candidate_class: str
    requested_operating_posture: str
    account_fit_report: AccountFitReport
    session_conditioned_risk_profile: SessionConditionedRiskProfile
    evidence_records: tuple[OvernightEvidenceRecord, ...]
    carry_restriction_rules: tuple[OvernightCarryRestrictionRule, ...]
    session_boundary_margin_checks: tuple[SessionBoundaryMarginCheck, ...]
    evaluated_at_utc: str | None = None
    schema_version: int = SUPPORTED_OVERNIGHT_CANDIDATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "allow_overnight": self.allow_overnight,
            "overnight_candidate_class": self.overnight_candidate_class,
            "requested_operating_posture": self.requested_operating_posture,
            "account_fit_report": self.account_fit_report.to_dict(),
            "session_conditioned_risk_profile": self.session_conditioned_risk_profile.to_dict(),
            "evidence_records": [record.to_dict() for record in self.evidence_records],
            "carry_restriction_rules": [rule.to_dict() for rule in self.carry_restriction_rules],
            "session_boundary_margin_checks": [
                check.to_dict() for check in self.session_boundary_margin_checks
            ],
            "evaluated_at_utc": self.evaluated_at_utc,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OvernightCandidateRequest":
        return cls(
            case_id=str(payload["case_id"]),
            candidate_id=str(payload["candidate_id"]),
            allow_overnight=bool(payload["allow_overnight"]),
            overnight_candidate_class=str(payload["overnight_candidate_class"]),
            requested_operating_posture=str(payload["requested_operating_posture"]),
            account_fit_report=AccountFitReport.from_dict(dict(payload["account_fit_report"])),
            session_conditioned_risk_profile=SessionConditionedRiskProfile.from_dict(
                dict(payload["session_conditioned_risk_profile"])
            ),
            evidence_records=tuple(
                OvernightEvidenceRecord.from_dict(dict(item))
                for item in payload.get("evidence_records", ())
            ),
            carry_restriction_rules=tuple(
                OvernightCarryRestrictionRule.from_dict(dict(item))
                for item in payload.get("carry_restriction_rules", ())
            ),
            session_boundary_margin_checks=tuple(
                SessionBoundaryMarginCheck.from_dict(dict(item))
                for item in payload.get("session_boundary_margin_checks", ())
            ),
            evaluated_at_utc=(
                str(payload["evaluated_at_utc"])
                if payload.get("evaluated_at_utc") not in (None, "")
                else None
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_OVERNIGHT_CANDIDATE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OvernightCandidateRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="overnight_candidate_request")
        )


@dataclass(frozen=True)
class OvernightCandidateCheckResult:
    check_id: str
    title: str
    passed: bool
    reason_code: str | None
    diagnostic: str
    context: dict[str, Any] = field(default_factory=dict)
    artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OvernightCandidateCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            title=str(payload["title"]),
            passed=bool(payload["passed"]),
            reason_code=(
                str(payload["reason_code"])
                if payload.get("reason_code") not in (None, "")
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
            context=dict(payload.get("context", {})),
            artifact_ids=tuple(str(item) for item in payload.get("artifact_ids", ())),
        )


@dataclass(frozen=True)
class SessionBoundaryMarginResult:
    boundary: str
    threshold_basis: str
    required_margin_usd: float
    buffer_usd: float
    actual_fraction: float
    threshold_fraction: float
    passed: bool
    artifact_id: str | None
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SessionBoundaryMarginResult":
        return cls(
            boundary=str(payload["boundary"]),
            threshold_basis=str(payload["threshold_basis"]),
            required_margin_usd=float(payload["required_margin_usd"]),
            buffer_usd=float(payload["buffer_usd"]),
            actual_fraction=float(payload["actual_fraction"]),
            threshold_fraction=float(payload["threshold_fraction"]),
            passed=bool(payload["passed"]),
            artifact_id=(
                str(payload["artifact_id"])
                if payload.get("artifact_id") not in (None, "")
                else None
            ),
            diagnostic=str(payload["diagnostic"]),
        )


@dataclass(frozen=True)
class OvernightCandidateReport:
    case_id: str
    candidate_id: str
    status: str
    reason_code: str
    overnight_candidate_class: str
    allow_overnight: bool
    requested_operating_posture: str
    account_fit_case_id: str
    account_fit_status: str
    session_conditioned_risk_profile_id: str
    carry_restriction_triggers: tuple[str, ...]
    retained_artifact_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    check_results: tuple[OvernightCandidateCheckResult, ...]
    boundary_results: tuple[SessionBoundaryMarginResult, ...]
    explanation: str
    remediation: str
    evaluated_at_utc: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "overnight_candidate_class": self.overnight_candidate_class,
            "allow_overnight": self.allow_overnight,
            "requested_operating_posture": self.requested_operating_posture,
            "account_fit_case_id": self.account_fit_case_id,
            "account_fit_status": self.account_fit_status,
            "session_conditioned_risk_profile_id": self.session_conditioned_risk_profile_id,
            "carry_restriction_triggers": list(self.carry_restriction_triggers),
            "retained_artifact_ids": list(self.retained_artifact_ids),
            "failed_check_ids": list(self.failed_check_ids),
            "check_results": [result.to_dict() for result in self.check_results],
            "boundary_results": [result.to_dict() for result in self.boundary_results],
            "explanation": self.explanation,
            "remediation": self.remediation,
            "evaluated_at_utc": self.evaluated_at_utc,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OvernightCandidateReport":
        return cls(
            case_id=str(payload["case_id"]),
            candidate_id=str(payload["candidate_id"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            overnight_candidate_class=str(payload["overnight_candidate_class"]),
            allow_overnight=bool(payload["allow_overnight"]),
            requested_operating_posture=str(payload["requested_operating_posture"]),
            account_fit_case_id=str(payload["account_fit_case_id"]),
            account_fit_status=str(payload["account_fit_status"]),
            session_conditioned_risk_profile_id=str(
                payload["session_conditioned_risk_profile_id"]
            ),
            carry_restriction_triggers=tuple(
                str(item) for item in payload.get("carry_restriction_triggers", ())
            ),
            retained_artifact_ids=tuple(
                str(item) for item in payload.get("retained_artifact_ids", ())
            ),
            failed_check_ids=tuple(str(item) for item in payload.get("failed_check_ids", ())),
            check_results=tuple(
                OvernightCandidateCheckResult.from_dict(dict(item))
                for item in payload.get("check_results", ())
            ),
            boundary_results=tuple(
                SessionBoundaryMarginResult.from_dict(dict(item))
                for item in payload.get("boundary_results", ())
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            evaluated_at_utc=str(payload["evaluated_at_utc"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "OvernightCandidateReport":
        return cls.from_dict(
            _decode_json_object(payload, label="overnight_candidate_report")
        )


def validate_overnight_candidate_contract() -> list[str]:
    errors: list[str] = []
    checks = (
        REQUIRED_OVERNIGHT_EVIDENCE_LANES,
        REQUIRED_LANE_SCENARIO_TYPES,
        REQUIRED_GLOBAL_SCENARIO_TYPES,
        REQUIRED_CARRY_RESTRICTION_TRIGGERS,
        REQUIRED_MARGIN_BOUNDARIES,
    )
    for values in checks:
        if len(values) != len(set(values)):
            errors.append("overnight candidate contract identifiers must be unique")
            break
    if SUPPORTED_OVERNIGHT_CANDIDATE_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    if not set(STRICT_CARRY_ACTIONS).issubset(set(OPERATING_ENVELOPE_ACTIONS)):
        errors.append("strict carry actions must be valid operating-envelope actions")
    if not set(STRICT_DEGRADATION_ACTIONS).issubset(set(OPERATING_ENVELOPE_ACTIONS)):
        errors.append("strict degradation actions must be valid operating-envelope actions")
    if not set(STRICT_BROKER_ACTIONS).issubset(set(OPERATING_ENVELOPE_ACTIONS)):
        errors.append("strict broker actions must be valid operating-envelope actions")
    return errors


VALIDATION_ERRORS = validate_overnight_candidate_contract()


def _invalid_report(
    request: OvernightCandidateRequest,
    *,
    reason_code: str,
    explanation: str,
    remediation: str,
) -> OvernightCandidateReport:
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()
    return OvernightCandidateReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=OvernightCandidateStatus.INVALID.value,
        reason_code=reason_code,
        overnight_candidate_class=request.overnight_candidate_class,
        allow_overnight=request.allow_overnight,
        requested_operating_posture=request.requested_operating_posture,
        account_fit_case_id=request.account_fit_report.case_id,
        account_fit_status=request.account_fit_report.status,
        session_conditioned_risk_profile_id=request.session_conditioned_risk_profile.profile_id,
        carry_restriction_triggers=tuple(
            rule.trigger_id for rule in request.carry_restriction_rules
        ),
        retained_artifact_ids=tuple(request.account_fit_report.artifact_ids),
        failed_check_ids=(),
        check_results=(),
        boundary_results=(),
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )


def _stale_report(
    request: OvernightCandidateRequest,
    *,
    reason_code: str,
    explanation: str,
    remediation: str,
) -> OvernightCandidateReport:
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()
    return OvernightCandidateReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=OvernightCandidateStatus.STALE.value,
        reason_code=reason_code,
        overnight_candidate_class=request.overnight_candidate_class,
        allow_overnight=request.allow_overnight,
        requested_operating_posture=request.requested_operating_posture,
        account_fit_case_id=request.account_fit_report.case_id,
        account_fit_status=request.account_fit_report.status,
        session_conditioned_risk_profile_id=request.session_conditioned_risk_profile.profile_id,
        carry_restriction_triggers=tuple(
            rule.trigger_id for rule in request.carry_restriction_rules
        ),
        retained_artifact_ids=tuple(request.account_fit_report.artifact_ids),
        failed_check_ids=(),
        check_results=(),
        boundary_results=(),
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )


def _check_result(
    *,
    check_id: str,
    title: str,
    passed: bool,
    reason_code: str | None,
    diagnostic: str,
    context: dict[str, Any] | None = None,
    artifact_ids: tuple[str, ...] = (),
) -> OvernightCandidateCheckResult:
    return OvernightCandidateCheckResult(
        check_id=check_id,
        title=title,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        context=context or {},
        artifact_ids=artifact_ids,
    )


def _actions_block_new_carry(actions: tuple[str, ...]) -> bool:
    return any(action in STRICT_CARRY_ACTIONS for action in actions)


def _validate_request(request: OvernightCandidateRequest) -> list[str]:
    errors: list[str] = []
    if request.schema_version != SUPPORTED_OVERNIGHT_CANDIDATE_SCHEMA_VERSION:
        errors.append("schema_version")
    if request.overnight_candidate_class not in {
        candidate_class.value for candidate_class in OvernightCandidateClass
    }:
        errors.append("overnight_candidate_class")
    if request.requested_operating_posture not in {
        posture.value for posture in OperatingPosture
    }:
        errors.append("requested_operating_posture")
    if request.account_fit_report.candidate_id != request.candidate_id:
        errors.append("account_fit_report.candidate_id")
    if (
        request.account_fit_report.requested_operating_posture
        != request.requested_operating_posture
    ):
        errors.append("account_fit_report.requested_operating_posture")
    if not request.session_conditioned_risk_profile.profile_id:
        errors.append("session_conditioned_risk_profile.profile_id")
    for index, evidence in enumerate(request.evidence_records):
        if evidence.lane not in {lane.value for lane in OvernightEvidenceLane}:
            errors.append(f"evidence_records[{index}].lane")
        if evidence.scenario_type not in {scenario.value for scenario in OvernightScenarioType}:
            errors.append(f"evidence_records[{index}].scenario_type")
    for index, rule in enumerate(request.carry_restriction_rules):
        if rule.trigger_id not in {
            trigger.value for trigger in OvernightCarryRestrictionTrigger
        }:
            errors.append(f"carry_restriction_rules[{index}].trigger_id")
        if rule.action not in OPERATING_ENVELOPE_ACTIONS:
            errors.append(f"carry_restriction_rules[{index}].action")
    for index, check in enumerate(request.session_boundary_margin_checks):
        if check.boundary not in {boundary.value for boundary in SessionBoundary}:
            errors.append(f"session_boundary_margin_checks[{index}].boundary")
        if check.threshold_basis not in {
            basis.value for basis in MarginThresholdBasis
        }:
            errors.append(f"session_boundary_margin_checks[{index}].threshold_basis")
    return errors


def _declaration_check(
    request: OvernightCandidateRequest,
) -> OvernightCandidateCheckResult:
    passes = (
        request.allow_overnight
        and request.overnight_candidate_class == OvernightCandidateClass.STRICT.value
        and request.requested_operating_posture == OperatingPosture.OVERNIGHT_STRICT.value
        and request.account_fit_report.overnight_requested
    )
    if passes:
        return _check_result(
            check_id="declaration",
            title="Explicit strict overnight declaration",
            passed=True,
            reason_code=None,
            diagnostic=(
                "The candidate explicitly requests overnight carrying through the strict "
                "overnight class and posture."
            ),
        )

    if not request.allow_overnight:
        reason_code = "OVERNIGHT_CANDIDATE_DECLARATION_REQUIRED"
        diagnostic = "Overnight carrying must be declared explicitly with allow_overnight=true."
    elif request.overnight_candidate_class != OvernightCandidateClass.STRICT.value:
        reason_code = "OVERNIGHT_CANDIDATE_STRICT_CLASS_REQUIRED"
        diagnostic = (
            "Overnight carrying is only promotable under the strict overnight candidate class."
        )
    elif request.requested_operating_posture != OperatingPosture.OVERNIGHT_STRICT.value:
        reason_code = "OVERNIGHT_CANDIDATE_STRICT_POSTURE_REQUIRED"
        diagnostic = (
            "Overnight carrying requires the strict overnight operating posture."
        )
    else:
        reason_code = "OVERNIGHT_CANDIDATE_ACCOUNT_FIT_REQUEST_NOT_OVERNIGHT"
        diagnostic = "The linked account-fit report did not evaluate an overnight request."

    return _check_result(
        check_id="declaration",
        title="Explicit strict overnight declaration",
        passed=False,
        reason_code=reason_code,
        diagnostic=diagnostic,
        context={
            "allow_overnight": request.allow_overnight,
            "overnight_candidate_class": request.overnight_candidate_class,
            "requested_operating_posture": request.requested_operating_posture,
            "account_fit_overnight_requested": request.account_fit_report.overnight_requested,
        },
    )


def _account_fit_check(request: OvernightCandidateRequest) -> OvernightCandidateCheckResult:
    report = request.account_fit_report
    gap_check = next(
        (
            result
            for result in report.check_results
            if result.check_id == "overnight_gap_stress_fraction"
        ),
        None,
    )
    passes = (
        report.status == AccountFitStatus.PASS.value
        and report.overnight_requested
        and report.requested_operating_posture == OperatingPosture.OVERNIGHT_STRICT.value
        and gap_check is not None
        and gap_check.applied
        and gap_check.passed
    )
    if passes:
        return _check_result(
            check_id="account_fit",
            title="Overnight-specific account fit",
            passed=True,
            reason_code=None,
            diagnostic=(
                "The actual execution contract passed overnight-specific account-fit, "
                "including the overnight gap-stress budget."
            ),
            artifact_ids=tuple(report.artifact_ids),
        )

    return _check_result(
        check_id="account_fit",
        title="Overnight-specific account fit",
        passed=False,
        reason_code="OVERNIGHT_CANDIDATE_ACCOUNT_FIT_NOT_PASSED",
        diagnostic=(
            "The linked account-fit report did not pass the overnight execution-contract "
            "and gap-stress checks."
        ),
        context={
            "account_fit_status": report.status,
            "account_fit_reason_code": report.reason_code,
            "failed_check_ids": list(report.failed_check_ids),
        },
        artifact_ids=tuple(report.artifact_ids),
    )


def _session_profile_check(
    request: OvernightCandidateRequest,
) -> OvernightCandidateCheckResult:
    rules_by_class = {
        rule.session_class: rule for rule in request.session_conditioned_risk_profile.rules
    }
    missing_rules = [
        session_class
        for session_class in REQUIRED_SESSION_RULES
        if session_class not in rules_by_class
    ]
    issues: list[str] = []
    if missing_rules:
        issues.append(f"missing rules for {', '.join(missing_rules)}")

    overnight_rule = rules_by_class.get("overnight")
    if overnight_rule is not None:
        if overnight_rule.required_operating_posture != OperatingPosture.OVERNIGHT_STRICT.value:
            issues.append("overnight rule does not require the strict overnight posture")
        if not overnight_rule.overnight_carry_allowed:
            issues.append("overnight rule does not allow overnight carry")

    for session_class in ("maintenance_adjacent", "degraded_data"):
        rule = rules_by_class.get(session_class)
        if rule is None:
            continue
        if not _actions_block_new_carry(rule.actions):
            issues.append(f"{session_class} rule does not block new overnight carry")
        if rule.overnight_carry_allowed:
            issues.append(f"{session_class} rule still allows overnight carry")

    passed = not issues
    return _check_result(
        check_id="session_profile",
        title="Session-conditioned overnight profile",
        passed=passed,
        reason_code=(
            None
            if passed
            else "OVERNIGHT_CANDIDATE_SESSION_PROFILE_INSUFFICIENT"
        ),
        diagnostic=(
            "The session-conditioned profile enforces strict overnight posture and carry "
            "suppression in the maintenance-adjacent and degraded-data classes."
            if passed
            else "The session-conditioned profile is missing one or more overnight-specific protections."
        ),
        context={
            "issues": issues,
            "profile_id": request.session_conditioned_risk_profile.profile_id,
        },
    )


def _evidence_check(request: OvernightCandidateRequest) -> OvernightCandidateCheckResult:
    available = {
        (record.lane, record.scenario_type)
        for record in request.evidence_records
        if record.passed and record.artifact_ids
    }
    missing: list[str] = []
    for lane in REQUIRED_OVERNIGHT_EVIDENCE_LANES:
        for scenario_type in REQUIRED_LANE_SCENARIO_TYPES:
            if (lane, scenario_type) not in available:
                missing.append(f"{lane}:{scenario_type}")
    for scenario_type in REQUIRED_GLOBAL_SCENARIO_TYPES:
        if not any(
            record.scenario_type == scenario_type
            and record.passed
            and record.artifact_ids
            for record in request.evidence_records
        ):
            missing.append(scenario_type)
    artifact_ids = tuple(
        sorted(
            {
                artifact_id
                for record in request.evidence_records
                for artifact_id in record.artifact_ids
            }
        )
    )
    passed = not missing
    return _check_result(
        check_id="evidence",
        title="Paper and shadow overnight evidence",
        passed=passed,
        reason_code=(
            None if passed else "OVERNIGHT_CANDIDATE_EVIDENCE_INCOMPLETE"
        ),
        diagnostic=(
            "Paper and shadow evidence cover overnight hold, exit, restart, and degradation scenarios."
            if passed
            else "The overnight evidence set is missing one or more required scenarios."
        ),
        context={"missing": missing},
        artifact_ids=artifact_ids,
    )


def _carry_restriction_check(
    request: OvernightCandidateRequest,
) -> OvernightCandidateCheckResult:
    rules_by_trigger = {
        rule.trigger_id: rule for rule in request.carry_restriction_rules
    }
    missing = [
        trigger
        for trigger in REQUIRED_CARRY_RESTRICTION_TRIGGERS
        if trigger not in rules_by_trigger
    ]
    issues: list[str] = []

    maintenance_rule = rules_by_trigger.get(
        OvernightCarryRestrictionTrigger.MAINTENANCE_WINDOW.value
    )
    if maintenance_rule is not None and (
        not maintenance_rule.blocks_new_carry
        or maintenance_rule.action not in STRICT_CARRY_ACTIONS
    ):
        issues.append("maintenance_window rule is not a strict no-new-carry restriction")

    for trigger in (
        OvernightCarryRestrictionTrigger.SEVERE_DATA_DEGRADATION.value,
        OvernightCarryRestrictionTrigger.RECONCILIATION_UNCERTAINTY.value,
    ):
        rule = rules_by_trigger.get(trigger)
        if rule is None:
            continue
        if not rule.blocks_new_carry or rule.action not in STRICT_DEGRADATION_ACTIONS:
            issues.append(f"{trigger} rule is not strict enough")

    broker_rule = rules_by_trigger.get(
        OvernightCarryRestrictionTrigger.BROKER_DISCONNECT.value
    )
    if broker_rule is not None and (
        not broker_rule.blocks_new_carry
        or broker_rule.action not in STRICT_BROKER_ACTIONS
    ):
        issues.append("broker_disconnect rule is not strict enough")

    passed = not missing and not issues
    return _check_result(
        check_id="carry_restrictions",
        title="No-new-carry windows and degradation responses",
        passed=passed,
        reason_code=(
            None
            if passed
            else (
                "OVERNIGHT_CANDIDATE_CARRY_RESTRICTION_MISSING"
                if missing
                else "OVERNIGHT_CANDIDATE_DEGRADATION_RESPONSE_INSUFFICIENT"
            )
        ),
        diagnostic=(
            "Maintenance, degradation, reconciliation, and broker impairment all have "
            "first-class overnight carry restrictions."
            if passed
            else "One or more overnight carry restrictions or degradation responses are missing or too weak."
        ),
        context={"missing": missing, "issues": issues},
    )


def _boundary_results(
    request: OvernightCandidateRequest,
) -> tuple[SessionBoundaryMarginResult, ...]:
    thresholds = request.account_fit_report.thresholds
    if thresholds is None:
        return ()

    approved_equity = float(thresholds.approved_starting_equity_usd)
    results: list[SessionBoundaryMarginResult] = []
    for check in request.session_boundary_margin_checks:
        buffer_usd = (
            request.account_fit_report.round_turn_fees_usd
            if check.buffer_usd is None
            else check.buffer_usd
        )
        if check.threshold_basis == MarginThresholdBasis.INITIAL_MARGIN.value:
            threshold_fraction = thresholds.max_initial_margin_fraction
        else:
            threshold_fraction = thresholds.max_maintenance_margin_fraction
        actual_fraction = (check.required_margin_usd + buffer_usd) / approved_equity
        passed = actual_fraction <= threshold_fraction
        diagnostic = check.diagnostic or (
            f"{check.boundary} margin fraction is {actual_fraction:.4f} against a "
            f"{threshold_fraction:.4f} limit."
        )
        results.append(
            SessionBoundaryMarginResult(
                boundary=check.boundary,
                threshold_basis=check.threshold_basis,
                required_margin_usd=check.required_margin_usd,
                buffer_usd=buffer_usd,
                actual_fraction=actual_fraction,
                threshold_fraction=threshold_fraction,
                passed=passed,
                artifact_id=check.artifact_id,
                diagnostic=diagnostic,
            )
        )
    return tuple(results)


def _margin_transition_check(
    request: OvernightCandidateRequest,
    boundary_results: tuple[SessionBoundaryMarginResult, ...],
) -> OvernightCandidateCheckResult:
    present_boundaries = {result.boundary for result in boundary_results}
    missing = [
        boundary
        for boundary in REQUIRED_MARGIN_BOUNDARIES
        if boundary not in present_boundaries
    ]
    failing = [
        result.boundary
        for result in boundary_results
        if not result.passed
    ]
    passed = not missing and not failing
    return _check_result(
        check_id="session_boundary_margin",
        title="Session-boundary margin transitions",
        passed=passed,
        reason_code=(
            None
            if passed
            else (
                "OVERNIGHT_CANDIDATE_SESSION_BOUNDARY_MARGIN_MISSING"
                if missing
                else "OVERNIGHT_CANDIDATE_SESSION_BOUNDARY_MARGIN_EXCEEDED"
            )
        ),
        diagnostic=(
            "Session-close, maintenance-window, and next-open margin transitions stay inside the approved overnight thresholds."
            if passed
            else "One or more session-boundary margin transitions are missing or exceed the approved account thresholds."
        ),
        context={"missing": missing, "failing": failing},
        artifact_ids=tuple(
            result.artifact_id
            for result in boundary_results
            if result.artifact_id is not None
        ),
    )


def evaluate_overnight_candidate(
    request: OvernightCandidateRequest,
) -> OvernightCandidateReport:
    validation_errors = _validate_request(request)
    if validation_errors:
        return _invalid_report(
            request,
            reason_code="OVERNIGHT_CANDIDATE_REQUEST_INVALID",
            explanation=(
                "The overnight candidate request failed validation: "
                f"{validation_errors}."
            ),
            remediation=(
                "Repair the request payload, linked account-fit report, or nested "
                "overnight structures before re-running the qualification."
            ),
        )

    if request.account_fit_report.status == AccountFitStatus.STALE.value:
        return _stale_report(
            request,
            reason_code="OVERNIGHT_CANDIDATE_ACCOUNT_FIT_STALE",
            explanation=(
                "Overnight qualification stopped because the linked account-fit report "
                "is stale."
            ),
            remediation=(
                "Refresh the margin or fee artifacts, regenerate account-fit, and then "
                "re-run overnight qualification."
            ),
        )

    if request.account_fit_report.status == AccountFitStatus.INVALID.value:
        return _invalid_report(
            request,
            reason_code="OVERNIGHT_CANDIDATE_ACCOUNT_FIT_INVALID",
            explanation=(
                "Overnight qualification cannot proceed because the linked account-fit "
                "report is invalid."
            ),
            remediation="Repair the account-fit request and regenerate the report.",
        )

    declaration_check = _declaration_check(request)
    account_fit_check = _account_fit_check(request)
    session_profile_check = _session_profile_check(request)
    evidence_check = _evidence_check(request)
    carry_restriction_check = _carry_restriction_check(request)
    boundary_results = _boundary_results(request)
    margin_transition_check = _margin_transition_check(request, boundary_results)

    check_results = (
        declaration_check,
        account_fit_check,
        session_profile_check,
        evidence_check,
        carry_restriction_check,
        margin_transition_check,
    )
    failed_check_ids = tuple(
        result.check_id for result in check_results if not result.passed
    )
    retained_artifact_ids = tuple(
        sorted(
            {
                *request.account_fit_report.artifact_ids,
                *(
                    artifact_id
                    for result in check_results
                    for artifact_id in result.artifact_ids
                ),
            }
        )
    )
    evaluated_at_utc = request.evaluated_at_utc or _utcnow()

    if not failed_check_ids:
        status = OvernightCandidateStatus.QUALIFIED.value
        reason_code = "OVERNIGHT_CANDIDATE_QUALIFIED"
        explanation = (
            "The candidate satisfies the strict overnight class with explicit declaration, "
            "overnight-specific account-fit, retained evidence, strict carry restrictions, "
            "and passing session-boundary margin transitions."
        )
        remediation = "No remediation required."
    else:
        status = OvernightCandidateStatus.BLOCKED.value
        if len(failed_check_ids) == 1:
            failed_check = next(
                result for result in check_results if result.check_id == failed_check_ids[0]
            )
            reason_code = str(failed_check.reason_code)
            remediation = failed_check.diagnostic
        else:
            reason_code = "OVERNIGHT_CANDIDATE_MULTIPLE_REQUIREMENTS_UNSATISFIED"
            remediation = (
                "Repair the failing declaration, evidence, restriction, and margin "
                "requirements before promoting an overnight class."
            )
        explanation = (
            "The candidate does not yet qualify for the strict overnight class because "
            f"the following checks failed: {', '.join(failed_check_ids)}."
        )

    return OvernightCandidateReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        status=status,
        reason_code=reason_code,
        overnight_candidate_class=request.overnight_candidate_class,
        allow_overnight=request.allow_overnight,
        requested_operating_posture=request.requested_operating_posture,
        account_fit_case_id=request.account_fit_report.case_id,
        account_fit_status=request.account_fit_report.status,
        session_conditioned_risk_profile_id=request.session_conditioned_risk_profile.profile_id,
        carry_restriction_triggers=tuple(
            rule.trigger_id for rule in request.carry_restriction_rules
        ),
        retained_artifact_ids=retained_artifact_ids,
        failed_check_ids=failed_check_ids,
        check_results=check_results,
        boundary_results=boundary_results,
        explanation=explanation,
        remediation=remediation,
        evaluated_at_utc=evaluated_at_utc,
    )
