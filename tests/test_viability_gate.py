"""Contract tests for the early execution-lane viability gate.

Verifies that:
  - the gate checks all five lane behaviors named in Plan v3.8 section 2.5
  - pass scenarios produce structured diagnostic reports with continue outcome
  - fail scenarios produce narrow/pivot/terminate outcomes
  - a failed gate does not silently allow continuation
  - reports include individual lane-check results and operator-readable rationale

Coverage required by bead backtesting_engine-ltc.1.5.
"""

from __future__ import annotations

import json

import pytest

from shared.policy.viability_gate import (
    GateOutcome,
    LaneCheckID,
    LaneCheckResult,
    ViabilityGateReport,
    check_deterministic_bar_construction,
    check_end_to_end_dummy_flow,
    check_execution_symbol_tradability,
    check_market_data_entitlement,
    check_no_lane_blockers,
    evaluate_viability_gate,
)


# All-passing evidence
ALL_PASSING = dict(
    oz1_entitled=True,
    session_coverage_verified=True,
    ibkr_setup_confirmed=True,
    data_profile_release_approved=True,
    bar_construction_deterministic=True,
    opsd_routing_ok=True,
    paper_routing_ok=True,
    shadow_live_suppression_ok=True,
    statement_ingestion_ok=True,
    reconciliation_ok=True,
    oz1_tradable_by_session_class=True,
    account_type_ok=True,
    permissions_ok=True,
    contract_definition_ok=True,
    operational_reset_ok=True,
)


# ---------------------------------------------------------------------------
# Individual lane checks
# ---------------------------------------------------------------------------


class TestMarketDataEntitlement:
    """LC01: 1OZ market-data entitlement and session coverage."""

    def test_pass_all_verified(self):
        r = check_market_data_entitlement(
            oz1_entitled=True,
            session_coverage_verified=True,
            ibkr_setup_confirmed=True,
        )
        assert r.passed
        assert r.reason_code == "VIABILITY_LC01_MARKET_DATA"

    def test_fail_not_entitled(self):
        r = check_market_data_entitlement(
            oz1_entitled=False,
            session_coverage_verified=True,
            ibkr_setup_confirmed=True,
        )
        assert not r.passed
        assert "oz1_entitled" in r.diagnostic

    def test_trace_has_evidence(self):
        r = check_market_data_entitlement(
            oz1_entitled=True,
            session_coverage_verified=False,
            ibkr_setup_confirmed=True,
        )
        parsed = json.loads(r.to_json())
        assert parsed["evidence"]["session_coverage_verified"] is False


class TestDeterministicBarConstruction:
    """LC02: Deterministic bar construction."""

    def test_pass(self):
        r = check_deterministic_bar_construction(
            data_profile_release_approved=True,
            bar_construction_deterministic=True,
        )
        assert r.passed
        assert r.reason_code == "VIABILITY_LC02_BAR_CONSTRUCTION"

    def test_fail_non_deterministic(self):
        r = check_deterministic_bar_construction(
            data_profile_release_approved=True,
            bar_construction_deterministic=False,
        )
        assert not r.passed


class TestEndToEndDummyFlow:
    """LC03: End-to-end dummy-strategy flow."""

    def test_pass_all_ok(self):
        r = check_end_to_end_dummy_flow(
            opsd_routing_ok=True,
            paper_routing_ok=True,
            shadow_live_suppression_ok=True,
            statement_ingestion_ok=True,
            reconciliation_ok=True,
        )
        assert r.passed
        assert r.reason_code == "VIABILITY_LC03_DUMMY_FLOW"

    def test_fail_reconciliation(self):
        r = check_end_to_end_dummy_flow(
            opsd_routing_ok=True,
            paper_routing_ok=True,
            shadow_live_suppression_ok=True,
            statement_ingestion_ok=True,
            reconciliation_ok=False,
        )
        assert not r.passed
        assert "reconciliation_ok" in r.diagnostic

    def test_fail_multiple(self):
        r = check_end_to_end_dummy_flow(
            opsd_routing_ok=False,
            paper_routing_ok=False,
            shadow_live_suppression_ok=True,
            statement_ingestion_ok=True,
            reconciliation_ok=True,
        )
        assert not r.passed
        assert "opsd_routing_ok" in r.diagnostic


class TestExecutionSymbolTradability:
    """LC04: Execution-symbol tradability."""

    def test_pass(self):
        r = check_execution_symbol_tradability(oz1_tradable_by_session_class=True)
        assert r.passed
        assert r.reason_code == "VIABILITY_LC04_TRADABILITY"

    def test_fail(self):
        r = check_execution_symbol_tradability(oz1_tradable_by_session_class=False)
        assert not r.passed
        assert "not tradable" in r.diagnostic


class TestNoLaneBlockers:
    """LC05: No lane blockers."""

    def test_pass_no_blockers(self):
        r = check_no_lane_blockers(
            account_type_ok=True,
            permissions_ok=True,
            contract_definition_ok=True,
            operational_reset_ok=True,
        )
        assert r.passed
        assert r.reason_code == "VIABILITY_LC05_LANE_BLOCKERS"

    def test_fail_account_type(self):
        r = check_no_lane_blockers(
            account_type_ok=False,
            permissions_ok=True,
            contract_definition_ok=True,
            operational_reset_ok=True,
        )
        assert not r.passed
        assert "account_type_ok" in r.diagnostic

    def test_fail_permissions(self):
        r = check_no_lane_blockers(
            account_type_ok=True,
            permissions_ok=False,
            contract_definition_ok=True,
            operational_reset_ok=True,
        )
        assert not r.passed


# ---------------------------------------------------------------------------
# Full gate: passing
# ---------------------------------------------------------------------------


class TestViabilityGatePassing:
    """Verify the gate passes and allows continuation when all checks pass."""

    def test_gate_passes_with_all_ok(self):
        report = evaluate_viability_gate(**ALL_PASSING)
        assert report.gate_passed
        assert report.outcome == GateOutcome.CONTINUE.value
        assert report.reason_code == "VIABILITY_GATE_PASSED"

    def test_report_has_five_checks(self):
        report = evaluate_viability_gate(**ALL_PASSING)
        assert len(report.checks) == 5
        assert report.passed_count == 5
        assert report.failed_count == 0

    def test_report_rationale_says_continue(self):
        report = evaluate_viability_gate(**ALL_PASSING)
        assert "proceed" in report.rationale.lower()

    def test_report_serializes_to_json(self):
        report = evaluate_viability_gate(**ALL_PASSING)
        parsed = json.loads(report.to_json())
        assert parsed["gate_passed"] is True
        assert parsed["outcome"] == "continue"
        assert len(parsed["checks"]) == 5

    def test_each_check_has_required_fields(self):
        report = evaluate_viability_gate(**ALL_PASSING)
        for check in report.checks:
            assert "check_id" in check
            assert "check_name" in check
            assert "passed" in check
            assert "reason_code" in check
            assert "diagnostic" in check
            assert "evidence" in check


# ---------------------------------------------------------------------------
# Full gate: failing — narrow outcome
# ---------------------------------------------------------------------------


class TestViabilityGateNarrow:
    """Verify the gate produces narrow when only bar construction fails."""

    def test_narrow_on_bar_construction_failure(self):
        evidence = dict(ALL_PASSING, bar_construction_deterministic=False)
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome == GateOutcome.NARROW.value
        assert report.reason_code == "VIABILITY_GATE_FAILED"

    def test_narrow_rationale_names_failed_check(self):
        evidence = dict(ALL_PASSING, bar_construction_deterministic=False)
        report = evaluate_viability_gate(**evidence)
        assert "deterministic_bar_construction" in report.rationale

    def test_does_not_allow_continuation(self):
        evidence = dict(ALL_PASSING, reconciliation_ok=False)
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert "must not proceed" in report.rationale.lower()


# ---------------------------------------------------------------------------
# Full gate: failing — pivot outcome
# ---------------------------------------------------------------------------


class TestViabilityGatePivot:
    """Verify the gate produces pivot on fundamental lane issues."""

    def test_pivot_on_market_data_failure(self):
        evidence = dict(ALL_PASSING, oz1_entitled=False)
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome == GateOutcome.PIVOT.value

    def test_pivot_on_tradability_failure(self):
        evidence = dict(ALL_PASSING, oz1_tradable_by_session_class=False)
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome == GateOutcome.PIVOT.value

    def test_pivot_on_lane_blockers(self):
        evidence = dict(ALL_PASSING, account_type_ok=False)
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome == GateOutcome.PIVOT.value


# ---------------------------------------------------------------------------
# Full gate: failing — terminate outcome
# ---------------------------------------------------------------------------


class TestViabilityGateTerminate:
    """Verify the gate produces terminate on multiple fundamental failures."""

    def test_terminate_on_many_failures(self):
        evidence = dict(
            ALL_PASSING,
            oz1_entitled=False,
            oz1_tradable_by_session_class=False,
            account_type_ok=False,
        )
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome == GateOutcome.TERMINATE.value

    def test_terminate_rationale_is_clear(self):
        evidence = dict(
            ALL_PASSING,
            oz1_entitled=False,
            bar_construction_deterministic=False,
            oz1_tradable_by_session_class=False,
        )
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.failed_count >= 3


# ---------------------------------------------------------------------------
# Gate failure: silent continuation prevention
# ---------------------------------------------------------------------------


class TestNoSilentContinuation:
    """Verify that a failed gate cannot silently allow continuation."""

    @pytest.mark.parametrize("field", [
        "oz1_entitled",
        "bar_construction_deterministic",
        "opsd_routing_ok",
        "oz1_tradable_by_session_class",
        "account_type_ok",
    ])
    def test_single_failure_blocks_continuation(self, field):
        evidence = dict(ALL_PASSING)
        evidence[field] = False
        report = evaluate_viability_gate(**evidence)
        assert not report.gate_passed
        assert report.outcome != GateOutcome.CONTINUE.value
        assert report.reason_code == "VIABILITY_GATE_FAILED"
        assert report.failed_count >= 1
