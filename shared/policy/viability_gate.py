"""Early execution-lane viability gate and execution-symbol-first viability screen.

The viability gate is a first-class spend checkpoint that must pass before
the platform invests in deep tuning or broad family expansion.  A failed
gate forces a documented narrow, pivot, or terminate outcome — it must not
silently allow continuation.

Plan v3.8 section 2.5 defines the five lane checks.
Plan v3.8 section 6.5A defines the execution-symbol-first viability screen.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


# ---------------------------------------------------------------------------
# Gate outcome
# ---------------------------------------------------------------------------

@unique
class GateOutcome(Enum):
    """Possible outcomes of the viability gate."""

    CONTINUE = "continue"
    NARROW = "narrow"
    PIVOT = "pivot"
    TERMINATE = "terminate"


@unique
class LaneCheckID(Enum):
    """Stable identifiers for the five lane checks."""

    MARKET_DATA_ENTITLEMENT = "LC01"
    DETERMINISTIC_BAR_CONSTRUCTION = "LC02"
    END_TO_END_DUMMY_FLOW = "LC03"
    EXECUTION_SYMBOL_TRADABILITY = "LC04"
    NO_LANE_BLOCKERS = "LC05"


# ---------------------------------------------------------------------------
# Individual lane check
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LaneCheckResult:
    """Result of a single lane check within the viability gate."""

    check_id: str
    check_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ---------------------------------------------------------------------------
# Gate diagnostic report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ViabilityGateReport:
    """Structured diagnostic report for the viability gate.

    Contains the individual lane check results, the overall outcome,
    and an operator-readable rationale for the decision.
    """

    gate_passed: bool
    outcome: str
    checks: list[dict[str, Any]]
    passed_count: int
    failed_count: int
    rationale: str
    reason_code: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ---------------------------------------------------------------------------
# Lane check functions
# ---------------------------------------------------------------------------

def check_market_data_entitlement(
    *,
    oz1_entitled: bool,
    session_coverage_verified: bool,
    ibkr_setup_confirmed: bool,
) -> LaneCheckResult:
    """LC01: 1OZ market-data entitlement and session coverage on IBKR."""
    passed = oz1_entitled and session_coverage_verified and ibkr_setup_confirmed
    evidence = {
        "oz1_entitled": oz1_entitled,
        "session_coverage_verified": session_coverage_verified,
        "ibkr_setup_confirmed": ibkr_setup_confirmed,
    }
    failing = [k for k, v in evidence.items() if not v]
    return LaneCheckResult(
        check_id=LaneCheckID.MARKET_DATA_ENTITLEMENT.value,
        check_name="market_data_entitlement",
        passed=passed,
        reason_code="VIABILITY_LC01_MARKET_DATA",
        diagnostic=(
            "1OZ market-data entitlement and session coverage verified on IBKR"
            if passed
            else f"Market-data entitlement check failed: {failing}"
        ),
        evidence=evidence,
    )


def check_deterministic_bar_construction(
    *,
    data_profile_release_approved: bool,
    bar_construction_deterministic: bool,
) -> LaneCheckResult:
    """LC02: Deterministic live bar construction from approved data_profile_release."""
    passed = data_profile_release_approved and bar_construction_deterministic
    evidence = {
        "data_profile_release_approved": data_profile_release_approved,
        "bar_construction_deterministic": bar_construction_deterministic,
    }
    failing = [k for k, v in evidence.items() if not v]
    return LaneCheckResult(
        check_id=LaneCheckID.DETERMINISTIC_BAR_CONSTRUCTION.value,
        check_name="deterministic_bar_construction",
        passed=passed,
        reason_code="VIABILITY_LC02_BAR_CONSTRUCTION",
        diagnostic=(
            "Deterministic bar construction verified from approved data_profile_release"
            if passed
            else f"Bar construction check failed: {failing}"
        ),
        evidence=evidence,
    )


def check_end_to_end_dummy_flow(
    *,
    opsd_routing_ok: bool,
    paper_routing_ok: bool,
    shadow_live_suppression_ok: bool,
    statement_ingestion_ok: bool,
    reconciliation_ok: bool,
) -> LaneCheckResult:
    """LC03: End-to-end dummy-strategy flow through opsd and reconciliation."""
    evidence = {
        "opsd_routing_ok": opsd_routing_ok,
        "paper_routing_ok": paper_routing_ok,
        "shadow_live_suppression_ok": shadow_live_suppression_ok,
        "statement_ingestion_ok": statement_ingestion_ok,
        "reconciliation_ok": reconciliation_ok,
    }
    passed = all(evidence.values())
    failing = [k for k, v in evidence.items() if not v]
    return LaneCheckResult(
        check_id=LaneCheckID.END_TO_END_DUMMY_FLOW.value,
        check_name="end_to_end_dummy_flow",
        passed=passed,
        reason_code="VIABILITY_LC03_DUMMY_FLOW",
        diagnostic=(
            "End-to-end dummy-strategy flow verified through opsd, paper, shadow-live, and reconciliation"
            if passed
            else f"Dummy-strategy flow check failed: {failing}"
        ),
        evidence=evidence,
    )


def check_execution_symbol_tradability(
    *,
    oz1_tradable_by_session_class: bool,
) -> LaneCheckResult:
    """LC04: Preliminary execution-symbol tradability on 1OZ by session class."""
    evidence = {"oz1_tradable_by_session_class": oz1_tradable_by_session_class}
    return LaneCheckResult(
        check_id=LaneCheckID.EXECUTION_SYMBOL_TRADABILITY.value,
        check_name="execution_symbol_tradability",
        passed=oz1_tradable_by_session_class,
        reason_code="VIABILITY_LC04_TRADABILITY",
        diagnostic=(
            "1OZ tradability verified by session class"
            if oz1_tradable_by_session_class
            else "1OZ is not tradable by session class on the intended setup"
        ),
        evidence=evidence,
    )


def check_no_lane_blockers(
    *,
    account_type_ok: bool,
    permissions_ok: bool,
    contract_definition_ok: bool,
    operational_reset_ok: bool,
) -> LaneCheckResult:
    """LC05: Lane is not blocked by account/permissions/contract/reset issues."""
    evidence = {
        "account_type_ok": account_type_ok,
        "permissions_ok": permissions_ok,
        "contract_definition_ok": contract_definition_ok,
        "operational_reset_ok": operational_reset_ok,
    }
    passed = all(evidence.values())
    failing = [k for k, v in evidence.items() if not v]
    return LaneCheckResult(
        check_id=LaneCheckID.NO_LANE_BLOCKERS.value,
        check_name="no_lane_blockers",
        passed=passed,
        reason_code="VIABILITY_LC05_LANE_BLOCKERS",
        diagnostic=(
            "No lane blockers detected"
            if passed
            else f"Lane blockers detected: {failing}"
        ),
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Full viability gate evaluation
# ---------------------------------------------------------------------------

def evaluate_viability_gate(
    *,
    # LC01
    oz1_entitled: bool,
    session_coverage_verified: bool,
    ibkr_setup_confirmed: bool,
    # LC02
    data_profile_release_approved: bool,
    bar_construction_deterministic: bool,
    # LC03
    opsd_routing_ok: bool,
    paper_routing_ok: bool,
    shadow_live_suppression_ok: bool,
    statement_ingestion_ok: bool,
    reconciliation_ok: bool,
    # LC04
    oz1_tradable_by_session_class: bool,
    # LC05
    account_type_ok: bool,
    permissions_ok: bool,
    contract_definition_ok: bool,
    operational_reset_ok: bool,
) -> ViabilityGateReport:
    """Run all five lane checks and produce a gate report.

    If any check fails, the gate fails and the outcome is determined by
    the severity of the failures.  The gate must not silently allow
    continuation when checks fail.
    """
    checks = [
        check_market_data_entitlement(
            oz1_entitled=oz1_entitled,
            session_coverage_verified=session_coverage_verified,
            ibkr_setup_confirmed=ibkr_setup_confirmed,
        ),
        check_deterministic_bar_construction(
            data_profile_release_approved=data_profile_release_approved,
            bar_construction_deterministic=bar_construction_deterministic,
        ),
        check_end_to_end_dummy_flow(
            opsd_routing_ok=opsd_routing_ok,
            paper_routing_ok=paper_routing_ok,
            shadow_live_suppression_ok=shadow_live_suppression_ok,
            statement_ingestion_ok=statement_ingestion_ok,
            reconciliation_ok=reconciliation_ok,
        ),
        check_execution_symbol_tradability(
            oz1_tradable_by_session_class=oz1_tradable_by_session_class,
        ),
        check_no_lane_blockers(
            account_type_ok=account_type_ok,
            permissions_ok=permissions_ok,
            contract_definition_ok=contract_definition_ok,
            operational_reset_ok=operational_reset_ok,
        ),
    ]

    passed_count = sum(1 for c in checks if c.passed)
    failed_count = len(checks) - passed_count
    gate_passed = failed_count == 0

    if gate_passed:
        outcome = GateOutcome.CONTINUE.value
        rationale = (
            "All five lane checks passed. The execution lane is viable. "
            "Deep tuning and family expansion may proceed."
        )
        reason_code = "VIABILITY_GATE_PASSED"
    else:
        failed_names = [c.check_name for c in checks if not c.passed]
        outcome = _determine_failure_outcome(checks)
        rationale = (
            f"Viability gate FAILED: {failed_count} of {len(checks)} checks failed "
            f"({', '.join(failed_names)}). "
            f"Outcome: {outcome}. "
            "Deep tuning and family expansion must not proceed until the gate passes."
        )
        reason_code = "VIABILITY_GATE_FAILED"

    return ViabilityGateReport(
        gate_passed=gate_passed,
        outcome=outcome,
        checks=[c.to_dict() for c in checks],
        passed_count=passed_count,
        failed_count=failed_count,
        rationale=rationale,
        reason_code=reason_code,
    )


def _determine_failure_outcome(checks: list[LaneCheckResult]) -> str:
    """Determine the appropriate failure outcome based on which checks failed.

    - If market data or tradability fails: pivot (fundamental lane issue)
    - If lane blockers exist: narrow or pivot depending on severity
    - If only flow or bar construction fails: narrow (potentially fixable)
    """
    failed_ids = {c.check_id for c in checks if not c.passed}

    # Fundamental lane issues require pivot or terminate
    fundamental = {
        LaneCheckID.MARKET_DATA_ENTITLEMENT.value,
        LaneCheckID.EXECUTION_SYMBOL_TRADABILITY.value,
    }
    if failed_ids & fundamental:
        if len(failed_ids) >= 3:
            return GateOutcome.TERMINATE.value
        return GateOutcome.PIVOT.value

    # Lane blockers may require pivot
    if LaneCheckID.NO_LANE_BLOCKERS.value in failed_ids:
        return GateOutcome.PIVOT.value

    # Flow or bar construction issues are potentially fixable
    return GateOutcome.NARROW.value


# ---------------------------------------------------------------------------
# Execution-symbol-first viability screen (Plan 6.5A)
# ---------------------------------------------------------------------------


@unique
class ScreenDimensionID(Enum):
    """Stable identifiers for the execution-symbol-first viability dimensions."""

    QUOTE_PRINT_PRESENCE = "VS01"
    SPREAD_AND_COMPLETENESS = "VS02"
    FEE_AND_SLIPPAGE_FEASIBILITY = "VS03"
    TRADABLE_SESSION_COVERAGE = "VS04"
    HOLDING_PERIOD_COMPATIBILITY = "VS05"


@dataclass(frozen=True)
class ExecutionSymbolDimensionResult:
    """Structured result for one execution-symbol-first viability dimension."""

    dimension_id: str
    dimension_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    measured_value: dict[str, Any]
    threshold: dict[str, Any]
    data_source_reference: str
    session_class: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class ExecutionSymbolViabilityReport:
    """Budget-gating report for MGC-vs-1OZ execution-symbol-first viability."""

    research_symbol: str
    execution_symbol: str
    candidate_id: str
    research_artifact_id: str
    native_execution_history_obtained: bool
    live_or_paper_observations_obtained: bool
    portability_study_required: bool
    viability_passed: bool
    deep_promotable_budget_allowed: bool
    outcome_recommendation: str
    dimensions: list[dict[str, Any]]
    passed_count: int
    failed_count: int
    rationale: str
    reason_code: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def check_quote_print_presence_by_session_class(
    *,
    session_class: str,
    quote_presence_ratio: float,
    print_presence_ratio: float,
    min_quote_presence_ratio: float,
    min_print_presence_ratio: float,
    data_source_reference: str,
) -> ExecutionSymbolDimensionResult:
    """VS01: Quote and print presence by session class."""

    passed = (
        quote_presence_ratio >= min_quote_presence_ratio
        and print_presence_ratio >= min_print_presence_ratio
    )
    measured_value = {
        "quote_presence_ratio": quote_presence_ratio,
        "print_presence_ratio": print_presence_ratio,
    }
    threshold = {
        "min_quote_presence_ratio": min_quote_presence_ratio,
        "min_print_presence_ratio": min_print_presence_ratio,
    }
    failing = [
        key
        for key, ok in {
            "quote_presence_ratio": quote_presence_ratio >= min_quote_presence_ratio,
            "print_presence_ratio": print_presence_ratio >= min_print_presence_ratio,
        }.items()
        if not ok
    ]
    return ExecutionSymbolDimensionResult(
        dimension_id=ScreenDimensionID.QUOTE_PRINT_PRESENCE.value,
        dimension_name="quote_print_presence_by_session_class",
        passed=passed,
        reason_code="VIABILITY_SCREEN_VS01_QUOTE_PRINT_PRESENCE",
        diagnostic=(
            f"Quote and print presence are sufficient for session class {session_class}"
            if passed
            else f"Quote/print presence below threshold for session class {session_class}: {failing}"
        ),
        measured_value=measured_value,
        threshold=threshold,
        data_source_reference=data_source_reference,
        session_class=session_class,
    )


def check_spread_and_bar_completeness(
    *,
    session_class: str,
    median_spread_bps: float,
    max_allowed_spread_bps: float,
    bar_completeness_ratio: float,
    min_bar_completeness_ratio: float,
    data_source_reference: str,
) -> ExecutionSymbolDimensionResult:
    """VS02: Spread regime and bar completeness."""

    passed = (
        median_spread_bps <= max_allowed_spread_bps
        and bar_completeness_ratio >= min_bar_completeness_ratio
    )
    measured_value = {
        "median_spread_bps": median_spread_bps,
        "bar_completeness_ratio": bar_completeness_ratio,
    }
    threshold = {
        "max_allowed_spread_bps": max_allowed_spread_bps,
        "min_bar_completeness_ratio": min_bar_completeness_ratio,
    }
    failing = [
        key
        for key, ok in {
            "median_spread_bps": median_spread_bps <= max_allowed_spread_bps,
            "bar_completeness_ratio": bar_completeness_ratio >= min_bar_completeness_ratio,
        }.items()
        if not ok
    ]
    return ExecutionSymbolDimensionResult(
        dimension_id=ScreenDimensionID.SPREAD_AND_COMPLETENESS.value,
        dimension_name="spread_and_bar_completeness",
        passed=passed,
        reason_code="VIABILITY_SCREEN_VS02_SPREAD_AND_COMPLETENESS",
        diagnostic=(
            f"Spread and bar completeness are acceptable for session class {session_class}"
            if passed
            else f"Spread/completeness check failed for session class {session_class}: {failing}"
        ),
        measured_value=measured_value,
        threshold=threshold,
        data_source_reference=data_source_reference,
        session_class=session_class,
    )


def check_fee_and_slippage_feasibility(
    *,
    session_class: str,
    intended_contract_count: int,
    approved_contract_count: int,
    estimated_round_trip_cost_bps: float,
    max_allowed_round_trip_cost_bps: float,
    estimated_round_trip_cost_usd: float,
    max_allowed_round_trip_cost_usd: float,
    data_source_reference: str,
) -> ExecutionSymbolDimensionResult:
    """VS03: Fee-and-slippage feasibility at the approved size."""

    passed = (
        intended_contract_count <= approved_contract_count
        and estimated_round_trip_cost_bps <= max_allowed_round_trip_cost_bps
        and estimated_round_trip_cost_usd <= max_allowed_round_trip_cost_usd
    )
    measured_value = {
        "intended_contract_count": intended_contract_count,
        "estimated_round_trip_cost_bps": estimated_round_trip_cost_bps,
        "estimated_round_trip_cost_usd": estimated_round_trip_cost_usd,
    }
    threshold = {
        "approved_contract_count": approved_contract_count,
        "max_allowed_round_trip_cost_bps": max_allowed_round_trip_cost_bps,
        "max_allowed_round_trip_cost_usd": max_allowed_round_trip_cost_usd,
    }
    failing = [
        key
        for key, ok in {
            "intended_contract_count": intended_contract_count <= approved_contract_count,
            "estimated_round_trip_cost_bps": (
                estimated_round_trip_cost_bps <= max_allowed_round_trip_cost_bps
            ),
            "estimated_round_trip_cost_usd": (
                estimated_round_trip_cost_usd <= max_allowed_round_trip_cost_usd
            ),
        }.items()
        if not ok
    ]
    return ExecutionSymbolDimensionResult(
        dimension_id=ScreenDimensionID.FEE_AND_SLIPPAGE_FEASIBILITY.value,
        dimension_name="fee_and_slippage_feasibility",
        passed=passed,
        reason_code="VIABILITY_SCREEN_VS03_FEE_AND_SLIPPAGE",
        diagnostic=(
            f"Fee and slippage are feasible at approved size for session class {session_class}"
            if passed
            else f"Fee/slippage feasibility failed for session class {session_class}: {failing}"
        ),
        measured_value=measured_value,
        threshold=threshold,
        data_source_reference=data_source_reference,
        session_class=session_class,
    )


def check_tradable_session_coverage(
    *,
    session_class: str,
    tradable_session_coverage_ratio: float,
    min_tradable_session_coverage_ratio: float,
    protected_windows_respected: bool,
    maintenance_fence_respected: bool,
    data_source_reference: str,
) -> ExecutionSymbolDimensionResult:
    """VS04: Tradable-session coverage after protected windows and maintenance fences."""

    passed = (
        tradable_session_coverage_ratio >= min_tradable_session_coverage_ratio
        and protected_windows_respected
        and maintenance_fence_respected
    )
    measured_value = {
        "tradable_session_coverage_ratio": tradable_session_coverage_ratio,
        "protected_windows_respected": protected_windows_respected,
        "maintenance_fence_respected": maintenance_fence_respected,
    }
    threshold = {
        "min_tradable_session_coverage_ratio": min_tradable_session_coverage_ratio,
        "protected_windows_respected": True,
        "maintenance_fence_respected": True,
    }
    failing = [
        key
        for key, ok in {
            "tradable_session_coverage_ratio": (
                tradable_session_coverage_ratio >= min_tradable_session_coverage_ratio
            ),
            "protected_windows_respected": protected_windows_respected,
            "maintenance_fence_respected": maintenance_fence_respected,
        }.items()
        if not ok
    ]
    return ExecutionSymbolDimensionResult(
        dimension_id=ScreenDimensionID.TRADABLE_SESSION_COVERAGE.value,
        dimension_name="tradable_session_coverage",
        passed=passed,
        reason_code="VIABILITY_SCREEN_VS04_SESSION_COVERAGE",
        diagnostic=(
            f"Tradable-session coverage is sufficient for session class {session_class}"
            if passed
            else f"Tradable-session coverage failed for session class {session_class}: {failing}"
        ),
        measured_value=measured_value,
        threshold=threshold,
        data_source_reference=data_source_reference,
        session_class=session_class,
    )


def check_holding_period_compatibility(
    *,
    session_class: str,
    intended_holding_period_minutes: int,
    liquidity_supported_holding_period_minutes: int,
    data_source_reference: str,
) -> ExecutionSymbolDimensionResult:
    """VS05: Intended holding period compatibility with 1OZ liquidity."""

    passed = liquidity_supported_holding_period_minutes >= intended_holding_period_minutes
    measured_value = {
        "intended_holding_period_minutes": intended_holding_period_minutes,
        "liquidity_supported_holding_period_minutes": liquidity_supported_holding_period_minutes,
    }
    threshold = {
        "min_liquidity_supported_holding_period_minutes": intended_holding_period_minutes,
    }
    return ExecutionSymbolDimensionResult(
        dimension_id=ScreenDimensionID.HOLDING_PERIOD_COMPATIBILITY.value,
        dimension_name="holding_period_compatibility",
        passed=passed,
        reason_code="VIABILITY_SCREEN_VS05_HOLDING_PERIOD",
        diagnostic=(
            f"Holding period is compatible with 1OZ liquidity for session class {session_class}"
            if passed
            else (
                f"Holding period exceeds 1OZ liquidity support for session class {session_class}: "
                f"{liquidity_supported_holding_period_minutes} < {intended_holding_period_minutes}"
            )
        ),
        measured_value=measured_value,
        threshold=threshold,
        data_source_reference=data_source_reference,
        session_class=session_class,
    )


def evaluate_execution_symbol_first_viability_screen(
    *,
    research_symbol: str,
    execution_symbol: str,
    candidate_id: str,
    research_artifact_id: str,
    native_execution_history_obtained: bool,
    live_or_paper_observations_obtained: bool,
    dimensions: list[ExecutionSymbolDimensionResult],
) -> ExecutionSymbolViabilityReport:
    """Gate deep promotable budget using 1OZ-native viability evidence."""

    if not dimensions:
        raise ValueError("Execution-symbol-first viability screen requires at least one dimension")

    viability_passed = all(dimension.passed for dimension in dimensions)
    passed_count = sum(1 for dimension in dimensions if dimension.passed)
    failed_count = len(dimensions) - passed_count
    portability_study_required = research_symbol != execution_symbol
    execution_symbol_first_gate_applies = execution_symbol == "1OZ"
    evidence_available = native_execution_history_obtained and live_or_paper_observations_obtained

    deep_promotable_budget_allowed = (
        viability_passed and evidence_available
        if execution_symbol_first_gate_applies
        else viability_passed
    )

    if deep_promotable_budget_allowed:
        outcome_recommendation = GateOutcome.CONTINUE.value
        reason_code = "EXECUTION_SYMBOL_FIRST_VIABILITY_PASSED"
        rationale = (
            "Execution-symbol-first viability passed with native execution history and live/paper "
            "observations. Deep promotable budget may proceed."
        )
    else:
        outcome_recommendation = _determine_screen_failure_outcome(
            dimensions=dimensions,
            native_execution_history_obtained=native_execution_history_obtained,
            live_or_paper_observations_obtained=live_or_paper_observations_obtained,
        )
        reason_code = "EXECUTION_SYMBOL_FIRST_VIABILITY_BLOCKED"
        failed_dimension_names = [dimension.dimension_name for dimension in dimensions if not dimension.passed]
        missing_evidence = [
            name
            for name, present in {
                "native_execution_history_obtained": native_execution_history_obtained,
                "live_or_paper_observations_obtained": live_or_paper_observations_obtained,
            }.items()
            if execution_symbol_first_gate_applies and not present
        ]
        rationale = (
            "Execution-symbol-first viability blocked deep promotable budget. "
            f"Failed dimensions: {failed_dimension_names or ['none']}. "
            f"Missing evidence prerequisites: {missing_evidence or ['none']}. "
            f"Outcome recommendation: {outcome_recommendation}."
        )

    return ExecutionSymbolViabilityReport(
        research_symbol=research_symbol,
        execution_symbol=execution_symbol,
        candidate_id=candidate_id,
        research_artifact_id=research_artifact_id,
        native_execution_history_obtained=native_execution_history_obtained,
        live_or_paper_observations_obtained=live_or_paper_observations_obtained,
        portability_study_required=portability_study_required,
        viability_passed=viability_passed,
        deep_promotable_budget_allowed=deep_promotable_budget_allowed,
        outcome_recommendation=outcome_recommendation,
        dimensions=[dimension.to_dict() for dimension in dimensions],
        passed_count=passed_count,
        failed_count=failed_count,
        rationale=rationale,
        reason_code=reason_code,
    )


def _determine_screen_failure_outcome(
    *,
    dimensions: list[ExecutionSymbolDimensionResult],
    native_execution_history_obtained: bool,
    live_or_paper_observations_obtained: bool,
) -> str:
    """Recommend how to respond when execution-symbol-first viability fails."""

    failed_ids = {dimension.dimension_id for dimension in dimensions if not dimension.passed}

    if not native_execution_history_obtained or not live_or_paper_observations_obtained:
        return GateOutcome.NARROW.value

    fundamental = {
        ScreenDimensionID.QUOTE_PRINT_PRESENCE.value,
        ScreenDimensionID.TRADABLE_SESSION_COVERAGE.value,
        ScreenDimensionID.HOLDING_PERIOD_COMPATIBILITY.value,
    }
    if len(failed_ids) >= 3:
        return GateOutcome.TERMINATE.value
    if failed_ids & fundamental:
        return GateOutcome.PIVOT.value
    return GateOutcome.NARROW.value
