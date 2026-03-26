"""Contract tests for fully loaded economics and recurring cost allocation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.fully_loaded_economics import (
    DIRECT_COST_COMPONENTS,
    RECURRING_COST_COMPONENTS,
    EconomicsLayer,
    FullyLoadedEconomicsReport,
    FullyLoadedEconomicsRequest,
    FullyLoadedEconomicsStatus,
    evaluate_fully_loaded_economics,
)

FIXTURE_PATH = Path("shared/fixtures/policy/fully_loaded_economics_cases.json")


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["cases"]


class FullyLoadedEconomicsFixtureCases(unittest.TestCase):
    def test_fixture_cases_match_expected_outputs(self) -> None:
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                expected_parse_error = case.get("expected_parse_error")
                if expected_parse_error is not None:
                    with self.assertRaisesRegex(ValueError, str(expected_parse_error)):
                        FullyLoadedEconomicsRequest.from_dict(dict(case["request"]))
                    continue

                request = FullyLoadedEconomicsRequest.from_dict(dict(case["request"]))
                report = evaluate_fully_loaded_economics(request)
                expected = dict(case["expected"])
                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["reason_code"], report.reason_code)

                if report.status == FullyLoadedEconomicsStatus.INVALID.value:
                    self.assertEqual(0.0, report.gross_pnl_usd)
                    self.assertEqual(0.0, report.net_direct_pnl_usd)
                    self.assertEqual(0.0, report.net_fully_loaded_pnl_usd)
                    continue

                self.assertEqual(
                    expected["liquidity_conditioning_used"],
                    report.liquidity_conditioning_used,
                )
                self.assertAlmostEqual(expected["gross_pnl_usd"], report.gross_pnl_usd)
                self.assertAlmostEqual(
                    expected["net_direct_pnl_usd"], report.net_direct_pnl_usd
                )
                self.assertAlmostEqual(
                    expected["net_fully_loaded_pnl_usd"],
                    report.net_fully_loaded_pnl_usd,
                )
                self.assertEqual(
                    expected["direct_cost_breakdown"], report.direct_cost_breakdown
                )
                self.assertEqual(
                    expected["recurring_cost_breakdown"],
                    report.recurring_cost_breakdown,
                )
                self.assertEqual(
                    expected["layer_order"],
                    [summary.layer for summary in report.layer_summaries],
                )


class FullyLoadedEconomicsContractTests(unittest.TestCase):
    def test_request_round_trip_preserves_execution_profiles_and_recurring_costs(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "heterogeneous_profiles_preserve_layered_breakdown"
        )
        request = FullyLoadedEconomicsRequest.from_dict(dict(case["request"]))

        round_trip = FullyLoadedEconomicsRequest.from_json(request.to_json())

        self.assertEqual(request, round_trip)

    def test_report_round_trip_preserves_layered_breakdowns(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "blended_profile_allowed_when_liquidity_is_not_materially_heterogeneous"
        )
        request = FullyLoadedEconomicsRequest.from_dict(dict(case["request"]))
        report = evaluate_fully_loaded_economics(request)

        parsed = FullyLoadedEconomicsReport.from_json(report.to_json())

        self.assertEqual(report, parsed)

    def test_report_contains_all_required_cost_components(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "heterogeneous_profiles_preserve_layered_breakdown"
        )
        request = FullyLoadedEconomicsRequest.from_dict(dict(case["request"]))
        report = evaluate_fully_loaded_economics(request)

        self.assertEqual(set(DIRECT_COST_COMPONENTS), set(report.direct_cost_breakdown))
        self.assertEqual(
            set(RECURRING_COST_COMPONENTS), set(report.recurring_cost_breakdown)
        )
        self.assertEqual(EconomicsLayer.GROSS.value, report.layer_summaries[0].layer)
        self.assertEqual(
            EconomicsLayer.NET_DIRECT.value,
            report.layer_summaries[1].layer,
        )
        self.assertEqual(
            EconomicsLayer.NET_FULLY_LOADED.value,
            report.layer_summaries[2].layer,
        )

    def test_invalid_json_payloads_raise_value_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "fully_loaded_economics: invalid JSON payload"
        ):
            FullyLoadedEconomicsRequest.from_json("not-json")

        with self.assertRaisesRegex(
            ValueError, "fully_loaded_economics_report: invalid JSON payload"
        ):
            FullyLoadedEconomicsReport.from_json("not-json")

