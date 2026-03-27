"""Program-level pivot and termination triggers for honest continuation decisions."""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION = 1


@unique
class ProgramClosureTriggerId(str, Enum):
    EXECUTION_SYMBOL_TRADABILITY = "program_closure.execution_symbol_tradability"
    DE_MINIMIS_ECONOMICS = "program_closure.de_minimis_economics"
    OPERATIONAL_FRICTION = "program_closure.operational_friction"
    POSTURE_OVERREACH = "program_closure.posture_overreach"


@unique
class ProgramClosureDecision(str, Enum):
    CONTINUE = "continue"
    NARROW = "narrow"
    PIVOT = "pivot"
    TERMINATE = "terminate"


@unique
class ProgramClosureAction(str, Enum):
    CONTINUE_CURRENT_LANE = "continue_current_lane"
    NARROW_TO_INTRADAY_FLAT_ONLY = "narrow_to_intraday_flat_only"
    RAISE_MINIMUM_CAPITAL_POSTURE = "raise_minimum_capital_posture"
    SWITCH_PRIMARY_EXECUTION_SYMBOL = "switch_primary_execution_symbol"
    REMAIN_PAPER_ONLY = "remain_paper_only"
    TERMINATE_PROGRAM = "terminate_program"


TRIGGER_IDS = tuple(trigger.value for trigger in ProgramClosureTriggerId)
ALLOWED_ACTIONS = tuple(action.value for action in ProgramClosureAction)


def validate_program_closure_contract() -> list[str]:
    errors: list[str] = []
    if len(TRIGGER_IDS) != len(set(TRIGGER_IDS)):
        errors.append("program-closure trigger identifiers must be unique")
    if len(ALLOWED_ACTIONS) != len(set(ALLOWED_ACTIONS)):
        errors.append("program-closure action identifiers must be unique")
    if SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION < 1:
        errors.append("program-closure schema version must be positive")
    return errors


VALIDATION_ERRORS = validate_program_closure_contract()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _REPO_ROOT / "shared" / "fixtures" / "policy" / "program_closure_cases.json"
)


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must decode from valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _as_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name}: must be boolean")


def _as_float(value: object, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be numeric") from exc


def _as_non_negative_float(value: object, *, field_name: str) -> float:
    parsed = _as_float(value, field_name=field_name)
    if parsed < 0.0:
        raise ValueError(f"{field_name}: must be non-negative")
    return parsed


def _as_non_empty_string(value: object, *, field_name: str) -> str:
    parsed = str(value).strip()
    if not parsed:
        raise ValueError(f"{field_name}: must be non-empty")
    return parsed


def _as_tuple_of_strings(value: object, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list of strings")
    items = tuple(_as_non_empty_string(item, field_name=field_name) for item in value)
    return items


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=None)
def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        decoded = json.JSONDecoder().decode(handle.read())
    if not isinstance(decoded, dict):  # pragma: no cover - defensive
        raise ValueError(f"fixture at {path} must decode to an object")
    return decoded


def _find_case(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if str(case["case_id"]) == case_id:
            return dict(case)
    raise KeyError(f"unknown program-closure case id: {case_id}")


@dataclass(frozen=True)
class ProgramClosureRequest:
    case_id: str
    review_id: str
    strategy_family_id: str
    execution_symbol: str
    target_session_class: str
    approved_posture_id: str
    source_tradability_report_id: str
    source_economics_report_id: str
    source_runtime_report_id: str
    approved_live_capital_usd: float
    required_live_capital_usd: float
    conservative_monthly_net_usd: float
    de_minimis_monthly_net_threshold_usd: float
    monthly_operational_friction_cost_usd: float
    monthly_operator_hours: float
    max_monthly_operator_hours: float
    tradability_verified: bool
    intraday_only_viable: bool = False
    alternate_execution_symbol_available: bool = False
    alternate_execution_symbol: str | None = None
    paper_only_fallback_viable: bool = False
    higher_capital_posture_available: bool = False
    higher_capital_posture_usd: float | None = None
    retained_artifact_ids: tuple[str, ...] = ()
    operator_notes: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProgramClosureRequest":
        alternate_execution_symbol_available = _as_bool(
            payload.get("alternate_execution_symbol_available", False),
            field_name="alternate_execution_symbol_available",
        )
        alternate_execution_symbol = payload.get("alternate_execution_symbol")
        if alternate_execution_symbol in (None, ""):
            alternate_execution_symbol = None
        else:
            alternate_execution_symbol = _as_non_empty_string(
                alternate_execution_symbol,
                field_name="alternate_execution_symbol",
            )
        if alternate_execution_symbol and not alternate_execution_symbol_available:
            raise ValueError(
                "alternate_execution_symbol_available: must be true when alternate_execution_symbol is set"
            )

        higher_capital_posture_available = _as_bool(
            payload.get("higher_capital_posture_available", False),
            field_name="higher_capital_posture_available",
        )
        higher_capital_posture_usd = payload.get("higher_capital_posture_usd")
        if higher_capital_posture_usd in (None, ""):
            higher_capital_posture_usd = None
        else:
            higher_capital_posture_usd = _as_non_negative_float(
                higher_capital_posture_usd,
                field_name="higher_capital_posture_usd",
            )
        if higher_capital_posture_available and higher_capital_posture_usd is None:
            raise ValueError(
                "higher_capital_posture_usd: required when higher_capital_posture_available is true"
            )

        return cls(
            case_id=_as_non_empty_string(payload["case_id"], field_name="case_id"),
            review_id=_as_non_empty_string(payload["review_id"], field_name="review_id"),
            strategy_family_id=_as_non_empty_string(
                payload["strategy_family_id"],
                field_name="strategy_family_id",
            ),
            execution_symbol=_as_non_empty_string(
                payload["execution_symbol"],
                field_name="execution_symbol",
            ),
            target_session_class=_as_non_empty_string(
                payload["target_session_class"],
                field_name="target_session_class",
            ),
            approved_posture_id=_as_non_empty_string(
                payload["approved_posture_id"],
                field_name="approved_posture_id",
            ),
            source_tradability_report_id=_as_non_empty_string(
                payload["source_tradability_report_id"],
                field_name="source_tradability_report_id",
            ),
            source_economics_report_id=_as_non_empty_string(
                payload["source_economics_report_id"],
                field_name="source_economics_report_id",
            ),
            source_runtime_report_id=_as_non_empty_string(
                payload["source_runtime_report_id"],
                field_name="source_runtime_report_id",
            ),
            approved_live_capital_usd=_as_non_negative_float(
                payload["approved_live_capital_usd"],
                field_name="approved_live_capital_usd",
            ),
            required_live_capital_usd=_as_non_negative_float(
                payload["required_live_capital_usd"],
                field_name="required_live_capital_usd",
            ),
            conservative_monthly_net_usd=_as_float(
                payload["conservative_monthly_net_usd"],
                field_name="conservative_monthly_net_usd",
            ),
            de_minimis_monthly_net_threshold_usd=_as_non_negative_float(
                payload["de_minimis_monthly_net_threshold_usd"],
                field_name="de_minimis_monthly_net_threshold_usd",
            ),
            monthly_operational_friction_cost_usd=_as_non_negative_float(
                payload["monthly_operational_friction_cost_usd"],
                field_name="monthly_operational_friction_cost_usd",
            ),
            monthly_operator_hours=_as_non_negative_float(
                payload["monthly_operator_hours"],
                field_name="monthly_operator_hours",
            ),
            max_monthly_operator_hours=_as_non_negative_float(
                payload["max_monthly_operator_hours"],
                field_name="max_monthly_operator_hours",
            ),
            tradability_verified=_as_bool(
                payload["tradability_verified"],
                field_name="tradability_verified",
            ),
            intraday_only_viable=_as_bool(
                payload.get("intraday_only_viable", False),
                field_name="intraday_only_viable",
            ),
            alternate_execution_symbol_available=alternate_execution_symbol_available,
            alternate_execution_symbol=alternate_execution_symbol,
            paper_only_fallback_viable=_as_bool(
                payload.get("paper_only_fallback_viable", False),
                field_name="paper_only_fallback_viable",
            ),
            higher_capital_posture_available=higher_capital_posture_available,
            higher_capital_posture_usd=higher_capital_posture_usd,
            retained_artifact_ids=_as_tuple_of_strings(
                payload.get("retained_artifact_ids", ()),
                field_name="retained_artifact_ids",
            ),
            operator_notes=_as_tuple_of_strings(
                payload.get("operator_notes", ()),
                field_name="operator_notes",
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION,
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ProgramClosureRequest":
        return cls.from_dict(_decode_json_object(payload, label="program_closure_request"))


@dataclass(frozen=True)
class ProgramClosureTriggerReport:
    trigger_id: str
    trigger_name: str
    triggered: bool
    reason_code: str
    explanation: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProgramClosureTriggerReport":
        evidence = payload.get("evidence", {})
        if not isinstance(evidence, dict):
            raise ValueError("evidence: must be an object")
        return cls(
            trigger_id=_as_non_empty_string(payload["trigger_id"], field_name="trigger_id"),
            trigger_name=_as_non_empty_string(
                payload["trigger_name"],
                field_name="trigger_name",
            ),
            triggered=_as_bool(payload["triggered"], field_name="triggered"),
            reason_code=_as_non_empty_string(payload["reason_code"], field_name="reason_code"),
            explanation=_as_non_empty_string(payload["explanation"], field_name="explanation"),
            evidence=dict(evidence),
        )


@dataclass(frozen=True)
class ProgramClosureReport:
    case_id: str
    review_id: str
    decision: str
    recommended_action: str
    reason_code: str
    triggered_rule_ids: tuple[str, ...]
    trigger_reports: tuple[ProgramClosureTriggerReport, ...]
    source_evidence_ids: dict[str, str]
    retained_artifact_ids: tuple[str, ...]
    operator_rationale: str
    schema_version: int = SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "review_id": self.review_id,
            "decision": self.decision,
            "recommended_action": self.recommended_action,
            "reason_code": self.reason_code,
            "triggered_rule_ids": list(self.triggered_rule_ids),
            "trigger_reports": [report.to_dict() for report in self.trigger_reports],
            "source_evidence_ids": dict(self.source_evidence_ids),
            "retained_artifact_ids": list(self.retained_artifact_ids),
            "operator_rationale": self.operator_rationale,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProgramClosureReport":
        source_evidence_ids = payload.get("source_evidence_ids", {})
        if not isinstance(source_evidence_ids, dict):
            raise ValueError("source_evidence_ids: must be an object")
        return cls(
            case_id=_as_non_empty_string(payload["case_id"], field_name="case_id"),
            review_id=_as_non_empty_string(payload["review_id"], field_name="review_id"),
            decision=_as_non_empty_string(payload["decision"], field_name="decision"),
            recommended_action=_as_non_empty_string(
                payload["recommended_action"],
                field_name="recommended_action",
            ),
            reason_code=_as_non_empty_string(payload["reason_code"], field_name="reason_code"),
            triggered_rule_ids=_as_tuple_of_strings(
                payload.get("triggered_rule_ids", ()),
                field_name="triggered_rule_ids",
            ),
            trigger_reports=tuple(
                ProgramClosureTriggerReport.from_dict(dict(item))
                for item in payload.get("trigger_reports", ())
            ),
            source_evidence_ids={
                str(key): _as_non_empty_string(value, field_name="source_evidence_ids")
                for key, value in source_evidence_ids.items()
            },
            retained_artifact_ids=_as_tuple_of_strings(
                payload.get("retained_artifact_ids", ()),
                field_name="retained_artifact_ids",
            ),
            operator_rationale=_as_non_empty_string(
                payload["operator_rationale"],
                field_name="operator_rationale",
            ),
            schema_version=int(
                payload.get(
                    "schema_version",
                    SUPPORTED_PROGRAM_CLOSURE_SCHEMA_VERSION,
                )
            ),
            timestamp=_as_non_empty_string(payload["timestamp"], field_name="timestamp"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ProgramClosureReport":
        return cls.from_dict(_decode_json_object(payload, label="program_closure_report"))


def _tradability_report(request: ProgramClosureRequest) -> ProgramClosureTriggerReport:
    triggered = not request.tradability_verified
    explanation = (
        "Execution-symbol tradability remains acceptable for the approved session class."
        if not triggered
        else "The tradability study does not support reliable live operation on the current execution symbol."
    )
    return ProgramClosureTriggerReport(
        trigger_id=ProgramClosureTriggerId.EXECUTION_SYMBOL_TRADABILITY.value,
        trigger_name="execution_symbol_tradability",
        triggered=triggered,
        reason_code=(
            "PROGRAM_CLOSURE_TRADABILITY_CLEAR"
            if not triggered
            else "PROGRAM_CLOSURE_TRADABILITY_BLOCKED"
        ),
        explanation=explanation,
        evidence={
            "execution_symbol": request.execution_symbol,
            "target_session_class": request.target_session_class,
            "tradability_verified": request.tradability_verified,
            "intraday_only_viable": request.intraday_only_viable,
            "alternate_execution_symbol_available": request.alternate_execution_symbol_available,
            "alternate_execution_symbol": request.alternate_execution_symbol,
        },
    )


def _economics_report(request: ProgramClosureRequest) -> ProgramClosureTriggerReport:
    triggered = (
        request.conservative_monthly_net_usd
        < request.de_minimis_monthly_net_threshold_usd
    )
    explanation = (
        "Conservative monthly net dollars remain above the approved de minimis floor."
        if not triggered
        else "Conservative fully loaded net dollars remain de minimis across the approved live posture."
    )
    return ProgramClosureTriggerReport(
        trigger_id=ProgramClosureTriggerId.DE_MINIMIS_ECONOMICS.value,
        trigger_name="de_minimis_economics",
        triggered=triggered,
        reason_code=(
            "PROGRAM_CLOSURE_ECONOMICS_CLEAR"
            if not triggered
            else "PROGRAM_CLOSURE_ECONOMICS_DE_MINIMIS"
        ),
        explanation=explanation,
        evidence={
            "conservative_monthly_net_usd": request.conservative_monthly_net_usd,
            "de_minimis_monthly_net_threshold_usd": (
                request.de_minimis_monthly_net_threshold_usd
            ),
            "higher_capital_posture_available": request.higher_capital_posture_available,
            "higher_capital_posture_usd": request.higher_capital_posture_usd,
        },
    )


def _operational_friction_report(
    request: ProgramClosureRequest,
) -> ProgramClosureTriggerReport:
    triggered = request.monthly_operational_friction_cost_usd >= max(
        request.conservative_monthly_net_usd,
        0.0,
    )
    explanation = (
        "Operational friction remains meaningfully smaller than the available edge."
        if not triggered
        else "Broker/data operational friction now dominates the available conservative edge."
    )
    return ProgramClosureTriggerReport(
        trigger_id=ProgramClosureTriggerId.OPERATIONAL_FRICTION.value,
        trigger_name="operational_friction",
        triggered=triggered,
        reason_code=(
            "PROGRAM_CLOSURE_FRICTION_CLEAR"
            if not triggered
            else "PROGRAM_CLOSURE_FRICTION_DOMINATES_EDGE"
        ),
        explanation=explanation,
        evidence={
            "monthly_operational_friction_cost_usd": (
                request.monthly_operational_friction_cost_usd
            ),
            "conservative_monthly_net_usd": request.conservative_monthly_net_usd,
            "paper_only_fallback_viable": request.paper_only_fallback_viable,
        },
    )


def _posture_overreach_report(request: ProgramClosureRequest) -> ProgramClosureTriggerReport:
    capital_overreach = (
        request.required_live_capital_usd > request.approved_live_capital_usd
    )
    operator_time_overreach = (
        request.monthly_operator_hours > request.max_monthly_operator_hours
    )
    triggered = capital_overreach or operator_time_overreach
    explanation = (
        "Operator-time and capital posture remain inside the approved live envelope."
        if not triggered
        else "The live lane now requires more operator time or capital than the approved posture allows."
    )
    return ProgramClosureTriggerReport(
        trigger_id=ProgramClosureTriggerId.POSTURE_OVERREACH.value,
        trigger_name="posture_overreach",
        triggered=triggered,
        reason_code=(
            "PROGRAM_CLOSURE_POSTURE_CLEAR"
            if not triggered
            else "PROGRAM_CLOSURE_POSTURE_EXCEEDED"
        ),
        explanation=explanation,
        evidence={
            "approved_live_capital_usd": request.approved_live_capital_usd,
            "required_live_capital_usd": request.required_live_capital_usd,
            "monthly_operator_hours": request.monthly_operator_hours,
            "max_monthly_operator_hours": request.max_monthly_operator_hours,
            "capital_overreach": capital_overreach,
            "operator_time_overreach": operator_time_overreach,
        },
    )


def _continue_report(
    request: ProgramClosureRequest,
    trigger_reports: tuple[ProgramClosureTriggerReport, ...],
) -> ProgramClosureReport:
    return ProgramClosureReport(
        case_id=request.case_id,
        review_id=request.review_id,
        decision=ProgramClosureDecision.CONTINUE.value,
        recommended_action=ProgramClosureAction.CONTINUE_CURRENT_LANE.value,
        reason_code="PROGRAM_CLOSURE_CONTINUE",
        triggered_rule_ids=(),
        trigger_reports=trigger_reports,
        source_evidence_ids={
            "tradability_report_id": request.source_tradability_report_id,
            "economics_report_id": request.source_economics_report_id,
            "runtime_report_id": request.source_runtime_report_id,
        },
        retained_artifact_ids=request.retained_artifact_ids,
        operator_rationale=(
            "The live lane remains tradable, economically non-de-minimis, operationally supportable, "
            "and inside the approved operator-time and capital posture."
        ),
    )


def _decision_report(
    *,
    request: ProgramClosureRequest,
    decision: ProgramClosureDecision,
    action: ProgramClosureAction,
    reason_code: str,
    operator_rationale: str,
    trigger_reports: tuple[ProgramClosureTriggerReport, ...],
) -> ProgramClosureReport:
    triggered_rule_ids = tuple(
        report.trigger_id for report in trigger_reports if report.triggered
    )
    return ProgramClosureReport(
        case_id=request.case_id,
        review_id=request.review_id,
        decision=decision.value,
        recommended_action=action.value,
        reason_code=reason_code,
        triggered_rule_ids=triggered_rule_ids,
        trigger_reports=trigger_reports,
        source_evidence_ids={
            "tradability_report_id": request.source_tradability_report_id,
            "economics_report_id": request.source_economics_report_id,
            "runtime_report_id": request.source_runtime_report_id,
        },
        retained_artifact_ids=request.retained_artifact_ids,
        operator_rationale=operator_rationale,
    )


def evaluate_program_closure(request: ProgramClosureRequest) -> ProgramClosureReport:
    trigger_reports = (
        _tradability_report(request),
        _economics_report(request),
        _operational_friction_report(request),
        _posture_overreach_report(request),
    )
    triggered_map = {report.trigger_id: report.triggered for report in trigger_reports}

    if not any(triggered_map.values()):
        return _continue_report(request, trigger_reports)

    if (
        triggered_map[ProgramClosureTriggerId.EXECUTION_SYMBOL_TRADABILITY.value]
        and triggered_map[ProgramClosureTriggerId.DE_MINIMIS_ECONOMICS.value]
    ):
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.TERMINATE,
            action=ProgramClosureAction.TERMINATE_PROGRAM,
            reason_code="PROGRAM_CLOSURE_TERMINATE_TRADABILITY_AND_ECONOMICS",
            operator_rationale=(
                "The current execution symbol is not reliably tradable and the approved live posture "
                "remains economically de minimis, so the governed outcome is termination rather than "
                "quiet continuation."
            ),
            trigger_reports=trigger_reports,
        )

    if triggered_map[ProgramClosureTriggerId.EXECUTION_SYMBOL_TRADABILITY.value]:
        if request.intraday_only_viable:
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.NARROW,
                action=ProgramClosureAction.NARROW_TO_INTRADAY_FLAT_ONLY,
                reason_code="PROGRAM_CLOSURE_TRADABILITY_NARROW",
                operator_rationale=(
                    "Tradability is not reliable across the approved session class, but the evidence still "
                    "supports a narrower intraday-flat lane."
                ),
                trigger_reports=trigger_reports,
            )
        if request.alternate_execution_symbol_available:
            alternate = request.alternate_execution_symbol or "an alternate execution symbol"
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.PIVOT,
                action=ProgramClosureAction.SWITCH_PRIMARY_EXECUTION_SYMBOL,
                reason_code="PROGRAM_CLOSURE_TRADABILITY_SWITCH_SYMBOL",
                operator_rationale=(
                    f"The current execution symbol is not reliably tradable, so the governed pivot is to "
                    f"switch the primary execution symbol to {alternate} rather than continuing silently."
                ),
                trigger_reports=trigger_reports,
            )
        if request.paper_only_fallback_viable:
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.PIVOT,
                action=ProgramClosureAction.REMAIN_PAPER_ONLY,
                reason_code="PROGRAM_CLOSURE_TRADABILITY_PAPER_ONLY",
                operator_rationale=(
                    "The current live execution symbol is not reliably tradable, so the governed outcome is "
                    "to remain paper-only until a better symbol or lane is approved."
                ),
                trigger_reports=trigger_reports,
            )
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.TERMINATE,
            action=ProgramClosureAction.TERMINATE_PROGRAM,
            reason_code="PROGRAM_CLOSURE_TRADABILITY_TERMINATE",
            operator_rationale=(
                "The tradability study blocks the live lane and no narrower or alternate governed pivot is "
                "available, so the correct decision is termination."
            ),
            trigger_reports=trigger_reports,
        )

    if triggered_map[ProgramClosureTriggerId.DE_MINIMIS_ECONOMICS.value]:
        if request.higher_capital_posture_available:
            target = request.higher_capital_posture_usd
            capital_note = f" to ${target:,.0f}" if target is not None else ""
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.PIVOT,
                action=ProgramClosureAction.RAISE_MINIMUM_CAPITAL_POSTURE,
                reason_code="PROGRAM_CLOSURE_ECONOMICS_RAISE_CAPITAL",
                operator_rationale=(
                    "The approved live posture remains economically de minimis, so the only governed pivot "
                    f"is to raise the minimum capital posture{capital_note} before reconsidering live operation."
                ),
                trigger_reports=trigger_reports,
            )
        if request.paper_only_fallback_viable:
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.PIVOT,
                action=ProgramClosureAction.REMAIN_PAPER_ONLY,
                reason_code="PROGRAM_CLOSURE_ECONOMICS_PAPER_ONLY",
                operator_rationale=(
                    "The approved live posture remains economically de minimis, so the governed fallback is "
                    "to remain paper-only rather than forcing a live lane that does not clear the dollar bar."
                ),
                trigger_reports=trigger_reports,
            )
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.TERMINATE,
            action=ProgramClosureAction.TERMINATE_PROGRAM,
            reason_code="PROGRAM_CLOSURE_ECONOMICS_TERMINATE",
            operator_rationale=(
                "The live lane remains economically de minimis and no governed capital or paper-only pivot is "
                "available, so the correct decision is termination."
            ),
            trigger_reports=trigger_reports,
        )

    if triggered_map[ProgramClosureTriggerId.OPERATIONAL_FRICTION.value]:
        if request.paper_only_fallback_viable:
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.PIVOT,
                action=ProgramClosureAction.REMAIN_PAPER_ONLY,
                reason_code="PROGRAM_CLOSURE_FRICTION_PAPER_ONLY",
                operator_rationale=(
                    "Broker/data operational friction is consuming the available edge, so the governed pivot "
                    "is to remain paper-only until the lane can be operated more honestly."
                ),
                trigger_reports=trigger_reports,
            )
        if request.intraday_only_viable:
            return _decision_report(
                request=request,
                decision=ProgramClosureDecision.NARROW,
                action=ProgramClosureAction.NARROW_TO_INTRADAY_FLAT_ONLY,
                reason_code="PROGRAM_CLOSURE_FRICTION_NARROW",
                operator_rationale=(
                    "Operational friction dominates the current edge, but the evidence still supports a tighter "
                    "intraday-flat lane with fewer operational touch points."
                ),
                trigger_reports=trigger_reports,
            )
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.TERMINATE,
            action=ProgramClosureAction.TERMINATE_PROGRAM,
            reason_code="PROGRAM_CLOSURE_FRICTION_TERMINATE",
            operator_rationale=(
                "Operational friction dominates the available edge and no governed narrower or paper-only pivot "
                "is available, so the correct outcome is termination."
            ),
            trigger_reports=trigger_reports,
        )

    if request.higher_capital_posture_available:
        target = request.higher_capital_posture_usd
        capital_note = f" to ${target:,.0f}" if target is not None else ""
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.PIVOT,
            action=ProgramClosureAction.RAISE_MINIMUM_CAPITAL_POSTURE,
            reason_code="PROGRAM_CLOSURE_POSTURE_RAISE_CAPITAL",
            operator_rationale=(
                "The live lane now exceeds the approved operator-time or capital posture, so the governed pivot "
                f"is to raise the minimum capital posture{capital_note} before continuing."
            ),
            trigger_reports=trigger_reports,
        )

    if request.paper_only_fallback_viable:
        return _decision_report(
            request=request,
            decision=ProgramClosureDecision.PIVOT,
            action=ProgramClosureAction.REMAIN_PAPER_ONLY,
            reason_code="PROGRAM_CLOSURE_POSTURE_PAPER_ONLY",
            operator_rationale=(
                "The lane exceeds the approved operator-time or capital posture, so the governed fallback is "
                "to remain paper-only instead of stretching the live mandate."
            ),
            trigger_reports=trigger_reports,
        )

    return _decision_report(
        request=request,
        decision=ProgramClosureDecision.TERMINATE,
        action=ProgramClosureAction.TERMINATE_PROGRAM,
        reason_code="PROGRAM_CLOSURE_POSTURE_TERMINATE",
        operator_rationale=(
            "The lane exceeds the approved operator-time or capital posture and no governed pivot is available, "
            "so the correct decision is termination."
        ),
        trigger_reports=trigger_reports,
    )


def load_program_closure_fixture() -> dict[str, Any]:
    return _load_json(_FIXTURE_PATH)


def evaluate_program_closure_case(case_id: str) -> ProgramClosureReport:
    fixture = load_program_closure_fixture()
    case = _find_case(list(fixture["cases"]), case_id)
    payload = _deep_merge(
        dict(fixture["shared_request_defaults"]),
        dict(case.get("overrides", {})),
    )
    payload["case_id"] = case["case_id"]
    payload.setdefault("review_id", f"program_closure_{case_id}")
    return evaluate_program_closure(ProgramClosureRequest.from_dict(payload))
