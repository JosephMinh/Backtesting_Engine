"""Contract tests for the non-negotiable program guardrails.

Each test verifies that a guardrail violation is correctly detected and that
the structured decision trace contains the required fields: principle_id,
violation_type, reason_code, and diagnostic context.

Coverage required by bead backtesting_engine-ltc.1.2:
  - mutable freeze-time state
  - notebook-only promotion evidence
  - missing shared kernel
  - non-idempotent broker mutation
  - unrecoverable state
  - guardian bypass attempts
"""

from __future__ import annotations

import json

import pytest

from shared.policy.guardrails import (
    GuardrailResult,
    check_guardrail,
    check_guardian_path,
    check_idempotent_broker_mutation,
    check_mutable_freeze_time_state,
    check_notebook_only_evidence,
    check_recoverability,
    check_shared_kernel,
)
from shared.policy.principles import (
    PRINCIPLES,
    Principle,
    PrincipleID,
    ViolationType,
    get_principle,
    get_principle_by_code,
)


# ---------------------------------------------------------------------------
# Principle registry integrity
# ---------------------------------------------------------------------------


class TestPrincipleRegistry:
    """Verify the principle registry is complete and consistent."""

    def test_all_15_principles_present(self):
        assert len(PRINCIPLES) == 15

    def test_unique_ids(self):
        ids = [p.id for p in PRINCIPLES]
        assert len(ids) == len(set(ids))

    def test_unique_reason_codes(self):
        codes = [p.reason_code for p in PRINCIPLES]
        assert len(codes) == len(set(codes))

    def test_unique_short_names(self):
        names = [p.short_name for p in PRINCIPLES]
        assert len(names) == len(set(names))

    def test_every_principle_id_enum_has_entry(self):
        registered_ids = {p.id for p in PRINCIPLES}
        for pid in PrincipleID:
            assert pid in registered_ids, f"{pid} missing from PRINCIPLES"

    def test_lookup_by_id(self):
        p = get_principle(PrincipleID.P01_NO_CUSTOM_MATCHING_ENGINE)
        assert p.reason_code == "GUARDRAIL_P01_CUSTOM_MATCHING_ENGINE"

    def test_lookup_by_reason_code(self):
        p = get_principle_by_code("GUARDRAIL_P05_NOTEBOOK_ONLY_EVIDENCE")
        assert p.id == PrincipleID.P05_NO_NOTEBOOK_ONLY_EVIDENCE

    def test_lookup_unknown_id_raises(self):
        with pytest.raises(KeyError):
            get_principle_by_code("NONEXISTENT_CODE")


# ---------------------------------------------------------------------------
# Decision trace structure
# ---------------------------------------------------------------------------


class TestDecisionTraceStructure:
    """Verify that all guardrail results carry the required trace fields."""

    def test_trace_has_required_fields(self):
        result = check_guardrail(
            PrincipleID.P01_NO_CUSTOM_MATCHING_ENGINE,
            condition_met=True,
            diagnostic="Using NautilusTrader backtest engine",
        )
        d = result.to_dict()
        required = {
            "principle_id",
            "principle_name",
            "violation_type",
            "passed",
            "reason_code",
            "diagnostic",
            "timestamp",
            "context",
        }
        assert required.issubset(d.keys())

    def test_trace_serializes_to_valid_json(self):
        result = check_guardrail(
            PrincipleID.P02_NO_ADHOC_FILES,
            condition_met=False,
            diagnostic="Ad-hoc CSV found in promotable path",
            context={"file": "/data/adhoc_results.csv"},
        )
        parsed = json.loads(result.to_json())
        assert parsed["principle_id"] == "P02"
        assert parsed["passed"] is False
        assert parsed["reason_code"] == "GUARDRAIL_P02_ADHOC_PROMOTABLE_FILE"

    def test_violated_property(self):
        passing = check_guardrail(
            PrincipleID.P01_NO_CUSTOM_MATCHING_ENGINE,
            condition_met=True,
            diagnostic="ok",
        )
        failing = check_guardrail(
            PrincipleID.P01_NO_CUSTOM_MATCHING_ENGINE,
            condition_met=False,
            diagnostic="violation",
        )
        assert not passing.violated
        assert failing.violated


# ---------------------------------------------------------------------------
# Contract tests: mutable freeze-time state (P03)
# ---------------------------------------------------------------------------


class TestMutableFreezeTimeState:
    """P03: No mutable reference resolution after freeze."""

    def test_pass_when_references_resolved_and_digest_verified(self):
        result = check_mutable_freeze_time_state(
            references_are_resolved=True,
            digest_verified=True,
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P03_MUTABLE_FREEZE_TIME_STATE"
        assert result.violation_type == "mutable_freeze_time_state"

    def test_violation_when_references_unresolved(self):
        result = check_mutable_freeze_time_state(
            references_are_resolved=False,
            digest_verified=True,
        )
        assert result.violated
        assert result.principle_id == "P03"
        assert result.context["references_resolved"] is False

    def test_violation_when_digest_not_verified(self):
        result = check_mutable_freeze_time_state(
            references_are_resolved=True,
            digest_verified=False,
        )
        assert result.violated
        assert result.context["digest_verified"] is False

    def test_trace_emits_stable_reason_code(self):
        result = check_mutable_freeze_time_state(
            references_are_resolved=False,
            digest_verified=False,
        )
        trace = json.loads(result.to_json())
        assert trace["reason_code"] == "GUARDRAIL_P03_MUTABLE_FREEZE_TIME_STATE"
        assert trace["violation_type"] == "mutable_freeze_time_state"
        assert trace["passed"] is False


# ---------------------------------------------------------------------------
# Contract tests: notebook-only promotion evidence (P05)
# ---------------------------------------------------------------------------


class TestNotebookOnlyEvidence:
    """P05: No notebook-only evidence for promotion."""

    def test_pass_with_mixed_evidence_sources(self):
        result = check_notebook_only_evidence(
            evidence_sources=["notebook", "backtest_report", "paper_trade_log"],
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P05_NOTEBOOK_ONLY_EVIDENCE"

    def test_violation_with_notebook_only(self):
        result = check_notebook_only_evidence(
            evidence_sources=["notebook"],
        )
        assert result.violated
        assert result.principle_id == "P05"
        assert result.violation_type == "notebook_only_evidence"

    def test_violation_with_empty_evidence(self):
        result = check_notebook_only_evidence(
            evidence_sources=[],
        )
        assert result.violated

    def test_pass_with_non_notebook_only(self):
        result = check_notebook_only_evidence(
            evidence_sources=["backtest_report"],
        )
        assert result.passed

    def test_trace_includes_source_lists(self):
        result = check_notebook_only_evidence(
            evidence_sources=["notebook", "shadow_live_report"],
        )
        trace = json.loads(result.to_json())
        assert "notebook" in trace["context"]["evidence_sources"]
        assert "shadow_live_report" in trace["context"]["non_notebook_sources"]


# ---------------------------------------------------------------------------
# Contract tests: missing shared kernel (P10)
# ---------------------------------------------------------------------------


class TestMissingSharedKernel:
    """P10: No research/live logic fork for live-eligible strategies."""

    def test_pass_when_hashes_match(self):
        h = "sha256:abcdef1234567890"
        result = check_shared_kernel(
            research_kernel_hash=h,
            live_kernel_hash=h,
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P10_MISSING_SHARED_KERNEL"

    def test_violation_when_hashes_differ(self):
        result = check_shared_kernel(
            research_kernel_hash="sha256:aaa",
            live_kernel_hash="sha256:bbb",
        )
        assert result.violated
        assert result.principle_id == "P10"
        assert result.violation_type == "missing_shared_kernel"

    def test_violation_when_hashes_empty(self):
        result = check_shared_kernel(
            research_kernel_hash="",
            live_kernel_hash="",
        )
        assert result.violated

    def test_trace_includes_both_hashes(self):
        result = check_shared_kernel(
            research_kernel_hash="sha256:aaa",
            live_kernel_hash="sha256:bbb",
        )
        trace = json.loads(result.to_json())
        assert trace["context"]["research_kernel_hash"] == "sha256:aaa"
        assert trace["context"]["live_kernel_hash"] == "sha256:bbb"


# ---------------------------------------------------------------------------
# Contract tests: non-idempotent broker mutation (P11)
# ---------------------------------------------------------------------------


class TestNonIdempotentBrokerMutation:
    """P11: No broker mutation without durable intent identity."""

    def test_pass_with_intent_and_journal(self):
        result = check_idempotent_broker_mutation(
            intent_id="intent-001-submit",
            action="submit_order",
            is_journaled=True,
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P11_NON_IDEMPOTENT_BROKER_MUTATION"

    def test_violation_without_intent_id(self):
        result = check_idempotent_broker_mutation(
            intent_id=None,
            action="cancel_order",
            is_journaled=True,
        )
        assert result.violated
        assert result.principle_id == "P11"
        assert result.violation_type == "non_idempotent_broker_mutation"

    def test_violation_with_empty_intent_id(self):
        result = check_idempotent_broker_mutation(
            intent_id="",
            action="modify_order",
            is_journaled=True,
        )
        assert result.violated

    def test_violation_without_journal(self):
        result = check_idempotent_broker_mutation(
            intent_id="intent-002",
            action="flatten",
            is_journaled=False,
        )
        assert result.violated
        assert result.context["is_journaled"] is False

    def test_trace_includes_action_context(self):
        result = check_idempotent_broker_mutation(
            intent_id="intent-003",
            action="submit_order",
            is_journaled=True,
        )
        trace = json.loads(result.to_json())
        assert trace["context"]["action"] == "submit_order"
        assert trace["context"]["intent_id"] == "intent-003"


# ---------------------------------------------------------------------------
# Contract tests: unrecoverable state (P12)
# ---------------------------------------------------------------------------


class TestUnrecoverableState:
    """P12: No live-capable stack without operational recoverability."""

    def test_pass_when_all_controls_present(self):
        result = check_recoverability(
            backup_configured=True,
            migration_tested=True,
            clock_discipline=True,
            secrets_managed=True,
            offhost_durability=True,
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P12_UNRECOVERABLE_STATE"

    def test_violation_missing_backup(self):
        result = check_recoverability(
            backup_configured=False,
            migration_tested=True,
            clock_discipline=True,
            secrets_managed=True,
            offhost_durability=True,
        )
        assert result.violated
        assert result.context["backup_configured"] is False

    def test_violation_missing_multiple_controls(self):
        result = check_recoverability(
            backup_configured=False,
            migration_tested=False,
            clock_discipline=True,
            secrets_managed=True,
            offhost_durability=False,
        )
        assert result.violated
        trace = json.loads(result.to_json())
        ctx = trace["context"]
        assert ctx["backup_configured"] is False
        assert ctx["migration_tested"] is False
        assert ctx["offhost_durability"] is False

    def test_violation_missing_secrets(self):
        result = check_recoverability(
            backup_configured=True,
            migration_tested=True,
            clock_discipline=True,
            secrets_managed=False,
            offhost_durability=True,
        )
        assert result.violated
        assert result.principle_id == "P12"
        assert result.violation_type == "unrecoverable_state"


# ---------------------------------------------------------------------------
# Contract tests: guardian bypass (P15)
# ---------------------------------------------------------------------------


class TestGuardianBypass:
    """P15: No single-path emergency control for live safety."""

    def test_pass_with_reachable_independent_guardian(self):
        result = check_guardian_path(
            guardian_reachable=True,
            guardian_independent=True,
        )
        assert result.passed
        assert result.reason_code == "GUARDRAIL_P15_GUARDIAN_BYPASS"

    def test_violation_when_guardian_unreachable(self):
        result = check_guardian_path(
            guardian_reachable=False,
            guardian_independent=True,
        )
        assert result.violated
        assert result.principle_id == "P15"
        assert result.violation_type == "guardian_bypass"

    def test_violation_when_guardian_not_independent(self):
        result = check_guardian_path(
            guardian_reachable=True,
            guardian_independent=False,
        )
        assert result.violated
        assert result.context["guardian_independent"] is False

    def test_violation_when_both_missing(self):
        result = check_guardian_path(
            guardian_reachable=False,
            guardian_independent=False,
        )
        assert result.violated
        trace = json.loads(result.to_json())
        assert trace["passed"] is False
        assert trace["reason_code"] == "GUARDRAIL_P15_GUARDIAN_BYPASS"


# ---------------------------------------------------------------------------
# Contract tests: generic guardrail check covers remaining principles
# ---------------------------------------------------------------------------


class TestGenericGuardrailCheck:
    """Verify that check_guardrail works for all 15 principles."""

    @pytest.mark.parametrize(
        "principle_id",
        list(PrincipleID),
        ids=[p.value for p in PrincipleID],
    )
    def test_each_principle_produces_valid_trace_on_pass(self, principle_id):
        result = check_guardrail(
            principle_id,
            condition_met=True,
            diagnostic=f"Contract test pass for {principle_id.value}",
        )
        assert result.passed
        trace = json.loads(result.to_json())
        assert trace["principle_id"] == principle_id.value
        assert trace["reason_code"].startswith("GUARDRAIL_")
        assert trace["passed"] is True

    @pytest.mark.parametrize(
        "principle_id",
        list(PrincipleID),
        ids=[p.value for p in PrincipleID],
    )
    def test_each_principle_produces_valid_trace_on_violation(self, principle_id):
        result = check_guardrail(
            principle_id,
            condition_met=False,
            diagnostic=f"Contract test violation for {principle_id.value}",
            context={"test": True},
        )
        assert result.violated
        trace = json.loads(result.to_json())
        assert trace["principle_id"] == principle_id.value
        assert trace["reason_code"].startswith("GUARDRAIL_")
        assert trace["passed"] is False
        assert trace["context"]["test"] is True
