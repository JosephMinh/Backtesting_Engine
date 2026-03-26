"""Capability tiers and infrastructure upgrade triggers.

Encodes the tier classification system (Plan v3.8 section 2.3) and the
infrastructure upgrade trigger rules (section 2.4).  Provides an evaluation
API that checks current system evidence against upgrade trigger conditions
and produces structured decision traces showing tier assignment, qualifying
evidence, and trigger condition status.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.scope import CapabilityTier


# ---------------------------------------------------------------------------
# Upgrade trigger conditions (Plan v3.8 section 2.4)
# ---------------------------------------------------------------------------

@unique
class UpgradeTriggerID(Enum):
    """Stable identifiers for the five infrastructure upgrade triggers."""

    MULTI_HOST_HOT_PATH = "UTR01"
    MULTI_CONSUMER_FAN_OUT = "UTR02"
    TELEMETRY_LATENCY_DEGRADATION = "UTR03"
    CREDENTIAL_DOMAIN_GROWTH = "UTR04"
    INFRASTRUCTURE_SLO_MISSES = "UTR05"


@dataclass(frozen=True)
class UpgradeTrigger:
    """A single infrastructure upgrade trigger rule.

    Attributes:
        id: Stable trigger identifier.
        short_name: Machine-friendly name.
        condition: Human-readable description of what must be true.
        evidence_keys: The evidence fields evaluated for this trigger.
        requires_continuation_memo: Whether upgrade needs a signed memo.
    """

    id: UpgradeTriggerID
    short_name: str
    condition: str
    evidence_keys: tuple[str, ...]
    requires_continuation_memo: bool = True


UPGRADE_TRIGGERS: tuple[UpgradeTrigger, ...] = (
    UpgradeTrigger(
        id=UpgradeTriggerID.MULTI_HOST_HOT_PATH,
        short_name="multi_host_hot_path",
        condition=(
            "More than one hot-path host is required for paper/shadow/live"
        ),
        evidence_keys=("hot_path_hosts_required",),
    ),
    UpgradeTrigger(
        id=UpgradeTriggerID.MULTI_CONSUMER_FAN_OUT,
        short_name="multi_consumer_fan_out",
        condition=(
            "More than one durable external consumer needs ordered event "
            "fan-out beyond the database"
        ),
        evidence_keys=("durable_external_consumers",),
    ),
    UpgradeTrigger(
        id=UpgradeTriggerID.TELEMETRY_LATENCY_DEGRADATION,
        short_name="telemetry_latency_degradation",
        condition=(
            "Telemetry write/query load materially degrades canonical "
            "metadata latency"
        ),
        evidence_keys=("telemetry_degrades_metadata_latency",),
    ),
    UpgradeTrigger(
        id=UpgradeTriggerID.CREDENTIAL_DOMAIN_GROWTH,
        short_name="credential_domain_growth",
        condition=(
            "The number of operators or credential domains makes OS-native "
            "or managed secret delivery insufficient"
        ),
        evidence_keys=("secret_delivery_insufficient",),
    ),
    UpgradeTrigger(
        id=UpgradeTriggerID.INFRASTRUCTURE_SLO_MISSES,
        short_name="infrastructure_slo_misses",
        condition=(
            "Live SLOs are repeatedly missed because of the current "
            "infrastructure rather than the strategy or broker"
        ),
        evidence_keys=("repeated_infra_slo_misses",),
    ),
)


# ---------------------------------------------------------------------------
# Subsystem tier registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubsystemTier:
    """A subsystem with its assigned capability tier."""

    key: str
    description: str
    tier: CapabilityTier


SUBSYSTEM_TIERS: tuple[SubsystemTier, ...] = (
    # v1_core_required
    SubsystemTier("early_execution_lane", "Early execution-lane vertical slice", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("release_pipeline", "Release pipeline", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("data_profile_release_pipeline", "data_profile_release pipeline", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("bitemporal_reference_model", "Bitemporal reference model", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("nautilus_backtesting", "Nautilus backtesting", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("regime_execution_profiles", "Regime-conditioned execution profiles", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("research_run_registry", "research_run registry", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("family_decision_record", "family_decision_record governance", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("candidate_freeze", "Candidate freeze", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("replay_certification", "Replay certification", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("paper_trading", "Paper trading", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("shadow_live", "Shadow-live", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("ibkr_runtime", "IBKR runtime", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("session_readiness_packets", "Session-readiness packets", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("guardian_emergency_control", "Guardian emergency control", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("idempotent_order_intent", "Idempotent order-intent layer", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("accounting_ledger", "Accounting ledger", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("intraday_eod_reconciliation", "Intraday and end-of-day reconciliation", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("backup_restore", "Backup/restore", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("migration_controls", "Migration controls", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("time_discipline", "Time discipline", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("policy_engine", "Policy engine", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("secret_baseline", "Secret baseline", CapabilityTier.V1_CORE_REQUIRED),
    SubsystemTier("solo_governance", "Solo governance", CapabilityTier.V1_CORE_REQUIRED),
    # v1_conditional
    SubsystemTier("overnight_candidate_class", "Overnight candidate class", CapabilityTier.V1_CONDITIONAL),
    SubsystemTier("native_1oz_validation", "Native 1OZ validation", CapabilityTier.V1_CONDITIONAL),
    SubsystemTier("screening_fast_path", "Screening fast path", CapabilityTier.V1_CONDITIONAL),
    SubsystemTier("nats_transport", "NATS transport", CapabilityTier.V1_CONDITIONAL),
    SubsystemTier("dedicated_telemetry_store", "Dedicated telemetry store", CapabilityTier.V1_CONDITIONAL),
    SubsystemTier("heavier_secret_management", "Heavier secret-management tooling", CapabilityTier.V1_CONDITIONAL),
    # future_only
    SubsystemTier("second_broker_hot_path", "Second broker hot path", CapabilityTier.FUTURE_ONLY),
    SubsystemTier("live_premium_feed", "Live premium feed", CapabilityTier.FUTURE_ONLY),
    SubsystemTier("sub_minute_execution", "Sub-minute execution", CapabilityTier.FUTURE_ONLY),
    SubsystemTier("depth_aware_signals", "Depth-aware signals", CapabilityTier.FUTURE_ONLY),
    SubsystemTier("multi_host_control_plane", "Multi-host live control plane", CapabilityTier.FUTURE_ONLY),
    SubsystemTier("portfolio_optimizer", "Portfolio optimizer", CapabilityTier.FUTURE_ONLY),
)

_SUBSYSTEM_INDEX: dict[str, SubsystemTier] = {s.key: s for s in SUBSYSTEM_TIERS}
_TRIGGER_INDEX: dict[str, UpgradeTrigger] = {t.id.value: t for t in UPGRADE_TRIGGERS}


# ---------------------------------------------------------------------------
# Evaluation results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierAssignmentTrace:
    """Structured decision trace for a tier assignment query."""

    subsystem: str
    tier: str
    description: str
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
class UpgradeTriggerTrace:
    """Structured decision trace for an upgrade trigger evaluation.

    Attributes:
        trigger_id: Stable trigger identifier.
        trigger_name: Human-friendly name.
        condition: The condition being tested.
        triggered: Whether the condition is met.
        evidence: The evidence values that were evaluated.
        requires_memo: Whether a continuation memo is required.
        reason_code: Stable code for downstream reference.
        explanation: Operator-readable explanation.
        timestamp: ISO-8601 timestamp.
    """

    trigger_id: str
    trigger_name: str
    condition: str
    triggered: bool
    evidence: dict[str, Any]
    requires_memo: bool
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ---------------------------------------------------------------------------
# Evaluation API
# ---------------------------------------------------------------------------

def get_subsystem_tier(subsystem_key: str) -> TierAssignmentTrace:
    """Look up the tier assignment for a subsystem."""
    if subsystem_key in _SUBSYSTEM_INDEX:
        entry = _SUBSYSTEM_INDEX[subsystem_key]
        return TierAssignmentTrace(
            subsystem=subsystem_key,
            tier=entry.tier.value,
            description=entry.description,
            reason_code=f"TIER_{entry.tier.value.upper()}_{subsystem_key.upper()}",
            explanation=f"Subsystem '{entry.description}' is classified as {entry.tier.value}",
        )
    return TierAssignmentTrace(
        subsystem=subsystem_key,
        tier="unknown",
        description="",
        reason_code="TIER_UNKNOWN",
        explanation=f"Subsystem '{subsystem_key}' is not in the tier registry",
    )


def get_subsystems_by_tier(tier: CapabilityTier) -> list[SubsystemTier]:
    """Return all subsystems assigned to a given tier."""
    return [s for s in SUBSYSTEM_TIERS if s.tier == tier]


def evaluate_upgrade_trigger(
    trigger_id: UpgradeTriggerID,
    evidence: dict[str, Any],
) -> UpgradeTriggerTrace:
    """Evaluate a single upgrade trigger against provided evidence.

    Evidence keys map to the trigger's evidence_keys.  A trigger fires when
    any of the following hold for its evidence:

    - A numeric evidence value exceeds 1 (for host/consumer counts)
    - A boolean evidence value is True (for degradation/miss flags)
    """
    trigger = _TRIGGER_INDEX[trigger_id.value]
    qualifying = {}
    triggered = False

    for key in trigger.evidence_keys:
        val = evidence.get(key)
        qualifying[key] = val
        if isinstance(val, bool) and val:
            triggered = True
        elif isinstance(val, (int, float)) and val > 1:
            triggered = True

    return UpgradeTriggerTrace(
        trigger_id=trigger.id.value,
        trigger_name=trigger.short_name,
        condition=trigger.condition,
        triggered=triggered,
        evidence=qualifying,
        requires_memo=trigger.requires_continuation_memo,
        reason_code=f"UPGRADE_{trigger.id.value}",
        explanation=(
            f"Upgrade trigger '{trigger.short_name}' is ACTIVE — "
            f"continuation memo required: {qualifying}"
            if triggered
            else f"Upgrade trigger '{trigger.short_name}' is inactive — "
            f"one-host baseline holds: {qualifying}"
        ),
    )


def evaluate_all_upgrade_triggers(
    evidence: dict[str, Any],
) -> list[UpgradeTriggerTrace]:
    """Evaluate all upgrade triggers against provided evidence."""
    return [evaluate_upgrade_trigger(t.id, evidence) for t in UPGRADE_TRIGGERS]


def one_host_baseline_holds(evidence: dict[str, Any]) -> bool:
    """Return True if no upgrade trigger is active — one-host baseline holds."""
    results = evaluate_all_upgrade_triggers(evidence)
    return not any(r.triggered for r in results)
