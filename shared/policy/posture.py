"""Mission and initial live-lane posture encoded as upstream constraints.

Defines the approved deployment posture (Plan v3.8 section 1.2) and the six
core program questions (section 1.1) as machine-readable policy assertions.
Downstream policy rules, contract tests, scenario scripts, and operator-facing
rejection logs reference these constraints to prove whether a workflow stays
inside or outside the approved live lane.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


# ---------------------------------------------------------------------------
# Core program questions (Plan v3.8 section 1.1)
# ---------------------------------------------------------------------------

CORE_PROGRAM_QUESTIONS: tuple[str, ...] = (
    "Which strategy families deserve budget?",
    "Which parameter regions are stable enough to validate?",
    (
        "Which candidates survive realistic fills, null comparisons, "
        "robustness tests, omission tests, and a frozen final holdout?"
    ),
    (
        "If research is done on MGC but live execution is on 1OZ, have "
        "portability and execution-symbol tradability been explicitly "
        "certified rather than assumed?"
    ),
    (
        "Can the exact frozen candidate be replayed through the operational "
        "stack without research/live drift, including data-profile, "
        "contract-state, and signal-kernel parity?"
    ),
    (
        "Can the candidate survive paper trading, shadow-live, account-fit, "
        "session resets, broker reconciliation, and solo-operator operational "
        "risk on the actual live contract?"
    ),
)


# ---------------------------------------------------------------------------
# Approved posture parameters
# ---------------------------------------------------------------------------

@unique
class ResearchSymbol(Enum):
    MGC = "MGC"


@unique
class ExecutionSymbol(Enum):
    OZ1 = "1OZ"


@unique
class Broker(Enum):
    IBKR = "IBKR"


@dataclass(frozen=True)
class PostureConstraints:
    """The approved initial deployment posture.

    Every field has a single approved value.  Violations occur when a
    workflow attempts to operate outside these bounds.
    """

    research_symbol: str = "MGC"
    execution_symbol: str = "1OZ"
    broker: str = "IBKR"
    max_account_value_usd: int = 5_000
    max_live_contracts: int = 1
    min_decision_interval_seconds: int = 60
    max_active_bundles_per_account: int = 1
    max_deployment_hosts: int = 1
    overnight_holding_allowed: bool = True
    overnight_requires_stricter_gates: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


APPROVED_POSTURE = PostureConstraints()


# ---------------------------------------------------------------------------
# Posture check result (structured decision trace)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PostureCheckResult:
    """Structured decision trace for a posture constraint evaluation.

    Attributes:
        constraint: Name of the constraint checked.
        passed: True when the value is within the approved lane.
        reason_code: Stable reason code for downstream references.
        actual: The value that was evaluated.
        expected: The approved constraint value.
        diagnostic: Human-readable explanation.
        timestamp: ISO-8601 timestamp of the evaluation.
    """

    constraint: str
    passed: bool
    reason_code: str
    actual: Any
    expected: Any
    diagnostic: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @property
    def violated(self) -> bool:
        return not self.passed


# ---------------------------------------------------------------------------
# Posture validation functions
# ---------------------------------------------------------------------------

def check_research_symbol(symbol: str) -> PostureCheckResult:
    """Verify research is centered on the approved symbol."""
    passed = symbol == APPROVED_POSTURE.research_symbol
    return PostureCheckResult(
        constraint="research_symbol",
        passed=passed,
        reason_code="POSTURE_RESEARCH_SYMBOL",
        actual=symbol,
        expected=APPROVED_POSTURE.research_symbol,
        diagnostic=(
            f"Research symbol '{symbol}' is approved"
            if passed
            else f"Research symbol '{symbol}' is outside approved lane (expected {APPROVED_POSTURE.research_symbol})"
        ),
    )


def check_execution_symbol(symbol: str) -> PostureCheckResult:
    """Verify live execution targets the approved symbol."""
    passed = symbol == APPROVED_POSTURE.execution_symbol
    return PostureCheckResult(
        constraint="execution_symbol",
        passed=passed,
        reason_code="POSTURE_EXECUTION_SYMBOL",
        actual=symbol,
        expected=APPROVED_POSTURE.execution_symbol,
        diagnostic=(
            f"Execution symbol '{symbol}' is approved"
            if passed
            else f"Execution symbol '{symbol}' is outside approved lane (expected {APPROVED_POSTURE.execution_symbol})"
        ),
    )


def check_broker(broker: str) -> PostureCheckResult:
    """Verify broker is the approved provider."""
    passed = broker == APPROVED_POSTURE.broker
    return PostureCheckResult(
        constraint="broker",
        passed=passed,
        reason_code="POSTURE_BROKER",
        actual=broker,
        expected=APPROVED_POSTURE.broker,
        diagnostic=(
            f"Broker '{broker}' is approved"
            if passed
            else f"Broker '{broker}' is not approved (expected {APPROVED_POSTURE.broker})"
        ),
    )


def check_account_value(value_usd: int) -> PostureCheckResult:
    """Verify account value does not exceed the approved cap."""
    passed = value_usd <= APPROVED_POSTURE.max_account_value_usd
    return PostureCheckResult(
        constraint="max_account_value_usd",
        passed=passed,
        reason_code="POSTURE_ACCOUNT_VALUE",
        actual=value_usd,
        expected=APPROVED_POSTURE.max_account_value_usd,
        diagnostic=(
            f"Account value ${value_usd} within approved cap"
            if passed
            else f"Account value ${value_usd} exceeds approved cap of ${APPROVED_POSTURE.max_account_value_usd}"
        ),
    )


def check_live_contracts(count: int) -> PostureCheckResult:
    """Verify live contract count does not exceed the approved limit."""
    passed = count <= APPROVED_POSTURE.max_live_contracts
    return PostureCheckResult(
        constraint="max_live_contracts",
        passed=passed,
        reason_code="POSTURE_LIVE_CONTRACTS",
        actual=count,
        expected=APPROVED_POSTURE.max_live_contracts,
        diagnostic=(
            f"Live contracts ({count}) within approved limit"
            if passed
            else f"Live contracts ({count}) exceeds approved limit of {APPROVED_POSTURE.max_live_contracts}"
        ),
    )


def check_decision_interval(interval_seconds: int) -> PostureCheckResult:
    """Verify strategy decision interval is at or above the approved minimum.

    Live-eligible strategies must be bar-based with decision intervals of
    1 minute or slower.  Sub-minute strategies are research-only.
    """
    passed = interval_seconds >= APPROVED_POSTURE.min_decision_interval_seconds
    return PostureCheckResult(
        constraint="min_decision_interval_seconds",
        passed=passed,
        reason_code="POSTURE_DECISION_INTERVAL",
        actual=interval_seconds,
        expected=APPROVED_POSTURE.min_decision_interval_seconds,
        diagnostic=(
            f"Decision interval {interval_seconds}s meets minimum (>= 60s)"
            if passed
            else f"Decision interval {interval_seconds}s is sub-minute; strategy is research-only"
        ),
    )


def check_active_bundles(count: int) -> PostureCheckResult:
    """Verify active bundle count per account does not exceed approved limit."""
    passed = count <= APPROVED_POSTURE.max_active_bundles_per_account
    return PostureCheckResult(
        constraint="max_active_bundles_per_account",
        passed=passed,
        reason_code="POSTURE_ACTIVE_BUNDLES",
        actual=count,
        expected=APPROVED_POSTURE.max_active_bundles_per_account,
        diagnostic=(
            f"Active bundles ({count}) within limit"
            if passed
            else f"Active bundles ({count}) exceeds approved limit of {APPROVED_POSTURE.max_active_bundles_per_account}"
        ),
    )


def check_deployment_hosts(count: int) -> PostureCheckResult:
    """Verify deployment targets the approved number of hosts."""
    passed = count <= APPROVED_POSTURE.max_deployment_hosts
    return PostureCheckResult(
        constraint="max_deployment_hosts",
        passed=passed,
        reason_code="POSTURE_DEPLOYMENT_HOSTS",
        actual=count,
        expected=APPROVED_POSTURE.max_deployment_hosts,
        diagnostic=(
            f"Deployment hosts ({count}) within limit"
            if passed
            else f"Deployment hosts ({count}) exceeds approved limit of {APPROVED_POSTURE.max_deployment_hosts}"
        ),
    )


def validate_full_posture(
    *,
    research_symbol: str = "MGC",
    execution_symbol: str = "1OZ",
    broker: str = "IBKR",
    account_value_usd: int = 5_000,
    live_contracts: int = 1,
    decision_interval_seconds: int = 60,
    active_bundles: int = 1,
    deployment_hosts: int = 1,
) -> list[PostureCheckResult]:
    """Run all posture checks and return the full list of results.

    Callers can filter for violations via ``[r for r in results if r.violated]``.
    """
    return [
        check_research_symbol(research_symbol),
        check_execution_symbol(execution_symbol),
        check_broker(broker),
        check_account_value(account_value_usd),
        check_live_contracts(live_contracts),
        check_decision_interval(decision_interval_seconds),
        check_active_bundles(active_bundles),
        check_deployment_hosts(deployment_hosts),
    ]
