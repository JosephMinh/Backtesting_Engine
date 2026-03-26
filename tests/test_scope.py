"""Contract tests for scope boundaries (Plan v3.8 section 2).

Verifies that:
  - in-scope deliverables cover the full research-to-paper/shadow/live path
  - anti-scope items are rejected with operator-readable explanations
  - classification tests correctly categorize items as in_scope, anti_scope, or unknown
  - boundary tests emit structured logs with categorization reasons and plan sections

Coverage required by bead backtesting_engine-ltc.1.3.
"""

from __future__ import annotations

import json

import pytest

from shared.policy.scope import (
    ANTI_SCOPE_RULES,
    IN_SCOPE_ITEMS,
    AntiScopeRule,
    CapabilityTier,
    ScopeCategory,
    ScopeClassification,
    ScopeItem,
    classify_item,
    classify_items,
    get_all_anti_scope_keys,
    get_items_by_tier,
)


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------


class TestScopeRegistry:
    """Verify the scope registry is complete and consistent."""

    def test_in_scope_items_nonempty(self):
        assert len(IN_SCOPE_ITEMS) >= 14  # 14 core + conditionals

    def test_anti_scope_rules_nonempty(self):
        assert len(ANTI_SCOPE_RULES) >= 11

    def test_unique_in_scope_keys(self):
        keys = [i.key for i in IN_SCOPE_ITEMS]
        assert len(keys) == len(set(keys))

    def test_unique_anti_scope_keys(self):
        keys = [r.key for r in ANTI_SCOPE_RULES]
        assert len(keys) == len(set(keys))

    def test_no_overlap_between_scope_and_anti_scope(self):
        in_keys = {i.key for i in IN_SCOPE_ITEMS}
        anti_keys = {r.key for r in ANTI_SCOPE_RULES}
        assert in_keys.isdisjoint(anti_keys)

    def test_all_in_scope_have_plan_section(self):
        for item in IN_SCOPE_ITEMS:
            assert item.plan_section, f"{item.key} missing plan_section"

    def test_all_anti_scope_have_rejection_reason(self):
        for rule in ANTI_SCOPE_RULES:
            assert rule.rejection_reason, f"{rule.key} missing rejection_reason"


# ---------------------------------------------------------------------------
# Capability tier classification
# ---------------------------------------------------------------------------


class TestCapabilityTiers:
    """Verify items are classified into the correct capability tiers."""

    def test_v1_core_required_items_exist(self):
        core = get_items_by_tier(CapabilityTier.V1_CORE_REQUIRED)
        assert len(core) >= 14

    def test_v1_conditional_items_exist(self):
        conditional = get_items_by_tier(CapabilityTier.V1_CONDITIONAL)
        assert len(conditional) >= 1

    def test_core_items_include_key_deliverables(self):
        core_keys = {i.key for i in get_items_by_tier(CapabilityTier.V1_CORE_REQUIRED)}
        expected = {
            "early_execution_lane_vertical_slice",
            "nautilus_backtesting",
            "candidate_freeze",
            "replay_certification",
            "paper_and_shadow_live",
            "rust_operational_daemon",
            "eod_broker_reconciliation",
            "narrow_first_live_lane",
        }
        assert expected.issubset(core_keys)

    def test_anti_scope_items_are_future_only(self):
        for key in get_all_anti_scope_keys():
            result = classify_item(key)
            assert result.tier == CapabilityTier.FUTURE_ONLY.value


# ---------------------------------------------------------------------------
# Classification: in-scope items
# ---------------------------------------------------------------------------


class TestInScopeClassification:
    """Verify in-scope items are correctly classified."""

    @pytest.mark.parametrize(
        "key",
        [i.key for i in IN_SCOPE_ITEMS],
        ids=[i.key for i in IN_SCOPE_ITEMS],
    )
    def test_each_in_scope_item_classified_correctly(self, key):
        result = classify_item(key)
        assert result.category == ScopeCategory.IN_SCOPE.value
        assert result.is_allowed
        assert not result.is_rejected
        assert result.tier is not None
        assert result.plan_section != "n/a"

    def test_trace_has_required_fields(self):
        result = classify_item("nautilus_backtesting")
        d = result.to_dict()
        required = {"item", "category", "tier", "rule", "plan_section", "reason_code", "explanation", "timestamp"}
        assert required.issubset(d.keys())

    def test_trace_serializes_to_json(self):
        result = classify_item("candidate_freeze")
        parsed = json.loads(result.to_json())
        assert parsed["category"] == "in_scope"
        assert parsed["reason_code"].startswith("SCOPE_IN_")


# ---------------------------------------------------------------------------
# Classification: anti-scope items (negative tests)
# ---------------------------------------------------------------------------


class TestAntiScopeClassification:
    """Verify anti-scope items are rejected with operator-readable explanations."""

    @pytest.mark.parametrize(
        "key",
        [r.key for r in ANTI_SCOPE_RULES],
        ids=[r.key for r in ANTI_SCOPE_RULES],
    )
    def test_each_anti_scope_item_rejected(self, key):
        result = classify_item(key)
        assert result.category == ScopeCategory.ANTI_SCOPE.value
        assert result.is_rejected
        assert not result.is_allowed
        assert result.explanation  # has operator-readable text

    def test_custom_matching_engine_rejected(self):
        result = classify_item("custom_matching_engine")
        assert result.is_rejected
        assert "NautilusTrader" in result.explanation
        assert result.reason_code == "SCOPE_ANTI_CUSTOM_MATCHING_ENGINE"

    def test_sub_minute_strategies_rejected(self):
        result = classify_item("sub_minute_live_strategies")
        assert result.is_rejected
        assert "research-only" in result.explanation

    def test_second_broker_rejected(self):
        result = classify_item("second_broker")
        assert result.is_rejected
        assert "IBKR" in result.explanation
        assert "continuation review" in result.explanation

    def test_kubernetes_rejected(self):
        result = classify_item("kubernetes_orchestration")
        assert result.is_rejected
        assert "one-host" in result.explanation.lower() or "One-host" in result.explanation

    def test_multiple_live_bundles_rejected(self):
        result = classify_item("multiple_active_live_bundles")
        assert result.is_rejected
        assert "one active" in result.explanation.lower() or "One active" in result.explanation

    def test_rejection_trace_includes_plan_section(self):
        result = classify_item("generalized_feature_store")
        parsed = json.loads(result.to_json())
        assert parsed["plan_section"] == "2.2"
        assert parsed["reason_code"] == "SCOPE_ANTI_GENERALIZED_FEATURE_STORE"

    def test_rejection_trace_has_stable_reason_code(self):
        for rule in ANTI_SCOPE_RULES:
            result = classify_item(rule.key)
            assert result.reason_code.startswith("SCOPE_ANTI_")


# ---------------------------------------------------------------------------
# Classification: unknown items
# ---------------------------------------------------------------------------


class TestUnknownClassification:
    """Verify unknown items produce a clear unknown classification."""

    def test_unknown_item(self):
        result = classify_item("blockchain_ledger")
        assert result.category == ScopeCategory.UNKNOWN.value
        assert not result.is_allowed
        assert not result.is_rejected
        assert result.reason_code == "SCOPE_UNKNOWN"
        assert "not in the scope registry" in result.explanation

    def test_unknown_has_no_tier(self):
        result = classify_item("quantum_optimizer")
        assert result.tier is None


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------


class TestBatchClassification:
    """Verify batch classification works correctly."""

    def test_mixed_batch(self):
        results = classify_items([
            "nautilus_backtesting",
            "custom_matching_engine",
            "unknown_thing",
        ])
        assert len(results) == 3
        assert results[0].is_allowed
        assert results[1].is_rejected
        assert results[2].category == ScopeCategory.UNKNOWN.value

    def test_all_results_have_timestamps(self):
        results = classify_items(["candidate_freeze", "second_broker"])
        for r in results:
            assert r.timestamp  # ISO-8601 timestamp present

    def test_all_results_serialize(self):
        results = classify_items(get_all_anti_scope_keys())
        for r in results:
            parsed = json.loads(r.to_json())
            assert parsed["category"] == "anti_scope"
