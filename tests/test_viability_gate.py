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
    check_after_cost_degradation,
    check_bar_sufficiency,
    check_cost_sensitivity,
    check_directional_agreement,
    check_event_timing_alignment,
    check_deterministic_bar_construction,
    check_end_to_end_dummy_flow,
    check_execution_symbol_tradability,
    check_fill_sensitivity,
    check_market_data_entitlement,
    check_no_lane_blockers,
    check_passive_assumption_credibility,
    check_session_conditioned_liquidity,
    check_slippage_realism,
    check_trade_count_drift,
    check_turnover_drift,
    evaluate_fidelity_calibration,
    evaluate_lower_frequency_live_lane,
    evaluate_portability_and_native_validation,
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
        assert not parsed["evidence"]["session_coverage_verified"]


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
        assert parsed["gate_passed"]
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


# ---------------------------------------------------------------------------
# Fidelity calibration and lower-frequency live lane
# ---------------------------------------------------------------------------


class TestFidelityCalibrationDimensions:
    def test_bar_sufficiency_tracks_frequency_coverage_and_gaps(self):
        result = check_bar_sufficiency(
            session_class="rth",
            decision_interval_seconds=60,
            bar_coverage_ratio=0.99,
            min_bar_coverage_ratio=0.97,
            largest_gap_seconds=30,
            max_allowed_gap_seconds=60,
            data_source_reference="fidelity_bars_rth_2026q1",
        )

        assert result.passed
        assert result.reason_code == "FIDELITY_FC01_BAR_SUFFICIENCY"
        assert result.threshold["min_decision_interval_seconds"] == 60

    def test_slippage_realism_rejects_unrealistic_cost_surface(self):
        result = check_slippage_realism(
            session_class="overnight",
            estimated_round_trip_slippage_bps=42.0,
            max_allowed_round_trip_slippage_bps=25.0,
            estimated_round_trip_slippage_usd=8.0,
            max_allowed_round_trip_slippage_usd=6.0,
            data_source_reference="fidelity_cost_surface_overnight_v1",
        )

        assert not result.passed
        assert "estimated_round_trip_slippage_bps" in result.diagnostic

    def test_passive_assumption_credibility_reports_both_thresholds(self):
        result = check_passive_assumption_credibility(
            session_class="rth",
            passive_fill_ratio=0.84,
            min_passive_fill_ratio=0.80,
            adverse_selection_bps=2.0,
            max_adverse_selection_bps=3.0,
            data_source_reference="fidelity_passive_rth_v1",
        )

        payload = json.loads(result.to_json())
        assert payload["passed"]
        assert payload["threshold"]["min_passive_fill_ratio"] == 0.80
        assert payload["threshold"]["max_adverse_selection_bps"] == 3.0

    def test_session_conditioned_liquidity_rejects_blended_assumptions(self):
        result = check_session_conditioned_liquidity(
            session_class="overnight",
            session_surface_documented=True,
            separate_session_surface_used=False,
            session_liquidity_supported=True,
            data_source_reference="fidelity_liquidity_overnight_v1",
        )

        assert not result.passed
        assert "separate_session_surface_used" in result.diagnostic


class TestLowerFrequencyLiveLane:
    def test_live_lane_accepts_bar_based_one_minute_strategy(self):
        report = evaluate_lower_frequency_live_lane(
            strategy_class_id="slow_bar_momentum",
            decision_interval_seconds=60,
            uses_bar_based_logic=True,
            uses_one_bar_late_decisions=False,
            depends_on_order_book_imbalance=False,
            requires_queue_position_edge=False,
            requires_sub_minute_market_making=False,
            requires_premium_live_depth_data=False,
        )

        assert report.live_lane_eligible
        assert report.reason_code == "LOWER_FREQUENCY_LIVE_LANE_ELIGIBLE"
        assert report.failed_count == 0

    @pytest.mark.parametrize(
        ("kwargs", "expected_reason_code", "diagnostic_fragment"),
        [
            (
                {
                    "decision_interval_seconds": 30,
                    "uses_bar_based_logic": True,
                    "uses_one_bar_late_decisions": False,
                    "depends_on_order_book_imbalance": False,
                    "requires_queue_position_edge": False,
                    "requires_sub_minute_market_making": False,
                    "requires_premium_live_depth_data": False,
                },
                "LOWER_LIVE_LANE_LL01_FREQUENCY",
                "Decision interval 30s",
            ),
            (
                {
                    "decision_interval_seconds": 60,
                    "uses_bar_based_logic": False,
                    "uses_one_bar_late_decisions": False,
                    "depends_on_order_book_imbalance": False,
                    "requires_queue_position_edge": False,
                    "requires_sub_minute_market_making": False,
                    "requires_premium_live_depth_data": False,
                },
                "LOWER_LIVE_LANE_LL02_BAR_TYPE",
                "not bar-based or one-bar-late",
            ),
            (
                {
                    "decision_interval_seconds": 60,
                    "uses_bar_based_logic": True,
                    "uses_one_bar_late_decisions": False,
                    "depends_on_order_book_imbalance": False,
                    "requires_queue_position_edge": True,
                    "requires_sub_minute_market_making": False,
                    "requires_premium_live_depth_data": False,
                },
                "LOWER_LIVE_LANE_LL04_QUEUE_POSITION",
                "queue-position edge",
            ),
            (
                {
                    "decision_interval_seconds": 60,
                    "uses_bar_based_logic": True,
                    "uses_one_bar_late_decisions": False,
                    "depends_on_order_book_imbalance": False,
                    "requires_queue_position_edge": False,
                    "requires_sub_minute_market_making": True,
                    "requires_premium_live_depth_data": False,
                },
                "LOWER_LIVE_LANE_LL05_SUB_MINUTE",
                "sub-minute market-making",
            ),
        ],
    )
    def test_live_lane_exclusions_are_explicit(self, kwargs, expected_reason_code, diagnostic_fragment):
        report = evaluate_lower_frequency_live_lane(
            strategy_class_id="candidate",
            **kwargs,
        )

        assert not report.live_lane_eligible
        assert expected_reason_code in report.exclusion_reason_codes
        assert any(
            diagnostic_fragment in check["diagnostic"]
            for check in report.checks
            if not check["passed"]
        )


class TestFidelityCalibrationReport:
    def test_fidelity_calibration_passes_with_structured_supporting_references(self):
        dimensions = [
            check_bar_sufficiency(
                session_class="rth",
                decision_interval_seconds=60,
                bar_coverage_ratio=0.99,
                min_bar_coverage_ratio=0.97,
                largest_gap_seconds=30,
                max_allowed_gap_seconds=60,
                data_source_reference="fidelity_bars_rth_2026q1",
            ),
            check_slippage_realism(
                session_class="rth",
                estimated_round_trip_slippage_bps=14.0,
                max_allowed_round_trip_slippage_bps=20.0,
                estimated_round_trip_slippage_usd=3.5,
                max_allowed_round_trip_slippage_usd=5.0,
                data_source_reference="fidelity_cost_surface_rth_v1",
            ),
            check_passive_assumption_credibility(
                session_class="rth",
                passive_fill_ratio=0.82,
                min_passive_fill_ratio=0.75,
                adverse_selection_bps=2.0,
                max_adverse_selection_bps=3.0,
                data_source_reference="fidelity_passive_rth_v1",
            ),
            check_session_conditioned_liquidity(
                session_class="rth",
                session_surface_documented=True,
                separate_session_surface_used=True,
                session_liquidity_supported=True,
                data_source_reference="fidelity_liquidity_rth_v1",
            ),
        ]

        report = evaluate_fidelity_calibration(
            strategy_class_id="slow_bar_momentum",
            calibration_evidence_report_id="fidelity-report-001",
            dimensions=dimensions,
            decision_interval_seconds=60,
            uses_bar_based_logic=True,
            uses_one_bar_late_decisions=False,
            depends_on_order_book_imbalance=False,
            requires_queue_position_edge=False,
            requires_sub_minute_market_making=False,
            requires_premium_live_depth_data=False,
        )

        assert report.promotable_for_live_lane
        assert report.reason_code == "FIDELITY_CALIBRATION_ADMISSIBLE"
        assert tuple(report.supporting_data_references) == (
            "fidelity_bars_rth_2026q1",
            "fidelity_cost_surface_rth_v1",
            "fidelity_passive_rth_v1",
            "fidelity_liquidity_rth_v1",
        )

    def test_fidelity_calibration_blocks_failed_dimensions_and_live_lane_exclusions(self):
        dimensions = [
            check_bar_sufficiency(
                session_class="overnight",
                decision_interval_seconds=60,
                bar_coverage_ratio=0.90,
                min_bar_coverage_ratio=0.97,
                largest_gap_seconds=120,
                max_allowed_gap_seconds=60,
                data_source_reference="fidelity_bars_overnight_2026q1",
            ),
            check_slippage_realism(
                session_class="overnight",
                estimated_round_trip_slippage_bps=30.0,
                max_allowed_round_trip_slippage_bps=20.0,
                estimated_round_trip_slippage_usd=8.0,
                max_allowed_round_trip_slippage_usd=5.0,
                data_source_reference="fidelity_cost_surface_overnight_v1",
            ),
            check_passive_assumption_credibility(
                session_class="overnight",
                passive_fill_ratio=0.50,
                min_passive_fill_ratio=0.75,
                adverse_selection_bps=5.0,
                max_adverse_selection_bps=3.0,
                data_source_reference="fidelity_passive_overnight_v1",
            ),
            check_session_conditioned_liquidity(
                session_class="overnight",
                session_surface_documented=True,
                separate_session_surface_used=False,
                session_liquidity_supported=False,
                data_source_reference="fidelity_liquidity_overnight_v1",
            ),
        ]

        report = evaluate_fidelity_calibration(
            strategy_class_id="queue_reactive_scalper",
            calibration_evidence_report_id="fidelity-report-002",
            dimensions=dimensions,
            decision_interval_seconds=30,
            uses_bar_based_logic=False,
            uses_one_bar_late_decisions=False,
            depends_on_order_book_imbalance=True,
            requires_queue_position_edge=True,
            requires_sub_minute_market_making=True,
            requires_premium_live_depth_data=True,
        )
        payload = json.loads(report.to_json())

        assert not report.promotable_for_live_lane
        assert report.reason_code == "FIDELITY_CALIBRATION_BLOCKED"
        assert not payload["lower_frequency_live_lane"]["live_lane_eligible"]
        assert "LOWER_LIVE_LANE_LL01_FREQUENCY" in payload["lower_frequency_live_lane"][
            "exclusion_reason_codes"
        ]
        assert "queue_reactive_scalper" in report.rationale
        assert payload["failed_count"] == 4


class TestPortabilityAndNativeValidation:
    def test_portability_dimensions_cover_all_required_axes(self):
        dimensions = [
            check_directional_agreement(
                directional_agreement_ratio=0.95,
                min_directional_agreement_ratio=0.90,
                data_source_reference="portability_directional_gold_v1",
            ),
            check_event_timing_alignment(
                median_timing_delta_seconds=6.0,
                max_median_timing_delta_seconds=15.0,
                data_source_reference="portability_timing_gold_v1",
            ),
            check_trade_count_drift(
                trade_count_drift_ratio=0.08,
                max_trade_count_drift_ratio=0.12,
                data_source_reference="portability_trade_count_gold_v1",
            ),
            check_fill_sensitivity(
                fill_sensitivity_bps=2.0,
                max_fill_sensitivity_bps=5.0,
                data_source_reference="portability_fill_gold_v1",
            ),
            check_cost_sensitivity(
                cost_sensitivity_bps=3.0,
                max_cost_sensitivity_bps=6.0,
                data_source_reference="portability_cost_gold_v1",
            ),
            check_turnover_drift(
                turnover_drift_ratio=0.05,
                max_turnover_drift_ratio=0.10,
                data_source_reference="portability_turnover_gold_v1",
            ),
            check_after_cost_degradation(
                after_cost_degradation_bps=10.0,
                max_after_cost_degradation_bps=12.0,
                data_source_reference="portability_after_cost_gold_v1",
            ),
        ]

        assert len(dimensions) == 7
        assert all(dimension.passed for dimension in dimensions)

    def test_missing_native_1oz_validation_blocks_finalist_promotion(self):
        dimensions = [
            check_directional_agreement(
                directional_agreement_ratio=0.95,
                min_directional_agreement_ratio=0.90,
                data_source_reference="portability_directional_gold_v1",
            ),
            check_event_timing_alignment(
                median_timing_delta_seconds=6.0,
                max_median_timing_delta_seconds=15.0,
                data_source_reference="portability_timing_gold_v1",
            ),
            check_trade_count_drift(
                trade_count_drift_ratio=0.08,
                max_trade_count_drift_ratio=0.12,
                data_source_reference="portability_trade_count_gold_v1",
            ),
            check_fill_sensitivity(
                fill_sensitivity_bps=2.0,
                max_fill_sensitivity_bps=5.0,
                data_source_reference="portability_fill_gold_v1",
            ),
            check_cost_sensitivity(
                cost_sensitivity_bps=3.0,
                max_cost_sensitivity_bps=6.0,
                data_source_reference="portability_cost_gold_v1",
            ),
            check_turnover_drift(
                turnover_drift_ratio=0.05,
                max_turnover_drift_ratio=0.10,
                data_source_reference="portability_turnover_gold_v1",
            ),
            check_after_cost_degradation(
                after_cost_degradation_bps=10.0,
                max_after_cost_degradation_bps=12.0,
                data_source_reference="portability_after_cost_gold_v1",
            ),
        ]

        report = evaluate_portability_and_native_validation(
            research_symbol="MGC",
            execution_symbol="1OZ",
            finalist_id="finalist-001",
            execution_symbol_viability_report_id="viability-report-001",
            execution_symbol_viability_passed=True,
            portability_study_id="portability-study-001",
            portability_dimensions=dimensions,
            sufficient_native_1oz_history_exists=True,
            native_1oz_validation_study_id=None,
            native_1oz_validation_passed=None,
        )

        assert not report.promotable_finalist_allowed
        assert report.outcome_recommendation == GateOutcome.NARROW.value
        assert report.reason_code == "NATIVE_1OZ_VALIDATION_REQUIRED"

    def test_failed_viability_screen_cannot_reach_finalist_gate(self):
        report = evaluate_portability_and_native_validation(
            research_symbol="MGC",
            execution_symbol="1OZ",
            finalist_id="finalist-002",
            execution_symbol_viability_report_id="viability-report-002",
            execution_symbol_viability_passed=False,
            portability_study_id=None,
            portability_dimensions=[],
            sufficient_native_1oz_history_exists=False,
            native_1oz_validation_study_id=None,
            native_1oz_validation_passed=None,
        )

        assert not report.promotable_finalist_allowed
        assert report.outcome_recommendation == GateOutcome.TERMINATE.value
        assert "must not be carried" in report.rationale
