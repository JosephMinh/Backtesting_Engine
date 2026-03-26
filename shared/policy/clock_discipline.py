"""Time discipline, compiled session clocks, and skew policy."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class ClockAction(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle status literal, not a credential
    WARN = "warn"
    RESTRICT = "restrict"
    BLOCK = "block"


class SynchronizationState(str, Enum):
    SYNCED = "synced"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SkewThresholdPolicy:
    warn_ms: int
    restrict_ms: int
    block_ms: int


@dataclass(frozen=True)
class TimeDisciplinePolicy:
    plan_section: str
    persisted_timestamp_timezone: str
    exchange_calendar_source: str
    session_boundary_source: str
    ordering_basis: str
    durable_sequence_numbers_required: bool
    monotonic_clocks_required: bool
    synchronization_service: str
    sync_health_visible_to_policy: bool
    sync_health_visible_to_observability: bool
    skew_thresholds: SkewThresholdPolicy


@dataclass(frozen=True)
class CompiledSessionBoundary:
    case_id: str
    calendar_id: str
    context_bundle_id: str
    venue: str
    session_name: str
    trading_day: str
    boundary_kind: str
    exchange_local_start: str
    exchange_local_end: str
    utc_start: str
    utc_end: str


@dataclass(frozen=True)
class SessionBoundaryResolution:
    case_id: str
    calendar_id: str
    context_bundle_id: str
    venue: str
    session_name: str
    trading_day: str
    boundary_kind: str
    source: str
    exchange_local_start: str
    exchange_local_end: str
    utc_start: str
    utc_end: str
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class TimingViolationDiagnostic:
    status: str
    reason_code: str
    synchronization_state: str
    measured_skew_ms: int
    configured_threshold_ms: int
    corrective_action: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


DEFAULT_TIME_DISCIPLINE_POLICY = TimeDisciplinePolicy(
    plan_section="3.5",
    persisted_timestamp_timezone="UTC",
    exchange_calendar_source="compiled_exchange_calendars",
    session_boundary_source="resolved_context_bundles",
    ordering_basis="durable_sequence_numbers_and_monotonic_clocks",
    durable_sequence_numbers_required=True,
    monotonic_clocks_required=True,
    synchronization_service="chrony_or_ntp_equivalent",
    sync_health_visible_to_policy=True,
    sync_health_visible_to_observability=True,
    skew_thresholds=SkewThresholdPolicy(warn_ms=100, restrict_ms=500, block_ms=2000),
)


def _parse_aware_timestamp(value: str) -> datetime.datetime:
    timestamp = datetime.datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {value}")
    return timestamp


def canonicalize_persisted_timestamp(
    timestamp: datetime.datetime,
) -> datetime.datetime:
    if timestamp.tzinfo is None:
        raise ValueError("persisted timestamps must be timezone-aware")
    return timestamp.astimezone(datetime.timezone.utc)


def resolve_session_boundary(
    compiled_boundaries: Iterable[CompiledSessionBoundary],
    *,
    venue: str,
    trading_day: str,
    session_name: str,
    policy: TimeDisciplinePolicy = DEFAULT_TIME_DISCIPLINE_POLICY,
) -> SessionBoundaryResolution:
    matching_boundaries = [
        boundary
        for boundary in compiled_boundaries
        if boundary.venue == venue
        and boundary.trading_day == trading_day
        and boundary.session_name == session_name
    ]
    if not matching_boundaries:
        raise KeyError(
            f"no compiled session boundary for {venue=} {trading_day=} {session_name=}"
        )
    if len(matching_boundaries) != 1:
        raise ValueError(
            f"expected exactly one compiled boundary for {venue=} {trading_day=} {session_name=}"
        )

    boundary = matching_boundaries[0]
    return SessionBoundaryResolution(
        case_id=boundary.case_id,
        calendar_id=boundary.calendar_id,
        context_bundle_id=boundary.context_bundle_id,
        venue=boundary.venue,
        session_name=boundary.session_name,
        trading_day=boundary.trading_day,
        boundary_kind=boundary.boundary_kind,
        source=policy.exchange_calendar_source,
        exchange_local_start=boundary.exchange_local_start,
        exchange_local_end=boundary.exchange_local_end,
        utc_start=boundary.utc_start,
        utc_end=boundary.utc_end,
        reason_code="COMPILED_SESSION_BOUNDARY_RESOLVED",
        explanation=(
            "Session boundaries come from compiled exchange calendars and resolved-context "
            "bundles rather than ad-hoc runtime timezone logic."
        ),
    )


def evaluate_clock_skew(
    measured_skew_ms: int,
    synchronization_state: SynchronizationState,
    policy: TimeDisciplinePolicy = DEFAULT_TIME_DISCIPLINE_POLICY,
) -> TimingViolationDiagnostic:
    absolute_skew_ms = abs(measured_skew_ms)
    thresholds = policy.skew_thresholds

    if synchronization_state == SynchronizationState.UNKNOWN:
        return TimingViolationDiagnostic(
            status=ClockAction.BLOCK.value,
            reason_code="CLOCK_SYNC_STATE_UNKNOWN",
            synchronization_state=synchronization_state.value,
            measured_skew_ms=absolute_skew_ms,
            configured_threshold_ms=thresholds.block_ms,
            corrective_action=(
                "Block new entries and require reviewed recovery until synchronization "
                "health is known."
            ),
            explanation=(
                "Synchronization state is unknown, so the host clock cannot be trusted for "
                "new entries or certification."
            ),
        )

    if absolute_skew_ms >= thresholds.block_ms:
        return TimingViolationDiagnostic(
            status=ClockAction.BLOCK.value,
            reason_code="CLOCK_SKEW_BLOCK_THRESHOLD",
            synchronization_state=synchronization_state.value,
            measured_skew_ms=absolute_skew_ms,
            configured_threshold_ms=thresholds.block_ms,
            corrective_action=(
                "Block new entries and require reviewed recovery before the host re-enters "
                "a tradeable lane."
            ),
            explanation=(
                "Measured skew exceeds the block threshold, so session-clock trust is lost "
                "until reviewed recovery completes."
            ),
        )

    if absolute_skew_ms >= thresholds.restrict_ms:
        return TimingViolationDiagnostic(
            status=ClockAction.RESTRICT.value,
            reason_code="CLOCK_SKEW_RESTRICT_THRESHOLD",
            synchronization_state=synchronization_state.value,
            measured_skew_ms=absolute_skew_ms,
            configured_threshold_ms=thresholds.restrict_ms,
            corrective_action=(
                "Restrict new activity, restore synchronization health, and re-check skew "
                "before lifting restrictions."
            ),
            explanation=(
                "Measured skew exceeds the restrict threshold, so the host stays in a "
                "restricted state until time health returns."
            ),
        )

    if absolute_skew_ms >= thresholds.warn_ms:
        return TimingViolationDiagnostic(
            status=ClockAction.WARN.value,
            reason_code="CLOCK_SKEW_WARN_THRESHOLD",
            synchronization_state=synchronization_state.value,
            measured_skew_ms=absolute_skew_ms,
            configured_threshold_ms=thresholds.warn_ms,
            corrective_action="Investigate skew and confirm synchronization remains healthy.",
            explanation=(
                "Measured skew exceeds the warn threshold but remains below restriction "
                "levels."
            ),
        )

    return TimingViolationDiagnostic(
        status=ClockAction.PASS.value,
        reason_code="CLOCK_SKEW_WITHIN_POLICY",
        synchronization_state=synchronization_state.value,
        measured_skew_ms=absolute_skew_ms,
        configured_threshold_ms=thresholds.warn_ms,
        corrective_action="No corrective action required; continue monitoring.",
        explanation="Measured skew is within the approved warn budget.",
    )


def validate_compiled_session_boundaries(
    compiled_boundaries: Iterable[CompiledSessionBoundary],
) -> list[str]:
    errors: list[str] = []
    case_ids: list[str] = []
    uniqueness_keys: list[tuple[str, str, str]] = []

    for boundary in compiled_boundaries:
        case_ids.append(boundary.case_id)
        uniqueness_keys.append((boundary.venue, boundary.trading_day, boundary.session_name))

        if not boundary.calendar_id:
            errors.append(f"{boundary.case_id}: calendar_id is required")
        if not boundary.context_bundle_id:
            errors.append(f"{boundary.case_id}: context_bundle_id is required")
        if not boundary.boundary_kind:
            errors.append(f"{boundary.case_id}: boundary_kind is required")

        utc_start = _parse_aware_timestamp(boundary.utc_start)
        utc_end = _parse_aware_timestamp(boundary.utc_end)
        local_start = _parse_aware_timestamp(boundary.exchange_local_start)
        local_end = _parse_aware_timestamp(boundary.exchange_local_end)

        if utc_start.tzinfo != datetime.timezone.utc or utc_end.tzinfo != datetime.timezone.utc:
            errors.append(f"{boundary.case_id}: UTC session boundaries must use UTC offsets")
        if utc_start >= utc_end:
            errors.append(f"{boundary.case_id}: utc_start must be before utc_end")
        if local_start >= local_end:
            errors.append(
                f"{boundary.case_id}: exchange_local_start must be before exchange_local_end"
            )
        if (utc_end - utc_start) != (local_end - local_start):
            errors.append(
                f"{boundary.case_id}: UTC and exchange-local durations must match compiled data"
            )

    if len(case_ids) != len(set(case_ids)):
        errors.append("compiled session boundary case_ids must be unique")
    if len(uniqueness_keys) != len(set(uniqueness_keys)):
        errors.append(
            "compiled session boundaries must be unique by venue, trading_day, and session_name"
        )

    return errors


def validate_time_discipline_policy(
    policy: TimeDisciplinePolicy = DEFAULT_TIME_DISCIPLINE_POLICY,
) -> list[str]:
    errors: list[str] = []
    thresholds = policy.skew_thresholds

    if policy.plan_section != "3.5":
        errors.append("time discipline policy must remain bound to plan section 3.5")
    if policy.persisted_timestamp_timezone != "UTC":
        errors.append("persisted timestamps must default to UTC")
    if policy.exchange_calendar_source != "compiled_exchange_calendars":
        errors.append("exchange-local times must come from compiled exchange calendars")
    if policy.session_boundary_source != "resolved_context_bundles":
        errors.append("session boundaries must come from resolved-context bundles")
    if policy.ordering_basis != "durable_sequence_numbers_and_monotonic_clocks":
        errors.append("ordering must be based on durable sequence numbers and monotonic clocks")
    if not policy.durable_sequence_numbers_required:
        errors.append("durable sequence numbers must be required")
    if not policy.monotonic_clocks_required:
        errors.append("monotonic clocks must be required")
    if thresholds.warn_ms <= 0:
        errors.append("warn skew threshold must be positive")
    if thresholds.warn_ms >= thresholds.restrict_ms:
        errors.append("warn skew threshold must be below restrict threshold")
    if thresholds.restrict_ms >= thresholds.block_ms:
        errors.append("restrict skew threshold must be below block threshold")
    if not policy.synchronization_service:
        errors.append("synchronization service requirement must be explicit")
    if not policy.sync_health_visible_to_policy:
        errors.append("synchronization health must be visible to policy")
    if not policy.sync_health_visible_to_observability:
        errors.append("synchronization health must be visible to observability")

    return errors


VALIDATION_ERRORS = validate_time_discipline_policy()
