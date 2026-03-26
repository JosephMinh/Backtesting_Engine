from __future__ import annotations
import json
import unittest
from pathlib import Path

from shared.policy.viability_gate import (
    GateOutcome,
    check_fee_and_slippage_feasibility,
    check_holding_period_compatibility,
    check_quote_print_presence_by_session_class,
    check_spread_and_bar_completeness,
    check_tradable_session_coverage,
    evaluate_execution_symbol_first_viability_screen,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "fixtures"
    / "policy"
    / "viability_gate_cases.json"
)


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["execution_symbol_viability_cases"]


def build_dimension(payload: dict[str, object]):
    kind = payload["kind"]
    kwargs = {key: value for key, value in payload.items() if key != "kind"}
    if kind == "quote_print_presence":
        return check_quote_print_presence_by_session_class(**kwargs)
    if kind == "spread_and_bar_completeness":
        return check_spread_and_bar_completeness(**kwargs)
    if kind == "fee_and_slippage_feasibility":
        return check_fee_and_slippage_feasibility(**kwargs)
    if kind == "tradable_session_coverage":
        return check_tradable_session_coverage(**kwargs)
    if kind == "holding_period_compatibility":
        return check_holding_period_compatibility(**kwargs)
    raise AssertionError(f"Unknown viability dimension kind: {kind}")


class ExecutionSymbolDimensionTests(unittest.TestCase):
    def test_quote_print_presence_emits_structured_metrics(self) -> None:
        result = check_quote_print_presence_by_session_class(
            session_class="rth",
            quote_presence_ratio=0.92,
            print_presence_ratio=0.91,
            min_quote_presence_ratio=0.95,
            min_print_presence_ratio=0.95,
            data_source_reference="native_1oz_quotes_rth_2026q1",
        )

        self.assertFalse(result.passed)
        self.assertEqual("VIABILITY_SCREEN_VS01_QUOTE_PRINT_PRESENCE", result.reason_code)
        self.assertEqual(0.92, result.measured_value["quote_presence_ratio"])
        self.assertEqual(0.95, result.threshold["min_quote_presence_ratio"])
        self.assertEqual("native_1oz_quotes_rth_2026q1", result.data_source_reference)

    def test_spread_and_completeness_emits_thresholds(self) -> None:
        result = check_spread_and_bar_completeness(
            session_class="rth",
            median_spread_bps=18.0,
            max_allowed_spread_bps=20.0,
            bar_completeness_ratio=0.98,
            min_bar_completeness_ratio=0.97,
            data_source_reference="native_1oz_bars_rth_2026q1",
        )

        self.assertTrue(result.passed)
        self.assertEqual(18.0, result.measured_value["median_spread_bps"])
        self.assertEqual(20.0, result.threshold["max_allowed_spread_bps"])

    def test_fee_and_slippage_blocks_unapproved_size(self) -> None:
        result = check_fee_and_slippage_feasibility(
            session_class="rth",
            intended_contract_count=2,
            approved_contract_count=1,
            estimated_round_trip_cost_bps=18.0,
            max_allowed_round_trip_cost_bps=25.0,
            estimated_round_trip_cost_usd=4.0,
            max_allowed_round_trip_cost_usd=6.0,
            data_source_reference="oneoz_cost_surface_rth_v1",
        )

        self.assertFalse(result.passed)
        self.assertEqual(2, result.measured_value["intended_contract_count"])
        self.assertEqual(1, result.threshold["approved_contract_count"])

    def test_tradable_session_coverage_blocks_protected_window_violations(self) -> None:
        result = check_tradable_session_coverage(
            session_class="overnight",
            tradable_session_coverage_ratio=0.94,
            min_tradable_session_coverage_ratio=0.90,
            protected_windows_respected=False,
            maintenance_fence_respected=True,
            data_source_reference="oneoz_session_coverage_overnight_v1",
        )

        self.assertFalse(result.passed)
        self.assertFalse(result.measured_value["protected_windows_respected"])
        self.assertTrue(result.threshold["protected_windows_respected"])

    def test_holding_period_compatibility_reports_liquidity_support(self) -> None:
        result = check_holding_period_compatibility(
            session_class="overnight",
            intended_holding_period_minutes=120,
            liquidity_supported_holding_period_minutes=45,
            data_source_reference="oneoz_liquidity_windows_overnight_v1",
        )

        self.assertFalse(result.passed)
        self.assertEqual(120, result.measured_value["intended_holding_period_minutes"])
        self.assertEqual(120, result.threshold["min_liquidity_supported_holding_period_minutes"])


class ExecutionSymbolViabilityReportTests(unittest.TestCase):
    def test_fixture_cases_match_expected_budget_gate(self) -> None:
        for payload in load_cases():
            with self.subTest(case_id=payload["case_id"]):
                dimensions = [build_dimension(item) for item in payload["dimensions"]]
                report = evaluate_execution_symbol_first_viability_screen(
                    research_symbol=payload["research_symbol"],
                    execution_symbol=payload["execution_symbol"],
                    candidate_id=payload["candidate_id"],
                    research_artifact_id=payload["research_artifact_id"],
                    native_execution_history_obtained=payload["native_execution_history_obtained"],
                    live_or_paper_observations_obtained=payload["live_or_paper_observations_obtained"],
                    dimensions=dimensions,
                )
                expected = payload["expected"]
                self.assertEqual(
                    expected["deep_promotable_budget_allowed"],
                    report.deep_promotable_budget_allowed,
                )
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(expected["outcome_recommendation"], report.outcome_recommendation)
                self.assertEqual(expected["portability_study_required"], report.portability_study_required)

    def test_report_keeps_research_and_execution_symbols_explicit(self) -> None:
        case = load_cases()[0]
        dimensions = [build_dimension(item) for item in case["dimensions"]]
        report = evaluate_execution_symbol_first_viability_screen(
            research_symbol=case["research_symbol"],
            execution_symbol=case["execution_symbol"],
            candidate_id=case["candidate_id"],
            research_artifact_id=case["research_artifact_id"],
            native_execution_history_obtained=case["native_execution_history_obtained"],
            live_or_paper_observations_obtained=case["live_or_paper_observations_obtained"],
            dimensions=dimensions,
        )

        self.assertEqual("MGC", report.research_symbol)
        self.assertEqual("1OZ", report.execution_symbol)
        self.assertEqual("candidate-001", report.candidate_id)
        self.assertEqual("research-run-001", report.research_artifact_id)
        self.assertTrue(report.portability_study_required)

    def test_missing_native_execution_evidence_blocks_deep_budget(self) -> None:
        case = load_cases()[0]
        dimensions = [build_dimension(item) for item in case["dimensions"]]
        report = evaluate_execution_symbol_first_viability_screen(
            research_symbol=case["research_symbol"],
            execution_symbol=case["execution_symbol"],
            candidate_id=case["candidate_id"],
            research_artifact_id=case["research_artifact_id"],
            native_execution_history_obtained=False,
            live_or_paper_observations_obtained=True,
            dimensions=dimensions,
        )

        self.assertFalse(report.deep_promotable_budget_allowed)
        self.assertEqual(GateOutcome.NARROW.value, report.outcome_recommendation)
        self.assertIn("native_execution_history_obtained", report.rationale)

    def test_report_dimensions_are_structured_and_operator_readable(self) -> None:
        case = load_cases()[0]
        dimensions = [build_dimension(item) for item in case["dimensions"]]
        report = evaluate_execution_symbol_first_viability_screen(
            research_symbol=case["research_symbol"],
            execution_symbol=case["execution_symbol"],
            candidate_id=case["candidate_id"],
            research_artifact_id=case["research_artifact_id"],
            native_execution_history_obtained=case["native_execution_history_obtained"],
            live_or_paper_observations_obtained=case["live_or_paper_observations_obtained"],
            dimensions=dimensions,
        )
        payload = report.to_dict()

        self.assertEqual(5, len(payload["dimensions"]))
        for dimension in payload["dimensions"]:
            self.assertTrue(
                {
                    "dimension_id",
                    "dimension_name",
                    "passed",
                    "reason_code",
                    "diagnostic",
                    "measured_value",
                    "threshold",
                    "data_source_reference",
                    "session_class",
                }.issubset(dimension.keys())
            )


if __name__ == "__main__":
    unittest.main()
