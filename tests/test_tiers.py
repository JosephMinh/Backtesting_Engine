"""Contract tests for capability tiers and infrastructure upgrade triggers.

Verifies that:
  - v1_core_required, v1_conditional, and future_only are explicit categories
  - all subsystems have tier assignments
  - upgrade triggers require evidence tied to listed conditions
  - one-host baseline holds until triggers fire
  - tests produce structured decision traces with tier, evidence, and trigger status

Coverage required by bead backtesting_engine-ltc.1.4.
"""

from __future__ import annotations

import json

import pytest

from shared.policy.scope import CapabilityTier
from shared.policy.tiers import (
    SUBSYSTEM_TIERS,
    UPGRADE_TRIGGERS,
    SubsystemTier,
    TierAssignmentTrace,
    UpgradeTriggerID,
    UpgradeTriggerTrace,
    evaluate_all_upgrade_triggers,
    evaluate_upgrade_trigger,
    get_subsystem_tier,
    get_subsystems_by_tier,
    one_host_baseline_holds,
)


# Evidence where no upgrade trigger fires
QUIET_EVIDENCE: dict[str, object] = {
    "hot_path_hosts_required": 1,
    "durable_external_consumers": 0,
    "telemetry_degrades_metadata_latency": False,
    "secret_delivery_insufficient": False,
    "repeated_infra_slo_misses": False,
}


# ---------------------------------------------------------------------------
# Subsystem tier registry
# ---------------------------------------------------------------------------


class TestSubsystemTierRegistry:
    """Verify the tier registry is complete and consistent."""

    def test_registry_nonempty(self):
        assert len(SUBSYSTEM_TIERS) >= 30

    def test_unique_keys(self):
        keys = [s.key for s in SUBSYSTEM_TIERS]
        assert len(keys) == len(set(keys))

    def test_all_three_tiers_represented(self):
        tiers = {s.tier for s in SUBSYSTEM_TIERS}
        assert tiers == {
            CapabilityTier.V1_CORE_REQUIRED,
            CapabilityTier.V1_CONDITIONAL,
            CapabilityTier.FUTURE_ONLY,
        }

    def test_v1_core_has_expected_count(self):
        core = get_subsystems_by_tier(CapabilityTier.V1_CORE_REQUIRED)
        assert len(core) >= 24

    def test_v1_conditional_has_expected_count(self):
        conditional = get_subsystems_by_tier(CapabilityTier.V1_CONDITIONAL)
        assert len(conditional) >= 6

    def test_future_only_has_expected_count(self):
        future = get_subsystems_by_tier(CapabilityTier.FUTURE_ONLY)
        assert len(future) >= 6

    def test_key_core_subsystems_present(self):
        core_keys = {s.key for s in get_subsystems_by_tier(CapabilityTier.V1_CORE_REQUIRED)}
        expected = {
            "nautilus_backtesting",
            "candidate_freeze",
            "replay_certification",
            "paper_trading",
            "shadow_live",
            "ibkr_runtime",
            "guardian_emergency_control",
            "idempotent_order_intent",
            "policy_engine",
            "backup_restore",
        }
        assert expected.issubset(core_keys)

    def test_key_future_subsystems_present(self):
        future_keys = {s.key for s in get_subsystems_by_tier(CapabilityTier.FUTURE_ONLY)}
        expected = {
            "second_broker_hot_path",
            "live_premium_feed",
            "sub_minute_execution",
            "portfolio_optimizer",
        }
        assert expected.issubset(future_keys)


# ---------------------------------------------------------------------------
# Tier assignment traces
# ---------------------------------------------------------------------------


class TestTierAssignment:
    """Verify tier assignment lookups produce correct traces."""

    @pytest.mark.parametrize(
        "key",
        [s.key for s in SUBSYSTEM_TIERS],
        ids=[s.key for s in SUBSYSTEM_TIERS],
    )
    def test_each_subsystem_returns_valid_trace(self, key):
        trace = get_subsystem_tier(key)
        assert trace.tier in {"v1_core_required", "v1_conditional", "future_only"}
        assert trace.reason_code.startswith("TIER_")
        assert trace.subsystem == key

    def test_unknown_subsystem(self):
        trace = get_subsystem_tier("quantum_computer")
        assert trace.tier == "unknown"
        assert trace.reason_code == "TIER_UNKNOWN"

    def test_trace_serializes_to_json(self):
        trace = get_subsystem_tier("nautilus_backtesting")
        parsed = json.loads(trace.to_json())
        assert parsed["tier"] == "v1_core_required"
        assert parsed["reason_code"].startswith("TIER_V1_CORE_REQUIRED_")

    def test_core_subsystem_trace(self):
        trace = get_subsystem_tier("guardian_emergency_control")
        assert trace.tier == "v1_core_required"
        assert "guardian" in trace.explanation.lower()

    def test_conditional_subsystem_trace(self):
        trace = get_subsystem_tier("nats_transport")
        assert trace.tier == "v1_conditional"

    def test_future_subsystem_trace(self):
        trace = get_subsystem_tier("portfolio_optimizer")
        assert trace.tier == "future_only"


# ---------------------------------------------------------------------------
# Upgrade trigger registry
# ---------------------------------------------------------------------------


class TestUpgradeTriggerRegistry:
    """Verify upgrade trigger rules are complete."""

    def test_five_triggers_defined(self):
        assert len(UPGRADE_TRIGGERS) == 5

    def test_unique_trigger_ids(self):
        ids = [t.id for t in UPGRADE_TRIGGERS]
        assert len(ids) == len(set(ids))

    def test_all_require_continuation_memo(self):
        for trigger in UPGRADE_TRIGGERS:
            assert trigger.requires_continuation_memo

    def test_all_have_evidence_keys(self):
        for trigger in UPGRADE_TRIGGERS:
            assert len(trigger.evidence_keys) > 0


# ---------------------------------------------------------------------------
# Upgrade trigger evaluation: no triggers active
# ---------------------------------------------------------------------------


class TestUpgradeTriggersQuiet:
    """Verify one-host baseline holds when no trigger conditions are met."""

    def test_baseline_holds_with_quiet_evidence(self):
        assert one_host_baseline_holds(QUIET_EVIDENCE)

    def test_all_triggers_inactive(self):
        results = evaluate_all_upgrade_triggers(QUIET_EVIDENCE)
        assert len(results) == 5
        assert all(not r.triggered for r in results)

    def test_traces_explain_baseline(self):
        results = evaluate_all_upgrade_triggers(QUIET_EVIDENCE)
        for r in results:
            assert "inactive" in r.explanation
            assert "baseline holds" in r.explanation


# ---------------------------------------------------------------------------
# Upgrade trigger evaluation: individual triggers
# ---------------------------------------------------------------------------


class TestMultiHostHotPath:
    """UTR01: Multi-host hot path trigger."""

    def test_inactive_with_one_host(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_HOST_HOT_PATH,
            {"hot_path_hosts_required": 1},
        )
        assert not result.triggered

    def test_active_with_two_hosts(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_HOST_HOT_PATH,
            {"hot_path_hosts_required": 2},
        )
        assert result.triggered
        assert result.requires_memo
        assert result.reason_code == "UPGRADE_UTR01"

    def test_trace_includes_evidence(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_HOST_HOT_PATH,
            {"hot_path_hosts_required": 3},
        )
        parsed = json.loads(result.to_json())
        assert parsed["evidence"]["hot_path_hosts_required"] == 3
        assert parsed["triggered"] is True


class TestMultiConsumerFanOut:
    """UTR02: Multi-consumer fan-out trigger."""

    def test_inactive_with_zero_consumers(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_CONSUMER_FAN_OUT,
            {"durable_external_consumers": 0},
        )
        assert not result.triggered

    def test_active_with_multiple_consumers(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_CONSUMER_FAN_OUT,
            {"durable_external_consumers": 2},
        )
        assert result.triggered
        assert result.reason_code == "UPGRADE_UTR02"


class TestTelemetryDegradation:
    """UTR03: Telemetry latency degradation trigger."""

    def test_inactive_when_no_degradation(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.TELEMETRY_LATENCY_DEGRADATION,
            {"telemetry_degrades_metadata_latency": False},
        )
        assert not result.triggered

    def test_active_when_degraded(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.TELEMETRY_LATENCY_DEGRADATION,
            {"telemetry_degrades_metadata_latency": True},
        )
        assert result.triggered
        assert result.reason_code == "UPGRADE_UTR03"


class TestCredentialDomainGrowth:
    """UTR04: Credential domain growth trigger."""

    def test_inactive_when_sufficient(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.CREDENTIAL_DOMAIN_GROWTH,
            {"secret_delivery_insufficient": False},
        )
        assert not result.triggered

    def test_active_when_insufficient(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.CREDENTIAL_DOMAIN_GROWTH,
            {"secret_delivery_insufficient": True},
        )
        assert result.triggered
        assert result.reason_code == "UPGRADE_UTR04"


class TestInfrastructureSLOMisses:
    """UTR05: Infrastructure SLO misses trigger."""

    def test_inactive_when_no_misses(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.INFRASTRUCTURE_SLO_MISSES,
            {"repeated_infra_slo_misses": False},
        )
        assert not result.triggered

    def test_active_when_misses_detected(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.INFRASTRUCTURE_SLO_MISSES,
            {"repeated_infra_slo_misses": True},
        )
        assert result.triggered
        assert result.reason_code == "UPGRADE_UTR05"
        assert "continuation memo required" in result.explanation


# ---------------------------------------------------------------------------
# Combined evaluation
# ---------------------------------------------------------------------------


class TestCombinedEvaluation:
    """Verify combined upgrade trigger evaluation."""

    def test_single_trigger_breaks_baseline(self):
        evidence = dict(QUIET_EVIDENCE)
        evidence["repeated_infra_slo_misses"] = True
        assert not one_host_baseline_holds(evidence)

    def test_multiple_triggers_active(self):
        evidence = {
            "hot_path_hosts_required": 3,
            "durable_external_consumers": 2,
            "telemetry_degrades_metadata_latency": True,
            "secret_delivery_insufficient": False,
            "repeated_infra_slo_misses": False,
        }
        results = evaluate_all_upgrade_triggers(evidence)
        active = [r for r in results if r.triggered]
        assert len(active) == 3

    def test_all_traces_have_stable_reason_codes(self):
        results = evaluate_all_upgrade_triggers(QUIET_EVIDENCE)
        for r in results:
            assert r.reason_code.startswith("UPGRADE_UTR")

    def test_all_traces_serialize(self):
        results = evaluate_all_upgrade_triggers(QUIET_EVIDENCE)
        for r in results:
            parsed = json.loads(r.to_json())
            assert "trigger_id" in parsed
            assert "triggered" in parsed
            assert "evidence" in parsed
            assert "requires_memo" in parsed

    def test_missing_evidence_key_does_not_trigger(self):
        result = evaluate_upgrade_trigger(
            UpgradeTriggerID.MULTI_HOST_HOT_PATH,
            {},  # missing key
        )
        assert not result.triggered
        assert result.evidence["hot_path_hosts_required"] is None
