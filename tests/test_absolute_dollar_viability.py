"""Contract tests for the absolute-dollar viability gate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from shared.policy.absolute_dollar_viability import (
    ABSOLUTE_DOLLAR_CHECK_IDS,
    BENCHMARK_IDS,
    SENSITIVITY_SCENARIO_IDS,
    VALIDATION_ERRORS,
    AbsoluteDollarViabilityReport,
    AbsoluteDollarViabilityRequest,
    AbsoluteDollarViabilityStatus,
    evaluate_absolute_dollar_viability,
)

FIXTURE_PATH = Path("shared/fixtures/policy/absolute_dollar_viability_cases.json")


def load_cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)["cases"]


class AbsoluteDollarViabilityCatalogTests(unittest.TestCase):
    def test_catalog_has_no_internal_errors(self) -> None:
        self.assertEqual([], VALIDATION_ERRORS)
        self.assertEqual(5, len(ABSOLUTE_DOLLAR_CHECK_IDS))
        self.assertEqual(2, len(BENCHMARK_IDS))
        self.assertEqual(2, len(SENSITIVITY_SCENARIO_IDS))


class AbsoluteDollarViabilityFixtureCases(unittest.TestCase):
    def test_fixture_cases_match_expected_outputs(self) -> None:
        for case in load_cases():
            with self.subTest(case_id=case["case_id"]):
                expected_parse_error = case.get("expected_parse_error")
                if expected_parse_error is not None:
                    with self.assertRaisesRegex(ValueError, str(expected_parse_error)):
                        AbsoluteDollarViabilityRequest.from_dict(dict(case["request"]))
                    continue

                request = AbsoluteDollarViabilityRequest.from_dict(dict(case["request"]))
                report = evaluate_absolute_dollar_viability(request)
                expected = dict(case["expected"])

                self.assertEqual(expected["status"], report.status)
                self.assertEqual(expected["decision"], report.decision)
                self.assertEqual(expected["reason_code"], report.reason_code)
                self.assertEqual(
                    tuple(expected["failed_check_ids"]),
                    report.failed_check_ids,
                )

                if report.status == AbsoluteDollarViabilityStatus.INVALID.value:
                    self.assertEqual((), report.check_results)
                    continue

                if "monthly_excess_vs_passive_gold_usd" in expected:
                    self.assertAlmostEqual(
                        expected["monthly_excess_vs_passive_gold_usd"],
                        report.monthly_excess_vs_passive_gold_usd,
                    )
                if "monthly_excess_vs_cash_usd" in expected:
                    self.assertAlmostEqual(
                        expected["monthly_excess_vs_cash_usd"],
                        report.monthly_excess_vs_cash_usd,
                    )
                if "free_cash_usd" in expected:
                    self.assertAlmostEqual(expected["free_cash_usd"], report.free_cash_usd)
                if "conservative_return_on_committed_margin" in expected:
                    self.assertAlmostEqual(
                        expected["conservative_return_on_committed_margin"],
                        report.conservative_return_on_committed_margin,
                    )
                if "worst_session_loss_fraction_of_free_cash" in expected:
                    self.assertAlmostEqual(
                        expected["worst_session_loss_fraction_of_free_cash"],
                        report.worst_session_loss_fraction_of_free_cash,
                    )
                if "net_per_operator_maintenance_hour_usd" in expected:
                    self.assertAlmostEqual(
                        expected["net_per_operator_maintenance_hour_usd"],
                        report.net_per_operator_maintenance_hour_usd,
                    )
                if "lower_touch_alternative_net_per_hour_usd" in expected:
                    self.assertAlmostEqual(
                        expected["lower_touch_alternative_net_per_hour_usd"],
                        report.lower_touch_alternative_net_per_hour_usd,
                    )
                self.assertEqual(
                    expected["lower_touch_dominates"],
                    report.lower_touch_dominates,
                )
                if "sensitivity_scenario_ids" in expected:
                    self.assertEqual(
                        tuple(expected["sensitivity_scenario_ids"]),
                        tuple(item.scenario_id for item in report.sensitivity_scenarios),
                    )


class AbsoluteDollarViabilityContractTests(unittest.TestCase):
    def test_report_round_trip_preserves_benchmark_and_sensitivity_details(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "keep_when_monthly_net_is_material_and_beats_required_benchmarks"
        )
        request = AbsoluteDollarViabilityRequest.from_dict(dict(case["request"]))
        report = evaluate_absolute_dollar_viability(request)

        reparsed = AbsoluteDollarViabilityReport.from_json(report.to_json())

        self.assertEqual(report, reparsed)

    def test_check_results_cover_the_full_gate_catalog(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "pivot_when_lower_touch_alternative_dominates_after_operator_time"
        )
        report = evaluate_absolute_dollar_viability(
            AbsoluteDollarViabilityRequest.from_dict(dict(case["request"]))
        )

        self.assertEqual(ABSOLUTE_DOLLAR_CHECK_IDS, tuple(item.check_id for item in report.check_results))
        self.assertEqual(BENCHMARK_IDS, tuple(item.benchmark_id for item in report.benchmark_comparisons))
        self.assertEqual(
            SENSITIVITY_SCENARIO_IDS,
            tuple(item.scenario_id for item in report.sensitivity_scenarios),
        )

    def test_invalid_json_payloads_raise_value_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "absolute_dollar_viability_request: invalid JSON payload"
        ):
            AbsoluteDollarViabilityRequest.from_json("not-json")

        with self.assertRaisesRegex(
            ValueError, "absolute_dollar_viability_report: invalid JSON payload"
        ):
            AbsoluteDollarViabilityReport.from_json("not-json")

    def test_request_loader_rejects_boolean_schema_version(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "keep_when_monthly_net_is_material_and_beats_required_benchmarks"
        )
        payload_with_bool_schema = dict(case["request"])
        payload_with_bool_schema["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "schema_version"):
            AbsoluteDollarViabilityRequest.from_dict(payload_with_bool_schema)

    def test_request_loader_rejects_boolean_and_non_finite_numeric_values(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "keep_when_monthly_net_is_material_and_beats_required_benchmarks"
        )

        bool_equity_payload = dict(case["request"])
        bool_equity_payload["approved_starting_equity_usd"] = True
        with self.assertRaisesRegex(ValueError, "approved_starting_equity_usd"):
            AbsoluteDollarViabilityRequest.from_dict(bool_equity_payload)

        nan_margin_payload = dict(case["request"])
        nan_margin_payload["committed_margin_usd"] = float("nan")
        with self.assertRaisesRegex(ValueError, "committed_margin_usd"):
            AbsoluteDollarViabilityRequest.from_dict(nan_margin_payload)

    def test_request_loader_rejects_invalid_account_fit_status(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "keep_when_monthly_net_is_material_and_beats_required_benchmarks"
        )
        invalid_status_payload = dict(case["request"])
        invalid_status_payload["account_fit_status"] = True
        with self.assertRaisesRegex(ValueError, "True"):
            AbsoluteDollarViabilityRequest.from_dict(invalid_status_payload)

    def test_report_loader_rejects_invalid_status_bool_coercion_and_missing_timestamp(self) -> None:
        case = next(
            case
            for case in load_cases()
            if case["case_id"] == "keep_when_monthly_net_is_material_and_beats_required_benchmarks"
        )
        report_payload = evaluate_absolute_dollar_viability(
            AbsoluteDollarViabilityRequest.from_dict(dict(case["request"]))
        ).to_dict()

        invalid_status_payload = dict(report_payload)
        invalid_status_payload["status"] = "green"
        with self.assertRaisesRegex(ValueError, "green"):
            AbsoluteDollarViabilityReport.from_dict(invalid_status_payload)

        bool_lower_touch_payload = dict(report_payload)
        bool_lower_touch_payload["lower_touch_dominates"] = "false"
        with self.assertRaisesRegex(ValueError, "lower_touch_dominates"):
            AbsoluteDollarViabilityReport.from_dict(bool_lower_touch_payload)

        missing_timestamp_payload = dict(report_payload)
        missing_timestamp_payload.pop("timestamp")
        with self.assertRaisesRegex(ValueError, "timestamp"):
            AbsoluteDollarViabilityReport.from_dict(missing_timestamp_payload)

        naive_timestamp_payload = dict(report_payload)
        naive_timestamp_payload["timestamp"] = "2026-03-28T01:05:00"
        with self.assertRaisesRegex(ValueError, "timestamp"):
            AbsoluteDollarViabilityReport.from_dict(naive_timestamp_payload)


if __name__ == "__main__":
    unittest.main()
