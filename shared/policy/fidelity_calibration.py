"""Fidelity calibration contract for the lower-frequency live lane.

Plan v3.8 section 6.3 requires fidelity calibration before a strategy class
becomes promotable. Section 6.4 constrains the first live lane to one-minute-
or-slower, bar-based strategies that do not depend on order-book, queue-
position, sub-minute, or premium-depth edges.

This module encodes those requirements as a machine-readable contract with
stable reason codes, explicit excluded strategy classes, and session-
conditioned calibration evidence.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

LIVE_LANE_MIN_DECISION_INTERVAL_SECONDS = 60
LIVE_LANE_DECISION_BASES: tuple[str, ...] = ("bar_close", "one_bar_late")

_LIVE_LANE_REASON_CODES = {
    "frequency": "FIDELITY_LIVE_LANE_FREQUENCY",
    "bar_type": "FIDELITY_LIVE_LANE_BAR_TYPE",
    "order_book_imbalance": "FIDELITY_LIVE_LANE_ORDER_BOOK",
    "queue_position": "FIDELITY_LIVE_LANE_QUEUE_POSITION",
    "sub_minute_dependency": "FIDELITY_LIVE_LANE_SUB_MINUTE",
    "premium_depth": "FIDELITY_LIVE_LANE_PREMIUM_DEPTH",
}


@unique
class FidelityCalibrationStatus(str, Enum):
    APPROVED = "pass"
    VIOLATION = "violation"
    INVALID = "invalid"


@unique
class FidelityCheckID(str, Enum):
    REQUEST_SHAPE = "FC00"
    BAR_SUFFICIENCY = "FC01"
    SLIPPAGE_REALISM = "FC02"
    PASSIVE_ASSUMPTIONS = "FC03"
    LIVE_LANE = "FC04"
    SESSION_SURFACES = "FC05"


@dataclass(frozen=True)
class StrategyClassExclusion:
    """Explicitly recorded strategy classes that remain outside the live lane."""

    strategy_class_id: str
    violated_constraint: str
    reason_code: str
    diagnostic: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EXPLICITLY_EXCLUDED_STRATEGY_CLASSES: tuple[StrategyClassExclusion, ...] = (
    StrategyClassExclusion(
        strategy_class_id="sub_minute_reactive_scalping",
        violated_constraint="frequency",
        reason_code="FIDELITY_EXCLUDED_FREQUENCY",
        diagnostic="Sub-minute strategies remain research-only in the first live lane.",
    ),
    StrategyClassExclusion(
        strategy_class_id="tick_reactive_intrabar",
        violated_constraint="bar_type",
        reason_code="FIDELITY_EXCLUDED_BAR_TYPE",
        diagnostic="Intrabar or tick-reactive strategies are outside the approved bar-based lane.",
    ),
    StrategyClassExclusion(
        strategy_class_id="order_book_imbalance_reversion",
        violated_constraint="order_book_imbalance",
        reason_code="FIDELITY_EXCLUDED_ORDER_BOOK",
        diagnostic="Order-book imbalance dependencies are excluded from the first live lane.",
    ),
    StrategyClassExclusion(
        strategy_class_id="queue_position_capture",
        violated_constraint="queue_position",
        reason_code="FIDELITY_EXCLUDED_QUEUE_POSITION",
        diagnostic="Queue-position edge strategies are excluded from the first live lane.",
    ),
    StrategyClassExclusion(
        strategy_class_id="sub_minute_market_making",
        violated_constraint="sub_minute_dependency",
        reason_code="FIDELITY_EXCLUDED_SUB_MINUTE",
        diagnostic="Sub-minute market-making remains outside the first live lane.",
    ),
    StrategyClassExclusion(
        strategy_class_id="premium_depth_microstructure",
        violated_constraint="premium_depth",
        reason_code="FIDELITY_EXCLUDED_PREMIUM_DEPTH",
        diagnostic="Strategies that need premium live depth data are excluded from v1.",
    ),
)


def list_explicitly_excluded_strategy_classes() -> tuple[StrategyClassExclusion, ...]:
    """Return the explicit list of strategy classes excluded from the live lane."""

    return EXPLICITLY_EXCLUDED_STRATEGY_CLASSES


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        loaded = json.JSONDecoder().decode(payload)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return loaded


@dataclass(frozen=True)
class SessionCalibrationEvidence:
    """Session-conditioned evidence for fidelity calibration."""

    session_class: str
    bar_interval_seconds: int
    bar_sufficiency_passed: bool
    realistic_slippage_bps: float
    max_allowed_slippage_bps: float
    passive_assumption_credible: bool
    supporting_data_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SessionCalibrationEvidence:
        return cls(
            session_class=str(payload["session_class"]),
            bar_interval_seconds=int(payload["bar_interval_seconds"]),
            bar_sufficiency_passed=bool(payload["bar_sufficiency_passed"]),
            realistic_slippage_bps=float(payload["realistic_slippage_bps"]),
            max_allowed_slippage_bps=float(payload["max_allowed_slippage_bps"]),
            passive_assumption_credible=bool(payload["passive_assumption_credible"]),
            supporting_data_refs=tuple(str(item) for item in payload.get("supporting_data_refs", ())),
        )


@dataclass(frozen=True)
class FidelityCalibrationRequest:
    """Candidate-level request for live-lane fidelity calibration."""

    case_id: str
    candidate_id: str
    strategy_class_id: str
    decision_interval_seconds: int
    decision_basis: str
    requires_passive_fill_assumption: bool
    depends_on_order_book_imbalance: bool
    requires_queue_position_edge: bool
    exhibits_sub_minute_market_making: bool
    requires_premium_depth_data: bool
    material_session_liquidity_difference: bool
    session_calibrations: tuple[SessionCalibrationEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_calibrations"] = [
            session.to_dict() for session in self.session_calibrations
        ]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FidelityCalibrationRequest:
        return cls(
            case_id=str(payload["case_id"]),
            candidate_id=str(payload["candidate_id"]),
            strategy_class_id=str(payload["strategy_class_id"]),
            decision_interval_seconds=int(payload["decision_interval_seconds"]),
            decision_basis=str(payload["decision_basis"]),
            requires_passive_fill_assumption=bool(payload["requires_passive_fill_assumption"]),
            depends_on_order_book_imbalance=bool(payload["depends_on_order_book_imbalance"]),
            requires_queue_position_edge=bool(payload["requires_queue_position_edge"]),
            exhibits_sub_minute_market_making=bool(payload["exhibits_sub_minute_market_making"]),
            requires_premium_depth_data=bool(payload["requires_premium_depth_data"]),
            material_session_liquidity_difference=bool(
                payload["material_session_liquidity_difference"]
            ),
            session_calibrations=tuple(
                SessionCalibrationEvidence.from_dict(item)
                for item in payload["session_calibrations"]
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> FidelityCalibrationRequest:
        return cls.from_dict(
            _decode_json_object(payload, label="fidelity_calibration_request")
        )


@dataclass(frozen=True)
class FidelityCheckResult:
    """Structured result for one fidelity calibration check."""

    check_id: str
    check_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any] = field(default_factory=dict)
    session_class: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class FidelityCalibrationReport:
    """Machine-readable fidelity calibration decision report."""

    case_id: str
    candidate_id: str
    strategy_class_id: str
    status: str
    live_lane_eligible: bool
    reason_code: str
    decision_trace: list[dict[str, Any]]
    failed_check_ids: list[str]
    known_excluded_strategy_class_ids: list[str]
    matched_excluded_strategy_class_ids: list[str]
    session_classes: list[str]
    supporting_data_refs: list[str]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def _find_matching_exclusions(strategy_class_id: str) -> list[str]:
    return [
        exclusion.strategy_class_id
        for exclusion in EXPLICITLY_EXCLUDED_STRATEGY_CLASSES
        if exclusion.strategy_class_id == strategy_class_id
    ]


def _validate_request(request: FidelityCalibrationRequest) -> list[str]:
    errors: list[str] = []

    if request.decision_interval_seconds <= 0:
        errors.append("decision_interval_seconds must be positive")
    if not request.decision_basis:
        errors.append("decision_basis must be non-empty")
    if not request.session_calibrations:
        errors.append("at least one session_calibration is required")

    session_classes = [session.session_class for session in request.session_calibrations]
    if len(session_classes) != len(set(session_classes)):
        errors.append("session_class values must be unique per request")
    if request.material_session_liquidity_difference and len(set(session_classes)) < 2:
        errors.append(
            "material session liquidity differences require separate session surfaces"
        )

    for session in request.session_calibrations:
        if session.bar_interval_seconds <= 0:
            errors.append(
                f"session_class={session.session_class}: bar_interval_seconds must be positive"
            )
        if session.max_allowed_slippage_bps <= 0:
            errors.append(
                f"session_class={session.session_class}: max_allowed_slippage_bps must be positive"
            )
        if not session.supporting_data_refs:
            errors.append(
                f"session_class={session.session_class}: supporting_data_refs must be provided"
            )

    return errors


def check_lower_frequency_live_lane(
    request: FidelityCalibrationRequest,
) -> FidelityCheckResult:
    """Check the candidate against the explicitly approved live-lane boundaries."""

    failures: list[str] = []
    if request.decision_interval_seconds < LIVE_LANE_MIN_DECISION_INTERVAL_SECONDS:
        failures.append("frequency")
    if request.decision_basis not in LIVE_LANE_DECISION_BASES:
        failures.append("bar_type")
    if request.depends_on_order_book_imbalance:
        failures.append("order_book_imbalance")
    if request.requires_queue_position_edge:
        failures.append("queue_position")
    if request.exhibits_sub_minute_market_making:
        failures.append("sub_minute_dependency")
    if request.requires_premium_depth_data:
        failures.append("premium_depth")

    matched_excluded_strategy_class_ids = _find_matching_exclusions(request.strategy_class_id)
    passed = not failures
    reason_code = (
        "FIDELITY_FC04_LIVE_LANE"
        if passed
        else (
            _LIVE_LANE_REASON_CODES[failures[0]]
            if len(failures) == 1
            else "FIDELITY_LIVE_LANE_MULTIPLE"
        )
    )

    diagnostic = (
        "Candidate stays inside the one-minute-or-slower, bar-based live lane."
        if passed
        else (
            "Candidate is outside the approved lower-frequency live lane due to "
            f"{failures}."
        )
    )
    if matched_excluded_strategy_class_ids:
        diagnostic = (
            f"{diagnostic} Explicitly recorded excluded classes matched: "
            f"{matched_excluded_strategy_class_ids}."
        )

    return FidelityCheckResult(
        check_id=FidelityCheckID.LIVE_LANE.value,
        check_name="lower_frequency_live_lane",
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence={
            "decision_interval_seconds": request.decision_interval_seconds,
            "decision_basis": request.decision_basis,
            "depends_on_order_book_imbalance": request.depends_on_order_book_imbalance,
            "requires_queue_position_edge": request.requires_queue_position_edge,
            "exhibits_sub_minute_market_making": request.exhibits_sub_minute_market_making,
            "requires_premium_depth_data": request.requires_premium_depth_data,
            "failed_constraints": failures,
            "matched_excluded_strategy_class_ids": matched_excluded_strategy_class_ids,
        },
    )


def check_session_surface_separation(
    request: FidelityCalibrationRequest,
) -> FidelityCheckResult:
    """Ensure session-conditioned liquidity differences use separate surfaces."""

    session_classes = [session.session_class for session in request.session_calibrations]
    passed = (
        not request.material_session_liquidity_difference or len(set(session_classes)) >= 2
    )
    return FidelityCheckResult(
        check_id=FidelityCheckID.SESSION_SURFACES.value,
        check_name="session_surface_separation",
        passed=passed,
        reason_code="FIDELITY_FC05_SESSION_SURFACES",
        diagnostic=(
            "Session-conditioned liquidity differences are backed by separate surfaces."
            if passed
            else "Calibration relies on a blended session surface where separate surfaces are required."
        ),
        evidence={
            "material_session_liquidity_difference": request.material_session_liquidity_difference,
            "session_classes": session_classes,
        },
    )


def check_bar_sufficiency(session: SessionCalibrationEvidence) -> FidelityCheckResult:
    """Check whether the chosen bar resolution is admissible for the session."""

    return FidelityCheckResult(
        check_id=FidelityCheckID.BAR_SUFFICIENCY.value,
        check_name="bar_sufficiency",
        passed=session.bar_sufficiency_passed,
        reason_code="FIDELITY_FC01_BAR_SUFFICIENCY",
        diagnostic=(
            f"Bar sufficiency is documented for session class {session.session_class}."
            if session.bar_sufficiency_passed
            else f"Bar sufficiency is not supported for session class {session.session_class}."
        ),
        evidence={
            "bar_interval_seconds": session.bar_interval_seconds,
            "supporting_data_refs": session.supporting_data_refs,
        },
        session_class=session.session_class,
    )


def check_slippage_realism(session: SessionCalibrationEvidence) -> FidelityCheckResult:
    """Check that slippage assumptions are bounded by session-conditioned evidence."""

    passed = session.realistic_slippage_bps <= session.max_allowed_slippage_bps
    return FidelityCheckResult(
        check_id=FidelityCheckID.SLIPPAGE_REALISM.value,
        check_name="slippage_realism",
        passed=passed,
        reason_code="FIDELITY_FC02_SLIPPAGE_REALISM",
        diagnostic=(
            f"Slippage evidence is within the allowed range for {session.session_class}."
            if passed
            else (
                f"Slippage evidence exceeds the allowed range for {session.session_class}: "
                f"{session.realistic_slippage_bps} > {session.max_allowed_slippage_bps} bps."
            )
        ),
        evidence={
            "realistic_slippage_bps": session.realistic_slippage_bps,
            "max_allowed_slippage_bps": session.max_allowed_slippage_bps,
            "supporting_data_refs": session.supporting_data_refs,
        },
        session_class=session.session_class,
    )


def check_passive_assumption_credibility(
    session: SessionCalibrationEvidence,
    *,
    requires_passive_fill_assumption: bool,
) -> FidelityCheckResult:
    """Check whether passive assumptions are credible when the strategy depends on them."""

    passed = session.passive_assumption_credible or not requires_passive_fill_assumption
    if passed and session.passive_assumption_credible:
        diagnostic = (
            f"Passive assumptions are credible for session class {session.session_class}."
        )
    elif passed:
        diagnostic = (
            f"Passive assumptions are not credible for session class {session.session_class}, "
            "but the candidate does not depend on passive fills."
        )
    else:
        diagnostic = (
            f"Passive assumptions are not credible for session class {session.session_class}, "
            "and the candidate depends on passive fills."
        )

    return FidelityCheckResult(
        check_id=FidelityCheckID.PASSIVE_ASSUMPTIONS.value,
        check_name="passive_assumption_credibility",
        passed=passed,
        reason_code="FIDELITY_FC03_PASSIVE_ASSUMPTIONS",
        diagnostic=diagnostic,
        evidence={
            "passive_assumption_credible": session.passive_assumption_credible,
            "requires_passive_fill_assumption": requires_passive_fill_assumption,
            "supporting_data_refs": session.supporting_data_refs,
        },
        session_class=session.session_class,
    )


def _aggregate_supporting_refs(
    request: FidelityCalibrationRequest,
) -> list[str]:
    refs = {
        ref
        for session in request.session_calibrations
        for ref in session.supporting_data_refs
    }
    return sorted(refs)


def _build_explanation(
    request: FidelityCalibrationRequest,
    *,
    status: FidelityCalibrationStatus,
    failed_checks: list[FidelityCheckResult],
) -> str:
    session_classes = [session.session_class for session in request.session_calibrations]
    if status == FidelityCalibrationStatus.APPROVED:
        return (
            "Candidate cleared the lower-frequency live lane with session-conditioned "
            f"fidelity evidence for {session_classes}."
        )

    failed_summary = [
        {
            "check_name": check.check_name,
            "reason_code": check.reason_code,
            "session_class": check.session_class,
        }
        for check in failed_checks
    ]
    return (
        "Candidate did not clear fidelity calibration. "
        f"Failed checks: {failed_summary}."
    )


def _build_remediation(failed_checks: list[FidelityCheckResult]) -> str:
    if not failed_checks:
        return "Maintain session-conditioned evidence and re-run the same contract on refresh."

    failed_codes = {check.reason_code for check in failed_checks}
    steps: list[str] = []
    if any(code.startswith("FIDELITY_LIVE_LANE") for code in failed_codes):
        steps.append(
            "Keep the strategy research-only or redesign it to stay bar-based, one-minute-or-slower, "
            "and independent of order-book, queue-position, and premium-depth edges."
        )
    if "FIDELITY_FC01_BAR_SUFFICIENCY" in failed_codes:
        steps.append(
            "Re-run bar-sufficiency studies with a slower bar cadence or narrow the strategy class."
        )
    if "FIDELITY_FC02_SLIPPAGE_REALISM" in failed_codes:
        steps.append(
            "Refresh session-conditioned slippage studies and update the allowed ranges."
        )
    if "FIDELITY_FC03_PASSIVE_ASSUMPTIONS" in failed_codes:
        steps.append(
            "Remove passive-fill dependence or produce evidence that passive assumptions are credible."
        )
    if "FIDELITY_FC05_SESSION_SURFACES" in failed_codes:
        steps.append(
            "Split blended calibration claims into separate regular and overnight session surfaces."
        )

    return " ".join(steps) or "Repair the invalid request shape and re-run calibration."


def evaluate_fidelity_calibration(
    request: FidelityCalibrationRequest,
) -> FidelityCalibrationReport:
    """Evaluate a candidate against the lower-frequency live-lane contract."""

    known_excluded_strategy_class_ids = [
        exclusion.strategy_class_id for exclusion in EXPLICITLY_EXCLUDED_STRATEGY_CLASSES
    ]
    matched_excluded_strategy_class_ids = _find_matching_exclusions(request.strategy_class_id)

    validation_errors = _validate_request(request)
    if validation_errors:
        invalid_check = FidelityCheckResult(
            check_id=FidelityCheckID.REQUEST_SHAPE.value,
            check_name="request_shape",
            passed=False,
            reason_code="FIDELITY_INVALID_REQUEST",
            diagnostic="Request shape is invalid for fidelity calibration.",
            evidence={"validation_errors": validation_errors},
        )
        return FidelityCalibrationReport(
            case_id=request.case_id,
            candidate_id=request.candidate_id,
            strategy_class_id=request.strategy_class_id,
            status=FidelityCalibrationStatus.INVALID.value,
            live_lane_eligible=False,
            reason_code="FIDELITY_INVALID_REQUEST",
            decision_trace=[invalid_check.to_dict()],
            failed_check_ids=[invalid_check.check_id],
            known_excluded_strategy_class_ids=known_excluded_strategy_class_ids,
            matched_excluded_strategy_class_ids=matched_excluded_strategy_class_ids,
            session_classes=[session.session_class for session in request.session_calibrations],
            supporting_data_refs=_aggregate_supporting_refs(request),
            explanation="Request is missing the minimum evidence needed for fidelity calibration.",
            remediation="Repair the request shape and provide session-conditioned supporting data references.",
        )

    decision_trace: list[FidelityCheckResult] = [
        check_lower_frequency_live_lane(request),
        check_session_surface_separation(request),
    ]
    for session in request.session_calibrations:
        decision_trace.extend(
            [
                check_bar_sufficiency(session),
                check_slippage_realism(session),
                check_passive_assumption_credibility(
                    session,
                    requires_passive_fill_assumption=request.requires_passive_fill_assumption,
                ),
            ]
        )

    failed_checks = [check for check in decision_trace if not check.passed]
    status = (
        FidelityCalibrationStatus.APPROVED
        if not failed_checks
        else FidelityCalibrationStatus.VIOLATION
    )
    reason_code = (
        "FIDELITY_CALIBRATION_PASSED"
        if status == FidelityCalibrationStatus.APPROVED
        else "FIDELITY_CALIBRATION_BLOCKED"
    )

    return FidelityCalibrationReport(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        strategy_class_id=request.strategy_class_id,
        status=status.value,
        live_lane_eligible=status == FidelityCalibrationStatus.APPROVED,
        reason_code=reason_code,
        decision_trace=[check.to_dict() for check in decision_trace],
        failed_check_ids=[check.check_id for check in failed_checks],
        known_excluded_strategy_class_ids=known_excluded_strategy_class_ids,
        matched_excluded_strategy_class_ids=matched_excluded_strategy_class_ids,
        session_classes=[session.session_class for session in request.session_calibrations],
        supporting_data_refs=_aggregate_supporting_refs(request),
        explanation=_build_explanation(
            request,
            status=status,
            failed_checks=failed_checks,
        ),
        remediation=_build_remediation(failed_checks),
    )
